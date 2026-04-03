#!/bin/bash
# 🚀 ATLAS PHASE 5 AUTONOMOUS DIRECTOR - COMPLETE SYSTEM LAUNCHER

echo "🎬 LAUNCHING ATLAS PHASE 5 AUTONOMOUS DIRECTOR"
echo "============================================================"

cd /Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM

# Create logs directory
mkdir -p logs

# Kill any existing instances
echo "🧹 Cleaning up existing processes..."
pkill -f "orchestrator_server.py" 2>/dev/null
sleep 2

# Start Orchestrator Server
echo "🎛️  Starting Orchestrator Server..."
PYTHONUNBUFFERED=1 python3 -u orchestrator_server.py > logs/orchestrator.log 2>&1 &
ORCH_PID=$!
echo "   PID: $ORCH_PID"

# Wait for server to be ready
sleep 5

echo ""
echo "============================================================"
echo "✅ ATLAS PHASE 5 AUTONOMOUS DIRECTOR IS LIVE"
echo "============================================================"
echo "Orchestrator: http://localhost:8888"
echo "Logs: tail -f logs/orchestrator.log"
echo "============================================================"
