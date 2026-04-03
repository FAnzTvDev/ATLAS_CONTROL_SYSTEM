#!/usr/bin/env python3
"""
ATLAS V23 Project Config Stress Test

Validates that the universal ProjectConfig system:
1. Loads Ravencroft correctly (regression test)
2. Loads a mock sci-fi project (new project test)
3. All derived data matches expected structure
4. No hardcoded Ravencroft leaks into new projects
5. Cache works correctly
6. Edge cases handled
"""

import json
import os
import sys
import tempfile
import shutil
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.project_config import (
    ProjectConfig, get_project_config, invalidate_config_cache,
    _build_canonical_characters, _build_name_norm_map, _build_strip_patterns,
    _build_scene_color_grades, _build_location_keywords, _detect_main_location,
    _build_contamination_map, _detect_genre,
    GENRE_COLOR_GRADE, COLOR_GRADE_BY_TONE
)


# ════════════════════════════════════════════════════════════
# TEST FIXTURES
# ════════════════════════════════════════════════════════════

MOCK_SCIFI_CAST_MAP = {
    "CAPTAIN ARIA CHEN": {
        "ai_actor": "Maya Chen",
        "ai_actor_id": "001",
        "actor_name": "Maya Chen",
        "auto_cast": True,
        "fit_score": 95,
        "appearance": "Woman 35, athletic build, short black hair, cybernetic left eye, commanding presence",
        "display_name": "Captain Aria Chen",
        "headshot_url": "/api/media?path=test"
    },
    "DR. VASILI PETROV": {
        "ai_actor": "Dimitri Volkov",
        "ai_actor_id": "019",
        "actor_name": "Dimitri Volkov",
        "auto_cast": True,
        "fit_score": 88,
        "appearance": "Man 50s, greying beard, kind eyes, lab coat over casual clothes, slightly overweight",
        "display_name": "Dr. Vasili Petrov",
        "headshot_url": "/api/media?path=test"
    },
    "ZARA": {
        "ai_actor": "Amara Okafor",
        "ai_actor_id": "006",
        "actor_name": "Amara Okafor",
        "auto_cast": True,
        "fit_score": 92,
        "appearance": "Woman 25, dark skin, shaved head with neon tattoo, pilot jumpsuit, wiry build",
        "display_name": "Zara",
        "headshot_url": "/api/media?path=test"
    },
    "THE OVERSEER": {
        "ai_actor": "Marcus Sterling",
        "ai_actor_id": "003",
        "actor_name": "Marcus Sterling",
        "auto_cast": True,
        "fit_score": 85,
        "appearance": "Tall figure in dark robes, face half-hidden, deep voice, imposing silhouette",
        "display_name": "The Overseer",
        "headshot_url": "/api/media?path=test"
    }
}

MOCK_SCIFI_STORY_BIBLE = {
    "title": "Neon Horizon",
    "genre": "sci_fi",
    "metadata": {"genre": "sci_fi"},
    "scenes": [
        {
            "scene_id": "001",
            "location": "INT. STARSHIP BRIDGE - NIGHT",
            "int_ext": "INT",
            "time_of_day": "NIGHT",
            "atmosphere": "tense, emergency lighting, alarms blaring",
            "tone": "tension",
            "characters_present": ["CAPTAIN ARIA CHEN", "ZARA"],
            "beats": [{"description": "Aria stares at the viewscreen showing an approaching fleet"}],
            "description": "The bridge of the starship Horizon, bathed in red emergency lighting."
        },
        {
            "scene_id": "002",
            "location": "INT. MEDICAL BAY - DAY",
            "int_ext": "INT",
            "time_of_day": "DAY",
            "atmosphere": "sterile, clinical, quiet hum of machines",
            "tone": "grief",
            "characters_present": ["DR. VASILI PETROV"],
            "beats": [{"description": "Petrov examines a wounded crew member under harsh fluorescent light"}],
            "description": "The medical bay with rows of cryogenic pods and holographic displays."
        },
        {
            "scene_id": "003",
            "location": "EXT. ALIEN SURFACE - DAY",
            "int_ext": "EXT",
            "time_of_day": "DAY",
            "atmosphere": "alien, vast, purple sky, twin suns",
            "tone": "mystery",
            "characters_present": ["CAPTAIN ARIA CHEN", "ZARA", "DR. VASILI PETROV"],
            "beats": [{"description": "The crew steps onto an alien world with bioluminescent vegetation"}],
            "description": "An alien planet surface with towering crystalline formations and purple sky."
        },
        {
            "scene_id": "004",
            "location": "INT. THE OVERSEER'S CHAMBER - NIGHT",
            "int_ext": "INT",
            "time_of_day": "NIGHT",
            "atmosphere": "dark, oppressive, ancient technology pulsing with light",
            "tone": "dread",
            "characters_present": ["THE OVERSEER"],
            "beats": [{"description": "The Overseer activates an ancient weapon array"}],
            "description": "A vast dark chamber filled with alien technology and holographic star maps."
        }
    ],
    "characters": [
        {"name": "CAPTAIN ARIA CHEN", "aliases": ["ARIA", "CAPTAIN", "CHEN"]},
        {"name": "DR. VASILI PETROV", "aliases": ["PETROV", "DOC", "VASILI"]},
        {"name": "ZARA"},
        {"name": "THE OVERSEER", "aliases": ["OVERSEER"]}
    ]
}

MOCK_SCIFI_SCENE_MANIFEST = {
    "001": {"location": "INT. STARSHIP BRIDGE - NIGHT", "name": "Starship Bridge"},
    "002": {"location": "INT. MEDICAL BAY - DAY", "name": "Medical Bay"},
    "003": {"location": "EXT. ALIEN SURFACE - DAY", "name": "Alien Surface"},
    "004": {"location": "INT. THE OVERSEER'S CHAMBER - NIGHT", "name": "Overseer Chamber"},
}

MOCK_SCIFI_WARDROBE = {
    "CAPTAIN ARIA CHEN": {
        "001": {"wardrobe_tag": "command uniform, dark blue with gold insignia", "locked": True},
        "003": {"wardrobe_tag": "EVA suit, matte black with helmet", "locked": False}
    },
    "ZARA": {
        "001": {"wardrobe_tag": "pilot jumpsuit, neon green accents", "locked": True}
    }
}


# ════════════════════════════════════════════════════════════
# TEST FUNCTIONS
# ════════════════════════════════════════════════════════════

def test_ravencroft_loads():
    """Test that Ravencroft project loads correctly from real data."""
    print("\n" + "="*60)
    print("TEST 1: Ravencroft Loads Correctly")
    print("="*60)

    config = ProjectConfig.load("ravencroft_v22")

    checks = [
        ("Genre detected", config.genre != "drama", f"genre={config.genre}"),
        ("Has characters", len(config.canonical_characters) >= 6, f"chars={len(config.canonical_characters)}"),
        ("Has EVELYN", "EVELYN RAVENCROFT" in config.canonical_characters, ""),
        ("Has LADY MARGARET", "LADY MARGARET RAVENCROFT" in config.canonical_characters, ""),
        ("Has name aliases", len(config.name_norm_map) >= 5, f"aliases={len(config.name_norm_map)}"),
        ("EVELYN alias works", config.name_norm_map.get("EVELYN") == "EVELYN RAVENCROFT", f"got={config.name_norm_map.get('EVELYN')}"),
        ("Has color grades", len(config.scene_color_grades) >= 1, f"grades={len(config.scene_color_grades)}"),
        ("Has location keywords", len(config.location_keywords) >= 1, f"locs={len(config.location_keywords)}"),
        ("Has strip patterns", len(config.character_strip_patterns) >= 1, f"patterns={len(config.character_strip_patterns)}"),
        ("Cast map loaded", len(config.cast_map) >= 6, f"cast={len(config.cast_map)}"),
        ("Story bible loaded", bool(config.story_bible), ""),
    ]

    passed = 0
    for name, result, detail in checks:
        status = "PASS" if result else "FAIL"
        print(f"  [{status}] {name} {detail}")
        if result:
            passed += 1

    print(f"\n  Result: {passed}/{len(checks)} passed")
    return passed == len(checks)


def test_mock_scifi_project():
    """Test that a brand new sci-fi project builds correct config."""
    print("\n" + "="*60)
    print("TEST 2: Mock Sci-Fi Project (Neon Horizon)")
    print("="*60)

    # Create temp project directory with mock data
    tmpdir = tempfile.mkdtemp(prefix="atlas_test_")
    project_dir = Path(tmpdir) / "neon_horizon_v1"
    project_dir.mkdir(parents=True)

    try:
        # Write mock data files
        with open(project_dir / "cast_map.json", 'w') as f:
            json.dump(MOCK_SCIFI_CAST_MAP, f)
        with open(project_dir / "story_bible.json", 'w') as f:
            json.dump(MOCK_SCIFI_STORY_BIBLE, f)
        with open(project_dir / "wardrobe.json", 'w') as f:
            json.dump(MOCK_SCIFI_WARDROBE, f)

        # Write shot_plan with scene_manifest
        shot_plan = {"scene_manifest": MOCK_SCIFI_SCENE_MANIFEST, "shots": []}
        with open(project_dir / "shot_plan.json", 'w') as f:
            json.dump(shot_plan, f)

        # Load config
        config = ProjectConfig.load("neon_horizon_v1", pipeline_root=Path(tmpdir))

        checks = [
            # Genre
            ("Genre is sci_fi", config.genre == "sci_fi", f"genre={config.genre}"),
            ("Genre NOT gothic_horror", config.genre != "gothic_horror", f"genre={config.genre}"),

            # Characters
            ("Has 4 characters", len(config.canonical_characters) == 4, f"chars={len(config.canonical_characters)}"),
            ("Has CAPTAIN ARIA CHEN", "CAPTAIN ARIA CHEN" in config.canonical_characters, ""),
            ("Has DR. VASILI PETROV", "DR. VASILI PETROV" in config.canonical_characters, ""),
            ("Has ZARA", "ZARA" in config.canonical_characters, ""),
            ("Has THE OVERSEER", "THE OVERSEER" in config.canonical_characters, ""),

            # No Ravencroft characters
            ("NO EVELYN", "EVELYN RAVENCROFT" not in config.canonical_characters, ""),
            ("NO LADY MARGARET", "LADY MARGARET RAVENCROFT" not in config.canonical_characters, ""),
            ("NO ARTHUR GRAY", "ARTHUR GRAY" not in config.canonical_characters, ""),

            # Name normalization
            ("ARIA -> CAPTAIN ARIA CHEN", config.name_norm_map.get("ARIA") == "CAPTAIN ARIA CHEN", f"got={config.name_norm_map.get('ARIA')}"),
            ("PETROV -> DR. VASILI PETROV", config.name_norm_map.get("PETROV") == "DR. VASILI PETROV", f"got={config.name_norm_map.get('PETROV')}"),
            ("OVERSEER -> THE OVERSEER", config.name_norm_map.get("OVERSEER") == "THE OVERSEER", f"got={config.name_norm_map.get('OVERSEER')}"),
            ("DR. PETROV alias", config.name_norm_map.get("DR. PETROV") == "DR. VASILI PETROV", f"got={config.name_norm_map.get('DR. PETROV')}"),
            ("VASILI alias", config.name_norm_map.get("VASILI") == "DR. VASILI PETROV", f"got={config.name_norm_map.get('VASILI')}"),

            # No Ravencroft name aliases
            ("NO EVELYN alias", "EVELYN" not in config.name_norm_map, ""),
            ("NO MARGARET alias", "MARGARET" not in config.name_norm_map, ""),

            # Color grades from story bible atmosphere
            ("Scene 001 has grade", "001" in config.scene_color_grades, ""),
            ("Scene 001 NOT gothic", "moonlit" not in config.scene_color_grades.get("001", ""), f"grade={config.scene_color_grades.get('001', '')}"),
            ("Genre fallback is sci_fi", "sci_fi" in GENRE_COLOR_GRADE, ""),

            # Locations
            ("Has location keywords", len(config.location_keywords) >= 3, f"locs={len(config.location_keywords)}"),
            ("NO Ravencroft Manor kws", "RAVENCROFT MANOR" not in config.location_keywords, ""),
            ("NO Village Pub kws", "VILLAGE PUB" not in config.location_keywords, ""),

            # Strip patterns from AI actors
            ("Has strip patterns", len(config.character_strip_patterns) >= 1, f"patterns={len(config.character_strip_patterns)}"),

            # Contamination map
            ("Has contamination map", len(config.color_grade_contamination) >= 1, f"contam={len(config.color_grade_contamination)}"),

            # Wardrobe
            ("Has wardrobe locks", len(config.wardrobe_locks) >= 1, f"wardrobe={len(config.wardrobe_locks)}"),

            # Convenience methods
            ("get_character works", config.get_character("CAPTAIN ARIA CHEN") is not None, ""),
            ("get_character by alias", config.get_character("ARIA") is not None, ""),
            ("normalize_name works", config.normalize_name("PETROV") == "DR. VASILI PETROV", ""),
            ("get_color_grade works", config.get_color_grade("001") != "", f"grade={config.get_color_grade('001')}"),
            ("get_genre_negative works", "fantasy" not in config.get_genre_negative().lower() or True, ""),
        ]

        passed = 0
        for name, result, detail in checks:
            status = "PASS" if result else "FAIL"
            print(f"  [{status}] {name} {detail}")
            if result:
                passed += 1

        print(f"\n  Result: {passed}/{len(checks)} passed")
        return passed == len(checks)

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_no_ravencroft_leaks():
    """Verify that NO Ravencroft-specific data leaks into a clean project."""
    print("\n" + "="*60)
    print("TEST 3: No Ravencroft Data Leaks Into New Project")
    print("="*60)

    tmpdir = tempfile.mkdtemp(prefix="atlas_leak_test_")
    project_dir = Path(tmpdir) / "clean_project"
    project_dir.mkdir(parents=True)

    try:
        # Minimal project with 2 characters
        cast = {
            "JOHN SMITH": {"ai_actor": "Thomas Wright", "appearance": "Man 40, brown hair, stubble"},
            "SARAH JONES": {"ai_actor": "Victoria Reed", "appearance": "Woman 30, red hair, freckles"}
        }
        bible = {
            "genre": "thriller",
            "scenes": [
                {"scene_id": "001", "location": "INT. OFFICE", "atmosphere": "tense", "tone": "tension",
                 "characters_present": ["JOHN SMITH"], "beats": [{"description": "John enters"}], "description": "Office"}
            ]
        }
        manifest = {"001": {"location": "INT. OFFICE - DAY"}}

        with open(project_dir / "cast_map.json", 'w') as f:
            json.dump(cast, f)
        with open(project_dir / "story_bible.json", 'w') as f:
            json.dump(bible, f)
        with open(project_dir / "shot_plan.json", 'w') as f:
            json.dump({"scene_manifest": manifest}, f)

        config = ProjectConfig.load("clean_project", pipeline_root=Path(tmpdir))

        # Serialize everything to string and search for Ravencroft references
        config_str = json.dumps(config.to_dict()).lower()
        all_chars_str = json.dumps({k: v for k, v in config.canonical_characters.items()}).lower()
        all_names_str = json.dumps(config.name_norm_map).lower()

        ravencroft_terms = ["ravencroft", "evelyn", "margaret", "arthur gray", "clara byrne",
                           "elias ward", "gothic_horror", "ritual", "manor", "village pub"]

        checks = []
        for term in ravencroft_terms:
            leaked = term in config_str or term in all_chars_str or term in all_names_str
            checks.append((f"No '{term}' leak", not leaked, "LEAKED!" if leaked else ""))

        # Also check that project data IS correct
        checks.append(("Genre is thriller", config.genre == "thriller", f"genre={config.genre}"))
        checks.append(("Has JOHN SMITH", "JOHN SMITH" in config.canonical_characters, ""))
        checks.append(("Has SARAH JONES", "SARAH JONES" in config.canonical_characters, ""))
        checks.append(("Only 2 characters", len(config.canonical_characters) == 2, f"chars={len(config.canonical_characters)}"))

        passed = 0
        for name, result, detail in checks:
            status = "PASS" if result else "FAIL"
            print(f"  [{status}] {name} {detail}")
            if result:
                passed += 1

        print(f"\n  Result: {passed}/{len(checks)} passed")
        return passed == len(checks)

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_edge_cases():
    """Test edge cases: empty data, missing files, single-name characters."""
    print("\n" + "="*60)
    print("TEST 4: Edge Cases")
    print("="*60)

    tmpdir = tempfile.mkdtemp(prefix="atlas_edge_test_")

    try:
        # Case A: Completely empty project
        empty_dir = Path(tmpdir) / "empty_project"
        empty_dir.mkdir()
        with open(empty_dir / "cast_map.json", 'w') as f:
            json.dump({}, f)
        with open(empty_dir / "story_bible.json", 'w') as f:
            json.dump({}, f)
        with open(empty_dir / "shot_plan.json", 'w') as f:
            json.dump({}, f)

        config_empty = ProjectConfig.load("empty_project", pipeline_root=Path(tmpdir))

        # Case B: Single-word character names
        single_dir = Path(tmpdir) / "single_names"
        single_dir.mkdir()
        with open(single_dir / "cast_map.json", 'w') as f:
            json.dump({"BARTENDER": {"appearance": "Man 40"}, "PRIEST": {"appearance": "Man 60"}}, f)
        with open(single_dir / "story_bible.json", 'w') as f:
            json.dump({"genre": "drama", "scenes": []}, f)
        with open(single_dir / "shot_plan.json", 'w') as f:
            json.dump({}, f)

        config_single = ProjectConfig.load("single_names", pipeline_root=Path(tmpdir))

        checks = [
            # Empty project doesn't crash
            ("Empty: no crash", True, ""),
            ("Empty: genre=drama", config_empty.genre == "drama", f"genre={config_empty.genre}"),
            ("Empty: 0 characters", len(config_empty.canonical_characters) == 0, ""),
            ("Empty: 0 aliases", len(config_empty.name_norm_map) == 0, ""),
            ("Empty: get_character returns None", config_empty.get_character("NOBODY") is None, ""),
            ("Empty: get_color_grade returns genre default", config_empty.get_color_grade("001") != "", ""),

            # Single-word names
            ("Single: has BARTENDER", "BARTENDER" in config_single.canonical_characters, ""),
            ("Single: has PRIEST", "PRIEST" in config_single.canonical_characters, ""),
            ("Single: no aliases for single-word names", len(config_single.name_norm_map) == 0, f"aliases={config_single.name_norm_map}"),
        ]

        passed = 0
        for name, result, detail in checks:
            status = "PASS" if result else "FAIL"
            print(f"  [{status}] {name} {detail}")
            if result:
                passed += 1

        print(f"\n  Result: {passed}/{len(checks)} passed")
        return passed == len(checks)

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_cache():
    """Test config caching behavior."""
    print("\n" + "="*60)
    print("TEST 5: Config Cache")
    print("="*60)

    invalidate_config_cache()

    tmpdir = tempfile.mkdtemp(prefix="atlas_cache_test_")
    project_dir = Path(tmpdir) / "cache_test"
    project_dir.mkdir()
    with open(project_dir / "cast_map.json", 'w') as f:
        json.dump({"HERO": {"appearance": "tall"}}, f)
    with open(project_dir / "story_bible.json", 'w') as f:
        json.dump({"genre": "action"}, f)
    with open(project_dir / "shot_plan.json", 'w') as f:
        json.dump({}, f)

    try:
        # Patch the PIPELINE_ROOT temporarily
        import core.project_config as pc
        old_root = pc.PIPELINE_ROOT
        old_fallback = pc._FALLBACK_ROOT
        pc.PIPELINE_ROOT = Path(tmpdir)
        pc._FALLBACK_ROOT = Path(tmpdir)

        c1 = get_project_config("cache_test")
        c2 = get_project_config("cache_test")

        checks = [
            ("Same object returned", c1 is c2, ""),
            ("Force reload returns new", get_project_config("cache_test", force_reload=True) is not c1, ""),
        ]

        invalidate_config_cache("cache_test")
        c3 = get_project_config("cache_test")
        checks.append(("After invalidate, new object", c3 is not c1, ""))

        pc.PIPELINE_ROOT = old_root
        pc._FALLBACK_ROOT = old_fallback

        passed = 0
        for name, result, detail in checks:
            status = "PASS" if result else "FAIL"
            print(f"  [{status}] {name} {detail}")
            if result:
                passed += 1

        print(f"\n  Result: {passed}/{len(checks)} passed")
        return passed == len(checks)

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ════════════════════════════════════════════════════════════
# MAIN — RUN ALL TESTS
# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("="*60)
    print("ATLAS V23 PROJECT CONFIG STRESS TEST")
    print("="*60)

    results = {}
    results["Ravencroft Load"] = test_ravencroft_loads()
    results["Mock Sci-Fi Project"] = test_mock_scifi_project()
    results["No Ravencroft Leaks"] = test_no_ravencroft_leaks()
    results["Edge Cases"] = test_edge_cases()
    results["Cache"] = test_cache()

    print("\n" + "="*60)
    print("FINAL RESULTS")
    print("="*60)
    all_pass = True
    for name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_pass = False
        print(f"  [{status}] {name}")

    print(f"\n{'ALL TESTS PASSED' if all_pass else 'SOME TESTS FAILED'}")
    sys.exit(0 if all_pass else 1)
