import asyncio
import pandas as pd
from deriv_api import DerivAPI
from src import config
import datetime

async def collect_and_save_historical_data(symbols, days=365, granularity=86400):
    """
    Collects historical data for a list of symbols and saves it to a CSV file.
    """
    api = DerivAPI(app_id=config.APP_ID)
    all_data = []

    for symbol in symbols:
        print(f"Fetching data for {symbol}...")
        try:
            end_time = datetime.datetime.now()
            start_time = end_time - datetime.timedelta(days=days)

            ticks_history = await api.ticks_history({
                'ticks_history': symbol,
                'start': int(start_time.timestamp()),
                'end': int(end_time.timestamp()),
                'style': 'candles',
                'granularity': granularity
            })

            if ticks_history.get('candles'):
                df = pd.DataFrame(ticks_history['candles'])
                df['symbol'] = symbol
                all_data.append(df)
            else:
                print(f"No data for {symbol}")

        except Exception as e:
            print(f"Error fetching data for {symbol}: {e}")

    if all_data:
        full_df = pd.concat(all_data, ignore_index=True)
        full_df.to_csv("historical_data.csv", index=False)
        print("Historical data saved to historical_data.csv")

    await api.disconnect()

if __name__ == "__main__":
    # Example usage:
    symbols_to_collect = [
        'frxAUDJPY', 'frxAUDUSD', 'frxEURCAD', 'frxEURCHF', 'frxEURGBP',
        'frxEURJPY', 'frxEURUSD', 'frxGBPJPY', 'frxGBPUSD', 'frxUSDCAD',
        'frxUSDCHF', 'frxUSDJPY'
    ]
    asyncio.run(collect_and_save_historical_data(symbols_to_collect))
