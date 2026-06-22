import os
from dotenv import load_dotenv
from binance import ThreadedWebsocketManager

load_dotenv()
API_KEY = os.getenv("BINANCE_API_KEY")
SECRET_KEY = os.getenv("BINANCE_SECRET_KEY")

twm = ThreadedWebsocketManager(api_key=API_KEY, api_secret=SECRET_KEY)
print("hasattr start_kline_futures_socket:", hasattr(twm, 'start_kline_futures_socket'))
print("hasattr start_futures_kline_socket:", hasattr(twm, 'start_futures_kline_socket'))
print("hasattr start_kline_socket:", hasattr(twm, 'start_kline_socket'))

methods = [m for m in dir(twm) if 'future' in m.lower()]
print("Futures methods in twm:", methods)
