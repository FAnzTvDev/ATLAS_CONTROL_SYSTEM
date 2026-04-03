# ATLAS ERROR DEEPDIVE — 2026-03-30 R5 (KEEP-UP LATEST)

**Session timestamp:** 2026-03-30T07:15:00Z
**Run number:** R5
**Prior report:** ATLAS_ERROR_DEEPDIVE_2026-03-30_R4_KEEPUP_LATEST.md
**System version:** V36.5 (CLAUDE.md) / V31.0 docstring (runner header)
**Ledger age at snapshot:** 0d 12h 25m (last entry: 2026-03-29T18:43:06 — contaminated; last real: 2026-03-29T17:54:06)
**Atlas project:** victorian_shadows_ep1

---

## 1. EXECUTIVE SUMMARY

**Score: 12 PASS / 1 CONFIRMED_BUG / 1 ARCHITECTURAL_DEBT / 2 STALE_DOC / 1 STALE_GATE_STATE / 1 NEW_CONFIRMED_FIXED**

| Category | Count | Delta vs R4 |
|----------|-------|-------------|
| CONFIRMED_BUG | 1 | = same (OPEN-004 CHRONIC-4) |
| STALE_GATE_STATE | 1 | = same (OPEN-006) |
| ARCHITECTURAL_DEBT | 1 | = same (OPEN-002) |
| STALE_DOC | 2 | = same (OPEN-003 STALE_DOC-5; OPEN-005 STALE_DOC-3) |
| CONFIRMED_FIXED | 19 | +3 (VVO wired, VVO enforcer checks pass, pipeline_stress_test calibration data generated) |
| FALSE_POSITIVES RETRACTED | 0 | None this session |
| NEW ISSUES | 0 | None |

**Key findings this session (R5):**

1. 🟢 **RUNNER UPDATED AFTER R4 (06:44 UTC) — VVO NOW WIRED:**
   The runner was modified at 2026-03-30T06:44Z, 32 minutes AFTER R4 was written (06:12Z). The runner grew by +25,980 bytes. The primary change: `video_vision_oversight` (`_vvo_run`) is now fully wired at runner line 3301. Session enforcer confirms 69 PASS (up from 47 in prior R3/R4 snapshots) including 3 new VVO-specific passes. This is NOT a retroactive fix — it happened between R4 and R5, and R4 could not have detected it.

2. 🟢 **VISION ASSEMBLY LINE RUNSHEET — CALIBRATION DATA AVAILABLE:**
   `VISION_ASSEMBLY_LINE_RUNSHEET.md` (35KB) generated from `pipeline_stress_test.py` run ($2.275 / $5.00 budget). 13 clips scored across D1-D20 vision doctrine. Key finding: arc_position framing override is the #1 failure axis (only 3/13 D8 passed). First-pass acceptable rate: 46% (6/13 A/B/C). This calibration data is now available for scene 1-4 generation sessions. Standalone tool — NOT wired into main runner.

3. 🟢 **`vision_doctrine_prompts.py` NEW MODULE (92KB) — BUILT, NOT WIRED INTO RUNNER:**
   Used by `pipeline_stress_test.py` and `generate_fanz_video_promos.py` as standalone calibration/promo tools. Not referenced in `atlas_universal_runner.py` or `orchestrator_server.py`. This is appropriate — it's a test/promo tool, not part of the Victorian Shadows production path.

4. 🔴 **OPEN-004 CHRONIC (4 reports):** `decontaminate_prompt` still absent from runner. `013_M01/M02` still have `_beat_action=None`. Fourth consecutive report. Severity LOW-MEDIUM.

5. 🟡 **OPEN-006 UNCHANGED:** gate_audit.json stale + 006 ledger contamination. Ledger age now 12h 25m. No new ledger entries. Clears on next `--videos-only` scene 006.

6. 🟢 **All other confirmed-fixed items intact.** Learning log: 0 regressions. .env: 5 keys PRESENT. 59 frames, 29 videos_kling_lite mp4s unchanged.

---

## 2. ORGAN HEALTH MAP

| Organ | Status | Signal | Proof (this session R5) |
|-------|--------|--------|-------------------------|
| 🦴 Skeleton (shot_plan) | 🟢 HEALTHY | isinstance guard at runner:1433/1470. 62/62 M-shots `_chain_group` truthy. 35/35 E-shots isolated. | Python live check R5 |
| 🫀 Liver (prompt sanitizer) | 🟡 DEGRADED (partial) | `_is_cpc_via_embedding` detection wired (runner:245/1115). `decontaminate_prompt` absent (replacement gap). 013_M01/M02 `_beat_action=None`. | grep + python R5 |
| 🛡️ Immune (doctrine) | 🟡 DEGRADED | Runner docstring V31.0 + Seedance PRIMARY (lines 24/39). CLAUDE.md = V36.5. Code correct. | grep R5 |
| ⚡ Nervous (hooks) | 🟢 HEALTHY | Session enforcer: ✅ SYSTEM HEALTHY. **69 PASS** (up from 47). All 4 vision backends available. 22 learning log fixes. VVO wired. | `python3 tools/session_enforcer.py` R5 |
| 👁️ Eyes (vision/identity) | 🟢 HEALTHY | Backends: gemini_vision, openrouter, florence_fal, heuristic. All 5 env keys PRESENT. VVO tier confirmed: CRITICAL + VIDEO. | session_enforcer R5 |
| 🧠 Cortex (reward signal) | 🟡 DEGRADED | 23/33 shots I=0.75 (70% heuristic). Last 4 entries contaminated V=0.5 (OPEN-006). Last real entry: 2026-03-29T17:54:06. | ledger R5 |
| 🎬 Cinematographer (generation) | 🟢 HEALTHY | atlas_run_report.json success=True errors=[]. 29 .mp4s in videos_kling_lite. 59 first_frames. VVO now fires after video gen (wired 06:44Z). | ls + run_report + runner R5 |
| ✂️ Editor (stitch) | 🟢 HEALTHY | Wire-B logic at runner:5339 via `_fail_sids/_blocked_sids`. Header reference line 9. "[WIRE-B]" label absent at line 5339 (OPEN-005 ongoing). | grep confirmed R5 |
| 🔄 Regenerator (frozen fix) | 🟢 HEALTHY | Wire-C at runner:5090 `[WIRE-C]` (6 occurrences). `extract_last_frame` at runner:1408/3534/3748. | grep confirmed R5 |
| 📋 Doctrine Doc | 🟡 DEGRADED | Runner header V31.0 / Seedance PRIMARY (lines 24/39). CLAUDE.md V36.5. Wire-B label absent at line 5339. | grep R5 |

---

## 3. CONFIRMED FIXED (DO NOT RE-INVESTIGATE)

All 19 items confirmed. 3 new additions this session (R5).

✅ **ENV LOAD ORDER (V35.0)** — All 5 keys PRESENT before vision_judge import. Confirmed R1→R5.

✅ **I-SCORE NORMALIZATION (V35.0)** — vision_judge.py line 675. Confirmed R1→R5.

✅ **GEMINI CIRCUIT BREAKER (V30.3)** — vision_judge.py lines 518-529. Confirmed R1→R5.

✅ **V-SCORE 4-STATE (V30.0)** — All four states present. Confirmed R1→R5.

✅ **END-FRAME CHAIN FIX (V31.0)** — `extract_last_frame()` called after each group (runner:1408, 3534). Confirmed R1→R5.

✅ **ROUTE_SHOT ALL KLING (V31.0)** — All branches return "kling". ACTIVE_VIDEO_MODEL="kling" at line 493. Confirmed R1→R5.

✅ **LTX RETIRED GUARD (C3)** — `_LTXRetiredGuard()` at line 463. Confirmed R1→R5.

✅ **BARE LIST GUARD (T2-OR-18)** — isinstance guard at runner:1433, 1470. Confirmed R1→R5.

✅ **WIRE-A BUDGET RESET** — `_wire_a_reset(scene_id)` at runner:4386. `_WIRE_A_MAX_REGENS_PER_SCENE=2`. Confirmed R1→R5.

✅ **CHAIN ARC INTELLIGENCE (V36.5)** — `enrich_shots_with_arc()` at runner:4566 (import at line 65). All 62/62 M-shots have `_arc_position`. Confirmed R1→R5.

✅ **V36.4 ROOM ANCHOR** — Room DNA + location_master_path wired. Confirmed R1→R5.

✅ **V37 GOVERNANCE HOOKS** — 2 HTML v37GovernanceBar refs, 9 v37RefreshAll refs, 7 api/v37 endpoints, 4 runner refs. Confirmed R1→R5.

✅ **LEARNING LOG** — 22 fixes, 0 regressions (ALL CLEAR). Confirmed R1→R5.

✅ **CPC INLINE DETECTION** — `_is_cpc_via_embedding()` at runner:245, called at runner:1115. Confirmed R2→R5.

✅ **E-SHOT ISOLATION** — 35/35 E-shots have `_no_char_ref` or `_is_broll` flag. Confirmed R3→R5.

✅ **Wire-C WIRED** — `[WIRE-C]` label at runner:5090 (6 occurrences). Confirmed R3→R5.

✅ **`_chain_group` SET ON ALL 62 M-SHOTS** — 62/62 M-shots have `_chain_group` truthy. Gate PASSES live. Confirmed R4→R5.

✅ **VVO (VIDEO VISION OVERSIGHT) WIRED — NEW R5:**
`tools/video_vision_oversight.py` (77KB) fully wired into production path.
- Runner: `_vvo_run` imported at runner:312–324 (NON-BLOCKING fallback); called at runner:3301 AFTER chain_gate, BEFORE ARJ.
- Session enforcer: 3 new VVO PASS checks (file exists, two-tier models present, `_vvo_run` called).
- Total enforcer passes: **69** (up from 47 in R3/R4 baseline).
- Checks: CHARACTER_BLEED, FROZEN_FRAME, DIALOGUE_SYNC. Non-blocking — any exception proceeds cleanly.
- This was BUILT but not reflected in R4 because runner was updated at 06:44Z, after R4 was written at 06:12Z.

✅ **PIPELINE STRESS TEST CALIBRATION DATA — NEW R5:**
`pipeline_stress_test.py` (74KB) run produced `VISION_ASSEMBLY_LINE_RUNSHEET.md` (35KB).
- 13 clips tested, $2.275 spent, D1-D20 scored via Gemini 2.5-flash.
- First-pass acceptable (A/B/C): 6/13 = 46%.
- Hard failures (D/F): 7/13 = 54%.
- #1 failure axis: arc_position framing override (D8 passed: 3/13 = 23%).
- Calibration rule confirmed: arc position MUST inject framing instruction overrides ("WIDE SHOT", "MEDIUM CLOSE-UP"), not just atmosphere text.
- Standing as calibration baseline for Victorian Shadows scenes 1-4.
- Standalone tool — NOT wired into `atlas_universal_runner.py` or `orchestrator_server.py`.

---

## 4. OPEN ISSUES

---

### ⏱️ CHRONIC (4 reports) — OPEN-004: CPC decontaminate_prompt() Not Called — Description Fallback

**Classification:** CHRONIC (4 consecutive reports: R2, R3, R4, R5)
**Severity:** LOW-MEDIUM — `013_M01/M02` have `_beat_action=None` (confirmed R5); CPC detection fires but replacement uses raw `description` field, not a CPC-rewritten directive.

**PROOF RECEIPT (this session — R5):**
```
PROOF: grep -n "decontaminate_prompt" atlas_universal_runner.py
OUTPUT: (no output) — function not present in runner

PROOF: python3 -c "...check 013_M01/M02 _beat_action..."
OUTPUT: 013_M01: _beat_action=None _arc_position='PIVOT'
        013_M02: _beat_action=None _arc_position='RESOLVE'
        Total _beat_action=None M-shots: 2

CONFIRMS: T2-CPC-6 requires CPC replacement not raw description.
          Current: detects generic content (correct), falls back to description (wrong).
          2 shots confirmed affected.
```

**FIX RECIPE (minimal, non-breaking):**
```python
# atlas_universal_runner.py ~line 1117 — change from:
    base = s.get("description", "")
# to:
    try:
        from tools.creative_prompt_compiler import decontaminate_prompt as _decon
        _emotion = s.get("_emotional_state") or s.get("_beat_atmosphere", "neutral")
        _char = (s.get("characters") or [""])[0]
        base = _decon(clean_choreo, _char, _emotion, s.get("description",""))
    except Exception:
        base = s.get("description", "")   # safe fallback unchanged
```

**REGRESSION GUARD:** Does NOT touch `_beat_action` primary path (~line 1113). `try/except` ensures non-blocking if CPC import fails. Does NOT affect `_is_cpc_via_embedding` detection at line 1115.

---

### 🟡 STALE_GATE_STATE (2 reports) — OPEN-006: gate_audit.json Stale + 006 Ledger Contamination

**Classification:** STALE_GATE_STATE (2 consecutive reports: R4, R5)
**Severity:** LOW — not a code bug. System production-ready. Ledger self-heals on next --videos-only.

**PROOF RECEIPT (R5):**
```
PROOF: Last 6 ledger entries
OUTPUT:
  006_M03 ts=2026-03-29T17:54:06 I=0.75 V=0.85 C=0.85  ← valid
  006_M04 ts=2026-03-29T17:54:06 I=0.80  V=0.85 C=0.85  ← valid
  006_M01 ts=2026-03-29T18:43:06 I=0.75 V=0.5  C=0.7   ← contaminated
  006_M02 ts=2026-03-29T18:43:06 I=0.75 V=0.5  C=0.7   ← contaminated
  006_M03 ts=2026-03-29T18:43:06 I=0.75 V=0.5  C=0.7   ← contaminated
  006_M04 ts=2026-03-29T18:43:06 I=0.75 V=0.5  C=0.7   ← contaminated

PROOF: Total entries=175, unique shots=33 — no new entries since R4
CONFIRMS: Ledger contamination unchanged. No new generation activity.
```

**RESOLUTION (operational — no code fix):**
```bash
python3 atlas_universal_runner.py victorian_shadows_ep1 006 --mode lite --videos-only
```

---

### 🟡 ARCHITECTURAL_DEBT (5 reports) — OPEN-002: 9 Un-Normalized I>1.0 Historical Ledger Entries

**Classification:** ARCHITECTURAL_DEBT (5 consecutive: R1→R5)
**Severity:** LOW — latest-per-shot I>1.0: **0** (clean). Raw historical only.

**PROOF RECEIPT (R5):**
```
PROOF: python3 -c "bad=[e for e in lines if max(e.get('I_score',0),e.get('I',0))>1.0]; print(len(bad))"
OUTPUT: 9 entries with I in [3.5, 4.0, 5.0] — all timestamps 2026-03-24T17-18:xx
        latest-per-shot I>1.0: 0 (clean)
```

---

### 🟡 STALE_DOC (5 reports) — OPEN-003: Runner Docstring Declares Seedance as PRIMARY

**Classification:** STALE_DOC (5 consecutive: R1→R5)
**Severity:** LOW — code correct (ACTIVE_VIDEO_MODEL="kling" at line 493). Comment wrong.

**PROOF RECEIPT (R5):**
```
PROOF: lines[23] and lines[38]
OUTPUT:
  Line 24: P2. Videos: ALL shots parallel → Seedance v2.0 PRIMARY (muapi.ai) | Kling v3/pro FALLBACK
  Line 39: All shots PRIMARY → Seedance v2.0 via muapi.ai (...)
```

---

### 🟡 STALE_DOC (3 reports) — OPEN-005: Wire-B Logic Unlabelled at Stitch Quality Gate

**Classification:** STALE_DOC (3 consecutive: R3→R5)
**Severity:** VERY LOW — logic correct at runner:5339. Header line 9 references "Wire B". Label absent from implementation.

**PROOF RECEIPT (R5):**
```
PROOF: grep -n "WIRE-B" atlas_universal_runner.py
OUTPUT: (no output at line 5339)
        Line 9: Wire B (2026-03-20): QUALITY GATE — FAIL/FROZEN shots blocked from stitch

CONFIRMS: Implementation functional; label absent. Probe scripts checking "[WIRE-B]" return 0.
```

---

## 5. FALSE POSITIVES RETRACTED THIS SESSION

None. No new reclassifications.

---

## 6. PRIORITISED FIX LIST

Only CONFIRMED_BUG and CHRONIC issues listed.

| Priority | Issue | Class | Impact | Fix Size |
|----------|-------|-------|--------|----------|
| 1 | OPEN-004: CPC decontaminate_prompt not called | CHRONIC (4) | LOW-MEDIUM — 2 shots affected; grows if enrichment gaps expand | 7 lines in runner (try/except safe) |

**Operational (no code fix needed):**
- OPEN-006: Run `python3 atlas_universal_runner.py victorian_shadows_ep1 006 --mode lite --videos-only` — clears stale gate_audit + ledger contamination.

**Defer:**
- OPEN-003 (STALE_DOC-5) — comment fix, no exec impact
- OPEN-005 (STALE_DOC-3) — label addition, no exec impact
- OPEN-002 (ARCH_DEBT-5) — one-time ledger migration, latest-per-shot clean

---

## 7. ANTI-REGRESSION CHECKLIST

```
□ ACTIVE_VIDEO_MODEL default = "kling" — ✅ PASS (line 493)
□ LTX_FAST raises RuntimeError — ✅ PASS (line 463 _LTXRetiredGuard)
□ route_shot() returns "kling" all branches — ✅ PASS (runner mtime confirmed, no route changes)
□ FAL_KEY / GOOGLE_API_KEY / OPENROUTER_API_KEY / ANTHROPIC_API_KEY / MUAPI_KEY PRESENT — ✅ PASS
□ I-score normalization in vision_judge — ✅ PASS (session_enforcer R5)
□ Gemini circuit breaker wired — ✅ PASS (session_enforcer R5)
□ Wire-A budget reset at scene start — ✅ PASS (runner:4386 _wire_a_reset)
□ Wire-B fail_sids logic — ✅ PASS (runner:5339 _fail_sids/_blocked_sids; label absent → OPEN-005)
□ Wire-C frozen regen — ✅ PASS (runner:5090 [WIRE-C] 6 occurrences confirmed R5)
□ Bare list guard on shot_plan load — ✅ PASS (runner:1433, 1470)
□ Chain arc enrichment wired — ✅ PASS (runner:65 import + line 4566 call)
□ All 62 M-shots have _arc_position — ✅ PASS (62/62 confirmed R5)
□ All 62 M-shots have _chain_group truthy — ✅ PASS (62/62 via _chain_group field R5)
□ E-shots have isolation flags — ✅ PASS (35/35 E-shots confirmed R5)
□ V37 governance hooks — ✅ PASS (2 GovernanceBar refs, 9 RefreshAll, 7 api/v37, 4 runner refs)
□ V37 Section 8 thumbBar/thumbUp/thumbDown — ✅ PASS (7 thumbBar refs, 7 thumbUp, 6 thumbDown confirmed R5)
□ shot-gallery-list display:grid — ✅ PASS (3 CSS grid refs confirmed R5)
□ Learning log: 0 regressions — ✅ PASS (ALL CLEAR R5)
□ Session enforcer: SYSTEM HEALTHY — ✅ PASS (69 passes, 0 blocks R5)
□ story_state_canon importable — ✅ PASS (R5)
□ failure_heatmap importable — ✅ PASS (R5)
□ chain_arc_intelligence.enrich_shots_with_arc importable — ✅ PASS (R5)
□ video_vision_oversight._vvo_run wired — ✅ PASS (runner:3301 confirmed R5) [NEW R5]
□ Session enforcer VVO checks: 3 new PASS — ✅ PASS (R5) [NEW R5]
□ gate_audit.json shows stale ORPHAN_SHOT — ⚠ OPEN-006 STALE_GATE_STATE-2 (operational, not code bug)
□ Last 4 ledger entries V=0.5 (contaminated 18:43 run) — ⚠ OPEN-006 (clears on --videos-only scene 006)
□ CPC decontaminate_prompt absent from runner — ⚠ OPEN-004 CHRONIC-4
□ Runner docstring lines 24/39 say Seedance PRIMARY — ⚠ OPEN-003 STALE_DOC-5
□ Wire-B "[WIRE-B]" comment label absent from line 5339 — ⚠ OPEN-005 STALE_DOC-3
□ 9 raw I>1.0 entries in full ledger history — ⚠ OPEN-002 ARCH_DEBT-5 (latest-per-shot clean)
```

---

## 8. NEW ARTIFACTS CREATED BETWEEN R4 AND R5

Files modified/created at 06:44–06:48 UTC (after R4 at 06:12 UTC):

| File | Size | Purpose | Impact on Production |
|------|------|---------|---------------------|
| `atlas_universal_runner.py` | 336,354 bytes (+25,980 vs backup) | VVO wiring, arc-aware Kling prompts, Vision Budget Tracker | CONFIRMED WIRED — VVO fires after video gen |
| `pipeline_stress_test.py` | 74,115 bytes | Standalone calibration test: 13 clips × D1-D20 Gemini scoring | Standalone only — NOT in production path |
| `VISION_ASSEMBLY_LINE_RUNSHEET.md` | 35,165 bytes | Output from stress test: clip scorecards, calibration findings, assembly-line plan | Reference doc — 4-layer loop for scenes 1-4 planning |

Additional files (created 00:24–02:15 UTC, before R4 write time but after R3):

| File | Size | Purpose |
|------|------|---------|
| `tools/video_vision_oversight.py` | 77,776 bytes | VVO module: CHARACTER_BLEED + FROZEN_FRAME + DIALOGUE_SYNC checks |
| `tools/vision_doctrine_prompts.py` | 92,501 bytes | D1-D20 doctrine prompt builder: used by stress test + FANZ promo generator |
| `generate_fanz_video_promos.py` | 32,860 bytes | FANZ TV promo generator with vision doctrine scoring |
| `generate_fanz_assets_batch3.py` | 22,967 bytes | FANZ asset batch generator V3 |
| `generate_fanz_assets_batch2.py` | 14,485 bytes | FANZ asset batch generator V2 |
| `generate_fanz_assets.py` | 39,071 bytes | FANZ asset generator V1 |

---

## 9. DOCUMENT LINEAGE

- Prior report: **ATLAS_ERROR_DEEPDIVE_2026-03-30_R4_KEEPUP_LATEST.md** (2026-03-30T06:12:47Z)
- Prior proof gate: **NONE** (no proof-gate run exists)
- Delta since R4: Runner updated (+25,980 bytes, VVO wired). 0 new ledger entries. 0 new frames. 0 new videos. System idle 12h 25m from last ledger entry.
- Report interval: ~62 minutes (R4→R5)
- Recommended next action: **Session is stable. VVO now confirmed wired. Run scene 006 --videos-only to clear ledger contamination. OPEN-004 fix is the only active code task.**

---

## PROOF_GATE_FEED

```json
{
  "session_timestamp": "2026-03-30T07:15:00Z",
  "report_number": "R5",
  "prior_report": "ATLAS_ERROR_DEEPDIVE_2026-03-30_R4_KEEPUP_LATEST.md",
  "ledger_age_hours": 12.5,
  "ledger_total_entries": 175,
  "ledger_unique_shots": 33,
  "ledger_last_contaminated_ts": "2026-03-29T18:43:06",
  "ledger_last_real_ts": "2026-03-29T17:54:06",
  "i_score_heuristic_pct": 70,
  "i_score_real_vlm_pct": 30,
  "production_idle_since": "2026-03-29T22:43:00Z",
  "runner_mtime": "2026-03-30T06:44:15Z",
  "runner_size_bytes": 336354,
  "runner_line_count": 5737,
  "shot_plan_mtime": "2026-03-30T01:20:43Z",
  "first_frames_count": 59,
  "mp4_count": 29,
  "session_enforcer_passes": 69,
  "session_enforcer_blocks": 0,
  "session_enforcer_status": "SYSTEM_HEALTHY",
  "vvo_wired": true,
  "vvo_call_site": "runner:3301",
  "vvo_checks": ["CHARACTER_BLEED", "FROZEN_FRAME", "DIALOGUE_SYNC"],
  "pipeline_stress_test_run": true,
  "stress_test_clips": 13,
  "stress_test_cost_usd": 2.275,
  "stress_test_first_pass_rate": 0.46,
  "stress_test_hard_fail_rate": 0.54,
  "stress_test_arc_d8_pass_rate": 0.23,
  "confirmed_bugs": [
    {
      "id": "OPEN-004",
      "title": "CPC decontaminate_prompt() not called — description fallback instead of CPC replacement",
      "consecutive_reports": 4,
      "class": "CHRONIC",
      "proof_receipt": "grep -n decontaminate_prompt atlas_universal_runner.py → no output; 013_M01/M02 _beat_action=None confirmed R5",
      "fix_recipe": "runner ~line 1117: import decontaminate_prompt from tools.creative_prompt_compiler; call with emotion + char; try/except safe fallback",
      "regression_guard": ["_beat_action primary path (~line 1113) unchanged", "_is_cpc_via_embedding detection (line 1115) unchanged"],
      "impact": "LOW-MEDIUM — 2 shots affected now; more if enrichment gaps grow"
    }
  ],
  "stale_gate_state": [
    {
      "id": "OPEN-006",
      "title": "gate_audit.json stale (ORPHAN_SHOT) + 006 ledger contamination",
      "consecutive_reports": 2,
      "class": "STALE_GATE_STATE",
      "proof_receipt": "Last 6 ledger entries show 4x contaminated V=0.5 ts=18:43; total entries=175 unchanged; gate code passes live",
      "resolution": "python3 atlas_universal_runner.py victorian_shadows_ep1 006 --mode lite --videos-only",
      "not_a_code_bug": true
    }
  ],
  "architectural_debt": [
    {
      "id": "OPEN-002",
      "title": "9 un-normalized I>1.0 historical ledger entries",
      "consecutive_reports": 5,
      "class": "ARCHITECTURAL_DEBT",
      "note": "Latest-per-shot clean (0 I>1.0). Raw aggregate only."
    }
  ],
  "stale_docs": [
    {
      "id": "OPEN-003",
      "title": "Runner docstring lines 24/39 say Seedance PRIMARY",
      "consecutive_reports": 5,
      "class": "STALE_DOC",
      "lines": [24, 39]
    },
    {
      "id": "OPEN-005",
      "title": "Wire-B QUALITY GATE logic unlabelled at line 5339 (line 9 changelog references it)",
      "consecutive_reports": 3,
      "class": "STALE_DOC",
      "note": "Wire B mentioned in line 9 header. [WIRE-B] label absent from line 5339 implementation. Logic healthy."
    }
  ],
  "false_positives_retracted": [],
  "confirmed_fixed_new_this_session": [
    "VVO (video_vision_oversight) fully wired: _vvo_run called at runner:3301 AFTER chain_gate BEFORE ARJ. Checks: CHARACTER_BLEED + FROZEN_FRAME + DIALOGUE_SYNC. Non-blocking.",
    "Session enforcer VVO checks: 3 new PASS entries. Total enforcer passes: 69 (up from 47).",
    "Pipeline stress test calibration data produced: 13 clips, $2.275, D1-D20 Gemini scoring. Arc framing override confirmed as #1 fix needed. First-pass rate 46%."
  ],
  "organ_health": {
    "skeleton": "HEALTHY — isinstance guard + 62/62 _chain_group truthy + 35/35 E-shots isolated",
    "liver": "DEGRADED — detection OK; decontaminate_prompt replacement absent (OPEN-004 CHRONIC-4)",
    "immune": "DEGRADED — runner header V31.0/Seedance docstring (OPEN-003); code correct",
    "nervous": "HEALTHY — session_enforcer SYSTEM HEALTHY, 69 passes, 0 blocks. VVO wired.",
    "eyes": "HEALTHY — 4 backends; all 5 env keys PRESENT; VVO two-tier models confirmed",
    "cortex": "DEGRADED — 70% I=0.75 heuristic; 4 contaminated 006 ledger entries (OPEN-006 operational)",
    "cinematographer": "HEALTHY — run_report success=True; 29 videos; VVO now active on video gen pipeline",
    "editor": "HEALTHY — Wire-B logic at runner:5339; Wire-C at runner:5090 (6 occurrences)",
    "regenerator": "HEALTHY — Wire-C confirmed at runner:5090",
    "doctrine_doc": "DEGRADED — version drift V31.0/V36.5; Seedance docstring; Wire-B label absent"
  },
  "recommended_next_action": "run_scene_006_videos_only_then_fix_open_004_CPC",
  "system_production_ready": true,
  "blocker_count": 0,
  "chronic_bug_count": 1,
  "note": "VVO newly wired between R4 and R5. System has no blocking issues. Scene 006 re-run recommended for ledger hygiene. OPEN-004 (CPC) is the only active code task."
}
```

---

*ATLAS Keep-Up R5 — 2026-03-30T07:15:00Z*
*Detection layer: REPORT only — no production files modified*
*Open issues: OPEN-004 (CHRONIC-4), OPEN-006 (STALE_GATE_STATE-2), OPEN-003 (STALE_DOC-5), OPEN-005 (STALE_DOC-3), OPEN-002 (ARCH_DEBT-5)*
*NEW CONFIRMED FIXED: VVO wired (runner:3301), enforcer 69 passes, stress test calibration data available*
*System production-ready. No blocking issues.*
*Key delta from R4: Runner updated after R4 was written (+25,980 bytes, VVO wired). No generation activity.*
