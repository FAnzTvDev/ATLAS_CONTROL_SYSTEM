#!/bin/bash
# ══════════════════════════════════════════════════════════════
# ATLAS V18 — Scene 001 Render Script
# Emotion Data Layer + AAA Prompts + Model Comparison
# ══════════════════════════════════════════════════════════════
#
# WHAT'S NEW IN V18:
#   - Emotion Data Layer: ACTING (bio-real) blocks in every LTX prompt
#   - Microexpression directives (dread freeze, fear flash)
#   - Blink suppression + gaze lock per shot type
#   - Asymmetry directives (prevents AI symmetrical face)
#   - Character-aware control levels (Margaret = high control)
#
# RUN FROM: /Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM
# REQUIRES: Server running on localhost:9999
# ══════════════════════════════════════════════════════════════

set -e
BASE="http://localhost:9999"
PROJECT="ravencroft_v17"

echo "╔══════════════════════════════════════╗"
echo "║  ATLAS V18 — Scene 001 Render        ║"
echo "║  Emotion Data Layer Active            ║"
echo "╚══════════════════════════════════════╝"
echo ""

# ── Step 0: Verify server ──
echo "→ Checking server..."
STATUS=$(curl -s -o /dev/null -w "%{http_code}" $BASE/api/auto/projects)
if [ "$STATUS" != "200" ]; then
    echo "✗ Server not running! Start with: python3 orchestrator_server.py"
    exit 1
fi
echo "✓ Server is running"
echo ""

# ── Step 1: Verify Emotion Layer exists ──
echo "→ Checking emotion layer..."
EMO_CHECK=$(curl -s "$BASE/api/v18/emotion-layer/$PROJECT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('scenes',0))")
if [ "$EMO_CHECK" = "0" ]; then
    echo "→ Generating emotion layer..."
    curl -s -X POST "$BASE/api/v18/emotion-layer/generate" \
        -H "Content-Type: application/json" \
        -d "{\"project\":\"$PROJECT\",\"force\":true}" | python3 -m json.tool
fi
echo "✓ Emotion layer ready ($EMO_CHECK scenes)"
echo ""

# ── Step 2: Choose render mode ──
echo "═══════════════════════════════════════"
echo "  Choose render mode:"
echo "  1) LTX-2 only (fast, $0.96/scene)"
echo "  2) Kling v3 only ($3.60/scene)"
echo "  3) BOTH (A/B comparison)"
echo "═══════════════════════════════════════"
read -p "Enter choice [1/2/3]: " CHOICE
echo ""

SCENE_SHOTS='["001_000A","001_001A","001_002R","001_009B","001_004R","001_005A","001_010B","001_006A","001_011R","001_007A","001_012B","001_008B"]'

# ══════════════════════════════════════
# LTX-2 RENDER
# ══════════════════════════════════════
if [ "$CHOICE" = "1" ] || [ "$CHOICE" = "3" ]; then
    echo "╔══════════════════════════════════════╗"
    echo "║  LTX-2 + Emotion Layer Render         ║"
    echo "╚══════════════════════════════════════╝"
    echo ""
    echo "→ Rendering 12 Scene 001 shots via LTX-2 (force overwrite)..."
    echo "  Prompts include: anti-morph + ACTING (bio-real) + static camera"
    echo ""

    curl -s -X POST "$BASE/api/auto/render-videos" \
        -H "Content-Type: application/json" \
        -d "{
            \"project\": \"$PROJECT\",
            \"shot_ids\": $SCENE_SHOTS,
            \"dry_run\": false,
            \"force\": true
        }" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    results = d.get('results', [])
    for r in results:
        status = r.get('status', '?')
        icon = '✓' if status == 'success' else '✗' if status == 'error' else '○'
        print(f'  {icon} {r.get(\"shot_id\",\"?\")}: {status}')
    print(f'  Total: {len(results)} shots')
except:
    print(sys.stdin.read())
"
    echo ""

    # Stitch
    echo "→ Stitching LTX scene..."
    curl -s -X POST "$BASE/api/v16/stitch/run" \
        -H "Content-Type: application/json" \
        -d "{\"project\":\"$PROJECT\",\"scene_ids\":[\"001\"]}" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(f'  Stitch: {d.get(\"status\", d.get(\"message\", \"?\"))}')
"
    echo ""
    echo "✓ LTX-2 render complete"
    echo "  Video: pipeline_outputs/$PROJECT/stitched_scenes/scene_001_full.mp4"
    echo ""
fi

# ══════════════════════════════════════
# KLING v3 RENDER
# ══════════════════════════════════════
if [ "$CHOICE" = "2" ] || [ "$CHOICE" = "3" ]; then
    echo "╔══════════════════════════════════════╗"
    echo "║  Kling v3 Pro + Emotion Layer         ║"
    echo "╚══════════════════════════════════════╝"
    echo ""

    # Kling prompts: same emotion layer but adapted for Kling's motion model
    # Kling handles natural motion better, so we lean into performance cues

    declare -A KLING_PROMPTS
    KLING_PROMPTS["001_000A"]="Gothic ritual room, stone chamber with carved occult symbols, candles burn low casting amber shadows, dust motes in light beams. Empty ancient room slowly revealed. LOCKED CAMERA, wide establishing."
    KLING_PROMPTS["001_001A"]="Lady Margaret kneels at stone altar, hands on carved surface, speaking ritual words with controlled dread. Face: inner brows lift slight, lower lid tension, gaze locked on altar, blink suppressed. Body: contained posture, hands precise, shallow controlled breath. Delivery: low restrained whisper."
    KLING_PROMPTS["001_002R"]="Lady Margaret reaction, determination under dread. Micro-expression: brief freeze 0.2s then composure returns. Eyes: lower lid tension, gaze locked forward, blink suppressed. Jaw slightly tight. Still body, deep controlled breath."
    KLING_PROMPTS["001_009B"]="Insert: carved stone altar surface detail, ancient occult symbols, candle wax dripping, ambient flickering light. No characters. Slow subtle camera drift."
    KLING_PROMPTS["001_004R"]="Lady Margaret reaction shot, controlled fear visible in eyes only. Asymmetric brow tension. Lower lid tense, gaze locked. Lip press subtle. Contained posture, still hands with minimal tremor."
    KLING_PROMPTS["001_005A"]="Lady Margaret kneeling at altar, hands tracing carved symbols with ritual precision. Body: centered, forward lean, deliberate hand movement. Face: determination, brow draw, focused gaze. Deep controlled breath."
    KLING_PROMPTS["001_010B"]="Insert: Lady Margaret hands on carved altar surface, fingers tracing symbols precisely. Slight hand tremor underneath steady movement. Candlelight flickers across stone."
    KLING_PROMPTS["001_006A"]="Lady Margaret continues binding ritual, eyes roll back slightly. Body shifts from control to altered state. Face: eyes unfocus, jaw relaxes, brow releases. Breath deepens. Candles flicker violently."
    KLING_PROMPTS["001_011R"]="Close-up Lady Margaret, ritual determination. Face: asymmetric brow, lower lid tension, gaze locked, blink fully suppressed. Micro-expression: 0.2s dread freeze then composure. Speaking: low whisper, breath catch, no blink on final words."
    KLING_PROMPTS["001_007A"]="Lady Margaret completes ritual with final binding words. Body: centered upright, hands steady on altar. Face: resolve setting in jaw, eyes narrow fractionally. Speaking final words with measured control."
    KLING_PROMPTS["001_012B"]="Insert: candle flames. All candles blow out simultaneously. Room plunges into darkness. Smoke wisps rise from extinguished wicks. Horror realization moment."
    KLING_PROMPTS["001_008B"]="B-roll: ritual room atmosphere after candles extinguish. Deep shadows, last wisps of smoke, carved symbols barely visible. Dread atmosphere. No characters."

    declare -A KLING_DURATIONS
    KLING_DURATIONS["001_000A"]=10
    KLING_DURATIONS["001_001A"]=10
    KLING_DURATIONS["001_002R"]=8
    KLING_DURATIONS["001_009B"]=8
    KLING_DURATIONS["001_004R"]=8
    KLING_DURATIONS["001_005A"]=8
    KLING_DURATIONS["001_006A"]=8
    KLING_DURATIONS["001_010B"]=8
    KLING_DURATIONS["001_011R"]=10
    KLING_DURATIONS["001_007A"]=8
    KLING_DURATIONS["001_012B"]=8
    KLING_DURATIONS["001_008B"]=8

    for SHOT_ID in 001_000A 001_001A 001_002R 001_009B 001_004R 001_005A 001_010B 001_006A 001_011R 001_007A 001_012B 001_008B; do
        PROMPT="${KLING_PROMPTS[$SHOT_ID]}"
        DUR="${KLING_DURATIONS[$SHOT_ID]}"
        echo "→ Kling: $SHOT_ID (${DUR}s)..."

        RESULT=$(curl -s -X POST "$BASE/api/v17/shot/kling-i2v" \
            -H "Content-Type: application/json" \
            -d "{
                \"project\": \"$PROJECT\",
                \"shot_id\": \"$SHOT_ID\",
                \"prompt\": \"$PROMPT\",
                \"duration\": $DUR,
                \"aspect_ratio\": \"16:9\"
            }")

        SUCCESS=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('success',False))" 2>/dev/null || echo "error")
        if [ "$SUCCESS" = "True" ]; then
            echo "  ✓ Done"
        else
            MSG=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('error','unknown'))" 2>/dev/null || echo "parse error")
            echo "  ✗ Failed: $MSG"
        fi
    done

    echo ""
    echo "✓ Kling v3 render complete"
    echo "  Videos: pipeline_outputs/$PROJECT/director_tools/001_*/videos/kling_v*.mp4"
    echo ""
fi

# ══════════════════════════════════════
# COMPARISON
# ══════════════════════════════════════
echo "╔══════════════════════════════════════╗"
echo "║  RENDER COMPLETE                      ║"
echo "╚══════════════════════════════════════╝"
echo ""
echo "  LTX-2 scene: open pipeline_outputs/$PROJECT/stitched_scenes/scene_001_full.mp4"
echo "  Kling shots: open pipeline_outputs/$PROJECT/director_tools/"
echo ""
echo "  Compare in QuickTime for:"
echo "    - Facial micro-expression quality"
echo "    - Blink naturalness"
echo "    - Body movement realism"
echo "    - Emotion consistency across cuts"
echo "    - Identity preservation"
echo ""
echo "  V18 Emotion Layer directives active in all prompts."
echo "  Templates: dread, ritual_focus (Scene 001)"
echo "  Character profile: Margaret (control=0.85, leak=0.25)"
echo ""
