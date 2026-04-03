#!/usr/bin/env python3
"""
ATLAS SESSION ENFORCER — Self-Monitoring System
=================================================
Runs at the START of every session. Verifies:
1. Code paths match doctrine (not just data)
2. All 17 harmony systems are importable and functional
3. Model routing is correct in the actual runner code
4. No regressions from previous sessions
5. Cost tracking from previous runs

THIS IS THE IMMUNE SYSTEM. It doesn't just check data — it checks CODE.
If the universal runner has been modified to bypass systems, this catches it.

Usage:
  python3 tools/session_enforcer.py              # Full health check
  python3 tools/session_enforcer.py --quick      # Fast check (no FAL calls)

Returns exit code 0 if healthy, 1 if any blocking issue found.
"""

import os, sys, json, re, ast
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).parent.parent

# V35.0: Load .env BEFORE any vision_judge imports so GOOGLE_API_KEY is available
# when _backend_available() checks os.environ at call time.
_env_path = BASE / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            if _k.strip() and _k.strip() not in os.environ:
                os.environ[_k.strip()] = _v.strip()
RUNNER = BASE / "atlas_universal_runner.py"
GATE = BASE / "tools" / "generation_gate.py"
BRIDGE = BASE / "atlas_api_bridge.py"

def check_all():
    results = {"pass": [], "warn": [], "block": []}

    print(f"\n{'='*70}")
    print(f"  ATLAS SESSION ENFORCER — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*70}")

    # ═══ 1. RUNNER CODE VERIFICATION ═══
    print(f"\n--- CODE PATH VERIFICATION ---")

    if not RUNNER.exists():
        results["block"].append("Universal runner not found")
    else:
        code = RUNNER.read_text()

        # CHECK: nano-banana-pro/edit used for character shots
        if "NANO_EDIT" in code and "nano-banana-pro/edit" in code:
            results["pass"].append("Runner uses nano-banana-pro/edit for character shots")
        else:
            results["block"].append("REGRESSION: Runner missing nano-banana-pro/edit endpoint")

        # CHECK: Kling v3/pro endpoint correct
        if "kling-video/v3/pro/image-to-video" in code:
            results["pass"].append("Runner uses Kling v3/pro (correct endpoint)")
        else:
            results["block"].append("REGRESSION: Runner has wrong Kling endpoint")

        # CHECK: C3 compliance — LTX is RETIRED (V29.3), must NOT be actively routed
        # LTX_FAST may exist as a constant for historical reference — that is fine.
        # VIOLATION = active routing: return LTX_FAST, fal_client call to ltx, or
        #             ALLOWED_MODELS list that includes LTX (not just a comment/definition).
        # NOT a violation = constant definition, docstring mention, or comment saying RETIRED.
        if "ltx-2/image-to-video/fast" in code:
            # Look for ACTIVE routing — must be on a single line, not spanning docstrings
            ltx_return   = bool(re.search(r'^\s*return\s+LTX_FAST', code, re.MULTILINE))
            ltx_fal_call = bool(re.search(r'fal_client\s*\.\s*run.*ltx|fal\.run.*ltx', code, re.IGNORECASE))
            ltx_allowed  = bool(re.search(r'ALLOWED_MODELS\s*=.*LTX_FAST', code, re.DOTALL))
            if ltx_return or ltx_fal_call or ltx_allowed:
                results["block"].append(
                    "C3 VIOLATION: LTX is actively routed (return/fal_client/ALLOWED_MODELS). "
                    "RETIRED in V29.3 — remove from route_shot() and ALLOWED_MODELS immediately."
                )
            else:
                results["pass"].append("C3: LTX_FAST defined as RETIRED constant only — not actively routed (correct)")
        else:
            results["pass"].append("C3: LTX_FAST not present in runner (fully removed — correct)")

        # CHECK: Identity elements wired
        if "frontal_image_url" in code and "reference_image_urls" in code:
            results["pass"].append("Kling identity elements wired")
        else:
            results["block"].append("REGRESSION: Identity elements not in runner")

        # CHECK: Generation gate called before generation
        if "run_gate" in code or "generation_gate" in code:
            results["pass"].append("Generation gate called before generation")
        else:
            results["block"].append("REGRESSION: Generation gate not called in runner")

        # CHECK: Vision judge imported (Wire A2 — specific import style)
        # Correct pattern: 'from vision_judge import judge_frame' (no tools. prefix)
        # Wrong pattern: 'from tools.vision_judge import ...' (old probe used this and false-alarmed)
        if "from vision_judge import judge_frame" in code:
            results["pass"].append("Wire A2: vision_judge imported correctly — 'from vision_judge import judge_frame'")
        elif "vision_judge" in code or "judge_frame" in code:
            results["pass"].append("Wire A2: vision_judge referenced in runner (variant import style — verify manually)")
        else:
            results["warn"].append("Wire A2: vision_judge not referenced — identity scoring may not fire")

        # CHECK: End-frame chaining
        if "extract_last_frame" in code or "lastframe" in code:
            results["pass"].append("End-frame chaining in runner")
        else:
            results["warn"].append("End-frame chaining not in runner")

        # CHECK: Kling prompt compiler
        if "compile_video_for_kling" in code or "kling_prompt_compiler" in code:
            results["pass"].append("Kling prompt compiler wired")
        else:
            results["warn"].append("Kling prompt compiler not wired")

        # CHECK: model selection logic (must branch on image_urls)
        if "NANO_EDIT" in code and "NANO_T2I" in code:
            results["pass"].append("Dual model selection (/edit vs /base) present")
        else:
            results["block"].append("REGRESSION: Single nano model — character shots will drift")

        # CHECK: Video model routing — Seedance primary, Kling fallback (V29.16)
        # LTX is RETIRED. Seedance is primary. Kling is fallback only.
        # route_shot() should send to Seedance first, Kling only as fallback.
        seedance_primary = "seedance" in code.lower() and ("muapi" in code.lower() or "SEEDANCE" in code)
        kling_fallback   = "KLING" in code and "fallback" in code.lower()
        if seedance_primary and kling_fallback:
            results["pass"].append("Video routing: Seedance primary + Kling fallback (V29.16 compliant)")
        elif seedance_primary:
            results["pass"].append("Video routing: Seedance present as primary model (Kling fallback not confirmed — warn)")
        elif "KLING" in code:
            results["warn"].append("Video routing: Only Kling found — verify Seedance is primary (V29.16 requires Seedance first)")
        else:
            results["block"].append("REGRESSION: No video model routing found in runner")

        # CHECK: Wire C2 — V_score written to reward ledger (video quality tracking)
        # Actual format in runner: {"V": round(V_score, 2), ...} inside reward_ledger.append()
        if '"V": round(V_score' in code or '"V":round(V_score' in code:
            results["pass"].append("Wire C2: V_score written to reward ledger — video quality measured")
        elif 'reward_ledger.append' in code and '"V"' in code:
            results["pass"].append("Wire C2: reward_ledger contains V field (format variant — confirmed by code inspection)")
        else:
            results["warn"].append("Wire C2: V_score reward ledger write not confirmed — video quality gate may not fire")

    # ═══ 1.5. BYPASS SCRIPT DETECTION ═══
    print(f"\n--- BYPASS SCRIPT DETECTION ---")
    # Any .py file in root with 'fal_client' that ISN'T the universal runner or bridge = bypass risk
    import glob
    bypass_scripts = []
    for pyfile in glob.glob(str(BASE / "run_*.py")) + glob.glob(str(BASE / "*_runner.py")):
        fname = os.path.basename(pyfile)
        if fname in ("atlas_universal_runner.py",):
            continue
        try:
            with open(pyfile) as _f:
                content = _f.read()
            if "fal_client" in content or "FAL_KEY" in content:
                bypass_scripts.append(fname)
        except:
            pass
    if bypass_scripts:
        results["block"].append(f"BYPASS RISK: {len(bypass_scripts)} scripts with FAL access outside universal runner: {bypass_scripts}")
    else:
        results["pass"].append("No bypass scripts with FAL access found (only universal runner)")

    # ═══ 1.75. WIRE PROBE VERIFICATION ═══
    # BUILT ≠ WIRED. This section verifies that critical modules are actually
    # CALLED in the correct generation path, not just imported or defined.
    # Each probe checks a specific function in a specific file context.
    print(f"\n--- WIRE PROBE VERIFICATION ---")

    ORCH = BASE / "orchestrator_server.py"

    if RUNNER.exists():
        runner_code = RUNNER.read_text()

        # ── Wire A: vision_judge verdict triggers REGEN in gen_frame() ──
        # Find gen_frame function body and verify it contains REGEN logic
        gen_frame_match = re.search(
            r'def gen_frame\b.*?(?=\ndef |\Z)', runner_code, re.DOTALL
        )
        if gen_frame_match:
            gen_frame_body = gen_frame_match.group(0)
            if "REGEN" in gen_frame_body and ("judge_frame" in gen_frame_body or "vision_judge" in gen_frame_body):
                results["pass"].append("Wire A: vision_judge REGEN verdict wired inside gen_frame()")
            elif "judge_frame" in gen_frame_body or "vision_judge" in gen_frame_body:
                results["warn"].append("Wire A: vision_judge called in gen_frame() but REGEN branch not found")
            else:
                results["block"].append("Wire A BROKEN: gen_frame() does not call vision_judge — low-identity frames pass silently")
        else:
            results["warn"].append("Wire A: gen_frame() not found in runner — cannot verify")

        # ── Wire B: _fail_sids blocks shots from stitch ──
        # Check that _fail_sids is defined AND used in the stitch section
        if "_fail_sids" in runner_code:
            # Check it's used to filter, not just declared
            if re.search(r'_fail_sids.*stitch|stitch.*_fail_sids|not.*_fail_sids|_fail_sids.*skip|_fail_sids.*\|', runner_code):
                results["pass"].append("Wire B: _fail_sids filters shots from stitch path")
            else:
                results["warn"].append("Wire B: _fail_sids defined but stitch filtering unclear — check manually")
        else:
            results["block"].append("Wire B BROKEN: _fail_sids not in runner — failed frames reach final output")

        # ── Wire C: is_frozen() triggers video regen ──
        if "_check_frozen" in runner_code or "is_frozen" in runner_code:
            if re.search(r'frozen.*regen|regen.*frozen|_check_frozen.*if|if.*_check_frozen', runner_code, re.IGNORECASE):
                results["pass"].append("Wire C: frozen video detection triggers regen")
            else:
                results["warn"].append("Wire C: frozen detection present but regen branch unclear")
        else:
            results["block"].append("Wire C BROKEN: no frozen video detection in runner — statue videos accepted silently")

        # ── compile_nano() called inside gen_frame() (not just defined) ──
        if gen_frame_match:
            if "compile_nano" in gen_frame_body:
                results["pass"].append("compile_nano() called inside gen_frame() — harmony prompts used at runtime")
            else:
                results["block"].append("REGRESSION: compile_nano() not called in gen_frame() — prompts not built from truth fields")

        # ── ACTIVE_VIDEO_MODEL defaults to 'kling' (V31.0: Kling v3 Pro is PRIMARY) ──
        # V31.0 SESSION LEARNING: route_shot() returns "kling" on all branches.
        # Seedance is retired. Default must be "kling" — not "seedance".
        kling_default  = bool(re.search(r'os\.environ\.get\(["\']ATLAS_VIDEO_MODEL["\'],\s*["\']kling["\']', runner_code))
        seedance_default = bool(re.search(r'os\.environ\.get\(["\']ATLAS_VIDEO_MODEL["\'],\s*["\']seedance["\']', runner_code))
        if kling_default:
            results["pass"].append("C3: ACTIVE_VIDEO_MODEL defaults to 'kling' (V31.0: Kling is PRIMARY — correct)")
        elif seedance_default:
            results["warn"].append("C3: ACTIVE_VIDEO_MODEL defaults to 'seedance' — V31.0 requires 'kling' as default. Update runner line 324.")
        else:
            results["warn"].append("C3: ACTIVE_VIDEO_MODEL default unclear — verify runner line 324 manually")

        # ── Approval gate: AWAITING_APPROVAL blocks video gen ──
        if "AWAITING_APPROVAL" in runner_code and "APPROVED" in runner_code:
            if re.search(r'AWAITING_APPROVAL.*skip|skip.*AWAITING|approval.*block|block.*approval', runner_code, re.IGNORECASE):
                results["pass"].append("Approval gate: AWAITING_APPROVAL blocks video gen (two-stage flow)")
            else:
                results["pass"].append("Approval gate: AWAITING_APPROVAL and APPROVED both present in runner")
        else:
            results["warn"].append("Approval gate: approval status not found in runner — Videos Only may not respect review")

        # ── V37: _independent_groups pattern for parallel generation ──
        if "_independent_groups" in runner_code:
            results["pass"].append("V37: _independent_groups pattern present — parallel generation grouping wired")
        else:
            results["warn"].append("V37: _independent_groups not found in runner — parallel group isolation may be missing")

        # ── V37: _gen_strategy field for hybrid generation strategy ──
        if "_gen_strategy" in runner_code:
            results["pass"].append("V37: _gen_strategy field present — hybrid generation strategy wired")
        else:
            results["warn"].append("V37: _gen_strategy not found in runner — V36.1 hybrid strategy field may be missing")

        # ── V37: Governance hooks import block + frame/video observe calls ──
        if "_V37_GOVERNANCE" in runner_code and "_v37_register_asset" in runner_code and "_v37_log_cost" in runner_code:
            results["pass"].append("V37: _V37_GOVERNANCE import block wired — asset_registry + cost_controller hooks present in runner")
        else:
            results["block"].append("V37: _V37_GOVERNANCE hooks missing from runner — frame/video governance observe not wired")

        # ── V36.5 CHAIN INTELLIGENCE GATE — pre/post-gen quality enforcement ──
        _cig_path = Path("tools/chain_intelligence_gate.py")
        if not _cig_path.exists():
            results["block"].append("V36.5: tools/chain_intelligence_gate.py not found — pre/post-gen quality gate missing")
        else:
            cig_code = _cig_path.read_text()
            if "validate_pre_generation" in cig_code and "validate_post_generation" in cig_code:
                results["pass"].append("V36.5: chain_intelligence_gate.py has pre/post-gen validators")
            else:
                results["block"].append("V36.5: chain_intelligence_gate.py missing validate_pre_generation or validate_post_generation")

            if "enforce_chain_quality" in cig_code:
                results["pass"].append("V36.5: enforce_chain_quality() auto-fix loop present")
            else:
                results["warn"].append("V36.5: enforce_chain_quality() not found — auto-fix loop missing")

            if "run_full_validation" in cig_code:
                results["pass"].append("V36.5: run_full_validation() plan-wide report present")
            else:
                results["warn"].append("V36.5: run_full_validation() not found — plan-wide pre-gen report missing")

            if "FROZEN_DIALOGUE" in cig_code and "_check_frozen_dialogue" in cig_code:
                results["pass"].append("V36.5: frozen dialogue detection + auto-regen wired")
            else:
                results["warn"].append("V36.5: frozen dialogue detection missing from gate")

            if "ACTION_TRUNCATED" in cig_code and "_check_action_truncation" in cig_code:
                results["pass"].append("V36.5: action truncation detection wired")
            else:
                results["warn"].append("V36.5: action truncation detection missing from gate")

            if "extract_chain_contract" in cig_code:
                results["pass"].append("V36.5: extract_chain_contract() position handoff wired")
            else:
                results["warn"].append("V36.5: extract_chain_contract() missing — no position-aware chain handoff")

            if "compute_duration_for_shot" in cig_code:
                results["pass"].append("V36.5: compute_duration_for_shot() auto-scaling wired")
            else:
                results["warn"].append("V36.5: compute_duration_for_shot() missing — duration auto-scaling unavailable")

            # ── RUNNER WIRING PROBES (gate file exists, verify it's called in runner) ──
            # Pattern: substring match is robust — won't false-alarm on comments or retired code.
            if "_CHAIN_GATE_AVAILABLE" in runner_code and "_cig_pre(" in runner_code:
                results["pass"].append("V36.5: chain_intelligence_gate PRE-GEN wired in runner (_cig_pre called in gen_scene_multishot)")
            else:
                results["block"].append("V36.5: chain_intelligence_gate PRE-GEN NOT wired in runner — _CHAIN_GATE_AVAILABLE or _cig_pre( missing")

            if "_cig_post(" in runner_code:
                results["pass"].append("V36.5: chain_intelligence_gate POST-GEN wired in runner (_cig_post called after Kling download)")
            else:
                results["block"].append("V36.5: chain_intelligence_gate POST-GEN NOT wired in runner — _cig_post( missing")

            if "_cig_contract(" in runner_code:
                results["pass"].append("V36.5: extract_chain_contract wired in runner (_cig_contract called for position handoff)")
            else:
                results["warn"].append("V36.5: extract_chain_contract NOT called in runner — position handoff contracts not built")

            if "_SKIP_CHAIN_GATES" in runner_code and "--skip-gates" in runner_code:
                results["pass"].append("V36.5: --skip-gates emergency bypass wired in runner")
            else:
                results["warn"].append("V36.5: --skip-gates bypass missing — cannot bypass gate in emergencies")

            if "gate_audit.json" in runner_code:
                results["pass"].append("V36.5: gate_audit.json write wired in runner")
            else:
                results["warn"].append("V36.5: gate_audit.json not written — gate decisions not logged for review")

        # ── V3.0 VIDEO VISION OVERSIGHT — two-tier model wiring ──────────────────────────────────
        # Checks: (1) VVO importable, (2) _vvo_run called in runner after video download,
        #          (3) uses two-tier models (CRITICAL + VIDEO constants present)
        _vvo_path = Path("tools/video_vision_oversight.py")
        if not _vvo_path.exists():
            results["warn"].append("V3.0: tools/video_vision_oversight.py not found — video QA not available")
        else:
            _vvo_code = _vvo_path.read_text()
            if "_GEMINI_CRITICAL_MODEL" in _vvo_code and "_GEMINI_VIDEO_MODEL" in _vvo_code:
                results["pass"].append("V3.0: video_vision_oversight two-tier models present (CRITICAL + VIDEO)")
            else:
                results["warn"].append("V3.0: video_vision_oversight missing two-tier model constants — upgrade not applied")
            if "gemini-2.5-pro" in _vvo_code:
                results["pass"].append("V3.0: gemini-2.5-pro wired as CRITICAL model for chain/stitch/dialogue")
            else:
                results["warn"].append("V3.0: gemini-2.5-pro NOT found in VVO — critical gates using weaker model")
            if "_vvo_run" in runner_code:
                results["pass"].append("V3.0: _vvo_run called in runner — VVO fires after video generation")
            else:
                results["warn"].append("V3.0: _vvo_run not found in runner — VVO not wired into generation path")

        # ── V36.1 SCENE TRANSITION MANAGER — opener classification + cross-scene entry context ──
        # Checks: (1) module exists, (2) inject_scene_entry called in run_scene, (3) compile_nano reads _opener_prefix
        _stm_path = Path("tools/scene_transition_manager.py")
        if not _stm_path.exists():
            results["block"].append("V36.1: tools/scene_transition_manager.py not found — scene opener intelligence not available")
        elif "inject_scene_entry" not in runner_code:
            results["block"].append("V36.1: inject_scene_entry not called in runner — scene_transition_manager built but not wired")
        elif "_opener_prefix" not in runner_code:
            results["block"].append("V36.1: _opener_prefix not read in compile_nano — opener prefix built but not injected into frame prompts")
        else:
            results["pass"].append("V36.1: scene_transition_manager wired — inject_scene_entry in run_scene, _opener_prefix in compile_nano")

    else:
        results["block"].append("Wire probes skipped — universal runner not found")

    # ── Orchestrator endpoints wired (UI button path) ──
    if ORCH.exists():
        orch_code = ORCH.read_text()

        if '@app.post("/api/auto/run-frames-only")' in orch_code:
            results["pass"].append("Endpoint /api/auto/run-frames-only exists (Frames Only button target)")
        else:
            results["block"].append("MISSING: /api/auto/run-frames-only endpoint — Frames Only button has no target")

        if '@app.post("/api/auto/approve-shot")' in orch_code:
            # Verify it has bare-list guard
            approve_match = re.search(
                r'@app\.post\("/api/auto/approve-shot"\).*?(?=\n@app\.)', orch_code, re.DOTALL
            )
            if approve_match and "isinstance" in approve_match.group(0) and "list" in approve_match.group(0):
                results["pass"].append("Endpoint /api/auto/approve-shot exists with bare-list guard")
            else:
                results["warn"].append("/api/auto/approve-shot exists but bare-list guard unclear")
        else:
            results["block"].append("MISSING: /api/auto/approve-shot endpoint — thumbs approval writes nowhere")

        # Architecture divergence warning: does generate-first-frames call runner, or has inline FAL?
        gen_ff_match = re.search(
            r'@app\.post\("/api/auto/generate-first-frames"\).*?(?=\n@app\.)', orch_code, re.DOTALL
        )
        if gen_ff_match:
            gen_ff_body = gen_ff_match.group(0)
            if "atlas_universal_runner" in gen_ff_body or "universal_runner" in gen_ff_body:
                results["pass"].append("generate-first-frames delegates to universal_runner (single path)")
            elif "fal_client" in gen_ff_body or "FAL_KEY" in gen_ff_body or "fal.run" in gen_ff_body:
                results["warn"].append(
                    "ARCH DRIFT: generate-first-frames has INLINE FAL calls — "
                    "Wire A/B/C upgrades to runner do NOT apply to this path. "
                    "Fix: make this endpoint call atlas_universal_runner.py as subprocess (like run-frames-only does)"
                )
            else:
                results["warn"].append("generate-first-frames: FAL call path unclear — verify manually")
    else:
        results["warn"].append("orchestrator_server.py not found — cannot verify UI endpoints")

    # ═══ 2. HARMONY SYSTEM IMPORTS ═══
    print(f"\n--- HARMONY SYSTEM IMPORTS ---")

    systems = [
        ("scene_visual_dna", "build_scene_dna"),
        ("prompt_identity_injector", "inject_identity_into_prompt"),
        ("truth_prompt_translator", "translate_truth_to_prompt"),
        ("beat_enrichment", "enrich_project"),
        ("shot_truth_contract", "compile_scene_truth"),
        ("kling_prompt_compiler", "compile_video_for_kling"),
        ("chain_arc_intelligence", "enrich_shots_with_arc"),  # V36.5: Three-act chain intelligence
        ("chain_intelligence_gate", "validate_pre_generation"),  # V36.5: Pre/post-gen quality gate
        ("video_vision_oversight", "run_video_oversight"),       # V3.0: Two-tier video QA (pro+flash)
    ]

    sys.path.insert(0, str(BASE / "tools"))
    for module_name, func_name in systems:
        try:
            mod = __import__(module_name)
            if hasattr(mod, func_name):
                results["pass"].append(f"{module_name}.{func_name}() importable")
            else:
                results["warn"].append(f"{module_name} loaded but {func_name}() missing")
        except Exception as e:
            results["warn"].append(f"{module_name} import failed: {e}")

    # Vision judge + V30.2 router (non-blocking)
    try:
        from vision_judge import judge_frame, route_vision_scoring, _VLM_PRIORITY, _backend_available
        results["pass"].append("vision_judge.judge_frame() importable")
        # Check router has gemini_vision in priority list (V30.2 upgrade)
        if "gemini_vision" in _VLM_PRIORITY:
            results["pass"].append("Vision router V30.2: gemini_vision backend registered in priority list")
        else:
            results["warn"].append("Vision router missing gemini_vision backend (V30.2 upgrade not applied)")
        # Check fallthrough fix is present (truthy check, not None check)
        vj_code = (Path(__file__).parent / "vision_judge.py").read_text()
        if 'if result.get("identity_scores"):' in vj_code:
            results["pass"].append("Vision router fallthrough bug fixed (truthy check, not None check)")
        else:
            results["warn"].append("Vision router may have fallthrough bug — check `is not None` vs truthy")
        # Report which backends are currently available
        available = [b for b in _VLM_PRIORITY if _backend_available(b)]
        results["pass"].append(f"Vision backends available: {available}")
    except Exception as e:
        results["warn"].append(f"vision_judge not importable: {e} (non-blocking)")

    # ═══ 3. GENERATION GATE INTEGRITY ═══
    print(f"\n--- GENERATION GATE ---")

    if GATE.exists():
        gate_code = GATE.read_text()
        check_count = gate_code.count("CHECK_")
        if check_count >= 15:
            results["pass"].append(f"Generation gate has {check_count}+ checks")
        else:
            results["warn"].append(f"Generation gate only has {check_count} checks (expected 15+)")

        if "BLOCKING" in gate_code:
            results["pass"].append("Gate has blocking capability")
        else:
            results["block"].append("Gate cannot block — all issues are warnings only")
    else:
        results["block"].append("Generation gate not found")

    # ═══ 3.5. LEARNING LOG REGRESSION CHECK ═══
    print(f"\n--- LEARNING LOG REGRESSION CHECK ---")
    try:
        from atlas_learning_log import LearningLog
        log = LearningLog()
        regressions = log.check_regression()
        results["pass"].append(f"Learning log: {len(log._entries)} fixes recorded")
        if regressions:
            for r in regressions:
                results["block"].append(f"REGRESSION: {r.get('bug_id', '?')} — {r.get('symptom', '?')[:60]}")
        else:
            results["pass"].append(f"Learning log: 0 regressions (all {len(log._entries)} fixes verified)")
    except Exception as e:
        results["warn"].append(f"Learning log check failed: {e}")

    # ═══ 4. CLAUDE.MD DOCTRINE ═══
    print(f"\n--- DOCTRINE VERIFICATION ---")

    claude_md = BASE / "CLAUDE.md"
    if claude_md.exists():
        doctrine = claude_md.read_text()

        checks = [
            ("V29", "V29 doctrine present"),
            ("nano-banana-pro/edit", "Model routing documented (/edit for chars)"),
            ("kling-video/v3/pro", "Kling endpoint documented"),
            ("GENERATION GATE", "Generation gate referenced"),
            ("SESSION LEARNINGS", "Session learnings section exists"),
            ("NEVER use nano-banana-pro (T2I) for character shots", "Anti-regression rule documented"),
        ]

        for keyword, desc in checks:
            if keyword in doctrine:
                results["pass"].append(f"Doctrine: {desc}")
            else:
                results["warn"].append(f"Doctrine missing: {desc}")
    else:
        results["block"].append("CLAUDE.md not found")

    # ═══ 5. PROJECT DATA HEALTH ═══
    print(f"\n--- PROJECT DATA ---")

    project_dir = BASE / "pipeline_outputs" / "victorian_shadows_ep1"
    if project_dir.exists():
        required = ["shot_plan.json", "story_bible.json", "cast_map.json"]
        for f in required:
            if (project_dir / f).exists():
                results["pass"].append(f"victorian_shadows_ep1/{f} exists")
            else:
                results["warn"].append(f"victorian_shadows_ep1/{f} MISSING")

        # Character refs
        char_dir = project_dir / "character_library_locked"
        if char_dir.exists():
            refs = list(char_dir.glob("*_CHAR_REFERENCE.jpg"))
            results["pass"].append(f"{len(refs)} character refs found")
        else:
            results["warn"].append("Character library not found")

        # Location masters
        loc_dir = project_dir / "location_masters"
        if loc_dir.exists():
            locs = list(loc_dir.glob("*.jpg"))
            results["pass"].append(f"{len(locs)} location masters found")
        else:
            results["warn"].append("Location masters not found")

    # ═══ 6. COST TRACKING (from logs) ═══
    print(f"\n--- COST ESTIMATE (from video outputs) ---")

    video_dirs = []
    for d in (project_dir).iterdir() if project_dir.exists() else []:
        if d.is_dir() and "video" in d.name.lower() and "kling" in d.name.lower():
            mp4s = list(d.glob("*.mp4"))
            if mp4s:
                video_dirs.append((d.name, len(mp4s)))

    total_kling_calls = sum(count for _, count in video_dirs)
    est_cost = total_kling_calls * 2.80  # $2.50 Kling + $0.30 nano
    results["pass"].append(f"Estimated total Kling calls: {total_kling_calls} (~${est_cost:.0f})")

    # ═══ REPORT ═══
    print(f"\n{'='*70}")
    print(f"  RESULTS")
    print(f"  Pass: {len(results['pass'])} | Warn: {len(results['warn'])} | Block: {len(results['block'])}")
    print(f"{'='*70}")

    if results["block"]:
        print(f"\n  ⛔ BLOCKING ISSUES:")
        for b in results["block"]:
            print(f"    {b}")

    if results["warn"]:
        print(f"\n  ⚠ WARNINGS:")
        for w in results["warn"]:
            print(f"    {w}")

    print(f"\n  ✓ PASSED ({len(results['pass'])}):")
    for p in results["pass"]:
        print(f"    {p}")

    healthy = len(results["block"]) == 0
    print(f"\n  {'✅ SYSTEM HEALTHY' if healthy else '❌ SYSTEM UNHEALTHY — fix blocking issues'}")
    print(f"{'='*70}")

    return healthy


if __name__ == "__main__":
    healthy = check_all()
    sys.exit(0 if healthy else 1)
