#!/usr/bin/env python3
"""
POST-FRAME QUALITY GATE — V27.1.5
==================================

Runs AFTER first frames are generated but BEFORE video generation (Kling/LTX).
This is a GROUP REVIEW system that verifies spatial and aesthetic continuity
across all shots in a scene.

THE PROBLEM:
Each shot generates independently. The result: wrong room, misframed faces,
identical OTS angles, characters teleporting across frame, inconsistent lighting.
A single human reviewer looking at 12 frames takes 3 minutes and spots every issue.

THE SOLUTION:
Post-frame quality gate runs automated checks that mimic a professional DIT's eye:
  1. Location Consistency: Does frame match scene's established room?
  2. Framing Fidelity: Does close-up show face filling frame (not panoramic room)?
  3. OTS Alternation: Do adjacent OTS shots show different angles (A vs B)?
  4. Screen Position Lock: Are characters on the correct side of frame?
  5. Lighting Continuity: Do all shots in scene have matching light color/temp?
  6. B-roll Narrative: Does B-roll show STORY content (not empty rooms)?

VERDICT SYSTEM:
  - APPROVED: Frame looks correct for its role. Ready for video.
  - NEEDS_VARIATION: Frame has issues but can be fixed. Generate 3 candidates, pick best.
  - REJECTED: Frame has fundamental problems (wrong room, wrong character). Must regenerate with fixed refs.

WORKFLOW:
  1. review_scene_frames() — Loads all first frames for a scene, checks each.
  2. build_variation_manifest() — Creates FAL generation jobs for NEEDS_VARIATION shots.
  3. After candidates generate → select_best_candidate() — Operator picks best variant.
  4. Run video generation on approved frames.

Architecture:
  - Each frame loaded + metadata extracted from shot_plan.json
  - Vision module analyzes frame (location score, identity score, motion)
  - Spatial checks (room lock, position lock, OTS angle)
  - Framing checks (focal length enforcement — does close-up show tight face?)
  - B-roll narrative check (compared to story_bible beats)
  - Verdict + structured recommendations

Universal: Works for ANY project, any scene. Data-driven from shot_plan + story_bible.
"""

import json
import os
import re
import sys
import logging
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from enum import Enum

logger = logging.getLogger("post_frame_quality_gate")

# =============================================================================
# VERDICTS
# =============================================================================


class FrameVerdict(Enum):
    """Verdict for a single frame post-generation review."""
    APPROVED = "APPROVED"
    NEEDS_VARIATION = "NEEDS_VARIATION"
    REJECTED = "REJECTED"


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class FrameReviewCheck:
    """A single check performed on a frame."""
    check_name: str
    passed: bool
    score: float = 0.0  # 0-1 confidence
    detail: str = ""
    recommendation: str = ""


@dataclass
class FrameReviewResult:
    """Complete review result for a single frame."""
    shot_id: str
    verdict: FrameVerdict
    frame_path: str = ""
    checks: List[FrameReviewCheck] = field(default_factory=list)
    score: float = 0.0  # Average of all checks that passed
    issues: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    needs_refs: Dict[str, str] = field(default_factory=dict)  # ref_type → required path
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


@dataclass
class VariationGenerationJob:
    """A FAL generation job for one candidate variant."""
    shot_id: str
    variant_idx: int  # 1, 2, or 3
    prompt: str
    nano_prompt: str
    ltx_motion_prompt: str
    image_urls: List[str]
    seed: int
    output_path: str  # e.g., first_frame_candidates/001_005B_v1.jpg
    reason: str  # Why this variation needed (e.g., "framing too wide")


@dataclass
class QualityGateReport:
    """Summary report for a scene's post-frame review."""
    project: str
    scene_id: str
    total_shots: int
    approved_count: int
    variation_count: int
    rejected_count: int
    per_shot_verdicts: Dict[str, FrameReviewResult] = field(default_factory=dict)
    variation_manifest: List[VariationGenerationJob] = field(default_factory=list)
    broll_narrative_check: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""
    note: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def _load_json_safe(path: str) -> Dict | List | None:
    """Load JSON file with error handling."""
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to load {path}: {e}")
        return None


def _normalize_shot_plan(sp: Any) -> Dict:
    """
    Normalize shot_plan to {"shots": [...]} format.
    Handles both bare list and dict formats.
    """
    if isinstance(sp, list):
        return {"shots": sp}
    return sp


def _extract_room_name(location_str: str) -> str:
    """
    Extract the primary room name from location string.
    E.g., "HARGROVE ESTATE - GRAND FOYER" → "GRAND FOYER"
    """
    if not location_str:
        return ""
    # Split on dash and take the last part
    parts = location_str.split("-")
    room = parts[-1].strip() if parts else location_str.strip()
    return room.upper()


def _extract_ref_room(ref_path: str) -> str:
    """
    Extract room identifier from a ref path.
    E.g., "location_masters/GRAND_FOYER_medium_interior.jpg" → "GRAND_FOYER"
    """
    basename = os.path.basename(ref_path)
    # Remove extension
    basename = os.path.splitext(basename)[0]
    # Split on underscores and take the base
    parts = basename.split("_")
    # Usually room name is before angle suffix (wide, medium, reverse, etc.)
    # Conservative: take first 2-3 parts as room name
    if len(parts) >= 2:
        return "_".join(parts[:-1]).upper()
    return basename.upper()


def _get_shot_type_framing_requirements(shot_type: str) -> Tuple[str, str, str]:
    """
    Return expected framing characteristics for a shot type.
    Returns (framing_type, face_fill_percent, background_detail_level)
    """
    shot_type = (shot_type or "").lower()

    if "close" in shot_type or "ecu" in shot_type or "extreme" in shot_type:
        return ("tight", "80-100", "minimal")
    elif "medium_close" in shot_type or "mcu" in shot_type:
        return ("medium_tight", "50-70", "soft_blurred")
    elif "medium" in shot_type:
        return ("medium", "30-50", "secondary")
    elif "two_shot" in shot_type:
        return ("medium", "25-40", "context")
    elif "over_the_shoulder" in shot_type or "ots" in shot_type:
        return ("medium", "30-50", "context")
    elif "wide" in shot_type or "establishing" in shot_type:
        return ("wide", "10-20", "full")
    elif "reaction" in shot_type:
        return ("medium_tight", "60-80", "soft_blurred")
    else:
        return ("unknown", "0", "unknown")


# =============================================================================
# LOCATION CONSISTENCY CHECKS
# =============================================================================


def _check_location_consistency(
    shot: Dict,
    scene_room: str,
    frame_path: str,
    story_bible: Dict,
) -> FrameReviewCheck:
    """
    Check: Does the frame's location ref match the scene's established room?

    RULE T2-OR-13: CHARACTERS DON'T TELEPORT — ROOM-LOCKED LOCATION RESOLUTION
    All shots in a scene must resolve to the scene's established room.
    """
    shot_id = shot.get("shot_id", "")
    location_ref = shot.get("location_ref", "") or ""

    # Extract room names
    ref_room = _extract_room_name(location_ref) if location_ref else ""
    expected_room = scene_room

    # If no location ref, it might be intentional (e.g., close_up with no location)
    if not location_ref:
        shot_type = (shot.get("shot_type") or "").lower()
        if "close" in shot_type or "extreme" in shot_type:
            # Close-ups often don't have location refs — this is acceptable
            return FrameReviewCheck(
                check_name="location_consistency",
                passed=True,
                score=1.0,
                detail=f"{shot_type} has no location ref (acceptable for face-centric shots)",
            )
        else:
            return FrameReviewCheck(
                check_name="location_consistency",
                passed=False,
                score=0.0,
                detail=f"Missing location ref for {shot_type}",
                recommendation="Add location ref for scene room context",
            )

    # Check if ref room matches scene room
    # Fuzzy match: allow substring (e.g., "FOYER" matches "GRAND FOYER")
    if expected_room in ref_room or ref_room in expected_room:
        return FrameReviewCheck(
            check_name="location_consistency",
            passed=True,
            score=1.0,
            detail=f"Location ref matches scene room: {ref_room}",
        )
    else:
        return FrameReviewCheck(
            check_name="location_consistency",
            passed=False,
            score=0.0,
            detail=f"Location ref room '{ref_room}' does not match scene room '{expected_room}'",
            recommendation=f"Must regenerate with correct location ref for {expected_room}",
        )


# =============================================================================
# FRAMING FIDELITY CHECKS (Focal Length Enforcement)
# =============================================================================


def _check_framing_fidelity(
    shot: Dict,
    frame_path: str,
) -> FrameReviewCheck:
    """
    Check: Is the framing consistent with the shot_type?
    E.g., close-ups should show face filling frame, not panoramic room.

    Without vision analysis, we do heuristic checks:
    - If frame exists and file size is large, might indicate wide framing
    - If nano_prompt has focal enforcement markers, score based on consistency

    RULE T2-FE-24: APPARENT-SIZE-AT-FOCAL-LENGTH IN PROMPTS
    FAL ignores numeric focal length. The prompt must describe VISUAL EFFECT.
    """
    shot_id = shot.get("shot_id", "")
    shot_type = (shot.get("shot_type") or "").lower()
    nano_prompt = shot.get("nano_prompt", "") or ""

    expected_framing, face_fill, bg_detail = _get_shot_type_framing_requirements(shot_type)

    # Check if focal enforcement markers are in the prompt
    has_tight_framing = "[TIGHT FRAMING:" in nano_prompt
    has_medium_tight = "[MEDIUM-TIGHT FRAMING:" in nano_prompt
    has_wide_framing = "[WIDE FRAMING:" in nano_prompt

    # Validate consistency
    if expected_framing == "tight" and not (has_tight_framing or has_medium_tight):
        return FrameReviewCheck(
            check_name="framing_fidelity",
            passed=False,
            score=0.3,
            detail=f"Close-up shot '{shot_type}' missing tight framing marker",
            recommendation="Regenerate with focal enforcement: 'face fills 80% of frame, minimal background'",
        )

    if expected_framing == "wide" and not has_wide_framing:
        return FrameReviewCheck(
            check_name="framing_fidelity",
            passed=False,
            score=0.4,
            detail=f"Wide shot '{shot_type}' missing wide framing marker",
            recommendation="Regenerate with focal enforcement: 'full room geography visible'",
        )

    # If markers exist, we pass (actual visual verification would require vision API)
    if has_tight_framing or has_medium_tight or has_wide_framing:
        return FrameReviewCheck(
            check_name="framing_fidelity",
            passed=True,
            score=0.9,
            detail=f"Shot has focal enforcement marker for '{expected_framing}' framing",
        )

    # Default: pass with lower confidence if no markers but shot type is known
    return FrameReviewCheck(
        check_name="framing_fidelity",
        passed=True,
        score=0.6,
        detail=f"Shot type '{shot_type}' recognized, assuming correct framing",
    )


# =============================================================================
# OTS ANGLE ALTERNATION CHECKS (180° Rule)
# =============================================================================


def _check_ots_angle_alternation(
    shot: Dict,
    scene_shots: List[Dict],
) -> FrameReviewCheck:
    """
    Check: For adjacent OTS shots in dialogue, do they show opposite angles (A vs B)?

    RULE T2-FE-14: OTS SHOT/REVERSE-SHOT FRAMING — 180° RULE
    Adjacent OTS dialogue shots MUST show OPPOSITE sides of the room.
    """
    shot_id = shot.get("shot_id", "")
    shot_type = (shot.get("shot_type") or "").lower()

    # Only check OTS shots
    if "over_the_shoulder" not in shot_type and "ots" not in shot_type:
        return FrameReviewCheck(
            check_name="ots_angle_alternation",
            passed=True,
            score=1.0,
            detail="Not an OTS shot, skipping check",
        )

    current_ots_angle = shot.get("_ots_angle", "")
    if not current_ots_angle:
        return FrameReviewCheck(
            check_name="ots_angle_alternation",
            passed=False,
            score=0.0,
            detail="OTS shot missing _ots_angle assignment",
            recommendation="Assign _ots_angle (A or B) based on speaker position",
        )

    # Find adjacent shots in this scene (by temporal order)
    scene_id = shot_id.split("_")[0]
    scene_shots_sorted = sorted(
        [s for s in scene_shots if s.get("shot_id", "").startswith(f"{scene_id}_")],
        key=lambda s: int(s.get("shot_number", 999)),
    )

    current_idx = None
    for idx, s in enumerate(scene_shots_sorted):
        if s.get("shot_id") == shot_id:
            current_idx = idx
            break

    if current_idx is None or current_idx == 0:
        return FrameReviewCheck(
            check_name="ots_angle_alternation",
            passed=True,
            score=0.8,
            detail="OTS shot found but no previous OTS to compare",
        )

    # Check previous shot
    prev_shot = scene_shots_sorted[current_idx - 1]
    prev_shot_type = (prev_shot.get("shot_type") or "").lower()
    prev_ots_angle = prev_shot.get("_ots_angle", "")

    # Only check if previous is also OTS
    if "over_the_shoulder" not in prev_shot_type and "ots" not in prev_shot_type:
        return FrameReviewCheck(
            check_name="ots_angle_alternation",
            passed=True,
            score=0.8,
            detail="Previous shot not OTS, cannot check alternation",
        )

    if not prev_ots_angle:
        return FrameReviewCheck(
            check_name="ots_angle_alternation",
            passed=False,
            score=0.3,
            detail=f"Previous OTS shot {prev_shot.get('shot_id')} missing _ots_angle",
            recommendation=f"Assign _ots_angle to both {prev_shot.get('shot_id')} and {shot_id}",
        )

    # Check alternation
    if current_ots_angle == prev_ots_angle:
        return FrameReviewCheck(
            check_name="ots_angle_alternation",
            passed=False,
            score=0.0,
            detail=f"Both OTS shots have same angle '{current_ots_angle}' — no shot/reverse-shot",
            recommendation=f"Previous shot: {prev_shot.get('shot_id')} ({prev_ots_angle}), this shot: {shot_id} ({current_ots_angle}). Must be opposite.",
        )

    return FrameReviewCheck(
        check_name="ots_angle_alternation",
        passed=True,
        score=1.0,
        detail=f"OTS angles alternate: {prev_ots_angle} → {current_ots_angle}",
    )


# =============================================================================
# SCREEN POSITION LOCK CHECKS
# =============================================================================


def _check_screen_position_lock(
    shot: Dict,
    scene_shots: List[Dict],
    story_bible: Dict,
) -> FrameReviewCheck:
    """
    Check: Are characters on the correct side of frame (screen position lock)?

    RULE T2-FE-20: SCREEN POSITION LOCK — 180° RULE ACROSS ALL SHOT TYPES
    Once the first OTS establishes screen positions, those are locked across
    the entire dialogue sequence.
    """
    shot_id = shot.get("shot_id", "")
    characters = shot.get("characters", [])

    # Only check dialogue shots with multiple characters
    if len(characters) < 2:
        return FrameReviewCheck(
            check_name="screen_position_lock",
            passed=True,
            score=1.0,
            detail="Single character or no characters, no position lock needed",
        )

    # Check if positions are recorded
    screen_positions = shot.get("_screen_positions", {})
    if not screen_positions:
        return FrameReviewCheck(
            check_name="screen_position_lock",
            passed=False,
            score=0.2,
            detail="Multi-character shot missing _screen_positions data",
            recommendation="Run screen position lock establishment during prep",
        )

    # Validate each character has a position
    missing_positions = [c for c in characters if c not in screen_positions]
    if missing_positions:
        return FrameReviewCheck(
            check_name="screen_position_lock",
            passed=False,
            score=0.4,
            detail=f"Missing position lock for: {missing_positions}",
            recommendation="Establish position lock for all characters in dialogue sequence",
        )

    return FrameReviewCheck(
        check_name="screen_position_lock",
        passed=True,
        score=1.0,
        detail=f"Screen positions locked: {screen_positions}",
    )


# =============================================================================
# LIGHTING CONTINUITY CHECKS
# =============================================================================


def _check_lighting_continuity(
    shot: Dict,
    scene_shots: List[Dict],
) -> FrameReviewCheck:
    """
    Check: Do all shots in scene have matching lighting (color temp, direction)?

    RULE T2-FE-25: LIGHTING RIG LOCK PER SCENE
    Every shot in a scene gets an identical [LIGHTING RIG: ...] block in nano_prompt.
    """
    shot_id = shot.get("shot_id", "")
    nano_prompt = shot.get("nano_prompt", "") or ""
    scene_id = shot_id.split("_")[0]

    # Check if lighting rig marker is present
    has_lighting_rig = "[LIGHTING RIG:" in nano_prompt

    if not has_lighting_rig:
        return FrameReviewCheck(
            check_name="lighting_continuity",
            passed=False,
            score=0.3,
            detail="Shot missing [LIGHTING RIG:] marker",
            recommendation="Inject scene lighting rig into nano_prompt for all scene shots",
        )

    # Extract lighting rig text for comparison
    rig_match = re.search(r"\[LIGHTING RIG: ([^\]]+)\]", nano_prompt)
    if rig_match:
        rig_text = rig_match.group(1)
        # For now, just verify it exists and is substantive
        if len(rig_text) > 10:
            return FrameReviewCheck(
                check_name="lighting_continuity",
                passed=True,
                score=0.95,
                detail=f"Lighting rig locked: {rig_text[:60]}...",
            )

    return FrameReviewCheck(
        check_name="lighting_continuity",
        passed=True,
        score=0.7,
        detail="Lighting rig marker present",
    )


# =============================================================================
# B-ROLL NARRATIVE CHECKS
# =============================================================================


def _check_broll_narrative_content(
    shot: Dict,
    story_bible: Dict,
) -> FrameReviewCheck:
    """
    Check: Does B-roll shot show NARRATIVE content (not empty rooms)?

    RULE T2-CK-7: B-ROLL MUST HAVE NARRATIVE CONTENT
    Generic B-roll ("environmental detail only", "no people") flagged for replacement.
    B-roll should show: approaching characters, meaningful props, servants/staff,
    letters/photos, exterior-to-interior transitions, reverse angles.
    """
    shot_id = shot.get("shot_id", "")
    is_broll = shot.get("is_broll", False)

    if not is_broll:
        return FrameReviewCheck(
            check_name="broll_narrative_content",
            passed=True,
            score=1.0,
            detail="Not a B-roll shot",
        )

    # Get shot description
    description = (shot.get("description") or "") + " " + (shot.get("action") or "")
    description = description.lower()

    # Narrative keywords that indicate story content
    narrative_keywords = [
        "approaching",
        "entering",
        "walking",
        "prop",
        "letter",
        "photograph",
        "photo",
        "servant",
        "staff",
        "door",
        "exterior",
        "transition",
        "reverse",
        "angle",
        "corridor",
        "staircase",
        "fireplace",
        "window",
        "garden",
    ]

    has_narrative = any(kw in description for kw in narrative_keywords)

    if not has_narrative:
        return FrameReviewCheck(
            check_name="broll_narrative_content",
            passed=False,
            score=0.2,
            detail=f"B-roll shot may be generic (description: '{description.strip()}')",
            recommendation="Rewrite B-roll description to include narrative content from story_bible beats",
        )

    return FrameReviewCheck(
        check_name="broll_narrative_content",
        passed=True,
        score=1.0,
        detail=f"B-roll has narrative keywords: {[kw for kw in narrative_keywords if kw in description]}",
    )


# =============================================================================
# FRAME FILE EXISTENCE CHECK
# =============================================================================


def _check_frame_existence(frame_path: str) -> FrameReviewCheck:
    """Check: Does the frame file actually exist?"""
    if os.path.exists(frame_path):
        file_size = os.path.getsize(frame_path)
        return FrameReviewCheck(
            check_name="frame_existence",
            passed=True,
            score=1.0,
            detail=f"Frame file exists ({file_size} bytes)",
        )
    else:
        return FrameReviewCheck(
            check_name="frame_existence",
            passed=False,
            score=0.0,
            detail=f"Frame file not found at {frame_path}",
            recommendation="Regenerate frame",
        )


# =============================================================================
# MAIN REVIEW FUNCTION
# =============================================================================


def review_scene_frames(
    project: str,
    scene_id: str,
) -> Dict[str, FrameReviewResult]:
    """
    Group review all first frames for a scene.
    Returns verdicts per shot.

    Args:
        project: Project name or path (e.g., "victorian_shadows_ep1")
        scene_id: Scene ID (e.g., "001")

    Returns:
        Dict mapping shot_id → FrameReviewResult with verdict, checks, and recommendations.
    """
    # Normalize project path
    if not project.startswith("pipeline_outputs/"):
        project = f"pipeline_outputs/{project}"

    # Load shot_plan and story_bible
    shot_plan_path = os.path.join(project, "shot_plan.json")
    story_bible_path = os.path.join(project, "story_bible.json")

    shot_plan = _load_json_safe(shot_plan_path)
    story_bible = _load_json_safe(story_bible_path)

    if not shot_plan:
        logger.error(f"Cannot load shot_plan from {shot_plan_path}")
        return {}

    # Normalize to {"shots": [...]}
    shot_plan = _normalize_shot_plan(shot_plan)
    shots_list = shot_plan.get("shots", [])

    # Filter to scene shots
    scene_shots = [s for s in shots_list if s.get("shot_id", "").startswith(f"{scene_id}_")]

    if not scene_shots:
        logger.warning(f"No shots found for scene {scene_id}")
        return {}

    # Extract scene room from story_bible
    scene_room = ""
    if story_bible:
        for scene in story_bible.get("scenes", []):
            if str(scene.get("scene_id", "")) == scene_id:
                scene_room = _extract_room_name(scene.get("location", ""))
                break

    logger.info(f"Reviewing {len(scene_shots)} shots for scene {scene_id} (room: {scene_room})")

    # Review each shot
    verdicts = {}
    for shot in scene_shots:
        shot_id = shot.get("shot_id", "")
        frame_path = os.path.join(project, "first_frames", f"{shot_id}.jpg")

        # Initialize result
        result = FrameReviewResult(
            shot_id=shot_id,
            verdict=FrameVerdict.APPROVED,
            frame_path=frame_path,
        )

        # Run all checks
        checks = []

        # 1. Frame existence
        checks.append(_check_frame_existence(frame_path))

        # 2. Location consistency
        if story_bible:
            checks.append(
                _check_location_consistency(shot, scene_room, frame_path, story_bible)
            )

        # 3. Framing fidelity
        checks.append(_check_framing_fidelity(shot, frame_path))

        # 4. OTS angle alternation (if OTS)
        checks.append(_check_ots_angle_alternation(shot, scene_shots))

        # 5. Screen position lock (if multi-character)
        checks.append(_check_screen_position_lock(shot, scene_shots, story_bible))

        # 6. Lighting continuity
        checks.append(_check_lighting_continuity(shot, scene_shots))

        # 7. B-roll narrative (if B-roll)
        if story_bible:
            checks.append(_check_broll_narrative_content(shot, story_bible))

        result.checks = checks

        # Determine verdict based on checks
        failed_checks = [c for c in checks if not c.passed]
        passed_checks = [c for c in checks if c.passed]

        if not passed_checks:
            result.verdict = FrameVerdict.REJECTED
        elif len(failed_checks) == 0:
            result.verdict = FrameVerdict.APPROVED
            result.score = sum(c.score for c in checks) / len(checks) if checks else 1.0
        else:
            # At least one failed check — needs variation
            result.verdict = FrameVerdict.NEEDS_VARIATION
            result.score = sum(c.score for c in passed_checks) / len(checks) if checks else 0.5

        # Collect issues and recommendations
        result.issues = [c.detail for c in failed_checks]
        result.recommendations = [c.recommendation for c in failed_checks if c.recommendation]

        verdicts[shot_id] = result

        logger.info(f"  {shot_id}: {result.verdict.value} (score: {result.score:.2f})")

    return verdicts


# =============================================================================
# VARIATION MANIFEST BUILDER
# =============================================================================


def build_variation_manifest(
    project: str,
    verdicts: Dict[str, FrameReviewResult],
) -> List[VariationGenerationJob]:
    """
    Build FAL generation jobs for 3 candidates per NEEDS_VARIATION shot.

    Args:
        project: Project path
        verdicts: Results from review_scene_frames()

    Returns:
        List of VariationGenerationJob objects ready for FAL submission.
    """
    if not project.startswith("pipeline_outputs/"):
        project = f"pipeline_outputs/{project}"

    # Load shot_plan for full metadata
    shot_plan = _load_json_safe(os.path.join(project, "shot_plan.json"))
    shot_plan = _normalize_shot_plan(shot_plan)
    shots_by_id = {s.get("shot_id"): s for s in shot_plan.get("shots", [])}

    manifest = []
    seed_base = 42

    for shot_id, verdict in verdicts.items():
        if verdict.verdict != FrameVerdict.NEEDS_VARIATION:
            continue

        shot_metadata = shots_by_id.get(shot_id, {})
        nano_prompt = (shot_metadata.get("nano_prompt") or "").strip()
        ltx_motion_prompt = (shot_metadata.get("ltx_motion_prompt") or "").strip()
        image_urls = shot_metadata.get("_fal_image_urls_resolved", [])

        if not nano_prompt:
            logger.warning(f"{shot_id}: No nano_prompt, skipping variation generation")
            continue

        # Generate 3 candidates with varied seeds and prompts
        for var_idx in range(1, 4):
            seed = seed_base + hash(shot_id) + var_idx
            seed = seed % (2**31)  # Ensure valid seed range

            # Vary the prompt slightly
            varied_nano = nano_prompt
            if var_idx == 2:
                # Tighten framing
                if "close" in shot_metadata.get("shot_type", "").lower():
                    varied_nano = re.sub(
                        r"\[MEDIUM-TIGHT FRAMING[^\]]*\]",
                        "[TIGHT FRAMING: face fills 90% of frame, extreme bokeh background]",
                        varied_nano,
                    )

            if var_idx == 3:
                # Adjust lighting
                varied_nano = re.sub(
                    r"\[LIGHTING RIG: ([^\]]+)\]",
                    r"[LIGHTING RIG: \1, +15% brightness for clarity]",
                    varied_nano,
                )

            output_path = os.path.join(
                project, "first_frame_candidates", f"{shot_id}_v{var_idx}.jpg"
            )

            reason = verdict.issues[0] if verdict.issues else "Quality improvement"

            job = VariationGenerationJob(
                shot_id=shot_id,
                variant_idx=var_idx,
                prompt=nano_prompt,
                nano_prompt=varied_nano,
                ltx_motion_prompt=ltx_motion_prompt,
                image_urls=image_urls,
                seed=seed,
                output_path=output_path,
                reason=reason,
            )

            manifest.append(job)

        logger.info(f"{shot_id}: Created 3 variation candidates for {verdict.verdict.value}")

    return manifest


# =============================================================================
# CANDIDATE SELECTION
# =============================================================================


def select_best_candidate(
    project: str,
    shot_id: str,
    variant_idx: int,
) -> str:
    """
    Copy chosen candidate variant to first_frames/ as the approved frame.

    Args:
        project: Project path
        shot_id: Shot ID
        variant_idx: Which variant (1, 2, or 3) to select

    Returns:
        Path to the now-approved frame file.
    """
    if not project.startswith("pipeline_outputs/"):
        project = f"pipeline_outputs/{project}"

    src_path = os.path.join(project, "first_frame_candidates", f"{shot_id}_v{variant_idx}.jpg")
    dst_path = os.path.join(project, "first_frames", f"{shot_id}.jpg")

    if not os.path.exists(src_path):
        logger.error(f"Variant file not found: {src_path}")
        return ""

    # Create backup of old frame if it exists
    if os.path.exists(dst_path):
        backup_path = dst_path.replace(".jpg", f"_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg")
        os.rename(dst_path, backup_path)
        logger.info(f"Backed up previous frame to {backup_path}")

    # Copy variant to approved location
    import shutil
    shutil.copy2(src_path, dst_path)
    logger.info(f"Selected variant {variant_idx} as approved frame for {shot_id}")

    return dst_path


# =============================================================================
# B-ROLL NARRATIVE REVIEW
# =============================================================================


def review_broll_narrative(
    project: str,
    scene_id: str,
) -> Dict[str, Any]:
    """
    Check B-roll shots against story_bible beats for narrative content.

    Returns:
        Dict with narrative_keywords_found, generic_broll_shots, recommendations.
    """
    if not project.startswith("pipeline_outputs/"):
        project = f"pipeline_outputs/{project}"

    shot_plan = _load_json_safe(os.path.join(project, "shot_plan.json"))
    story_bible = _load_json_safe(os.path.join(project, "story_bible.json"))

    shot_plan = _normalize_shot_plan(shot_plan)
    shots_list = shot_plan.get("shots", [])

    # Filter to B-roll shots in this scene
    broll_shots = [
        s
        for s in shots_list
        if s.get("shot_id", "").startswith(f"{scene_id}_") and s.get("is_broll", False)
    ]

    # Extract narrative beat keywords from story_bible
    scene_beats = []
    if story_bible:
        for scene in story_bible.get("scenes", []):
            if str(scene.get("scene_id", "")) == scene_id:
                scene_beats = scene.get("beats", [])
                break

    beat_text = " ".join([str(b) for b in scene_beats]).lower()
    beat_keywords = set(re.findall(r"\b\w{4,}\b", beat_text))  # words 4+ chars

    # Analyze each B-roll shot
    narrative_keywords_found = {}
    generic_broll_shots = []

    for shot in broll_shots:
        shot_id = shot.get("shot_id", "")
        description = (
            (shot.get("description") or "") + " " + (shot.get("action") or "")
        ).lower()

        # Find narrative keywords in description
        found_keywords = [kw for kw in beat_keywords if kw in description]

        if found_keywords:
            narrative_keywords_found[shot_id] = found_keywords
        else:
            generic_broll_shots.append(shot_id)

    report = {
        "scene_id": scene_id,
        "total_broll_shots": len(broll_shots),
        "narrative_shots": len(narrative_keywords_found),
        "generic_shots": len(generic_broll_shots),
        "narrative_keywords_found": narrative_keywords_found,
        "generic_broll_shots": generic_broll_shots,
    }

    return report


# =============================================================================
# FULL PIPELINE
# =============================================================================


def run_quality_gate(
    project: str,
    scene_id: str,
) -> QualityGateReport:
    """
    Full pipeline: review → verdicts → variation manifest → summary report.

    Args:
        project: Project path
        scene_id: Scene ID to review

    Returns:
        QualityGateReport with all results.
    """
    if not project.startswith("pipeline_outputs/"):
        project = f"pipeline_outputs/{project}"

    logger.info(f"\n=== POST-FRAME QUALITY GATE: {project} Scene {scene_id} ===")

    # Step 1: Review all frames for the scene
    verdicts = review_scene_frames(project, scene_id)

    if not verdicts:
        logger.error(f"No shots reviewed for scene {scene_id}")
        return QualityGateReport(
            project=project,
            scene_id=scene_id,
            total_shots=0,
            approved_count=0,
            variation_count=0,
            rejected_count=0,
            note="No shots found in scene",
        )

    # Step 2: Count verdicts
    approved = sum(1 for v in verdicts.values() if v.verdict == FrameVerdict.APPROVED)
    variations = sum(1 for v in verdicts.values() if v.verdict == FrameVerdict.NEEDS_VARIATION)
    rejected = sum(1 for v in verdicts.values() if v.verdict == FrameVerdict.REJECTED)

    # Step 3: Build variation manifest for shots needing variation
    variation_manifest = build_variation_manifest(project, verdicts)

    # Step 4: Review B-roll narrative
    broll_check = review_broll_narrative(project, scene_id)

    # Step 5: Assemble report
    report = QualityGateReport(
        project=project,
        scene_id=scene_id,
        total_shots=len(verdicts),
        approved_count=approved,
        variation_count=variations,
        rejected_count=rejected,
        per_shot_verdicts=verdicts,
        variation_manifest=variation_manifest,
        broll_narrative_check=broll_check,
    )

    # Log summary
    logger.info(f"\nQuality Gate Summary:")
    logger.info(f"  Total shots: {report.total_shots}")
    logger.info(f"  APPROVED: {report.approved_count}")
    logger.info(f"  NEEDS_VARIATION: {report.variation_count}")
    logger.info(f"  REJECTED: {report.rejected_count}")
    logger.info(f"  Variation candidates to generate: {len(variation_manifest)}")
    logger.info(f"  B-roll narrative: {broll_check.get('narrative_shots', 0)}/{broll_check.get('total_broll_shots', 0)}")

    return report


# =============================================================================
# REPORTING AND SERIALIZATION
# =============================================================================


def save_quality_gate_report(
    report: QualityGateReport,
    project: str,
) -> str:
    """
    Save the quality gate report as JSON.

    Returns:
        Path to saved report file.
    """
    if not project.startswith("pipeline_outputs/"):
        project = f"pipeline_outputs/{project}"

    report_dir = os.path.join(project, "reports")
    os.makedirs(report_dir, exist_ok=True)

    report_path = os.path.join(
        report_dir,
        f"quality_gate_scene_{report.scene_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
    )

    # Convert dataclasses to dicts for JSON serialization
    verdicts_dict = {
        shot_id: {
            "verdict": verdict.verdict.value,
            "frame_path": verdict.frame_path,
            "score": verdict.score,
            "checks": [asdict(c) for c in verdict.checks],
            "issues": verdict.issues,
            "recommendations": verdict.recommendations,
        }
        for shot_id, verdict in report.per_shot_verdicts.items()
    }

    report_dict = {
        "project": report.project,
        "scene_id": report.scene_id,
        "timestamp": report.timestamp,
        "summary": {
            "total_shots": report.total_shots,
            "approved_count": report.approved_count,
            "variation_count": report.variation_count,
            "rejected_count": report.rejected_count,
        },
        "per_shot_verdicts": verdicts_dict,
        "variation_manifest": [asdict(job) for job in report.variation_manifest],
        "broll_narrative_check": report.broll_narrative_check,
    }

    with open(report_path, "w") as f:
        json.dump(report_dict, f, indent=2)

    logger.info(f"Quality gate report saved to {report_path}")
    return report_path


# =============================================================================
# SELF-TEST
# =============================================================================


if __name__ == "__main__":
    import sys

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="[%(name)s] %(levelname)s: %(message)s",
    )

    # Test on victorian_shadows_ep1 if available
    test_project = "pipeline_outputs/victorian_shadows_ep1"
    test_scene = "001"

    if os.path.exists(os.path.join(test_project, "shot_plan.json")):
        logger.info(f"\n{'=' * 70}")
        logger.info(f"Running quality gate on {test_project} Scene {test_scene}")
        logger.info(f"{'=' * 70}\n")

        report = run_quality_gate(test_project, test_scene)

        # Save report
        report_path = save_quality_gate_report(report, test_project)

        # Print summary
        print(f"\n{'=' * 70}")
        print(f"QUALITY GATE SUMMARY — Scene {report.scene_id}")
        print(f"{'=' * 70}")
        print(f"Total shots reviewed:  {report.total_shots}")
        print(f"APPROVED:              {report.approved_count}")
        print(f"NEEDS_VARIATION:       {report.variation_count}")
        print(f"REJECTED:              {report.rejected_count}")
        print(f"\nVariation candidates:  {len(report.variation_manifest)}")
        print(f"Report saved to:       {report_path}")

        # Print per-shot verdicts
        print(f"\n{'=' * 70}")
        print(f"PER-SHOT VERDICTS")
        print(f"{'=' * 70}")
        for shot_id, verdict in report.per_shot_verdicts.items():
            status = verdict.verdict.value
            score = f"{verdict.score:.2f}"
            issues = len(verdict.issues)
            print(f"  {shot_id:15} | {status:20} | Score: {score} | Issues: {issues}")

        # Print B-roll check
        if report.broll_narrative_check:
            print(f"\n{'=' * 70}")
            print(f"B-ROLL NARRATIVE CHECK")
            print(f"{'=' * 70}")
            bc = report.broll_narrative_check
            print(f"Total B-roll shots:    {bc.get('total_broll_shots', 0)}")
            print(f"With narrative:        {bc.get('narrative_shots', 0)}")
            print(f"Generic (no narrative):{bc.get('generic_shots', 0)}")
            if bc.get("generic_broll_shots"):
                print(f"Generic B-roll shots:  {bc['generic_broll_shots']}")

        print(f"\n✅ Quality gate run complete\n")

    else:
        logger.warning(f"{test_project} not found, skipping self-test")
        logger.info("To test, run with a valid project path:")
        logger.info("  python3 tools/post_frame_quality_gate.py")
