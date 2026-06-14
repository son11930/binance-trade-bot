import os
import urllib.parse
from datetime import datetime, timezone
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
import logging

def sanitize_text(text: str) -> str:
    if not text:
        return text
    text_str = str(text)
    
    secrets = [
        ("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY")),
        ("BINANCE_API_KEY", os.getenv("BINANCE_API_KEY")),
        ("BINANCE_API_SECRET", os.getenv("BINANCE_API_SECRET")),
        ("BINANCE_SECRET_KEY", os.getenv("BINANCE_SECRET_KEY")),
        ("DASHBOARD_USER", os.getenv("DASHBOARD_USER")),
        ("DASHBOARD_PASS", os.getenv("DASHBOARD_PASS")),
        ("DASHBOARD_SECRET_SALT", os.getenv("DASHBOARD_SECRET_SALT"))
    ]
    
    # Generate AUTH_TOKEN
    user = os.getenv("DASHBOARD_USER", "")
    pwd = os.getenv("DASHBOARD_PASS", "")
    salt = os.getenv("DASHBOARD_SECRET_SALT", "")
    if user and pwd and salt:
        import hashlib
        import hmac
        auth_token = hmac.new(salt.encode(), f"{user}:{pwd}".encode(), hashlib.sha256).hexdigest()
        webhook_token = hmac.new(salt.encode(), f"{user}_webhook".encode(), hashlib.sha256).hexdigest()
        secrets.append(("AUTH_TOKEN", auth_token))
        secrets.append(("WEBHOOK_TOKEN", webhook_token))
    
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        secrets.append(("DATABASE_URL", db_url))
        if "://" in db_url and "@" in db_url:
            try:
                parsed = urllib.parse.urlparse(db_url)
                if parsed.password:
                    secrets.append(("DB_PASS", parsed.password))
                if parsed.hostname:
                    secrets.append(("DB_HOST", parsed.hostname))
            except Exception:
                pass
                
    for name, val in secrets:
        if val and len(val) > 3:
            text_str = text_str.replace(val, f"***MASKED_{name}***")
            text_str = text_str.replace(urllib.parse.quote(val), f"***MASKED_{name}***")
            
    return text_str

class SanitizedFormatter(logging.Formatter):
    def format(self, record):
        original_msg = super().format(record)
        return sanitize_text(original_msg)

def setup_logging():
    formatter = SanitizedFormatter('%(asctime)s - %(levelname)s - %(message)s')
    
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        handler = logging.StreamHandler()
        root_logger.addHandler(handler)
        
    for handler in root_logger.handlers:
        handler.setFormatter(formatter)
        
    for name, logger_obj in logging.root.manager.loggerDict.items():
        if isinstance(logger_obj, logging.Logger):
            for handler in logger_obj.handlers:
                handler.setFormatter(formatter)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./trades.db")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

if DATABASE_URL.startswith("postgres"):
    # PostgreSQL configuration (Supabase/Neon)
    # pool_pre_ping=True ensures dropped connections are automatically reconnected
    engine = create_engine(
        DATABASE_URL, 
        pool_pre_ping=True, 
        pool_size=5, 
        max_overflow=10
    )
else:
    # Local SQLite fallback
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

from sqlalchemy.sql import func

class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True)
    side = Column(String)  # BUY or SELL
    price = Column(Float)
    quantity = Column(Float)
    # timezone=True is required for PostgreSQL compatibility
    timestamp = Column(DateTime(timezone=True), default=func.now())
    ai_risk_score = Column(Float, nullable=True)
    ai_reasoning = Column(String, nullable=True)
    paper_trade = Column(Boolean, default=True)
    fee = Column(Float, nullable=True)
    fee_asset = Column(String, nullable=True)
    pnl_amount = Column(Float, nullable=True)
    pnl_percent = Column(Float, nullable=True)

class SystemLog(Base):
    __tablename__ = "system_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), default=func.now())
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
            trade = db.query(Trade).filter(Trade.symbol == symbol).order_by(Trade.timestamp.desc()).first()
            if trade and trade.side == 'BUY':
                return trade.price
            return 0.0
        except Exception:
            logging.exception(f"Error fetching last buy price for {symbol}")
            return 0.0
        finally:
            db.close()

    @staticmethod
    def create_trade(symbol: str, side: str, price: float, quantity: float, risk_score: float = None, reason: str = None, is_paper: bool = True, fee: float = None, fee_asset: str = None, pnl_amount: float = None, pnl_percent: float = None):
        db = SessionLocal()
        try:
            trade = Trade(
                symbol=symbol,
                side=side,
                price=price,
                quantity=quantity,
                ai_risk_score=risk_score,
                ai_reasoning=sanitize_text(reason) if reason else None,
                paper_trade=is_paper,
                fee=fee,
                fee_asset=fee_asset,
                pnl_amount=pnl_amount,
                pnl_percent=pnl_percent
            )
            db.add(trade)
            db.commit()
            db.refresh(trade)
            return trade
        except Exception:
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
            safe_message = sanitize_text(message)
            log_entry = SystemLog(level=level, message=safe_message)
            db.add(log_entry)
            db.commit()
        except Exception as e:
            import sys
            print(f"CRITICAL DB ERROR in LogRepository: {e}", file=sys.stderr, flush=True)
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
