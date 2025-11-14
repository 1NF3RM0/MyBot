# Deriv Trading Bot

This project is an asynchronous Python trading bot designed for the Deriv platform. It automates trading across various asset classes, including forex, indices, and commodities, by leveraging technical analysis indicators and a multi-strategy approach.

## Features

-   **Dynamic Symbol Fetching:** Automatically retrieves a list of available trading instruments from the Deriv API.
-   **Technical Analysis:** Calculates a range of indicators, including Moving Averages (SMA), Relative Strength Index (RSI), MACD, Bollinger Bands, Ichimoku Cloud, and Average True Range (ATR).
-   **Multi-Strategy Confirmation:** Trades are only proposed if at least two strategies agree and their combined confidence score exceeds a threshold.
-   **Dynamic Strategy Selection:** Strategies are dynamically selected based on classified market conditions (trending, ranging, volatile).
-   **Strategy Evolution Engine:** Strategies are managed as objects with tunable parameters, confidence scores, and active status. Performance is tracked, and strategies can be re-enabled from a disabled state if they show recent success.
-   **Parameter Auto-tuning:** Trading parameters like cooldown period, SMA/RSI thresholds, and risk percentage are dynamically adjusted based on market volatility.
-   **Trade Cooldown and Similarity Checks:** Prevents re-trading the same setup within a cooldown period or if market conditions are too similar.
-   **Single Trade Per Symbol Per Cycle:** Ensures only one contract is proposed per symbol within a single main bot loop iteration.
-   **Proposal Validation:** Rejects trades if `ask_price > 20` or `payout < 15`.
-   **Early Exit Logic:** Monitors open contracts and initiates early exits (sells) if conditions like RSI overbought/oversold are met.
-   **Comprehensive Logging:** All significant events (signals, proposals, buys, errors, skipped trades, contract outcomes) are logged to `trading_log.db` (SQLite) with timestamps, symbol, strategy, action, price, payout, and outcome.
-   **Robust Error Handling:** Implements `retry_async` decorator with exponential backoff for API-dependent asynchronous functions.
-   **Graceful Shutdown:** Catches `KeyboardInterrupt` to cleanly disconnect from the API and save `open_contracts` to `open_contracts.json`.

## Getting Started

### 1. Installation

To set up the project, first install the required dependencies. It is recommended to use a virtual environment.

```bash
pip install -r requirements.txt --break-system-packages
```

### 2. Configuration

Before running the bot, you must configure your Deriv API credentials in the `src/config.py` file. You will need to provide your App ID and API Token.

```python
# src/config.py

APP_ID = "YOUR_APP_ID"  # Replace with your Deriv App ID
API_TOKEN = "YOUR_API_TOKEN"  # Replace with your Deriv API Token

# ... other trading parameters
```

### 3. Running the Bot

To run the trading bot, execute the following command from the project's root directory:

```bash
python3 -m src.core
```

### 4. Running Tests

To run the test suite, use the following command:

```bash
python -m unittest discover tests
```

### 5. Generating Strategy Performance Report

To generate a report on strategy performance, execute the following command:

```bash
python3 -m src.report_generator
```

### 6. Running the Dashboard

To run the Streamlit performance dashboard, execute the following command from the project's root directory:

```bash
streamlit run src/dashboard.py
```

## Development Conventions

-   **Modularity:** The code is organized into modules with distinct responsibilities (`bot.py` for main logic, `config.py` for configuration, `utils.py` for utilities, `logging_utils.py` for logging, `strategy_manager.py` for strategy management, `param_tuner.py` for parameter tuning, `report_generator.py` for reporting).
-   **Asynchronous Programming:** The bot leverages `asyncio` for efficient handling of API requests and responses.
-   **Configuration Management:** API credentials and trading parameters are externalized in `config.py` for easy management and security.
-   **Dynamic Symbol Discovery:** Trading symbols are fetched dynamically from the Deriv API, making the bot adaptable to changes in available instruments.
-   **Technical Analysis Integration:** The `ta` library is used for comprehensive and standardized calculation of technical indicators.
-   **Error Handling:** The bot includes `try-except` blocks and a `retry_async` decorator to gracefully handle API errors and other exceptions, providing informative messages.
-   **Strategy Management:** Strategies are treated as objects, allowing for dynamic adjustment of confidence scores, activation/deactivation, and future mutation.
-   **Parameter Tuning:** Key trading parameters are dynamically adjusted based on real-time market conditions.