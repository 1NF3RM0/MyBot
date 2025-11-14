# tests/test_indicators.py
import pandas as pd
from src.indicators import get_indicators

def make_df(prices):
    return pd.DataFrame([{'close': p} for p in prices])

def test_indicators_basic():
    prices = [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15]
    df = make_df(prices)
    df2 = get_indicators(df)
    assert 'SMA_10' in df2.columns
    assert 'RSI' in df2.columns
    assert df2['SMA_10'].iloc[-1] > 0
    assert 0 <= df2['RSI'].iloc[-1] <= 100
