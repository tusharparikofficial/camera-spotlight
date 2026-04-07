#!/bin/bash
set -e

echo "=== Setting up jarvis.tuxy.online ==="

# 1. Create systemd service for HoloForge
echo "[1/4] Creating holoforge systemd service..."
cat > /etc/systemd/system/holoforge.service <<'SVC'
[Unit]
Description=HoloForge Static File Server
After=network.target

[Service]
Type=simple
User=tusharparik
WorkingDirectory=/home/projects/tushar/camera-spotlight
ExecStart=/usr/bin/python3 -m http.server 8082
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
SVC

# 2. Add jarvis.tuxy.online to cloudflared config
echo "[2/4] Adding jarvis.tuxy.online to cloudflared config..."
if grep -q "jarvis.tuxy.online" /etc/cloudflared/config.yml; then
    echo "  Already exists, skipping."
else
    sed -i '/^  - service: http_status:404/i\  - hostname: jarvis.tuxy.online\n    service: http://localhost:8082\n' /etc/cloudflared/config.yml
fi

# 3. Add DNS route
echo "[3/4] Adding DNS CNAME for jarvis.tuxy.online..."
cloudflared tunnel route dns f54c6c40-9be3-4a58-bb4d-36fd2c437206 jarvis.tuxy.online 2>&1 || echo "  DNS route may already exist, continuing."

# 4. Reload and restart services
echo "[4/4] Starting services..."
systemctl daemon-reload
systemctl enable --now holoforge.service
systemctl restart cloudflared.service

echo ""
echo "=== Done! ==="
echo "HoloForge server: http://localhost:8082"
echo "Public URL:       https://jarvis.tuxy.online"
echo ""
systemctl status holoforge.service --no-pager
