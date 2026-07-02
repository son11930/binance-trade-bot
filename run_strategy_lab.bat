@echo off
title AI Strategy Lab Controller (Windows Launcher)
cd /d "%~dp0"
if not exist "logs" mkdir "logs"

if "%~1"=="1" goto START_DEFAULT_AUTO
if "%~1"=="stop" goto STOP_LAB
if "%~1"=="2" goto CHECK_ARG2
if not "%~1"=="" goto CHECK_ARG1
goto MENU

:CHECK_ARG2
set "trials=%~2"
if "%trials%"=="" set "trials=50"
goto START_CUSTOM_AUTO

:CHECK_ARG1
set "trials=%~1"
goto START_CUSTOM_AUTO

:MENU
cls
echo ===============================================================================
echo            AI STRATEGY LAB CONTROLLER - WINDOWS LAUNCHER
echo ===============================================================================
echo.
echo    [1] Start Lab (Default: 30 Trials - Quick Alpha Search)
echo    [2] Start Lab (Custom / Overnight Run: e.g. 100, 500, or 0 = Infinite)
echo    [3] Stop Lab (Terminate running synthesizer processes)
echo    [4] Restart Lab (Stop existing lab and start 30 trials)
echo    [5] Check Lab Status and Top 3 Alpha Blueprints
echo    [6] View Live Log Stream (Tail strategy_lab.log)
echo    [7] Update Dependencies (pip install requirements)
echo    [0] Exit
echo.
echo ===============================================================================
set /p choice="Select an option (0-7): "

if "%choice%"=="1" goto START_DEFAULT
if "%choice%"=="2" goto START_CUSTOM
if "%choice%"=="3" goto STOP_LAB
if "%choice%"=="4" goto RESTART_LAB
if "%choice%"=="5" goto CHECK_STATUS
if "%choice%"=="6" goto VIEW_LOGS
if "%choice%"=="7" goto UPDATE_DEPS
if "%choice%"=="0" goto EXIT_SCRIPT

echo [!] Invalid choice! Please try again.
timeout /t 2 >nul
goto MENU

:START_DEFAULT
echo.
echo [*] Starting AI Strategy Synthesizer Lab (30 Trials)...
echo [*] Output will be logged to logs\strategy_lab.log
if not exist logs mkdir logs
start "AI_Strategy_Synthesizer_Lab" /D "%~dp0" /min cmd /c "python bot_strategy_synthesizer.py 30 > logs\strategy_lab.log 2>&1"
echo [+] Lab launched in background! You can check status with Option [5] or logs with Option [6].
echo.
pause
goto MENU

:START_DEFAULT_AUTO
echo [*] Starting AI Strategy Synthesizer Lab (30 Trials)...
if not exist logs mkdir logs
start "AI_Strategy_Synthesizer_Lab" /D "%~dp0" /min cmd /c "python bot_strategy_synthesizer.py 30 > logs\strategy_lab.log 2>&1"
echo [+] Lab launched in background!
timeout /t 2 >nul
exit /b 0

:START_CUSTOM
echo.
echo [i] TIP: Enter 0 for INFINITE / UNLIMITED EVOLUTION MODE (Runs until stopped!)
set /p trials="Enter number of trials to run (e.g. 50, 100, 500, or 0 for Infinite): "
if "%trials%"=="" set trials=50
if "%trials%"=="0" goto PRINT_INF_1
echo [*] Starting AI Strategy Synthesizer Lab (%trials% Trials)...
goto START_CUSTOM_LAUNCH
:PRINT_INF_1
echo [*] Starting AI Strategy Synthesizer Lab in INFINITE EVOLUTION MODE...
:START_CUSTOM_LAUNCH
echo [*] Output will be logged to logs\strategy_lab.log
if not exist logs mkdir logs
start "AI_Strategy_Synthesizer_Lab" /D "%~dp0" /min cmd /c "python bot_strategy_synthesizer.py %trials% > logs\strategy_lab.log 2>&1"
echo [+] Lab launched in background!
echo.
pause
goto MENU

:START_CUSTOM_AUTO
if "%trials%"=="0" goto PRINT_INF_2
echo [*] Starting AI Strategy Synthesizer Lab (%trials% Trials)...
goto START_CUSTOM_AUTO_LAUNCH
:PRINT_INF_2
echo [*] Starting AI Strategy Synthesizer Lab in INFINITE EVOLUTION MODE...
:START_CUSTOM_AUTO_LAUNCH
if not exist logs mkdir logs
start "AI_Strategy_Synthesizer_Lab" /D "%~dp0" /min cmd /c "python bot_strategy_synthesizer.py %trials% > logs\strategy_lab.log 2>&1"
echo [+] Lab launched in background!
timeout /t 2 >nul
exit /b 0

:STOP_LAB
echo.
echo [*] Terminating all AI Strategy Synthesizer processes...
taskkill /f /fi "WINDOWTITLE eq AI_Strategy_Synthesizer_Lab*" >nul 2>&1
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*bot_strategy_synthesizer*' } | Invoke-CimMethod -MethodName Terminate" >nul 2>&1
python bot_strategy_synthesizer.py stop >nul 2>&1
echo [+] AI Strategy Synthesizer stopped.
if "%~1"=="stop" exit /b 0
echo.
pause
goto MENU

:RESTART_LAB
echo.
echo [*] Restarting Lab...
taskkill /f /fi "WINDOWTITLE eq AI_Strategy_Synthesizer_Lab*" >nul 2>&1
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*bot_strategy_synthesizer*' } | Invoke-CimMethod -MethodName Terminate" >nul 2>&1
timeout /t 2 >nul
if not exist logs mkdir logs
start "AI_Strategy_Synthesizer_Lab" /D "%~dp0" /min cmd /c "python bot_strategy_synthesizer.py 30 > logs\strategy_lab.log 2>&1"
echo [+] Lab restarted with 30 trials!
echo.
pause
goto MENU

:CHECK_STATUS
echo.
echo ===============================================================================
echo                      CURRENT LAB STATUS and TOP RESULTS
echo ===============================================================================
powershell -NoProfile -Command "$p = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*bot_strategy_synthesizer*' }; if ($p) { Write-Host '[RUNNING] (Process ID:' $p.ProcessId ')' -ForegroundColor Green } else { Write-Host '[NOT RUNNING]' -ForegroundColor Red }"
echo.
echo TOP 3 ALPHA BLUEPRINTS (from dashboard\data\strategy_leaderboard.json):
echo -------------------------------------------------------------------------------
python -c "import json, os; p='dashboard/data/strategy_leaderboard.json'; d=json.load(open(p,encoding='utf-8'))['strategies'][:3] if os.path.exists(p) else []; print('\n'.join([f'  {s[\"rank\"]}. {s[\"name\"]} | 1Y: {s.get(\"net_profit_1y\",0)}% | WinRate: {s.get(\"win_rate_1y\",0)}% | Trades: {s.get(\"total_trades_1y\",0)}' for s in d]) if d else '  No results found yet.')" 2>nul
echo -------------------------------------------------------------------------------
echo.
pause
goto MENU

:VIEW_LOGS
echo.
if not exist "logs\strategy_lab.log" (
    echo [!] Log file logs\strategy_lab.log does not exist yet. Please start the lab first!
    pause
    goto MENU
)
echo [*] Opening live log stream in new PowerShell window...
start "Live Lab Logs" /D "%~dp0" powershell -NoExit -Command "Get-Content -Path 'logs\strategy_lab.log' -Wait -Tail 30"
goto MENU

:UPDATE_DEPS
echo.
echo [*] Updating Python dependencies (including Optuna, SQLAlchemy, etc.)...
pip install -r requirements.txt
echo [+] Dependencies updated!
echo.
pause
goto MENU

:EXIT_SCRIPT
echo Exiting... Goodbye!
timeout /t 1 >nul
exit /b 0
