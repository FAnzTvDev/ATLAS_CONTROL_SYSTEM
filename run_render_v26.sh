#!/bin/bash
echo "=== V26.1 SCENE 001 RENDER ==="
echo "Started: $(date)"
echo ""

# Clear pycache
find /Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null

# Launch render
curl -s -X POST http://localhost:9999/api/v18/master-chain/render-scene \
  -H 'Content-Type: application/json' \
  -d '{"project":"victorian_shadows_ep1","scene_id":"001"}' \
  > /tmp/atlas_v26_render.log 2>&1 &

RENDER_PID=$!
echo "Render PID: $RENDER_PID"
echo "Monitoring progress..."
echo ""

# Poll for new frames
while kill -0 $RENDER_PID 2>/dev/null; do
    NEWEST=$(ls -t /Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM/pipeline_outputs/victorian_shadows_ep1/first_frames/001_* 2>/dev/null | head -1)
    NEWEST_TIME=$(stat -f "%Sm" -t "%H:%M:%S" "$NEWEST" 2>/dev/null)
    FRAME_COUNT=$(ls /Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM/pipeline_outputs/victorian_shadows_ep1/first_frames/001_* 2>/dev/null | wc -l | tr -d ' ')
    LOG_SIZE=$(wc -c < /tmp/atlas_v26_render.log 2>/dev/null | tr -d ' ')
    echo "[$(date +%H:%M:%S)] Frames: $FRAME_COUNT/12 | Latest: $(basename "$NEWEST" 2>/dev/null) @ $NEWEST_TIME | Log: ${LOG_SIZE}B"
    sleep 15
done

echo ""
echo "=== RENDER COMPLETE ==="
echo "Finished: $(date)"
echo ""
echo "Result:"
cat /tmp/atlas_v26_render.log | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(f'Status: {data.get(\"status\",\"?\")}')
    print(f'Chained: {data.get(\"chained_shots\",\"?\")}')
    print(f'Breaks: {data.get(\"chain_breaks\",\"?\")}')
    print(f'Cost: \${data.get(\"total_cost\",0):.2f}')
    print(f'Report: {data.get(\"report_file\",\"?\")}')
except:
    print(sys.stdin.read() if hasattr(sys.stdin,'read') else 'Could not parse response')
" 2>&1
echo ""
echo "Frames generated:"
ls -lt /Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM/pipeline_outputs/victorian_shadows_ep1/first_frames/001_* 2>&1
