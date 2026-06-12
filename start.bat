@echo off
title Binance AI System Launcher

echo ===================================================
echo        Starting Binance AI Trading System...
echo ===================================================
echo.

echo [1/2] Starting API Web Server...
start "Binance AI Server" cmd /k "title Binance AI Server && python -m uvicorn api.server:app --host 0.0.0.0"

echo [2/2] Starting Trading Bot Logic...
start "Binance Trading Bot" cmd /k "title Binance Trading Bot && python -m bot.main"

echo.
echo ===================================================
echo Both systems have been launched in separate windows!
echo You can now close this launcher window.
echo ===================================================
timeout /t 5 >nul
exit
