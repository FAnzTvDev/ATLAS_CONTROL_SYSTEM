#!/bin/bash
# ATLAS V24.2 — Victorian Shadows EP1 Scene 001 Full Pipeline
# Runs: fix-v16 → sanitizer → audit → gate-snapshot → master-chain → stitch
set -e

PROJECT="victorian_shadows_ep1"
SERVER="http://localhost:9999"
LOG="/Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM/pipeline_outputs/${PROJECT}/reports/scene001_pipeline_$(date +%Y%m%d_%H%M%S).log"
mkdir -p "$(dirname "$LOG")"

log() { echo "[$(date +%H:%M:%S)] $1" | tee -a "$LOG"; }

log "═══════════════════════════════════════════════════════"
log "ATLAS V24.2 — SCENE 001 PIPELINE START"
log "═══════════════════════════════════════════════════════"

# ──── STEP 1: fix-v16 (full enrichment) ────
log "STEP 1/7: fix-v16 — Full enrichment pass..."
FIX_RESULT=$(curl -s -X POST "$SERVER/api/shot-plan/fix-v16" \
  -H "Content-Type: application/json" \
  -d "{\"project\":\"$PROJECT\"}" 2>&1)
log "fix-v16 result: $(echo "$FIX_RESULT" | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("status","?"), "—", d.get("message","")[:100])' 2>/dev/null || echo "$FIX_RESULT" | head -c 200)"

# ──── STEP 2: Post-fix sanitizer ────
log "STEP 2/7: Post-fix sanitizer — Strip contamination..."
cd /Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM
SANITIZE_RESULT=$(python3 tools/post_fixv16_sanitizer.py "$PROJECT" 2>&1)
log "Sanitizer result: $(echo "$SANITIZE_RESULT" | tail -5)"

# ──── STEP 3: Audit (10 contracts) ────
log "STEP 3/7: Contract audit — 10 contracts..."
AUDIT_RESULT=$(curl -s -X POST "$SERVER/api/v21/audit/$PROJECT" \
  -H "Content-Type: application/json" 2>&1)
AUDIT_CRITICAL=$(echo "$AUDIT_RESULT" | python3 -c 'import sys,json; d=json.load(sys.stdin); print(f"CRITICAL: {d.get(\"critical_count\",\"?\")}, WARNING: {d.get(\"warning_count\",\"?\")}, PASS: {d.get(\"pass_count\",\"?\")}")' 2>/dev/null || echo "Parse failed")
log "Audit: $AUDIT_CRITICAL"

# ──── STEP 4: Gate snapshot ────
log "STEP 4/7: Gate snapshot — Lock prompts..."
GATE_RESULT=$(curl -s -X POST "$SERVER/api/v21/gate-snapshot/$PROJECT" \
  -H "Content-Type: application/json" 2>&1)
log "Gate snapshot: $(echo "$GATE_RESULT" | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("status","?"), "shots:", d.get("shot_count","?"))' 2>/dev/null || echo "$GATE_RESULT" | head -c 200)"

# ──── STEP 5: Master chain Scene 001 (LTX) ────
log "STEP 5/7: Master chain Scene 001 — Generating frames + LTX videos..."
log "  This will take ~5-10 minutes per scene..."
CHAIN_RESULT=$(curl -s --max-time 900 -X POST "$SERVER/api/v18/master-chain/render-scene" \
  -H "Content-Type: application/json" \
  -d "{\"project\":\"$PROJECT\",\"scene_id\":\"001\",\"dry_run\":false}" 2>&1)
log "Chain result: $(echo "$CHAIN_RESULT" | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("status","?"), "— shots:", d.get("shots_completed","?"), "/", d.get("shots_total","?"))' 2>/dev/null || echo "$CHAIN_RESULT" | head -c 300)"

# ──── STEP 6: Stitch Scene 001 ────
log "STEP 6/7: Stitching Scene 001..."
STITCH_RESULT=$(curl -s -X POST "$SERVER/api/v16/stitch/run" \
  -H "Content-Type: application/json" \
  -d "{\"project\":\"$PROJECT\",\"scene_ids\":[\"001\"]}" 2>&1)
log "Stitch result: $(echo "$STITCH_RESULT" | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("status","?"), d.get("output_path","")[-50:])' 2>/dev/null || echo "$STITCH_RESULT" | head -c 200)"

# ──── STEP 7: Post-generation audit ────
log "STEP 7/7: Post-generation verification..."
VERIFY=$(curl -s "$SERVER/api/v16/ui/bundle/$PROJECT" 2>&1 | python3 -c '
import sys, json
d = json.load(sys.stdin)
shots = d.get("shot_gallery_rows", [])
s001 = [s for s in shots if s.get("shot_id","").startswith("001_")]
frames = sum(1 for s in s001 if s.get("first_frame_url"))
vids = sum(1 for s in s001 if s.get("video_url"))
print(f"Scene 001: {len(s001)} shots, {frames} frames, {vids} videos")
' 2>/dev/null || echo "Verify failed")
log "Verification: $VERIFY"

log "═══════════════════════════════════════════════════════"
log "PIPELINE COMPLETE"
log "═══════════════════════════════════════════════════════"
log "Log saved to: $LOG"
