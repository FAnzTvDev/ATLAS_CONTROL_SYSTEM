#!/bin/bash
# ============================================
# ATLAS HETZNER DEPLOYMENT
# Run on: 5.78.151.20 (as root)
# One command: bash deploy_hetzner.sh
# ============================================
set -e

echo "=========================================="
echo "ATLAS HETZNER DEPLOY — Phase 1: System"
echo "=========================================="

apt update && apt upgrade -y
apt install -y python3 python3-pip python3-venv git curl redis-server

# Start Redis
systemctl enable redis-server
systemctl start redis-server

echo "Redis status:"
redis-cli ping

echo ""
echo "=========================================="
echo "Phase 2: Clone + Install"
echo "=========================================="

mkdir -p /opt
cd /opt

if [ -d "atlas" ]; then
    echo "atlas/ exists — pulling latest..."
    cd atlas && git pull origin main
else
    echo "Cloning ATLAS..."
    git clone https://github.com/FAnzTvDev/ATLAS_CONTROL_SYSTEM.git atlas
    cd atlas
fi

echo "Creating venv..."
python3 -m venv venv
source venv/bin/activate

echo "Installing requirements..."
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "=========================================="
echo "Phase 3: Environment"
echo "=========================================="

if [ ! -f ".env" ]; then
    echo "Creating .env from .env.example..."
    cp .env.example .env
    echo ""
    echo "*** EDIT .env WITH YOUR API KEYS ***"
    echo "  nano /opt/atlas/.env"
    echo ""
fi

# Create .env.online for controller-specific config
cat > .env.online << 'ENVEOF'
PORT=8000
REDIS_HOST=localhost
REDIS_PORT=6379
R2_ACCESS_KEY=35969dbefd3bd2b8d7f452806493924a
R2_SECRET_KEY=791b7c09af8725462e1fb54b1ccfa49e22c4b0401850e4f48bea8b8cb8297eec
R2_BUCKET=atlas
R2_ENDPOINT=https://026089839555deec85ae1cfc77648038.r2.cloudflarestorage.com
MAX_RETRIES=1
ENVEOF

echo ".env.online created."

# Create data directories
mkdir -p pipeline_outputs
mkdir -p character_library_locked
mkdir -p location_masters

echo ""
echo "=========================================="
echo "Phase 4: Systemd Service"
echo "=========================================="

cat > /etc/systemd/system/atlas.service << 'SVCEOF'
[Unit]
Description=ATLAS Control System
After=network.target redis-server.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/atlas
Environment=PATH=/opt/atlas/venv/bin:/usr/bin:/bin
ExecStart=/opt/atlas/venv/bin/python3 orchestrator_server.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SVCEOF

systemctl daemon-reload
systemctl enable atlas

echo ""
echo "=========================================="
echo "Phase 5: Firewall"
echo "=========================================="

ufw allow 22/tcp
ufw allow 8000/tcp
ufw allow 9999/tcp
ufw --force enable

echo ""
echo "=========================================="
echo "DEPLOYMENT COMPLETE"
echo "=========================================="
echo ""
echo "To start ATLAS:"
echo "  systemctl start atlas"
echo ""
echo "To check status:"
echo "  systemctl status atlas"
echo "  curl http://localhost:9999/api/auto/projects"
echo ""
echo "To view logs:"
echo "  journalctl -u atlas -f"
echo ""
echo "External access:"
echo "  http://5.78.151.20:9999"
echo "=========================================="
