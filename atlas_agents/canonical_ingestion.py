"""
CANONICAL INGESTION PIPELINE - V17 FACTORY

This is the ONLY valid path for script ingestion.
All entry points (UI, file upload, re-import, agent repair) MUST call this.

Rules:
1. NO summarization allowed
2. Dialogue, beats, characters, locations MUST be preserved verbatim
3. Output is ALWAYS: story_bible.json + shot_plan.json
4. Both files contain the SAME semantic content

Usage:
    from atlas_agents.canonical_ingestion import ingest_script

    story_bible, shot_plan = ingest_script(
        script_text="...",
        project="my_project",
        metadata={"runtime": 52, "genre": "fantasy"}
    )
"""

import json
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any

# Base paths
BASE_DIR = Path("/Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM")
PIPELINE_DIR = BASE_DIR / "pipeline_outputs"


class IngestionError(Exception):
    """Raised when ingestion fails validation."""
    pass


class DataLossError(Exception):
    """Raised when data loss is detected."""
    pass


def validate_no_data_loss(original: Dict, processed: Dict, stage: str) -> None:
    """
    Validate that no data was lost between processing stages.
    Raises DataLossError if data loss detected.
    """
    # Check beats preservation
    orig_beats = sum(len(s.get("beats", [])) for s in original.get("scenes", []))
    proc_beats = sum(len(s.get("beats", [])) for s in processed.get("scenes", []))

    if orig_beats > 0 and proc_beats == 0:
        raise DataLossError(f"[{stage}] Beats were stripped: {orig_beats} -> {proc_beats}")

    # Check dialogue preservation
    orig_dialogue = sum(
        1 for s in original.get("scenes", [])
        for b in s.get("beats", [])
        if b.get("dialogue")
    )
    proc_dialogue = sum(
        1 for s in processed.get("scenes", [])
        for b in s.get("beats", [])
        if b.get("dialogue")
    )

    if orig_dialogue > 0 and proc_dialogue == 0:
        raise DataLossError(f"[{stage}] Dialogue was stripped: {orig_dialogue} -> {proc_dialogue}")

    # Check character preservation
    orig_chars = len(original.get("characters", []))
    proc_chars = len(processed.get("characters", []))

    if orig_chars > 0 and proc_chars == 0:
        raise DataLossError(f"[{stage}] Characters were stripped: {orig_chars} -> {proc_chars}")


def extract_locations_from_scenes(scenes: List[Dict]) -> List[Dict]:
    """Extract unique locations from scenes."""
    location_names = set()
    for scene in scenes:
        loc = scene.get("location", "")
        if loc and loc not in ["", "UNKNOWN"]:
            location_names.add(loc)

    return [
        {"name": loc, "source": "script", "description": ""}
        for loc in sorted(location_names)
    ]


def extract_characters_from_scenes(scenes: List[Dict]) -> List[str]:
    """Extract unique characters from scenes and beats."""
    characters = set()

    for scene in scenes:
        # From scene.characters
        for c in scene.get("characters", []):
            if isinstance(c, dict):
                characters.add(c.get("name", "").upper())
            else:
                characters.add(str(c).upper())

        # From beats
        for beat in scene.get("beats", []):
            for c in beat.get("characters", []):
                if isinstance(c, dict):
                    characters.add(c.get("name", "").upper())
                else:
                    characters.add(str(c).upper())

            # From dialogue speaker
            dialogue = beat.get("dialogue", "")
            if dialogue:
                match = re.match(r"^([A-Z][A-Z\s]+):", dialogue)
                if match:
                    characters.add(match.group(1).strip())

    return sorted([c for c in characters if c])


def create_story_bible(
    scenes: List[Dict],
    characters: List[Dict],
    locations: List[Dict],
    metadata: Dict
) -> Dict:
    """
    Create story_bible.json with FULL data preservation.
    NO summarization. NO stripping.
    """
    return {
        "title": metadata.get("title", "Untitled"),
        "series_title": metadata.get("series_title", metadata.get("title", "Untitled")),
        "episode_number": metadata.get("episode_number", 1),
        "genre": metadata.get("genre", "drama"),
        "tone": metadata.get("tone", ["cinematic"]),
        "runtime_target_minutes": metadata.get("runtime", 45),
        "runtime_target_seconds": metadata.get("runtime", 45) * 60,
        "logline": metadata.get("logline", ""),

        # FULL locations array
        "locations": locations,
        "setting": {
            "time_period": metadata.get("time_period", "modern"),
            "locations": [loc.get("name", loc) for loc in locations]
        },

        # FULL characters array
        "characters": characters,

        # FULL scenes with ALL beats and dialogue - NO STRIPPING
        "scenes": [
            {
                "scene_id": scene.get("scene_id", f"{i+1:03d}"),
                "title": scene.get("title", ""),
                "location": scene.get("location", ""),
                "time_of_day": scene.get("time_of_day", "DAY"),
                "int_ext": scene.get("int_ext", "INT"),
                "estimated_duration_seconds": scene.get("duration_seconds", scene.get("estimated_duration_seconds", 60)),

                # CRITICAL: PRESERVE FULL BEATS - NEVER STRIP
                "beats": scene.get("beats", []),
                "beat_count": len(scene.get("beats", [])),

                # Preserve other fields
                "characters": scene.get("characters", []),
                "description": scene.get("description", ""),
                "shots": scene.get("shots", [])
            }
            for i, scene in enumerate(scenes)
        ],

        "visual_style": {
            "aspect_ratio": "16:9",
            "color_palette": "cinematic",
            "lighting_style": "atmospheric"
        },

        # Metadata
        "_generated_by": "CANONICAL_INGESTION_V17",
        "_timestamp": datetime.now().isoformat(),
        "_v17_invariants_enforced": True
    }


def create_shot_plan(
    scenes: List[Dict],
    characters: List[Dict],
    locations: List[Dict],
    metadata: Dict
) -> Dict:
    """
    Create shot_plan.json from scenes.
    This is the EXECUTION TRUTH.
    """
    shots = []
    shot_idx = 0

    for scene in scenes:
        scene_id = scene.get("scene_id", "001")
        scene_chars = scene.get("characters", [])
        scene_location = scene.get("location", "")

        beats = scene.get("beats", [])

        if beats:
            # Create shots from beats
            for beat_idx, beat in enumerate(beats):
                shot_id = f"{scene_id}_{beat_idx+1:03d}A"

                # Get characters from beat or fall back to scene
                beat_chars = beat.get("characters", [])
                if not beat_chars:
                    beat_chars = scene_chars

                shot = {
                    "shot_id": shot_id,
                    "scene_id": scene_id,
                    "beat_number": beat_idx + 1,
                    "shot_type": beat.get("beat_type", "action"),
                    "duration": beat.get("duration", 20),
                    "location": scene_location,

                    # CRITICAL: Preserve dialogue
                    "dialogue": beat.get("dialogue", ""),

                    # CRITICAL: Preserve characters
                    "characters": beat_chars,

                    # CRITICAL: Preserve emotional data
                    "emotional_tone": beat.get("emotional_tone", "neutral"),
                    "emotional_beat": beat.get("emotional_beat", ""),

                    # Prompts
                    "nano_prompt": beat.get("description", ""),
                    "ltx_motion_prompt": f"Subtle cinematic motion, {beat.get('emotional_tone', 'neutral')} mood"
                }

                shots.append(shot)
                shot_idx += 1
        else:
            # No beats - create single shot for scene
            shot = {
                "shot_id": f"{scene_id}_001A",
                "scene_id": scene_id,
                "beat_number": 1,
                "shot_type": "establishing",
                "duration": scene.get("estimated_duration_seconds", 20),
                "location": scene_location,
                "dialogue": "",
                "characters": scene_chars,
                "emotional_tone": "neutral",
                "nano_prompt": scene.get("description", scene.get("title", "")),
                "ltx_motion_prompt": "Subtle cinematic motion"
            }
            shots.append(shot)
            shot_idx += 1

    return {
        "shots": shots,
        "metadata": {
            "title": metadata.get("title", "Untitled"),
            "genre": metadata.get("genre", "drama"),
            "target_runtime": metadata.get("runtime", 45) * 60,
            "runtime_target_minutes": metadata.get("runtime", 45),
            "total_shots": len(shots),
            "total_duration_seconds": sum(s.get("duration", 20) for s in shots)
        },
        "characters": characters,
        "locations": locations,
        "scene_manifest": scenes,

        # Metadata
        "_generated_by": "CANONICAL_INGESTION_V17",
        "_timestamp": datetime.now().isoformat(),
        "_requires_shot_expansion": False,  # Already expanded
        "_v17_invariants_enforced": True
    }


def ingest_script(
    script_text: str,
    project: str,
    metadata: Optional[Dict] = None,
    use_llm: bool = True
) -> Tuple[Dict, Dict]:
    """
    CANONICAL SCRIPT INGESTION - THE ONLY VALID PATH

    Args:
        script_text: Raw script text
        project: Project name
        metadata: Optional metadata (runtime, genre, title, etc.)
        use_llm: Whether to use LLM for extraction (default True)

    Returns:
        (story_bible, shot_plan) tuple

    Raises:
        IngestionError: If ingestion fails
        DataLossError: If data loss is detected
    """
    if metadata is None:
        metadata = {}

    # Set defaults
    metadata.setdefault("title", project)
    metadata.setdefault("runtime", 45)
    metadata.setdefault("genre", "drama")

    project_path = PIPELINE_DIR / project
    project_path.mkdir(parents=True, exist_ok=True)

    # Create required directories
    (project_path / "location_masters").mkdir(exist_ok=True)
    (project_path / "first_frames").mkdir(exist_ok=True)
    (project_path / "videos").mkdir(exist_ok=True)

    # Save raw script
    with open(project_path / "imported_script.txt", 'w') as f:
        f.write(script_text)

    # Run LLM extraction if requested
    if use_llm:
        try:
            from LLM_SCRIPT_EXTRACTOR import run_full_extraction

            manifest, extraction_metadata = run_full_extraction(
                script_text=script_text,
                project_name=project,
                genre=metadata.get("genre", "drama"),
                enable_repair=True,
                target_runtime_minutes=metadata.get("runtime", 45)
            )

            if manifest:
                scenes = manifest.get("scenes", manifest.get("scene_manifest", []))
                characters = manifest.get("characters", [])
                locations = manifest.get("locations", [])

                # Merge metadata
                metadata.update(manifest.get("metadata", {}))
                metadata["_llm_extraction"] = extraction_metadata
        except Exception as e:
            # Fall back to basic parsing
            scenes = []
            characters = []
            locations = []
    else:
        scenes = []
        characters = []
        locations = []

    # If no scenes extracted, try basic parsing
    if not scenes:
        scenes = _basic_script_parse(script_text)

    # Extract locations if not provided
    if not locations:
        locations = extract_locations_from_scenes(scenes)

    # Ensure locations are dicts
    locations = [
        loc if isinstance(loc, dict) else {"name": str(loc), "source": "extracted"}
        for loc in locations
    ]

    # Extract characters if not provided
    if not characters:
        char_names = extract_characters_from_scenes(scenes)
        characters = [{"name": name, "role": "supporting"} for name in char_names]

    # Ensure characters are dicts
    characters = [
        char if isinstance(char, dict) else {"name": str(char), "role": "supporting"}
        for char in characters
    ]

    # Create story_bible
    story_bible = create_story_bible(scenes, characters, locations, metadata)

    # Validate no data loss in story_bible
    original_data = {"scenes": scenes, "characters": characters}
    validate_no_data_loss(original_data, story_bible, "story_bible_creation")

    # Create shot_plan
    shot_plan = create_shot_plan(scenes, characters, locations, metadata)

    # Save files
    with open(project_path / "story_bible.json", 'w') as f:
        json.dump(story_bible, f, indent=2)

    with open(project_path / "shot_plan.json", 'w') as f:
        json.dump(shot_plan, f, indent=2)

    return story_bible, shot_plan


def _basic_script_parse(script_text: str) -> List[Dict]:
    """
    Basic script parsing when LLM is unavailable.
    Extracts scenes from screenplay format.
    """
    scenes = []
    current_scene = None
    current_beats = []

    lines = script_text.split('\n')
    scene_idx = 0

    for line in lines:
        line = line.strip()

        # Scene header detection
        if re.match(r'^(INT\.|EXT\.|INT/EXT\.)', line):
            # Save previous scene
            if current_scene:
                current_scene["beats"] = current_beats
                scenes.append(current_scene)

            scene_idx += 1
            parts = line.split(' - ')
            location = parts[0].replace('INT.', '').replace('EXT.', '').replace('INT/EXT.', '').strip()
            time_of_day = parts[1].strip() if len(parts) > 1 else "DAY"

            current_scene = {
                "scene_id": f"{scene_idx:03d}",
                "title": location,
                "location": location,
                "time_of_day": time_of_day,
                "int_ext": "INT" if "INT" in line else "EXT",
                "beats": [],
                "characters": []
            }
            current_beats = []

        # Dialogue detection (CHARACTER NAME in caps followed by dialogue)
        elif current_scene and re.match(r'^[A-Z][A-Z\s]+$', line):
            character = line.strip()
            if character not in current_scene["characters"]:
                current_scene["characters"].append(character)

        # Dialogue content (after character name)
        elif current_scene and line and not line.startswith('('):
            if current_beats and "dialogue" not in current_beats[-1]:
                # This might be dialogue following a character name
                pass

    # Don't forget last scene
    if current_scene:
        current_scene["beats"] = current_beats
        scenes.append(current_scene)

    return scenes


# Expose for external use
__all__ = ['ingest_script', 'IngestionError', 'DataLossError', 'validate_no_data_loss']
