"""
Film Engine V24.0 — Regression Tests
Tests: routing logic, camera token translation, model-specific compilation, cost estimation
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.film_engine import (
    route_shot, translate_camera_tokens, build_camera_zone,
    compile_for_kling, compile_for_ltx, compile_shot_for_model,
    estimate_scene_cost, estimate_project_cost,
    translate_emotion_for_model, RoutingDecision,
    FOCAL_LENGTH_DESCRIPTORS, CAMERA_MOVEMENT_TOKENS,
    EMOTION_TO_PHYSICAL, COLOR_SCIENCE_TOKENS,
)

PASS = 0
FAIL = 0

def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name} — {detail}")


def test_routing_basics():
    print("\n[1] ROUTING BASICS")

    # B-roll → always LTX
    shot = {"_broll": True, "characters": [], "shot_type": "wide"}
    r = route_shot(shot)
    check("B-roll routes to LTX", r.model == "ltx", f"got {r.model}")
    check("B-roll mode is atmo", r.mode == "atmo", f"got {r.mode}")

    # Close-up with character → Kling
    shot = {"characters": ["EVELYN"], "shot_type": "close", "dialogue_text": ""}
    r = route_shot(shot)
    check("Close-up + character → Kling", r.model == "kling", f"got {r.model}")
    check("Close-up mode is identity", r.mode == "identity", f"got {r.mode}")

    # Dialogue shot → Kling
    shot = {"characters": ["EVELYN"], "shot_type": "medium", "dialogue_text": "Hello"}
    r = route_shot(shot)
    check("Dialogue → Kling", r.model == "kling", f"got {r.model}")
    check("Dialogue mode is dialogue", r.mode == "dialogue", f"got {r.mode}")

    # No characters → LTX
    shot = {"characters": [], "shot_type": "wide"}
    r = route_shot(shot)
    check("No chars → LTX", r.model == "ltx", f"got {r.model}")

    # Force override
    shot = {"characters": ["EVELYN"], "shot_type": "close"}
    r = route_shot(shot, force_model="ltx")
    check("Force LTX overrides routing", r.model == "ltx", f"got {r.model}")


def test_routing_advanced():
    print("\n[2] ROUTING ADVANCED")

    # Multi-character medium → Kling (bleed prevention)
    shot = {"characters": ["EVELYN", "VICTOR"], "shot_type": "medium", "dialogue_text": ""}
    r = route_shot(shot)
    check("Multi-char medium → Kling", r.model == "kling", f"got {r.model}")

    # C_EMOTION coverage → Kling
    shot = {"characters": ["EVELYN"], "shot_type": "medium", "coverage_role": "C_EMOTION", "dialogue_text": ""}
    r = route_shot(shot)
    check("C_EMOTION → Kling", r.model == "kling", f"got {r.model}")

    # A_GEOGRAPHY → LTX
    shot = {"characters": ["EVELYN"], "shot_type": "medium", "coverage_role": "A_GEOGRAPHY", "dialogue_text": ""}
    r = route_shot(shot)
    check("A_GEOGRAPHY → LTX", r.model == "ltx", f"got {r.model}")

    # Establishing → LTX
    shot = {"characters": ["EVELYN"], "shot_type": "establishing", "dialogue_text": ""}
    r = route_shot(shot)
    check("Establishing → LTX", r.model == "ltx", f"got {r.model}")

    # Default medium with 1 char → LTX (cost effective)
    shot = {"characters": ["EVELYN"], "shot_type": "medium", "dialogue_text": ""}
    r = route_shot(shot)
    check("Default medium 1-char → LTX", r.model == "ltx", f"got {r.model}")


def test_camera_token_translation():
    print("\n[3] CAMERA TOKEN TRANSLATION")

    # Strip ARRI
    prompt = "Close up, shot on ARRI Alexa 35, Cooke S7/i Prime 85mm"
    result = translate_camera_tokens(prompt)
    check("ARRI stripped", "ARRI" not in result, f"got: {result}")
    check("Cooke stripped", "Cooke" not in result, f"got: {result}")

    # Strip RED (case sensitive)
    prompt = "Wide shot, RED V-Raptor, red hair flowing"
    result = translate_camera_tokens(prompt)
    check("RED camera stripped", "RED V-Raptor" not in result, f"got: {result}")
    check("red hair preserved", "red hair" in result, f"got: {result}")

    # Strip Sony Venice
    prompt = "Medium shot, Sony Venice 2 sensor"
    result = translate_camera_tokens(prompt)
    check("Sony Venice stripped", "Sony Venice" not in result, f"got: {result}")

    # Build camera zone
    zone = build_camera_zone("85mm", "dolly_in", "close", "C_EMOTION")
    check("Camera zone has focal desc", "portrait" in zone.lower() or "85mm" in zone, f"got: {zone}")
    check("Camera zone has movement", "dolly" in zone.lower(), f"got: {zone}")
    check("Camera zone no brands", "ARRI" not in zone and "Cooke" not in zone, f"got: {zone}")


def test_focal_length_descriptors():
    print("\n[4] FOCAL LENGTH DESCRIPTORS")

    check("14mm exists", "14mm" in FOCAL_LENGTH_DESCRIPTORS)
    check("50mm has natural", "natural" in FOCAL_LENGTH_DESCRIPTORS["50mm"].lower())
    check("85mm has portrait", "portrait" in FOCAL_LENGTH_DESCRIPTORS["85mm"].lower())
    check("135mm has compression", "compression" in FOCAL_LENGTH_DESCRIPTORS["135mm"].lower())
    check("All movements defined", len(CAMERA_MOVEMENT_TOKENS) >= 10, f"got {len(CAMERA_MOVEMENT_TOKENS)}")


def test_emotion_translation():
    print("\n[5] EMOTION TRANSLATION")

    # Kling: natural language
    result = translate_emotion_for_model("dread", "kling", "EVELYN")
    check("Kling emotion is natural lang", "fear" in result.lower() or "composure" in result.lower() or "dread" in result.lower(), f"got: {result}")
    check("Kling includes char name", "EVELYN" in result, f"got: {result}")

    # LTX: physical descriptions
    result = translate_emotion_for_model("dread", "ltx", "EVELYN")
    check("LTX emotion has physical", any(w in result.lower() for w in ["jaw", "pupils", "breath", "shoulders"]), f"got: {result}")
    check("LTX includes char name", "EVELYN" in result, f"got: {result}")

    # Grief
    result = translate_emotion_for_model("grief", "ltx")
    check("LTX grief has physical", any(w in result.lower() for w in ["jaw", "breath", "eyes", "glistening"]), f"got: {result}")

    # Unknown emotion fallback — V26.1: uses CPC physical direction or concrete body description
    result = translate_emotion_for_model("bewilderment", "ltx")
    check("Unknown emotion has fallback (V26.1 physical)", len(result) > 10 and "subtle expression" not in result.lower(), f"got: {result}")


def test_model_specific_compilation():
    print("\n[6] MODEL-SPECIFIC COMPILATION")

    context = {
        "shot_details": {"shot_id": "001_01", "scene_id": "001", "shot_type": "close",
                         "coverage_role": "C_EMOTION", "duration": 6,
                         "has_characters": True, "has_dialogue": True,
                         "is_broll": False, "is_chained": False},
        "narrative": {"description": "Evelyn enters", "action": "Evelyn walks through the door",
                      "dialogue": "Hello?", "atmosphere": "tense, cold"},
        "visual_anchor": {"color_grade": "cold desaturated", "genre": "gothic_horror",
                          "camera_body": "ARRI Alexa 35", "camera_style": "handheld",
                          "lens_specs": "85mm", "lens_type": "Cooke S7/i Prime",
                          "location": "INT. MANOR FOYER - NIGHT"},
        "characters": {"EVELYN": {"appearance": "28, dark hair, sharp eyes"}},
        "actor_intent": {"emotion": "dread", "stature": "tense"},
        "wardrobe": {"EVELYN": "dark navy jacket"},
        "chain_context": {},
        "gold_negatives": "NO grid, NO morphing",
        "photo_anchors": {"skin": "natural skin texture"},
        "anti_cgi": "NO CGI look",
        "zone_budgets": {},
    }

    routing_kling = RoutingDecision("kling", "test", 0.9, "identity", 0.56, True)
    routing_ltx = RoutingDecision("ltx", "test", 0.9, "i2v", 0.16, False)

    # Kling compilation
    kling = compile_for_kling("test nano", "test ltx", context, routing_kling)
    check("Kling output has nano", len(kling["nano_prompt"]) > 0, f"empty nano")
    check("Kling nano no ARRI", "ARRI" not in kling["nano_prompt"], f"ARRI found")
    check("Kling nano no Cooke", "Cooke" not in kling["nano_prompt"], f"Cooke found")
    check("Kling has character tag", "[Character" in kling["nano_prompt"], f"no char tag")
    check("Kling has emphasis", "++" in kling["nano_prompt"], f"no emphasis")

    # LTX compilation
    ltx = compile_for_ltx("test nano", "test ltx", context, routing_ltx)
    check("LTX output has nano", len(ltx["nano_prompt"]) > 0, f"empty nano")
    check("LTX nano no ARRI", "ARRI" not in ltx["nano_prompt"], f"ARRI found")
    check("LTX has photo anchors", "skin" in ltx["nano_prompt"].lower(), f"no anchors")
    # V26.1: negative vocabulary moved to _negative_prompt field (Law 264)
    check("LTX has _negative_prompt field (V26.1)", "_negative_prompt" in ltx, f"missing _negative_prompt")
    check("LTX negative has worst quality", "worst quality" in ltx.get("_negative_prompt", "").lower(), f"no worst quality in negative")
    check("LTX positive has NO worst quality", "worst quality" not in ltx["nano_prompt"].lower(), f"worst quality leaked into positive!")


def test_compile_shot_for_model():
    print("\n[7] COMPILE SHOT FOR MODEL (FULL PIPELINE)")

    context = {
        "shot_details": {"shot_id": "003_05", "scene_id": "003", "shot_type": "close",
                         "coverage_role": "C_EMOTION", "duration": 6,
                         "has_characters": True, "has_dialogue": False,
                         "is_broll": False, "is_chained": False},
        "narrative": {"description": "Victor watches", "action": "Victor watches from shadows",
                      "dialogue": "", "atmosphere": "menacing"},
        "visual_anchor": {"color_grade": "cold teal", "genre": "gothic_horror",
                          "camera_body": "ARRI Alexa 35", "camera_style": "static",
                          "lens_specs": "135mm", "lens_type": "Cooke S7/i Prime",
                          "location": "INT. LIBRARY - NIGHT"},
        "characters": {"VICTOR": {"appearance": "45, gaunt, piercing eyes"}},
        "actor_intent": {"emotion": "menace"},
        "wardrobe": {},
        "chain_context": {},
        "gold_negatives": "NO grid",
        "photo_anchors": {},
        "anti_cgi": "",
        "zone_budgets": {},
    }

    shot = {
        "shot_id": "003_05", "scene_id": "003", "shot_type": "close",
        "characters": ["VICTOR"], "dialogue_text": "",
        "nano_prompt": "Close up of Victor, ARRI Alexa 35, Cooke S7/i 135mm",
        "ltx_motion_prompt": "6s, static, character watches",
    }

    result = compile_shot_for_model(shot, context)
    check("Result has model", "model" in result, f"missing model key")
    check("Result routes to kling (close+char)", result.get("model") == "kling", f"got {result.get('model')}")
    check("Result has routing metadata", "routing" in result, f"missing routing")
    check("Nano prompt generated", len(result.get("nano_prompt", "")) > 0, f"empty nano")


def test_cost_estimation():
    print("\n[8] COST ESTIMATION")

    shots = [
        {"shot_id": "001_01", "shot_type": "close", "characters": ["EVELYN"], "dialogue_text": "Hello", "coverage_role": "C_EMOTION"},
        {"shot_id": "001_02", "shot_type": "wide", "characters": ["EVELYN"], "dialogue_text": "", "coverage_role": "A_GEOGRAPHY"},
        {"shot_id": "001_03", "shot_type": "medium", "characters": [], "dialogue_text": "", "_broll": True},
        {"shot_id": "001_04", "shot_type": "close", "characters": ["EVELYN", "VICTOR"], "dialogue_text": "Yes", "coverage_role": "C_EMOTION"},
        {"shot_id": "001_05", "shot_type": "establishing", "characters": [], "dialogue_text": ""},
    ]

    est = estimate_scene_cost(shots)
    check("Estimate has total", est["total_shots"] == 5, f"got {est['total_shots']}")
    check("Has kling shots", est["kling_shots"] >= 2, f"got {est['kling_shots']}")
    check("Has ltx shots", est["ltx_shots"] >= 2, f"got {est['ltx_shots']}")
    check("Cost is positive", est["estimated_cost"] > 0, f"got {est['estimated_cost']}")
    check("Smart routing saves money", est["kling_shots"] + est["ltx_shots"] == 5)

    # Project estimation
    shots2 = shots + [
        {"shot_id": "002_01", "scene_id": "002", "shot_type": "medium", "characters": ["VICTOR"], "dialogue_text": ""},
    ]
    for s in shots[:5]:
        s["scene_id"] = "001"

    proj_est = estimate_project_cost(shots2)
    check("Project has scenes", proj_est["total_scenes"] >= 1, f"got {proj_est['total_scenes']}")
    check("Project has savings", proj_est["smart_routing_savings"] >= 0, f"got {proj_est['smart_routing_savings']}")


def test_color_science_tokens():
    print("\n[9] COLOR SCIENCE TOKENS")

    # V26.1: Film stock brands REMOVED per Law 235/269 — verify they're gone
    check("Gothic horror has NO Kodak (Law 269)", "Kodak" not in COLOR_SCIENCE_TOKENS.get("gothic_horror", ""))
    check("Gothic horror has teal", "teal" in COLOR_SCIENCE_TOKENS.get("gothic_horror", ""))
    check("Period has NO Kodak", "Kodak" not in COLOR_SCIENCE_TOKENS.get("period", ""))
    check("Thriller has NO Fuji", "Fuji" not in COLOR_SCIENCE_TOKENS.get("thriller", ""))
    check("Noir has monochrome", "monochrome" in COLOR_SCIENCE_TOKENS.get("noir", "").lower())
    check("All genres covered", len(COLOR_SCIENCE_TOKENS) >= 7, f"got {len(COLOR_SCIENCE_TOKENS)}")


def test_production_stress():
    """
    Group 10: Production Stress Test — real Victorian Shadows EP1 data.
    Autonomous Build Covenant Rule C: synthetic-only pass is a false positive.
    """
    import json as _json
    print("\n[10] PRODUCTION STRESS TEST (real Victorian Shadows EP1)")

    _sp_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             "pipeline_outputs", "victorian_shadows_ep1", "shot_plan.json")
    if not os.path.exists(_sp_path):
        print("  SKIP  Victorian Shadows shot plan not found")
        return

    with open(_sp_path) as _f:
        _plan = _json.load(_f)
    if isinstance(_plan, list):
        _plan = {"shots": _plan}
    _shots = _plan.get("shots", [])
    if len(_shots) < 20:
        print(f"  SKIP  Only {len(_shots)} shots — need 20+")
        return

    # Load cast_map for routing
    _cast_path = os.path.join(os.path.dirname(_sp_path), "cast_map.json")
    _cast_map = {}
    if os.path.exists(_cast_path):
        with open(_cast_path) as _cf:
            _cast_map = _json.load(_cf)

    # Test A: route_shot works on every real shot without crashing
    _route_errors = 0
    _kling_count = 0
    _ltx_count = 0
    for _s in _shots:
        try:
            _rd = route_shot(_s, _cast_map)
            if _rd.model == "kling":
                _kling_count += 1
            else:
                _ltx_count += 1
        except Exception as _e:
            _route_errors += 1
    check(f"route_shot succeeds on all {len(_shots)} real shots (0 errors)",
          _route_errors == 0, f"{_route_errors} errors")
    check(f"Smart routing splits real shots (Kling: {_kling_count}, LTX: {_ltx_count})",
          _kling_count > 0 and _ltx_count > 0,
          f"Kling={_kling_count}, LTX={_ltx_count}")

    # Test B: translate_camera_tokens doesn't crash on real prompts
    _translate_errors = 0
    for _s in _shots:
        try:
            _np = _s.get("nano_prompt") or _s.get("nano_prompt_final") or ""
            if _np:
                translate_camera_tokens(_np)
        except Exception:
            _translate_errors += 1
    check(f"translate_camera_tokens succeeds on all real prompts",
          _translate_errors == 0, f"{_translate_errors} errors")

    # Test C: estimate_project_cost works on real data
    try:
        _est = estimate_project_cost(_shots)
        check(f"estimate_project_cost returns result for {len(_shots)} shots",
              _est["total_shots"] == len(_shots),
              f"got total_shots={_est.get('total_shots')}")
        _cost = _est.get("estimated_total_cost") or _est.get("estimated_cost", 0)
        check(f"Project cost is positive",
              _cost > 0, f"got ${_cost:.2f}")
    except Exception as _e:
        check("estimate_project_cost doesn't crash on real data", False, str(_e))

    # Test D: compile_shot_for_model on dialogue shots (the hardest case)
    _compile_errors = 0
    _compile_empty = 0
    _dlg_shots = [s for s in _shots if s.get("dialogue_text")][:10]
    for _ds in _dlg_shots:
        try:
            _ctx = {
                "shot_metadata": {
                    "shot_type": _ds.get("shot_type", "medium"),
                    "coverage_role": _ds.get("coverage_role", "B_ACTION"),
                    "has_characters": bool(_ds.get("characters")),
                    "has_dialogue": True,
                    "is_broll": False,
                    "is_chained": False,
                },
                "narrative": {
                    "description": _ds.get("beat_description", ""),
                    "action": _ds.get("_beat_action", ""),
                    "dialogue": _ds.get("dialogue_text", ""),
                    "atmosphere": _ds.get("atmosphere", "tense"),
                },
                "visual_anchor": {
                    "color_grade": _ds.get("_scene_color_grade", "cold teal"),
                    "genre": "gothic_horror",
                    "camera_body": _ds.get("camera_body", ""),
                    "camera_style": _ds.get("camera_style", "static"),
                    "lens_specs": _ds.get("lens_specs", "85mm"),
                    "lens_type": _ds.get("lens_type", ""),
                    "location": _ds.get("location", ""),
                },
                "characters": {c: _cast_map.get(c, {}) for c in (_ds.get("characters") or [])},
                "actor_intent": {"emotion": _ds.get("emotion") or "neutral"},
                "wardrobe": {},
                "chain_context": {},
                "gold_negatives": "NO grid, NO morphing",
                "photo_anchors": {},
                "anti_cgi": "",
                "zone_budgets": {},
            }
            _result = compile_shot_for_model(_ds, _ctx)
            if not _result.get("nano_prompt", ""):
                _compile_empty += 1
        except Exception:
            _compile_errors += 1

    check(f"compile_shot_for_model succeeds on {len(_dlg_shots)} real dialogue shots",
          _compile_errors == 0, f"{_compile_errors} errors")
    check(f"Compiled prompts are non-empty for real dialogue shots",
          _compile_empty == 0, f"{_compile_empty} empty outputs")


# ─────────────────────────────────────
# RUN ALL
# ─────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("ATLAS FILM ENGINE V24.0 — REGRESSION TESTS")
    print("=" * 60)

    test_routing_basics()
    test_routing_advanced()
    test_camera_token_translation()
    test_focal_length_descriptors()
    test_emotion_translation()
    test_model_specific_compilation()
    test_compile_shot_for_model()
    test_cost_estimation()
    test_color_science_tokens()
    test_production_stress()

    print(f"\n{'=' * 60}")
    print(f"RESULTS: {PASS} PASS, {FAIL} FAIL out of {PASS + FAIL} tests")
    print(f"{'=' * 60}")

    sys.exit(1 if FAIL > 0 else 0)
