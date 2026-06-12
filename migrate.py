import sqlite3

try:
    conn = sqlite3.connect('trades.db')
    cursor = conn.cursor()
    cursor.execute("ALTER TABLE trades ADD COLUMN fee FLOAT;")
    cursor.execute("ALTER TABLE trades ADD COLUMN fee_asset VARCHAR;")
    cursor.execute("ALTER TABLE trades ADD COLUMN pnl_amount FLOAT;")
    cursor.execute("ALTER TABLE trades ADD COLUMN pnl_percent FLOAT;")
    conn.commit()
    conn.close()
    print("Migration successful")
except Exception as e:
    print(f"Error: {e}")
