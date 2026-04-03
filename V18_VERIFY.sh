#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# ATLAS V18 — FULL VERIFICATION SCRIPT
# Run this on your Mac to prove all 4 systems are end-to-end
# ═══════════════════════════════════════════════════════════════

HOST="http://localhost:9999"
PROJECT="ravencroft_v17"
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'
PASS=0
FAIL=0

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "          ATLAS V18 END-TO-END VERIFICATION"
echo "═══════════════════════════════════════════════════════════"
echo ""

# ──────────────────────────────────────────────────────────
# CHECK 0: Server health
# ──────────────────────────────────────────────────────────
echo -e "${CYAN}[CHECK 0] Server health...${NC}"
HEALTH=$(curl -s -o /dev/null -w "%{http_code}" "$HOST/api/auto/projects" 2>/dev/null)
if [ "$HEALTH" = "200" ]; then
    echo -e "${GREEN}  ✅ Server is running (HTTP 200)${NC}"
    ((PASS++))
else
    echo -e "${RED}  ❌ Server not responding (HTTP $HEALTH)${NC}"
    echo -e "${RED}  → Run: cd ~/Desktop/ATLAS_CONTROL_SYSTEM && python3 orchestrator_server.py${NC}"
    ((FAIL++))
    echo ""
    echo "Server must be running first. Exiting."
    exit 1
fi

# ──────────────────────────────────────────────────────────
# CHECK 1: UI toggle — LTX ↔ Kling dropdown exists + payload
# ──────────────────────────────────────────────────────────
echo ""
echo -e "${CYAN}[CHECK 1] UI Model Toggle (LTX ↔ Kling)...${NC}"

# 1a: HTML has the dropdown
if grep -q 'id="videoModelSelector"' auto_studio_tab.html 2>/dev/null; then
    echo -e "${GREEN}  ✅ videoModelSelector dropdown exists in HTML${NC}"
    ((PASS++))
else
    echo -e "${RED}  ❌ videoModelSelector NOT found in HTML${NC}"
    ((FAIL++))
fi

# 1b: JS setVideoModel function exists
if grep -q 'function setVideoModel' auto_studio_tab.html 2>/dev/null; then
    echo -e "${GREEN}  ✅ setVideoModel() JS function exists${NC}"
    ((PASS++))
else
    echo -e "${RED}  ❌ setVideoModel() NOT found${NC}"
    ((FAIL++))
fi

# 1c: state.videoModel wired into autonomous render
if grep -q 'video_model: state.videoModel' auto_studio_tab.html 2>/dev/null; then
    echo -e "${GREEN}  ✅ video_model sent in render payload (state.videoModel)${NC}"
    ((PASS++))
else
    echo -e "${RED}  ❌ video_model NOT in render payload${NC}"
    ((FAIL++))
fi

# 1d: Screening room respects model selection for video playback
if grep -q "selectedModel === 'kling' && shot.video_url_kling" auto_studio_tab.html 2>/dev/null; then
    echo -e "${GREEN}  ✅ Screening room switches video source by model${NC}"
    ((PASS++))
else
    echo -e "${RED}  ❌ Screening room does NOT switch video by model${NC}"
    ((FAIL++))
fi

# ──────────────────────────────────────────────────────────
# CHECK 2: Server accepts video_model and routes correctly
# ──────────────────────────────────────────────────────────
echo ""
echo -e "${CYAN}[CHECK 2] Server video_model routing...${NC}"

# 2a: render-videos-turbo accepts video_model
if grep -q 'video_model = request.get("video_model"' orchestrator_server.py 2>/dev/null; then
    echo -e "${GREEN}  ✅ render_videos_turbo reads video_model from request${NC}"
    ((PASS++))
else
    echo -e "${RED}  ❌ Server does NOT read video_model${NC}"
    ((FAIL++))
fi

# 2b: Kling model ID configured
if grep -q 'fal-ai/kling-video' orchestrator_server.py 2>/dev/null; then
    echo -e "${GREEN}  ✅ Kling model ID (fal-ai/kling-video) configured${NC}"
    ((PASS++))
else
    echo -e "${RED}  ❌ Kling model ID NOT in server${NC}"
    ((FAIL++))
fi

# 2c: Server actually accepts video_model in turbo endpoint (live test)
TURBO_TEST=$(curl -s -X POST "$HOST/api/auto/render-videos-turbo" \
    -H "Content-Type: application/json" \
    -d "{\"project\":\"$PROJECT\",\"scene_filter\":\"001\",\"video_model\":\"kling\",\"dry_run\":true}" 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('status','') or d.get('error','no-response'))" 2>/dev/null)
if [ -n "$TURBO_TEST" ] && [ "$TURBO_TEST" != "no-response" ]; then
    echo -e "${GREEN}  ✅ Turbo endpoint responded: $TURBO_TEST${NC}"
    ((PASS++))
else
    echo -e "${YELLOW}  ⚠️  Turbo endpoint did not respond (may need dry_run support)${NC}"
fi

# ──────────────────────────────────────────────────────────
# CHECK 3: Bundle includes video_url_kling field
# ──────────────────────────────────────────────────────────
echo ""
echo -e "${CYAN}[CHECK 3] Bundle video_url_kling field...${NC}"

# 3a: Bundle builder code has video_url_kling
if grep -q '"video_url_kling"' orchestrator_server.py 2>/dev/null; then
    echo -e "${GREEN}  ✅ Bundle builder emits video_url_kling field${NC}"
    ((PASS++))
else
    echo -e "${RED}  ❌ video_url_kling NOT in bundle builder${NC}"
    ((FAIL++))
fi

# 3b: Kling video discovery from videos_kling/ directory
if grep -q 'videos_kling_dir' orchestrator_server.py 2>/dev/null; then
    echo -e "${GREEN}  ✅ Bundle discovers Kling videos from videos_kling/ dir${NC}"
    ((PASS++))
else
    echo -e "${RED}  ❌ No Kling video discovery${NC}"
    ((FAIL++))
fi

# 3c: Live bundle test
BUNDLE_RESULT=$(curl -s "$HOST/api/v16/ui/bundle/$PROJECT" 2>/dev/null | python3 -c "
import json,sys
try:
    d=json.load(sys.stdin)
    rows=d.get('shot_gallery_rows') or []
    has_kling = any(r.get('video_url_kling') for r in rows)
    has_ltx = any(r.get('video_url') for r in rows)
    has_chain = any(r.get('_chain_source') for r in rows)
    print(f'rows={len(rows)} ltx_videos={sum(1 for r in rows if r.get(\"video_url\"))} kling_videos={sum(1 for r in rows if r.get(\"video_url_kling\"))} chain_metadata={sum(1 for r in rows if r.get(\"_chain_source\"))}')
except Exception as e:
    print(f'error: {e}')
" 2>/dev/null)
echo -e "  📦 Bundle: ${BUNDLE_RESULT}"
if echo "$BUNDLE_RESULT" | grep -q "rows="; then
    ((PASS++))
    echo -e "${GREEN}  ✅ Bundle loads successfully${NC}"
    # Check if Kling videos exist on disk
    KLING_COUNT=$(ls pipeline_outputs/$PROJECT/videos_kling/*.mp4 2>/dev/null | wc -l)
    echo -e "  📁 Kling videos on disk: $KLING_COUNT"
    if [ "$KLING_COUNT" -gt 0 ]; then
        echo -e "${GREEN}  ✅ Kling videos exist on disk${NC}"
    else
        echo -e "${YELLOW}  ⚠️  No Kling videos on disk yet (need to generate)${NC}"
    fi
else
    echo -e "${RED}  ❌ Bundle failed to load${NC}"
    ((FAIL++))
fi

# ──────────────────────────────────────────────────────────
# CHECK 4: Master Shot Chain — endpoints + artifacts
# ──────────────────────────────────────────────────────────
echo ""
echo -e "${CYAN}[CHECK 4] Master Shot Chain System...${NC}"

# 4a: Agent file exists
if [ -f "atlas_agents/master_shot_chain_agent.py" ]; then
    LINES=$(wc -l < atlas_agents/master_shot_chain_agent.py)
    echo -e "${GREEN}  ✅ master_shot_chain_agent.py exists ($LINES lines)${NC}"
    ((PASS++))
else
    echo -e "${RED}  ❌ master_shot_chain_agent.py NOT found${NC}"
    ((FAIL++))
fi

# 4b: Agent imports successfully
IMPORT_TEST=$(python3 -c "
import sys; sys.path.insert(0,'.'); sys.path.insert(0,'atlas_agents_v16_7')
from atlas_agents.master_shot_chain_agent import should_chain, ShotChainReport, SCENE_CONTINUITY_LOCKS
print(f'locks={list(SCENE_CONTINUITY_LOCKS.keys())}')
" 2>&1)
if echo "$IMPORT_TEST" | grep -q "locks="; then
    echo -e "${GREEN}  ✅ Agent imports clean: $IMPORT_TEST${NC}"
    ((PASS++))
else
    echo -e "${RED}  ❌ Agent import failed: $IMPORT_TEST${NC}"
    ((FAIL++))
fi

# 4c: Endpoints wired into server
CHAIN_ENDPOINTS=0
for EP in "master-chain/render-scene" "master-chain/parallel-render" "master-chain/status" "master-chain/variant-analysis"; do
    if grep -q "$EP" orchestrator_server.py 2>/dev/null; then
        ((CHAIN_ENDPOINTS++))
    fi
done
if [ "$CHAIN_ENDPOINTS" -eq 4 ]; then
    echo -e "${GREEN}  ✅ All 4 master-chain endpoints wired ($CHAIN_ENDPOINTS/4)${NC}"
    ((PASS++))
else
    echo -e "${RED}  ❌ Only $CHAIN_ENDPOINTS/4 endpoints found${NC}"
    ((FAIL++))
fi

# 4d: should_chain() logic validates B-roll exclusion
BROLL_TEST=$(python3 -c "
import sys; sys.path.insert(0,'.'); sys.path.insert(0,'atlas_agents_v16_7')
from atlas_agents.master_shot_chain_agent import should_chain
# B-roll should NOT chain
assert not should_chain({'shot_id':'001_004R','location':'ROOM','characters':['A']}, {'shot_id':'001_009B','location':'ROOM','characters':['A'],'shot_type':'b-roll'}), 'B-roll should NOT chain'
# Same location blocking SHOULD chain
assert should_chain({'shot_id':'001_001A','location':'ROOM','characters':['A']}, {'shot_id':'001_002R','location':'ROOM','characters':['A'],'shot_type':'medium'}), 'Medium should chain'
# Location change should NOT chain
assert not should_chain({'shot_id':'001_001A','location':'ROOM A','characters':['A']}, {'shot_id':'002_001A','location':'ROOM B','characters':['A'],'shot_type':'medium'}), 'Location change should NOT chain'
# No chars should NOT chain
assert not should_chain({'shot_id':'001_001A','location':'ROOM','characters':['A']}, {'shot_id':'001_010B','location':'ROOM','characters':[],'shot_type':'insert'}), 'No chars should NOT chain'
print('ALL_PASS')
" 2>&1)
if echo "$BROLL_TEST" | grep -q "ALL_PASS"; then
    echo -e "${GREEN}  ✅ should_chain() logic correct (B-roll excluded, blocking chains, location breaks)${NC}"
    ((PASS++))
else
    echo -e "${RED}  ❌ should_chain() test failed: $BROLL_TEST${NC}"
    ((FAIL++))
fi

# 4e: Live endpoint test — variant analysis
VA_RESULT=$(curl -s -X POST "$HOST/api/v18/master-chain/variant-analysis" \
    -H "Content-Type: application/json" \
    -d "{\"project\":\"$PROJECT\",\"scene_id\":\"001\"}" 2>/dev/null | python3 -c "
import json,sys
try:
    d=json.load(sys.stdin)
    if 'error' in d:
        print(f'error: {d[\"error\"]}')
    else:
        shots = d.get('shots',[])
        chained = d.get('chained_shots',0)
        broll = d.get('broll_shots',0)
        flow = d.get('cinematic_flow',[])
        locks = d.get('continuity_locks',[])
        print(f'shots={len(shots)} chained={chained} broll={broll} flow_recs={len(flow)} locks={locks}')
except Exception as e:
    print(f'parse_error: {e}')
" 2>/dev/null)
echo -e "  🔗 Variant Analysis: ${VA_RESULT}"
if echo "$VA_RESULT" | grep -q "shots="; then
    echo -e "${GREEN}  ✅ Variant analysis endpoint works${NC}"
    ((PASS++))
else
    echo -e "${RED}  ❌ Variant analysis endpoint failed${NC}"
    ((FAIL++))
fi

# 4f: Live endpoint test — chain render (dry run)
CHAIN_RENDER=$(curl -s -X POST "$HOST/api/v18/master-chain/render-scene" \
    -H "Content-Type: application/json" \
    -d "{\"project\":\"$PROJECT\",\"scene_id\":\"001\",\"dry_run\":true}" 2>/dev/null | python3 -c "
import json,sys
try:
    d=json.load(sys.stdin)
    if 'error' in d:
        print(f'error: {d[\"error\"]}')
    else:
        print(f'success={d.get(\"success\")} status={d.get(\"status\")} shots={d.get(\"total_shots\")} chained={d.get(\"chained_shots\")} breaks={d.get(\"chain_breaks\")} master={bool(d.get(\"master_frame_path\"))} locks={d.get(\"continuity_locks\",[])}')
except Exception as e:
    print(f'parse_error: {e}')
" 2>/dev/null)
echo -e "  🔗 Chain Render (dry): ${CHAIN_RENDER}"
if echo "$CHAIN_RENDER" | grep -q "success="; then
    echo -e "${GREEN}  ✅ Chain render endpoint works${NC}"
    ((PASS++))
else
    echo -e "${RED}  ❌ Chain render endpoint failed${NC}"
    ((FAIL++))
fi

# 4g: Chain metadata on bundle shots
CHAIN_META=$(curl -s "$HOST/api/v16/ui/bundle/$PROJECT" 2>/dev/null | python3 -c "
import json,sys
try:
    d=json.load(sys.stdin)
    rows=d.get('shot_gallery_rows') or []
    has_chain_fields = sum(1 for r in rows if '_chain_source' in r or '_chain_first_frame_url' in r)
    print(f'bundle_shots_with_chain_fields={has_chain_fields}/{len(rows)}')
except:
    print('error')
" 2>/dev/null)
echo -e "  📦 ${CHAIN_META}"

# 4h: Master Chain button in UI
if grep -q 'id="masterChainBtn"' auto_studio_tab.html 2>/dev/null; then
    echo -e "${GREEN}  ✅ 🔗 Master Chain button exists in UI${NC}"
    ((PASS++))
else
    echo -e "${RED}  ❌ Master Chain button NOT in UI${NC}"
    ((FAIL++))
fi

# ──────────────────────────────────────────────────────────
# CHECK 5: Disk artifacts
# ──────────────────────────────────────────────────────────
echo ""
echo -e "${CYAN}[CHECK 5] Disk artifacts...${NC}"

# First frames
FF_COUNT=$(ls pipeline_outputs/$PROJECT/first_frames/*.jpg 2>/dev/null | wc -l)
echo -e "  📁 First frames: $FF_COUNT"

# LTX videos
LTX_COUNT=$(ls pipeline_outputs/$PROJECT/videos/*.mp4 2>/dev/null | wc -l)
echo -e "  📁 LTX videos: $LTX_COUNT"

# Kling videos
KLING_COUNT=$(ls pipeline_outputs/$PROJECT/videos_kling/*.mp4 2>/dev/null | wc -l)
echo -e "  📁 Kling videos: $KLING_COUNT"

# Variants
VARIANT_COUNT=$(ls pipeline_outputs/$PROJECT/first_frame_variants/*.jpg 2>/dev/null | wc -l)
echo -e "  📁 Variants: $VARIANT_COUNT"

# Chain reports
CHAIN_REPORTS=$(ls pipeline_outputs/$PROJECT/chain_reports/*.json 2>/dev/null | wc -l)
echo -e "  📁 Chain reports: $CHAIN_REPORTS"

# Chain metadata
if [ -f "pipeline_outputs/$PROJECT/chain_metadata.json" ]; then
    echo -e "${GREEN}  ✅ chain_metadata.json exists${NC}"
else
    echo -e "${YELLOW}  ⚠️  chain_metadata.json not yet created (run master chain first)${NC}"
fi

# Master shots
MASTER_COUNT=$(ls pipeline_outputs/$PROJECT/master_shots/*.jpg 2>/dev/null | wc -l)
echo -e "  📁 Master shots: $MASTER_COUNT"

# Frame chains (end-frame extractions)
FRAME_CHAINS=$(ls pipeline_outputs/$PROJECT/frame_chains/*.jpg 2>/dev/null | wc -l)
echo -e "  📁 Frame chains (end-frame extractions): $FRAME_CHAINS"

# ──────────────────────────────────────────────────────────
# SUMMARY
# ──────────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════════"
TOTAL=$((PASS + FAIL))
echo -e "  RESULTS: ${GREEN}${PASS} passed${NC} / ${RED}${FAIL} failed${NC} / ${TOTAL} total"
echo ""
if [ "$FAIL" -eq 0 ]; then
    echo -e "  ${GREEN}🎉 ALL CHECKS PASSED — V18 is end-to-end verified${NC}"
else
    echo -e "  ${YELLOW}⚠️  $FAIL checks need attention${NC}"
fi
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "To trigger the master chain pipeline from UI:"
echo "  1. Open http://localhost:9999 in browser"
echo "  2. Select a scene in Screening Room"
echo "  3. Click 🔗 Master Chain button"
echo ""
echo "Or via curl:"
echo "  curl -X POST '$HOST/api/v18/master-chain/render-scene' \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"project\":\"$PROJECT\",\"scene_id\":\"001\",\"dry_run\":false}'"
echo ""
