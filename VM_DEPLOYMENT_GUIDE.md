# คู่มือการนำบอทขึ้น Google Cloud VM (Free Tier) แบบละเอียด

คู่มือนี้จะสอนวิธีเช่าเครื่องเซิร์ฟเวอร์ฟรี (VM) ของ Google Cloud และวิธีตั้งค่าเพื่อให้สามารถดูหน้าเว็บของบอทจากมือถือได้ตลอด 24 ชั่วโมง โดยไม่เสียเงิน

---

## ขั้นตอนที่ 1: สร้างเครื่อง VM ฟรี (e2-micro)
1. สมัครใช้งานและล็อกอินเข้า [Google Cloud Console](https://console.cloud.google.com/)
2. ไปที่เมนู **Compute Engine** -> **VM instances** -> กดปุ่ม **Create Instance**
3. ตั้งค่าเครื่องให้ได้สิทธิ์ **ฟรี (Free Tier)** ดังนี้:
   - **Region:** ให้เลือกโซนที่เป็นของอเมริกาเท่านั้น (สำคัญมาก ถ้าเลือกโซนอื่นจะเสียเงิน) เช่น `us-central1 (Iowa)`, `us-west1 (Oregon)` หรือ `us-east1 (South Carolina)`
   - **Machine Configuration:** 
     - Series: `E2`
     - Machine type: `e2-micro (2 vCPU, 1 GB memory)`
   - **Boot disk:** เปลี่ยนเป็น `Ubuntu 22.04 LTS` และปรับขนาดเป็น `30 GB` (ฟรีไม่เกิน 30 GB)
   - **Firewall:** ติ๊กถูกที่ `Allow HTTP traffic` และ `Allow HTTPS traffic`
4. กดปุ่ม **Create** แล้วรอจนกว่าเครื่องจะสร้างเสร็จ (จะมีเลข IP ขึ้นมา)

---

## ขั้นตอนที่ 2: ตั้งค่า Firewall (เพื่อเปิด Port 8000 ให้มือถือเข้าได้)
โดยปกติ Google จะบล็อคพอร์ต 8000 ไว้ ทำให้เราเข้าดูหน้าเว็บจากมือถือไม่ได้ เราต้องไปปลดล็อกก่อน:
1. ไปที่เมนู **VPC network** -> **Firewall**
2. กดปุ่ม **Create Firewall Rule** ที่ด้านบน
3. ตั้งค่าดังนี้:
   - **Name:** `allow-bot-8000`
   - **Targets:** `All instances in the network`
   - **Source IPv4 ranges:** `0.0.0.0/0`
   - **Protocols and ports:** ติ๊กถูกที่ `TCP` และใส่เลข `8000`
4. กด **Create**

---

## ขั้นตอนที่ 3: เอาโค้ดไปรันบน VM
1. กลับไปที่หน้า **VM instances** แล้วกดปุ่ม **SSH** (จะเป็นการเปิดหน้าต่างสีดำๆ ขึ้นมา)
2. อัปเดตเครื่องและติดตั้ง Python ด้วยคำสั่ง:
   ```bash
   sudo apt update && sudo apt upgrade -y
   sudo apt install python3 python3-pip python3-venv git -y
   ```
3. ดาวน์โหลดโค้ดบอทของคุณจาก Git (เปลี่ยนลิงก์เป็นของคุณเอง):
   ```bash
   git clone <ลิงก์_GITHUB_ของคุณ> binancetrade
   cd binancetrade
   ```
4. ติดตั้งแพ็กเกจที่จำเป็น:
   ```bash
   pip3 install -r requirements.txt
   ```
   *(หมายเหตุ: หากไม่มีไฟล์ `requirements.txt` ให้ใช้ `pip3 install pandas numpy binance requests uvicorn fastapi google-genai python-dotenv`)*
5. สร้างไฟล์ `.env` เพื่อใส่คีย์ API ของคุณ (Gemini, Binance, รหัสหน้าเว็บ) ด้วยคำสั่ง `nano .env`
6. รันบอทด้วยไฟล์ที่ผมเตรียมไว้ให้:
   ```bash
   chmod +x start.sh
   ./start.sh
   ```

---

## ขั้นตอนที่ 4: เข้าดูหน้าเว็บจากมือถือ
เมื่อรันคำสั่ง `./start.sh` สำเร็จ ให้คุณเอาเลข **External IP** ของเครื่อง VM (ดูได้จากหน้าต่าง Compute Engine) ไปเปิดในบราวเซอร์มือถือ ตามด้วย `:8000` เช่น:

`http://34.123.45.67:8000`

เพียงเท่านี้บอทก็จะทำงานตลอด 24 ชั่วโมง และคุณสามารถเข้ามาเช็คดูเมื่อไหร่ก็ได้ผ่านมือถือครับ!

> **⚠️ ข้อควรระวังเรื่องค่าเน็ต (Egress)**
> หน้าเว็บของเรามีการดึงข้อมูลอัปเดตอัตโนมัติตลอดเวลา ถ้าคุณลืมปิดแท็บในมือถือทิ้งไว้ 24 ชั่วโมงติดต่อกันเป็นเวลาหลายวัน เน็ตฟรีของ Google อาจจะหมดโควต้าได้ครับ **วิธีแก้คือให้เปิดดูเป็นครั้งคราว (วันละ 1-2 ชั่วโมงสบายมาก) ดูเสร็จแล้วปิดแท็บบราวเซอร์ทิ้ง บอทก็ยังคงรันอยู่หลังบ้านปกติครับ**
