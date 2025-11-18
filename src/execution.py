from src.logging_utils import log_new_trade
import datetime
import time
import json
from src import config
from src.risk import calculate_lot_size
from deriv_api import DerivAPI
from deriv_api.errors import ResponseError
from src.utils import retry_async, get_valid_durations

@retry_async
async def sell_contract(api, contract_id, log_func):
    """Sells an open contract."""
    try:
        sell_response = await api.sell({'sell': contract_id, 'price': 0}) # Price 0 means sell at market price
        if sell_response.get('error'):
            error_message = sell_response['error']['message']
            if "Resale of this contract is not offered" in error_message:
                await log_func(f"⚠️ Early exit for contract {contract_id} not offered: {error_message}. Continuing to monitor.")
                return None # Indicate that the sell was not successful, but not a critical error
            else:
                await log_func(f"❌ Error selling contract {contract_id}: {error_message}")
                return None
        await log_func(f"✅ Successfully sold contract {contract_id}.")
        return sell_response
    except Exception as e:
        await log_func(f"❌ Exception while selling contract {contract_id}: {e}")
        return None

@retry_async
async def execute_trade(api, symbol, confirmed_strategies, balance_response, trading_parameters, open_contracts, traded_symbols_this_cycle, trade_cache, data, log_func, user_id: int):
    """Executes a trade based on confirmed strategies."""
    strategy_ids_tuple = tuple(sorted([s.id for s in confirmed_strategies]))
    try:
        await log_func(f"Multi-strategy confirmation for {symbol}. Strategies: {[s.name for s in confirmed_strategies]}, Total Confidence: {sum(s.confidence for s in confirmed_strategies)}")

        # Check cache
        if (symbol, strategy_ids_tuple) in trade_cache:
            last_trade_time, last_trade_conditions = trade_cache[(symbol, strategy_ids_tuple)]
            if time.time() - last_trade_time < trading_parameters['cooldown_period']:
                log_message = f"Cooldown period for {symbol} - {[s.name for s in confirmed_strategies]} has not passed yet. Skipping trade."
                await log_func(f"❌ Trade for {symbol} skipped: Cooldown period for {[s.name for s in confirmed_strategies]} has not passed yet.")
                return

        # Check if symbol already traded this cycle
        if symbol in traded_symbols_this_cycle:
            log_message = f"Symbol {symbol} already traded this cycle. Skipping trade."
            await log_func(f"❌ Trade for {symbol} skipped: Already traded this cycle.")
            return
        
        # Calculate lot size
        num_lots, amount_per_lot = calculate_lot_size(balance_response['balance']['balance'], trading_parameters['risk_percentage'])

        # Adjust num_lots based on MAX_OPEN_CONTRACTS
        remaining_capacity = config.MAX_OPEN_CONTRACTS - len(open_contracts)
        if remaining_capacity <= 0:
            await log_func(f"⚠️ Maximum number of open contracts ({config.MAX_OPEN_CONTRACTS}) already reached. Skipping new trade for {symbol}.")
            return
        
        num_lots = min(num_lots, remaining_capacity)
        
        if num_lots == 0:
            await log_func(f"⚠️ Not enough capacity to open new contracts. Skipping new trade for {symbol}.")
            return

        await log_func(f"✅ Strategy {', '.join([s.name for s in confirmed_strategies])} triggered a trade for {symbol}. Proposing {num_lots} contracts...")
        
        # Determine contract type based on signal
        contract_type = 'PUT' # Default to PUT
        for strategy_obj in confirmed_strategies:
            # Assuming strategy_obj.func returns (signal, confidence)
            # and we need to infer the signal type from the strategy's intent
            # This is a simplification; a more robust solution would pass signal type explicitly
            if 'buy' in strategy_obj.name.lower() or 'call' in strategy_obj.name.lower(): # Heuristic for now
                contract_type = 'CALL'
                break

        # Dynamically determine duration
        valid_durations = await get_valid_durations(api, symbol, contract_type)
        
        selected_duration = None
        selected_duration_unit = None

        target_duration_hours = 4
        target_duration_minutes = target_duration_hours * 60

        # Prioritize days, then hours, then minutes
        for unit_preference in ['d', 'h', 'm']:
            if unit_preference in valid_durations:
                for duration_range in valid_durations[unit_preference]:
                    min_val = duration_range['min']
                    max_val = duration_range['max']

                    if unit_preference == 'd':
                        # Try to find 1 day within the range, otherwise pick the largest valid day duration
                        if min_val <= 1 <= max_val:
                            selected_duration = 1
                            selected_duration_unit = 'd'
                            break
                        elif max_val >= 1: # If 1 day is not available, pick the largest valid day duration
                            selected_duration = max_val
                            selected_duration_unit = 'd'
                            break
                    elif unit_preference == 'h':
                        # Try to find 4 hours within the range, otherwise pick the largest valid hour duration
                        if min_val <= target_duration_hours <= max_val:
                            selected_duration = target_duration_hours
                            selected_duration_unit = 'h'
                            break
                        elif max_val >= 1: # If 4 hours not in range, pick the largest valid hour duration
                            selected_duration = max_val
                            selected_duration_unit = 'h'
                            break
                    elif unit_preference == 'm':
                        # Try to find 240 minutes within the range, otherwise pick the largest valid minute duration
                        if min_val <= target_duration_minutes <= max_val:
                            selected_duration = target_duration_minutes
                            selected_duration_unit = 'm'
                            break
                        elif max_val >= 1: # If 240 minutes not in range, pick the largest valid minute duration
                            selected_duration = max_val
                            selected_duration_unit = 'm'
                            break
                if selected_duration:
                    break # Break from unit_preference loop if a duration is found

        if not selected_duration:
            await log_func(f"❌ No suitable duration found for {symbol} with contract type {contract_type}. Skipping trade. Valid durations: {valid_durations}")
            return

        # Propose and buy contracts
        for i in range(num_lots):
            # Re-check capacity before each buy attempt within the num_lots loop
            if len(open_contracts) >= config.MAX_OPEN_CONTRACTS:
                await log_func(f"⚠️ Maximum number of open contracts ({config.MAX_OPEN_CONTRACTS}) reached during multi-lot execution. Stopping further buys for {symbol}.")
                break

            proposal = await api.proposal({
                'proposal': 1,
                'symbol': symbol,
                'contract_type': contract_type,
                'duration': selected_duration,
                'duration_unit': selected_duration_unit,
                'currency': 'USD',
                'amount': amount_per_lot,
                'basis': 'stake'
            })
        
            if proposal.get('error'):
                await log_func(f"❌ Error getting proposal for {symbol}: {proposal['error']['message']}")
                continue
        
            if proposal['proposal']['ask_price'] > config.MAX_ASK_PRICE or proposal['proposal']['payout'] < config.MIN_PAYOUT:
                await log_func(f"❌ Proposal for {symbol} rejected: Price {proposal['proposal']['ask_price']:.2f}, Payout {proposal['proposal']['payout']:.2f} (criteria not met).")
                continue
            
            buy = await api.buy({
                'buy': proposal['proposal']['id'],
                'price': proposal['proposal']['ask_price']
            })
    
            if buy.get('error'):
                await log_func(f"❌ Error buying contract for {symbol}: {buy['error']['message']}")
            else:
                strategy_ids = [s.id for s in confirmed_strategies]
                
                # Log new trade to the database
                new_trade_log_entry = log_new_trade(
                    user_id=user_id,
                    symbol=symbol,
                    strategy=str(strategy_ids_tuple),
                    trade_type='buy',
                    entry_price=buy['buy']['buy_price'],
                    status='Open',
                    message=f"Successfully bought contract {buy['buy']['contract_id']}. Payout: {buy['buy']['payout']:.2f}"
                )
                
                await log_func(f"✅ Successfully bought contract {buy['buy']['contract_id']} for {symbol}. Payout: {buy['buy']['payout']:.2f}")
                
                contract_info = buy['buy']
                contract_info['strategy_ids'] = strategy_ids
                contract_info['trade_log_id'] = new_trade_log_entry.id # Store the trade_log_id
                
                latest_rsi = float(data.iloc[-1]['RSI'])
                contract_info['latest_rsi'] = latest_rsi
                if 'CDLENGULFING' in data.columns:
                    contract_info['latest_engulfing'] = int(data.iloc[-1]['CDLENGULFING'])
                else:
                    contract_info['latest_engulfing'] = 0

                open_contracts.append(contract_info)
                
                traded_symbols_this_cycle.add(symbol)
                trade_cache[(symbol, strategy_ids_tuple)] = (time.time(), (data.iloc[-1]['SMA_10'], data.iloc[-1]['RSI']))
    except ResponseError as e:
        log_message = f"Error processing trade for {symbol}: {e}"
        await log_func(f"❌ {log_message}")
    except Exception as e:
        log_message = f"An unexpected error occurred during trade execution for {symbol}: {e}"
        await log_func(f"❌ {log_message}")