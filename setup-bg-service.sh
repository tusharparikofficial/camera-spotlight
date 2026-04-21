#!/bin/bash
# Run with: sudo bash setup-bg-service.sh
set -e

echo "=== Setting up GPU bg removal + URL screenshot services ==="

# 1. bg-remove systemd unit
echo "[1/5] Creating bg-remove.service..."
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

# 2. snap systemd unit
echo "[2/5] Creating snap.service..."
cat > /etc/systemd/system/snap-server.service <<'SVC'
[Unit]
Description=URL/HTML Screenshot WebSocket Service (Playwright)
After=network.target

[Service]
Type=simple
User=tusharparik
WorkingDirectory=/home/projects/tushar/camera-spotlight/bg_service
ExecStart=/home/projects/tushar/camera-spotlight/bg_service/run_snap.sh
Restart=on-failure
RestartSec=5
Environment="SNAP_HOST=0.0.0.0"
Environment="SNAP_PORT=8084"
Environment="PLAYWRIGHT_BROWSERS_PATH=/home/tusharparik/.cache/ms-playwright"

[Install]
WantedBy=multi-user.target
SVC

# 3. cloudflared tunnel entries
echo "[3/5] Adding cloudflared routes..."
# Clean up old bg.jarvis.tuxy.online entries
if grep -q "bg.jarvis.tuxy.online" /etc/cloudflared/config.yml; then
    sed -i '/bg.jarvis.tuxy.online/,/service:.*localhost:8083/d' /etc/cloudflared/config.yml
fi
# Add bg.tuxy.online
if ! grep -q "bg.tuxy.online" /etc/cloudflared/config.yml; then
    sed -i '/^  - service: http_status:404/i\  - hostname: bg.tuxy.online\n    service: http://localhost:8083\n' /etc/cloudflared/config.yml
fi
# Add snap.tuxy.online
if ! grep -q "snap.tuxy.online" /etc/cloudflared/config.yml; then
    sed -i '/^  - service: http_status:404/i\  - hostname: snap.tuxy.online\n    service: http://localhost:8084\n' /etc/cloudflared/config.yml
fi

# 4. DNS CNAMEs
echo "[4/5] Adding DNS routes..."
cloudflared --origincert /home/tusharparik/.cloudflared/cert.pem tunnel route dns f54c6c40-9be3-4a58-bb4d-36fd2c437206 bg.tuxy.online 2>&1 || echo "  bg route may exist."
cloudflared --origincert /home/tusharparik/.cloudflared/cert.pem tunnel route dns f54c6c40-9be3-4a58-bb4d-36fd2c437206 snap.tuxy.online 2>&1 || echo "  snap route may exist."

# 5. Enable + start
echo "[5/5] Starting services..."
systemctl daemon-reload
systemctl enable --now bg-remove.service
systemctl enable --now snap-server.service
systemctl restart cloudflared.service

echo ""
echo "=== Done! ==="
echo "BG:   wss://bg.tuxy.online   (RMBG-1.4 GPU bg removal)"
echo "Snap: wss://snap.tuxy.online (URL screenshot service)"
echo ""
systemctl status bg-remove.service --no-pager -n 2
systemctl status snap-server.service --no-pager -n 2
