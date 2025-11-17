import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="pandas")

import asyncio
import pandas as pd
from deriv_api import DerivAPI
from deriv_api.errors import ResponseError
from src import config
from src.utils import retry_async, classify_market_condition
from src.indicators import get_indicators

import datetime
import os # Import the os module
from src import logging_utils
import time
import json
from src import strategy_manager
from src import param_tuner
from src.strategies import evaluate_golden_cross, evaluate_rsi_dip, evaluate_macd_crossover, evaluate_bollinger_breakout, evaluate_awesome_oscillator, evaluate_ml_prediction, evaluate_symbols_strategies_batch
from src.execution import sell_contract, execute_trade
from src.monitor import monitor_open_contracts

class TradingBot:
    def __init__(self):
        self.api = None
        self.strategies = {
            'evaluate_golden_cross': strategy_manager.Strategy('Golden Cross', evaluate_golden_cross, {}, 1.0),
            'evaluate_rsi_dip': strategy_manager.Strategy('RSI Dip', evaluate_rsi_dip, {}, 0.8),
            'evaluate_macd_crossover': strategy_manager.Strategy('MACD Crossover', evaluate_macd_crossover, {}, 0.9),
            'evaluate_bollinger_breakout': strategy_manager.Strategy('Bollinger Breakout', evaluate_bollinger_breakout, {}, 0.85),
            'evaluate_awesome_oscillator': strategy_manager.Strategy('Awesome Oscillator', evaluate_awesome_oscillator, {}, 0.8),
            'evaluate_ml_prediction': strategy_manager.Strategy('ML Prediction', evaluate_ml_prediction, {}, 0.7, is_active=True)
        }
        self.open_contracts = []
        self.trade_cache = {}
        self.trading_parameters = {
            'cooldown_period': 3600,  # 1 hour in seconds
            'sma_threshold': 0.001,
            'rsi_threshold': 1,
            'risk_percentage': 0.02
        }

    async def run(self):
        """Main asynchronous function to run the trading bot."""
        logging_utils.init_db()

        # Load open contracts from file
        try:
            with open("open_contracts.json", "r") as f:
                self.open_contracts = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"⚠️ Could not load open_contracts.json ({e}). Starting with no open contracts.")
            self.open_contracts = []

        try:
            # Initialize Deriv API once, outside the loop
            self.api = DerivAPI(app_id=config.APP_ID)

            # Authorize with your API token
            authorize_response = await self._authorize_api(config.API_TOKEN)
            if authorize_response.get('error'):
                log_message = f"Authorization error: {authorize_response['error']['message']}"
                logging_utils.log_trade(datetime.datetime.now(), None, None, 'error', None, None, log_message)
                print(f"❌ {log_message}. Bot will exit.")
                return # Exit if authorization fails

            while True:
                traded_symbols_this_cycle = set()  # Clear cache at the start of each new cycle
                try:
                    # Get account information
                    balance_response = await self._get_balance()
                    if balance_response.get('error'):
                        log_message = f"Error getting balance: {balance_response['error']['message']}"
                        logging_utils.log_trade(datetime.datetime.now(), None, None, 'error', None, None, log_message)
                        print(f"❌ {log_message}. Retrying in 60 seconds.")
                        await asyncio.sleep(60)
                        continue
                    print(f"💰 Account Balance: ${balance_response['balance']['balance']:.2f} {balance_response['balance']['currency']}")

                    # Get available symbols
                    asset_index_response = await self._get_asset_index()
                    # Filter symbols
                    symbols_to_trade = []
                    forex_commodities = ['frxXAUUSD', 'frxXPDUSD', 'frxXPTUSD', 'frxXAGUSD']

                    for asset in asset_index_response['asset_index']:
                        symbol = asset[0]
                        if symbol.startswith('frx') and symbol not in forex_commodities:
                            # This is a forex symbol (excluding gold, palladium, platinum, silver)
                            symbols_to_trade.append(symbol)
                        elif symbol.startswith('OTC_'):
                            # This is an index symbol
                            symbols_to_trade.append(symbol)
                        elif symbol in forex_commodities:
                            # These are specific commodities
                            symbols_to_trade.append(symbol)

                    print(f"📊 Actively monitoring these symbols: {', '.join(symbols_to_trade)}")

                    # Get market volatility for parameter tuning
                    market_volatility = await param_tuner.get_composite_market_volatility(self.api, symbols_to_trade)
                    self.trading_parameters = param_tuner.adjust_parameters(self.trading_parameters, market_volatility)
                    
                    # Get updated confidence scores and disabled strategies
                    performance_data = strategy_manager.get_strategy_performance()
                    self.strategies = strategy_manager.adjust_strategy_confidence(self.strategies, performance_data)

                    active_strategies = [s for s in self.strategies.values() if s.is_active]

                    results = await evaluate_symbols_strategies_batch(symbols_to_trade, self.api, active_strategies, self.strategies)

                    # Process results
                    for result in results:
                        if result:
                            symbol = result['symbol']
                            signals = result['signals']
                            data = result['data']

                            # Aggregate signals and confidence scores
                            confirmed_strategies = signals
                            total_confidence = sum(s.confidence for s in signals)

                            try:
                                await execute_trade(self.api, symbol, confirmed_strategies, balance_response, self.trading_parameters, self.open_contracts, traded_symbols_this_cycle, self.trade_cache, data)
                            except Exception as e:
                                log_message = f"Error during trade execution for {symbol}: {e}"
                                logging_utils.log_trade(datetime.datetime.now(), symbol, str([s.id for s in confirmed_strategies]), 'error', None, None, log_message)
                                print(f"❌ {log_message}")
                    # Monitor open contracts
                    await self.monitor_open_contracts()

                    print("\n😴 Cycle finished. Resting for 15 minutes...\n")
                    try:
                        await asyncio.sleep(15 * 60)
                    except asyncio.CancelledError:
                        print("Sleep interrupted by shutdown.")
                        break

                except Exception as e:
                    log_message = f"An unexpected error occurred during bot execution: {e}"
                    logging_utils.log_trade(datetime.datetime.now(), None, None, 'error', None, None, log_message)
                    print(f"❌ An unexpected error occurred: {e}")

        except KeyboardInterrupt:
            print("\n👋 Bot interrupted by user. Shutting down gracefully...")
        finally:
            # Disconnect from the API
            if self.api:
                await self.api.disconnect()
            
            # Save open contracts to a temporary file first, then rename
            temp_file_path = "open_contracts.json.tmp"
            try:
                with open(temp_file_path, "w") as f:
                    json.dump(self.open_contracts, f)
                os.replace(temp_file_path, "open_contracts.json")
            except Exception as e:
                print(f"❌ Error saving open contracts: {e}")

            print("✅ Bot shut down gracefully.")

    @retry_async()
    async def _authorize_api(self, api_token):
        return await self.api.authorize(api_token)

    @retry_async()
    async def _get_balance(self):
        return await self.api.balance()

    @retry_async()
    async def _get_asset_index(self):
        return await self.api.asset_index()

    @retry_async()
    async def monitor_open_contracts(self):
        """Monitors open contracts for exit conditions and logs outcomes."""
        try: # Outer try block starts here
            # Create a new list for contracts that are still open
            updated_open_contracts = []
            
            # Cache for historical data per symbol for this monitoring cycle
            symbol_data_cache = {}

            for contract in list(self.open_contracts): # Iterate over a copy to allow modification
                contract_id = contract['contract_id']
                symbol = contract['shortcode'].split('_')[1]
                buy_price = contract['buy_price']
                payout = contract['payout']
                contract_type = contract['shortcode'].split('_')[0] # Re-introduce contract_type extraction
                
                strategies_used = contract.get('strategy_ids', "Unknown")
                strategies_used_str = ', '.join(strategies_used) if isinstance(strategies_used, list) else str(strategies_used)

                try: # Inner try block
                    # Fetch contract details to get current profit/loss
                    contract_details_response = await self.api.send({'proposal_open_contract': 1, 'contract_id': contract_id})
                    
                    if contract_details_response.get('error'):
                        error_message = contract_details_response['error']['message']
                        if "ContractNotFound" in error_message or "InvalidContract" in error_message:
                            # Contract is no longer active (expired or sold previously)
                            print(f"ℹ️ Contract {contract_id} for {symbol} is no longer active. Removing from monitoring.")
                            # Log the final outcome if possible, otherwise log as info
                            final_payout = contract.get('sell_price', 0) # Try to get sell_price if available
                            outcome = "closed"
                            outcome_message = f"Contract {contract_id} for {symbol} closed. Final Payout: {final_payout:.2f}"
                            logging_utils.log_trade(datetime.datetime.now(), symbol, strategies_used_str, outcome, buy_price, final_payout, outcome_message)
                            
                            # Update strategy performance (assuming it was a loss if no sell_price or profit)
                            if isinstance(strategies_used, list):
                                for strategy_id in strategies_used:
                                    # This is a simplification, actual win/loss should be determined by the API
                                    logging_utils.update_strategy_performance(strategy_id, "loss") 
                        else:
                            log_message = f"Error getting contract details for {contract_id}: {error_message}"
                            logging_utils.log_trade(datetime.datetime.now(), symbol, strategies_used_str, 'error', buy_price, payout, log_message)
                            print(f"❌ {log_message}")
                        continue # Move to the next contract if it's no longer active or an error occurred

                    contract_info = contract_details_response['proposal_open_contract']
                    profit_percentage = contract_info.get('profit_percentage', 0)
                    current_price = contract_info.get('current_spot', 0)

                    # If we reach here, the contract is still active, so add it to updated_open_contracts
                    updated_open_contracts.append(contract)

                    # Stop-loss and Take-profit logic
                    if contract_info.get('is_sell_available'):
                        if profit_percentage <= -config.STOP_LOSS_PERCENT:
                            log_message = f"Stop-loss triggered for {symbol} at {profit_percentage:.2f}%. Selling contract {contract_id}."
                            logging_utils.log_trade(datetime.datetime.now(), symbol, strategies_used_str, 'stop_loss', buy_price, payout, log_message)
                            print(f"🛡️ {log_message}")
                            await sell_contract(self.api, contract_id)
                            continue # Move to the next contract
                        
                        if profit_percentage >= config.TAKE_PROFIT_PERCENT:
                            log_message = f"Take-profit triggered for {symbol} at {profit_percentage:.2f}%. Selling contract {contract_id}."
                            logging_utils.log_trade(datetime.datetime.now(), symbol, strategies_used_str, 'take_profit', buy_price, payout, log_message)
                            print(f"🎯 {log_message}")
                            await sell_contract(self.api, contract_id)
                            continue # Move to the next contract

                    outcome_message = f"Current price: {current_price}. "
                    if profit_percentage > 0:
                        outcome_message += "Currently profitable."
                    else:
                        outcome_message += "Currently unprofitable."
                    
                    logging_utils.log_trade(datetime.datetime.now(), symbol, strategies_used_str, 'monitor', buy_price, payout, outcome_message)
                    print(f"   - Current price: {current_price:.5f}. Status: {'Profitable' if profit_percentage > 0 else 'Unprofitable'}.")

                    # Use stored RSI and Engulfing pattern for early exit checks
                    latest_rsi = contract.get('latest_rsi')
                    latest_engulfing = contract.get('latest_engulfing', 0) # Default to 0 if not present
                    
                    if latest_rsi is None:
                        print(f"⚠️ RSI not available for contract {contract_id}. Skipping early exit checks based on RSI.")
                        continue

                    # Early exit condition: Engulfing pattern
                    if latest_engulfing != 0:
                        if contract_type == 'CALL' and latest_engulfing == -100:
                            log_message = f"Bearish Engulfing pattern detected for {symbol}. Initiating early exit for contract {contract_id}."
                            logging_utils.log_trade(datetime.datetime.now(), symbol, strategies_used_str, 'early_exit_signal', buy_price, payout, log_message)
                            print(f"⚠️ {log_message}")
                            if contract_info.get('is_sell_available'):
                                await sell_contract(self.api, contract_id)
                                continue
                        elif contract_type == 'PUT' and latest_engulfing == 100:
                            log_message = f"Bullish Engulfing pattern detected for {symbol}. Initiating early exit for contract {contract_id}."
                            logging_utils.log_trade(datetime.datetime.now(), symbol, strategies_used_str, 'early_exit_signal', buy_price, payout, log_message)
                            print(f"⚠️ {log_message}")
                            if contract_info.get('is_sell_available'):
                                await sell_contract(self.api, contract_id)
                                continue

                    # Early exit condition: RSI overbought/oversold
                    if contract_type == 'CALL' and latest_rsi > 70:
                        log_message = f"RSI overbought for {symbol}. Initiating early exit for contract {contract_id}."
                        logging_utils.log_trade(datetime.datetime.now(), symbol, strategies_used_str, 'early_exit_signal', buy_price, payout, log_message)
                        print(f"⚠️ {log_message}")
                        # Check if resale is available before attempting to sell
                        contract_details_response = await self.api.send({'proposal_open_contract': 1, 'contract_id': contract_id})
                        log_message = "" # Initialize log_message
                        if contract_details_response.get('error'):
                            log_message = f"Error getting contract details for resale check for {contract_id}: {contract_details_response['error']['message']}"
                            logging_utils.log_trade(datetime.datetime.now(), symbol, strategies_used_str, 'error', buy_price, payout, log_message)
                            print(f"❌ {log_message}")
                        else:
                            contract_info = contract_details_response['proposal_open_contract']
                            if contract_info.get('is_sell_available'):
                                if await sell_contract(self.api, contract_id):
                                    # If sold successfully, remove from open_contracts
                                    # The contract will be removed from updated_open_contracts in the next cycle
                                    pass
                            else:
                                print(f"⚠️ Resale not available for contract {contract_id}. Continuing to monitor.")
                                logging_utils.log_trade(datetime.datetime.now(), symbol, strategies_used_str, 'info', buy_price, payout, f"Resale not available for contract {contract_id}.")
                    elif contract_type == 'PUT' and latest_rsi < 30:
                        log_message = f"RSI oversold for {symbol}. Initiating early exit for contract {contract_id}."
                        logging_utils.log_trade(datetime.datetime.now(), symbol, strategies_used_str, 'early_exit_signal', buy_price, payout, log_message)
                        print(f"⚠️ {log_message}")
                        # Check if resale is available before attempting to sell
                        contract_details_response = await self.api.send({'proposal_open_contract': 1, 'contract_id': contract_id})
                        log_message = "" # Initialize log_message
                        if contract_details_response.get('error'):
                            log_message = f"Error getting contract details for resale check for {contract_id}: {contract_details_response['error']['message']}"
                            logging_utils.log_trade(datetime.datetime.now(), symbol, strategies_used_str, 'error', buy_price, payout, log_message)
                            print(f"❌ {log_message}")
                        else:
                            contract_info = contract_details_response['proposal_open_contract']
                            if contract_info.get('is_sell_available'):
                                if await sell_contract(self.api, contract_id):
                                    # If sold successfully, remove from open_contracts
                                    # The contract will be removed from updated_open_contracts in the next cycle
                                    pass
                            else:
                                print(f"⚠️ Resale not available for contract {contract_id}. Continuing to monitor.")
                                logging_utils.log_trade(datetime.datetime.now(), symbol, strategies_used_str, 'info', buy_price, payout, f"Resale not available for contract {contract_id}.")
                except Exception as e: # Inner except block
                    logging_utils.log_trade(datetime.datetime.now(), symbol, strategies_used_str, 'error', buy_price, payout, f"Unhandled exception processing contract {contract_id}: {e}")
                    print(f"❌ Unhandled exception processing contract {contract_id}: {e}")
            
            self.open_contracts[:] = updated_open_contracts # Update the original list
        except Exception as e: # Outer except block
            logging_utils.log_trade(datetime.datetime.now(), None, None, 'error', None, None, f"Error during contract monitoring: {e}")
            print(f"❌ Error during contract monitoring: {e}")
