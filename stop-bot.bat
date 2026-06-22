@echo off
title Stop Binance AI System
echo ===================================================
echo Connecting to VPS to STOP the bot...
echo Please enter your password when prompted.
echo ===================================================
ssh -t root@45.136.254.62 "sudo systemctl stop binance-bot.service && echo '' && echo '[OK] Bot completely STOPPED!'"
echo.
pause
