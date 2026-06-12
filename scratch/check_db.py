import sqlite3

conn = sqlite3.connect('trades.db')
cursor = conn.cursor()
cursor.execute('SELECT id, symbol, side, ai_reasoning FROM trades WHERE side="SELL" AND ai_reasoning="Manual SELL"')
rows = cursor.fetchall()
print(f"Found {len(rows)} manual sell rows:")
for r in rows:
    print(r)
