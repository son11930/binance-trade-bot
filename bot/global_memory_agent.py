import os
import sys
import logging
from datetime import datetime, timezone, timedelta
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from bot.database import SessionLocalFutures, SessionLocalSpot, Trade, AIDecision
from bot.ai_engine import _call_model

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def fetch_daily_stats():
    db = SessionLocalFutures()
    now = datetime.now(timezone.utc)
    one_day_ago = now - timedelta(days=1)
    
    try:
        # Fetch trades
        trades = db.query(Trade).filter(Trade.timestamp >= one_day_ago).all()
        wins = [t for t in trades if t.pnl_percent and t.pnl_percent > 0]
        losses = [t for t in trades if t.pnl_percent and t.pnl_percent <= 0]
        
        # Fetch missed opportunities
        decisions = db.query(AIDecision).filter(
            AIDecision.timestamp >= one_day_ago,
            AIDecision.decision == 'HOLD'
        ).all()
        
        missed = [d for d in decisions if d.retroactive_outcome == 'Win']
        good_blocks = [d for d in decisions if d.retroactive_outcome == 'Loss']
        
        return {
            "wins": len(wins),
            "losses": len(losses),
            "missed_opportunities": len(missed),
            "good_blocks": len(good_blocks),
            "win_details": [f"{t.symbol} {t.side} {t.pnl_percent:.2f}% (Reason: {t.ai_reasoning})" for t in wins[:5]],
            "loss_details": [f"{t.symbol} {t.side} {t.pnl_percent:.2f}% (Reason: {t.ai_reasoning})" for t in losses[:5]],
            "missed_details": [f"{d.symbol} {d.proposed_direction} (Reason: {d.ai_reasoning})" for d in missed[:5]]
        }
    except Exception as e:
        logging.error(f"Error fetching stats: {e}")
        return None
    finally:
        db.close()

def generate_global_memory():
    stats = fetch_daily_stats()
    if not stats:
        return

    prompt = f"""Analyze the following 24-hour trading performance data for a crypto futures bot.
Wins: {stats['wins']}, Losses: {stats['losses']}
Missed Opportunities (false HOLDs that would have won): {stats['missed_opportunities']}
Good Blocks (HOLDs that prevented losses): {stats['good_blocks']}

Recent Wins:
{chr(10).join(stats['win_details'])}

Recent Losses:
{chr(10).join(stats['loss_details'])}

Recent Missed Opportunities:
{chr(10).join(stats['missed_details'])}

Generate a 3-bullet-point 'Global Market Context' summarizing what strategies are working, what traps to avoid, and if the AI is being too cautious. Keep it extremely concise and actionable.
"""
    
    try:
        res = _call_model('groq-llama-3.1-8b-instant', prompt, is_json=False)
        with open(os.path.join(os.path.dirname(__file__), "..", "global_memory.txt"), "w", encoding="utf-8") as f:
            f.write(res.text)
        logging.info("Successfully updated global_memory.txt")
    except Exception as e:
        logging.error(f"Failed to generate global memory: {e}")

if __name__ == "__main__":
    generate_global_memory()
