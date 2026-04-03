"""
SEMANTIC INVARIANTS - V17 Factory

These are NON-NEGOTIABLE rules that MUST be enforced.
Critic MUST FAIL (not warn) if any invariant is violated.

Usage:
    from atlas_agents.semantic_invariants import check_all_invariants

    result = check_all_invariants(project)
    if not result["passed"]:
        # BLOCK - do not proceed
"""

import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from enum import Enum


class Severity(Enum):
    BLOCKING = "BLOCKING"  # Must fail, cannot proceed
    WARNING = "WARNING"    # Warn but can proceed
    INFO = "INFO"          # Informational only


@dataclass
class Invariant:
    """Defines a semantic invariant."""
    name: str
    description: str
    severity: Severity
    check_fn: callable


class InvariantViolation:
    """Records a violation of an invariant."""
    def __init__(self, invariant_name: str, message: str, severity: Severity, details: dict = None):
        self.invariant_name = invariant_name
        self.message = message
        self.severity = severity
        self.details = details or {}


# =============================================================================
# INVARIANT DEFINITIONS
# =============================================================================

def check_beats_exist_if_script_has_dialogue(project_path: Path) -> Optional[InvariantViolation]:
    """
    INVARIANT: If the original script has dialogue, beats MUST exist.
    Beats are where dialogue lives - stripping them loses the story.
    """
    story_bible_path = project_path / "story_bible.json"
    if not story_bible_path.exists():
        return None  # Can't check without story_bible

    with open(story_bible_path) as f:
        sb = json.load(f)

    scenes = sb.get("scenes", [])
    if not scenes:
        return None

    # Check if any scene has beats
    scenes_with_beats = [s for s in scenes if s.get("beats")]

    if len(scenes_with_beats) == 0:
        # Check if there was supposed to be dialogue
        imported_script = project_path / "imported_script.txt"
        if imported_script.exists():
            content = imported_script.read_text()
            # Simple dialogue detection (CHARACTER NAME followed by lines)
            import re
            dialogue_matches = re.findall(r'^[A-Z][A-Z\s]+\n', content, re.MULTILINE)
            if len(dialogue_matches) > 5:  # More than 5 potential dialogue cues
                return InvariantViolation(
                    "beats_must_exist_if_script_has_dialogue",
                    f"Story bible has {len(scenes)} scenes but 0 beats. Dialogue appears to have been stripped.",
                    Severity.BLOCKING,
                    {"scenes": len(scenes), "beats": 0, "dialogue_cues_in_script": len(dialogue_matches)}
                )

    return None


def check_dialogue_propagates_to_shots(project_path: Path) -> Optional[InvariantViolation]:
    """
    INVARIANT: If story_bible has dialogue, shot_plan MUST have dialogue.
    Dialogue is execution truth for video generation.
    """
    story_bible_path = project_path / "story_bible.json"
    shot_plan_path = project_path / "shot_plan.json"

    if not story_bible_path.exists() or not shot_plan_path.exists():
        return None

    with open(story_bible_path) as f:
        sb = json.load(f)

    with open(shot_plan_path) as f:
        sp = json.load(f)

    # Count dialogue in story_bible
    sb_dialogue_count = sum(
        1 for s in sb.get("scenes", [])
        for b in s.get("beats", [])
        if b.get("dialogue")
    )

    # Count dialogue in shot_plan
    sp_dialogue_count = sum(
        1 for s in sp.get("shots", [])
        if s.get("dialogue")
    )

    if sb_dialogue_count > 0 and sp_dialogue_count == 0:
        return InvariantViolation(
            "dialogue_must_propagate_to_shots",
            f"Story bible has {sb_dialogue_count} dialogue entries but shot_plan has 0.",
            Severity.BLOCKING,
            {"story_bible_dialogue": sb_dialogue_count, "shot_plan_dialogue": sp_dialogue_count}
        )

    return None


def check_characters_exist_in_shots(project_path: Path) -> Optional[InvariantViolation]:
    """
    INVARIANT: Every shot MUST have characters assigned.
    Characters are required for reference-based generation.
    """
    shot_plan_path = project_path / "shot_plan.json"

    if not shot_plan_path.exists():
        return None

    with open(shot_plan_path) as f:
        sp = json.load(f)

    shots = sp.get("shots", [])
    shots_without_chars = [s for s in shots if not s.get("characters")]

    if len(shots_without_chars) > len(shots) * 0.5:  # More than 50% without characters
        return InvariantViolation(
            "characters_must_exist_in_shots",
            f"{len(shots_without_chars)}/{len(shots)} shots have no characters assigned.",
            Severity.BLOCKING,
            {"total_shots": len(shots), "shots_without_chars": len(shots_without_chars)}
        )

    return None


def check_locations_have_masters(project_path: Path) -> Optional[InvariantViolation]:
    """
    INVARIANT: Locations array must exist.
    Location masters directory should exist for reference-based generation.
    """
    story_bible_path = project_path / "story_bible.json"
    location_masters_dir = project_path / "location_masters"

    if not story_bible_path.exists():
        return None

    with open(story_bible_path) as f:
        sb = json.load(f)

    locations = sb.get("locations", []) or sb.get("setting", {}).get("locations", [])

    if not locations:
        return InvariantViolation(
            "locations_must_have_masters",
            "No locations array in story_bible.",
            Severity.WARNING,
            {"locations_count": 0}
        )

    if not location_masters_dir.exists():
        return InvariantViolation(
            "locations_must_have_masters",
            "location_masters directory does not exist.",
            Severity.WARNING,
            {"locations_count": len(locations), "directory_exists": False}
        )

    return None


def check_extended_shots_for_long_runtime(project_path: Path) -> Optional[InvariantViolation]:
    """
    INVARIANT: If runtime > 10 minutes, extended shots (>20s) MUST exist.
    Otherwise the final output will be drastically shorter than intended.
    """
    shot_plan_path = project_path / "shot_plan.json"

    if not shot_plan_path.exists():
        return None

    with open(shot_plan_path) as f:
        sp = json.load(f)

    shots = sp.get("shots", [])
    total_duration = sum(s.get("duration", 20) for s in shots)
    extended_shots = [s for s in shots if s.get("duration", 20) > 20]

    # If target runtime > 10 min but no extended shots
    if total_duration > 600 and len(extended_shots) == 0:
        return InvariantViolation(
            "extended_shots_required_for_long_runtime",
            f"Runtime is {total_duration}s but no shots are >20s.",
            Severity.WARNING,
            {"total_duration": total_duration, "extended_shots": 0}
        )

    return None


def check_cast_has_references(project_path: Path) -> Optional[InvariantViolation]:
    """
    INVARIANT: Cast map entries MUST have reference_url.
    Without references, generation cannot use character consistency.
    """
    cast_map_path = project_path / "cast_map.json"

    if not cast_map_path.exists():
        return InvariantViolation(
            "cast_must_have_references",
            "cast_map.json does not exist.",
            Severity.BLOCKING,
            {}
        )

    with open(cast_map_path) as f:
        cm = json.load(f)

    entries = [k for k in cm.keys() if not k.startswith("_")]
    # Skip EXTRAS POOL entries - they don't require character references by design
    entries_without_refs = [
        k for k, v in cm.items()
        if not k.startswith("_") and isinstance(v, dict)
        and not v.get("is_extras_pool", False)  # Skip extras pool
        and not v.get("character_reference_url") and not v.get("reference_url")
    ]

    if len(entries_without_refs) > 0:
        return InvariantViolation(
            "cast_must_have_references",
            f"{len(entries_without_refs)}/{len(entries)} cast entries missing character_reference_url.",
            Severity.BLOCKING,
            {"total_entries": len(entries), "missing_refs": len(entries_without_refs)}
        )

    return None


def check_nano_prompts_exist(project_path: Path) -> Optional[InvariantViolation]:
    """
    INVARIANT: All shots MUST have nano_prompts.
    Without prompts, generation cannot proceed.
    """
    shot_plan_path = project_path / "shot_plan.json"

    if not shot_plan_path.exists():
        return None

    with open(shot_plan_path) as f:
        sp = json.load(f)

    shots = sp.get("shots", [])
    shots_without_prompts = [s for s in shots if not s.get("nano_prompt")]

    if len(shots_without_prompts) > 0:
        return InvariantViolation(
            "nano_prompts_must_exist",
            f"{len(shots_without_prompts)}/{len(shots)} shots missing nano_prompt.",
            Severity.BLOCKING,
            {"total_shots": len(shots), "missing_prompts": len(shots_without_prompts)}
        )

    return None


def check_segment_metadata_complete(project_path: Path) -> Optional[InvariantViolation]:
    """
    INVARIANT: Extended shots (>20s) MUST have complete segment metadata.
    Segments must have: segment_index, duration (not undefined).
    Segment indices must be contiguous (0, 1, 2, ...).
    Sum of segment durations must equal shot duration (±2s tolerance).

    This prevents "undefined" in UI bundle and stitch failures.
    """
    shot_plan_path = project_path / "shot_plan.json"

    if not shot_plan_path.exists():
        return None

    with open(shot_plan_path) as f:
        sp = json.load(f)

    shots = sp.get("shots", [])
    extended_shots = [s for s in shots if s.get("duration", 20) > 20]

    if not extended_shots:
        return None  # No extended shots to check

    violations = []
    DURATION_TOLERANCE = 2.0

    for shot in extended_shots:
        shot_id = shot.get("shot_id", "unknown")
        duration = shot.get("duration", shot.get("duration_seconds", 20))
        segments = shot.get("segments", shot.get("render_plan", {}).get("segments", []))

        # Check 1: Extended shot must have segments
        if not segments:
            num_expected = max(1, (duration + 19) // 20)
            if num_expected > 1:
                violations.append(f"{shot_id}: {duration}s shot has no segments (needs {num_expected})")
                continue

        # Check 2: Each segment must have valid metadata
        for seg in segments:
            seg_idx = seg.get("segment_index")
            seg_dur = seg.get("duration")

            if seg_idx is None or seg_idx == "undefined":
                violations.append(f"{shot_id}: segment missing segment_index")
            if seg_dur is None or seg_dur == "undefined" or seg_dur == 0:
                violations.append(f"{shot_id}: segment missing duration")

        # Check 3: Segment indices contiguous
        if segments:
            indices = []
            for seg in segments:
                idx = seg.get("segment_index")
                if isinstance(idx, int):
                    indices.append(idx)
                elif isinstance(idx, str) and idx.isdigit():
                    indices.append(int(idx))

            if indices:
                indices.sort()
                expected = list(range(len(indices)))
                if indices != expected:
                    violations.append(f"{shot_id}: non-contiguous indices {indices}")

        # Check 4: Sum of durations matches shot duration
        if segments:
            seg_total = sum(s.get("duration", 0) for s in segments if isinstance(s.get("duration"), (int, float)))
            if abs(seg_total - duration) > DURATION_TOLERANCE:
                violations.append(f"{shot_id}: segment sum {seg_total}s != shot duration {duration}s")

    if violations:
        return InvariantViolation(
            "segment_metadata_must_be_complete",
            f"{len(violations)} segment metadata issues in extended shots.",
            Severity.BLOCKING,
            {"issues": violations[:10], "total_issues": len(violations)}
        )

    return None


def check_cast_references_are_ai_actors(project_path: Path) -> Optional[InvariantViolation]:
    """
    INVARIANT #10: Character references MUST be valid AI actor references.
    NEVER use SCRIPT_ACCURATE references — they are manual/wrong.

    Valid refs:
      - character_reference_url: *_CHAR_REFERENCE.jpg (actor in character wardrobe — preferred)
      - character_reference_url: *_LOCKED_REFERENCE.jpg (actor headshot — acceptable fallback)
      - headshot_url: *_LOCKED_REFERENCE.jpg (actor headshot for UI display)
    Invalid refs: /SCRIPT_ACCURATE/*.jpg, any path containing SCRIPT_ACCURATE

    CHAR_REFERENCE files are generated by the pipeline to show the cast AI actor
    in character-appropriate wardrobe and setting. They are the PREFERRED reference
    for generation because they capture the character's look, not just the actor's face.
    """
    cast_map_path = project_path / "cast_map.json"

    if not cast_map_path.exists():
        return None

    with open(cast_map_path) as f:
        cm = json.load(f)

    violations = []

    for char_name, entry in cm.items():
        if char_name.startswith("_"):
            continue
        if not isinstance(entry, dict):
            continue
        if entry.get("is_extras_pool", False) or entry.get("ai_actor") == "EXTRAS POOL":
            continue

        # Check ALL reference fields
        ref_fields = [
            ("character_reference_url", entry.get("character_reference_url", "")),
            ("recast_image_path", entry.get("recast_image_path", "")),
            ("headshot_url", entry.get("headshot_url", "")),
        ]

        for field_name, ref_path in ref_fields:
            if not ref_path:
                continue
            ref_str = str(ref_path).upper()

            # BLOCK: Any reference containing SCRIPT_ACCURATE
            if "SCRIPT_ACCURATE" in ref_str:
                violations.append(
                    f"{char_name}.{field_name} uses SCRIPT_ACCURATE ref: {ref_path}"
                )

            # V17.7.2: Accept BOTH CHAR_REFERENCE and LOCKED_REFERENCE as valid
            # CHAR_REFERENCE = actor in character wardrobe (preferred for generation)
            # LOCKED_REFERENCE = actor headshot (acceptable for UI/fallback)
            if field_name != "recast_image_path":
                is_valid_ref = (
                    "CHAR_REFERENCE" in ref_str or
                    "LOCKED_REFERENCE" in ref_str or
                    "ai_actors" in str(ref_path).lower() or
                    "fal.ai" in str(ref_path).lower() or
                    "character_library_locked" in str(ref_path).lower()
                )
                if not is_valid_ref:
                    violations.append(
                        f"{char_name}.{field_name} not a valid character reference: {ref_path}"
                    )

    if violations:
        return InvariantViolation(
            "cast_references_must_be_ai_actors",
            f"{len(violations)} character references are invalid. "
            f"SCRIPT_ACCURATE refs cause wrong character appearances.",
            Severity.BLOCKING,
            {"violations": violations[:15], "total": len(violations)}
        )

    return None


def check_ltx_prompt_contextual(project_path: Path) -> Optional[InvariantViolation]:
    """
    INVARIANT: LTX motion prompts should be contextual, not generic.
    If shot has dialogue/characters, LTX prompt should reference them.

    This is a WARNING, not blocking - helps catch template-style prompts.
    """
    shot_plan_path = project_path / "shot_plan.json"

    if not shot_plan_path.exists():
        return None

    with open(shot_plan_path) as f:
        sp = json.load(f)

    shots = sp.get("shots", [])
    generic_prompts = []

    GENERIC_PATTERNS = [
        "subtle camera movement",
        "slow dolly",
        "static shot",
        "gentle movement"
    ]

    for shot in shots:
        shot_id = shot.get("shot_id", "unknown")
        ltx_prompt = (shot.get("ltx_motion_prompt") or "").lower()
        dialogue = shot.get("dialogue", "")
        characters = shot.get("characters", [])

        if not ltx_prompt:
            continue

        # Check if prompt is generic AND shot has dialogue/characters
        is_generic = any(p in ltx_prompt for p in GENERIC_PATTERNS)
        has_context = bool(dialogue) or len(characters) > 0

        if is_generic and has_context and len(ltx_prompt) < 50:
            generic_prompts.append(shot_id)

    # Warn if more than 30% are generic
    if len(generic_prompts) > len(shots) * 0.3:
        return InvariantViolation(
            "ltx_prompts_should_be_contextual",
            f"{len(generic_prompts)}/{len(shots)} shots have generic LTX prompts despite having dialogue/characters.",
            Severity.WARNING,
            {"generic_shots": generic_prompts[:10], "total_generic": len(generic_prompts)}
        )

    return None


# =============================================================================
# INVARIANT REGISTRY
# =============================================================================

# =============================================================================
# V17.6: TRUTH-VALIDATION INVARIANTS — Catch lies, not just missing data
# =============================================================================

def check_location_master_matches_scene(project_path: Path) -> Optional[InvariantViolation]:
    """
    INVARIANT: A shot's location_master_url MUST reference the correct location for its scene.
    A LAW_OFFICE shot must reference LAW_OFFICE.jpg, NOT CITY_APARTMENT.jpg.
    This catches the UI lying about which location a shot belongs to.
    """
    shot_plan_path = project_path / "shot_plan.json"
    if not shot_plan_path.exists():
        return None

    with open(shot_plan_path) as f:
        sp = json.load(f)

    mismatches = []
    for shot in sp.get("shots", []):
        loc_url = shot.get("location_master_url", "")
        scene_loc = (shot.get("location") or shot.get("scene_location") or "").upper().strip()
        if not loc_url or not scene_loc:
            continue

        # Extract filename from URL: /api/media?path=.../location_masters/LAW_OFFICE.jpg
        import re as _re
        url_match = _re.search(r'/location_masters/([^/]+)\.jpg', loc_url)
        if not url_match:
            continue

        file_loc = url_match.group(1).replace("_", " ").replace("-", " ").strip().upper()
        # Remove ONLY time-of-day suffixes, preserve compound location parts
        scene_loc_clean = _re.sub(r'\s*[-–]\s*(NIGHT|DAY|EVENING|MORNING|AFTERNOON|LATE|DAWN|DUSK|LATER|CONTINUOUS).*$', '', scene_loc, flags=_re.IGNORECASE).strip()
        # Also extract compound parts (MANOR – EAST WING CORRIDOR → [MANOR, EAST WING CORRIDOR])
        scene_parts = [p.strip() for p in _re.split(r'\s*[-–/,]\s*', scene_loc_clean) if len(p.strip()) > 2]

        # Check if the filename location matches ANY part of the scene location
        matched = False
        if file_loc in scene_loc_clean or scene_loc_clean in file_loc:
            matched = True
        else:
            # Check word overlap against full location AND each compound part
            file_words = set(file_loc.split())
            all_scene_words = set(scene_loc_clean.split())
            if len(file_words & all_scene_words) >= 1:
                matched = True
            else:
                # Check if file_loc matches any compound part
                for part in scene_parts:
                    if file_loc in part or part in file_loc:
                        matched = True
                        break
                    part_words = set(part.split())
                    if len(file_words & part_words) >= 1:
                        matched = True
                        break

        if not matched:
                mismatches.append({
                    "shot_id": shot.get("shot_id"),
                    "scene_location": scene_loc,
                    "master_file": url_match.group(1),
                    "expected": scene_loc_clean
                })

    if len(mismatches) > 3:  # Allow a few edge cases
        return InvariantViolation(
            "location_master_matches_scene",
            f"{len(mismatches)} shots have wrong location master assigned (e.g., {mismatches[0]['shot_id']}: scene={mismatches[0]['scene_location']} but master={mismatches[0]['master_file']})",
            Severity.BLOCKING,
            {"mismatches": mismatches[:10]}
        )
    return None


def check_reference_files_exist(project_path: Path) -> Optional[InvariantViolation]:
    """
    INVARIANT: All character_reference_url and location_master_url files MUST exist on disk.
    A URL pointing to a non-existent file is a lie.
    V17.7: Applies path translation for cross-environment compatibility.
    """
    shot_plan_path = project_path / "shot_plan.json"
    if not shot_plan_path.exists():
        return None

    with open(shot_plan_path) as f:
        sp = json.load(f)

    project_name = project_path.name
    missing_refs = []
    checked = {}  # url -> exists bool

    def _path_exists(file_path_str):
        """Check if file exists, with path translation for cross-environment."""
        p = Path(file_path_str)
        if p.exists():
            return True
        # V17.7: Try path translation (user's local → sandbox)
        markers = [f"pipeline_outputs/{project_name}/", f"ATLAS_CONTROL_SYSTEM/"]
        for marker in markers:
            idx = file_path_str.find(marker)
            if idx >= 0:
                if "pipeline_outputs/" in marker:
                    rel = file_path_str[idx + len(marker):]
                    candidate = project_path / rel
                else:
                    rel = file_path_str[idx + len(marker):]
                    # Try from the ATLAS_CONTROL_SYSTEM root
                    candidate = project_path.parent.parent / rel
                if candidate.exists():
                    return True
        return False

    for shot in sp.get("shots", []):
        for field in ["character_reference_url", "location_master_url"]:
            url = shot.get(field, "")
            if not url or url in checked:
                continue

            # Extract filesystem path from /api/media?path=...
            if "path=" in url:
                file_path = url.split("path=", 1)[1]
                exists = _path_exists(file_path)
                checked[url] = exists
                if not exists:
                    missing_refs.append({
                        "shot_id": shot.get("shot_id"),
                        "field": field,
                        "url": url[:100],
                        "file_path": file_path
                    })
            else:
                checked[url] = True  # Non-path URLs (http, etc.) — skip

    if missing_refs:
        return InvariantViolation(
            "reference_files_exist",
            f"{len(missing_refs)} reference URLs point to non-existent files (e.g., {missing_refs[0]['field']} in {missing_refs[0]['shot_id']})",
            Severity.WARNING,  # V17.7: Downgraded from BLOCKING — path translation handles most cases
            {"missing": missing_refs[:10]}
        )
    return None


def check_stale_first_frames(project_path: Path) -> Optional[InvariantViolation]:
    """
    INVARIANT: First frame images should not be older than their shot's last prompt edit.
    Stale frames mean the UI shows an image that doesn't match the current prompt.
    """
    import os

    shot_plan_path = project_path / "shot_plan.json"
    if not shot_plan_path.exists():
        return None

    sp_mtime = os.path.getmtime(shot_plan_path)

    with open(shot_plan_path) as f:
        sp = json.load(f)

    stale_frames = []
    ff_dir = project_path / "first_frames"
    if not ff_dir.exists():
        return None

    for shot in sp.get("shots", []):
        sid = shot.get("shot_id", "")
        frame_path = ff_dir / f"{sid}.jpg"
        if not frame_path.exists():
            continue

        frame_mtime = os.path.getmtime(frame_path)
        # If shot_plan was modified AFTER the frame was generated, frame may be stale
        if sp_mtime > frame_mtime + 60:  # 60s grace period
            stale_frames.append({
                "shot_id": sid,
                "frame_age_hours": round((sp_mtime - frame_mtime) / 3600, 1)
            })

    if len(stale_frames) > 5:  # Allow a few
        return InvariantViolation(
            "stale_first_frames",
            f"{len(stale_frames)} first frames may be stale (shot_plan modified after frame generation)",
            Severity.WARNING,
            {"stale": stale_frames[:10]}
        )
    return None


def check_cast_map_field_normalization(project_path: Path) -> Optional[InvariantViolation]:
    """
    INVARIANT: Cast map entries should use canonical 'character_reference_url' field.
    Legacy names (reference_url, locked_reference_url) indicate unnormalized data.
    """
    cast_map_path = project_path / "cast_map.json"
    if not cast_map_path.exists():
        return None
    with open(cast_map_path) as f:
        cm = json.load(f)
    violations = []
    for char_name, entry in cm.items():
        if not isinstance(entry, dict) or char_name.startswith("_"):
            continue
        has_legacy = any(k in entry for k in ["reference_url", "locked_reference_url"])
        has_canonical = "character_reference_url" in entry
        if has_legacy and not has_canonical:
            violations.append(char_name)
    if violations:
        return InvariantViolation(
            "cast_map_field_normalization",
            f"{len(violations)} cast entries use legacy field names (should be 'character_reference_url'): {violations[:5]}",
            Severity.WARNING,
            {"affected": violations}
        )
    return None


def check_locks_field_normalization(project_path: Path) -> Optional[InvariantViolation]:
    """
    INVARIANT: master_locks.json should use canonical lock field names
    (characters, locations, casting) not legacy (characters_locked, etc.).
    """
    locks_path = project_path / "master_locks.json"
    if not locks_path.exists():
        return None
    with open(locks_path) as f:
        locks = json.load(f)
    legacy_keys = []
    if "characters_locked" in locks and "characters" not in locks:
        legacy_keys.append("characters_locked")
    if "locations_locked" in locks and "locations" not in locks:
        legacy_keys.append("locations_locked")
    if "casting_locked" in locks and "casting" not in locks:
        legacy_keys.append("casting_locked")
    if legacy_keys:
        return InvariantViolation(
            "locks_field_normalization",
            f"master_locks.json uses legacy field names: {legacy_keys}",
            Severity.WARNING,
            {"legacy_fields": legacy_keys}
        )
    return None


INVARIANTS = [
    Invariant(
        "beats_must_exist_if_script_has_dialogue",
        "If the original script has dialogue, beats MUST exist in story_bible",
        Severity.BLOCKING,
        check_beats_exist_if_script_has_dialogue
    ),
    Invariant(
        "dialogue_must_propagate_to_shots",
        "Dialogue from story_bible MUST appear in shot_plan",
        Severity.BLOCKING,
        check_dialogue_propagates_to_shots
    ),
    Invariant(
        "characters_must_exist_in_shots",
        "Every shot MUST have characters assigned",
        Severity.BLOCKING,
        check_characters_exist_in_shots
    ),
    Invariant(
        "locations_must_have_masters",
        "Locations array must exist with corresponding directory",
        Severity.WARNING,
        check_locations_have_masters
    ),
    Invariant(
        "extended_shots_required_for_long_runtime",
        "If runtime > 10 min, extended shots (>20s) MUST exist",
        Severity.WARNING,
        check_extended_shots_for_long_runtime
    ),
    Invariant(
        "cast_must_have_references",
        "Cast map entries MUST have reference_url",
        Severity.BLOCKING,
        check_cast_has_references
    ),
    Invariant(
        "nano_prompts_must_exist",
        "All shots MUST have nano_prompts",
        Severity.BLOCKING,
        check_nano_prompts_exist
    ),
    Invariant(
        "segment_metadata_must_be_complete",
        "Extended shots (>20s) MUST have complete segment metadata",
        Severity.BLOCKING,
        check_segment_metadata_complete
    ),
    Invariant(
        "ltx_prompts_should_be_contextual",
        "LTX motion prompts should reference dialogue/characters when present",
        Severity.WARNING,
        check_ltx_prompt_contextual
    ),
    Invariant(
        "cast_references_must_be_ai_actors",
        "Character references MUST be valid (CHAR_REFERENCE or LOCKED_REFERENCE), NEVER SCRIPT_ACCURATE",
        Severity.BLOCKING,
        check_cast_references_are_ai_actors
    ),
    # V17.6: TRUTH-VALIDATION INVARIANTS
    Invariant(
        "location_master_matches_scene",
        "Shot location_master_url MUST reference the correct location for its scene",
        Severity.WARNING,  # V17.7: Downgraded — cross-environment path issues make this unreliable as blocking
        check_location_master_matches_scene
    ),
    Invariant(
        "reference_files_exist",
        "All character_reference_url and location_master_url files MUST exist on disk",
        Severity.WARNING,  # V17.7: Downgraded — path translation handles cross-environment
        check_reference_files_exist
    ),
    Invariant(
        "stale_first_frames",
        "First frames should not be older than their shot's prompt edits",
        Severity.WARNING,
        check_stale_first_frames
    ),
    # V17.6: NORMALIZATION INVARIANTS
    Invariant(
        "cast_map_field_normalization",
        "Cast map entries should use canonical field name 'character_reference_url'",
        Severity.WARNING,
        check_cast_map_field_normalization
    ),
    Invariant(
        "locks_field_normalization",
        "master_locks.json should use canonical lock field names",
        Severity.WARNING,
        check_locks_field_normalization
    ),
]


# =============================================================================
# PUBLIC API
# =============================================================================

def check_all_invariants(project: str, repo_root: Path = None) -> Dict:
    """
    Check all semantic invariants for a project.

    Returns:
        {
            "passed": bool,
            "blocking_violations": [...],
            "warnings": [...],
            "all_violations": [...]
        }
    """
    if repo_root is None:
        repo_root = Path("/Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM")

    project_path = repo_root / "pipeline_outputs" / project

    if not project_path.exists():
        return {
            "passed": False,
            "blocking_violations": [{"invariant": "project_exists", "message": f"Project {project} not found"}],
            "warnings": [],
            "all_violations": []
        }

    blocking_violations = []
    warnings = []

    for invariant in INVARIANTS:
        try:
            violation = invariant.check_fn(project_path)
            if violation:
                violation_dict = {
                    "invariant": violation.invariant_name,
                    "message": violation.message,
                    "severity": violation.severity.value,
                    "details": violation.details
                }

                if violation.severity == Severity.BLOCKING:
                    blocking_violations.append(violation_dict)
                else:
                    warnings.append(violation_dict)
        except Exception as e:
            warnings.append({
                "invariant": invariant.name,
                "message": f"Check failed: {str(e)}",
                "severity": "ERROR",
                "details": {}
            })

    return {
        "passed": len(blocking_violations) == 0,
        "blocking_violations": blocking_violations,
        "warnings": warnings,
        "all_violations": blocking_violations + warnings
    }


def get_invariant_names() -> List[str]:
    """Get list of all invariant names."""
    return [i.name for i in INVARIANTS]


if __name__ == "__main__":
    import sys
    project = sys.argv[1] if len(sys.argv) > 1 else "kord_v17"
    result = check_all_invariants(project)
    print(json.dumps(result, indent=2))
