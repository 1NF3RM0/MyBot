import pandas as pd
try:
    import talib
    TALIB_AVAILABLE = True
except ImportError:
    TALIB_AVAILABLE = False
from ta.trend import SMAIndicator, MACD
from ta.momentum import RSIIndicator, AwesomeOscillatorIndicator
from ta.volatility import BollingerBands, AverageTrueRange
from ta.trend import IchimokuIndicator, ADXIndicator

def get_indicators(data):
    """Calculates all the required technical indicators using the 'ta' library."""
    # Clean NaN values
    data = data.ffill()
    
    # SMA
    data['SMA_10'] = SMAIndicator(close=data['close'], window=10, fillna=True).sma_indicator()
    data['SMA_20'] = SMAIndicator(close=data['close'], window=20, fillna=True).sma_indicator()
    data['SMA_50'] = SMAIndicator(close=data['close'], window=50, fillna=True).sma_indicator()
    data['SMA_200'] = SMAIndicator(close=data['close'], window=200, fillna=True).sma_indicator()

    # RSI
    data['RSI'] = RSIIndicator(close=data['close'], window=14, fillna=True).rsi()

    # MACD
    macd = MACD(close=data['close'], window_slow=26, window_fast=12, window_sign=9, fillna=True)
    data['MACD'] = macd.macd()
    data['MACD_signal'] = macd.macd_signal()

    # Bollinger Bands
    bb = BollingerBands(close=data['close'], window=20, window_dev=2, fillna=True)
    data['BB_high'] = bb.bollinger_hband()
    data['BB_low'] = bb.bollinger_lband()

    # Ichimoku
    ichimoku = IchimokuIndicator(high=data['high'], low=data['low'], window1=9, window2=26, window3=52, fillna=True)
    data['Ichimoku_conv'] = ichimoku.ichimoku_conversion_line()
    data['Ichimoku_base'] = ichimoku.ichimoku_base_line()

    # ATR
    data['ATR'] = AverageTrueRange(high=data['high'], low=data['low'], close=data['close'], window=14, fillna=True).average_true_range()

    # Awesome Oscillator
    data['Awesome_Oscillator'] = AwesomeOscillatorIndicator(high=data['high'], low=data['low'], window1=5, window2=34, fillna=True).awesome_oscillator()

    # ADX
    adx = ADXIndicator(high=data['high'], low=data['low'], close=data['close'], window=14, fillna=True)
    data['ADX'] = adx.adx()

    # Candlestick Patterns
    if TALIB_AVAILABLE:
        for pattern in talib.get_function_groups()['Pattern Recognition']:
            data[pattern] = getattr(talib, pattern)(data['open'], data['high'], data['low'], data['close'])
    else:
        print("TA-Lib not found. Skipping candlestick pattern recognition.")

    return data