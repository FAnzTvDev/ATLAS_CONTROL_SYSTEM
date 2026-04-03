#!/usr/bin/env python3
"""
V25.3 Editorial Intelligence — Research-Backed Cut/Hold/Overlay Decision Engine

BODY FUNCTION: The Editor's Cerebellum — Rhythm, Timing, Spatial Flow
Maps to the biological body like this:
  - Brain (Film Engine) decides WHAT to show
  - Eyes (Vision Analyst) verify what was shown
  - Cerebellum (THIS MODULE) decides WHEN to cut, hold, or overlay
  - Nervous System (Doctrine) validates the sequence is healthy

Five capabilities (expanded from 3):
1. FRAME REUSE: Same blocking + static character = reuse frame, skip FAL
2. B-ROLL OVERLAY: Cutaways play OVER dialogue audio (J-cut/L-cut support)
3. HOLD LOGIC: When NOT to cut — Hitchcock anticipation, Schoonmaker breathing room
4. CUT POINT SCORING: Murch's Rule of Six applied to every transition (NEW)
5. ASL GOVERNOR: Scene-level pacing enforced by genre/emotion targets (NEW)

Research Sources (synthesized March 2026):
  - Walter Murch, Rule of Six: emotion (51%), story, rhythm, eye-trace, planarity, 3D
  - Thelma Schoonmaker (Scorsese's editor): roughness over perfection, long takes for
    emotional gravity, cutting INTO action not away from it
  - Average Shot Length (ASL) by genre: Horror ~15.7s, Drama 4-6s, Action <2s, Thriller 3-5s
  - J-cuts and L-cuts: audio bridge across visual transitions — maps directly to B-roll overlay
  - Hitchcock anticipation: tension from holding, NOT from cutting — hold > cut when emotion builds
  - AI-specific gap workarounds: character drift mitigated by frame reuse, environment
    inconsistency mitigated by hold logic, temporal coherence via chained reframes

Architecture:
- Runs BEFORE generation (pre-gen intelligence)
- Scores every potential cut point using Murch's 6 criteria
- Enforces ASL targets per scene based on genre + emotion arc
- Tags shots with editorial metadata for generation filtering and stitch planning
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
import re
import logging

logger = logging.getLogger("editorial_intelligence")


# ============================================================
# MURCH'S RULE OF SIX — Cut Quality Scoring
# ============================================================
# Walter Murch's priority-weighted criteria for every edit point.
# Higher score = better cut. Scale: 0.0 to 1.0 per criterion.
# Weights from "In the Blink of an Eye" (2001), confirmed by
# StudioBinder analysis (2024).

MURCH_WEIGHTS = {
    "emotion":     0.51,   # Does the cut serve the emotion of the moment?
    "story":       0.23,   # Does it advance the story?
    "rhythm":      0.10,   # Does it happen at a rhythmically interesting point?
    "eye_trace":   0.07,   # Does the eye know where to look in the new shot?
    "planarity":   0.05,   # Does the new camera angle respect the 2D plane?
    "spatial":     0.04,   # Does it respect 3D spatial continuity?
}

# Emotion escalation pairs — cutting INTO escalation scores higher
EMOTION_ESCALATION = {
    ("neutral", "tension"): 0.8,
    ("tension", "fear"): 0.9,
    ("tension", "anger"): 0.85,
    ("neutral", "grief"): 0.7,
    ("grief", "revelation"): 0.95,   # The turn — highest cut value
    ("fear", "revelation"): 0.95,
    ("anger", "grief"): 0.8,
    ("neutral", "determination"): 0.75,
    ("love", "grief"): 0.9,          # Loss after connection
    ("revelation", "determination"): 0.85,
}

# Shot-size progression scoring (Schoonmaker principle: cut INTO action)
# Good progressions score high. Jump-cuts and same-size cuts score low.
SIZE_PROGRESSION_SCORE = {
    ("wide", "medium"):       0.9,   # Classic film grammar
    ("medium", "close_up"):   0.95,  # Push into emotion
    ("wide", "close_up"):     0.7,   # Jump but motivated by revelation
    ("close_up", "wide"):     0.65,  # Pull back — release
    ("close_up", "medium"):   0.6,   # Retreat — slightly awkward
    ("medium", "wide"):       0.5,   # Pull back — acceptable for geography
    ("wide", "wide"):         0.3,   # Same size = weak cut
    ("medium", "medium"):     0.35,  # Same size = weak cut
    ("close_up", "close_up"): 0.4,   # OK for dialogue ping-pong
}

# Coverage role transitions — how well does the editorial grammar flow?
COVERAGE_FLOW_SCORE = {
    ("A_GEOGRAPHY", "B_ACTION"):  0.9,   # Establish then act
    ("B_ACTION", "C_EMOTION"):    0.95,  # Act then feel
    ("A_GEOGRAPHY", "C_EMOTION"): 0.7,   # Establish then emote (skip action)
    ("C_EMOTION", "A_GEOGRAPHY"): 0.6,   # Feel then reestablish
    ("C_EMOTION", "B_ACTION"):    0.75,  # Feel then act
    ("B_ACTION", "A_GEOGRAPHY"):  0.5,   # Act then reestablish (pull back)
}


def _infer_emotion_from_prompt(shot: dict) -> str:
    """
    Infer dominant emotion from shot prompt text when emotion field is missing.

    This is how a real editor works — they READ the scene and FEEL the emotion,
    they don't look at a metadata field. The Murch scorer needs this because
    production shot plans rarely have explicit emotion tags.
    """
    # Check explicit fields first (emotion_level can be int, so str() it)
    explicit = str(shot.get("emotion") or shot.get("_emotion") or "").lower().strip()
    if explicit and explicit not in ("neutral", "none", ""):
        return explicit

    # Infer from prompt text
    nano = (shot.get("nano_prompt") or shot.get("nano_prompt_final") or "").lower()
    ltx = (shot.get("ltx_motion_prompt") or "").lower()
    combined = f"{nano} {ltx}"

    # Priority-ordered emotion detection (most specific first)
    EMOTION_MARKERS = [
        ("revelation", ["revelation", "shock", "discovers", "realization", "realizes",
                        "reveals", "uncovers", "truth dawns", "stunned"]),
        ("grief", ["grief", "sorrow", "mourning", "loss", "weeping", "tears",
                   "crying", "anguish", "heartbreak", "devastated"]),
        ("fear", ["fear", "terrified", "frightened", "scared", "panic",
                  "screams", "trembling", "backing away"]),
        ("anger", ["anger", "furious", "rage", "confrontation", "defiant",
                   "slams", "shouts", "livid", "snaps"]),
        ("dread", ["dread", "horror", "ominous", "foreboding", "menacing",
                   "dark", "sinister", "creeping", "looming", "shadows",
                   "eerie", "unsettling", "haunting"]),
        ("tension", ["tension", "tense", "uneasy", "nervous", "anxious",
                     "apprehensive", "suspicious", "wary", "guarded"]),
        ("determination", ["determination", "resolve", "decided", "firm",
                          "steely", "purposeful", "commanding"]),
        ("love", ["love", "tender", "gentle", "affection", "warmth",
                  "caring", "embrace", "intimate", "compassion"]),
    ]

    best_emo = "neutral"
    best_hits = 0
    for emo, markers in EMOTION_MARKERS:
        hits = sum(1 for m in markers if m in combined)
        if hits > best_hits:
            best_hits = hits
            best_emo = emo

    return best_emo


def score_cut_point(shot_a: dict, shot_b: dict) -> dict:
    """
    Score the quality of a cut between two consecutive shots using
    Murch's Rule of Six criteria.

    Returns dict with per-criterion scores and weighted total.
    Higher = better cut. Range: 0.0 to 1.0.

    CRITICAL: Uses emotion inference from prompts when emotion field is
    missing — the Murch scorer CANNOT function without emotion data (51% weight).
    """
    scores = {}

    # 1. EMOTION (51%) — Does the cut serve emotion?
    # V25.3: Infer from prompt text when explicit field missing
    emo_a = _infer_emotion_from_prompt(shot_a)
    emo_b = _infer_emotion_from_prompt(shot_b)
    emo_pair = (emo_a, emo_b)
    if emo_pair in EMOTION_ESCALATION:
        scores["emotion"] = EMOTION_ESCALATION[emo_pair]
    elif emo_a != emo_b:
        scores["emotion"] = 0.6   # Different emotion = some value
    else:
        scores["emotion"] = 0.3   # Same emotion = low cut value (consider holding)

    # 2. STORY (23%) — Does the cut advance the story?
    # Dialogue shots advance story. Action beats advance story.
    b_has_dialogue = bool(shot_b.get("dialogue_text") or shot_b.get("dialogue"))
    b_has_action = bool(shot_b.get("_beat_action") or shot_b.get("beat_desc")
                        or shot_b.get("beat_description"))
    if b_has_dialogue and b_has_action:
        scores["story"] = 0.9
    elif b_has_dialogue:
        scores["story"] = 0.8
    elif b_has_action:
        scores["story"] = 0.7
    else:
        scores["story"] = 0.4   # Atmosphere/insert — low story advancement

    # 3. RHYTHM (10%) — Is it at a rhythmically interesting point?
    # Duration-based: very short or very long shots break rhythm (intentionally)
    dur_a = float(shot_a.get("duration") or shot_a.get("duration_seconds") or 5)
    dur_b = float(shot_b.get("duration") or shot_b.get("duration_seconds") or 5)
    # Ideal rhythm: shots alternate between 3-6s range
    if 3.0 <= dur_a <= 6.0 and 3.0 <= dur_b <= 6.0:
        scores["rhythm"] = 0.8
    elif abs(dur_a - dur_b) > 4.0:
        scores["rhythm"] = 0.7   # Intentional tempo change = OK
    else:
        scores["rhythm"] = 0.5

    # 4. EYE TRACE (7%) — Does the eye know where to look?
    # Same character in both shots = eye stays in place = good
    chars_a = set(c if isinstance(c, str) else str(c) for c in (shot_a.get("characters") or []))
    chars_b = set(c if isinstance(c, str) else str(c) for c in (shot_b.get("characters") or []))
    if chars_a & chars_b:  # Shared characters
        scores["eye_trace"] = 0.85
    elif chars_b:
        scores["eye_trace"] = 0.5   # New character = eye must find them
    else:
        scores["eye_trace"] = 0.6   # B-roll/landscape = eye free to roam

    # 5. PLANARITY (5%) — Does it respect 2D screen plane?
    # Coverage role progression is a proxy for planarity
    role_a = (shot_a.get("coverage_role") or "").upper()
    role_b = (shot_b.get("coverage_role") or "").upper()
    role_pair = (role_a, role_b)
    if role_pair in COVERAGE_FLOW_SCORE:
        scores["planarity"] = COVERAGE_FLOW_SCORE[role_pair]
    else:
        scores["planarity"] = 0.5

    # 6. SPATIAL (4%) — 3D spatial continuity
    # Same location = spatial continuity preserved
    loc_a = (shot_a.get("location") or "").strip().lower()
    loc_b = (shot_b.get("location") or "").strip().lower()
    if loc_a == loc_b and loc_a:
        scores["spatial"] = 0.9
    elif not loc_a or not loc_b:
        scores["spatial"] = 0.5
    else:
        scores["spatial"] = 0.2   # Location change = spatial disruption

    # Weighted total
    total = sum(scores.get(k, 0) * w for k, w in MURCH_WEIGHTS.items())

    return {
        "scores": scores,
        "total": round(total, 3),
        "recommendation": "CUT" if total >= 0.55 else "HOLD",
        "emotion_pair": f"{emo_a}→{emo_b}",
    }


# ============================================================
# ASL GOVERNOR — Average Shot Length Enforcement
# ============================================================
# Genre-calibrated ASL targets from Filmmaker's Academy research,
# cross-referenced with Victorian Shadows target pacing.

ASL_TARGETS = {
    # genre: (min_asl, target_asl, max_asl) in seconds
    "gothic_horror":    (4.0, 6.5, 12.0),   # Slow burn, Victorian shadows sweet spot
    "horror":           (3.0, 5.5, 15.7),    # Can go very long for tension
    "drama":            (4.0, 5.5, 8.0),     # Character-driven pacing
    "thriller":         (2.5, 4.0, 6.0),     # Faster pacing
    "action":           (1.5, 2.5, 4.0),     # Rapid cuts
    "noir":             (3.5, 5.0, 8.0),     # Moody, atmospheric
    "period":           (4.0, 6.0, 10.0),    # Stately pacing
    "romance":          (4.0, 5.5, 8.0),     # Lingering shots
    "default":          (3.5, 5.0, 8.0),
}

# Emotion modifiers — some emotions DEMAND longer or shorter shots
EMOTION_ASL_MODIFIER = {
    "tension":      1.3,    # 30% longer — Hitchcock anticipation principle
    "dread":        1.4,    # Even longer — let the audience squirm
    "grief":        1.2,    # Schoonmaker: "let the face breathe"
    "anger":        0.8,    # Faster cuts when rage builds
    "revelation":   0.7,    # Quick cuts at the turn — information overload
    "fear":         0.9,    # Slightly faster than dread
    "determination": 1.0,   # Normal pacing
    "love":         1.15,   # Slightly lingering
    "neutral":      1.0,    # No modifier
}


def compute_scene_asl_target(scene_shots: list, genre: str = "gothic_horror",
                              dominant_emotion: str = "neutral") -> dict:
    """
    Compute the target ASL for a scene based on genre and emotional arc.

    Returns target ASL, current ASL, and per-shot duration recommendations.
    """
    if not scene_shots:
        return {"target_asl": 5.0, "current_asl": 0, "within_range": True, "adjustments": []}

    genre_key = genre.lower().replace(" ", "_")
    min_asl, target_asl, max_asl = ASL_TARGETS.get(genre_key, ASL_TARGETS["default"])

    # Apply emotion modifier
    modifier = EMOTION_ASL_MODIFIER.get(dominant_emotion.lower(), 1.0)
    target_asl = round(target_asl * modifier, 1)
    min_asl = round(min_asl * modifier, 1)
    max_asl = round(max_asl * modifier, 1)

    # Current ASL
    durations = [float(s.get("duration") or s.get("duration_seconds") or 5) for s in scene_shots]
    current_asl = round(sum(durations) / len(durations), 1) if durations else 0

    within_range = min_asl <= current_asl <= max_asl

    # Per-shot recommendations
    adjustments = []
    for i, shot in enumerate(scene_shots):
        dur = durations[i]
        sid = shot.get("shot_id", f"shot_{i}")

        if dur < min_asl * 0.6:
            adjustments.append({
                "shot_id": sid,
                "current": dur,
                "suggested": round(target_asl * 0.8, 1),
                "reason": f"Too short ({dur}s) for {genre} pacing — extend to {round(target_asl * 0.8, 1)}s",
            })
        elif dur > max_asl * 1.5:
            adjustments.append({
                "shot_id": sid,
                "current": dur,
                "suggested": round(target_asl * 1.2, 1),
                "reason": f"Very long ({dur}s) — consider splitting or trimming to {round(target_asl * 1.2, 1)}s",
            })

    return {
        "genre": genre,
        "emotion": dominant_emotion,
        "target_asl": target_asl,
        "current_asl": current_asl,
        "min_asl": min_asl,
        "max_asl": max_asl,
        "within_range": within_range,
        "shot_count": len(scene_shots),
        "total_duration": round(sum(durations), 1),
        "adjustments": adjustments,
    }


# ============================================================
# AI-SPECIFIC EDITORIAL WORKAROUNDS
# ============================================================
# Maps known AI video generation failures to editorial solutions.
# These are NOT compromises — they're how real editors handle similar
# problems with practical footage (shaky takes, missed focus, etc.)

AI_GAP_WORKAROUNDS = {
    "character_drift": {
        "problem": "AI-generated characters change appearance across shots",
        "editorial_solution": "frame_reuse",
        "logic": "Reuse frames where character blocking hasn't changed — "
                 "identical pixels = zero drift. Real editors do this with "
                 "multi-camera setups (use cam A angle when cam B drifted).",
    },
    "environment_inconsistency": {
        "problem": "Background/environment changes between shots",
        "editorial_solution": "hold_extend",
        "logic": "Hold on a verified-good shot rather than cutting to a new "
                 "generation where the environment might shift. Hitchcock used "
                 "this — extended takes in Rope specifically to avoid cut-induced "
                 "continuity errors.",
    },
    "temporal_coherence": {
        "problem": "Motion doesn't flow naturally across cut points",
        "editorial_solution": "overlay_broll",
        "logic": "When motion doesn't match across a cut, insert a cutaway "
                 "(B-roll overlay). The audience's brain fills in the motion gap. "
                 "Every editor uses this — it's called a 'cheat cut'. The cutaway "
                 "resets the audience's spatial memory.",
    },
    "morphing_artifacts": {
        "problem": "Face/body morphing during video generation",
        "editorial_solution": "hold_extend",
        "logic": "If a 5-second video morphs at second 3, trim to 2.5s and hold. "
                 "Better to have a clean 2.5s than a full 5s with artifacts. "
                 "Real editors trim around flubbed takes daily.",
    },
    "dialogue_lip_sync": {
        "problem": "Lip movement doesn't match dialogue timing",
        "editorial_solution": "overlay_broll",
        "logic": "Cut away to listener reaction, environment, or insert detail "
                 "during the worst sync moments. Audio continues while visuals "
                 "are elsewhere. This is literally why J-cuts and L-cuts exist.",
    },
}


# ============================================================
# J-CUT / L-CUT MARKERS
# ============================================================
# J-cut: audio from NEXT shot starts before the visual cut
# L-cut: audio from CURRENT shot continues after the visual cut
# Both are B-roll overlay types — the audio bridge smooths the transition.

def classify_audio_transition(shot_a: dict, shot_b: dict) -> str:
    """
    Classify the ideal audio transition between two shots.

    Returns: "j_cut", "l_cut", "straight_cut", or "no_audio"
    """
    a_has_dialogue = bool(shot_a.get("dialogue_text") or shot_a.get("dialogue"))
    b_has_dialogue = bool(shot_b.get("dialogue_text") or shot_b.get("dialogue"))
    b_is_broll = bool(shot_b.get("_broll") or shot_b.get("_no_chain", False))  # V26 DOCTRINE: suffixes are editorial, not runtime

    # B-roll between dialogue shots = L-cut (current dialogue continues over B-roll)
    if a_has_dialogue and b_is_broll:
        return "l_cut"

    # B-roll BEFORE dialogue = J-cut (next dialogue starts early)
    a_is_broll = bool(shot_a.get("_broll") or shot_a.get("_no_chain", False))  # V26 DOCTRINE: suffixes are editorial, not runtime
    if a_is_broll and b_has_dialogue:
        return "j_cut"

    # Reaction shot after dialogue = L-cut (dialogue resonates over reaction)
    if a_has_dialogue and not b_has_dialogue:
        b_prompt = (shot_b.get("nano_prompt") or "").lower()
        if any(w in b_prompt for w in ["reacts", "reaction", "listens", "absorbs"]):
            return "l_cut"

    # Dialogue to dialogue = straight cut (standard cross-cutting)
    if a_has_dialogue and b_has_dialogue:
        return "straight_cut"

    return "no_audio"


# ============================================================
# EDITORIAL DECISIONS
# ============================================================

@dataclass
class EditorialDecision:
    """One editorial decision about a shot."""
    shot_id: str
    decision: str  # "reuse_frame", "overlay_broll", "hold_extend", "generate_new"
    reason: str
    source_shot_id: Optional[str] = None  # For reuse/overlay — which shot to reference
    hold_seconds: float = 0.0  # For hold_extend
    confidence: float = 0.0  # 0-1 how confident we are


@dataclass
class EditorialPlan:
    """Full editorial plan for a scene."""
    scene_id: str
    decisions: List[EditorialDecision] = field(default_factory=list)
    frames_saved: int = 0  # How many frames we DON'T need to generate
    total_shots: int = 0
    reuse_count: int = 0
    overlay_count: int = 0
    hold_count: int = 0


# ============================================================
# BLOCKING ANALYSIS — Is the character actually moving?
# ============================================================

STATIC_INDICATORS = {
    # Postures that mean "not moving"
    "standing", "sitting", "seated", "leaning", "lying",
    "kneeling", "crouching", "frozen", "still", "motionless",
    "stationary", "rigid", "fixed", "rooted", "planted",
}

MOVEMENT_INDICATORS = {
    # Actions that mean "character is physically relocating"
    "walks", "walking", "enters", "entering", "exits", "exiting",
    "crosses", "crossing", "runs", "running", "moves", "moving",
    "stands up", "sits down", "turns around", "spins", "falls",
    "collapses", "jumps", "leaps", "lunges", "charges", "retreats",
    "approaches", "leaves", "storms", "rushes", "stumbles",
    "climbs", "descends", "rises", "drops", "steps",
}

# Shot types where the CAMERA moves enough to need new framing
CAMERA_MOVEMENT_TYPES = {
    "tracking", "dolly", "crane", "steadicam", "handheld",
}

# Shot types that are inherently static (camera doesn't move much)
STATIC_SHOT_TYPES = {
    "close_up", "medium", "medium_close_up", "extreme_close_up",
    "over_the_shoulder", "two_shot",
}


def _is_character_static(shot: dict) -> bool:
    """
    Determine if the character in this shot is essentially stationary.
    Checks nano_prompt and ltx_motion_prompt for movement vs static indicators.
    """
    nano = (shot.get("nano_prompt") or shot.get("nano_prompt_final") or "").lower()
    ltx = (shot.get("ltx_motion_prompt") or "").lower()
    combined = f"{nano} {ltx}"

    # Count movement vs static indicators
    movement_hits = sum(1 for m in MOVEMENT_INDICATORS if m in combined)
    static_hits = sum(1 for s in STATIC_INDICATORS if s in combined)

    # If dialogue shot with no explicit movement, character is likely static
    has_dialogue = bool(shot.get("dialogue_text") or shot.get("dialogue"))
    if has_dialogue and movement_hits == 0:
        return True

    # More static indicators than movement = static
    if static_hits > movement_hits:
        return True

    # No movement words at all = static
    if movement_hits == 0:
        return True

    return False


def _same_blocking(shot_a: dict, shot_b: dict) -> bool:
    """
    Do these two shots have the same blocking setup?
    Same characters, same location, same general framing.
    """
    # Same characters?
    chars_a = set(c if isinstance(c, str) else str(c)
                  for c in (shot_a.get("characters") or []))
    chars_b = set(c if isinstance(c, str) else str(c)
                  for c in (shot_b.get("characters") or []))
    if chars_a != chars_b:
        return False

    # Same location?
    loc_a = (shot_a.get("location") or "").strip().lower()
    loc_b = (shot_b.get("location") or "").strip().lower()
    if loc_a != loc_b and loc_a and loc_b:
        return False

    # Same scene?
    scene_a = shot_a.get("scene_id", shot_a.get("shot_id", "").split("_")[0])
    scene_b = shot_b.get("scene_id", shot_b.get("shot_id", "").split("_")[0])
    if str(scene_a) != str(scene_b):
        return False

    return True


def _is_same_framing(shot_a: dict, shot_b: dict) -> bool:
    """
    Are these shots essentially the same camera setup?
    Same shot_type AND same coverage_role = same framing.
    """
    type_a = (shot_a.get("shot_type") or "").lower()
    type_b = (shot_b.get("shot_type") or "").lower()

    role_a = (shot_a.get("coverage_role") or "").upper()
    role_b = (shot_b.get("coverage_role") or "").upper()

    # Exact match on both
    if type_a == type_b and role_a == role_b:
        return True

    # Close enough — both are close-up variants
    close_types = {"close_up", "close-up", "mcu", "medium_close_up", "extreme_close_up"}
    if type_a in close_types and type_b in close_types:
        return True

    return False


# ============================================================
# FRAME REUSE ANALYSIS
# ============================================================

def analyze_frame_reuse(shots: List[dict]) -> List[EditorialDecision]:
    """
    Analyze consecutive shots for frame reuse opportunities.

    Rules:
    1. Same blocking (characters + location + scene) = candidate
    2. Character is static in BOTH shots = strong candidate
    3. Same framing (shot_type + coverage_role) = definite reuse
    4. Different framing but same blocking = end-frame chain (not reuse)
    5. NEVER reuse across scenes
    6. NEVER reuse if either shot has explicit movement

    Returns list of EditorialDecisions for shots that can reuse frames.
    """
    decisions = []

    for i in range(1, len(shots)):
        prev = shots[i - 1]
        curr = shots[i]

        prev_id = prev.get("shot_id", f"shot_{i-1}")
        curr_id = curr.get("shot_id", f"shot_{i}")

        # Skip B-roll — handled separately
        if curr.get("_broll") or curr.get("_no_chain", False):  # V26 DOCTRINE: suffixes are editorial, not runtime
            continue

        # Must be same blocking setup
        if not _same_blocking(prev, curr):
            continue

        # Both characters must be static
        if not _is_character_static(prev) or not _is_character_static(curr):
            continue

        # Same framing = definite frame reuse
        if _is_same_framing(prev, curr):
            decisions.append(EditorialDecision(
                shot_id=curr_id,
                decision="reuse_frame",
                source_shot_id=prev_id,
                reason=f"Same blocking, same framing, character static — reuse frame from {prev_id}",
                confidence=0.9,
            ))
        else:
            # Different framing but same blocking — end-frame chain handles this already
            # Just note it as a recommendation
            decisions.append(EditorialDecision(
                shot_id=curr_id,
                decision="chain_preferred",
                source_shot_id=prev_id,
                reason=f"Same blocking, different framing — end-frame chain from {prev_id} is optimal",
                confidence=0.7,
            ))

    return decisions


# ============================================================
# B-ROLL OVERLAY ANALYSIS
# ============================================================

def analyze_broll_overlays(shots: List[dict]) -> List[EditorialDecision]:
    """
    Identify B-roll shots that should overlay continuing dialogue.

    Pattern detected:
    [dialogue_shot_A] → [B-roll] → [dialogue_shot_B or continuation]

    If B-roll sits between two dialogue shots of the same character in the
    same location, it's a CUTAWAY — the audio from the surrounding dialogue
    should continue while the B-roll visuals play.

    Tags:
    _overlay_on: the dialogue shot this B-roll plays over
    _overlay_type: "cutaway" | "insert" | "reaction"
    """
    decisions = []

    for i, shot in enumerate(shots):
        sid = shot.get("shot_id", "")
        is_broll = bool(shot.get("_broll") or shot.get("_no_chain", False))  # V26 DOCTRINE: suffixes are editorial, not runtime

        if not is_broll:
            continue

        # Look at the shot BEFORE and AFTER this B-roll
        prev_shot = shots[i - 1] if i > 0 else None
        next_shot = shots[i + 1] if i < len(shots) - 1 else None

        # Is the previous shot a dialogue shot?
        prev_has_dialogue = False
        if prev_shot:
            prev_has_dialogue = bool(
                prev_shot.get("dialogue_text") or prev_shot.get("dialogue")
            )

        # Is the next shot from the same character/location?
        next_continues = False
        if next_shot and prev_shot:
            next_continues = _same_blocking(prev_shot, next_shot)

        # PATTERN: dialogue → B-roll → same blocking = CUTAWAY OVERLAY
        if prev_has_dialogue and prev_shot:
            prev_id = prev_shot.get("shot_id", "")

            # Determine overlay type
            shot_type = (shot.get("shot_type") or "").lower()
            if shot_type in ("insert", "detail", "extreme_close_up"):
                overlay_type = "insert"
            elif any(c in (shot.get("nano_prompt") or "").lower()
                     for c in ["reaction", "listens", "reacts"]):
                overlay_type = "reaction"
            else:
                overlay_type = "cutaway"

            confidence = 0.85 if next_continues else 0.65

            decisions.append(EditorialDecision(
                shot_id=sid,
                decision="overlay_broll",
                source_shot_id=prev_id,
                reason=f"B-roll {overlay_type} over {prev_id} dialogue — audio continues from {prev_id}",
                confidence=confidence,
            ))

    return decisions


# ============================================================
# HOLD-ON-SHOT ANALYSIS
# ============================================================

# Minimum words-per-second for dialogue (generous — allows pauses)
WORDS_PER_SECOND = 2.0
# How much extra time to allow for reaction/pause
REACTION_BUFFER = 1.5

def analyze_hold_opportunities(shots: List[dict]) -> List[EditorialDecision]:
    """
    Find shots where HOLDING is better than CUTTING.

    Situations where hold is better:
    1. Dialogue shot where the character finishes speaking and emotion lingers
    2. Reaction shot after receiving information — audience needs to see the face
    3. Character is completely still — generating new video adds nothing
    4. Two consecutive shots of same static setup — second one is wasted

    Tags:
    _hold_extension: seconds to add to the PREVIOUS shot instead of generating
    """
    decisions = []

    for i in range(1, len(shots)):
        prev = shots[i - 1]
        curr = shots[i]

        prev_id = prev.get("shot_id", "")
        curr_id = curr.get("shot_id", "")

        # Skip B-roll — has its own logic
        if curr.get("_broll") or curr.get("_no_chain", False):  # V26 DOCTRINE: suffixes are editorial, not runtime
            continue

        # Case 1: Same framing, same blocking, both static = HOLD instead of cut
        if (_same_blocking(prev, curr) and
            _is_same_framing(prev, curr) and
            _is_character_static(prev) and
            _is_character_static(curr)):

            curr_duration = float(curr.get("duration") or curr.get("duration_seconds") or 4)

            # If the "new" shot is short (under 5s) AND same setup, just hold
            if curr_duration <= 5.0:
                decisions.append(EditorialDecision(
                    shot_id=curr_id,
                    decision="hold_extend",
                    source_shot_id=prev_id,
                    hold_seconds=curr_duration,
                    reason=f"Same framing, static character — hold {prev_id} for {curr_duration}s instead of cutting",
                    confidence=0.8,
                ))

        # Case 2: Reaction shot after dialogue — let the face breathe
        prev_has_dialogue = bool(prev.get("dialogue_text") or prev.get("dialogue"))
        curr_is_reaction = any(w in (curr.get("nano_prompt") or "").lower()
                               for w in ["reacts", "reaction", "listens", "absorbs", "processes"])

        if prev_has_dialogue and curr_is_reaction and _same_blocking(prev, curr):
            # Don't eliminate the reaction shot — but flag that the previous
            # shot could be extended to include the reaction beat
            decisions.append(EditorialDecision(
                shot_id=curr_id,
                decision="hold_extend",
                source_shot_id=prev_id,
                hold_seconds=REACTION_BUFFER,
                reason=f"Reaction beat — could extend {prev_id} by {REACTION_BUFFER}s instead of cutting to reaction shot",
                confidence=0.6,  # Lower confidence — reaction cuts ARE valid editorial choices
            ))

    return decisions


# ============================================================
# FULL EDITORIAL PLAN
# ============================================================

def build_editorial_plan(shots: List[dict], scene_id: str = "",
                         genre: str = "gothic_horror") -> EditorialPlan:
    """
    Build a complete editorial plan for a scene (or all shots).

    Five analysis passes (expanded from 3):
    1. Frame reuse opportunities (blocking + static analysis)
    2. B-roll overlay candidates (J/L cut classification)
    3. Hold-vs-cut decisions (Murch scoring + Hitchcock anticipation)
    4. Cut point quality scoring (Rule of Six per transition)
    5. ASL governance (genre + emotion target enforcement)

    The plan is ADVISORY — it produces tags and recommendations, but
    the pipeline decides what to act on. Non-blocking by design.
    """
    plan = EditorialPlan(scene_id=scene_id, total_shots=len(shots))

    # Run all analyses
    reuse_decisions = analyze_frame_reuse(shots)
    overlay_decisions = analyze_broll_overlays(shots)
    hold_decisions = analyze_hold_opportunities(shots)

    # NEW: Score every cut point with Murch's Rule of Six
    cut_scores = []
    for i in range(1, len(shots)):
        cut_score = score_cut_point(shots[i - 1], shots[i])
        cut_scores.append({
            "from": shots[i - 1].get("shot_id", ""),
            "to": shots[i].get("shot_id", ""),
            **cut_score,
        })
        # If Murch says HOLD and confidence is high, reinforce hold decisions
        if cut_score["recommendation"] == "HOLD" and cut_score["total"] < 0.45:
            # Check if there's already a hold decision for this shot
            to_id = shots[i].get("shot_id", "")
            existing_hold = any(d.shot_id == to_id and d.decision == "hold_extend"
                               for d in hold_decisions)
            if not existing_hold and _is_character_static(shots[i]):
                hold_decisions.append(EditorialDecision(
                    shot_id=to_id,
                    decision="hold_extend",
                    source_shot_id=shots[i - 1].get("shot_id", ""),
                    hold_seconds=float(shots[i].get("duration") or 4),
                    reason=f"Murch score {cut_score['total']:.2f} — weak cut, hold {shots[i-1].get('shot_id', '')} instead",
                    confidence=0.7,
                ))

    # NEW: Classify audio transitions for overlay shots
    for d in overlay_decisions:
        # Find the shots involved
        source_idx = next((j for j, s in enumerate(shots) if s.get("shot_id") == d.source_shot_id), None)
        target_idx = next((j for j, s in enumerate(shots) if s.get("shot_id") == d.shot_id), None)
        if source_idx is not None and target_idx is not None:
            audio_type = classify_audio_transition(shots[source_idx], shots[target_idx])
            d.reason += f" [{audio_type}]"

    # NEW: ASL analysis for the scene — uses inferred emotion from prompts
    dominant_emotion = "neutral"
    from collections import Counter as _Counter
    _scene_emotions = [_infer_emotion_from_prompt(s) for s in shots]
    _emo_counts = _Counter(e for e in _scene_emotions if e != "neutral")
    if _emo_counts:
        dominant_emotion = _emo_counts.most_common(1)[0][0]
    asl_report = compute_scene_asl_target(shots, genre, dominant_emotion)

    # Merge — reuse and overlay take priority over hold
    seen_shots = set()

    for d in reuse_decisions:
        if d.decision == "reuse_frame":
            plan.decisions.append(d)
            plan.reuse_count += 1
            plan.frames_saved += 1
            seen_shots.add(d.shot_id)
        else:
            plan.decisions.append(d)

    for d in overlay_decisions:
        plan.decisions.append(d)
        plan.overlay_count += 1
        seen_shots.add(d.shot_id)

    for d in hold_decisions:
        if d.shot_id not in seen_shots:
            plan.decisions.append(d)
            plan.hold_count += 1

    # Attach enriched metadata to plan
    plan._cut_scores = cut_scores
    plan._asl_report = asl_report
    plan._ai_workarounds_applied = []

    # Check for AI-specific workarounds that may apply
    for shot in shots:
        sid = shot.get("shot_id", "")
        if sid in seen_shots:
            continue
        # Character drift risk: dialogue shots that will be regenerated
        has_dialogue = bool(shot.get("dialogue_text") or shot.get("dialogue"))
        if has_dialogue and not shot.get("_editorial_skip_gen"):
            plan._ai_workarounds_applied.append({
                "shot_id": sid,
                "risk": "dialogue_lip_sync",
                "mitigation": "Overlay B-roll if sync fails post-generation",
            })

    return plan


def apply_editorial_tags(shots: List[dict], plan: EditorialPlan) -> int:
    """
    Apply editorial intelligence tags to shots in-place.

    Tags added:
    - _reuse_frame_from: shot_id to copy frame from (skip FAL generation)
    - _overlay_on: dialogue shot this B-roll plays over
    - _overlay_type: cutaway | insert | reaction
    - _hold_extension: seconds the previous shot should extend
    - _editorial_reason: human-readable explanation
    - _editorial_skip_gen: True if this shot doesn't need frame generation

    Returns number of shots tagged.
    """
    shot_map = {s.get("shot_id", ""): s for s in shots}
    tagged = 0

    for decision in plan.decisions:
        shot = shot_map.get(decision.shot_id)
        if not shot:
            continue

        if decision.decision == "reuse_frame":
            shot["_reuse_frame_from"] = decision.source_shot_id
            shot["_editorial_skip_gen"] = True
            shot["_editorial_reason"] = decision.reason
            tagged += 1

        elif decision.decision == "overlay_broll":
            shot["_overlay_on"] = decision.source_shot_id
            # Parse overlay type from reason
            if "insert" in decision.reason:
                shot["_overlay_type"] = "insert"
            elif "reaction" in decision.reason:
                shot["_overlay_type"] = "reaction"
            else:
                shot["_overlay_type"] = "cutaway"
            shot["_editorial_reason"] = decision.reason
            tagged += 1

        elif decision.decision == "hold_extend":
            shot["_hold_extension"] = decision.hold_seconds
            shot["_hold_source"] = decision.source_shot_id
            shot["_editorial_reason"] = decision.reason
            # High confidence holds can skip generation
            if decision.confidence >= 0.8:
                shot["_editorial_skip_gen"] = True
            tagged += 1

    return tagged


# ============================================================
# STITCH INTEGRATION — FFmpeg overlay support
# ============================================================

def build_overlay_stitch_plan(shots: List[dict]) -> List[dict]:
    """
    Build a stitch plan that handles overlays.

    Normal shots: sequential concat (current behavior)
    Overlay shots: B-roll visuals over dialogue audio

    Returns list of stitch entries:
    {
        "shot_id": "003_002B",
        "type": "overlay" | "sequential",
        "video_path": "path/to/video.mp4",
        "overlay_on": "003_001C",    # for overlays
        "overlay_start": 3.5,         # seconds into the base shot
        "overlay_duration": 2.5,      # how long the overlay lasts
    }
    """
    shot_map = {s.get("shot_id", ""): s for s in shots}
    plan = []

    for shot in shots:
        sid = shot.get("shot_id", "")

        if shot.get("_overlay_on"):
            # This is an overlay — plays OVER the base shot's audio
            base_id = shot["_overlay_on"]
            base_shot = shot_map.get(base_id, {})
            base_duration = float(base_shot.get("duration") or base_shot.get("duration_seconds") or 5)
            overlay_duration = float(shot.get("duration") or shot.get("duration_seconds") or 3)

            # Place overlay in the middle-to-end of the base shot
            # (editorial convention: cutaway after dialogue starts, not at the top)
            overlay_start = max(1.5, base_duration - overlay_duration - 0.5)

            plan.append({
                "shot_id": sid,
                "type": "overlay",
                "overlay_on": base_id,
                "overlay_start": round(overlay_start, 1),
                "overlay_duration": round(overlay_duration, 1),
            })

        elif shot.get("_editorial_skip_gen") and shot.get("_reuse_frame_from"):
            # Reused frame — sequential but skip generation
            plan.append({
                "shot_id": sid,
                "type": "reuse",
                "reuse_from": shot["_reuse_frame_from"],
            })

        elif shot.get("_hold_extension") and shot.get("_editorial_skip_gen"):
            # Hold extension — extend previous shot, skip this one
            plan.append({
                "shot_id": sid,
                "type": "hold",
                "extend_shot": shot.get("_hold_source", ""),
                "extend_seconds": shot["_hold_extension"],
            })

        else:
            # Normal sequential shot
            plan.append({
                "shot_id": sid,
                "type": "sequential",
            })

    return plan


# ============================================================
# GENERATION FILTER — Skip shots that don't need new frames
# ============================================================

def filter_shots_for_generation(shots: List[dict]) -> Tuple[List[dict], List[dict]]:
    """
    Split shots into two lists:
    1. Shots that NEED new frame generation
    2. Shots that can REUSE existing frames

    Call this BEFORE generate-first-frames to skip unnecessary FAL calls.
    """
    need_generation = []
    skip_generation = []

    for shot in shots:
        if shot.get("_editorial_skip_gen"):
            skip_generation.append(shot)
            logger.info(f"[EDITORIAL] Skipping generation for {shot.get('shot_id')}: "
                        f"{shot.get('_editorial_reason', 'reuse/hold')}")
        else:
            need_generation.append(shot)

    if skip_generation:
        logger.info(f"[EDITORIAL] {len(skip_generation)} shots skipped, "
                    f"{len(need_generation)} shots need generation "
                    f"(saving ~{len(skip_generation) * 0.15:.0f} FAL credits)")

    return need_generation, skip_generation


def copy_reused_frames(shots: List[dict], project_path: str) -> int:
    """
    For shots tagged with _reuse_frame_from, copy the source frame.

    Returns number of frames copied.
    """
    import shutil
    from pathlib import Path

    project = Path(project_path)
    frames_dir = project / "first_frames"
    copied = 0

    shot_map = {s.get("shot_id", ""): s for s in shots}

    for shot in shots:
        source_id = shot.get("_reuse_frame_from")
        if not source_id:
            continue

        curr_id = shot.get("shot_id", "")
        source_shot = shot_map.get(source_id, {})

        # Find source frame path
        source_frame = source_shot.get("first_frame_path") or source_shot.get("first_frame_url")
        if not source_frame:
            # Try filesystem
            for ext in [".jpg", ".png", ".jpeg"]:
                candidate = frames_dir / f"{source_id}{ext}"
                if candidate.exists():
                    source_frame = str(candidate)
                    break

        if source_frame and not source_frame.startswith("http"):
            source_path = Path(source_frame)
            if source_path.exists():
                dest_path = frames_dir / f"{curr_id}{source_path.suffix}"
                shutil.copy2(str(source_path), str(dest_path))
                shot["first_frame_path"] = str(dest_path)
                shot["_reuse_applied"] = True
                copied += 1
                logger.info(f"[EDITORIAL] Copied frame {source_id} → {curr_id}")

    return copied


# ============================================================
# REPORT
# ============================================================

def editorial_report(plan: EditorialPlan) -> str:
    """Human-readable editorial intelligence report with Murch + ASL data."""
    lines = [
        f"EDITORIAL INTELLIGENCE — Scene {plan.scene_id or 'ALL'}",
        f"{'=' * 55}",
        f"Total shots: {plan.total_shots}",
        f"Frame reuse opportunities: {plan.reuse_count} (saves {plan.reuse_count} FAL calls)",
        f"B-roll overlays: {plan.overlay_count} (cutaways over dialogue)",
        f"Hold opportunities: {plan.hold_count} (extend instead of cut)",
        "",
    ]

    # ASL report
    asl = getattr(plan, '_asl_report', None)
    if asl:
        status = "WITHIN RANGE" if asl.get("within_range") else "OUT OF RANGE"
        lines.append(f"ASL GOVERNANCE ({asl.get('genre', 'default')}, emotion: {asl.get('emotion', 'neutral')}):")
        lines.append(f"  Current ASL: {asl.get('current_asl', 0)}s | Target: {asl.get('target_asl', 5)}s ({asl.get('min_asl', 3)}-{asl.get('max_asl', 8)}s) — {status}")
        if asl.get("adjustments"):
            for adj in asl["adjustments"][:5]:  # Show max 5
                lines.append(f"    {adj['shot_id']}: {adj['reason']}")
        lines.append("")

    # Cut quality scores (show worst 5)
    cut_scores = getattr(plan, '_cut_scores', [])
    if cut_scores:
        weak_cuts = sorted(cut_scores, key=lambda x: x.get("total", 0))[:5]
        if weak_cuts and weak_cuts[0].get("total", 1) < 0.55:
            lines.append("WEAK CUT POINTS (Murch score < 0.55):")
            for cs in weak_cuts:
                if cs.get("total", 1) < 0.55:
                    lines.append(f"  {cs['from']} → {cs['to']}: {cs['total']:.2f} ({cs.get('recommendation', '')}) [{cs.get('emotion_pair', '')}]")
            lines.append("")

    # Editorial decisions
    lines.append("DECISIONS:")
    for d in plan.decisions:
        icon = {"reuse_frame": "♻️", "overlay_broll": "🎬",
                "hold_extend": "⏸️", "chain_preferred": "🔗"}.get(d.decision, "📋")
        lines.append(f"  {icon} {d.shot_id}: {d.reason}")
        if d.confidence < 0.7:
            lines.append(f"     ⚠️ Low confidence ({d.confidence:.0%}) — review recommended")

    # AI workarounds
    ai_workarounds = getattr(plan, '_ai_workarounds_applied', [])
    if ai_workarounds:
        lines.append("")
        lines.append(f"AI GAP MITIGATIONS ({len(ai_workarounds)} shots at risk):")
        for w in ai_workarounds[:10]:
            lines.append(f"  {w['shot_id']}: {w['risk']} — {w['mitigation']}")

    return "\n".join(lines)
