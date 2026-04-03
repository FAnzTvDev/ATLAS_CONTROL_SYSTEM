#!/bin/bash
# ============================================================
# ATLAS V26.1 — FRESH SCENE 001 RENDER PIPELINE
# Run this after server is started:
#   python3 orchestrator_server.py
# Then in a second terminal:
#   bash RUN_V26_FRESH_RENDER.sh
# ============================================================

set -e
SERVER="http://localhost:9999"
PROJECT="victorian_shadows_ep1"

echo "============================================================"
echo "  ATLAS V26.1 — FRESH RENDER PIPELINE"
echo "  Project: $PROJECT"
echo "============================================================"
echo ""

# Step 0: Verify server is running
echo "⏳ Step 0: Checking server..."
if ! curl -s --connect-timeout 3 "$SERVER/api/auto/projects" > /dev/null 2>&1; then
    echo "❌ Server not running! Start it first:"
    echo "   python3 orchestrator_server.py"
    exit 1
fi
echo "✅ Server is running"
echo ""

# Step 1: Backup before fumigation, then archive stale frames
PP="pipeline_outputs/$PROJECT"
echo "⏳ Step 1a: Creating pre-fumigation backup..."
cp "$PP/shot_plan.json" "$PP/shot_plan.json.backup_pre_v261_$(date +%Y%m%d_%H%M%S)" 2>/dev/null
echo "⏳ Step 1b: Running fumigation (archiving stale Scene 001 frames)..."
FUMIGATION=$(curl -s -X POST "$SERVER/api/v21/fumigation/$PROJECT" \
    -H "Content-Type: application/json" \
    -d '{}')
echo "✅ Fumigation complete"
# Restore critical files if fumigation moved them
if [ ! -f "$PP/shot_plan.json" ]; then
    echo "⚠️  Fumigation archived shot_plan.json — restoring from latest archive..."
    LATEST_ARCHIVE=$(ls -td "$PP"/archive_fumigation_*/ 2>/dev/null | head -1)
    if [ -n "$LATEST_ARCHIVE" ] && [ -f "${LATEST_ARCHIVE}shot_plan.json" ]; then
        cp "${LATEST_ARCHIVE}shot_plan.json" "$PP/shot_plan.json"
        cp "${LATEST_ARCHIVE}cast_map.json" "$PP/cast_map.json" 2>/dev/null
        cp "${LATEST_ARCHIVE}wardrobe.json" "$PP/wardrobe.json" 2>/dev/null
        cp "${LATEST_ARCHIVE}extras.json" "$PP/extras.json" 2>/dev/null
        cp -r "${LATEST_ARCHIVE}character_library_locked/" "$PP/character_library_locked/" 2>/dev/null
        cp -r "${LATEST_ARCHIVE}location_masters/" "$PP/location_masters/" 2>/dev/null
        echo "✅ Restored shot_plan + cast_map + wardrobe + extras + refs from archive"
    fi
fi
echo ""

# Step 2: Fix-v16 on ALL shots
echo "⏳ Step 2: Running fix-v16 on ALL shots (enrichment pipeline)..."
echo "   This may take 30-60 seconds..."
FIX=$(curl -s -X POST "$SERVER/api/shot-plan/fix-v16" \
    -H "Content-Type: application/json" \
    -d "{\"project\":\"$PROJECT\"}")
echo "✅ Fix-v16: $(echo $FIX | python3 -c 'import sys,json; d=json.load(sys.stdin); print(f"fixes={d.get(\"fixes_applied\",\"?\")}") ' 2>/dev/null || echo 'complete')"
echo ""

# Step 3: Post-fix sanitizer
echo "⏳ Step 3: Running post-fix sanitizer (stripping contaminants)..."
python3 tools/post_fixv16_sanitizer.py "$PROJECT" 2>&1 | tail -5
echo "✅ Sanitizer complete"
echo ""

# Step 4: 10-contract audit
echo "⏳ Step 4: Running 10-contract audit..."
AUDIT=$(curl -s -X POST "$SERVER/api/v21/audit/$PROJECT" \
    -H "Content-Type: application/json" \
    -d '{}')
CRITICAL=$(echo $AUDIT | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("critical_count",d.get("summary",{}).get("critical","?")))' 2>/dev/null || echo '?')
echo "✅ Audit: CRITICAL=$CRITICAL"
if [ "$CRITICAL" != "0" ] && [ "$CRITICAL" != "?" ]; then
    echo "⚠️  WARNING: $CRITICAL critical violations found. Review before rendering."
    echo "   Full audit: curl -s -X POST $SERVER/api/v21/audit/$PROJECT | python3 -m json.tool"
fi
echo ""

# Step 5: Render Scene 001 via master chain
echo "============================================================"
echo "  RENDERING SCENE 001 — MASTER CHAIN PIPELINE"
echo "  Smart chain: REFRAME + BLOCKING_AWARE + INDEPENDENT modes"
echo "============================================================"
echo ""
echo "⏳ Step 5: Starting Scene 001 master chain render..."
echo "   This will take 5-15 minutes depending on FAL API load."
echo "   Watch the server terminal for live progress."
echo ""

RENDER=$(curl -s -X POST "$SERVER/api/v18/master-chain/render-scene" \
    -H "Content-Type: application/json" \
    -d "{\"project\":\"$PROJECT\",\"scene_id\":\"001\"}" \
    --max-time 900)

echo ""
echo "============================================================"
echo "  RENDER COMPLETE"
echo "============================================================"
echo "$RENDER" | python3 -c '
import sys, json
try:
    d = json.load(sys.stdin)
    shots = d.get("shot_results", d.get("results", []))
    total = len(shots)
    ok = sum(1 for s in shots if s.get("status") == "ok" or s.get("status") == "completed")
    chained = sum(1 for s in shots if s.get("chained") or s.get("chain_mode") == "REFRAME")
    blocking = sum(1 for s in shots if s.get("chain_mode") == "BLOCKING_AWARE")
    print(f"  Shots: {ok}/{total} successful")
    print(f"  Chain modes: {chained} REFRAME, {blocking} BLOCKING_AWARE, {total-chained-blocking} INDEPENDENT")
    for s in shots:
        sid = s.get("shot_id", "?")
        status = s.get("status", "?")
        mode = s.get("chain_mode", s.get("frame_source", "?"))
        print(f"    {sid}: {status} ({mode})")
except:
    print(sys.stdin.read() if hasattr(sys.stdin, "read") else "See server logs for details")
' 2>/dev/null || echo "  See server terminal for full results"

echo ""
echo "============================================================"
echo "  DONE — Open browser to http://localhost:9999"
echo "  Load project: $PROJECT"
echo "  Review Scene 001 in screening room"
echo "============================================================"
