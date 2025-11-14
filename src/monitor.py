import asyncio
import pandas as pd
import datetime
from deriv_api import DerivAPI
from src import logging_utils, config
from src.utils import retry_async
from src.indicators import get_indicators
from src.execution import sell_contract # Import sell_contract from execution.py

@retry_async()
async def monitor_open_contracts(api, open_contracts, trade_cache):
    """Monitors open contracts for exit conditions and logs outcomes."""
    try:
        portfolio = await api.portfolio()
        active_contracts = portfolio.get('portfolio', {}).get('contracts', [])
        active_contract_ids = {c['contract_id'] for c in active_contracts}

        # Create a new list for contracts that are still open
        updated_open_contracts = []

        for contract in open_contracts:
            contract_id = contract['contract_id']
            symbol = contract['shortcode'].split('_')[1]
            buy_price = contract['buy_price']
            payout = contract['payout']
            
            strategies_used = contract.get('strategy_ids', "Unknown")
            strategies_used_str = ', '.join(strategies_used) if isinstance(strategies_used, list) else str(strategies_used)

            if contract_id in active_contract_ids:
                updated_open_contracts.append(contract)
                try:
                    print(f"⏳ Monitoring contract {contract_id} for {symbol}...")
                    
                    # Fetch contract details to get current profit/loss
                    contract_details_response = await api.send({'proposal_open_contract': 1, 'contract_id': contract_id})
                    if contract_details_response.get('error'):
                        log_message = f"Error getting contract details for {contract_id}: {contract_details_response['error']['message']}"
                        logging_utils.log_trade(datetime.datetime.now(), symbol, strategies_used_str, 'error', buy_price, payout, log_message)
                        print(f"❌ {log_message}")
                        continue

                    contract_info = contract_details_response['proposal_open_contract']
                    profit_percentage = contract_info.get('profit_percentage', 0)
                    current_price = contract_info.get('current_spot', 0)

                    # Stop-loss and Take-profit logic
                    if contract_info.get('is_sell_available'):
                        if profit_percentage <= -config.STOP_LOSS_PERCENT:
                            log_message = f"Stop-loss triggered for {symbol} at {profit_percentage:.2f}%. Selling contract {contract_id}."
                            logging_utils.log_trade(datetime.datetime.now(), symbol, strategies_used_str, 'stop_loss', buy_price, payout, log_message)
                            print(f"🛡️ {log_message}")
                            await sell_contract(api, contract_id)
                            continue # Move to the next contract
                        
                        if profit_percentage >= config.TAKE_PROFIT_PERCENT:
                            log_message = f"Take-profit triggered for {symbol} at {profit_percentage:.2f}%. Selling contract {contract_id}."
                            logging_utils.log_trade(datetime.datetime.now(), symbol, strategies_used_str, 'take_profit', buy_price, payout, log_message)
                            print(f"🎯 {log_message}")
                            await sell_contract(api, contract_id)
                            continue # Move to the next contract

                    # Determine profitability (simplified for example)
                    # For CALL/PUT, profitability is determined at contract expiry or early exit
                    # Here, we're just checking current price vs buy price for a general idea
                    # A more complex logic would involve contract type and expiry
                    contract_type = contract['shortcode'].split('_')[0] # Extract contract type from shortcode
                    if contract_type == 'CALL':
                        is_profitable = current_price > buy_price
                    elif contract_type == 'PUT':
                        is_profitable = current_price < buy_price
                    else:
                        is_profitable = False # Handle other contract types as needed

                    outcome_message = f"Current price: {current_price}. "
                    if is_profitable:
                        outcome_message += "Currently profitable."
                    else:
                        outcome_message += "Currently unprofitable."
                    
                    logging_utils.log_trade(datetime.datetime.now(), symbol, strategies_used_str, 'monitor', buy_price, payout, outcome_message)
                    print(f"   - Current price: {current_price:.5f}. Status: {'Profitable' if is_profitable else 'Unprofitable'}.")

                    # Example early exit condition (RSI overbought/oversold)
                    # This part would require fetching historical data and calculating RSI again
                    # For simplicity, let's assume we have `data` from `evaluate_symbol_strategies`
                    # and can re-calculate RSI or pass it along with the contract.
                    # For now, I'll keep the existing RSI check as a placeholder.
                    # This needs to be refined for actual early exit logic.
                    
                    # TODO: This is inefficient as it re-fetches historical data and re-calculates indicators
                    # for every open contract on every monitoring cycle. A better approach would be to
                    # cache indicator data and reuse it.
                    # Fetch historical data for RSI check
                    ticks_history_rsi = await api.ticks_history({
                        'ticks_history': symbol,
                        'end': 'latest',
                        'count': 200,
                        'style': 'candles',
                        'granularity': 86400  # 1 day
                    })

                    if ticks_history_rsi.get('error'):
                        log_message = f"Error getting historical data for RSI check for {symbol}: {ticks_history_rsi['error']['message']}"
                        logging_utils.log_trade(datetime.datetime.now(), symbol, strategies_used_str, 'error', buy_price, payout, log_message)
                        print(f"❌ {log_message}")
                        continue

                    if not ticks_history_rsi.get('candles'):
                        print(f"⚠️ No historical data found for RSI check for {symbol}.")
                        continue

                    data_rsi = pd.DataFrame(ticks_history_rsi['candles'])
                    data_rsi['epoch'] = pd.to_datetime(data_rsi['epoch'], unit='s')
                    data_rsi = get_indicators(data_rsi)
                    latest_rsi = data_rsi.iloc[-1]['RSI']
                    
                    # Early exit condition: Engulfing pattern
                    if 'CDLENGULFING' in data_rsi.columns:
                        latest_engulfing = data_rsi.iloc[-1]['CDLENGULFING']
                        if contract_type == 'CALL' and latest_engulfing == -100:
                            log_message = f"Bearish Engulfing pattern detected for {symbol}. Initiating early exit for contract {contract_id}."
                            logging_utils.log_trade(datetime.datetime.now(), symbol, strategies_used_str, 'early_exit_signal', buy_price, payout, log_message)
                            print(f"⚠️ {log_message}")
                            if contract_info.get('is_sell_available'):
                                await sell_contract(api, contract_id)
                                continue
                        elif contract_type == 'PUT' and latest_engulfing == 100:
                            log_message = f"Bullish Engulfing pattern detected for {symbol}. Initiating early exit for contract {contract_id}."
                            logging_utils.log_trade(datetime.datetime.now(), symbol, strategies_used_str, 'early_exit_signal', buy_price, payout, log_message)
                            print(f"⚠️ {log_message}")
                            if contract_info.get('is_sell_available'):
                                await sell_contract(api, contract_id)
                                continue

                    # Early exit condition: RSI overbought/oversold
                    if contract_type == 'CALL' and latest_rsi > 70:
                        log_message = f"RSI overbought for {symbol}. Initiating early exit for contract {contract_id}."
                        logging_utils.log_trade(datetime.datetime.now(), symbol, strategies_used_str, 'early_exit_signal', buy_price, payout, log_message)
                        print(f"⚠️ {log_message}")
                        # Check if resale is available before attempting to sell
                        contract_details_response = await api.send({'proposal_open_contract': 1, 'contract_id': contract_id})
                        log_message = "" # Initialize log_message
                        if contract_details_response.get('error'):
                            log_message = f"Error getting contract details for resale check for {contract_id}: {contract_details_response['error']['message']}"
                            logging_utils.log_trade(datetime.datetime.now(), symbol, strategies_used_str, 'error', buy_price, payout, log_message)
                            print(f"❌ {log_message}")
                        else:
                            contract_info = contract_details_response['proposal_open_contract']
                            if contract_info.get('is_sell_available'):
                                if await sell_contract(api, contract_id):
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
                        contract_details_response = await api.send({'proposal_open_contract': 1, 'contract_id': contract_id})
                        log_message = "" # Initialize log_message
                        if contract_details_response.get('error'):
                            log_message = f"Error getting contract details for resale check for {contract_id}: {contract_details_response['error']['message']}"
                            logging_utils.log_trade(datetime.datetime.now(), symbol, strategies_used_str, 'error', buy_price, payout, log_message)
                            print(f"❌ {log_message}")
                        else:
                            contract_info = contract_details_response['proposal_open_contract']
                            if contract_info.get('is_sell_available'):
                                if await sell_contract(api, contract_id):
                                    # If sold successfully, remove from open_contracts
                                    # The contract will be removed from updated_open_contracts in the next cycle
                                    pass
                            else:
                                print(f"⚠️ Resale not available for contract {contract_id}. Continuing to monitor.")
                                logging_utils.log_trade(datetime.datetime.now(), symbol, strategies_used_str, 'info', buy_price, payout, f"Resale not available for contract {contract_id}.")
                except Exception as e:
                    logging_utils.log_trade(datetime.datetime.now(), symbol, strategies_used_str, 'error', buy_price, payout, f"Unhandled exception processing contract {contract_id}: {e}")
                    print(f"❌ Unhandled exception processing contract {contract_id}: {e}")
            else:
                # Contract is no longer active, it has been closed
                # Fetch contract details to determine final outcome
                contract_details_response = await api.send({'proposal_open_contract': 1, 'contract_id': contract_id})
                if contract_details_response.get('error'):
                    log_message = f"Error getting contract details for {contract_id}: {contract_details_response['error']['message']}"
                    logging_utils.log_trade(datetime.datetime.now(), symbol, strategies_used_str, 'error', buy_price, payout, log_message)
                    print(f"❌ Error getting contract details for {contract_id}: {contract_details_response['error']['message']}")
                    continue

                contract_info = contract_details_response['proposal_open_contract']
                final_payout = contract_info.get('sell_price', 0) # Use sell_price for final payout
                
                if final_payout > buy_price:
                    outcome = "win"
                    outcome_message = f"Contract {contract_id} for {symbol} WON. Payout: {final_payout:.2f}, Buy Price: {buy_price:.2f}, Profit: {(final_payout - buy_price):.2f}"
                    print(f"🎉 Contract {contract_id} for {symbol} WON! Profit: {(final_payout - buy_price):.2f}")
                else:
                    outcome = "loss"
                    outcome_message = f"Contract {contract_id} for {symbol} LOST. Payout: {final_payout:.2f}, Buy Price: {buy_price:.2f}, Loss: {(buy_price - final_payout):.2f}"
                    print(f"💔 Contract {contract_id} for {symbol} LOST. Loss: {(buy_price - final_payout):.2f}")

                logging_utils.log_trade(datetime.datetime.now(), symbol, strategies_used_str, outcome, buy_price, final_payout, outcome_message)
                
                # Update strategy performance
                if isinstance(strategies_used, list):
                    for strategy_id in strategies_used:
                        logging_utils.update_strategy_performance(strategy_id, outcome)
        
        open_contracts[:] = updated_open_contracts # Update the original list
    except Exception as e:
        logging_utils.log_trade(datetime.datetime.now(), None, None, 'error', None, None, f"Error getting portfolio: {e}")
        print(f"❌ Error getting portfolio: {e}")