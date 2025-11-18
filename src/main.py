# Force reload: 2025-11-18 01:45:00
import asyncio
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
import json
import os
import re
import io
import csv
from datetime import timedelta # Added this import
from jose import JWTError, jwt

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
    
    bot_instances[user_id] = TradingBot(user_id=user_id)
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

@app.post("/bot/emergency_stop")
async def emergency_stop_bot(current_user: schemas.User = Depends(auth.get_current_active_user)):
    user_id = current_user.id
    if user_id not in bot_instances or not bot_instances[user_id]._is_running:
        return JSONResponse(content={"status": "error", "message": "Bot is not running."}, status_code=400)
    
    await bot_instances[user_id].emergency_stop()
    del bot_instances[user_id]
    return {"status": "success", "message": "Bot emergency stopped."}

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
    user_id = None # Initialize user_id
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
        
        user_id = user.id # Assign user_id here
        await manager.connect(websocket, user_id)
        try:
            while True:
                try:
                    await websocket.receive_text()
                except WebSocketDisconnect:
                    # Expected disconnection
                    break
                except (AttributeError, TypeError) as e:
                    # Catch the specific error and break the loop
                    print(f"Caught AttributeError/TypeError during websocket receive: {e}")
                    break
                except Exception as e:
                    # Catch any other unexpected errors
                    print(f"Unexpected error during websocket receive: {e}")
                    break
        finally:
            if user_id is not None:
                manager.disconnect(user_id)
    except JWTError:
        await websocket.close(code=status.WS_1008_POLICY_VIolation)
    except Exception as e:
        print(f"Unhandled exception in websocket_endpoint (outer block): {e}")
        if user_id is not None:
            manager.disconnect(user_id)

# --- Data & Metrics Endpoints ---

@app.get("/bot/metrics")
async def get_metrics(current_user: schemas.User = Depends(auth.get_current_active_user), db: Session = Depends(database.get_db)):
    user_id = current_user.id
    trades = db.query(database.TradeLog).filter(database.TradeLog.user_id == current_user.id).all()
    settings = db.query(database.UserSettings).filter(database.UserSettings.user_id == current_user.id).first()
    
    closed_trades = [t for t in trades if t.pnl is not None]
    
    total_pnl = sum(t.pnl for t in closed_trades)
    total_investment = sum(t.entry_price for t in closed_trades if t.entry_price is not None and t.pnl is not None)
    
    pnl_percentage = (total_pnl / total_investment) * 100 if total_investment > 0 else 0
    
    win_rate = (sum(1 for t in closed_trades if t.pnl > 0) / len(closed_trades)) * 100 if closed_trades else 0

    # Get open trades count from the running bot instance
    open_trades_count = 0
    if user_id in bot_instances and bot_instances[user_id]._is_running:
        open_trades_count = len(bot_instances[user_id].open_contracts)

    active_strategies_count = len(settings.active_strategies.split(',')) if settings and settings.active_strategies else 0
    
    # In a real scenario, this would be a more complex calculation, possibly requiring access to the running bot's analysis.
    trend_signal = "Ranging" 

    return {
        "total_pnl": total_pnl,
        "win_rate": win_rate,
        "open_trades": open_trades_count,
        "active_strategies": active_strategies_count,
        "pnl_percentage": pnl_percentage,
        "trend_signal": trend_signal,
    }

@app.get("/bot/account")
async def get_account_info(current_user: schemas.User = Depends(auth.get_current_active_user)):
    user_id = current_user.id
    if user_id in bot_instances and bot_instances[user_id]._is_running:
        bot = bot_instances[user_id]
        return {"balance": bot.balance, "currency": bot.currency}
    return {"balance": None, "currency": None}

@app.get("/bot/open_contracts_deriv")
async def get_open_contracts_from_deriv(current_user: schemas.User = Depends(auth.get_current_active_user)):
    user_id = current_user.id
    if user_id not in bot_instances or not bot_instances[user_id]._is_running:
        raise HTTPException(status_code=400, detail="Bot is not running for this user.")
    
    bot = bot_instances[user_id]
    try:
        portfolio_response = await bot.api.portfolio()
        if portfolio_response.get('error'):
            raise HTTPException(status_code=500, detail=portfolio_response['error']['message'])
        
        contracts = portfolio_response.get('portfolio', {}).get('contracts', [])
        
        # You might want to filter or format these contracts before returning
        # For now, returning them as is
        return contracts
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch open contracts from Deriv: {e}")

@app.get("/bot/performance")
async def get_performance_data(current_user: schemas.User = Depends(auth.get_current_active_user), db: Session = Depends(database.get_db)):
    trades = db.query(database.TradeLog).filter(
        database.TradeLog.user_id == current_user.id,
        database.TradeLog.pnl != None
    ).order_by(database.TradeLog.timestamp.asc()).all()

    cumulative_pnl = 0
    performance_data = []
    for trade in trades:
        cumulative_pnl += trade.pnl
        performance_data.append({
            "timestamp": trade.timestamp.strftime("%Y-%m-%d %H:%M"),
            "pnl": cumulative_pnl
        })
    return performance_data

@app.get("/tradelog/recent")
async def get_recent_trades(current_user: schemas.User = Depends(auth.get_current_active_user), db: Session = Depends(database.get_db)):
    trades = db.query(database.TradeLog).filter(
        database.TradeLog.user_id == current_user.id
    ).order_by(database.TradeLog.timestamp.desc()).limit(5).all()
    
    # Convert to a list of dictionaries to add current_pnl
    trades_data = []
    for trade in trades:
        trade_dict = trade.__dict__
        trade_dict.pop('_sa_instance_state', None) # Remove SQLAlchemy internal state
        trades_data.append(trade_dict)
        
    return trades_data

@app.get("/tradelog")
async def get_full_tradelog(
    search: str = None,
    strategy: str = None,
    status: str = None,
    skip: int = 0,
    limit: int = 100,
    current_user: schemas.User = Depends(auth.get_current_active_user), 
    db: Session = Depends(database.get_db)
):
    query = db.query(database.TradeLog).filter(database.TradeLog.user_id == current_user.id)
    
    if search:
        query = query.filter(database.TradeLog.symbol.contains(search))
    if strategy and strategy != "all":
        query = query.filter(database.TradeLog.strategy == strategy)
    if status and status != "all":
        query = query.filter(database.TradeLog.status.contains(status))
        
    trades = query.order_by(database.TradeLog.timestamp.desc()).offset(skip).limit(limit).all()
    
    # Convert to a list of dictionaries to include current_pnl
    trades_data = []
    for trade in trades:
        trade_dict = trade.__dict__
        trade_dict.pop('_sa_instance_state', None) # Remove SQLAlchemy internal state
        trades_data.append(trade_dict)
        
    return trades_data

@app.get("/tradelog/export")
async def export_tradelog(
    search: str = None,
    strategy: str = None,
    status: str = None,
    current_user: schemas.User = Depends(auth.get_current_active_user), 
    db: Session = Depends(database.get_db)
):
    query = db.query(database.TradeLog).filter(database.TradeLog.user_id == current_user.id)
    
    if search:
        query = query.filter(database.TradeLog.symbol.contains(search))
    if strategy and strategy != "all":
        query = query.filter(database.TradeLog.strategy == strategy)
    if status and status != "all":
        query = query.filter(database.TradeLog.status.contains(status))
        
    trades = query.order_by(database.TradeLog.timestamp.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['Timestamp', 'Symbol', 'Strategy', 'Type', 'Entry Price', 'Exit Price', 'P/L', 'Status'])
    
    # Write trade data
    for trade in trades:
        writer.writerow([
            trade.timestamp,
            trade.symbol,
            trade.strategy,
            trade.type,
            trade.entry_price,
            trade.exit_price,
            trade.pnl,
            trade.status
        ])
    
    output.seek(0)
    
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=trade_log.csv"}
    )

from src.strategy_definitions import BASE_STRATEGIES

# --- Strategy Management Endpoints ---

@app.get("/strategies")
async def get_strategies(current_user: schemas.User = Depends(auth.get_current_active_user), db: Session = Depends(database.get_db)):
    base_strategies = BASE_STRATEGIES 

    settings = db.query(database.UserSettings).filter(database.UserSettings.user_id == current_user.id).first()
    if not settings:
        # Create default settings if they don't exist
        settings = database.UserSettings(user_id=current_user.id)
        db.add(settings)
        db.commit()
        db.refresh(settings)

    active_strategy_ids = settings.active_strategies.split(',') if settings.active_strategies else []
    
    strategy_performance = []
    for strategy_id, strategy_obj in base_strategies.items():
        trades = db.query(database.TradeLog).filter(
            database.TradeLog.user_id == current_user.id,
            database.TradeLog.strategy.contains(strategy_id),
            database.TradeLog.pnl != None
        ).all()
        
        total_trades = len(trades)
        pnl = sum(t.pnl for t in trades)
        win_rate = (sum(1 for t in trades if t.pnl > 0) / total_trades) * 100 if total_trades > 0 else 0
        
        strategy_performance.append({
            "id": strategy_id,
            "name": strategy_obj.name,
            "is_active": strategy_id in active_strategy_ids,
            "win_rate": win_rate,
            "total_trades": total_trades,
            "pnl": pnl
        })
    return strategy_performance

@app.post("/strategies/{strategy_id}/toggle")
async def toggle_strategy(strategy_id: str, current_user: schemas.User = Depends(auth.get_current_active_user), db: Session = Depends(database.get_db)):
    settings = db.query(database.UserSettings).filter(database.UserSettings.user_id == current_user.id).first()
    if not settings:
        raise HTTPException(status_code=404, detail="User settings not found")

    active_strategies = settings.active_strategies.split(',') if settings.active_strategies else []
    
    if strategy_id in active_strategies:
        active_strategies.remove(strategy_id)
    else:
        active_strategies.append(strategy_id)
        
    settings.active_strategies = ",".join(active_strategies)
    db.commit()
    
    return {"status": "success", "active_strategies": active_strategies}

# --- User Management Endpoints ---

@app.post("/user/reset")
async def reset_user_data(current_user: schemas.User = Depends(auth.get_current_active_user), db: Session = Depends(database.get_db)):
    # This is a destructive operation.
    
    # Delete Trade Logs
    db.query(database.TradeLog).filter(database.TradeLog.user_id == current_user.id).delete()
    
    # Delete User Settings
    db.query(database.UserSettings).filter(database.UserSettings.user_id == current_user.id).delete()
    
    db.commit()
    
    return {"status": "success", "message": "All user data has been reset."}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
