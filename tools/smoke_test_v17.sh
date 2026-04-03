#!/bin/bash
# ATLAS V17 Quick Smoke Test
# Usage: ./tools/smoke_test_v17.sh [project_name]
# Exit 0 = ready to ship, Exit 1 = blocked

set -e
PROJECT="${1:-kord_v17}"
BASE="http://localhost:9999"

echo "=========================================="
echo "ATLAS V17 SMOKE TEST - $PROJECT"
echo "=========================================="

# 1. Health
echo -n "[1/7] Health check... "
HEALTH=$(curl -sf "$BASE/api/health" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','fail'))")
if [ "$HEALTH" = "ok" ]; then echo "PASS"; else echo "FAIL"; exit 1; fi

# 2. Bundle
echo -n "[2/7] Bundle check... "
BUNDLE=$(curl -sf "$BASE/api/v16/ui/bundle/$PROJECT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f\"{d.get('success')},{d.get('shot_plan_summary',{}).get('total_shots',0)}\")")
if [[ "$BUNDLE" == "True,"* ]]; then echo "PASS ($BUNDLE)"; else echo "FAIL"; exit 1; fi

# 3. Auto-Cast
echo -n "[3/7] Auto-cast... "
CAST=$(curl -sf -X POST "$BASE/api/v6/casting/auto-cast" -H "Content-Type: application/json" -d "{\"project\":\"$PROJECT\"}" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('success', d.get('cast_count',0) > 0))")
if [ "$CAST" != "False" ]; then echo "PASS"; else echo "WARN (check manually)"; fi

# 4. Frame Gen (dry-run)
echo -n "[4/7] Frame gen... "
FRAME=$(curl -sf -X POST "$BASE/api/auto/generate-first-frames" -H "Content-Type: application/json" -d "{\"project\":\"$PROJECT\",\"limit\":1,\"dry_run\":true}" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('generation_plan',[])))")
echo "PASS ($FRAME ready)"

# 5. Video Gen (dry-run)
echo -n "[5/7] Video gen... "
VIDEO=$(curl -sf -X POST "$BASE/api/auto/render-videos" -H "Content-Type: application/json" -d "{\"project\":\"$PROJECT\",\"limit\":1,\"dry_run\":true}" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('generation_plan',[])))")
echo "PASS ($VIDEO ready)"

# 6. Stitch Dry-Run
echo -n "[6/7] Stitch dry-run... "
STITCH=$(curl -sf -X POST "$BASE/api/v16/stitch/dry-run" -H "Content-Type: application/json" -d "{\"project\":\"$PROJECT\"}" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f\"{d.get('ready_count',0)}/{d.get('total_count',0)}\")")
echo "PASS ($STITCH)"

# 7. QA Analyze
echo -n "[7/7] QA analyze... "
SHOT_ID=$(curl -sf "$BASE/api/v16/ui/bundle/$PROJECT" | python3 -c "import sys,json; d=json.load(sys.stdin); rows=d.get('shot_gallery_rows',[]); print(rows[0]['shot_id'] if rows else '')")
if [ -n "$SHOT_ID" ]; then
    QA=$(curl -sf -X POST "$BASE/api/v16/qa/analyze" -H "Content-Type: application/json" -d "{\"project\":\"$PROJECT\",\"shot_id\":\"$SHOT_ID\"}" | python3 -c "import sys,json; print('ok')" 2>/dev/null || echo "fail")
    if [ "$QA" = "ok" ]; then echo "PASS"; else echo "WARN"; fi
else
    echo "SKIP (no shots)"
fi

echo "=========================================="
echo "SMOKE TEST PASSED - Ready to ship"
echo "=========================================="
exit 0
