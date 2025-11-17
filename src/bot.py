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
import os
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
        self._is_running = False
        self._manager = None
        self.task = None

    async def _log(self, message):
        print(message)
        if self._manager:
            await self._manager.broadcast(message)

    async def start(self, manager):
        if self._is_running:
            await self._log("Bot is already running.")
            return
        self._manager = manager
        self._is_running = True
        self.task = asyncio.create_task(self.run())
        await self._log("Bot started successfully.")

    async def stop(self):
        if not self._is_running:
            await self._log("Bot is not running.")
            return
            
        self._is_running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass # Expected
        
        # Graceful shutdown logic moved from finally block
        if self.api:
            await self.api.disconnect()
        
        temp_file_path = "open_contracts.json.tmp"
        try:
            with open(temp_file_path, "w") as f:
                json.dump(self.open_contracts, f)
            os.replace(temp_file_path, "open_contracts.json")
        except Exception as e:
            await self._log(f"❌ Error saving open contracts: {e}")

        await self._log("Bot stopped successfully.")


    async def run(self):
        """Main asynchronous function to run the trading bot."""
        logging_utils.init_db()

        try:
            with open("open_contracts.json", "r") as f:
                self.open_contracts = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            await self._log(f"⚠️ Could not load open_contracts.json ({e}). Starting with no open contracts.")
            self.open_contracts = []

        try:
            self.api = DerivAPI(app_id=config.APP_ID)
            authorize_response = await self._authorize_api(config.API_TOKEN)
            if authorize_response.get('error'):
                log_message = f"Authorization error: {authorize_response['error']['message']}"
                logging_utils.log_trade(datetime.datetime.now(), None, None, 'error', None, None, log_message)
                await self._log(f"❌ {log_message}. Bot will exit.")
                self._is_running = False
                return

            while self._is_running:
                traded_symbols_this_cycle = set()
                try:
                    balance_response = await self._get_balance()
                    if balance_response.get('error'):
                        log_message = f"Error getting balance: {balance_response['error']['message']}"
                        logging_utils.log_trade(datetime.datetime.now(), None, None, 'error', None, None, log_message)
                        await self._log(f"❌ {log_message}. Retrying in 60 seconds.")
                        await asyncio.sleep(60)
                        continue
                    await self._log(f"💰 Account Balance: ${balance_response['balance']['balance']:.2f} {balance_response['balance']['currency']}")

                    asset_index_response = await self._get_asset_index()
                    symbols_to_trade = []
                    forex_commodities = ['frxXAUUSD', 'frxXPDUSD', 'frxXPTUSD', 'frxXAGUSD']

                    for asset in asset_index_response['asset_index']:
                        symbol = asset[0]
                        if symbol.startswith('frx') and symbol not in forex_commodities:
                            symbols_to_trade.append(symbol)
                        elif symbol.startswith('OTC_'):
                            symbols_to_trade.append(symbol)
                        elif symbol in forex_commodities:
                            symbols_to_trade.append(symbol)

                    await self._log(f"📊 Actively monitoring these symbols: {', '.join(symbols_to_trade)}")

                    market_volatility = await param_tuner.get_composite_market_volatility(self.api, symbols_to_trade)
                    self.trading_parameters = param_tuner.adjust_parameters(self.trading_parameters, market_volatility)
                    
                    performance_data = strategy_manager.get_strategy_performance()
                    self.strategies = strategy_manager.adjust_strategy_confidence(self.strategies, performance_data)

                    active_strategies = [s for s in self.strategies.values() if s.is_active]

                    results = await evaluate_symbols_strategies_batch(symbols_to_trade, self.api, active_strategies, self.strategies)

                    for result in results:
                        if result:
                            symbol = result['symbol']
                            signals = result['signals']
                            data = result['data']

                            confirmed_strategies = signals
                            total_confidence = sum(s.confidence for s in signals)

                            if len(confirmed_strategies) >= 2 and total_confidence >= config.MIN_COMBINED_CONFIDENCE:
                                try:
                                    # Pass the _log method to execute_trade
                                    await execute_trade(self.api, symbol, confirmed_strategies, balance_response, self.trading_parameters, self.open_contracts, traded_symbols_this_cycle, self.trade_cache, data, self._log)
                                except Exception as e:
                                    log_message = f"Error during trade execution for {symbol}: {e}"
                                    logging_utils.log_trade(datetime.datetime.now(), symbol, str([s.id for s in confirmed_strategies]), 'error', None, None, log_message)
                                    await self._log(f"❌ {log_message}")
                            else:
                                await self._log(f"⚠️ Not enough confirmed strategies ({len(confirmed_strategies)}) or combined confidence ({total_confidence:.2f}) below threshold ({config.MIN_COMBINED_CONFIDENCE}) for {symbol}. Skipping trade.")
                    
                    await self.monitor_open_contracts()

                    await self._log("\n😴 Cycle finished. Resting for 15 minutes...\n")
                    await asyncio.sleep(15 * 60)

                except asyncio.CancelledError:
                    await self._log("Run loop cancelled.")
                    break
                except Exception as e:
                    log_message = f"An unexpected error occurred during bot execution: {e}"
                    logging_utils.log_trade(datetime.datetime.now(), None, None, 'error', None, None, log_message)
                    await self._log(f"❌ An unexpected error occurred: {e}")
        
        except Exception as e:
            await self._log(f"❌ A critical error occurred in the run method: {e}")
        finally:
            await self._log("✅ Bot run loop finished.")

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
