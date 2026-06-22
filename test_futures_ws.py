import os
import time
from dotenv import load_dotenv
from binance import ThreadedWebsocketManager

load_dotenv()
API_KEY = os.getenv("BINANCE_API_KEY")
SECRET_KEY = os.getenv("BINANCE_SECRET_KEY")

twm = ThreadedWebsocketManager(api_key=API_KEY, api_secret=SECRET_KEY)
twm.start()

def handle_socket_message(msg):
    print(f"Full MSG: {msg}")

print("Starting futures socket for BTCUSDT...")
twm.start_kline_futures_socket(callback=handle_socket_message, symbol='BTCUSDT', interval='1m')

print("Waiting for messages...")
time.sleep(2)
print("Stopping...")
twm.stop()
