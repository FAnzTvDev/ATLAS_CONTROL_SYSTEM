#!/usr/bin/env python3
"""
Test suite for composition_cache.py
Quick validation of core functionality
"""

import json
import tempfile
import os
from pathlib import Path

# Test imports
try:
    from composition_cache import (
        CompositionKey,
        CacheEntry,
        CompositionCache,
        should_reuse,
        get_reuse_source,
        analyze_reuse_opportunities,
    )
    print("✓ All imports successful")
except ImportError as e:
    print(f"✗ Import failed: {e}")
    exit(1)


def test_composition_key():
    """Test CompositionKey creation and serialization."""
    print("\n[TEST] CompositionKey")
    
    key = CompositionKey(
        scene_id="001",
        shot_type="wide",
        lens_class="wide",
        characters_present=frozenset({"ARTHUR GRAY", "EVELYN RAVENCROFT"}),
        camera_angle="eye_level",
        location="RAVENCROFT MANOR - FOYER",
    )
    
    # Test hashability
    key_set = {key}
    assert len(key_set) == 1
    print("  ✓ CompositionKey is hashable")
    
    # Test serialization
    data = key.to_dict()
    assert data["scene_id"] == "001"
    assert isinstance(data["characters_present"], list)
    print("  ✓ to_dict() serialization works")
    
    # Test deserialization
    key2 = CompositionKey.from_dict(data)
    assert key == key2
    print("  ✓ from_dict() deserialization works")


def test_cache_entry():
    """Test CacheEntry creation and serialization."""
    print("\n[TEST] CacheEntry")
    
    entry = CacheEntry(
        shot_id="001_shot_a",
        frame_path="/pipeline_outputs/test/first_frames/001_shot_a.jpg",
        frame_url="/api/media?path=/first_frames/001_shot_a.jpg",
        timestamp="2026-03-04T14:30:00Z",
        usage_count=0,
    )
    
    # Test serialization
    data = entry.to_dict()
    assert data["shot_id"] == "001_shot_a"
    print("  ✓ to_dict() serialization works")
    
    # Test deserialization
    entry2 = CacheEntry.from_dict(data)
    assert entry2.shot_id == entry.shot_id
    print("  ✓ from_dict() deserialization works")


def test_composition_cache():
    """Test CompositionCache core functionality."""
    print("\n[TEST] CompositionCache")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = CompositionCache(project="test_project", pipeline_outputs_dir=tmpdir)
        
        # Test shot data
        shots = [
            {
                "shot_id": "001_shot_a",
                "scene_id": "001",
                "shot_type": "wide",
                "lens_specs": "24mm",
                "camera_angle": "eye_level",
                "location": "RAVENCROFT MANOR - FOYER",
                "characters": ["EVELYN RAVENCROFT", "ARTHUR GRAY"],
            },
            {
                "shot_id": "001_shot_b",
                "scene_id": "001",
                "shot_type": "wide",
                "lens_specs": "24mm",
                "camera_angle": "eye_level",
                "location": "RAVENCROFT MANOR - FOYER",
                "characters": ["EVELYN RAVENCROFT", "ARTHUR GRAY"],
            },
            {
                "shot_id": "001_shot_c",
                "scene_id": "001",
                "shot_type": "medium",
                "lens_specs": "50mm",
                "camera_angle": "eye_level",
                "location": "RAVENCROFT MANOR - FOYER",
                "characters": ["EVELYN RAVENCROFT"],
            },
        ]
        
        # Test compute_key
        key_a = cache.compute_key(shots[0])
        key_b = cache.compute_key(shots[1])
        key_c = cache.compute_key(shots[2])
        
        assert key_a == key_b, "Keys for identical compositions should match"
        assert key_a != key_c, "Keys for different compositions should differ"
        print("  ✓ compute_key() works correctly")
        
        # Test register
        cache.register(shots[0], "/tmp/001_shot_a.jpg", "/api/media?path=/001_shot_a.jpg")
        print("  ✓ register() works")
        
        # Test lookup
        entry = cache.lookup(shots[1])
        assert entry is not None
        assert entry.shot_id == "001_shot_a"
        print("  ✓ lookup() finds matching composition")
        
        entry_none = cache.lookup(shots[2])
        assert entry_none is None
        print("  ✓ lookup() returns None for non-matching composition")
        
        # Test get_reuse_plan
        plan = cache.get_reuse_plan(shots)
        assert plan["001_shot_a"] is None, "Anchor should be None"
        assert plan["001_shot_b"] == "001_shot_a", "Reuser should reference anchor"
        assert plan["001_shot_c"] is None, "Different composition should be None"
        print("  ✓ get_reuse_plan() groups compositions correctly")
        
        # Test apply_reuse_to_shot_plan
        modified = cache.apply_reuse_to_shot_plan(shots, cache_only=False)
        assert "_reuse_frame_from" in modified[1], "Reuser should have metadata"
        assert "_reuse_frame_from" not in modified[0], "Anchor should not have metadata"
        print("  ✓ apply_reuse_to_shot_plan() marks reusers")
        
        # Test should_reuse and get_reuse_source
        assert not should_reuse(modified[0]), "Anchor should not be marked for reuse"
        assert should_reuse(modified[1]), "Reuser should be marked for reuse"
        assert get_reuse_source(modified[1]) == "001_shot_a"
        print("  ✓ should_reuse() and get_reuse_source() work")
        
        # Test stats
        stats = cache.stats()
        assert stats["unique_compositions"] == 2
        assert stats["reusable_shots"] == 1
        assert stats["total_shots"] == 3
        print("  ✓ stats() computes correctly")
        
        # Test save/load
        os.makedirs(os.path.join(tmpdir, "test_project"), exist_ok=True)
        path = cache.save()
        assert os.path.exists(path)
        print("  ✓ save() writes to disk")
        
        # Create new cache and load
        cache2 = CompositionCache(project="test_project", pipeline_outputs_dir=tmpdir)
        cache2.load(path)
        assert len(cache2._cache) == len(cache._cache)
        print("  ✓ load() restores from disk")


def test_analyze_reuse_opportunities():
    """Test analyze_reuse_opportunities helper."""
    print("\n[TEST] analyze_reuse_opportunities()")
    
    shots = [
        {
            "shot_id": "001_a",
            "scene_id": "001",
            "shot_type": "wide",
            "lens_specs": "24mm",
            "camera_angle": "eye_level",
            "location": "FOYER",
            "characters": ["EVELYN"],
        },
        {
            "shot_id": "001_b",
            "scene_id": "001",
            "shot_type": "wide",
            "lens_specs": "24mm",
            "camera_angle": "eye_level",
            "location": "FOYER",
            "characters": ["EVELYN"],
        },
        {
            "shot_id": "002_a",
            "scene_id": "002",
            "shot_type": "medium",
            "lens_specs": "50mm",
            "camera_angle": "eye_level",
            "location": "LIBRARY",
            "characters": ["ARTHUR"],
        },
    ]
    
    report = analyze_reuse_opportunities(shots)
    
    assert report["total_shots"] == 3
    assert report["unique_compositions"] == 2
    assert report["total_reusable_shots"] == 1
    assert report["savings_pct"] == 33.3
    print("  ✓ analyze_reuse_opportunities() counts correctly")
    print(f"  Estimated savings: {report['estimated_savings']}")


def test_lens_classification():
    """Test lens classification."""
    print("\n[TEST] classify_lens()")
    
    assert CompositionCache.classify_lens(24) == "wide"
    assert CompositionCache.classify_lens(35) == "wide"
    assert CompositionCache.classify_lens(36) == "normal"
    assert CompositionCache.classify_lens(50) == "normal"
    assert CompositionCache.classify_lens(65) == "normal"
    assert CompositionCache.classify_lens(66) == "tele"
    assert CompositionCache.classify_lens(85) == "tele"
    assert CompositionCache.classify_lens(None) == "normal"
    print("  ✓ Lens classification works for all ranges")


def test_camera_angle_extraction():
    """Test camera angle extraction."""
    print("\n[TEST] extract_camera_angle()")
    
    shot1 = {"camera_angle": "high"}
    assert CompositionCache.extract_camera_angle(shot1) == "high"
    
    shot2 = {"shot_type": "pov"}
    assert CompositionCache.extract_camera_angle(shot2) == "high"
    
    shot3 = {"shot_type": "low angle"}
    assert CompositionCache.extract_camera_angle(shot3) == "low"
    
    shot4 = {}
    assert CompositionCache.extract_camera_angle(shot4) == "eye_level"
    
    print("  ✓ Camera angle extraction works")


def test_character_extraction():
    """Test character extraction."""
    print("\n[TEST] extract_characters()")
    
    shot = {
        "characters": ["EVELYN RAVENCROFT", "ARTHUR GRAY"],
    }
    chars = CompositionCache.extract_characters(shot)
    assert "EVELYN RAVENCROFT" in chars
    assert "ARTHUR GRAY" in chars
    assert len(chars) == 2
    print("  ✓ Character extraction from array works")
    
    shot2 = {
        "dialogue_text": "EVELYN RAVENCROFT\nI received the letter.\n\nARTHUR GRAY\nYes, it was specific.",
    }
    chars2 = CompositionCache.extract_characters(shot2)
    assert "EVELYN RAVENCROFT" in chars2
    assert "ARTHUR GRAY" in chars2
    print("  ✓ Character extraction from dialogue works")


def main():
    """Run all tests."""
    print("=" * 70)
    print("COMPOSITION CACHE — V21.10 Test Suite")
    print("=" * 70)
    
    try:
        test_composition_key()
        test_cache_entry()
        test_composition_cache()
        test_analyze_reuse_opportunities()
        test_lens_classification()
        test_camera_angle_extraction()
        test_character_extraction()
        
        print("\n" + "=" * 70)
        print("✓ ALL TESTS PASSED")
        print("=" * 70)
        return 0
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n✗ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
