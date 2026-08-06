import sqlite3
import os

dbs = ['/root/binance-trade-bot/trades.db', '/root/binance-trade-bot/trades_spot.db', '/root/binance-trade-bot/trades_futures.db']
for db_path in dbs:
    if os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
            conn.execute("DELETE FROM system_logs")
            conn.commit()
            conn.close()
            print(f"Cleared system_logs in {db_path}")
        except Exception as e:
            print(f"Error in {db_path}: {e}")
    else:
        print(f"Not found: {db_path}")
