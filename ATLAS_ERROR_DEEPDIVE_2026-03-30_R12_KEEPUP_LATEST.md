# ATLAS ERROR DEEPDIVE — 2026-03-30 R12 (KEEP-UP LATEST)

**Session timestamp:** 2026-03-30T14:55:00Z
**Run number:** R12
**Prior report:** ATLAS_ERROR_DEEPDIVE_2026-03-30_R11_KEEPUP_LATEST.md
**System version:** V36.5 (CLAUDE.md) / V31.0 docstring (runner header)
**Ledger age at snapshot:** 0d 5h 21m (last entry 2026-03-30T08:47:31 — 001/002/004/006/008 last generation)
**Atlas project:** victorian_shadows_ep1

---

## 1. EXECUTIVE SUMMARY

**Score: 13 PASS / 2 CONFIRMED_BUG / 1 CHRONIC (≥5 reports) / 1 ARCHITECTURAL_DEBT / 2 STALE_DOC / 1 STALE_GATE_STATE / 1 NEW_ISSUE**

| Category | Count | Delta vs R11 | Status |
|----------|-------|-------------|--------|
| CONFIRMED_BUG | 2 | = same (OPEN-008 persists) | **BLOCKING 3 SCENES** |
| NEW_ISSUE | 1 | ⬆ NEW (OPEN-009: 008 API-path video_urls) | **NON-BLOCKING but data inconsistency** |
| CHRONIC | 1 | OPEN-004 (5th consecutive report, true CHRONIC threshold met) | P1 fix available |
| ARCHITECTURAL_DEBT | 1 | = same (OPEN-002 reward signal) | Defer post-run |
| STALE_DOC | 2 | = same (OPEN-003, OPEN-005) | Cosmetic |
| STALE_GATE_STATE | 1 | = same (OPEN-006) | Awaits OPEN-008 fix |
| CONFIRMED_FIXED | 19 | = unchanged | ✅ CLEAN |
| FALSE_POSITIVES RETRACTED | 0 | None | — |

**Key findings R12:**

1. 🔴 **OPEN-008 PERSISTS UNCHANGED.** 30 E-shots across all 13 scenes retain character names in `_beat_description`. Scenes 001, 002, 004 blocked for video generation. No fix applied since R11. `shot_plan_gate_fixer.py FIX-1` still not executed. **P0 BLOCKER.**

2. 🔴 **NEW OPEN-009: API-FORMAT VIDEO_URL on 008 E-shots + M03b.** 4 shots (008_E01, 008_E02, 008_E03, 008_M03b) have `video_url = /api/media?path=pipeline_outputs/...` format instead of the standard filesystem path format used by all other shots. Files physically exist at the resolved path; this is a path format inconsistency. Non-blocking for generation, but the `os.path.exists()` check in keep-up scripts will incorrectly report these as broken (false positives). Could affect stitch logic if runner uses same check.

3. 🟡 **OPEN-004 NOW TRUE CHRONIC (5 consecutive reports: R8→R12).** `decontaminate_prompt()` still absent from runner. 013_M01/M02/E01/E02 all have `_beat_action=None`. META-CHRONIC label in R11 was premature (threshold is 10 reports); correct classification is now CHRONIC-5. Fix recipe unchanged (7-line try/except at runner:~1120). **P1.**

4. 🟢 **SESSION ENFORCER: 69 PASS, 0 BLOCK.** Unchanged from R11. All 22 learning log fixes intact, 0 regressions.

5. 🟢 **RUN REPORT: success=True, errors=[].** No pipeline failures since R11.

6. 🟢 **LEDGER: STABLE AT 228 ENTRIES.** No new generation run executed since R11 (5h 21m ago). Heuristic I-score pattern unchanged: 87.8% heuristic latest-per-shot, all 5 recent real scores from scenes 004/008.

7. 🟡 **OPEN-002 (REWARD SIGNAL) NOTE.** Scenes 006 and 008 show the highest real I-score rates (17/30 and 3/4 respectively). Scenes 003, 004 (except latest 5 shots) show heuristic only. Scene-level variance suggests vision_judge fires on some runs but not others — possibly a warm-up latency issue in the CLI process rather than a permanent outage.

8. ℹ️ **RUNNER HEADER / CLAUDE.MD MISMATCH PERSISTS.** Runner header lines 24/39 still reference Seedance v2.0 as PRIMARY. Code is correct (kling default at line 515). Cosmetic only.

---

## 2. ORGAN HEALTH MAP

| Organ | Status | Signal | Proof (R12) |
|-------|--------|--------|------------|
| 🦴 Skeleton (shot_plan) | 🟢 HEALTHY | 97 shots, 13 scenes. Bare-list guard confirmed at runner:1433/1470. Video path inconsistency on 4 shots is data issue, not schema issue. | `isinstance` guard in runner; shot_plan loaded |
| 🫀 Liver (prompt sanitizer) | 🔴 DEGRADED | `decontaminate_prompt()` not called in runner (0 grep hits). CHRONIC-5. 013_M01/M02/E01/E02 `_beat_action=None`. | `grep decontaminate_prompt atlas_universal_runner.py` → empty |
| 🛡️ Immune (doctrine) | 🟡 DEGRADED | Runner header lines 24/39 still claim Seedance as PRIMARY. Code correct. CLAUDE.md V36.5 conflicts with runner docstring. | sed runner:24p = "Seedance v2.0 PRIMARY" |
| ⚡ Nervous (hooks) | 🟢 HEALTHY | Session enforcer 69 PASS, 0 BLOCK. All wiring intact. CIG gates wired at runner:3240. | `python3 tools/session_enforcer.py` → ✅ SYSTEM HEALTHY |
| 👁️ Eyes (vision/identity) | 🟡 DEGRADED | All 5 env keys PRESENT (FAL, OPENROUTER, ANTHROPIC, MUAPI, GOOGLE). Vision backends: [gemini_vision, openrouter, florence_fal, heuristic]. BUT 87.8% latest shots still heuristic. | Enforcer + ledger snapshot R12 |
| 🧠 Cortex (reward signal) | 🔴 DEGRADED | 228 total entries, 87.8% heuristic latest-per-shot. Last 5 ledger entries (001_M01–M05) all I=0.75. Scene 006/008 have real scores; 001/002/003/004 mostly heuristic. | `python3 -c "... ledger analysis R12"` |
| 🎬 Cinematographer (generation) | 🟡 DEGRADED | 62 first_frames, 62 videos_kling_lite. Scenes 006/008 complete; 001/002/004 blocked by CIG gate (OPEN-008). 4 shots have API-path video_url (OPEN-009). | `ls first_frames/ wc -l`, shot_plan analysis |
| ✂️ Editor (stitch) | 🟢 HEALTHY | Wire-B logic at runner:5470 (`_fail_sids`). Functional. Missing [WIRE-B] label only. | `grep -n "fail_sids" atlas_universal_runner.py` |
| 🔄 Regenerator (frozen fix) | 🟢 HEALTHY | Wire-C at runner:5245, 5265, 5267, 5270, 5272, 5274. All branches intact. | `grep "WIRE-C" atlas_universal_runner.py` |
| 📋 Doctrine Doc | 🟡 DEGRADED | Runner header V31.0 Seedance claims. CLAUDE.md V36.5 Kling standard. Code reality = Kling (line 515). Cosmetic conflict. | grep ACTIVE_VIDEO_MODEL → "kling" default |

---

## 3. CONFIRMED FIXED (DO NOT RE-INVESTIGATE)

All 19 items intact as of R12 — identical set from R11, no changes.

✅ **ENV LOAD ORDER (V35.0)** — All 5 keys PRESENT.
✅ **I-SCORE NORMALIZATION (V35.0)** — vision_judge.py line 675.
✅ **GEMINI CIRCUIT BREAKER (V30.3)** — vision_judge.py lines 518-529.
✅ **V-SCORE 4-STATE (V30.0)** — All four states present.
✅ **END-FRAME CHAIN FIX (V31.0)** — extract_last_frame() at runner:1408, 3534.
✅ **ROUTE_SHOT ALL KLING (V31.0)** — All branches return "kling".
✅ **LTX RETIRED GUARD (C3)** — _LTXRetiredGuard() at runner:485.
✅ **BARE LIST GUARD (T2-OR-18)** — isinstance at runner:1433, 1470.
✅ **WIRE-A BUDGET RESET** — _wire_a_reset() at runner:4386.
✅ **CHAIN ARC INTELLIGENCE (V36.5)** — enrich_shots_with_arc() imported, wired at runner:4424+.
✅ **V36.4 ROOM ANCHOR** — loc_master in images_list, Room DNA in prompts (runner:913-976).
✅ **V37 GOVERNANCE HOOKS** — All endpoints + runner hooks verified present.
✅ **LEARNING LOG** — 22 fixes recorded, 0 regressions (ALL CLEAR).
✅ **CPC INLINE DETECTION** — _is_cpc_via_embedding() at runner:245, called at runner:1118.
✅ **E-SHOT ISOLATION** — _no_char_ref=True, _is_broll=True marked on E-shots.
✅ **Wire-C WIRED** — [WIRE-C] labels at runner:5245+.
✅ **CHAIN_GROUP SET ON M-SHOTS** — All 62 M-shots confirmed with _chain_group.
✅ **ACTIVE_VIDEO_MODEL DEFAULT = "kling"** — runner:515 confirmed.
✅ **OPEN-007 CLOSED** — 0 broken video_url filesystem paths (R11 archival resolved).

---

## 4. OPEN ISSUES

### OPEN-008 (CONFIRMED_BUG — Tier 1 BLOCKER, 5th consecutive report)

**Issue:** CIG pre-gen CHARACTER_NAME_LEAK gate blocks video generation for 3 scenes.

**PROOF RECEIPT:**
```
PROOF: python3 -c "... E-shot character name scan ..."
OUTPUT:
  E_SHOTS_WITH_CHAR_NAMES: 30
    001_E01: ['Eleanor', 'Victoria'] — "Eleanor enters the dust-covered Victorian foyer..."
    001_E02: ['Eleanor', 'Victoria'] — "Eleanor enters the dust-covered Victorian foyer..."
    001_E03: ['Thomas'] — "Thomas follows reluctantly, touching the banister..."
    002_E01: ['Nadia'] — "Nadia photographs floor-to-ceiling bookshelves..."
    002_E02: ['Nadia'] — "Nadia photographs floor-to-ceiling bookshelves..."
    002_E03: ['Nadia'] — "A folded letter falls from a book — Nadia reads it..."
    ... and 24 more (across all 13 scenes)
CONFIRMS: 30 E-shots still have character names in _beat_description. Gate fires on scenes 001/002/004 blocking video generation.
```

**Root cause:** `_beat_description` was populated from story bible beats which contain character names. `chain_intelligence_gate.validate_pre_generation()` CHARACTER_NAME_LEAK check fires when E-shot `_beat_description` contains known character names. Gate sets `_cig_pre_blocked=True`. Runner at line 3273 skips video generation for blocked groups.

**Affected scenes:** 001, 002, 004 (video blocked). Scenes 003, 005-013 have E-shots with character names but may not trigger CIG depending on gate scope.

**Fix recipe (shot_plan_gate_fixer.py FIX-1 — exists, not executed):**
```
1. python3 tools/shot_plan_gate_fixer.py --project victorian_shadows_ep1 --fix CHARACTER_NAME_LEAK
2. Verify: python3 -c "... E-shot scan..." → E_SHOTS_WITH_CHAR_NAMES: 0
3. python3 atlas_universal_runner.py victorian_shadows_ep1 001 002 004 --mode lite --videos-only
```

**Regression guard:** E-shot _beat_description rewrites must NOT alter M-shot descriptions. After fix, grep for character names in M-shot _beat_description to confirm M-shots are untouched.

**Classification:** CONFIRMED_BUG (data remediation needed). Fix tool exists, not yet run.

**Status:** OPEN — P0 blocker. Awaiting execution.

---

### OPEN-009 (CONFIRMED_BUG — NEW R12, Non-blocking)

**Issue:** 4 shots (008_E01, 008_E02, 008_E03, 008_M03b) have API-format `video_url` instead of filesystem paths.

**PROOF RECEIPT:**
```
PROOF: python3 -c "... video_url format analysis ..."
OUTPUT:
  SHOTS_WITH_API_MEDIA_PATH: 4 (008_E01, 008_E02, 008_E03, 008_M03b)
    All 4 resolve to: /api/media?path=pipeline_outputs/victorian_shadows_ep1/videos_kling_lite/{shot}.mp4
  Filesystem verification: ALL 4 files EXIST at resolved path.
  SHOTS_WITH_BROKEN_FS_PATH: 0
CONFIRMS: Files exist. Path format is API route, not filesystem path. os.path.exists() check fails on these 4 shots.
```

**Root cause:** During an earlier generation run (likely before R11 archival), these 4 shots had their `video_url` written via the UI/API path rather than the runner's standard filesystem path. All other 24 video_url shots use `pipeline_outputs/...` filesystem format.

**Impact:**
- `os.path.exists()` check incorrectly flags these as broken → false positives in keep-up scripts
- If runner stitch logic calls `os.path.exists(video_url)` before adding to concat list, these 4 shots may be excluded from scene 008 stitch
- UI media endpoint should resolve the API path format correctly, so UI display is unaffected

**Fix recipe (data remediation — shot_plan.json edit only):**
```python
# For each of 4 shots, convert:
# "/api/media?path=pipeline_outputs/victorian_shadows_ep1/videos_kling_lite/008_E01.mp4"
# → "pipeline_outputs/victorian_shadows_ep1/videos_kling_lite/008_E01.mp4"
```

**Regression guard:** After fix, re-run keep-up broken video_url check → 0 broken.

**Classification:** CONFIRMED_BUG (data inconsistency). Low severity — files exist. Affects stitch reliability and keep-up reporting accuracy.

**Status:** OPEN — NEW R12. Non-blocking for generation, but introduces false positives in health checks.

---

### ⏱️ CHRONIC-5 (5 reports): OPEN-004 — decontaminate_prompt absent from runner

**Issue:** `decontaminate_prompt()` not called in runner. 013_M01/M02/E01/E02 have `_beat_action=None`.

**Consecutive reports:** R8, R9, R10, R11, R12 (5 reports). **CHRONIC threshold met (5–9 range).**

*Note: R11 prematurely labeled this META-CHRONIC-1. Correct classification per task criteria is CHRONIC-5 (5–9 consecutive reports). META-CHRONIC requires 10+ reports.*

**PROOF RECEIPT:**
```
PROOF: grep -n "decontaminate_prompt" atlas_universal_runner.py
OUTPUT: (no output — function not called in runner)

PROOF: python3 -c "scene 013 shots _beat_action check"
OUTPUT:
  SCENE_013_SHOTS: 4
    013_E01: _beat_action=None _beat_ref=beat_1
    013_E02: _beat_action=None _beat_ref=beat_1
    013_M01: _beat_action=None _beat_ref=beat_2
    013_M02: _beat_action=None _beat_ref=beat_2
CONFIRMS: CPC decontamination still absent. 013 shots will produce generic video.
```

**Why CHRONIC:** CPC detection fires (runner:1118) but decontamination never runs. CPC inline detection at runner:245/1118 only identifies generic prompts — it does not replace them. Replacement requires the separate `decontaminate_prompt()` call which is missing.

**Fix recipe (7 lines, non-breaking):**
```python
# At runner line ~1120, after _is_cpc_via_embedding() detection:
if clean_choreo and _is_cpc_via_embedding(clean_choreo):
    try:
        from tools.creative_prompt_compiler import decontaminate_prompt
        clean_choreo = decontaminate_prompt(clean_choreo, shot.get("_emotional_state", ""))
    except ImportError:
        pass  # Fallback: detection-only mode, no regression
```

**Regression guard:** After fix, run 013_M01 frame-only and verify prompt no longer contains GENERIC_PATTERNS blacklist terms. Confirm existing scenes 001-008 show no change in prompt structure.

**Classification:** CHRONIC-5 — Persistent degraded state. Fix recipe is safe (try/except wrapper, non-blocking).

**Status:** ESCALATED — 5 consecutive reports. Recommend human review of fix recipe before next generation cycle.

---

### OPEN-006 (STALE_GATE_STATE-7)

**Issue:** gate_audit.json timing artifact with ORPHAN_SHOT entries on M-shots + CHARACTER_NAME_LEAK entries.

**Proof receipt R12:** No new gate_audit.json entries since R11. Gate audit is an observation log only (non-blocking).

**Status:** OPEN — Awaits OPEN-008 fix. Will auto-resolve after E-shot name remediation.

---

### OPEN-003 (STALE_DOC-11)

**Issue:** Wire-B label missing from runner logic at line 5470.

**Proof receipt R12:** `grep "WIRE-B" atlas_universal_runner.py` → (no output). Code functional. Label cosmetic.

**Fix recipe:** Add `# ── [WIRE-B] Quality gate stitch filter` comment at runner:5470.

**Status:** STALE_DOC — Low priority. 11th consecutive report.

---

### OPEN-005 (STALE_DOC-9)

**Issue:** Runner header lines 24/39 still claim Seedance v2.0 as PRIMARY model.

**Proof receipt R12:**
```
Runner line 24: "ALL shots parallel → Seedance v2.0 PRIMARY (muapi.ai) | Kling v3/pro FALLBACK"
Runner line 39: "All shots PRIMARY → Seedance v2.0 via muapi.ai"
Code reality: ACTIVE_VIDEO_MODEL = os.environ.get("ATLAS_VIDEO_MODEL", "kling") [line 515]
```

**Status:** STALE_DOC — Cosmetic. Non-blocking. 9th consecutive report.

---

### OPEN-002 (ARCHITECTURAL_DEBT-11)

**Issue:** Reward signal degradation — 87.8% heuristic I-scores latest-per-shot.

**Proof receipt R12:**
```
LATEST_PER_SHOT: 41 unique shots
REAL_I (latest): 5/41 = 12.2% — all from scenes 004/008
HEURISTIC_I (latest): 36/41 = 87.8%
Scene-level: 006 has 17/30 real entries, 008 has 3/4 real. Scenes 001/002/003 nearly 100% heuristic.
```

**R12 insight:** Scene 006 (17/30 real) and 008 (3/4 real) show vision_judge does fire. Scenes 001/002/003/004 are predominantly heuristic. The pattern suggests vision_judge fires correctly on some generation runs and not others — consistent with a warm-up/initialization timing issue rather than a permanent backend failure. All 5 vision backends reported available by session_enforcer.

**Classification:** ARCHITECTURAL_DEBT — Not urgent. Defer until after OPEN-008 fix and new generation run for 001/002/004.

**Status:** OPEN — Monitoring. Expect improvement after fresh generation of scenes 001/002/004.

---

## 5. FALSE POSITIVES RETRACTED THIS SESSION

**None new this session.**

**Note:** The 4 "broken video_url" shots identified in initial snapshot (`os.path.exists()` returning False) are NOT broken — they use API path format. Files exist at resolved paths. These are a NEW pattern (OPEN-009), not a regression of OPEN-007. OPEN-007 (R11 closed) remains correctly closed: filesystem-path video_urls are all intact.

---

## 6. PRIORITISED FIX LIST

| Priority | Issue | Effort | Fix Recipe | Blocking |
|----------|-------|--------|-----------|----------|
| **P0** | OPEN-008 (CIG CHARACTER_NAME_LEAK) | 2 min | `python3 tools/shot_plan_gate_fixer.py --fix CHARACTER_NAME_LEAK` | **YES — 3 scenes blocked** |
| **P1** | OPEN-009 (API-path video_url on 4 shots) | 1 min | sed/json replace `/api/media?path=` prefix in shot_plan.json | NO — cosmetic/stitch risk |
| **P2** | OPEN-004 (CPC decontamination CHRONIC-5) | 5 min | 7-line try/except at runner:~1120 | NO — future scenes |
| **P3** | OPEN-002 (reward signal degradation) | 30 min | Debug vision_judge CLI init + calibrate gates | NO — observational |
| **P4** | OPEN-003 (Wire-B label) | 1 min | Add comment at runner:5470 | NO — cosmetic |
| **P4** | OPEN-005 (docstring Seedance) | 2 min | Update runner header lines 24, 39 | NO — cosmetic |

---

## 7. ANTI-REGRESSION CHECKLIST

**Before next generation run:**
```
□ Execute OPEN-008 fix: shot_plan_gate_fixer.py FIX-1 (CHARACTER_NAME_LEAK strip)
□ Verify E-shot scan returns 0 character name matches
□ Execute OPEN-009 fix: normalize 4 API-path video_urls to filesystem format
□ Run session_enforcer → ✅ SYSTEM HEALTHY (target 69 PASS, 0 BLOCK)
□ Verify vision backends online: gemini_vision + openrouter in available list
□ Run pre-run-gate before generation to archive stale artifacts
□ After generation: check reward_ledger I-score distribution (target: ≥50% real scores)
□ After generation: verify gate_audit.json shows 0 CHARACTER_NAME_LEAK entries
□ Confirm 013_M01/M02 have _beat_action populated after fix (not None)
```

---

## 8. DELTA FROM R11

| Signal | R11 | R12 | Delta | Note |
|--------|-----|-----|-------|------|
| Ledger entries | 228 | 228 | = unchanged | No new generation run |
| Broken FS video_urls | 0 | 0 | = unchanged | OPEN-007 stays closed |
| API-path video_urls | 0 (not checked) | 4 | ⬆ NEW OPEN-009 | Files exist; format inconsistency |
| E-shots with char names | 30 | 30 | = unchanged | OPEN-008 fix still not executed |
| OPEN-004 consecutive | 4 (META-CHRONIC label) | 5 (CHRONIC-5) | reclassified | R11 premature escalation corrected |
| Session enforcer PASS | 69 | 69 | = unchanged | All systems healthy |
| Heuristic I-score latest | 87.8% | 87.8% | = unchanged | No improvement without new run |
| Scenes 100% video | 2 (006, 008) | 2 (006, 008) | = unchanged | Pending OPEN-008 fix |
| Shot plan total | 97 | 97 | = unchanged | No new shots added |

---

## 9. DOCUMENT LINEAGE

**Report chain:**
- R1 (2026-03-30 initial baseline)
- R2–R7 (hourly incremental updates, issues consolidated)
- R8 (OPEN-004 first reported)
- R9 (OPEN-004 persists, OPEN-007 NEW)
- R10 (2 CONFIRMED_BUG, OPEN-004 → CHRONIC-9 in prior labeling)
- R11 (OPEN-007 → ✅ CLOSED, OPEN-004 → META-CHRONIC-1 [premature label])
- **R12 (CURRENT)** — NEW OPEN-009 (API-path video_urls), OPEN-004 correctly reclassified CHRONIC-5

**Session learnings integrated:** V36.5 Chain Arc (present), V36.4 Room DNA (present), V37 Governance (present), learning log 22/22 (verified), LTX guard at runner:485 (verified).

**Test coverage:** session_enforcer 69/69 PASS, 0 regressions.

---

## PROOF_GATE_FEED (Machine-readable)

```json
{
  "session_timestamp": "2026-03-30T14:55:00Z",
  "run_number": 12,
  "prior_report": "R11",
  "system_version": "V36.5",
  "ledger_age_minutes": 321,
  "atlas_project": "victorian_shadows_ep1",
  "audit_scores": {
    "confirmed_fixed": 19,
    "confirmed_bug": 2,
    "new_issue": 1,
    "chronic": 1,
    "architectural_debt": 1,
    "stale_doc": 2,
    "stale_gate_state": 1,
    "false_positives_retracted": 0
  },
  "key_signals": {
    "broken_fs_video_urls": 0,
    "api_path_video_urls": 4,
    "e_shots_with_char_names": 30,
    "session_enforcer_status": "HEALTHY",
    "session_enforcer_pass_count": 69,
    "session_enforcer_block_count": 0,
    "reward_ledger_heuristic_pct_latest": 87.8,
    "reward_ledger_total_entries": 228,
    "reward_ledger_unique_shots": 41,
    "scenes_with_100pct_video": 2,
    "blocked_scenes": ["001", "002", "004"],
    "shot_plan_total_shots": 97,
    "shot_plan_unique_scenes": 13
  },
  "open_issues": [
    {
      "id": "OPEN-008",
      "classification": "CONFIRMED_BUG",
      "severity": "P0",
      "blocking": true,
      "consecutive_reports": 5,
      "fix_effort_minutes": 2,
      "affected_scenes": ["001", "002", "004"],
      "fix_recipe": "python3 tools/shot_plan_gate_fixer.py --project victorian_shadows_ep1 --fix CHARACTER_NAME_LEAK"
    },
    {
      "id": "OPEN-009",
      "classification": "CONFIRMED_BUG",
      "severity": "P1",
      "blocking": false,
      "consecutive_reports": 1,
      "fix_effort_minutes": 1,
      "affected_shots": ["008_E01", "008_E02", "008_E03", "008_M03b"],
      "note": "API-path format video_url; files exist at resolved path"
    },
    {
      "id": "OPEN-004",
      "classification": "CHRONIC-5",
      "severity": "P2",
      "blocking": false,
      "consecutive_reports": 5,
      "fix_effort_minutes": 5,
      "note": "R11 premature META-CHRONIC label corrected to CHRONIC-5 (threshold is 10 for META-CHRONIC)"
    },
    {
      "id": "OPEN-002",
      "classification": "ARCHITECTURAL_DEBT",
      "severity": "P3",
      "blocking": false,
      "fix_effort_minutes": 30,
      "note": "Scene 006/008 show real VLM scores; 001/002/003 heuristic. Likely CLI warm-up timing issue."
    },
    {
      "id": "OPEN-003",
      "classification": "STALE_DOC",
      "severity": "P4",
      "blocking": false,
      "consecutive_reports": 11,
      "fix_effort_minutes": 1
    },
    {
      "id": "OPEN-005",
      "classification": "STALE_DOC",
      "severity": "P4",
      "blocking": false,
      "consecutive_reports": 9,
      "fix_effort_minutes": 2
    }
  ],
  "reclassifications": [
    {
      "id": "OPEN-004",
      "from": "META-CHRONIC-1",
      "to": "CHRONIC-5",
      "reason": "R11 applied META-CHRONIC label at 4 reports; task criteria requires 10+ for META-CHRONIC. Correct class at 5 reports is CHRONIC."
    }
  ],
  "recommended_next_action": "run_open008_fix_then_generation",
  "recommended_scenes_for_next_run": ["001", "002", "004"],
  "run_command": "python3 atlas_universal_runner.py victorian_shadows_ep1 001 002 004 --mode lite --videos-only"
}
```

---

**END REPORT**

*ATLAS R12 — Keep-up detection complete. System DEGRADED but stable. OPEN-008 blocks 3 scenes (P0 fix recipe available, not executed). NEW OPEN-009 found (4 API-path video_urls, files exist). OPEN-004 correctly reclassified CHRONIC-5. Recommend P0 fix execution before next generation cycle.*
