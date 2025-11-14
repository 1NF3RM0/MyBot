import asyncio
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src import data_collector
from src import ml_strategy

async def main():
    print("Starting data collection for ML model training...")
    
    # Define symbols to collect, similar to data_collector.py's example
    symbols_to_collect = [
        'frxAUDJPY', 'frxAUDUSD', 'frxEURCAD', 'frxEURCHF', 'frxEURGBP',
        'frxEURJPY', 'frxEURUSD', 'frxGBPJPY', 'frxGBPUSD', 'frxUSDCAD',
        'frxUSDCHF', 'frxUSDJPY',
        'OTC_AS51', 'OTC_HSI', 'OTC_N225', 'OTC_SX5E', 'OTC_FCHI', 'OTC_GDAXI', 'OTC_AEX', 'OTC_SSMI', 'OTC_FTSE', 'OTC_SPC', 'OTC_NDX', 'OTC_DJI', # Indices
        'frxXAUUSD', 'frxXPDUSD', 'frxXPTUSD', 'frxXAGUSD' # Commodities
    ]
    
    await data_collector.collect_and_save_historical_data(symbols_to_collect)
    print("Data collection complete. Starting ML model training...")
    ml_strategy.train_model()
    print("ML model training complete.")

if __name__ == "__main__":
    asyncio.run(main())
