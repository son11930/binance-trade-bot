#!/bin/bash

echo "==================================================="
echo "       Starting Binance AI Trading System...       "
echo "==================================================="
echo ""

# Export environment variables if needed
# source .env

echo "[1/2] Starting API Web Server in background..."
python3 -m uvicorn api.server:app --host 0.0.0.0 --port 8000 &
SERVER_PID=$!

echo "[2/2] Starting Trading Bot Logic..."
python3 -m bot.main &
BOT_PID=$!

echo ""
echo "==================================================="
echo "Systems are running! Press Ctrl+C to stop both."
echo "==================================================="

# Wait for background processes to finish (or Ctrl+C to kill them)
trap "kill $SERVER_PID $BOT_PID; exit" INT TERM
wait
