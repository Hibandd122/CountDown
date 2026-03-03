import discord
from discord.ext import tasks
import os
import logging
import random
from datetime import datetime, timezone, timedelta
from flask import Flask, render_template, jsonify
from threading import Thread, Lock
import requests
import uuid
import concurrent.futures
import time
import atexit

# ================= CONFIG =================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("VN_Countdown_Bot")

TOKEN = os.environ.get("DISCORD_TOKEN")
if not TOKEN:
    logger.critical("Missing DISCORD_TOKEN env var")
    exit(1)

TARGET_STR = "April, 03 2026 at 08:30 PM"
DATE_FORMAT = "%B, %d %Y at %I:%M %p"

# ================= PROXY MANAGER =================
# Lưu trữ proxy hiện tại và thời gian
_PROXY_CACHE = {
    "proxy": None,
    "ts": 0,
    "status": "Unknown",
    "last_check": 0
}
_PROXY_LOCK = Lock()
_PROXY_TTL = 600  # 10 phút (thời gian cache proxy, không phải thời gian sống)
_PROXY_REFRESH_INTERVAL = 300  # 5 phút kiểm tra proxy một lần

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
]

def _check_proxy(proxy_url, test_url="https://discord.com/api/v10/users/@me", timeout=5):
    """Kiểm tra proxy bằng cách gọi Discord API (cần token). Tuy nhiên để đơn giản, dùng httpbin."""
    try:
        r = requests.get(
            "https://httpbin.org/ip",
            proxies={"http": proxy_url, "https": proxy_url},
            timeout=timeout,
            verify=False
        )
        if r.status_code == 200:
            return True
    except Exception:
        pass
    return False

def fetch_proxies_from_antpeak():
    """Lấy danh sách proxy từ antpeak.com, trả về list proxy URLs"""
    try:
        ua = random.choice(USER_AGENTS)
        headers = {"Content-Type": "application/json", "User-Agent": ua}
        data = {
            "udid": str(uuid.uuid4()),
            "appVersion": "2.1.7",
            "platform": "chrome",
            "platformVersion": ua,
            "timeZone": "Asia/Ho_Chi_Minh",
            "deviceName": "Chrome 124"
        }
        r = requests.post(
            "https://antpeak.com/api/launch/",
            json=data,
            headers=headers,
            timeout=10,
            verify=False
        )
        if not r.ok:
            logger.error("Antpeak launch failed")
            return []
        token = r.json()['data']['accessToken']
        headers["authorization"] = f"Bearer {token}"

        r2 = requests.post(
            "https://antpeak.com/api/server/list/",
            json={"protocol": "https", "region": "sg", "type": 0},
            headers=headers,
            timeout=10,
            verify=False
        )
        if not r2.ok:
            logger.error("Antpeak server list failed")
            return []

        servers = r2.json().get("data", [])
        proxies = [
            f"https://{s['username']}:{s['password']}@{s['addresses'][0]}:{s['port']}"
            for s in servers
        ]
        logger.info(f"Fetched {len(proxies)} proxies from antpeak")
        return proxies
    except Exception as e:
        logger.error(f"Error fetching proxies: {e}")
        return []

def find_working_proxy():
    """Tìm một proxy hoạt động từ antpeak"""
    proxies = fetch_proxies_from_antpeak()
    if not proxies:
        return None
    # Kiểm tra nhanh 5 proxy đầu
    for proxy in proxies[:5]:
        if _check_proxy(proxy):
            return proxy
    # Nếu không có, kiểm tra toàn bộ nhưng giới hạn thời gian
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_to_proxy = {executor.submit(_check_proxy, proxy): proxy for proxy in proxies}
        for future in concurrent.futures.as_completed(future_to_proxy):
            if future.result():
                return future_to_proxy[future]
    return None

def proxy_refresh_loop():
    """Vòng lặp nền để kiểm tra và cập nhật proxy"""
    while True:
        try:
            with _PROXY_LOCK:
                current_proxy = _PROXY_CACHE["proxy"]
                last_check = _PROXY_CACHE["last_check"]
            # Nếu có proxy hiện tại, kiểm tra nó còn sống không
            proxy_alive = False
            if current_proxy:
                proxy_alive = _check_proxy(current_proxy)
                with _PROXY_LOCK:
                    _PROXY_CACHE["status"] = "Alive" if proxy_alive else "Dead"
                    _PROXY_CACHE["last_check"] = time.time()
            if not proxy_alive:
                logger.info("Current proxy dead or none, searching for new proxy...")
                new_proxy = find_working_proxy()
                with _PROXY_LOCK:
                    if new_proxy:
                        _PROXY_CACHE["proxy"] = new_proxy
                        _PROXY_CACHE["ts"] = time.time()
                        _PROXY_CACHE["status"] = "Alive"
                        # Cập nhật biến môi trường
                        os.environ['HTTP_PROXY'] = new_proxy
                        os.environ['HTTPS_PROXY'] = new_proxy
                        logger.info(f"New proxy set: {new_proxy}")
                    else:
                        _PROXY_CACHE["status"] = "No proxy available"
                        logger.warning("No working proxy found")
            else:
                logger.debug(f"Proxy still alive: {current_proxy}")
        except Exception as e:
            logger.error(f"Proxy refresh error: {e}")
        time.sleep(_PROXY_REFRESH_INTERVAL)

# Khởi động thread proxy ngay khi import (sẽ start sau khi Flask app init)
proxy_thread = None

def start_proxy_refresh():
    global proxy_thread
    if proxy_thread is None or not proxy_thread.is_alive():
        proxy_thread = Thread(target=proxy_refresh_loop, daemon=True)
        proxy_thread.start()
        logger.info("Proxy refresh thread started")

# ================= DISCORD BOT =================
bot_state = {
    "status": "Starting...",
    "last_updated": "Never",
    "target": TARGET_STR,
    "user": "Unknown",
    "ping": "N/A"
}

intents = discord.Intents.default()
client = discord.Client(intents=intents)

def get_proxy_info():
    with _PROXY_LOCK:
        return {
            "proxy": _PROXY_CACHE["proxy"],
            "status": _PROXY_CACHE["status"],
            "last_check": _PROXY_CACHE["last_check"]
        }

# ================= COUNTDOWN LOGIC =================
def calculate_time_data():
    vn_tz = timezone(timedelta(hours=7))
    now = datetime.now(vn_tz)
    try:
        target = datetime.strptime(TARGET_STR, DATE_FORMAT).replace(tzinfo=vn_tz)
    except Exception as e:
        logger.error(f"Date parsing error: {e}")
        return "Config Error", "⚠️"
    delta = target - now
    total_seconds = delta.total_seconds()
    if total_seconds <= 0:
        return "Event Started! 🎉", "🎆"
    days = delta.days
    hours = delta.seconds // 3600
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

@tasks.loop(minutes=5)
async def update_status_task():
    try:
        text, emoji = calculate_time_data()
        full_status = f"{text}"
        activity = discord.CustomActivity(name=full_status, emoji=emoji)
        await client.change_presence(status=discord.Status.dnd, activity=activity)
        bot_state["status"] = f"[{emoji}] {full_status}"
        bot_state["last_updated"] = datetime.now(timezone(timedelta(hours=7))).strftime("%H:%M:%S")
        bot_state["ping"] = f"{round(client.latency * 1000)}ms"
        logger.info(f"Updated: {full_status}")
    except Exception as e:
        logger.error(f"Task error: {e}")

@update_status_task.before_loop
async def before_update_status():
    await client.wait_until_ready()

@client.event
async def on_ready():
    user_name = f"{client.user.name}#{client.user.discriminator}"
    logger.info(f"✅ Logged in as: {user_name}")
    bot_state["user"] = user_name
    if not update_status_task.is_running():
        update_status_task.start()

@client.event
async def on_rate_limit(rate_limit_info):
    logger.warning(f"⚠️ Rate limit hit: retry after {rate_limit_info.retry_after}s")

# ================= FLASK WEB SERVER =================
app = Flask(__name__, template_folder='templates', static_folder='static')

@app.route('/')
def home():
    return render_template('index.html', state=bot_state)

@app.route('/api/status')
def api_status():
    # Trả về JSON cho JS fetch
    proxy_info = get_proxy_info()
    # Định dạng thời gian last_check
    last_check_str = "N/A"
    if proxy_info["last_check"]:
        last_check_str = datetime.fromtimestamp(proxy_info["last_check"]).strftime("%H:%M:%S")
    return jsonify({
        "bot": {
            "status": bot_state["status"],
            "user": bot_state["user"],
            "ping": bot_state["ping"],
            "last_updated": bot_state["last_updated"],
            "target": bot_state["target"]
        },
        "proxy": {
            "url": proxy_info["proxy"],
            "status": proxy_info["status"],
            "last_check": last_check_str
        }
    })

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# ================= MAIN =================
if __name__ == "__main__":
    # Bắt đầu thread proxy
    start_proxy_refresh()
    # Chạy Flask trong thread riêng
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    # Chạy bot Discord
    try:
        client.run(TOKEN)
    except discord.errors.HTTPException as e:
        if e.status == 429:
            logger.critical("🛑 Blocked by rate limit. Exiting. Will retry after 30 minutes?")
        else:
            logger.critical(f"Discord HTTP error: {e}")
    except Exception as e:
        logger.critical(f"Unexpected error: {e}")
