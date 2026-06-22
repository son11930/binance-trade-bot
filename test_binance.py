import json
from binance.client import Client
from bot.config import API_KEY, API_SECRET
client = Client(API_KEY, API_SECRET)
positions = client.futures_position_information()
for p in positions:
    if float(p.get('positionAmt', '0')) != 0:
        print(p['symbol'], p['positionAmt'], p['positionSide'])
