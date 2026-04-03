#!/bin/bash
# ATLAS V18 Scene 001 Autonomous Render
# Run this on your Mac (not in sandbox)

echo "=============================================="
echo "  ATLAS V18 - Scene 001 Autonomous Render"
echo "=============================================="
echo ""

cd /Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM

# Check server is running
if ! curl -s http://localhost:9999/health > /dev/null 2>&1; then
    echo "[!] Server not running. Starting..."
    python3 orchestrator_server.py > /tmp/atlas_server.log 2>&1 &
    sleep 5
fi

echo "[1/4] Generating missing first frame (001_001A)..."
START=$(date +%s)

curl -s -X POST "http://localhost:9999/api/auto/generate-first-frames-turbo" \
  -H "Content-Type: application/json" \
  -d '{"project":"ravencroft_v17","scene_filter":"001"}' | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(f'  First frames: {data.get(\"generated\", 0)} generated, {data.get(\"skipped\", 0)} skipped')
"

FF_TIME=$(($(date +%s) - START))
echo "  Time: ${FF_TIME}s"

echo ""
echo "[2/4] Generating videos (turbo parallel)..."
START=$(date +%s)

curl -s -X POST "http://localhost:9999/api/auto/render-videos-turbo" \
  -H "Content-Type: application/json" \
  -d '{"project":"ravencroft_v17","scene_filter":"001"}' | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(f'  Videos: {data.get(\"summary\", {}).get(\"generated\", 0)} generated')
print(f'  Mode: {data.get(\"mode\", \"unknown\")}')
print(f'  Throughput: {data.get(\"throughput\", \"N/A\")}')
"

VID_TIME=$(($(date +%s) - START))
echo "  Time: ${VID_TIME}s"

echo ""
echo "[3/4] Stitching Scene 001..."
START=$(date +%s)

STITCH_RESULT=$(curl -s -X POST "http://localhost:9999/api/v12/stitch-scenes" \
  -H "Content-Type: application/json" \
  -d '{"project":"ravencroft_v17","scenes":["001"]}')

OUTPUT_PATH=$(echo "$STITCH_RESULT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('output_path',''))")
VIDEOS_USED=$(echo "$STITCH_RESULT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('videos_used',0))")
FILE_SIZE=$(echo "$STITCH_RESULT" | python3 -c "import json,sys; print(f\"{json.load(sys.stdin).get('file_size',0)/1024/1024:.1f}\")")

STITCH_TIME=$(($(date +%s) - START))
echo "  Videos stitched: $VIDEOS_USED"
echo "  Output: $OUTPUT_PATH"
echo "  Size: ${FILE_SIZE} MB"
echo "  Time: ${STITCH_TIME}s"

echo ""
echo "[4/4] Opening UI and previs..."
open "http://localhost:9999/?project=ravencroft_v17"
open "http://localhost:9999/api/media?path=$OUTPUT_PATH"

TOTAL_TIME=$((FF_TIME + VID_TIME + STITCH_TIME))

echo ""
echo "=============================================="
echo "  COMPLETE!"
echo "=============================================="
echo "  First Frames: ${FF_TIME}s"
echo "  Videos:       ${VID_TIME}s"
echo "  Stitch:       ${STITCH_TIME}s"
echo "  TOTAL:        ${TOTAL_TIME}s"
echo ""
echo "  Estimated cost: ~$0.70"
echo "=============================================="
