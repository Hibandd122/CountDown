import discord
import os
import asyncio
from datetime import datetime, timezone, timedelta
from flask import Flask
from threading import Thread

# ================= CẤU HÌNH =================
TOKEN = os.environ.get("DISCORD_TOKEN")
TARGET_STR = "April, 03 2026 at 08:30 PM"
DATE_FORMAT = "%B, %d %Y at %I:%M %p"

# Khởi tạo Client (Mode giả lập người dùng)
client = discord.Client()
app = Flask(__name__)

# ================= LOGIC TÍNH TOÁN =================
def get_status_content():
    vn_tz = timezone(timedelta(hours=7))
    now = datetime.now(vn_tz)
    try:
        target = datetime.strptime(TARGET_STR, DATE_FORMAT).replace(tzinfo=vn_tz)
    except:
        return "Lỗi ngày tháng"
        
    delta = target - now
    if delta.total_seconds() <= 0:
        return "Sự kiện đã bắt đầu! 🎉"

    days = delta.days
    hours = (delta.seconds // 3600)
    minutes = (delta.seconds % 3600) // 60
    
    # Text hiển thị
    return f"Còn {days}d {hours}h {minutes}m"

# ================= BACKGROUND TASK =================
async def status_task():
    """Vòng lặp chạy ngầm để cập nhật status"""
    await client.wait_until_ready()
    print(f"✅ Đã đăng nhập thành công vào: {client.user}")
    
    while not client.is_closed():
        try:
            status_text = get_status_content()
            
            # Đổi Custom Status
            # Lưu ý: discord.py-self dùng CustomActivity để set status chữ
            activity = discord.CustomActivity(name=status_text)
            
            # status=discord.Status.dnd : Set trạng thái "Không làm phiền" (Đỏ)
            # status=discord.Status.online : Set trạng thái "Online" (Xanh)
            await client.change_presence(status=discord.Status.dnd, activity=activity)
            
            print(f"Updated: {status_text}")
            
            # Chờ 120s (2 phút) để an toàn, tránh bị Discord nghi ngờ
            await asyncio.sleep(120) 
            
        except Exception as e:
            print(f"❌ Lỗi update: {e}")
            await asyncio.sleep(60)

@client.event
async def on_ready():
    # Khi bot khởi động xong, chạy vòng lặp update
    client.loop.create_task(status_task())

# ================= WEB SERVER (KEEP ALIVE) =================
@app.route('/')
def home():
    if client.is_ready():
        return f"Bot đang chạy trên acc: {client.user}", 200
    return "Bot đang khởi động...", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

def run_discord_bot():
    if not TOKEN:
        print("❌ Lỗi: Chưa có Token!")
        return
    try:
        client.run(TOKEN)
    except Exception as e:
        print(f"❌ Lỗi Login: {e}")
        # Nếu bị lỗi token không hợp lệ, cần check lại token

if __name__ == "__main__":
    # Chạy Web Server ở luồng riêng
    t = Thread(target=run_flask)
    t.start()
    
    # Chạy Discord Bot ở luồng chính
    run_discord_bot()
