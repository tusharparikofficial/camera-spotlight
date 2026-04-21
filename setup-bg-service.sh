#!/bin/bash
# Run with: sudo bash setup-bg-service.sh
set -e

echo "=== Setting up GPU bg removal service ==="

# 1. systemd unit
echo "[1/3] Creating bg-remove.service..."
cat > /etc/systemd/system/bg-remove.service <<'SVC'
[Unit]
Description=GPU Background Removal WebSocket Service (RMBG-1.4 on CUDA)
After=network.target

[Service]
Type=simple
User=tusharparik
WorkingDirectory=/home/projects/tushar/camera-spotlight/bg_service
ExecStart=/home/projects/tushar/camera-spotlight/bg_service/run.sh
Restart=on-failure
RestartSec=5
Environment="BG_HOST=0.0.0.0"
Environment="BG_PORT=8083"

[Install]
WantedBy=multi-user.target
SVC

# 2. cloudflared tunnel entry for bg.jarvis.tuxy.online
echo "[2/3] Adding bg.jarvis.tuxy.online to cloudflared tunnel..."
if grep -q "bg.jarvis.tuxy.online" /etc/cloudflared/config.yml; then
    echo "  Already in config, skipping."
else
    sed -i '/^  - service: http_status:404/i\  - hostname: bg.jarvis.tuxy.online\n    service: http://localhost:8083\n' /etc/cloudflared/config.yml
fi

# 3. DNS CNAME
echo "[3/3] Adding DNS route..."
cloudflared --origincert /home/tusharparik/.cloudflared/cert.pem tunnel route dns f54c6c40-9be3-4a58-bb4d-36fd2c437206 bg.jarvis.tuxy.online 2>&1 || echo "  DNS route may already exist."

# Enable + start
systemctl daemon-reload
systemctl enable --now bg-remove.service
systemctl restart cloudflared.service

echo ""
echo "=== Done! ==="
echo "Local:  ws://localhost:8083"
echo "Public: wss://bg.jarvis.tuxy.online"
echo ""
systemctl status bg-remove.service --no-pager -n 5
