@echo off
setlocal
cd /d "%~dp0"

if "%~1"=="" exit /b 2
if not exist "logs" mkdir "logs"

if exist "venv\Scripts\python.exe" (
    "venv\Scripts\python.exe" "bot_strategy_synthesizer_gpu.py" %~1 > "logs\gpu_lab.log" 2>&1
) else (
    python "bot_strategy_synthesizer_gpu.py" %~1 > "logs\gpu_lab.log" 2>&1
)

set "exit_code=%ERRORLEVEL%"
endlocal & exit /b %exit_code%
