"""
CREATION PACK VALIDATOR — V27.1
================================
Universal pre-generation quality gate for character and location references.
Runs BEFORE any scene generation to ensure the ref pack is production-ready.

This is NOT a one-time audit. This runs automatically as a BLOCKING gate
in the generation pipeline. If the creation pack fails, generation halts
with actionable diagnostics — not silent degradation.

Architecture:
  - Character Ref Pack: multi-angle coverage per character
  - Location Ref Pack: multi-angle coverage per location
  - Shot-to-Ref Mapping: DP-standard best-fit selection per shot type
  - Probe Shot System: single-shot canary before full scene render

Universal: Works for ANY script/story, not project-specific.
"""

import json
import os
import re
import logging
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime

logger = logging.getLogger("creation_pack")


def _extract_appearance_keywords(appearance: str) -> List[str]:
    """
    Extract meaningful visual keywords from an appearance description.
    Used to verify that a reference image was generated FROM the canonical description.

    Example: "woman, 34, auburn hair pulled back severely, charcoal blazer over black turtleneck"
    → ["auburn", "hair", "pulled back", "charcoal", "blazer", "black", "turtleneck"]
    """
    # Remove common filler words
    fillers = {"a", "an", "the", "of", "in", "with", "and", "or", "her", "his",
               "their", "very", "quite", "somewhat", "slightly", "that", "this",
               "is", "are", "was", "were", "has", "have", "man", "woman", "person"}

    # Split on commas and spaces, keep multi-word descriptors
    words = []
    for segment in appearance.lower().split(","):
        segment = segment.strip()
        # Keep multi-word phrases like "pulled back" or "dark brown"
        tokens = segment.split()
        for token in tokens:
            cleaned = re.sub(r'[^a-z]', '', token)
            if cleaned and cleaned not in fillers and len(cleaned) > 2:
                words.append(cleaned)

    return words


# =============================================================================
# DP FRAMING STANDARDS — Hollywood cinematography ref requirements
# =============================================================================

# What type of character reference works best for each shot type
# Key insight: FAL weights reference images heavily. If you send a headshot
# for a wide shot, the AI over-focuses on face at the expense of environment.
# If you send a full-body for a close-up, you get lower facial fidelity.

SHOT_TYPE_REF_MAP = {
    # Shot type → (ideal_char_ref_type, ideal_loc_ref_type, notes)
    "establishing": {
        "char_ref": None,  # No character ref for establishing — environment only
        "loc_ref": "wide_exterior",
        "notes": "Environment-only. No characters in ref. Location master wide angle.",
    },
    "b-roll": {
        "char_ref": None,
        "loc_ref": "detail_insert",
        "notes": "Contextual B-roll. Detail inserts, props, atmosphere. NOT empty rooms.",
    },
    "wide": {
        "char_ref": "full_body",
        "loc_ref": "wide_interior",
        "notes": "Full geography. Character in environment. Full body ref preferred.",
    },
    "two_shot": {
        "char_ref": "three_quarter",
        "loc_ref": "wide_interior",
        "notes": "Two characters in frame. 3/4 refs for both. Wide location context.",
    },
    "medium": {
        "char_ref": "three_quarter",
        "loc_ref": "medium_interior",
        "notes": "Waist-up framing. 3/4 character ref optimal.",
    },
    "medium_close": {
        "char_ref": "headshot",
        "loc_ref": "medium_interior",
        "notes": "Chest-up. Headshot ref for facial fidelity.",
    },
    "close_up": {
        "char_ref": "headshot",
        "loc_ref": None,  # Close-ups don't need location ref
        "notes": "Face only. Headshot ref mandatory. No location needed.",
    },
    "extreme_close_up": {
        "char_ref": "headshot",
        "loc_ref": None,
        "notes": "Detail on eyes/hands. Highest fidelity headshot.",
    },
    "over_the_shoulder": {
        "char_ref": "three_quarter",
        "loc_ref": "reverse_angle",
        "notes": "OTS needs BOTH characters + reverse angle of room.",
    },
    "reaction": {
        "char_ref": "headshot",
        "loc_ref": None,
        "notes": "Facial reaction. Headshot ref for maximum expression fidelity.",
    },
    "closing": {
        "char_ref": "full_body",
        "loc_ref": "wide_interior",
        "notes": "Scene closing. Full body + environment for exit framing.",
    },
    "insert": {
        "char_ref": None,
        "loc_ref": "detail_insert",
        "notes": "Prop/detail insert. Location detail ref, no character.",
    },
}

# Character ref types needed for complete coverage
CHARACTER_REF_TYPES = {
    "headshot": {
        "description": "Front-facing, shoulders up, neutral expression, plain background",
        "use_for": ["close_up", "extreme_close_up", "medium_close", "reaction"],
        "priority": 1,  # MUST HAVE — identity anchor
    },
    "three_quarter": {
        "description": "3/4 angle, waist up, slight body angle, character wardrobe visible",
        "use_for": ["medium", "over_the_shoulder", "two_shot"],
        "priority": 2,  # SHOULD HAVE — most versatile
    },
    "full_body": {
        "description": "Full standing pose, character in wardrobe, posture visible",
        "use_for": ["wide", "establishing", "closing"],
        "priority": 3,  # NICE TO HAVE — wide shots
    },
    "profile": {
        "description": "Side profile, 90 degree angle, for OTS reverse shots",
        "use_for": ["over_the_shoulder"],
        "priority": 4,  # OPTIONAL — OTS improvement
    },
}

# Location ref types needed for complete coverage
LOCATION_REF_TYPES = {
    "wide_exterior": {
        "description": "Exterior establishing wide shot of the location",
        "use_for": ["establishing"],
        "priority": 1,
    },
    "wide_interior": {
        "description": "Interior wide shot showing full room geography",
        "use_for": ["wide", "two_shot", "closing"],
        "priority": 1,
    },
    "reverse_angle": {
        "description": "180-degree reverse of wide interior — the OTHER side of the room",
        "use_for": ["over_the_shoulder", "reaction"],
        "priority": 2,
    },
    "medium_interior": {
        "description": "Medium framing of key area within location (desk, fireplace, window)",
        "use_for": ["medium", "medium_close"],
        "priority": 2,
    },
    "detail_insert": {
        "description": "Close-up detail shots — props, textures, atmospheric elements",
        "use_for": ["b-roll", "insert"],
        "priority": 3,
    },
}


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class CharacterPackStatus:
    """Validation status for a single character's reference pack."""
    character_name: str
    appearance_description: str = ""
    refs_available: Dict[str, str] = field(default_factory=dict)  # type → file path
    refs_missing: List[str] = field(default_factory=list)
    description_match: str = "UNKNOWN"  # PASS / WEAK / FAIL
    description_issues: List[str] = field(default_factory=list)
    is_production_ready: bool = False
    minimum_viable: bool = False  # At least has headshot that matches description


@dataclass
class LocationPackStatus:
    """Validation status for a single location's reference pack."""
    location_name: str
    location_description: str = ""
    refs_available: Dict[str, str] = field(default_factory=dict)  # type → file path
    refs_missing: List[str] = field(default_factory=list)
    scenes_using: List[str] = field(default_factory=list)
    is_production_ready: bool = False
    minimum_viable: bool = False  # At least has one usable master


@dataclass
class CreationPackReport:
    """Full creation pack validation report for a project."""
    project: str
    timestamp: str = ""
    characters: Dict[str, CharacterPackStatus] = field(default_factory=dict)
    locations: Dict[str, LocationPackStatus] = field(default_factory=dict)
    scene_coverage: Dict[str, Dict] = field(default_factory=dict)  # scene_id → coverage gaps
    is_production_ready: bool = False
    blocking_issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    recommended_generations: List[Dict] = field(default_factory=list)  # What to generate to fix gaps

    def to_dict(self):
        return asdict(self)


# =============================================================================
# PROBE SHOT SYSTEM
# =============================================================================

@dataclass
class ProbeResult:
    """Result from running a single probe shot through the pipeline."""
    shot_id: str
    scene_id: str
    status: str  # PASS / WARN / FAIL
    ref_resolution: Dict = field(default_factory=dict)
    doctrine_verdict: Dict = field(default_factory=dict)
    vision_analysis: Dict = field(default_factory=dict)
    issues_found: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    elapsed_ms: float = 0
    can_proceed_to_full_scene: bool = False


def select_probe_shot(shots: List[dict], scene_id: str) -> Optional[dict]:
    """
    Select the best single shot to use as a probe/canary for a scene.

    Strategy: Pick the HARDEST shot in the scene — if it passes, everything easier will too.
    Priority order:
      1. First dialogue shot with 2+ characters (OTS/two-shot) — tests identity, dialogue, chaining
      2. First dialogue shot with 1 character — tests identity + dialogue
      3. First character shot without dialogue — tests identity
      4. First B-roll — tests location ref
    """
    scene_shots = [s for s in shots if s.get("scene_id") == scene_id]
    if not scene_shots:
        return None

    # Category buckets
    multi_char_dialogue = []
    single_char_dialogue = []
    char_no_dialogue = []
    broll = []

    for s in scene_shots:
        chars = s.get("characters", [])
        has_dial = bool(s.get("dialogue_text", ""))
        is_br = s.get("is_broll") or s.get("_broll") or (s.get("shot_type", "") in ("b-roll", "b_roll"))

        if is_br or not chars:
            broll.append(s)
        elif has_dial and len(chars) >= 2:
            multi_char_dialogue.append(s)
        elif has_dial:
            single_char_dialogue.append(s)
        else:
            char_no_dialogue.append(s)

    # Return hardest available
    if multi_char_dialogue:
        return multi_char_dialogue[0]
    if single_char_dialogue:
        return single_char_dialogue[0]
    if char_no_dialogue:
        return char_no_dialogue[0]
    if broll:
        return broll[0]
    return scene_shots[0]


def analyze_probe_result(result: dict) -> ProbeResult:
    """
    Analyze the API response from a single probe shot generation.
    Extracts actionable diagnostics before committing to full scene render.
    """
    shot_id = result.get("shot_id", "unknown")
    scene_id = shot_id[:3] if len(shot_id) >= 3 else "unknown"

    issues = []
    recommendations = []
    status = "PASS"

    # Check doctrine verdict
    doctrine = result.get("doctrine_verdict", {})
    gates = doctrine.get("gates_checked", 0)
    phase_excs = doctrine.get("phase_exceptions", [])

    if gates == 0:
        issues.append("CRITICAL: Doctrine gates_checked=0 — feedback loop broken")
        status = "FAIL"
    if phase_excs:
        issues.append(f"Doctrine had {len(phase_excs)} phase exception(s): {phase_excs}")
        status = "WARN" if status != "FAIL" else status

    # Check vision analysis
    vision = result.get("vision_analyst", result.get("vision_badges", {}))
    if not vision:
        issues.append("Vision analysis empty — no quality scoring available")
        status = "WARN" if status != "FAIL" else status
    else:
        identity_score = vision.get("identity_score") or vision.get("face_similarity")
        if identity_score is not None and identity_score < 0.6:
            issues.append(f"Identity score {identity_score:.2f} below threshold — character ref may not match")
            status = "FAIL"
        location_score = vision.get("location_score") or vision.get("location_similarity")
        if location_score is not None and location_score < 0.5:
            issues.append(f"Location score {location_score:.2f} below threshold — environment drift")
            status = "WARN" if status != "FAIL" else status

    # Check ref resolution
    ref_data = result.get("ref_resolution", result.get("refs_used", {}))
    if isinstance(ref_data, dict):
        char_refs = ref_data.get("character_refs", [])
        loc_refs = ref_data.get("location_refs", [])
        warnings_list = ref_data.get("warnings", [])
        if warnings_list:
            issues.extend([f"Ref warning: {w}" for w in warnings_list])
        if not char_refs and result.get("characters"):
            issues.append("No character refs resolved despite characters in shot")
            status = "FAIL"

    # Check if frame was actually generated
    frame_url = result.get("first_frame_url") or result.get("frame_path")
    if not frame_url:
        issues.append("No frame generated — FAL call may have failed")
        status = "FAIL"

    can_proceed = status != "FAIL"
    if status == "WARN":
        recommendations.append("Probe passed with warnings — review before full scene")
    if status == "FAIL":
        recommendations.append("HALT: Fix issues before running full scene")

    return ProbeResult(
        shot_id=shot_id,
        scene_id=scene_id,
        status=status,
        doctrine_verdict=doctrine,
        vision_analysis=vision,
        issues_found=issues,
        recommendations=recommendations,
        can_proceed_to_full_scene=can_proceed,
    )


# =============================================================================
# CREATION PACK VALIDATOR — Universal for any script
# =============================================================================

def validate_creation_pack(
    project_path: str,
    shot_plan: dict,
    cast_map: dict,
    story_bible: dict = None,
) -> CreationPackReport:
    """
    Universal creation pack validation.

    Checks:
      1. Every character in cast_map has refs that match their description
      2. Every location used in the script has adequate angle coverage
      3. Every scene has the refs it needs for its shot types
      4. B-roll slots have narrative-appropriate ref targets (not empty rooms)

    Returns a CreationPackReport with blocking issues and generation recommendations.
    """
    report = CreationPackReport(
        project=os.path.basename(project_path),
        timestamp=datetime.utcnow().isoformat(),
    )

    pp = Path(project_path)
    shots = shot_plan.get("shots", [])

    # =========================================================================
    # 1. CHARACTER PACK VALIDATION
    # =========================================================================

    for char_name, char_data in cast_map.items():
        if not isinstance(char_data, dict) or char_data.get("_is_alias_of"):
            continue
        if char_name.startswith("_"):
            continue

        pack = CharacterPackStatus(
            character_name=char_name,
            appearance_description=char_data.get("appearance", ""),
        )

        # ---- DESCRIPTION-MATCH VALIDATION ----
        # Check if ref image was generated FROM the canonical appearance description
        # or if it's a stale AI actor headshot that doesn't match
        appearance = char_data.get("appearance", "")
        ref_gen_prompt = char_data.get("_reference_generation_prompt", "")
        ref_gen_at = char_data.get("_reference_generated_at", "")
        ref_validated = char_data.get("_reference_validated", False)

        if appearance and not ref_validated:
            # Check if the reference was generated with the canonical description
            # If no generation prompt recorded, or if it doesn't contain key appearance terms,
            # the ref is SUSPECT — it may be an auto-cast AI actor headshot
            appearance_keywords = _extract_appearance_keywords(appearance)
            if ref_gen_prompt:
                prompt_lower = ref_gen_prompt.lower()
                matched_kw = sum(1 for kw in appearance_keywords if kw in prompt_lower)
                match_ratio = matched_kw / len(appearance_keywords) if appearance_keywords else 0
                if match_ratio < 0.5:
                    pack.description_match = "FAIL"
                    pack.description_issues.append(
                        f"Ref generation prompt matches only {match_ratio:.0%} of appearance keywords"
                    )
                elif match_ratio < 0.8:
                    pack.description_match = "WEAK"
                    pack.description_issues.append(
                        f"Ref generation prompt partially matches ({match_ratio:.0%}) — review recommended"
                    )
                else:
                    pack.description_match = "PASS"
            else:
                # No generation prompt recorded — ref is from auto-cast, likely AI actor headshot
                pack.description_match = "UNVERIFIED"
                pack.description_issues.append(
                    "No _reference_generation_prompt recorded — ref may be stale AI actor headshot. "
                    "Run auto-recast to generate ref from canonical appearance description."
                )
                report.warnings.append(
                    f"CHARACTER {char_name}: Ref image has no generation provenance — "
                    f"may not match description: '{appearance[:80]}...'"
                )

        # Check what refs exist
        char_lib = pp / "character_library_locked"
        safe_name = char_name.replace(" ", "_").upper()

        # Look for multi-image pack structure
        ref_patterns = {
            "headshot": [
                f"{safe_name}_CHAR_REFERENCE.jpg",
                f"{safe_name}_headshot.jpg",
            ],
            "three_quarter": [
                f"{safe_name}_three_quarter.jpg",
                f"{safe_name}_3q.jpg",
                f"{safe_name}_medium.jpg",
            ],
            "full_body": [
                f"{safe_name}_full_body.jpg",
                f"{safe_name}_full.jpg",
                f"{safe_name}_wide.jpg",
            ],
            "profile": [
                f"{safe_name}_profile.jpg",
                f"{safe_name}_side.jpg",
            ],
        }

        for ref_type, patterns in ref_patterns.items():
            for pattern in patterns:
                candidate = char_lib / pattern
                if candidate.exists():
                    pack.refs_available[ref_type] = str(candidate)
                    break

        # Check minimum viable: headshot exists
        if "headshot" in pack.refs_available:
            pack.minimum_viable = True
        else:
            # Fall back: check if CHAR_REFERENCE.jpg exists (legacy single-ref)
            legacy = char_lib / f"{safe_name}_CHAR_REFERENCE.jpg"
            if legacy.exists():
                pack.refs_available["headshot"] = str(legacy)
                pack.minimum_viable = True
            else:
                pack.minimum_viable = False
                report.blocking_issues.append(
                    f"CHARACTER {char_name}: No headshot/CHAR_REFERENCE found — identity will be unanchored"
                )

        # Check what's missing
        for ref_type, ref_info in CHARACTER_REF_TYPES.items():
            if ref_type not in pack.refs_available:
                pack.refs_missing.append(ref_type)
                if ref_info["priority"] <= 2:
                    report.warnings.append(
                        f"CHARACTER {char_name}: Missing {ref_type} ref — degraded quality for {ref_info['use_for']}"
                    )

        # Full production ready = headshot + three_quarter minimum
        pack.is_production_ready = (
            "headshot" in pack.refs_available and
            "three_quarter" in pack.refs_available
        )

        report.characters[char_name] = pack

    # =========================================================================
    # 2. LOCATION PACK VALIDATION
    # =========================================================================

    # Discover all locations from story bible (most specific) or shot plan
    location_map = {}  # normalized_name → {description, scenes, sub_location}

    if story_bible:
        for scene in story_bible.get("scenes", []):
            loc = scene.get("location", "")
            sid = scene.get("scene_id", scene.get("id", ""))
            desc = scene.get("description", "")
            if loc:
                norm = loc.replace(" ", "_").replace("-", "_").upper()
                if norm not in location_map:
                    location_map[norm] = {"name": loc, "description": desc, "scenes": [], "sub_locations": set()}
                location_map[norm]["scenes"].append(str(sid))
                # Extract sub-location: "HARGROVE ESTATE - LIBRARY" → "LIBRARY"
                if " - " in loc:
                    sub = loc.split(" - ", 1)[1].strip()
                    location_map[norm]["sub_locations"].add(sub)

    # Also scan shot_plan for locations
    for shot in shots:
        loc = shot.get("location", "")
        sid = shot.get("scene_id", "")
        if loc:
            norm = loc.replace(" ", "_").replace("-", "_").upper()
            if norm not in location_map:
                location_map[norm] = {"name": loc, "description": "", "scenes": [], "sub_locations": set()}
            if str(sid) not in location_map[norm]["scenes"]:
                location_map[norm]["scenes"].append(str(sid))

    # Check location masters directory
    loc_masters_dir = pp / "location_masters"
    existing_masters = {}
    if loc_masters_dir.exists():
        for f in loc_masters_dir.iterdir():
            if f.suffix.lower() in (".jpg", ".jpeg", ".png"):
                existing_masters[f.stem.upper()] = str(f)

    # Validate each location
    for norm_name, loc_data in location_map.items():
        pack = LocationPackStatus(
            location_name=loc_data["name"],
            location_description=loc_data["description"],
            scenes_using=loc_data["scenes"],
        )

        # Check for existing masters matching this location
        for master_key, master_path in existing_masters.items():
            master_norm = master_key.replace(" ", "_").replace("-", "_").upper()
            # Check if this master belongs to this location
            # Handle both "HARGROVE_ESTATE___LIBRARY" and "HARGROVE_ESTATE_-_LIBRARY"
            base_loc = norm_name.split("___")[0].split("_-_")[0] if "___" in norm_name or "_-_" in norm_name else norm_name

            if base_loc in master_norm or master_norm in norm_name:
                # Classify the master type based on name
                ref_type = "wide_interior"  # default
                master_lower = master_key.lower()
                if any(ext in master_lower for ext in ["exterior", "front", "drive", "garden", "approach"]):
                    ref_type = "wide_exterior"
                elif any(rev in master_lower for rev in ["reverse", "back", "opposite"]):
                    ref_type = "reverse_angle"
                elif any(det in master_lower for det in ["detail", "insert", "close", "prop"]):
                    ref_type = "detail_insert"
                elif any(med in master_lower for med in ["medium", "mid"]):
                    ref_type = "medium_interior"

                pack.refs_available[ref_type] = master_path

        # What's missing
        for ref_type, ref_info in LOCATION_REF_TYPES.items():
            if ref_type not in pack.refs_available:
                pack.refs_missing.append(ref_type)
                if ref_info["priority"] == 1:
                    report.warnings.append(
                        f"LOCATION {loc_data['name']}: Missing {ref_type} — needed for {ref_info['use_for']}"
                    )

        pack.minimum_viable = len(pack.refs_available) >= 1
        pack.is_production_ready = (
            "wide_interior" in pack.refs_available and
            "reverse_angle" in pack.refs_available
        )

        if not pack.minimum_viable:
            report.blocking_issues.append(
                f"LOCATION {loc_data['name']}: No masters at all — scenes {loc_data['scenes']} will have no environment ref"
            )

        report.locations[norm_name] = pack

    # =========================================================================
    # 3. SCENE COVERAGE GAP ANALYSIS
    # =========================================================================

    from collections import defaultdict
    scene_groups = defaultdict(list)
    for shot in shots:
        scene_groups[shot.get("scene_id", "")].append(shot)

    for scene_id, scene_shots in scene_groups.items():
        coverage = {
            "shot_count": len(scene_shots),
            "needs_character_ref": False,
            "needs_location_ref": False,
            "needs_reverse_angle": False,
            "needs_narrative_broll": False,
            "gaps": [],
        }

        for shot in scene_shots:
            shot_type = (shot.get("shot_type") or "").lower()
            chars = shot.get("characters", [])
            is_br = shot.get("is_broll") or shot_type in ("b-roll", "b_roll")

            ref_spec = SHOT_TYPE_REF_MAP.get(shot_type, SHOT_TYPE_REF_MAP.get("medium"))
            if not ref_spec:
                continue

            # Character ref gap
            if ref_spec.get("char_ref") and chars:
                coverage["needs_character_ref"] = True
                for char in chars:
                    char_upper = char.upper()
                    char_pack = report.characters.get(char_upper)
                    if char_pack and not char_pack.minimum_viable:
                        coverage["gaps"].append(
                            f"{shot.get('shot_id')}: {char} has no viable ref for {shot_type}"
                        )

            # Location ref gap
            if ref_spec.get("loc_ref"):
                coverage["needs_location_ref"] = True
                if ref_spec["loc_ref"] == "reverse_angle":
                    coverage["needs_reverse_angle"] = True

            # B-roll narrative check
            if is_br:
                coverage["needs_narrative_broll"] = True
                desc = shot.get("description", "") or shot.get("_locked_nano_prompt", "")
                if not desc or "environmental detail only" in desc.lower():
                    coverage["gaps"].append(
                        f"{shot.get('shot_id')}: B-roll has no narrative content — will produce empty room"
                    )

        report.scene_coverage[scene_id] = coverage

    # =========================================================================
    # 4. GENERATE RECOMMENDATIONS (what FAL calls to make to fix gaps)
    # =========================================================================

    for char_name, pack in report.characters.items():
        for missing_type in pack.refs_missing:
            ref_info = CHARACTER_REF_TYPES[missing_type]
            if ref_info["priority"] <= 2:  # Only recommend high-priority refs
                report.recommended_generations.append({
                    "type": "character_ref",
                    "character": char_name,
                    "ref_type": missing_type,
                    "description": ref_info["description"],
                    "prompt_hint": f"{pack.appearance_description}, {ref_info['description']}",
                    "priority": ref_info["priority"],
                })

    for loc_name, pack in report.locations.items():
        for missing_type in pack.refs_missing:
            ref_info = LOCATION_REF_TYPES[missing_type]
            if ref_info["priority"] <= 2:
                report.recommended_generations.append({
                    "type": "location_ref",
                    "location": pack.location_name,
                    "ref_type": missing_type,
                    "description": ref_info["description"],
                    "prompt_hint": f"{pack.location_name}. {ref_info['description']}",
                    "priority": ref_info["priority"],
                })

    # Sort recommendations by priority
    report.recommended_generations.sort(key=lambda x: x["priority"])

    # =========================================================================
    # 5. OVERALL VERDICT
    # =========================================================================

    report.is_production_ready = len(report.blocking_issues) == 0

    return report


# =============================================================================
# BEST-FIT REF SELECTOR — DP-standard ref selection per shot
# =============================================================================

def select_best_ref_for_shot(
    shot: dict,
    character_packs: Dict[str, CharacterPackStatus],
    location_packs: Dict[str, LocationPackStatus],
) -> Dict[str, Any]:
    """
    Given a shot and the available ref packs, select the BEST ref for this specific
    shot type following DP framing standards.

    Returns dict with:
      - character_refs: List[str] (file paths, ordered primary→secondary)
      - location_ref: Optional[str] (file path)
      - ref_strategy: str (explanation of selection)
    """
    shot_type = (shot.get("shot_type") or "medium").lower()
    characters = shot.get("characters", [])
    dialogue = shot.get("dialogue_text", "") or ""

    ref_spec = SHOT_TYPE_REF_MAP.get(shot_type, SHOT_TYPE_REF_MAP.get("medium"))
    ideal_char_type = ref_spec.get("char_ref") if ref_spec else "headshot"
    ideal_loc_type = ref_spec.get("loc_ref") if ref_spec else "wide_interior"

    # Determine primary character (speaker priority)
    primary = None
    if dialogue and ":" in dialogue:
        speaker = dialogue.split(":")[0].strip()
        speaker = re.sub(r'\s*\(.*?\)\s*', '', speaker).strip().upper()
        if speaker in [c.upper() for c in characters]:
            primary = speaker
    if not primary and characters:
        primary = characters[0].upper()

    # Select character refs
    char_refs = []
    strategy_notes = []

    ordered = []
    if primary:
        ordered.append(primary)
    for c in characters:
        if c.upper() not in [o.upper() for o in ordered]:
            ordered.append(c.upper())

    for char_name in ordered:
        pack = character_packs.get(char_name)
        if not pack:
            strategy_notes.append(f"{char_name}: no pack found")
            continue

        # Try ideal type first, then fallback chain
        fallback_chain = {
            "headshot": ["headshot", "three_quarter", "full_body"],
            "three_quarter": ["three_quarter", "headshot", "full_body"],
            "full_body": ["full_body", "three_quarter", "headshot"],
            "profile": ["profile", "three_quarter", "headshot"],
        }

        chain = fallback_chain.get(ideal_char_type, ["headshot"])
        selected = None
        for ref_type in chain:
            if ref_type in pack.refs_available:
                selected = pack.refs_available[ref_type]
                if ref_type != ideal_char_type:
                    strategy_notes.append(
                        f"{char_name}: Using {ref_type} (ideal was {ideal_char_type})"
                    )
                else:
                    strategy_notes.append(f"{char_name}: Using ideal {ref_type}")
                break

        if selected:
            char_refs.append(selected)
        else:
            strategy_notes.append(f"{char_name}: NO viable ref found")

    # Select location ref
    loc_ref = None
    location = (shot.get("location") or "").replace(" ", "_").replace("-", "_").upper()

    for loc_norm, pack in location_packs.items():
        base = loc_norm.split("___")[0].split("_-_")[0]
        if base in location or location in loc_norm:
            # Try ideal type first, then fallback
            loc_fallback = {
                "wide_exterior": ["wide_exterior", "wide_interior"],
                "wide_interior": ["wide_interior", "medium_interior", "wide_exterior"],
                "reverse_angle": ["reverse_angle", "wide_interior", "medium_interior"],
                "medium_interior": ["medium_interior", "wide_interior"],
                "detail_insert": ["detail_insert", "medium_interior", "wide_interior"],
            }

            chain = loc_fallback.get(ideal_loc_type, ["wide_interior"])
            for ref_type in chain:
                if ref_type in pack.refs_available:
                    loc_ref = pack.refs_available[ref_type]
                    if ref_type != ideal_loc_type:
                        strategy_notes.append(
                            f"Location: Using {ref_type} (ideal was {ideal_loc_type})"
                        )
                    break
            break

    return {
        "character_refs": char_refs,
        "location_ref": loc_ref,
        "ref_strategy": "; ".join(strategy_notes) if strategy_notes else "default",
        "ideal_char_type": ideal_char_type,
        "ideal_loc_type": ideal_loc_type,
    }


# =============================================================================
# NARRATIVE B-ROLL ANALYZER
# =============================================================================

def analyze_broll_narrative(
    shot: dict,
    scene_context: dict = None,
    story_bible_scene: dict = None,
) -> Dict[str, Any]:
    """
    Determine what a B-roll slot SHOULD show based on narrative context.

    B-roll should NEVER be "empty room, environmental detail only."
    B-roll should advance the story or establish context:
      - Character approaching the building (establishing)
      - A specific prop mentioned in dialogue (insert)
      - Servants/staff doing period-appropriate work (atmosphere)
      - A photograph, letter, or object that matters to the plot (foreshadowing)
      - The reverse angle of where a conversation is happening (geography)
    """
    shot_id = shot.get("shot_id", "")
    scene_id = shot.get("scene_id", shot_id[:3] if shot_id else "")

    result = {
        "shot_id": shot_id,
        "current_description": shot.get("description", "") or shot.get("_locked_nano_prompt", ""),
        "is_narrative": False,
        "suggested_content": None,
        "narrative_type": None,
    }

    # Check if current description has actual narrative content
    generic_markers = [
        "environmental detail only",
        "no people, no figures",
        "static hold",
        "atmosphere",
    ]
    current = result["current_description"].lower()
    is_generic = any(m in current for m in generic_markers) or len(current) < 20

    if not is_generic:
        result["is_narrative"] = True
        return result

    # Try to derive narrative B-roll from story bible
    if story_bible_scene:
        desc = story_bible_scene.get("description", "")
        key_props = story_bible_scene.get("key_props", [])
        key_moments = story_bible_scene.get("key_moments", story_bible_scene.get("beats", []))

        # Extract narrative elements
        suggestions = []

        if key_props:
            suggestions.append({
                "type": "prop_insert",
                "content": f"Close-up detail of {key_props[0] if isinstance(key_props[0], str) else key_props[0].get('name', 'prop')}",
            })

        if key_moments and isinstance(key_moments, list):
            for moment in key_moments[:2]:
                if isinstance(moment, str):
                    suggestions.append({"type": "beat_cutaway", "content": moment})
                elif isinstance(moment, dict):
                    suggestions.append({
                        "type": "beat_cutaway",
                        "content": moment.get("description", moment.get("action", "")),
                    })

        if suggestions:
            result["suggested_content"] = suggestions[0]["content"]
            result["narrative_type"] = suggestions[0]["type"]

    return result


# =============================================================================
# CONVENIENCE: Run full validation from file paths
# =============================================================================

def validate_project(project_path: str) -> CreationPackReport:
    """Load project files and run full creation pack validation."""
    pp = Path(project_path)

    # Load required files
    shot_plan_path = pp / "shot_plan.json"
    cast_map_path = pp / "cast_map.json"
    story_bible_path = pp / "story_bible.json"

    if not shot_plan_path.exists():
        report = CreationPackReport(project=pp.name, timestamp=datetime.utcnow().isoformat())
        report.blocking_issues.append("shot_plan.json not found")
        return report

    with open(shot_plan_path) as f:
        shot_plan = json.load(f)

    cast_map = {}
    if cast_map_path.exists():
        with open(cast_map_path) as f:
            cast_map = json.load(f)

    story_bible = None
    if story_bible_path.exists():
        with open(story_bible_path) as f:
            story_bible = json.load(f)

    return validate_creation_pack(str(pp), shot_plan, cast_map, story_bible)


# =============================================================================
# AUTO-RECAST SYSTEM — Generate missing/mismatched refs from descriptions
# =============================================================================

def build_recast_manifest(
    report: CreationPackReport,
    cast_map: dict,
    story_bible: dict = None,
    force_all: bool = False,
) -> List[Dict[str, Any]]:
    """
    Build a manifest of FAL generation calls needed to fix the creation pack.

    Universal: Uses cast_map appearance descriptions to generate character refs.
    Uses story bible location descriptions to generate location masters.

    If force_all=True, regenerates ALL refs (full recast).
    If force_all=False, only regenerates refs that are missing or description-mismatched.

    Returns a list of generation jobs, each with:
      - job_type: "character_ref" or "location_ref"
      - name: character or location name
      - ref_type: "headshot", "three_quarter", "full_body", etc.
      - prompt: The FAL prompt to use
      - output_path: Where to save the result
      - num_candidates: How many to generate (pick best)
      - priority: 1=blocking, 2=quality, 3=nice-to-have
    """
    jobs = []

    # ---- CHARACTER RECAST JOBS ----
    # V27.1 FIX: Headshot is text-to-image (master identity). All other angles
    # are IMAGE-TO-IMAGE reframes FROM the headshot — ensuring same person,
    # same wardrobe, same lighting. Never independent text-to-image for angles.
    for char_name, pack in report.characters.items():
        char_data = cast_map.get(char_name, {})
        appearance = char_data.get("appearance", "")
        if not appearance:
            continue

        safe_name = char_name.replace(" ", "_").upper()
        needs_recast = force_all or pack.description_match in ("FAIL", "UNVERIFIED")

        # Resolve headshot path (needed as source for angle reframes)
        headshot_path = pack.refs_available.get("headshot", "")
        if not headshot_path:
            headshot_path = f"character_library_locked/{safe_name}_CHAR_REFERENCE.jpg"

        for ref_type, ref_info in CHARACTER_REF_TYPES.items():
            # Generate if missing OR if description doesn't match (recast)
            if ref_type not in pack.refs_available or needs_recast:
                prompt = _build_character_ref_prompt(appearance, ref_type, ref_info)
                output_name = f"{safe_name}_CHAR_REFERENCE.jpg" if ref_type == "headshot" else f"{safe_name}_{ref_type}.jpg"

                job = {
                    "job_type": "character_ref",
                    "name": char_name,
                    "ref_type": ref_type,
                    "prompt": prompt,
                    "output_path": f"character_library_locked/{output_name}",
                    "num_candidates": 3 if ref_type == "headshot" else 1,
                    "priority": ref_info["priority"],
                    "resolution": "2K" if ref_type == "headshot" else "1K",
                    "aspect_ratio": "1:1" if ref_type == "headshot" else "3:4",
                }

                if ref_type == "headshot":
                    # Headshot = TEXT-TO-IMAGE (establish identity master)
                    job["model"] = "fal-ai/nano-banana-pro"
                    job["source_image"] = None
                else:
                    # All other angles = IMAGE-TO-IMAGE reframe FROM headshot
                    # Same person, same wardrobe, different camera angle
                    job["model"] = "fal-ai/nano-banana-pro/edit"
                    job["source_image"] = headshot_path

                jobs.append(job)

    # ---- LOCATION RECAST JOBS ----
    bible_scenes = {}
    if story_bible:
        for scene in story_bible.get("scenes", []):
            loc = scene.get("location", "")
            if loc:
                norm = loc.replace(" ", "_").replace("-", "_").upper()
                bible_scenes[norm] = scene

    # V27.1 FIX: Location angles are IMAGE-TO-IMAGE reframes FROM the wide master.
    # The wide master establishes the canonical environment. Reverse angles and
    # medium interiors must show THE SAME ROOM from a different camera position —
    # not an independently generated room that doesn't match. No characters in any
    # location ref (add "no people" to negative).
    for loc_norm, pack in report.locations.items():
        loc_name = pack.location_name
        bible_scene = bible_scenes.get(loc_norm)
        loc_desc = ""
        if bible_scene:
            loc_desc = bible_scene.get("description", "")

        # Find the wide master to use as source image for angle reframes
        wide_master_path = (
            pack.refs_available.get("wide_interior") or
            pack.refs_available.get("wide_exterior") or
            pack.refs_available.get("wide_master") or
            None
        )
        # Also search existing_masters dict for this location
        if not wide_master_path:
            for mk, mp in existing_masters.items():
                mk_norm = mk.replace(" ", "_").replace("-", "_").upper()
                base = loc_norm.split("___")[0].split("_-_")[0]
                if base in mk_norm and "MASTER" in mk_norm:
                    wide_master_path = mp
                    break

        for ref_type in pack.refs_missing:
            ref_info = LOCATION_REF_TYPES.get(ref_type)
            if not ref_info or ref_info["priority"] > 2:
                continue  # Skip low-priority location refs for auto-gen

            prompt = _build_location_ref_prompt(loc_name, ref_type, ref_info, loc_desc)
            safe_loc = loc_name.replace(" ", "_").replace("-", "_").upper()
            output_name = f"{safe_loc}_{ref_type}.jpg"

            job = {
                "job_type": "location_ref",
                "name": loc_name,
                "ref_type": ref_type,
                "prompt": prompt,
                "output_path": f"location_masters/{output_name}",
                "num_candidates": 1,
                "priority": ref_info["priority"],
                "resolution": "1K",
                "aspect_ratio": "16:9",
            }

            if wide_master_path and ref_type != "wide_exterior":
                # IMAGE-TO-IMAGE reframe from existing wide master
                # Same room, different camera angle — no independent generation
                job["model"] = "fal-ai/nano-banana-pro/edit"
                job["source_image"] = wide_master_path
            else:
                # Only wide_exterior or missing master = text-to-image
                job["model"] = "fal-ai/nano-banana-pro"
                job["source_image"] = None

            jobs.append(job)

    # Sort by priority
    jobs.sort(key=lambda x: x["priority"])

    return jobs


def _build_character_ref_prompt(
    appearance: str,
    ref_type: str,
    ref_info: dict,
) -> str:
    """Build a FAL prompt for generating a character reference image."""
    base = f"Cinematic portrait photograph. {appearance}."

    framing = {
        "headshot": "Front-facing headshot, shoulders visible, neutral background, studio lighting, sharp focus on face, identity reference photograph",
        "three_quarter": "Three-quarter angle portrait, waist up, slight body turn, character in wardrobe, soft studio lighting",
        "full_body": "Full body standing portrait, character in complete wardrobe, posture visible, neutral background",
        "profile": "Side profile portrait, 90 degree angle, clean silhouette, studio lighting",
    }

    pose = framing.get(ref_type, framing["headshot"])
    negative = "worst quality, blurry, deformed, extra limbs, cartoon, anime, illustration, painting, sketch"

    return f"{base} {pose}. photorealistic, 8k detail, cinematic color grading"


def _build_location_ref_prompt(
    location_name: str,
    ref_type: str,
    ref_info: dict,
    scene_description: str = "",
) -> str:
    """Build a FAL prompt for generating a location reference image."""
    base = f"Cinematic wide shot. {location_name}."
    if scene_description:
        # Extract atmospheric details from scene description
        base += f" {scene_description[:200]}."

    framing = {
        "wide_exterior": "Exterior establishing shot, wide angle, full building/location visible, atmospheric lighting, no people",
        "wide_interior": "Interior wide shot, full room geography visible, production design detail, atmospheric lighting, no people",
        "reverse_angle": "Interior reverse angle, 180 degrees from main view, showing the opposite wall/side of the room, no people",
        "medium_interior": "Interior medium shot, focused on key furniture/area within the room, atmospheric detail, no people",
        "detail_insert": "Close-up detail shot, specific prop or texture, atmospheric, shallow depth of field, no people",
    }

    angle = framing.get(ref_type, framing["wide_interior"])

    return f"{base} {angle}. cinematic, desaturated tones, production design, 8k detail"


# =============================================================================
# CLI ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python creation_pack_validator.py <project_path>")
        sys.exit(1)

    project_path = sys.argv[1]
    report = validate_project(project_path)

    print(f"\n{'='*70}")
    print(f"CREATION PACK REPORT — {report.project}")
    print(f"{'='*70}")

    print(f"\nProduction Ready: {'YES' if report.is_production_ready else 'NO'}")

    if report.blocking_issues:
        print(f"\nBLOCKING ISSUES ({len(report.blocking_issues)}):")
        for issue in report.blocking_issues:
            print(f"  BLOCK: {issue}")

    if report.warnings:
        print(f"\nWARNINGS ({len(report.warnings)}):")
        for w in report.warnings:
            print(f"  WARN: {w}")

    print(f"\nCHARACTERS ({len(report.characters)}):")
    for name, pack in report.characters.items():
        status = "READY" if pack.is_production_ready else ("VIABLE" if pack.minimum_viable else "BLOCKED")
        refs = list(pack.refs_available.keys())
        missing = pack.refs_missing
        print(f"  {name}: [{status}] has={refs} missing={missing}")

    print(f"\nLOCATIONS ({len(report.locations)}):")
    for name, pack in report.locations.items():
        status = "READY" if pack.is_production_ready else ("VIABLE" if pack.minimum_viable else "BLOCKED")
        refs = list(pack.refs_available.keys())
        missing = pack.refs_missing
        scenes = pack.scenes_using
        print(f"  {pack.location_name}: [{status}] has={refs} missing={missing} scenes={scenes}")

    if report.recommended_generations:
        print(f"\nRECOMMENDED GENERATIONS ({len(report.recommended_generations)}):")
        for rec in report.recommended_generations:
            print(f"  P{rec['priority']}: {rec['type']} — {rec.get('character', rec.get('location', '?'))} → {rec['ref_type']}")

    print(f"\n{'='*70}")
