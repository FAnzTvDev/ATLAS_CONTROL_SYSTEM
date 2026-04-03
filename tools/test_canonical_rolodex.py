#!/usr/bin/env python3
"""
Unit tests for canonical_rolodex.py

Test coverage:
  - CharacterRefPack + LocationRefPack dataclass operations
  - CanonicalRolodex loading + fallback chains
  - DPFramingProfile strategy lookup
  - select_best_refs() main engine
  - Emotion detection + B-roll context determination
  - Validation + audit functions
  - Non-blocking error handling

Run:
  python3 tools/test_canonical_rolodex.py
  pytest tools/test_canonical_rolodex.py -v
"""

import json
import tempfile
import pytest
from pathlib import Path
from typing import Dict, Any

from tools.canonical_rolodex import (
    CharacterRefPack,
    LocationRefPack,
    CanonicalRolodex,
    DPFramingProfile,
    RefSelectionResult,
    ShotType,
    SceneType,
    RefType,
    LocationRefType,
    BRollContext,
    select_best_refs,
    _detect_emotion_from_shot,
    _determine_broll_context,
    _build_selection_reason,
    validate_rolodex_completeness,
    create_empty_character_pack_structure,
    create_empty_location_pack_structure,
)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def temp_project_dir():
    """Create temporary project directory with sample pack structures."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_path = Path(tmpdir) / "test_project"
        project_path.mkdir()

        # Create character packs directory
        char_packs = project_path / "character_packs"
        char_packs.mkdir()

        # Create ELEANOR_VOSS pack
        eleanor_dir = char_packs / "ELEANOR_VOSS"
        eleanor_dir.mkdir()
        (eleanor_dir / "headshot_front.jpg").touch()
        (eleanor_dir / "headshot_34.jpg").touch()
        (eleanor_dir / "profile.jpg").touch()
        (eleanor_dir / "full_body.jpg").touch()
        (eleanor_dir / "expression_neutral.jpg").touch()
        (eleanor_dir / "expression_vulnerable.jpg").touch()

        # Create location packs directory
        loc_packs = project_path / "location_packs"
        loc_packs.mkdir()

        # Create DRAWING_ROOM pack
        room_dir = loc_packs / "DRAWING_ROOM"
        room_dir.mkdir()
        (room_dir / "master_wide.jpg").touch()
        (room_dir / "reverse_wide.jpg").touch()
        (room_dir / "detail_a.jpg").touch()
        (room_dir / "detail_b.jpg").touch()

        yield str(project_path)


@pytest.fixture
def sample_cast_map():
    """Sample cast mapping."""
    return {
        "ELEANOR_VOSS": {
            "actor_id": "ai_001",
            "appearance": "dark hair, pale complexion",
        },
        "THOMAS_BLACKWOOD": {
            "actor_id": "ai_002",
            "appearance": "auburn hair, stern features",
        }
    }


@pytest.fixture
def sample_story_bible():
    """Sample story bible."""
    return {
        "scenes": [
            {
                "scene_id": "001",
                "location": "DRAWING_ROOM",
                "beats": [
                    {
                        "beat_id": "001_beat_01",
                        "summary": "Eleanor enters the drawing room for the first time."
                    }
                ]
            }
        ]
    }


# ============================================================================
# TESTS: CharacterRefPack
# ============================================================================

class TestCharacterRefPack:
    def test_creation_empty(self):
        """Test creating empty pack."""
        pack = CharacterRefPack(character_name="TEST")
        assert pack.character_name == "TEST"
        assert not pack.has_required()

    def test_creation_with_headshot_front(self):
        """Test creating pack with required image."""
        pack = CharacterRefPack(
            character_name="ELEANOR",
            headshot_front="/path/to/headshot.jpg"
        )
        assert pack.has_required()

    def test_get_ref_by_type(self):
        """Test getting ref by enum type."""
        pack = CharacterRefPack(
            character_name="ELEANOR",
            headshot_front="/path/front.jpg",
            headshot_34="/path/34.jpg"
        )

        assert pack.get_ref_by_type(RefType.HEADSHOT_FRONT) == "/path/front.jpg"
        assert pack.get_ref_by_type(RefType.HEADSHOT_34) == "/path/34.jpg"
        assert pack.get_ref_by_type(RefType.PROFILE) is None

    def test_to_dict(self):
        """Test serialization."""
        pack = CharacterRefPack(
            character_name="ELEANOR",
            headshot_front="/path/front.jpg"
        )
        d = pack.to_dict()
        assert isinstance(d, dict)
        assert d["character_name"] == "ELEANOR"
        assert d["headshot_front"] == "/path/front.jpg"


# ============================================================================
# TESTS: LocationRefPack
# ============================================================================

class TestLocationRefPack:
    def test_creation_with_master_wide(self):
        """Test creating pack with required image."""
        pack = LocationRefPack(
            location_id="DRAWING_ROOM",
            master_wide="/path/master.jpg"
        )
        assert pack.has_required()

    def test_get_ref_by_type(self):
        """Test getting location ref by enum type."""
        pack = LocationRefPack(
            location_id="LIBRARY",
            master_wide="/path/master.jpg",
            detail_a="/path/detail_a.jpg"
        )

        assert pack.get_ref_by_type(LocationRefType.MASTER_WIDE) == "/path/master.jpg"
        assert pack.get_ref_by_type(LocationRefType.DETAIL_A) == "/path/detail_a.jpg"
        assert pack.get_ref_by_type(LocationRefType.REVERSE_WIDE) is None


# ============================================================================
# TESTS: DPFramingProfile
# ============================================================================

class TestDPFramingProfile:
    def test_dialogue_ots_speaker(self):
        """Test OTS speaker framing strategy."""
        profile = DPFramingProfile()
        strategy = profile.get_strategy(ShotType.OTS_SPEAKER, SceneType.DIALOGUE)

        assert strategy is not None
        assert strategy.primary_character_ref == RefType.HEADSHOT_34
        assert strategy.location_ref == LocationRefType.MASTER_WIDE

    def test_dialogue_cu_clean_single(self):
        """Test clean single close-up framing."""
        profile = DPFramingProfile()
        strategy = profile.get_strategy(ShotType.CU, SceneType.DIALOGUE)

        assert strategy.primary_character_ref == RefType.HEADSHOT_FRONT
        assert strategy.location_ref == LocationRefType.DETAIL_A

    def test_action_wide(self):
        """Test action wide shot framing."""
        profile = DPFramingProfile()
        strategy = profile.get_strategy(ShotType.WS, SceneType.ACTION)

        assert strategy.primary_character_ref == RefType.FULL_BODY
        assert strategy.location_ref == LocationRefType.MASTER_WIDE

    def test_intimate_cu_expression_override(self):
        """Test intimate scene expression override."""
        profile = DPFramingProfile()
        strategy = profile.get_strategy(ShotType.CU, SceneType.INTIMATE)

        assert strategy.include_expression_override == "vulnerable"

    def test_fallback_default(self):
        """Test fallback to default strategy."""
        profile = DPFramingProfile()

        # Unknown combination should get default
        strategy = profile.get_strategy_or_default(ShotType.ECU, SceneType.ACTION)
        assert strategy is not None
        assert "FALLBACK" in strategy.reason


# ============================================================================
# TESTS: CanonicalRolodex
# ============================================================================

class TestCanonicalRolodex:
    def test_initialization(self, temp_project_dir):
        """Test rolodex initialization."""
        rolodex = CanonicalRolodex(temp_project_dir)
        assert rolodex.project_path == Path(temp_project_dir)
        assert isinstance(rolodex.dp_framing, DPFramingProfile)

    def test_load_character_pack(self, temp_project_dir):
        """Test loading character pack from disk."""
        rolodex = CanonicalRolodex(temp_project_dir)
        pack = rolodex.load_character_pack("ELEANOR_VOSS")

        assert pack is not None
        assert pack.character_name == "ELEANOR_VOSS"
        assert pack.has_required()
        assert pack.headshot_front is not None

    def test_load_missing_character_pack(self, temp_project_dir):
        """Test loading missing pack (non-blocking)."""
        rolodex = CanonicalRolodex(temp_project_dir)
        pack = rolodex.load_character_pack("NONEXISTENT")

        assert pack is None

    def test_load_location_pack(self, temp_project_dir):
        """Test loading location pack from disk."""
        rolodex = CanonicalRolodex(temp_project_dir)
        pack = rolodex.load_location_pack("DRAWING_ROOM")

        assert pack is not None
        assert pack.location_id == "DRAWING_ROOM"
        assert pack.has_required()

    def test_caching(self, temp_project_dir):
        """Test pack caching."""
        rolodex = CanonicalRolodex(temp_project_dir)

        # First load
        pack1 = rolodex.get_character_pack("ELEANOR_VOSS")
        # Second load (should return cached)
        pack2 = rolodex.get_character_pack("ELEANOR_VOSS")

        assert pack1 is pack2  # Same object


# ============================================================================
# TESTS: select_best_refs() Main Engine
# ============================================================================

class TestSelectBestRefs:
    def test_dialogue_ots_speaker(self, temp_project_dir, sample_cast_map, sample_story_bible):
        """Test ref selection for OTS dialogue speaker."""
        rolodex = CanonicalRolodex(temp_project_dir)

        shot = {
            "shot_id": "001_A",
            "shot_type": "over_the_shoulder_speaker",
            "scene_type": "dialogue",
            "characters": ["ELEANOR_VOSS"],
            "location": "DRAWING_ROOM",
            "dialogue_text": "I don't understand.",
        }

        result = select_best_refs(shot, sample_cast_map, sample_story_bible, rolodex)

        assert result.shot_id == "001_A"
        assert len(result.selected_character_refs) > 0
        assert len(result.selected_location_refs) > 0
        assert result.confidence > 0.9
        assert "headshot_34" in result.selection_reason

    def test_close_up_dialogue(self, temp_project_dir, sample_cast_map, sample_story_bible):
        """Test ref selection for close-up dialogue."""
        rolodex = CanonicalRolodex(temp_project_dir)

        shot = {
            "shot_id": "001_B",
            "shot_type": "close_up",
            "scene_type": "dialogue",
            "characters": ["ELEANOR_VOSS"],
            "location": "DRAWING_ROOM",
        }

        result = select_best_refs(shot, sample_cast_map, sample_story_bible, rolodex)

        assert "headshot_front" in result.selection_reason
        assert result.confidence >= 0.9

    def test_emotion_detection_grief(self, temp_project_dir, sample_cast_map, sample_story_bible):
        """Test emotion detection and vulnerable expression selection."""
        rolodex = CanonicalRolodex(temp_project_dir)

        shot = {
            "shot_id": "006_A",
            "shot_type": "close_up",
            "scene_type": "intimate",
            "characters": ["ELEANOR_VOSS"],
            "location": "DRAWING_ROOM",
            "beat_summary": "Eleanor realizes the truth. Her world collapses in grief.",
        }

        result = select_best_refs(shot, sample_cast_map, sample_story_bible, rolodex)

        # Intimate scene should trigger expression override
        assert result.emotion_override == "vulnerable"

    def test_broll_no_character_refs(self, temp_project_dir, sample_cast_map, sample_story_bible):
        """Test B-roll generation (no character refs)."""
        rolodex = CanonicalRolodex(temp_project_dir)

        shot = {
            "shot_id": "005_B",
            "shot_type": "wide_shot",
            "scene_type": "montage",
            "characters": [],  # B-roll
            "location": "DRAWING_ROOM",
            "is_broll": True,
            "shot_index_in_scene": 0,
            "scene_shot_count": 8,
        }

        result = select_best_refs(shot, sample_cast_map, sample_story_bible, rolodex)

        assert len(result.selected_character_refs) == 0  # No char refs
        assert len(result.selected_location_refs) > 0  # Location still used
        assert result.broll_context == BRollContext.SCENE_OPENING

    def test_missing_location_pack(self, temp_project_dir, sample_cast_map, sample_story_bible):
        """Test selection with missing location pack (non-blocking)."""
        rolodex = CanonicalRolodex(temp_project_dir)

        shot = {
            "shot_id": "002_A",
            "shot_type": "close_up",
            "scene_type": "dialogue",
            "characters": ["ELEANOR_VOSS"],
            "location": "NONEXISTENT_LOCATION",  # Missing
        }

        result = select_best_refs(shot, sample_cast_map, sample_story_bible, rolodex)

        # Should proceed but with reduced confidence
        assert result.confidence < 0.8
        assert len(result.selected_location_refs) == 0
        # Generation still proceeds

    def test_confidence_calculation(self, temp_project_dir, sample_cast_map, sample_story_bible):
        """Test confidence scoring."""
        rolodex = CanonicalRolodex(temp_project_dir)

        # Full pack available
        shot = {
            "shot_id": "001_A",
            "shot_type": "close_up",
            "scene_type": "dialogue",
            "characters": ["ELEANOR_VOSS"],
            "location": "DRAWING_ROOM",
        }

        result = select_best_refs(shot, sample_cast_map, sample_story_bible, rolodex)
        assert result.confidence == 1.0
        assert not result.fallback_used


# ============================================================================
# TESTS: Emotion Detection
# ============================================================================

class TestEmotionDetection:
    def test_emotion_from_explicit_field(self):
        """Test explicit emotion field."""
        shot = {
            "shot_id": "001",
            "emotion": "grief",
        }
        emotion = _detect_emotion_from_shot(shot)
        assert emotion == "grief"

    def test_emotion_from_beat_summary(self):
        """Test emotion detection from beat summary."""
        shot = {
            "shot_id": "001",
            "beat_summary": "Eleanor confronts Thomas about his betrayal.",
        }
        emotion = _detect_emotion_from_shot(shot)
        assert emotion in ["anger", "confrontation"]

    def test_emotion_default_neutral(self):
        """Test default to neutral."""
        shot = {
            "shot_id": "001",
            "beat_summary": "A scene with no emotional keywords.",
        }
        emotion = _detect_emotion_from_shot(shot)
        assert emotion == "neutral"


# ============================================================================
# TESTS: B-roll Context
# ============================================================================

class TestBrollContext:
    def test_opening_context(self):
        """Test B-roll at start of scene."""
        shot = {
            "shot_id": "001_B",
            "is_broll": True,
            "shot_index_in_scene": 0,
            "scene_shot_count": 8,
        }
        context = _determine_broll_context(shot, {})
        assert context == BRollContext.SCENE_OPENING

    def test_closing_context(self):
        """Test B-roll at end of scene."""
        shot = {
            "shot_id": "008_B",
            "is_broll": True,
            "shot_index_in_scene": 7,
            "scene_shot_count": 8,
        }
        context = _determine_broll_context(shot, {})
        assert context == BRollContext.SCENE_CLOSING

    def test_context_with_keywords(self):
        """Test B-roll with narrative keywords."""
        shot = {
            "shot_id": "004_B",
            "is_broll": True,
            "shot_index_in_scene": 3,
            "scene_shot_count": 8,
            "beat_summary": "Margaret packing her belongings for departure.",
        }
        context = _determine_broll_context(shot, {})
        assert context == BRollContext.CONTEXT


# ============================================================================
# TESTS: Validation & Audit
# ============================================================================

class TestValidation:
    def test_audit_complete(self, temp_project_dir):
        """Test audit on complete rolodex."""
        audit = validate_rolodex_completeness(
            temp_project_dir,
            required_characters=["ELEANOR_VOSS"],
            required_locations=["DRAWING_ROOM"]
        )

        assert audit["complete"]
        assert len(audit["missing_required"]) == 0

    def test_audit_missing_character_pack(self, temp_project_dir):
        """Test audit detects missing character pack."""
        audit = validate_rolodex_completeness(
            temp_project_dir,
            required_characters=["ELEANOR_VOSS", "NONEXISTENT"],
            required_locations=["DRAWING_ROOM"]
        )

        assert not audit["complete"]
        assert any("NONEXISTENT" in item for item in audit["missing_required"])

    def test_audit_missing_required_image(self, temp_project_dir):
        """Test audit detects missing required image."""
        # Delete headshot_front
        headshot = Path(temp_project_dir) / "character_packs" / "ELEANOR_VOSS" / "headshot_front.jpg"
        headshot.unlink()

        audit = validate_rolodex_completeness(
            temp_project_dir,
            required_characters=["ELEANOR_VOSS"],
            required_locations=["DRAWING_ROOM"]
        )

        assert not audit["complete"]
        assert any("headshot_front" in item for item in audit["missing_required"])


# ============================================================================
# TESTS: Pack Creation
# ============================================================================

class TestPackCreation:
    def test_create_character_pack_structure(self):
        """Test creating empty character pack structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pack_dir = create_empty_character_pack_structure(tmpdir, "TEST_CHAR")

            assert pack_dir.exists()
            assert (pack_dir / "pack_manifest.json").exists()

            # Check manifest
            with open(pack_dir / "pack_manifest.json") as f:
                manifest = json.load(f)

            assert manifest["character_name"] == "TEST_CHAR"
            assert "headshot_front" in manifest["images"]
            assert manifest["images"]["headshot_front"]["required"]

    def test_create_location_pack_structure(self):
        """Test creating empty location pack structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pack_dir = create_empty_location_pack_structure(tmpdir, "TEST_LOC")

            assert pack_dir.exists()
            assert (pack_dir / "pack_manifest.json").exists()

            # Check manifest
            with open(pack_dir / "pack_manifest.json") as f:
                manifest = json.load(f)

            assert manifest["location_id"] == "TEST_LOC"
            assert "master_wide" in manifest["images"]
            assert manifest["images"]["master_wide"]["required"]


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestIntegration:
    def test_full_dialogue_workflow(self, temp_project_dir, sample_cast_map, sample_story_bible):
        """Test complete workflow: load rolodex, select refs for dialogue scene."""
        rolodex = CanonicalRolodex(temp_project_dir)

        # Dialogue OTS shots
        shots = [
            {
                "shot_id": "001_A",
                "shot_type": "over_the_shoulder_speaker",
                "scene_type": "dialogue",
                "characters": ["ELEANOR_VOSS"],
                "location": "DRAWING_ROOM",
            },
            {
                "shot_id": "001_B",
                "shot_type": "over_the_shoulder_listener",
                "scene_type": "dialogue",
                "characters": ["THOMAS_BLACKWOOD"],
                "location": "DRAWING_ROOM",
            }
        ]

        for shot in shots:
            result = select_best_refs(shot, sample_cast_map, sample_story_bible, rolodex)

            assert result.shot_id == shot["shot_id"]
            assert result.confidence >= 0.7  # 0.7 when pack missing, 1.0 when full pack

            # OTS_SPEAKER should use headshot_34
            if shot["shot_type"] == "over_the_shoulder_speaker":
                assert "headshot_34" in result.selection_reason or "FALLBACK" in result.selection_reason

            # OTS_LISTENER should use profile
            if shot["shot_type"] == "over_the_shoulder_listener":
                assert "profile" in result.selection_reason or "FALLBACK" in result.selection_reason or \
                       "headshot_34" in result.selection_reason  # Fallback chain

    def test_multi_character_shot(self, temp_project_dir, sample_cast_map, sample_story_bible):
        """Test ref selection for multi-character shot."""
        rolodex = CanonicalRolodex(temp_project_dir)

        shot = {
            "shot_id": "001_AB",
            "shot_type": "medium_wide_shot",
            "scene_type": "dialogue",
            "characters": ["ELEANOR_VOSS", "THOMAS_BLACKWOOD"],
            "location": "DRAWING_ROOM",
        }

        result = select_best_refs(shot, sample_cast_map, sample_story_bible, rolodex)

        # Should have refs for both characters (or fallback for missing pack)
        assert len(result.selected_character_refs) >= 1
        assert len(result.selected_location_refs) > 0


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
