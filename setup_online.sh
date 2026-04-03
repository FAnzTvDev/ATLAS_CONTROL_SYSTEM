#!/bin/bash
# =============================================================================
# V15.4 ATLAS ONLINE MODE - ONE-TIME SETUP SCRIPT
# =============================================================================
# Run this ONCE before going online to set up PostgreSQL and environment
#
# Prerequisites:
# - PostgreSQL installed (brew install postgresql@14)
# - Python venv activated
# =============================================================================

set -e

echo "============================================================"
echo "V15.4 ATLAS ONLINE MODE - SETUP"
echo "============================================================"

cd /Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM

# Step 1: Check PostgreSQL is installed
echo "[1/5] Checking PostgreSQL installation..."
if ! command -v psql &> /dev/null; then
    echo "ERROR: PostgreSQL not installed"
    echo "Install with: brew install postgresql@14"
    exit 1
fi
echo "  ✓ PostgreSQL installed"

# Step 2: Start PostgreSQL if not running
echo "[2/5] Starting PostgreSQL..."
brew services start postgresql@14 2>/dev/null || true
sleep 2

# Step 3: Create database and user
echo "[3/5] Creating ATLAS database..."
createdb atlas_production 2>/dev/null || echo "  (database may already exist)"
psql -c "CREATE USER atlas WITH PASSWORD 'atlas_v15';" 2>/dev/null || echo "  (user may already exist)"
psql -c "GRANT ALL PRIVILEGES ON DATABASE atlas_production TO atlas;" 2>/dev/null || true
echo "  ✓ Database ready"

# Step 4: Install Python dependencies
echo "[4/5] Installing Python dependencies..."
source venv/bin/activate 2>/dev/null || true
pip install psycopg2-binary --quiet 2>/dev/null || pip install psycopg2-binary
echo "  ✓ psycopg2 installed"

# Step 5: Create .env file for online mode
echo "[5/5] Creating environment configuration..."
cat > .env.online << 'EOF'
# V15.4 ATLAS ONLINE MODE CONFIGURATION
export ATLAS_ONLINE_MODE=1
export ATLAS_USE_POSTGRES=1
export ATLAS_DB_HOST=localhost
export ATLAS_DB_PORT=5432
export ATLAS_DB_NAME=atlas_production
export ATLAS_DB_USER=atlas
export ATLAS_DB_PASS=atlas_v15

# API Keys (loaded from main .env)
source .env 2>/dev/null || true
EOF

echo ""
echo "============================================================"
echo "✓ V15.4 ONLINE MODE SETUP COMPLETE"
echo "============================================================"
echo ""
echo "To start ATLAS in online mode, run:"
echo "  ./start_online.sh"
echo ""
echo "Or manually:"
echo "  source .env.online"
echo "  python3 orchestrator_server.py"
echo "============================================================"
