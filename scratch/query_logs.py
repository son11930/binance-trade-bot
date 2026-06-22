import sqlite3
import sys

# Force stdout encoding to utf-8
sys.stdout.reconfigure(encoding='utf-8')

def check_logs(db_path, market):
    print(f"\n--- Logs from {market.upper()} ({db_path}) ---")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT timestamp, level, message 
            FROM system_logs 
            ORDER BY timestamp DESC 
            LIMIT 10
        """)
        rows = cursor.fetchall()
        for row in rows:
            print(f"[{row[0]}] [{row[1]}] {row[2]}")
    except Exception as e:
        pass
    conn.close()

check_logs('trades_spot.db', 'spot')
