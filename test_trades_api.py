import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from api.server import get_db_updates

try:
    trades_data, logs_data, stats_data = get_db_updates(market_type='futures')
    print("Success! Trades fetched:", len(trades_data))
except Exception as e:
    import traceback
    traceback.print_exc()
