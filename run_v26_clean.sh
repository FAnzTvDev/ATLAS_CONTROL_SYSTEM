#!/bin/bash
set -e
cd /Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM

echo "============================================"
echo "  ATLAS V26.1 CLEAN RENDER — Scene 001"
echo "  $(date)"
echo "============================================"
echo ""

# Step 1: Clear pycache
echo "[1/5] Clearing __pycache__..."
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null
echo "  Done."

# Step 2: Sync agent mirrors
echo "[2/5] Syncing agent mirrors..."
cp atlas_agents/*.py atlas_agents_v16_7/atlas_agents/ 2>/dev/null
echo "  Done."

# Step 3: Start server in background
echo "[3/5] Starting server..."
python3 orchestrator_server.py > /tmp/atlas_server.log 2>&1 &
SERVER_PID=$!
echo "  Server PID: $SERVER_PID"

# Wait for server to be ready
echo "  Waiting for server..."
for i in $(seq 1 30); do
    if curl -s --connect-timeout 2 http://localhost:9999/api/auto/projects > /dev/null 2>&1; then
        echo "  Server ready!"
        break
    fi
    sleep 2
done

# Verify server
if ! curl -s --connect-timeout 2 http://localhost:9999/api/auto/projects > /dev/null 2>&1; then
    echo "  ERROR: Server failed to start. Check /tmp/atlas_server.log"
    exit 1
fi

# Step 4: Quick audit check
echo "[4/5] Running audit..."
AUDIT=$(curl -s -X POST http://localhost:9999/api/v21/audit/victorian_shadows_ep1 -H 'Content-Type: application/json')
CRITICAL=$(echo "$AUDIT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('critical_count',99))" 2>/dev/null)
echo "  Critical violations: $CRITICAL"
if [ "$CRITICAL" != "0" ]; then
    echo "  WARNING: $CRITICAL critical violations found. Proceeding anyway..."
fi

# Step 5: Launch render
echo "[5/5] Launching Scene 001 master chain render..."
echo ""
echo "  This will take ~10-15 minutes (12 shots × ~60-90s each)"
echo "  Monitoring progress below..."
echo ""

# Launch render and capture output
curl -s -X POST http://localhost:9999/api/v18/master-chain/render-scene \
  -H 'Content-Type: application/json' \
  -d '{"project":"victorian_shadows_ep1","scene_id":"001"}' \
  > /tmp/atlas_v26_render.log 2>&1 &
RENDER_PID=$!

# Monitor loop
while kill -0 $RENDER_PID 2>/dev/null; do
    FRAME_COUNT=$(ls /Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM/pipeline_outputs/victorian_shadows_ep1/first_frames/001_* 2>/dev/null | wc -l | tr -d ' ')
    NEWEST=$(ls -t /Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM/pipeline_outputs/victorian_shadows_ep1/first_frames/001_* 2>/dev/null | head -1)
    NEWEST_NAME=$(basename "$NEWEST" 2>/dev/null)
    NEWEST_TIME=$(stat -f "%Sm" -t "%H:%M:%S" "$NEWEST" 2>/dev/null)
    LOG_SIZE=$(wc -c < /tmp/atlas_v26_render.log 2>/dev/null | tr -d ' ')
    echo "  [$(date +%H:%M:%S)] Frames: $FRAME_COUNT | Latest: $NEWEST_NAME @ $NEWEST_TIME | Log: ${LOG_SIZE}B"
    sleep 15
done

echo ""
echo "============================================"
echo "  RENDER COMPLETE — $(date)"
echo "============================================"
echo ""

# Parse result
python3 -c "
import json
try:
    data = json.load(open('/tmp/atlas_v26_render.log'))
    print(f'  Status:  {data.get(\"status\",\"?\")}')
    print(f'  Chained: {data.get(\"chained_shots\",\"?\")}')
    print(f'  Breaks:  {data.get(\"chain_breaks\",\"?\")}')
    print(f'  Cost:    \${data.get(\"total_cost\",0):.2f}')
    print(f'  Report:  {data.get(\"report_file\",\"?\")}')
except Exception as e:
    print(f'  Could not parse result: {e}')
    print(f'  Raw log:')
    print(open('/tmp/atlas_v26_render.log').read()[:500])
"

echo ""
echo "  Scene 001 frames:"
ls -lt /Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM/pipeline_outputs/victorian_shadows_ep1/first_frames/001_*
echo ""
echo "  To stitch: curl -X POST http://localhost:9999/api/v16/stitch/run -H 'Content-Type: application/json' -d '{\"project\":\"victorian_shadows_ep1\"}'"
