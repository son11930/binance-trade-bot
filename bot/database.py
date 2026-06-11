import os
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = "sqlite:///./trades.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True)
    side = Column(String)  # BUY or SELL
    price = Column(Float)
    quantity = Column(Float)
    timestamp = Column(DateTime, default=datetime.utcnow)
    ai_risk_score = Column(Float, nullable=True)
    ai_reasoning = Column(String, nullable=True)
    paper_trade = Column(Boolean, default=True)

# Create tables
Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_last_buy_price(symbol: str) -> float:
    db = SessionLocal()
    try:
        trade = db.query(Trade).filter(Trade.symbol == symbol, Trade.side == 'BUY').order_by(Trade.timestamp.desc()).first()
        if trade:
            return trade.price
        return 0.0
    except Exception as e:
        print(f"Error fetching last buy price: {e}")
        return 0.0
    finally:
        db.close()
