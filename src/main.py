import asyncio
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
import json
import os
import re
from datetime import timedelta # Added this import

from src.bot import TradingBot
from . import auth, schemas, database

# Create all database tables
database.create_db_and_tables()

app = FastAPI()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[int, WebSocket] = {}

    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        self.active_connections[user_id] = websocket

    def disconnect(self, user_id: int):
        if user_id in self.active_connections:
            del self.active_connections[user_id]

    async def broadcast(self, message: str):
        for user_id, connection in self.active_connections.items():
            try:
                await connection.send_text(message)
            except Exception:
                # This connection is likely dead, but disconnect will handle removal
                pass

manager = ConnectionManager()
bot_instances: dict[int, TradingBot] = {}

# --- Authentication Endpoints ---

@app.post("/register", response_model=schemas.User)
def register_user(user: schemas.UserCreate, db: Session = Depends(database.get_db)):
    db_user = db.query(database.User).filter(database.User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    hashed_password = auth.get_password_hash(user.password)
    db_user = database.User(username=user.username, hashed_password=hashed_password, email=user.email)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@app.post("/token", response_model=schemas.Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(database.get_db)):
    user = db.query(database.User).filter(database.User.username == form_data.username).first()
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


# --- Bot Control Endpoints ---

@app.post("/bot/start")
async def start_bot(current_user: schemas.User = Depends(auth.get_current_active_user)):
    user_id = current_user.id
    if user_id in bot_instances and bot_instances[user_id]._is_running:
        return JSONResponse(content={"status": "error", "message": "Bot is already running."}, status_code=400)
    
    bot_instances[user_id] = TradingBot()
    await bot_instances[user_id].start(manager)
    return {"status": "success", "message": "Bot started."}

@app.post("/bot/stop")
async def stop_bot(current_user: schemas.User = Depends(auth.get_current_active_user)):
    user_id = current_user.id
    if user_id not in bot_instances or not bot_instances[user_id]._is_running:
        return JSONResponse(content={"status": "error", "message": "Bot is not running."}, status_code=400)
    
    await bot_instances[user_id].stop()
    del bot_instances[user_id]
    return {"status": "success", "message": "Bot stopped."}

@app.get("/bot/status")
async def get_status(current_user: schemas.User = Depends(auth.get_current_active_user)):
    user_id = current_user.id
    if user_id in bot_instances and bot_instances[user_id]._is_running:
        return {"status": "running"}
    return {"status": "stopped"}

# --- Configuration Endpoints ---

@app.get("/config")
async def get_config(current_user: schemas.User = Depends(auth.get_current_active_user), db: Session = Depends(database.get_db)):
    settings = db.query(database.UserSettings).filter(database.UserSettings.user_id == current_user.id).first()
    if not settings:
        return {}
    return settings

@app.post("/config")
async def set_config(config_data: dict, current_user: schemas.User = Depends(auth.get_current_active_user), db: Session = Depends(database.get_db)):
    settings = db.query(database.UserSettings).filter(database.UserSettings.user_id == current_user.id).first()
    if not settings:
        settings = database.UserSettings(user_id=current_user.id)
        db.add(settings)

    for key, value in config_data.items():
        setattr(settings, key, value)
    
    db.commit()
    await manager.broadcast(f"Configuration updated for user {current_user.username}.")
    return {"status": "success", "message": "Configuration updated."}


# --- WebSocket Endpoint ---

@app.websocket("/ws/{token}")
async def websocket_endpoint(websocket: WebSocket, token: str, db: Session = Depends(database.get_db)):
    try:
        payload = jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        user = db.query(database.User).filter(database.User.username == username).first()
        if user is None:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        
        await manager.connect(websocket, user.id)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            manager.disconnect(user.id)
    except JWTError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
