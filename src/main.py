import asyncio
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import json
import os
import re
from src.bot import TradingBot

app = FastAPI()

# CORS middleware to allow frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        connections_to_remove = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                connections_to_remove.append(connection)
        
        for connection in connections_to_remove:
            self.active_connections.remove(connection)

manager = ConnectionManager()
bot_instance = TradingBot()

@app.post("/bot/start")
async def start_bot():
    if bot_instance._is_running:
        return JSONResponse(content={"status": "error", "message": "Bot is already running."}, status_code=400)
    
    await bot_instance.start(manager)
    return {"status": "success", "message": "Bot started."}

@app.post("/bot/stop")
async def stop_bot():
    if not bot_instance._is_running:
        return JSONResponse(content={"status": "error", "message": "Bot is not running."}, status_code=400)
    
    await bot_instance.stop()
    return {"status": "success", "message": "Bot stopped."}

@app.get("/bot/status")
async def get_status():
    if bot_instance._is_running:
        return {"status": "running"}
    return {"status": "stopped"}

@app.get("/config")
async def get_config():
    config_path = os.path.join(os.path.dirname(__file__), 'config.py')
    config_values = {}
    with open(config_path, 'r') as f:
        content = f.read()
        # Use regex to find variable assignments
        app_id_match = re.search(r"APP_ID\s*=\s*['\"](.*?)['\"]", content)
        api_token_match = re.search(r"API_TOKEN\s*=\s*['\"](.*?)['\"]", content)
        
        if app_id_match:
            config_values['APP_ID'] = app_id_match.group(1)
        if api_token_match:
            config_values['API_TOKEN'] = api_token_match.group(1)
            
    return config_values

@app.post("/config")
async def set_config(config_data: dict):
    config_path = os.path.join(os.path.dirname(__file__), 'config.py')
    with open(config_path, 'r') as f:
        content = f.read()

    # Replace values using regex
    if 'APP_ID' in config_data:
        content = re.sub(r"(APP_ID\s*=\s*)['\"].*?['\"]", f"\\1'{config_data['APP_ID']}'", content)
    if 'API_TOKEN' in config_data:
        content = re.sub(r"(API_TOKEN\s*=\s*)['\"].*?['\"]", f"\\1'{config_data['API_TOKEN']}'", content)

    with open(config_path, 'w') as f:
        f.write(content)
        
    await manager.broadcast(f"Configuration updated.")
    return {"status": "success", "message": "Configuration updated."}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
