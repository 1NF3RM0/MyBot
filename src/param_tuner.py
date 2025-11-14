import pandas as pd
import sqlite3
import asyncio
from src.indicators import get_indicators

async def get_market_volatility(api, symbol: str, lookback_period=200):
    """Fetches historical data and calculates market volatility using ATR.

    Args:
        api: The DerivAPI instance.
        symbol (str): The symbol to fetch historical data for.
        lookback_period (int): The number of candles to look back for ATR calculation.

    Returns:
        float: The latest ATR value, or None if data is insufficient.
    """
    try:
        ticks_history = await api.ticks_history({
            'ticks_history': symbol,
            'end': 'latest',
            'count': lookback_period,
            'style': 'candles',
            'granularity': 86400  # 1 day
        })

        if ticks_history.get('error'):
            print(f"Error getting historical data for volatility for {symbol}: {ticks_history['error']['message']}")
            return None

        if not ticks_history.get('candles'):
            print(f"No historical data found for volatility calculation for {symbol}")
            return None

        data = pd.DataFrame(ticks_history['candles'])
        data['epoch'] = pd.to_datetime(data['epoch'], unit='s')
        data = get_indicators(data) # Ensure ATR is calculated

        if 'ATR' in data.columns and not data['ATR'].empty:
            return data['ATR'].iloc[-1]
        return None

    except Exception as e:
        print(f"Error calculating market volatility for {symbol}: {e}")
        return None

async def get_composite_market_volatility(api, symbols: list, lookback_period=200):
    """Calculates a composite market volatility by averaging ATR across multiple symbols.

    Args:
        api: The DerivAPI instance.
        symbols (list): A list of symbols to fetch historical data for.
        lookback_period (int): The number of candles to look back for ATR calculation.

    Returns:
        float: The average ATR value across all symbols, or None if no data is available.
    """
    volatilities = []
    tasks = [get_market_volatility(api, symbol, lookback_period) for symbol in symbols]
    results = await asyncio.gather(*tasks)

    for vol in results:
        if vol is not None:
            volatilities.append(vol)

    if volatilities:
        return sum(volatilities) / len(volatilities)
    return None

def adjust_parameters(current_params, volatility):
    """Adjusts trading parameters based on market volatility.

    Args:
        current_params (dict): Dictionary of current parameters (cooldown_period, sma_threshold, rsi_threshold, risk_percentage).
        volatility (float): Current market volatility (ATR).

    Returns:
        dict: Updated parameters.
    """
    adjusted_params = current_params.copy()

    if volatility is None:
        print("Volatility data not available, using default parameters.")
        return adjusted_params

    # Example adjustment logic (these values will need tuning)
    if volatility > 0.005:  # High volatility
        adjusted_params['cooldown_period'] = 1800  # Shorter cooldown (30 mins)
        adjusted_params['sma_threshold'] = 0.002   # Wider SMA threshold
        adjusted_params['rsi_threshold'] = 2       # Wider RSI threshold
        adjusted_params['risk_percentage'] = 0.015 # Slightly lower risk
        print(f"Adjusting parameters for HIGH volatility. New params: {adjusted_params}")
    elif volatility < 0.001: # Low volatility
        adjusted_params['cooldown_period'] = 7200  # Longer cooldown (2 hours)
        adjusted_params['sma_threshold'] = 0.0005  # Tighter SMA threshold
        adjusted_params['rsi_threshold'] = 0.5     # Tighter RSI threshold
        adjusted_params['risk_percentage'] = 0.025 # Slightly higher risk
        print(f"Adjusting parameters for LOW volatility. New params: {adjusted_params}")
    else: # Moderate volatility
        adjusted_params['cooldown_period'] = 3600  # Default cooldown (1 hour)
        adjusted_params['sma_threshold'] = 0.001   # Default SMA threshold
        adjusted_params['rsi_threshold'] = 1       # Default RSI threshold
        adjusted_params['risk_percentage'] = 0.02  # Default risk
        print(f"Adjusting parameters for MODERATE volatility. New params: {adjusted_params}")

    return adjusted_params

if __name__ == "__main__":
    # This part would typically be run within the bot's main loop
    # For demonstration, we'll simulate some values
    print("Running parameter tuner example...")
    current_params = {
        'cooldown_period': 3600,
        'sma_threshold': 0.001,
        'rsi_threshold': 1,
        'risk_percentage': 0.02
    }

    # Simulate high volatility
    print("\nSimulating high volatility...")
    adjusted_high_vol_params = adjust_parameters(current_params, 0.006)
    print(f"Final adjusted params (high vol): {adjusted_high_vol_params}")

    # Simulate low volatility
    print("\nSimulating low volatility...")
    adjusted_low_vol_params = adjust_parameters(current_params, 0.0008)
    print(f"Final adjusted params (low vol): {adjusted_low_vol_params}")

    # Simulate moderate volatility
    print("\nSimulating moderate volatility...")
    adjusted_mod_vol_params = adjust_parameters(current_params, 0.003)
    print(f"Final adjusted params (moderate vol): {adjusted_mod_vol_params}")
