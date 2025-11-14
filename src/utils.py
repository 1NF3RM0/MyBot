import asyncio
import time
from functools import wraps

def retry_async(retries=3, delay=1):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            for i in range(retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    print(f"Error in {func.__name__}: {e}. Retrying in {delay} seconds...")
                    await asyncio.sleep(delay)
                    delay *= 2
            print(f"Function {func.__name__} failed after {retries} retries.")
            return None
        return wrapper
    return decorator





def classify_market_condition(data):
    """Classifies the market condition as trending, ranging, or volatile based on ADX."""
    adx = data['ADX'].iloc[-1]

    if adx > 25:
        return "trending"
    elif adx < 20:
        return "ranging"
    else:
        return "volatile"
