# tests/test_strategies.py
import pytest
import pandas as pd
import asyncio
from src.strategies import golden_cross

@pytest.mark.asyncio
async def test_golden_cross_signal():
    # create a DataFrame where SMA_10 crosses above SMA_20 at final row
    close = [1]*25
    # create values so that sma10 crosses sma20 on last index
    df = pd.DataFrame({'close': close})
    # artificially set SMA columns to simulate
    df['SMA_10'] = [1 + (i/100) for i in range(len(df))]
    df['SMA_20'] = [1 + ((i-1)/100) for i in range(len(df))]
    # previous had sma10 <= sma20
    df.loc[len(df)-2, 'SMA_10'] = 1.0
    df.loc[len(df)-2, 'SMA_20'] = 1.1
    df.loc[len(df)-1, 'SMA_10'] = 1.2
    df.loc[len(df)-1, 'SMA_20'] = 1.1

    sign, conf = await golden_cross('TEST', df, 1.0)
    assert sign is True
    assert conf == 1.0
