# ATLAS ERROR DEEPDIVE — 2026-03-30 R8 (KEEP-UP LATEST)

**Session timestamp:** 2026-03-30T10:11:01Z
**Run number:** R8
**Prior report:** ATLAS_ERROR_DEEPDIVE_2026-03-30_R7_KEEPUP_LATEST.md
**System version:** V36.5 (CLAUDE.md) / V31.0 docstring (runner header)
**Ledger age at snapshot:** 0d 15h 26m (last real entry 2026-03-29T17:54:06; last contaminated: 2026-03-29T18:43:06)
**Atlas project:** victorian_shadows_ep1

---

## 1. EXECUTIVE SUMMARY

**Score: 12 PASS / 1 CHRONIC_BUG / 1 ARCHITECTURAL_DEBT / 2 STALE_DOC / 1 STALE_GATE_STATE**

| Category | Count | Delta vs R7 |
|----------|-------|-------------|
| CONFIRMED_BUG / CHRONIC | 1 | = same (OPEN-004 → CHRONIC-7) |
| STALE_GATE_STATE | 1 | = same (OPEN-006 → STALE_GATE_STATE-5) |
| ARCHITECTURAL_DEBT | 1 | = same (OPEN-002 → ARCH_DEBT-8) |
| STALE_DOC | 2 | = same (OPEN-003 STALE_DOC-8; OPEN-005 STALE_DOC-6) |
| CONFIRMED_FIXED | 19 | = unchanged (all 19 verified intact via session_enforcer) |
| FALSE_POSITIVES RETRACTED | 0 | None |
| NEW ISSUES | 0 | None |

**Key findings R8:**

1. 🟡 **SYSTEM IDLE SINCE R7 — NO CHANGES:** Runner mtime = 2026-03-30T06:44:15Z (UNCHANGED from R7). Shot plan mtime = 2026-03-29T21:20:43Z (UNCHANGED). No new first frames, no new videos, no new ledger entries since R7. System has been production-idle for ~60 additional minutes (total ~15h 26m from last real ledger entry at 17:54:06 on 2026-03-29).

2. 🔴 **OPEN-004 CHRONIC-7:** `decontaminate_prompt` absent from runner — confirmed by live grep (zero output). `013_M01/M02` still `_beat_action=None`. 7th consecutive report. Severity LOW-MEDIUM. Fix recipe unchanged (7-line try/except at runner ~line 1117). **Escalation: 3 reports remaining until META-CHRONIC threshold (R11).**

3. 🟡 **OPEN-006 STALE_GATE_STATE-5:** gate_audit.json confirmed at `videos_kling_lite/gate_audit.json`. 4 ORPHAN_SHOT errors on 006_M01–M04, timestamp 2026-03-29T18:43:06, now 15h 27m old. Current shot_plan: all 4 shots have `_chain_group=006_chain` (correct). Gate_audit is a pre-fix stale artifact. Ledger: last 4 entries V=0.5 (contaminated, 18:43 run) — **unchanged**. Clears on next `--videos-only` scene 006.

4. 🟢 **SESSION ENFORCER: SYSTEM HEALTHY — 69 PASS, 0 BLOCK.** All 22 learning log fixes present, 0 regressions. All 5 env keys PRESENT. VVO wired at runner:3297. Arc enrichment at runner:4569/65. 4 vision backends active. No change from R7.

5. 🟢 **ALL 19 CONFIRMED-FIXED ITEMS INTACT.** Verified via session_enforcer 69/0 pass/block result and targeted greps. No regressions.

6. 🟢 **NO NEW ISSUES INTRODUCED.** R8 is a pure steady-state delta from R7 — counters increment, no new failure modes detected.

---

## 2. ORGAN HEALTH MAP

| Organ | Status | Signal | Proof (R8) |
|-------|--------|--------|------------|
| 🦴 Skeleton (shot_plan) | 🟢 HEALTHY | isinstance guard runner:1433/1470. shot_plan mtime unchanged from R7. 006_M01–04 all `_chain_group=006_chain`. | stat: shot_plan.json mtime 2026-03-29T21:20:43 |
| 🫀 Liver (prompt sanitizer) | 🟡 DEGRADED | `_is_cpc_via_embedding` detection at runner:245/1118. `decontaminate_prompt` absent from runner. 013_M01/M02 `_beat_action=None`. | grep decontaminate_prompt → no output (R8) |
| 🛡️ Immune (doctrine) | 🟡 DEGRADED | Runner header V31.0 + Seedance PRIMARY (lines 24/39). CLAUDE.md = V36.5. Code correct (ACTIVE_VIDEO_MODEL="kling" at line 493). | sed -n '24p;39p' R8 |
| ⚡ Nervous (hooks) | 🟢 HEALTHY | Session enforcer: ✅ SYSTEM HEALTHY. 69 PASS, 0 BLOCKS. VVO tier confirmed. | `python3 tools/session_enforcer.py` R8 |
| 👁️ Eyes (vision/identity) | 🟢 HEALTHY | All 5 env keys PRESENT. VVO `_vvo_run` at runner:3297. 4 vision backends active (session_enforcer R8). | grep _vvo_run runner:3297; .env check R8 |
| 🧠 Cortex (reward signal) | 🟡 DEGRADED | 23/33 latest-per-shot I=0.75 (70% heuristic). Last 4 ledger entries contaminated V=0.5 (18:43 run). Ledger age: 15h 26m. | ledger R8 (175 entries, 33 unique — UNCHANGED) |
| 🎬 Cinematographer (generation) | 🟢 HEALTHY | run_report success=True errors=[]. 59 first_frames. 29 mp4s in videos_kling_lite/. VVO fires post-video gen. | ls count + run_report R8 |
| ✂️ Editor (stitch) | 🟢 HEALTHY | Wire-B logic at runner:5342 (`_fail_sids/_blocked_sids`). Header line 9 references Wire-B. `[WIRE-B]` label absent at implementation site (OPEN-005 STALE_DOC). | grep Wire-B / _fail_sids R8 |
| 🔄 Regenerator (frozen fix) | 🟢 HEALTHY | Wire-C at runner:5090 — `[WIRE-C]` label (5 occurrences confirmed R7). `extract_last_frame` at runner:1408/3534/3748. | grep WIRE-C R7 (runner unchanged) |
| 📋 Doctrine Doc | 🟡 DEGRADED | Runner header V31.0 / Seedance PRIMARY (lines 24/39). CLAUDE.md V36.5. Wire-B label absent at implementation. Cosmetic — code correct. | sed R8 |

---

## 3. CONFIRMED FIXED (DO NOT RE-INVESTIGATE)

All 19 items intact as of R8. **No new additions this session.**

✅ **ENV LOAD ORDER (V35.0)** — All 5 keys PRESENT before vision_judge import. R1→R8.

✅ **I-SCORE NORMALIZATION (V35.0)** — vision_judge.py line 675. R1→R8.

✅ **GEMINI CIRCUIT BREAKER (V30.3)** — vision_judge.py lines 518-529. R1→R8.

✅ **V-SCORE 4-STATE (V30.0)** — All four states present. R1→R8.

✅ **END-FRAME CHAIN FIX (V31.0)** — `extract_last_frame()` called after each group (runner:1408, 3534). R1→R8.

✅ **ROUTE_SHOT ALL KLING (V31.0)** — All branches return "kling". ACTIVE_VIDEO_MODEL="kling" at line 493. R1→R8.

✅ **LTX RETIRED GUARD (C3)** — `_LTXRetiredGuard()` at line 463. R1→R8.

✅ **BARE LIST GUARD (T2-OR-18)** — isinstance guard at runner:1433, 1470. R1→R8.

✅ **WIRE-A BUDGET RESET** — `_wire_a_reset(scene_id)` at runner:4386. `_WIRE_A_MAX_REGENS_PER_SCENE=2`. R1→R8.

✅ **CHAIN ARC INTELLIGENCE (V36.5)** — `enrich_shots_with_arc()` at runner:4569 (import at line 65). R1→R8.

✅ **V36.4 ROOM ANCHOR** — Room DNA + location_master_path wired. R1→R8.

✅ **V37 GOVERNANCE HOOKS** — 2 HTML v37GovernanceBar refs, 9 v37RefreshAll refs, 7 api/v37 endpoints, 4 runner refs. R1→R8.

✅ **LEARNING LOG** — 22 fixes, 0 regressions (ALL CLEAR). R1→R8.

✅ **CPC INLINE DETECTION** — `_is_cpc_via_embedding()` at runner:245, called at runner:1118. R2→R8.

✅ **E-SHOT ISOLATION** — 35/35 E-shots `_no_char_ref` or `_is_broll` (shot_plan unchanged R8). R3→R8.

✅ **Wire-C WIRED** — `[WIRE-C]` label at runner:5090 (5 occurrences confirmed R7/R8 runner unchanged). R3→R8.

✅ **`_chain_group` SET ON ALL 62 M-SHOTS** — 62/62 M-shots (shot_plan unchanged R8). R4→R8.

✅ **VVO (VIDEO VISION OVERSIGHT) WIRED** — `_vvo_run` imported at runner:313–323; called at runner:3297. Checks: CHARACTER_BLEED, FROZEN_FRAME, DIALOGUE_SYNC. R5→R8.

✅ **PIPELINE STRESS TEST CALIBRATION DATA** — `VISION_ASSEMBLY_LINE_RUNSHEET.md` (35KB). 13 clips, $2.275, D1-D20. R5→R8.

---

## 4. OPEN ISSUES

---

### ⏱️ CHRONIC (7 reports) — OPEN-004: CPC decontaminate_prompt() Not Called — Description Fallback

**Classification:** CHRONIC (7 consecutive reports: R2→R8)
**Severity:** LOW-MEDIUM — `013_M01/M02` `_beat_action=None`. CPC detects generic content correctly but replaces with raw `description` field instead of CPC-rewritten directive.
**Escalation:** META-CHRONIC threshold at 10 consecutive reports (R11 if unaddressed — 3 reports remaining).

**PROOF RECEIPT (R8 — live):**
```
PROOF: grep -n "decontaminate_prompt" atlas_universal_runner.py
OUTPUT: (no output) — function not present in runner

PROOF: python3 check 013_M01/M02 _beat_action
OUTPUT:
  013_M01 _beat_action= None _arc_position= PIVOT
  013_M02 _beat_action= None _arc_position= RESOLVE

CONFIRMS: T2-CPC-6 requires CPC replacement not raw description.
          2 shots confirmed affected (unchanged from R7). Shot plan mtime unchanged.
```

**FIX RECIPE (minimal, non-breaking — unchanged from R7):**
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

**REGRESSION GUARD:** Does NOT touch `_beat_action` primary path (~line 1113). `try/except` non-blocking. Does NOT affect `_is_cpc_via_embedding` detection at runner:1118.

---

### 🟡 STALE_GATE_STATE (5 reports) — OPEN-006: gate_audit.json Stale + 006 Ledger Contamination

**Classification:** STALE_GATE_STATE (5 consecutive reports: R4→R8)
**Severity:** LOW — not a code bug. Clears on next production run.

**Location clarification (established R7):** gate_audit.json at `pipeline_outputs/victorian_shadows_ep1/videos_kling_lite/gate_audit.json` (not project root).

**PROOF RECEIPT (R8):**
```
PROOF: gate_audit.json content (R8 live)
OUTPUT: 4 entries, all ORPHAN_SHOT on 006_M01–04, timestamp 2026-03-29T18:43:06, age ~15h 27m

PROOF: shot_plan 006_M01–04 _chain_group (R8 live)
OUTPUT: all four = 006_chain ← correct, not orphan

PROOF: ledger tail
OUTPUT: 175 entries, 33 unique shots, last 4 entries V=0.5 C=0.7 — UNCHANGED from R7

CONFIRMS: gate_audit is a stale artifact from the pre-fix 18:43:06 run.
          Current shot_plan is correct. Ledger contamination unchanged.
          0 new generation activity in ~60 min (R7→R8 window).
```

**RESOLUTION (operational — no code fix needed):**
```bash
python3 atlas_universal_runner.py victorian_shadows_ep1 006 --mode lite --videos-only
```

---

### 🟡 ARCHITECTURAL_DEBT (8 reports) — OPEN-002: 9 Un-Normalized I>1.0 Historical Ledger Entries

**Classification:** ARCHITECTURAL_DEBT (8 consecutive: R1→R8)
**Severity:** LOW — latest-per-shot I>1.0: **0** (clean). Raw historical aggregate only.

**PROOF RECEIPT (R8):**
```
PROOF: python3 — raw ledger I>1.0 count (using 'I' field)
OUTPUT: RAW I>1.0: 9 (historical, all from pre-normalization runs)

PROOF: latest-per-shot I>1.0
OUTPUT: LATEST_PER_SHOT I>1.0: 0 entries: [] (clean)

CONFIRMS: No regression. Historical artefacts from 2026-03-24 pre-normalization runs only.
```

---

### 🟡 STALE_DOC (8 reports) — OPEN-003: Runner Docstring Declares Seedance as PRIMARY

**Classification:** STALE_DOC (8 consecutive: R1→R8)
**Severity:** LOW — code correct (ACTIVE_VIDEO_MODEL="kling" at line 493). Comments wrong.

**PROOF RECEIPT (R8):**
```
PROOF: sed -n '24p;39p' atlas_universal_runner.py
OUTPUT:
  Line 24: P2. Videos: ALL shots parallel → Seedance v2.0 PRIMARY (muapi.ai) | Kling v3/pro FALLBACK
  Line 39: All shots PRIMARY → Seedance v2.0 via muapi.ai (...)

CONFIRMS: Docstring says Seedance. Code says Kling. STALE_DOC — code correct.
```

---

### 🟡 STALE_DOC (6 reports) — OPEN-005: Wire-B Logic Unlabelled at Runner:5342

**Classification:** STALE_DOC (6 consecutive: R3→R8)
**Severity:** VERY LOW — logic correct at runner:5342 (`_fail_sids/_blocked_sids`). Header line 9 references Wire-B. Label absent from implementation.

**PROOF RECEIPT (R8):**
```
PROOF: grep -n "WIRE-B" atlas_universal_runner.py
OUTPUT: (no output at implementation line)

PROOF: grep -n "_fail_sids" atlas_universal_runner.py
OUTPUT: Line 5342: _fail_sids = {e["shot_id"] for e in reward_ledger if e.get("verdict") == "FAIL"}
        Line 5344: _blocked_sids = _fail_sids | _frozen_sids

PROOF: grep -n "Wire B" atlas_universal_runner.py
OUTPUT: Line 9: Wire B (2026-03-20): QUALITY GATE — FAIL/FROZEN shots blocked from stitch

CONFIRMS: Wire-B logic functional at line 5342; `[WIRE-B]` comment label missing from implementation site.
```

---

## 5. FALSE POSITIVES RETRACTED THIS SESSION

None. No new reclassifications this session.

---

## 6. PRIORITISED FIX LIST

Only CONFIRMED_BUG and CHRONIC issues listed.

| Priority | Issue | Class | Impact | Fix Size |
|----------|-------|-------|--------|----------|
| 1 | OPEN-004: CPC decontaminate_prompt not called | CHRONIC (7) | LOW-MEDIUM — 2 shots affected | 7 lines, try/except safe |

**Operational (no code fix needed):**
- OPEN-006: Run `python3 atlas_universal_runner.py victorian_shadows_ep1 006 --mode lite --videos-only` — clears stale gate_audit + ledger contamination.

**Defer (comment fixes, no exec impact):**
- OPEN-003 (STALE_DOC-8) — 2-line comment update in runner header lines 24/39
- OPEN-005 (STALE_DOC-6) — add `[WIRE-B]` comment at runner:5342
- OPEN-002 (ARCH_DEBT-8) — one-time ledger migration; latest-per-shot clean

---

## 7. ANTI-REGRESSION CHECKLIST

```
□ ACTIVE_VIDEO_MODEL default = "kling" — ✅ PASS (runner:493 confirmed R8)
□ LTX_FAST raises RuntimeError — ✅ PASS (runner:463 _LTXRetiredGuard R8)
□ route_shot() returns "kling" all branches — ✅ PASS (runner mtime unchanged R8)
□ FAL_KEY / GOOGLE_API_KEY / OPENROUTER_API_KEY / ANTHROPIC_API_KEY / MUAPI_KEY — ✅ PASS (all 5 R8)
□ I-score normalization in vision_judge — ✅ PASS (session_enforcer R8 69 passes)
□ Gemini circuit breaker wired — ✅ PASS (session_enforcer R8)
□ Wire-A budget reset at scene start — ✅ PASS (runner:4386 _wire_a_reset R8)
□ Wire-B fail_sids logic — ✅ PASS (runner:5342 _fail_sids/_blocked_sids; label absent → OPEN-005)
□ Wire-C frozen regen — ✅ PASS (runner:5090 [WIRE-C] 5 occurrences, runner unchanged R8)
□ Bare list guard on shot_plan load — ✅ PASS (runner:1433, 1470 R8)
□ Chain arc enrichment wired — ✅ PASS (runner:65 import + line 4569 call R8)
□ All 62 M-shots have _arc_position — ✅ PASS (shot_plan unchanged)
□ All 62 M-shots have _chain_group truthy — ✅ PASS (shot_plan unchanged)
□ E-shots have isolation flags — ✅ PASS (shot_plan unchanged)
□ V37 governance HTML refs — ✅ PASS (confirmed R6, no HTML changes since)
□ Section 8 thumbBar/thumbUp/thumbDown — ✅ PASS (confirmed R6, no HTML changes since)
□ shot-gallery-list display:grid — ✅ PASS (confirmed R6, no HTML changes since)
□ Learning log: 0 regressions — ✅ PASS (ALL CLEAR R8)
□ Session enforcer: SYSTEM HEALTHY — ✅ PASS (69 passes, 0 blocks R8)
□ story_state_canon importable — ✅ PASS (session_enforcer R8)
□ failure_heatmap importable — ✅ PASS (session_enforcer R8)
□ chain_arc_intelligence.enrich_shots_with_arc importable — ✅ PASS (session_enforcer R8)
□ VVO _vvo_run wired at runner:3297 — ✅ PASS (session_enforcer R8)
□ Session enforcer VVO checks — ✅ PASS (session_enforcer R8 69 passes)
□ 006 chain_groups in shot_plan correct — ✅ PASS (006_M01–04 all _chain_group=006_chain R8)
□ gate_audit.json ORPHAN_SHOT stale — ⚠ OPEN-006 STALE_GATE_STATE-5 (videos_kling_lite/; operational, not code bug)
□ Last 4 ledger entries V=0.5 contaminated — ⚠ OPEN-006 (clears on --videos-only scene 006)
□ CPC decontaminate_prompt absent from runner — ⚠ OPEN-004 CHRONIC-7
□ Runner docstring lines 24/39 say Seedance PRIMARY — ⚠ OPEN-003 STALE_DOC-8
□ Wire-B "[WIRE-B]" comment label absent from line 5342 — ⚠ OPEN-005 STALE_DOC-6
□ 9 raw I>1.0 entries in full ledger history — ⚠ OPEN-002 ARCH_DEBT-8 (latest-per-shot clean)
```

---

## 8. DELTA FROM R7

| Metric | R7 | R8 | Delta |
|--------|----|----|-------|
| Session timestamp | 2026-03-30T09:10:20Z | 2026-03-30T10:11:01Z | +61 min |
| Runner mtime | 2026-03-30T06:44:15Z | 2026-03-30T06:44:15Z | **UNCHANGED** |
| Runner size (bytes) | 336,354 | 336,354 | **UNCHANGED** |
| Shot plan mtime | 2026-03-29T21:20:43Z | 2026-03-29T21:20:43Z | **UNCHANGED** |
| Ledger entries | 175 | 175 | **UNCHANGED** |
| Ledger unique shots | 33 | 33 | **UNCHANGED** |
| Ledger age | 14h 26m | 15h 26m | +60 min |
| First frames count | 59 | 59 | **UNCHANGED** |
| Video mp4 count (videos_kling_lite/) | 29 | 29 | **UNCHANGED** |
| Session enforcer passes | 69 | 69 | **UNCHANGED** |
| Session enforcer blocks | 0 | 0 | **UNCHANGED** |
| Learning log regressions | 0 | 0 | **UNCHANGED** |
| OPEN-004 consecutive count | 6 | 7 | +1 (CHRONIC-7) |
| OPEN-006 consecutive count | 4 | 5 | +1 (STALE_GATE_STATE-5) |
| OPEN-003 consecutive count | 7 | 8 | +1 (STALE_DOC-8) |
| OPEN-005 consecutive count | 5 | 6 | +1 (STALE_DOC-6) |
| OPEN-002 consecutive count | 7 | 8 | +1 (ARCH_DEBT-8) |
| New confirmed fixed | 0 | 0 | unchanged |
| New issues | 0 | 0 | unchanged |
| Clarifications | 0 | 0 | None |

**Summary:** System has been production-idle for the entire R7→R8 interval (~61 minutes). No code changes, no generation activity, no new ledger entries. All counters tick forward by 1. OPEN-004 is now CHRONIC-7, 3 reports away from META-CHRONIC threshold (R11). System remains production-ready with 0 blocking issues.

---

## 9. DOCUMENT LINEAGE

- Prior report: **ATLAS_ERROR_DEEPDIVE_2026-03-30_R7_KEEPUP_LATEST.md** (2026-03-30T09:10:20Z)
- Prior proof gate: **NONE** (no proof-gate run has been executed)
- Delta since R7: 0 code changes. 0 new frames. 0 new videos. 0 new ledger entries.
- Report interval: ~61 minutes (R7→R8)
- Recommended next action: **Run scene 006 `--videos-only` to clear ledger contamination (OPEN-006). Apply OPEN-004 CPC fix in next human session (CHRONIC-7 — 7 lines, non-blocking). Defer OPEN-003/005 doc cosmetic fixes.**

---

## PROOF_GATE_FEED

```json
{
  "session_timestamp": "2026-03-30T10:11:01Z",
  "report_number": "R8",
  "prior_report": "ATLAS_ERROR_DEEPDIVE_2026-03-30_R7_KEEPUP_LATEST.md",
  "ledger_age_hours": 15.43,
  "ledger_total_entries": 175,
  "ledger_unique_shots": 33,
  "ledger_last_contaminated_ts": "2026-03-29T18:43:06",
  "ledger_last_real_ts": "2026-03-29T17:54:06",
  "i_score_heuristic_latest_pct": 70,
  "i_score_real_vlm_latest_pct": 30,
  "production_idle_since": "2026-03-29T22:43:00Z",
  "runner_mtime": "2026-03-30T06:44:15Z",
  "runner_size_bytes": 336354,
  "shot_plan_mtime": "2026-03-29T21:20:43Z",
  "first_frames_count": 59,
  "mp4_count_videos_kling_lite": 29,
  "mp4_count_videos_dir": 0,
  "session_enforcer_passes": 69,
  "session_enforcer_blocks": 0,
  "session_enforcer_status": "SYSTEM_HEALTHY",
  "vvo_wired": true,
  "vvo_call_site": "runner:3297",
  "confirmed_bugs": [
    {
      "id": "OPEN-004",
      "title": "CPC decontaminate_prompt() not called — description fallback instead of CPC replacement",
      "consecutive_reports": 7,
      "class": "CHRONIC",
      "escalation_note": "CHRONIC-7. META-CHRONIC threshold at 10 consecutive (R11). 3 reports remaining. No current production blocker; 2 shots with null beat_action only.",
      "proof_receipt": "grep -n decontaminate_prompt atlas_universal_runner.py → no output; 013_M01/M02 _beat_action=None confirmed R8",
      "fix_recipe": "runner ~line 1117: import decontaminate_prompt from tools.creative_prompt_compiler; call with emotion + char; try/except safe fallback",
      "regression_guard": ["_beat_action primary path (~line 1113) unchanged", "_is_cpc_via_embedding detection (runner:1118) unchanged"],
      "impact": "LOW-MEDIUM — 2 shots affected; contained"
    }
  ],
  "stale_gate_state": [
    {
      "id": "OPEN-006",
      "title": "gate_audit.json stale (ORPHAN_SHOT) + 006 ledger contamination",
      "consecutive_reports": 5,
      "class": "STALE_GATE_STATE",
      "gate_audit_location": "pipeline_outputs/victorian_shadows_ep1/videos_kling_lite/gate_audit.json",
      "proof_receipt": "gate_audit.json: 4 ORPHAN_SHOT entries 006_M01-04 ts=2026-03-29T18:43:06 age=~15h27m. Current shot_plan: 006_M01-04 all _chain_group=006_chain.",
      "resolution": "python3 atlas_universal_runner.py victorian_shadows_ep1 006 --mode lite --videos-only",
      "not_a_code_bug": true
    }
  ],
  "architectural_debt": [
    {
      "id": "OPEN-002",
      "title": "9 un-normalized I>1.0 historical ledger entries",
      "consecutive_reports": 8,
      "class": "ARCHITECTURAL_DEBT",
      "note": "Latest-per-shot clean (0 I>1.0). Raw aggregate: 9. Historical artefacts from pre-normalization runs only."
    }
  ],
  "stale_docs": [
    {
      "id": "OPEN-003",
      "title": "Runner docstring lines 24/39 say Seedance PRIMARY",
      "consecutive_reports": 8,
      "class": "STALE_DOC",
      "lines": [24, 39]
    },
    {
      "id": "OPEN-005",
      "title": "Wire-B QUALITY GATE logic unlabelled at line 5342",
      "consecutive_reports": 6,
      "class": "STALE_DOC",
      "note": "Wire B in line 9 header. [WIRE-B] label absent from implementation at line 5342. Logic healthy."
    }
  ],
  "false_positives_retracted": [],
  "confirmed_fixed_new_this_session": [],
  "clarifications_this_session": [],
  "organ_health": {
    "skeleton": "HEALTHY — isinstance guard runner:1433/1470; shot_plan mtime unchanged; 006 chain_groups correct",
    "liver": "DEGRADED — detection OK; decontaminate_prompt replacement absent (OPEN-004 CHRONIC-7)",
    "immune": "DEGRADED — runner header V31.0/Seedance docstring (OPEN-003 STALE_DOC-8); code correct",
    "nervous": "HEALTHY — session_enforcer SYSTEM HEALTHY, 69 passes, 0 blocks",
    "eyes": "HEALTHY — all 5 env keys PRESENT; VVO confirmed runner:3297; 4 backends active",
    "cortex": "DEGRADED — 70% I=0.75 heuristic (latest); 4 contaminated 006 entries (OPEN-006 STALE_GATE_STATE-5)",
    "cinematographer": "HEALTHY — run_report success=True; 59 frames, 29 videos_kling_lite mp4s; VVO active",
    "editor": "HEALTHY — Wire-B logic at runner:5342; Wire-C runner:5090 5 occurrences (runner unchanged)",
    "regenerator": "HEALTHY — Wire-C confirmed runner:5090 (runner unchanged R8)",
    "doctrine_doc": "DEGRADED — version drift V31.0/V36.5; Seedance docstring (lines 24/39); Wire-B label absent"
  },
  "recommended_next_action": "run_scene_006_videos_only_then_fix_open_004_CPC_next_human_session",
  "system_production_ready": true,
  "blocker_count": 0,
  "chronic_bug_count": 1,
  "system_delta_from_prior": "IDLE — no code changes, no generation activity, no new ledger entries in ~61-minute R7→R8 window",
  "note": "Steady-state report. System idle since R7. OPEN-004 CHRONIC-7 is the only active code task (3 reports until META-CHRONIC). Scene 006 --videos-only recommended for ledger hygiene. No new issues, no regressions, no false positives."
}
```

---

*ATLAS Keep-Up R8 — 2026-03-30T10:11:01Z*
*Detection layer: REPORT only — no production files modified*
*Open issues: OPEN-004 (CHRONIC-7), OPEN-006 (STALE_GATE_STATE-5), OPEN-003 (STALE_DOC-8), OPEN-005 (STALE_DOC-6), OPEN-002 (ARCH_DEBT-8)*
*Confirmed fixed: 19 items — all intact*
*System production-ready. No blocking issues. Production idle 15h 26m.*
*Key delta from R7: NONE — system unchanged. All open-issue counters +1. OPEN-004 now CHRONIC-7 (3 from META-CHRONIC).*
