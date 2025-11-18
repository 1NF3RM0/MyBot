from sqlalchemy.orm import Session
from src.database import SessionLocal, TradeLog
import datetime

def get_db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def log_new_trade(
    user_id: int,
    symbol: str,
    strategy: str,
    trade_type: str,
    entry_price: float,
    status: str,
    message: str = None
) -> TradeLog:
    db: Session = next(get_db_session())
    trade_log_entry = TradeLog(
        user_id=user_id,
        timestamp=datetime.datetime.utcnow(),
        symbol=symbol,
        strategy=strategy,
        type=trade_type,
        entry_price=entry_price,
        status=status,
        message=message
    )
    db.add(trade_log_entry)
    db.commit()
    db.refresh(trade_log_entry)
    return trade_log_entry

def update_trade(
    trade_id: int,
    exit_price: float = None,
    pnl: float = None,
    status: str = None,
    message: str = None
):
    db: Session = next(get_db_session())
    trade_log_entry = db.query(TradeLog).filter(TradeLog.id == trade_id).first()
    if trade_log_entry:
        if exit_price is not None:
            trade_log_entry.exit_price = exit_price
        if pnl is not None:
            trade_log_entry.pnl = pnl
        if status is not None:
            trade_log_entry.status = status
        if message is not None:
            trade_log_entry.message = message
        db.commit()
        db.refresh(trade_log_entry)
    db.close()

def init_db():
    # This function is no longer needed as database.py handles table creation
    pass

# Placeholder for strategy performance, will be handled by main.py queries
def update_strategy_performance(strategy_id, outcome):
    pass

