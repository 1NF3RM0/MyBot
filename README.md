# MyBot — Deriv Trading Bot with Web UI

**MyBot** is an advanced, asynchronous Python trading bot built for the **Deriv** platform. It automates trading across forex, indices, and commodities using a multi-strategy technical analysis engine, real-time market classification, and a powerful web interface for control and monitoring.

![image](https://github.com/user-attachments/assets/15704251-652d-4a3c-8a9a-1960d183139a)

## ✨ Core Features

### Trading Engine
-   **Multi-Strategy Confirmation:** Executes trades only when multiple strategies agree, increasing signal confidence.
-   **Dynamic Strategy Management:** Automatically adjusts strategy confidence and enables/disables strategies based on performance.
-   **Adaptive Parameters:** Dynamically tunes risk, cooldowns, and indicator thresholds based on market volatility.
-   **Advanced Technical Indicators:** Utilizes RSI, MACD, Bollinger Bands, Ichimoku Cloud, ATR, SMAs, and more.
-   **Parallel Evaluation:** Evaluates all symbols and strategies concurrently for maximum speed and reduced signal lag.
-   **Robust Error Handling:** Features an exponential backoff retry mechanism for all API communications.
-   **Persistent State:** Gracefully saves all open trades on shutdown and reloads them on startup.

### Web Interface
-   **Remote Control:** Start and stop the bot from a user-friendly web dashboard.
-   **Real-Time Monitoring:** View a live stream of all bot activities, including signals, trades, and errors.
-   **Live Status:** See the bot's current status (running/stopped), account balance, and open positions.
-   **Centralized Configuration:** View and update your Deriv API credentials directly from the settings page.
-   **Strategy Insights:** Monitor the confidence scores and status of all trading strategies in real-time.

## 🚀 Getting Started

The application runs in two parts: a Python backend and a React frontend.

### 1. Prerequisites
- Python 3.11+
- Node.js 18+ and npm

### 2. Backend Setup

First, set up and run the bot's core engine.

```bash
# 1. Clone the repository
git clone https://github.com/your-username/MyBot.git
cd MyBot

# 2. Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Configure API Keys (Optional)
# You can pre-fill your API keys in `src/config.py` or set them later in the web UI.
# APP_ID = "YOUR_APP_ID"
# API_TOKEN = "YOUR_API_TOKEN"

# 5. Run the backend server
python3 -m src.main
```
The backend is now running on `http://localhost:8000`.

### 3. Frontend Setup

In a **new terminal**, set up and run the web interface.

```bash
# 1. Navigate to the frontend directory
cd MyBot/frontend

# 2. Install Node.js dependencies
npm install

# 3. Run the frontend application
npm run dev
```
The frontend is now running, typically on `http://localhost:5173`.

### 4. Launch the Dashboard
Open your web browser and navigate to the frontend URL (e.g., `http://localhost:5173`). You can now start the bot and monitor its activity from the dashboard.

## 🛠️ Development & Architecture

-   **Backend:** [FastAPI](https://fastapi.tiangolo.com/) provides the web server and API endpoints.
-   **Frontend:** [React](https://react.dev/) (using [Vite](https://vitejs.dev/)) powers the interactive user interface.
-   **Real-Time Communication:** [WebSockets](https://developer.mozilla.org/en-US/docs/Web/API/WebSockets_API) are used to stream live logs and status updates from the backend to the frontend.
-   **Database:** [SQLite](https://www.sqlite.org/index.html) is used for logging all trade events and strategy performance data.

## ⚠️ Troubleshooting and Recent Fixes

### Database Schema Mismatch (`no such column: trade_log.current_pnl`)

**Problem:** After updating the bot's code, you might encounter an error like `sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) no such column: trade_log.current_pnl`. This happens when the database schema (the structure of your `trading_app.db` file) is out of sync with the application's code (specifically, the `TradeLog` model in `src/database.py`).

**Solution:** To resolve this, you need to update your database schema. The simplest way to do this (especially during development) is to:

1.  **Stop the bot and the FastAPI server.**
2.  **Delete the existing `trading_app.db` file.** You can do this by running:
    ```bash
    rm trading_app.db
    ```
    **WARNING: This will erase all your historical trade data.** If you have important data, please back it up first.
3.  **Restart the FastAPI server.** This will cause the application to recreate the database with the correct, updated schema.

### Contract Monitoring Warnings

After recent updates, you might observe the following warnings during bot operation:

1.  **`⚠ Contract XXXXX for YYY has no 'trade_log_id'. Skipping local database updates for this contract, but continuing to monitor its status on Deriv.`**
    *   **Explanation:** This warning is expected. It means the bot found contracts on your Deriv account that it didn't initiate itself (e.g., manually opened trades, or trades opened by the bot before a restart that cleared its internal memory). Since these contracts don't have a corresponding entry in the bot's local database, the bot cannot update their P/L or status in your local trade log. It will still monitor them on Deriv and remove them from its internal list when they close.
    *   **Impact:** These specific contracts won't appear in your local trade history or contribute to the web app's metrics.

2.  **`⚠ Resale not available for contract XXXXX. Continuing to monitor.`**
    *   **Explanation:** This is also expected behavior. The Deriv API sometimes indicates that certain contracts cannot be sold before their natural expiry due to market conditions or contract type. The bot is correctly identifying these and will not attempt to sell them early, even if stop-loss or take-profit conditions are met. It will simply wait for the contract to expire naturally.
    *   **Impact:** The bot won't perform early exits for these contracts.

3.  **`⚠ RSI not available for contract XXXXX. Skipping early exit checks based on RSI.`**
    *   **Explanation:** This warning suggests that for some contracts, the bot was unable to calculate the Relative Strength Index (RSI). This could be due to insufficient historical data for that specific symbol, or a temporary data fetching issue.
    *   **Impact:** The bot will not use RSI-based early exit strategies for these particular contracts.

## 🤝 Contributing

Contributions are welcome! Please feel free to open an issue or submit a pull request. For major changes, please open an issue first to discuss what you would like to change.

## 📄 License

This project is licensed under the MIT License. See the `LICENSE` file for details.
