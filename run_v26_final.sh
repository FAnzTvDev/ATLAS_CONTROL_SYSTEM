#!/bin/bash
cd /Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM

echo "============================================"
echo "  ATLAS V26.1 FINAL RENDER — Scene 001"
echo "  $(date)"
echo "  R2 URL fix applied (base64 fallback)"
echo "============================================"
echo ""

# Clear pycache
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null
echo "[OK] pycache cleared"

# Start server
python3 orchestrator_server.py > /tmp/atlas_server.log 2>&1 &
SERVER_PID=$!
echo "[OK] Server starting (PID $SERVER_PID)..."

# Wait for server
for i in $(seq 1 30); do
    if curl -s --connect-timeout 2 http://localhost:9999/api/auto/projects > /dev/null 2>&1; then
        echo "[OK] Server ready"
        break
    fi
    sleep 2
    printf "."
done
echo ""

# Verify server
if ! curl -s --connect-timeout 2 http://localhost:9999/api/auto/projects > /dev/null 2>&1; then
    echo "[FAIL] Server did not start. Last 20 lines of log:"
    tail -20 /tmp/atlas_server.log
    exit 1
fi

# Quick audit
echo ""
echo "Running audit..."
CRITICAL=$(curl -s -X POST http://localhost:9999/api/v21/audit/victorian_shadows_ep1 \
  -H 'Content-Type: application/json' | \
  python3 -c "import sys,json; print(json.load(sys.stdin).get('critical_count',99))" 2>/dev/null)
echo "[OK] Audit: $CRITICAL critical violations"

# Launch render
echo ""
echo "=== LAUNCHING SCENE 001 MASTER CHAIN ==="
echo "  12 shots, ~60-90s each, total ~10-15 min"
echo "  With V26.1 fixes: smart chain, extras guard, base64 fallback"
echo ""

curl -s -X POST http://localhost:9999/api/v18/master-chain/render-scene \
  -H 'Content-Type: application/json' \
  -d '{"project":"victorian_shadows_ep1","scene_id":"001"}' \
  > /tmp/atlas_v26_render.log 2>&1 &
RENDER_PID=$!

# Monitor
while kill -0 $RENDER_PID 2>/dev/null; do
    FC=$(ls /Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM/pipeline_outputs/victorian_shadows_ep1/first_frames/001_* 2>/dev/null | wc -l | tr -d ' ')
    NW=$(ls -t /Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM/pipeline_outputs/victorian_shadows_ep1/first_frames/001_* 2>/dev/null | head -1)
    NM=$(basename "$NW" 2>/dev/null)
    NT=$(stat -f "%Sm" -t "%H:%M:%S" "$NW" 2>/dev/null)
    # Check server log for chain progress
    CHAIN_MSG=$(grep -o '\[CHAIN\].*' /tmp/atlas_server.log 2>/dev/null | tail -1 | head -c 100)
    echo "  [$(date +%H:%M:%S)] Frames:$FC/12 | Latest:$NM@$NT | $CHAIN_MSG"
    sleep 12
done

echo ""
echo "============================================"
echo "  RENDER COMPLETE — $(date)"
echo "============================================"
echo ""

# Show result
python3 << 'PYEOF'
import json
try:
    data = json.load(open("/tmp/atlas_v26_render.log"))
    print(f"  Status:  {data.get('status','?')}")
    print(f"  Chained: {data.get('chained_shots','?')}")
    print(f"  Breaks:  {data.get('chain_breaks','?')}")
    print(f"  Cost:    ${data.get('total_cost',0):.2f}")
    print(f"  Report:  {data.get('report_file','?')}")
except Exception as e:
    print(f"  Parse error: {e}")
    with open("/tmp/atlas_v26_render.log") as f:
        print(f"  Raw: {f.read()[:500]}")
PYEOF

echo ""
echo "Frames:"
ls -lt /Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM/pipeline_outputs/victorian_shadows_ep1/first_frames/001_*

echo ""
echo "Chain log entries:"
grep '\[CHAIN\]' /tmp/atlas_server.log | grep -i 'chain_mode\|base64\|R2.*verified\|R2.*not accessible\|BLOCKING_AWARE\|REFRAME\|INDEPENDENT' | tail -20
