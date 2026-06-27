import paramiko
import sys

host = "45.136.254.62"
username = "root"
password = "6hl$!5CXBkgx"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    print(f"Connecting to {host}...")
    client.connect(host, username=username, password=password, timeout=10)
    
    commands = [
        "cd /root/binance-trade-bot && git pull origin main",
        "pkill -f python",
        "sudo systemctl stop binance-bot.service",
        "sudo systemctl start binance-bot.service",
        "sudo systemctl status binance-bot.service | head -n 10"
    ]
    
    for cmd in commands:
        print(f"\n> {cmd}")
        stdin, stdout, stderr = client.exec_command(cmd)
        
        out = stdout.read().decode().strip()
        err = stderr.read().decode().strip()
        
        if out: print(out)
        if err: print(f"Error: {err}")
        
    print("\n[SUCCESS] Updated code from Github and restarted binance-bot.service cleanly.")
    
except Exception as e:
    print(f"Failed to connect or execute commands: {e}")
finally:
    client.close()
