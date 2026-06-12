import os
from datetime import datetime, timezone
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
import logging

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
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    ai_risk_score = Column(Float, nullable=True)
    ai_reasoning = Column(String, nullable=True)
    paper_trade = Column(Boolean, default=True)

class SystemLog(Base):
    __tablename__ = "system_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    level = Column(String, index=True) # INFO, WARNING, ERROR
    message = Column(String)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class TradeRepository:
    @staticmethod
    def get_last_buy_price(symbol: str) -> float:
        db = SessionLocal()
        try:
            trade = db.query(Trade).filter(Trade.symbol == symbol, Trade.side == 'BUY').order_by(Trade.timestamp.desc()).first()
            if trade:
                return trade.price
            return 0.0
        except Exception as e:
            logging.exception(f"Error fetching last buy price for {symbol}")
            return 0.0
        finally:
            db.close()

    @staticmethod
    def create_trade(symbol: str, side: str, price: float, quantity: float, risk_score: float = None, reason: str = None, is_paper: bool = True):
        db = SessionLocal()
        try:
            trade = Trade(
                symbol=symbol,
                side=side,
                price=price,
                quantity=quantity,
                ai_risk_score=risk_score,
                ai_reasoning=reason,
                paper_trade=is_paper
            )
            db.add(trade)
            db.commit()
            db.refresh(trade)
            return trade
        except Exception as e:
            logging.exception(f"Error creating trade for {symbol}")
            db.rollback()
            return None
        finally:
            db.close()

class LogRepository:
    @staticmethod
    def log_event(level: str, message: str):
        db = SessionLocal()
        try:
            log_entry = SystemLog(level=level, message=message)
            db.add(log_entry)
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

    @staticmethod
    def get_recent_logs(limit: int = 100):
        db = SessionLocal()
        try:
            return db.query(SystemLog).order_by(SystemLog.timestamp.desc()).limit(limit).all()
        except Exception:
            return []
        finally:
            db.close()
