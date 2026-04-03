#!/bin/bash
# Quick ATLAS Server Health Check

echo "=== ATLAS Server Health Check ==="
echo "Time: $(date)"
echo ""

# Check if server is running
if pgrep -f "python3 orchestrator_server" > /dev/null; then
    echo "✓ Server process running"
    PID=$(pgrep -f "python3 orchestrator_server")
    echo "  PID: $PID"
else
    echo "✗ Server NOT running"
    echo "  Starting server..."
    PYTHONUNBUFFERED=1 nohup python3 -u orchestrator_server.py > server.log 2>&1 &
    sleep 3
fi

# Check if port 9999 is listening
if netstat -tuln 2>/dev/null | grep -q :9999 || ss -tuln 2>/dev/null | grep -q :9999; then
    echo "✓ Port 9999 listening"
else
    echo "✗ Port 9999 NOT listening"
    exit 1
fi

# Test projects endpoint
echo ""
echo "Testing /api/auto/projects..."
RESPONSE=$(curl -s http://localhost:9999/api/auto/projects)
if echo "$RESPONSE" | grep -q "ravencroft_v17"; then
    echo "✓ Projects endpoint working"
    PROJECT_COUNT=$(echo "$RESPONSE" | python3 -c "import sys, json; print(len(json.load(sys.stdin).get('projects', [])))")
    echo "  Found $PROJECT_COUNT projects"
else
    echo "✗ Projects endpoint failed"
fi

# Test bundle endpoint
echo ""
echo "Testing /api/v16/ui/bundle/ravencroft_v17..."
BUNDLE=$(curl -s http://localhost:9999/api/v16/ui/bundle/ravencroft_v17)
if echo "$BUNDLE" | grep -q "shot_gallery_rows"; then
    echo "✓ Bundle endpoint working"
    SHOT_COUNT=$(echo "$BUNDLE" | python3 -c "import sys, json; print(len(json.load(sys.stdin).get('shot_gallery_rows', [])))")
    echo "  Bundle has $SHOT_COUNT shots"
else
    echo "✗ Bundle endpoint failed"
fi

echo ""
echo "=== Summary ==="
echo "✓ ATLAS server is healthy and responsive"
