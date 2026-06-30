import sqlite3
import os

def check_logs():
    for db_name in ['trades_futures.db', 'futures.db', 'spot_trading.db', 'trades.db']:
        if os.path.exists(db_name):
            print(f"Checking {db_name}...")
            try:
                conn = sqlite3.connect(db_name)
                c = conn.cursor()
                c.execute("SELECT timestamp, level, message FROM system_logs WHERE message LIKE '%APT%' ORDER BY timestamp DESC LIMIT 50")
                rows = c.fetchall()
                for row in rows:
                    print(f"[{row[0]}] {row[1]}: {row[2]}")
                conn.close()
            except Exception as e:
                pass

if __name__ == '__main__':
    check_logs()
