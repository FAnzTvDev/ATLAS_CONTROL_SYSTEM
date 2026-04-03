#!/usr/bin/env python3
"""
V20 Shot Type Enricher — Editorial Intelligence Post-Processor

PROBLEM: The shot expander produces only wide/medium (2 types across 266 shots).
V9 hand-crafted manifests use 19+ shot types with motivated editorial flow.

SOLUTION: This enricher runs AFTER fix-v16 and REPLACES the monotone wide/medium
pattern with V9-style editorial coverage based on scene content analysis.

DESIGN PRINCIPLES (from V9 analysis):
1. Every shot type serves a PURPOSE — geography, emotion, texture, or dialogue
2. Scene-level TEMPLATES based on content (dialogue, arrival, ritual, etc.)
3. Shot type VARIETY within scenes — never 2+ consecutive same-type shots
4. Motivated TRANSITIONS — size progression drives emotional escalation
5. INSERT/REACTION/OTS shots break up dialogue metronomes
6. ESTABLISHING shots reset geography at scene boundaries and every 6-8 shots
7. INTERCUTTING for phone/V.O. scenes (shots in two locations)

WHAT THIS MODULE DOES:
- Reads shot_plan.json after fix-v16 has run
- Analyzes each scene's content (dialogue count, characters, beats, location)
- Assigns a SCENE TEMPLATE (dialogue_two_person, arrival, ritual, etc.)
- Rewrites shot types using V9-style editorial patterns
- Preserves all other shot data (prompts, durations, characters, etc.)
- Writes updated shot_plan.json

WHAT IT DOES NOT DO:
- Does NOT change nano_prompt or ltx_motion_prompt content
- Does NOT change durations (that's the duration scaler's job)
- Does NOT add or remove shots (that's the scene_template_enforcer's job)
- Does NOT modify characters or casting
"""

import json
import re
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════
# V9 EDITORIAL PATTERNS — Extracted from V9 BROADCAST READY manifest
# Each pattern is a sequence of shot types that tells a story
# ═══════════════════════════════════════════════════════════════════

@dataclass
class EditorialPattern:
    """A reusable editorial shot sequence."""
    name: str
    description: str
    # Shot type sequence — applied cyclically if scene has more shots
    sequence: List[str]
    # Which shots in the sequence should get dialogue (by index)
    dialogue_slots: List[int] = field(default_factory=list)
    # Minimum shots before this pattern makes sense
    min_shots: int = 2


# V9's actual patterns, extracted from the comparison analysis
SCENE_PATTERNS = {
    # ─── DIALOGUE SCENES ───
    "dialogue_two_person": EditorialPattern(
        name="Two-Person Dialogue",
        description="V9 pub pattern: establish → two-shot → reaction → OTS",
        sequence=[
            "establishing",           # 1. Set the room
            "two_shot",               # 2. Both characters together
            "medium",                 # 3. Speaker A
            "over_the_shoulder",      # 4. Speaker B (OTS from A)
            "close",                  # 5. Reaction
            "medium",                 # 6. Speaker A response
            "over_the_shoulder",      # 7. Speaker B response (OTS)
            "wide",                   # 8. Geography reset
            "medium",                 # 9. Continue
            "close",                  # 10. Emotion beat
            "reaction",              # 11. Listener reacts
            "medium",                 # 12. Resolution
        ],
        dialogue_slots=[2, 3, 5, 6, 9, 11],
        min_shots=4,
    ),

    "dialogue_confrontation": EditorialPattern(
        name="Confrontation Dialogue",
        description="Tense exchange with power dynamics",
        sequence=[
            "establishing",           # 1. Set the arena
            "medium",                 # 2. Dominant character
            "close",                  # 3. Subordinate reaction
            "over_the_shoulder",      # 4. Dominant pushes
            "close",                  # 5. Subordinate breaking
            "wide",                   # 6. Geography — feel the distance
            "medium",                 # 7. Subordinate pushes back
            "close",                  # 8. Dominant surprised
            "two_shot",              # 9. Both in frame — power shift
            "medium",                 # 10. Resolution speaker
            "reaction",              # 11. Other reacts
            "wide",                   # 12. Aftermath geography
        ],
        dialogue_slots=[1, 3, 4, 6, 7, 9],
        min_shots=4,
    ),

    "dialogue_phone_intercut": EditorialPattern(
        name="Phone Call / Intercut",
        description="V9 apartment/law office pattern: location A → face → location B → face",
        sequence=[
            "establishing",           # 1. Location A
            "medium_close",           # 2. Character A on phone
            "establishing",           # 3. Location B (intercut!)
            "medium_close",           # 4. Character B (or back to A)
            "medium",                 # 5. A — decision/reaction
            "medium_close",           # 6. A — emotion
        ],
        dialogue_slots=[1, 3, 4, 5],
        min_shots=4,
    ),

    "dialogue_group": EditorialPattern(
        name="Group Dialogue (3+)",
        description="Multiple speakers with geography resets",
        sequence=[
            "wide",                   # 1. Establish the group
            "medium",                 # 2. First speaker
            "reaction",              # 3. Group/listener reaction
            "over_the_shoulder",      # 4. Second speaker
            "close",                  # 5. Key listener
            "wide",                   # 6. Reset — see everyone
            "medium",                 # 7. Third speaker or callback
            "two_shot",              # 8. Key pair
            "medium",                 # 9. Resolution speaker
            "close",                  # 10. Final emotion
            "wide",                   # 11. Geography close
            "reaction",              # 12. Group reaction
        ],
        dialogue_slots=[1, 3, 4, 6, 8, 9],
        min_shots=4,
    ),

    # ─── NON-DIALOGUE SCENES ───
    "ritual_ceremony": EditorialPattern(
        name="Ritual / Ceremony",
        description="V9 opening: geography → subject → texture (3 inserts) → payoff",
        sequence=[
            "establishing",           # 1. Exterior or room wide
            "wide",                   # 2. Interior geography
            "detail",                 # 3. Hands / action detail
            "close",                  # 4. Character face
            "insert",                 # 5. Prop/texture (candle, sigil)
            "insert",                 # 6. Another texture element
            "insert",                 # 7. Third atmospheric insert
            "medium",                 # 8. Character performing action
            "wide",                   # 9. Climax wide
        ],
        dialogue_slots=[],
        min_shots=5,
    ),

    "arrival_approach": EditorialPattern(
        name="Arrival / Approach",
        description="V9 manor arrival: ext → tracking → arrive → interior reveal → reverse → OTS",
        sequence=[
            "establishing",           # 1. External geography
            "tracking",              # 2. Character moving toward location
            "medium",                 # 3. Character at threshold
            "establishing",           # 4. Interior reveal (NEW master)
            "reverse_medium",         # 5. Character from inside POV
            "over_the_shoulder",      # 6. First interaction
        ],
        dialogue_slots=[5],
        min_shots=3,
    ),

    "travel_journey": EditorialPattern(
        name="Travel / Journey",
        description="V9 bus ride: landscape → interior → insert → sign",
        sequence=[
            "wide",                   # 1. Landscape / exterior
            "medium",                 # 2. Character in vehicle
            "insert",                 # 3. Phone/map/detail
            "wide",                   # 4. Landscape changing
            "medium",                 # 5. Character reaction
            "detail",                 # 6. Arrival marker / sign
        ],
        dialogue_slots=[],
        min_shots=3,
    ),

    "exploration_discovery": EditorialPattern(
        name="Exploration / Discovery",
        description="Moving through space, finding things",
        sequence=[
            "wide",                   # 1. New room/space
            "tracking",              # 2. Following character
            "medium",                 # 3. Character examines
            "insert",                 # 4. Object discovered
            "close",                  # 5. Reaction face
            "wide",                   # 6. Pull back — context
        ],
        dialogue_slots=[],
        min_shots=3,
    ),

    "suspense_atmosphere": EditorialPattern(
        name="Suspense / Atmosphere",
        description="Gothic horror tension building",
        sequence=[
            "wide",                   # 1. Empty space — dread
            "tracking",              # 2. Slow push into space
            "close",                  # 3. Character sensing something
            "insert",                 # 4. Atmospheric detail (shadow, sound)
            "medium",                 # 5. Character reacts
            "wide",                   # 6. Space has changed
        ],
        dialogue_slots=[],
        min_shots=3,
    ),

    "will_reading_legal": EditorialPattern(
        name="Will Reading / Legal / Office",
        description="Formal setting with multiple parties — V9 study pattern",
        sequence=[
            "establishing",           # 1. The room — formal
            "medium",                 # 2. Authority figure (lawyer)
            "close",                  # 3. Protagonist reaction
            "over_the_shoulder",      # 4. Back to authority
            "medium",                 # 5. Protagonist challenges
            "wide",                   # 6. Feel the room
            "medium",                 # 7. Authority responds
            "close",                  # 8. Protagonist emotion
            "reaction",              # 9. Third party (Arthur, etc.)
            "medium",                 # 10. Decision beat
            "two_shot",              # 11. Key pair
            "wide",                   # 12. Resolution geography
        ],
        dialogue_slots=[1, 3, 4, 6, 7, 9],
        min_shots=4,
    ),

    # ─── FALLBACK ───
    "generic": EditorialPattern(
        name="Generic Scene",
        description="Default with geography resets and variety",
        sequence=[
            "establishing",           # 1. Geography
            "medium",                 # 2. Primary subject
            "close",                  # 3. Emotion / detail
            "wide",                   # 4. Reset
            "medium",                 # 5. Action
            "insert",                 # 6. Detail / prop
            "medium",                 # 7. Continue
            "reaction",              # 8. React
            "wide",                   # 9. Geography close
        ],
        dialogue_slots=[1, 4, 6],
        min_shots=2,
    ),
}


# ═══════════════════════════════════════════════════════════════════
# SCENE CLASSIFICATION — Detect what template to apply
# ═══════════════════════════════════════════════════════════════════

# Keywords for each pattern
PATTERN_TRIGGERS = {
    "ritual_ceremony": [
        "ritual", "ceremony", "altar", "candle", "summoning", "incantation",
        "sacrifice", "chanting", "sigil", "symbol", "prayer", "blessing",
    ],
    "arrival_approach": [
        "arrive", "arrival", "approach", "gate", "door", "enter",
        "threshold", "knock", "welcome", "first time", "greet",
    ],
    "travel_journey": [
        "bus", "train", "car", "drive", "road", "highway", "journey",
        "travel", "ride", "window seat", "passing", "landscape",
    ],
    "exploration_discovery": [
        "explore", "wander", "discover", "find", "search", "room by room",
        "investigate", "examine", "hallway", "corridor", "uncover",
    ],
    "suspense_atmosphere": [
        "shadow", "dark", "noise", "creak", "night", "alone",
        "haunting", "ghost", "eerie", "silence", "whisper", "appear",
    ],
    "will_reading_legal": [
        "will", "lawyer", "solicitor", "legal", "estate", "inheritance",
        "document", "sign", "clause", "condition", "property", "terms",
        "office", "study", "desk", "formal",
    ],
    "dialogue_confrontation": [
        "confront", "argue", "demand", "accuse", "threaten", "anger",
        "shout", "furious", "challenge", "standoff", "refuse",
    ],
    "dialogue_phone_intercut": [
        "phone", "call", "v.o.", "voice over", "voiceover", "intercut",
        "receiver", "dial", "ring", "hang up", "on the line",
    ],
}


def classify_scene(scene_shots: List[Dict], story_bible_scene: Dict = None) -> str:
    """
    Analyze a scene's content and return the best matching template name.
    Uses dialogue count, character count, location, and beat descriptions.
    """
    # Gather all text for analysis
    texts = []
    dialogue_count = 0
    char_set = set()

    for s in scene_shots:
        desc = s.get("description", "") or s.get("beat_description", "") or ""
        dlg = s.get("dialogue_text", "") or s.get("dialogue", "") or ""
        loc = s.get("location", "") or ""
        texts.append(f"{desc} {dlg} {loc}".lower())
        if dlg.strip():
            dialogue_count += 1
        chars = s.get("characters", [])
        if isinstance(chars, str):
            chars = [c.strip() for c in chars.split(",") if c.strip()]
        for c in chars:
            char_set.add(c.upper())

    # Add story bible scene text if available
    if story_bible_scene and isinstance(story_bible_scene, dict):
        sb_desc = story_bible_scene.get("description", "") or ""
        sb_title = story_bible_scene.get("title", "") or ""
        texts.append(f"{sb_desc} {sb_title}".lower())
        for beat in story_bible_scene.get("beats", []):
            if isinstance(beat, dict):
                texts.append((beat.get("description", "") or "").lower())

    combined = " ".join(texts)

    # Score each pattern by keyword matches
    scores = {}
    for pattern_name, keywords in PATTERN_TRIGGERS.items():
        score = sum(1 for kw in keywords if kw in combined)
        if score > 0:
            scores[pattern_name] = score

    # Check for phone/V.O. intercut first (high priority)
    if scores.get("dialogue_phone_intercut", 0) >= 2:
        return "dialogue_phone_intercut"

    # If non-dialogue pattern scores higher, use it
    non_dlg_patterns = ["ritual_ceremony", "arrival_approach", "travel_journey",
                        "exploration_discovery", "suspense_atmosphere"]
    best_non_dlg = max(non_dlg_patterns, key=lambda p: scores.get(p, 0), default=None)
    if best_non_dlg and scores.get(best_non_dlg, 0) >= 3:
        return best_non_dlg

    # Dialogue-heavy scenes
    if dialogue_count >= 3:
        if scores.get("will_reading_legal", 0) >= 2:
            return "will_reading_legal"
        if scores.get("dialogue_confrontation", 0) >= 2:
            return "dialogue_confrontation"
        if len(char_set) >= 3:
            return "dialogue_group"
        if len(char_set) >= 2:
            return "dialogue_two_person"

    # Arrival
    if scores.get("arrival_approach", 0) >= 2:
        return "arrival_approach"

    # Travel
    if scores.get("travel_journey", 0) >= 2:
        return "travel_journey"

    # Any dialogue at all with 2+ chars
    if dialogue_count >= 1 and len(char_set) >= 2:
        return "dialogue_two_person"

    # Non-dialogue with some keyword match
    if best_non_dlg and scores.get(best_non_dlg, 0) >= 1:
        return best_non_dlg

    return "generic"


# ═══════════════════════════════════════════════════════════════════
# SHOT TYPE ENRICHER — Applies V9 patterns to existing shots
# ═══════════════════════════════════════════════════════════════════

# Map enriched types to coverage roles for continuity gate
TYPE_TO_COVERAGE = {
    "establishing": "A_GEOGRAPHY",
    "wide": "A_GEOGRAPHY",
    "tracking": "A_GEOGRAPHY",
    "reverse_medium": "B_ACTION",
    "medium": "B_ACTION",
    "two_shot": "B_ACTION",
    "over_the_shoulder": "B_ACTION",
    "medium_close": "C_EMOTION",
    "close": "C_EMOTION",
    "reaction": "C_EMOTION",
    "insert": "C_EMOTION",
    "detail": "C_EMOTION",
}

# Map enriched types to blocking roles for chain pipeline
TYPE_TO_BLOCKING = {
    "establishing": "master",
    "wide": "master",
    "tracking": "movement",
    "reverse_medium": "coverage",
    "medium": "coverage",
    "two_shot": "coverage",
    "over_the_shoulder": "OTS-A",
    "medium_close": "close_coverage",
    "close": "close_coverage",
    "reaction": "reaction",
    "insert": "insert",
    "detail": "insert",
}


class V20ShotTypeEnricher:
    """
    Post-processes shot_plan.json to replace wide/medium metronome
    with V9-style editorial coverage patterns.
    """

    def __init__(self, project_path: Path, story_bible: Dict = None):
        self.project_path = Path(project_path)
        self.story_bible = story_bible or {}
        self.changes = []

    def enrich(self, dry_run: bool = False) -> Dict:
        """
        Main entry point. Reads shot_plan, enriches types, writes back.
        Returns summary of changes.
        """
        sp_path = self.project_path / "shot_plan.json"
        if not sp_path.exists():
            return {"error": "shot_plan.json not found"}

        with open(sp_path) as f:
            shot_plan = json.load(f)

        shots = shot_plan if isinstance(shot_plan, list) else shot_plan.get("shots", [])

        # Group by scene
        scenes = {}
        for s in shots:
            sid = s.get("scene_id", "?")
            scenes.setdefault(sid, []).append(s)

        # Get story bible scenes for richer classification
        sb_scenes = {}
        raw_sb_scenes = self.story_bible.get("scenes", [])
        if isinstance(raw_sb_scenes, list):
            for s in raw_sb_scenes:
                if isinstance(s, dict):
                    sb_scenes[s.get("scene_id", "")] = s
        elif isinstance(raw_sb_scenes, dict):
            sb_scenes = raw_sb_scenes

        total_changes = 0
        scene_summaries = []

        for scene_id, scene_shots in scenes.items():
            sb_scene = sb_scenes.get(scene_id, {})

            # Classify the scene
            template_name = classify_scene(scene_shots, sb_scene)
            pattern = SCENE_PATTERNS.get(template_name, SCENE_PATTERNS["generic"])

            # Track original types
            original_types = [s.get("type", s.get("shot_type", "medium")) for s in scene_shots]

            # Apply the pattern
            changes_in_scene = self._apply_pattern(scene_shots, pattern)
            total_changes += changes_in_scene

            # Track new types
            new_types = [s.get("type", "medium") for s in scene_shots]

            scene_summaries.append({
                "scene_id": scene_id,
                "template": template_name,
                "shot_count": len(scene_shots),
                "changes": changes_in_scene,
                "original_unique_types": len(set(original_types)),
                "new_unique_types": len(set(new_types)),
                "type_sequence": new_types,
            })

        if not dry_run and total_changes > 0:
            # Write back
            with open(sp_path, "w") as f:
                json.dump(shot_plan, f, indent=2, default=str)
            logger.info(f"[V20] Wrote {total_changes} shot type changes to {sp_path.name}")

        # Compute summary stats
        all_new_types = []
        for s in shots:
            all_new_types.append(s.get("type", "medium"))

        return {
            "status": "dry_run" if dry_run else "applied",
            "total_shots": len(shots),
            "total_changes": total_changes,
            "unique_types_before": len(set(t for s in scene_summaries for t in [s.get("original_unique_types", 0)])),
            "unique_types_after": len(set(all_new_types)),
            "type_distribution": {t: all_new_types.count(t) for t in sorted(set(all_new_types))},
            "scenes": scene_summaries,
        }

    def _apply_pattern(self, scene_shots: List[Dict], pattern: EditorialPattern) -> int:
        """
        Apply an editorial pattern to a scene's shots.
        Maps the pattern's type sequence cyclically onto the shots.
        Respects dialogue content — if a shot has dialogue, it gets a dialogue-appropriate type.
        """
        changes = 0
        seq = pattern.sequence
        n_seq = len(seq)
        n_shots = len(scene_shots)

        for i, shot in enumerate(scene_shots):
            old_type = shot.get("type", shot.get("shot_type", "medium"))

            # Get the pattern type for this position
            pattern_idx = i % n_seq
            new_type = seq[pattern_idx]

            # Dialogue-aware override: if shot has dialogue, ensure it's a dialogue-appropriate type
            has_dialogue = bool(
                (shot.get("dialogue_text", "") or "").strip() or
                (shot.get("dialogue", "") or "").strip()
            )

            if has_dialogue:
                # Dialogue shots should be: medium, close, over_the_shoulder, two_shot, medium_close
                # NOT: establishing, wide, insert, detail, tracking
                non_dialogue_types = {"establishing", "wide", "insert", "detail", "tracking"}
                if new_type in non_dialogue_types:
                    # Find the next dialogue-appropriate type in the sequence
                    new_type = self._next_dialogue_type(i, n_shots, scene_shots)

            # First shot in scene should always be establishing or wide
            if i == 0 and new_type not in ("establishing", "wide"):
                new_type = "establishing"

            # Last shot should be medium or wide (resolution)
            if i == n_shots - 1 and n_shots > 2:
                if new_type in ("insert", "detail", "reaction"):
                    new_type = "medium"

            # Anti-repetition: don't allow 3 consecutive same types
            if i >= 2:
                prev1 = scene_shots[i - 1].get("type", "")
                prev2 = scene_shots[i - 2].get("type", "")
                if new_type == prev1 == prev2:
                    # Force variety
                    new_type = self._variety_override(new_type, has_dialogue)

            # Apply the change
            if new_type != old_type:
                shot["type"] = new_type
                shot["_v20_original_type"] = old_type
                shot["_v20_enriched"] = True
                changes += 1

            # Update coverage and blocking roles
            shot["coverage_role"] = TYPE_TO_COVERAGE.get(new_type, "B_ACTION")
            shot["blocking_role"] = TYPE_TO_BLOCKING.get(new_type, "coverage")

        return changes

    def _next_dialogue_type(self, idx: int, total: int, shots: List[Dict]) -> str:
        """Pick an appropriate dialogue shot type based on position."""
        # Alternate between these for dialogue scenes
        dialogue_types = ["medium", "over_the_shoulder", "close", "medium",
                         "two_shot", "medium", "reaction", "medium"]
        return dialogue_types[idx % len(dialogue_types)]

    def _variety_override(self, current: str, has_dialogue: bool) -> str:
        """When 3 consecutive same-type, force a different type."""
        if has_dialogue:
            overrides = {"medium": "over_the_shoulder", "close": "medium",
                        "over_the_shoulder": "close", "two_shot": "medium"}
        else:
            overrides = {"medium": "close", "wide": "medium",
                        "close": "insert", "insert": "medium"}
        return overrides.get(current, "medium" if not has_dialogue else "close")


# ═══════════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════════

def enrich_shot_types(project_path: Path, story_bible: Dict = None, dry_run: bool = False) -> Dict:
    """
    Enrich a project's shot types with V9-style editorial patterns.
    Call this after fix-v16 and before generation.
    """
    enricher = V20ShotTypeEnricher(project_path, story_bible)
    return enricher.enrich(dry_run=dry_run)
