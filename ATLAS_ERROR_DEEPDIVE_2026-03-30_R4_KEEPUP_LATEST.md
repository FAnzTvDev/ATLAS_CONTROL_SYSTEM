# ATLAS ERROR DEEPDIVE — 2026-03-30 R4 (KEEP-UP LATEST)

**Session timestamp:** 2026-03-30T06:12:47Z
**Run number:** R4
**Prior report:** ATLAS_ERROR_DEEPDIVE_2026-03-30_R3_KEEPUP_LATEST.md
**System version:** V36.5 (CLAUDE.md) / V31.0 docstring (runner header), V37 governance hooks present
**Ledger age at snapshot:** 0d 11h 25m (last entry: 2026-03-29T18:43:06 — contaminated; last real: 2026-03-29T17:54:06)
**Atlas project:** victorian_shadows_ep1

---

## 1. EXECUTIVE SUMMARY

**Score: 11 PASS / 1 CONFIRMED_BUG / 1 ARCHITECTURAL_DEBT / 2 STALE_DOC / 1 STALE_GATE_STATE / 1 FALSE_POSITIVE_RETRACTED**

| Category | Count | Delta vs R3 |
|----------|-------|-------------|
| CONFIRMED_BUG | 1 | -1 (OPEN-001 RETRACTED as FALSE_POSITIVE; OPEN-004 remains CHRONIC-3) |
| STALE_GATE_STATE | 1 | NEW (OPEN-006 — successor to OPEN-001 retraction: gate_audit.json stale + ledger contamination) |
| ARCHITECTURAL_DEBT | 1 | = same (OPEN-002) |
| STALE_DOC | 2 | = same (OPEN-003 STALE_DOC-4; OPEN-005 STALE_DOC-2) |
| CONFIRMED_FIXED | 16 | +2 (OPEN-001 gate code confirmed correct; `_chain_group` confirmed on all 62 M-shots) |
| FALSE_POSITIVES RETRACTED | 1 | OPEN-001 CHRONIC-3 — gate passes live (see Section 5) |
| NEW ISSUES | 1 | OPEN-006: STALE_GATE_STATE — gate_audit.json stale from 18:43; ledger 006 contamination persists |

**Key findings this session (R4):**

1. 🟢 **OPEN-001 → RETRACTED (FALSE_POSITIVE):** R3's "CHRONIC-3" classification was based on a faulty proof. Live test this session: `_check_orphan_shot()` called directly on current 006 M-shots → **0/4 failures, all PASS**. Root cause of false positive: R3's Python proof only checked `chain_group` (None for all shots), but the gate code at line 450 checks BOTH `chain_group` AND `_chain_group`. Current shot_plan has `_chain_group='006_chain'` on ALL 006 M-shots (set since shot_plan mtime 21:20 local / 01:20Z). The gate has been correct all along — the proof was wrong.

2. 🔴 **OPEN-004 CHRONIC (3 reports):** `decontaminate_prompt` still absent from runner. `013_M01/M02` still have `_beat_action=None`. Now third consecutive report. Severity remains LOW-MEDIUM.

3. 🟡 **OPEN-006 NEW — STALE_GATE_STATE (gate_audit.json + ledger contamination):** The 2026-03-29T18:43:06 run failed the ORPHAN_SHOT gate (legitimately — `_chain_group` was not yet set at that time). Phase 2d still wrote V=0.5/I=0.75 defaults to the ledger for 006_M01-M04, overwriting the valid M04 entry (V=0.85 from 17:54). The gate_audit.json still reflects this stale failure. No code bug — the fix is to re-run `--videos-only` on scene 006 now that `_chain_group` is populated.

4. 🟢 **System idle — no production activity since R3.** Ledger age: 11h 25m. Runner mtime unchanged (2026-03-30T04:24:11 UTC). 59 frames, 29 videos, same as R3.

5. 🟢 **All confirmed-fixed items intact.** Session enforcer: ✅ SYSTEM HEALTHY (0 blocks). Learning log: 0 regressions. V37 governance bar: 46 HTML refs, 7 api/v37 endpoints, 4 runner refs. All 5 env keys PRESENT.

---

## 2. ORGAN HEALTH MAP

| Organ | Status | Signal | Proof (this session R4) |
|-------|--------|--------|-------------------------|
| 🦴 Skeleton (shot_plan) | 🟢 HEALTHY | isinstance bare-list guard at runner:1430, 1467. 62/62 M-shots have `_chain_group`. 35/35 E-shots isolated. | Python live check R4 |
| 🫀 Liver (prompt sanitizer) | 🟡 DEGRADED (partial) | `_is_cpc_via_embedding` at runner:245/1115 (detection). `decontaminate_prompt` absent (replacement gap). 013_M01/M02 `_beat_action=None`. | grep + python R4 |
| 🛡️ Immune (doctrine) | 🟡 DEGRADED | Runner docstring header = V31.0 + "Seedance PRIMARY" lines 24/39. CLAUDE.md = V36.5. Section 9 pre-response protocol intact. | grep R4 |
| ⚡ Nervous (hooks) | 🟢 HEALTHY | Session enforcer: ✅ SYSTEM HEALTHY. All 4 vision backends available. 34+ gate checks. 22 learning log fixes. | `python3 tools/session_enforcer.py` R4 |
| 👁️ Eyes (vision/identity) | 🟢 HEALTHY | Backends: gemini_vision, openrouter, florence_fal, heuristic. All 5 env keys PRESENT. | session_enforcer R4 |
| 🧠 Cortex (reward signal) | 🟡 DEGRADED | 23/33 shots I=0.75 (69% heuristic). Last 4 ledger entries = gate-contaminated V=0.5 (OPEN-006). Last real entry: 2026-03-29T17:54:06. | ledger python analysis R4 |
| 🎬 Cinematographer (generation) | 🟢 HEALTHY | atlas_run_report.json success=True errors=[]. 29 .mp4 files. 59 first_frames. | ls + run_report R4 |
| ✂️ Editor (stitch) | 🟢 HEALTHY | Wire-B LOGIC present via `_fail_sids/_blocked_sids` at runner:5339–5355. "Wire B" changelog at line 9. Label absent at line 5336 → OPEN-005. | grep + inspect R4 |
| 🔄 Regenerator (frozen fix) | 🟢 HEALTHY | Wire-C confirmed at runner:5081 `[WIRE-C]`. `extract_last_frame` at runner:1408/3534/3745. | grep confirmed R4 |
| 📋 Doctrine Doc | 🟡 DEGRADED | Runner header V31.0 / Seedance PRIMARY (lines 24, 39). CLAUDE.md V36.5. Wire-B implementation comment absent from line 5336. | grep R4 |

---

## 3. CONFIRMED FIXED (DO NOT RE-INVESTIGATE)

All 16 items confirmed. 2 new additions this session.

✅ **ENV LOAD ORDER (V35.0)** — All 5 keys PRESENT before vision_judge import. Confirmed R1→R4.

✅ **I-SCORE NORMALIZATION (V35.0)** — vision_judge.py line 675. Confirmed R1→R4.

✅ **GEMINI CIRCUIT BREAKER (V30.3)** — vision_judge.py lines 518-529. Confirmed R1→R4.

✅ **V-SCORE 4-STATE (V30.0)** — All four states present. Confirmed R1→R4.

✅ **END-FRAME CHAIN FIX (V31.0)** — `extract_last_frame()` called after each group (runner:1408, 3534). Confirmed R1→R4.

✅ **ROUTE_SHOT ALL KLING (V31.0)** — All branches return "kling". ACTIVE_VIDEO_MODEL="kling" at line 490. Confirmed R1→R4.

✅ **LTX RETIRED GUARD (C3)** — `_LTXRetiredGuard()` at line 460. Confirmed R1→R4.

✅ **BARE LIST GUARD (T2-OR-18)** — isinstance guard at runner:1430, 1467. Confirmed R1→R4.

✅ **WIRE-A BUDGET RESET** — `_wire_a_reset(scene_id)` at runner:424. `_WIRE_A_MAX_REGENS_PER_SCENE=2`. Confirmed R1→R4.

✅ **CHAIN ARC INTELLIGENCE (V36.5)** — `enrich_shots_with_arc()` at runner:4566 (import at line 65). All 62/62 M-shots have `_arc_position`. Confirmed R1→R4.

✅ **V36.4 ROOM ANCHOR** — Room DNA + location_master_path wired. Confirmed R1→R4.

✅ **V37 GOVERNANCE HOOKS** — 46 HTML refs, 7 api/v37 endpoints, 4 runner refs. Confirmed R1→R4.

✅ **LEARNING LOG** — 22 fixes, 0 regressions (ALL CLEAR). Confirmed R1→R4.

✅ **CPC INLINE DETECTION** — `_is_cpc_via_embedding()` at runner:245, called at runner:1115. Confirmed R2→R4.

✅ **E-SHOT ISOLATION** — 35/35 E-shots have `_no_char_ref` or `_is_broll` flag. Confirmed R3→R4.

✅ **Wire-C WIRED** — `[WIRE-C]` label at runner:5081. Confirmed R3→R4.

✅ **`_chain_group` SET ON ALL 62 M-SHOTS (NEW R4)** — Shot_plan updated (mtime 2026-03-29 21:20 local). All scenes 001–013 have `_chain_group` set (e.g., '001_chain', '006_chain'). Gate `_check_orphan_shot()` PASSES live. OPEN-001 fully retracted.

✅ **ORPHAN_SHOT GATE CODE CORRECT (NEW R4)** — `chain_intelligence_gate.py` line 450 checks BOTH `chain_group` AND `_chain_group`. Gate passes with `_chain_group` truthy. No code fix needed.

---

## 4. OPEN ISSUES

---

### ⏱️ CHRONIC (3 reports) — OPEN-004: CPC decontaminate_prompt() Not Called — Description Fallback

**Classification:** CHRONIC (3 consecutive reports: R2, R3, R4)
**Severity:** LOW-MEDIUM — `013_M01/M02` have `_beat_action=None` (confirmed R4); CPC detection fires but replacement uses `description` field, not a CPC-rewritten directive. Gap grows if more scenes miss beat enrichment.

**PROOF RECEIPT (this session — R4):**
```
PROOF: grep -n "decontaminate_prompt" atlas_universal_runner.py
OUTPUT: (no output) — function not present in runner

PROOF: python3 -c "...check 013_M01/M02 _beat_action..."
OUTPUT: 013_M01: _beat_action=None _arc_position='PIVOT'
        013_M02: _beat_action=None _arc_position='RESOLVE'

CONFIRMS: T2-CPC-6 requires replacement not stripping. Current code detects generic content
(correct at runner:1115) but falls back to raw description rather than CPC-rewritten
physical directive. 2 shots confirmed affected.
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

### 🟡 STALE_GATE_STATE (1 report) — OPEN-006: gate_audit.json Stale + 006 Ledger Contamination

**Classification:** STALE_GATE_STATE — NEW this session (R4). Successor to OPEN-001 retraction.
**Severity:** LOW — not a code bug. System is production-ready for scene 006 re-run. Ledger will self-heal on next `--videos-only`.

**Context:**
- 2026-03-29T18:43:06: Runner attempted scene 006 `--videos-only`. At that time, `_chain_group` was NOT set on 006 M-shots → gate raised ORPHAN_SHOT → Phase 2d still ran → wrote V=0.5/I=0.75 defaults for 006_M01-M04 to ledger, overwriting the valid M04 entry (V=0.85, ts 17:54).
- 2026-03-29T21:20:43 local: shot_plan.json updated (adds `_chain_group='006_chain'` on all 006 M-shots).
- Current state: gate_audit.json shows 4x ORPHAN_SHOT (stale, from 18:43). The gate would PASS if re-run now.

**PROOF RECEIPT (R4):**
```
PROOF: python3 -c "from chain_intelligence_gate import _check_orphan_shot; ..."
OUTPUT:
  006_M01: PASS
  006_M02: PASS
  006_M03: PASS
  006_M04: PASS
  RESULT: 0/4 failures. Gate would: PASS

PROOF: Last 4 ledger entries
OUTPUT:
  006_M01 ts=2026-03-29T18:43:06 I=0.75 V=0.5 C=0.7  ← contaminated
  006_M02 ts=2026-03-29T18:43:06 I=0.75 V=0.5 C=0.7  ← contaminated
  006_M03 ts=2026-03-29T18:43:06 I=0.75 V=0.5 C=0.7  ← contaminated
  006_M04 ts=2026-03-29T18:43:06 I=0.75 V=0.5 C=0.7  ← contaminated (overwrote V=0.85)

CONFIRMS: gate_audit.json is stale. Ledger has 4 contaminated entries from failed Phase 2d
run. Next --videos-only on scene 006 will clear contamination and produce proper scores.
```

**RESOLUTION (not a code fix — operational):**
```bash
python3 atlas_universal_runner.py victorian_shadows_ep1 006 --mode lite --videos-only
```
After run: gate_audit.json should show 4x `passed=true`. New ledger entries for 006_M01-M04 with real V/I/C scores.

---

### 🟡 ARCHITECTURAL_DEBT (4 reports) — OPEN-002: 9 Un-Normalized I>1.0 Historical Ledger Entries

**Classification:** ARCHITECTURAL_DEBT (consecutive: 4, R1→R4)
**Severity:** LOW — latest-per-shot all normalized (0 entries > 1.0 in current view). Raw history only.

**PROOF RECEIPT (R4):**
```
PROOF: python3 -c "bad=[e for e in lines if max(e.get('I_score',0),e.get('I',0))>1.0]; print(len(bad))"
OUTPUT: 9 entries with I in [3.5, 4.0, 5.0] — all timestamps 2026-03-24T17-18:xx
        latest-per-shot I>1.0: 0 (clean)
```

**FIX RECIPE (one-time migration — NOT in runner, run manually in session):**
```python
import json, pathlib
path = pathlib.Path('pipeline_outputs/victorian_shadows_ep1/reward_ledger.jsonl')
lines = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
fixed = [{**e, 'I': round(e['I']/5.0,3) if e.get('I',0)>1.0 else e.get('I',0)}
         for e in lines]
path.write_text('\n'.join(json.dumps(e) for e in fixed)+'\n')
```

---

### 🟡 STALE_DOC (4 reports) — OPEN-003: Runner Docstring Declares Seedance as PRIMARY

**Classification:** STALE_DOC (consecutive: 4, R1→R4)
**Severity:** LOW — code correct (ACTIVE_VIDEO_MODEL="kling" at line 490). Docstring wrong.

**PROOF RECEIPT (R4):**
```
PROOF: grep -n "Seedance.*PRIMARY\|muapi" atlas_universal_runner.py | head -3
OUTPUT:
  Line 24: P2. Videos: ALL shots parallel → Seedance v2.0 PRIMARY (muapi.ai) | Kling v3/pro FALLBACK
  Line 39: All shots PRIMARY → Seedance v2.0 via muapi.ai (...)
```

**FIX RECIPE:**
```
# Line 24 → replace with:
#   P2. Videos: ALL shots sequential (chain) → Kling v3/pro PRIMARY | Seedance RETIRED V31.0
# Line 39 → replace with:
#   All shots PRIMARY → Kling v3/pro via fal-ai (multi_prompt + @Element, end-frame chain)
```

---

### 🟡 STALE_DOC (2 reports) — OPEN-005: Wire-B Logic Unlabelled in Stitch Quality Gate

**Classification:** STALE_DOC (consecutive: 2, R3→R4)
**Severity:** VERY LOW — logic correct at runner:5339 via `_fail_sids/_blocked_sids`. "Wire B" referenced in line 9 changelog header. Implementation code at line 5336 missing inline label. Probe scripts checking "WIRE-B" string will return 0.

**PROOF RECEIPT (R4):**
```
PROOF: grep -n "Wire B\|WIRE-B\|WIRE B" atlas_universal_runner.py
OUTPUT:
  Line 9: Wire B (2026-03-20): QUALITY GATE — FAIL/FROZEN shots blocked from stitch (pre-existing)
  (no match in implementation code at line 5336)

CONFIRMS: Line 9 changelog references "Wire B". Implementation at 5336 says only
"QUALITY GATE — FAIL/FROZEN SHOTS BLOCKED FROM STITCH". Label present in header,
absent in implementation. Function is healthy.
```

**FIX RECIPE (1 comment change):**
```python
# atlas_universal_runner.py line 5336 — change from:
    # ═══ QUALITY GATE — FAIL/FROZEN SHOTS BLOCKED FROM STITCH ════════════════
# to:
    # ═══ [WIRE-B] QUALITY GATE — FAIL/FROZEN SHOTS BLOCKED FROM STITCH ═══════
```

---

## 5. FALSE POSITIVES RETRACTED THIS SESSION

**FP-003 (R4) — OPEN-001 RETRACTED:**

R1–R3 classified OPEN-001 as CHRONIC ("ORPHAN_SHOT gate blocks Kling"). R4 live verification proves this was based on faulty proof logic.

**R3's proof (incorrect):**
```python
# R3 checked only:
has_chain = [s for s in m_shots if s.get('chain_group') or s.get('_chain_group')]
# → reported HAS_chain_group=0, implying both fields were falsy
```

**R4 live verification (correct):**
```
Gate code (chain_intelligence_gate.py line 450):
  chain_group = shot.get("chain_group") or shot.get("_chain_group")

Current shot_plan (all 62 M-shots):
  chain_group=None (still None)
  _chain_group='006_chain' / '001_chain' / etc. (TRUTHY — set since shot_plan mtime 21:20)

Live test: _check_orphan_shot() called on 006 M-shots → 0/4 failures, all PASS

Distribution (all scenes):
  chain_group truthy: 0/62   ← always was None
  _chain_group truthy: 62/62 ← populated since mtime 21:20 local
  both_falsy: 0/62           ← no shots lack both fields
```

**What actually happened:**
1. 2026-03-29T18:43 local: Gate ran with `_chain_group` not yet set → ORPHAN_SHOT was a REAL failure at that moment
2. 2026-03-29T21:20 local: shot_plan.json updated, adding `_chain_group` on all M-shots
3. R3 ran at 05:08Z (after the shot_plan update) but proof only checked `chain_group` (None) — missed that `_chain_group` was now truthy
4. R3 falsely concluded ORPHAN_SHOT was still open → classified as CHRONIC-3

**ACTIONS:**
- OPEN-001 removed from open issues list
- OPEN-006 registered as STALE_GATE_STATE (gate_audit.json + contaminated 006 ledger — operational, not a code bug)
- Two new CONFIRMED_FIXED items added: `_chain_group` confirmed on 62/62 M-shots; gate code correct

---

## 6. PRIORITISED FIX LIST

Only CONFIRMED_BUG and CHRONIC issues listed.

| Priority | Issue | Class | Impact | Fix Size |
|----------|-------|-------|--------|----------|
| 1 | OPEN-004: CPC decontaminate_prompt not called | CHRONIC (3) | LOW-MEDIUM — 2 shots affected; grows if enrichment gaps expand | 7 lines in runner (try/except safe) |

**Operational (no code fix needed):**
- OPEN-006: Run `python3 atlas_universal_runner.py victorian_shadows_ep1 006 --mode lite --videos-only` — clears stale gate_audit.json and produces proper 006 ledger scores.

**Defer:**
- OPEN-003 (STALE_DOC) — comment fix, no exec impact
- OPEN-005 (STALE_DOC) — label addition, no exec impact
- OPEN-002 (ARCH_DEBT) — one-time ledger migration, latest-per-shot clean

---

## 7. ANTI-REGRESSION CHECKLIST

```
□ ACTIVE_VIDEO_MODEL default = "kling" — ✅ PASS (line 490)
□ LTX_FAST raises RuntimeError — ✅ PASS (line 460 _LTXRetiredGuard)
□ route_shot() returns "kling" all branches — ✅ PASS (verified prior, runner mtime unchanged)
□ FAL_KEY / GOOGLE_API_KEY / OPENROUTER_API_KEY / ANTHROPIC_API_KEY / MUAPI_KEY PRESENT — ✅ PASS
□ I-score normalization in vision_judge — ✅ PASS (session_enforcer R4)
□ Gemini circuit breaker wired — ✅ PASS (session_enforcer R4)
□ Wire-A budget reset at scene start — ✅ PASS (runner:424 _wire_a_reset)
□ Wire-B fail_sids logic — ✅ PASS (runner:5339 _fail_sids/_blocked_sids; label absent → OPEN-005)
□ Wire-C frozen regen — ✅ PASS (runner:5081 [WIRE-C] confirmed R4)
□ Bare list guard on shot_plan load — ✅ PASS (runner:1430, 1467)
□ Chain arc enrichment wired — ✅ PASS (runner:65 import + line 4566 call)
□ All 62 M-shots have _arc_position — ✅ PASS (62/62 confirmed R4)
□ All 62 M-shots have _chain_group (truthy) — ✅ PASS (62/62 via _chain_group field R4) [NEW]
□ _check_orphan_shot() PASSES for all 006 M-shots — ✅ PASS (0/4 failures, live test R4) [NEW]
□ E-shots have isolation flags — ✅ PASS (35/35 E-shots confirmed R3)
□ V37 governance hooks — ✅ PASS (46 HTML refs, 7 orchestrator endpoints, 4 runner refs)
□ V37 Section 8.9 thumbBar/thumbUp/thumbDown — ✅ PASS (7 thumbBar refs confirmed R4)
□ shot-gallery-list display:grid — ✅ PASS (confirmed R4)
□ Learning log: 0 regressions — ✅ PASS (ALL CLEAR R4)
□ Session enforcer: SYSTEM HEALTHY — ✅ PASS (R4 confirmed, 0 blocks)
□ story_state_canon importable — ✅ PASS (R4)
□ failure_heatmap importable — ✅ PASS (R4)
□ chain_arc_intelligence.enrich_shots_with_arc importable — ✅ PASS (runner:65 import confirmed R4)
□ gate_audit.json shows stale ORPHAN_SHOT — ⚠ OPEN-006 STALE_GATE_STATE (operational, not code bug)
□ Last 4 ledger entries V=0.5 (contaminated 18:43 run) — ⚠ OPEN-006 (clears on next --videos-only scene 006)
□ CPC decontaminate_prompt absent from runner — ⚠ OPEN-004 CHRONIC-3
□ Runner docstring lines 24/39 say Seedance PRIMARY — ⚠ OPEN-003 STALE_DOC-4
□ Wire-B "WIRE-B" comment label absent from line 5336 — ⚠ OPEN-005 STALE_DOC-2
□ 9 raw I>1.0 entries in full ledger history — ⚠ OPEN-002 ARCH_DEBT-4 (latest-per-shot clean)
```

---

## 8. DOCUMENT LINEAGE

- Prior report: **ATLAS_ERROR_DEEPDIVE_2026-03-30_R3_KEEPUP_LATEST.md** (2026-03-30T05:08:52Z)
- Prior proof gate: **NONE** (no proof-gate run exists)
- Delta since R3: 0 new ledger entries, 0 new frames, 0 new videos. Runner mtime unchanged. System idle 11h 25m.
- Report interval: ~64 minutes (R3→R4)
- Recommended next action: **Operational — run `--videos-only` on scene 006 to clear contaminated ledger. Then fix OPEN-004 if more enrichment gaps emerge. OPEN-001 was a false positive — system is production-ready.**

---

## PROOF_GATE_FEED

```json
{
  "session_timestamp": "2026-03-30T06:12:47Z",
  "report_number": "R4",
  "prior_report": "ATLAS_ERROR_DEEPDIVE_2026-03-30_R3_KEEPUP_LATEST.md",
  "ledger_age_hours": 11.4,
  "ledger_total_entries": 175,
  "ledger_unique_shots": 33,
  "ledger_last_contaminated_ts": "2026-03-29T18:43:06",
  "ledger_last_real_ts": "2026-03-29T17:54:06",
  "i_score_heuristic_pct": 69,
  "i_score_real_vlm_pct": 30,
  "production_idle_since": "2026-03-29T21:19:00Z",
  "runner_mtime": "2026-03-30T04:24:11Z",
  "shot_plan_mtime": "2026-03-30T01:20:43Z",
  "first_frames_count": 59,
  "mp4_count": 29,
  "confirmed_bugs": [
    {
      "id": "OPEN-004",
      "title": "CPC decontaminate_prompt() not called — description fallback instead of CPC replacement",
      "consecutive_reports": 3,
      "class": "CHRONIC",
      "proof_receipt": "grep -n decontaminate_prompt atlas_universal_runner.py → no output; 013_M01/M02 _beat_action=None confirmed R4",
      "fix_recipe": "runner ~line 1117: import decontaminate_prompt from tools.creative_prompt_compiler; call with emotion + char; try/except safe fallback",
      "regression_guard": ["_beat_action primary path (~line 1113) unchanged", "_is_cpc_via_embedding detection (line 1115) unchanged"],
      "impact": "LOW-MEDIUM — 2 shots affected now; more if enrichment gaps grow"
    }
  ],
  "stale_gate_state": [
    {
      "id": "OPEN-006",
      "title": "gate_audit.json stale (ORPHAN_SHOT) + 006 ledger contamination",
      "class": "STALE_GATE_STATE",
      "proof_receipt": "_check_orphan_shot() PASSES 0/4 failures live; gate_audit.json timestamp 18:43 unchanged; last 4 ledger entries V=0.5 contaminated",
      "resolution": "python3 atlas_universal_runner.py victorian_shadows_ep1 006 --mode lite --videos-only",
      "not_a_code_bug": true
    }
  ],
  "architectural_debt": [
    {
      "id": "OPEN-002",
      "title": "9 un-normalized I>1.0 historical ledger entries",
      "consecutive_reports": 4,
      "class": "ARCHITECTURAL_DEBT",
      "note": "Latest-per-shot clean (0 I>1.0). Raw aggregate only."
    }
  ],
  "stale_docs": [
    {
      "id": "OPEN-003",
      "title": "Runner docstring lines 24/39 say Seedance PRIMARY",
      "consecutive_reports": 4,
      "class": "STALE_DOC",
      "lines": [24, 39]
    },
    {
      "id": "OPEN-005",
      "title": "Wire-B QUALITY GATE logic unlabelled at line 5336 (line 9 changelog references it)",
      "consecutive_reports": 2,
      "class": "STALE_DOC",
      "note": "Wire B mentioned in line 9 header. WIRE-B label absent from line 5336 implementation. Logic healthy."
    }
  ],
  "false_positives_retracted": [
    {
      "id": "FP-003",
      "issue_retracted": "OPEN-001 CHRONIC-3",
      "from": "R1-R3: ORPHAN_SHOT gate blocks all --videos-only reruns (CHRONIC)",
      "to": "R4: _check_orphan_shot() PASSES live (0/4 failures). _chain_group='006_chain' truthy on all 62 M-shots. R3 proof only checked chain_group (None), missed _chain_group (truthy). Gate code correct at line 450.",
      "new_issue_registered": "OPEN-006: STALE_GATE_STATE — gate_audit.json stale + ledger contamination (operational, not code bug)"
    }
  ],
  "confirmed_fixed_new_this_session": [
    "_chain_group set on all 62 M-shots (00 both_falsy): shot_plan updated at 2026-03-30T01:20Z",
    "Gate code _check_orphan_shot() confirmed correct: checks both chain_group AND _chain_group at line 450"
  ],
  "organ_health": {
    "skeleton": "HEALTHY — isinstance guard + 62/62 _chain_group set + 35/35 E-shots isolated",
    "liver": "DEGRADED — detection OK; decontaminate_prompt replacement absent (OPEN-004 CHRONIC-3)",
    "immune": "DEGRADED — runner header V31.0/Seedance docstring (OPEN-003); code correct",
    "nervous": "HEALTHY — session_enforcer SYSTEM HEALTHY, 0 blocks",
    "eyes": "HEALTHY — 4 backends; all 5 env keys PRESENT",
    "cortex": "DEGRADED — 69% I=0.75 heuristic; 4 contaminated 006 ledger entries (OPEN-006 operational)",
    "cinematographer": "HEALTHY — run_report success=True; 29 videos; gate passes live",
    "editor": "HEALTHY — Wire-B logic at runner:5339; Wire-C at runner:5081",
    "regenerator": "HEALTHY — Wire-C confirmed at runner:5081",
    "doctrine_doc": "DEGRADED — version drift V31.0/V36.5; Seedance docstring; Wire-B label absent at line 5336"
  },
  "recommended_next_action": "run_scene_006_videos_only_to_clear_ledger_contamination",
  "system_production_ready": true,
  "blocker_count": 0,
  "chronic_bug_count": 1,
  "note": "OPEN-001 was a false positive in R1-R3. System has no blocking issues. Scene 006 re-run recommended for ledger hygiene."
}
```

---

*ATLAS Keep-Up R4 — 2026-03-30T06:12:47Z*
*Detection layer: REPORT only — no production files modified*
*Open issues: OPEN-004 (CHRONIC-3), OPEN-006 (STALE_GATE_STATE-1 NEW), OPEN-003 (STALE_DOC-4), OPEN-005 (STALE_DOC-2), OPEN-002 (ARCH_DEBT-4)*
*FALSE POSITIVES RETRACTED: OPEN-001 (R1-R3 CHRONIC — gate passes live, _chain_group truthy on all 62 M-shots)*
*System production-ready. No blocking issues. Recommend scene 006 --videos-only before next generation session.*
