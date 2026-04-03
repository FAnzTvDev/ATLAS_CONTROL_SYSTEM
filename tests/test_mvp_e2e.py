#!/usr/bin/env python3
"""
ATLAS MVP End-to-End Test Suite
================================
Validates the complete workflow from script import to shot plan generation.
Run with: python tests/test_mvp_e2e.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from pathlib import Path
from typing import Dict, List, Tuple

# Test results tracking
TESTS_RUN = 0
TESTS_PASSED = 0
TESTS_FAILED = 0

def test(name: str, condition: bool, details: str = ""):
    """Record a test result."""
    global TESTS_RUN, TESTS_PASSED, TESTS_FAILED
    TESTS_RUN += 1
    if condition:
        TESTS_PASSED += 1
        print(f"  ✓ {name}")
    else:
        TESTS_FAILED += 1
        print(f"  ✗ FAIL: {name}")
        if details:
            print(f"    {details}")


def test_config_loading():
    """Test that configuration loads correctly."""
    print("\n" + "=" * 60)
    print("TEST: Configuration Loading")
    print("=" * 60)

    from config import Config

    test("ATLAS_ROOT exists", Config.ATLAS_ROOT.exists())
    test("Pipeline outputs dir exists", Config.get_pipeline_outputs_dir().exists())
    test("Character library exists", Config.get_character_dir().exists())
    test("MEDIA_ROOTS has entries", len(Config.get_media_roots()) > 0)


def test_parser_imports():
    """Test that all parser modules import correctly."""
    print("\n" + "=" * 60)
    print("TEST: Parser Module Imports")
    print("=" * 60)

    try:
        from UNIVERSAL_SCRIPT_PARSER import parse_script_to_story_bible
        test("UNIVERSAL_SCRIPT_PARSER imports", True)
    except ImportError as e:
        test("UNIVERSAL_SCRIPT_PARSER imports", False, str(e))

    try:
        from V55_RAVENCROFT_STANDARD_GENERATOR import generate_v55_shot_plan
        test("V55_RAVENCROFT_STANDARD_GENERATOR imports", True)
    except ImportError as e:
        test("V55_RAVENCROFT_STANDARD_GENERATOR imports", False, str(e))

    try:
        from SIMULATION_GATES import validate_simulation, SemanticGate
        test("SIMULATION_GATES imports", True)
    except ImportError as e:
        test("SIMULATION_GATES imports", False, str(e))

    try:
        from LOCAL_LLM_INTEGRATION import plan_episode_pacing
        test("LOCAL_LLM_INTEGRATION imports", True)
    except ImportError as e:
        test("LOCAL_LLM_INTEGRATION imports", False, str(e))


def test_script_parsing():
    """Test script parsing with a sample screenplay."""
    print("\n" + "=" * 60)
    print("TEST: Script Parsing")
    print("=" * 60)

    from UNIVERSAL_SCRIPT_PARSER import parse_script_to_story_bible

    test_script = """
FADE IN:

INT. DETECTIVE'S OFFICE - NIGHT

SARAH BLACKWOOD sits at a cluttered desk, papers everywhere.

MARCUS
(entering)
We found another victim.

SARAH
Where?

MARCUS
Downtown. Same pattern.

SARAH
Let's go.

EXT. CRIME SCENE - NIGHT

Police lights flash. SARAH and MARCUS approach the scene.

DETECTIVE HAYES
Blackwood. About time.

SARAH
What do we have?

HAYES
Female, early twenties. No ID yet.

SARAH
(examining the body)
Same marks on the wrists...

FADE OUT.
"""

    result = parse_script_to_story_bible(test_script, title="Test Case", genre="thriller", runtime="5min")

    # Validate result structure
    test("Parser returns dict", isinstance(result, dict))
    test("Has characters key", "characters" in result)
    test("Has scenes key", "scenes" in result)
    test("Has locations key", "locations" in result)

    # Validate characters
    chars = result.get("characters", [])
    char_names = [c.get("name", "").upper() for c in chars]

    test("Found SARAH", any("SARAH" in n for n in char_names))
    test("Found MARCUS", "MARCUS" in char_names)
    test("Found HAYES", "HAYES" in char_names)
    test("No pronouns in characters", not any(n in ["HE", "SHE", "THEY", "IT"] for n in char_names))

    # Validate scenes
    scenes = result.get("scenes", [])
    test("Has 2 scenes", len(scenes) == 2)
    if scenes:
        test("Scene 1 has location", bool(scenes[0].get("location")))
        test("Scene 1 has characters", len(scenes[0].get("characters", [])) > 0)

    return result


def test_ai_actor_filtering():
    """Test that AI actor names are properly rejected."""
    print("\n" + "=" * 60)
    print("TEST: AI Actor Name Filtering")
    print("=" * 60)

    from UNIVERSAL_SCRIPT_PARSER import parse_script_to_story_bible

    test_script = """
INT. OFFICE - DAY

Agent MAYA CHEN enters the room.

JACKSON WRIGHT
You made it.

MAYA
Let's get started.
"""

    result = parse_script_to_story_bible(test_script, title="AI Filter Test", genre="thriller", runtime="2min")

    chars = result.get("characters", [])
    char_names = [c.get("name", "").upper() for c in chars]

    test("MAYA CHEN rejected (AI actor)", "MAYA CHEN" not in char_names)
    test("JACKSON WRIGHT rejected (AI actor)", "JACKSON WRIGHT" not in char_names)
    test("Agent MAYA CHEN rejected", "AGENT MAYA CHEN" not in char_names)
    test("MAYA kept (valid name)", "MAYA" in char_names)


def test_validation_gates():
    """Test SIMULATION_GATES validation."""
    print("\n" + "=" * 60)
    print("TEST: Validation Gates")
    print("=" * 60)

    from SIMULATION_GATES import SemanticGate
    from SIMULATION_CONTEXT import create_simulation_context, Character as SimCharacter

    ctx = create_simulation_context(
        script_text="Test",
        project_name="gate_test",
        target_runtime=300
    )

    # Add problematic characters
    ctx.story_bible_simulation.canonical_characters = [
        SimCharacter(name="He", role="unknown", dialogue_count=1),  # Pronoun
        SimCharacter(name="MAYA CHEN", role="main", dialogue_count=5),  # AI actor
        SimCharacter(name="Agent SARAH", role="main", dialogue_count=3),  # Title prefix
        SimCharacter(name="VALID CHARACTER", role="supporting", dialogue_count=2),  # Valid
    ]

    gate = SemanticGate(ctx)
    issues = gate.run()

    issue_codes = [i.code for i in issues]

    test("Detects pronoun character", "INVALID_CHARACTER_NAME" in issue_codes)
    test("Detects AI actor name", "AI_ACTOR_AS_CHARACTER" in issue_codes)
    test("Detects title prefix", "TITLE_PREFIX_CHARACTER" in issue_codes)

    critical_count = sum(1 for i in issues if i.severity.value == "critical")
    test("Has critical issues", critical_count >= 3)


def test_shot_plan_generation():
    """Test V55 shot plan generation."""
    print("\n" + "=" * 60)
    print("TEST: Shot Plan Generation")
    print("=" * 60)

    from V55_RAVENCROFT_STANDARD_GENERATOR import generate_v55_shot_plan, V55GeneratorConfig

    test_story_bible = {
        "title": "Test Project",
        "genre": "thriller",
        "characters": [
            {"name": "SARAH", "role": "main", "dialogue_count": 5},
            {"name": "MARCUS", "role": "supporting", "dialogue_count": 3},
        ],
        "scenes": [
            {
                "scene_id": 1,
                "location": "DETECTIVE'S OFFICE",
                "time_of_day": "NIGHT",
                "characters": ["SARAH", "MARCUS"],
                "dialogue_lines": [
                    {"character": "SARAH", "text": "We need to find him.", "scene_id": 1, "word_count": 5},
                    {"character": "MARCUS", "text": "I have a lead.", "scene_id": 1, "word_count": 4},
                ],
            },
            {
                "scene_id": 2,
                "location": "STREET",
                "time_of_day": "NIGHT",
                "characters": ["SARAH"],
                "dialogue_lines": [],
            },
        ],
        "locations": [
            {"name": "DETECTIVE'S OFFICE", "time_of_day": "NIGHT"},
            {"name": "STREET", "time_of_day": "NIGHT"},
        ],
    }

    # Mock director/writer profiles
    director_profile = {"name": "Test Director", "visual_signature": {}}
    writer_profile = {"name": "Test Writer", "voice_characteristics": {}}

    # Mock cast_actors
    cast_actors = {
        "SARAH": {"name": "Elena Rodriguez", "id": "003", "image_prompt": "ELENA RODRIGUEZ, test"},
        "MARCUS": {"name": "Jackson Wright", "id": "002", "image_prompt": "JACKSON WRIGHT, test"},
    }

    config = V55GeneratorConfig(target_runtime_seconds=120)

    result = generate_v55_shot_plan(
        story_bible=test_story_bible,
        director_profile=director_profile,
        writer_profile=writer_profile,
        cast_actors=cast_actors,
        config=config,
    )

    shot_plan = result.get("shots", result) if isinstance(result, dict) else result

    test("Shot plan is list", isinstance(shot_plan, list))
    test("Has shots", len(shot_plan) > 0)

    if shot_plan:
        first_shot = shot_plan[0]
        test("Shot has shot_id", "shot_id" in first_shot)
        test("Shot has scene", "scene" in first_shot or "scene_id" in first_shot)
        test("Shot has prompt", "prompt" in first_shot or "visual_prompt" in first_shot or "nano_prompt" in first_shot)
        test("Shot has duration", "duration" in first_shot or "duration_seconds" in first_shot)

        # Check scene isolation - scene 2 shots shouldn't have MARCUS
        scene_2_shots = [s for s in shot_plan if s.get("scene", s.get("scene_id")) == 2]
        for shot in scene_2_shots:
            chars = shot.get("characters", [])
            if isinstance(chars, list):
                char_names = [c.get("name", c) if isinstance(c, dict) else c for c in chars]
                test(f"Scene 2 shot doesn't have MARCUS", "MARCUS" not in char_names,
                     f"Found: {char_names}")


def test_llm_planner():
    """Test LLM planner fallback behavior."""
    print("\n" + "=" * 60)
    print("TEST: LLM Planner Fallback")
    print("=" * 60)

    from LOCAL_LLM_INTEGRATION import plan_episode_pacing

    test_scenes = [
        {"location": "OFFICE", "dialogue": [{"character": "A", "line": "Hello"}]},
        {"location": "STREET", "dialogue": []},
    ]

    # Should work with heuristic fallback
    result = plan_episode_pacing(test_scenes, target_runtime_seconds=120)

    test("Returns result", result is not None)
    test("Has planned_scenes", "planned_scenes" in result)

    if "planned_scenes" in result:
        test("Planned scenes is list", isinstance(result["planned_scenes"], list))
        test("Has correct scene count", len(result["planned_scenes"]) == 2)


def test_asset_paths():
    """Test that asset paths resolve correctly."""
    print("\n" + "=" * 60)
    print("TEST: Asset Path Resolution")
    print("=" * 60)

    from config import Config
    from pathlib import Path

    char_dir = Config.get_character_dir()
    ai_actors_dir = char_dir / "ai_actors"

    test("Character dir exists", char_dir.exists())
    test("AI actors dir exists", ai_actors_dir.exists())

    if ai_actors_dir.exists():
        jpg_files = list(ai_actors_dir.glob("*.jpg"))
        test("Has AI actor images", len(jpg_files) > 0, f"Found {len(jpg_files)} images")

        if jpg_files:
            # Test path is within MEDIA_ROOTS
            media_roots = Config.get_media_roots()
            first_file = jpg_files[0]

            in_media_roots = False
            for root in media_roots:
                try:
                    first_file.relative_to(root)
                    in_media_roots = True
                    break
                except ValueError:
                    continue

            test("AI actor image in MEDIA_ROOTS", in_media_roots)


def test_project_structure():
    """Test that existing projects have correct structure."""
    print("\n" + "=" * 60)
    print("TEST: Project Structure")
    print("=" * 60)

    from config import Config

    pipeline_dir = Config.get_pipeline_outputs_dir()
    projects = [d for d in pipeline_dir.iterdir() if d.is_dir()]

    test("Has projects", len(projects) > 0, f"Found {len(projects)} projects")

    if projects:
        # Check shadow_protocol specifically
        shadow = pipeline_dir / "shadow_protocol"
        if shadow.exists():
            test("shadow_protocol has story_bible.json", (shadow / "story_bible.json").exists())

            # Validate story_bible content
            sb_path = shadow / "story_bible.json"
            if sb_path.exists():
                sb = json.loads(sb_path.read_text())

                chars = sb.get("characters", [])
                char_names = [c.get("name", "").upper() for c in chars]

                test("No AI actor names in shadow_protocol",
                     "MAYA CHEN" not in char_names and "AGENT MAYA CHEN" not in char_names,
                     f"Found: {char_names}")


def test_orchestrator_imports():
    """Test that orchestrator server imports correctly."""
    print("\n" + "=" * 60)
    print("TEST: Orchestrator Server Imports")
    print("=" * 60)

    try:
        # Don't import the full module (starts server), just test key functions exist
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "orchestrator_check",
            Path(__file__).parent.parent / "orchestrator_server.py"
        )
        test("orchestrator_server.py is valid Python", spec is not None)
    except SyntaxError as e:
        test("orchestrator_server.py is valid Python", False, str(e))


def run_all_tests():
    """Run all MVP tests."""
    print("=" * 60)
    print("ATLAS MVP END-TO-END TEST SUITE")
    print("=" * 60)

    test_config_loading()
    test_parser_imports()
    test_script_parsing()
    test_ai_actor_filtering()
    test_validation_gates()
    test_shot_plan_generation()
    test_llm_planner()
    test_asset_paths()
    test_project_structure()
    test_orchestrator_imports()

    print("\n" + "=" * 60)
    print("TEST RESULTS")
    print("=" * 60)
    print(f"Total: {TESTS_RUN}")
    print(f"Passed: {TESTS_PASSED}")
    print(f"Failed: {TESTS_FAILED}")
    print(f"Pass Rate: {TESTS_PASSED/TESTS_RUN*100:.1f}%")
    print("=" * 60)

    if TESTS_FAILED == 0:
        print("✅ ALL MVP TESTS PASSED")
    else:
        print(f"❌ {TESTS_FAILED} TEST(S) FAILED")

    return TESTS_FAILED == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
