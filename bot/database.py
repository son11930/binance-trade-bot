import os
import urllib.parse
from datetime import datetime, timezone
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.sql import func
import logging

# Cache secrets at module level to avoid re-hashing on every log
_SECRETS_CACHE = None

def _get_secrets_cache():
    global _SECRETS_CACHE
    if _SECRETS_CACHE is not None:
        return _SECRETS_CACHE
        
    secrets = [
        ("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY")),
        ("GROQ_API_KEY", os.getenv("GROQ_API_KEY")),
        ("BINANCE_API_KEY", os.getenv("BINANCE_API_KEY")),
        ("BINANCE_API_SECRET", os.getenv("BINANCE_API_SECRET")),
        ("BINANCE_SECRET_KEY", os.getenv("BINANCE_SECRET_KEY")),
        ("DASHBOARD_USER", os.getenv("DASHBOARD_USER")),
        ("DASHBOARD_PASS", os.getenv("DASHBOARD_PASS")),
        ("DASHBOARD_SECRET_SALT", os.getenv("DASHBOARD_SECRET_SALT")),
        ("DISCORD_WEBHOOK_URL", os.getenv("DISCORD_WEBHOOK_URL"))
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
        jwt_secret = hmac.new(salt.encode(), b"jwt", hashlib.sha256).hexdigest()
        secrets.append(("AUTH_TOKEN", auth_token))
        secrets.append(("WEBHOOK_TOKEN", webhook_token))
        secrets.append(("JWT_SECRET", jwt_secret))
    
    for url_name in ["DATABASE_URL_SPOT", "DATABASE_URL_FUTURES", "DATABASE_URL"]:
        db_url = os.getenv(url_name)
        if db_url:
            secrets.append((url_name, db_url))
            if "://" in db_url and "@" in db_url:
                try:
                    parsed = urllib.parse.urlparse(db_url)
                    if parsed.password:
                        secrets.append(("DB_PASS", parsed.password))
                    if parsed.hostname:
                        secrets.append(("DB_HOST", parsed.hostname))
                except Exception:
                    pass
    
    final_secrets = []
    for name, val in secrets:
        if val and len(val) > 3:
            final_secrets.append((name, val))
            quoted_val = urllib.parse.quote(val)
            if quoted_val != val:
                final_secrets.append((name, quoted_val))
                
    unique_secrets = []
    seen = set()
    for name, val in final_secrets:
        if val not in seen:
            seen.add(val)
            unique_secrets.append((name, val))
            
    _SECRETS_CACHE = unique_secrets
    return _SECRETS_CACHE

def sanitize_text(text: str) -> str:
    if not text:
        return text
    text_str = str(text)
    
    # We must allow the cache to be reset if env vars change (mostly for tests)
    if os.environ.get("TEST_RESET_SECRETS") == "1":
        global _SECRETS_CACHE
        _SECRETS_CACHE = None
    
    secrets = _get_secrets_cache()
    
    for name, val in secrets:
        text_str = text_str.replace(val, f"***MASKED_{name}***")
            
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

def get_engine(db_url: str):
    if db_url and db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
        
    if db_url and db_url.startswith("postgres"):
        return create_engine(
            db_url, 
            pool_pre_ping=True, 
            pool_size=5, 
            max_overflow=10
        )
    else:
        # SQLite
        from sqlalchemy import event
        engine = create_engine(db_url, connect_args={"check_same_thread": False, "timeout": 15})
        
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()
            
        return engine

import sqlalchemy
from bot.config import DATABASE_URL_SPOT, DATABASE_URL_FUTURES

engine_spot = get_engine(DATABASE_URL_SPOT)
engine_futures = get_engine(DATABASE_URL_FUTURES)

SessionLocalSpot = sessionmaker(autocommit=False, autoflush=False, bind=engine_spot)
SessionLocalFutures = sessionmaker(autocommit=False, autoflush=False, bind=engine_futures)

Base = declarative_base()

class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True)
    side = Column(String)  # BUY or SELL
    price = Column(Float)
    quantity = Column(Float)
    timestamp = Column(DateTime(timezone=True), default=func.now(), index=True)
    ai_risk_score = Column(Float, nullable=True)
    ai_reasoning = Column(String, nullable=True)
    paper_trade = Column(Boolean, default=True)
    fee = Column(Float, nullable=True)
    fee_asset = Column(String, nullable=True)
    pnl_amount = Column(Float, nullable=True)
    pnl_percent = Column(Float, nullable=True)
    position_side = Column(String, nullable=True)
    market_type = Column(String, default="spot", index=True)

    __table_args__ = (
        sqlalchemy.Index('ix_trade_symbol_market_time', 'symbol', 'market_type', 'timestamp'),
    )

class SystemLog(Base):
    __tablename__ = "system_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), default=func.now(), index=True)
    level = Column(String, index=True) # INFO, WARNING, ERROR
    message = Column(String)
    market_type = Column(String, default="spot", index=True)

class AIDecision(Base):
    __tablename__ = "ai_decisions"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True)
    timestamp = Column(DateTime(timezone=True), default=func.now(), index=True)
    proposed_direction = Column(String) # LONG or SHORT
    risk_score = Column(Float, nullable=True)
    decision = Column(String) # PROCEED or HOLD
    ai_reasoning = Column(String, nullable=True)
    tech_context = Column(String, nullable=True)
    market_type = Column(String, default="spot", index=True)
    
    # Tracking for Opportunity Cost Tracker
    retroactive_outcome = Column(String, nullable=True) # Win, Loss, Unknown
    max_pnl_reached = Column(Float, nullable=True)
    max_loss_reached = Column(Float, nullable=True)

    __table_args__ = (
        sqlalchemy.Index('ix_ai_decision_symbol_market_time', 'symbol', 'market_type', 'timestamp'),
    )

class StrategyLeaderboard(Base):
    __tablename__ = "strategy_leaderboard"
    id = Column(Integer, primary_key=True, index=True)
    rank = Column(Integer)
    name = Column(String(100))
    net_profit_1m = Column(Float)
    net_profit_3m = Column(Float)
    net_profit_6m = Column(Float)
    net_profit_1y = Column(Float)
    win_rate_1y = Column(Float)
    max_drawdown = Column(Float)
    total_trades_1y = Column(Integer)
    moonshots_1y = Column(Integer)
    parameters_json = Column(String(2000))
    created_at = Column(DateTime(timezone=True), default=func.now())

def init_db():
    Base.metadata.create_all(bind=engine_spot)
    Base.metadata.create_all(bind=engine_futures)

def get_db(market_type: str = 'spot'):
    if market_type == 'futures':
        db = SessionLocalFutures()
    else:
        db = SessionLocalSpot()
    try:
        yield db
    finally:
        db.close()

class TradeRepository:
    @staticmethod
    def save_ai_decision(symbol: str, proposed_direction: str, risk_score: float, decision: str, ai_reasoning: str, tech_context: str, market_type: str = 'spot'):
        db = SessionLocalFutures() if market_type == 'futures' else SessionLocalSpot()
        try:
            ai_dec = AIDecision(
                symbol=symbol,
                proposed_direction=proposed_direction,
                risk_score=risk_score,
                decision=decision,
                ai_reasoning=sanitize_text(ai_reasoning) if ai_reasoning else None,
                tech_context=sanitize_text(tech_context) if tech_context else None,
                market_type=market_type
            )
            db.add(ai_dec)
            db.commit()
        except Exception as e:
            db.rollback()
            logging.error(f"Error saving AI decision for {symbol} ({market_type}): {sanitize_text(str(e))}")
        finally:
            db.close()

    @staticmethod
    def get_last_buy_price(symbol: str, market_type: str = 'spot') -> float:
        db = SessionLocalFutures() if market_type == 'futures' else SessionLocalSpot()
        try:
            trade = db.query(Trade).filter(Trade.symbol == symbol, Trade.market_type == market_type).order_by(Trade.timestamp.desc(), Trade.id.desc()).first()
            if trade and trade.side == 'BUY':
                return trade.price
            return 0.0
        except Exception as e:
            logging.error(f"Error fetching last buy price for {symbol} ({market_type}): {sanitize_text(str(e))}")
            return 0.0
        finally:
            db.close()

    @staticmethod
    def create_trade(symbol: str, side: str, price: float, quantity: float, risk_score: float = None, reason: str = None, is_paper: bool = True, fee: float = None, fee_asset: str = None, pnl_amount: float = None, pnl_percent: float = None, market_type: str = 'spot', position_side: str = None):
        db = SessionLocalFutures() if market_type == 'futures' else SessionLocalSpot()
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
                pnl_percent=pnl_percent,
                position_side=position_side,
                market_type=market_type
            )
            db.add(trade)
            db.commit()
            db.refresh(trade)
            
            # Convert to dictionary before closing session to avoid DetachedInstanceError
            trade_dict = {
                "id": trade.id,
                "symbol": trade.symbol,
                "side": trade.side,
                "price": trade.price,
                "quantity": trade.quantity,
                "ai_risk_score": trade.ai_risk_score,
                "ai_reasoning": trade.ai_reasoning,
                "paper_trade": trade.paper_trade,
                "fee": trade.fee,
                "fee_asset": trade.fee_asset,
                "pnl_amount": trade.pnl_amount,
                "pnl_percent": trade.pnl_percent,
                "position_side": trade.position_side,
                "market_type": trade.market_type,
                "timestamp": trade.timestamp
            }
            return trade_dict
        except Exception as e:
            db.rollback()
            logging.error(f"Error creating trade for {symbol} ({market_type}): {sanitize_text(str(e))}")
            return None
        finally:
            db.close()

    @staticmethod
    def get_recent_losing_trades(symbol: str, limit: int = 5, market_type: str = 'spot'):
        db = SessionLocalFutures() if market_type == 'futures' else SessionLocalSpot()
        try:
            trades = db.query(Trade).filter(
                Trade.symbol == symbol, 
                Trade.market_type == market_type,
                Trade.pnl_percent < 0
            ).order_by(Trade.timestamp.desc()).limit(limit).all()
            
            result = []
            for t in trades:
                result.append({
                    "timestamp": t.timestamp,
                    "side": t.side,
                    "position_side": t.position_side,
                    "pnl_percent": t.pnl_percent,
                    "ai_reasoning": t.ai_reasoning
                })
            return result
        except Exception as e:
            logging.error(f"Error fetching losing trades for {symbol} ({market_type}): {sanitize_text(str(e))}")
            return []
        finally:
            db.close()

    @staticmethod
    def get_recent_winning_trades(symbol: str, limit: int = 5, market_type: str = 'spot'):
        db = SessionLocalFutures() if market_type == 'futures' else SessionLocalSpot()
        try:
            trades = db.query(Trade).filter(
                Trade.symbol == symbol, 
                Trade.market_type == market_type,
                Trade.pnl_percent > 0
            ).order_by(Trade.timestamp.desc()).limit(limit).all()
            
            result = []
            for t in trades:
                result.append({
                    "timestamp": t.timestamp,
                    "side": t.side,
                    "position_side": t.position_side,
                    "pnl_percent": t.pnl_percent,
                    "ai_reasoning": t.ai_reasoning
                })
            return result
        except Exception as e:
            logging.error(f"Error fetching winning trades for {symbol} ({market_type}): {sanitize_text(str(e))}")
            return []
        finally:
            db.close()

class LogRepository:
    @staticmethod
    def log_event(level: str, message: str, market_type: str = 'spot'):
        db = SessionLocalFutures() if market_type == 'futures' else SessionLocalSpot()
        try:
            safe_message = sanitize_text(message)
            log_entry = SystemLog(level=level, message=safe_message, market_type=market_type)
            db.add(log_entry)
            db.commit()
        except Exception as e:
            import sys
            print(f"CRITICAL DB ERROR in LogRepository: {sanitize_text(str(e))}", file=sys.stderr, flush=True)
            db.rollback()
        finally:
            db.close()

    @staticmethod
    def get_recent_logs(limit: int = 100, market_type: str = 'spot'):
        db = SessionLocalFutures() if market_type == 'futures' else SessionLocalSpot()
        try:
            return db.query(SystemLog).filter(SystemLog.market_type == market_type).order_by(SystemLog.timestamp.desc()).limit(limit).all()
        except Exception:
            return []
        finally:
            db.close()
