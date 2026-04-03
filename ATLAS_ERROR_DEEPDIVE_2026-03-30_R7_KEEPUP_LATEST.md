# ATLAS ERROR DEEPDIVE — 2026-03-30 R7 (KEEP-UP LATEST)

**Session timestamp:** 2026-03-30T09:10:20Z
**Run number:** R7
**Prior report:** ATLAS_ERROR_DEEPDIVE_2026-03-30_R6_KEEPUP_LATEST.md
**System version:** V36.5 (CLAUDE.md) / V31.0 docstring (runner header)
**Ledger age at snapshot:** 0d 14h 26m (last real entry 2026-03-29T17:54:06; last contaminated: 2026-03-29T18:43:06)
**Atlas project:** victorian_shadows_ep1

---

## 1. EXECUTIVE SUMMARY

**Score: 12 PASS / 1 CHRONIC_BUG / 1 ARCHITECTURAL_DEBT / 2 STALE_DOC / 1 STALE_GATE_STATE**

| Category | Count | Delta vs R6 |
|----------|-------|-------------|
| CONFIRMED_BUG / CHRONIC | 1 | = same (OPEN-004 → CHRONIC-6) |
| STALE_GATE_STATE | 1 | = same (OPEN-006 → STALE_GATE_STATE-4) |
| ARCHITECTURAL_DEBT | 1 | = same (OPEN-002 → ARCH_DEBT-7) |
| STALE_DOC | 2 | = same (OPEN-003 STALE_DOC-7; OPEN-005 STALE_DOC-5) |
| CONFIRMED_FIXED | 19 | = unchanged (all 19 verified intact via session_enforcer) |
| FALSE_POSITIVES RETRACTED | 0 | None |
| NEW ISSUES | 0 | None |

**Key findings R7:**

1. 🟡 **SYSTEM IDLE SINCE R6 — NO CHANGES:** Runner mtime = 2026-03-30T06:44:15Z (UNCHANGED from R6). Shot plan mtime = 2026-03-29T21:20:43Z (UNCHANGED). No new first frames, no new videos, no new ledger entries since R6. System has been production-idle for ~60 additional minutes (total ~14h 26m from last real ledger entry).

2. 🔴 **OPEN-004 CHRONIC-6:** `decontaminate_prompt` absent from runner — confirmed by live grep (zero output). `013_M01/M02` still `_beat_action=None`. 6th consecutive report. Severity LOW-MEDIUM. Fix recipe unchanged (7-line try/except at runner ~line 1117). **Escalation: approaching META-CHRONIC (threshold at 10 consecutive = R11).**

3. 🟡 **OPEN-006 STALE_GATE_STATE-4:** gate_audit.json confirmed in `videos_kling_lite/` (not project root). 4 ORPHAN_SHOT errors on 006_M01–M04, timestamp 2026-03-29T18:43:06, 14h 27m old. **CLARIFICATION from R7:** current shot_plan has `_chain_group=006_chain` on all 4 shots — gate_audit is stale from a pre-fix run. Ledger contamination unchanged (last 4 entries V=0.5 from 18:43). Clears on next `--videos-only` scene 006.

4. 🟢 **VIDEOS/ DIRECTORY CLARIFICATION (R7 NEW FINDING — NON-ISSUE):** `pipeline_outputs/victorian_shadows_ep1/videos/` is empty (mtime 2026-03-28T17:01). The 29 production mp4s reside in `videos_kling_lite/`. This was already the state in R6 — the R6 report's "29 mp4s" was counting `videos_kling_lite/*.mp4`. Not a regression; historical clarification only.

5. 🟢 **ALL 19 CONFIRMED-FIXED ITEMS INTACT:** Session enforcer SYSTEM HEALTHY — 69 passes, 0 blocks. Learning log 22 fixes, 0 regressions. All env keys PRESENT. VVO wired at runner:3297. Arc enrichment at runner:4569. All key wires verified.

6. 🟢 **NO NEW ISSUES INTRODUCED.** R7 is a steady-state delta from R6 — counters increment, no new failure modes detected.

---

## 2. ORGAN HEALTH MAP

| Organ | Status | Signal | Proof (R7) |
|-------|--------|--------|------------|
| 🦴 Skeleton (shot_plan) | 🟢 HEALTHY | isinstance guard runner:1433/1470. shot_plan mtime unchanged from R6. 006_M01–04 all have `_chain_group=006_chain` (contradicts stale gate_audit). | stat: shot_plan.json mtime 2026-03-29T21:20:43 |
| 🫀 Liver (prompt sanitizer) | 🟡 DEGRADED | `_is_cpc_via_embedding` detection at runner:245/1118. `decontaminate_prompt` absent from runner. 013_M01/M02 `_beat_action=None`. | grep decontaminate_prompt → no output (R7) |
| 🛡️ Immune (doctrine) | 🟡 DEGRADED | Runner header V31.0 + Seedance PRIMARY (lines 24/39). CLAUDE.md = V36.5. Code correct (ACTIVE_VIDEO_MODEL="kling" at line 493). | sed -n '24p;39p' R7 |
| ⚡ Nervous (hooks) | 🟢 HEALTHY | Session enforcer: ✅ SYSTEM HEALTHY. 69 PASS, 0 BLOCKS. VVO tier confirmed. | `python3 tools/session_enforcer.py` R7 |
| 👁️ Eyes (vision/identity) | 🟢 HEALTHY | All 5 env keys PRESENT. VVO _vvo_run at runner:3297. 4 vision backends active (session_enforcer R7). | grep _vvo_run runner:3297; .env check R7 |
| 🧠 Cortex (reward signal) | 🟡 DEGRADED | 23/33 latest-per-shot I=0.75 (70% heuristic). Last 4 ledger entries contaminated V=0.5 (18:43 run). Ledger age: 14h 26m. | ledger R7 (175 entries, 33 unique — UNCHANGED) |
| 🎬 Cinematographer (generation) | 🟢 HEALTHY | run_report success=True errors=[]. 59 first_frames. 29 mp4s in videos_kling_lite/. VVO fires post-video gen. | ls count + run_report R7 |
| ✂️ Editor (stitch) | 🟢 HEALTHY | Wire-B logic at runner:5339 (`_fail_sids/_blocked_sids`). Header line 9 references Wire-B. "[WIRE-B]" label absent at implementation site (OPEN-005 STALE_DOC). | grep WIRE-B R7 |
| 🔄 Regenerator (frozen fix) | 🟢 HEALTHY | Wire-C at runner:5090 — `[WIRE-C]` label (5 occurrences confirmed R7). `extract_last_frame` at runner:1408/3534/3748. | grep WIRE-C R7 |
| 📋 Doctrine Doc | 🟡 DEGRADED | Runner header V31.0 / Seedance PRIMARY (lines 24/39). CLAUDE.md V36.5. Wire-B label absent at implementation. Cosmetic — code correct. | sed R7 |

---

## 3. CONFIRMED FIXED (DO NOT RE-INVESTIGATE)

All 19 items intact as of R7. **No new additions this session.**

✅ **ENV LOAD ORDER (V35.0)** — All 5 keys PRESENT before vision_judge import. R1→R7.

✅ **I-SCORE NORMALIZATION (V35.0)** — vision_judge.py line 675. R1→R7.

✅ **GEMINI CIRCUIT BREAKER (V30.3)** — vision_judge.py lines 518-529. R1→R7.

✅ **V-SCORE 4-STATE (V30.0)** — All four states present. R1→R7.

✅ **END-FRAME CHAIN FIX (V31.0)** — `extract_last_frame()` called after each group (runner:1408, 3534). R1→R7.

✅ **ROUTE_SHOT ALL KLING (V31.0)** — All branches return "kling". ACTIVE_VIDEO_MODEL="kling" at line 493. R1→R7.

✅ **LTX RETIRED GUARD (C3)** — `_LTXRetiredGuard()` at line 463. R1→R7.

✅ **BARE LIST GUARD (T2-OR-18)** — isinstance guard at runner:1433, 1470. R1→R7.

✅ **WIRE-A BUDGET RESET** — `_wire_a_reset(scene_id)` at runner:4386. `_WIRE_A_MAX_REGENS_PER_SCENE=2`. R1→R7.

✅ **CHAIN ARC INTELLIGENCE (V36.5)** — `enrich_shots_with_arc()` at runner:4569 (import at line 65). R1→R7.

✅ **V36.4 ROOM ANCHOR** — Room DNA + location_master_path wired. R1→R7.

✅ **V37 GOVERNANCE HOOKS** — 2 HTML v37GovernanceBar refs, 9 v37RefreshAll refs, 7 api/v37 endpoints, 4 runner refs. R1→R7.

✅ **LEARNING LOG** — 22 fixes, 0 regressions (ALL CLEAR). R1→R7.

✅ **CPC INLINE DETECTION** — `_is_cpc_via_embedding()` at runner:245, called at runner:1118. R2→R7.

✅ **E-SHOT ISOLATION** — 35/35 E-shots `_no_char_ref` or `_is_broll` (shot_plan unchanged R7). R3→R7.

✅ **Wire-C WIRED** — `[WIRE-C]` label at runner:5090 (5 occurrences confirmed R7). R3→R7.

✅ **`_chain_group` SET ON ALL 62 M-SHOTS** — 62/62 M-shots (shot_plan unchanged R7). R4→R7.

✅ **VVO (VIDEO VISION OVERSIGHT) WIRED** — `_vvo_run` imported at runner:313–323; called at runner:3297. Checks: CHARACTER_BLEED, FROZEN_FRAME, DIALOGUE_SYNC. R5→R7.

✅ **PIPELINE STRESS TEST CALIBRATION DATA** — `VISION_ASSEMBLY_LINE_RUNSHEET.md` (35KB). 13 clips, $2.275, D1-D20. R5→R7.

---

## 4. OPEN ISSUES

---

### ⏱️ CHRONIC (6 reports) — OPEN-004: CPC decontaminate_prompt() Not Called — Description Fallback

**Classification:** CHRONIC (6 consecutive reports: R2→R7)
**Severity:** LOW-MEDIUM — `013_M01/M02` `_beat_action=None`. CPC detects generic content correctly but replaces with raw `description` field instead of CPC-rewritten directive.
**Escalation:** META-CHRONIC threshold at 10 consecutive reports (R11 if unaddressed).

**PROOF RECEIPT (R7 — live):**
```
PROOF: grep -n "decontaminate_prompt" atlas_universal_runner.py
OUTPUT: (no output) — function not present in runner

PROOF: python3 check 013_M01/M02 _beat_action
OUTPUT:
  013_M01 _beat_action= None _arc_position= PIVOT
  013_M02 _beat_action= None _arc_position= RESOLVE

CONFIRMS: T2-CPC-6 requires CPC replacement not raw description.
          2 shots confirmed affected (unchanged from R6). Shot plan unchanged.
```

**FIX RECIPE (minimal, non-breaking — unchanged from R6):**
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

### 🟡 STALE_GATE_STATE (4 reports) — OPEN-006: gate_audit.json Stale + 006 Ledger Contamination

**Classification:** STALE_GATE_STATE (4 consecutive reports: R4→R7)
**Severity:** LOW — not a code bug. Clears on next production run.

**R7 CLARIFICATION (new detail):** gate_audit.json is located at `pipeline_outputs/victorian_shadows_ep1/videos_kling_lite/gate_audit.json` (not project root as R6 implied). The 4 ORPHAN_SHOT errors on 006_M01–M04 are from the 18:43:06 run on 2026-03-29 — which ran BEFORE the shot_plan received `_chain_group=006_chain`. The **current shot_plan** has correct chain_groups. This gate_audit is a stale artifact from a bad run.

**PROOF RECEIPT (R7):**
```
PROOF: gate_audit.json content
OUTPUT: 4 entries, all ORPHAN_SHOT on 006_M01–04, timestamp 2026-03-29T18:43:06, age 14h 27m

PROOF: current shot_plan 006_M01 _chain_group
OUTPUT: 006_M01 _chain_group= 006_chain ← correct, not orphan

PROOF: ledger tail — 175 entries, 33 unique, last 4 V=0.5 C=0.7 — UNCHANGED from R6

CONFIRMS: gate_audit stale (bad pre-fix run artifact). Current shot_plan correct.
          Ledger contamination unchanged. 0 new generation activity in ~60 min.
```

**RESOLUTION (operational — no code fix):**
```bash
python3 atlas_universal_runner.py victorian_shadows_ep1 006 --mode lite --videos-only
```

---

### 🟡 ARCHITECTURAL_DEBT (7 reports) — OPEN-002: 9 Un-Normalized I>1.0 Historical Ledger Entries

**Classification:** ARCHITECTURAL_DEBT (7 consecutive: R1→R7)
**Severity:** LOW — latest-per-shot I>1.0: **0** (clean). Raw historical aggregate only.

**PROOF RECEIPT (R7):**
```
PROOF: python3 count raw I>1.0
OUTPUT: I_GT_1: 9 (raw count, all historical from pre-normalization runs)

PROOF: latest-per-shot I>1.0
OUTPUT: LATEST_PER_SHOT_I_GT1: 0 entries: [] (clean)

CONFIRMS: No regression. Historical artefacts from 2026-03-24 pre-normalization runs only.
```

---

### 🟡 STALE_DOC (7 reports) — OPEN-003: Runner Docstring Declares Seedance as PRIMARY

**Classification:** STALE_DOC (7 consecutive: R1→R7)
**Severity:** LOW — code correct (ACTIVE_VIDEO_MODEL="kling" at line 493). Comments wrong.

**PROOF RECEIPT (R7):**
```
PROOF: sed -n '24p;39p' atlas_universal_runner.py
OUTPUT:
  Line 24: P2. Videos: ALL shots parallel → Seedance v2.0 PRIMARY (muapi.ai) | Kling v3/pro FALLBACK
  Line 39: All shots PRIMARY → Seedance v2.0 via muapi.ai (...)

CONFIRMS: Docstring says Seedance. Code says Kling. STALE_DOC — code correct.
```

---

### 🟡 STALE_DOC (5 reports) — OPEN-005: Wire-B Logic Unlabelled at Runner:5339

**Classification:** STALE_DOC (5 consecutive: R3→R7)
**Severity:** VERY LOW — logic correct at runner:5339. Header line 9 references Wire-B. Label absent from implementation.

**PROOF RECEIPT (R7):**
```
PROOF: grep -n "WIRE-B" atlas_universal_runner.py
OUTPUT: (no output at implementation line)

PROOF: grep -n "Wire B" atlas_universal_runner.py
OUTPUT: Line 9: Wire B (2026-03-20): QUALITY GATE — FAIL/FROZEN shots blocked from stitch

CONFIRMS: Wire-B logic functional; "[WIRE-B]" comment label missing from implementation site.
```

---

## 5. FALSE POSITIVES RETRACTED THIS SESSION

None. No new reclassifications this session.

**R7 NOTE:** "videos/ directory empty" (observed this session) is a non-issue. Directory mtime = 2026-03-28T17:01 — already empty before R6. R6's "29 mp4s" was counting `videos_kling_lite/*.mp4` files, which remain intact at 29. No regression.

---

## 6. PRIORITISED FIX LIST

Only CONFIRMED_BUG and CHRONIC issues listed.

| Priority | Issue | Class | Impact | Fix Size |
|----------|-------|-------|--------|----------|
| 1 | OPEN-004: CPC decontaminate_prompt not called | CHRONIC (6) | LOW-MEDIUM — 2 shots affected | 7 lines, try/except safe |

**Operational (no code fix needed):**
- OPEN-006: Run `python3 atlas_universal_runner.py victorian_shadows_ep1 006 --mode lite --videos-only` — clears stale gate_audit + ledger contamination.

**Defer (comment fixes, no exec impact):**
- OPEN-003 (STALE_DOC-7) — 2-line comment update in runner header
- OPEN-005 (STALE_DOC-5) — add `[WIRE-B]` comment at runner:5339
- OPEN-002 (ARCH_DEBT-7) — one-time ledger migration; latest-per-shot clean

---

## 7. ANTI-REGRESSION CHECKLIST

```
□ ACTIVE_VIDEO_MODEL default = "kling" — ✅ PASS (runner:493 confirmed R7)
□ LTX_FAST raises RuntimeError — ✅ PASS (runner:463 _LTXRetiredGuard × 2 R7)
□ route_shot() returns "kling" all branches — ✅ PASS (runner mtime unchanged R7)
□ FAL_KEY / GOOGLE_API_KEY / OPENROUTER_API_KEY / ANTHROPIC_API_KEY / MUAPI_KEY — ✅ PASS (all 5 R7)
□ I-score normalization in vision_judge — ✅ PASS (session_enforcer R7 69 passes)
□ Gemini circuit breaker wired — ✅ PASS (session_enforcer R7)
□ Wire-A budget reset at scene start — ✅ PASS (runner:4386 _wire_a_reset R7)
□ Wire-B fail_sids logic — ✅ PASS (runner:5339 _fail_sids/_blocked_sids; label absent → OPEN-005)
□ Wire-C frozen regen — ✅ PASS (runner:5090 [WIRE-C] 5 occurrences R7)
□ Bare list guard on shot_plan load — ✅ PASS (runner:1433, 1470 R7)
□ Chain arc enrichment wired — ✅ PASS (runner:65 import + line 4569 call R7)
□ All 62 M-shots have _arc_position — ✅ PASS (shot_plan unchanged from R5 where 62/62 confirmed)
□ All 62 M-shots have _chain_group truthy — ✅ PASS (shot_plan unchanged)
□ E-shots have isolation flags — ✅ PASS (shot_plan unchanged from R5 where 35/35 confirmed)
□ V37 governance HTML refs — ✅ PASS (confirmed R6, no HTML changes since)
□ Section 8 thumbBar/thumbUp/thumbDown — ✅ PASS (confirmed R6, no HTML changes since)
□ shot-gallery-list display:grid — ✅ PASS (confirmed R6, no HTML changes since)
□ Learning log: 0 regressions — ✅ PASS (ALL CLEAR R7)
□ Session enforcer: SYSTEM HEALTHY — ✅ PASS (69 passes, 0 blocks R7)
□ story_state_canon importable — ✅ PASS (session_enforcer R7)
□ failure_heatmap importable — ✅ PASS (session_enforcer R7)
□ chain_arc_intelligence.enrich_shots_with_arc importable — ✅ PASS (session_enforcer R7)
□ VVO _vvo_run wired at runner:3297 — ✅ PASS (grep R7)
□ Session enforcer VVO checks — ✅ PASS (session_enforcer R7 69 passes)
□ 006 chain_groups in shot_plan correct — ✅ PASS (006_M01–04 all _chain_group=006_chain R7)
□ gate_audit.json ORPHAN_SHOT stale — ⚠ OPEN-006 STALE_GATE_STATE-4 (location: videos_kling_lite/; operational, not code bug)
□ Last 4 ledger entries V=0.5 contaminated — ⚠ OPEN-006 (clears on --videos-only scene 006)
□ CPC decontaminate_prompt absent from runner — ⚠ OPEN-004 CHRONIC-6
□ Runner docstring lines 24/39 say Seedance PRIMARY — ⚠ OPEN-003 STALE_DOC-7
□ Wire-B "[WIRE-B]" comment label absent from line 5339 — ⚠ OPEN-005 STALE_DOC-5
□ 9 raw I>1.0 entries in full ledger history — ⚠ OPEN-002 ARCH_DEBT-7 (latest-per-shot clean)
```

---

## 8. DELTA FROM R6

| Metric | R6 | R7 | Delta |
|--------|----|----|-------|
| Session timestamp | 2026-03-30T08:10:34Z | 2026-03-30T09:10:20Z | +59 min |
| Runner mtime | 2026-03-30T06:44:15Z | 2026-03-30T06:44:15Z | **UNCHANGED** |
| Runner size (bytes) | 336,354 | 336,354 | **UNCHANGED** |
| Shot plan mtime | 2026-03-29T21:20:43Z | 2026-03-29T21:20:43Z | **UNCHANGED** |
| Ledger entries | 175 | 175 | **UNCHANGED** |
| Ledger unique shots | 33 | 33 | **UNCHANGED** |
| Ledger age | 13h 26m | 14h 26m | +60 min |
| First frames count | 59 | 59 | **UNCHANGED** |
| Video mp4 count (videos_kling_lite/) | 29 | 29 | **UNCHANGED** |
| Session enforcer passes | 69 | 69 | **UNCHANGED** |
| Session enforcer blocks | 0 | 0 | **UNCHANGED** |
| Learning log regressions | 0 | 0 | **UNCHANGED** |
| OPEN-004 consecutive count | 5 | 6 | +1 (CHRONIC-6) |
| OPEN-006 consecutive count | 3 | 4 | +1 (STALE_GATE_STATE-4) |
| OPEN-003 consecutive count | 6 | 7 | +1 (STALE_DOC-7) |
| OPEN-005 consecutive count | 4 | 5 | +1 (STALE_DOC-5) |
| OPEN-002 consecutive count | 6 | 7 | +1 (ARCH_DEBT-7) |
| New confirmed fixed | 0 | 0 | unchanged |
| New issues | 0 | 0 | unchanged |
| Clarifications | 0 | 1 | videos/ location clarification; gate_audit location clarification |

**Summary:** System has been production-idle for the entire R6→R7 interval (~60 minutes). No code changes, no generation activity, no new issues. All counters tick forward by 1. OPEN-004 is CHRONIC-6, escalating toward META-CHRONIC threshold (R11). Two minor clarifications added: `videos/` was already empty before R6 (R7 confirms), and `gate_audit.json` lives at `videos_kling_lite/gate_audit.json` (not project root).

---

## 9. DOCUMENT LINEAGE

- Prior report: **ATLAS_ERROR_DEEPDIVE_2026-03-30_R6_KEEPUP_LATEST.md** (2026-03-30T08:10:34Z)
- Prior proof gate: **NONE** (no proof-gate run has been executed)
- Delta since R6: 0 code changes. 0 new frames. 0 new videos. 0 new ledger entries. 2 clarifications.
- Report interval: ~59 minutes (R6→R7)
- Recommended next action: **Run scene 006 `--videos-only` to clear ledger contamination (OPEN-006). Apply OPEN-004 CPC fix (CHRONIC-6 — 7 lines, next session). Defer OPEN-003/005 doc fixes.**

---

## PROOF_GATE_FEED

```json
{
  "session_timestamp": "2026-03-30T09:10:20Z",
  "report_number": "R7",
  "prior_report": "ATLAS_ERROR_DEEPDIVE_2026-03-30_R6_KEEPUP_LATEST.md",
  "ledger_age_hours": 14.43,
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
  "videos_dir_clarification": "videos/ empty since 2026-03-28 — not a regression. Production mp4s in videos_kling_lite/ (29 files intact).",
  "session_enforcer_passes": 69,
  "session_enforcer_blocks": 0,
  "session_enforcer_status": "SYSTEM_HEALTHY",
  "vvo_wired": true,
  "vvo_call_site": "runner:3297",
  "confirmed_bugs": [
    {
      "id": "OPEN-004",
      "title": "CPC decontaminate_prompt() not called — description fallback instead of CPC replacement",
      "consecutive_reports": 6,
      "class": "CHRONIC",
      "escalation_note": "CHRONIC-6. META-CHRONIC threshold at 10 consecutive (R11). No current production blocker; 2 shots with null beat_action only.",
      "proof_receipt": "grep -n decontaminate_prompt atlas_universal_runner.py → no output; 013_M01/M02 _beat_action=None confirmed R7",
      "fix_recipe": "runner ~line 1117: import decontaminate_prompt from tools.creative_prompt_compiler; call with emotion + char; try/except safe fallback",
      "regression_guard": ["_beat_action primary path (~line 1113) unchanged", "_is_cpc_via_embedding detection (runner:1118) unchanged"],
      "impact": "LOW-MEDIUM — 2 shots affected; contained"
    }
  ],
  "stale_gate_state": [
    {
      "id": "OPEN-006",
      "title": "gate_audit.json stale (ORPHAN_SHOT) + 006 ledger contamination",
      "consecutive_reports": 4,
      "class": "STALE_GATE_STATE",
      "gate_audit_location": "pipeline_outputs/victorian_shadows_ep1/videos_kling_lite/gate_audit.json",
      "proof_receipt": "gate_audit.json at videos_kling_lite/: 4 ORPHAN_SHOT entries 006_M01-04 ts=2026-03-29T18:43:06 age=14h27m. Current shot_plan: 006_M01-04 all _chain_group=006_chain. Gate_audit is pre-fix artifact.",
      "resolution": "python3 atlas_universal_runner.py victorian_shadows_ep1 006 --mode lite --videos-only",
      "not_a_code_bug": true,
      "clarification_r7": "gate_audit location confirmed as videos_kling_lite/ (not project root as R6 implied)"
    }
  ],
  "architectural_debt": [
    {
      "id": "OPEN-002",
      "title": "9 un-normalized I>1.0 historical ledger entries",
      "consecutive_reports": 7,
      "class": "ARCHITECTURAL_DEBT",
      "note": "Latest-per-shot clean (0 I>1.0). Raw aggregate: 9. Historical artefacts from pre-normalization runs only."
    }
  ],
  "stale_docs": [
    {
      "id": "OPEN-003",
      "title": "Runner docstring lines 24/39 say Seedance PRIMARY",
      "consecutive_reports": 7,
      "class": "STALE_DOC",
      "lines": [24, 39]
    },
    {
      "id": "OPEN-005",
      "title": "Wire-B QUALITY GATE logic unlabelled at line 5339",
      "consecutive_reports": 5,
      "class": "STALE_DOC",
      "note": "Wire B in line 9 header. [WIRE-B] label absent from implementation. Logic healthy."
    }
  ],
  "false_positives_retracted": [],
  "confirmed_fixed_new_this_session": [],
  "clarifications_this_session": [
    "videos/ directory: empty since 2026-03-28 (mtime confirmed). Not a regression. R6 '29 mp4s' was videos_kling_lite count.",
    "gate_audit.json location: videos_kling_lite/gate_audit.json (not project root). 006 shot_plan chain_groups correct."
  ],
  "organ_health": {
    "skeleton": "HEALTHY — isinstance guard runner:1433/1470; shot_plan mtime unchanged; 006 chain_groups correct",
    "liver": "DEGRADED — detection OK; decontaminate_prompt replacement absent (OPEN-004 CHRONIC-6)",
    "immune": "DEGRADED — runner header V31.0/Seedance docstring (OPEN-003 STALE_DOC-7); code correct",
    "nervous": "HEALTHY — session_enforcer SYSTEM HEALTHY, 69 passes, 0 blocks",
    "eyes": "HEALTHY — all 5 env keys PRESENT; VVO confirmed runner:3297; 4 backends active",
    "cortex": "DEGRADED — 70% I=0.75 heuristic (latest); 4 contaminated 006 entries (OPEN-006 STALE_GATE_STATE-4)",
    "cinematographer": "HEALTHY — run_report success=True; 59 frames, 29 videos_kling_lite mp4s; VVO active",
    "editor": "HEALTHY — Wire-B logic at runner:5339; Wire-C runner:5090 5 occurrences",
    "regenerator": "HEALTHY — Wire-C confirmed runner:5090",
    "doctrine_doc": "DEGRADED — version drift V31.0/V36.5; Seedance docstring (lines 24/39); Wire-B label absent"
  },
  "recommended_next_action": "run_scene_006_videos_only_then_fix_open_004_CPC_next_session",
  "system_production_ready": true,
  "blocker_count": 0,
  "chronic_bug_count": 1,
  "system_delta_from_prior": "IDLE — no code changes, no generation activity, no new ledger entries in ~60-minute R6→R7 window",
  "note": "Steady-state report. System idle since R6. OPEN-004 CHRONIC-6 is the only active code task. Scene 006 --videos-only recommended for ledger hygiene. Two clarifications: videos/ empty since 2026-03-28 (non-issue), gate_audit.json in videos_kling_lite/ (location clarified)."
}
```

---

*ATLAS Keep-Up R7 — 2026-03-30T09:10:20Z*
*Detection layer: REPORT only — no production files modified*
*Open issues: OPEN-004 (CHRONIC-6), OPEN-006 (STALE_GATE_STATE-4), OPEN-003 (STALE_DOC-7), OPEN-005 (STALE_DOC-5), OPEN-002 (ARCH_DEBT-7)*
*Confirmed fixed: 19 items — all intact*
*System production-ready. No blocking issues. Production idle 14h 26m.*
*Key delta from R6: NONE — system unchanged. All open-issue counters +1. Two clarifications added.*
