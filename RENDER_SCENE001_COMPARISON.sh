#!/bin/bash
# ============================================================
# ATLAS V17.8.3 — Scene 001 LTX vs Kling Comparison Render
# ============================================================
# Run this from your Mac terminal (not the sandbox)
# Server must be running: python3 orchestrator_server.py
# ============================================================

SERVER="http://localhost:9999"
PROJECT="ravencroft_v17"

SHOTS=("001_000A" "001_001A" "001_002R" "001_004R" "001_005A" "001_006A" "001_007A" "001_008B" "001_009B" "001_010B" "001_011R" "001_012B")

echo "============================================"
echo "  ATLAS Scene 001 — LTX vs Kling Comparison"
echo "============================================"
echo ""

# ============================================================
# STEP 1: Re-render LTX-2 videos with AAA prompts
# ============================================================
echo ">>> STEP 1: Rendering LTX-2 AAA videos (12 shots)..."
echo "    Using force=true to overwrite old renders"
echo ""

curl -s -X POST "$SERVER/api/auto/render-videos" \
  -H "Content-Type: application/json" \
  -d "{
    \"project\":\"$PROJECT\",
    \"shot_ids\":[\"001_000A\",\"001_001A\",\"001_002R\",\"001_004R\",\"001_005A\",\"001_006A\",\"001_007A\",\"001_008B\",\"001_009B\",\"001_010B\",\"001_011R\",\"001_012B\"],
    \"force\":true,
    \"dry_run\":false
  }" | python3 -m json.tool

echo ""
echo ">>> LTX-2 render complete!"
echo ""

# ============================================================
# STEP 2: Stitch LTX-2 AAA scene
# ============================================================
echo ">>> STEP 2: Stitching LTX-2 AAA Scene 001..."
curl -s -X POST "$SERVER/api/v16/stitch/run" \
  -H "Content-Type: application/json" \
  -d "{\"project\":\"$PROJECT\",\"scene_id\":\"001\"}" | python3 -m json.tool

echo ""

# ============================================================
# STEP 3: Render Kling v3 videos (shot by shot)
# ============================================================
echo ">>> STEP 3: Rendering Kling v3 videos (12 shots, one at a time)..."
echo ""

# Kling prompts — crafted for Kling v3 Pro (more natural motion)
declare -A KLING_PROMPTS
KLING_PROMPTS["001_000A"]="Gothic ritual room, candlelight flickering, dust motes in amber light beams, shadows shifting on stone walls, no camera movement, static shot"
KLING_PROMPTS["001_001A"]="Woman kneeling in candlelit stone chamber, natural breathing, subtle chest movement, amber light on face, no camera movement"
KLING_PROMPTS["001_002R"]="Woman places hands on stone altar, head bowed, subtle weight shift, candlelight flickering, no camera movement"
KLING_PROMPTS["001_004R"]="Woman's eyes roll back, body trembles, candle flames surge wildly, supernatural energy, no camera movement"
KLING_PROMPTS["001_005A"]="Medium shot, woman kneeling at altar, intense concentration, natural breathing, candlelight on face, no camera movement"
KLING_PROMPTS["001_006A"]="Woman speaking ritual words, lips moving naturally, jaw articulation, candle flames respond, no camera movement"
KLING_PROMPTS["001_007A"]="Woman speaking with desperate conviction, brow furrowed, natural breathing between phrases, no camera movement"
KLING_PROMPTS["001_008B"]="Candle flames flickering ominously, shadows writhing on stone walls, carved symbols in shifting light, no camera movement"
KLING_PROMPTS["001_009B"]="Wide ritual chamber, dying candlelight, stone walls with symbols, thick atmosphere, shadows deepening, no camera movement"
KLING_PROMPTS["001_010B"]="Woman trembling at altar, ritual intensifying, candle flames surging unnaturally, no camera movement"
KLING_PROMPTS["001_011R"]="Woman speaking final words with power, body taut with effort, candlelight surging, no camera movement"
KLING_PROMPTS["001_012B"]="All candles extinguish simultaneously, room plunges into darkness, afterglow of dying flames, absolute stillness"

# Duration map (Kling accepts 3-15s, so cap at 10 for quality)
declare -A KLING_DURATIONS
KLING_DURATIONS["001_000A"]=10
KLING_DURATIONS["001_001A"]=10
KLING_DURATIONS["001_002R"]=10
KLING_DURATIONS["001_004R"]=10
KLING_DURATIONS["001_005A"]=8
KLING_DURATIONS["001_006A"]=8
KLING_DURATIONS["001_007A"]=8
KLING_DURATIONS["001_008B"]=8
KLING_DURATIONS["001_009B"]=10
KLING_DURATIONS["001_010B"]=10
KLING_DURATIONS["001_011R"]=10
KLING_DURATIONS["001_012B"]=10

for SHOT in "${SHOTS[@]}"; do
    PROMPT="${KLING_PROMPTS[$SHOT]}"
    DUR="${KLING_DURATIONS[$SHOT]}"
    echo "  Rendering Kling: $SHOT (${DUR}s)..."

    curl -s -X POST "$SERVER/api/v17/shot/kling-i2v" \
      -H "Content-Type: application/json" \
      -d "{
        \"project\":\"$PROJECT\",
        \"shot_id\":\"$SHOT\",
        \"prompt\":\"$PROMPT\",
        \"duration\":$DUR,
        \"aspect_ratio\":\"16:9\"
      }" | python3 -c "
import sys,json
d=json.load(sys.stdin)
if d.get('success'):
    print(f'    ✓ {d.get(\"shot_id\",\"?\")}: Kling v{d.get(\"version\",\"?\")} generated ({d.get(\"duration\")}s)')
else:
    print(f'    ✗ ERROR: {d.get(\"error\",\"unknown\")}')
"
    echo ""
done

echo ""
echo "============================================"
echo "  RENDERING COMPLETE!"
echo "============================================"
echo ""
echo "  LTX-2 AAA videos: pipeline_outputs/$PROJECT/videos/001_*.mp4"
echo "  Kling v3 videos:  pipeline_outputs/$PROJECT/director_tools/001_*/videos/kling_*.mp4"
echo "  LTX Stitch:       pipeline_outputs/$PROJECT/stitched_scenes/scene_001_full.mp4"
echo ""
echo "  Open in QuickTime to compare:"
echo "  open pipeline_outputs/$PROJECT/stitched_scenes/scene_001_full.mp4"
echo ""
echo "  Individual shot comparison:"
echo "  open pipeline_outputs/$PROJECT/videos/001_001A.mp4  # LTX version"
echo "  open pipeline_outputs/$PROJECT/director_tools/001_001A/videos/kling_v001.mp4  # Kling version"
echo ""
