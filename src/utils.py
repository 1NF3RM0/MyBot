import asyncio
from deriv_api import DerivAPI

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
