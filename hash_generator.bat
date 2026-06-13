@echo off
title Password Hash Generator
echo Installing required dependencies...
pip install -r requirements.txt >nul 2>&1
echo.
python generate_hash.py
echo.
pause
