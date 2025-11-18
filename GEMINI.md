# Project Overview

This project is an advanced, asynchronous Python trading bot designed for the Deriv platform. It aims to automate trading across various asset classes, including forex, indices, and commodities, by leveraging a multi-strategy technical analysis engine, real-time market classification, and a powerful web interface for comprehensive control, monitoring, and analysis.

The bot's architecture is built around the `deriv_api` library for interacting with the Deriv platform and the `ta` library for comprehensive technical indicator calculations. It operates asynchronously using `asyncio` for efficient, non-blocking communication with the trading API. The backend is implemented using FastAPI, and the frontend is a React application.

Key features include:
-   **Dynamic Symbol Fetching:** The bot automatically retrieves a list of available trading instruments from the Deriv API, ensuring it always works with up-to-date and valid symbols.
-   **Technical Analysis:** It calculates a range of indicators, including Moving Averages (SMA), Relative Strength Index (RSI), MACD, Bollinger Bands, Ichimoku Cloud, and Average True Range (ATR).
-   **Multi-Strategy Confirmation:** Trades are only proposed if at least two strategies agree and their combined confidence score exceeds a threshold.
-   **Dynamic Strategy Selection:** Strategies are dynamically selected based on classified market conditions (trending, ranging, volatile).
-   **Strategy Evolution Engine:** Strategies are managed as `Strategy` objects with tunable parameters, confidence scores, and active status. Performance is tracked, and strategies can be re-enabled from a disabled state if they show recent success.
-   **Parameter Auto-tuning:** Trading parameters like cooldown period, SMA/RSI thresholds, and risk percentage are dynamically adjusted based on market volatility.
-   **Trade Cooldown and Similarity Checks:** Prevents re-trading the same setup within a cooldown period or if market conditions are too similar.
-   **Single Trade Per Symbol Per Cycle:** Ensures only one contract is proposed per symbol within a single main bot loop iteration.
-   **Proposal Validation:** Rejects trades if `ask_price > 20` or `payout < 15`.
-   **Early Exit Logic:** Monitors open contracts and initiates early exits (sells) if conditions like RSI overbought/oversold are met.
-   **Comprehensive Logging:** All significant events (signals, proposals, buys, errors, skipped trades, contract outcomes) are logged to `trading_log.db` (SQLite) with timestamps, symbol, strategy, action, price, payout, and outcome.
-   **Robust Error Handling:** Implements `retry_async` decorator with exponential backoff for API-dependent asynchronous functions.
-   **Graceful Shutdown:** Catches `KeyboardInterrupt` to cleanly disconnect from the API and save `open_contracts` to `open_contracts.json`.
-   **Web Interface:** A React frontend provides a dashboard for remote control (start/stop/emergency stop), real-time monitoring of logs and status, live account balance, and centralized configuration management.

# Building and Running

## 1. Installation

To set up the project, first install the required dependencies for both the Python backend and the React frontend. It is recommended to use a virtual environment for Python.

### Backend Dependencies

```bash
# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt
```

### Frontend Dependencies

```bash
# Navigate to the frontend directory
cd frontend

# Install Node.js dependencies
npm install
```

## 2. Configuration

Before running the bot, you must configure your Deriv API credentials. This can be done by editing `src/config.py` or through the web UI after initial setup.

```python
# src/config.py

APP_ID = "YOUR_APP_ID"  # Replace with your Deriv App ID
API_TOKEN = "YOUR_API_TOKEN"  # Replace with your Deriv API Token

# ... other trading parameters
```

## 3. Running the Bot

The application runs in two parts: a Python backend (FastAPI) and a React frontend.

### Running the Backend

To run the trading bot's backend, execute the following command from the project's root directory:

```bash
python3 -m src.main
```
The backend will typically run on `http://localhost:8000`.

### Running the Frontend

In a **new terminal**, navigate to the `frontend` directory and run the React application:

```bash
cd frontend
npm run dev
```
The frontend will typically run on `http://localhost:5173`.

### Launching the Dashboard

Open your web browser and navigate to the frontend URL (e.g., `http://localhost:5173`). You can now register, log in, start the bot, and monitor its activity from the dashboard.

## 4. Running Tests

To run the test suite, use the following command from the project's root directory:

```bash
python -m unittest discover tests
```

## 5. Generating Strategy Performance Report

To generate a report on strategy performance, execute the following command:

```bash
python3 -m src.report_generator
```

## 6. Running the Dashboard (Streamlit)

To run the Streamlit performance dashboard (separate from the main React frontend), execute the following command from the project's root directory:

```bash
streamlit run src/dashboard.py
```

# Development Conventions

*   **Modularity:** The code is organized into modules with distinct responsibilities (`bot.py` for main logic, `config.py` for configuration, `utils.py` for utilities, `logging_utils.py` for logging, `strategy_manager.py` for strategy management, `param_tuner.py` for parameter tuning, `report_generator.py` for reporting, `main.py` for FastAPI endpoints, `auth.py` for authentication, `database.py` for database interactions).
*   **Asynchronous Programming:** The bot leverages `asyncio` for efficient handling of API requests and responses.
*   **Configuration Management:** API credentials and trading parameters are externalized in `src/config.py` and can be managed via the web UI for easy management and security.
*   **Dynamic Symbol Discovery:** Trading symbols are fetched dynamically from the Deriv API, making the bot adaptable to changes in available instruments.
*   **Technical Analysis Integration:** The `ta` library is used for comprehensive and standardized calculation of technical indicators.
*   **Error Handling:** The bot includes `try-except` blocks and a `retry_async` decorator to gracefully handle API errors and other exceptions, providing informative messages.
*   **Strategy Management:** Strategies are treated as objects, allowing for dynamic adjustment of confidence scores, activation/deactivation, and future mutation.
*   **Parameter Tuning:** Key trading parameters are dynamically adjusted based on real-time market conditions.
*   **Frontend Structure:** The React frontend follows a component-based architecture with pages, components, and context for state management.
*   **API Interaction:** The frontend interacts with the FastAPI backend via REST endpoints and WebSockets for real-time updates.
