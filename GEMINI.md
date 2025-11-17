# Project Overview: MyBot (Developer Documentation)

This document provides a technical overview of the MyBot trading application, intended for developers and contributors.

## 1. Architecture

MyBot is a client-server application composed of a Python backend and a React frontend.

### Backend

-   **Framework:** FastAPI
-   **Entry Point:** `src/main.py`
-   **Description:** The backend exposes a REST API to control and configure the bot. It uses a long-running `TradingBot` instance (`src/bot.py`) to manage the trading logic. All communication about the bot's status and logs is pushed to the frontend via a WebSocket connection.

### Frontend

-   **Framework:** React (bootstrapped with Vite)
-   **Location:** `/frontend`
-   **Description:** The single-page application (SPA) provides a dashboard for users to interact with the bot. It communicates with the backend via HTTP requests for control actions (start, stop, configure) and a WebSocket for receiving real-time updates.

## 2. Backend API & Endpoints

The backend server runs on `http://localhost:8000`.

### REST API

| Method | Endpoint      | Description                                                 |
| :----- | :------------ | :---------------------------------------------------------- |
| `POST` | `/bot/start`  | Starts the trading bot's main run loop.                     |
| `POST` | `/bot/stop`   | Stops the trading bot gracefully.                           |
| `GET`  | `/bot/status` | Returns the current status (`running` or `stopped`).        |
| `GET`  | `/config`     | Retrieves the current `APP_ID` and `API_TOKEN`.             |
| `POST` | `/config`     | Updates the `APP_ID` and `API_TOKEN` in `src/config.py`.    |

### WebSocket

-   **Endpoint:** `ws://localhost:8000/ws`
-   **Purpose:** Streams JSON-encoded messages from the server to all connected clients. This is the primary channel for real-time logs and status updates. The `ConnectionManager` class in `src/main.py` manages all active WebSocket connections.

## 3. Building and Running

### Prerequisites

-   Python 3.11+
-   Node.js 18+ and `npm`

### Step 1: Run the Backend

From the project root:
```bash
# Install dependencies
pip install -r requirements.txt --break-system-packages

# Run the server
python3 -m src.main
```

### Step 2: Run the Frontend

In a separate terminal, from the project root:
```bash
# Navigate to the frontend directory
cd frontend

# Install dependencies
npm install

# Run the dev server
npm run dev
```

### Step 3: Access the Application

Open a web browser and navigate to the local URL provided by the Vite dev server (e.g., `http://localhost:5173`).

## 4. Key Modules & Conventions

-   **`src/main.py`**: The FastAPI application server. Manages the bot's lifecycle and API endpoints.
-   **`src/bot.py`**: Contains the core `TradingBot` class, refactored for API control with `start()` and `stop()` methods.
-   **`src/config.py`**: Stores configuration variables. It is read from and written to by the API.
-   **`/frontend`**: Contains the entire React application, including components for the dashboard, settings, and monitoring tabs.
-   **Logging**: The `_log` method in the `TradingBot` class now serves a dual purpose: it prints to the console an broadcasts the message over the WebSocket, ensuring the UI is always in sync.

## 5. Other Scripts

-   **`src/report_generator.py`**: Generates a performance report for trading strategies.
    ```bash
    python3 -m src.report_generator
    ```
-   **`tests/`**: Contains the project's unit tests.
    ```bash
    python -m unittest discover tests
    ```