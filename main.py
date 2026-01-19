import time
import requests
import threading
from datetime import datetime, timezone, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
import os

# ================= CẤU HÌNH =================
# Lấy token từ biến môi trường (Cài đặt sau trên Render)
TOKEN = os.environ.get("DISCORD_TOKEN")
TARGET_STR = "April, 03 2026 at 08:30 PM"
DATE_FORMAT = "%B, %d %Y at %I:%M %p"
# ============================================

def get_countdown():
    vn_tz = timezone(timedelta(hours=7))
    now = datetime.now(vn_tz)
    try:
        target = datetime.strptime(TARGET_STR, DATE_FORMAT).replace(tzinfo=vn_tz)
    except:
        return "Lỗi định dạng ngày", "⚠️"
        
    delta = target - now
    
    if delta.total_seconds() <= 0:
        return "Sự kiện đã bắt đầu!", "🎉"

    days = delta.days
    seconds = delta.seconds
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    
    # Logic Emoji
    if days > 30: emoji = "🗓️"
    elif days > 7: emoji = "⏳"
    elif days > 0: emoji = "🔥"
    else: emoji = "🚨"
    
    return f"Còn {days}d {hours}h {minutes}m", emoji

def update_discord():
    while True:
        if not TOKEN:
            print("Chưa có Token!")
            time.sleep(60)
            continue

        text, emoji = get_countdown()
        
        url = "https://discord.com/api/v9/users/@me/settings"
        headers = {
            "Authorization": TOKEN,
            "Content-Type": "application/json"
        }
        # Thêm status: dnd để ép online
        payload = {
            "status": "dnd", 
            "custom_status": {"text": text, "emoji_name": emoji}
        }
        
        try:
            r = requests.patch(url, headers=headers, json=payload)
            if r.status_code == 200:
                print(f"Updated: {text}")
            else:
                print(f"Error {r.status_code}: {r.text}")
        except Exception as e:
            print(f"Lỗi mạng: {e}")
            
        # Chờ 60 giây (để tránh bị Discord khóa mõm vì spam)
        time.sleep(60)

# ================= SERVER GIẢ (Để Render không tắt App) =================
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running 24/7!")

def run_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), SimpleHandler)
    server.serve_forever()

if __name__ == "__main__":
    # Chạy bot ở luồng riêng
    t = threading.Thread(target=update_discord)
    t.start()
    
    # Chạy server ở luồng chính
    print("Server starting...")
    run_server()
