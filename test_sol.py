import os
from dotenv import load_dotenv
from binance.client import Client

load_dotenv()
API_KEY = os.getenv("BINANCE_API_KEY")
SECRET_KEY = os.getenv("BINANCE_SECRET_KEY")

client = Client(API_KEY, SECRET_KEY)
try:
    print("Fetching SOLUSDT position...")
    pos = client.futures_position_information(symbol="SOLUSDT")
    print(pos)
except Exception as e:
    print(f"Error: {e}")
