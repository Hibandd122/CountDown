from http.server import BaseHTTPRequestHandler
import os
import json
import logging
import requests
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass
from typing import Optional, Tuple

# ================= SETUP LOGGING =================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("DiscordCountdown")

# ================= CONFIGURATION =================
@dataclass
class AppConfig:
    DISCORD_TOKEN: str
    TARGET_DATE_STR: str
    DATE_FORMAT: str = "%B, %d %Y at %I:%M %p"
    TIMEZONE_OFFSET: int = 7  # UTC+7 for Vietnam

    @property
    def target_date(self) -> datetime:
        vn_tz = timezone(timedelta(hours=self.TIMEZONE_OFFSET))
        try:
            dt_naive = datetime.strptime(self.TARGET_DATE_STR, self.DATE_FORMAT)
            return dt_naive.replace(tzinfo=vn_tz)
        except ValueError as e:
            logger.error(f"Date format config error: {e}")
            raise

# Load config from Environment for Security
config = AppConfig(
    DISCORD_TOKEN=os.environ.get("DISCORD_TOKEN", ""),
    TARGET_DATE_STR="April, 03 2026 at 08:30 PM"
)

# ================= DOMAIN LOGIC =================
class TimeManager:
    """Chuyên trách xử lý tính toán thời gian"""
    
    @staticmethod
    def get_current_time(offset: int) -> datetime:
        return datetime.now(timezone(timedelta(hours=offset)))

    @staticmethod
    def calculate_remaining(target: datetime, now: datetime) -> Tuple[bool, str, str]:
        """
        Trả về: (is_expired, status_text, emoji)
        """
        delta = target - now
        total_seconds = delta.total_seconds()

        if total_seconds <= 0:
            return True, "Sự kiện đã diễn ra! 🎉", "🎉"

        days = delta.days
        hours = delta.seconds // 3600
        minutes = (delta.seconds % 3600) // 60
        
        # Logic chọn Emoji thông minh dựa trên thời gian còn lại
        if days > 30:
            emoji = "🗓️" # Còn xa
        elif days > 7:
            emoji = "⏳" # Đang đếm ngược
        elif days > 0:
            emoji = "🔥" # Sắp tới
        else:
            emoji = "🚨" # Khẩn cấp (< 24h)

        # Format text gọn gàng
        if days > 0:
            text = f"Còn {days}d {hours}h {minutes}m"
        else:
            text = f"Chỉ còn {hours}h {minutes}m!"

        return False, text, emoji

# ================= INFRASTRUCTURE LAYER =================
class DiscordClient:
    """Chuyên trách giao tiếp với Discord API"""
    
    API_URL = "https://discord.com/api/v9/users/@me/settings"

    def __init__(self, token: str):
        self.headers = {
            "Authorization": token,
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (VercelCronBot/1.0)"
        }

    def update_status(self, text: str, emoji: str) -> bool:
        if not self.headers["Authorization"]:
            logger.error("Missing Discord Token")
            return False

        payload = {
            "status": "dnd",
            "custom_status": {
                "text": text,
                "emoji_name": emoji
            }
        }
        
        # Chỉ update status text, giữ nguyên trạng thái Online/DND nếu muốn
        # Hoặc thêm "status": "dnd" vào payload nếu muốn force DND

        try:
            response = requests.patch(self.API_URL, headers=self.headers, json=payload)
            response.raise_for_status()
            logger.info(f"Updated status: [{emoji}] {text}")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Discord API Error: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response: {e.response.text}")
            return False

# ================= VERCEL HANDLER =================
class handler(BaseHTTPRequestHandler):
    """Entry point cho Vercel Serverless Function"""
    
    def do_GET(self):
        # 1. Init Dependencies
        time_mgr = TimeManager()
        discord = DiscordClient(config.DISCORD_TOKEN)
        
        # 2. Process Logic
        now = time_mgr.get_current_time(config.TIMEZONE_OFFSET)
        is_expired, text, emoji = time_mgr.calculate_remaining(config.target_date, now)
        
        # 3. Execute Side Effect (API Call)
        success = discord.update_status(text, emoji)

        # 4. Return Response to Vercel System
        self.send_response(200 if success else 500)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        
        response_data = {
            "timestamp": now.isoformat(),
            "status_text": text,
            "success": success
        }
        self.wfile.write(json.dumps(response_data).encode('utf-8'))
