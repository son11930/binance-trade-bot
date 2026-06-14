# Ubuntu VPS Deployment Guide (systemd)

This guide provides step-by-step instructions for deploying the Binance AI Trading Bot on an Ubuntu VPS (Recommended: 3 Core, 3GB RAM or higher). It covers setting up the environment, installing dependencies, and configuring `systemd` to run the bot as a background service.

## Prerequisites

- Ubuntu 20.04, 22.04, or 24.04 server.
- A user account with `sudo` privileges.
- Your API keys (Binance API Key/Secret, Google Gemini API Key).

## ทำไมถึงแนะนำ systemd แทนที่จะใช้ screen?
หลายคนอาจคุ้นเคยกับการเปิด `screen` หรือ `tmux` แล้วรันสคริปต์ทิ้งไว้ ซึ่งใช้งานได้ดีครับ **แต่สำหรับบอทเทรด เราแนะนำให้ใช้ `systemd` มากกว่าด้วยเหตุผลดังนี้:**
1. **Auto-Restart (เริ่มทำงานใหม่เมื่อพัง):** ถ้าบอทเกิด Error หรือค้างจนหลุด `systemd` จะสามารถสั่งรันบอทขึ้นมาใหม่ได้เองทันทีใน 10 วินาที 
2. **Auto-Boot (ทำงานทันทีเมื่อเซิร์ฟเวอร์เปิด):** หากเซิร์ฟเวอร์ (VPS) รีสตาร์ทตัวเอง บอทจะเริ่มทำงานเองอัตโนมัติโดยที่คุณไม่ต้องรีบ SSH เข้าไปเปิด `screen` ใหม่
3. **Log Management:** `systemd` มีระบบเก็บ Log ในตัวที่ดูง่ายกว่า ทำให้เราย้อนดูได้ว่าเกิดอะไรขึ้นเมื่อวานนี้

---

## 🛠 วิธีใช้งาน `nano` แบบเข้าใจง่าย (สำหรับมือใหม่)
`nano` เป็นโปรแกรมแก้ไขข้อความ (Text Editor) บน Terminal ที่ใช้งานง่ายที่สุดครับ

1. **เปิดไฟล์:** พิมพ์ `nano ชื่อไฟล์` เช่น `nano .env`
2. **การพิมพ์:** พิมพ์ข้อความ ก๊อปปี้มาวาง (คลิกขวาที่หน้าจอ Terminal) ได้เหมือนพิมพ์งานบน Notepad ปกติ ใช้ลูกศรเลื่อนเคอร์เซอร์
3. **การเซฟ (Save):** 
   - กดปุ่ม `Ctrl` ค้างไว้ แล้วกดตัว `O` (ตัวโอ ไม่ใช่เลขศูนย์)
   - ระบบจะถามชื่อไฟล์ที่ต้องการเซฟ ให้กด `Enter` ไปได้เลยเพื่อยืนยัน
4. **การออกจากโปรแกรม (Exit):**
   - กดปุ่ม `Ctrl` ค้างไว้ แล้วกดตัว `X`

---

## Step 1: System Update & Install Dependencies

First, SSH into your VPS and update the system packages:

```bash
sudo apt update && sudo apt upgrade -y
```

Install Python 3, pip, git, and the Python virtual environment package:

```bash
sudo apt install python3 python3-pip python3-venv git -y
```

## Step 2: Clone the Repository

Clone the trading bot code to your desired directory (e.g., your home directory or `/opt/`):

```bash
cd ~
git clone https://github.com/son11930/binance-trade-bot.git
cd binance-trade-bot
```

## Step 3: Setup Virtual Environment & Install Requirements

It is highly recommended to use a virtual environment to isolate the Python dependencies.

```bash
# Create a virtual environment named 'venv'
python3 -m venv venv

# Activate the virtual environment
source venv/bin/activate

# Install the required packages
pip install -r requirements.txt
```

## Step 4: Configure Environment Variables

Create the `.env` file from the sample or your existing setup:

```bash
nano .env
```

Add your keys inside the `.env` file. For example:
```ini
BINANCE_API_KEY=your_binance_api_key
BINANCE_API_SECRET=your_binance_api_secret
GEMINI_API_KEY=your_gemini_api_key

# Other configurations as needed
# ...
```
Save and exit (`Ctrl+O`, `Enter`, `Ctrl+X`).

## Step 5: Configure Background Service (systemd)

To ensure the bot runs in the background and restarts automatically if the server reboots or the bot crashes, we will set up a `systemd` service.

1.  **Create the service file:**
    ```bash
    sudo nano /etc/systemd/system/binance-bot.service
    ```

2.  **Paste the following configuration:**
    *(Important: Replace `your_username` with your actual VPS username (e.g., `root` or `ubuntu`). Also, ensure the `WorkingDirectory` matches where you cloned the repo).*

    ```ini
    [Unit]
    Description=Binance AI Trading Bot Service
    After=network.target

    [Service]
    Type=simple
    # Replace 'your_username' with your actual username
    User=your_username
    Group=your_username

    # Update this path if you cloned it elsewhere
    WorkingDirectory=/home/your_username/binance-trade-bot

    # We use start.sh which we've updated to auto-pull from git
    # Using bash to execute the script
    ExecStart=/bin/bash /home/your_username/binance-trade-bot/start.sh

    # Always restart the service if it crashes
    Restart=always
    RestartSec=10

    # Environment variables (Optional, can rely on .env file)
    # Environment=PYTHONUNBUFFERED=1

    [Install]
    WantedBy=multi-user.target
    ```

    Save and exit.

## Step 6: Start and Enable the Service

Reload the `systemd` daemon to recognize the new service:

```bash
sudo systemctl daemon-reload
```

Enable the service to start automatically on system boot:

```bash
sudo systemctl enable binance-bot.service
```

Start the service:

```bash
sudo systemctl start binance-bot.service
```

## Step 7: Check Status and Logs

You can check if the service is running successfully:

```bash
sudo systemctl status binance-bot.service
```

To view the live logs of the bot:

```bash
sudo journalctl -u binance-bot.service -f
```
Press `Ctrl+C` to exit the log view.

---

### Updating the Bot
Since we added `git pull` inside `start.sh`, whenever you want to apply the latest updates from GitHub, you simply need to restart the service:

```bash
sudo systemctl restart binance-bot.service
```
The script will automatically fetch and pull the latest code before spinning up the processes.
