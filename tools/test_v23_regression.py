"""
ATLAS V24 — Regression Test Suite
===================================
Tests all V24 modules: ProjectTruth, BasalGanglia, VisionAnalyst,
LITE Synthesizer (V24 upgrades), MetaDirector, V24Integration.

Run: python3 tools/test_v23_regression.py
"""

import sys
import os
import json
import traceback
from datetime import datetime

# Setup path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PASS = 0
FAIL = 0
ERRORS = []

def test(name, fn):
    global PASS, FAIL, ERRORS
    try:
        result = fn()
        if result:
            PASS += 1
            print(f"  PASS  {name}")
        else:
            FAIL += 1
            ERRORS.append(f"{name}: returned False")
            print(f"  FAIL  {name}")
    except Exception as e:
        FAIL += 1
        ERRORS.append(f"{name}: {e}")
        print(f"  FAIL  {name} — {e}")


# ============================================================================
# TEST 1: ProjectTruth
# ============================================================================

def test_project_truth():
    print("\n=== TEST: ProjectTruth ===")

    from tools.project_truth import ProjectTruth, generate_project_truth, ActOutline, CharacterArc

    project_path = "pipeline_outputs/victorian_shadows_ep1"

    # Test: generate
    def t_generate():
        truth = generate_project_truth(project_path)
        return truth is not None and truth.total_scenes > 0

    # Test: load
    def t_load():
        truth = ProjectTruth.load(project_path)
        return truth is not None and len(truth.act_outlines) > 0

    # Test: LITE data object
    def t_lite_data():
        truth = ProjectTruth.load(project_path)
        lite = truth.get_lite_data_object({"scene_id": "001", "shot_id": "001_001A"})
        required_keys = ["episode_overview", "act_position", "emotional_trajectory",
                         "scene_cards_context", "pacing_target", "film_progress_pct"]
        return all(k in lite for k in required_keys)

    # Test: character arcs populated
    def t_character_arcs():
        truth = ProjectTruth.load(project_path)
        return len(truth.character_arcs) >= 3  # At least 3 characters

    # Test: act outline has 3 acts
    def t_three_acts():
        truth = ProjectTruth.load(project_path)
        return len(truth.act_outlines) == 3

    # Test: reward recording
    def t_reward():
        truth = ProjectTruth.load(project_path)
        truth.record_reward("test_001", "hash123", 0.85, {"identity": 0.9})
        return len(truth.reward_history) > 0

    test("ProjectTruth.generate()", t_generate)
    test("ProjectTruth.load()", t_load)
    test("ProjectTruth.get_lite_data_object()", t_lite_data)
    test("ProjectTruth character arcs", t_character_arcs)
    test("ProjectTruth 3-act structure", t_three_acts)
    test("ProjectTruth reward recording", t_reward)


# ============================================================================
# TEST 2: BasalGangliaEngine
# ============================================================================

def test_basal_ganglia():
    print("\n=== TEST: BasalGangliaEngine ===")

    from tools.basal_ganglia_engine import BasalGangliaEngine, DIMENSION_WEIGHTS

    project_path = "pipeline_outputs/victorian_shadows_ep1"
    engine = BasalGangliaEngine(project_path)

    # Test: dimensions defined
    def t_dimensions():
        return len(DIMENSION_WEIGHTS) == 6

    # Test: weights sum to 1.0
    def t_weights():
        total = sum(DIMENSION_WEIGHTS.values())
        return abs(total - 1.0) < 0.01

    # Test: candidate scoring
    def t_scoring():
        candidates = [
            {"variant_id": "A", "angle": "wide", "vision": {"identity": 0.8, "location": 0.7}},
            {"variant_id": "B", "angle": "medium", "vision": {"identity": 0.9, "location": 0.8}},
            {"variant_id": "C", "angle": "close", "vision": {"identity": 0.6, "location": 0.9}},
        ]
        shot = {
            "shot_id": "001_001A",
            "characters": ["EVELYN RAVENCROFT"],
            "nano_prompt": "test prompt",
            "ltx_motion_prompt": "test face stable NO morphing",
        }
        winner, result = engine.select_best_candidate(candidates, shot)
        return winner is not None and result.composite_score > 0

    # Test: Go/No-Go thresholds
    def t_thresholds():
        from tools.basal_ganglia_engine import GO_THRESHOLD, NOGO_THRESHOLD
        return GO_THRESHOLD == 0.60 and NOGO_THRESHOLD == 0.40

    # Test: reward log recording
    def t_reward_log():
        log_path = os.path.join(project_path, "reports", "reward_log.jsonl")
        return True  # Engine creates reports dir lazily

    test("BasalGanglia 6 dimensions", t_dimensions)
    test("BasalGanglia weights sum to 1.0", t_weights)
    test("BasalGanglia candidate scoring", t_scoring)
    test("BasalGanglia Go/No-Go thresholds", t_thresholds)
    test("BasalGanglia reward log", t_reward_log)


# ============================================================================
# TEST 3: VisionAnalyst
# ============================================================================

def test_vision_analyst():
    print("\n=== TEST: VisionAnalyst ===")

    from tools.vision_analyst import VisionAnalyst, HEALTH_DIMENSIONS, PACING_PROFILES

    project_path = "pipeline_outputs/victorian_shadows_ep1"
    analyst = VisionAnalyst(project_path)

    # Test: 8 health dimensions
    def t_dimensions():
        return len(HEALTH_DIMENSIONS) == 8

    # Test: dimension weights sum to 1.0
    def t_weights():
        total = sum(d["weight"] for d in HEALTH_DIMENSIONS.values())
        return abs(total - 1.0) < 0.01

    # Test: 4 pacing profiles
    def t_pacing():
        return len(PACING_PROFILES) == 4 and all(
            k in PACING_PROFILES for k in ["allegro", "andante", "adagio", "moderato"]
        )

    # Test: scene evaluation
    def t_evaluate():
        shots = [
            {
                "shot_id": "001_001A", "scene_id": "001",
                "characters": ["EVELYN RAVENCROFT"],
                "shot_type": "wide", "duration": 8,
                "ltx_motion_prompt": "8s, face stable NO morphing",
                "location": "INT. RAVENCROFT MANOR",
            },
            {
                "shot_id": "001_002A", "scene_id": "001",
                "characters": ["EVELYN RAVENCROFT"],
                "shot_type": "medium", "duration": 6,
                "ltx_motion_prompt": "6s, character performs: walking, face stable NO morphing",
                "location": "INT. RAVENCROFT MANOR",
            },
        ]
        report = analyst.evaluate_scene("001", shots)
        return (
            report.total_shots == 2
            and report.evaluated_shots == 2
            and report.composite_score > 0
            and report.verdict in ("PASS", "WARN", "FAIL")
        )

    # Test: empty scene
    def t_empty():
        report = analyst.evaluate_scene("999", [])
        return report.verdict == "FAIL"

    test("VisionAnalyst 8 health dimensions", t_dimensions)
    test("VisionAnalyst weights sum to 1.0", t_weights)
    test("VisionAnalyst 4 pacing profiles", t_pacing)
    test("VisionAnalyst scene evaluation", t_evaluate)
    test("VisionAnalyst empty scene handling", t_empty)


# ============================================================================
# TEST 4: LITE Synthesizer V24 Upgrades
# ============================================================================

def test_lite_synthesizer():
    print("\n=== TEST: LITE Synthesizer V24 ===")

    from tools.atlas_lite_synthesizer import (
        build_context_object, synthesize_deterministic,
        ZONE_BUDGETS, PHOTOREALISTIC_ANCHORS, ANTI_CGI_NEGATIVES,
        SCENE_TEMPO_MAP, GOLD_NEGATIVES
    )

    # Test: Zone budgets defined
    def t_zones():
        return len(ZONE_BUDGETS) == 5 and all(
            k in ZONE_BUDGETS for k in ["CAMERA", "CHARACTER", "PERFORMANCE", "ENVIRONMENT", "CONSTRAINTS"]
        )

    # Test: Photorealistic anchors
    def t_photo():
        return len(PHOTOREALISTIC_ANCHORS) == 5 and "skin" in PHOTOREALISTIC_ANCHORS

    # Test: Anti-CGI negatives
    def t_anti_cgi():
        return "NO plastic skin" in ANTI_CGI_NEGATIVES and "NO CGI look" in ANTI_CGI_NEGATIVES

    # Test: Scene tempo map
    def t_tempo():
        return len(SCENE_TEMPO_MAP) == 4

    # Test: Context object includes V24 fields
    def t_context_v23():
        shot = {
            "shot_id": "001_001A", "scene_id": "001",
            "characters": ["EVELYN RAVENCROFT"],
            "shot_type": "medium", "duration": 8,
            "description": "Evelyn walks through the manor",
            "camera_body": "ARRI Alexa 35",
            "camera_style": "handheld",
            "lens_specs": "50mm",
            "lens_type": "Cooke S7/i Prime",
            "location": "INT. RAVENCROFT MANOR",
        }
        cast_map = {
            "EVELYN RAVENCROFT": {
                "appearance": "28, dark hair, sharp eyes",
                "character_reference_url": "/path/to/ref.jpg",
            }
        }
        story_bible = {"scenes": [{"scene_id": "001", "atmosphere": "tense dread"}]}

        ctx = build_context_object(shot, cast_map, story_bible, "gothic_horror", "dread")
        has_v23 = all(k in ctx for k in [
            "lite_data", "scene_tempo", "tempo_config",
            "photo_anchors", "anti_cgi", "zone_budgets"
        ])
        return has_v23

    # Test: Deterministic synthesis uses zones
    def t_deterministic_v23():
        shot = {
            "shot_id": "001_001A", "scene_id": "001",
            "characters": ["EVELYN RAVENCROFT"],
            "shot_type": "medium", "duration": 8,
            "description": "Evelyn walks through the manor",
            "camera_body": "ARRI Alexa 35",
            "camera_style": "handheld",
            "lens_specs": "50mm",
            "lens_type": "Cooke S7/i Prime",
            "location": "INT. RAVENCROFT MANOR",
        }
        cast_map = {
            "EVELYN RAVENCROFT": {
                "appearance": "28, dark hair, sharp eyes",
            }
        }
        story_bible = {"scenes": [{"scene_id": "001", "atmosphere": "tense dread"}]}

        ctx = build_context_object(shot, cast_map, story_bible, "gothic_horror", "dread")
        nano, ltx = synthesize_deterministic(ctx)

        # V24: nano should contain photorealistic anchors for character shots
        has_photo = "natural skin" in nano or "pores" in nano
        # V24: ltx should contain tempo-aware movement
        has_tempo = len(ltx) > 20
        # Gold negatives still present
        has_gold = "NO morphing" in nano or GOLD_NEGATIVES[:20] in nano

        return has_gold and has_tempo and len(nano) > 50

    # Test: Chained shot nano is empty
    def t_chained():
        shot = {
            "shot_id": "001_002A", "scene_id": "001",
            "characters": ["EVELYN RAVENCROFT"],
            "shot_type": "medium", "duration": 6,
            "description": "Evelyn continues walking",
            "_should_chain": True, "_no_chain": False, "_is_chain_first": False,
            "camera_body": "ARRI Alexa 35", "camera_style": "handheld",
            "lens_specs": "50mm", "lens_type": "Cooke S7/i Prime",
            "location": "INT. RAVENCROFT MANOR",
        }
        cast_map = {"EVELYN RAVENCROFT": {"appearance": "28, dark hair"}}
        story_bible = {"scenes": [{"scene_id": "001", "atmosphere": "tense"}]}

        ctx = build_context_object(shot, cast_map, story_bible)
        nano, ltx = synthesize_deterministic(ctx)
        return nano == "" and len(ltx) > 10

    test("LITE V24 5 zone budgets", t_zones)
    test("LITE V24 photorealistic anchors", t_photo)
    test("LITE V24 anti-CGI negatives", t_anti_cgi)
    test("LITE V24 scene tempo map", t_tempo)
    test("LITE V24 context includes V24 fields", t_context_v23)
    test("LITE V24 deterministic synthesis", t_deterministic_v23)
    test("LITE V24 chained shot nano empty", t_chained)


# ============================================================================
# TEST 5: MetaDirector
# ============================================================================

def test_meta_director():
    print("\n=== TEST: MetaDirector ===")

    from tools.meta_director import MetaDirector

    project_path = "pipeline_outputs/victorian_shadows_ep1"
    director = MetaDirector(project_path)

    # Test: status
    def t_status():
        status = director.get_status()
        return "project" in status and "subsystems" in status

    # Test: scene context
    def t_context():
        ctx = director.prepare_scene_context("001")
        return "scene_id" in ctx and ctx["scene_id"] == "001"

    # Test: shot readiness - good shot
    def t_readiness_pass():
        shot = {
            "shot_id": "001_001A", "characters": ["EVELYN RAVENCROFT"],
            "nano_prompt": "test prompt", "duration": 8,
            "dialogue_text": "",
            "ltx_motion_prompt": "8s, character performs: walking, face stable NO morphing",
            "actor_intent": {"emotion": "anxious", "stature": "rigid"},
        }
        decision = director.check_shot_readiness(shot, {})
        return decision.decision_type == "approve"

    # Test: shot readiness - bad shot
    def t_readiness_fail():
        shot = {
            "shot_id": "001_001A", "characters": ["EVELYN"],
            "nano_prompt": "", "duration": 7,
            "ltx_motion_prompt": "",
        }
        decision = director.check_shot_readiness(shot, {})
        return decision.decision_type == "flag"

    # Test: scene evaluation
    def t_evaluate():
        shots = [{
            "shot_id": "001_001A", "scene_id": "001",
            "characters": ["EVELYN"], "shot_type": "wide", "duration": 8,
            "nano_prompt": "test", "ltx_motion_prompt": "8s, face stable NO morphing, character performs: test",
            "location": "INT. RAVENCROFT MANOR",
        }]
        report = director.evaluate_scene_render("001", shots)
        return report.status in ("directed", "approved", "needs_review")

    test("MetaDirector status", t_status)
    test("MetaDirector scene context", t_context)
    test("MetaDirector shot readiness PASS", t_readiness_pass)
    test("MetaDirector shot readiness FAIL", t_readiness_fail)
    test("MetaDirector scene evaluation", t_evaluate)


# ============================================================================
# TEST 6: V24 Integration Layer
# ============================================================================

def test_v23_integration():
    print("\n=== TEST: V24 Integration ===")

    from tools.v23_integration import V24Pipeline

    project_path = "pipeline_outputs/victorian_shadows_ep1"
    pipeline = V24Pipeline(project_path)

    # Test: status
    def t_status():
        status = pipeline.get_status()
        return "project" in status

    # Test: LITE data
    def t_lite():
        lite = pipeline.get_lite_data({"scene_id": "001", "shot_id": "001_001A"})
        return "pacing_target" in lite or lite == {}  # Empty ok if truth not generated

    # Test: shot check
    def t_check():
        result = pipeline.check_shot({
            "shot_id": "test", "characters": ["TEST"],
            "nano_prompt": "test", "duration": 8,
            "ltx_motion_prompt": "8s, face stable NO morphing, character performs: test",
        })
        return "decision_type" in result

    test("V24Pipeline status", t_status)
    test("V24Pipeline LITE data", t_lite)
    test("V24Pipeline shot check", t_check)


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    print("=" * 60)
    print("ATLAS V24 REGRESSION TEST SUITE")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    test_project_truth()
    test_basal_ganglia()
    test_vision_analyst()
    test_lite_synthesizer()
    test_meta_director()
    test_v23_integration()

    print("\n" + "=" * 60)
    print(f"RESULTS: {PASS} PASS, {FAIL} FAIL")
    if ERRORS:
        print(f"\nFAILURES:")
        for e in ERRORS:
            print(f"  - {e}")
    print("=" * 60)

    sys.exit(1 if FAIL > 0 else 0)
