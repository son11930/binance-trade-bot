@echo off
chcp 65001 >nul
title 🧬 AI Strategy Lab Controller (Windows Launcher)
cd /d "%~dp0"
if not exist "logs" mkdir "logs"

:MENU
cls
echo ===============================================================================
echo            🧬 AI STRATEGY LAB CONTROLLER - WINDOWS LAUNCHER 🧬
echo ===============================================================================
echo.
echo    [1] 🚀 Start Lab (Default: 30 Trials - Quick Alpha Search)
echo    [2] 🌙 Start Lab (Custom / Overnight Run e.g. 100, 500 Trials)
echo    [3] 🛑 Stop Lab (Terminate running synthesizer processes)
echo    [4] 🔄 Restart Lab (Stop existing lab and start 30 trials)
echo    [5] 📊 Check Lab Status ^& Top 3 Alpha Blueprints
echo    [6] 📜 View Live Log Stream (Tail strategy_lab.log)
echo    [7] 📦 Update Dependencies (pip install requirements)
echo    [0] ❌ Exit
echo.
echo ===============================================================================
set /p choice="👉 Select an option (0-7): "

if "%choice%"=="1" goto START_DEFAULT
if "%choice%"=="2" goto START_CUSTOM
if "%choice%"=="3" goto STOP_LAB
if "%choice%"=="4" goto RESTART_LAB
if "%choice%"=="5" goto CHECK_STATUS
if "%choice%"=="6" goto VIEW_LOGS
if "%choice%"=="7" goto UPDATE_DEPS
if "%choice%"=="0" goto EXIT_SCRIPT

echo ⚠️ Invalid choice! Please try again.
timeout /t 2 >nul
goto MENU

:START_DEFAULT
echo.
echo 🚀 Starting AI Strategy Synthesizer Lab (30 Trials)...
echo 📋 Output will be logged to logs\strategy_lab.log
start "AI_Strategy_Synthesizer_Lab" /min cmd /c "python -c "from bot_strategy_synthesizer import run_synthesizer_lab; run_synthesizer_lab(n_trials=30)" > logs\strategy_lab.log 2>&1"
echo ✅ Lab launched in background! You can check status with Option [5] or logs with Option [6].
echo.
pause
goto MENU

:START_CUSTOM
echo.
set /p trials="🔢 Enter number of trials to run (e.g. 50, 100, 500): "
if "%trials%"=="" set trials=50
echo 🌙 Starting AI Strategy Synthesizer Lab (%trials% Trials)...
echo 📋 Output will be logged to logs\strategy_lab.log
start "AI_Strategy_Synthesizer_Lab" /min cmd /c "python -c "from bot_strategy_synthesizer import run_synthesizer_lab; run_synthesizer_lab(n_trials=%trials%)" > logs\strategy_lab.log 2>&1"
echo ✅ Lab launched in background for %trials% trials!
echo.
pause
goto MENU

:STOP_LAB
echo.
echo 🛑 Terminating all AI Strategy Synthesizer processes...
taskkill /f /fi "WINDOWTITLE eq AI_Strategy_Synthesizer_Lab*" >nul 2>&1
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*bot_strategy_synthesizer*' } | Invoke-CimMethod -MethodName Terminate" >nul 2>&1
echo ✅ AI Strategy Synthesizer stopped.
echo.
pause
goto MENU

:RESTART_LAB
echo.
echo 🔄 Restarting Lab...
taskkill /f /fi "WINDOWTITLE eq AI_Strategy_Synthesizer_Lab*" >nul 2>&1
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*bot_strategy_synthesizer*' } | Invoke-CimMethod -MethodName Terminate" >nul 2>&1
timeout /t 2 >nul
start "AI_Strategy_Synthesizer_Lab" /min cmd /c "python -c "from bot_strategy_synthesizer import run_synthesizer_lab; run_synthesizer_lab(n_trials=30)" > logs\strategy_lab.log 2>&1"
echo ✅ Lab restarted with 30 trials!
echo.
pause
goto MENU

:CHECK_STATUS
echo.
echo ===============================================================================
echo                      📊 CURRENT LAB STATUS ^& TOP RESULTS
echo ===============================================================================
powershell -NoProfile -Command "$p = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*bot_strategy_synthesizer*' }; if ($p) { Write-Host '🟢 STATUS: RUNNING (Process ID:' $p.ProcessId ')' -ForegroundColor Green } else { Write-Host '🛑 STATUS: NOT RUNNING' -ForegroundColor Red }"
echo.
echo 🏆 TOP 3 ALPHA BLUEPRINTS (from dashboard\data\strategy_leaderboard.json):
echo -------------------------------------------------------------------------------
python -c "import json, os; p='dashboard/data/strategy_leaderboard.json'; d=json.load(open(p,encoding='utf-8'))['strategies'][:3] if os.path.exists(p) else []; print('\n'.join([f'  {s[\"rank\"]}. {s[\"name\"]} | 1Y: {s.get(\"net_profit_1y\",0)}% | WinRate: {s.get(\"win_rate_1y\",0)}% | Trades: {s.get(\"total_trades_1y\",0)}' for s in d]) if d else '  No results found yet.')" 2>nul
echo -------------------------------------------------------------------------------
echo.
pause
goto MENU

:VIEW_LOGS
echo.
if not exist "logs\strategy_lab.log" (
    echo ⚠️ Log file logs\strategy_lab.log does not exist yet. Please start the lab first!
    pause
    goto MENU
)
echo 📜 Opening live log stream in new PowerShell window...
start "📜 Live Lab Logs" powershell -NoExit -Command "Get-Content -Path 'logs\strategy_lab.log' -Wait -Tail 30"
goto MENU

:UPDATE_DEPS
echo.
echo 📦 Updating Python dependencies (including Optuna, SQLAlchemy, etc.)...
pip install -r requirements.txt
echo ✅ Dependencies updated!
echo.
pause
goto MENU

:EXIT_SCRIPT
echo 👋 Exiting... Goodbye!
timeout /t 1 >nul
exit /b 0
