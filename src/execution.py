import asyncio
from deriv_api import DerivAPI
from deriv_api.errors import ResponseError
from src import logging_utils
import datetime
import time
import json
from src import config
from src.risk import calculate_lot_size
from .utils import retry_async

@retry_async()
async def sell_contract(api, contract_id):
    """Sells an open contract."""
    try:
        sell_response = await api.sell({'sell': contract_id, 'price': 0}) # Price 0 means sell at market price
        if sell_response.get('error'):
            error_message = sell_response['error']['message']
            if "Resale of this contract is not offered" in error_message:
                print(f"⚠️ Early exit for contract {contract_id} not offered: {error_message}. Continuing to monitor.")
                return False # Indicate that the sell was not successful, but not a critical error
            else:
                print(f"❌ Error selling contract {contract_id}: {error_message}")
                return False
        print(f"✅ Successfully sold contract {contract_id}.")
        return True
    except Exception as e:
        print(f"❌ Exception while selling contract {contract_id}: {e}")
        return False

@retry_async()
async def execute_trade(api, symbol, confirmed_strategies, balance_response, trading_parameters, open_contracts, traded_symbols_this_cycle, trade_cache, data):
    """Executes a trade based on confirmed strategies."""
    try:
        print(f"Multi-strategy confirmation for {symbol}. Strategies: {[s.name for s in confirmed_strategies]}, Total Confidence: {sum(s.confidence for s in confirmed_strategies)}")

        # Check cache
        strategy_ids_tuple = tuple(sorted([s.id for s in confirmed_strategies]))
        if (symbol, strategy_ids_tuple) in trade_cache:
            last_trade_time, last_trade_conditions = trade_cache[(symbol, strategy_ids_tuple)]
            if time.time() - last_trade_time < trading_parameters['cooldown_period']:
                log_message = f"Cooldown period for {symbol} - {[s.name for s in confirmed_strategies]} has not passed yet. Skipping trade."
                logging_utils.log_trade(datetime.datetime.now(), symbol, str(strategy_ids_tuple), 'info', None, None, log_message)
                print(f"❌ Trade for {symbol} skipped: Cooldown period for {[s.name for s in confirmed_strategies]} has not passed yet.")
                return

        # Check if symbol already traded this cycle
        if symbol in traded_symbols_this_cycle:
            log_message = f"Symbol {symbol} already traded this cycle. Skipping trade."
            logging_utils.log_trade(datetime.datetime.now(), symbol, str(strategy_ids_tuple), 'info', None, None, log_message)
            print(f"❌ Trade for {symbol} skipped: Already traded this cycle.")
            return
        
        # Calculate lot size
        num_lots, amount_per_lot = calculate_lot_size(balance_response['balance']['balance'], trading_parameters['risk_percentage'])

        logging_utils.log_trade(datetime.datetime.now(), symbol, str(strategy_ids_tuple), 'proposal', None, None, None)
        print(f"✅ Strategy {', '.join([s.name for s in confirmed_strategies])} triggered a trade for {symbol}. Proposing {num_lots} contracts...")
        
        # Propose a contract
        for i in range(num_lots):
            proposal = await api.proposal({
                'proposal': 1,
                'symbol': symbol,
                'contract_type': 'CALL',  # Reverted to CALL as RISEFALL caused validation error
                'duration': 4,
                'duration_unit': 'h',
                'currency': 'USD',
                'amount': amount_per_lot,
                'basis': 'stake'
            })
        
            if proposal.get('error'):
                logging_utils.log_trade(datetime.datetime.now(), symbol, str(strategy_ids_tuple), 'error', None, None, proposal['error']['message'])
                print(f"❌ Error getting proposal for {symbol}: {proposal['error']['message']}")
                continue
        
            # Validate the proposal
            if proposal['proposal']['ask_price'] > config.MAX_ASK_PRICE or proposal['proposal']['payout'] < config.MIN_PAYOUT:
                logging_utils.log_trade(datetime.datetime.now(), symbol, str(strategy_ids_tuple), 'reject', proposal['proposal']['ask_price'], proposal['proposal']['payout'], None)
                print(f"❌ Proposal for {symbol} rejected: Price {proposal['proposal']['ask_price']:.2f}, Payout {proposal['proposal']['payout']:.2f} (criteria not met).")
                continue
            
            # Buy the contract
            buy = await api.buy({
                'buy': proposal['proposal']['id'],
                'price': proposal['proposal']['ask_price']
            })
    
            if buy.get('error'):
                logging_utils.log_trade(datetime.datetime.now(), symbol, str(strategy_ids_tuple), 'error', proposal['proposal']['ask_price'], proposal['proposal']['payout'], buy['error']['message'])
                print(f"❌ Error buying contract for {symbol}: {buy['error']['message']}")
            else:
                strategy_ids = [s.id for s in confirmed_strategies]
                logging_utils.log_trade(datetime.datetime.now(), symbol, str(strategy_ids_tuple), 'buy', buy['buy']['buy_price'], buy['buy']['payout'], None)
                print(f"✅ Successfully bought contract {buy['buy']['contract_id']} for {symbol}. Payout: {buy['buy']['payout']:.2f}")
                
                contract_info = buy['buy']
                contract_info['strategy_ids'] = strategy_ids
                
                # Store latest RSI and Engulfing pattern for early exit checks
                latest_rsi = float(data.iloc[-1]['RSI'])
                contract_info['latest_rsi'] = latest_rsi
                if 'CDLENGULFING' in data.columns:
                    contract_info['latest_engulfing'] = int(data.iloc[-1]['CDLENGULFING'])
                else:
                    contract_info['latest_engulfing'] = 0 # Default to 0 if not present

                open_contracts.append(contract_info)
                
                traded_symbols_this_cycle.add(symbol)
                trade_cache[(symbol, strategy_ids_tuple)] = (time.time(), (data.iloc[-1]['SMA_10'], data.iloc[-1]['RSI']))
    except ResponseError as e:
        log_message = f"Error processing trade for {symbol}: {e}"
        logging_utils.log_trade(datetime.datetime.now(), symbol, str(strategy_ids_tuple), 'error', None, None, log_message)
        print(f"❌ {log_message}")
    except Exception as e:
        log_message = f"An unexpected error occurred during trade execution for {symbol}: {e}"
        logging_utils.log_trade(datetime.datetime.now(), symbol, str(strategy_ids_tuple), 'error', None, None, log_message)
        print(f"❌ {log_message}")