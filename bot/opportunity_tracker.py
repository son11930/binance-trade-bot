import os
import sys
import logging
import time
import requests
from datetime import datetime, timezone, timedelta
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from bot.database import SessionLocalFutures, SessionLocalSpot, AIDecision
from bot.binance_client import get_historical_klines

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def send_discord_alert(msg: str):
    webhook = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook:
        return
    try:
        requests.post(webhook, json={"content": msg}, timeout=5)
    except Exception as e:
        logging.error(f"Discord webhook failed: {e}")

def track_opportunities():
    db = SessionLocalFutures()
    now = datetime.now(timezone.utc)
    four_hours_ago = now - timedelta(hours=4)
    
    try:
        pending_decisions = db.query(AIDecision).filter(
            AIDecision.decision == 'HOLD',
            AIDecision.retroactive_outcome == None,
            AIDecision.timestamp <= four_hours_ago
        ).limit(50).all()
        
        for d in pending_decisions:
            symbol = d.symbol
            direction = d.proposed_direction
            eval_time = d.timestamp
            
            # Fetch 15m klines for the next 4 hours after eval_time
            end_time = eval_time + timedelta(hours=4)
            
            klines = get_historical_klines(symbol, "15m", int(eval_time.timestamp() * 1000), int(end_time.timestamp() * 1000))
            if not klines or len(klines) < 2:
                continue
                
            entry_price = float(klines[0][4]) # Close price of the candle when evaluated
            max_pnl = 0.0
            min_pnl = 0.0
            
            outcome = "Unknown"
            
            for k in klines[1:]:
                high = float(k[2])
                low = float(k[3])
                
                if direction == "LONG":
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
            
            d.max_pnl_reached = max_pnl
            d.max_loss_reached = min_pnl
            
            if outcome == "Win":
                d.retroactive_outcome = "Win"
                alert_msg = f"📉 **Missed Opportunity!** AI rejected a {direction} on {symbol} 4 hours ago. It would have hit **+{max_pnl:.2f}%** profit! Reason given: {d.ai_reasoning}"
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
        logging.error(f"Error in opportunity tracker: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    track_opportunities()
