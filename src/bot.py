import asyncio
import json
import datetime
import copy
from deriv_api import DerivAPI
from src import config, logging_utils, strategy_manager
from src.utils import get_active_symbols, retry_async
from src.strategies import evaluate_golden_cross, evaluate_rsi_dip, evaluate_macd_crossover, evaluate_bollinger_breakout, evaluate_awesome_oscillator, evaluate_ml_prediction, evaluate_symbols_strategies_batch
from src.execution import sell_contract, execute_trade
from src.monitor import monitor_open_contracts
from src.strategy_definitions import BASE_STRATEGIES

class TradingBot:
    def __init__(self):
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
        logging_utils.init_db()
        
        while self._is_running:
            try:
                await self._log("Starting new trading cycle...")
                traded_symbols_this_cycle = set()
                
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
                        evaluate_symbols_strategies_batch(self.api, active_symbols, self.strategies, self.strategies),
                        timeout=30.0
                    )
                except asyncio.TimeoutError:
                    await self._log("Error: Timed out evaluating strategies. Retrying in 60s.")
                    await asyncio.sleep(60)
                    continue
                
                await self._log(f"Finished evaluating. Found {len(all_proposals)} potential trade(s).")

                if not all_proposals:
                    await self._log("No valid trading signals found in this cycle.")

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
                        self._log
                    )
                    if contract:
                        self.open_contracts.append(contract)
                        self.trade_cache[symbol] = datetime.datetime.now()
                        logging_utils.log_trade(
                            timestamp=datetime.datetime.now(),
                            symbol=symbol,
                            strategy=str(proposal['strategy_ids']),
                            type='buy',
                            entry_price=contract['buy_price'],
                            status='Open',
                            pnl=0.0,
                            user_id=1 # This needs to be dynamic in a multi-user context
                        )

                # 4. Monitor open contracts
                await monitor_open_contracts(self.api, self.open_contracts, self._log, self.update_balance_on_close)
                
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
                buy_price = contract['buy_price']
                payout = contract['payout']
                contract_type = contract['shortcode'].split('_')[0]
                
                strategies_used = contract.get('strategy_ids', "Unknown")
                strategies_used_str = ', '.join(strategies_used) if isinstance(strategies_used, list) else str(strategies_used)

                try:
                    contract_details_response = await self.api.send({'proposal_open_contract': 1, 'contract_id': contract_id})
                    
                    if contract_details_response.get('error'):
                        error_message = contract_details_response['error']['message']
                        if "ContractNotFound" in error_message or "InvalidContract" in error_message:
                            await self._log(f"ℹ️ Contract {contract_id} for {symbol} is no longer active. Removing from monitoring.")
                            final_payout = contract.get('sell_price', 0)
                            outcome = "closed"
                            outcome_message = f"Contract {contract_id} for {symbol} closed. Final Payout: {final_payout:.2f}"
                            logging_utils.log_trade(datetime.datetime.now(), symbol, strategies_used_str, outcome, buy_price, final_payout, outcome_message)
                            
                            if isinstance(strategies_used, list):
                                for strategy_id in strategies_used:
                                    logging_utils.update_strategy_performance(strategy_id, "loss") 
                        else:
                            log_message = f"Error getting contract details for {contract_id}: {error_message}"
                            logging_utils.log_trade(datetime.datetime.now(), symbol, strategies_used_str, 'error', buy_price, payout, log_message)
                            await self._log(f"❌ {log_message}")
                        continue

                    contract_info = contract_details_response['proposal_open_contract']
                    profit_percentage = contract_info.get('profit_percentage', 0)
                    current_price = contract_info.get('current_spot', 0)

                    updated_open_contracts.append(contract)

                    if contract_info.get('is_sell_available'):
                        if profit_percentage <= -config.STOP_LOSS_PERCENT:
                            log_message = f"Stop-loss triggered for {symbol} at {profit_percentage:.2f}%. Selling contract {contract_id}."
                            logging_utils.log_trade(datetime.datetime.now(), symbol, strategies_used_str, 'stop_loss', buy_price, payout, log_message)
                            await self._log(f"🛡️ {log_message}")
                            await sell_contract(self.api, contract_id)
                            continue
                        
                        if profit_percentage >= config.TAKE_PROFIT_PERCENT:
                            log_message = f"Take-profit triggered for {symbol} at {profit_percentage:.2f}%. Selling contract {contract_id}."
                            logging_utils.log_trade(datetime.datetime.now(), symbol, strategies_used_str, 'take_profit', buy_price, payout, log_message)
                            await self._log(f"🎯 {log_message}")
                            await sell_contract(self.api, contract_id)
                            continue

                    outcome_message = f"Current price: {current_price}. "
                    if profit_percentage > 0:
                        outcome_message += "Currently profitable."
                    else:
                        outcome_message += "Currently unprofitable."
                    
                    logging_utils.log_trade(datetime.datetime.now(), symbol, strategies_used_str, 'monitor', buy_price, payout, outcome_message)
                    await self._log(f"   - Current price: {current_price:.5f}. Status: {'Profitable' if profit_percentage > 0 else 'Unprofitable'}.")

                    latest_rsi = contract.get('latest_rsi')
                    latest_engulfing = contract.get('latest_engulfing', 0)
                    
                    if latest_rsi is None:
                        await self._log(f"⚠️ RSI not available for contract {contract_id}. Skipping early exit checks based on RSI.")
                        continue

                    if latest_engulfing != 0:
                        if contract_type == 'CALL' and latest_engulfing == -100:
                            log_message = f"Bearish Engulfing pattern detected for {symbol}. Initiating early exit for contract {contract_id}."
                            logging_utils.log_trade(datetime.datetime.now(), symbol, strategies_used_str, 'early_exit_signal', buy_price, payout, log_message)
                            await self._log(f"⚠️ {log_message}")
                            if contract_info.get('is_sell_available'):
                                await sell_contract(self.api, contract_id)
                                continue
                        elif contract_type == 'PUT' and latest_engulfing == 100:
                            log_message = f"Bullish Engulfing pattern detected for {symbol}. Initiating early exit for contract {contract_id}."
                            logging_utils.log_trade(datetime.datetime.now(), symbol, strategies_used_str, 'early_exit_signal', buy_price, payout, log_message)
                            await self._log(f"⚠️ {log_message}")
                            if contract_info.get('is_sell_available'):
                                await sell_contract(self.api, contract_id)
                                continue

                    if contract_type == 'CALL' and latest_rsi > 70:
                        log_message = f"RSI overbought for {symbol}. Initiating early exit for contract {contract_id}."
                        logging_utils.log_trade(datetime.datetime.now(), symbol, strategies_used_str, 'early_exit_signal', buy_price, payout, log_message)
                        await self._log(f"⚠️ {log_message}")
                        contract_details_response = await self.api.send({'proposal_open_contract': 1, 'contract_id': contract_id})
                        if contract_details_response.get('error'):
                            log_message = f"Error getting contract details for resale check for {contract_id}: {contract_details_response['error']['message']}"
                            logging_utils.log_trade(datetime.datetime.now(), symbol, strategies_used_str, 'error', buy_price, payout, log_message)
                            await self._log(f"❌ {log_message}")
                        else:
                            contract_info = contract_details_response['proposal_open_contract']
                            if contract_info.get('is_sell_available'):
                                await sell_contract(self.api, contract_id)
                            else:
                                await self._log(f"⚠️ Resale not available for contract {contract_id}. Continuing to monitor.")
                                logging_utils.log_trade(datetime.datetime.now(), symbol, strategies_used_str, 'info', buy_price, payout, f"Resale not available for contract {contract_id}.")
                    elif contract_type == 'PUT' and latest_rsi < 30:
                        log_message = f"RSI oversold for {symbol}. Initiating early exit for contract {contract_id}."
                        logging_utils.log_trade(datetime.datetime.now(), symbol, strategies_used_str, 'early_exit_signal', buy_price, payout, log_message)
                        await self._log(f"⚠️ {log_message}")
                        contract_details_response = await self.api.send({'proposal_open_contract': 1, 'contract_id': contract_id})
                        if contract_details_response.get('error'):
                            log_message = f"Error getting contract details for resale check for {contract_id}: {contract_details_response['error']['message']}"
                            logging_utils.log_trade(datetime.datetime.now(), symbol, strategies_used_str, 'error', buy_price, payout, log_message)
                            await self._log(f"❌ {log_message}")
                        else:
                            contract_info = contract_details_response['proposal_open_contract']
                            if contract_info.get('is_sell_available'):
                                await sell_contract(self.api, contract_id)
                            else:
                                await self._log(f"⚠️ Resale not available for contract {contract_id}. Continuing to monitor.")
                                logging_utils.log_trade(datetime.datetime.now(), symbol, strategies_used_str, 'info', buy_price, payout, f"Resale not available for contract {contract_id}.")
                except Exception as e:
                    logging_utils.log_trade(datetime.datetime.now(), symbol, strategies_used_str, 'error', buy_price, payout, f"Unhandled exception processing contract {contract_id}: {e}")
                    await self._log(f"❌ Unhandled exception processing contract {contract_id}: {e}")
            
            self.open_contracts[:] = updated_open_contracts
        except Exception as e:
            logging_utils.log_trade(datetime.datetime.now(), None, None, 'error', None, None, f"Error during contract monitoring: {e}")
            await self._log(f"❌ Error during contract monitoring: {e}")
