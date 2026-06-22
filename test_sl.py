import os
from dotenv import load_dotenv
from binance.client import Client

load_dotenv()
API_KEY = os.getenv("BINANCE_API_KEY")
SECRET_KEY = os.getenv("BINANCE_SECRET_KEY")

client = Client(API_KEY, SECRET_KEY)

try:
    print("Testing place SL order for SOLUSDT...")
    res = client.futures_create_order(
        symbol='SOLUSDT',
        side='BUY',
        positionSide='SHORT',
        type='STOP_MARKET',
        stopPrice='73.00',
        closePosition=True,
        timeInForce='GTC'
    )
    print(res)
except Exception as e:
    print(f"Error: {e}")
