import sqlite3
import sys

# Ensure utf-8 output for emojis
sys.stdout.reconfigure(encoding='utf-8')

def check_logs(db_name, title):
    try:
        conn = sqlite3.connect(db_name)
        c = conn.cursor()
        c.execute("SELECT timestamp, level, message FROM system_logs ORDER BY id DESC LIMIT 15")
        print(f'--- {title} ---')
        for row in c.fetchall():
            print(f'{row[0]} | {row[1]} | {row[2][:150]}')
    except Exception as e:
        print(f'{title} DB Error:', e)

check_logs('trades_spot.db', 'SPOT LOGS')
check_logs('trades_futures.db', 'FUTURES LOGS')
