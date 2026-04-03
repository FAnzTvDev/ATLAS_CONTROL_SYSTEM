#!/bin/bash
# V5 ATLAS Autonomous Testing Agent Launcher
# Run this script and leave it running overnight

echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║           V5 ATLAS AUTONOMOUS TESTING AGENT                      ║"
echo "║                  8-Hour Autonomous Run                           ║"
echo "╚══════════════════════════════════════════════════════════════════╝"

cd /Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM

# Ensure server is running
echo "Checking server status..."
if ! curl -s http://localhost:9999/health > /dev/null 2>&1; then
    echo "Starting orchestrator server..."
    nohup python3 orchestrator_server.py > orchestrator_server.log 2>&1 &
    sleep 10
fi

# Run the autonomous agent
echo "Starting autonomous testing agent..."
echo "Logs: V5_AUTONOMOUS_RUN.log"
echo "Report: V5_AUTONOMOUS_REPORT.md"
echo ""
echo "Press Ctrl+C to stop gracefully (state will be saved)"
echo ""

python3 V5_AUTONOMOUS_TESTING_AGENT.py

echo ""
echo "Autonomous run complete. Check V5_AUTONOMOUS_REPORT.md for results."
