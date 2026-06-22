import sys
import json
from datetime import datetime, timezone
import pytz

project_path = "e:/Code/binancetrade"
if project_path not in sys.path:
    sys.path.append(project_path)

from bot.binance_client import client, futures_get_position
from bot.database import SessionLocalFutures, Trade
from bot.config import SYMBOLS, FUTURES_LEVERAGE

def fix_missing_trades():
    db = SessionLocalFutures()
    count = 0
    try:
        for symbol in SYMBOLS:
            last_trade = db.query(Trade).filter(Trade.symbol == symbol, Trade.market_type == 'futures').order_by(Trade.timestamp.desc(), Trade.id.desc()).first()
            if not last_trade:
                continue

            is_open = (last_trade.position_side == "LONG" and last_trade.side == "BUY") or \
                      (last_trade.position_side == "SHORT" and last_trade.side == "SELL")
                      
            if is_open:
                pos_info = futures_get_position(symbol)
                if not pos_info:
                    continue
                amt = float(pos_info.get("positionAmt", "0"))
                if abs(amt) < 0.0001:
                    print(f"Missing close trade detected for {symbol}!")
                    b_trades = client.futures_account_trades(symbol=symbol, limit=20)
                    close_side = "SELL" if last_trade.position_side == "LONG" else "BUY"
                    
                    close_trade = None
                    for bt in reversed(b_trades):
                        if bt['side'] == close_side and float(bt.get('realizedPnl', 0)) != 0:
                            close_trade = bt
                            break
                            
                    if close_trade:
                        print(f"  -> Found closing trade on Binance at price {close_trade['price']}")
                        price = float(close_trade['price'])
                        qty = float(close_trade['qty'])
                        pnl = float(close_trade['realizedPnl'])
                        fee = float(close_trade['commission'])
                        fee_asset = close_trade['commissionAsset']
                        ts = datetime.fromtimestamp(close_trade['time'] / 1000.0, tz=timezone.utc)
                        
                        margin = (last_trade.price * qty) / FUTURES_LEVERAGE
                        pnl_pct = (pnl / margin * 100) if margin > 0 else 0.0
                        
                        new_t = Trade(
                            symbol=symbol,
                            side=close_side,
                            price=price,
                            quantity=qty,
                            market_type='futures',
                            position_side=last_trade.position_side,
                            ai_reasoning="Binance Native SL/TP (Auto-Sync)",
                            pnl_amount=pnl,
                            pnl_percent=pnl_pct,
                            fee=fee,
                            fee_asset=fee_asset,
                            timestamp=ts
                        )
                        db.add(new_t)
                        db.commit()
                        count += 1
                        print(f"  -> Successfully logged close trade for {symbol}")
                    else:
                        print(f"  -> Could not find matching close trade on Binance for {symbol}.")
    finally:
        db.close()
    
    print(f"Fixed {count} missing trades.")

if __name__ == '__main__':
    fix_missing_trades()
