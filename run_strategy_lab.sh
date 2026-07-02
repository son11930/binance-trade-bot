#!/usr/bin/env bash

# ==============================================================================
#            AI STRATEGY LAB CONTROLLER - LINUX SERVER LAUNCHER
# ==============================================================================
# Optimized for Linux servers (e.g., 2 CPU Cores, 3GB RAM)
# Uses nohup for background execution (persists after SSH disconnects).

cd "$(dirname "$0")" || exit 1
mkdir -p logs

# Determine Python command (prefer python3)
if command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
elif command -v python &>/dev/null; then
    PYTHON_CMD="python"
else
    echo "[!] Error: Python not found on this server!"
    exit 1
fi

start_lab() {
    local trials="${1:-30}"
    if [ "$trials" = "0" ]; then
        echo "[*] Starting AI Strategy Synthesizer Lab in INFINITE EVOLUTION MODE (Unlimited)..."
    else
        echo "[*] Starting AI Strategy Synthesizer Lab ($trials Trials)..."
    fi
    echo "[*] Output is logged to logs/strategy_lab.log (persistent via nohup)"
    
    # Terminate any existing lab process before starting a new one
    pkill -f "bot_strategy_synthesizer.py" 2>/dev/null
    
    # Launch in background using nohup so it stays alive after SSH disconnects
    nohup "$PYTHON_CMD" bot_strategy_synthesizer.py "$trials" > logs/strategy_lab.log 2>&1 &
    
    local pid=$!
    echo "[+] Lab launched successfully in background! (PID: $pid)"
    echo "[i] To view live logs, run: ./run_strategy_lab.sh logs  or  tail -f logs/strategy_lab.log"
}

stop_lab() {
    echo "[*] Terminating all AI Strategy Synthesizer processes..."
    pkill -f "bot_strategy_synthesizer.py" 2>/dev/null
    "$PYTHON_CMD" bot_strategy_synthesizer.py stop >/dev/null 2>&1
    echo "[+] AI Strategy Synthesizer stopped."
}

check_status() {
    echo ""
    echo "==============================================================================="
    echo "                      CURRENT LAB STATUS & TOP RESULTS"
    echo "==============================================================================="
    if pgrep -f "bot_strategy_synthesizer.py" >/dev/null 2>&1; then
        local pids=$(pgrep -f "bot_strategy_synthesizer.py" | tr '\n' ' ')
        echo -e "\033[1;32m[RUNNING]\033[0m (Process PID(s): $pids)"
    else
        echo -e "\033[1;31m[NOT RUNNING]\033[0m"
    fi
    echo ""
    echo "TOP 3 ALPHA BLUEPRINTS (from dashboard/data/strategy_leaderboard.json):"
    echo "-------------------------------------------------------------------------------"
    "$PYTHON_CMD" -c "
import json, os
p = 'dashboard/data/strategy_leaderboard.json'
if os.path.exists(p):
    try:
        data = json.load(open(p, encoding='utf-8')).get('strategies', [])[:3]
        if data:
            for s in data:
                print(f'  {s.get(\"rank\", \"-\")}. {s.get(\"name\", \"Unknown\")} | 1Y Net: {s.get(\"net_profit_1y\", 0)}% | WinRate: {s.get(\"win_rate_1y\", 0)}% | Trades: {s.get(\"total_trades_1y\", 0)}')
        else:
            print('  No results found yet.')
    except Exception as e:
        print('  Error reading leaderboard:', e)
else:
    print('  No results found yet.')
" 2>/dev/null
    echo "-------------------------------------------------------------------------------"
    echo ""
}

view_logs() {
    if [ ! -f "logs/strategy_lab.log" ]; then
        echo "[!] Log file logs/strategy_lab.log does not exist yet. Start the lab first!"
        exit 1
    fi
    echo "[*] Streaming live log stream (Press Ctrl+C to exit)..."
    tail -f -n 50 logs/strategy_lab.log
}

update_deps() {
    echo "[*] Updating Python dependencies..."
    "$PYTHON_CMD" -m pip install -r requirements.txt
    echo "[+] Dependencies updated!"
}

show_menu() {
    clear
    echo "==============================================================================="
    echo "            AI STRATEGY LAB CONTROLLER - LINUX SERVER LAUNCHER"
    echo "==============================================================================="
    echo ""
    echo "    [1] Start Lab (Default: 30 Trials - Quick Alpha Search)"
    echo "    [2] Start Lab (Custom / Overnight Run: e.g. 100, 500, or 0 = Infinite)"
    echo "    [3] Stop Lab (Terminate running synthesizer processes)"
    echo "    [4] Restart Lab (Stop existing lab and start 30 trials)"
    echo "    [5] Check Lab Status and Top 3 Alpha Blueprints"
    echo "    [6] View Live Log Stream (tail -f logs/strategy_lab.log)"
    echo "    [7] Update Dependencies (pip install requirements)"
    echo "    [0] Exit"
    echo ""
    echo "==============================================================================="
    read -p "Select an option (0-7): " choice
    
    case "$choice" in
        1) start_lab 30; read -p "Press Enter to continue..." ;;
        2) 
            read -p "Enter number of trials (e.g. 50, 100, or 0 for Infinite): " custom_trials
            start_lab "${custom_trials:-50}"
            read -p "Press Enter to continue..."
            ;;
        3) stop_lab; read -p "Press Enter to continue..." ;;
        4) stop_lab; sleep 1; start_lab 30; read -p "Press Enter to continue..." ;;
        5) check_status; read -p "Press Enter to continue..." ;;
        6) view_logs ;;
        7) update_deps; read -p "Press Enter to continue..." ;;
        0) echo "Exiting... Goodbye!"; exit 0 ;;
        *) echo "[!] Invalid choice!"; sleep 1 ;;
    esac
    show_menu
}

# Command-line argument handling
case "$1" in
    1|start)
        start_lab "${2:-30}"
        ;;
    2)
        start_lab "${2:-50}"
        ;;
    stop)
        stop_lab
        ;;
    restart)
        stop_lab
        sleep 1
        start_lab "${2:-30}"
        ;;
    status)
        check_status
        ;;
    logs|tail)
        view_logs
        ;;
    update)
        update_deps
        ;;
    ""|menu)
        show_menu
        ;;
    *)
        # If argument is numeric, treat it as custom trials
        if [[ "$1" =~ ^[0-9]+$ ]]; then
            start_lab "$1"
        else
            echo "Usage: $0 {start|stop|restart|status|logs|update|<trials>}"
            exit 1
        fi
        ;;
esac
