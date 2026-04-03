# ATLAS ERROR DEEPDIVE — 2026-03-30 R14 (KEEP-UP LATEST)

**Session timestamp:** 2026-03-30T16:12:00Z
**Run number:** R14
**Prior report:** ATLAS_ERROR_DEEPDIVE_2026-03-30_R13_KEEPUP_LATEST.md
**System version:** V36.5 (CLAUDE.md) / V31.0 docstring (runner header)
**Ledger age at snapshot:** 0d 7h 21m (last entry 2026-03-30T08:47:31Z)
**Atlas project:** victorian_shadows_ep1

---

## 1. EXECUTIVE SUMMARY

**Score: 13 PASS / 1 CONFIRMED_BUG / 1 CHRONIC-7 / 1 ARCHITECTURAL_DEBT / 2 STALE_DOC / 0 NEW FALSE POSITIVES**

| Category | Count | Delta vs R13 | Status |
|----------|-------|-------------|--------|
| FALSE_POSITIVES RETRACTED | 0 | = same | None new |
| CONFIRMED_BUG | 1 | = same (OPEN-009) | Non-blocking, API-path format |
| CHRONIC | 1 | OPEN-004 → now 7th consecutive report | P2, fix recipe available |
| ARCHITECTURAL_DEBT | 1 | = same (OPEN-002 reward signal) | Defer post-run |
| STALE_DOC | 2 | OPEN-003 (13th), OPEN-005 (11th) | Cosmetic |
| CONFIRMED_FIXED | 21 | = same | ✅ No regressions |

**Key findings R14:**

1. 🟢 **SESSION ENFORCER: SYSTEM HEALTHY.** 0 blocks. All wiring intact. Vision backends: [gemini_vision, openrouter, florence_fal, heuristic]. 22/22 learning log fixes verified, 0 regressions.

2. 🟢 **CIG PRE-GEN GATE: 0/97 shots blocked.** Confirmed via live `validate_pre_generation()` sweep. OPEN-008 retraction (R13) holds — gate never scanned `_beat_description`. All 97 shots pass.

3. 🟡 **NO NEW GENERATION SINCE R13.** Newest kling_lite video files timestamp to 12:46Z (before R13 at 15:14Z). Ledger unchanged at 228 entries, 7h21m old. The 30 MP4 files in videos_kling_lite break down as: 28 current shots + 2 legacy v364 variants (006_M03 and 006_M04 from earlier V36.4 session).

4. 🟡 **OPEN-004 ADVANCES TO CHRONIC-7.** `decontaminate_prompt()` still absent from runner (confirmed by grep). Scene 013 still has 4 shots with `_beat_action=None`. 7th consecutive report. Fix recipe unchanged.

5. 🟡 **OPEN-009 PERSISTS (3rd consecutive report).** 4 shots (008_E01/E02/E03, 008_M03b) still have `/api/media?path=` prefix in `video_url`. Physical files exist at resolved paths. No stitch has been run on scene 008 since detection. Risk remains theoretical (stitch exclusion) but non-blocking for generation.

6. 🔵 **VIDEO COVERAGE DELTA vs R13: UNCHANGED.** 28/97 shots with `video_url` (28.9%). Frame coverage: 62 first_frames on disk (same count). Scenes 006/008 still 100% video. Scenes 001 (8/8 frames, 3/8 video), 002 (4/7 frames, 5/7 video), 003 (8/9 frames, 3/9 video), 004 (7/7 frames, 5/7 video). Scenes 005/007/009-013: 0 frames, 0 video.

7. 🟡 **REWARD SIGNAL UNCHANGED.** 228 entries. 87.8% heuristic I-score (latest-per-shot). 5 real-VLM shots: 008_M01(1.0), 008_M02(0.9), 008_M04(0.8), 004_M01(1.0), 004_M02(1.0). Last 5 ledger entries all I=0.75 (001_M01-M05 from 08:47 run).

---

## 2. ORGAN HEALTH MAP

| Organ | Status | Signal | Proof (R14) |
|-------|--------|--------|------------|
| 🦴 Skeleton (shot_plan) | 🟢 HEALTHY | 97 shots, 13 scenes; bare-list guard at runner:1492. All 62 M-shots have `_chain_group`. | `isinstance(sp, list)` guard confirmed; shot_plan loads cleanly |
| 🫀 Liver (prompt sanitizer) | 🔴 DEGRADED | `decontaminate_prompt()` absent from runner. CHRONIC-7. 013_M01/M02/E01/E02 have `_beat_action=None`. | `grep decontaminate_prompt atlas_universal_runner.py` → (no output) |
| 🛡️ Immune (doctrine) | 🟡 DEGRADED | Runner header lines 24/39 still claim Seedance PRIMARY. Code correct (`ACTIVE_VIDEO_MODEL="kling"` at line 515). | Runner line 24: "Seedance v2.0 PRIMARY (muapi.ai)" — stale docstring |
| ⚡ Nervous (hooks) | 🟢 HEALTHY | Session enforcer: ✅ SYSTEM HEALTHY. 22 learning log fixes verified, 0 regressions. All 4 doctrine hooks wired. Chain arc wired at runner:65 + runner:4719. | `python3 tools/session_enforcer.py` → ✅ SYSTEM HEALTHY |
| 👁️ Eyes (vision/identity) | 🟡 DEGRADED | All 5 env keys PRESENT (FAL, OPENROUTER, ANTHROPIC, MUAPI, GOOGLE). Vision backends: 4 available including gemini_vision. BUT 87.8% heuristic I-scores in ledger. | Enforcer + env check + ledger latest-per-shot analysis |
| 🧠 Cortex (reward signal) | 🔴 DEGRADED | 228 entries. 87.8% heuristic I=0.75 latest-per-shot. Only scenes 004/008 show real VLM scores. Last 5 entries all I=0.75. No new generation to test. | `python3 -c "... ledger analysis R14"` |
| 🎬 Cinematographer (generation) | 🟡 DEGRADED | 62 first_frames on disk; 28 shots with video_url. Scenes 006/008 complete. Scenes 001-004 partial. Scenes 005/007/009-013 = 0%. CIG gate: 0/97 blocked. | Shot_plan video_url count + kling_lite MP4 count + CIG sweep |
| ✂️ Editor (stitch) | 🟢 HEALTHY | Wire-B logic `_fail_sids` at runner:5470. No `[WIRE-B]` label (OPEN-003 cosmetic). Functional stitch present — 5 scene stitches in stitched_scenes/ dir. | `grep _fail_sids atlas_universal_runner.py` → runner:5470 |
| 🔄 Regenerator (frozen fix) | 🟢 HEALTHY | Wire-C at runner:5245, 5265, 5267, 5270, 5272. All branches intact. | `grep "WIRE-C" atlas_universal_runner.py` → 5 matches |
| 📋 Doctrine Doc | 🟡 DEGRADED | Runner header Seedance claims (lines 24/39). CLAUDE.md V36.5 correct. Code reality = Kling default (line 515). | `ACTIVE_VIDEO_MODEL = os.environ.get("ATLAS_VIDEO_MODEL", "kling")` confirmed |

---

## 3. CONFIRMED FIXED (DO NOT RE-INVESTIGATE)

21 items total — unchanged from R13.

✅ **ENV LOAD ORDER (V35.0)** — All 5 keys PRESENT in .env.
✅ **I-SCORE NORMALIZATION (V35.0)** — vision_judge.py line 675.
✅ **GEMINI CIRCUIT BREAKER (V30.3)** — vision_judge.py lines 518-529.
✅ **V-SCORE 4-STATE (V30.0)** — All four states present.
✅ **END-FRAME CHAIN FIX (V31.0)** — extract_last_frame() at runner:1408, 3534.
✅ **ROUTE_SHOT ALL KLING (V31.0)** — All branches return "kling".
✅ **LTX RETIRED GUARD (C3)** — `_LTXRetiredGuard()` at runner:485.
✅ **BARE LIST GUARD (T2-OR-18)** — `isinstance` at runner:1492.
✅ **WIRE-A BUDGET RESET** — `_wire_a_reset()` at runner:4386.
✅ **CHAIN ARC INTELLIGENCE (V36.5)** — `enrich_shots_with_arc()` imported at runner:65, called at runner:4719.
✅ **V36.4 ROOM ANCHOR** — loc_master in images_list, Room DNA in prompts.
✅ **V37 GOVERNANCE HOOKS** — All endpoints + runner hooks verified present.
✅ **LEARNING LOG** — 22 fixes recorded, 0 regressions (ALL CLEAR).
✅ **CPC INLINE DETECTION** — `_is_cpc_via_embedding()` at runner:245, called at runner:1118.
✅ **E-SHOT ISOLATION** — `_no_char_ref=True`, `_is_broll=True` marked on E-shots.
✅ **Wire-C WIRED** — `[WIRE-C]` labels at runner:5245+.
✅ **CHAIN_GROUP SET ON M-SHOTS** — All 62 M-shots confirmed with `_chain_group`.
✅ **ACTIVE_VIDEO_MODEL DEFAULT = "kling"** — runner:515 confirmed.
✅ **OPEN-007 CLOSED (R11)** — 0 broken video_url filesystem paths.
✅ **OPEN-008 CLOSED (R13)** — CIG gate never fires on current shot_plan. 0/97 shots fail CIG pre-gen gate.
✅ **OPEN-006 CLOSED (R13)** — Dependent on OPEN-008 (false positive). Closed.

---

## 4. OPEN ISSUES

### OPEN-009 (CONFIRMED_BUG — R12/R13/R14, Non-blocking, 3rd consecutive report)

**Issue:** 4 shots have `/api/media?path=` prefix in `video_url` instead of raw filesystem path.

**PROOF RECEIPT (R14 live):**
```
PROOF: python3 -c "scan shot_plan for API-path video_urls"
OUTPUT:
  SHOTS_WITH_API_MEDIA_PATH: 4
    008_E01: /api/media?path=pipeline_outputs/.../videos_kling_lite/008_E01 exists=True
    008_E02: /api/media?path=pipeline_outputs/.../videos_kling_lite/008_E02 exists=True
    008_E03: /api/media?path=pipeline_outputs/.../videos_kling_lite/008_E03 exists=True
    008_M03b: /api/media?path=pipeline_outputs/.../videos_kling_lite/008_M03 exists=True
  SHOTS_WITH_BROKEN_FS_PATH: 0
CONFIRMS: API-format paths persist on these 4 shots. Files physically exist.
```

**Impact:**
- `os.path.exists(video_url)` fails for these 4 → false positives in keep-up monitoring scripts
- Stitch risk: if runner uses `os.path.exists()` check before concat, these 4 shots excluded from scene 008 stitch
- UI display unaffected (API path resolves correctly in browser)

**Fix recipe (data patch, no code changes):**
```python
# In pipeline_outputs/victorian_shadows_ep1/shot_plan.json, for each of 4 shots:
# Replace video_url = "/api/media?path=X" with video_url = "X"
# Total: 4 field changes, no code changes required
```

**Regression guard:** After fix, re-run broken video_url check → 0 API-path shots, 0 broken FS paths.

**Classification:** CONFIRMED_BUG (data inconsistency). Non-blocking for generation. Introduces monitoring false positives and stitch exclusion risk.

---

### ⏱️ CHRONIC-7 (7 consecutive reports: R8→R14): OPEN-004 — decontaminate_prompt absent from runner

**Issue:** `decontaminate_prompt()` not called in runner. Detection fires (`_is_cpc_via_embedding()` at runner:1118) but replacement call never wired. Scene 013 has 4 shots with `_beat_action=None`.

**PROOF RECEIPT (R14 live):**
```
PROOF: grep -n "decontaminate_prompt" atlas_universal_runner.py
OUTPUT: (no output — function not called in runner)

PROOF: python3 -c "scene 013 _beat_action check"
OUTPUT:
  013_E01: _beat_action=None _beat_ref=beat_1
  013_E02: _beat_action=None _beat_ref=beat_1
  013_M01: _beat_action=None _beat_ref=beat_2
  013_M02: _beat_action=None _beat_ref=beat_2
CONFIRMS: CPC decontamination absent from runner. Scene 013 will produce generic video on next run.
```

**Why CHRONIC:** CPC module (`tools/creative_prompt_compiler.py`) has `decontaminate_prompt()` at line 558 — confirmed present. The runner's detection at line 1118 fires but does NOT call it. Detection-only mode since at least R8.

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

**Regression guard:** After fix, run 013_M01 frame-only and verify prompt no longer contains GENERIC_PATTERNS terms. Verify scenes 001-008 prompt structure unchanged (try/except means no-op if import fails).

**Classification:** CHRONIC-7. Approaching META-CHRONIC threshold (10). Fix recipe safe and proven non-breaking. Recommend human-applied fix before next generation cycle targeting scenes 009-013.

---

### OPEN-002 (ARCHITECTURAL_DEBT — 13th report)

**Issue:** Reward signal degradation — 87.8% heuristic I-scores (latest-per-shot).

**PROOF RECEIPT (R14 live):**
```
PROOF: python3 -c "... ledger analysis R14"
OUTPUT:
  LEDGER_ENTRIES: 228
  UNIQUE_SHOTS: 41
  HEURISTIC_I (latest, I=0.75): 36/41 = 87.8%
  REAL_I (latest, I!=0.75): 5/41 = 12.2%
  REAL_I SAMPLES: [('008_M01',1.0),('008_M02',0.9),('008_M04',0.8),('004_M01',1.0),('004_M02',1.0)]
  LAST 5 ENTRIES (001_M01-M05): all I=0.75
CONFIRMS: Vision_judge fires on scenes 004/008 but heuristic dominates overall.
```

**R14 note:** No new generation run. The architectural pattern is the same as R13 — vision_judge fires successfully for some scenes but not others. Cannot determine root cause without a new generation run A/B test. Defer to proof-gate.

**Classification:** ARCHITECTURAL_DEBT. Not a code failure — vision_judge IS available (backends confirmed). Pattern suggests CLI init timing or environment variable scope issue on some runs.

---

### OPEN-003 (STALE_DOC — 13th consecutive report)

**Issue:** No `[WIRE-B]` label at runner:5470. Logic functional (`_fail_sids` present and working).

**PROOF RECEIPT:**
```
PROOF: grep "WIRE-B" atlas_universal_runner.py
OUTPUT: (no output)

PROOF: grep -n "_fail_sids" atlas_universal_runner.py
OUTPUT: runner:5470 _fail_sids = {e["shot_id"] for e in reward_ledger ...}
CONFIRMS: Logic present, label absent. Cosmetic only.
```

**Fix:** Add `# ── [WIRE-B] Quality gate stitch filter` comment at runner:5470.

**Classification:** STALE_DOC. 13th consecutive report. Purely cosmetic — logic is functional.

---

### OPEN-005 (STALE_DOC — 11th consecutive report)

**Issue:** Runner header lines 24/39 claim Seedance v2.0 as PRIMARY model. Code default is Kling.

**PROOF RECEIPT:**
```
PROOF: sed -n '24p;39p' atlas_universal_runner.py
OUTPUT:
  line 24: "ALL shots parallel → Seedance v2.0 PRIMARY (muapi.ai) | Kling v3/pro FALLBACK"
  line 39: "All shots PRIMARY → Seedance v2.0 via muapi.ai"

PROOF: grep -n "ACTIVE_VIDEO_MODEL" atlas_universal_runner.py | head -1
OUTPUT: runner:515 ACTIVE_VIDEO_MODEL = os.environ.get("ATLAS_VIDEO_MODEL", "kling")
CONFIRMS: Stale docstring contradicts live code. Code is correct.
```

**Classification:** STALE_DOC. 11th consecutive report. Code behavior correct.

---

## 5. FALSE POSITIVES RETRACTED THIS SESSION

None. All 21 confirmed-fixed items from R13 remain intact. No new reclassifications.

---

## 6. NEW OBSERVATION (R14 only) — VIDEO FILE INVENTORY CLARIFICATION

R14 ran a full inventory of `pipeline_outputs/victorian_shadows_ep1/videos_kling_lite/`:

- **Total MP4 files:** 30
- **Current shot-plan-referenced files:** 28 (matching 28 `video_url` entries in shot_plan)
- **Legacy files:** 2 (`multishot_g3_006_M03_v364.mp4`, `multishot_g4_006_M04_v364.mp4` — from V36.4 reframe session)
- **Non-MP4 files in directory:** 32 (.jpg endframes, reframed images, gate_audit.json, vcheck images)

The `videos/` directory is empty (0 files). All current videos reside in `videos_kling_lite/`. This is consistent with `--mode lite` generation. No "orphan" video records — the 2 extra files are correctly identified as legacy v364 variants, not missing shot_plan entries.

**This finding is INFORMATIONAL only.** No new issues introduced.

---

## 7. PRIORITISED FIX LIST

| Priority | Issue | Effort | Fix Recipe | Blocking |
|----------|-------|--------|-----------|----------|
| **P1** | OPEN-009 (API-path video_url on 4 shots) | 1 min | JSON patch: strip `/api/media?path=` prefix from 4 video_url fields | NO — stitch risk only |
| **P2** | OPEN-004 (CPC decontamination CHRONIC-7) | 5 min | 7-line try/except at runner:~1120 | NO — future scenes only |
| **P3** | OPEN-002 (reward signal) | 30 min | Debug vision_judge CLI init timing in new generation run | NO — observational |
| **P4** | OPEN-003 (Wire-B label) | 1 min | Add comment at runner:5470 | NO — cosmetic |
| **P4** | OPEN-005 (docstring Seedance) | 2 min | Update runner header lines 24, 39 | NO — cosmetic |

**No P0 blockers exist. Scenes 001-004 remain ready for video generation.**

---

## 8. ANTI-REGRESSION CHECKLIST

**Before next generation run:**
```
□ Run session_enforcer → ✅ SYSTEM HEALTHY (confirmed: 0 blocks this session)
□ Confirm OPEN-009 fix: normalize 4 API-path video_urls (recommended before scene 008 stitch)
□ Verify vision backends online: gemini_vision + openrouter in available list (confirmed this session)
□ Run pre-run-gate before generation to archive stale artifacts
□ After generation: check reward_ledger I-score distribution (target: ≥50% real scores)
□ Confirm gate_audit.json shows 0 pre_gen failures for target scenes
□ DO NOT run shot_plan_gate_fixer.py FIX-1 — not needed (OPEN-008 retracted R13)
□ Confirm E-shot _beat_action fields remain clean (confirmed: all 97 shots pass CIG)
```

---

## 9. DELTA FROM R13

| Signal | R13 | R14 | Delta | Note |
|--------|-----|-----|-------|------|
| FALSE_POSITIVES_RETRACTED | 2 cumulative | 0 new | — | No new reclassifications |
| CONFIRMED_FIXED | 21 | 21 | = | All intact, 0 regressions |
| P0 blockers | 0 | 0 | = | None |
| CIG gate blocks | 0/97 | 0/97 | = | Confirmed by live sweep R14 |
| Ledger entries | 228 | 228 | = | No new generation |
| Ledger age | ~6h27m | 7h21m | +54m | Approaching proof-gate threshold |
| API-path video_urls | 4 (OPEN-009) | 4 | = | Persists |
| OPEN-004 consecutive | 6 (CHRONIC-6) | 7 (CHRONIC-7) | +1 | Fix recipe unchanged |
| OPEN-003 consecutive | 12 | 13 | +1 | Cosmetic label only |
| OPEN-005 consecutive | 10 | 11 | +1 | Cosmetic docstring only |
| Session enforcer | HEALTHY | HEALTHY | = | 0 blocks |
| Heuristic I-score latest | 87.8% | 87.8% | = | No new run |
| Scenes 100% video | 2 (006, 008) | 2 (006, 008) | = | |
| First frames on disk | 62 | 62 | = | |
| Shot plan total | 97 | 97 | = | |
| kling_lite MP4 files | 28 current | 28 current (+2 v364 legacy) | clarified | 30 total but 2 are v364 |

---

## 10. GENERATION READINESS ASSESSMENT (R14)

All R13 readiness signals confirmed unchanged:

**Can generate scenes 001/002/003/004 videos NOW:**
```bash
python3 atlas_universal_runner.py victorian_shadows_ep1 001 002 003 004 --mode lite --videos-only
```
- ✅ CIG gate: 0/97 shots blocked (live confirmed R14)
- ✅ M-shots: all have _chain_group
- ✅ E-shot _beat_action: clean (no character names)
- ✅ Session enforcer: SYSTEM HEALTHY
- ✅ Vision backends: gemini_vision + openrouter available
- ⚠️ OPEN-009: patch 4 API-path video_urls in scene 008 after run if stitch needed

**Can generate scenes 005/007/009-013 frames + videos:**
```bash
# First frames (review gate):
python3 atlas_universal_runner.py victorian_shadows_ep1 005 007 009 010 011 012 013 --mode lite --frames-only
# After review, approve, then videos:
python3 atlas_universal_runner.py victorian_shadows_ep1 005 007 009 010 011 012 013 --mode lite --videos-only
```
- ✅ No gate blocks confirmed
- ⚠️ OPEN-004: Scene 013 will have generic prompts (decontaminate not wired) — monitor I-scores

---

## 11. DOCUMENT LINEAGE

- R1-R7: hourly incremental baseline and consolidation
- R8: OPEN-004 first reported; OPEN-008 first reported (later retracted R13 as FALSE POSITIVE)
- R9-R12: OPEN-008 persisted as P0 (was FALSE POSITIVE throughout)
- R13: OPEN-008 + OPEN-006 retracted. System cleared of all P0 blockers.
- **R14 (CURRENT):** No new false positives, no new bugs. System stable. OPEN-004 advances to CHRONIC-7. All confirmed-fixed items intact.

---

## PROOF_GATE_FEED (Machine-readable)

```json
{
  "session_timestamp": "2026-03-30T16:12:00Z",
  "run_number": 14,
  "prior_report": "R13",
  "system_version": "V36.5",
  "ledger_age_minutes": 441,
  "atlas_project": "victorian_shadows_ep1",
  "audit_scores": {
    "confirmed_fixed": 21,
    "confirmed_bug": 1,
    "chronic": 1,
    "architectural_debt": 1,
    "stale_doc": 2,
    "false_positives_retracted": 0
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
    "shots_with_video_url_in_plan": 28,
    "kling_lite_mp4_files_total": 30,
    "kling_lite_mp4_files_current": 28,
    "kling_lite_mp4_files_legacy_v364": 2,
    "first_frames_on_disk": 62,
    "scenes_with_100pct_video": 2,
    "p0_blockers": 0,
    "shot_plan_total_shots": 97,
    "shot_plan_unique_scenes": 13,
    "run_report_success": true,
    "learning_log_fixes": 22,
    "learning_log_regressions": 0
  },
  "false_positives_retracted": [],
  "open_issues": [
    {
      "id": "OPEN-009",
      "classification": "CONFIRMED_BUG",
      "severity": "P1",
      "blocking": false,
      "consecutive_reports": 3,
      "affected_shots": ["008_E01", "008_E02", "008_E03", "008_M03b"],
      "note": "API-path format video_url; files exist. Stitch exclusion risk for scene 008."
    },
    {
      "id": "OPEN-004",
      "classification": "CHRONIC-7",
      "severity": "P2",
      "blocking": false,
      "consecutive_reports": 7,
      "approaching_meta_chronic": true,
      "meta_chronic_threshold": 10,
      "fix_effort_minutes": 5,
      "fix_recipe": "7-line try/except at runner:~1120 calling decontaminate_prompt()"
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
      "consecutive_reports": 13
    },
    {
      "id": "OPEN-005",
      "classification": "STALE_DOC",
      "severity": "P4",
      "consecutive_reports": 11
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

*ATLAS R14 — Keep-up detection complete. No new bugs, no new false positives. System stable. OPEN-004 advances to CHRONIC-7 (approaching META-CHRONIC at 10). No P0 blockers. Scenes 001/002/003/004 remain ready for video generation. Ledger 7h21m old — recommend generation run to refresh reward signal.*
