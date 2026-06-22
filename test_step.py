import os
from dotenv import load_dotenv
from binance.client import Client

load_dotenv()
API_KEY = os.getenv("BINANCE_API_KEY")
SECRET_KEY = os.getenv("BINANCE_SECRET_KEY")

client = Client(API_KEY, SECRET_KEY)
info = client.futures_exchange_info()
for s in info['symbols']:
    if s['symbol'] == 'SOLUSDT':
        for f in s['filters']:
            if f['filterType'] == 'LOT_SIZE':
                print(f"SOLUSDT step size: {f['stepSize']}")
                break
