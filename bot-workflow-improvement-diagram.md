+--------------------+
| Start / Init Bot   |
| - Initialize DB    |
| - Load open trades |
| - API Connect      |
+---------+----------+
          |
          v
+---------------------------+
| Fetch Account & Balance   |
| Fetch Available Symbols   |
+------------+--------------+
             |
             v
+---------------------------+
| Fetch Market Data         |
| - Historical Candles      |
| - Ticks for real-time     |
+------------+--------------+
             |
             v
+---------------------------+
| Classify Market Condition |
| - Trending / Ranging / Volatile |
| - Optional: Multi-timeframe check |
+------------+--------------+
             |
             v
+---------------------------+
| Select Active Strategies  |
| - Based on market condition |
| - Confidence scoring       |
+------------+--------------+
             |
             v
+---------------------------+
| Evaluate Strategies per Symbol |
| - Golden Cross            |
| - RSI Dip                 |
| - MACD Crossover          |
| - Bollinger Breakout      |
| - Optional: Add ATR, EMA, ADX |
+------------+--------------+
             |
             v
+---------------------------+
| Multi-Strategy Confirmation |
| - Aggregate signals & confidence |
| - Check cooldowns / cache       |
| - Optional: Adaptive position sizing |
+------------+--------------+
             |
             v
+---------------------------+
| Propose & Buy Contract    |
| - Validate price/payout   |
| - Buy if criteria met     |
| - Log purchase            |
+------------+--------------+
             |
             v
+---------------------------+
| Monitor Open Contracts    |
| - Early exits (RSI / ATR / Trailing Stop) |
| - Profit/loss check       |
| - Resale if allowed       |
| - Update trade cache      |
+------------+--------------+
             |
             v
+---------------------------+
| End Cycle / Wait / Repeat |
| - Sleep 15 minutes        |
| - Save open trades        |
+---------------------------+
