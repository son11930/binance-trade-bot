@echo off
title AI Strategy Lab - REMOTE SERVER CONTROLLER (root@45.136.254.62)
cd /d "%~dp0"

set "SERVER_USER=root"
set "SERVER_HOST=45.136.254.62"
set "SERVER_DIR=/root/binance-trade-bot"
set "SSH_CMD=ssh -t -o BatchMode=yes -o ConnectTimeout=10 %SERVER_USER%@%SERVER_HOST%"

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
echo      AI STRATEGY LAB - REMOTE SERVER MANAGER (root@45.136.254.62)
echo ===============================================================================
echo.
echo    [1] Start Lab on Server (Default: 30 Trials - Quick Alpha Search)
echo    [2] Start Lab on Server (Custom / Overnight Run: e.g. 100, 500, or 0 = Infinite)
echo    [3] Stop Lab on Server (Terminate running synthesizer processes)
echo    [4] Restart Lab on Server (Stop existing lab and start 30 trials)
echo    [5] Check Lab Status and Top 3 Alpha Blueprints on Server
echo    [6] View Live Log Stream from Server (Tail strategy_lab.log)
echo    [7] Sync Code & Update Dependencies on Server (Git Pull + Pip Install)
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
echo [*] Syncing Git and Starting AI Strategy Synthesizer Lab (30 Trials) on Server...
echo [*] Output will be logged to logs/strategy_lab.log on the remote server.
%SSH_CMD% "cd %SERVER_DIR% && git stash && git pull origin main && chmod +x run_strategy_lab.sh && ./run_strategy_lab.sh 30"
echo.
echo [+] Command sent to server! You can check status with Option [5] or logs with Option [6].
pause
goto MENU

:START_DEFAULT_AUTO
echo [*] Starting AI Strategy Synthesizer Lab (30 Trials) on Server...
%SSH_CMD% "cd %SERVER_DIR% && git stash && git pull origin main && chmod +x run_strategy_lab.sh && ./run_strategy_lab.sh 30"
echo [+] Lab launched on remote server!
timeout /t 2 >nul
exit /b 0

:START_CUSTOM
echo.
echo [i] TIP: Enter 0 for INFINITE / UNLIMITED EVOLUTION MODE (Runs until stopped!)
set /p trials="Enter number of trials to run on Server (e.g. 50, 100, 500, or 0 for Infinite): "
if "%trials%"=="" set trials=50
if "%trials%"=="0" goto PRINT_INF_1
echo [*] Syncing Git and Starting AI Strategy Synthesizer Lab (%trials% Trials) on Server...
goto START_CUSTOM_LAUNCH
:PRINT_INF_1
echo [*] Syncing Git and Starting AI Strategy Synthesizer Lab in INFINITE EVOLUTION MODE on Server...
:START_CUSTOM_LAUNCH
%SSH_CMD% "cd %SERVER_DIR% && git stash && git pull origin main && chmod +x run_strategy_lab.sh && ./run_strategy_lab.sh %trials%"
echo.
echo [+] Command sent to server!
pause
goto MENU

:START_CUSTOM_AUTO
if "%trials%"=="0" goto PRINT_INF_2
echo [*] Starting AI Strategy Synthesizer Lab (%trials% Trials) on Server...
goto START_CUSTOM_AUTO_LAUNCH
:PRINT_INF_2
echo [*] Starting AI Strategy Synthesizer Lab in INFINITE EVOLUTION MODE on Server...
:START_CUSTOM_AUTO_LAUNCH
%SSH_CMD% "cd %SERVER_DIR% && git stash && git pull origin main && chmod +x run_strategy_lab.sh && ./run_strategy_lab.sh %trials%"
echo [+] Lab launched on remote server!
timeout /t 2 >nul
exit /b 0

:STOP_LAB
echo.
echo [*] Terminating all AI Strategy Synthesizer processes on Remote Server...
%SSH_CMD% "cd %SERVER_DIR% && chmod +x run_strategy_lab.sh && ./run_strategy_lab.sh stop"
echo [+] AI Strategy Synthesizer stopped on server.
if "%~1"=="stop" exit /b 0
echo.
pause
goto MENU

:RESTART_LAB
echo.
echo [*] Restarting Lab on Remote Server...
%SSH_CMD% "cd %SERVER_DIR% && git stash && git pull origin main && chmod +x run_strategy_lab.sh && ./run_strategy_lab.sh restart 30"
echo [+] Lab restarted on remote server with 30 trials!
echo.
pause
goto MENU

:CHECK_STATUS
echo.
echo [*] Checking Lab Status on Remote Server...
%SSH_CMD% "cd %SERVER_DIR% && chmod +x run_strategy_lab.sh && ./run_strategy_lab.sh status"
echo.
pause
goto MENU

:VIEW_LOGS
echo.
echo [*] Connecting to Remote Server to Stream Live Logs (Press Ctrl+C to exit)...
%SSH_CMD% "cd %SERVER_DIR% && tail -f -n 50 logs/strategy_lab.log"
goto MENU

:UPDATE_DEPS
echo.
echo [*] Syncing Git and Updating Python dependencies on Remote Server...
%SSH_CMD% "cd %SERVER_DIR% && git stash && git pull origin main && python3 -m pip install -r requirements.txt"
echo [+] Dependencies updated on remote server!
echo.
pause
goto MENU

:EXIT_SCRIPT
echo Exiting... Goodbye!
timeout /t 1 >nul
exit /b 0
