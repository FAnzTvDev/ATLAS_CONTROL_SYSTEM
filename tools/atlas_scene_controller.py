"""
ATLAS V27 — SCENE CONTROLLER (Spinal Cord / Unified Executive)
================================================================
The SINGLE entry point for all scene generation. Replaces the old
enforcement-agent → enrichment → FAL pipeline with a unified executive
that coordinates all brain modules.

This is the missing spinal cord. The organs existed (Film Engine, Meta Director,
Basal Ganglia, Continuity Memory, Vision Analyst, Coverage Contract, Editorial
Intelligence, Creative Prompt Compiler). But they weren't wired into the actual
motor pathway that generates frames.

Architecture:
  SceneController.prepare_scene(scene_id, shots, cast_map, story_bible)
  → Phase 1: SCENE PLAN (coverage, speaker map, eyeline map, character count)
  → Phase 2: SHOT COMPILE (Film Engine + speaker + eyeline + coverage per shot)
  → Phase 3: VALIDATION (character count, framing, dialogue, dedup, generic check)
  → Phase 4: REF RESOLUTION (cast_map → character refs, multi-char handling)
  → Phase 5: AUTHORITY CONTRACT (shot authority gate per shot)
  → Returns: List[PreparedShot] ready for FAL with all checks passed

The enforcement agent is BYPASSED for controller-compiled shots.
The controller marks every shot with `_controller_compiled: True`.
The generation endpoint checks this flag and skips enforcement.

Brain region mapping:
  - Prefrontal cortex: SceneController.prepare_scene() (planning)
  - Motor cortex: PreparedShot (execution-ready payload)
  - Basal ganglia: coverage_validate() + variant scoring
  - Hippocampus: ContinuityMemory spatial state
  - Cerebellum: EditorialIntelligence timing/rhythm
  - Eyes: character_count_validate() + eyeline_validate()
  - Immune: dedup_validate() + generic_check()
  - Mouth: speaker_attribute() + dialogue_inject()

Usage:
  from tools.atlas_scene_controller import SceneController
  ctrl = SceneController(project_path, cast_map, story_bible, scene_manifest)
  prepared = ctrl.prepare_scene("001", shots)
  # prepared is List[PreparedShot] — each has .nano_prompt, .ltx_prompt,
  # .ref_urls, .fal_params, .validations, .speaker, .eyeline_target
  # Feed directly to FAL — no enforcement agent needed.
"""

import json
import re
import logging
import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
from copy import deepcopy
from datetime import datetime

logger = logging.getLogger(__name__)

# V27.1: DP Framing Standards — select best ref per shot type
try:
    from tools.creation_pack_validator import select_best_ref_for_shot, SHOT_TYPE_REF_MAP
    _DP_FRAMING_AVAILABLE = True
except ImportError:
    _DP_FRAMING_AVAILABLE = False
    SHOT_TYPE_REF_MAP = {}

# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class SpeakerAttribution:
    """Who is speaking, who is listening, and where they look."""
    speaker: str                    # Character name who owns this line
    listeners: List[str]            # Characters listening
    eyeline_target: str             # "off-screen-left", "off-screen-right", "partner", "camera"
    speaker_screen_position: str    # "left", "right", "center"
    dialogue_text: str              # The actual line
    is_reaction: bool = False       # True if this shot is a reaction (listener focus)

@dataclass
class CoverageAssignment:
    """Coverage role and framing contract for a shot."""
    role: str              # "A_GEOGRAPHY", "B_ACTION", "C_EMOTION"
    shot_type: str         # "wide", "medium", "close", "ECU", "OTS", etc.
    focal_length: str      # "24mm", "50mm", "85mm", "100mm", "135mm"
    expected_chars: int    # How many characters MUST be in frame
    framing_note: str      # "both visible", "single subject", "silhouette"
    isolation_negative: str  # "no other people" for single-char shots, "" for multi

@dataclass
class RefResolution:
    """Resolved character and location references for FAL."""
    character_refs: List[str]   # Absolute paths to char ref images
    location_refs: List[str]    # Absolute paths to location master images
    all_refs: List[str]         # character_refs + location_refs (ordered)
    primary_character: str      # Name of the char whose ref is FIRST
    ref_warnings: List[str]     # Any resolution issues

@dataclass
class ValidationResult:
    """Result of a single validation check."""
    check: str         # "speaker_attribution", "character_count", "eyeline", etc.
    passed: bool
    severity: str      # "blocking", "warning", "info"
    message: str
    auto_fix: str = "" # Description of auto-fix applied, or ""

@dataclass
class PreparedShot:
    """A fully prepared shot ready for FAL generation."""
    shot_id: str
    scene_id: str
    nano_prompt: str
    ltx_prompt: str
    ref_urls: List[str]
    fal_params: Dict[str, Any]
    speaker: Optional[SpeakerAttribution]
    coverage: CoverageAssignment
    refs: RefResolution
    validations: List[ValidationResult]
    authority_tier: str          # "hero", "production", "establishing", "broll"
    resolution: str              # "1K", "2K"
    duration: int
    characters: List[str]
    dialogue_text: str
    shot_type: str
    is_broll: bool
    is_chain_candidate: bool
    _controller_compiled: bool = True  # Flag for enforcement bypass
    _skip_enforcement: bool = True     # Explicit enforcement bypass

    @property
    def blocking_failures(self) -> List[ValidationResult]:
        return [v for v in self.validations if not v.passed and v.severity == "blocking"]

    @property
    def is_ready(self) -> bool:
        return len(self.blocking_failures) == 0


# ============================================================================
# SPEAKER ATTRIBUTION ENGINE
# ============================================================================

def attribute_speaker(shot: dict, scene_shots: List[dict]) -> Optional[SpeakerAttribution]:
    """
    Determine WHO is speaking in this shot, WHO is listening,
    and WHERE each character should look.

    This is the MOUTH system — it maps script dialogue to shot execution.
    """
    dialogue = shot.get("dialogue_text", "") or ""
    characters = shot.get("characters", [])
    if isinstance(characters, str):
        characters = [c.strip() for c in characters.split(",") if c.strip()]

    if not dialogue or not characters:
        return None

    # Parse speaker from dialogue text
    # Format: "CHARACTER NAME: line text" or "CHARACTER NAME: line | CHARACTER NAME: line"
    speaker = None
    lines = [l.strip() for l in dialogue.split("|")]
    for line in lines:
        if ":" in line:
            candidate = line.split(":")[0].strip()
            # Normalize — strip parentheticals like (V.O.)
            candidate = re.sub(r'\s*\(.*?\)\s*', '', candidate).strip()
            if candidate.upper() in [c.upper() for c in characters]:
                speaker = candidate.upper()
                break

    if not speaker:
        # Fallback: if dialogue exists but no "NAME:" prefix, assume first character
        speaker = characters[0].upper() if characters else None

    if not speaker:
        return None

    # Listeners = everyone except the speaker
    listeners = [c for c in characters if c.upper() != speaker]

    # Determine eyeline based on shot type and character count
    shot_type = (shot.get("shot_type") or "").lower()

    if len(characters) == 1:
        # Single character — eyeline should be OFF-CAMERA to imagined partner
        eyeline = "off-screen-right"  # Default: look screen-right to off-camera partner
    elif "over_the_shoulder" in shot_type or "ots" in shot_type:
        # OTS — speaker looks AT the foreground character (toward camera side)
        eyeline = "partner"
    elif "two_shot" in shot_type:
        eyeline = "partner"  # Face each other
    elif "reaction" in shot_type or "close" in shot_type:
        eyeline = "off-screen-left"  # Looking at off-screen partner
    else:
        eyeline = "partner"

    # Screen position: speaker tends to be on the side they're looking FROM
    if "reverse" in (shot.get("nano_prompt", "") or "").lower():
        speaker_pos = "right"
    else:
        speaker_pos = "left"

    # Is this a reaction shot? (listener is the focus, not the speaker)
    is_reaction = "reaction" in shot_type or "reacts" in dialogue.lower()

    return SpeakerAttribution(
        speaker=speaker,
        listeners=listeners,
        eyeline_target=eyeline,
        speaker_screen_position=speaker_pos,
        dialogue_text=dialogue,
        is_reaction=is_reaction,
    )


# ============================================================================
# COVERAGE ASSIGNMENT ENGINE
# ============================================================================

def assign_coverage(shot: dict, scene_shots: List[dict], shot_index: int) -> CoverageAssignment:
    """
    Assign coverage role and framing contract based on shot type,
    position in scene, and character count.
    """
    shot_type = (shot.get("shot_type") or "medium").lower()
    characters = shot.get("characters", [])
    if isinstance(characters, str):
        characters = [c.strip() for c in characters.split(",") if c.strip()]
    n_chars = len(characters)

    # Coverage role mapping
    WIDE_TYPES = {"establishing", "wide", "master", "closing"}
    MEDIUM_TYPES = {"medium", "over_the_shoulder", "two_shot", "medium_wide"}
    CLOSE_TYPES = {"close_up", "medium_close", "mcu", "ecu", "reaction", "extreme_close"}
    BROLL_TYPES = {"b-roll", "b_roll", "broll", "insert", "detail", "cutaway"}

    if shot_type in WIDE_TYPES or shot.get("is_broll") or shot.get("_broll"):
        role = "A_GEOGRAPHY"
        focal = shot.get("focal_length", "35mm") or "35mm"
    elif shot_type in CLOSE_TYPES:
        role = "C_EMOTION"
        focal = shot.get("focal_length", "100mm") or "100mm"
    elif shot_type in BROLL_TYPES:
        role = "B_ACTION"
        focal = shot.get("focal_length", "50mm") or "50mm"
    else:
        role = "B_ACTION"
        focal = shot.get("focal_length", "50mm") or "50mm"

    # Expected character count
    if shot_type in BROLL_TYPES or n_chars == 0:
        expected_chars = 0
        framing = "no characters"
        isolation = "no people, no figures, environmental detail only"
    elif n_chars == 1:
        expected_chars = 1
        framing = "single subject"
        isolation = "only one person in frame, no background figures, no other people"
    elif shot_type in {"over_the_shoulder"}:
        expected_chars = 2
        framing = "both visible, one foreground shoulder, one background face"
        isolation = ""
    elif shot_type in {"two_shot"}:
        expected_chars = 2
        framing = "both visible"
        isolation = ""
    else:
        expected_chars = n_chars
        framing = f"{n_chars} characters visible" if n_chars > 1 else "single subject"
        isolation = "" if n_chars > 1 else "only one person in frame, no background figures"

    return CoverageAssignment(
        role=role,
        shot_type=shot_type,
        focal_length=focal,
        expected_chars=expected_chars,
        framing_note=framing,
        isolation_negative=isolation,
    )


# ============================================================================
# REFERENCE RESOLUTION ENGINE
# ============================================================================

def resolve_refs(
    shot: dict,
    cast_map: dict,
    location_masters: dict,
    project_path: str,
    scene_manifest: dict = None,
    story_bible: dict = None,
) -> RefResolution:
    """
    Resolve ALL character and location references for a shot.
    For 2-character shots, returns BOTH character refs.
    Primary character = the SPEAKER if dialogue exists, else first in list.
    """
    characters = shot.get("characters", [])
    if isinstance(characters, str):
        characters = [c.strip() for c in characters.split(",") if c.strip()]

    dialogue = shot.get("dialogue_text", "") or ""
    shot_type = (shot.get("shot_type") or "").lower()

    # Determine primary character (speaker gets priority)
    primary = None
    if dialogue and ":" in dialogue:
        speaker_name = dialogue.split(":")[0].strip()
        speaker_name = re.sub(r'\s*\(.*?\)\s*', '', speaker_name).strip().upper()
        if speaker_name in [c.upper() for c in characters]:
            primary = speaker_name

    if not primary and characters:
        primary = characters[0].upper()

    # Resolve character refs from cast_map
    char_refs = []
    char_ref_names = []
    warnings = []

    # Order: primary character FIRST, then others
    ordered_chars = []
    if primary:
        ordered_chars.append(primary)
    for c in characters:
        if c.upper() not in [oc.upper() for oc in ordered_chars]:
            ordered_chars.append(c.upper())

    pp = Path(project_path)

    for char_name in ordered_chars:
        resolved = False
        for cm_name, cm_data in cast_map.items():
            if not isinstance(cm_data, dict) or cm_data.get("_is_alias_of"):
                continue
            if char_name.upper() in cm_name.upper() or cm_name.upper() in char_name.upper():
                # V27.1: DP Framing Standards — select best ref per shot type
                preferred_ref = None
                if _DP_FRAMING_AVAILABLE:
                    dp_prefs = SHOT_TYPE_REF_MAP.get(shot_type, {})
                    preferred_type = dp_prefs.get("char_ref")
                    if preferred_type and preferred_type != "headshot":
                        # Look for multi-angle ref pack
                        pack_key = f"_ref_pack_{preferred_type}"
                        pack_data = cm_data.get(pack_key, {})
                        if isinstance(pack_data, dict) and pack_data.get("path"):
                            # V27.1 FIX: Try direct path first, then relative to project
                            candidate = Path(pack_data["path"])
                            if not candidate.exists() and not candidate.is_absolute():
                                candidate = pp / pack_data["path"]
                            if not candidate.exists():
                                # Last resort: just the filename in char lib
                                candidate = pp / "character_library_locked" / Path(pack_data["path"]).name
                            if candidate.exists():
                                preferred_ref = str(candidate)
                                logger.debug(f"[DP FRAMING] {char_name} → {preferred_type} ref for {shot_type}")

                # V21.10: character_reference_url FIRST — never AI actor headshots
                ref = preferred_ref or (
                    cm_data.get("character_reference_url") or
                    cm_data.get("reference_url") or
                    cm_data.get("headshot_url", "")
                )
                if ref:
                    # Clean path
                    if ref.startswith("/api/media?path="):
                        ref = ref.split("path=", 1)[1]
                    # Try to find the file
                    ref_path = Path(ref)
                    if not ref_path.exists():
                        # Search in character_library_locked
                        fname = ref_path.name
                        for search_dir in [
                            pp / "character_library_locked",
                            Path(project_path).parent / "character_library_locked",
                        ]:
                            candidate = search_dir / fname
                            if candidate.exists():
                                ref = str(candidate)
                                break

                    if Path(ref).exists():
                        char_refs.append(ref)
                        char_ref_names.append(char_name)
                        resolved = True
                    else:
                        warnings.append(f"Ref file not found for {char_name}: {ref}")
                break

        if not resolved:
            warnings.append(f"No cast_map entry found for {char_name}")

    # Resolve location refs — V26.1 fix: normalize spaces/underscores + sub-location from scene_manifest
    loc_refs = []
    is_broll = shot.get("is_broll") or shot.get("_broll") or shot_type in ("b-roll", "b_roll", "insert", "detail")
    is_exterior = "ext" in (shot.get("location") or "").upper()[:5]
    is_establishing = shot_type in ("establishing", "master")

    # V27.1: DP Framing Standards — select best location ref type for shot type
    preferred_loc_type = None
    if _DP_FRAMING_AVAILABLE:
        dp_prefs = SHOT_TYPE_REF_MAP.get(shot_type, {})
        preferred_loc_type = dp_prefs.get("loc_ref")
        if preferred_loc_type and preferred_loc_type == "reverse_angle":
            logger.debug(f"[DP FRAMING] {shot_type} shot → looking for reverse_angle location ref")

    if location_masters:
        # Build sub-location from scene_manifest time_of_day field
        # e.g., scene_manifest time_of_day="GRAND FOYER - MORNING" → sub_location="GRAND FOYER"
        sub_location = ""
        scene_id = shot.get("scene_id") or (shot.get("shot_id", "")[:3] if shot.get("shot_id") else "")
        if scene_manifest and isinstance(scene_manifest, (list, dict)):
            manifest_list = scene_manifest if isinstance(scene_manifest, list) else scene_manifest.values()
            for entry in manifest_list:
                if not isinstance(entry, dict):
                    continue
                if entry.get("scene_id") == scene_id:
                    tod = (entry.get("time_of_day") or "").strip().upper()
                    # Extract sub-location: "GRAND FOYER - MORNING" → "GRAND FOYER"
                    if " - " in tod:
                        sub_location = tod.split(" - ")[0].strip()
                    break

        # V27.5.1: Fallback — resolve sub-location from story_bible when scene_manifest empty
        # ROOT CAUSE FIX: shot location="HARGROVE ESTATE" has no room specifier.
        # Story bible has "HARGROVE ESTATE - LIBRARY". Without this, FRONT_DRIVE wins by iteration order.
        if not sub_location and story_bible:
            sb_scenes = story_bible.get("scenes", [])
            if isinstance(sb_scenes, list):
                for sb_sc in sb_scenes:
                    if isinstance(sb_sc, dict) and sb_sc.get("scene_id") == scene_id:
                        sb_loc = (sb_sc.get("location") or "").strip().upper()
                        # Extract room from "HARGROVE ESTATE - LIBRARY" → "LIBRARY"
                        if " - " in sb_loc:
                            sub_location = sb_loc.split(" - ", 1)[1].strip()
                            logger.info(f"[V27.5.1 ROOM-LOCK] Scene {scene_id}: resolved room '{sub_location}' from story_bible")
                        break

        # Normalize helper: replace spaces with underscores for comparison
        def _norm(s):
            return s.replace(" ", "_").replace("-", "_").strip("_").upper()

        location = (shot.get("location") or "").strip().upper()
        location_norm = _norm(location)
        sub_norm = _norm(sub_location) if sub_location else ""

        # Try matching with sub-location first (most specific), then base location
        # V27.1: DP Framing — prefer reverse_angle for OTS shots
        matched_path = None
        best_score = 0
        for loc_key, loc_path in location_masters.items():
            loc_key_norm = _norm(loc_key)
            score = 0

            # V27.1: Check if this is the preferred location type (e.g., reverse_angle for OTS)
            type_bonus = 0
            if preferred_loc_type and preferred_loc_type.lower() in loc_key_norm.lower():
                type_bonus = 10  # Strongly prefer matched type
                logger.debug(f"[DP FRAMING] Found {preferred_loc_type} ref: {loc_key}")

            # Exact sub-location match: "GRAND_FOYER" in "HARGROVE_ESTATE___GRAND_FOYER"
            if sub_norm and sub_norm in loc_key_norm:
                score = 3  # Best: specific room match
            # Base location match: "HARGROVE_ESTATE" in "HARGROVE_ESTATE___GRAND_FOYER"
            elif location_norm and (location_norm in loc_key_norm or loc_key_norm in location_norm):
                score = 1  # Fallback: estate-level match

            score += type_bonus

            if score > best_score:
                # Verify file exists before accepting
                real_path = loc_path
                if "path=" in str(loc_path):
                    real_path = str(loc_path).split("path=")[-1]
                if Path(real_path).exists():
                    matched_path = real_path
                    best_score = score
                    if score >= 13:  # Sub-location match + type match is definitive
                        break

        if matched_path:
            loc_refs.append(matched_path)
        elif not is_exterior and not is_establishing and location_masters:
            # Last resort: any location master is better than none for interior shots
            for loc_key, loc_path in location_masters.items():
                real_path = str(loc_path).split("path=")[-1] if "path=" in str(loc_path) else loc_path
                if Path(real_path).exists():
                    loc_refs.append(real_path)
                    warnings.append(f"Location master fallback: no match for '{location}' (sub: '{sub_location}'), using {loc_key}")
                    break

    all_refs = char_refs + loc_refs

    return RefResolution(
        character_refs=char_refs,
        location_refs=loc_refs,
        all_refs=all_refs,
        primary_character=primary or "",
        ref_warnings=warnings,
    )


# ============================================================================
# VALIDATION GATES
# ============================================================================

def validate_speaker_attribution(shot: dict, speaker: Optional[SpeakerAttribution]) -> ValidationResult:
    """Check that dialogue shots have proper speaker attribution."""
    dialogue = shot.get("dialogue_text", "") or ""
    if not dialogue:
        return ValidationResult("speaker_attribution", True, "info", "No dialogue — skipped")

    if not speaker:
        return ValidationResult("speaker_attribution", False, "blocking",
                                f"Shot {shot.get('shot_id')} has dialogue but no speaker attribution")

    # Check speaker is in characters[]
    characters = [c.upper() for c in (shot.get("characters") or [])]
    if speaker.speaker not in characters:
        return ValidationResult("speaker_attribution", False, "blocking",
                                f"Speaker {speaker.speaker} not in characters {characters}")

    return ValidationResult("speaker_attribution", True, "info",
                            f"Speaker: {speaker.speaker}, Listeners: {speaker.listeners}")


def validate_character_count(shot: dict, coverage: CoverageAssignment) -> ValidationResult:
    """Check that expected character count matches shot plan."""
    characters = shot.get("characters", [])
    if isinstance(characters, str):
        characters = [c.strip() for c in characters.split(",") if c.strip()]

    actual = len(characters)
    expected = coverage.expected_chars

    if expected == 0:
        return ValidationResult("character_count", True, "info", "B-roll/no-char shot")

    if actual < expected:
        return ValidationResult("character_count", False, "blocking",
                                f"Expected {expected} chars but only {actual} in characters[]: {characters}")

    if actual == 0 and (shot.get("dialogue_text") or ""):
        return ValidationResult("character_count", False, "blocking",
                                f"Dialogue exists but characters[] is empty")

    return ValidationResult("character_count", True, "info",
                            f"Character count OK: {actual} (expected {expected})")


def validate_eyeline(shot: dict, speaker: Optional[SpeakerAttribution]) -> ValidationResult:
    """Check that eyeline direction is specified and not into camera."""
    if not speaker or not shot.get("dialogue_text"):
        return ValidationResult("eyeline", True, "info", "Non-dialogue — skipped")

    nano = (shot.get("nano_prompt") or "").lower()

    # Check for direct-to-camera indicators (BAD for dialogue)
    camera_gaze_patterns = [
        "looking directly into camera",
        "looks into camera",
        "staring at camera",
        "facing camera directly",
        "eyes to camera",
    ]
    for pattern in camera_gaze_patterns:
        if pattern in nano:
            return ValidationResult("eyeline", False, "warning",
                                    f"Dialogue shot has camera-gaze text: '{pattern}'")

    # Check that eyeline direction exists in prompt
    eyeline_patterns = [
        "eyeline", "eye-line", "looking at", "looks toward",
        "gaze", "facing", "turned toward", "eyes on",
    ]
    has_eyeline = any(p in nano for p in eyeline_patterns)

    if not has_eyeline and len(shot.get("characters", [])) >= 2:
        return ValidationResult("eyeline", False, "warning",
                                "Multi-character dialogue shot missing eyeline direction in nano_prompt")

    return ValidationResult("eyeline", True, "info",
                            f"Eyeline: {speaker.eyeline_target}")


def validate_coverage_variety(scene_shots: List[dict]) -> List[ValidationResult]:
    """Check that a scene has proper coverage variety — not all same framing."""
    results = []

    # Check for duplicate framings in first 4 shots
    if len(scene_shots) >= 3:
        first_types = [s.get("shot_type", "") for s in scene_shots[:4]]
        if len(set(first_types)) == 1:
            results.append(ValidationResult(
                "coverage_variety", False, "warning",
                f"First {len(first_types)} shots all have same type: {first_types[0]}"))

    # Check for A/B/C coverage distribution
    roles = [s.get("coverage_role", "") for s in scene_shots if s.get("characters")]
    if roles:
        has_A = any("A_" in r for r in roles)
        has_B = any("B_" in r for r in roles)
        has_C = any("C_" in r for r in roles)
        if not has_A:
            results.append(ValidationResult(
                "coverage_variety", False, "warning",
                "Scene has no A_GEOGRAPHY (wide) anchor shot"))
        if not has_C and len(roles) > 3:
            results.append(ValidationResult(
                "coverage_variety", False, "warning",
                "Scene with >3 character shots has no C_EMOTION (close) shot"))

    # Check for B-roll differentiation
    broll_shots = [s for s in scene_shots if s.get("is_broll") or s.get("_broll") or
                   (s.get("shot_type") or "").lower() in ("b-roll", "b_roll", "insert", "detail")]
    if len(broll_shots) >= 2:
        nano_hashes = []
        for br in broll_shots:
            # Hash the core visual description (strip common prefixes)
            nano = (br.get("nano_prompt") or "")
            # Remove location prefix and composition prefix
            core = re.sub(r'^.*?composition:\s*\w+[^,]*,\s*', '', nano, count=1)
            core = re.sub(r'^at\s+\w.*?,\s*', '', core, count=1)
            h = hashlib.md5(core[:100].encode()).hexdigest()[:8]
            nano_hashes.append((br.get("shot_id"), h, core[:60]))

        # Check for duplicates — WARNING not blocking (B-roll variety is advisory)
        seen = {}
        for sid, h, preview in nano_hashes:
            if h in seen:
                results.append(ValidationResult(
                    "coverage_variety", False, "warning",
                    f"B-roll {sid} has near-identical prompt to {seen[h]}: '{preview}...'"))
            seen[h] = sid

    if not results:
        results.append(ValidationResult("coverage_variety", True, "info", "Coverage variety OK"))

    return results


def validate_dialogue_ltx(shot: dict, speaker: Optional[SpeakerAttribution]) -> ValidationResult:
    """
    Check that LTX prompt has the CORRECT speaker marked.
    This catches the V26.2 failure where enforcement agent put Thomas as speaker
    when Eleanor was actually speaking.
    """
    ltx = (shot.get("ltx_motion_prompt") or "")
    dialogue = shot.get("dialogue_text", "") or ""

    if not dialogue:
        return ValidationResult("dialogue_ltx", True, "info", "No dialogue — skipped")

    if not speaker:
        return ValidationResult("dialogue_ltx", False, "warning", "Has dialogue but no speaker attribution")

    # Check that LTX mentions the CORRECT speaker
    if "speaks" in ltx.lower():
        ltx_upper = ltx.upper()
        actual_speaker = speaker.speaker.upper()

        # Check if the WRONG character is marked as speaking
        # Patterns to detect: "CHAR speaks:", "CHAR delivers line", "speaks: CHAR"
        characters = [c.upper() for c in (shot.get("characters") or [])]
        for char in characters:
            if char != actual_speaker and char in ltx_upper:
                # Multiple detection patterns for wrong speaker
                wrong_patterns = [
                    rf'{re.escape(char)}.*?SPEAKS',           # "THOMAS BLACKWOOD ... SPEAKS"
                    rf'SPEAKS:\s*{re.escape(char)}',          # "SPEAKS: THOMAS BLACKWOOD"
                    rf'{re.escape(char)}\s+DELIVERS',         # "THOMAS BLACKWOOD DELIVERS"
                    rf'{re.escape(char)}\s+PRESENT\s+AND',    # "THOMAS BLACKWOOD PRESENT AND GROUNDED"
                ]
                for wp in wrong_patterns:
                    if re.search(wp, ltx_upper):
                        # Also verify the actual speaker is NOT the one marked
                        actual_patterns = [
                            rf'{re.escape(actual_speaker)}.*?SPEAKS',
                            rf'SPEAKS:\s*{re.escape(actual_speaker)}',
                        ]
                        actual_marked = any(re.search(ap, ltx_upper) for ap in actual_patterns)
                        if not actual_marked:
                            return ValidationResult("dialogue_ltx", False, "blocking",
                                                    f"LTX says {char} speaks, but dialogue says {actual_speaker} speaks. "
                                                    f"WRONG CHARACTER SPEAKING.")

    # Check that "character speaks:" exists at all for dialogue shots
    if "speaks:" not in ltx.lower():
        return ValidationResult("dialogue_ltx", False, "warning",
                                f"Dialogue shot missing 'speaks:' marker in LTX")

    return ValidationResult("dialogue_ltx", True, "info",
                            f"LTX correctly attributes speech to {speaker.speaker}")


def validate_no_generic_prompt(shot: dict) -> ValidationResult:
    """Check that prompts aren't generic/template garbage."""
    try:
        from tools.creative_prompt_compiler import is_prompt_generic
        nano = shot.get("nano_prompt", "") or ""
        ltx = shot.get("ltx_motion_prompt", "") or ""

        if is_prompt_generic(nano):
            return ValidationResult("generic_check", False, "warning",
                                    f"Nano prompt is generic (CPC flagged)")
        if is_prompt_generic(ltx):
            return ValidationResult("generic_check", False, "warning",
                                    f"LTX prompt is generic (CPC flagged)")
    except ImportError:
        pass

    # Manual check for known enforcement agent garbage
    garbage_patterns = [
        "present and grounded in the physical space",
        "experiences the moment",
        "natural movement begins",
        "delivers line with conviction",  # Generic — doesn't say WHICH line
    ]
    ltx = (shot.get("ltx_motion_prompt") or "").lower()
    for pattern in garbage_patterns:
        if pattern in ltx:
            return ValidationResult("generic_check", False, "warning",
                                    f"LTX contains enforcement agent generic: '{pattern}'")

    return ValidationResult("generic_check", True, "info", "Prompts pass generic check")


# ============================================================================
# PROMPT COMPILATION (Speaker + Eyeline + Isolation injection)
# ============================================================================

def compile_prompt_with_intelligence(
    shot: dict,
    speaker: Optional[SpeakerAttribution],
    coverage: CoverageAssignment,
    refs: RefResolution,
) -> Tuple[str, str]:
    """
    Take the existing nano and LTX prompts and ENHANCE them with:
    - Correct speaker attribution in LTX
    - Eyeline direction
    - Character isolation for single-char shots
    - Coverage framing notes

    This does NOT overwrite hand-crafted prompts — it ADDS missing intelligence.
    """
    nano = shot.get("nano_prompt", "") or ""
    ltx = shot.get("ltx_motion_prompt", "") or ""
    characters = shot.get("characters", [])
    if isinstance(characters, str):
        characters = [c.strip() for c in characters.split(",") if c.strip()]

    # === NANO PROMPT ENHANCEMENTS ===

    # Add isolation negative for single-character shots
    if coverage.isolation_negative and coverage.isolation_negative not in nano:
        nano = nano.rstrip(". ") + ". " + coverage.isolation_negative + "."

    # Add eyeline direction if missing and speaker exists
    if speaker and speaker.eyeline_target != "camera":
        eyeline_text = ""
        if speaker.eyeline_target == "partner" and speaker.listeners:
            eyeline_text = f"eyeline toward {speaker.listeners[0]}"
        elif speaker.eyeline_target == "off-screen-right":
            eyeline_text = "eyeline directed off-screen right, NOT looking at camera"
        elif speaker.eyeline_target == "off-screen-left":
            eyeline_text = "eyeline directed off-screen left, NOT looking at camera"

        if eyeline_text and eyeline_text.lower() not in nano.lower():
            nano = nano.rstrip(". ") + ". " + eyeline_text + "."

    # Add "NOT looking directly into camera" for ALL dialogue shots
    if speaker and "not looking" not in nano.lower() and "off-axis" not in nano.lower():
        nano = nano.rstrip(". ") + ". Subject NOT looking directly into camera lens."

    # === LTX PROMPT ENHANCEMENTS ===

    # Fix speaker attribution — ensure CORRECT character is marked as speaking
    if speaker and not speaker.is_reaction:
        # Check if LTX has wrong speaker
        ltx_has_wrong_speaker = False
        for char in characters:
            char_upper = char.upper()
            if char_upper != speaker.speaker and f"{char_upper}" in ltx.upper():
                if "speaks" in ltx.lower() or "delivers" in ltx.lower():
                    ltx_has_wrong_speaker = True
                    break

        if ltx_has_wrong_speaker or "speaks:" not in ltx.lower():
            # Strip any existing generic speaker markers
            ltx = re.sub(r'\w+ present and grounded[^,]*,?\s*', '', ltx)
            ltx = re.sub(r'character speaks:\s*\w+ delivers line with conviction,?\s*', '', ltx)

            # Inject correct speaker
            speaker_line = speaker.dialogue_text.split("|")[0].strip()
            if ":" in speaker_line:
                speaker_line = speaker_line.split(":", 1)[1].strip()
            speaker_injection = f"character speaks: {speaker.speaker} says \"{speaker_line[:80]}\""

            # Prepend to LTX
            ltx = speaker_injection + ", " + ltx.lstrip(", ")

    # For reaction shots, mark the listener
    if speaker and speaker.is_reaction and speaker.listeners:
        if "reacts" not in ltx.lower() and "listens" not in ltx.lower():
            reactor = speaker.listeners[0] if speaker.listeners else characters[0]
            ltx = f"character performs: {reactor} listens and reacts, " + ltx.lstrip(", ")

    # Ensure gold standard exists
    if characters and "NO morphing" not in ltx:
        ltx = ltx.rstrip(". ") + ", face stable NO morphing, character consistent"

    # Ensure duration marker exists
    duration = shot.get("duration", 6)
    if not any(f"{d}s" in ltx for d in range(1, 121)):
        ltx = ltx.rstrip(", ") + f", {duration}s"

    return nano, ltx


# ============================================================================
# SCENE CONTROLLER (THE UNIFIED EXECUTIVE)
# ============================================================================

class SceneController:
    """
    The spinal cord. Coordinates all brain modules for scene generation.

    Replaces the old pipeline:
      enforcement_agent → enrichment → cast_trait_injection → FAL

    With:
      SceneController.prepare_scene() → List[PreparedShot] → FAL
    """

    def __init__(
        self,
        project_path: str,
        cast_map: dict,
        story_bible: dict = None,
        scene_manifest: dict = None,
        location_masters: dict = None,
    ):
        self.project_path = project_path
        self.cast_map = cast_map or {}
        self.story_bible = story_bible or {}
        self.scene_manifest = scene_manifest or {}
        self.location_masters = location_masters or {}

        # Try to load brain modules (all non-blocking)
        self.meta_director = None
        self.continuity_memory = None
        self.film_engine_available = False
        self.editorial_available = False
        self.cpc_available = False

        try:
            from tools.meta_director import MetaDirector
            self.meta_director = MetaDirector(project_path)
        except Exception as e:
            logger.warning(f"[CONTROLLER] MetaDirector not available: {e}")

        try:
            from tools.continuity_memory import ContinuityMemory
            self.continuity_memory = ContinuityMemory(project_path)
        except Exception as e:
            logger.warning(f"[CONTROLLER] ContinuityMemory not available: {e}")

        try:
            from tools.film_engine import compile_shot_for_model
            self.film_engine_available = True
        except ImportError:
            logger.warning("[CONTROLLER] Film Engine not available")

        try:
            from tools.editorial_intelligence import build_editorial_plan
            self.editorial_available = True
        except ImportError:
            logger.warning("[CONTROLLER] Editorial Intelligence not available")

        try:
            from tools.creative_prompt_compiler import is_prompt_generic
            self.cpc_available = True
        except ImportError:
            logger.warning("[CONTROLLER] Creative Prompt Compiler not available")

    def prepare_scene(self, scene_id: str, shots: List[dict]) -> List[PreparedShot]:
        """
        THE MAIN ENTRY POINT.

        Takes raw shots from shot_plan.json and returns PreparedShot objects
        with all intelligence applied and all validations run.

        Phases:
        1. Scene-level planning (coverage map, speaker map)
        2. Per-shot compilation (speaker, eyeline, coverage, refs)
        3. Validation (all gates)
        4. Authority contract (resolution, ref cap)
        """
        scene_shots = [s for s in shots if s.get("scene_id") == scene_id]
        scene_shots.sort(key=lambda s: s.get("shot_id", ""))

        if not scene_shots:
            logger.warning(f"[CONTROLLER] No shots found for scene {scene_id}")
            return []

        logger.info(f"[CONTROLLER] Preparing scene {scene_id}: {len(scene_shots)} shots")

        # Phase 1: Scene-level analysis
        scene_context = {}
        if self.meta_director:
            try:
                scene_context = self.meta_director.prepare_scene_context(scene_id)
            except Exception as e:
                logger.warning(f"[CONTROLLER] MetaDirector context failed: {e}")

        # Editorial plan (non-blocking)
        editorial_plan = None
        if self.editorial_available:
            try:
                from tools.editorial_intelligence import build_editorial_plan
                editorial_plan = build_editorial_plan(scene_shots, scene_id)
            except Exception as e:
                logger.warning(f"[CONTROLLER] Editorial plan failed: {e}")

        # Scene-level coverage validation
        coverage_validations = validate_coverage_variety(scene_shots)

        # Phase 2-4: Per-shot preparation
        prepared_shots = []

        for idx, shot in enumerate(scene_shots):
            prepared = self._prepare_shot(shot, scene_shots, idx, scene_context)
            prepared_shots.append(prepared)

        # Attach scene-level validations to first shot
        if prepared_shots:
            prepared_shots[0].validations.extend(coverage_validations)

        # Log summary
        blocking = sum(1 for ps in prepared_shots if not ps.is_ready)
        warnings = sum(1 for ps in prepared_shots
                       for v in ps.validations if not v.passed and v.severity == "warning")
        logger.info(f"[CONTROLLER] Scene {scene_id} prepared: "
                     f"{len(prepared_shots)} shots, {blocking} blocking, {warnings} warnings")

        return prepared_shots

    def _prepare_shot(
        self, shot: dict, scene_shots: List[dict], shot_index: int, scene_context: dict
    ) -> PreparedShot:
        """Prepare a single shot with full intelligence."""
        shot_id = shot.get("shot_id", f"unknown_{shot_index}")

        # Step 1: Speaker attribution
        speaker = attribute_speaker(shot, scene_shots)

        # Step 2: Coverage assignment
        coverage = assign_coverage(shot, scene_shots, shot_index)

        # Step 3: Reference resolution
        refs = resolve_refs(shot, self.cast_map, self.location_masters, self.project_path,
                            scene_manifest=self.scene_manifest,
                            story_bible=self.story_bible)

        # Step 4: Compile prompts with intelligence
        nano, ltx = compile_prompt_with_intelligence(shot, speaker, coverage, refs)

        # Step 5: Validations
        validations = []
        validations.append(validate_speaker_attribution(shot, speaker))
        validations.append(validate_character_count(shot, coverage))
        validations.append(validate_eyeline(shot, speaker))
        validations.append(validate_dialogue_ltx(
            {**shot, "ltx_motion_prompt": ltx},  # Validate the COMPILED ltx
            speaker
        ))
        validations.append(validate_no_generic_prompt(
            {**shot, "nano_prompt": nano, "ltx_motion_prompt": ltx}
        ))

        # Step 6: Shot Authority
        authority_tier = "production"
        resolution = "1K"
        try:
            from tools.shot_authority import build_shot_contract
            contract = build_shot_contract(shot, self.cast_map, refs.all_refs)
            authority_tier = contract.profile.quality_tier
            resolution = contract.profile.resolution
        except Exception:
            # Fallback authority based on shot type
            shot_type = (shot.get("shot_type") or "").lower()
            if shot_type in ("close_up", "medium_close", "ecu", "mcu", "reaction"):
                authority_tier = "hero"
                resolution = "2K"
            if shot.get("dialogue_text"):
                resolution = "2K"  # Dialogue always 2K minimum

        # Determine chain candidacy
        shot_type = (shot.get("shot_type") or "").lower()
        is_broll = (shot.get("is_broll") or shot.get("_broll") or
                    shot_type in ("b-roll", "b_roll", "insert", "detail", "cutaway"))
        is_chain = (not is_broll and
                    len(shot.get("characters", [])) > 0 and
                    shot_type not in ("establishing", "master"))

        # Build FAL params
        fal_params = {
            "aspect_ratio": "16:9",
            "resolution": resolution,
            "output_format": "jpeg",
        }
        if refs.all_refs:
            fal_params["num_outputs"] = 1
        else:
            fal_params["num_images"] = 1

        duration = shot.get("duration", 6)

        return PreparedShot(
            shot_id=shot_id,
            scene_id=shot.get("scene_id", ""),
            nano_prompt=nano,
            ltx_prompt=ltx,
            ref_urls=refs.all_refs,
            fal_params=fal_params,
            speaker=speaker,
            coverage=coverage,
            refs=refs,
            validations=validations,
            authority_tier=authority_tier,
            resolution=resolution,
            duration=duration,
            characters=shot.get("characters", []),
            dialogue_text=shot.get("dialogue_text", "") or "",
            shot_type=shot_type,
            is_broll=is_broll,
            is_chain_candidate=is_chain,
        )

    def get_scene_report(self, prepared_shots: List[PreparedShot]) -> Dict:
        """Generate a human-readable scene preparation report."""
        report = {
            "total_shots": len(prepared_shots),
            "ready": sum(1 for ps in prepared_shots if ps.is_ready),
            "blocking": sum(1 for ps in prepared_shots if not ps.is_ready),
            "warnings": 0,
            "coverage_map": {},
            "speaker_map": {},
            "ref_map": {},
            "shots": [],
        }

        for ps in prepared_shots:
            shot_report = {
                "shot_id": ps.shot_id,
                "ready": ps.is_ready,
                "coverage": ps.coverage.role,
                "speaker": ps.speaker.speaker if ps.speaker else None,
                "listeners": ps.speaker.listeners if ps.speaker else [],
                "eyeline": ps.speaker.eyeline_target if ps.speaker else None,
                "char_refs": len(ps.refs.character_refs),
                "expected_chars": ps.coverage.expected_chars,
                "authority": ps.authority_tier,
                "resolution": ps.resolution,
                "validations": [],
            }

            for v in ps.validations:
                if not v.passed:
                    report["warnings"] += 1
                    shot_report["validations"].append({
                        "check": v.check,
                        "severity": v.severity,
                        "message": v.message,
                    })

            report["shots"].append(shot_report)

            # Coverage map
            role = ps.coverage.role
            report["coverage_map"][role] = report["coverage_map"].get(role, 0) + 1

            # Speaker map
            if ps.speaker:
                spk = ps.speaker.speaker
                report["speaker_map"][spk] = report["speaker_map"].get(spk, 0) + 1

        return report
