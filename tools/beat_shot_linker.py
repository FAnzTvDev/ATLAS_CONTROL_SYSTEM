#!/usr/bin/env python3
"""
ATLAS V27.6 — Beat-Shot Linker (Cinematographic Logic Engine)
=============================================================
Connects story bible beats to shots with PHYSICAL MOTIVATION.

THE PROBLEM THIS SOLVES:
In cinema, every cut is motivated. The camera changes framing because:
  1. The character MOVED (walked, turned, picked something up)
  2. The character LOOKED at something new (eyes shift → cut to what they see)
  3. The emotion SHIFTED (realization, shock, decision)
  4. Time passed (dissolve, fade)

Without this, you get:
  - Jump cuts (same framing, no motivation, jarring)
  - Dead eye-lines (character stares at camera or into void)
  - Duplicate compositions (two identical medium_close shots back-to-back)
  - Dialogue on wrong shots (establishing shot speaks, close-up is silent)

THE SOLUTION:
  1. Parse beats for PHYSICAL ACTIONS (enters, photographs, reads, picks up, turns, looks)
  2. Map each shot to a beat based on dialogue content, shot type, and position
  3. Derive EYE-LINE TARGET from the beat's action (reading → DOWN at letter, photographing → UP at shelves)
  4. Derive BODY ACTION from the beat (entering → walking, reading → still, pocketing → hand movement)
  5. Flag UNMOTIVATED CUTS (two adjacent shots, same framing, no action change between them)
  6. Flag MISPLACED DIALOGUE (establishing shot has dialogue, close-up is silent)

This runs PRE-compilation as a diagnostic, and its output feeds into:
  - OTS Enforcer (eye-line direction)
  - Film Engine (performance direction)
  - Story Judge (narrative validation)
"""

import re
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ── Physical action vocabulary ──
# Maps beat keywords to character physical state

ACTION_KEYWORDS = {
    # MOVEMENT actions — character changes position
    "enters": {"body": "walking into frame", "movement": True, "zone_change": True},
    "walks": {"body": "walking through space", "movement": True, "zone_change": True},
    "crosses": {"body": "crossing the room", "movement": True, "zone_change": True},
    "approaches": {"body": "moving toward", "movement": True, "zone_change": False},
    "follows": {"body": "following behind", "movement": True, "zone_change": True},
    "steps": {"body": "stepping forward", "movement": True, "zone_change": False},
    "moves": {"body": "shifting position", "movement": True, "zone_change": False},

    # OBSERVATION actions — character looks at something
    "photographs": {"body": "holding camera, framing shots", "eye_target": "through viewfinder, scanning room", "movement": True},
    "examines": {"body": "leaning in, studying closely", "eye_target": "down at object in hands", "movement": False},
    "reads": {"body": "holding paper/book, still", "eye_target": "down at text", "movement": False},
    "discovers": {"body": "freezing in place, hands pause", "eye_target": "widening on discovery", "movement": False},
    "scans": {"body": "head turning slowly", "eye_target": "sweeping across shelves/room", "movement": False},
    "looks": {"body": "turning head", "eye_target": "toward target", "movement": False},
    "stares": {"body": "frozen, tension visible", "eye_target": "fixed on target", "movement": False},
    "notices": {"body": "slight head tilt, attention caught", "eye_target": "shifting to new object", "movement": False},

    # MANIPULATION actions — character interacts with object
    "picks up": {"body": "reaching down, lifting", "eye_target": "down at object", "movement": False, "object_interaction": True},
    "opens": {"body": "hands working, pulling apart", "eye_target": "down at object", "movement": False, "object_interaction": True},
    "pockets": {"body": "hand moving to pocket, tucking away", "eye_target": "brief glance down then up", "movement": False, "object_interaction": True},
    "holds": {"body": "gripping, hands visible", "eye_target": "at held object", "movement": False, "object_interaction": True},
    "unfolds": {"body": "carefully opening paper", "eye_target": "down at paper", "movement": False, "object_interaction": True},
    "pulls": {"body": "reaching, extracting", "eye_target": "at extraction point", "movement": False, "object_interaction": True},
    "falls": {"body": "startled reaction", "eye_target": "tracking falling object downward", "movement": False, "object_interaction": True},

    # EMOTIONAL actions — character's internal state changes
    "realizes": {"body": "breath catches, posture shifts", "eye_target": "unfocused then sharpening", "movement": False, "emotion_shift": True},
    "decides": {"body": "jaw sets, posture straightens", "eye_target": "resolute, forward", "movement": False, "emotion_shift": True},
    "reacts": {"body": "visible physical response", "eye_target": "on source of reaction", "movement": False, "emotion_shift": True},

    # DIRECTIONAL actions — character orients toward specific target
    "toward the door": {"body": "turning body toward exit", "eye_target": "toward door/exit", "movement": False, "direction": "door"},
    "toward the window": {"body": "turning toward light source", "eye_target": "toward window", "movement": False, "direction": "window"},
}


@dataclass
class BeatAction:
    """Physical action extracted from a story bible beat."""
    beat_index: int
    beat_text: str
    primary_action: str  # The dominant verb
    body_state: str  # What the body is doing
    eye_target: str  # Where the eyes are directed
    has_movement: bool  # Is the character changing position?
    has_object: bool  # Is there object interaction?
    has_emotion_shift: bool  # Does internal state change?
    direction: Optional[str] = None  # Specific directional target
    objects: List[str] = field(default_factory=list)  # Objects mentioned in beat


@dataclass
class ShotBeatLink:
    """Connection between a shot and its motivating beat."""
    shot_id: str
    shot_type: str
    beat_index: int  # Which beat this shot belongs to (0-indexed)
    beat_action: Optional[BeatAction]
    eye_line: str  # Derived eye-line direction for this shot
    body_direction: str  # Derived body/performance direction
    cut_motivation: str  # WHY the camera cuts here
    issues: List[str] = field(default_factory=list)  # Problems detected


@dataclass
class SceneContinuityPlan:
    """Full cinematographic plan for a scene."""
    scene_id: str
    beats: List[BeatAction]
    shot_links: List[ShotBeatLink]
    issues: List[str] = field(default_factory=list)


class BeatShotLinker:
    """
    Links story bible beats to shots with physical motivation.

    The core insight: every cut in cinema is motivated by CHANGE.
    If nothing changed (position, attention, emotion), the camera holds.
    """

    def __init__(self):
        pass

    def parse_beat_actions(self, beats: List) -> List[BeatAction]:
        """Extract physical actions from story bible beats."""
        results = []
        for i, beat in enumerate(beats):
            text = beat.get("description", beat.get("beat", str(beat))) if isinstance(beat, dict) else str(beat)
            text_lower = text.lower()

            # Find matching action keywords
            primary_action = "static"
            body_state = "still, present in scene"
            eye_target = "neutral, scene-level"
            has_movement = False
            has_object = False
            has_emotion_shift = False
            direction = None
            objects = []

            # Scan for action keywords (longest match first)
            sorted_keywords = sorted(ACTION_KEYWORDS.keys(), key=len, reverse=True)
            for keyword in sorted_keywords:
                if keyword in text_lower:
                    action_data = ACTION_KEYWORDS[keyword]
                    primary_action = keyword
                    body_state = action_data.get("body", body_state)
                    eye_target = action_data.get("eye_target", eye_target)
                    has_movement = action_data.get("movement", False)
                    has_object = action_data.get("object_interaction", False)
                    has_emotion_shift = action_data.get("emotion_shift", False)
                    direction = action_data.get("direction", None)
                    break

            # Extract objects mentioned (books, letters, doors, etc.)
            object_patterns = [
                r'\b(letter|book|note|photograph|camera|door|window|painting|desk|chair|shelf|shelves|manuscript)\b'
            ]
            for pattern in object_patterns:
                objects.extend(re.findall(pattern, text_lower))

            results.append(BeatAction(
                beat_index=i,
                beat_text=text,
                primary_action=primary_action,
                body_state=body_state,
                eye_target=eye_target,
                has_movement=has_movement,
                has_object=has_object,
                has_emotion_shift=has_emotion_shift,
                direction=direction,
                objects=objects,
            ))

        return results

    def link_shots_to_beats(self, shots: List[Dict], beats: List[BeatAction]) -> List[ShotBeatLink]:
        """
        Map each shot to its most likely beat based on:
        1. Dialogue content matching beat content
        2. Shot position in sequence (early shots → beat 1, late → beat N)
        3. Shot type (establishing → beat 1, closing → last beat)
        4. Object/action references in prompts
        """
        if not beats:
            return [ShotBeatLink(
                shot_id=s.get("shot_id", ""),
                shot_type=s.get("shot_type", ""),
                beat_index=-1,
                beat_action=None,
                eye_line="neutral",
                body_direction="static",
                cut_motivation="NO BEATS — cannot derive motivation",
                issues=["No story bible beats to link against"],
            ) for s in shots]

        links = []
        num_shots = len(shots)
        num_beats = len(beats)

        for i, shot in enumerate(shots):
            shot_id = shot.get("shot_id", "")
            shot_type = (shot.get("shot_type") or "").lower()
            dialogue = (shot.get("dialogue_text") or "").lower()
            nano = (shot.get("nano_prompt") or "").lower()

            # ── RULE 1: Shot type hints ──
            if shot_type in ("establishing", "wide") and i == 0:
                beat_idx = 0  # First shot → first beat
            elif shot_type == "closing" or i == num_shots - 1:
                beat_idx = num_beats - 1  # Last shot → last beat
            else:
                # ── RULE 2: Position-based proportional mapping ──
                # Shot 3 of 8 in a 3-beat scene → beat 1 (early third)
                proportion = i / max(num_shots - 1, 1)
                beat_idx = min(int(proportion * num_beats), num_beats - 1)

            # ── RULE 3: Dialogue content matching ──
            # If dialogue mentions keywords from a specific beat, override
            for bi, beat in enumerate(beats):
                beat_lower = beat.beat_text.lower()
                # Check if distinctive beat words appear in dialogue
                beat_words = set(re.findall(r'\b\w{4,}\b', beat_lower)) - {
                    "nadia", "cole", "with", "from", "that", "this", "their", "into", "have"
                }
                dialogue_words = set(re.findall(r'\b\w{4,}\b', dialogue))
                overlap = beat_words & dialogue_words
                if len(overlap) >= 2:
                    beat_idx = bi
                    break
                # Check for object mentions
                for obj in beat.objects:
                    if obj in dialogue or obj in nano:
                        beat_idx = bi
                        break

            beat_action = beats[beat_idx]

            # ── Derive eye-line from beat action ──
            eye_line = beat_action.eye_target
            if "letter" in dialogue or "letter" in (beat_action.beat_text.lower()):
                eye_line = "down at letter in hands, reading"
            elif "book" in dialogue or "edition" in dialogue or "shelf" in nano:
                eye_line = "scanning across book spines at eye level"
            elif beat_action.direction == "door":
                eye_line = "turning to look toward door/exit"

            # ── Derive body direction from beat action ──
            body_direction = beat_action.body_state

            # ── Derive cut motivation ──
            if i == 0:
                cut_motivation = "SCENE OPEN — establishing spatial geography"
            elif beat_action.has_movement:
                cut_motivation = f"CHARACTER MOVED — {beat_action.primary_action}"
            elif beat_action.has_object:
                cut_motivation = f"OBJECT INTERACTION — {beat_action.primary_action} {', '.join(beat_action.objects)}"
            elif beat_action.has_emotion_shift:
                cut_motivation = f"EMOTION SHIFT — {beat_action.primary_action}"
            elif i > 0 and beats[min(beat_idx, num_beats-1)].beat_index != links[-1].beat_index:
                cut_motivation = f"NEW BEAT — transition from beat {links[-1].beat_index+1} to beat {beat_idx+1}"
            else:
                cut_motivation = "UNMOTIVATED — same beat, same state, no change detected"

            # ── Detect issues ──
            issues = []

            # Issue: Dialogue on establishing shot
            if shot_type == "establishing" and dialogue:
                issues.append(f"DIALOGUE ON ESTABLISHING: establishing shots show geography, not performance. "
                             f"Move dialogue to medium_close/close_up.")

            # Issue: Adjacent same-type shots with no beat change
            if i > 0 and links:
                prev = links[-1]
                if (prev.shot_type == shot_type and
                    prev.beat_index == beat_idx and
                    not beat_action.has_movement and
                    not beat_action.has_object):
                    issues.append(f"JUMP CUT: {prev.shot_id} and {shot_id} are both {shot_type} "
                                 f"in same beat with no physical change. Merge or add motivation.")

            # Issue: Character shot with no eye-line target
            chars = shot.get("characters") or []
            if chars and eye_line in ("neutral", "neutral, scene-level"):
                issues.append(f"DEAD EYE-LINE: {shot_id} has character but no specific eye target. "
                             f"What are they looking at?")

            # Issue: B-roll tagged as character shot
            if shot_type == "b-roll" and chars and dialogue:
                issues.append(f"IDENTITY CONFUSION: {shot_id} is b-roll but has characters AND dialogue. "
                             f"Should this be a medium_close or insert?")

            links.append(ShotBeatLink(
                shot_id=shot_id,
                shot_type=shot_type,
                beat_index=beat_idx,
                beat_action=beat_action,
                eye_line=eye_line,
                body_direction=body_direction,
                cut_motivation=cut_motivation,
                issues=issues,
            ))

        return links

    def analyze_scene(self, scene_id: str, shots: List[Dict],
                      story_bible_scene: Dict) -> SceneContinuityPlan:
        """Full cinematographic analysis of a scene."""
        beats_raw = story_bible_scene.get("beats", [])
        beats = self.parse_beat_actions(beats_raw)

        scene_shots = [s for s in shots if s.get("shot_id", "").startswith(scene_id)]
        links = self.link_shots_to_beats(scene_shots, beats)

        # Scene-level issues
        scene_issues = []

        # Check: every beat should have at least one shot
        covered_beats = set(l.beat_index for l in links)
        for bi in range(len(beats)):
            if bi not in covered_beats:
                scene_issues.append(f"UNCOVERED BEAT: Beat {bi+1} ({beats[bi].beat_text[:60]}) "
                                   f"has no shots mapped to it.")

        # Check: no two adjacent shots should have identical framing without motivation
        unmotivated_count = sum(1 for l in links if "UNMOTIVATED" in l.cut_motivation)
        if unmotivated_count > 0:
            scene_issues.append(f"UNMOTIVATED CUTS: {unmotivated_count} cuts have no physical "
                               f"motivation (same beat, same state).")

        return SceneContinuityPlan(
            scene_id=scene_id,
            beats=beats,
            shot_links=links,
            issues=scene_issues,
        )

    def print_analysis(self, plan: SceneContinuityPlan):
        """Print human-readable analysis."""
        print(f"\n{'='*80}")
        print(f"  BEAT-SHOT CONTINUITY ANALYSIS — Scene {plan.scene_id}")
        print(f"  {len(plan.beats)} beats → {len(plan.shot_links)} shots")
        print(f"{'='*80}")

        print(f"\n  PHYSICAL JOURNEY (from story bible):")
        for b in plan.beats:
            move = "🚶" if b.has_movement else "🧍"
            obj = "🤲" if b.has_object else "  "
            emo = "💭" if b.has_emotion_shift else "  "
            print(f"    Beat {b.beat_index+1} {move}{obj}{emo}: {b.beat_text[:80]}")
            print(f"           body: {b.body_state}")
            print(f"           eyes: {b.eye_target}")
            if b.objects:
                print(f"           objects: {', '.join(b.objects)}")

        print(f"\n  SHOT-BY-SHOT PLAN:")
        total_issues = 0
        for link in plan.shot_links:
            beat_num = link.beat_index + 1 if link.beat_index >= 0 else "?"
            status = "✓" if not link.issues else "✗"
            print(f"\n    {status} {link.shot_id} ({link.shot_type}) → Beat {beat_num}")
            print(f"      Cut motivation: {link.cut_motivation}")
            print(f"      Eye-line: {link.eye_line}")
            print(f"      Body: {link.body_direction}")
            for issue in link.issues:
                print(f"      ⚠ {issue}")
                total_issues += 1

        if plan.issues:
            print(f"\n  SCENE-LEVEL ISSUES:")
            for issue in plan.issues:
                print(f"    ⚠ {issue}")
                total_issues += len(plan.issues)

        print(f"\n  TOTAL ISSUES: {total_issues}")
        print(f"{'='*80}")

        return total_issues


if __name__ == "__main__":
    import json, sys

    project = sys.argv[1] if len(sys.argv) > 1 else "pipeline_outputs/victorian_shadows_ep1"
    scene_id = sys.argv[2] if len(sys.argv) > 2 else "002"

    with open(f"{project}/shot_plan.json") as f:
        sp = json.load(f)
    shots = sp if isinstance(sp, list) else sp.get("shots", [])

    with open(f"{project}/story_bible.json") as f:
        sb = json.load(f)
    sb_scene = next((s for s in sb.get("scenes", []) if s.get("scene_id") == scene_id), None)

    if not sb_scene:
        print(f"Scene {scene_id} not found in story bible")
        sys.exit(1)

    linker = BeatShotLinker()
    plan = linker.analyze_scene(scene_id, shots, sb_scene)
    issues = linker.print_analysis(plan)

    sys.exit(1 if issues > 0 else 0)
