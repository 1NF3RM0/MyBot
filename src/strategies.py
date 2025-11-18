import asyncio
import pandas as pd
import datetime
from src import logging_utils
from src.utils import retry_async, classify_market_condition
from src.indicators import get_indicators # get_indicators is needed for evaluate_symbol_strategies
from src.ml_strategy import predict_signal # Import ML prediction function

@retry_async
async def evaluate_golden_cross(candles):
    """Evaluates the Golden Cross strategy."""
    if len(candles) < 25: return None
    df = pd.DataFrame(candles)
    sma_short = ta.trend.SMAIndicator(df['close'], window=10).sma_series()
    sma_long = ta.trend.SMAIndicator(df['close'], window=25).sma_series()
    if sma_short.iloc[-2] < sma_long.iloc[-2] and sma_short.iloc[-1] > sma_long.iloc[-1]:
        return {'signal': 'buy', 'confidence': 0.7}
    return None

@retry_async
async def evaluate_rsi_dip(candles):
    """Evaluates the RSI Dip strategy."""
    if len(candles) < 14: return None
    df = pd.DataFrame(candles)
    rsi = ta.momentum.RSIIndicator(df['close']).rsi()
    if rsi.iloc[-1] < 45:
        return {'signal': 'buy', 'confidence': 0.6}
    return None

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

@retry_async
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

@retry_async
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

def _get_strategies_for_condition(market_condition, active_strategies, all_strategies, is_fallback=False):
    """Helper function to select strategies based on market condition."""
    strategies = []
    if market_condition == "trending":
        for s in active_strategies:
            if s.name in ["Golden Cross", "MACD Crossover", "Awesome Oscillator"]:
                strategies.append(s)
    elif market_condition == "ranging":
        for s in active_strategies:
            if s.name in ["RSI Dip", "Bollinger Breakout"]:
                strategies.append(s)
    elif market_condition == "volatile":
        for s in active_strategies:
            if s.name == "Bollinger Breakout":
                strategies.append(s)
    
    # Always add ML strategy if it's active, unless it's a fallback call and ML is not explicitly for this condition
    if not is_fallback:
        for s in active_strategies:
            if s.name == "ML Prediction":
                strategies.append(s)
    
    return strategies

async def _evaluate_single_symbol_strategies(symbol, api, active_strategies, all_strategies):
    """Evaluates all strategies for a single symbol."""
    try:
        response = await api.ticks_history({
            'ticks_history': symbol,
            'end': 'latest',
            'count': 200,
            'style': 'candles',
            'granularity': 86400  # 1 day
        })

        if response.get('error'):
            log_message = f"Error getting historical data for {symbol}: {response['error']['message']}"
            logging_utils.log_trade(datetime.datetime.now(), symbol, None, 'error', None, None, log_message)
            print(f"❌ {log_message}")
            return None

        if not response.get('candles'):
            print(f"⚠️ No historical data found for {symbol}.")
            return None

        data = pd.DataFrame(response['candles'])
        data['epoch'] = pd.to_datetime(data['epoch'], unit='s')

        # Calculate indicators
        data = get_indicators(data)

        # Classify market condition for the symbol
        market_condition = classify_market_condition(data)

        # Select strategies based on market condition
        selected_strategies = _get_strategies_for_condition(market_condition, active_strategies, all_strategies)
        
        if not selected_strategies:
            print(f"⚠️ No active strategies selected for market condition: {market_condition} on symbol {symbol}. Attempting to select a fallback strategy.")
            
            fallback_strategy = None
            max_confidence = -1

            # Find the highest confidence fallback strategy
            fallback_options = _get_strategies_for_condition(market_condition, active_strategies, all_strategies, is_fallback=True)
            for strategy_obj in fallback_options:
                if strategy_obj.confidence > max_confidence:
                    max_confidence = strategy_obj.confidence
                    fallback_strategy = strategy_obj
            
            if fallback_strategy:
                selected_strategies.append(fallback_strategy)
                print(f"Fallback strategy '{fallback_strategy.name}' selected for {symbol} due to lack of qualified strategies.")
            else:
                print(f"⚠️ No fallback strategy found for {symbol} with market condition: {market_condition}.")
                return None

        # Evaluate strategies
        signals = []
        for strategy_obj in selected_strategies:
            signal, confidence = await strategy_obj.func(symbol, data, strategy_obj.confidence) # Pass strategy_obj.confidence
            if signal:
                signals.append(strategy_obj) # Append the whole strategy object
        
        if signals:
            return {'symbol': symbol, 'signals': signals, 'data': data}
        return None
    except Exception as e:
        log_message = f"Unhandled exception during evaluation for {symbol}: {e}"
        logging_utils.log_trade(datetime.datetime.now(), symbol, None, 'error', None, None, log_message)
        print(f"❌ {log_message}")
        return None

@retry_async
async def evaluate_symbols_strategies_batch(symbols, api, active_strategies, all_strategies):
    """Evaluates all strategies for a given list of symbols concurrently."""
    tasks = [
        _evaluate_single_symbol_strategies(symbol, api, active_strategies, all_strategies)
        for symbol in symbols
    ]
    results = await asyncio.gather(*tasks)
    return [result for result in results if result is not None]
