import sqlite3
import os

print("Starting migration...")

if not os.path.exists('trades.db'):
    print("Old trades.db not found. Nothing to migrate.")
    exit(0)

# Connect to both DBs
old_conn = sqlite3.connect('trades.db')
new_conn = sqlite3.connect('trades_spot.db')

old_cursor = old_conn.cursor()
new_cursor = new_conn.cursor()

try:
    # Get all trades
    old_cursor.execute('SELECT * FROM trades')
    trades = old_cursor.fetchall()
    
    trades_migrated = 0
    # Insert into new DB
    for trade in trades:
        columns = "symbol, side, price, quantity, timestamp, ai_risk_score, ai_reasoning, paper_trade, fee, fee_asset, pnl_amount, pnl_percent, market_type"
        values = (trade[1], trade[2], trade[3], trade[4], trade[5], trade[6], trade[7], trade[8], trade[9], trade[10], trade[11], trade[12], 'spot')
        
        new_cursor.execute("SELECT id FROM trades WHERE symbol=? AND timestamp=?", (trade[1], trade[5]))
        if not new_cursor.fetchone():
            new_cursor.execute(f"INSERT INTO trades ({columns}) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", values)
            trades_migrated += 1
    
    new_conn.commit()
    print(f"Migrated {trades_migrated} trades to trades_spot.db")
except Exception as e:
    print("Error migrating trades:", e)

try:
    # Same for logs
    old_cursor.execute('SELECT * FROM system_logs')
    logs = old_cursor.fetchall()
    
    logs_migrated = 0
    for log in logs:
        new_cursor.execute("SELECT id FROM system_logs WHERE timestamp=? AND message=?", (log[1], log[3]))
        if not new_cursor.fetchone():
            new_cursor.execute("INSERT INTO system_logs (timestamp, level, message, market_type) VALUES (?, ?, ?, ?)", (log[1], log[2], log[3], 'spot'))
            logs_migrated += 1
    
    new_conn.commit()
    print(f"Migrated {logs_migrated} logs to trades_spot.db")
except Exception as e:
    print("Error migrating logs:", e)

old_conn.close()
new_conn.close()
print("Migration script finished successfully.")
