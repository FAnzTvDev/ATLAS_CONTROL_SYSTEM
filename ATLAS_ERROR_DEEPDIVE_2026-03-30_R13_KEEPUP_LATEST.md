# ATLAS ERROR DEEPDIVE — 2026-03-30 R13 (KEEP-UP LATEST)

**Session timestamp:** 2026-03-30T15:14:48Z
**Run number:** R13
**Prior report:** ATLAS_ERROR_DEEPDIVE_2026-03-30_R12_KEEPUP_LATEST.md
**System version:** V36.5 (CLAUDE.md) / V31.0 docstring (runner header)
**Ledger age at snapshot:** 0d 6h 27m (last entry 2026-03-30T08:47:31)
**Atlas project:** victorian_shadows_ep1

---

## 1. EXECUTIVE SUMMARY

**Score: 13 PASS / 1 CONFIRMED_BUG (non-blocking) / 1 CHRONIC-6 / 1 ARCHITECTURAL_DEBT / 2 STALE_DOC / 2 FALSE_POSITIVES_RETRACTED**

| Category | Count | Delta vs R12 | Status |
|----------|-------|-------------|--------|
| FALSE_POSITIVES RETRACTED | **2** | ⬆ +2 NEW | **OPEN-008 + OPEN-006 → CLOSED** |
| CONFIRMED_BUG | 1 | ↓ -1 (OPEN-009 only) | Non-blocking path format |
| CHRONIC | 1 | OPEN-004 (6th consecutive report) | P2, fix recipe available |
| ARCHITECTURAL_DEBT | 1 | = same (OPEN-002 reward signal) | Defer post-run |
| STALE_DOC | 2 | = same (OPEN-003, OPEN-005) | Cosmetic |
| CONFIRMED_FIXED | **21** | +2 (OPEN-008 retracted + OPEN-006 retracted) | ✅ |

**Key findings R13:**

1. 🟢 **OPEN-008 RETRACTED — FALSE POSITIVE ACROSS R8-R12 (5 reports).** This report proves via live code execution that the CIG CHARACTER_NAME_LEAK gate does NOT scan `_beat_description`. The gate's `_get_text_fields()` function checks only `_beat_action`, `nano_prompt`, `_frame_prompt`, `_choreography`, `_beat_atmosphere`, `_arc_carry_directive`. Character names in `_beat_description` are metadata-only and never reach the gate. Live full-sweep test: 0/35 E-shots currently fail CIG gate, 0/62 M-shots fail. **Scenes 001/002/004 were NEVER blocked by CIG.** Furthermore, the gate_audit.json temporal analysis shows the CHARACTER_NAME_LEAK failures from 07:52 run were fixed by 08:21 (during same session). The fix tool (`shot_plan_gate_fixer.py FIX-1`) targets `_beat_action` — and that field is NOW CLEAN on all E-shots. OPEN-008 is closed as FALSE_POSITIVE.

2. 🟢 **OPEN-006 RETRACTED — DEPENDENT ON FALSE POSITIVE (OPEN-008).** OPEN-006 was a STALE_GATE_STATE that was "awaiting OPEN-008 fix." Since OPEN-008 was a false positive, OPEN-006 also closes.

3. 🟡 **OPEN-004 NOW CHRONIC-6 (6 consecutive reports: R8→R13).** `decontaminate_prompt()` confirmed absent from runner (`grep` → empty). 013_M01/M02/E01/E02 still have `_beat_action=None`. Fix recipe unchanged (7-line try/except at runner:~1120).

4. 🟢 **SESSION ENFORCER: SYSTEM HEALTHY.** 0 blocks — all wiring intact. Vision backends: [gemini_vision, openrouter, florence_fal, heuristic].

5. 🟢 **ALL E-SHOTS AND M-SHOTS PASS CIG PRE-GEN GATE.** Full live sweep: 0/97 shots fail.

6. 🟡 **REWARD SIGNAL UNCHANGED.** 228 ledger entries, 87.8% heuristic latest-per-shot. Last run was 6h 27m ago (scenes 001 M-shots at 08:47). No new generation.

7. 🟡 **VIDEO COVERAGE: 28/97 shots have video** (28.9%). Scenes 006, 008 = 100%. Scenes 001/002/003/004 partial. Scenes 005/007/009-013 = 0%. The production gap is not a code bug — it's a generation pipeline that hasn't been run for most scenes yet.

8. ℹ️ **OPEN-009 (API-path video_url) PERSISTS.** 4 shots (008_E01/E02/E03, 008_M03b) still have `/api/media?path=` prefix on `video_url`. Files confirmed to exist at resolved paths. Non-blocking.

---

## 2. ORGAN HEALTH MAP

| Organ | Status | Signal | Proof (R13) |
|-------|--------|--------|------------|
| 🦴 Skeleton (shot_plan) | 🟢 HEALTHY | 97 shots, 13 scenes, bare-list guard at runner:1492. All M-shots have `_chain_group`. | `isinstance` guard confirmed; 62/62 M-shots have `_chain_group` |
| 🫀 Liver (prompt sanitizer) | 🔴 DEGRADED | `decontaminate_prompt()` absent from runner. CHRONIC-6. 013_M01/M02/E01/E02 have `_beat_action=None`. | `grep decontaminate_prompt atlas_universal_runner.py` → (no output) |
| 🛡️ Immune (doctrine) | 🟡 DEGRADED | Runner header lines 24/39 still claim Seedance PRIMARY. Code correct (ACTIVE_VIDEO_MODEL="kling" at line 515). | Runner:24 = "Seedance v2.0 PRIMARY (muapi.ai)" |
| ⚡ Nervous (hooks) | 🟢 HEALTHY | Session enforcer: ✅ SYSTEM HEALTHY. All 22 learning log fixes intact, 0 regressions. All 4 doctrine hooks wired. | `python3 tools/session_enforcer.py` |
| 👁️ Eyes (vision/identity) | 🟡 DEGRADED | All 5 env keys PRESENT (FAL, OPENROUTER, ANTHROPIC, MUAPI, GOOGLE). Vision backends available. BUT 87.8% heuristic latest-per-shot. | Enforcer + env check + ledger |
| 🧠 Cortex (reward signal) | 🔴 DEGRADED | 228 entries. 87.8% latest-per-shot heuristic. Last 5 entries all I=0.75. Only scenes 004/008 show real VLM scores (I≠0.75). | `python3 -c "... ledger analysis R13"` |
| 🎬 Cinematographer (generation) | 🟡 DEGRADED | 62 first_frames, 28 shots with video_url. Scenes 006/008 complete. 11 scenes either partial (001-004) or zero (005/007/009-013). CIG gate: 0/97 blocked. | Shot_plan + gate live scan |
| ✂️ Editor (stitch) | 🟢 HEALTHY | Wire-B logic at runner:5470 (`_fail_sids`). Functional; label cosmetic only (OPEN-003). | `grep _fail_sids atlas_universal_runner.py` |
| 🔄 Regenerator (frozen fix) | 🟢 HEALTHY | Wire-C at runner:5245, 5265, 5267, 5270, 5272. All branches intact. | `grep "WIRE-C" atlas_universal_runner.py` |
| 📋 Doctrine Doc | 🟡 DEGRADED | Runner header Seedance claims (lines 24/39). CLAUDE.md V36.5 is correct. Code reality = Kling default. Cosmetic. | grep ACTIVE_VIDEO_MODEL → "kling" |

---

## 3. CONFIRMED FIXED (DO NOT RE-INVESTIGATE)

Now 21 items — 2 newly retracted from open issues and promoted to confirmed-closed.

✅ **ENV LOAD ORDER (V35.0)** — All 5 keys PRESENT.
✅ **I-SCORE NORMALIZATION (V35.0)** — vision_judge.py line 675.
✅ **GEMINI CIRCUIT BREAKER (V30.3)** — vision_judge.py lines 518-529.
✅ **V-SCORE 4-STATE (V30.0)** — All four states present.
✅ **END-FRAME CHAIN FIX (V31.0)** — extract_last_frame() at runner:1408, 3534.
✅ **ROUTE_SHOT ALL KLING (V31.0)** — All branches return "kling".
✅ **LTX RETIRED GUARD (C3)** — _LTXRetiredGuard() at runner:485.
✅ **BARE LIST GUARD (T2-OR-18)** — isinstance at runner:1492.
✅ **WIRE-A BUDGET RESET** — _wire_a_reset() at runner:4386.
✅ **CHAIN ARC INTELLIGENCE (V36.5)** — enrich_shots_with_arc() imported and wired.
✅ **V36.4 ROOM ANCHOR** — loc_master in images_list, Room DNA in prompts.
✅ **V37 GOVERNANCE HOOKS** — All endpoints + runner hooks verified present.
✅ **LEARNING LOG** — 22 fixes recorded, 0 regressions (ALL CLEAR).
✅ **CPC INLINE DETECTION** — _is_cpc_via_embedding() at runner:245, called at runner:1118.
✅ **E-SHOT ISOLATION** — _no_char_ref=True, _is_broll=True marked on E-shots.
✅ **Wire-C WIRED** — [WIRE-C] labels at runner:5245+.
✅ **CHAIN_GROUP SET ON M-SHOTS** — All 62 M-shots confirmed with _chain_group.
✅ **ACTIVE_VIDEO_MODEL DEFAULT = "kling"** — runner:515 confirmed.
✅ **OPEN-007 CLOSED (R11)** — 0 broken video_url filesystem paths.
✅ **OPEN-008 CLOSED (R13) — CIG CHARACTER_NAME_LEAK gate never fires on current shot_plan.** Gate scans `_beat_action`/`nano_prompt`/`_frame_prompt`/`_choreography`/`_beat_atmosphere`/`_arc_carry_directive` — NOT `_beat_description`. All E-shot gate fields are clean. 0/35 E-shots fail CIG gate. The CHARACTER_NAME_LEAK failures in gate_audit.json (timestamps 07:52) were from an EARLIER run that day; by 08:21 the fields were cleaned and the gate PASSED. Scenes 001/002/004 are not blocked.
✅ **OPEN-006 CLOSED (R13) — STALE_GATE_STATE was dependent on OPEN-008.** With OPEN-008 retracted, OPEN-006 also closes. gate_audit.json historic CHARACTER_NAME_LEAK entries are from an earlier run; current state is clean.

---

## 4. OPEN ISSUES

### OPEN-009 (CONFIRMED_BUG — R12+R13, Non-blocking, 2nd consecutive report)

**Issue:** 4 shots have `/api/media?path=` prefix in `video_url` instead of filesystem path.

**PROOF RECEIPT:**
```
PROOF: python3 -c "... video_url format scan ..."
OUTPUT:
  SHOTS_WITH_API_MEDIA_PATH: 4
    008_E01: /api/media?path=pipeline_outputs/.../videos_kling_lite/008_E01 exists=True
    008_E02: /api/media?path=pipeline_outputs/.../videos_kling_lite/008_E02 exists=True
    008_E03: /api/media?path=pipeline_outputs/.../videos_kling_lite/008_E03 exists=True
    008_M03b: /api/media?path=pipeline_outputs/.../videos_kling_lite/008_M03 exists=True
  SHOTS_WITH_BROKEN_FS_PATH: 0
CONFIRMS: API-format paths persist. Files physically exist. os.path.exists() fails on these 4.
```

**Impact:**
- `os.path.exists()` check incorrectly reports these as broken in health scripts → false positives in keep-up monitoring
- Stitch risk: if runner uses `os.path.exists(video_url)` before adding to concat list, these 4 shots excluded from scene 008 stitch
- UI display unaffected (API path resolves correctly)

**Fix recipe (shot_plan.json data patch only):**
```python
# In pipeline_outputs/victorian_shadows_ep1/shot_plan.json, for each of 4 shots:
# Find video_url = "/api/media?path=X" and replace with just "X"
# 4 lines only, no code changes required
```

**Regression guard:** After fix, re-run broken video_url check → 0 API-path shots, 0 broken FS paths.

**Classification:** CONFIRMED_BUG — data inconsistency. Non-blocking for generation. Introduces false positives in keep-up monitoring.

---

### ⏱️ CHRONIC-6 (6 reports): OPEN-004 — decontaminate_prompt absent from runner

**Issue:** `decontaminate_prompt()` not called in runner. 013_M01/M02/E01/E02 have `_beat_action=None`.

**Consecutive reports:** R8, R9, R10, R11, R12, R13 (6 reports). **CHRONIC (5–9 range).**

**PROOF RECEIPT:**
```
PROOF: grep -n "decontaminate_prompt" atlas_universal_runner.py
OUTPUT: (no output — function not present in runner)

PROOF: python3 -c "scene 013 _beat_action check"
OUTPUT:
  013_E01: _beat_action=None _beat_ref=beat_1
  013_E02: _beat_action=None _beat_ref=beat_1
  013_M01: _beat_action=None _beat_ref=beat_2
  013_M02: _beat_action=None _beat_ref=beat_2
CONFIRMS: CPC decontamination absent from runner. Scene 013 will produce generic video.
```

**Why CHRONIC:** CPC inline detection fires at runner:1118 (`_is_cpc_via_embedding()`) but the replacement call `decontaminate_prompt()` was never wired. Detection-only mode — identifies generic prompts but does not replace them.

**Fix recipe (7 lines, non-breaking, try/except wrapper):**
```python
# At runner line ~1120, AFTER _is_cpc_via_embedding() detection block:
if clean_choreo and _is_cpc_via_embedding(clean_choreo):
    try:
        from tools.creative_prompt_compiler import decontaminate_prompt
        clean_choreo = decontaminate_prompt(clean_choreo, shot.get("_emotional_state", ""))
    except ImportError:
        pass  # Non-blocking: detection-only mode continues as fallback
```

**Regression guard:** After fix, run 013_M01 frame-only and verify prompt no longer contains GENERIC_PATTERNS terms. Verify scenes 001-008 show identical prompt structure (the try/except means no-op if import fails).

**Classification:** CHRONIC-6. Fix recipe safe. Recommend human review before next generation cycle.

---

### OPEN-002 (ARCHITECTURAL_DEBT-12)

**Issue:** Reward signal degradation — 87.8% heuristic I-scores latest-per-shot.

**PROOF RECEIPT:**
```
PROOF: python3 -c "... ledger analysis R13"
OUTPUT:
  UNIQUE_SHOTS: 41
  HEURISTIC_I (latest): 36/41 = 87.8%
  REAL_I (latest): 5/41 = 12.2%
  REAL_I SAMPLES: [('008_M01',1.0),('008_M02',0.9),('008_M04',0.8),('004_M01',1.0),('004_M02',1.0)]
CONFIRMS: Vision_judge fires on some scenes (004/008) but not others. Heuristic dominates.
```

**R13 note:** Scene 001 videos were generated in the 08:47 run. All 5 entries (001_M01-M05) show I=0.75 heuristic. This confirms vision_judge is NOT firing during CLI generation runs consistently. The scenes 004/008 that show real scores had their videos generated in different runs. Possible warm-up timing or environment initialization order issue.

**Classification:** ARCHITECTURAL_DEBT — Not code-broken, partially operational. Defer until new generation run allows A/B comparison.

---

### OPEN-003 (STALE_DOC-12)

**Issue:** Wire-B label missing from runner code at line 5470.

**Proof:** `grep "WIRE-B" atlas_universal_runner.py` → (no output). Logic functional (`_fail_sids` at line 5470).

**Fix:** Add `# ── [WIRE-B] Quality gate stitch filter` comment at runner:5470.

**Status:** STALE_DOC — Cosmetic. 12th consecutive report.

---

### OPEN-005 (STALE_DOC-10)

**Issue:** Runner header lines 24/39 still claim Seedance v2.0 as PRIMARY model.

**Proof:**
```
Runner line 24: "ALL shots parallel → Seedance v2.0 PRIMARY (muapi.ai) | Kling v3/pro FALLBACK"
Runner line 39: "All shots PRIMARY → Seedance v2.0 via muapi.ai"
Code reality: ACTIVE_VIDEO_MODEL = os.environ.get("ATLAS_VIDEO_MODEL", "kling") [line 515]
```

**Status:** STALE_DOC — Cosmetic. 10th consecutive report.

---

## 5. FALSE POSITIVES RETRACTED THIS SESSION

### ✅ OPEN-008 RETRACTED — "CIG CHARACTER_NAME_LEAK blocks scenes 001/002/004"

**Why it was reported:** Keep-up scripts R8-R12 scanned `_beat_description` for character names and found 30-32 matches. Reports incorrectly assumed the CIG gate scanned this field.

**Why it was wrong:**
```
PROOF: Inspect tools/chain_intelligence_gate.py _get_text_fields() (line 246-254)
OUTPUT: Returns _beat_action, nano_prompt, _frame_prompt, _choreography,
        _beat_atmosphere, _arc_carry_directive. NOT _beat_description.

PROOF: python3 -c "validate_pre_generation(001_E01...)"
OUTPUT: passed=True errors=[]

PROOF: Full sweep — validate_pre_generation() on all 97 shots
OUTPUT: ALL SHOTS PASS CIG PRE-GEN GATE: 0 blocked

PROOF: gate_audit.json temporal analysis
OUTPUT: CHARACTER_NAME_LEAK failures at 07:52 (earlier run) → PASSED at 08:21+
        (shot_plan.json fixed between runs, shot_plan mtime = 08:47:31)
```

**Impact of retraction:** The previous P0 priority fix recommendation (run shot_plan_gate_fixer.py FIX-1) was unnecessary. The scenes were not blocked. Scenes 001/002/004 partial video coverage is a generation gap (not enough runs), not a gate block.

**Action:** Remove from open issues. Add to confirmed-fixed list. Prior fix recipe (`shot_plan_gate_fixer.py FIX-1`) does not need to be run for generation to proceed.

---

### ✅ OPEN-006 RETRACTED — "STALE_GATE_STATE awaiting OPEN-008 fix"

**Why it was reported:** R8-R12 listed OPEN-006 as dependent on OPEN-008.

**Why it closes:** OPEN-008 was a false positive. The gate_audit.json CHARACTER_NAME_LEAK entries in the ORPHAN category are historical (from 07:52 run) — the current run (08:21+) shows all passes. The stale gate state was the observation log capturing the history of a problem that was already resolved.

---

## 6. PRIORITISED FIX LIST

| Priority | Issue | Effort | Fix Recipe | Blocking |
|----------|-------|--------|-----------|----------|
| **P1** | OPEN-009 (API-path video_url on 4 shots) | 1 min | JSON patch: strip `/api/media?path=` prefix from 4 video_url fields | NO — stitch risk only |
| **P2** | OPEN-004 (CPC decontamination CHRONIC-6) | 5 min | 7-line try/except at runner:~1120 | NO — future scenes |
| **P3** | OPEN-002 (reward signal) | 30 min | Debug vision_judge CLI init timing | NO — observational |
| **P4** | OPEN-003 (Wire-B label) | 1 min | Add comment at runner:5470 | NO — cosmetic |
| **P4** | OPEN-005 (docstring Seedance) | 2 min | Update runner header lines 24, 39 | NO — cosmetic |

**Previously P0 OPEN-008 removed — FALSE POSITIVE. No generation blocking issues exist.**

---

## 7. ANTI-REGRESSION CHECKLIST

**Before next generation run:**
```
□ Run session_enforcer → ✅ SYSTEM HEALTHY (target: 0 blocks)
□ Confirm OPEN-009 fix: normalize 4 API-path video_urls (optional but recommended for stitch safety)
□ Verify vision backends online: gemini_vision + openrouter in available list
□ Run pre-run-gate before generation to archive stale artifacts
□ After generation: check reward_ledger I-score distribution (target: ≥50% real scores)
□ Confirm gate_audit.json shows 0 pre_gen failures for target scenes
□ DO NOT run shot_plan_gate_fixer.py FIX-1 — not needed (OPEN-008 retracted)
□ Confirm E-shot _beat_action fields remain clean (no character names)
```

---

## 8. DELTA FROM R12

| Signal | R12 | R13 | Delta | Note |
|--------|-----|-----|-------|------|
| FALSE_POSITIVES_RETRACTED | 0 | 2 | ⬆ +2 | OPEN-008 + OPEN-006 → closed |
| CONFIRMED_FIXED | 19 | 21 | +2 | Two open issues retracted |
| P0 blockers | 1 (OPEN-008) | 0 | ↓ -1 | OPEN-008 was FALSE_POSITIVE |
| CIG gate blocks | Claimed 30 E-shots blocked | 0/97 shots blocked | ✅ CLEAR | Gate never scanned _beat_description |
| Ledger entries | 228 | 228 | = unchanged | No new generation run |
| API-path video_urls | 4 (OPEN-009) | 4 | = unchanged | Persists |
| OPEN-004 consecutive | 5 (CHRONIC-5) | 6 (CHRONIC-6) | +1 | Decontaminate still absent |
| Session enforcer | 69 PASS, 0 BLOCK | SYSTEM HEALTHY | = unchanged | All healthy |
| Heuristic I-score latest | 87.8% | 87.8% | = unchanged | No new run |
| Scenes 100% video | 2 (006, 008) | 2 (006, 008) | = unchanged | |
| Shot plan total | 97 | 97 | = unchanged | |

---

## 9. GENERATION READINESS ASSESSMENT (R13)

With OPEN-008 false positive retracted, the generation readiness picture changes:

**Can generate scenes 001/002/003/004 videos NOW:**
```bash
python3 atlas_universal_runner.py victorian_shadows_ep1 001 002 003 004 --mode lite --videos-only
```
- ✅ CIG gate: 0 blocks on all shots
- ✅ M-shots: all 62 have _chain_group (no ORPHAN_SHOT errors)
- ✅ E-shot _beat_action: clean (no character names)
- ✅ Session enforcer: SYSTEM HEALTHY
- ⚠️ OPEN-009 (4 API-path video_url): patch scene 008 shot_plan after run if stitch needed

**Can generate scenes 005/007/009-013 frames + videos:**
```bash
python3 atlas_universal_runner.py victorian_shadows_ep1 005 007 009 010 011 012 013 --mode lite
```
- ✅ No gate blocks confirmed
- ✅ First frames not yet generated — need `--frames-only` first for review

---

## 10. DOCUMENT LINEAGE

**Report chain:**
- R1-R7: hourly incremental baseline and consolidation
- R8 (OPEN-004 first reported, OPEN-008 first reported — both NOW RECLASSIFIED as of R13)
- R9-R12: OPEN-008 persisted as P0 (FALSE POSITIVE — gate was never scanning _beat_description)
- **R13 (CURRENT)** — OPEN-008 + OPEN-006 retracted as FALSE POSITIVES. No P0 blockers remain.

**Session learnings integrated:** V36.5 Chain Arc (present), V36.4 Room DNA (present), V37 Governance (present), learning log 22/22 (verified), LTX guard at runner:485 (verified).

---

## PROOF_GATE_FEED (Machine-readable)

```json
{
  "session_timestamp": "2026-03-30T15:14:48Z",
  "run_number": 13,
  "prior_report": "R12",
  "system_version": "V36.5",
  "ledger_age_minutes": 387,
  "atlas_project": "victorian_shadows_ep1",
  "audit_scores": {
    "confirmed_fixed": 21,
    "confirmed_bug": 1,
    "chronic": 1,
    "architectural_debt": 1,
    "stale_doc": 2,
    "false_positives_retracted": 2
  },
  "key_signals": {
    "cig_gate_blocked_shots": 0,
    "cig_gate_scans_beat_description": false,
    "broken_fs_video_urls": 0,
    "api_path_video_urls": 4,
    "e_shots_with_char_names_in_gate_fields": 0,
    "e_shots_total": 35,
    "m_shots_with_chain_group": 62,
    "m_shots_without_chain_group": 0,
    "session_enforcer_status": "HEALTHY",
    "session_enforcer_block_count": 0,
    "reward_ledger_heuristic_pct_latest": 87.8,
    "reward_ledger_total_entries": 228,
    "reward_ledger_unique_shots": 41,
    "shots_with_video": 28,
    "scenes_with_100pct_video": 2,
    "p0_blockers": 0,
    "shot_plan_total_shots": 97,
    "shot_plan_unique_scenes": 13,
    "run_report_success": true
  },
  "false_positives_retracted": [
    {
      "id": "OPEN-008",
      "consecutive_reports": 5,
      "retraction_reason": "CIG gate _get_text_fields() does not scan _beat_description. Character names in _beat_description are metadata only. Live gate sweep: 0/35 E-shots fail. gate_audit.json temporal analysis confirms CHARACTER_NAME_LEAK failures were from 07:52 run; by 08:21 E-shot _beat_action fields were clean and gate passed."
    },
    {
      "id": "OPEN-006",
      "retraction_reason": "Was dependent on OPEN-008. With OPEN-008 retracted, OPEN-006 has no basis."
    }
  ],
  "open_issues": [
    {
      "id": "OPEN-009",
      "classification": "CONFIRMED_BUG",
      "severity": "P1",
      "blocking": false,
      "consecutive_reports": 2,
      "affected_shots": ["008_E01", "008_E02", "008_E03", "008_M03b"],
      "note": "API-path format video_url; files exist at resolved path. Stitch risk."
    },
    {
      "id": "OPEN-004",
      "classification": "CHRONIC-6",
      "severity": "P2",
      "blocking": false,
      "consecutive_reports": 6,
      "fix_effort_minutes": 5
    },
    {
      "id": "OPEN-002",
      "classification": "ARCHITECTURAL_DEBT",
      "severity": "P3",
      "blocking": false,
      "note": "87.8% heuristic. Vision_judge fires inconsistently. Defer until new generation run."
    },
    {
      "id": "OPEN-003",
      "classification": "STALE_DOC",
      "severity": "P4",
      "consecutive_reports": 12
    },
    {
      "id": "OPEN-005",
      "classification": "STALE_DOC",
      "severity": "P4",
      "consecutive_reports": 10
    }
  ],
  "generation_readiness": {
    "scenes_ready_for_video": ["001", "002", "003", "004"],
    "scenes_need_frames_first": ["005", "007", "009", "010", "011", "012", "013"],
    "gate_blocking_any_scene": false,
    "recommended_command": "python3 atlas_universal_runner.py victorian_shadows_ep1 001 002 003 004 --mode lite --videos-only"
  },
  "recommended_next_action": "run_generation_001_002_003_004_videos_only"
}
```

---

**END REPORT**

*ATLAS R13 — Keep-up detection complete. 2 false positives retracted: OPEN-008 (CIG gate never scanned _beat_description — 5 reports of false P0) and OPEN-006 (dependent on OPEN-008). System has 0 P0 blockers. Scenes 001/002/003/004 are ready for video generation. Recommend running --videos-only for those 4 scenes next cycle.*
