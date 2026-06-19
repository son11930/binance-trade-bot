import os
import sys
from datetime import datetime, timezone
import math

# Ensure we can import from bot package
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from bot.binance_client import client
from bot.database import SessionLocalFutures, Trade
from bot.config import SYMBOLS

def sync_futures_trades():
    print("Starting Binance Futures Sync...")
    
    db = SessionLocalFutures()
    try:
        total_synced = 0
        for symbol in SYMBOLS:
            print(f"Fetching trades for {symbol}...")
            try:
                trades = client.futures_account_trades(symbol=symbol)
            except Exception as e:
                print(f"Error fetching {symbol}: {e}")
                continue
                
            if not trades:
                continue
                
            # Group trades by orderId
            grouped_orders = {}
            for t in trades:
                order_id = t.get('orderId')
                if not order_id:
                    continue
                if order_id not in grouped_orders:
                    grouped_orders[order_id] = {
                        'time': t['time'],
                        'side': t['side'],
                        'positionSide': t['positionSide'],
                        'symbol': symbol,
                        'total_qty': 0.0,
                        'total_cost': 0.0,
                        'total_pnl': 0.0,
                        'total_fee': 0.0,
                        'fee_asset': t.get('commissionAsset', 'USDT')
                    }
                
                qty = float(t['qty'])
                price = float(t['price'])
                
                grouped_orders[order_id]['total_qty'] += qty
                grouped_orders[order_id]['total_cost'] += (price * qty)
                grouped_orders[order_id]['total_pnl'] += float(t.get('realizedPnl', 0.0))
                grouped_orders[order_id]['total_fee'] += float(t.get('commission', 0.0))
                
            for order_id, order_data in grouped_orders.items():
                if order_data['total_qty'] == 0:
                    continue
                    
                # Calculate average price
                avg_price = order_data['total_cost'] / order_data['total_qty']
                qty = order_data['total_qty']
                pnl = order_data['total_pnl']
                fee = order_data['total_fee']
                fee_asset = order_data['fee_asset']
                side = order_data['side']
                pos_side = order_data['positionSide']
                
                trade_time = datetime.fromtimestamp(order_data['time'] / 1000.0, tz=timezone.utc)
                
                # Check if trade already exists
                existing = db.query(Trade).filter(
                    Trade.symbol == symbol,
                    Trade.side == side,
                    Trade.market_type == 'futures'
                ).all()
                
                is_duplicate = False
                for ex in existing:
                    # check if time is within 60 seconds (since fills can take time) and qty matches roughly
                    time_diff = abs((ex.timestamp.replace(tzinfo=timezone.utc) - trade_time).total_seconds())
                    if time_diff < 60.0 and math.isclose(ex.quantity, qty, rel_tol=1e-3):
                        is_duplicate = True
                        
                        # Update all fields to match Binance EXACTLY
                        if not math.isclose(ex.pnl_amount or 0, pnl, abs_tol=1e-4) or not math.isclose(ex.fee or 0, fee, abs_tol=1e-4) or not math.isclose(ex.price, avg_price, abs_tol=1e-4):
                            ex.pnl_amount = pnl
                            ex.fee = fee
                            ex.fee_asset = fee_asset
                            ex.price = avg_price
                            ex.quantity = qty
                            
                            # Recalculate pnl_percent
                            margin = (avg_price * qty) / 3.0
                            if margin > 0 and pnl != 0.0:
                                ex.pnl_percent = (pnl / margin) * 100
                            else:
                                ex.pnl_percent = 0.0
                                
                            ex.paper_trade = False
                            db.commit()
                        break
                        
                if not is_duplicate:
                    pnl_amount_to_save = pnl if pnl != 0.0 else None
                    pnl_percent_to_save = None
                    
                    if pnl and qty > 0 and avg_price > 0 and pnl != 0.0:
                        margin = (avg_price * qty) / 3.0
                        pnl_percent_to_save = (pnl / margin) * 100 if margin > 0 else 0.0
                        
                    new_trade = Trade(
                        symbol=symbol,
                        side=side,
                        price=avg_price,
                        quantity=qty,
                        timestamp=trade_time,
                        paper_trade=False,
                        fee=fee,
                        fee_asset=fee_asset,
                        pnl_amount=pnl_amount_to_save,
                        pnl_percent=pnl_percent_to_save,
                        position_side=pos_side,
                        market_type='futures',
                        ai_reasoning="Synced from Binance API"
                    )
                    db.add(new_trade)
                    db.commit()
                    total_synced += 1
                    print(f"  -> Added missing order: {side} {qty} {symbol} @ {avg_price:.4f}")
                    
        print(f"Sync complete! Successfully synced {total_synced} new trades from Binance Futures.")
    except Exception as e:
        print(f"Critical error during sync: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    sync_futures_trades()
