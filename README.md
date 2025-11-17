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

## 🤝 Contributing

Contributions are welcome! Please feel free to open an issue or submit a pull request. For major changes, please open an issue first to discuss what you would like to change.

## 📄 License

This project is licensed under the MIT License. See the `LICENSE` file for details.
