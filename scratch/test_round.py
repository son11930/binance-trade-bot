from decimal import Decimal
import math

def round_step_size(quantity: float, step_size: float) -> float:
    try:
        dec_qty = Decimal(str(quantity))
        dec_step = Decimal(str(step_size))
        # Floor division ensures we round down to nearest multiple of step_size
        rounded = (dec_qty // dec_step) * dec_step
        return float(rounded)
    except Exception as e:
        print("Error:", e)
        # Fallback to math
        precision = int(round(-math.log(step_size, 10), 0))
        return math.floor(quantity * (10**precision)) / (10**precision)

import requests
info = requests.get("https://api.binance.com/api/v3/exchangeInfo?symbol=RENDERUSDT").json()
step_size = float([f for f in info['symbols'][0]['filters'] if f['filterType'] == 'LOT_SIZE'][0]['stepSize'])
min_qty = float([f for f in info['symbols'][0]['filters'] if f['filterType'] == 'LOT_SIZE'][0]['minQty'])

print(f"RENDERUSDT step_size: {step_size}, min_qty: {min_qty}")

# Test round_step_size
test_qties = [2.86234, 1.0, 0.00001, 2.86]
for q in test_qties:
    r = round_step_size(q, step_size)
    print(f"q={q} -> rounded={r} -> type={type(r)} -> str={str(r)}")
