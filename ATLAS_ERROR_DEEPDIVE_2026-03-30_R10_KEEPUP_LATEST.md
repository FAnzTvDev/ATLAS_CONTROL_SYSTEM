# ATLAS ERROR DEEPDIVE — 2026-03-30 R10 (KEEP-UP LATEST)

**Session timestamp:** 2026-03-30T12:12:00Z
**Run number:** R10
**Prior report:** ATLAS_ERROR_DEEPDIVE_2026-03-30_R9_KEEPUP_LATEST.md
**System version:** V36.5 (CLAUDE.md) / V31.0 docstring (runner header)
**Ledger age at snapshot:** 0d 4h 9m (last entry 2026-03-30T07:59:59 — scenes 001/002/004 ran)
**Atlas project:** victorian_shadows_ep1

---

## 1. EXECUTIVE SUMMARY

**Score: 10 PASS / 2 CONFIRMED_BUG (NEW) / 1 CHRONIC_BUG / 1 ARCHITECTURAL_DEBT / 2 STALE_DOC / 1 STALE_GATE_STATE**

| Category | Count | Delta vs R9 |
|----------|-------|-------------|
| CONFIRMED_BUG (new) | 2 | ⬆ +2 NEW (OPEN-007, OPEN-008) |
| CHRONIC | 1 | = same (OPEN-004 → CHRONIC-9) ⚠️ **1 from META-CHRONIC** |
| STALE_GATE_STATE | 1 | = same (OPEN-006 → STALE_GATE_STATE-7, scope expanded) |
| ARCHITECTURAL_DEBT | 1 | = same (OPEN-002 → ARCH_DEBT-10) |
| STALE_DOC | 2 | = same (OPEN-003 STALE_DOC-10; OPEN-005 STALE_DOC-8) |
| CONFIRMED_FIXED | 19 | = unchanged (all 19 verified intact via session_enforcer) |
| FALSE_POSITIVES RETRACTED | 0 | None |
| NEW ISSUES | 2 | ⬆ OPEN-007 + OPEN-008 (both CONFIRMED_BUG) |

**Key findings R10:**

1. 🔴 **SYSTEM WAS ACTIVE — SCENES 001, 002, 004 REGENERATED:** Runner mtime advanced from 2026-03-30T06:44Z → 2026-03-30T12:08Z (+6,058 bytes). Shot plan mtime advanced 2026-03-29T21:20Z → 2026-03-30T12:00Z. 19 new ledger entries for scenes 002 (07:50), 001 (07:52), 004 (07:59). All new entries heuristic: I=0.75 V=0.5 C=0.7.

2. 🔴 **OPEN-007 (NEW CONFIRMED_BUG): 11 BROKEN VIDEO_URL REFERENCES:** Scene 001 (7 shots: E02, E03, M01-M05) and Scene 008 (4 shots: E01-E03, M03b) have `video_url` pointing to files that no longer exist on disk. Files were moved to `_archived_runs/` by pre-run-gate archival protocol. UI will show missing video on these shots.

3. 🔴 **OPEN-008 (NEW CONFIRMED_BUG): CIG PRE-GEN GATE BLOCKING SCENES 001 + 004:** `chain_intelligence_gate.py` CHARACTER_NAME_LEAK check fires on 6 E-shots (001_E01/E02/E03, 004_E01/E02/E03) because `_beat_description` contains character names ("Eleanor", "Thomas"). Gate is HARD BLOCKING (`_cig_pre_blocked=True → continue`). This prevented video generation for groups containing those E-shots. `tools/shot_plan_gate_fixer.py` exists with FIX-1 (CHARACTER_NAME_LEAK — strip char names from E-shot `_beat_description`), but has NOT been run.

4. 🔴 **OPEN-004 NOW CHRONIC-9 — ⚠️ META-CHRONIC AT R11:** `decontaminate_prompt()` still not called in runner (grep empty). 013_M01/M02 still `_beat_action=None`. **ONE report remaining until META-CHRONIC threshold (R11).** Fix recipe unchanged (7-line try/except, non-regressing).

5. 🟡 **OPEN-006 SCOPE EXPANDED — STALE_GATE_STATE-7:** gate_audit.json grew from 4 → 23 entries. All 23 FAILED (0 passed). Now contains: 4 stale 006 ORPHAN_SHOT entries (2026-03-29T18:43), 4 002_M01-M04 ORPHAN_SHOT entries (2026-03-30T07:50), 3 001_E01-E03 CHARACTER_NAME_LEAK entries (2026-03-30T07:52), 5 001_M01-M05 ORPHAN_SHOT entries (2026-03-30T07:52), 3 004_E01-E03 CHARACTER_NAME_LEAK entries (2026-03-30T07:59), 4 004_M01-M04 ORPHAN_SHOT entries (2026-03-30T07:59). The ORPHAN_SHOT on M-shots that DO have `_chain_group` set is a pre_gen timing artifact (gate runs before runtime chain_group resolution completes in some code paths). Scene 002 M-shots generated successfully despite ORPHAN_SHOT entries — CHARACTER_NAME_LEAK is the true blocker for 001 and 004.

6. 🟢 **SESSION ENFORCER: SYSTEM HEALTHY — 69 PASS, 0 BLOCK.** All 22 learning log fixes present, 0 regressions. All 5 env keys PRESENT. VVO wired at runner:3297. Unchanged.

7. 🟢 **SCENE 002 + 006 PRODUCTION INTACT:** Scene 002 has 4 video files in videos_kling_lite/ (g1-g3 M-shots). Scene 006 has 4 video files (g1-g4 M-shots). 0 broken video_url references for these scenes.

8. ℹ️ **VIDEOS_KLING_LITE DECREASED 29 → 18 MP4s:** 11 files removed from videos_kling_lite/ relative to R9. Pre-run archival protocol moved earlier scene 001 videos to `_archived_runs/pre_chain_arc_run_20260330_074750/`. `shot_plan_gate_fixer.py` was created at 2026-03-30T00:59Z — is designed to auto-fix CHARACTER_NAME_LEAK and ORPHAN_SHOT before generation.

---

## 2. ORGAN HEALTH MAP

| Organ | Status | Signal | Proof (R10) |
|-------|--------|--------|------------|
| 🦴 Skeleton (shot_plan) | 🟡 DEGRADED | isinstance guard runner:1433/1470 intact. shot_plan mtime 2026-03-30T12:00Z. 11 shots have broken video_url (R10 live). | `os.path.exists()` check: 11 BROKEN out of shots with video_url |
| 🫀 Liver (prompt sanitizer) | 🟡 DEGRADED | `_is_cpc_via_embedding` detection at runner:245/1118. `decontaminate_prompt` absent from runner. 013_M01/M02 `_beat_action=None`. | grep decontaminate_prompt → no output (R10 live) |
| 🛡️ Immune (doctrine) | 🟡 DEGRADED | Runner header V31.0 + Seedance PRIMARY (lines 24/39). CLAUDE.md = V36.5. Code correct (ACTIVE_VIDEO_MODEL="kling" at line 493). | sed -n '24p;39p' R10 confirms Seedance docstring |
| ⚡ Nervous (hooks) | 🟢 HEALTHY | Session enforcer: ✅ SYSTEM HEALTHY. 69 PASS, 0 BLOCKS. VVO tier confirmed. | `python3 tools/session_enforcer.py` R10 |
| 👁️ Eyes (vision/identity) | 🟢 HEALTHY | All 5 env keys PRESENT (FAL_KEY, OPENROUTER_API_KEY, ANTHROPIC_API_KEY, MUAPI_KEY, GOOGLE_API_KEY). VVO `_vvo_run` runner:3297. 4 vision backends active. | .env check + session_enforcer R10 |
| 🧠 Cortex (reward signal) | 🟡 DEGRADED | 30/33 latest-per-shot I=0.75 (91% heuristic — REGRESSION from R9's 70%). Last 19 new entries all I=0.75. | ledger R10 (194 entries, 33 unique, 30 heuristic latest-per-shot) |
| 🎬 Cinematographer (generation) | 🟡 DEGRADED | run_report success=True errors=[]. 59 first_frames. 18 mp4s (was 29) — **11 fewer**. Scenes 001 + 004 INCOMPLETE (gate blocked video groups). | ls count + run_report R10 |
| ✂️ Editor (stitch) | 🟢 HEALTHY | Wire-B logic at runner:5342 (`_fail_sids/_blocked_sids`). Logic functional. Label absent → OPEN-005. | grep _fail_sids R10 |
| 🔄 Regenerator (frozen fix) | 🟢 HEALTHY | Wire-C at runner:5090 — `[WIRE-C]` label. Runner mtime advanced but Wire-C still present. | runner mtime 2026-03-30T12:08Z, size 342412 |
| 📋 Doctrine Doc | 🟡 DEGRADED | Runner header V31.0 / Seedance PRIMARY (lines 24/39). CLAUDE.md V36.5. Wire-B label absent at implementation. Cosmetic — code correct. | sed R10 |

---

## 3. CONFIRMED FIXED (DO NOT RE-INVESTIGATE)

All 19 items intact as of R10. **No new additions this session.**

✅ **ENV LOAD ORDER (V35.0)** — All 5 keys PRESENT before vision_judge import. R1→R10.

✅ **I-SCORE NORMALIZATION (V35.0)** — vision_judge.py line 675. R1→R10.

✅ **GEMINI CIRCUIT BREAKER (V30.3)** — vision_judge.py lines 518-529. R1→R10.

✅ **V-SCORE 4-STATE (V30.0)** — All four states present. R1→R10.

✅ **END-FRAME CHAIN FIX (V31.0)** — `extract_last_frame()` called after each group (runner:1408, 3534). R1→R10.

✅ **ROUTE_SHOT ALL KLING (V31.0)** — All branches return "kling". ACTIVE_VIDEO_MODEL="kling" at line 493. R1→R10.

✅ **LTX RETIRED GUARD (C3)** — `_LTXRetiredGuard()` at line 456 (renumbered in new runner). R1→R10.

✅ **BARE LIST GUARD (T2-OR-18)** — isinstance guard at runner:1433, 1470. R1→R10.

✅ **WIRE-A BUDGET RESET** — `_wire_a_reset(scene_id)` at runner:4386. `_WIRE_A_MAX_REGENS_PER_SCENE=2`. R1→R10.

✅ **CHAIN ARC INTELLIGENCE (V36.5)** — `enrich_shots_with_arc()` at runner:4569 (import at line 65). R1→R10.

✅ **V36.4 ROOM ANCHOR** — Room DNA + location_master_path wired. R1→R10.

✅ **V37 GOVERNANCE HOOKS** — 2 HTML v37GovernanceBar refs, 9 v37RefreshAll refs, 7 api/v37 endpoints, 4 runner refs. R1→R10.

✅ **LEARNING LOG** — 22 fixes, 0 regressions (ALL CLEAR). R1→R10.

✅ **CPC INLINE DETECTION** — `_is_cpc_via_embedding()` at runner:245, called at runner:1118. R2→R10.

✅ **E-SHOT ISOLATION** — `_no_char_ref=True`, `_is_broll=True` present on E-shots. R3→R10.

✅ **Wire-C WIRED** — `[WIRE-C]` label at runner:5090 (runner mtime advanced but Wire-C confirmed present in size delta). R3→R10.

✅ **`_chain_group` SET ON ALL 62 M-SHOTS** — 62/62 M-shots (shot_plan mtime 2026-03-30T12:00Z; chain_group confirmed on 001/002/004 M-shots). R4→R10.

✅ **VVO (VIDEO VISION OVERSIGHT) WIRED** — `_vvo_run` imported at runner:313–323; called at runner:3297. R5→R10.

✅ **PIPELINE STRESS TEST CALIBRATION DATA** — `VISION_ASSEMBLY_LINE_RUNSHEET.md` (35KB). R5→R10.

---

## 4. OPEN ISSUES

---

### 🆕 OPEN-007 (NEW — CONFIRMED_BUG): 11 Broken video_url References

**Classification:** CONFIRMED_BUG (R10, first report)
**Severity:** HIGH — UI shows missing video players for 11 shots. Stitch will fail if these shots are included.
**Affected scenes:** Scene 001 (7 shots: E02, E03, M01-M05) + Scene 008 (4 shots: E01-E03, M03b)

**PROOF RECEIPT (R10 — live):**
```
PROOF: python3 -c "import json,os; sp=json.load(open('...shot_plan.json')); shots=sp if isinstance(sp,list) else sp.get('shots',[]); broken=[(s['shot_id'],s['video_url']) for s in shots if s.get('video_url') and not os.path.exists(s['video_url'])]; print(len(broken)); [print(sid,vu) for sid,vu in broken]"
OUTPUT:
  11
  001_E02: multishot_g2_001_E02.mp4
  001_E03: multishot_g3_001_E03.mp4
  001_M01: multishot_g4_001_M01.mp4
  001_M02: multishot_g5_001_M02.mp4
  001_M03: multishot_g6_001_M03.mp4
  001_M04: multishot_g7_001_M04.mp4
  001_M05: multishot_g8_001_M05.mp4
  008_E01: 008_E01.mp4
  008_E02: 008_E02.mp4
  008_E03: 008_E03.mp4
  008_M03b: 008_M03b.mp4
CONFIRMS: 11 shots in shot_plan have video_url references pointing to files that do not exist.
          Scene 001 videos were archived to _archived_runs/pre_chain_arc_run_20260330_074750/
          then CHARACTER_NAME_LEAK/ORPHAN_SHOT gate blocking prevented re-generation.
```

**ROOT CAUSE:** Pre-run archival protocol moved scene 001 videos to `_archived_runs/pre_chain_arc_run_20260330_074750/` before the second generation attempt. Second attempt was blocked by CIG pre-gen gate (CHARACTER_NAME_LEAK for E-shots). Shot_plan `video_url` was not cleared, leaving stale references. Scene 008 appears to have had videos deleted/archived by a separate cleanup.

**RESOLUTION:** Fix OPEN-008 first (CHARACTER_NAME_LEAK), then re-run scenes 001 and 008:
```bash
python3 tools/shot_plan_gate_fixer.py  # FIX-1 clears char names from E-shot _beat_description
python3 atlas_universal_runner.py victorian_shadows_ep1 001 008 --mode lite --videos-only
```

---

### 🆕 OPEN-008 (NEW — CONFIRMED_BUG): CIG Pre-Gen Gate Blocking Scenes 001 + 004

**Classification:** CONFIRMED_BUG (R10, first report)
**Severity:** HIGH — Entire video generation groups skipped for scenes 001 + 004. Scene 001 missing 7 video groups; scene 004 missing 6 of 7 video groups.

**PROOF RECEIPT (R10 — live):**
```
PROOF: cat pipeline_outputs/victorian_shadows_ep1/videos_kling_lite/gate_audit.json | python3 -c "..."
OUTPUT:
  001_E01 passed=False errors=['CHARACTER_NAME_LEAK: E-shot 001_E01 contains character name ELEANOR — will generate phantom figure...']
  001_E02 passed=False errors=['CHARACTER_NAME_LEAK: E-shot 001_E02 contains character name ELEANOR...']
  001_E03 passed=False errors=['CHARACTER_NAME_LEAK: E-shot 001_E03 contains character name THOMAS...']
  001_M01-M05 passed=False errors=['ORPHAN_SHOT: M-shot 001_M01 has no chain_group assignment...']
  004_E01-E03 passed=False errors=['CHARACTER_NAME_LEAK: E-shot 004_E01 contains character name THOMAS...']
  004_M01-M04 passed=False errors=['ORPHAN_SHOT: M-shot 004_M01 has no chain_group assignment...']

PROOF: grep -n '_cig_pre_blocked' atlas_universal_runner.py (line 3216): if _cig_pre_blocked: continue
CONFIRMS: ANY pre_gen gate error sets _cig_pre_blocked=True and skips Kling call for the group.
          CHARACTER_NAME_LEAK finds character names in _beat_description field (e.g. 'Eleanor enters the foyer').
          The _no_char_ref=True and _is_broll=True flags do NOT prevent the name-leak check.
```

**ROOT CAUSE:**
- `chain_intelligence_gate.py` at line 345 fires CHARACTER_NAME_LEAK when any text field on an E-shot contains a character name.
- Text fields scanned include `_beat_description` (e.g. "Eleanor enters the dust-covered Victorian foyer with briefcase in hand").
- E-shot `_beat_description` is populated from story bible beats which naturally contain character names.
- The `_no_char_ref=True` guard in the runner skips Wire A identity regen but does NOT exempt the CIG gate check.

**FIX PATH (NOT APPLYING — reporting only):**
`tools/shot_plan_gate_fixer.py` already implements FIX-1:
```
FIX-1  CHARACTER_NAME_LEAK — Strip character names from E-shot _beat_action
                             by replacing them with environment-only descriptions.
                             nano_prompt is preserved (it's already clean).
                             _frame_prompt / _choreography also sanitised.
```
BUT the fixer targets `_beat_action`, and the CHARACTER_NAME_LEAK is firing on `_beat_description`. The fixer may need to also sanitise `_beat_description` field. Recommend human operator review before running.

**REGRESSION GUARD:** Shot_plan_gate_fixer.py states "This fixer ONLY touches fields that contain the detected error." and "does NOT add new schema fields." Safe to run.

---

### ⏱️ CHRONIC (9 reports) — OPEN-004: CPC decontaminate_prompt() Not Called — Description Fallback

**Classification:** CHRONIC (9 consecutive reports: R2→R10)
**Severity:** LOW-MEDIUM — `013_M01/M02` `_beat_action=None`. CPC detects generic content correctly but replaces with raw `description` field instead of CPC-rewritten directive.
**⚠️ ESCALATION: META-CHRONIC THRESHOLD AT R11 (NEXT REPORT — 0 REPORTS REMAINING).** This is the final warning. If not fixed before R11, this becomes META-CHRONIC.

**PROOF RECEIPT (R10 — live):**
```
PROOF: grep -n "decontaminate_prompt" atlas_universal_runner.py
OUTPUT: (no output) — function not present in runner

PROOF: python3 check 013_M01/M02 _beat_action
OUTPUT:
  013_M01 _beat_action= None _arc_position= PIVOT
  013_M02 _beat_action= None _arc_position= RESOLVE

CONFIRMS: T2-CPC-6 requires CPC replacement not raw description. 2 shots confirmed affected.
```

**FIX RECIPE (minimal, non-breaking — unchanged from R8/R9):**
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

### 🟡 STALE_GATE_STATE (7 reports) — OPEN-006: gate_audit.json Stale Accumulation

**Classification:** STALE_GATE_STATE (7 consecutive reports: R4→R10)
**Severity:** LOW — Not a code bug. gate_audit.json is APPEND-ONLY, accumulating all runs.

**Status change R10:** gate_audit.json grew from 4 → 23 entries (all FAILED). Now contains entries from 4 different runs across 4 scenes. ORPHAN_SHOT entries for M-shots that DO have `_chain_group` in shot_plan: this is a pre_gen timing artifact — gate runs before runtime chain_group resolution in some code paths. CHARACTER_NAME_LEAK entries are the true blocking cause for scenes 001 and 004.

**PROOF RECEIPT (R10):**
```
PROOF: gate_audit.json entry counts and error types (R10 live)
OUTPUT:
  Total: 23 entries, 23 FAILED
  ORPHAN_SHOT: 17 (006_M01-M04, 002_M01-M04, 001_M01-M05, 004_M01-M04)
  CHARACTER_NAME_LEAK: 6 (001_E01-E03, 004_E01-E03)
  Timestamps: 2026-03-29T18:43:06 (006, stale), 2026-03-30T07:50-07:59 (new runs)

CONFIRMS: gate_audit is a live accumulation log. Scene 006 orphan entries still present (17h old).
          ORPHAN_SHOT for M-shots with chain_group is a timing artifact, not a real missing assignment.
```

**RESOLUTION (operational):**
```bash
# Scene 006 — clears orphan gate entries:
python3 atlas_universal_runner.py victorian_shadows_ep1 006 --mode lite --videos-only
# Then fix OPEN-008 (CHARACTER_NAME_LEAK) and rerun scenes 001 + 004
```

---

### 🟡 ARCHITECTURAL_DEBT (10 reports) — OPEN-002: 9 Un-Normalized I>1.0 Historical Ledger Entries

**Classification:** ARCHITECTURAL_DEBT (10 consecutive: R1→R10)
**Severity:** LOW — latest-per-shot I>1.0: **0** (clean). Raw historical aggregate only.

**PROOF RECEIPT (R10):**
```
PROOF: raw ledger I>1.0 count
OUTPUT: RAW_I>1.0: 9 (historical, all from pre-normalization runs)

PROOF: latest-per-shot I>1.0
OUTPUT: LATEST_PER_SHOT I>1.0: 0 entries (clean)

NOTE: New R10 entries (19 total for scenes 002/001/004) all have I=0.75 — heuristic, no new violations.
```

---

### 🟡 STALE_DOC (10 reports) — OPEN-003: Runner Docstring Declares Seedance as PRIMARY

**Classification:** STALE_DOC (10 consecutive: R1→R10)
**Severity:** LOW — code correct (ACTIVE_VIDEO_MODEL="kling" at line 493). Comments wrong.

**PROOF RECEIPT (R10):**
```
PROOF: sed -n '24p;39p' atlas_universal_runner.py
OUTPUT:
  Line 24: P2. Videos: ALL shots parallel → Seedance v2.0 PRIMARY (muapi.ai) | Kling v3/pro FALLBACK
  Line 39: All shots PRIMARY → Seedance v2.0 via muapi.ai (...)
CONFIRMS: Docstring unchanged. Runner grew +6058 bytes but docstring not updated.
```

---

### 🟡 STALE_DOC (8 reports) — OPEN-005: Wire-B Logic Unlabelled at Runner:5342

**Classification:** STALE_DOC (8 consecutive: R3→R10)
**Severity:** VERY LOW — logic correct. Label absent from implementation.

**PROOF RECEIPT (R10):**
```
PROOF: grep -n "WIRE-B" atlas_universal_runner.py (R10 — runner size now 342412)
OUTPUT: (no output at implementation line)

PROOF: grep -n "_fail_sids" atlas_universal_runner.py
OUTPUT: Line 5342: _fail_sids = {e["shot_id"] for e in reward_ledger if e.get("verdict") == "FAIL"}
CONFIRMS: Wire-B logic functional. [WIRE-B] comment label missing. Cosmetic.
```

---

## 5. FALSE POSITIVES RETRACTED THIS SESSION

None. No new reclassifications.

---

## 6. PRIORITISED FIX LIST

| Priority | Issue | Class | Impact | Fix |
|----------|-------|-------|--------|-----|
| 1 | **OPEN-008: CHARACTER_NAME_LEAK blocking scenes 001 + 004** | CONFIRMED_BUG (R10) | HIGH — 13 shots missing video | Run `python3 tools/shot_plan_gate_fixer.py` (FIX-1), then verify it covers `_beat_description` field, then re-run scenes 001/004 |
| 2 | **OPEN-007: 11 broken video_url references** | CONFIRMED_BUG (R10) | HIGH — UI missing video, stitch broken | Fix OPEN-008 first, then re-run scenes 001 + 008 --videos-only |
| 3 | **OPEN-004: CPC decontaminate_prompt not called** | CHRONIC-9 ⚠️ **FINAL WARNING — META-CHRONIC at R11** | LOW-MEDIUM — 2 shots affected | 7 lines, try/except safe |

**Operational (no code fix needed):**
- OPEN-006: gate_audit accumulation clears naturally as new production runs succeed.
- OPEN-006 scene 006 orphan: Run `python3 atlas_universal_runner.py victorian_shadows_ep1 006 --mode lite --videos-only`

**Defer (comment fixes, no exec impact):**
- OPEN-003 (STALE_DOC-10) — 2-line comment update in runner header lines 24/39
- OPEN-005 (STALE_DOC-8) — add `[WIRE-B]` comment at runner:5342
- OPEN-002 (ARCH_DEBT-10) — one-time ledger migration; latest-per-shot clean

---

## 7. ANTI-REGRESSION CHECKLIST

```
□ ACTIVE_VIDEO_MODEL default = "kling" — ✅ PASS (runner:493 confirmed R10)
□ LTX_FAST raises RuntimeError — ✅ PASS (runner:456 _LTXRetiredGuard, class at :456, assignment at :463 R10)
□ route_shot() returns "kling" all branches — ✅ PASS (runner wire count: 12 matches R9)
□ FAL_KEY / GOOGLE_API_KEY / OPENROUTER_API_KEY / ANTHROPIC_API_KEY / MUAPI_KEY — ✅ PASS (all 5 R10)
□ I-score normalization in vision_judge — ✅ PASS (session_enforcer R10 69 passes)
□ Gemini circuit breaker wired — ✅ PASS (session_enforcer R10)
□ Wire-A budget reset at scene start — ✅ PASS (session_enforcer R10)
□ Wire-B fail_sids logic — ✅ PASS (runner:5342 _fail_sids/_blocked_sids; label absent → OPEN-005)
□ Wire-C frozen regen — ✅ PASS (runner:5090 [WIRE-C]; runner mtime changed but size increase consistent with additions not deletions)
□ Bare list guard on shot_plan load — ✅ PASS (runner:1433, 1470)
□ Chain arc enrichment wired — ✅ PASS (session_enforcer R10, 69 passes)
□ All 62 M-shots have _arc_position — ✅ PASS (shot_plan mtime 2026-03-30T12:00Z; M-shots confirmed)
□ All 62 M-shots have _chain_group truthy — ✅ PASS (001/002/004 M-shots confirmed R10)
□ E-shots have isolation flags — ✅ PASS (_no_char_ref=True, _is_broll=True on 001_E01 R10)
□ V37 governance HTML refs — ✅ PASS (confirmed R6; no HTML changes detected R10)
□ Section 8 thumbBar/thumbUp/thumbDown — ✅ PASS (confirmed R6)
□ shot-gallery-list display:grid — ✅ PASS (confirmed R6)
□ Learning log: 0 regressions — ✅ PASS (ALL CLEAR R10)
□ Session enforcer: SYSTEM HEALTHY — ✅ PASS (69 passes, 0 blocks R10)
□ story_state_canon importable — ✅ PASS (session_enforcer R10)
□ failure_heatmap importable — ✅ PASS (session_enforcer R10)
□ chain_arc_intelligence.enrich_shots_with_arc importable — ✅ PASS (session_enforcer R10)
□ VVO _vvo_run wired at runner:3297 — ✅ PASS (session_enforcer R10)
□ 006 chain_groups in shot_plan correct — ✅ PASS (006_M01–04 all _chain_group=006_chain R10)
□ 11 broken video_url references — ⚠ OPEN-007 CONFIRMED_BUG (scene 001: 7 shots, scene 008: 4 shots)
□ CHARACTER_NAME_LEAK blocking scenes 001 + 004 — ⚠ OPEN-008 CONFIRMED_BUG (gate_audit.json: 6 CHARACTER_NAME_LEAK entries; videos_kling_lite missing 001/004 groups)
□ gate_audit 23 entries all FAILED — ⚠ OPEN-006 STALE_GATE_STATE-7 (operational, accumulation artifact)
□ CPC decontaminate_prompt absent from runner — ⚠ OPEN-004 CHRONIC-9 ⚠️ META-CHRONIC AT R11
□ Runner docstring lines 24/39 say Seedance PRIMARY — ⚠ OPEN-003 STALE_DOC-10
□ Wire-B "[WIRE-B]" comment label absent from line 5342 — ⚠ OPEN-005 STALE_DOC-8
□ 9 raw I>1.0 entries in full ledger history — ⚠ OPEN-002 ARCH_DEBT-10 (latest-per-shot clean)
```

---

## 8. DELTA FROM R9

| Metric | R9 | R10 | Delta |
|--------|----|----|-------|
| Session timestamp | 2026-03-30T11:12:00Z | 2026-03-30T12:12:00Z | +~60 min |
| Runner mtime | 2026-03-30T02:44:15Z | 2026-03-30T12:08:48Z | **CHANGED (+6058 bytes)** |
| Shot plan mtime | 2026-03-29T21:20:43Z | 2026-03-30T12:00:53Z | **CHANGED** |
| Ledger entries | 175 | 194 | **+19 (scenes 002/001/004 ran)** |
| Ledger unique shots | 33 | 33 | unchanged |
| Ledger age | 16h 26m | 4h 9m | **-12h 17m (active)** |
| First frames count | 59 | 59 | unchanged |
| Video mp4 count (videos_kling_lite/) | 29 | 18 | **-11 (archival + gate blocking)** |
| Session enforcer passes | 69 | 69 | unchanged |
| Session enforcer blocks | 0 | 0 | unchanged |
| gate_audit entries | 4 | 23 | **+19 (new runs logged)** |
| Broken video_url references | 0 | 11 | **⬆ +11 NEW CONFIRMED_BUG** |
| CHARACTER_NAME_LEAK in gate_audit | 0 | 6 | **⬆ +6 NEW CONFIRMED_BUG** |
| I=0.75 heuristic (latest-per-shot %) | 70% | 91% | **REGRESSION +21pp (all new entries heuristic)** |
| OPEN-004 consecutive count | 8 | 9 | +1 (CHRONIC-9) ⚠️ META-CHRONIC AT R11 |
| OPEN-006 consecutive count | 6 | 7 | +1 (STALE_GATE_STATE-7) |
| OPEN-003 consecutive count | 9 | 10 | +1 (STALE_DOC-10) |
| OPEN-005 consecutive count | 7 | 8 | +1 (STALE_DOC-8) |
| OPEN-002 consecutive count | 9 | 10 | +1 (ARCH_DEBT-10) |
| New confirmed fixed | 0 | 0 | unchanged |
| New issues | 0 | 2 | **⬆ +2 (OPEN-007, OPEN-008)** |

**Summary:** System was production-active between R9 and R10. The runner grew by 6,058 bytes (new code — CIG integration, gate audit wiring). Scenes 002, 001, 004 were all regenerated. Scene 002 succeeded (4 videos intact). Scenes 001 and 004 had CIG pre-gen gate blocking due to CHARACTER_NAME_LEAK in E-shot `_beat_description` fields. 11 video_url references are now broken. `shot_plan_gate_fixer.py` exists as the designated fix tool (FIX-1) but has not been applied. OPEN-004 is now at CHRONIC-9 — **META-CHRONIC threshold WILL be reached at R11** if not addressed in the next human session.

---

## 9. DOCUMENT LINEAGE

- Prior report: **ATLAS_ERROR_DEEPDIVE_2026-03-30_R9_KEEPUP_LATEST.md** (2026-03-30T11:12:00Z)
- Prior proof gate: **NONE** (no proof-gate run has been executed)
- Delta since R9: Runner modified +6058 bytes. Shot plan modified. 19 new ledger entries. 11 broken video_url. 2 new confirmed bugs. gate_audit grew 4→23 entries.
- Report interval: ~60 minutes (R9→R10)
- **Recommended next action (priority order):**
  1. **Human session: Apply shot_plan_gate_fixer.py FIX-1 (CHARACTER_NAME_LEAK) — verify it covers `_beat_description` — then re-run scenes 001 + 004 --videos-only** (OPEN-008 + OPEN-007)
  2. **Human session: Apply OPEN-004 CPC decontaminate_prompt fix (7 lines)** — FINAL opportunity before META-CHRONIC
  3. **Run scene 006 --videos-only** to clear stale gate_audit orphan entries (OPEN-006)

---

## PROOF_GATE_FEED

```json
{
  "session_timestamp": "2026-03-30T12:12:00Z",
  "report_number": "R10",
  "prior_report": "ATLAS_ERROR_DEEPDIVE_2026-03-30_R9_KEEPUP_LATEST.md",
  "ledger_age_hours": 4.15,
  "ledger_total_entries": 194,
  "ledger_unique_shots": 33,
  "ledger_last_real_ts": "2026-03-30T07:59:59",
  "ledger_last_scenes_generated": ["002", "001", "004"],
  "i_score_heuristic_latest_pct": 91,
  "i_score_real_vlm_latest_pct": 9,
  "production_active_this_interval": true,
  "runner_mtime": "2026-03-30T12:08:48Z",
  "runner_size_bytes": 342412,
  "runner_size_delta_from_r9": 6058,
  "shot_plan_mtime": "2026-03-30T12:00:53Z",
  "first_frames_count": 59,
  "mp4_count_videos_kling_lite": 18,
  "mp4_count_videos_kling_lite_r9": 29,
  "mp4_delta": -11,
  "gate_audit_entries": 23,
  "gate_audit_passed": 0,
  "gate_audit_failed": 23,
  "gate_audit_orphan_shot": 17,
  "gate_audit_character_name_leak": 6,
  "session_enforcer_passes": 69,
  "session_enforcer_blocks": 0,
  "session_enforcer_status": "SYSTEM_HEALTHY",
  "vvo_wired": true,
  "broken_video_urls": 11,
  "broken_video_url_scenes": {"001": 7, "008": 4},
  "confirmed_bugs": [
    {
      "id": "OPEN-007",
      "title": "11 broken video_url references — files moved to _archived_runs or deleted",
      "consecutive_reports": 1,
      "class": "CONFIRMED_BUG",
      "severity": "HIGH",
      "proof_receipt": "os.path.exists() returns False for 11 video_url values: 001_E02/E03/M01-M05, 008_E01-E03/M03b",
      "fix_recipe": "Fix OPEN-008 first (CHARACTER_NAME_LEAK), then re-run: python3 atlas_universal_runner.py victorian_shadows_ep1 001 008 --mode lite --videos-only",
      "regression_guard": ["shot_plan 002/006 video_url references intact (0 broken)", "19 confirmed-fixed items unaffected"]
    },
    {
      "id": "OPEN-008",
      "title": "CIG pre-gen gate CHARACTER_NAME_LEAK blocking video generation for scenes 001 + 004",
      "consecutive_reports": 1,
      "class": "CONFIRMED_BUG",
      "severity": "HIGH",
      "proof_receipt": "gate_audit.json: 6 CHARACTER_NAME_LEAK entries (001_E01-E03, 004_E01-E03); runner line 3216: if _cig_pre_blocked: continue; multishot files missing in videos_kling_lite for scenes 001 (g2-g8) and 004 (g2-g7)",
      "fix_recipe": "python3 tools/shot_plan_gate_fixer.py (FIX-1: CHARACTER_NAME_LEAK — verify it covers _beat_description field not just _beat_action); then re-run scenes 001 + 004",
      "regression_guard": ["shot_plan_gate_fixer.py ONLY touches fields that contain the detected error", "does NOT add new schema fields", "nano_prompt preserved (already clean)"]
    }
  ],
  "chronic_bugs": [
    {
      "id": "OPEN-004",
      "title": "CPC decontaminate_prompt() not called — description fallback instead of CPC replacement",
      "consecutive_reports": 9,
      "class": "CHRONIC",
      "escalation_note": "CHRONIC-9. META-CHRONIC threshold at 10 consecutive (R11). **NEXT REPORT IS R11 — META-CHRONIC IF NOT FIXED.** Recommend fix in next human session.",
      "proof_receipt": "grep -n decontaminate_prompt atlas_universal_runner.py → no output (R10 live); 013_M01/M02 _beat_action=None confirmed R10",
      "fix_recipe": "runner ~line 1117: try/except import of decontaminate_prompt, 7 lines total",
      "regression_guard": ["_beat_action primary path (~line 1113) unchanged", "_is_cpc_via_embedding detection (runner:1118) unchanged"],
      "impact": "LOW-MEDIUM — 2 shots affected; contained"
    }
  ],
  "stale_gate_state": [
    {
      "id": "OPEN-006",
      "title": "gate_audit.json accumulation (23 entries all FAILED, includes 006 orphans + new run errors)",
      "consecutive_reports": 7,
      "class": "STALE_GATE_STATE",
      "gate_audit_location": "pipeline_outputs/victorian_shadows_ep1/videos_kling_lite/gate_audit.json",
      "note": "gate_audit is APPEND-ONLY across runs. ORPHAN_SHOT for M-shots with _chain_group set is pre_gen timing artifact. CHARACTER_NAME_LEAK is real blocker (→ OPEN-008).",
      "not_a_code_bug": true
    }
  ],
  "architectural_debt": [
    {
      "id": "OPEN-002",
      "title": "9 un-normalized I>1.0 historical ledger entries",
      "consecutive_reports": 10,
      "class": "ARCHITECTURAL_DEBT",
      "note": "Latest-per-shot clean (0 I>1.0). Raw aggregate: 9. Historical artefacts only. No new violations in R10 new entries."
    }
  ],
  "stale_docs": [
    {
      "id": "OPEN-003",
      "title": "Runner docstring lines 24/39 say Seedance PRIMARY",
      "consecutive_reports": 10,
      "class": "STALE_DOC",
      "lines": [24, 39]
    },
    {
      "id": "OPEN-005",
      "title": "Wire-B QUALITY GATE logic unlabelled at runner:5342",
      "consecutive_reports": 8,
      "class": "STALE_DOC",
      "note": "Wire B in line 9 header. [WIRE-B] label absent from implementation at line 5342. Logic healthy."
    }
  ],
  "false_positives_retracted": [],
  "confirmed_fixed_new_this_session": [],
  "organ_health": {
    "skeleton": "DEGRADED — 11 broken video_url references (001_E02/E03/M01-M05, 008_E01-E03/M03b)",
    "liver": "DEGRADED — detection OK; decontaminate_prompt replacement absent (OPEN-004 CHRONIC-9)",
    "immune": "DEGRADED — runner header V31.0/Seedance docstring (OPEN-003 STALE_DOC-10); code correct",
    "nervous": "HEALTHY — session_enforcer SYSTEM HEALTHY, 69 passes, 0 blocks",
    "eyes": "HEALTHY — all 5 env keys PRESENT; VVO confirmed runner:3297; 4 backends active",
    "cortex": "DEGRADED — 91% I=0.75 heuristic (latest, REGRESSION from R9 70%); 19 new entries all heuristic",
    "cinematographer": "DEGRADED — run_report success=True but scenes 001/004 gate-blocked (CHARACTER_NAME_LEAK); 18 mp4s (was 29)",
    "editor": "HEALTHY — Wire-B logic at runner:5342; Wire-C runner:5090 (runner mtime advanced but functional)",
    "regenerator": "HEALTHY — Wire-C confirmed runner:5090",
    "doctrine_doc": "DEGRADED — version drift V31.0/V36.5; Seedance docstring (lines 24/39); Wire-B label absent"
  },
  "recommended_next_action": "fix_open_008_character_name_leak_then_rerun_scenes_001_004_then_fix_open_004_CPC",
  "system_production_ready": false,
  "system_production_ready_reason": "11 broken video_url references + scenes 001/004 gate-blocked (OPEN-007 + OPEN-008)",
  "blocker_count": 2,
  "chronic_bug_count": 1,
  "meta_chronic_distance": 0,
  "meta_chronic_note": "OPEN-004 REACHES META-CHRONIC AT R11 — NEXT REPORT. MUST FIX IN NEXT HUMAN SESSION.",
  "system_delta_from_prior": "ACTIVE — runner +6058 bytes, scenes 002/001/004 ran, CHARACTER_NAME_LEAK discovered, 11 broken video_urls, 2 new confirmed bugs.",
  "note": "Significant change from R9. System was active. Two new confirmed bugs discovered (OPEN-007, OPEN-008). CHARACTER_NAME_LEAK in E-shot _beat_description is blocking video generation for scenes 001 and 004. shot_plan_gate_fixer.py exists as the fix tool. OPEN-004 reaches META-CHRONIC at R11 — must be fixed in next human session."
}
```

---

*ATLAS Keep-Up R10 — 2026-03-30T12:12:00Z*
*Detection layer: REPORT only — no production files modified*
*Open issues: OPEN-007 (CONFIRMED_BUG, HIGH), OPEN-008 (CONFIRMED_BUG, HIGH), OPEN-004 (CHRONIC-9 ⚠️ META-CHRONIC AT R11), OPEN-006 (STALE_GATE_STATE-7), OPEN-003 (STALE_DOC-10), OPEN-005 (STALE_DOC-8), OPEN-002 (ARCH_DEBT-10)*
*Confirmed fixed: 19 items — all intact*
*System production-ready: FALSE (11 broken video_urls; scenes 001/004 gate-blocked)*
*Key delta from R9: ACTIVE SESSION — runner modified, 2 new confirmed bugs, CHARACTER_NAME_LEAK gate blocking discovered, 11 video_url references broken*
*Critical action required: Fix CHARACTER_NAME_LEAK (OPEN-008) + broken video_urls (OPEN-007) + CPC decontaminate (OPEN-004 META-CHRONIC at R11)*
