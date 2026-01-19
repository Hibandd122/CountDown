import discord
import os
import asyncio
import logging
import random
import time
from datetime import datetime, timezone, timedelta
from flask import Flask, render_template_string
from threading import Thread

# ================= 1. SYSTEM SETUP =================
# Cấu hình Logging (Nhìn chuyên nghiệp hơn print)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("VN_Countdown_Bot")

# Cấu hình Token & Ngày
TOKEN = os.environ.get("DISCORD_TOKEN")
TARGET_STR = "April, 03 2026 at 08:30 PM"
DATE_FORMAT = "%B, %d %Y at %I:%M %p"

# Global State (Để truyền dữ liệu từ Bot sang Web)
bot_state = {
    "status": "Starting...",
    "last_updated": "Never",
    "target": TARGET_STR,
    "user": "Unknown",
    "ping": "N/A"
}

client = discord.Client()
app = Flask(__name__)

# ================= 2. DOMAIN LOGIC (PYTHON) =================
def calculate_time_data():
    """Tính toán thời gian và chọn Emoji phù hợp"""
    vn_tz = timezone(timedelta(hours=7))
    now = datetime.now(vn_tz)
    
    try:
        target = datetime.strptime(TARGET_STR, DATE_FORMAT).replace(tzinfo=vn_tz)
    except Exception as e:
        logger.error(f"Date Parsing Error: {e}")
        return "Lỗi Config", "⚠️"
        
    delta = target - now
    total_seconds = delta.total_seconds()

    if total_seconds <= 0:
        return "Sự kiện đã bắt đầu! 🎉", "🎆"

    days = delta.days
    hours = (delta.seconds // 3600)
    minutes = (delta.seconds % 3600) // 60
    
    # --- SMART EMOJI LOGIC ---
    if days > 100:
        emoji = "📅"  # Còn rất xa
    elif days > 30:
        emoji = "🗓️"  # Tầm trung
    elif days > 7:
        emoji = "⏳"  # Bắt đầu đếm ngược
    elif days > 1:
        emoji = "🔥"  # Nóng rồi
    elif days > 0:
        emoji = "🚨"  # Khẩn cấp (dưới 48h)
    else:
        emoji = "🧨"  # Cực gấp (dưới 24h)
    
    # Format Text đẹp
    if days > 0:
        text = f"Còn {days}d {hours}h {minutes}m"
    else:
        text = f"CHỈ CÒN {hours}h {minutes}m"
        
    return text, emoji

# ================= 3. DISCORD BACKGROUND TASK =================
async def status_task():
    await client.wait_until_ready()
    user_name = f"{client.user.name}#{client.user.discriminator}"
    logger.info(f"✅ Logged in as: {user_name}")
    bot_state["user"] = user_name
    
    while not client.is_closed():
        try:
            # 1. Tính toán
            text, emoji = calculate_time_data()
            full_status = f"{text}"
            
            # 2. Cập nhật Discord Presence
            # status=dnd (Màu đỏ - Do Not Disturb) để gây chú ý
            activity = discord.CustomActivity(name=full_status, emoji=emoji) 
            await client.change_presence(status=discord.Status.dnd, activity=activity)
            
            # 3. Cập nhật State cho Web Dashboard
            bot_state["status"] = f"[{emoji}] {full_status}"
            bot_state["last_updated"] = datetime.now(timezone(timedelta(hours=7))).strftime("%H:%M:%S")
            bot_state["ping"] = f"{round(client.latency * 1000)}ms"
            
            logger.info(f"Updated: {full_status}")
            
            # 4. Anti-Ban Jitter (Ngẫu nhiên hóa thời gian chờ)
            # Chờ từ 120s đến 180s để giống người thật hơn
            wait_time = random.randint(120, 180)
            await asyncio.sleep(wait_time) 
            
        except Exception as e:
            logger.error(f"Loop Error: {e}")
            bot_state["status"] = f"Error: {str(e)}"
            await asyncio.sleep(60)

@client.event
async def on_ready():
    client.loop.create_task(status_task())

# ================= 4. WEB DASHBOARD (HTML/CSS) =================
# HTML Template nhúng trực tiếp (Đỡ phải tạo file riêng)
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Discord Bot Monitor</title>
    <style>
        body {
            background-color: #1e1e2e;
            color: #cdd6f4;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
        }
        .card {
            background: #313244;
            padding: 2rem;
            border-radius: 16px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
            text-align: center;
            max-width: 400px;
            width: 90%;
            border: 1px solid #45475a;
        }
        .status-badge {
            background: #a6e3a1;
            color: #1e1e2e;
            padding: 5px 12px;
            border-radius: 20px;
            font-weight: bold;
            font-size: 0.9rem;
            display: inline-block;
            margin-bottom: 1rem;
        }
        h1 { margin: 0; font-size: 1.5rem; color: #89b4fa; }
        .main-stat {
            font-size: 1.8rem;
            font-weight: bold;
            margin: 1.5rem 0;
            color: #fab387;
        }
        .meta {
            font-size: 0.9rem;
            color: #bac2de;
            margin-top: 0.5rem;
            display: flex;
            justify-content: space-between;
        }
        .refresh-hint { font-size: 0.8rem; color: #6c7086; margin-top: 2rem; }
    </style>
</head>
<body>
    <div class="card">
        <span class="status-badge">● System Online</span>
        <h1>{{ state.user }}</h1>
        <div class="main-stat">{{ state.status }}</div>
        <div style="border-top: 1px solid #45475a; margin: 15px 0;"></div>
        <div class="meta">
            <span>Target:</span>
            <span>{{ state.target[:10] }}...</span>
        </div>
        <div class="meta">
            <span>Last Update:</span>
            <span>{{ state.last_updated }}</span>
        </div>
        <div class="meta">
            <span>Ping:</span>
            <span>{{ state.ping }}</span>
        </div>
        <div class="refresh-hint">Running 24/7 on Render Cloud</div>
    </div>
</body>
</html>
"""

@app.route('/')
def home():
    # Render giao diện đẹp thay vì text thường
    return render_template_string(HTML_TEMPLATE, state=bot_state)

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    # Tắt log access của Flask cho đỡ rác
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    app.run(host='0.0.0.0', port=port)

def run_discord_bot():
    if not TOKEN:
        logger.critical("❌ MISSING DISCORD_TOKEN!")
        return
    try:
        client.run(TOKEN)
    except Exception as e:
        logger.critical(f"❌ Login Failed: {e}")

# ================= 5. ENTRY POINT =================
if __name__ == "__main__":
    # Thread 1: Web Server (Để cron-job ping vào)
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()
    
    # Thread 2: Bot Logic (Chạy chính)
    run_discord_bot()
