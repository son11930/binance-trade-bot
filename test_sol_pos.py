import json
from bot.binance_client import client

positions = client.futures_position_information()
sol_pos = [p for p in positions if p['symbol'] == 'SOLUSDT']
print(json.dumps(sol_pos, indent=2))
