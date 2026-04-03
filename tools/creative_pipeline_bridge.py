#!/usr/bin/env python3
"""
ATLAS Creative Pipeline Bridge — V1.0
Wires Creative Intelligence into Shot Expansion at INGESTION time.

This replaces generic template expansion with grammar-driven, research-backed
creative decisions. The creative rolodex classifies each scene, selects the
right grammar, and builds shots with motivated camera choices.

DESIGN PRINCIPLE:
    Creative intelligence is the FIRST pass — not a late fix.
    Script in → classify scenes → apply grammar → build shots → enrich.
    fix-v16 FINETUNES. It does not REBUILD.

INTEGRATION POINT:
    Called by orchestrator_server.py Step 3 (shot expansion)
    Replaces SHOT_EXPANSION_INTEGRATOR.expand_project_shots()

Usage:
    from tools.creative_pipeline_bridge import creative_expand_project
    success, result, msg = creative_expand_project("victorian_shadows_ep1")
"""

import json
import logging
import os
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional

logger = logging.getLogger(__name__)

# Import the creative rolodex
try:
    from tools.creative_rolodex import (
        classify_scene_type,
        get_scene_grammar,
        get_shot_recipe,
        build_shot_plan_from_grammar,
        get_emotion_camera,
        GENRE_PACING,
        SCENE_GRAMMARS,
        EMOTION_TO_CAMERA,
    )
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from tools.creative_rolodex import (
        classify_scene_type,
        get_scene_grammar,
        get_shot_recipe,
        build_shot_plan_from_grammar,
        get_emotion_camera,
        GENRE_PACING,
        SCENE_GRAMMARS,
        EMOTION_TO_CAMERA,
    )

BASE_DIR = Path(os.environ.get("ATLAS_BASE_DIR", "/Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM"))
PIPELINE_DIR = BASE_DIR / "pipeline_outputs"

# ═══════════════════════════════════════════════════════════════
# DIRECTOR AESTHETIC PROFILES
# Each profile shapes how grammars are applied — focal preferences,
# pacing modifiers, lighting tendencies.
# ═══════════════════════════════════════════════════════════════

DIRECTOR_PROFILES = {
    "fincher": {
        "name": "David Fincher",
        "style": "Precision, control, clinical dread",
        "focal_bias": "wide",  # prefers 24-35mm establishing, 50mm dialogue
        "asl_modifier": 0.85,  # cuts slightly faster than genre average
        "movement_preference": "dolly_track",  # smooth mechanical movement
        "held_shot_modifier": 0.7,  # shorter holds — keep tension tight
        "color_tendency": "desaturated_cold",
        "shadow_preference": "deep_contrast",
        "best_for": ["mystery_thriller", "noir", "horror"],
    },
    "villeneuve": {
        "name": "Denis Villeneuve",
        "style": "Scale, silence, awe",
        "focal_bias": "extreme_wide",  # 14-24mm landscapes, 85mm faces
        "asl_modifier": 1.4,  # longer holds — let images breathe
        "movement_preference": "slow_drift",
        "held_shot_modifier": 1.5,  # extended contemplative holds
        "color_tendency": "muted_earth",
        "shadow_preference": "natural_fall",
        "best_for": ["drama", "period_drama", "horror"],
    },
    "scorsese": {
        "name": "Martin Scorsese",
        "style": "Energy, character, rhythm",
        "focal_bias": "medium",  # 35-50mm — always about the person in space
        "asl_modifier": 0.9,
        "movement_preference": "handheld_subtle",
        "held_shot_modifier": 0.8,
        "color_tendency": "warm_saturated",
        "shadow_preference": "motivated_practical",
        "best_for": ["drama", "action", "noir"],
    },
    "kubrick": {
        "name": "Stanley Kubrick",
        "style": "Symmetry, distance, unease",
        "focal_bias": "wide_symmetric",  # centered compositions, wide lens
        "asl_modifier": 1.3,  # deliberate, unhurried
        "movement_preference": "steadicam_tracking",
        "held_shot_modifier": 1.4,
        "color_tendency": "controlled_palette",
        "shadow_preference": "practical_source",
        "best_for": ["horror", "drama", "period_drama"],
    },
    "coppola": {
        "name": "Francis Ford Coppola",
        "style": "Operatic, shadow, ritual",
        "focal_bias": "medium_close",  # 50-85mm — faces in shadow
        "asl_modifier": 1.1,
        "movement_preference": "slow_push",
        "held_shot_modifier": 1.2,
        "color_tendency": "amber_shadow",
        "shadow_preference": "chiaroscuro",
        "best_for": ["drama", "period_drama", "noir"],
    },
    "jenkins": {
        "name": "Barry Jenkins",
        "style": "Intimacy, color, tenderness",
        "focal_bias": "close",  # 65-100mm — always about the face
        "asl_modifier": 1.2,
        "movement_preference": "orbit_gentle",
        "held_shot_modifier": 1.3,
        "color_tendency": "warm_rich",
        "shadow_preference": "soft_wrap",
        "best_for": ["drama", "period_drama"],
    },
    "nolan": {
        "name": "Christopher Nolan",
        "style": "Scale, time, spectacle",
        "focal_bias": "imax_wide",  # extreme wide for scope, tight for tension
        "asl_modifier": 0.95,
        "movement_preference": "practical_mount",
        "held_shot_modifier": 0.9,
        "color_tendency": "natural_contrast",
        "shadow_preference": "high_key_natural",
        "best_for": ["action", "mystery_thriller", "drama"],
    },
    "atlas_default": {
        "name": "ATLAS Default",
        "style": "Balanced prestige — Succession meets Severance",
        "focal_bias": "medium",
        "asl_modifier": 1.0,
        "movement_preference": "static_to_drift",
        "held_shot_modifier": 1.0,
        "color_tendency": "scene_appropriate",
        "shadow_preference": "motivated",
        "best_for": ["mystery_thriller", "drama", "period_drama", "noir"],
    },
}


# ═══════════════════════════════════════════════════════════════
# SCENE ANALYSIS — Classify scenes from story bible data
# ═══════════════════════════════════════════════════════════════

def analyze_scene_for_classification(scene: dict, scene_index: int,
                                      total_scenes: int) -> dict:
    """Analyze a story bible scene and classify it for grammar selection.

    Returns dict with:
        scene_type: classified type
        emotion_arc: detected emotional trajectory
        has_dialogue: bool
        character_count: int
        position: opening/middle/climax/closing
    """
    beats = scene.get("beats") or []
    characters = scene.get("characters_present") or scene.get("characters") or []
    description = scene.get("description") or ""
    atmosphere = scene.get("atmosphere") or ""

    # Detect dialogue from beats
    has_dialogue = any(
        b.get("dialogue") or b.get("dialogue_text")
        for b in beats
    )

    # Determine position
    if scene_index == 0:
        position = "opening"
    elif scene_index >= total_scenes - 1:
        position = "closing"
    elif scene_index >= total_scenes * 0.7:
        position = "climax"
    else:
        position = "middle"

    # Build combined description from beats
    beat_text = " ".join(b.get("description", "") for b in beats)
    combined_desc = f"{description} {beat_text} {atmosphere}"

    scene_type = classify_scene_type(
        combined_desc, characters, has_dialogue, position
    )

    # Detect emotion level from atmosphere keywords
    emotion_level = _estimate_emotion_level(atmosphere, combined_desc)

    return {
        "scene_type": scene_type,
        "has_dialogue": has_dialogue,
        "character_count": len(characters),
        "characters": characters,
        "position": position,
        "emotion_level": emotion_level,
        "beat_count": len(beats),
    }


def _estimate_emotion_level(atmosphere: str, description: str) -> int:
    """Estimate 1-10 emotion level from text cues."""
    text = f"{atmosphere} {description}".lower()

    high_emotion = ["shock", "grief", "rage", "confession", "tears",
                    "trembling", "screaming", "sobbing", "desperate",
                    "breaking", "collapse", "confrontation", "reveal"]
    medium_emotion = ["tension", "unease", "suspicion", "concern",
                      "curious", "determined", "resolute", "searching"]
    low_emotion = ["calm", "quiet", "still", "peaceful", "morning",
                   "routine", "methodical", "clinical"]

    high_count = sum(1 for w in high_emotion if w in text)
    medium_count = sum(1 for w in medium_emotion if w in text)
    low_count = sum(1 for w in low_emotion if w in text)

    if high_count >= 2:
        return 9
    elif high_count >= 1:
        return 7
    elif medium_count >= 2:
        return 6
    elif medium_count >= 1:
        return 5
    elif low_count >= 2:
        return 3
    return 5  # neutral default


# ═══════════════════════════════════════════════════════════════
# SHOT BUILDER — Grammar → Shot Plan with IDs and metadata
# ═══════════════════════════════════════════════════════════════

def build_scene_shots(scene_id: str, scene: dict, classification: dict,
                      genre: str = "mystery_thriller",
                      director: str = "atlas_default") -> List[dict]:
    """Build a complete shot list for a scene using creative grammar.

    This is the core function — it replaces template expansion with
    motivated, grammar-driven shot selection.

    Args:
        scene_id: e.g. "001"
        scene: story bible scene dict
        classification: output from analyze_scene_for_classification
        genre: for pacing data
        director: director profile key

    Returns:
        List of shot dicts with IDs, prompts, durations, coverage roles
    """
    scene_type = classification["scene_type"]
    characters = classification["characters"]
    emotion_level = classification["emotion_level"]
    beats = scene.get("beats") or []
    location = scene.get("location") or ""
    int_ext = scene.get("int_ext") or "INT"
    time_of_day = scene.get("time_of_day") or "DAY"
    atmosphere = scene.get("atmosphere") or ""

    # Get grammar and director profile
    grammar = get_scene_grammar(scene_type, genre)
    profile = DIRECTOR_PROFILES.get(director, DIRECTOR_PROFILES["atlas_default"])
    asl_mod = profile["asl_modifier"]

    # Get shot sequence from grammar
    sequence = grammar["shot_sequence"]

    # Scale sequence to beat count if we have more beats than grammar positions
    if len(beats) > len(sequence):
        sequence = _scale_sequence_to_beats(sequence, len(beats), scene_type)

    shots = []
    coverage_roles_assigned = {"A": 0, "B": 0, "C": 0}

    for i, recipe_key in enumerate(sequence):
        recipe = get_shot_recipe(recipe_key, emotion_level)

        # Map beat proportionally
        if beats:
            beat_idx = int(i * len(beats) / len(sequence))
            beat_idx = min(beat_idx, len(beats) - 1)
            beat = beats[beat_idx]
        else:
            beat = {}

        # Determine coverage role (A/B/C)
        coverage_role = _assign_coverage_role(recipe, i, len(sequence), coverage_roles_assigned)
        coverage_roles_assigned[coverage_role[0]] += 1

        # Calculate duration with director modifier
        dur_min, dur_max = recipe["duration_range"]
        genre_asl = grammar["genre_asl"] * asl_mod
        base_duration = max(dur_min, min(dur_max, genre_asl))

        # Dialogue duration floor (Law 224)
        dialogue_text = beat.get("dialogue") or beat.get("dialogue_text") or ""
        if dialogue_text:
            word_count = len(dialogue_text.split())
            min_speak_time = (word_count / 2.3) + 1.5
            base_duration = max(base_duration, min_speak_time)

        duration = round(base_duration, 1)

        # Determine shot suffix
        shot_suffix = _get_shot_suffix(coverage_role, recipe)

        # Build shot ID: {scene_id}_{shot_number}{suffix}
        shot_number = str(i + 1).zfill(3)
        shot_id = f"{scene_id}_{shot_number}{shot_suffix}"

        # Determine characters for this shot
        shot_characters = _assign_shot_characters(
            recipe_key, characters, beat, i, len(sequence)
        )

        # Build nano_prompt from beat + grammar
        nano_prompt = _build_creative_nano_prompt(
            recipe, beat, shot_characters, location, atmosphere,
            time_of_day, emotion_level, profile
        )

        # Build ltx_motion_prompt
        ltx_motion = _build_creative_ltx_prompt(
            recipe, beat, shot_characters, duration, emotion_level
        )

        shot = {
            "shot_id": shot_id,
            "scene_id": scene_id,
            "shot_type": recipe["shot_type"],
            "duration_seconds": duration,
            "duration": duration,
            "ltx_duration_seconds": duration,
            "characters": shot_characters,
            "location": f"{int_ext}. {location} - {time_of_day}",
            "nano_prompt": nano_prompt,
            "ltx_motion_prompt": ltx_motion,
            "coverage_role": coverage_role,
            "shot_role": coverage_role.split("_")[1] if "_" in coverage_role else "ACTION",
            "dialogue_text": dialogue_text,
            "beat_description": beat.get("description", ""),
            "creative_motivation": recipe["motivation"],
            "creative_reference": recipe["reference"],
            "creative_recipe": recipe_key,
            "rhythm_position": _get_rhythm_position(grammar, i),
            "emotion_level": emotion_level,
            "focal_length": recipe["focal_length"],
            "aperture": recipe["aperture"],
            "camera_movement": recipe["movement"],
            "_creative_grammar": scene_type,
            "_director_profile": director,
            "_scene_classification": classification,
        }

        shots.append(shot)

    # Validate coverage distribution (Law 225)
    _validate_coverage_distribution(shots, scene_id)

    return shots


def _scale_sequence_to_beats(sequence: list, beat_count: int,
                              scene_type: str) -> list:
    """Scale a grammar sequence to cover more beats.

    Strategy: repeat the middle section (dialogue/action beats)
    while keeping opener and closer fixed.
    """
    if len(sequence) <= 2:
        return sequence

    opener = sequence[:2]
    closer = sequence[-1:]
    middle = sequence[2:-1]

    if not middle:
        middle = sequence[1:-1] or [sequence[1]]

    # Repeat middle to fill beat_count
    needed = beat_count - len(opener) - len(closer)
    if needed <= 0:
        return sequence

    expanded_middle = []
    for i in range(needed):
        expanded_middle.append(middle[i % len(middle)])

    return opener + expanded_middle + closer


def _assign_coverage_role(recipe: dict, position: int, total: int,
                           counts: dict) -> str:
    """Assign A/B/C coverage role based on shot type and position."""
    shot_type = recipe["shot_type"]

    # Wide/establishing → A_GEOGRAPHY
    if shot_type in ("establishing", "wide", "master"):
        return "A_GEOGRAPHY"

    # Close-up/ECU → C_EMOTION
    if shot_type in ("close_up", "extreme_close_up"):
        return "C_EMOTION"

    # Medium shots → B_ACTION
    if shot_type in ("medium", "medium_close", "over_the_shoulder", "two_shot"):
        return "B_ACTION"

    # First shot should be A if we haven't assigned one yet
    if position == 0 and counts["A"] == 0:
        return "A_GEOGRAPHY"

    # Default to B
    return "B_ACTION"


def _get_shot_suffix(coverage_role: str, recipe: dict) -> str:
    """Determine shot ID suffix from coverage role."""
    if coverage_role.startswith("A"):
        return "A"
    elif coverage_role.startswith("C"):
        return "C"
    else:
        return "B"


def _assign_shot_characters(recipe_key: str, all_characters: list,
                             beat: dict, position: int, total: int) -> list:
    """Determine which characters appear in a shot."""
    # Beat may specify characters
    beat_chars = beat.get("characters_present") or beat.get("characters") or []
    if beat_chars:
        return beat_chars

    # Dialogue and confession shots need characters
    if "dialogue" in recipe_key or "confession" in recipe_key:
        if "reaction" in recipe_key and len(all_characters) > 1:
            return [all_characters[1]]  # Listener
        elif "speaker" in recipe_key and all_characters:
            return [all_characters[0]]  # Speaker
        elif "two_shot" in recipe_key or "over_shoulder" in recipe_key:
            return all_characters[:2]  # Both
        return all_characters[:1] if all_characters else []

    # Discovery face reactions need a character
    if "face_reaction" in recipe_key and all_characters:
        return [all_characters[0]]

    # Object inserts — no characters
    if "object" in recipe_key:
        return []

    # Atmosphere / establishing — include characters if beat mentions them
    if any(k in recipe_key for k in ["atmosphere", "opener_detail",
                                      "opener_reveal", "closing", "exit"]):
        # But if beat has dialogue, we NEED characters (Law 223)
        beat_dlg = beat.get("dialogue") or beat.get("dialogue_text") or ""
        if beat_dlg and all_characters:
            return [all_characters[0]]
        return []

    # Default: include first character if available
    return all_characters[:1] if all_characters else []


def _build_creative_nano_prompt(recipe: dict, beat: dict,
                                 characters: list, location: str,
                                 atmosphere: str, time_of_day: str,
                                 emotion_level: int,
                                 profile: dict) -> str:
    """Build a nano_prompt using creative intelligence.

    Structure: location/light + character action + composition + atmosphere
    Each line = one implied shot (DP discipline).
    """
    parts = []

    # Location and light (DP discipline)
    if location:
        time_light = {
            "MORNING": "morning light filters through",
            "LATE MORNING": "late morning sun slants through",
            "MIDDAY": "harsh midday light",
            "AFTERNOON": "warm afternoon light",
            "LATE AFTERNOON": "golden late afternoon light pours through",
            "EVENING": "fading evening light",
            "NIGHT": "darkness, practical light sources only",
            "DAWN": "first pale light of dawn",
            "DUSK": "last blue light of dusk",
        }.get(time_of_day.upper(), "natural light")

        parts.append(f"{location}, {time_light}")

    # Character action (Actor discipline)
    beat_desc = beat.get("description") or beat.get("character_action") or ""
    if characters and beat_desc:
        char_name = characters[0] if characters else ""
        parts.append(f"Character action: {char_name} {beat_desc}")
    elif beat_desc:
        parts.append(beat_desc)

    # Dialogue marker (if applicable)
    dialogue = beat.get("dialogue") or beat.get("dialogue_text") or ""
    if dialogue and characters:
        speaker = characters[0]
        # Truncate for prompt
        short_dialogue = dialogue[:120] + "..." if len(dialogue) > 120 else dialogue
        parts.append(f'{speaker} speaks: "{short_dialogue}"')

    # Atmosphere (Sound Designer discipline)
    if atmosphere:
        parts.append(atmosphere)

    # Composition note from recipe
    if recipe.get("motivation"):
        parts.append(f"Composition: {recipe['focal_length']}, {recipe['aperture']}")

    return ". ".join(p for p in parts if p)


def _build_creative_ltx_prompt(recipe: dict, beat: dict,
                                characters: list, duration: float,
                                emotion_level: int) -> str:
    """Build an LTX motion prompt using creative intelligence.

    Key: LTX needs PHYSICAL MOTION descriptions, not atmosphere.
    """
    parts = []

    # Motion hint from recipe (Editor discipline — rhythm)
    motion_hint = recipe.get("ltx_motion_hint", "")
    if motion_hint:
        parts.append(motion_hint)

    # Character performance marker (Actor discipline — Law 142)
    dialogue = beat.get("dialogue") or beat.get("dialogue_text") or ""
    beat_desc = beat.get("description") or beat.get("character_action") or ""

    if characters:
        char_name = characters[0]
        if dialogue:
            parts.append(f"character speaks: {char_name} delivers dialogue with conviction")
        elif beat_desc:
            # Extract physical verb from beat
            parts.append(f"character performs: {char_name} {beat_desc[:100]}")
        else:
            parts.append(f"character reacts: {char_name} subtle emotional response")

    # Camera movement (Director discipline)
    movement = recipe.get("movement", "static")
    if movement and movement != "static":
        parts.append(f"camera: {movement}")

    # Timing (Editor discipline — V25 Cure 231)
    if dialogue and characters:
        # Dialogue-aware: character PERFORMS speech from frame 1
        parts.append(f"0-{duration}s: continuous speaking performance, natural gestures throughout")
    else:
        parts.append(f"0-{duration}s: {movement}, natural micro-movement")

    # Gold standard negatives (Law 4)
    parts.append("face stable NO morphing NO grid NO split screen")

    return ", ".join(p for p in parts if p)


def _get_rhythm_position(grammar: dict, position: int) -> str:
    """Get the rhythm label for a shot position."""
    pattern = grammar.get("rhythm_pattern", "")
    if " → " in pattern:
        positions = pattern.split(" → ")
        idx = min(position, len(positions) - 1)
        return positions[idx]
    return ""


def _validate_coverage_distribution(shots: list, scene_id: str):
    """Validate that scene has proper A/B/C coverage (Law 225)."""
    roles = [s.get("coverage_role", "") for s in shots]
    has_a = any(r.startswith("A") for r in roles)

    if not has_a and len(shots) > 1:
        # Promote first wide/establishing shot to A_GEOGRAPHY
        for shot in shots:
            if shot["shot_type"] in ("establishing", "wide", "medium"):
                shot["coverage_role"] = "A_GEOGRAPHY"
                shot["shot_role"] = "GEOGRAPHY"
                logger.info(f"[CREATIVE] Scene {scene_id}: promoted {shot['shot_id']} to A_GEOGRAPHY (was missing)")
                break
        else:
            # Force first shot to A
            shots[0]["coverage_role"] = "A_GEOGRAPHY"
            shots[0]["shot_role"] = "GEOGRAPHY"
            logger.warning(f"[CREATIVE] Scene {scene_id}: forced first shot to A_GEOGRAPHY — no natural anchor")


# ═══════════════════════════════════════════════════════════════
# MAIN ENTRY POINT — Full project expansion
# ═══════════════════════════════════════════════════════════════

def creative_expand_project(project: str,
                            genre: str = "mystery_thriller",
                            director: str = "atlas_default",
                            target_runtime_seconds: int = 600) -> Tuple[bool, dict, str]:
    """Expand an entire project using creative grammar.

    This is the main entry point called by the pipeline.
    Replaces SHOT_EXPANSION_INTEGRATOR.expand_project_shots().

    Args:
        project: project name
        genre: genre for pacing
        director: director aesthetic profile
        target_runtime_seconds: target total runtime

    Returns:
        (success: bool, result: dict, message: str)
    """
    project_path = PIPELINE_DIR / project

    # Load story bible
    bible_path = project_path / "story_bible.json"
    if not bible_path.exists():
        return False, {}, f"No story_bible.json found for {project}"

    with open(bible_path) as f:
        story_bible = json.load(f)

    scenes = story_bible.get("scenes") or []
    if not scenes:
        return False, {}, f"Story bible has no scenes for {project}"

    total_scenes = len(scenes)
    all_shots = []
    scene_manifest = []
    scene_classifications = {}

    logger.info(f"\n{'='*60}")
    logger.info(f"CREATIVE EXPANSION: {project}")
    logger.info(f"Genre: {genre} | Director: {director} | Scenes: {total_scenes}")
    logger.info(f"Target runtime: {target_runtime_seconds}s ({target_runtime_seconds/60:.1f}min)")
    logger.info(f"{'='*60}\n")

    for i, scene in enumerate(scenes):
        scene_id = scene.get("scene_id") or str(i).zfill(3)
        location = scene.get("location") or "UNKNOWN"
        int_ext = scene.get("int_ext") or "INT"
        time_of_day = scene.get("time_of_day") or "DAY"

        # Classify scene
        classification = analyze_scene_for_classification(scene, i, total_scenes)
        scene_classifications[scene_id] = classification

        # Build shots from grammar
        shots = build_scene_shots(
            scene_id, scene, classification, genre, director
        )

        logger.info(
            f"  Scene {scene_id} [{classification['scene_type'].upper()}]: "
            f"{len(shots)} shots | "
            f"{sum(s['duration_seconds'] for s in shots):.0f}s | "
            f"Characters: {', '.join(classification['characters'][:3])}"
        )

        all_shots.extend(shots)
        scene_manifest.append({
            "scene_id": scene_id,
            "location": f"{int_ext}. {location} - {time_of_day}",
            "int_ext": int_ext,
            "time_of_day": time_of_day,
            "shot_count": len(shots),
            "scene_type": classification["scene_type"],
            "characters": classification["characters"],
        })

    # Scale durations to hit target runtime
    total_duration = sum(s["duration_seconds"] for s in all_shots)
    if total_duration > 0 and abs(total_duration - target_runtime_seconds) > 30:
        scale_factor = target_runtime_seconds / total_duration
        # Clamp scale factor to reasonable range
        scale_factor = max(0.5, min(2.0, scale_factor))

        for shot in all_shots:
            new_dur = round(shot["duration_seconds"] * scale_factor, 1)
            # Respect dialogue duration floor (Law 224)
            dialogue = shot.get("dialogue_text", "")
            if dialogue:
                word_count = len(dialogue.split())
                min_speak = (word_count / 2.3) + 1.5
                new_dur = max(new_dur, min_speak)
            # Clamp to reasonable bounds
            new_dur = max(3.0, min(20.0, new_dur))
            shot["duration_seconds"] = new_dur
            shot["duration"] = new_dur
            shot["ltx_duration_seconds"] = new_dur

        scaled_total = sum(s["duration_seconds"] for s in all_shots)
        logger.info(f"\n  Duration scaled: {total_duration:.0f}s → {scaled_total:.0f}s "
                    f"(target: {target_runtime_seconds}s, factor: {scale_factor:.2f})")

    # Load existing shot_plan or create new
    shot_plan_path = project_path / "shot_plan.json"
    if shot_plan_path.exists():
        with open(shot_plan_path) as f:
            manifest = json.load(f)
    else:
        manifest = {}

    # Preserve immutable metadata
    canonical_count = manifest.get("_canonical_scene_count", total_scenes)

    # Build final manifest
    manifest["shots"] = all_shots
    manifest["scene_manifest"] = scene_manifest
    manifest["_requires_shot_expansion"] = False
    manifest["_creative_expansion"] = True
    manifest["_creative_genre"] = genre
    manifest["_creative_director"] = director
    manifest["_creative_timestamp"] = datetime.now().isoformat()
    manifest["_canonical_scene_count"] = canonical_count
    manifest["_scene_classifications"] = scene_classifications

    # Backup before write (Law 180)
    if shot_plan_path.exists():
        backup_name = f"shot_plan.json.backup_creative_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        backup_path = project_path / backup_name
        import shutil
        shutil.copy2(shot_plan_path, backup_path)
        logger.info(f"  Backup: {backup_name}")

    # Write
    with open(shot_plan_path, "w") as f:
        json.dump(manifest, f, indent=2, default=str)

    final_duration = sum(s["duration_seconds"] for s in all_shots)
    result = {
        "shots": all_shots,
        "scene_manifest": scene_manifest,
        "total_shots": len(all_shots),
        "total_duration": final_duration,
        "total_duration_formatted": f"{int(final_duration//60)}:{int(final_duration%60):02d}",
        "scene_classifications": scene_classifications,
        "genre": genre,
        "director": director,
    }

    msg = (
        f"Creative expansion complete: {len(all_shots)} shots across {total_scenes} scenes, "
        f"{result['total_duration_formatted']} total runtime"
    )
    logger.info(f"\n  {msg}")
    logger.info(f"  Shot plan saved to {shot_plan_path}")

    return True, result, msg


# ═══════════════════════════════════════════════════════════════
# CLI ENTRY POINT
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format='%(message)s')

    if len(sys.argv) < 2:
        print("Usage: python3 tools/creative_pipeline_bridge.py <project> [genre] [director]")
        print(f"\nGenres: {', '.join(GENRE_PACING.keys())}")
        print(f"Directors: {', '.join(DIRECTOR_PROFILES.keys())}")
        sys.exit(1)

    project = sys.argv[1]
    genre = sys.argv[2] if len(sys.argv) > 2 else "mystery_thriller"
    director = sys.argv[3] if len(sys.argv) > 3 else "atlas_default"

    success, result, msg = creative_expand_project(project, genre, director)
    if success:
        print(f"\n✅ {msg}")
        print(f"\nScene breakdown:")
        for sc in result["scene_manifest"]:
            cls = result["scene_classifications"].get(sc["scene_id"], {})
            print(f"  {sc['scene_id']} [{cls.get('scene_type', '?').upper():15s}] "
                  f"{sc['shot_count']} shots | {sc['location']}")
    else:
        print(f"\n❌ {msg}")
        sys.exit(1)
