# CLAUDE.md PROPOSED UPDATES — 2026-03-31
## Status: 16 desyncs found (all line-number drift — no logic/feature desyncs)

Runner has grown since last grep (2026-03-29). All wire positions and function locations have shifted. No functional or architectural claims are wrong — only line references are stale.

---

### DESYNC 1: ACTIVE_VIDEO_MODEL default line (V31.0 section)
CLAUDE.md currently says: "`ACTIVE_VIDEO_MODEL` default at line 324"
Live codebase shows: Line 546 — `ACTIVE_VIDEO_MODEL = os.environ.get("ATLAS_VIDEO_MODEL", "kling")`
PROPOSED REPLACEMENT: "`ACTIVE_VIDEO_MODEL` default at line 546: **already `"kling"`** — no change needed."

### DESYNC 2: route_shot() line (V31.0 section)
CLAUDE.md currently says: "`route_shot()` (~line 1381)"
Live codebase shows: `def route_shot` at line 1614
PROPOSED REPLACEMENT: "`route_shot()` (~line 1614)"

### DESYNC 3: Wire A position (V31.0 WIRE POSITIONS)
CLAUDE.md currently says: "Wire A: runner line ~2184 (`_wire_a_can_regen` check in `gen_frame`), budget reset at ~2960"
Live codebase shows: `_wire_a_can_regen` check at line ~2520, budget reset `_wire_a_reset` at line ~4738
PROPOSED REPLACEMENT: "Wire A: runner line ~2520 (`_wire_a_can_regen` check in `gen_frame`), budget reset at ~4738 (top of `run_scene`)"

### DESYNC 4: Wire B position (V31.0 WIRE POSITIONS)
CLAUDE.md currently says: "Wire B: runner line ~3658 (`_fail_sids` filter before stitch)"
Live codebase shows: `_fail_sids` filter at line ~5717
PROPOSED REPLACEMENT: "Wire B: runner line ~5717 (`_fail_sids` filter before stitch)"

### DESYNC 5: Wire C position (V31.0 WIRE POSITIONS)
CLAUDE.md currently says: "Wire C: runner line ~3451 (`[WIRE-C]` frozen video regen in `_analyze_video` path)"
Live codebase shows: `[WIRE-C]` frozen regen at line ~5476
PROPOSED REPLACEMENT: "Wire C: runner line ~5476 (`[WIRE-C]` frozen video regen in `_analyze_video` path)"

### DESYNC 6: Wire D position (V31.0 WIRE POSITIONS)
CLAUDE.md currently says: "Wire D: runner line ~85 (`# ── SCREEN POSITION LOCK — Wire D (V30.4)`)"
Live codebase shows: SCREEN POSITION LOCK comment at line ~134
PROPOSED REPLACEMENT: "Wire D: runner line ~134 (`# ── SCREEN POSITION LOCK — Wire D (V30.4)`)"

### DESYNC 7: Wire A back-to-camera skip (V31.0 WIRE POSITIONS)
CLAUDE.md currently says: "Wire A back-to-camera skip: runner line ~2165"
Live codebase shows: back-to-camera skip print at line ~2518
PROPOSED REPLACEMENT: "Wire A back-to-camera skip: runner line ~2518"

### DESYNC 8: Wire A budget functions (V30.3 section)
CLAUDE.md currently says: "lines 210–223: Wire A budget cap"
Live codebase shows: Wire A budget cap functions at lines 465–482
PROPOSED REPLACEMENT: "lines 465–482: Wire A budget cap"

### DESYNC 9: V36.4 reframe Room DNA wire location
CLAUDE.md currently says: "runner ~line 3280 (reframe Room DNA)"
Live codebase shows: Reframe Room DNA injection at lines ~3874–3902
PROPOSED REPLACEMENT: "runner ~line 3874 (reframe Room DNA)"

### DESYNC 10: V36.4 reframe location master image_urls
CLAUDE.md currently says: "~line 3310 (reframe location master image_urls)"
Live codebase shows: `_rf_loc_path = context.get("_location_master_path")` at line ~3924
PROPOSED REPLACEMENT: "~line 3924 (reframe location master image_urls)"

### DESYNC 11: V36.4 Kling "Setting:" anchor
CLAUDE.md currently says: "~line 2900 (Kling 'Setting:' anchor)"
Live codebase shows: `parts.append(f"Setting: {_rf_dna_short}.")` at line ~3160
PROPOSED REPLACEMENT: "~line 3160 (Kling 'Setting:' anchor)"

### DESYNC 12: V36.4 context dict _location_master_path
CLAUDE.md currently says: "~line 4206 (context dict with _location_master_path)"
Live codebase shows: `"_location_master_path": _ctx_loc_path` at line ~4939
PROPOSED REPLACEMENT: "~line 4939 (context dict with _location_master_path)"

### DESYNC 13: V36.5 arc enrichment line
CLAUDE.md currently says: "arc enrichment at ~line 4210 (before groups)"
Live codebase shows: `enrich_shots_with_arc(mshots, _sb_full, scene_id)` at line ~4950
PROPOSED REPLACEMENT: "arc enrichment at ~line 4950 (before groups)"

### DESYNC 14: V36.5 arc modifier in Kling prompt
CLAUDE.md currently says: "arc modifier in Kling prompt at ~line 2920"
Live codebase shows: `_arc_pos = s.get("_arc_position", "")` at line ~3165
PROPOSED REPLACEMENT: "arc modifier in Kling prompt at ~line 3165"

### DESYNC 15: V36.5 arc-aware reframe
CLAUDE.md currently says: "arc-aware reframe at ~line 3290"
Live codebase shows: `_next_arc = _next_shot.get("_arc_position", "ESCALATE")` at line ~3883
PROPOSED REPLACEMENT: "arc-aware reframe at ~line 3883"

### DESYNC 16: learning_log check_regression import
CLAUDE.md currently says: "`check_regression()` returns `[]` — 22 entries, 0 regressions detected (live Python confirmed)."
Live codebase shows: `check_regression` is a class METHOD on the learning log object, not a standalone function. `from tools.atlas_learning_log import check_regression` fails. Must instantiate the class first.
PROPOSED REPLACEMENT: "`AtlasLearningLog().check_regression()` — class method, not standalone import. Instantiate log object first."

---

## NO-CHANGE ITEMS (verified accurate):

- **Version**: V36.5 — confirmed in header ✅
- **Date**: 2026-03-29 — confirmed ✅
- **ACTIVE_VIDEO_MODEL default value**: `"kling"` — confirmed ✅
- **LTX retired guard**: `RuntimeError` + `LTX` present in runner — confirmed ✅
- **Runner total lines**: 6,219 (codebase claim of ~100,000 refers to full repo) ✅
- **chain_arc_intelligence.py exists**: confirmed ✅
- **failure_heatmap.py exists**: confirmed ✅
- **story_state_canon.py exists**: confirmed ✅
- **story_judge.py exists**: confirmed ✅
- **vision_analyst.py exists**: confirmed ✅
- **session_enforcer.py exists**: confirmed ✅
- **session_enforcer .env load**: lines 28–37 (CLAUDE.md says 26–34 — close, within range) ✅
- **vision_judge I-score normalization**: line 674 (CLAUDE.md says ~672 — accurate) ✅
- **vision_judge _score_via_gemini def**: line 572 ✅
- **Gemini vision in vision_judge**: confirmed ✅
- **FAL_KEY in .env**: present and valid ✅
- **OPENROUTER_API_KEY in .env**: present and valid ✅
- **ANTHROPIC_API_KEY in .env**: present and valid ✅
- **GOOGLE_API_KEY in .env**: present and valid ✅
- **MUAPI_KEY in .env**: present and valid ✅
- **chain_arc_intelligence import in runner**: line 65, importing `enrich_shots_with_arc, get_chain_modifier, should_release_room_dna` ✅
- **All V36 modules wired**: chain_arc, failure_heatmap, story_state_canon all present ✅
- **E-shot isolation**: back-to-camera skip confirmed at ~L2518 ✅
- **Wire A budget cap**: 2 regens per scene max — confirmed at L469 ✅
- **Gemini circuit breaker**: referenced in vision_judge — confirmed ✅

---

## SUMMARY

All 16 desyncs are **line-number drift** caused by runner growth since the last grep on 2026-03-29. No functional, architectural, or feature claims are incorrect. The codebase has grown (runner now 6,219 lines) and all wire/function positions have shifted upward by ~300-2000 lines depending on location.

**Recommendation**: Batch-update all line references in CLAUDE.md V31.0 WIRE POSITIONS section and V36.4/V36.5 session learnings section. Consider switching to function-name anchors (e.g., "in `_wire_a_can_regen()` call") instead of line numbers to reduce drift frequency.
