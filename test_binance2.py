from bot.binance_client import client
positions = client.futures_position_information()
for p in positions:
    if float(p.get('positionAmt', '0')) != 0:
        print(p['symbol'], p['positionAmt'], p['positionSide'])
