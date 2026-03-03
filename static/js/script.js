// Hàm fetch dữ liệu từ API và cập nhật giao diện
async function fetchStatus() {
    try {
        const response = await fetch('/api/status');
        const data = await response.json();
        
        // Cập nhật thông tin bot
        document.getElementById('bot-user').innerText = data.bot.user;
        document.getElementById('bot-status').innerText = data.bot.status;
        document.getElementById('bot-ping').innerText = data.bot.ping;
        document.getElementById('bot-last-updated').innerText = data.bot.last_updated;
        
        // Cập nhật thông tin proxy
        const proxyUrlElem = document.getElementById('proxy-url');
        const proxyStatusElem = document.getElementById('proxy-status');
        const proxyLastCheckElem = document.getElementById('proxy-last-check');
        
        if (data.proxy.url) {
            proxyUrlElem.innerText = data.proxy.url;
        } else {
            proxyUrlElem.innerText = 'No proxy';
        }
        
        proxyStatusElem.innerText = data.proxy.status;
        // Đổi màu theo trạng thái
        if (data.proxy.status === 'Alive') {
            proxyStatusElem.style.color = '#4ade80';
        } else if (data.proxy.status === 'Dead') {
            proxyStatusElem.style.color = '#f87171';
        } else {
            proxyStatusElem.style.color = '#fbbf24';
        }
        
        proxyLastCheckElem.innerText = data.proxy.last_check;
    } catch (error) {
        console.error('Failed to fetch status:', error);
    }
}

// Tự động cập nhật mỗi 30 giây
setInterval(fetchStatus, 30000);

// Gọi ngay khi tải trang
fetchStatus();
