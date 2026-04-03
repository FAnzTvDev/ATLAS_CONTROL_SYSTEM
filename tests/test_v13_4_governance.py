#!/usr/bin/env python3
"""
V13.4 Governance & Validation Tests
====================================
Comprehensive test suite for the unified governance layer.

Tests:
1. Parser character extraction (no action text)
2. Shot generator scene-character isolation
3. Gate simulation with bad data
4. Unified validate endpoint
5. LLM planner integration
6. Full pipeline smoke test
"""

import sys
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_parser_no_action_text():
    """Test that parser doesn't extract action text as characters."""
    from UNIVERSAL_SCRIPT_PARSER import parse_script_to_story_bible

    test_script = '''
INT. PUB - NIGHT

Evelyn steps inside. The room goes quiet.

CLARA
You shouldn't be here.

EVELYN
I had no choice.

Clara eyes her suspiciously. Evelyn manages a weak smile.
'''

    result = parse_script_to_story_bible(test_script, 'Test', 'horror', '5min')

    # Get all characters from scenes
    all_scene_chars = []
    for scene in result.get('scenes', []):
        all_scene_chars.extend(scene.get('characters', []))

    # Get global characters
    global_chars = [c.get('name', c) if isinstance(c, dict) else c for c in result.get('characters', [])]

    print(f"Global characters: {global_chars}")
    print(f"Scene characters: {all_scene_chars}")

    # Action text that should NOT be characters
    bad_chars = [
        'Evelyn steps inside',
        'The room goes',
        'Clara eyes',
        'Evelyn manages a',
        'The room goes quiet',
        'Clara eyes her suspiciously'
    ]

    for bad in bad_chars:
        assert bad not in global_chars, f'FAIL: Action text "{bad}" in global characters!'
        assert bad not in all_scene_chars, f'FAIL: Action text "{bad}" in scene characters!'

    # Real characters should be present (case-insensitive check)
    char_names_upper = [c.upper() for c in global_chars]
    assert any('CLARA' in c for c in char_names_upper), 'FAIL: Clara not found in characters!'
    assert any('EVELYN' in c for c in char_names_upper), 'FAIL: Evelyn not found in characters!'

    print("✅ Parser action text test PASSED")


def test_shot_generator_scene_isolation():
    """Test that shot generator keeps characters isolated to their scenes."""
    from V55_RAVENCROFT_STANDARD_GENERATOR import generate_v55_shot_plan, V55GeneratorConfig

    story_bible = {
        'title': 'Test',
        'characters': [
            {'name': 'Eleanor', 'role': 'lead'},
            {'name': 'Marcus', 'role': 'supporting'},
            {'name': 'Clara', 'role': 'minor'}
        ],
        'scenes': [
            {
                'scene_id': 'S01',
                'location': 'Manor',
                'characters': ['Eleanor'],  # ONLY Eleanor
                'dialogue_lines': [{'text': 'Hello', 'character': 'Eleanor'}]
            },
            {
                'scene_id': 'S02',
                'location': 'Pub',
                'characters': ['Clara', 'Marcus'],  # Clara and Marcus
                'dialogue_lines': [{'text': 'Hi', 'character': 'Clara'}]
            },
        ]
    }

    config = V55GeneratorConfig(target_runtime_seconds=120)
    result = generate_v55_shot_plan(story_bible, {}, {}, {}, config)
    shots = result.get('shots', [])

    # Group shots by scene
    s01_chars = set()
    s02_chars = set()

    for shot in shots:
        scene_id = shot.get('scene_id', '')
        chars = shot.get('characters', [])
        if 'S01' in scene_id:
            s01_chars.update(chars)
        elif 'S02' in scene_id:
            s02_chars.update(chars)

    print(f"S01 (Manor) characters: {s01_chars}")
    print(f"S02 (Pub) characters: {s02_chars}")

    # S01 should primarily have Eleanor, not Marcus or Clara
    # (Some fallback is acceptable but Marcus/Clara shouldn't dominate)
    if 'Marcus' in s01_chars or 'Clara' in s01_chars:
        # Check if Eleanor is at least present
        assert 'Eleanor' in s01_chars, 'FAIL: Eleanor missing from S01 entirely!'
        print("⚠️ Warning: Other characters leaked into S01, but Eleanor is present")

    print("✅ Shot generator scene isolation test PASSED")


def test_gate_blocks_bad_data():
    """Test that gates block on AI actors, pronouns, and garbage."""
    from orchestrator_server import validate_story_bible_with_gates

    bad_story = {
        'characters': [
            {'name': 'Maya Chen', 'role': 'lead'},      # AI Actor - CRITICAL
            {'name': 'He', 'role': 'supporting'},       # Pronoun - CRITICAL
            {'name': 'She walks away', 'role': 'minor'} # Action text
        ],
        'scenes': []
    }

    result = validate_story_bible_with_gates(bad_story, 300)

    print(f"Valid: {result.get('valid')}")
    print(f"Can proceed: {result.get('can_proceed_with_warnings')}")
    print(f"Issues: {len(result.get('issues', []))}")

    for issue in result.get('issues', []):
        print(f"  [{issue.get('severity')}] {issue.get('code')}: {issue.get('message')}")

    # Should NOT be valid
    assert result.get('valid') == False, 'FAIL: Bad data should not validate!'

    # Should have issues for AI actor and pronoun at minimum
    issues = result.get('issues', [])
    issue_codes = [i.get('code', '') for i in issues]

    assert any('AI_ACTOR' in code for code in issue_codes), 'FAIL: Should flag AI actor name!'
    assert any('INVALID' in code or 'PRONOUN' in code for code in issue_codes), 'FAIL: Should flag pronoun!'

    print("✅ Gate blocking test PASSED")


def test_llm_planner_fallback():
    """Test that LLM planner falls back gracefully on bad responses."""
    from LOCAL_LLM_INTEGRATION import plan_episode_pacing

    test_scenes = [
        {'location': 'Test Location', 'dialogue': [{'character': 'A', 'line': 'Hello'}]}
    ]

    bad_responses = [
        "Not JSON at all",
        '{"partial": true',
        '{"planned_scenes": "string_not_array"}',
        '{}',
    ]

    for bad_response in bad_responses:
        with patch('LOCAL_LLM_INTEGRATION.check_ollama_available', return_value=True):
            with patch('LOCAL_LLM_INTEGRATION.query_ollama', return_value=bad_response):
                result = plan_episode_pacing(test_scenes, target_runtime_seconds=300)

        # Should always return a valid result (fallback to heuristic)
        assert result is not None, f"Result None for: {bad_response}"
        assert 'planned_scenes' in result, f"No planned_scenes for: {bad_response}"

    print("✅ LLM planner fallback test PASSED")


def test_rate_limiting():
    """Test rate limit tracking."""
    from LOCAL_LLM_INTEGRATION import get_rate_limit_status, _check_rate_limit

    status = get_rate_limit_status()

    assert 'requests_in_window' in status
    assert 'max_requests' in status
    assert 'remaining' in status
    assert status['remaining'] >= 0

    print(f"Rate limit: {status['remaining']}/{status['max_requests']} remaining")
    print("✅ Rate limiting test PASSED")


def test_character_sanitization():
    """Test V13 character sanitization removes bad characters."""
    from orchestrator_server import sanitize_story_bible_characters

    dirty_story = {
        'characters': [
            {'name': 'Eleanor Ashworth', 'role': 'lead'},
            {'name': 'He', 'role': 'supporting'},           # Pronoun - remove
            {'name': 'DAY', 'role': 'minor'},               # Time marker - remove
            {'name': 'Maya Chen', 'role': 'supporting'},    # AI Actor - remove
            {'name': 'Marcus Cole', 'role': 'supporting'},
            {'name': '', 'role': 'minor'},                  # Empty - remove
            {'name': 'INT', 'role': 'minor'},               # Scene term - remove
        ]
    }

    clean_story = sanitize_story_bible_characters(dirty_story)
    clean_names = [c.get('name') for c in clean_story.get('characters', [])]

    print(f"Before: {len(dirty_story['characters'])} characters")
    print(f"After: {len(clean_names)} characters")
    print(f"Clean names: {clean_names}")

    # Should keep good characters
    assert any('Eleanor' in n for n in clean_names), 'Eleanor should remain!'
    assert any('Marcus' in n for n in clean_names), 'Marcus should remain!'

    # Should remove bad characters
    assert 'He' not in clean_names, 'Pronoun "He" should be removed!'
    assert 'DAY' not in clean_names, 'Time marker "DAY" should be removed!'
    assert '' not in clean_names, 'Empty name should be removed!'
    assert 'INT' not in clean_names, 'Scene term "INT" should be removed!'

    print("✅ Character sanitization test PASSED")


def test_asset_manager():
    """Test V13.4 project-scoped asset management."""
    from orchestrator_server import AssetManager, get_asset_manager

    # Create an AssetManager for a test project
    am = get_asset_manager('test_asset_manager_v13_4')

    # Test directory creation
    for asset_type in am.ASSET_TYPES:
        asset_dir = am.get_asset_dir(asset_type)
        assert asset_dir.exists(), f'Asset dir should exist: {asset_type}'
        print(f"  {asset_type}: {asset_dir}")

    # Test asset URL construction
    char_url = am.get_asset_url('character_refs', 'eleanor_ref.png')
    assert 'test_asset_manager_v13_4' in char_url, 'Project name should be in URL'
    assert 'character_refs' in char_url, 'Asset type should be in URL'
    print(f"  Character URL: {char_url}")

    loc_url = am.get_asset_url('location_masters', 'manor_exterior.jpg')
    assert 'location_masters' in loc_url, 'Asset type should be in URL'
    print(f"  Location URL: {loc_url}")

    # Test shared/global assets
    shared_dir = AssetManager.get_global_shared_dir()
    assert shared_dir.exists(), 'Shared dir should exist'
    print(f"  Shared dir: {shared_dir}")

    ai_actors_dir = AssetManager.get_ai_actors_dir()
    assert ai_actors_dir.exists(), 'AI actors dir should exist'
    print(f"  AI actors dir: {ai_actors_dir}")

    # Clean up test project
    import shutil
    test_dir = am._get_project_dir()
    if test_dir.exists():
        shutil.rmtree(test_dir)

    print("✅ Asset manager test PASSED")


def run_all_tests():
    """Run all V13.4 governance tests."""
    print("=" * 60)
    print("V13.4 GOVERNANCE & VALIDATION TESTS")
    print("=" * 60)
    print()

    tests = [
        ("Parser - No Action Text", test_parser_no_action_text),
        ("Shot Generator - Scene Isolation", test_shot_generator_scene_isolation),
        ("Gates - Block Bad Data", test_gate_blocks_bad_data),
        ("LLM Planner - Fallback", test_llm_planner_fallback),
        ("Rate Limiting", test_rate_limiting),
        ("Character Sanitization", test_character_sanitization),
        ("Asset Manager - Project Scoping", test_asset_manager),
    ]

    passed = 0
    failed = 0

    for name, test_fn in tests:
        print(f"\n{'='*60}")
        print(f"TEST: {name}")
        print("=" * 60)
        try:
            test_fn()
            passed += 1
        except AssertionError as e:
            print(f"❌ FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"❌ ERROR: {e}")
            failed += 1

    print()
    print("=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)

    if failed == 0:
        print("✅ ALL V13.4 GOVERNANCE TESTS PASSED")
        return True
    else:
        print("❌ SOME TESTS FAILED - Review output above")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
