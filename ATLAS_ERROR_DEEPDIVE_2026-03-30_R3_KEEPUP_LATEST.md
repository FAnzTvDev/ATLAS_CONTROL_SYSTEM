# ATLAS ERROR DEEPDIVE — 2026-03-30 R3 (KEEP-UP LATEST)

**Session timestamp:** 2026-03-30T05:08:52Z
**Run number:** R3
**Prior report:** ATLAS_ERROR_DEEPDIVE_2026-03-30_R2_KEEPUP_LATEST.md
**System version:** V36.5 (CLAUDE.md) / V31.0 docstring (runner header), V37 governance hooks present
**Ledger age at snapshot:** 0d 10h 26m (last valid: 2026-03-29T18:43:06 — gate-blocked contamination entries; last REAL: 2026-03-29T17:54:06)
**Atlas project:** victorian_shadows_ep1

---

## 1. EXECUTIVE SUMMARY

**Score: 10 PASS / 2 CONFIRMED_BUG / 1 ARCHITECTURAL_DEBT / 1 STALE_DOC / 1 NEW FALSE_POSITIVE_RETRACTION**

| Category | Count | Delta vs R2 |
|----------|-------|-------------|
| CONFIRMED_BUG | 2 | = same (OPEN-001 now CHRONIC at 3 reports; OPEN-004 at 2 reports) |
| ARCHITECTURAL_DEBT | 1 | = same (OPEN-002) |
| STALE_DOC | 2 | +1 (OPEN-003 carried; OPEN-005 NEW — "Wire-B" label absent from runner) |
| CONFIRMED_FIXED | 14 | = same |
| FALSE_POSITIVES RETRACTED | 1 | Wire-B grep label reclassified — see Section 5 |
| NEW ISSUES | 1 | OPEN-005 (minor): R2 reported Wire-B "6 grep hits" which was wrong (0 WIRE-B strings) — the logic IS present via `_fail_sids` at line 5339 (just unlabelled). Function HEALTHY, probe was wrong. |

**Key findings this session (R3):**
1. 🔴 **OPEN-001 CHRONIC (3 reports)** — ORPHAN_SHOT gate still fails all 4 scene-006 shots. `chain_group=None` on all 62 M-shots confirmed AGAIN this session via Python live check. gate_audit.json unchanged (4x ORPHAN_SHOT timestamp 2026-03-29T18:43:06). No new generation occurred. Ledger age: 10h 26m.
2. 🟢 **Wire-B FUNCTIONAL (no label)** — R2 claimed grep -c WIRE-B returned 6 hits. This session: 0 hits. Wire-B functionality DOES exist as `_fail_sids/_blocked_sids` logic at runner lines 5339–5355. The unlabelled code is correct. R2 grep count was a false positive in the report (possibly counted "WIRE-A/C" refs containing "WIRE" but not "WIRE-B" string). No regression — logic is healthy. New OPEN-005 registered as STALE_DOC to add a `# WIRE-B:` label.
3. 🟢 **No new production activity** — 0 new ledger entries, 0 new frames, 0 new videos since R2. Runner mtime: 2026-03-30T04:24:11 UTC (unchanged). System idle 10h+.
4. 🟢 **All confirmed-fixed items remain intact** — session enforcer SYSTEM HEALTHY, learning log ALL CLEAR, all env keys PRESENT, V37 governance bar intact (10 HTML refs, 7 api/v37 endpoints, 4 runner refs).
5. 🟡 **OPEN-004 CHRONIC (2 reports)** — `decontaminate_prompt` still absent from runner. `013_M01/_arc_position` confirmed set but `_beat_action=None` on both 013_M01/M02. CPC fallback gap persists. Low blast radius but worth noting it's now 2 consecutive reports.

---

## 2. ORGAN HEALTH MAP

| Organ | Status | Signal | Proof (this session R3) |
|-------|--------|--------|-------------------------|
| 🦴 Skeleton (shot_plan) | 🟢 HEALTHY | isinstance bare-list guard at runner:1430, 1467. E-shots 35/35 have isolation flags. | grep + python confirmed |
| 🫀 Liver (prompt sanitizer) | 🟡 DEGRADED (partial) | `_is_cpc_via_embedding` at runner:245 (detection). `decontaminate_prompt` absent (replacement). 013_M01/M02 `_beat_action=None`. | grep confirmed R3 |
| 🛡️ Immune (doctrine) | 🟡 DEGRADED | Runner docstring header = V31.0 + "Seedance PRIMARY" lines 24/39. CLAUDE.md = V36.5. Section 9 pre-response protocol intact. | grep confirmed R3 |
| ⚡ Nervous (hooks) | 🟢 HEALTHY | Session enforcer: ✅ SYSTEM HEALTHY (52 check lines, 0 blocks). All 4 vision backends available. | `python3 tools/session_enforcer.py` R3 |
| 👁️ Eyes (vision/identity) | 🟢 HEALTHY | Backends: gemini_vision, openrouter, florence_fal, heuristic. All 5 env keys (FAL_KEY, OPENROUTER_API_KEY, ANTHROPIC_API_KEY, MUAPI_KEY, GOOGLE_API_KEY) PRESENT. | session_enforcer output R3 |
| 🧠 Cortex (reward signal) | 🟡 DEGRADED | Latest-per-shot: 23/33 shots I=0.75 (69% heuristic). Last 4 ledger entries = gate-contaminated V=0.5 (OPEN-001). Last real production entry: 2026-03-29T17:54:06. | ledger python analysis R3 |
| 🎬 Cinematographer (generation) | 🟢 HEALTHY | atlas_run_report.json success=True errors=[]. Latest frames: 2026-03-29T21:19. 29 .mp4 files. 59 first_frames. | ls + run_report R3 |
| ✂️ Editor (stitch) | 🟢 HEALTHY | Wire-B LOGIC present via `_fail_sids/_blocked_sids` at runner:5339–5355 (QUALITY GATE block). Label "WIRE-B" absent from code — see OPEN-005. | sed inspect runner:5335-5355 R3 |
| 🔄 Regenerator (frozen fix) | 🟢 HEALTHY | Wire-C confirmed at runner:5081 with `[WIRE-C]` label. `_check_frozen()` at runner:3715. | grep confirmed R3 |
| 📋 Doctrine Doc | 🟡 DEGRADED | Runner header V31.0 / Seedance PRIMARY (lines 24, 39). CLAUDE.md V36.5. Minor: "WIRE-B" comment absent from stitch quality gate. | grep R3 |

---

## 3. CONFIRMED FIXED (DO NOT RE-INVESTIGATE)

All 14 items from R2 remain confirmed. No new additions this session.

✅ **ENV LOAD ORDER (V35.0)** — All 5 keys (FAL_KEY, OPENROUTER, ANTHROPIC, MUAPI, GOOGLE_API_KEY) PRESENT before vision_judge import. Confirmed R1, R2, R3.

✅ **I-SCORE NORMALIZATION (V35.0)** — vision_judge.py line 675 present. Confirmed R1, R2, R3.

✅ **GEMINI CIRCUIT BREAKER (V30.3)** — vision_judge.py lines 518-529. Confirmed R1, R2, R3.

✅ **V-SCORE 4-STATE (V30.0)** — All four states [0.0, 0.3, 0.5, 0.85] present. Confirmed R1, R2, R3.

✅ **END-FRAME CHAIN FIX (V31.0)** — `extract_last_frame()` called after each group. Confirmed R1, R2, R3.

✅ **ROUTE_SHOT ALL KLING (V31.0)** — All branches return "kling". ACTIVE_VIDEO_MODEL = "kling" at line 490. Confirmed R1, R2, R3.

✅ **LTX RETIRED GUARD (C3)** — `_LTXRetiredGuard()` at line 460. Confirmed R1, R2, R3.

✅ **BARE LIST GUARD (T2-OR-18)** — isinstance guard at runner:1430, 1467. Confirmed R1, R2, R3.

✅ **WIRE-A BUDGET RESET** — `_wire_a_reset(scene_id)` wired. `_WIRE_A_MAX_REGENS_PER_SCENE=2` at line 413. Confirmed R1, R2, R3.

✅ **CHAIN ARC INTELLIGENCE (V36.5)** — `enrich_shots_with_arc()` at runner:4566. All 62/62 M-shots have `_arc_position`. Confirmed R1, R2, R3.

✅ **V36.4 ROOM ANCHOR** — Room DNA + location_master_path wired. Confirmed R1, R2, R3.

✅ **V37 GOVERNANCE HOOKS** — 10 HTML refs, 7 api/v37 endpoints, 4 runner refs. Confirmed R1, R2, R3.

✅ **LEARNING LOG** — 22 fixes, 0 regressions (ALL CLEAR). Confirmed R1, R2, R3.

✅ **CPC INLINE DETECTION** — `_is_cpc_via_embedding()` at runner:245, called at runner:1115. Confirmed R2, R3.

✅ **E-SHOT ISOLATION** — 35/35 E-shots have `_no_char_ref` or `_is_broll` flag. Confirmed R3.

✅ **Wire-C WIRED** — `[WIRE-C]` label at runner:5081, `_check_frozen()` at runner:3715. Confirmed R3.

---

## 4. OPEN ISSUES

---

### ⏱️ CHRONIC (3 reports) — OPEN-001: ORPHAN_SHOT Gate Blocks Kling + Ledger Contamination

**Classification:** CHRONIC (3 consecutive reports: R1, R2, R3)
**Severity:** HIGH — blocks all --videos-only reruns on scene 006 M-shots; last 4 ledger entries contaminated
**First seen:** R1 (2026-03-30T03:16:14Z)

**PROOF RECEIPT (this session — R3):**
```
PROOF: python3 -c "shots = sp if isinstance(sp, list) else sp.get('shots', []); m_shots = [s for s in shots if '_M' in s.get('shot_id','')]; no_chain = [s for s in m_shots if not s.get('chain_group') and not s.get('_chain_group')]"
OUTPUT: M_SHOTS_TOTAL=62, NO_chain_group=62, HAS_chain_group=0
NOTE: chain_group key EXISTS on all shots but value is None — same as absent for gate's truthy check

PROOF: cat pipeline_outputs/victorian_shadows_ep1/videos_kling_lite/gate_audit.json
OUTPUT: 4 entries, all passed=false, ORPHAN_SHOT error, timestamp unchanged 2026-03-29T18:43:06
→ No new generation has run since R2

PROOF: last 5 reward_ledger.jsonl entries
OUTPUT: last entry still 2026-03-29T18:43:06 006_M04 I=0.75 V=0.5 C=0.7 (contaminated)
        real last entry: 2026-03-29T17:54:06 006_M04 I=0.8 V=0.85 C=0.85
```

**CONFIRMS:** gate checks `shot.get("chain_group") or shot.get("_chain_group")` — both return None → ORPHAN_SHOT → gate blocks Kling call → Phase 2d runs anyway → writes I=0.75/V=0.5 defaults → overwrites valid entries in ledger.

**FIX RECIPE (Option A — 1 line in gate, preferred):**
```python
# tools/chain_intelligence_gate.py line 450 — change from:
chain_group = shot.get("chain_group") or shot.get("_chain_group")
# to:
chain_group = (shot.get("chain_group") or shot.get("_chain_group")
               or shot.get("_gen_strategy"))  # V36.5: runner writes _gen_strategy not chain_group
```

**FIX RECIPE (Option B — 3 lines in runner):**
```python
# atlas_universal_runner.py ~line 2699 (INDEPENDENT branch):
s["_gen_strategy"] = "INDEPENDENT"
s["chain_group"] = "independent"                # ADD

# ~line 2705 (CHAIN_ANCHOR branch):
s["_gen_strategy"] = "CHAIN_ANCHOR"
s["chain_group"] = f"chain_{scene_id}"          # ADD

# ~line 2709 (CHAIN branch):
s["_gen_strategy"] = "CHAIN"
s["chain_group"] = f"chain_{scene_id}"          # ADD
```

**REGRESSION GUARD (do NOT touch):**
- `_WIRE_A_MAX_REGENS_PER_SCENE` budget logic (lines 413-426)
- `extract_last_frame()` chain path
- `_arc_position` enrichment (62/62 M-shots confirmed correct)
- `_independent_start_url` logic for INDEPENDENT shots

**VERIFY FIX:** Run `python3 atlas_universal_runner.py victorian_shadows_ep1 006 --mode lite --videos-only`. `gate_audit.json` should show `"passed": true`. New ledger entries should show V=0.85.

---

### ⏱️ CHRONIC (2 reports) — OPEN-004: CPC decontaminate_prompt() Not Called — Description Fallback

**Classification:** CHRONIC (2 consecutive reports: R2, R3)
**Severity:** LOW-MEDIUM — `013_M01/M02` have `_beat_action=None` (confirmed R3); CPC detection fires but replacement uses `description` field, not a CPC-rewritten directive.

**PROOF RECEIPT (this session — R3):**
```
PROOF: grep -n "decontaminate_prompt" atlas_universal_runner.py
OUTPUT: (no output) — function not present

PROOF: python3 -c "...check 013_M01/M02 _beat_action..."
OUTPUT: 013_M01: _beat_action=None
        013_M02: _beat_action=None

PROOF: grep -n "_is_cpc_via_embedding" atlas_universal_runner.py
OUTPUT: Line 245: def _is_cpc_via_embedding(text: str) -> bool:
        Line 1115: elif clean_choreo and _is_cpc_via_embedding(clean_choreo):
        (no decontaminate_prompt import or call below line 1115)
```

**CONFIRMS:** T2-CPC-6 requires replacement not stripping. Current code detects generic content (correct) but falls back to raw `description` rather than CPC-rewritten physical directive (gap). 2 shots affected now.

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

**REGRESSION GUARD:** Does NOT touch `_beat_action` primary path (~line 1113). `try/except` ensures non-blocking if CPC import fails.

---

### 🟡 ARCHITECTURAL_DEBT (3 reports) — OPEN-002: 9 Un-Normalized I>1.0 Historical Ledger Entries

**Classification:** ARCHITECTURAL_DEBT (consecutive: 3, R1+R2+R3)
**Severity:** LOW — latest-per-shot all normalized (0 entries > 1.0 in current view). Raw history only.

**PROOF RECEIPT (R3):**
```
PROOF: python3 -c "bad=[e for e in lines if max(e.get('I_score',0),e.get('I',0))>1.0]; print(len(bad))"
OUTPUT: 9 entries with I in [3.5, 4.0, 5.0] — all timestamps 2026-03-24T17-18:xx
        latest-per-shot I>1.0: 0 (clean)
```

**FIX RECIPE (one-time migration — not in runner):**
```python
import json, pathlib
path = pathlib.Path('pipeline_outputs/victorian_shadows_ep1/reward_ledger.jsonl')
lines = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
fixed = [{**e, 'I_score': round(e['I_score']/5.0,3) if e.get('I_score',0)>1.0 else e.get('I_score',0)}
         for e in lines]
path.write_text('\n'.join(json.dumps(e) for e in fixed)+'\n')
```

---

### 🟡 STALE_DOC (3 reports) — OPEN-003: Runner Docstring Declares Seedance as PRIMARY

**Classification:** STALE_DOC (consecutive: 3, R1+R2+R3)
**Severity:** LOW — code is correct (ACTIVE_VIDEO_MODEL="kling" at line 490). Docstring is wrong.

**PROOF RECEIPT (R3):**
```
PROOF: grep -n "Seedance.*PRIMARY\|muapi" atlas_universal_runner.py | head -3
OUTPUT:
  Line 24: P2. Videos: ALL shots parallel → Seedance v2.0 PRIMARY (muapi.ai) | Kling v3/pro FALLBACK
  Line 39: All shots PRIMARY → Seedance v2.0 via muapi.ai (images_list=[start_frame, char1, char2, loc])
```

**FIX RECIPE:**
```python
# Line 24 → replace with:
#   P2. Videos: ALL shots sequential (chain) → Kling v3/pro PRIMARY (fal-ai/kling-video/v3/pro) | Seedance RETIRED V31.0

# Line 39 → replace with:
#   All shots PRIMARY → Kling v3/pro via fal-ai (multi_prompt + @Element identity, end-frame chain)
```

---

### 🟡 STALE_DOC (1 report) — OPEN-005: Wire-B Logic Unlabelled in Stitch Quality Gate

**Classification:** STALE_DOC — first report (R3). NEW this session.
**Severity:** VERY LOW — code is correct, label is absent. Risk: future probe scripts looking for "WIRE-B" string will return false.
**First seen:** R3 (probe discrepancy — R2 claimed "WIRE-B: 6 grep hits" but R3 confirms 0 hits)

**PROOF RECEIPT (R3):**
```
PROOF: grep -c "WIRE-B\|WIRE.B" atlas_universal_runner.py
OUTPUT: 0

PROOF: Wire-B logic exists at runner:5339?
sed -n '5335,5355p' atlas_universal_runner.py
OUTPUT:
    # ═══ QUALITY GATE — FAIL/FROZEN SHOTS BLOCKED FROM STITCH ════════════════
    _fail_sids = {e["shot_id"] for e in reward_ledger if e.get("verdict") == "FAIL"}
    ...videos = [v for v in videos if not any(_bsid in os.path.basename(v) for _bsid in _blocked_sids)]
```

**CONFIRMS:** Wire-B LOGIC is intact (T2-SA-5 compliant). The "WIRE-B" comment label is missing. R2's "Wire-B: 6 grep hits" was a false reading — likely `grep -c "WIRE-A\|WIRE-B\|WIRE-C"` returning total matches for all three strings (6 = Wire-A + Wire-C refs; 0 Wire-B strings). This is a documentation/labelling gap only.

**FIX RECIPE (1 comment line):**
```python
# atlas_universal_runner.py line 5336 — add label to existing comment:
# ═══ WIRE B: QUALITY GATE — FAIL/FROZEN SHOTS BLOCKED FROM STITCH ════════════
```

---

## 5. FALSE POSITIVES RETRACTED THIS SESSION

**FP-002 (R3):** R2 anti-regression checklist stated "Wire B (`_fail_sids`) confirmed at runner:5228 (grep)" with implied grep hit count of 6 for `grep -c "WIRE-A\|WIRE-B\|WIRE-C"`. R3 investigation shows `grep -c "WIRE-B"` = 0. The combined grep was counting Wire-A + Wire-C hits. Wire-B FUNCTION is healthy at runner:5339 via `_fail_sids/_blocked_sids` logic. R2's "confirmed at runner:5228" line number was also off (actual: 5339). **Wire-B functionality: HEALTHY. Label: ABSENT. No regression.**

Reclassification: Wire-B status: 🟢 HEALTHY (logic present, unlabelled) → registered as STALE_DOC OPEN-005.

---

## 6. PRIORITISED FIX LIST

Only CONFIRMED_BUG and CHRONIC issues listed. ARCHITECTURAL_DEBT and STALE_DOC excluded per protocol.

| Priority | Issue | Class | Impact | Fix Size |
|----------|-------|-------|--------|----------|
| 1 | OPEN-001: ORPHAN_SHOT gate + ledger contamination | CHRONIC (3) | HIGH — blocks all reruns, poisons reward ledger | 1 line in gate OR 3 lines in runner |
| 2 | OPEN-004: CPC decontaminate_prompt not called | CHRONIC (2) | LOW-MEDIUM — 2 shots affected; grows if enrichment gaps expand | 7 lines in runner (try/except safe) |

**Defer:**
- OPEN-003 (STALE_DOC) — comment fix, no exec impact
- OPEN-005 (STALE_DOC) — label addition, no exec impact
- OPEN-002 (ARCH_DEBT) — one-time ledger migration, latest-per-shot clean

---

## 7. ANTI-REGRESSION CHECKLIST

```
□ ACTIVE_VIDEO_MODEL default = "kling" — ✅ PASS (line 490: os.environ.get("ATLAS_VIDEO_MODEL", "kling"))
□ LTX_FAST raises RuntimeError — ✅ PASS (line 460: _LTXRetiredGuard())
□ route_shot() returns "kling" all branches — ✅ PASS (verified R2, runner unchanged since)
□ FAL_KEY / GOOGLE_API_KEY / OPENROUTER_API_KEY / ANTHROPIC_API_KEY / MUAPI_KEY set before vision_judge import — ✅ PASS (all PRESENT in .env)
□ I-score normalization present in vision_judge — ✅ PASS (confirmed via session_enforcer R3)
□ Gemini circuit breaker wired — ✅ PASS (session_enforcer R3)
□ Wire-A budget reset at scene start — ✅ PASS (runner:424 _wire_a_reset)
□ Wire-B fail_sids logic — ✅ PASS (runner:5339 _fail_sids/_blocked_sids; label absent → OPEN-005)
□ Wire-C frozen regen — ✅ PASS (runner:5081 [WIRE-C] label confirmed R3)
□ Bare list guard on shot_plan load — ✅ PASS (runner:1430, 1467)
□ Chain arc enrichment wired — ✅ PASS (runner:4566 enrich_shots_with_arc)
□ All 62 M-shots have _arc_position — ✅ PASS (62/62 confirmed R3)
□ E-shots have isolation flags — ✅ PASS (35/35 E-shots confirmed R3)
□ V37 governance hooks — ✅ PASS (10 HTML refs, 7 orchestrator endpoints, 4 runner refs)
□ V37 Section 8.9 thumbBar/thumbUp/thumbDown — ✅ PASS (18 refs confirmed R3)
□ shot-gallery-list display:grid — ✅ PASS (confirmed R1, no HTML changes since)
□ Learning log: 0 regressions — ✅ PASS (ALL CLEAR R3)
□ Session enforcer: SYSTEM HEALTHY — ✅ PASS (R3 confirmed, 52 checks, 0 blocks)
□ story_state_canon importable — ✅ PASS (confirmed R2)
□ failure_heatmap importable — ✅ PASS (confirmed R2)
□ chain_arc_intelligence.enrich_shots_with_arc importable — ✅ PASS (runner:65 import confirmed R3)
□ chain_group = None on all M-shots (gate truthy check) — ⚠ OPEN-001 CHRONIC-3 (62/62 None)
□ gate_audit.json shows ORPHAN_SHOT — ⚠ OPEN-001 (4 failures, unchanged since R2)
□ Last 4 ledger entries V=0.5 (gate-blocked contamination) — ⚠ OPEN-001 (ledger age: 10h 26m)
□ CPC decontaminate_prompt absent from runner — ⚠ OPEN-004 CHRONIC-2 (013_M01/M02 at risk)
□ Runner docstring lines 24/39 say Seedance PRIMARY — ⚠ OPEN-003 STALE_DOC-3
□ Wire-B "WIRE-B" comment label absent — ⚠ OPEN-005 STALE_DOC-1 (NEW R3)
□ 9 raw I>1.0 entries in full ledger history — ⚠ OPEN-002 ARCH_DEBT-3 (latest-per-shot clean)
```

---

## 8. DOCUMENT LINEAGE

- Prior report: **ATLAS_ERROR_DEEPDIVE_2026-03-30_R2_KEEPUP_LATEST.md** (2026-03-30T04:14:21Z)
- Prior proof gate: **NONE** (no proof-gate run exists)
- Delta since R2: 0 new ledger entries, 0 new frames, 0 new videos. Runner mtime unchanged (2026-03-30T04:24:11 UTC). System idle 10h+.
- Report interval: ~55 minutes (R2→R3)
- Recommended next action: **Fix OPEN-001 before any --videos-only reruns. Ledger is clean enough to proceed once gate is patched.**

---

## PROOF_GATE_FEED

```json
{
  "session_timestamp": "2026-03-30T05:08:52Z",
  "report_number": "R3",
  "prior_report": "ATLAS_ERROR_DEEPDIVE_2026-03-30_R2_KEEPUP_LATEST.md",
  "ledger_age_hours": 10.5,
  "ledger_total_entries": 175,
  "ledger_unique_shots": 33,
  "ledger_last_contaminated_ts": "2026-03-29T18:43:06",
  "ledger_last_real_ts": "2026-03-29T17:54:06",
  "i_score_heuristic_pct": 69,
  "i_score_real_vlm_pct": 30,
  "production_idle_since": "2026-03-29T21:19:00Z",
  "runner_mtime": "2026-03-30T04:24:11Z",
  "first_frames_count": 59,
  "mp4_count": 29,
  "confirmed_bugs": [
    {
      "id": "OPEN-001",
      "title": "ORPHAN_SHOT gate blocks Kling + ledger contamination",
      "consecutive_reports": 3,
      "class": "CHRONIC",
      "proof_receipt": "62/62 M-shots chain_group=None (truthy fails); gate_audit.json 4x passed=false ORPHAN_SHOT unchanged; last 4 ledger V=0.5 overwrote valid V=0.85",
      "fix_recipe_primary": "tools/chain_intelligence_gate.py line 450: add `or shot.get('_gen_strategy')` to chain_group resolution",
      "fix_recipe_alternative": "atlas_universal_runner.py: set s['chain_group']=f'chain_{scene_id}' alongside _gen_strategy at lines 2699/2705/2709",
      "regression_guard": ["_WIRE_A_MAX_REGENS budget (lines 413-426)", "extract_last_frame chain path", "_arc_position (62/62 M-shots clean)", "_independent_start_url"],
      "verify_fix": "Re-run --videos-only on scene 006; gate_audit.json passed=true; new ledger V=0.85"
    },
    {
      "id": "OPEN-004",
      "title": "CPC decontaminate_prompt() not called — description fallback instead of CPC replacement",
      "consecutive_reports": 2,
      "class": "CHRONIC",
      "proof_receipt": "grep -n decontaminate_prompt atlas_universal_runner.py → no output; 013_M01/M02 _beat_action=None confirmed R3",
      "fix_recipe": "runner ~line 1117: import decontaminate_prompt from tools.creative_prompt_compiler; call with emotion + char; try/except safe fallback",
      "regression_guard": ["_beat_action primary path (~line 1113) unchanged", "_is_cpc_via_embedding detection (line 1115) unchanged"],
      "impact": "LOW-MEDIUM — 2 shots affected now; more if enrichment gaps grow"
    }
  ],
  "architectural_debt": [
    {
      "id": "OPEN-002",
      "title": "9 un-normalized I>1.0 historical ledger entries",
      "consecutive_reports": 3,
      "class": "ARCHITECTURAL_DEBT",
      "note": "Latest-per-shot clean (0 I>1.0). Raw aggregate only. One-time migration script in report."
    }
  ],
  "stale_docs": [
    {
      "id": "OPEN-003",
      "title": "Runner docstring lines 24/39 say Seedance PRIMARY",
      "consecutive_reports": 3,
      "class": "STALE_DOC",
      "lines": [24, 39]
    },
    {
      "id": "OPEN-005",
      "title": "Wire-B QUALITY GATE logic unlabelled — no WIRE-B comment in code",
      "consecutive_reports": 1,
      "class": "STALE_DOC",
      "note": "Logic healthy at runner:5339 via _fail_sids/_blocked_sids. Label missing. Add one comment line.",
      "new_this_session": true
    }
  ],
  "false_positives_retracted": [
    {
      "id": "FP-002",
      "from": "R2 Wire-B 'grep confirmed at runner:5228 (6 hits)'",
      "to": "R3: grep -c 'WIRE-B' = 0; combined grep hit count was Wire-A+Wire-C only; Wire-B logic present at runner:5339 via _fail_sids (unlabelled). Function HEALTHY.",
      "new_issue": "OPEN-005 registered as STALE_DOC for labelling gap"
    }
  ],
  "organ_health": {
    "skeleton": "HEALTHY — isinstance guard at runner:1430/1467; 35/35 E-shots isolated",
    "liver": "DEGRADED — _is_cpc_via_embedding detection OK; decontaminate_prompt replacement absent (OPEN-004 CHRONIC-2)",
    "immune": "DEGRADED — runner header V31.0 / CLAUDE.md V36.5 drift; Seedance docstring lines 24/39 (OPEN-003)",
    "nervous": "HEALTHY — session_enforcer SYSTEM HEALTHY, 52 checks, 0 blocks",
    "eyes": "HEALTHY — 4 backends; all 5 env keys PRESENT",
    "cortex": "DEGRADED — 69% I=0.75 heuristic; gate contamination on last 4 entries (OPEN-001)",
    "cinematographer": "HEALTHY — run_report success=True; 29 videos; frames at 2026-03-29T21:19",
    "editor": "HEALTHY — Wire-B logic at runner:5339; Wire-C at runner:5081",
    "regenerator": "HEALTHY — Wire-C confirmed with label at runner:5081",
    "doctrine_doc": "DEGRADED — version drift V31.0/V36.0/V36.5; Seedance docstring; Wire-B label absent"
  },
  "new_issues_this_session": [
    "OPEN-005: Wire-B comment label absent from stitch quality gate (STALE_DOC, very low severity)"
  ],
  "new_confirmed_fixed_this_session": [
    "E-shot isolation: 35/35 E-shots confirmed with _no_char_ref or _is_broll flag",
    "Wire-C: [WIRE-C] label confirmed at runner:5081",
    "Wire-B: _fail_sids logic confirmed at runner:5339 (unlabelled but functional)"
  ],
  "recommended_next_action": "fix_open_001_before_any_generation",
  "fix_priority_1": "tools/chain_intelligence_gate.py line 450: add `or shot.get('_gen_strategy')` — 1 line, unblocks all --videos-only reruns and stops ledger contamination",
  "fix_priority_2": "atlas_universal_runner.py ~line 1117: add decontaminate_prompt call in CPC fallback branch (7 lines, try/except safe)"
}
```

---

*ATLAS Keep-Up R3 — 2026-03-30T05:08:52Z*
*Detection layer: REPORT only — no production files modified*
*Open issues: OPEN-001 (CHRONIC-3), OPEN-004 (CHRONIC-2), OPEN-003 (STALE_DOC-3), OPEN-005 (STALE_DOC-1 NEW), OPEN-002 (ARCH_DEBT-3)*
*System idle since 2026-03-29T21:19 — no new generation since R2*
*Next: fix OPEN-001 (1 line in chain_intelligence_gate.py) before any --videos-only reruns*
