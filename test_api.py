import os
from dotenv import load_dotenv
from binance.client import Client

load_dotenv()
API_KEY = os.getenv("BINANCE_API_KEY")
SECRET_KEY = os.getenv("BINANCE_SECRET_KEY")

client = Client(API_KEY, SECRET_KEY)

try:
    print("Testing futures_position_information (no symbol)...")
    pos = client.futures_position_information()
    print("List length:", len(pos))
    if len(pos) > 0:
        print("First item:", pos[0])
except Exception as e:
    print(f"Exception: {type(e)}: {e}")
