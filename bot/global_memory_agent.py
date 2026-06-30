import os
import sys
import logging
from datetime import datetime, timezone, timedelta
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from bot.database import SessionLocalFutures, SessionLocalSpot, Trade, AIDecision, setup_logging, sanitize_text
from bot.ai_engine import _call_model
from bot.webhook_notifier import send_discord_alert

setup_logging()

def fetch_daily_stats(market_type: str):
    now = datetime.now(timezone.utc)
    one_day_ago = now - timedelta(days=1)
    
    stats = {
        "wins": 0, "losses": 0, "missed_opportunities": 0, "good_blocks": 0,
        "win_details": [], "loss_details": [], "missed_details": []
    }
    
    db = None
    try:
        db = SessionLocalFutures() if market_type == 'futures' else SessionLocalSpot()
        all_wins = db.query(Trade).filter(Trade.timestamp >= one_day_ago, Trade.pnl_percent > 0).all()
        all_losses = db.query(Trade).filter(Trade.timestamp >= one_day_ago, Trade.pnl_percent <= 0).all()
        
        win_count = len(all_wins)
        loss_count = len(all_losses)
        
        gross_profit = sum(t.pnl_percent for t in all_wins)
        gross_loss = abs(sum(t.pnl_percent for t in all_losses))
        
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else (999.9 if gross_profit > 0 else 0)
        net_profit = gross_profit - gross_loss
        
        stats["gross_profit"] = gross_profit
        stats["gross_loss"] = gross_loss
        stats["profit_factor"] = profit_factor
        stats["net_profit"] = net_profit
        
        recent_wins = sorted(all_wins, key=lambda x: x.timestamp, reverse=True)[:5]
        recent_losses = sorted(all_losses, key=lambda x: x.timestamp, reverse=True)[:5]
        
        stats["wins"] += win_count
        stats["losses"] += loss_count
        stats["win_details"].extend([f"[{market_type.upper()}] {t.symbol} {t.side} {t.pnl_percent:.2f}% (Reason: {t.ai_reasoning})" for t in recent_wins])
        stats["loss_details"].extend([f"[{market_type.upper()}] {t.symbol} {t.side} {t.pnl_percent:.2f}% (Reason: {t.ai_reasoning})" for t in recent_losses])
        
        missed_count = db.query(AIDecision).filter(
            AIDecision.timestamp >= one_day_ago,
            AIDecision.decision == 'HOLD',
            AIDecision.retroactive_outcome == 'Win'
        ).count()
        
        good_blocks_count = db.query(AIDecision).filter(
            AIDecision.timestamp >= one_day_ago,
            AIDecision.decision == 'HOLD',
            AIDecision.retroactive_outcome == 'Loss'
        ).count()
        
        recent_missed = db.query(AIDecision).filter(
            AIDecision.timestamp >= one_day_ago,
            AIDecision.decision == 'HOLD',
            AIDecision.retroactive_outcome == 'Win'
        ).order_by(AIDecision.timestamp.desc()).limit(5).all()
        
        stats["missed_opportunities"] += missed_count
        stats["good_blocks"] += good_blocks_count
        stats["missed_details"].extend([f"[{market_type.upper()}] {d.symbol} {d.proposed_direction} (Reason: {d.ai_reasoning})" for d in recent_missed])
        
    except Exception as e:
        logging.error(f"Error fetching stats for {market_type}: {sanitize_text(str(e))}")
    finally:
        if db:
            db.close()
            
    # Take top 5
    stats["win_details"] = stats["win_details"][:5]
    stats["loss_details"] = stats["loss_details"][:5]
    stats["missed_details"] = stats["missed_details"][:5]
    
    if stats["wins"] == 0 and stats["losses"] == 0 and stats["missed_opportunities"] == 0 and stats["good_blocks"] == 0:
        return None
        
    return stats

def generate_global_memory():
    for market_type in ['spot', 'futures']:
        stats = fetch_daily_stats(market_type)
        if not stats:
            continue

        prompt = f"""Analyze the following 24-hour trading performance data for our crypto bot ({market_type.upper()}).
CRITICAL INSTRUCTION: Evaluate performance based on Profit Factor and Net Profit %, NOT Win Rate. A strategy with a low win rate but a high Profit Factor (>1.5) is excellent. A strategy with a high win rate but negative Net Profit % is terrible.

Performance Metrics:
- Net Profit %: {stats.get('net_profit', 0):.2f}%
- Profit Factor (Gross Profit / Gross Loss): {stats.get('profit_factor', 0):.2f}
- Win/Loss Count: {stats['wins']} Wins / {stats['losses']} Losses
- Gross Profit: {stats.get('gross_profit', 0):.2f}%
- Gross Loss: {stats.get('gross_loss', 0):.2f}%

Missed Opportunities (false HOLDs that would have won): {stats['missed_opportunities']}
Good Blocks (HOLDs that prevented losses): {stats['good_blocks']}

Recent Wins:
{chr(10).join(stats['win_details'])}

Recent Losses:
{chr(10).join(stats['loss_details'])}

Recent Missed Opportunities:
{chr(10).join(stats['missed_details'])}

Generate a 3-bullet-point 'Global Market Context' summarizing what strategies are yielding high risk/reward, what traps are causing large drawdowns, and if the AI is being too cautious. Keep it extremely concise and actionable. Focus on actual profitability, not just winning count.
"""
        success = False
        models = ['groq-llama-3.1-8b-instant', 'gemini-3.1-flash-lite', 'groq-qwen-2.5-32b', 'groq-mixtral-8x7b-32768']
        
        for m in models:
            try:
                res = _call_model(m, prompt, is_json=False)
                filename = f"global_memory_{market_type}.txt"
                with open(os.path.join(os.path.dirname(__file__), "..", filename), "w", encoding="utf-8") as f:
                    f.write(res.text)
                logging.info(f"Successfully updated {filename} using {m}")
                
                # Flex Mode: Send to Discord
                send_discord_alert(f"🧠 **AI Market Briefing [{market_type.upper()}]**\n\n{res.text}")
                
                success = True
                break
            except Exception as e:
                logging.warning(f"Failed to generate global memory with {m} for {market_type}: {sanitize_text(str(e))}")
                
        if not success:
            logging.error(f"All models failed to generate global memory for {market_type}.")

if __name__ == "__main__":
    generate_global_memory()
