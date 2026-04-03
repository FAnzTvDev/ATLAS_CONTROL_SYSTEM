#!/usr/bin/env python3
"""
ATLAS Creative Prompt Compiler — V1.0
======================================
The SYSTEMIC fix for prompt corruption.

ROOT CAUSE: fix-v16 enrichment injects generic templates because no system
translates story beats → scene type → shot grammar → motivated prompts.
The Creative Intelligence Codex describes 6 disciplines. The Creative
Reference Memory describes shot selection intelligence. This module
IMPLEMENTS both as callable functions that replace every generic fallback.

INTEGRATION:
- Called by unified_prompt_builder.py as the PRIMARY prompt authority
- Called by fix-v16 CHECK 5B to replace generic "experiences the moment" fallbacks
- Called by cinematic_enricher._motion_opener() for dialogue-aware motion
- Called by post-save audit to validate NO generics remain

GOVERNANCE:
- Autonomous Build Covenant Rule A: Diagnosis before implementation ✓
  (5 contamination points diagnosed before this code was written)
- Autonomous Build Covenant Rule B: No gate changes without approval ✓
  (this adds a new layer, does NOT modify existing gates)
- Autonomous Build Covenant Rule C: Green is not success — diagnostic accuracy ✓
  (quality gate checks for specific patterns, not just pass/fail)

DESIGN PRINCIPLE (from Creative Intelligence Codex):
"The screenplay is the DNA. If the DNA is generic, the organism is generic."
Every prompt line must serve AT LEAST 2 of the 6 disciplines:
Writer (structure), Director (visual thesis), DP (lens/light),
Editor (rhythm), Actor (physical verbs), Sound (atmosphere).

Created: 2026-03-12
"""

import re
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger("atlas.creative_prompt_compiler")

# ═══════════════════════════════════════════════════════════════
# GENERIC PATTERN BLACKLIST — if ANY of these appear in a final
# prompt, the prompt is CONTAMINATED and must be recompiled.
# From Autonomous Build Covenant: diagnostic accuracy, not green count.
# ═══════════════════════════════════════════════════════════════

GENERIC_PATTERNS = [
    r"experiences?\s+the\s+moment",
    r"natural\s+movement\s+begins",
    r"subtle\s+shift\s+in\s+weight",
    r"present\s+and\s+engaged",
    r"holds?\s+the\s+moment",
    r"gentle\s+breathing",
    r"natural\s+pause",
    r"0-[23]s\s+(?:settle|static\s+hold)",
    r"key\s+motion:\s+experiences",
    r"continues?\s+natural\s+movement",
    r"subtle\s+gesture\s+or\s+weight\s+shift",
    r"camera\s+holds\s+steady.*gentle\s+slow\s+push",
    r"environment\s+reaches\s+atmospheric\s+peak",
    r"None\s+\w+\s+the\s+moment",
    r"Character\s+experiences",
]

GENERIC_REGEX = re.compile("|".join(GENERIC_PATTERNS), re.IGNORECASE)


def is_prompt_generic(text: str) -> bool:
    """Check if a prompt contains generic filler patterns."""
    return bool(GENERIC_REGEX.search(text))


def count_generic_patterns(text: str) -> int:
    """Count how many generic patterns exist in text."""
    return len(GENERIC_REGEX.findall(text))


# ═══════════════════════════════════════════════════════════════
# SCENE TYPE → SHOT GRAMMAR — Creative Intelligence Codex
# "Every scene must answer all six discipline questions."
# ═══════════════════════════════════════════════════════════════

@dataclass
class ShotDirective:
    """A motivated, research-backed prompt directive for a specific shot context."""
    nano_action: str       # What the character DOES (Actor discipline)
    ltx_motion: str        # How the camera MOVES (DP + Editor discipline)
    atmosphere: str        # What the space SOUNDS/FEELS like (Sound + Director)
    visual_thesis: str     # The ONE IMAGE meaning (Director discipline)
    disciplines_served: int  # Must be >= 2


# ═══════════════════════════════════════════════════════════════
# EMOTION → PHYSICAL VERB MAPPING (Actor discipline)
# From Creative Intelligence Codex: "EVERY CHARACTER ENTRANCE HAS
# A PHYSICAL VERB. Not 'enters the room' but 'steps inside, her
# heels echoing on marble.'"
# ═══════════════════════════════════════════════════════════════

EMOTION_PHYSICAL_MAP = {
    # High emotion states → specific physical behaviors
    "grief": {
        "standing": "shoulders bowed, weight uneven, hand braced against furniture",
        "sitting": "collapsed inward, hands clasped or limp in lap, gaze dropped",
        "walking": "steps slow and heavy, each one deliberate, as if the floor pulls",
        "speaking": "voice catches, jaw tightens before words come, breath visible",
        "default": "body carries the weight visibly, movement deliberate and slow",
    },
    "tension": {
        "standing": "spine rigid, jaw set, one hand clenched at side",
        "sitting": "leaned forward, elbows on knees, coiled energy",
        "walking": "steps measured and controlled, checking surroundings",
        "speaking": "words precise, clipped, controlled breath between phrases",
        "default": "stillness that suggests restraint, not calm",
    },
    "anger": {
        "standing": "posture squared, weight forward on balls of feet",
        "sitting": "gripping armrest, leaned forward, ready to stand",
        "walking": "strides long and deliberate, body angled forward",
        "speaking": "voice drops low and hard, hands gesture sharply",
        "default": "energy barely contained, movement sharp and decisive",
    },
    "revelation": {
        "standing": "body goes still, then reorients — turns slowly toward the truth",
        "sitting": "leans back as information lands, hand rises to face",
        "walking": "stops mid-stride, body pivots",
        "speaking": "words slow as understanding forms, eyes widening",
        "default": "physical recalibration visible — the body processes before the mind speaks",
    },
    "fear": {
        "standing": "pulled inward, arms close to body, breath shallow",
        "sitting": "gripping seat edge, ready to flee, eyes scanning",
        "walking": "steps quicken, shoulders hunched, frequent backward glances",
        "speaking": "voice thin, words rushed or halting, swallowing between phrases",
        "default": "body instinctively makes itself smaller, peripheral awareness heightened",
    },
    "determination": {
        "standing": "chin lifted, shoulders back, eyes locked on objective",
        "sitting": "leaned forward with purpose, hands flat on table",
        "walking": "stride confident, direct path, gaze forward",
        "speaking": "voice steady, measured, each word placed with intention",
        "default": "body aligned and purposeful, no wasted movement",
    },
    "love": {
        "standing": "body angled toward the other, open posture, unconscious lean",
        "sitting": "turned toward other person, hand extended or resting near",
        "walking": "pace matches the other's, proximity closes naturally",
        "speaking": "voice soft, eyes holding, breath syncs with listener",
        "default": "gravitational pull visible — body drawn toward the other",
    },
    "neutral": {
        "standing": "weight settled, hands at rest, eyes engaged with surroundings",
        "sitting": "comfortable but alert, natural posture",
        "walking": "measured pace appropriate to the space",
        "speaking": "natural cadence, genuine eye contact",
        "default": "present and grounded in the physical space",
    },
}


def get_physical_direction(emotion: str, posture: str = "default",
                           character: str = "", beat_desc: str = "") -> str:
    """
    Get motivated physical direction based on emotion + posture.

    Creative Intelligence Codex Rule: "Subtext is in the body, not the dialogue."
    Uses specific physical verbs, never generic "experiences" or "engages".

    If beat_desc contains specific physical verbs, those take priority
    (the script is the DNA — screenplay specifics override templates).
    """
    # PRIORITY 1: Beat description has specific physical verbs
    if beat_desc:
        physical_verbs = extract_physical_verbs(beat_desc)
        if physical_verbs:
            char_prefix = f"{character} " if character else ""
            return f"{char_prefix}{beat_desc.rstrip('.')}"

    # PRIORITY 2: Emotion-driven physical map
    emotion_lower = emotion.lower().strip() if emotion else "neutral"
    posture_lower = posture.lower().strip() if posture else "default"

    emotion_map = EMOTION_PHYSICAL_MAP.get(emotion_lower, EMOTION_PHYSICAL_MAP["neutral"])
    direction = emotion_map.get(posture_lower, emotion_map.get("default", ""))

    if character and direction:
        return f"{character} {direction}"
    return direction


# ═══════════════════════════════════════════════════════════════
# PHYSICAL VERB EXTRACTION — replaces the broken "experiences"
# fallback in fix-v16 line 24397
# ═══════════════════════════════════════════════════════════════

# Comprehensive physical verb list (Actor discipline)
# Organized by action type, not alphabetical — so we catch
# the most specific verbs first
PHYSICAL_VERBS = {
    # Whole body movement
    "enters", "exits", "crosses", "approaches", "retreats", "stumbles",
    "rushes", "pauses", "freezes", "collapses", "rises", "sinks",
    "paces", "staggers", "lunges", "recoils", "spins", "pivots",
    # Hands and arms
    "reaches", "grabs", "drops", "places", "lifts", "opens", "closes",
    "touches", "strokes", "clutches", "releases", "points", "gestures",
    "catches", "throws", "pushes", "pulls", "pours", "writes",
    # Face and head
    "stares", "glances", "squints", "blinks", "nods", "shakes",
    "frowns", "smiles", "grimaces", "winces", "smirks",
    # Legs and feet
    "kneels", "sits", "stands", "steps", "stamps", "kicks",
    "climbs", "descends", "crouches", "crawls",
    # Voice-adjacent (physical aspect of speech)
    "whispers", "screams", "gasps", "sighs", "laughs", "cries",
    "speaks", "mutters", "shouts", "pleads", "demands",
    # Object interaction
    "reads", "holds", "drinks", "eats", "lights", "extinguishes",
    "locks", "unlocks", "dials", "answers", "hangs", "picks",
    "sets", "arranges", "tears", "folds", "unfolds",
    # Emotional physical
    "trembles", "shudders", "steadies", "braces", "clenches",
    "relaxes", "tenses", "breathes", "exhales", "swallows",
}

# Also match -ing forms
PHYSICAL_VERB_PATTERNS = set()
for v in PHYSICAL_VERBS:
    PHYSICAL_VERB_PATTERNS.add(v)
    if v.endswith("s"):
        PHYSICAL_VERB_PATTERNS.add(v[:-1])  # enters → enter
        PHYSICAL_VERB_PATTERNS.add(v[:-1] + "ing")  # enters → entering
    if v.endswith("es"):
        PHYSICAL_VERB_PATTERNS.add(v[:-2])  # touches → touch
        PHYSICAL_VERB_PATTERNS.add(v[:-2] + "ing")  # touches → touching


def extract_physical_verbs(text: str) -> List[str]:
    """
    Extract specific physical verbs from beat description.
    Returns empty list only if NO physical verbs found — which triggers
    the emotion-based physical map instead of generic "experiences".
    """
    if not text:
        return []
    text_lower = text.lower()
    found = []
    for verb in PHYSICAL_VERB_PATTERNS:
        # Word boundary match to avoid false positives
        if re.search(rf'\b{re.escape(verb)}\b', text_lower):
            found.append(verb)
    return list(dict.fromkeys(found))[:6]  # deduplicate, max 6


def build_beat_action_replacement(beat_desc: str, character: str,
                                   emotion: str = "neutral",
                                   scene_type: str = "") -> str:
    """
    REPLACES the generic "Character experiences the moment" fallback
    at orchestrator_server.py line 24397.

    If beat has physical verbs → use the beat directly.
    If beat has NO physical verbs → use emotion-driven physical map.
    NEVER returns generic filler.

    This is the single function that prevents contamination point #1.
    """
    if not beat_desc:
        # No beat at all — compose from emotion + scene type
        return get_physical_direction(emotion, "default", character, "")

    verbs = extract_physical_verbs(beat_desc)
    if verbs:
        # Beat has specific physical content — use it as-is
        return beat_desc.rstrip(".")

    # Beat exists but has NO physical verbs (atmospheric description)
    # Use the emotion-driven physical map WITH the beat atmosphere
    physical = get_physical_direction(emotion, "default", character, "")
    if physical:
        # Combine: physical direction + atmospheric context
        atmo = beat_desc.rstrip(".")
        return f"{physical}, amid {atmo.lower()}" if atmo else physical

    # Ultimate fallback — still specific, never generic
    return f"{character} present in the moment, body telling the story the words cannot"


# ═══════════════════════════════════════════════════════════════
# SHOT-TYPE AWARE MOTION BUILDER — replaces generic timing templates
# From Creative Reference Memory: "AI Video Movement Mapping for LTX-2.3"
# ═══════════════════════════════════════════════════════════════

def build_ltx_motion(shot_type: str, character: str, emotion: str,
                     has_dialogue: bool, beat_desc: str = "",
                     duration: float = 8.0,
                     coverage_role: str = "") -> str:
    """
    Build a motivated LTX motion prompt based on Creative Reference Memory.

    Replaces generic CAMERA_TIMING templates in unified_prompt_builder.py.
    Every motion choice is MOTIVATED by the shot type + emotion + beat.

    Creative Intelligence Codex rule:
    "SHORT SENTENCES = fast cuts. LONG DESCRIPTIVE PARAGRAPHS = slow shots."
    The WRITING ITSELF teaches the pipeline how fast to cut.
    """
    parts = []

    # DIALOGUE SHOTS: Character performs speech action from frame 1
    # (Doctrine Law 231: NEVER "enters frame" on dialogue shots)
    if has_dialogue:
        energy = _classify_dialogue_energy(emotion, beat_desc)
        dialogue_motion = _get_dialogue_motion(character, energy, shot_type)
        parts.append(dialogue_motion)

        # Add beat-specific action if available
        if beat_desc:
            verbs = extract_physical_verbs(beat_desc)
            if verbs:
                action = ", ".join(verbs[:3])
                parts.append(f"character performs: {action}")

        # Duration-aware pacing (Creative Reference Memory: dialogue ASL 5-8s)
        if duration <= 5:
            parts.append("tight pacing, conversation drives forward")
        elif duration >= 10:
            parts.append("measured pacing, weight given to silences between words")

        parts.append(f"face stable NO morphing, character consistent, {int(duration)}s")
        return ", ".join(parts)

    # NON-DIALOGUE: Shot-type driven motion
    # Creative Reference Memory: movement type maps to emotional psychology

    if shot_type in ("establishing", "wide", "master"):
        # DP discipline: "The first shot of every scene establishes space.
        # But 'establishing' does NOT mean 'empty wide shot of a building.'"
        if emotion in ("tension", "dread"):
            parts.append(f"slow controlled push into space, shadows deepen")
        elif emotion in ("grief", "loss"):
            parts.append(f"camera drifts through space as if searching for someone gone")
        else:
            parts.append(f"measured reveal of space, architectural depth visible")

        if character:
            parts.append(f"{character} visible in environment, scale established")
        parts.append(f"NO morphing, {int(duration)}s")

    elif shot_type in ("close_up", "extreme_close_up", "medium_close_up"):
        physical = get_physical_direction(emotion, "default", character, beat_desc)
        if physical:
            parts.append(f"character performs: {physical}")

        if shot_type == "extreme_close_up":
            parts.append("camera locked, imperceptible drift, every detail readable")
        else:
            parts.append("camera holds, subtle drift, face detail preserved")

        parts.append(f"face stable NO morphing, character consistent, {int(duration)}s")

    elif shot_type in ("medium", "over_the_shoulder", "two_shot"):
        physical = get_physical_direction(emotion, "standing", character, beat_desc)
        if physical:
            parts.append(f"character performs: {physical}")

        if shot_type == "over_the_shoulder":
            parts.append("OTS framing locked, foreground soft, background sharp")
        elif shot_type == "two_shot":
            parts.append("both characters visible, spatial relationship clear")
        else:
            parts.append("natural framing, body language readable")

        parts.append(f"face stable NO morphing, character consistent, {int(duration)}s")

    elif shot_type in ("reaction",):
        parts.append(f"character reacts: {character} processes what was just said")
        physical = get_physical_direction(emotion, "default", character, "")
        if physical and character not in physical:
            parts.append(physical)
        parts.append(f"camera holds still, face stable NO morphing, {int(duration)}s")

    elif shot_type in ("insert", "detail", "cutaway", "b-roll"):
        # No characters — environment only
        if beat_desc:
            parts.append(beat_desc.rstrip("."))
        else:
            parts.append("static detail, shallow depth of field, texture visible")
        parts.append(f"NO morphing, NO face generation, environment only, {int(duration)}s")

    else:
        # Unknown shot type — use beat or emotion
        physical = get_physical_direction(emotion, "default", character, beat_desc)
        if physical:
            parts.append(f"character performs: {physical}")
        parts.append(f"face stable NO morphing, {int(duration)}s")

    return ", ".join(parts)


def _classify_dialogue_energy(emotion: str, beat_desc: str = "") -> str:
    """Map emotion to dialogue energy level for motion opener."""
    e = emotion.lower().strip() if emotion else ""
    if e in ("anger", "rage", "fury"):
        return "intense"
    elif e in ("grief", "sadness", "loss", "sorrow"):
        return "grief"
    elif e in ("revelation", "shock", "surprise", "discovery"):
        return "revelation"
    elif e in ("tension", "dread", "fear", "anxiety"):
        return "intense"
    elif e in ("quiet", "contemplation", "reflection", "peace"):
        return "quiet"
    elif e in ("joy", "hope", "love", "warmth"):
        return "warm"
    return "neutral"


def _get_dialogue_motion(character: str, energy: str, shot_type: str) -> str:
    """
    Get dialogue-specific motion opener.
    Doctrine Law 231: character performs speech from frame 1.
    """
    energy_map = {
        "intense": f"{character} speaks with conviction, jaw set, eyes locked on target",
        "grief": f"{character} speaks through visible effort, voice catching, breath unsteady",
        "revelation": f"{character} leans forward, urgency building in every word",
        "warm": f"{character} speaks with open expression, genuine presence",
        "quiet": f"{character} speaks low, measured, each word placed deliberately",
        "neutral": f"{character} speaks naturally, engaged and present from first frame",
    }

    base = energy_map.get(energy, energy_map["neutral"])

    # Shot type modifier
    if shot_type in ("close_up", "extreme_close_up"):
        base += ", face fills frame"
    elif shot_type in ("medium", "two_shot"):
        base += ", gestures visible"

    return base


# ═══════════════════════════════════════════════════════════════
# 6-DISCIPLINE QUALITY GATE — validates prompts against Creative
# Intelligence Codex requirements
# ═══════════════════════════════════════════════════════════════

@dataclass
class DisciplineScore:
    """Score for each of the 6 Creative Intelligence Codex disciplines."""
    writer: float = 0.0       # Structure, dramatic question
    director: float = 0.0     # Visual thesis, blocking
    dp: float = 0.0           # Lens, light, composition
    editor: float = 0.0       # Rhythm, pacing cues
    actor: float = 0.0        # Physical verbs, subtext
    sound: float = 0.0        # Atmosphere, ambient texture

    @property
    def total(self) -> float:
        return self.writer + self.director + self.dp + self.editor + self.actor + self.sound

    @property
    def disciplines_met(self) -> int:
        """Count of disciplines with score > 0."""
        return sum(1 for s in [self.writer, self.director, self.dp,
                                self.editor, self.actor, self.sound] if s > 0)


def score_prompt_quality(nano: str, ltx: str, shot: Dict) -> DisciplineScore:
    """
    Score a prompt against the 6-discipline standard.

    Creative Intelligence Codex rule:
    "Every action line should serve AT LEAST 2 disciplines.
    If a line serves zero disciplines, cut it."

    Returns per-discipline scores (0-1 each, 6.0 max total).
    """
    score = DisciplineScore()
    combined = f"{nano} {ltx}".lower()

    # WRITER (structure): Does the prompt reference story beats?
    if any(m in combined for m in ["character action:", "character performs:",
                                    "character speaks:", "character reacts:"]):
        score.writer = 0.7
    if shot.get("beat_id") or shot.get("_beat_index"):
        score.writer = min(score.writer + 0.3, 1.0)

    # DIRECTOR (visual thesis): Is there spatial/blocking information?
    director_cues = ["framing", "blocking", "composition:", "visual thesis",
                     "spatial", "distance", "separation", "positioned"]
    if any(c in combined for c in director_cues):
        score.director = 0.6
    if shot.get("blocking_role") or shot.get("coverage_role"):
        score.director = min(score.director + 0.4, 1.0)

    # DP (lens/light): Is there specific visual language?
    dp_cues = ["mm", "f/", "focal", "depth", "shallow", "bokeh",
               "light", "shadow", "golden", "diffused", "silhouette",
               "backlit", "contrast"]
    dp_hits = sum(1 for c in dp_cues if c in combined)
    score.dp = min(dp_hits * 0.2, 1.0)

    # EDITOR (rhythm): Are there pacing cues?
    if re.search(r'\d+s\b', combined):  # Duration tag
        score.editor = 0.4
    editor_cues = ["slow", "fast", "held", "cut", "pace", "rhythm",
                   "steady", "drift", "push", "pull"]
    ed_hits = sum(1 for c in editor_cues if c in combined)
    score.editor = min(score.editor + ed_hits * 0.15, 1.0)

    # ACTOR (physical verbs): Specific body actions?
    verbs_found = extract_physical_verbs(combined)
    score.actor = min(len(verbs_found) * 0.25, 1.0)

    # SOUND (atmosphere): Environmental texture?
    sound_cues = ["echo", "silence", "creak", "wind", "ambient",
                  "dust", "mist", "atmosphere", "still", "quiet",
                  "hum", "tick", "drip"]
    snd_hits = sum(1 for c in sound_cues if c in combined)
    score.sound = min(snd_hits * 0.25, 1.0)

    return score


def validate_prompt_quality(nano: str, ltx: str, shot: Dict) -> Tuple[bool, str]:
    """
    Validate that a prompt meets the 2-discipline minimum.

    Returns (passed, reason).

    Rule from Creative Intelligence Codex:
    "Every action line should serve AT LEAST 2 disciplines.
    If a line serves zero disciplines, cut it."
    """
    # First check: no generic patterns allowed
    if is_prompt_generic(nano):
        return False, f"Generic pattern in nano: {GENERIC_REGEX.search(nano).group()}"
    if is_prompt_generic(ltx):
        return False, f"Generic pattern in ltx: {GENERIC_REGEX.search(ltx).group()}"

    # Second check: minimum 2 disciplines served
    score = score_prompt_quality(nano, ltx, shot)
    if score.disciplines_met < 2:
        return False, f"Only {score.disciplines_met}/6 disciplines served (need ≥2)"

    return True, f"PASS: {score.disciplines_met}/6 disciplines, score={score.total:.1f}"


# ═══════════════════════════════════════════════════════════════
# PROMPT DECONTAMINATION — strips generic patterns and replaces
# with motivated alternatives
# ═══════════════════════════════════════════════════════════════

def decontaminate_prompt(text: str, character: str = "",
                         emotion: str = "neutral",
                         beat_desc: str = "") -> str:
    """
    Remove generic patterns and replace with motivated alternatives.

    This is the LAST LINE OF DEFENSE — runs after all other enrichment.
    If a generic pattern survives everything else, this catches it.

    Does NOT just strip — REPLACES with specific direction.
    An empty prompt is worse than a generic one, but a specific prompt
    is better than both.
    """
    if not text:
        return text

    result = text

    # Replace each generic pattern with motivated alternative
    replacements = {
        r"experiences?\s+the\s+moment": get_physical_direction(emotion, "default", character, beat_desc) or f"{character} engaged with the space",
        r"natural\s+movement\s+begins": f"{character} already in motion, present from first frame" if character else "environment breathes, natural atmospheric motion",
        r"subtle\s+shift\s+in\s+weight": f"{character} adjusts weight, body tells the subtext" if character else "gentle atmospheric shift",
        r"present\s+and\s+engaged": get_physical_direction(emotion, "standing", character, beat_desc) or f"{character} anchored in the space",
        r"holds?\s+the\s+moment": get_physical_direction(emotion, "standing", character, beat_desc) or f"{character} still, weight of the scene visible in posture",
        r"gentle\s+breathing": f"{character} breath visible, chest rises with emotion" if character else "atmospheric stillness, space breathes",
        r"continues?\s+natural\s+movement": get_physical_direction(emotion, "default", character, beat_desc) or f"{character} movement purposeful and motivated",
        r"0-[23]s\s+settle\s*,?\s*": "",  # Just strip — the motion opener handles timing
        r"0-[23]s\s+static\s+hold\s*,?\s*": "",
        r"key\s+motion:\s+experiences": f"key motion: {', '.join(extract_physical_verbs(beat_desc)[:3]) if beat_desc else 'purposeful movement'}",
    }

    for pattern, replacement in replacements.items():
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)

    # Clean up double spaces and commas
    result = re.sub(r'\s+', ' ', result)
    result = re.sub(r',\s*,', ',', result)
    result = re.sub(r'\.\s*\.', '.', result)

    return result.strip()


# ═══════════════════════════════════════════════════════════════
# BATCH OPERATIONS — for pipeline integration
# ═══════════════════════════════════════════════════════════════

def audit_all_prompts(shots: List[Dict]) -> Dict:
    """
    Audit ALL shots for generic contamination.
    Returns detailed report with per-shot scores.

    Autonomous Build Covenant Rule C:
    "The success metric is diagnostic accuracy, not green count."
    """
    total = len(shots)
    contaminated = 0
    below_threshold = 0
    scores = []
    issues = []

    for shot in shots:
        sid = shot.get("shot_id", "?")
        nano = shot.get("nano_prompt_final") or shot.get("nano_prompt", "")
        ltx = shot.get("ltx_motion_prompt_final") or shot.get("ltx_motion_prompt", "")

        # Check for generic patterns
        nano_generics = count_generic_patterns(nano)
        ltx_generics = count_generic_patterns(ltx)
        if nano_generics + ltx_generics > 0:
            contaminated += 1
            issues.append({
                "shot_id": sid,
                "type": "GENERIC_CONTAMINATION",
                "nano_generics": nano_generics,
                "ltx_generics": ltx_generics,
            })

        # Score disciplines
        score = score_prompt_quality(nano, ltx, shot)
        if score.disciplines_met < 2:
            below_threshold += 1
            issues.append({
                "shot_id": sid,
                "type": "LOW_DISCIPLINE_SCORE",
                "disciplines_met": score.disciplines_met,
                "total_score": round(score.total, 2),
            })

        scores.append({
            "shot_id": sid,
            "disciplines_met": score.disciplines_met,
            "total_score": round(score.total, 2),
            "generic_count": nano_generics + ltx_generics,
        })

    avg_score = sum(s["total_score"] for s in scores) / max(total, 1)
    avg_disciplines = sum(s["disciplines_met"] for s in scores) / max(total, 1)

    return {
        "total_shots": total,
        "contaminated": contaminated,
        "below_threshold": below_threshold,
        "clean": total - contaminated - below_threshold,
        "avg_score": round(avg_score, 2),
        "avg_disciplines": round(avg_disciplines, 1),
        "contamination_rate": round(contaminated / max(total, 1) * 100, 1),
        "issues": issues[:50],  # cap at 50 for readability
        "per_shot_scores": scores,
    }


def decontaminate_all_prompts(shots: List[Dict], story_bible: Optional[Dict] = None) -> int:
    """
    Run decontamination on ALL shots.
    Returns number of shots cleaned.

    This is the systemic fix — every generic pattern is replaced
    with a motivated, research-backed alternative.
    """
    # Build scene→beats map for beat lookup
    scene_beats = {}
    if story_bible:
        for sc in story_bible.get("scenes", []):
            sc_id = str(sc.get("scene_id", sc.get("scene_number", ""))).zfill(3)
            scene_beats[sc_id] = sc.get("beats", sc.get("story_beats", []))

    # Build scene shot counts for proportional mapping
    scene_shots = {}
    for shot in shots:
        sid = shot.get("shot_id", "")
        sc_id = sid.split("_")[0] if "_" in sid else ""
        if sc_id:
            scene_shots.setdefault(sc_id, []).append(sid)

    cleaned = 0
    for shot in shots:
        sid = shot.get("shot_id", "?")
        sc_id = sid.split("_")[0] if "_" in sid else ""
        chars = shot.get("characters", [])
        character = chars[0] if chars else ""
        emotion = _infer_emotion(shot)

        # Get proportional beat
        beat_desc = ""
        beats = scene_beats.get(sc_id, [])
        if beats and sc_id in scene_shots:
            sc_shot_list = scene_shots[sc_id]
            try:
                idx = sc_shot_list.index(sid)
                beat_idx = min(int(idx * len(beats) / len(sc_shot_list)), len(beats) - 1)
                beat = beats[beat_idx]
                beat_desc = (beat.get("character_action") or beat.get("description") or "").strip()
            except (ValueError, IndexError):
                pass

        # Decontaminate nano
        nano = shot.get("nano_prompt", "")
        if is_prompt_generic(nano):
            shot["nano_prompt"] = decontaminate_prompt(nano, character, emotion, beat_desc)
            cleaned += 1

        # Decontaminate ltx
        ltx = shot.get("ltx_motion_prompt", "")
        if is_prompt_generic(ltx):
            shot["ltx_motion_prompt"] = decontaminate_prompt(ltx, character, emotion, beat_desc)
            cleaned += 1

        # Also check final prompts
        nano_final = shot.get("nano_prompt_final", "")
        if nano_final and is_prompt_generic(nano_final):
            shot["nano_prompt_final"] = decontaminate_prompt(nano_final, character, emotion, beat_desc)

        ltx_final = shot.get("ltx_motion_prompt_final", "")
        if ltx_final and is_prompt_generic(ltx_final):
            shot["ltx_motion_prompt_final"] = decontaminate_prompt(ltx_final, character, emotion, beat_desc)

    return cleaned


def _infer_emotion(shot: Dict) -> str:
    """Infer emotion from shot metadata."""
    # Check multiple sources
    emotion = shot.get("emotion", "")
    if emotion:
        return emotion

    state_in = shot.get("state_in", {})
    if isinstance(state_in, dict):
        for char_state in state_in.values():
            if isinstance(char_state, dict):
                e = char_state.get("emotion", "") or char_state.get("emotion_read", "")
                if e:
                    return e

    # Infer from shot content
    nano = (shot.get("nano_prompt") or "").lower()
    if any(w in nano for w in ["grief", "mourn", "loss", "sorrow"]):
        return "grief"
    if any(w in nano for w in ["tension", "dread", "fear", "ominous"]):
        return "tension"
    if any(w in nano for w in ["anger", "rage", "furious", "confront"]):
        return "anger"
    if any(w in nano for w in ["reveal", "discover", "shock", "realize"]):
        return "revelation"

    return "neutral"


# ═══════════════════════════════════════════════════════════════
# INTEGRATION HOOKS — for wiring into existing pipeline
# ═══════════════════════════════════════════════════════════════

def replace_story_bible_fallback(beat_desc: str, character: str,
                                  characters_list: List[str] = None,
                                  emotion: str = "neutral") -> Tuple[str, List[str]]:
    """
    DIRECT REPLACEMENT for orchestrator_server.py line 24397.

    Instead of:
        _eb["character_action"] = f"{_char} experiences the moment"
        _eb["action_verbs"] = ["experiences"]

    Use:
        action, verbs = replace_story_bible_fallback(desc, char)
        _eb["character_action"] = action
        _eb["action_verbs"] = verbs

    NEVER returns "experiences the moment".
    """
    if not beat_desc:
        action = get_physical_direction(emotion, "default", character, "")
        if not action:
            action = f"{character} present, body grounded in the physical space"
        return action, extract_physical_verbs(action) or ["present"]

    verbs = extract_physical_verbs(beat_desc)
    if verbs:
        return beat_desc.rstrip("."), verbs

    # Beat exists but no physical verbs — compose from emotion
    physical = get_physical_direction(emotion, "default", character, "")
    atmo = beat_desc.rstrip(".")
    if physical:
        composed = f"{physical}, amid {atmo.lower()}" if atmo else physical
    else:
        composed = f"{character} anchored in the space, {atmo.lower()}"

    return composed, extract_physical_verbs(composed) or ["anchored"]
