# ATLAS ERROR DEEPDIVE — 2026-03-30 R1 (KEEP-UP LATEST)

**Session timestamp:** 2026-03-30T03:16:14Z
**Run number:** R1 (FIRST RUN — no prior deepdive report found)
**System version:** V36.5 (CLAUDE.md) / V36.x (runner inline, V37 governance hooks present)
**Ledger age at snapshot:** 0d 8h 27m (last entry: 2026-03-29T18:43:06)
**Atlas project:** victorian_shadows_ep1

---

## 1. EXECUTIVE SUMMARY

**Score: 8 PASS / 2 CONFIRMED_BUG / 1 ARCHITECTURAL_DEBT / 1 STALE_DOC**

| Category | Count | Delta vs Prior |
|----------|-------|----------------|
| CONFIRMED_BUG | 2 | N/A (R1) |
| ARCHITECTURAL_DEBT | 1 | N/A (R1) |
| STALE_DOC | 1 | N/A (R1) |
| CONFIRMED_FIXED | 9 | N/A (R1) |
| FALSE_POSITIVES | 0 | N/A (R1) |

**Key findings this session:**
1. 🔴 **ORPHAN_SHOT gate blocks Kling + contaminates ledger** — `chain_intelligence_gate` checks `chain_group` field, but runner never writes it (uses in-memory `_gen_strategy` only). ALL M-shots across ALL 6 scenes trigger ORPHAN_SHOT. Gate-blocked run at 2026-03-29T18:43:06 still wrote V=0.5/I=0.75 entries to reward_ledger, overwriting valid V=0.85/I=1.0 data from the 17:54 successful run.
2. 🟡 **9 un-normalized I>1.0 entries in historical ledger** — From 2026-03-24 runs before the V35.0 normalization fix was proven. These are historical artifacts only (latest-per-shot is now normalized), but they pollute aggregate ledger analysis.
3. 🟡 **Runner docstring has stale Seedance-as-PRIMARY references** — Comment block at lines 24, 39 still says "Seedance v2.0 PRIMARY (muapi.ai)" — contradicts C3 Constitutional Law and CLAUDE.md V36 which declares Kling as PRIMARY.
4. ✅ Session enforcer: **47 pass / 0 block** — system is import-healthy.

---

## 2. ORGAN HEALTH MAP

| Organ | Status | Signal | Proof |
|-------|--------|--------|-------|
| 🦴 Skeleton (shot_plan) | 🟢 HEALTHY | isinstance bare-list guard present | runner:1429, runner:4077 |
| 🫀 Liver (prompt sanitizer) | 🟡 DEGRADED | CPC not wired in runner (no `decontaminate_prompt` call found) | `grep decontaminate_prompt atlas_universal_runner.py` → 0 results |
| 🛡️ Immune (doctrine) | 🟡 DEGRADED | CLAUDE.md header says V36.0 but runner already has V37 governance hooks; stale Seedance docstring | Header mismatch, lines 24/39 |
| ⚡ Nervous (hooks) | 🟢 HEALTHY | session_enforcer: 47 pass / 0 block; all imports verified | `python3 tools/session_enforcer.py` → ✅ SYSTEM HEALTHY |
| 👁️ Eyes (vision/identity) | 🟢 HEALTHY | All 4 vision backends registered: gemini_vision, openrouter, florence_fal, heuristic; env keys PRESENT | session_enforcer output |
| 🧠 Cortex (reward signal) | 🟡 DEGRADED | Latest 4 ledger entries: I=0.75 flat (gate-blocked run overwrote valid I=1.0 data); 23/33 latest-per-shot are I=0.75 | Ledger analysis this session |
| 🎬 Cinematographer (generation) | 🟢 HEALTHY | atlas_run_report success=True; scene 006 videos exist (17:54 run) | run report + videos_kling_lite/ |
| ✂️ Editor (stitch) | 🟢 HEALTHY | Wire B (`_fail_sids`) at runner:5228; stitched scenes present for 001,002,004,006,008 | grep + ls |
| 🔄 Regenerator (frozen fix) | 🟢 HEALTHY | Wire C at runner:4976 | grep `WIRE-C` |
| 📋 Doctrine Doc | 🟡 DEGRADED | CLAUDE.md header = V36.0; runner has V37 hooks; docstring says Seedance PRIMARY | Version drift |

---

## 3. CONFIRMED FIXED (DO NOT RE-INVESTIGATE)

These fixes are code-confirmed as of this session:

✅ **ENV LOAD ORDER (V35.0)** — `GOOGLE_API_KEY` + `FAL_KEY` + `OPENROUTER_API_KEY` all set BEFORE vision_judge import (runner lines 154–195). Gemini backend available.

✅ **I-SCORE NORMALIZATION (V35.0)** — `vision_judge.py` line 675: `identity_score = round(identity_score / 5.0, 3)`. Present and correct.

✅ **GEMINI CIRCUIT BREAKER (V30.3)** — `_CONSECUTIVE_ZEROS` / `_ZERO_CIRCUIT_BREAKER=3` / `_GEMINI_TRIPPED` present in vision_judge.py lines 518-529.

✅ **V-SCORE 4-STATE (V30.0)** — Ledger shows [0.0, 0.3, 0.5, 0.85] — all four states present and correct.

✅ **END-FRAME CHAIN FIX (V31.0)** — `extract_last_frame()` called after each group's video (runner lines 1370, 3423). Chain continues from last frame of each clip.

✅ **ROUTE_SHOT ALL KLING (V31.0)** — `route_shot()` returns `"kling"` on all branches (lines 1531-1537). ACTIVE_VIDEO_MODEL default = `"kling"` (line 452).

✅ **LTX RETIRED GUARD (C3)** — `LTX_FAST = _LTXRetiredGuard()` at line 422. Any call raises RuntimeError immediately.

✅ **BARE LIST GUARD (T2-OR-18)** — `isinstance(sp, list)` guard present at runner lines 1429, 4077, and throughout. Multiple files guarded.

✅ **WIRE-A BUDGET RESET** — `_wire_a_reset(scene_id)` called at runner:4272 before each scene. Budget cap = 2 regens/scene.

✅ **CHAIN ARC INTELLIGENCE (V36.5)** — `enrich_shots_with_arc()` called at runner:4455. All 97 shots have `_arc_position` set in shot_plan. E-shots all have `_no_char_ref` flag.

✅ **V36.4 ROOM ANCHOR (chain reframe)** — Room DNA injected into reframe prompts (~runner:3467) and `_location_master_path` in context dict (~runner:4444). Two-layer room anchor present.

✅ **V37 GOVERNANCE HOOKS** — `_V37_GOVERNANCE` wired in runner (4 references). 7 `/api/v37/*` endpoints in orchestrator. V37 runner hook calls at frame-write and video-write sites.

✅ **LEARNING LOG** — 22 fixes recorded, 0 regressions detected (`check_regression()` → ALL CLEAR).

---

## 4. OPEN ISSUES

---

### 🔴 CONFIRMED_BUG — OPEN-001: ORPHAN_SHOT Gate Blocks Kling + Ledger Contamination

**Classification:** CONFIRMED_BUG
**Consecutive reports:** 1 (R1)
**Severity:** HIGH — blocks video regeneration on all M-shots; overwrites good ledger entries

**PROOF RECEIPT:**
```
PROOF: python3 -c "import json; sp=json.load(open('pipeline_outputs/victorian_shadows_ep1/shot_plan.json')); shots=sp if isinstance(sp,list) else sp.get('shots',[]); m=[s for s in shots if '_M' in s.get('shot_id','')]; print([s['shot_id'] for s in m if not s.get('chain_group')][:5])"
OUTPUT: ['001_M01', '001_M02', '001_M03', '001_M04', '001_M05'] (all 28 M-shots across 6 scenes)

PROOF: cat pipeline_outputs/victorian_shadows_ep1/videos_kling_lite/gate_audit.json
OUTPUT: All 4 shots flagged ORPHAN_SHOT at 2026-03-29T18:43:06

PROOF: tail ledger entries at 18:43:06
OUTPUT: 006_M01 I=0.75 V=0.5 C=0.7 (was I=1.0 V=0.85 at 17:54:06 — overwritten by blocked run)
```

**CONFIRMS:** The `chain_intelligence_gate.validate_pre_generation()` checks `shot.get("chain_group")`, but the runner NEVER writes `chain_group` to shot dicts — it uses in-memory `_gen_strategy` ("INDEPENDENT", "CHAIN_ANCHOR", "CHAIN"). The gate has no knowledge of `_gen_strategy`. Every M-shot returns ORPHAN_SHOT.

**Root cause (secondary — ledger contamination):** `gen_scene_multishot()` has NO early exit when ALL groups are gate-blocked. After the group loop, code falls through to Phase 2d (reward signal), which writes V=default(0.5) / I=heuristic(0.75) entries to ledger — overwriting the valid V=0.85 entries from the previous successful run.

**FIX RECIPE (≤5 lines):**
In `atlas_universal_runner.py`, where `_gen_strategy` is assigned (~line 2699-2709), also set `chain_group`:
```python
# EXISTING (line 2699):
s["_gen_strategy"] = "INDEPENDENT"
# ADD:
s["chain_group"] = "independent"

# EXISTING (line 2705):
s["_gen_strategy"] = "CHAIN_ANCHOR"
# ADD:
s["chain_group"] = f"chain_{scene_id}"

# EXISTING (line 2709):
s["_gen_strategy"] = "CHAIN"
# ADD:
s["chain_group"] = f"chain_{scene_id}"
```

**Alternatively** (simpler fix): In `chain_intelligence_gate.py` line 449, accept `_gen_strategy` as valid chain membership:
```python
chain_group = shot.get("chain_group") or shot.get("_chain_group") or shot.get("_gen_strategy")
```

**REGRESSION GUARD:** This fix must NOT touch:
- `_WIRE_A_MAX_REGENS_PER_SCENE` budget logic
- `extract_last_frame()` chain path
- `_arc_position` enrichment (already works correctly)
- `_independent_start_url` logic for INDEPENDENT shots

**VERIFY FIX:** `grep -n "chain_group" atlas_universal_runner.py | grep "s\[" | grep "= "` should show new assignments. Re-run `--videos-only` on scene 006 — gate_audit.json should have `"passed": true`.

---

### 🟡 ARCHITECTURAL_DEBT — OPEN-002: 9 Un-Normalized I>1.0 Historical Ledger Entries

**Classification:** ARCHITECTURAL_DEBT (historical data; normalization fix applied V35.0 but ledger is append-only)
**Consecutive reports:** 1 (R1)
**Severity:** LOW — these are historical (2026-03-24 era); latest-per-shot is normalized

**PROOF RECEIPT:**
```
PROOF: python3 -c "import json; lines=[json.loads(l) for l in open('pipeline_outputs/victorian_shadows_ep1/reward_ledger.jsonl').readlines() if l.strip()]; bad=[e for e in lines if e['I']>1.0]; print(len(bad))"
OUTPUT: 9 entries: I values [5.0, 4.0, 5.0, 5.0, 5.0, 4.0, 5.0, 4.0, 3.5]
Timestamps: all 2026-03-24 (before V35.0 normalization fix)
```

**CONFIRMS:** Pre-V35.0 runs wrote raw Gemini 0-5 I-scores to ledger. The V35.0 fix (vision_judge.py:675) normalizes at scoring time but cannot retroactively fix existing entries.

**Impact:** `avg_I` across all ledger entries is inflated. Any tool reading full ledger history (not latest-per-shot) will compute wrong averages.

**FIX RECIPE:** No code change needed. Run a one-time migration script to normalize historical entries. NOT urgent — only affects aggregate historical analysis.

```python
# One-time fix (do NOT add to runner — run manually):
import json, pathlib
path = pathlib.Path('pipeline_outputs/victorian_shadows_ep1/reward_ledger.jsonl')
lines = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
fixed = [{**e, 'I': round(e['I']/5.0, 3) if e['I'] > 1.0 else e['I']} for e in lines]
path.write_text('\n'.join(json.dumps(e) for e in fixed) + '\n')
```

**REGRESSION GUARD:** This is a data operation only. Does NOT touch any runner code.

---

### 🟡 STALE_DOC — OPEN-003: Runner Docstring Declares Seedance as PRIMARY

**Classification:** STALE_DOC (documentation inconsistency — C3 violation in comment only, not in execution)
**Consecutive reports:** 1 (R1)
**Severity:** LOW — code is correct (ACTIVE_VIDEO_MODEL="kling"), docstring is wrong

**PROOF RECEIPT:**
```
PROOF: grep -n "Seedance.*PRIMARY\|All shots PRIMARY.*Seedance" atlas_universal_runner.py | head -3
OUTPUT:
  Line 24: P2. Videos: ALL shots parallel → Seedance v2.0 PRIMARY (muapi.ai) | Kling v3/pro FALLBACK
  Line 39: All shots PRIMARY → Seedance v2.0 via muapi.ai (images_list=[start_frame, char1, char2, loc])

PROOF: grep -n "ACTIVE_VIDEO_MODEL" atlas_universal_runner.py | head -3
OUTPUT: line 452: ACTIVE_VIDEO_MODEL = os.environ.get("ATLAS_VIDEO_MODEL", "kling")
```

**CONFIRMS:** Execution default is correctly `"kling"`. Docstring at lines 24 and 39 says Seedance is PRIMARY — contradicts C3 and CLAUDE.md V31.0+.

**FIX RECIPE:**
```python
# Line 24 — replace:
#   P2. Videos: ALL shots parallel → Seedance v2.0 PRIMARY (muapi.ai) | Kling v3/pro FALLBACK
# With:
#   P2. Videos: ALL shots sequential (chain) → Kling v3/pro PRIMARY (fal-ai/kling-video/v3/pro) | Seedance RETIRED V31.0

# Line 39 — replace:
#   All shots PRIMARY → Seedance v2.0 via muapi.ai (images_list=[start_frame, char1, char2, loc])
# With:
#   All shots PRIMARY → Kling v3/pro via fal-ai (multi_prompt + @Element identity, end-frame chain)
```

**REGRESSION GUARD:** Comment-only change. No execution impact. Verify `ACTIVE_VIDEO_MODEL` default unchanged.

---

## 5. FALSE POSITIVES RETRACTED THIS SESSION

None. This is R1 — no prior false positives to retract.

---

## 6. PRIORITISED FIX LIST

| Priority | Issue | Class | Impact | Fix Size |
|----------|-------|-------|--------|----------|
| 1 | OPEN-001: ORPHAN_SHOT gate + ledger contamination | CONFIRMED_BUG | HIGH — blocks reruns, contaminates ledger | 3 lines in runner OR 1 line in gate |
| 2 | OPEN-003: Stale Seedance docstring | STALE_DOC | LOW — doc only | 2 comment lines |
| 3 | OPEN-002: Historical I>1.0 ledger entries | ARCHITECTURAL_DEBT | LOW — data only, one-time migration | 5-line migration script |

**NOT IN FIX LIST (excluded by protocol):**
- CPC `decontaminate_prompt` not wired in runner — needs investigation whether it was removed intentionally or never wired (no prior confirmed state to compare against). Flagged for next session.

---

## 7. ANTI-REGRESSION CHECKLIST

```
□ ACTIVE_VIDEO_MODEL default = "kling" — PASS (line 452: os.environ.get("ATLAS_VIDEO_MODEL", "kling"))
□ LTX_FAST raises RuntimeError — PASS (line 422: _LTXRetiredGuard())
□ route_shot() returns "kling" all branches — PASS (lines 1531-1537)
□ FAL_KEY / GOOGLE_API_KEY / OPENROUTER_API_KEY set before vision_judge import — PASS (lines 154-195)
□ I-score normalization present in vision_judge — PASS (line 675: identity_score / 5.0)
□ Gemini circuit breaker wired — PASS (vision_judge lines 518-529)
□ Wire-A budget reset at scene start — PASS (runner:4272 _wire_a_reset(scene_id))
□ Wire-B fail_sids filter — PASS (runner:5228)
□ Wire-C frozen regen — PASS (runner:4976)
□ Bare list guard on shot_plan load — PASS (runner:1429, 4077)
□ Chain arc enrichment wired — PASS (runner:4455 enrich_shots_with_arc)
□ All 97 shots have _arc_position — PASS (python3 check this session)
□ E-shots have _no_char_ref — PASS (35 E-shots, 0 missing flag)
□ V37 governance hooks — PASS (4 _V37_GOVERNANCE refs in runner, 7 /api/v37 in orchestrator)
□ Learning log: 0 regressions — PASS (LearningLog().check_regression() → ALL CLEAR)
□ Session enforcer: SYSTEM HEALTHY — PASS (47 pass, 0 block)
□ chain_group MISSING on all M-shots — ⚠ OPEN-001 (see above)
□ gate_audit.json shows ORPHAN_SHOT errors — ⚠ OPEN-001 (2026-03-29T18:43:06)
□ Last ledger entries show V=0.5 (gate-blocked run contamination) — ⚠ OPEN-001
```

---

## 8. DOCUMENT LINEAGE

- Prior report: **NONE** (this is R1 — first ever keep-up deepdive)
- Prior proof gate: **NONE**
- Next scheduled run: keep-up (+1h), proof-gate (+4h), doctrine-sync (daily)
- Next recommended action: **fix OPEN-001** before any --videos-only re-run or the gate will block again

---

## PROOF_GATE_FEED

```json
{
  "session_timestamp": "2026-03-30T03:16:14Z",
  "ledger_age_hours": 8.5,
  "ledger_last_entry": "006_M04 I=0.75 V=0.5 C=0.7 R=0.756 verdict=PASS",
  "ledger_total_entries": 175,
  "ledger_unique_shots": 33,
  "i_score_unique_values": [0.0, 0.08, 0.15, 0.75, 0.8, 0.85, 0.9, 1.0, 3.5, 4.0, 5.0],
  "i_score_latest_flat_0.75": "23/33 shots (69%) — heuristic fallback dominant in latest state",
  "v_score_unique_values": [0.0, 0.3, 0.5, 0.85],
  "confirmed_bugs": [
    {
      "id": "OPEN-001",
      "title": "ORPHAN_SHOT gate blocks Kling + ledger contamination",
      "consecutive_reports": 1,
      "class": "CONFIRMED_BUG",
      "proof_receipt": "gate_audit.json ORPHAN_SHOT at 18:43:06; ledger V=0.5 overwrite of V=0.85",
      "fix_recipe": "Set s['chain_group'] = f'chain_{scene_id}' when _gen_strategy is CHAIN/CHAIN_ANCHOR; or accept _gen_strategy in gate line 449",
      "regression_guard": ["Wire-A budget", "extract_last_frame", "_arc_position", "_independent_start_url"]
    },
    {
      "id": "OPEN-002",
      "title": "9 un-normalized I>1.0 historical ledger entries",
      "consecutive_reports": 1,
      "class": "ARCHITECTURAL_DEBT",
      "proof_receipt": "9 entries with I in [3.5, 4.0, 5.0] from 2026-03-24 pre-V35.0 runs",
      "fix_recipe": "One-time data migration: divide I by 5.0 where I > 1.0",
      "regression_guard": ["DO NOT modify vision_judge.py — normalization fix already present and correct"]
    }
  ],
  "stale_docs": [
    {
      "id": "OPEN-003",
      "title": "Runner docstring says Seedance PRIMARY",
      "class": "STALE_DOC",
      "lines": [24, 39],
      "fix_recipe": "Update comment to Kling PRIMARY / Seedance RETIRED V31.0"
    }
  ],
  "false_positives_retracted": [],
  "organ_health": {
    "skeleton": "HEALTHY",
    "liver": "DEGRADED — CPC decontaminate_prompt not found in runner (unverified gap)",
    "immune": "DEGRADED — CLAUDE.md header V36.0 while runner has V37 hooks; stale Seedance docstring",
    "nervous": "HEALTHY — session_enforcer 47 pass / 0 block",
    "eyes": "HEALTHY — gemini_vision + openrouter + florence_fal + heuristic all registered",
    "cortex": "DEGRADED — 23/33 latest-per-shot I=0.75 flat; last 4 entries overwritten by OPEN-001",
    "cinematographer": "HEALTHY — run_report success=True; 29 kling videos in videos_kling_lite/",
    "editor": "HEALTHY — Wire B at runner:5228; stitches for 001/002/004/006/008",
    "regenerator": "HEALTHY — Wire C at runner:4976",
    "doctrine_doc": "DEGRADED — version drift V36.0 vs V37 hooks; stale Seedance comment"
  },
  "scenes_with_ledger_data": ["001", "002", "003", "004", "005", "006", "008"],
  "scenes_without_ledger_data": ["007", "009", "010", "011", "012", "013"],
  "production_status": {
    "scenes_001_006": "VIDEOS_GENERATED — stitches exist for 001, 002, 004, 006",
    "scenes_007_013": "FRAMES_ONLY or NOT_STARTED",
    "approval_status": "26 AWAITING_APPROVAL / 6 AUTO_APPROVED / 2 APPROVED / 2 REGEN_REQUESTED / 61 empty"
  },
  "recommended_next_action": "fix_open_001_then_run_generation",
  "fix_priority_1": "Set chain_group on shots in runner before gate check — fixes ORPHAN_SHOT and ledger contamination simultaneously"
}
```

---

*ATLAS Keep-Up R1 — 2026-03-30T03:16:14Z*
*Detection layer: REPORT only — no production files modified*
*Next: fix OPEN-001 before any --videos-only reruns*
