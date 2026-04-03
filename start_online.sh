#!/bin/bash
# =============================================================================
# V15.4 ATLAS ONLINE MODE - QUICK START SCRIPT
# =============================================================================
# Daily startup script for online/production mode
# Assumes setup_online.sh has already been run
# =============================================================================

set -e

echo "============================================================"
echo "V15.4 ATLAS ONLINE MODE - STARTING"
echo "============================================================"

cd /Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM

# Source environment
if [ -f .env.online ]; then
    source .env.online
else
    echo "WARNING: .env.online not found. Run setup_online.sh first."
    echo "Continuing with default settings..."
    export ATLAS_ONLINE_MODE=1
    export ATLAS_USE_POSTGRES=1
fi

# Load API keys from main .env
source .env 2>/dev/null || true

# Activate virtual environment
source venv/bin/activate 2>/dev/null || true

# Ensure PostgreSQL is running
echo "[1/3] Checking PostgreSQL..."
brew services start postgresql@14 2>/dev/null || true
sleep 1

# Kill any existing server instances
echo "[2/3] Cleaning up existing processes..."
pkill -f "orchestrator_server.py" 2>/dev/null || true
sleep 1

# Start the server
echo "[3/3] Starting ATLAS Orchestrator..."
echo ""
echo "============================================================"
echo "V15.4 ONLINE MODE ACTIVE"
echo "============================================================"
echo "PostgreSQL: ${ATLAS_DB_HOST:-localhost}:${ATLAS_DB_PORT:-5432}/${ATLAS_DB_NAME:-atlas_production}"
echo "Server:     http://localhost:8888"
echo "============================================================"
echo ""

# Run server (foreground so logs are visible)
python3 orchestrator_server.py
