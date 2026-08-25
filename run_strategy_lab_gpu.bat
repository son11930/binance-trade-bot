@echo off
title AI Strategy Lab GPU - RTX 3070 Controller (Windows Launcher)
cd /d "%~dp0"
if not exist "logs" mkdir "logs"

REM ── CUDA PATH SETUP (ลง CUDA Toolkit ที่ E:\Cuda toolkit) ──
set "CUDA_PATH=E:\Cuda toolkit"
set "CUDA_HOME=E:\Cuda toolkit"
set "PATH=%CUDA_PATH%\bin\x64;%CUDA_PATH%\bin;%PATH%"

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
echo      AI STRATEGY LAB - GPU EDITION (NVIDIA RTX 3070) - WINDOWS LAUNCHER
echo ===============================================================================
echo.
echo   Engine  : GPU CUDA (RTX 3070 8GB) + i7-11800H 8-Core Multi-Worker Optuna
echo   Speed   : Uses GPU CUDA for High-Throughput Genomes/sec
echo   Shared  : Syncs results to SAME Aiven DB as CPU lab (combined leaderboard!)
echo.
echo   [1] Start GPU Lab (Default: 100 Trials - Fast Alpha Search)
echo   [2] Start GPU Lab (Custom Trials: e.g. 500, 5000, or 0 = Infinite)
echo   [3] Stop GPU Lab (Terminate running processes)
echo   [4] Restart GPU Lab (Stop existing and start 100 trials)
echo   [5] Check Lab Status and Top 3 Alpha Blueprints
echo   [6] View Live Log Stream (Tail logs\gpu_lab.log)
echo   [7] Install / Check GPU Dependencies (Numba + CuPy CUDA)
echo   [8] Test GPU Detection (Check if RTX 3070 is ready)
echo   [0] Exit
echo.
echo ===============================================================================
set /p choice="Select an option (0-8): "

if "%choice%"=="1" goto START_DEFAULT
if "%choice%"=="2" goto START_CUSTOM
if "%choice%"=="3" goto STOP_LAB
if "%choice%"=="4" goto RESTART_LAB
if "%choice%"=="5" goto CHECK_STATUS
if "%choice%"=="6" goto VIEW_LOGS
if "%choice%"=="7" goto INSTALL_GPU_DEPS
if "%choice%"=="8" goto TEST_GPU
if "%choice%"=="0" goto EXIT_SCRIPT

echo [!] Invalid choice!
timeout /t 2 >nul
goto MENU

:START_DEFAULT
echo.
echo [*] Starting GPU Strategy Lab (100 Trials)...
echo [*] Output logged to logs\gpu_lab.log
if not exist logs mkdir logs
start "AI_GPU_Strategy_Lab" /D "%~dp0" /min cmd /c "python bot_strategy_synthesizer_gpu.py 100 > logs\gpu_lab.log 2>&1"
echo [+] GPU Lab launched in background!
echo [i] Check status with [5] or view logs with [6].
echo.
pause
goto MENU

:START_DEFAULT_AUTO
echo [*] Starting GPU Strategy Lab (100 Trials)...
if not exist logs mkdir logs
start "AI_GPU_Strategy_Lab" /D "%~dp0" /min cmd /c "python bot_strategy_synthesizer_gpu.py 100 > logs\gpu_lab.log 2>&1"
echo [+] GPU Lab launched!
timeout /t 2 >nul
exit /b 0

:START_CUSTOM
echo.
echo [i] TIP: Enter 0 for INFINITE MODE (Runs until you stop! RTX 3070 can handle millions of trials overnight)
set /p trials="Enter number of trials (e.g. 500, 5000, 50000, or 0 for Infinite): "
if "%trials%"=="" set trials=100
if "%trials%"=="0" goto PRINT_INF_1
echo [*] Starting GPU Lab (%trials% Trials)...
goto START_CUSTOM_LAUNCH
:PRINT_INF_1
echo [*] Starting GPU Lab in INFINITE EVOLUTION MODE...
echo [*] Your RTX 3070 will evolve millions of strategy genomes overnight!
:START_CUSTOM_LAUNCH
echo [*] Output logged to logs\gpu_lab.log
if not exist logs mkdir logs
start "AI_GPU_Strategy_Lab" /D "%~dp0" /min cmd /c "python bot_strategy_synthesizer_gpu.py %trials% > logs\gpu_lab.log 2>&1"
echo [+] GPU Lab launched in background!
echo.
pause
goto MENU

:START_CUSTOM_AUTO
if "%trials%"=="0" goto PRINT_INF_2
echo [*] Starting GPU Lab (%trials% Trials)...
goto START_CUSTOM_AUTO_LAUNCH
:PRINT_INF_2
echo [*] Starting GPU Lab in INFINITE EVOLUTION MODE...
:START_CUSTOM_AUTO_LAUNCH
if not exist logs mkdir logs
start "AI_GPU_Strategy_Lab" /D "%~dp0" /min cmd /c "python bot_strategy_synthesizer_gpu.py %trials% > logs\gpu_lab.log 2>&1"
echo [+] GPU Lab launched!
timeout /t 2 >nul
exit /b 0

:STOP_LAB
echo.
echo [*] Sending graceful stop signal to GPU Strategy Lab...
echo stop > stop_lab.txt
echo [+] Signal sent. The lab will finish the current batch, save to DB, and then exit.
echo [!] Please wait up to 1-2 minutes for the process to close cleanly.
if "%~1"=="stop" exit /b 0
echo.
pause
goto MENU

:RESTART_LAB
echo.
echo [*] Restarting GPU Lab...
taskkill /f /fi "WINDOWTITLE eq AI_GPU_Strategy_Lab*" >nul 2>&1
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*bot_strategy_synthesizer_gpu*' } | Invoke-CimMethod -MethodName Terminate" >nul 2>&1
timeout /t 2 >nul
if not exist logs mkdir logs
start "AI_GPU_Strategy_Lab" /D "%~dp0" /min cmd /c "python bot_strategy_synthesizer_gpu.py 100 > logs\gpu_lab.log 2>&1"
echo [+] GPU Lab restarted with 100 trials!
echo.
pause
goto MENU

:CHECK_STATUS
echo.
echo ===============================================================================
echo               GPU LAB STATUS and TOP 3 ALPHA BLUEPRINTS
echo ===============================================================================
powershell -NoProfile -Command "$p = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*bot_strategy_synthesizer_gpu*' }; if ($p) { Write-Host '[GPU LAB RUNNING] (PID:' $p.ProcessId ')' -ForegroundColor Cyan } else { Write-Host '[NOT RUNNING]' -ForegroundColor Red }"
echo.
echo GPU Detection:
python -c "from numba import cuda; print('[GPU READY]', cuda.get_current_device().name.decode()) if cuda.is_available() else print('[NO GPU] Running in CPU fallback mode')" 2>nul || echo [!] Numba not installed. Run option [7] to install.
echo.
echo TOP 3 ALPHA BLUEPRINTS (from dashboard\data\strategy_leaderboard.json):
echo -------------------------------------------------------------------------------
python -c "import json, os; p='dashboard/data/strategy_leaderboard.json'; d=json.load(open(p,encoding='utf-8'))['strategies'][:3] if os.path.exists(p) else []; [print(f'  {s[chr(114)+chr(97)+chr(110)+chr(107)]}. {s[chr(110)+chr(97)+chr(109)+chr(101)]} | 1Y: {s.get(chr(110)+chr(101)+chr(116)+chr(95)+chr(112)+chr(114)+chr(111)+chr(102)+chr(105)+chr(116)+chr(95)+chr(49)+chr(121),0)}%% | Win: {s.get(chr(119)+chr(105)+chr(110)+chr(95)+chr(114)+chr(97)+chr(116)+chr(101)+chr(95)+chr(49)+chr(121),0)}%%') for s in d] if d else print('  No results yet.')" 2>nul
echo -------------------------------------------------------------------------------
echo.
echo Live Progress (from dashboard\data\lab_progress.json):
python -c "import json,os; p='dashboard/data/lab_progress.json'; d=json.load(open(p)) if os.path.exists(p) else {}; print(f'  Status: {d.get(chr(115)+chr(116)+chr(97)+chr(116)+chr(117)+chr(115),chr(110)+chr(47)+chr(97))} | Trial: {d.get(chr(99)+chr(117)+chr(114)+chr(114)+chr(101)+chr(110)+chr(116)+chr(95)+chr(116)+chr(114)+chr(105)+chr(97)+chr(108),0)}/{d.get(chr(116)+chr(111)+chr(116)+chr(97)+chr(108)+chr(95)+chr(116)+chr(114)+chr(105)+chr(97)+chr(108)+chr(115),0)} | Score: {d.get(chr(98)+chr(101)+chr(115)+chr(116)+chr(95)+chr(115)+chr(99)+chr(111)+chr(114)+chr(101),0)} | Engine: {d.get(chr(101)+chr(110)+chr(103)+chr(105)+chr(110)+chr(101),chr(67)+chr(80)+chr(85))}') if d else print('  No progress data yet.')" 2>nul
echo.
pause
goto MENU

:VIEW_LOGS
echo.
if not exist "logs\gpu_lab.log" (
    echo [!] logs\gpu_lab.log not found yet. Start the GPU Lab first!
    pause
    goto MENU
)
echo [*] Opening Live GPU Lab Log Stream (Press Ctrl+C to close log, lab keeps running)...
start "GPU Lab Live Logs" /D "%~dp0" powershell -NoExit -Command "Get-Content -Path 'logs\gpu_lab.log' -Wait -Tail 40"
goto MENU

:INSTALL_GPU_DEPS
echo.
echo ===============================================================================
echo              INSTALLING GPU DEPENDENCIES FOR RTX 3070
echo ===============================================================================
echo.
echo [1/3] Checking CUDA version...
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader 2>nul || echo [!] nvidia-smi not found. Please ensure NVIDIA drivers are installed.
echo.
echo [2/3] Installing Numba (CUDA JIT compiler)...
pip install numba
echo.
echo [3/3] Installing CuPy (GPU NumPy) for CUDA 11.x...
echo [i] If you have CUDA 12.x, change 'cupy-cuda11x' to 'cupy-cuda12x' below.
pip install cupy-cuda12x
echo.
echo [+] GPU dependencies installation complete!
echo [i] Restart and use option [8] to test GPU detection.
echo.
pause
goto MENU

:TEST_GPU
echo.
echo ===============================================================================
echo                        GPU DETECTION TEST
echo ===============================================================================
echo.
echo Testing NVIDIA RTX 3070 readiness for AI Strategy Lab...
echo.
python -c "
import sys
print('Python:', sys.version)
print()

# Test 1: Numba CUDA
try:
    from numba import cuda
    if cuda.is_available():
        dev = cuda.get_current_device()
        cc = dev.compute_capability
        print('[PASS] Numba CUDA:', dev.name.decode(), f'| Compute Capability {cc[0]}.{cc[1]}')
    else:
        print('[FAIL] Numba installed but no CUDA GPU detected!')
except ImportError:
    print('[FAIL] Numba NOT installed. Run option [7] to install.')

print()

# Test 2: CuPy
try:
    import cupy as cp
    x = cp.array([1.0, 2.0, 3.0])
    y = cp.sum(x)
    print(f'[PASS] CuPy {cp.__version__}: GPU array sum = {float(y)} (expected 6.0)')
except ImportError:
    print('[FAIL] CuPy NOT installed. Run option [7] to install.')
except Exception as e:
    print(f'[FAIL] CuPy error: {e}')

print()

# Test 3: Optuna
try:
    import optuna; optuna.logging.set_verbosity(optuna.logging.CRITICAL)
    s = optuna.create_study(); s.optimize(lambda t: t.suggest_float('x', 0, 1), n_trials=5, n_jobs=4)
    print(f'[PASS] Optuna multi-core (4 workers) test passed!')
except Exception as e:
    print(f'[FAIL] Optuna error: {e}')

print()
print('GPU Lab readiness check complete!')
"
echo.
pause
goto MENU

:EXIT_SCRIPT
echo Exiting... Goodbye! Your RTX 3070 is ready to evolve millions of strategies!
timeout /t 1 >nul
exit /b 0
