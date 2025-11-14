import asyncio
import pandas as pd
import datetime
from src import logging_utils
from src.utils import retry_async, classify_market_condition
from src.indicators import get_indicators # get_indicators is needed for evaluate_symbol_strategies
from src.ml_strategy import predict_signal # Import ML prediction function

@retry_async()
async def evaluate_golden_cross(symbol, data, confidence):
    """Evaluates the Golden Cross strategy."""
    if confidence == 0:
        return False, 0.0 # Strategy disabled

    latest_data = data.iloc[-1]
    previous_data = data.iloc[-2]
    golden_cross = latest_data['SMA_10'] > latest_data['SMA_20'] and previous_data['SMA_10'] <= previous_data['SMA_20']
    if golden_cross:
        logging_utils.log_trade(datetime.datetime.now(), symbol, 'golden_cross', 'signal', None, None, None)
        print(f"🔍 Signal detected for {symbol}: Golden Cross!")
        return True, confidence  # Signal, Confidence Score
    return False, 0.0

@retry_async()
async def evaluate_rsi_dip(symbol, data, confidence):
    """Evaluates the RSI dip strategy."""
    if confidence == 0:
        return False, 0.0 # Strategy disabled

    latest_data = data.iloc[-1]
    if latest_data['RSI'] < 30:
        logging_utils.log_trade(datetime.datetime.now(), symbol, 'rsi_dip', 'signal', None, None, None)
        print(f"🔍 Signal detected for {symbol}: RSI Dip!")
        return True, confidence  # Signal, Confidence Score
    return False, 0.0

async def evaluate_macd_crossover(symbol, data, confidence):
    """Evaluates the MACD crossover strategy."""
    if confidence == 0:
        return False, 0.0 # Strategy disabled

    latest_data = data.iloc[-1]
    previous_data = data.iloc[-2]
    if latest_data['MACD'] > latest_data['MACD_signal'] and previous_data['MACD'] <= previous_data['MACD_signal']:
        logging_utils.log_trade(datetime.datetime.now(), symbol, 'macd_crossover', 'signal', None, None, None)
        print(f"🔍 Signal detected for {symbol}: MACD Crossover!")
        return True, confidence  # Signal, Confidence Score
    return False, 0.0

async def evaluate_bollinger_breakout(symbol, data, confidence):
    """Evaluates the Bollinger Bands breakout strategy."""
    if confidence == 0:
        return False, 0.0 # Strategy disabled

    latest_data = data.iloc[-1]
    if latest_data['close'] > latest_data['BB_high']:
        logging_utils.log_trade(datetime.datetime.now(), symbol, 'bollinger_breakout', 'signal', None, None, None)
        print(f"🔍 Signal detected for {symbol}: Bollinger Bands Breakout!")
        return True, confidence  # Signal, Confidence Score
    return False, 0.0

@retry_async()
async def evaluate_awesome_oscillator(symbol, data, confidence):
    """Evaluates the Awesome Oscillator strategy."""
    if confidence == 0:
        return False, 0.0 # Strategy disabled

    latest_data = data.iloc[-1]
    previous_data = data.iloc[-2]
    if latest_data['Awesome_Oscillator'] > 0 and previous_data['Awesome_Oscillator'] <= 0:
        logging_utils.log_trade(datetime.datetime.now(), symbol, 'awesome_oscillator', 'signal', None, None, None)
        print(f"🔍 Signal detected for {symbol}: Awesome Oscillator Crossover!")
        return True, confidence  # Signal, Confidence Score
    return False, 0.0

@retry_async()
async def evaluate_ml_prediction(symbol, data, confidence):
    """Evaluates the ML prediction strategy."""
    if confidence == 0:
        return False, 0.0 # Strategy disabled

    signal, ml_confidence = predict_signal(data)
    if signal == "buy":
        logging_utils.log_trade(datetime.datetime.now(), symbol, 'ml_prediction', 'signal', None, None, None)
        print(f"🔍 Signal detected for {symbol}: ML Buy Prediction! Confidence: {ml_confidence:.2f}")
        return True, confidence * ml_confidence # Combine strategy confidence with ML confidence
    elif signal == "sell":
        logging_utils.log_trade(datetime.datetime.now(), symbol, 'ml_prediction', 'signal', None, None, None)
        print(f"🔍 Signal detected for {symbol}: ML Sell Prediction! Confidence: {ml_confidence:.2f}")
        return True, confidence * ml_confidence # Combine strategy confidence with ML confidence
    return False, 0.0

@retry_async()
async def evaluate_symbols_strategies_batch(symbols, api, active_strategies, all_strategies):
    """Evaluates all strategies for a given list of symbols concurrently."""
    results = []
    tasks = []

    for symbol in symbols:
        tasks.append(api.ticks_history({
            'ticks_history': symbol,
            'end': 'latest',
            'count': 200,
            'style': 'candles',
            'granularity': 86400  # 1 day
        }))
    
    responses = await asyncio.gather(*tasks, return_exceptions=True)

    for i, response in enumerate(responses):
        symbol = symbols[i]
        if isinstance(response, Exception):
            log_message = f"Error getting historical data for {symbol}: {response}"
            logging_utils.log_trade(datetime.datetime.now(), symbol, None, 'error', None, None, log_message)
            print(f"❌ {log_message}")
            continue

        if response.get('error'):
            log_message = f"Error getting historical data for {symbol}: {response['error']['message']}"
            logging_utils.log_trade(datetime.datetime.now(), symbol, None, 'error', None, None, log_message)
            print(f"❌ {log_message}")
            continue

        if not response.get('candles'):
            print(f"⚠️ No historical data found for {symbol}.")
            continue

        data = pd.DataFrame(response['candles'])
        data['epoch'] = pd.to_datetime(data['epoch'], unit='s')

        # Calculate indicators
        data = get_indicators(data)

        # Classify market condition for the symbol
        market_condition = classify_market_condition(data)

        # Select strategies based on market condition
        selected_strategies = []
        if market_condition == "trending":
            for s in active_strategies:
                if s.name in ["Golden Cross", "MACD Crossover", "Awesome Oscillator"]:
                    selected_strategies.append(s)
        elif market_condition == "ranging":
            for s in active_strategies:
                if s.name in ["RSI Dip", "Bollinger Breakout"]:
                    selected_strategies.append(s)
        elif market_condition == "volatile":
            for s in active_strategies:
                if s.name == "Bollinger Breakout":
                    selected_strategies.append(s)
        
        # Always add ML strategy if it's active
        for s in active_strategies:
            if s.name == "ML Prediction":
                selected_strategies.append(s)
        
        if not selected_strategies:
            print(f"⚠️ No active strategies selected for market condition: {market_condition} on symbol {symbol}. Attempting to select a fallback strategy.")
            
            fallback_strategy = None
            max_confidence = -1

            # Iterate through all strategies to find the highest confidence one matching the market condition
            for strategy_obj in all_strategies.values():
                if strategy_obj.is_active: # Only consider active strategies for fallback
                    # Check if the strategy matches the current market condition
                    if market_condition == "trending" and (strategy_obj.func == evaluate_golden_cross or strategy_obj.func == evaluate_macd_crossover):
                        if strategy_obj.confidence > max_confidence:
                            max_confidence = strategy_obj.confidence
                            fallback_strategy = strategy_obj
                    elif market_condition == "ranging" and (strategy_obj.func == evaluate_rsi_dip or strategy_obj.func == evaluate_bollinger_breakout):
                        if strategy_obj.confidence > max_confidence:
                            max_confidence = strategy_obj.confidence
                            fallback_strategy = strategy_obj
                    elif market_condition == "volatile" and strategy_obj.func == evaluate_bollinger_breakout:
                        if strategy_obj.confidence > max_confidence:
                            max_confidence = strategy_obj.confidence
                            fallback_strategy = strategy_obj
            
            if fallback_strategy:
                selected_strategies.append(fallback_strategy)
                print(f"Fallback strategy '{fallback_strategy.name}' selected for {symbol} due to lack of qualified strategies.")
            else:
                print(f"⚠️ No fallback strategy found for {symbol} with market condition: {market_condition}.")
                continue # Continue to the next symbol

        # Evaluate strategies
        signals = []
        for strategy_obj in selected_strategies:
            signal, confidence = await strategy_obj.func(symbol, data, strategy_obj.confidence) # Pass strategy_obj.confidence
            if signal:
                signals.append(strategy_obj) # Append the whole strategy object
        
        if signals:
            results.append({'symbol': symbol, 'signals': signals, 'data': data})
    
    return results
