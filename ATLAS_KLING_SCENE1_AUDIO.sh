#!/bin/bash
# ===========================================================================
# ATLAS V18 — Master Chain + Kling Scene 1 (Audio + End-Frame Chaining)
# ===========================================================================
# This runs the FULL Master Shot Chain pipeline for Scene 001:
#   1. Shot-by-shot Kling O3 Pro video generation
#   2. End-frame chaining: last frame of shot N → first frame of shot N+1
#   3. B-roll/inserts rendered independently (no chain)
#   4. Native Kling audio: SFX/foley only, no soundscapes
#   5. Auto-stitch all shots into scene_{scene_id}_kling.mp4
#
# Prerequisites:
#   1. Server running: python3 orchestrator_server.py
#   2. FAL_KEY set in environment
#   3. First frames generated for scene 001
#
# Usage: bash ATLAS_KLING_SCENE1_AUDIO.sh
# ===========================================================================

SERVER="http://localhost:9999"
PROJECT="ravencroft_v17"
SCENE="001"

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  ATLAS V18 — Master Chain + Kling Scene 1                   ║"
echo "║  🔗 End-Frame Chaining | 🎤 Audio (SFX/Foley) | 🎬 Kling O3 ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Check server is running
if ! curl -s "$SERVER/api/auto/projects" > /dev/null 2>&1; then
    echo "❌ Server not running! Start it first:"
    echo "   cd /Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM"
    echo "   python3 orchestrator_server.py"
    exit 1
fi
echo "✅ Server running"
echo ""

# Show what will happen
echo "━━━ Pipeline ━━━"
echo "  📦 Scene: $SCENE (12 shots)"
echo "  🎥 Model: Kling O3 Pro (image-to-video)"
echo "  🔗 Chain: End-frame → first-frame for blocking/movement shots"
echo "  📦 Independent: B-roll/inserts rendered separately"
echo "  🎤 Audio: Native SFX/foley (no soundscapes/music)"
echo "  🎬 Stitch: Auto-concat into single scene video"
echo ""
echo "  Estimated time: ~8-15 minutes (depends on Kling queue)"
echo "  Estimated cost: ~\$1.10 (11 shots × \$0.10)"
echo ""
echo "Starting in 3 seconds..."
sleep 3

echo ""
echo "━━━ Launching Master Chain + Kling Render ━━━"
echo ""

# Call the V18 master chain + Kling endpoint
RESULT=$(curl -s -X POST "$SERVER/api/v18/kling/render-scene" \
    -H "Content-Type: application/json" \
    -d "{
        \"project\": \"$PROJECT\",
        \"scene_id\": \"$SCENE\",
        \"duration\": 5,
        \"generate_audio\": true,
        \"enable_chain\": true
    }")

# Parse and display results
echo "$RESULT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    if not d.get('success'):
        print(f'  ❌ Pipeline failed: {d.get(\"error\", \"unknown\")}')
        sys.exit(1)

    print(f'  ⏱  Total time: {d.get(\"elapsed_seconds\", 0):.1f}s')
    print(f'  💰 Cost: \${d.get(\"cost_estimate_usd\", 0):.2f}')
    print()

    s = d.get('summary', {})
    print(f'  📊 Results:')
    print(f'     Total:       {s.get(\"total\", 0)}')
    print(f'     ✅ Success:   {s.get(\"success\", 0)}')
    print(f'     🔗 Chained:   {s.get(\"chained\", 0)}')
    print(f'     📦 Independent: {s.get(\"independent\", 0)}')
    print(f'     ⚠️  Skipped:   {s.get(\"skipped\", 0)}')
    print(f'     ❌ Errors:    {s.get(\"errors\", 0)}')
    print()

    # Show per-shot results
    print('  ━━━ Per-Shot Details ━━━')
    for r in d.get('results', []):
        sid = r.get('shot_id', '?')
        status = r.get('status', '?')
        chained = '🔗' if r.get('chained') else '📦'
        source = r.get('frame_source', '?')
        if status == 'success':
            print(f'     {chained} {sid}: ✅ ({source}, {r.get(\"duration\",\"?\")}s)')
        elif status == 'skipped':
            print(f'     ⏭  {sid}: skipped — {r.get(\"error\",\"\")}')
        else:
            print(f'     ❌ {sid}: {r.get(\"error\",\"\")}')

    print()
    if d.get('kling_stitch_path'):
        print(f'  🎬 Stitched video: {d[\"kling_stitch_path\"]}')
    print(f'  📁 Individual videos: {d.get(\"kling_videos_dir\", \"\")}')
    if d.get('chain_frames_dir'):
        print(f'  🔗 Chain frames: {d[\"chain_frames_dir\"]}')

except Exception as e:
    print(f'  ❌ Parse error: {e}')
    print(sys.stdin.read() if hasattr(sys.stdin, 'read') else '')
"

echo ""
echo "══════════════════════════════════════════════════════════════"
echo "  🎬 DONE! Check the stitched video:"
echo "  open pipeline_outputs/$PROJECT/stitched_scenes/scene_${SCENE}_kling.mp4"
echo "══════════════════════════════════════════════════════════════"
