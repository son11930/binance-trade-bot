import os
import time
from dotenv import load_dotenv
from binance import ThreadedWebsocketManager

load_dotenv()
API_KEY = os.getenv("BINANCE_API_KEY")
SECRET_KEY = os.getenv("BINANCE_SECRET_KEY")

twm = ThreadedWebsocketManager(api_key=API_KEY, api_secret=SECRET_KEY)
twm.start()

print("hasattr start_multiplex_socket:", hasattr(twm, 'start_multiplex_socket'))
print("hasattr start_futures_multiplex_socket:", hasattr(twm, 'start_futures_multiplex_socket'))

def handle_socket_message(msg):
    print(f"Full MSG: {msg}")

print("Starting multiplex sockets...")
spot_streams = ['btcusdt@kline_15m', 'ethusdt@kline_15m']
twm.start_multiplex_socket(callback=handle_socket_message, streams=spot_streams)

futures_streams = ['btcusdt@continuousKline_5m', 'ethusdt@continuousKline_5m']
twm.start_futures_multiplex_socket(callback=handle_socket_message, streams=futures_streams)

print("Waiting for messages...")
time.sleep(3)
print("Stopping...")
twm.stop()
