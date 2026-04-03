"""
ATLAS V19 Scene Template Enforcer
===================================

Deterministic scene structure enforcement for dialogue, bar, office, and
generic scenes. Runs BETWEEN fix-v16 and chain render.

Produces edit_decisions.json artifact showing all changes made.

Design rules:
- Templates are PATTERNS, not rigid sequences
- Can reorder within a scene, insert missing required shots
- Can clamp durations to template defaults
- Total shot count increase capped at +15% unless explicitly overridden
- Writes edit_decisions.json for auditability
- Non-blocking on failure (pipeline continues)
"""

import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from collections import Counter

logger = logging.getLogger("atlas.scene_template_enforcer")


# ============================================================================
# SCENE TEMPLATES — Deterministic patterns for common scene types
# ============================================================================

# Template = ordered list of (role, shot_type, duration_range, required)
# role = EDIT_GRAMMAR category, shot_type = specific plan type to create
# required = True means template INSERTS if missing, False = advisory

DIALOGUE_TWO_PERSON = {
    "name": "TWO_PERSON_DIALOGUE",
    "description": "Standard two-person conversation pattern",
    "trigger": lambda scene: _has_dialogue_between_two(scene),
    "pattern": [
        {"role": "GEOGRAPHY", "type": "wide", "duration": (4, 6), "required": True, "label": "establish geography"},
        {"role": "OTS", "type": "over_the_shoulder", "duration": (5, 8), "required": True, "label": "OTS speaker A"},
        {"role": "OTS", "type": "over_the_shoulder", "duration": (5, 8), "required": True, "label": "OTS speaker B"},
        {"role": "CLOSE", "type": "close", "duration": (4, 6), "required": False, "label": "reaction A"},
        {"role": "INSERT", "type": "insert", "duration": (3, 4), "required": False, "label": "contextual insert"},
        {"role": "ACTION", "type": "two_shot", "duration": (5, 8), "required": False, "label": "two-shot reset"},
    ],
    "rules": {
        "max_consecutive_same_speaker": 2,
        "require_reaction_after_emotional_line": True,
        "geography_reset_every_n": 6,
    },
}

DIALOGUE_CONFRONTATION = {
    "name": "CONFRONTATION_DIALOGUE",
    "description": "Tense face-off between two characters",
    "trigger": lambda scene: _is_confrontation(scene),
    "pattern": [
        {"role": "GEOGRAPHY", "type": "wide", "duration": (4, 6), "required": True, "label": "geography anchor"},
        {"role": "ACTION", "type": "medium", "duration": (5, 7), "required": True, "label": "entrance/action"},
        {"role": "OTS", "type": "over_the_shoulder", "duration": (5, 7), "required": True, "label": "OTS aggressor"},
        {"role": "OTS", "type": "over_the_shoulder", "duration": (5, 7), "required": True, "label": "OTS defender"},
        {"role": "CLOSE", "type": "close", "duration": (4, 6), "required": True, "label": "close tension"},
        {"role": "REACTION", "type": "reaction", "duration": (3, 5), "required": True, "label": "reaction beat"},
        {"role": "INSERT", "type": "insert", "duration": (3, 4), "required": False, "label": "tension detail"},
        {"role": "GEOGRAPHY", "type": "wide", "duration": (4, 6), "required": False, "label": "geography reset"},
    ],
    "rules": {
        "max_consecutive_same_speaker": 2,
        "require_reaction_after_emotional_line": True,
        "geography_reset_every_n": 5,
    },
}

BAR_PUB_SCENE = {
    "name": "BAR_PUB",
    "description": "Pub/bar/nightclub scene with atmosphere + conversation",
    "trigger": lambda scene: _is_bar_scene(scene),
    "pattern": [
        {"role": "ESTABLISHING", "type": "establishing", "duration": (4, 6), "required": True, "label": "exterior establish"},
        {"role": "GEOGRAPHY", "type": "wide", "duration": (5, 7), "required": True, "label": "interior geography"},
        {"role": "INSERT", "type": "insert", "duration": (3, 4), "required": False, "label": "bar detail (glass/drink)"},
        {"role": "OTS", "type": "over_the_shoulder", "duration": (5, 8), "required": True, "label": "OTS exchange A"},
        {"role": "OTS", "type": "over_the_shoulder", "duration": (5, 8), "required": True, "label": "OTS exchange B"},
        {"role": "CLOSE", "type": "close", "duration": (4, 6), "required": False, "label": "close reaction"},
        {"role": "GEOGRAPHY", "type": "wide", "duration": (4, 5), "required": False, "label": "crowd/atmosphere reset"},
    ],
    "rules": {
        "max_consecutive_same_speaker": 2,
        "require_reaction_after_emotional_line": True,
        "geography_reset_every_n": 5,
    },
}

OFFICE_LEGAL_SCENE = {
    "name": "OFFICE_LEGAL",
    "description": "Office/legal/formal meeting scene",
    "trigger": lambda scene: _is_office_scene(scene),
    "pattern": [
        {"role": "GEOGRAPHY", "type": "wide", "duration": (4, 6), "required": True, "label": "office geography"},
        {"role": "ACTION", "type": "medium", "duration": (5, 7), "required": True, "label": "desk action"},
        {"role": "INSERT", "type": "insert", "duration": (3, 4), "required": False, "label": "desk/document detail"},
        {"role": "OTS", "type": "over_the_shoulder", "duration": (5, 8), "required": True, "label": "OTS speaker"},
        {"role": "CLOSE", "type": "close", "duration": (4, 6), "required": False, "label": "reaction close"},
        {"role": "GEOGRAPHY", "type": "wide", "duration": (4, 5), "required": False, "label": "geography anchor"},
    ],
    "rules": {
        "max_consecutive_same_speaker": 2,
        "require_reaction_after_emotional_line": True,
        "geography_reset_every_n": 6,
    },
}

ARRIVAL_SCENE = {
    "name": "ARRIVAL",
    "description": "Character arrives at new location",
    "trigger": lambda scene: _is_arrival(scene),
    "pattern": [
        {"role": "ESTABLISHING", "type": "establishing", "duration": (4, 6), "required": True, "label": "location establish"},
        {"role": "GEOGRAPHY", "type": "wide", "duration": (5, 7), "required": True, "label": "approach geography"},
        {"role": "ACTION", "type": "medium", "duration": (5, 7), "required": True, "label": "character enters"},
        {"role": "CLOSE", "type": "close", "duration": (4, 6), "required": False, "label": "reaction to arrival"},
        {"role": "INSERT", "type": "insert", "duration": (3, 4), "required": False, "label": "arrival detail (suitcase/door/key)"},
    ],
    "rules": {
        "geography_reset_every_n": 8,
    },
}

GENERIC_SCENE = {
    "name": "GENERIC",
    "description": "Fallback: ensures basic coverage requirements",
    "trigger": lambda scene: True,  # Always matches as fallback
    "pattern": [
        {"role": "GEOGRAPHY", "type": "wide", "duration": (4, 6), "required": True, "label": "geography anchor"},
        {"role": "ACTION", "type": "medium", "duration": (5, 8), "required": True, "label": "primary action"},
    ],
    "rules": {
        "geography_reset_every_n": 8,
    },
}

# Template priority order (first match wins)
ALL_TEMPLATES = [
    DIALOGUE_CONFRONTATION,
    BAR_PUB_SCENE,
    OFFICE_LEGAL_SCENE,
    ARRIVAL_SCENE,
    DIALOGUE_TWO_PERSON,
    GENERIC_SCENE,
]


# ============================================================================
# TRIGGER DETECTION FUNCTIONS
# ============================================================================

def _has_dialogue_between_two(scene: Dict) -> bool:
    """Scene has dialogue between exactly 2 characters."""
    chars = scene.get("characters", [])
    if isinstance(chars, str):
        chars = [c.strip() for c in chars.split(",")]
    beats = scene.get("beats", [])
    has_dialogue = any(b.get("dialogue") for b in beats) if beats else False
    # Also check if shots have dialogue
    shots = scene.get("_shots", [])
    if not has_dialogue:
        has_dialogue = any(s.get("dialogue_text") or s.get("dialogue") for s in shots)
    return len(chars) == 2 and has_dialogue


def _is_confrontation(scene: Dict) -> bool:
    """Scene involves tense confrontation."""
    desc = (scene.get("description", "") + " " + scene.get("title", "")).lower()
    triggers = r"\b(confronts?|accuses?|demands?|threatens?|slaps?|argument|tension|hostile|angry)\b"
    return bool(re.search(triggers, desc))


def _is_bar_scene(scene: Dict) -> bool:
    """Scene is set in a bar, pub, nightclub, tavern."""
    location = (scene.get("location", "") + " " + scene.get("title", "")).lower()
    triggers = r"\b(bar|pub|tavern|inn|nightclub|saloon|club|lounge|cantina)\b"
    return bool(re.search(triggers, location))


def _is_office_scene(scene: Dict) -> bool:
    """Scene is set in an office, legal, or formal meeting space."""
    location = (scene.get("location", "") + " " + scene.get("title", "")).lower()
    triggers = r"\b(office|court|legal|boardroom|chambers|study|library|solicitor|commissioner)\b"
    return bool(re.search(triggers, location))


def _is_arrival(scene: Dict) -> bool:
    """Scene involves character arriving at a new location."""
    desc = (scene.get("description", "") + " " + scene.get("title", "")).lower()
    triggers = r"\b(arrives?|returns?|enters?|pulls up|steps into|first time|approaches?)\b"
    return bool(re.search(triggers, desc))


# ============================================================================
# SCENE TEMPLATE ENFORCER
# ============================================================================

class SceneTemplateEnforcer:
    """
    Applies deterministic scene templates to enforce proper coverage.

    Runs between fix-v16 and chain render. Can:
    - Reorder shots within a scene
    - Insert missing required shots from templates
    - Clamp dialogue durations to template ranges
    - Enforce geography resets every N shots
    - Cap total additions at +15%

    Writes edit_decisions.json for auditability.
    """

    def __init__(self, project_path: Path, story_bible: Dict, cast_map: Dict):
        self.project_path = Path(project_path)
        self.story_bible = story_bible
        self.cast_map = cast_map
        self.decisions: List[Dict] = []
        self.max_addition_rate = 0.15  # +15% cap

    def enforce(self, scene_id: Optional[str] = None, dry_run: bool = True) -> Dict:
        """
        Run template enforcement on all scenes or a specific scene.

        Args:
            scene_id: Specific scene (None = all)
            dry_run: If True, report only. If False, modify shot_plan.

        Returns:
            Dict with template matches, insertions, clamps, decisions.
        """
        self.decisions = []

        shot_plan_path = self.project_path / "shot_plan.json"
        if not shot_plan_path.exists():
            return {"status": "no_shot_plan", "decisions": []}

        with open(shot_plan_path) as f:
            shot_plan = json.load(f)

        shots = shot_plan.get("shots", [])
        original_count = len(shots)

        # Group shots by scene
        scenes_map = {}
        for s in shots:
            sid = s.get("scene_id", "unknown")
            if sid not in scenes_map:
                scenes_map[sid] = []
            scenes_map[sid].append(s)

        # Get scene metadata from story bible (handles both dict and list formats)
        _raw_scenes = self.story_bible.get("scenes", {})
        if isinstance(_raw_scenes, list):
            sb_scenes = {s.get("scene_id", f"scene_{i}"): s
                         for i, s in enumerate(_raw_scenes) if isinstance(s, dict)}
        elif isinstance(_raw_scenes, dict):
            sb_scenes = _raw_scenes
        else:
            sb_scenes = {}

        result = {
            "status": "success",
            "scenes_processed": 0,
            "templates_matched": {},
            "insertions": 0,
            "duration_clamps": 0,
            "reorders": 0,
            "geography_resets": 0,
            "decisions": [],
        }

        for sid, scene_shots in sorted(scenes_map.items()):
            if scene_id and sid != scene_id:
                continue

            # Build scene context for template matching
            scene_meta = sb_scenes.get(sid, {})
            scene_context = {
                **scene_meta,
                "_shots": scene_shots,
                "characters": scene_meta.get("characters", []),
            }

            # Match template
            template = self._match_template(scene_context)
            result["templates_matched"][sid] = template["name"]

            # Apply template
            modified_shots, scene_decisions = self._apply_template(
                scene_shots, template, sid, scene_context
            )

            # Cap additions
            max_additions = max(1, int(len(scene_shots) * self.max_addition_rate))
            new_shots_added = len(modified_shots) - len(scene_shots)
            if new_shots_added > max_additions:
                # Trim excess insertions (keep only required ones)
                excess = new_shots_added - max_additions
                trimmed = 0
                for i in range(len(modified_shots) - 1, -1, -1):
                    if modified_shots[i].get("_inserted_by") == "scene_template_enforcer" and trimmed < excess:
                        modified_shots.pop(i)
                        trimmed += 1
                scene_decisions.append({
                    "type": "cap_insertions",
                    "scene_id": sid,
                    "detail": f"Capped insertions: removed {trimmed} to stay within +{self.max_addition_rate:.0%}",
                })

            # Update result stats
            result["scenes_processed"] += 1
            result["insertions"] += sum(1 for d in scene_decisions if d["type"] == "insert")
            result["duration_clamps"] += sum(1 for d in scene_decisions if d["type"] == "duration_clamp")
            result["geography_resets"] += sum(1 for d in scene_decisions if d["type"] == "geography_reset")
            result["decisions"].extend(scene_decisions)
            self.decisions.extend(scene_decisions)

            # Replace scene shots in the full list
            if not dry_run and modified_shots != scene_shots:
                # Rebuild shots list with modified scene
                new_shots = []
                for s in shots:
                    if s.get("scene_id") == sid:
                        continue  # Skip old scene shots
                    new_shots.append(s)
                # Insert modified scene shots at the right position
                insert_idx = next((i for i, s in enumerate(new_shots)
                                   if s.get("scene_id", "") > sid), len(new_shots))
                for ms in modified_shots:
                    new_shots.insert(insert_idx, ms)
                    insert_idx += 1
                shots = new_shots

        # Persist if not dry run
        if not dry_run:
            shot_plan["shots"] = shots
            try:
                import tempfile, os
                tmp = tempfile.NamedTemporaryFile(mode='w', dir=str(self.project_path),
                                                   suffix='.json', delete=False)
                json.dump(shot_plan, tmp, indent=2)
                tmp.close()
                os.replace(tmp.name, str(shot_plan_path))
                result["persisted"] = True
            except Exception as e:
                result["persist_error"] = str(e)

        # Write edit_decisions.json
        try:
            decisions_path = self.project_path / "edit_decisions.json"
            with open(decisions_path, "w") as f:
                json.dump({
                    "version": "v19",
                    "decisions": self.decisions,
                    "templates_matched": result["templates_matched"],
                    "stats": {
                        "insertions": result["insertions"],
                        "duration_clamps": result["duration_clamps"],
                        "geography_resets": result["geography_resets"],
                    },
                }, f, indent=2)
        except Exception:
            pass

        result["original_shots"] = original_count
        result["final_shots"] = len(shots)
        return result

    def _match_template(self, scene_context: Dict) -> Dict:
        """Find best matching template for a scene."""
        for template in ALL_TEMPLATES:
            try:
                if template["trigger"](scene_context):
                    return template
            except Exception:
                continue
        return GENERIC_SCENE

    def _apply_template(self, shots: List[Dict], template: Dict,
                        scene_id: str, scene_context: Dict) -> Tuple[List[Dict], List[Dict]]:
        """
        Apply a template to a scene's shots.

        Returns: (modified_shots, decisions_list)
        """
        from atlas_agents.director_edit_pass import normalize_shot_type

        decisions = []
        modified = list(shots)  # Copy

        # Build role inventory for existing shots
        existing_roles = Counter()
        for s in modified:
            raw = s.get("type", s.get("shot_type", ""))
            role = normalize_shot_type(raw)
            existing_roles[role] += 1

        # 1. Check for missing REQUIRED roles and insert if absent
        for pattern_entry in template["pattern"]:
            if not pattern_entry["required"]:
                continue
            role = pattern_entry["role"]
            if existing_roles.get(role, 0) == 0:
                # Insert a stub shot for this missing role
                new_shot = self._create_template_shot(
                    pattern_entry, scene_id, scene_context
                )
                # Insert at position that makes grammatical sense
                insert_pos = self._find_insert_position(modified, role)
                modified.insert(insert_pos, new_shot)
                existing_roles[role] += 1
                decisions.append({
                    "type": "insert",
                    "scene_id": scene_id,
                    "template": template["name"],
                    "role": role,
                    "shot_type": pattern_entry["type"],
                    "position": insert_pos,
                    "detail": f"Inserted {pattern_entry['label']} (missing required {role})",
                })

        # 2. Dialogue duration clamping per template
        for s in modified:
            has_dialogue = bool(s.get("dialogue_text") or s.get("dialogue"))
            if not has_dialogue:
                continue
            raw_type = s.get("type", s.get("shot_type", "medium")).lower()
            # Find matching template entry for duration range
            for pe in template["pattern"]:
                if pe.get("type") == raw_type or normalize_shot_type(raw_type) == pe["role"]:
                    dur_min, dur_max = pe["duration"]
                    cur = s.get("duration", 10)
                    clamped = max(dur_min, min(cur, dur_max))
                    if clamped != cur:
                        s["duration"] = clamped
                        s["duration_seconds"] = clamped
                        s["ltx_duration_seconds"] = clamped
                        s["_template_clamped"] = True
                        decisions.append({
                            "type": "duration_clamp",
                            "scene_id": scene_id,
                            "shot_id": s.get("shot_id", "?"),
                            "detail": f"Clamped {cur}s → {clamped}s ({pe['label']})",
                        })
                    break

        # 3. Geography reset enforcement
        rules = template.get("rules", {})
        reset_interval = rules.get("geography_reset_every_n", 8)
        shots_since_geography = 0
        for i, s in enumerate(modified):
            raw = s.get("type", s.get("shot_type", ""))
            role = normalize_shot_type(raw)
            if role == "GEOGRAPHY" or role == "ESTABLISHING":
                shots_since_geography = 0
            else:
                shots_since_geography += 1

            if shots_since_geography >= reset_interval:
                # Check if we can insert a geography reset
                if i + 1 < len(modified):
                    location = scene_context.get("location", "scene location")
                    reset_shot = {
                        "shot_id": f"{scene_id}_geo_reset_{i}",
                        "scene_id": scene_id,
                        "type": "wide",
                        "duration": 4,
                        "characters": scene_context.get("characters", [])[:2],
                        "nano_prompt": f"Wide geography reset, {location}, character positions visible",
                        "ltx_motion_prompt": "slow establishing movement, re-orient viewer",
                        "_inserted_by": "scene_template_enforcer",
                        "_template": template["name"],
                    }
                    modified.insert(i + 1, reset_shot)
                    shots_since_geography = 0
                    decisions.append({
                        "type": "geography_reset",
                        "scene_id": scene_id,
                        "position": i + 1,
                        "detail": f"Inserted geography reset after {reset_interval} shots without wide/establishing",
                    })

        return modified, decisions

    def _create_template_shot(self, pattern_entry: Dict, scene_id: str,
                              scene_context: Dict) -> Dict:
        """Create a new shot from a template pattern entry."""
        location = scene_context.get("location", "scene location")
        characters = scene_context.get("characters", [])
        if isinstance(characters, str):
            characters = [c.strip() for c in characters.split(",")]

        dur_min, dur_max = pattern_entry["duration"]
        duration = (dur_min + dur_max) / 2  # Middle of range

        # Build prompt based on role
        role = pattern_entry["role"]
        label = pattern_entry["label"]
        prompt_templates = {
            "ESTABLISHING": f"Establishing shot, {location}, atmosphere and geography visible",
            "GEOGRAPHY": f"Wide shot, {location}, character positions visible, spatial context",
            "ACTION": f"Medium shot, character action in {location}",
            "OTS": f"Over-the-shoulder shot, conversation framing, {location}",
            "CLOSE": f"Close-up, character reaction, emotional detail",
            "REACTION": f"Reaction shot, character responds with controlled emotion",
            "INSERT": f"Insert detail shot, contextual object in focus, {location}",
        }

        shot = {
            "shot_id": f"{scene_id}_{pattern_entry['type']}_{label.replace(' ', '_')[:20]}",
            "scene_id": scene_id,
            "type": pattern_entry["type"],
            "duration": duration,
            "duration_seconds": duration,
            "characters": characters[:2] if role != "INSERT" else [],
            "nano_prompt": prompt_templates.get(role, f"{label}, {location}"),
            "ltx_motion_prompt": f"subtle movement, {label}",
            "_inserted_by": "scene_template_enforcer",
            "_template": label,
        }
        return shot

    def _find_insert_position(self, shots: List[Dict], target_role: str) -> int:
        """Find the best position to insert a shot of a given role."""
        from atlas_agents.director_edit_pass import normalize_shot_type

        # ESTABLISHING/GEOGRAPHY → insert at beginning
        if target_role in ("ESTABLISHING", "GEOGRAPHY"):
            return 0
        # CLOSE/REACTION → insert after first ACTION or OTS
        if target_role in ("CLOSE", "REACTION"):
            for i, s in enumerate(shots):
                raw = s.get("type", s.get("shot_type", ""))
                role = normalize_shot_type(raw)
                if role in ("ACTION", "OTS"):
                    return i + 1
        # OTS → insert after first GEOGRAPHY or ACTION
        if target_role == "OTS":
            for i, s in enumerate(shots):
                raw = s.get("type", s.get("shot_type", ""))
                role = normalize_shot_type(raw)
                if role in ("GEOGRAPHY", "ACTION"):
                    return i + 1
        # INSERT → insert near middle
        if target_role == "INSERT":
            return len(shots) // 2
        # Default: append
        return len(shots)


# ============================================================================
# PUBLIC API
# ============================================================================

def run_scene_template_enforcer(
    project_path: Path,
    story_bible: Dict,
    cast_map: Dict,
    scene_id: Optional[str] = None,
    dry_run: bool = True,
) -> Dict:
    """
    Convenience function to run scene template enforcement.

    Args:
        project_path: Path to project
        story_bible: Story bible data
        cast_map: Character to actor mapping
        scene_id: Optional scene to process
        dry_run: Report only (True) or modify (False)

    Returns:
        Result dict with stats and decisions
    """
    enforcer = SceneTemplateEnforcer(project_path, story_bible, cast_map)
    return enforcer.enforce(scene_id=scene_id, dry_run=dry_run)
