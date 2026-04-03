#!/usr/bin/env python3
"""
ATLAS V18.3 — Emotion Data Layer Agent
========================================

Structured, per-shot performance payload that sits between:
    Story Bible Beat → Prompt Builder → Video Render

Outputs BEHAVIOR, not emotion labels. Produces machine-injectable acting
direction for believable facial expression, body language, delivery,
and emotional transitions.

Design principle: Same pattern as wardrobe/extras — defaults by SCENE,
injection is NON-BLOCKING, auto-generated from beats + character profiles.

Core Objects:
  - EmotionState: what the character actually feels (primary/secondary/intensity/control)
  - ExpressionPlan: what the face DOES (muscle groups, asymmetry, microexpressions)
  - BodyPlan: physical acting (posture, hands, breath, movement)
  - DeliveryPlan: dialogue performance (pace, volume, tone, subtext)
  - ContinuityLocks: prevent emotion drift across shots

Files managed:
  pipeline_outputs/{project}/emotion_layer.json  — Per-character per-scene per-shot plans
  pipeline_outputs/{project}/character_profiles.json — Character emotional tendencies

Integration points:
  - Beat parse: creates default emotion state per beat
  - Shot assignment: refines per shot type
  - Prompt builder: injects compact ACTING block into LTX
  - LOA pre-gen: validates emotion continuity (non-blocking warning)
"""

import json
import os
import logging
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger("atlas.emotion_layer")

# ──────────────────────────────────────────────────────────────
# EMOTION TEMPLATE LIBRARY
# ──────────────────────────────────────────────────────────────

EMOTION_TEMPLATES = {
    "fear": {
        "primary": "fear", "secondary": "alertness",
        "intensity": 0.70, "valence": -0.65, "arousal": 0.80, "control": 0.40,
        "expression": {
            "brows": {"inner_up": 0.30, "down_draw": 0.05, "asymmetry": 0.10},
            "eyes": {"upper_lid_raise": 0.35, "lower_lid_tension": 0.25, "gaze_lock": 0.60},
            "mouth": {"lip_press": 0.10, "corner_pull": -0.15, "jaw_drop": 0.12},
            "blink": {"rate_per_10s": 2, "suppression": 0.50},
        },
        "body": {"posture": "retreating", "center_of_gravity": "back", "hands": "tremor_medium", "breath": "shallow_fast"},
    },
    "dread": {
        "primary": "fear", "secondary": "resignation",
        "intensity": 0.60, "valence": -0.70, "arousal": 0.45, "control": 0.70,
        "expression": {
            "brows": {"inner_up": 0.15, "down_draw": 0.10, "asymmetry": 0.12},
            "eyes": {"upper_lid_raise": 0.10, "lower_lid_tension": 0.30, "gaze_lock": 0.80},
            "mouth": {"lip_press": 0.20, "corner_pull": -0.08, "jaw_drop": 0.04},
            "blink": {"rate_per_10s": 1, "suppression": 0.70},
        },
        "body": {"posture": "contained", "center_of_gravity": "still", "hands": "tremor_low", "breath": "controlled_shallow"},
    },
    "ritual_focus": {
        "primary": "determination", "secondary": "dread",
        "intensity": 0.75, "valence": -0.30, "arousal": 0.55, "control": 0.85,
        "expression": {
            "brows": {"inner_up": 0.08, "down_draw": 0.15, "asymmetry": 0.06},
            "eyes": {"upper_lid_raise": 0.05, "lower_lid_tension": 0.20, "gaze_lock": 0.90},
            "mouth": {"lip_press": 0.25, "corner_pull": 0.0, "jaw_drop": 0.02},
            "blink": {"rate_per_10s": 1, "suppression": 0.80},
        },
        "body": {"posture": "centered", "center_of_gravity": "forward", "hands": "precise_steady", "breath": "deep_controlled"},
    },
    "grief": {
        "primary": "sadness", "secondary": "emptiness",
        "intensity": 0.80, "valence": -0.85, "arousal": 0.25, "control": 0.35,
        "expression": {
            "brows": {"inner_up": 0.40, "down_draw": 0.0, "asymmetry": 0.15},
            "eyes": {"upper_lid_raise": 0.0, "lower_lid_tension": 0.10, "gaze_lock": 0.20},
            "mouth": {"lip_press": 0.05, "corner_pull": -0.25, "jaw_drop": 0.08},
            "blink": {"rate_per_10s": 4, "suppression": 0.0},
        },
        "body": {"posture": "collapsed", "center_of_gravity": "down", "hands": "limp", "breath": "irregular_deep"},
    },
    "controlled_anger": {
        "primary": "anger", "secondary": "determination",
        "intensity": 0.75, "valence": -0.50, "arousal": 0.70, "control": 0.80,
        "expression": {
            "brows": {"inner_up": 0.0, "down_draw": 0.35, "asymmetry": 0.08},
            "eyes": {"upper_lid_raise": 0.0, "lower_lid_tension": 0.35, "gaze_lock": 0.95},
            "mouth": {"lip_press": 0.30, "corner_pull": -0.05, "jaw_drop": 0.0},
            "blink": {"rate_per_10s": 1, "suppression": 0.85},
        },
        "body": {"posture": "upright_rigid", "center_of_gravity": "forward", "hands": "clenched", "breath": "controlled_deep"},
    },
    "guarded_curiosity": {
        "primary": "curiosity", "secondary": "caution",
        "intensity": 0.50, "valence": 0.10, "arousal": 0.55, "control": 0.65,
        "expression": {
            "brows": {"inner_up": 0.20, "down_draw": 0.08, "asymmetry": 0.18},
            "eyes": {"upper_lid_raise": 0.15, "lower_lid_tension": 0.10, "gaze_lock": 0.50},
            "mouth": {"lip_press": 0.08, "corner_pull": 0.03, "jaw_drop": 0.05},
            "blink": {"rate_per_10s": 3, "suppression": 0.30},
        },
        "body": {"posture": "leaning_forward", "center_of_gravity": "forward", "hands": "exploratory", "breath": "normal"},
    },
    "resolve": {
        "primary": "determination", "secondary": "acceptance",
        "intensity": 0.70, "valence": 0.05, "arousal": 0.50, "control": 0.90,
        "expression": {
            "brows": {"inner_up": 0.05, "down_draw": 0.12, "asymmetry": 0.04},
            "eyes": {"upper_lid_raise": 0.0, "lower_lid_tension": 0.15, "gaze_lock": 0.85},
            "mouth": {"lip_press": 0.18, "corner_pull": 0.02, "jaw_drop": 0.0},
            "blink": {"rate_per_10s": 2, "suppression": 0.60},
        },
        "body": {"posture": "upright_centered", "center_of_gravity": "balanced", "hands": "steady", "breath": "deep_even"},
    },
    "shame": {
        "primary": "shame", "secondary": "vulnerability",
        "intensity": 0.65, "valence": -0.75, "arousal": 0.35, "control": 0.30,
        "expression": {
            "brows": {"inner_up": 0.25, "down_draw": 0.05, "asymmetry": 0.20},
            "eyes": {"upper_lid_raise": 0.0, "lower_lid_tension": 0.05, "gaze_lock": 0.10},
            "mouth": {"lip_press": 0.15, "corner_pull": -0.12, "jaw_drop": 0.03},
            "blink": {"rate_per_10s": 5, "suppression": 0.0},
        },
        "body": {"posture": "shoulders_forward", "center_of_gravity": "down", "hands": "self_touch", "breath": "shallow_irregular"},
    },
    "relief": {
        "primary": "relief", "secondary": "exhaustion",
        "intensity": 0.60, "valence": 0.50, "arousal": 0.30, "control": 0.20,
        "expression": {
            "brows": {"inner_up": 0.10, "down_draw": 0.0, "asymmetry": 0.08},
            "eyes": {"upper_lid_raise": 0.0, "lower_lid_tension": 0.0, "gaze_lock": 0.30},
            "mouth": {"lip_press": 0.0, "corner_pull": 0.10, "jaw_drop": 0.06},
            "blink": {"rate_per_10s": 4, "suppression": 0.0},
        },
        "body": {"posture": "releasing", "center_of_gravity": "settling", "hands": "opening", "breath": "long_exhale"},
    },
    "horror_realization": {
        "primary": "horror", "secondary": "disbelief",
        "intensity": 0.90, "valence": -0.90, "arousal": 0.85, "control": 0.15,
        "expression": {
            "brows": {"inner_up": 0.45, "down_draw": 0.0, "asymmetry": 0.05},
            "eyes": {"upper_lid_raise": 0.50, "lower_lid_tension": 0.30, "gaze_lock": 0.95},
            "mouth": {"lip_press": 0.0, "corner_pull": -0.20, "jaw_drop": 0.30},
            "blink": {"rate_per_10s": 0, "suppression": 1.0},
        },
        "body": {"posture": "frozen", "center_of_gravity": "locked", "hands": "frozen_mid_gesture", "breath": "held"},
    },
    "contained_neutral": {
        "primary": "neutral", "secondary": "watchfulness",
        "intensity": 0.45, "valence": 0.0, "arousal": 0.35, "control": 0.65,
        "expression": {
            "brows": {"inner_up": 0.05, "down_draw": 0.05, "asymmetry": 0.08},
            "eyes": {"upper_lid_raise": 0.05, "lower_lid_tension": 0.10, "gaze_lock": 0.50},
            "mouth": {"lip_press": 0.08, "corner_pull": 0.0, "jaw_drop": 0.0},
            "blink": {"rate_per_10s": 3, "suppression": 0.20},
        },
        "body": {"posture": "neutral_upright", "center_of_gravity": "balanced", "hands": "at_rest", "breath": "normal"},
    },
}

# ──────────────────────────────────────────────────────────────
# BEAT → EMOTION CLASSIFIER
# ──────────────────────────────────────────────────────────────

# Map beat keywords to emotion templates
BEAT_EMOTION_MAP = {
    # Threat / danger / unknown
    "threat": "fear", "danger": "fear", "lurk": "fear", "chase": "fear",
    "scream": "fear", "flee": "fear", "hide": "fear", "escape": "fear",
    # Dread / horror / occult
    "dread": "dread", "ominous": "dread", "foreboding": "dread",
    "horror": "horror_realization", "nightmare": "horror_realization",
    "occult": "ritual_focus", "ritual": "ritual_focus", "binding": "ritual_focus",
    "ceremony": "ritual_focus", "spell": "ritual_focus", "altar": "ritual_focus",
    "chant": "ritual_focus", "incantation": "ritual_focus",
    # Loss / grief
    "loss": "grief", "death": "grief", "mourn": "grief", "funeral": "grief",
    "weep": "grief", "cry": "grief", "grave": "grief", "coffin": "grief",
    # Anger / confrontation
    "confront": "controlled_anger", "argue": "controlled_anger", "accuse": "controlled_anger",
    "demand": "controlled_anger", "rage": "controlled_anger", "betray": "controlled_anger",
    # Revelation / surprise
    "discover": "horror_realization", "reveal": "horror_realization",
    "shock": "horror_realization", "realize": "horror_realization",
    # Investigation / curiosity
    "search": "guarded_curiosity", "investigate": "guarded_curiosity",
    "explore": "guarded_curiosity", "examine": "guarded_curiosity",
    "read": "guarded_curiosity", "study": "guarded_curiosity",
    # Resolution
    "resolve": "resolve", "decide": "resolve", "commit": "resolve",
    "vow": "resolve", "promise": "resolve", "protect": "resolve",
    # Shame / guilt
    "shame": "shame", "guilt": "shame", "regret": "shame", "confess": "shame",
    # Relief
    "relief": "relief", "safe": "relief", "rescue": "relief", "survive": "relief",
    # Darkness / environment
    "darkness": "dread", "candle": "dread", "blow": "horror_realization",
    "extinguish": "horror_realization", "plunge": "horror_realization",
}

# ──────────────────────────────────────────────────────────────
# SHOT TYPE MODIFIERS
# ──────────────────────────────────────────────────────────────

SHOT_TYPE_MODIFIERS = {
    "establishing": {
        "facial_intensity_mult": 0.0,  # No face in establishing
        "body_emphasis": 0.3,
        "microexpression_density": 0.0,
        "blink_control": False,
        "notes": "environment only, no facial performance required"
    },
    "wide": {
        "facial_intensity_mult": 0.5,
        "body_emphasis": 1.0,
        "microexpression_density": 0.3,
        "blink_control": False,
        "notes": "more body language, less facial detail visible"
    },
    "medium": {
        "facial_intensity_mult": 0.8,
        "body_emphasis": 0.7,
        "microexpression_density": 0.6,
        "blink_control": True,
        "notes": "balanced face and body"
    },
    "close-up": {
        "facial_intensity_mult": 1.0,
        "body_emphasis": 0.3,
        "microexpression_density": 1.0,
        "blink_control": True,
        "notes": "highest microexpression density, blink control critical"
    },
    "dialogue": {
        "facial_intensity_mult": 0.9,
        "body_emphasis": 0.5,
        "microexpression_density": 0.8,
        "blink_control": True,
        "notes": "face dominant, delivery plan required"
    },
    "reaction": {
        "facial_intensity_mult": 1.0,
        "body_emphasis": 0.4,
        "microexpression_density": 0.9,
        "blink_control": True,
        "notes": "pure facial performance, reaction microleaks"
    },
    "action": {
        "facial_intensity_mult": 0.6,
        "body_emphasis": 1.0,
        "microexpression_density": 0.4,
        "blink_control": False,
        "notes": "body-first, face secondary"
    },
    "insert": {
        "facial_intensity_mult": 0.0,
        "body_emphasis": 0.2,
        "microexpression_density": 0.0,
        "blink_control": False,
        "notes": "hands/objects, no face required"
    },
    "b-roll": {
        "facial_intensity_mult": 0.0,
        "body_emphasis": 0.0,
        "microexpression_density": 0.0,
        "blink_control": False,
        "notes": "environment only"
    },
    "over-the-shoulder": {
        "facial_intensity_mult": 0.7,
        "body_emphasis": 0.5,
        "microexpression_density": 0.7,
        "blink_control": True,
        "notes": "gaze lock + subtle jaw tension"
    },
}

# ──────────────────────────────────────────────────────────────
# CHARACTER PROFILES (emotional tendencies)
# ──────────────────────────────────────────────────────────────

DEFAULT_CHARACTER_PROFILES = {
    "LADY MARGARET RAVENCROFT": {
        "control_modifier": 0.85,  # High control — ritual precision
        "leak_tendency": 0.25,     # Low leak — microleaks under pressure only
        "dominant_emotion": "ritual_focus",
        "suppression_style": "compressed",  # Holds everything in, leaks through eyes
        "voice_quality": "measured_low",
        "physical_habit": "deliberate_precise"
    },
    "EVELYN": {
        "control_modifier": 0.55,
        "leak_tendency": 0.60,
        "dominant_emotion": "guarded_curiosity",
        "suppression_style": "partial",  # Tries to hide but fails
        "voice_quality": "clear_wavering",
        "physical_habit": "restless_hands"
    },
    "ARTHUR": {
        "control_modifier": 0.90,
        "leak_tendency": 0.15,
        "dominant_emotion": "contained_neutral",
        "suppression_style": "stoic",
        "voice_quality": "steady_deep",
        "physical_habit": "still_measured"
    },
    "ARTHUR GRAY": {
        "control_modifier": 0.90,
        "leak_tendency": 0.15,
        "dominant_emotion": "contained_neutral",
        "suppression_style": "stoic",
        "voice_quality": "steady_deep",
        "physical_habit": "still_measured"
    },
    "CLARA": {
        "control_modifier": 0.45,
        "leak_tendency": 0.65,
        "dominant_emotion": "guarded_curiosity",
        "suppression_style": "blunt",  # Says it straight, face matches words
        "voice_quality": "warm_direct",
        "physical_habit": "hands_busy"
    },
    "CLARA BYRNE": {
        "control_modifier": 0.45,
        "leak_tendency": 0.65,
        "dominant_emotion": "guarded_curiosity",
        "suppression_style": "blunt",
        "voice_quality": "warm_direct",
        "physical_habit": "hands_busy"
    },
    "LAWYER": {
        "control_modifier": 0.85,
        "leak_tendency": 0.20,
        "dominant_emotion": "contained_neutral",
        "suppression_style": "professional",  # Emotion stays behind the glasses
        "voice_quality": "measured_formal",
        "physical_habit": "paper_shuffling"
    },
    "DR. ELIAS WARD": {
        "control_modifier": 0.50,
        "leak_tendency": 0.55,
        "dominant_emotion": "guarded_curiosity",
        "suppression_style": "academic",  # Hides behind data, leaks through gestures
        "voice_quality": "scholarly_halting",
        "physical_habit": "fidgeting_glasses"
    },
    "EVELYN RAVENCROFT": {
        "control_modifier": 0.55,
        "leak_tendency": 0.60,
        "dominant_emotion": "guarded_curiosity",
        "suppression_style": "partial",
        "voice_quality": "clear_wavering",
        "physical_habit": "restless_hands"
    },
    "LADY MARGARET": {
        "control_modifier": 0.85,
        "leak_tendency": 0.25,
        "dominant_emotion": "ritual_focus",
        "suppression_style": "compressed",
        "voice_quality": "measured_low",
        "physical_habit": "deliberate_precise"
    },
}

# ──────────────────────────────────────────────────────────────
# MICROEXPRESSION PATTERNS
# ──────────────────────────────────────────────────────────────

MICROLEAK_PATTERNS = {
    "fear_flash": {"duration_s": 0.18, "description": "inner brows flash upward, eyes widen briefly"},
    "anger_leak": {"duration_s": 0.15, "description": "lip corner tightens, nostril flare micro-flash"},
    "grief_break": {"duration_s": 0.22, "description": "chin dimple quiver, eye moisture flash"},
    "contempt_tell": {"duration_s": 0.12, "description": "one corner lifts asymmetrically"},
    "surprise_flash": {"duration_s": 0.20, "description": "brows shoot up, mouth opens micro-beat"},
    "shame_avert": {"duration_s": 0.25, "description": "gaze drops, head micro-turn away"},
    "resolve_set": {"duration_s": 0.15, "description": "jaw sets, eyes narrow fractionally"},
    "dread_freeze": {"duration_s": 0.30, "description": "all motion stops, breath held, blink suspended"},
}


def classify_beat_emotion(beat_description: str, dialogue: str = "") -> str:
    """Classify a beat into an emotion template name."""
    text = f"{beat_description} {dialogue}".lower()
    scores = {}
    for keyword, emotion in BEAT_EMOTION_MAP.items():
        if keyword in text:
            scores[emotion] = scores.get(emotion, 0) + 1
    if scores:
        return max(scores, key=scores.get)
    # Default fallback
    return "contained_neutral"


def get_character_profile(character: str, project_path: str = "") -> Dict:
    """Get character emotional profile, checking project file first."""
    char_upper = character.upper().strip()
    # Check project-specific profiles
    if project_path:
        profile_path = Path(project_path) / "character_profiles.json"
        if profile_path.exists():
            try:
                with open(profile_path) as f:
                    profiles = json.load(f)
                for name, profile in profiles.items():
                    if name.upper().strip() == char_upper:
                        return profile
            except Exception:
                pass
    # Fall back to defaults
    for name, profile in DEFAULT_CHARACTER_PROFILES.items():
        if name == char_upper or char_upper in name or name in char_upper:
            return profile
    # Generic default
    return {
        "control_modifier": 0.60,
        "leak_tendency": 0.40,
        "dominant_emotion": "contained_neutral",
        "suppression_style": "partial",
        "voice_quality": "normal",
        "physical_habit": "natural"
    }


# ──────────────────────────────────────────────────────────────
# EMOTION STATE GENERATOR
# ──────────────────────────────────────────────────────────────

def generate_emotion_state(
    beat_description: str,
    dialogue: str,
    shot_type: str,
    character: str,
    duration: float,
    project_path: str = "",
) -> Dict[str, Any]:
    """
    Generate a complete emotion state for a shot.
    Returns: {emotion_state, expression_plan, body_plan, delivery_plan, continuity, acting_block}
    """
    # Step 1: Classify beat emotion
    emotion_name = classify_beat_emotion(beat_description, dialogue)
    template = EMOTION_TEMPLATES.get(emotion_name, EMOTION_TEMPLATES["contained_neutral"])

    # Step 2: Get character profile modifiers
    profile = get_character_profile(character, project_path)
    control_mod = profile.get("control_modifier", 0.60)

    # Step 3: Build EmotionState with character modifiers
    emotion_state = {
        "primary": template["primary"],
        "secondary": template["secondary"],
        "intensity": round(template["intensity"] * (0.8 + control_mod * 0.4), 2),
        "valence": template["valence"],
        "arousal": template["arousal"],
        "control": round(min(1.0, template["control"] * control_mod / 0.6), 2),
        "blend_mode": "layered" if control_mod > 0.7 else "conflicted",
        "template_used": emotion_name,
    }

    # Step 4: Get shot type modifier
    shot_mod = SHOT_TYPE_MODIFIERS.get(shot_type, SHOT_TYPE_MODIFIERS.get("medium", {}))
    facial_mult = shot_mod.get("facial_intensity_mult", 0.7)
    micro_density = shot_mod.get("microexpression_density", 0.5)

    # Step 5: Build ExpressionPlan (face) — only if shot type shows faces
    expression_plan = None
    if facial_mult > 0 and character:
        expr = template["expression"]
        expression_plan = {
            "brows": {
                "inner_up": round(expr["brows"]["inner_up"] * facial_mult, 2),
                "down_draw": round(expr["brows"]["down_draw"] * facial_mult, 2),
                "asymmetry": round(expr["brows"]["asymmetry"] * max(0.5, facial_mult), 2),
            },
            "eyes": {
                "upper_lid_raise": round(expr["eyes"]["upper_lid_raise"] * facial_mult, 2),
                "lower_lid_tension": round(expr["eyes"]["lower_lid_tension"] * facial_mult, 2),
                "gaze_lock": round(expr["eyes"]["gaze_lock"], 2),
            },
            "mouth": {
                "lip_press": round(expr["mouth"]["lip_press"] * facial_mult, 2),
                "corner_pull": round(expr["mouth"]["corner_pull"] * facial_mult, 2),
                "jaw_drop": round(expr["mouth"]["jaw_drop"] * facial_mult, 2),
            },
            "blink": {
                "rate_per_10s": expr["blink"]["rate_per_10s"],
                "suppression": round(expr["blink"]["suppression"] * control_mod, 2),
            },
        }
        # Add microexpressions based on density and duration
        if micro_density > 0.3 and duration >= 5:
            leak_tendency = profile.get("leak_tendency", 0.40)
            # Pick appropriate microleak
            microleak_type = _pick_microleak(emotion_name, template["primary"])
            microleak = MICROLEAK_PATTERNS.get(microleak_type, MICROLEAK_PATTERNS["fear_flash"])
            # Place microleak at ~20% into shot (before main action)
            start_s = round(duration * 0.15 + 0.5, 1)
            expression_plan["microexpressions"] = [{
                "type": microleak_type,
                "start_s": start_s,
                "duration_s": microleak["duration_s"],
                "strength": round(leak_tendency * micro_density, 2),
                "description": microleak["description"],
            }]

    # Step 6: Build BodyPlan
    body_template = template["body"]
    body_emphasis = shot_mod.get("body_emphasis", 0.5)
    body_plan = None
    if body_emphasis > 0 and character:
        body_plan = {
            "posture": body_template["posture"],
            "center_of_gravity": body_template["center_of_gravity"],
            "hands": body_template["hands"],
            "breath": body_template["breath"],
            "physical_habit": profile.get("physical_habit", "natural"),
            "emphasis": round(body_emphasis, 2),
        }

    # Step 7: Build DeliveryPlan (only for dialogue shots)
    delivery_plan = None
    if dialogue and character:
        delivery_plan = {
            "pace": "slow_controlled" if control_mod > 0.7 else "natural_rhythm",
            "volume": "low" if emotion_state["control"] > 0.6 else "medium",
            "tone": "restrained" if control_mod > 0.7 else "emotional",
            "breath_support": "tight" if emotion_state["control"] > 0.6 else "natural",
            "subtext": _generate_subtext(emotion_state, profile),
            "voice_quality": profile.get("voice_quality", "normal"),
        }

    # Step 8: Build ContinuityLocks
    continuity = {
        "identity_lock": True,
        "expression_lock_level": round(emotion_state["control"] * 0.8, 2),
        "wardrobe_lock": True,
        "emotion_carryover": "scene",
        "no_emotion_flip_without_beat": True,
    }

    # Step 9: Generate compact ACTING BLOCK for LTX injection
    acting_block = generate_acting_block(
        emotion_state, expression_plan, body_plan, delivery_plan,
        shot_type, character, duration
    )

    return {
        "emotion_state": emotion_state,
        "expression_plan": expression_plan,
        "body_plan": body_plan,
        "delivery_plan": delivery_plan,
        "continuity": continuity,
        "acting_block": acting_block,
        "shot_type_modifier": shot_mod.get("notes", ""),
    }


def _pick_microleak(emotion_name: str, primary: str) -> str:
    """Pick appropriate microleak type based on emotion."""
    mapping = {
        "fear": "fear_flash", "dread": "dread_freeze",
        "grief": "grief_break", "anger": "anger_leak",
        "horror": "fear_flash", "shame": "shame_avert",
        "curiosity": "surprise_flash", "determination": "resolve_set",
        "horror_realization": "fear_flash", "controlled_anger": "anger_leak",
        "ritual_focus": "dread_freeze", "resolve": "resolve_set",
        "guarded_curiosity": "surprise_flash", "relief": "grief_break",
        "contained_neutral": "resolve_set",
    }
    return mapping.get(emotion_name, mapping.get(primary, "fear_flash"))


def _generate_subtext(emotion_state: Dict, profile: Dict) -> str:
    """Generate subtext description for delivery plan."""
    primary = emotion_state["primary"]
    control = emotion_state["control"]
    suppression = profile.get("suppression_style", "partial")

    if control > 0.7:
        return f"feeling {primary} but refusing to show it — {suppression} suppression, truth leaks through eyes only"
    elif control > 0.4:
        return f"{primary} visible but held back — struggling to maintain composure"
    else:
        return f"{primary} openly expressed — overwhelmed, defenses down"


# ──────────────────────────────────────────────────────────────
# ACTING BLOCK GENERATOR (compact prompt format)
# ──────────────────────────────────────────────────────────────

def generate_acting_block(
    emotion_state: Dict,
    expression_plan: Optional[Dict],
    body_plan: Optional[Dict],
    delivery_plan: Optional[Dict],
    shot_type: str,
    character: str,
    duration: float,
) -> str:
    """
    Generate compact ACTING block for LTX prompt injection.
    This is the actual text injected into ltx_motion_prompt.

    V21.9.1: Uses semicolons instead of newlines as delimiters.
    Newlines were being destroyed by Prompt Authority Gate's regex
    (re.sub(r'\\s{2,}', ' ')), which collapsed the acting block into
    an unreadable mess and truncated float values (0.15s → 0.).
    Semicolons survive all regex passes and are readable by LTX.
    """
    parts = []

    # Emotion blend — the CORE acting direction
    primary = emotion_state.get("primary", "neutral")
    secondary = emotion_state.get("secondary", "")
    intensity = emotion_state.get("intensity", 0.5)
    control = emotion_state.get("control", 0.5)
    control_desc = "high control" if control > 0.7 else "moderate control" if control > 0.4 else "low control"
    blend = f"emotion blend: {primary} at intensity {intensity:.1f}"
    if secondary:
        blend += f" layered with {secondary}"
    blend += f", {control_desc}"
    parts.append(blend)

    # Expression (face) — only for shots with facial visibility
    if expression_plan:
        # Microexpressions — V21.9.1: use "Xs" not "X.Ys" to avoid decimal truncation
        micros = expression_plan.get("microexpressions", [])
        for m in micros:
            # Convert floats to integer milliseconds to avoid decimal destruction
            dur_ms = int(m['duration_s'] * 1000)
            start_ms = int(m['start_s'] * 1000)
            parts.append(f"microleak: {dur_ms}ms {m['type'].replace('_', ' ')} at {start_ms}ms then composure returns")

        # Brows
        brows = expression_plan.get("brows", {})
        brow_parts = []
        if brows.get("inner_up", 0) > 0.1:
            brow_parts.append("inner lift slight")
        if brows.get("down_draw", 0) > 0.1:
            brow_parts.append("brow draw")
        if brows.get("asymmetry", 0) > 0.05:
            brow_parts.append("asymmetry")
        if brow_parts:
            parts.append(f"brows: {', '.join(brow_parts)}")

        # Eyes
        eyes = expression_plan.get("eyes", {})
        eye_parts = []
        if eyes.get("lower_lid_tension", 0) > 0.1:
            eye_parts.append("lower lid tension")
        if eyes.get("gaze_lock", 0) > 0.5:
            eye_parts.append("gaze lock")
        if eyes.get("upper_lid_raise", 0) > 0.2:
            eye_parts.append("eyes widened")
        if eye_parts:
            blink = expression_plan.get("blink", {})
            rate = blink.get("rate_per_10s", 3)
            supp = blink.get("suppression", 0)
            if supp > 0.5:
                eye_parts.append(f"blink suppressed ({rate} per 10s)")
            parts.append(f"eyes: {', '.join(eye_parts)}")

        # Mouth/jaw
        mouth = expression_plan.get("mouth", {})
        mouth_parts = []
        if abs(mouth.get("jaw_drop", 0)) > 0.05:
            mouth_parts.append("jaw slightly tight" if mouth["jaw_drop"] < 0.1 else "jaw tension visible")
        if abs(mouth.get("lip_press", 0)) > 0.1:
            mouth_parts.append("lips pressed")
        if abs(mouth.get("corner_pull", 0)) > 0.05:
            if mouth["corner_pull"] < 0:
                mouth_parts.append("corners pulled down slightly")
            else:
                mouth_parts.append("corners neutral")
        if mouth_parts:
            parts.append(f"mouth/jaw: {', '.join(mouth_parts)}")

    # Body
    if body_plan and body_plan.get("emphasis", 0) > 0.1:
        body_parts = []
        posture = body_plan.get("posture", "")
        if posture:
            body_parts.append(posture.replace("_", " "))
        hands = body_plan.get("hands", "")
        if hands and hands != "at_rest":
            body_parts.append(f"hands {hands.replace('_', ' ')}")
        breath = body_plan.get("breath", "")
        if breath and breath != "normal":
            body_parts.append(f"{breath.replace('_', ' ')} breath")
        if body_parts:
            parts.append(f"body: {', '.join(body_parts)}")

    # Delivery (dialogue only)
    if delivery_plan:
        pace = delivery_plan.get("pace", "natural").replace("_", " ")
        volume = delivery_plan.get("volume", "medium")
        tone = delivery_plan.get("tone", "natural")
        parts.append(f"delivery: {volume} {tone} {pace}, breath catch at line end, no blink on final words")

    # V21.9.1: Join with "; " instead of newlines — survives Authority Gate regex
    return "ACTING (bio-real): " + "; ".join(parts)


# ──────────────────────────────────────────────────────────────
# SCENE-WIDE EMOTION GENERATION
# ──────────────────────────────────────────────────────────────

def generate_scene_emotions(
    shots: List[Dict],
    beats: List[Dict],
    project_path: str = "",
) -> Dict[str, Any]:
    """
    Generate emotion layer for all shots in a scene.
    Uses proportional beat mapping (same as script fidelity agent).
    Returns keyed by shot_id.
    """
    n_shots = len(shots)
    n_beats = len(beats)
    result = {}

    for shot_idx, shot in enumerate(shots):
        shot_id = shot.get("shot_id", f"unknown_{shot_idx}")
        shot_type = shot.get("shot_type", "medium")
        characters = shot.get("characters", [])
        dialogue = shot.get("dialogue_text", "") or shot.get("dialogue", "")
        duration = shot.get("duration", 8)

        # Proportional beat mapping (same as V17.7 script fidelity)
        beat_desc = ""
        beat_dialogue = ""
        if n_beats > 0:
            beat_idx = int(shot_idx * n_beats / n_shots)
            beat_idx = min(beat_idx, n_beats - 1)
            beat = beats[beat_idx]
            beat_desc = beat.get("description", "")
            beat_dialogue = beat.get("dialogue", "")

        # Use shot dialogue if available, else beat dialogue
        active_dialogue = dialogue or beat_dialogue

        # Generate for primary character (or empty for no-character shots)
        primary_char = characters[0] if characters else ""

        emotion_data = generate_emotion_state(
            beat_description=beat_desc,
            dialogue=active_dialogue,
            shot_type=shot_type,
            character=primary_char,
            duration=duration,
            project_path=project_path,
        )

        result[shot_id] = emotion_data

    return result


# ──────────────────────────────────────────────────────────────
# PROMPT INJECTION
# ──────────────────────────────────────────────────────────────

EMOTION_MARKER = "ACTING (bio-real):"


def inject_emotion_into_ltx(ltx_prompt: str, acting_block: str) -> str:
    """
    Inject ACTING block into LTX motion prompt.
    Places it after anti-morph but before camera/atmosphere.
    Skips if already present.
    """
    if not acting_block:
        return ltx_prompt
    if EMOTION_MARKER in ltx_prompt:
        return ltx_prompt  # Already injected

    # Find injection point: after anti-morph line, before camera
    lines = ltx_prompt.split(". ")
    inject_after = 1  # Default: after first sentence (anti-morph)

    for i, line in enumerate(lines):
        if "NO morphing" in line or "identity locked" in line:
            inject_after = i + 1
            break

    # Build injected prompt
    before = ". ".join(lines[:inject_after])
    after = ". ".join(lines[inject_after:])

    result = f"{before}. {acting_block}. {after}" if after else f"{before}. {acting_block}"
    return result


def inject_emotion_into_nano(nano_prompt: str, emotion_state: Dict, character: str) -> str:
    """
    Inject minimal emotion cue into nano_prompt for first frame.
    Keeps it light — nano only needs the emotion's physical manifestation.
    """
    if not character or not emotion_state:
        return nano_prompt
    if "emotion:" in nano_prompt.lower():
        return nano_prompt  # Already has emotion

    primary = emotion_state.get("primary", "neutral")
    control = emotion_state.get("control", 0.5)

    if control > 0.7:
        cue = f"{character} expression: controlled {primary}, tension held in jaw and eyes"
    elif control > 0.4:
        cue = f"{character} expression: visible {primary}, partially restrained"
    else:
        cue = f"{character} expression: {primary} openly visible, unguarded"

    return f"{nano_prompt}, {cue}"


# ──────────────────────────────────────────────────────────────
# FILE I/O (same pattern as wardrobe agent)
# ──────────────────────────────────────────────────────────────

def load_emotion_layer(project_path: str) -> Dict:
    """Load emotion_layer.json for project."""
    path = Path(project_path) / "emotion_layer.json"
    if path.exists():
        try:
            with open(path) as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load emotion_layer.json: {e}")
    return {}


def save_emotion_layer(project_path: str, data: Dict) -> str:
    """Save emotion_layer.json atomically (same pattern as wardrobe)."""
    path = Path(project_path) / "emotion_layer.json"
    try:
        fd, tmp_path = tempfile.mkstemp(dir=project_path, suffix=".json")
        with os.fdopen(fd, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        os.replace(tmp_path, str(path))
        logger.info(f"Saved emotion_layer.json ({len(data)} scenes)")
        return str(path)
    except Exception as e:
        logger.error(f"Failed to save emotion_layer.json: {e}")
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def auto_generate_emotion_layer(
    project_path: str,
    shot_plan: Dict,
    story_bible: Dict,
) -> Dict:
    """
    Auto-generate emotion layer for entire project.
    Called on first generation if emotion_layer.json doesn't exist.
    Non-blocking — failures don't stop generation.
    """
    shots = shot_plan.get("shots", [])
    scenes = story_bible.get("scenes", [])
    scene_beats = {}
    for scene in scenes:
        sid = scene.get("scene_id", "")
        scene_beats[sid] = scene.get("beats", [])

    # Group shots by scene
    from collections import defaultdict
    scene_shots = defaultdict(list)
    for shot in shots:
        shot_id = shot.get("shot_id", "")
        scene_id = shot_id.split("_")[0] if "_" in shot_id else ""
        scene_shots[scene_id].append(shot)

    emotion_data = {}
    total_generated = 0

    for scene_id, scene_shot_list in sorted(scene_shots.items()):
        beats = scene_beats.get(scene_id, [])
        # Also check with leading zeros / different formats
        if not beats:
            for sid, b in scene_beats.items():
                if sid.lstrip("0") == scene_id.lstrip("0") or scene_id in sid:
                    beats = b
                    break

        scene_emotions = generate_scene_emotions(
            shots=scene_shot_list,
            beats=beats,
            project_path=project_path,
        )
        emotion_data[f"scene_{scene_id}"] = scene_emotions
        total_generated += len(scene_emotions)

    logger.info(f"Auto-generated emotion layer: {total_generated} shots across {len(emotion_data)} scenes")

    # Save
    save_emotion_layer(project_path, emotion_data)

    return emotion_data


# ──────────────────────────────────────────────────────────────
# VALIDATION
# ──────────────────────────────────────────────────────────────

def validate_emotion_prompt(ltx_prompt: str) -> Dict[str, bool]:
    """Validate that a prompt has proper emotion directives."""
    return {
        "has_emotion_blend": "emotion blend:" in ltx_prompt,
        "has_microleak": "microleak:" in ltx_prompt,
        "has_blink_directive": "blink" in ltx_prompt.lower(),
        "has_asymmetry": "asymmetry" in ltx_prompt.lower(),
        "has_acting_block": EMOTION_MARKER in ltx_prompt,
    }


def validate_scene_emotion_continuity(scene_emotions: Dict) -> List[str]:
    """Check for emotion continuity issues within a scene."""
    warnings = []
    prev_primary = None
    prev_shot_id = None

    for shot_id, data in sorted(scene_emotions.items()):
        state = data.get("emotion_state", {})
        primary = state.get("primary", "")

        if prev_primary and primary != prev_primary:
            # Check if there's a beat justification
            template = state.get("template_used", "")
            if template == prev_primary:
                continue  # Same template, different primary is fine
            warnings.append(
                f"Emotion shift {prev_shot_id}→{shot_id}: {prev_primary}→{primary} "
                f"(verify beat justification)"
            )

        prev_primary = primary
        prev_shot_id = shot_id

    return warnings
