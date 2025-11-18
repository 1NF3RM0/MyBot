import asyncio
import json
import datetime
import copy
from deriv_api import DerivAPI
from deriv_api.errors import ResponseError
from src import config, strategy_manager
from src.logging_utils import log_new_trade, update_trade
from src.utils import get_active_symbols, retry_async
from src.strategies import evaluate_golden_cross, evaluate_rsi_dip, evaluate_macd_crossover, evaluate_bollinger_breakout, evaluate_awesome_oscillator, evaluate_ml_prediction, evaluate_symbols_strategies_batch
from src.execution import sell_contract, execute_trade

from src.strategy_definitions import BASE_STRATEGIES

class TradingBot:
    def __init__(self, user_id: int):
        self.api = None
        self.strategies = copy.deepcopy(BASE_STRATEGIES)
        self.open_contracts = []
        self.trade_cache = {}
        self.trading_parameters = {
            'cooldown_period': 3600,  # 1 hour in seconds
            'risk_percentage': 2.0,
            'stop_loss_percent': 10.0,
            'take_profit_percent': 20.0,
        }
        self._is_running = False
        self._monitor_task = None
        self.websocket = None
        self.balance = None
        self.currency = None
        self.user_id = user_id

    async def _log(self, message):
        if self.websocket:
            log_entry = {'timestamp': datetime.datetime.now().isoformat(), 'message': message}
            await self.websocket.broadcast(json.dumps(log_entry))
        print(message)

    async def start(self, websocket_manager):
        self.websocket = websocket_manager
        self._is_running = True
        await self._log("Starting bot...")
        try:
            self.api = DerivAPI(app_id=config.APP_ID)
            await self._authorize_api(config.API_TOKEN)
            await self._log("Successfully connected and authorized to Deriv API.")
            
            # Fetch account balance with timeout
            try:
                response = await asyncio.wait_for(self.api.balance(), timeout=10.0)
                if response and not response.get('error'):
                    self.balance = response['balance']['balance']
                    self.currency = response['balance']['currency']
                    await self._log(f"Account balance: {self.balance} {self.currency}")
                else:
                    error_message = response.get('error', {}).get('message', 'Unknown error')
                    await self._log(f"Error: Failed to fetch account balance: {error_message}")
            except asyncio.TimeoutError:
                await self._log("Error: Timed out while fetching account balance.")
            except Exception as e:
                await self._log(f"An error occurred while fetching account balance: {e}")

        except Exception as e:
            await self._log(f"Error connecting to Deriv API: {e}")
            self._is_running = False
            return

        self._monitor_task = asyncio.create_task(self.run())
        await self._log("Bot started successfully.")

    async def stop(self):
        self._is_running = False
        if self._monitor_task:
            self._monitor_task.cancel()
        if self.api:
            await self.api.disconnect()
        await self._log("Bot stopped successfully.")

    async def emergency_stop(self):
        await self._log("🚨 Emergency Stop initiated! Attempting to sell all open positions...")
        for contract in list(self.open_contracts):
            await self._log(f"Attempting to sell contract {contract['contract_id']}...")
            await sell_contract(self.api, contract['contract_id'], self._log)
        
        await self.stop()


    async def run(self):
        """Main asynchronous function to run the trading bot."""

        
        while self._is_running:
            try:
                await self._log("Starting new trading cycle...")
                traded_symbols_this_cycle = set()

                # Synchronize open_contracts with Deriv API
                try:
                    portfolio_response = await asyncio.wait_for(self.api.portfolio(), timeout=10.0)
                    if portfolio_response and not portfolio_response.get('error'):
                        # Filter for contracts that are still open and update self.open_contracts
                        # This assumes that contracts in portfolio_response['portfolio']['contracts']
                        # have a 'contract_id' and 'shortcode' similar to what the bot stores.
                        # We need to be careful not to overwrite bot-specific metadata.
                        deriv_open_contracts = portfolio_response.get('portfolio', {}).get('contracts', [])
                        
                        # Create a mapping of contract_id to existing bot contract info
                        bot_contract_map = {c['contract_id']: c for c in self.open_contracts}
                        
                        new_open_contracts = []
                        for deriv_contract in deriv_open_contracts:
                            contract_id = deriv_contract.get('contract_id')
                            if contract_id in bot_contract_map:
                                # If the bot is already tracking this contract, update its info
                                updated_contract = bot_contract_map[contract_id]
                                updated_contract.update(deriv_contract) # Update with latest Deriv info
                                new_open_contracts.append(updated_contract)
                            else:
                                # If the bot is not tracking this contract, add it (with minimal info)
                                # This might happen if the bot was restarted or contracts were opened externally
                                new_open_contracts.append({
                                    'contract_id': contract_id,
                                    'shortcode': deriv_contract.get('shortcode'),
                                    'buy_price': deriv_contract.get('buy_price'),
                                    'is_resale_offered': deriv_contract.get('is_sell_available', True), # Assume resaleable if not specified
                                    # Add other relevant fields if necessary for monitoring
                                })
                        self.open_contracts = new_open_contracts
                        await self._log(f"Synchronized with Deriv. Found {len(self.open_contracts)} open contracts on platform.")
                    else:
                        error_message = portfolio_response.get('error', {}).get('message', 'Unknown error')
                        await self._log(f"Error: Failed to fetch portfolio from Deriv: {error_message}")
                except asyncio.TimeoutError:
                    await self._log("Error: Timed out while fetching portfolio from Deriv.")
                except Exception as e:
                    await self._log(f"An error occurred while fetching portfolio from Deriv: {e}")
                
                # 1. Fetch active symbols with timeout
                try:
                    active_symbols = await asyncio.wait_for(get_active_symbols(self.api), timeout=15.0)
                except asyncio.TimeoutError:
                    await self._log("Error: Timed out fetching active symbols. Retrying in 60s.")
                    await asyncio.sleep(60)
                    continue
                
                await self._log(f"Found {len(active_symbols)} active symbols. Evaluating strategies...")

                # 2. Evaluate strategies in batches with timeout
                try:
                    all_proposals = await asyncio.wait_for(
                        evaluate_symbols_strategies_batch(active_symbols, self.api, self.strategies, self.strategies),
                        timeout=30.0
                    )
                except asyncio.TimeoutError:
                    await self._log("Error: Timed out evaluating strategies. Retrying in 60s.")
                    await asyncio.sleep(60)
                    continue
                
                await self._log(f"Finished evaluating. Found {len(all_proposals)} potential trade(s).")

                if not all_proposals:
                    await self._log("No valid trading signals found in this cycle.")
                    
                # Check if the maximum number of open contracts has been reached
                if len(self.open_contracts) >= config.MAX_OPEN_CONTRACTS:
                    await self._log(f"⚠️ Maximum number of open contracts ({config.MAX_OPEN_CONTRACTS}) reached. Skipping new trades this cycle.")
                    # Still monitor existing contracts and then continue to the next cycle
                    await self.monitor_open_contracts()
                    await self._log(f"Cycle finished. Waiting {config.LOOP_DELAY} seconds.")
                    await asyncio.sleep(config.LOOP_DELAY)
                    continue

                # 3. Filter and execute trades
                for proposal in all_proposals:
                    symbol = proposal['symbol']
                    
                    # Check cooldown
                    last_trade_time = self.trade_cache.get(symbol)
                    if last_trade_time and (datetime.datetime.now() - last_trade_time).total_seconds() < self.trading_parameters['cooldown_period']:
                        await self._log(f"Skipping {symbol}: Cooldown period active.")
                        continue

                    # Execute trade
                    contract = await execute_trade(
                        self.api,
                        symbol,
                        proposal['signals'],
                        {'balance': {'balance': self.balance, 'currency': self.currency}},
                        self.trading_parameters,
                        self.open_contracts,
                        traded_symbols_this_cycle,
                        self.trade_cache,
                        proposal['data'],
                        self._log,
                        self.user_id
                    )
                    if contract:
                        self.open_contracts.append(contract)
                        self.trade_cache[symbol] = datetime.datetime.now()


                # 4. Monitor open contracts using the instance method
                await self.monitor_open_contracts()
                
                await self._log(f"Cycle finished. Waiting {config.LOOP_DELAY} seconds.")
                await asyncio.sleep(config.LOOP_DELAY)

            except asyncio.CancelledError:
                await self._log("Trading loop cancelled.")
                break
            except Exception as e:
                await self._log(f"An unexpected error occurred in the main loop: {e}")
                await self._log("Restarting trading loop in 60 seconds...")
                await asyncio.sleep(60)
    
    async def update_balance_on_close(self, sell_receipt):
        """Callback to update balance when a contract is sold."""
        if self.balance is not None and 'balance_after' in sell_receipt:
            self.balance = sell_receipt['balance_after']
            await self._log(f"Contract sold. New account balance: {self.balance} {self.currency}")


    @retry_async
    async def _authorize_api(self, api_token):
        return await self.api.authorize(api_token)

    @retry_async
    async def _get_balance(self):
        return await self.api.balance()

    @retry_async
    async def _get_asset_index(self):
        return await self.api.asset_index()

    @retry_async
    async def monitor_open_contracts(self):
        """Monitors open contracts for exit conditions and logs outcomes."""
        try:
            updated_open_contracts = []
            symbol_data_cache = {}

            for contract in list(self.open_contracts):
                contract_id = contract['contract_id']
                symbol = contract['shortcode'].split('_')[1]

                # Check if trade_log_id exists. If not, this contract was likely added during synchronization
                # and wasn't initiated by this bot instance, so we can't update the local DB for it.
                trade_log_id = contract.get('trade_log_id')
                if trade_log_id is None:
                    await self._log(f"⚠️ Contract {contract_id} for {symbol} has no 'trade_log_id'. Skipping local database updates for this contract, but continuing to monitor its status on Deriv.")
                    # We still need to process the contract to see if it's closed on Deriv
                    # and remove it from open_contracts if it is.
                    pass # Continue to the rest of the loop to check Deriv status

                contract_type = contract['shortcode'].split('_')[0]
                
                strategies_used = contract.get('strategy_ids', "Unknown")
                strategies_used_str = ', '.join(strategies_used) if isinstance(strategies_used, list) else str(strategies_used)

                try:
                    contract_details_response = await self.api.send({'proposal_open_contract': 1, 'contract_id': contract_id})
                    
                    if contract_details_response.get('error'):
                        error_message = contract_details_response['error']['message']
                        if "ContractNotFound" in error_message or "InvalidContract" in error_message:
                            await self._log(f"ℹ️ Contract {contract_id} for {symbol} is no longer active. Removing from monitoring.")
                            
                            # Calculate PnL and exit price
                            final_payout = contract.get('sell_price', 0)
                            buy_price = contract.get('buy_price', 0)
                            pnl = final_payout - buy_price
                            
                            # Update the trade log entry
                            if trade_log_id:
                                update_trade(
                                    trade_id=trade_log_id,
                                    exit_price=final_payout,
                                    pnl=pnl,
                                    status='loss',
                                    message=f"Contract {contract_id} for {symbol} closed. Final Payout: {final_payout:.2f}, PnL: {pnl:.2f}"
                                )
                            
                            if isinstance(strategies_used, list):
                                for strategy_id in strategies_used:
                                    # This needs to be handled by main.py queries, not directly here
                                    pass 
                        else:
                            log_message = f"Error getting contract details for {contract_id}: {error_message}"
                            if trade_log_id:
                                update_trade(
                                    trade_id=trade_log_id,
                                    status='error',
                                    message=log_message
                                )
                            await self._log(f"❌ {log_message}")
                        continue

                    contract_info = contract_details_response['proposal_open_contract']
                    profit_percentage = contract_info.get('profit_percentage', 0)
                    current_price = contract_info.get('current_spot', 0)

                    # Check if the contract has expired/settled
                    if contract_info.get('is_sold') or contract_info.get('status') in ['won', 'lost', 'settled']:
                        # Determine final payout based on contract info
                        final_payout = contract_info.get('sell_price', contract_info.get('payout', 0))
                        buy_price = contract.get('buy_price', 0)
                        pnl = final_payout - buy_price
                        status = 'win' if pnl > 0 else ('loss' if pnl < 0 else 'draw')
                        
                        if trade_log_id:
                            update_trade(
                                trade_id=trade_log_id,
                                exit_price=final_payout,
                                pnl=pnl,
                                status=status,
                                message=f"Contract {contract_id} for {symbol} settled. Final Payout: {final_payout:.2f}, PnL: {pnl:.2f}"
                            )
                        await self._log(f"✅ Contract {contract_id} for {symbol} settled. PnL: {pnl:.2f}, Status: {status.upper()}")
                        # Update balance if it was a successful sell (is_sold is true)
                        if contract_info.get('is_sold'):
                            # The sell_response from sell_contract has 'balance_after'.
                            # For naturally settled contracts, we need to fetch the balance again or calculate.
                            # For simplicity, let's assume the balance is updated by the API automatically
                            # and we just need to refresh it.
                            try:
                                balance_response = await self.api.balance()
                                if balance_response and not balance_response.get('error'):
                                    self.balance = balance_response['balance']['balance']
                                    await self._log(f"Balance refreshed. New account balance: {self.balance} {self.currency}")
                            except Exception as bal_e:
                                await self._log(f"Error refreshing balance after contract settlement: {bal_e}")
                        continue # Move to the next contract, as this one is closed

                    # Calculate current PnL for open contracts
                    buy_price = contract.get('buy_price', 0)
                    current_pnl = current_price - buy_price
                    
                    # Update the trade log entry with current PnL
                    if trade_log_id:
                        update_trade(
                            trade_id=trade_log_id,
                            current_pnl=current_pnl,
                            status='Open', # Ensure status remains Open
                            message=f"Contract {contract_id} for {symbol} is open. Current PnL: {current_pnl:.2f}"
                        )

                    updated_open_contracts.append(contract)

                    if contract_info.get('is_sell_available') and contract.get('is_resale_offered', True):
                        if profit_percentage <= -self.trading_parameters['stop_loss_percent']:
                            log_message = f"Stop-loss triggered for {symbol} at {profit_percentage:.2f}%. Selling contract {contract_id}."
                            await self._log(f"🛡️ {log_message}")
                            sell_response = await sell_contract(self.api, contract_id, self._log)
                            if sell_response:
                                sell_price = sell_response['sell']['sold_for']
                                pnl = sell_price - contract.get('buy_price', 0)
                                if trade_log_id:
                                    update_trade(
                                        trade_id=trade_log_id,
                                        exit_price=sell_price,
                                        pnl=pnl,
                                        status='loss',
                                        message=log_message
                                    )
                                await self.update_balance_on_close(sell_response)
                            else:
                                # If sell failed, check if it was due to resale not offered
                                if "Resale of this contract is not offered" in log_message: # This log_message is from sell_contract
                                    contract['is_resale_offered'] = False
                                    await self._log(f"⚠️ Contract {contract_id} for {symbol} is not resaleable. Will continue to monitor until expiry.")
                            continue
                    elif not contract_info.get('is_sell_available'):
                        await self._log(f"⚠️ Resale not available for contract {contract_id}. Continuing to monitor.")
                        contract['is_resale_offered'] = False
                    elif not contract.get('is_resale_offered', True):
                        await self._log(f"⚠️ Contract {contract_id} for {symbol} was previously identified as not resaleable. Continuing to monitor.")
                        
                        if profit_percentage >= self.trading_parameters['take_profit_percent']:
                            log_message = f"Take-profit triggered for {symbol} at {profit_percentage:.2f}%. Selling contract {contract_id}."
                            await self._log(f"🎯 {log_message}")
                            sell_response = await sell_contract(self.api, contract_id, self._log)
                            if sell_response:
                                sell_price = sell_response['sell']['sold_for']
                                pnl = sell_price - contract.get('buy_price', 0)
                                if trade_log_id:
                                    update_trade(
                                        trade_id=trade_log_id,
                                        exit_price=sell_price,
                                        pnl=pnl,
                                        status='win',
                                        message=log_message
                                    )
                                await self.update_balance_on_close(sell_response)
                            else:
                                # If sell failed, check if it was due to resale not offered
                                if "Resale of this contract is not offered" in log_message: # This log_message is from sell_contract
                                    contract['is_resale_offered'] = False
                                    await self._log(f"⚠️ Contract {contract_id} for {symbol} is not resaleable. Will continue to monitor until expiry.")
                            continue

                    outcome_message = f"Current price: {current_price}. "
                    if profit_percentage > 0:
                        outcome_message += "Currently profitable."
                    else:
                        outcome_message += "Currently unprofitable."
                    
                    # No need to log 'monitor' action to DB, as it's not a final state
                    await self._log(f"   - Current price: {current_price:.5f}. Status: {'Profitable' if profit_percentage > 0 else 'Unprofitable'}.")

                    latest_rsi = contract.get('latest_rsi')
                    latest_engulfing = contract.get('latest_engulfing', 0)
                    
                    if latest_rsi is None:
                        await self._log(f"⚠️ RSI not available for contract {contract_id}. Skipping early exit checks based on RSI.")
                        continue

                    if latest_engulfing != 0:
                        if contract_type == 'CALL' and latest_engulfing == -100:
                            log_message = f"Bearish Engulfing pattern detected for {symbol}. Initiating early exit for contract {contract_id}."
                            await self._log(f"⚠️ {log_message}")
                            if contract_info.get('is_sell_available') and contract.get('is_resale_offered', True):
                                sell_response = await sell_contract(self.api, contract_id, self._log)
                                if sell_response:
                                    sell_price = sell_response['sell']['sold_for']
                                    pnl = sell_price - contract.get('buy_price', 0)
                                    if trade_log_id:
                                        update_trade(
                                            trade_id=trade_log_id,
                                            exit_price=sell_price,
                                            pnl=pnl,
                                            status='win' if pnl > 0 else 'loss',
                                            message=log_message
                                        )
                                    await self.update_balance_on_close(sell_response)
                                else:
                                    if "Resale of this contract is not offered" in log_message:
                                        contract['is_resale_offered'] = False
                                        await self._log(f"⚠️ Contract {contract_id} for {symbol} is not resaleable. Will continue to monitor until expiry.")
                                continue
                            elif not contract_info.get('is_sell_available'):
                                await self._log(f"⚠️ Resale not available for contract {contract_id}. Continuing to monitor.")
                                contract['is_resale_offered'] = False
                            elif not contract.get('is_resale_offered', True):
                                await self._log(f"⚠️ Contract {contract_id} for {symbol} was previously identified as not resaleable. Continuing to monitor.")
                        elif contract_type == 'PUT' and latest_engulfing == 100:
                            log_message = f"Bullish Engulfing pattern detected for {symbol}. Initiating early exit for contract {contract_id}."
                            await self._log(f"⚠️ {log_message}")
                            if contract_info.get('is_sell_available') and contract.get('is_resale_offered', True):
                                sell_response = await sell_contract(self.api, contract_id, self._log)
                                if sell_response:
                                    sell_price = sell_response['sell']['sold_for']
                                    pnl = sell_price - contract.get('buy_price', 0)
                                    if trade_log_id:
                                        update_trade(
                                            trade_id=trade_log_id,
                                            exit_price=sell_price,
                                            pnl=pnl,
                                            status='closed', # Determine win/loss based on pnl
                                            message=log_message
                                        )
                                else:
                                    if "Resale of this contract is not offered" in log_message:
                                        contract['is_resale_offered'] = False
                                        await self._log(f"⚠️ Contract {contract_id} for {symbol} is not resaleable. Will continue to monitor until expiry.")
                                continue
                            elif not contract_info.get('is_sell_available'):
                                await self._log(f"⚠️ Resale not available for contract {contract_id}. Continuing to monitor.")
                                contract['is_resale_offered'] = False
                            elif not contract.get('is_resale_offered', True):
                                await self._log(f"⚠️ Contract {contract_id} for {symbol} was previously identified as not resaleable. Continuing to monitor.")

                    if contract_type == 'CALL' and latest_rsi > 70:
                        log_message = f"RSI overbought for {symbol}. Initiating early exit for contract {contract_id}."
                        await self._log(f"⚠️ {log_message}")
                        contract_details_response = await self.api.send({'proposal_open_contract': 1, 'contract_id': contract_id})
                        if contract_details_response.get('error'):
                            log_message = f"Error getting contract details for resale check for {contract_id}: {contract_details_response['error']['message']}"
                            if trade_log_id:
                                update_trade(
                                    trade_id=trade_log_id,
                                    status='error',
                                    message=log_message
                                )
                            await self._log(f"❌ {log_message}")
                        else:
                            contract_info = contract_details_response['proposal_open_contract']
                            if contract_info.get('is_sell_available') and contract.get('is_resale_offered', True):
                                sell_response = await sell_contract(self.api, contract_id, self._log)
                                if sell_response:
                                    sell_price = sell_response['sell']['sold_for']
                                    pnl = sell_price - contract.get('buy_price', 0)
                                    if trade_log_id:
                                        update_trade(
                                            trade_id=trade_log_id,
                                            exit_price=sell_price,
                                            pnl=pnl,
                                            status='win' if pnl > 0 else 'loss',
                                            message=log_message
                                        )
                                    await self.update_balance_on_close(sell_response)
                                else:
                                    if "Resale of this contract is not offered" in log_message:
                                                                                contract['is_resale_offered'] = False
                                                                                await self._log(f"⚠️ Contract {contract_id} for {symbol} is not resaleable. Will continue to monitor until expiry.")
                                                                        else:
                                                                            await self._log(f"⚠️ Resale not available for contract {contract_id}. Continuing to monitor.")
                                                                            if trade_log_id:
                                                                                update_trade(
                                                                                    trade_id=trade_log_id,
                                                                                    message=f"Resale not available for contract {contract_id}. Continuing to monitor."
                                                                                )
                                                                            contract['is_resale_offered'] = False
                                                            elif contract_type == 'PUT' and latest_rsi < 30:                        log_message = f"RSI oversold for {symbol}. Initiating early exit for contract {contract_id}."
                        await self._log(f"⚠️ {log_message}")
                        contract_details_response = await self.api.send({'proposal_open_contract': 1, 'contract_id': contract_id})
                        if contract_details_response.get('error'):
                            log_message = f"Error getting contract details for resale check for {contract_id}: {contract_details_response['error']['message']}"
                            if trade_log_id:
                                update_trade(
                                    trade_id=trade_log_id,
                                    status='error',
                                    message=log_message
                                )
                            await self._log(f"❌ {log_message}")
                        else:
                            contract_info = contract_details_response['proposal_open_contract']
                            if contract_info.get('is_sell_available') and contract.get('is_resale_offered', True):
                                sell_response = await sell_contract(self.api, contract_id, self._log)
                                if sell_response:
                                    sell_price = sell_response['sell']['sold_for']
                                    pnl = sell_price - contract.get('buy_price', 0)
                                    if trade_log_id:
                                        update_trade(
                                            trade_id=trade_log_id,
                                            exit_price=sell_price,
                                            pnl=pnl,
                                            status='win' if pnl > 0 else 'loss',
                                            message=log_message
                                        )
                                    await self.update_balance_on_close(sell_response)
                                else:
                                    if "Resale of this contract is not offered" in log_message:
                                        contract['is_resale_offered'] = False
                                        await self._log(f"⚠️ Contract {contract_id} for {symbol} is not resaleable. Will continue to monitor until expiry.")
                            else:
                                await self._log(f"⚠️ Resale not available for contract {contract_id}. Continuing to monitor.")
                                if trade_log_id:
                                    update_trade(
                                        trade_id=trade_log_id,
                                        message=f"Resale not available for contract {contract_id}. Continuing to monitor."
                                    )
                                contract['is_resale_offered'] = False                except Exception as e:
                    log_message = f"Unhandled exception processing contract {contract_id}: {e}"
                    if trade_log_id:
                        update_trade(
                            trade_id=trade_log_id,
                            status='error',
                            message=log_message
                        )
                    await self._log(f"❌ {log_message}")
            
            self.open_contracts[:] = updated_open_contracts
        except Exception as e:
            await self._log(f"❌ Error during contract monitoring: {e}")
