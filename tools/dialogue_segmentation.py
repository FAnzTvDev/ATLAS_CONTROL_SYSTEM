"""
ATLAS V17.6 — Dialogue-Aware LTX Segmentation Engine
=====================================================

The big gap: ATLAS segments by DURATION only.
But filmmaking segments by CONVERSATIONAL LOGIC.

An 18s two-person dialogue should NOT be one LTX shot.
It should be split into coverage segments:

  18s dialogue →
    Master Wide    (4s) — establish geography
    OTS Speaker A  (4s) — "I've seen what lurks below"
    OTS Speaker B  (4s) — "You don't understand the ritual"
    Reaction A     (3s) — processing / fear
    Reaction B     (3s) — resolve / defiance

Each segment:
  - ≤ 15s (LTX quality sweet spot)
  - Inherits same identity embedding
  - Gets morph constraint ("face stable NO morphing")
  - Gets unique camera angle per segment type
  - Gets dialogue text injected into LTX prompt

This prevents:
  - Face morphing (main LTX failure mode on long shots)
  - Identity drift
  - Monotone coverage
  - Dialogue being visually flat

Architecture:
  DialogueAnalyzer reads shot metadata + dialogue text
  CoveragePlanner generates segment plans
  SegmentBuilder creates the actual segment array for shot_plan.json

Usage:
  from tools.dialogue_segmentation import auto_segment_dialogue_shot
  segments = auto_segment_dialogue_shot(shot, cast_map)
"""

import re
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("atlas.dialogue_seg")

# ═══════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════

MAX_LTX_SEGMENT = 15   # seconds — quality ceiling for LTX
MIN_SEGMENT = 3         # seconds — minimum useful segment
DEFAULT_SEGMENT = 6     # seconds — default when no dialogue cues

# Coverage templates by speaker count
COVERAGE_TEMPLATES = {
    1: [
        # Single speaker: master → medium → CU → reaction → CU
        {"type": "establishing", "ratio": 0.20, "min": 3, "camera": "wide", "lens": "24mm"},
        {"type": "medium", "ratio": 0.30, "min": 4, "camera": "medium", "lens": "50mm"},
        {"type": "close_up", "ratio": 0.30, "min": 3, "camera": "close_up", "lens": "85mm"},
        {"type": "reaction", "ratio": 0.20, "min": 3, "camera": "close_up", "lens": "85mm"},
    ],
    2: [
        # Two speakers: master → OTS_A → OTS_B → reaction_A → reaction_B
        {"type": "establishing", "ratio": 0.18, "min": 3, "camera": "wide", "lens": "24mm"},
        {"type": "over_shoulder_a", "ratio": 0.22, "min": 4, "camera": "over_shoulder", "lens": "50mm"},
        {"type": "over_shoulder_b", "ratio": 0.22, "min": 4, "camera": "over_shoulder", "lens": "50mm"},
        {"type": "reaction_a", "ratio": 0.19, "min": 3, "camera": "close_up", "lens": "85mm"},
        {"type": "reaction_b", "ratio": 0.19, "min": 3, "camera": "close_up", "lens": "85mm"},
    ],
    3: [
        # Three+ speakers: master → medium_A → medium_B → CU_C → group_reaction
        {"type": "establishing", "ratio": 0.15, "min": 3, "camera": "wide", "lens": "24mm"},
        {"type": "medium_a", "ratio": 0.20, "min": 3, "camera": "medium", "lens": "50mm"},
        {"type": "medium_b", "ratio": 0.20, "min": 3, "camera": "medium", "lens": "50mm"},
        {"type": "close_up_c", "ratio": 0.20, "min": 3, "camera": "close_up", "lens": "85mm"},
        {"type": "group_reaction", "ratio": 0.25, "min": 4, "camera": "two_shot", "lens": "35mm"},
    ],
}

# Camera motion by segment type
SEGMENT_MOTION = {
    "establishing": "slow_crane",
    "wide": "static",
    "medium": "static",
    "over_shoulder_a": "static",
    "over_shoulder_b": "static",
    "close_up": "push_in",
    "close_up_c": "push_in",
    "reaction_a": "static",
    "reaction_b": "static",
    "reaction": "static",
    "medium_a": "static",
    "medium_b": "static",
    "group_reaction": "slow_pan",
}


class DialogueAnalyzer:
    """
    Analyze dialogue content to determine speaker count,
    emotional beats, and line alternation patterns.
    """

    @staticmethod
    def analyze(shot: Dict) -> Dict:
        """
        Analyze a shot's dialogue content.
        Returns {speaker_count, lines, emotional_beats, word_count, estimated_duration}.
        """
        characters = shot.get("characters", [])
        dialogue_text = shot.get("dialogue_text", "") or shot.get("beat_text", "") or ""
        nano_prompt = shot.get("nano_prompt", "")

        # Extract quoted dialogue
        quoted = re.findall(r'"([^"]+)"', dialogue_text + " " + nano_prompt)
        if not quoted:
            quoted = re.findall(r"'([^']+)'", dialogue_text + " " + nano_prompt)

        # Count speakers from character list
        speaker_count = len(characters) if characters else 1
        if speaker_count > 3:
            speaker_count = 3  # Template max

        # Count words for duration estimation
        all_dialogue = " ".join(quoted)
        word_count = len(all_dialogue.split()) if all_dialogue else 0

        # Estimate spoken duration (avg 2.5 words/second for dramatic delivery)
        spoken_duration = word_count / 2.5 if word_count > 0 else 0

        # Detect emotional beats from keywords
        emotional_beats = []
        beat_keywords = {
            "tension": ["fear", "afraid", "danger", "threat", "lurk", "dark", "scream", "horror"],
            "confrontation": ["confront", "demand", "accuse", "argue", "fight", "angry", "rage"],
            "revelation": ["reveal", "discover", "truth", "realize", "secret", "shock", "learn"],
            "intimacy": ["love", "care", "gentle", "whisper", "touch", "embrace", "comfort"],
            "resolve": ["decide", "must", "will", "determination", "stand", "fight back", "vow"],
        }
        text_lower = (dialogue_text + " " + nano_prompt).lower()
        for beat_type, keywords in beat_keywords.items():
            if any(kw in text_lower for kw in keywords):
                emotional_beats.append(beat_type)

        # Detect line alternation (back-and-forth dialogue)
        has_alternation = len(quoted) > 2 and speaker_count > 1

        return {
            "speaker_count": speaker_count,
            "lines": quoted,
            "line_count": len(quoted),
            "word_count": word_count,
            "spoken_duration": round(spoken_duration, 1),
            "emotional_beats": emotional_beats,
            "has_alternation": has_alternation,
            "characters": characters,
        }


class CoveragePlanner:
    """
    Generate a segment plan based on dialogue analysis.
    """

    @staticmethod
    def plan(shot: Dict, analysis: Dict) -> List[Dict]:
        """
        Create a segment plan for a dialogue shot.
        Returns list of segment dicts ready for shot_plan.json.
        """
        duration = shot.get("duration", 10)
        speaker_count = analysis.get("speaker_count", 1)
        characters = analysis.get("characters", [])
        lines = analysis.get("lines", [])

        # Only segment if duration > MAX_LTX_SEGMENT
        if duration <= MAX_LTX_SEGMENT:
            return []  # No segmentation needed

        # Get coverage template
        template_key = min(speaker_count, 3)
        template = COVERAGE_TEMPLATES.get(template_key, COVERAGE_TEMPLATES[1])

        # Allocate durations
        segments = []
        remaining = duration
        cumulative = 0.0

        for i, tmpl in enumerate(template):
            # Calculate duration from ratio
            seg_duration = max(tmpl["min"], round(duration * tmpl["ratio"]))
            seg_duration = min(seg_duration, MAX_LTX_SEGMENT)
            seg_duration = min(seg_duration, remaining)

            if seg_duration < MIN_SEGMENT:
                continue

            # Determine which character this segment focuses on
            seg_characters = list(characters)  # default: all
            if "over_shoulder_a" in tmpl["type"] or "reaction_a" in tmpl["type"] or "medium_a" in tmpl["type"]:
                seg_characters = [characters[0]] if characters else []
            elif "over_shoulder_b" in tmpl["type"] or "reaction_b" in tmpl["type"] or "medium_b" in tmpl["type"]:
                seg_characters = [characters[1]] if len(characters) > 1 else characters[:1]
            elif "close_up_c" in tmpl["type"]:
                seg_characters = [characters[2]] if len(characters) > 2 else characters[:1]

            # Get dialogue for this segment
            seg_dialogue = ""
            if lines:
                # Distribute dialogue lines across segments
                line_start = int(len(lines) * (cumulative / duration))
                line_end = int(len(lines) * ((cumulative + seg_duration) / duration))
                seg_lines = lines[line_start:max(line_start + 1, line_end)]
                seg_dialogue = " ".join(seg_lines)[:200]

            # Camera motion
            motion = SEGMENT_MOTION.get(tmpl["type"], "static")

            segment = {
                "segment_index": i,
                "segment_type": tmpl["type"],
                "start_time": round(cumulative, 1),
                "end_time": round(cumulative + seg_duration, 1),
                "duration": seg_duration,
                "characters": seg_characters,
                "camera_style": tmpl["camera"],
                "lens": tmpl["lens"],
                "motion": motion,
                "dialogue_context": seg_dialogue,
                "morph_constraint": "face stable NO morphing, character consistent",
            }
            segments.append(segment)

            cumulative += seg_duration
            remaining -= seg_duration

            if remaining < MIN_SEGMENT:
                # Extend last segment to absorb remainder
                if segments:
                    segments[-1]["duration"] += remaining
                    segments[-1]["end_time"] = round(segments[-1]["end_time"] + remaining, 1)
                break

        return segments


class SegmentBuilder:
    """
    Convert coverage plan into the segment array format
    that ATLAS shot_plan.json expects.
    """

    @staticmethod
    def build_segment_prompts(shot: Dict, segments: List[Dict], cast_map: Dict = None) -> List[Dict]:
        """
        Generate LTX-ready segment entries with prompts.
        Each segment gets its own nano_prompt and ltx_motion_prompt.
        """
        base_nano = shot.get("nano_prompt", "")
        base_ltx = shot.get("ltx_motion_prompt", "")
        shot_id = shot.get("shot_id", "")

        result_segments = []
        for seg in segments:
            # Build nano_prompt for this segment
            seg_type = seg.get("segment_type", "")
            chars = seg.get("characters", [])
            dialogue = seg.get("dialogue_context", "")
            camera = seg.get("camera_style", "medium")
            lens = seg.get("lens", "50mm")

            # Adapt the base prompt for this segment's framing
            if "over_shoulder" in seg_type:
                char_name = chars[0] if chars else "character"
                nano = f"{camera} shot, {lens}, over-the-shoulder framing on {char_name}, "
                if dialogue:
                    nano += f'speaking: "{dialogue[:100]}", '
                nano += "cinematic depth of field, production lighting"
            elif "reaction" in seg_type:
                char_name = chars[0] if chars else "character"
                nano = f"close-up reaction shot, {lens}, {char_name} listening and processing, "
                nano += "subtle emotion, cinematic lighting, face stable"
            elif "establishing" in seg_type:
                nano = f"wide establishing shot, {lens}, showing the full scene geography, "
                nano += "all characters visible, cinematic composition"
            elif "close_up" in seg_type:
                char_name = chars[0] if chars else "character"
                nano = f"extreme close-up, {lens}, {char_name}, "
                if dialogue:
                    nano += f'delivering: "{dialogue[:80]}", '
                nano += "catch light in eyes, shallow depth of field, face stable"
            elif "group" in seg_type:
                nano = f"group shot, {lens}, {', '.join(chars[:3])}, "
                nano += "two-shot or three-shot framing, balanced composition"
            else:
                nano = f"{camera} shot, {lens}, "
                if chars:
                    nano += f"{', '.join(chars[:2])}, "
                nano += base_nano[:100]

            # Add gold standard negatives
            nano += ", NO grid, NO collage, NO split screen, NO morphing faces, NO watermarks"

            # Build LTX motion prompt
            motion = seg.get("motion", "static")
            morph = seg.get("morph_constraint", "face stable NO morphing")
            dur = seg.get("duration", 6)

            ltx = f"0-2s {motion} hold establishing frame, "
            if dur > 4:
                ltx += f"2-{dur}s slow {motion}, "
            if dialogue:
                ltx += f'character speaks: "{dialogue[:100]}", '
            ltx += f"{morph}, character consistent, natural micro-movements"

            # Get character reference from cast_map
            char_ref = ""
            if chars and cast_map:
                entry = cast_map.get(chars[0], {})
                char_ref = entry.get("character_reference_url", "") or entry.get("headshot_url", "")

            segment_entry = {
                "segment_index": seg["segment_index"],
                "segment_type": seg_type,
                "start_time": seg["start_time"],
                "end_time": seg["end_time"],
                "duration": seg["duration"],
                "nano_prompt": nano,
                "ltx_motion_prompt": ltx,
                "characters": chars,
                "character_reference_url": char_ref,
                "camera_style": camera,
                "lens": lens,
                "motion": motion,
            }
            result_segments.append(segment_entry)

        return result_segments


# ═══════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════

def auto_segment_dialogue_shot(shot: Dict, cast_map: Dict = None) -> List[Dict]:
    """
    Main entry: analyze a shot and auto-segment if it's a dialogue scene > 15s.

    Returns empty list if no segmentation needed.
    Returns segment array if dialogue segmentation was applied.

    Usage:
      segments = auto_segment_dialogue_shot(shot, cast_map)
      if segments:
          shot["segments"] = segments
          shot["_segmentation_method"] = "dialogue_aware"
    """
    duration = shot.get("duration", 0)
    characters = shot.get("characters", [])

    # Only segment if > MAX_LTX_SEGMENT and has characters
    if duration <= MAX_LTX_SEGMENT:
        return []

    # Analyze dialogue content
    analysis = DialogueAnalyzer.analyze(shot)

    # Generate coverage plan
    plan = CoveragePlanner.plan(shot, analysis)
    if not plan:
        return []

    # Build segment prompts
    segments = SegmentBuilder.build_segment_prompts(shot, plan, cast_map)

    logger.info(
        f"[DIALOGUE-SEG] Shot {shot.get('shot_id', '?')}: "
        f"{duration}s → {len(segments)} segments "
        f"({analysis['speaker_count']} speakers, {analysis['word_count']} words, "
        f"beats: {analysis['emotional_beats']})"
    )

    return segments


def should_segment_dialogue(shot: Dict) -> bool:
    """Quick check: does this shot need dialogue-aware segmentation?"""
    duration = shot.get("duration", 0)
    characters = shot.get("characters", [])
    has_dialogue = bool(shot.get("dialogue_text", "")) or bool(shot.get("beat_text", ""))

    return (
        duration > MAX_LTX_SEGMENT and
        len(characters) >= 1 and
        (has_dialogue or len(characters) >= 2)
    )


def get_segmentation_preview(shot: Dict) -> Dict:
    """Preview what segmentation would look like without applying it."""
    analysis = DialogueAnalyzer.analyze(shot)
    plan = CoveragePlanner.plan(shot, analysis)

    return {
        "shot_id": shot.get("shot_id", ""),
        "duration": shot.get("duration", 0),
        "needs_segmentation": should_segment_dialogue(shot),
        "analysis": analysis,
        "planned_segments": len(plan),
        "segment_types": [s.get("segment_type", "") for s in plan],
        "segment_durations": [s.get("duration", 0) for s in plan],
    }
