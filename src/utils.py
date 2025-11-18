import asyncio
from deriv_api import DerivAPI
import json

# This is a placeholder for a real retry decorator
def retry_async(*args, **kwargs):
    if len(args) == 1 and callable(args[0]):
        # Used as @retry_async
        return args[0]
    else:
        # Used as @retry_async()
        def decorator(func):
            return func
        return decorator

@retry_async
async def get_active_symbols(api: DerivAPI) -> list:
    """
    Fetches the list of active symbols from the Deriv API.
    """
    try:
        response = await api.active_symbols({"active_symbols": "brief"})
        if response.get('error'):
            print(f"Error fetching active symbols: {response['error'].get('message')}")
            return []
        
        active_symbols = response.get('active_symbols', [])
        # Filter for symbols that are allowed to be traded
        return [symbol['symbol'] for symbol in active_symbols if symbol.get('market') != 'synthetic_index' and symbol.get('is_trading_suspended') != 1]
    except Exception as e:
        print(f"An exception occurred while fetching active symbols: {e}")
        return []

@retry_async
async def get_valid_durations(api: DerivAPI, symbol: str, contract_type: str) -> dict:
    """
    Fetches valid durations for a given symbol and contract type from the Deriv API.
    Returns a dictionary with duration units as keys and lists of durations as values.
    """
    try:
        response = await api.contracts_for({
            "contracts_for": symbol,
            "currency": "USD",  # Assuming USD as base currency
            "product_type": "basic"
        })
        
        if response.get('error'):
            print(f"Error fetching contracts for symbol {symbol}: {response['error'].get('message')}")
            return {}
        
        contract_details = response.get('contracts_for', {}).get('available', [])
        
        valid_durations = {}
        for contract in contract_details:
            if contract_type in contract.get('contract_type', ''):
                min_duration_str = contract.get('min_contract_duration')
                max_duration_str = contract.get('max_contract_duration')

                if min_duration_str and max_duration_str:
                    # Function to parse duration string (e.g., "1d", "15m", "1h")
                    def parse_duration(duration_str):
                        if duration_str.endswith('d'):
                            return int(duration_str[:-1]), 'd'
                        elif duration_str.endswith('h'):
                            return int(duration_str[:-1]), 'h'
                        elif duration_str.endswith('m'):
                            return int(duration_str[:-1]), 'm'
                        elif duration_str.endswith('s'):
                            return int(duration_str[:-1]), 's'
                        return None, None

                    min_val, min_unit = parse_duration(min_duration_str)
                    max_val, max_unit = parse_duration(max_duration_str)
                    
                    if min_unit == max_unit and min_val is not None and max_val is not None:
                        duration_unit = min_unit
                        if duration_unit not in valid_durations:
                            valid_durations[duration_unit] = []
                        valid_durations[duration_unit].append({
                            'min': min_val,
                            'max': max_val
                        })
        return valid_durations
    except Exception as e:
        print(f"An exception occurred while fetching valid durations for {symbol}: {e}")
        return {}

def some_other_utility_function():
    # This is just a placeholder for other potential utils
    pass

def classify_market_condition(data):
    """Classifies the market condition as trending, ranging, or volatile based on ADX."""
    adx = data['ADX'].iloc[-1]

    if adx > 25:
        return "trending"
    elif adx < 20:
        return "ranging"
    else:
        return "volatile"
