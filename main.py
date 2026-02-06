import discord
from discord.ext import tasks
import os
import logging
import random
from datetime import datetime, timezone, timedelta
from flask import Flask, render_template_string
from threading import Thread

# ================= 1. SYSTEM SETUP =================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("VN_Countdown_Bot")

TOKEN = os.environ.get("DISCORD_TOKEN")
TARGET_STR = "April, 03 2026 at 08:30 PM"
DATE_FORMAT = "%B, %d %Y at %I:%M %p"

bot_state = {
    "status": "Starting...",
    "last_updated": "Never",
    "target": TARGET_STR,
    "user": "Unknown",
    "ping": "N/A"
}

# --- IMPROVEMENT: INTENTS (REQUIRED FOR DISCORD.PY 2.0+) ---
intents = discord.Intents.default()
client = discord.Client(intents=intents)
app = Flask(__name__)

# ================= 2. DOMAIN LOGIC =================
def calculate_time_data():
    vn_tz = timezone(timedelta(hours=7))
    now = datetime.now(vn_tz)
    
    try:
        target = datetime.strptime(TARGET_STR, DATE_FORMAT).replace(tzinfo=vn_tz)
    except Exception as e:
        logger.error(f"Date Parsing Error: {e}")
        return "Config Error", "⚠️"
        
    delta = target - now
    total_seconds = delta.total_seconds()

    if total_seconds <= 0:
        return "Event Started! 🎉", "🎆"

    days = delta.days
    hours = (delta.seconds // 3600)
    minutes = (delta.seconds % 3600) // 60
    
    if days > 100: emoji = "📅"
    elif days > 30: emoji = "🗓️"
    elif days > 7: emoji = "⏳"
    elif days > 1: emoji = "🔥"
    elif days > 0: emoji = "🚨"
    else: emoji = "🧨"
    
    if days > 0:
        text = f"Còn {days}d {hours}h {minutes}m"
    else:
        text = f"CHỈ CÒN {hours}h {minutes}m"
        
    return text, emoji

# ================= 3. DISCORD BACKGROUND TASK (MODERN) =================
# --- IMPROVEMENT: Using tasks.loop instead of while True ---
@tasks.loop(minutes=5)  
async def update_status_task():
    try:
        text, emoji = calculate_time_data()
        full_status = f"{text}"
        
        # Update Discord Presence
        activity = discord.CustomActivity(name=full_status, emoji=emoji)
        await client.change_presence(status=discord.Status.dnd, activity=activity)
        
        # Update Web State
        bot_state["status"] = f"[{emoji}] {full_status}"
        bot_state["last_updated"] = datetime.now(timezone(timedelta(hours=7))).strftime("%H:%M:%S")
        bot_state["ping"] = f"{round(client.latency * 1000)}ms"
        
        logger.info(f"Updated: {full_status}")
        
    except Exception as e:
        logger.error(f"Task Error: {e}")

# Wait until bot is ready before starting the loop
@update_status_task.before_loop
async def before_update_status():
    await client.wait_until_ready()

@client.event
async def on_ready():
    user_name = f"{client.user.name}#{client.user.discriminator}"
    logger.info(f"✅ Logged in as: {user_name}")
    bot_state["user"] = user_name
    
    # Start the task if not already running
    if not update_status_task.is_running():
        update_status_task.start()

@client.event
async def on_rate_limit(rate_limit_info):
    # This logs if you actually hit a rate limit
    logger.warning(f"⚠️ RATE LIMIT HIT: Try again in {rate_limit_info.retry_after}s")

# ================= 4. WEB DASHBOARD =================
# ================= 4. WEB DASHBOARD (UPGRADE UI) =================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="refresh" content="60"> <title>🤖 Bot Status Monitor</title>
    
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&family=JetBrains+Mono:wght@500;700&display=swap" rel="stylesheet">
    
    <style>
        :root {
            --bg-color: #0f172a;
            --card-bg: rgba(30, 41, 59, 0.7);
            --border-color: rgba(148, 163, 184, 0.1);
            --primary: #38bdf8;
            --accent: #f472b6;
            --text-main: #f1f5f9;
            --text-muted: #94a3b8;
            --success: #4ade80;
        }

        body {
            background-color: var(--bg-color);
            background-image: 
                radial-gradient(at 0% 0%, rgba(56, 189, 248, 0.15) 0px, transparent 50%),
                radial-gradient(at 100% 100%, rgba(244, 114, 182, 0.15) 0px, transparent 50%);
            color: var(--text-main);
            font-family: 'Inter', sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
            overflow: hidden;
        }

        /* Hiệu ứng Glassmorphism cho Card */
        .dashboard-card {
            background: var(--card-bg);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid var(--border-color);
            padding: 2.5rem;
            border-radius: 24px;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
            text-align: center;
            max-width: 420px;
            width: 90%;
            position: relative;
            animation: fadeIn 0.8s ease-out;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }

        /* Header: Status Badge */
        .status-container {
            display: inline-flex;
            align-items: center;
            background: rgba(74, 222, 128, 0.1);
            border: 1px solid rgba(74, 222, 128, 0.2);
            padding: 6px 16px;
            border-radius: 99px;
            margin-bottom: 1.5rem;
        }

        .status-dot {
            width: 8px;
            height: 8px;
            background-color: var(--success);
            border-radius: 50%;
            margin-right: 8px;
            box-shadow: 0 0 10px var(--success);
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0% { box-shadow: 0 0 0 0 rgba(74, 222, 128, 0.7); }
            70% { box-shadow: 0 0 0 6px rgba(74, 222, 128, 0); }
            100% { box-shadow: 0 0 0 0 rgba(74, 222, 128, 0); }
        }

        .status-text {
            color: var(--success);
            font-weight: 600;
            font-size: 0.85rem;
            letter-spacing: 0.5px;
            text-transform: uppercase;
        }

        /* Tên Bot */
        h1 {
            font-size: 1.25rem;
            color: var(--text-muted);
            margin: 0 0 1rem 0;
            font-weight: 400;
        }
        
        h1 span {
            color: var(--text-main);
            font-weight: 700;
        }

        /* Countdown Chính */
        .main-stat {
            font-family: 'JetBrains Mono', monospace;
            font-size: 1.6rem;
            font-weight: 700;
            background: linear-gradient(135deg, var(--primary), var(--accent));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin: 1.5rem 0;
            padding: 1rem;
            background-color: rgba(15, 23, 42, 0.3);
            border-radius: 12px;
            border: 1px solid var(--border-color);
            word-wrap: break-word;
        }

        /* Grid thông tin phụ */
        .info-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1rem;
            margin-top: 2rem;
            border-top: 1px solid var(--border-color);
            padding-top: 1.5rem;
        }

        .info-item {
            display: flex;
            flex-direction: column;
            align-items: center;
        }

        .info-label {
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: var(--text-muted);
            margin-bottom: 0.5rem;
        }

        .info-value {
            font-family: 'JetBrains Mono', monospace;
            font-weight: 600;
            font-size: 1rem;
            color: var(--text-main);
        }

        /* Footer */
        .footer {
            margin-top: 2rem;
            font-size: 0.75rem;
            color: var(--text-muted);
            opacity: 0.6;
        }
    </style>
</head>
<body>
    <div class="dashboard-card">
        <div class="status-container">
            <div class="status-dot"></div>
            <span class="status-text">System Operational</span>
        </div>

        <h1>Bot: <span>{{ state.user }}</span></h1>

        <div class="main-stat">
            {{ state.status }}
        </div>

        <div class="info-grid">
            <div class="info-item">
                <span class="info-label">Server Ping</span>
                <span class="info-value" style="color: #4ade80;">{{ state.ping }}</span>
            </div>
            <div class="info-item">
                <span class="info-label">Last Checked</span>
                <span class="info-value">{{ state.last_updated }}</span>
            </div>
        </div>

        <div class="footer">
            Target: {{ state.target[:10] }}... | Region: VN (GMT+7)
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE, state=bot_state)

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    # Suppress flask logs
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    app.run(host='0.0.0.0', port=port)

# ================= 5. ENTRY POINT =================
if __name__ == "__main__":
    if not TOKEN:
        logger.critical("❌ MISSING DISCORD_TOKEN!")
    else:
        # Run Flask
        t = Thread(target=run_flask)
        t.daemon = True
        t.start()
        
        # Run Bot
        try:
            client.run(TOKEN)
        except discord.errors.HTTPException as e:
            if e.status == 429:
                logger.critical("🛑 BLOCKED BY RATE LIMIT. KILLING PROCESS. TRY AGAIN IN 30 MINS.")
            else:
                logger.critical(f"❌ Error: {e}")
