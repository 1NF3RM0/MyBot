import os
os.environ['CUDA_VISIBLE_DEVICES'] = '-1'
import asyncio
from src.bot import TradingBot

async def main():
    """Main asynchronous function to run the trading bot."""
    bot = TradingBot()
    await bot.run()

if __name__ == "__main__":
    asyncio.run(main())