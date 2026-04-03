#!/usr/bin/env python3
"""
ATLAS V18.3 — Wardrobe & Extras Agent
=========================================

Manages two continuity systems that prevent AI-generated drift:

1. WARDROBE (Look IDs)
   - Per-character, per-scene wardrobe definitions
   - Lock toggle prevents drift between shots
   - Prompt injection: positive wardrobe description + negative constraints
   - Validator: flags clothing drift across adjacent shots

2. EXTRAS (Crowd Packs)
   - Named crowd profiles with demographic/behavior/density
   - Per-shot injection of background character direction
   - Validator: empty room detection, density mismatch, focus stealing

Design principle: defaults by SCENE (not timeblock). A character's look stays
consistent within a scene unless explicitly changed. Cross-scene look changes
happen at scene boundaries (wardrobe change = new look_id).

Files managed:
  pipeline_outputs/{project}/wardrobe.json  — Look definitions + locks
  pipeline_outputs/{project}/extras.json    — Crowd pack definitions

Integration points:
  - Cinematic enricher: injects wardrobe/extras into prompts
  - LOA pre-gen gate: validates wardrobe locks and extras requirements
  - Post-gen QA: flags drift in adjacent shots
"""

import json
import os
import logging
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("atlas.wardrobe_extras")

# ──────────────────────────────────────────────────────────────
# WARDROBE SYSTEM
# ──────────────────────────────────────────────────────────────

def generate_look_id(character: str, scene_id: str, description: str = "") -> str:
    """Generate a deterministic Look ID from character + scene + description."""
    char_clean = character.upper().replace(" ", "_")[:20]
    desc_tag = ""
    if description:
        # Extract key clothing words
        clothing_words = []
        for w in description.lower().split():
            if w in _CLOTHING_VOCAB:
                clothing_words.append(w.upper())
        desc_tag = "_".join(clothing_words[:3]) if clothing_words else "DEFAULT"
    else:
        desc_tag = "DEFAULT"
    return f"{char_clean}_S{scene_id}_{desc_tag}"


_CLOTHING_VOCAB = {
    # Colors
    "black", "white", "blue", "red", "green", "grey", "gray", "brown",
    "navy", "cream", "beige", "burgundy", "charcoal", "tan", "ivory",
    "dark", "light", "deep", "pale", "rich",
    # Garments
    "jacket", "coat", "dress", "suit", "shirt", "blouse", "sweater",
    "vest", "skirt", "pants", "trousers", "jeans", "shorts", "gown",
    "robe", "cloak", "cape", "hood", "apron", "uniform", "nightgown",
    "shawl", "scarf", "tie", "bowtie", "hat", "cap", "gloves",
    # Materials
    "silk", "cotton", "wool", "leather", "linen", "velvet", "lace",
    "denim", "tweed", "satin", "fur", "suede",
    # Styles
    "formal", "casual", "vintage", "modern", "elegant", "rugged",
    "tailored", "loose", "fitted", "worn", "tattered", "pristine",
    "bloodstained", "muddy", "dusty", "wet", "torn",
}


def load_wardrobe(project_path: Path) -> Dict:
    """Load wardrobe.json or create default structure."""
    wp = project_path / "wardrobe.json"
    if wp.exists():
        try:
            with open(wp) as f:
                return json.load(f)
        except Exception:
            pass
    return {"looks": {}, "scene_locks": {}, "_schema_version": "17.7.5"}


def save_wardrobe(project_path: Path, wardrobe: Dict):
    """Atomic save of wardrobe.json."""
    wp = project_path / "wardrobe.json"
    tmp = tempfile.NamedTemporaryFile(mode='w', dir=str(project_path),
                                      suffix='.tmp', delete=False)
    json.dump(wardrobe, tmp, indent=2)
    tmp.close()
    os.replace(tmp.name, str(wp))


def auto_assign_wardrobe(project_path: Path, shots: List[Dict],
                          story_bible: Dict = None, cast_map: Dict = None) -> Dict:
    """
    Auto-assign wardrobe Look IDs per character per scene.

    Strategy:
    - Group shots by scene
    - For each scene, find characters present
    - If story bible has wardrobe description, use it
    - Otherwise, derive from cast_map actor appearance or use DEFAULT
    - Same character in same scene = same look_id
    """
    wardrobe = load_wardrobe(project_path)
    looks = wardrobe.get("looks", {})
    scene_locks = wardrobe.get("scene_locks", {})

    # Gather character appearances per scene
    scene_chars = {}  # scene_id → set of character names
    for shot in shots:
        sid = shot.get("shot_id", "")
        scene = sid.split("_")[0] if "_" in sid else ""
        if not scene:
            continue
        chars = shot.get("characters", [])
        if scene not in scene_chars:
            scene_chars[scene] = set()
        for c in chars:
            name = c if isinstance(c, str) else c.get("name", "")
            if name:
                scene_chars[scene].add(name.upper().strip())

    # Try to extract wardrobe descriptions from story bible
    sb_wardrobe = {}  # char_name → scene_id → description
    if story_bible:
        for char in story_bible.get("characters", []):
            char_name = (char.get("name") or "").upper().strip()
            appearance = char.get("appearance", char.get("physical_description", ""))
            wardrobe_desc = char.get("wardrobe", char.get("costume", ""))
            if char_name and (appearance or wardrobe_desc):
                sb_wardrobe[char_name] = wardrobe_desc or appearance

    # Try to get appearance from cast_map actor
    cast_appearance = {}
    if cast_map:
        for char_name, entry in cast_map.items():
            if char_name.startswith("_"):
                continue
            if isinstance(entry, dict):
                # The actor's image_prompt often describes appearance
                actor_name = entry.get("ai_actor", "")
                cast_appearance[char_name.upper()] = {
                    "actor": actor_name,
                    "wardrobe_hex": entry.get("wardrobe_hex", ""),
                }

    new_looks = 0
    for scene_id, chars in scene_chars.items():
        for char_name in chars:
            look_key = f"{char_name}::{scene_id}"
            if look_key in looks:
                continue  # Already assigned

            # Build description from available sources
            desc = sb_wardrobe.get(char_name, "")
            if not desc:
                # Check for scene-specific wardrobe notes
                desc = ""

            look_id = generate_look_id(char_name, scene_id, desc)

            looks[look_key] = {
                "look_id": look_id,
                "character": char_name,
                "scene_id": scene_id,
                "description": desc[:200] if desc else "",
                "locked": False,
                "wardrobe_tag": _extract_wardrobe_tag(desc) if desc else "",
                "negative_constraints": "",
            }
            new_looks += 1

    wardrobe["looks"] = looks
    wardrobe["scene_locks"] = scene_locks
    save_wardrobe(project_path, wardrobe)

    logger.info(f"[WARDROBE] Auto-assigned {new_looks} new look IDs across {len(scene_chars)} scenes")
    return wardrobe


def _extract_wardrobe_tag(description: str) -> str:
    """Extract concise wardrobe tag from a description for prompt injection."""
    if not description:
        return ""
    words = description.lower().split()
    tags = []
    for w in words:
        w_clean = w.strip(".,;:'\"()[]")
        if w_clean in _CLOTHING_VOCAB:
            tags.append(w_clean)
    return " ".join(tags[:8]) if tags else description[:120]


def get_wardrobe_for_shot(wardrobe: Dict, shot: Dict) -> Dict:
    """
    Get wardrobe info for a shot's characters.
    Returns: {char_name: {look_id, description, wardrobe_tag, locked, negative_constraints}}
    """
    result = {}
    sid = shot.get("shot_id", "")
    scene = sid.split("_")[0] if "_" in sid else ""
    chars = shot.get("characters", [])

    looks = wardrobe.get("looks", {})
    for c in chars:
        name = (c if isinstance(c, str) else c.get("name", "")).upper().strip()
        if not name:
            continue
        look_key = f"{name}::{scene}"
        look = looks.get(look_key)
        if look:
            result[name] = look
    return result


def inject_wardrobe_into_prompt(prompt: str, shot_wardrobe: Dict, is_ltx: bool = False) -> str:
    """
    Inject wardrobe continuity directives into a prompt.

    For nano_prompt: adds positive wardrobe description
    For ltx_motion: adds wardrobe lock constraints
    """
    if not shot_wardrobe:
        return prompt

    additions = []
    negatives = []

    for char_name, look in shot_wardrobe.items():
        tag = look.get("wardrobe_tag", "")
        locked = look.get("locked", False)
        desc = look.get("description", "")
        neg = look.get("negative_constraints", "")

        if is_ltx:
            # For LTX: focus on motion constraints, not visual
            if locked:
                additions.append(f"wardrobe continuity: {char_name} same outfit throughout")
        else:
            # For nano: describe what they're wearing
            if tag:
                additions.append(f"{char_name} wearing: {tag}")
            elif desc:
                additions.append(f"{char_name} wearing: {desc[:80]}")

            if locked:
                negatives.append(f"NO outfit change for {char_name}")
                if neg:
                    negatives.append(neg)

    if additions:
        prompt = prompt.rstrip(". ,") + ". " + ". ".join(additions)

    if negatives:
        # Insert before existing negatives if possible
        neg_text = ", ".join(negatives)
        neg_idx = prompt.find("NO grid")
        if neg_idx > 0:
            prompt = prompt[:neg_idx] + neg_text + ", " + prompt[neg_idx:]
        else:
            prompt = prompt.rstrip(". ,") + ". " + neg_text

    return prompt


def lock_wardrobe(project_path: Path, character: str, scene_id: str,
                   locked: bool = True) -> Dict:
    """Lock/unlock wardrobe for a character in a scene."""
    wardrobe = load_wardrobe(project_path)
    look_key = f"{character.upper()}::{scene_id}"
    if look_key in wardrobe["looks"]:
        wardrobe["looks"][look_key]["locked"] = locked
        save_wardrobe(project_path, wardrobe)
        logger.info(f"[WARDROBE] {'Locked' if locked else 'Unlocked'} {look_key}")
    return wardrobe


def set_wardrobe(project_path: Path, character: str, scene_id: str,
                  description: str, locked: bool = True) -> Dict:
    """Set wardrobe description for a character in a scene and optionally lock."""
    wardrobe = load_wardrobe(project_path)
    look_key = f"{character.upper()}::{scene_id}"

    wardrobe["looks"][look_key] = {
        "look_id": generate_look_id(character, scene_id, description),
        "character": character.upper(),
        "scene_id": scene_id,
        "description": description[:200],
        "locked": locked,
        "wardrobe_tag": _extract_wardrobe_tag(description),
        "negative_constraints": "",
    }
    save_wardrobe(project_path, wardrobe)
    logger.info(f"[WARDROBE] Set {look_key} = {description[:60]}")
    return wardrobe


def carry_wardrobe_forward(project_path: Path, character: str,
                            from_scene: str, to_scene: str) -> Dict:
    """Copy wardrobe from one scene to another (e.g., continuous sequence)."""
    wardrobe = load_wardrobe(project_path)
    from_key = f"{character.upper()}::{from_scene}"
    to_key = f"{character.upper()}::{to_scene}"

    if from_key in wardrobe["looks"]:
        source = wardrobe["looks"][from_key].copy()
        source["scene_id"] = to_scene
        source["look_id"] = generate_look_id(character, to_scene,
                                              source.get("description", ""))
        wardrobe["looks"][to_key] = source
        save_wardrobe(project_path, wardrobe)
        logger.info(f"[WARDROBE] Carried {character} look from scene {from_scene} → {to_scene}")
    return wardrobe


# ──────────────────────────────────────────────────────────────
# EXTRAS SYSTEM (Crowd Packs)
# ──────────────────────────────────────────────────────────────

# Pre-built crowd packs for common scenes
DEFAULT_CROWD_PACKS = {
    "BAR_CROWD_A": {
        "name": "Bar Crowd A",
        "demographic": "mixed age adults, local village patrons",
        "wardrobe_theme": "casual pub attire, wool sweaters, work clothes, weathered jackets",
        "count_range": [6, 18],
        "default_behavior": "drinking, talking quietly, occasional laughter",
        "consistency": "medium",
        "focus_rule": "do not steal focus from main characters",
    },
    "VILLAGE_STREET": {
        "name": "Village Street",
        "demographic": "mixed locals, shopkeepers, pedestrians",
        "wardrobe_theme": "rural village clothing, practical weather-appropriate outfits",
        "count_range": [3, 12],
        "default_behavior": "walking, carrying bags, standing at doorways",
        "consistency": "low",
        "focus_rule": "background motion only, no direct camera engagement",
    },
    "MANOR_SERVANTS": {
        "name": "Manor Servants",
        "demographic": "mixed age adults in domestic service",
        "wardrobe_theme": "period-appropriate servant uniforms, aprons, dark formal attire",
        "count_range": [1, 6],
        "default_behavior": "moving purposefully, carrying items, standing at attention",
        "consistency": "high",
        "focus_rule": "peripheral awareness, may acknowledge main characters subtly",
    },
    "EMPTY_SETTING": {
        "name": "Empty Setting (No Extras)",
        "demographic": "",
        "wardrobe_theme": "",
        "count_range": [0, 0],
        "default_behavior": "no people in background",
        "consistency": "high",
        "focus_rule": "absolutely no background people",
    },
    "FUNERAL_MOURNERS": {
        "name": "Funeral Mourners",
        "demographic": "mixed age adults, somber demeanor",
        "wardrobe_theme": "black formal attire, dark coats, veils optional",
        "count_range": [8, 25],
        "default_behavior": "standing solemnly, heads bowed, quiet grief",
        "consistency": "high",
        "focus_rule": "unified backdrop, no individual attention-grabbing behavior",
    },
    "OFFICE_WORKERS": {
        "name": "Office Workers",
        "demographic": "business professionals",
        "wardrobe_theme": "business casual to formal, suits, blouses, modern office wear",
        "count_range": [3, 15],
        "default_behavior": "typing, walking with purpose, holding coffee, phone calls",
        "consistency": "low",
        "focus_rule": "background motion texture, no direct interaction",
    },
}


def load_extras(project_path: Path) -> Dict:
    """Load extras.json or create default structure.
    Always ensures crowd_packs key exists (V22 fix for KeyError)."""
    ep = project_path / "extras.json"
    result = {
        "crowd_packs": dict(DEFAULT_CROWD_PACKS),
        "scene_extras": {},
        "_schema_version": "17.7.5",
    }
    if ep.exists():
        try:
            with open(ep) as f:
                data = json.load(f)
            # Merge loaded data but ALWAYS ensure crowd_packs exists
            if "scene_extras" in data:
                result["scene_extras"] = data["scene_extras"]
            elif "crowd_packs" not in data:
                # V22 fix: corrupt flat-schema (scene IDs at root) — migrate
                migrated = {}
                for k, v in data.items():
                    if k.startswith("_") or k in ("crowd_packs", "scene_extras"):
                        continue
                    if isinstance(v, dict) and ("pack_id" in v or "count" in v or "location" in v):
                        migrated[k] = v
                if migrated:
                    result["scene_extras"] = migrated
                    logger.info(f"[EXTRAS] Migrated {len(migrated)} flat-schema entries to scene_extras")
            result["_schema_version"] = data.get("_schema_version", "17.7.5")
            # If file has crowd_packs, use them; otherwise keep defaults
            if "crowd_packs" in data and data["crowd_packs"]:
                result["crowd_packs"] = data["crowd_packs"]
        except Exception:
            pass
    return result


def save_extras(project_path: Path, extras: Dict):
    """Atomic save of extras.json."""
    ep = project_path / "extras.json"
    tmp = tempfile.NamedTemporaryFile(mode='w', dir=str(project_path),
                                      suffix='.tmp', delete=False)
    json.dump(extras, tmp, indent=2)
    tmp.close()
    os.replace(tmp.name, str(ep))


def assign_extras_to_scene(project_path: Path, scene_id: str,
                            pack_id: str, count: int = None,
                            behavior: str = None) -> Dict:
    """Assign a crowd pack to a scene with optional overrides."""
    extras = load_extras(project_path)
    pack = extras["crowd_packs"].get(pack_id)
    if not pack:
        logger.warning(f"[EXTRAS] Unknown crowd pack: {pack_id}")
        return extras

    if count is None:
        count = pack["count_range"][1]  # Default to max

    extras["scene_extras"][scene_id] = {
        "pack_id": pack_id,
        "count": count,
        "behavior": behavior or pack["default_behavior"],
        "wardrobe_theme": pack["wardrobe_theme"],
        "consistency": pack["consistency"],
        "focus_rule": pack["focus_rule"],
    }
    save_extras(project_path, extras)
    logger.info(f"[EXTRAS] Assigned {pack_id} ({count} people) to scene {scene_id}")
    return extras


def get_extras_for_shot(extras: Dict, shot: Dict) -> Optional[Dict]:
    """Get extras info for a shot based on its scene."""
    sid = shot.get("shot_id", "")
    scene = sid.split("_")[0] if "_" in sid else ""
    return extras.get("scene_extras", {}).get(scene)


def inject_extras_into_prompt(prompt: str, extras_info: Dict,
                               is_ltx: bool = False,
                               shot: Dict = None) -> str:
    """Inject extras/crowd direction into a prompt.

    V26.1: Shot-type guard — close-ups, MCUs, ECUs, reaction shots, and
    C_EMOTION coverage roles ALWAYS get EMPTY_SETTING. Servants don't appear
    in close-ups. This was the #1 visual defect in V26 Scene 001 benchmark.
    """
    if not extras_info:
        return prompt

    # V26.1: SHOT TYPE GUARD — force EMPTY_SETTING for tight shots
    # Close-ups, MCU, ECU, reaction, detail shots should NEVER have background people
    if shot:
        _coverage = (shot.get("coverage_role") or "").upper()
        _stype = (shot.get("type") or shot.get("shot_type") or "").lower()
        _TIGHT_TYPES = {"close_up", "close", "mcu", "ecu", "extreme_close", "medium_close",
                        "reaction", "detail", "insert", "cutaway"}
        if _coverage == "C_EMOTION" or _stype in _TIGHT_TYPES:
            # Force empty setting for tight shots — no servants in close-ups
            if "Empty setting" not in prompt and "no background people" not in prompt:
                prompt = prompt.rstrip(". ,") + ". Empty setting, no background people, no bystanders."
            return prompt

    count = extras_info.get("count", 0)
    behavior = extras_info.get("behavior", "")
    wardrobe = extras_info.get("wardrobe_theme", "")
    focus_rule = extras_info.get("focus_rule", "")

    if count == 0:
        # Explicitly no extras — check if already injected to prevent duplication
        if "Empty setting" not in prompt and "no background people" not in prompt:
            prompt = prompt.rstrip(". ,") + ". Empty setting, no background people, no bystanders."
        return prompt

    additions = []
    if is_ltx:
        # LTX: focus on motion
        if behavior:
            additions.append(f"background: {count} people {behavior}")
        if focus_rule:
            additions.append(focus_rule)
    else:
        # Nano: visual description
        additions.append(f"Background: {count} background people")
        if wardrobe:
            additions.append(f"dressed in {wardrobe}")
        if behavior:
            additions.append(behavior)
        if focus_rule:
            additions.append(focus_rule)

    if additions:
        prompt = prompt.rstrip(". ,") + ". " + ", ".join(additions) + "."

    return prompt


def auto_assign_extras(project_path: Path, shots: List[Dict],
                        story_bible: Dict = None) -> Dict:
    """
    Auto-assign extras to scenes based on location type.

    Heuristics:
    - pub/bar/inn → BAR_CROWD_A
    - village/street/town → VILLAGE_STREET
    - manor interior (private rooms) → EMPTY_SETTING or MANOR_SERVANTS
    - office/law → OFFICE_WORKERS
    - funeral/ceremony → FUNERAL_MOURNERS
    """
    extras = load_extras(project_path)
    scene_extras = extras.get("scene_extras", {})

    # Build scene → location map
    scene_locations = {}
    for shot in shots:
        sid = shot.get("shot_id", "")
        scene = sid.split("_")[0] if "_" in sid else ""
        loc = (shot.get("location") or "").upper()
        if scene and loc and scene not in scene_locations:
            scene_locations[scene] = loc

    new_assignments = 0
    for scene_id, location in scene_locations.items():
        if scene_id in scene_extras:
            continue  # Already assigned

        loc_lower = location.lower()

        # Determine pack based on location keywords
        pack_id = None
        count = None

        if any(w in loc_lower for w in ["pub", "bar", "inn", "tavern", "gull"]):
            pack_id = "BAR_CROWD_A"
            count = 12
        elif any(w in loc_lower for w in ["village", "street", "town", "square", "market"]):
            pack_id = "VILLAGE_STREET"
            count = 8
        elif any(w in loc_lower for w in ["office", "law", "firm", "practice"]):
            pack_id = "OFFICE_WORKERS"
            count = 5
        elif any(w in loc_lower for w in ["funeral", "church", "ceremony", "grave"]):
            pack_id = "FUNERAL_MOURNERS"
            count = 15
        elif any(w in loc_lower for w in ["manor", "room", "chamber", "study", "bedroom",
                                           "kitchen", "hall", "foyer", "corridor", "cellar",
                                           "attic", "library", "ritual"]):
            # Private rooms: no extras unless it's a big hall
            if "hall" in loc_lower or "foyer" in loc_lower:
                pack_id = "MANOR_SERVANTS"
                count = 2
            else:
                pack_id = "EMPTY_SETTING"
                count = 0
        elif any(w in loc_lower for w in ["exterior", "gate", "garden", "cliff",
                                           "road", "path", "coast", "beach", "dock"]):
            pack_id = "EMPTY_SETTING"  # Exterior scenes usually just main chars
            count = 0

        if pack_id:
            pack_data = extras.get("crowd_packs", DEFAULT_CROWD_PACKS).get(pack_id, {})
            scene_extras[scene_id] = {
                "pack_id": pack_id,
                "count": count,
                "behavior": pack_data.get("default_behavior", ""),
                "wardrobe_theme": pack_data.get("wardrobe_theme", ""),
                "consistency": pack_data.get("consistency", "medium"),
                "focus_rule": pack_data.get("focus_rule", "do not steal focus from main characters"),
            }
            new_assignments += 1

    extras["scene_extras"] = scene_extras
    save_extras(project_path, extras)
    logger.info(f"[EXTRAS] Auto-assigned {new_assignments} scenes with crowd packs")
    return extras


# ──────────────────────────────────────────────────────────────
# VALIDATORS
# ──────────────────────────────────────────────────────────────

def validate_wardrobe_continuity(shots: List[Dict], wardrobe: Dict) -> List[Dict]:
    """
    Validate wardrobe continuity across adjacent shots in same scene.

    Returns list of warnings/errors for shots that may have drift.
    This is a pre-render check based on prompt content, not vision.
    """
    issues = []
    looks = wardrobe.get("looks", {})

    # Group shots by scene
    scene_shots = {}
    for shot in shots:
        sid = shot.get("shot_id", "")
        scene = sid.split("_")[0] if "_" in sid else ""
        if scene:
            if scene not in scene_shots:
                scene_shots[scene] = []
            scene_shots[scene].append(shot)

    for scene_id, scene_shot_list in scene_shots.items():
        for shot in scene_shot_list:
            chars = shot.get("characters", [])
            nano = (shot.get("nano_prompt") or "").lower()

            for c in chars:
                name = (c if isinstance(c, str) else c.get("name", "")).upper()
                look_key = f"{name}::{scene_id}"
                look = looks.get(look_key)

                if not look:
                    continue

                if look.get("locked"):
                    tag = look.get("wardrobe_tag", "")
                    if tag and tag.lower() not in nano:
                        issues.append({
                            "shot_id": shot.get("shot_id", ""),
                            "character": name,
                            "severity": "warning",
                            "message": f"Wardrobe locked for {name} ({tag}) but not mentioned in nano_prompt",
                            "look_id": look.get("look_id", ""),
                        })

    return issues


def validate_extras_consistency(shots: List[Dict], extras: Dict) -> List[Dict]:
    """
    Validate extras assignment — check that shots in crowd scenes
    have appropriate crowd direction in their prompts.
    """
    issues = []
    scene_extras = extras.get("scene_extras", {})

    for shot in shots:
        sid = shot.get("shot_id", "")
        scene = sid.split("_")[0] if "_" in sid else ""
        extras_info = scene_extras.get(scene)

        if not extras_info:
            continue

        nano = (shot.get("nano_prompt") or "").lower()
        count = extras_info.get("count", 0)

        if count > 0 and "background" not in nano and "people" not in nano and "crowd" not in nano:
            issues.append({
                "shot_id": sid,
                "severity": "info",
                "message": f"Scene {scene} expects {count} extras but nano_prompt doesn't mention background people",
                "pack_id": extras_info.get("pack_id", ""),
            })

        if count == 0:
            # Check for unwanted people references
            for trigger in ["crowd", "bystander", "onlooker", "passerby", "background people"]:
                if trigger in nano:
                    issues.append({
                        "shot_id": sid,
                        "severity": "warning",
                        "message": f"Scene {scene} is EMPTY_SETTING but prompt mentions '{trigger}'",
                    })

    return issues


# ──────────────────────────────────────────────────────────────
# COMBINED INJECTION (for cinematic enricher integration)
# ──────────────────────────────────────────────────────────────

def enrich_shot_with_wardrobe_extras(shot: Dict, project_path: Path,
                                      wardrobe: Dict = None,
                                      extras: Dict = None) -> Dict:
    """
    One-call enrichment: inject wardrobe + extras into shot prompts.
    Modifies shot dict in-place and returns it.
    """
    pp = Path(project_path) if not isinstance(project_path, Path) else project_path

    if wardrobe is None:
        wardrobe = load_wardrobe(pp)
    if extras is None:
        extras = load_extras(pp)

    # Wardrobe injection
    shot_wardrobe = get_wardrobe_for_shot(wardrobe, shot)
    if shot_wardrobe:
        nano = shot.get("nano_prompt", "") or ""
        ltx = shot.get("ltx_motion_prompt", "") or ""

        shot["nano_prompt"] = inject_wardrobe_into_prompt(nano, shot_wardrobe, is_ltx=False)
        shot["ltx_motion_prompt"] = inject_wardrobe_into_prompt(ltx, shot_wardrobe, is_ltx=True)
        shot["_wardrobe_applied"] = True

    # Extras injection
    extras_info = get_extras_for_shot(extras, shot)
    if extras_info:
        nano = shot.get("nano_prompt", "") or ""
        ltx = shot.get("ltx_motion_prompt", "") or ""

        shot["nano_prompt"] = inject_extras_into_prompt(nano, extras_info, is_ltx=False)
        shot["ltx_motion_prompt"] = inject_extras_into_prompt(ltx, extras_info, is_ltx=True)
        shot["_extras_applied"] = True

    return shot


# ──────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)

    project = sys.argv[1] if len(sys.argv) > 1 else "ravencroft_v17"
    base = Path(__file__).parent.parent / "pipeline_outputs" / project
    sp_path = base / "shot_plan.json"
    sb_path = base / "story_bible.json"

    if not sp_path.exists():
        print(f"Error: {sp_path} not found")
        sys.exit(1)

    with open(sp_path) as f:
        shots = json.load(f).get("shots", [])
    story_bible = None
    if sb_path.exists():
        with open(sb_path) as f:
            story_bible = json.load(f)

    cast_map = None
    cm_path = base / "cast_map.json"
    if cm_path.exists():
        with open(cm_path) as f:
            cast_map = json.load(f)

    action = sys.argv[2] if len(sys.argv) > 2 else "auto"

    if action == "auto":
        print("=== Auto-Assign Wardrobe ===")
        wardrobe = auto_assign_wardrobe(base, shots, story_bible, cast_map)
        print(f"  Total looks: {len(wardrobe['looks'])}")
        for key, look in sorted(wardrobe['looks'].items()):
            print(f"  {key}: {look['look_id']} {'🔒' if look['locked'] else ''}")

        print("\n=== Auto-Assign Extras ===")
        extras = auto_assign_extras(base, shots, story_bible)
        print(f"  Total scene assignments: {len(extras['scene_extras'])}")
        for scene_id, info in sorted(extras['scene_extras'].items()):
            print(f"  Scene {scene_id}: {info['pack_id']} ({info['count']} people)")

    elif action == "validate":
        wardrobe = load_wardrobe(base)
        extras = load_extras(base)

        print("=== Wardrobe Validation ===")
        w_issues = validate_wardrobe_continuity(shots, wardrobe)
        print(f"  {len(w_issues)} issues found")
        for issue in w_issues[:10]:
            print(f"  [{issue['severity']}] {issue['shot_id']}: {issue['message']}")

        print("\n=== Extras Validation ===")
        e_issues = validate_extras_consistency(shots, extras)
        print(f"  {len(e_issues)} issues found")
        for issue in e_issues[:10]:
            print(f"  [{issue['severity']}] {issue['shot_id']}: {issue['message']}")
