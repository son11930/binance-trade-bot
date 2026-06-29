import os
import sys
import logging
import time
import requests
from datetime import datetime, timezone, timedelta
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from bot.database import SessionLocalFutures, SessionLocalSpot, AIDecision, setup_logging, sanitize_text
from bot.binance_client import client

setup_logging()

def send_discord_alert(msg: str):
    webhook = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook or not webhook.startswith("https://"):
        return
    try:
        requests.post(webhook, json={"content": msg}, timeout=5)
    except Exception as e:
        logging.error(f"Discord webhook failed: {sanitize_text(str(e))}")

def track_opportunities():
    now = datetime.now(timezone.utc)
    four_hours_ago = now - timedelta(hours=4)
    
    for market_type in ['spot', 'futures']:
        db = SessionLocalFutures() if market_type == 'futures' else SessionLocalSpot()
        try:
            pending_decisions = db.query(AIDecision).filter(
                AIDecision.decision == 'HOLD',
                AIDecision.retroactive_outcome.is_(None),
                AIDecision.timestamp <= four_hours_ago
            ).limit(50).all()
            
            pending_data = [
                (d.id, d.symbol, d.proposed_direction, d.timestamp, d.ai_reasoning) 
                for d in pending_decisions
            ]
        
            for did, symbol, direction, eval_time, ai_reasoning in pending_data:
                
                if eval_time.tzinfo is None:
                    eval_time = eval_time.replace(tzinfo=timezone.utc)
                
                # Fetch 15m klines for the next 4 hours after eval_time
                end_time = eval_time + timedelta(hours=4)
                
                klines = client.get_klines(
                    symbol=symbol,
                    interval="15m",
                    startTime=int(eval_time.timestamp() * 1000),
                    endTime=int(end_time.timestamp() * 1000)
                )
                
                if not klines or len(klines) < 2:
                    continue
                    
                entry_price = float(klines[0][4]) # Close price of the candle when evaluated
                max_pnl = 0.0
                min_pnl = 0.0
                
                outcome = "Unknown"
                
                for k in klines[1:]:
                    high = float(k[2])
                    low = float(k[3])
                    
                    if direction in ["LONG", "BUY"]:
                        pnl_high = ((high - entry_price) / entry_price) * 100
                        pnl_low = ((low - entry_price) / entry_price) * 100
                    else:
                        pnl_high = ((entry_price - low) / entry_price) * 100
                        pnl_low = ((entry_price - high) / entry_price) * 100
                        
                    if pnl_high > max_pnl: max_pnl = pnl_high
                    if pnl_low < min_pnl: min_pnl = pnl_low
                    
                    # Assume SL is -1.5% and TP is 1.0%
                    if min_pnl <= -1.5:
                        outcome = "Loss"
                        break
                    elif max_pnl >= 1.0:
                        outcome = "Win"
                        break
                
                d = db.query(AIDecision).get(did)
                if not d:
                    continue
                
                d.max_pnl_reached = max_pnl
                d.max_loss_reached = min_pnl
                
                if outcome == "Win":
                    d.retroactive_outcome = "Win"
                    alert_msg = f"📉 **Missed Opportunity ({market_type.upper()})!** AI rejected a {direction} on {symbol} 4 hours ago. It would have hit **+{max_pnl:.2f}%** profit! Reason given: {ai_reasoning}"
                    send_discord_alert(alert_msg)
                    logging.info(f"Missed Opportunity on {symbol}: +{max_pnl:.2f}%")
                elif outcome == "Loss":
                    d.retroactive_outcome = "Loss"
                    logging.info(f"Good Block on {symbol}: AI correctly avoided a {min_pnl:.2f}% loss.")
                else:
                    d.retroactive_outcome = "Unknown"
                    
                db.commit()
                time.sleep(0.5) # Prevent rate limiting
                
        except Exception as e:
            logging.error(f"Error in opportunity tracker for {market_type}: {sanitize_text(str(e))}")
            db.rollback()
        finally:
            db.close()

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    track_opportunities()
