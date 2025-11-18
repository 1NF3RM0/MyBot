from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import datetime

DATABASE_URL = "sqlite:///./trading_app.db"

engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    email = Column(String, unique=True, index=True, nullable=True)
    
    settings = relationship("UserSettings", back_populates="user", uselist=False)
    trade_logs = relationship("TradeLog", back_populates="user")

class UserSettings(Base):
    __tablename__ = "user_settings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    
    deriv_app_id = Column(String, nullable=True)
    deriv_api_token = Column(String, nullable=True)
    
    risk_percentage = Column(Float, default=2.0)
    stop_loss_percent = Column(Float, default=10.0)
    take_profit_percent = Column(Float, default=20.0)
    
    notifications_enabled = Column(Boolean, default=False)
    active_strategies = Column(String, default="evaluate_golden_cross,evaluate_rsi_dip,evaluate_macd_crossover")

    user = relationship("User", back_populates="settings")

class TradeLog(Base):
    __tablename__ = "trade_log"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    symbol = Column(String, index=True)
    strategy = Column(String)
    type = Column(String) # e.g., 'buy', 'sell', 'proposal', 'error'
    entry_price = Column(Float, nullable=True)
    exit_price = Column(Float, nullable=True)
    pnl = Column(Float, nullable=True)
    status = Column(String) # e.g., 'open', 'closed', 'win', 'loss'
    message = Column(String, nullable=True)
    
    user = relationship("User", back_populates="trade_logs")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_db_and_tables():
    Base.metadata.create_all(bind=engine)
