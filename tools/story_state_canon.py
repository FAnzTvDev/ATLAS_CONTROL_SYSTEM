"""
tools/story_state_canon.py — ATLAS V36.0 Story State Canon System

Canonical truth source for story-legible change enforcement.
Every gate checks against this. It knows what is TRUE at each point in the story.

Authority order (per CLAUDE.md Section 0 V36):
  Controller ONLY writes. QA ONLY validates. Heatmap ONLY observes.
  This module is a QA/validation layer — it returns verdicts, never mutates.

Three change types:
  hard_lock        — must match exactly within same scene
  canon_progression — allowed to evolve because story authorizes it
  controlled_variance — can vary slightly without being wrong

Usage:
  from tools.story_state_canon import get_canon_state, validate_against_canon
"""

import json
import os
from pathlib import Path
from typing import Optional

# ── STATIC CANON DEFINITIONS (built from story_bible.json analysis) ──────────
# These are derived from the Victorian Shadows story bible and are the ground
# truth for what must be visually true at each scene.

_STATIC_CANON: dict[str, dict] = {

    "001": {
        "scene_id": "001",
        "location": "HARGROVE ESTATE - GRAND FOYER",
        "int_ext": "INT",
        "time_of_day": "MORNING",
        "lighting": "morning light through stained glass, dust motes, dark chandelier unlit",
        "atmosphere": "dust-filtered morning light, faded grandeur, professional tension, grandfather clock ticking",
        "room_condition": "pristine disuse — dust sheets on furniture, untouched since Harriet's death",
        "characters": {
            "ELEANOR VOSS": {
                "present": True,
                "wardrobe": "tailored charcoal blazer, black turtleneck, dark trousers",
                "wardrobe_policy": "hard_lock",
                "hair": "auburn hair pulled back in severe bun",
                "accessories": "leather briefcase",
                "props_carried": ["leather briefcase", "thick document folder"],
                "emotional_state": "professional detachment, controlled authority",
                "physical_state": "upright, precise movement, surveying",
                "knowledge_state": "knows about estate debts, here to execute the sale",
                "injuries": None,
                "wardrobe_negative": "NO casual clothing, NO warm expression, NO blonde hair",
            },
            "THOMAS BLACKWOOD": {
                "present": True,
                "wardrobe": "rumpled navy suit, white shirt open at collar, no tie",
                "wardrobe_policy": "hard_lock",
                "hair": "distinguished silver hair",
                "accessories": "pocket watch chain visible",
                "props_carried": [],
                "emotional_state": "grief, resistance, reverent sorrow",
                "physical_state": "slightly stooped, trails hand along banister, moves slowly",
                "knowledge_state": "knows about his secret love for Harriet, has the emerald ring",
                "injuries": None,
                "wardrobe_negative": "NO bright clothing, NO energetic posture, NO young face",
            },
        },
        "story_progression": {
            "what_just_happened": "Eleanor arrives at estate to begin the estate sale process",
            "what_happens_here": "Eleanor and Thomas meet in the foyer — professional duty vs grief. Thomas resists. Eleanor presents financial reality. Harriet's portrait establishes her presence.",
            "what_changes_after": "Eleanor gains control of the sale. Thomas's grief is established. The portrait is seen for the first time.",
            "key_objects": ["Harriet's oil portrait above staircase", "dust sheets", "console table", "document folder"],
        },
        "forbidden_mistakes": [
            "NO characters teleporting between rooms",
            "NO warm smile on Eleanor",
            "NO clean-shaven young Thomas",
            "NO modern lighting (no electric lights on)",
            "NO absent briefcase on Eleanor",
        ],
    },

    "002": {
        "scene_id": "002",
        "location": "HARGROVE ESTATE - LIBRARY",
        "int_ext": "INT",
        "time_of_day": "MORNING",
        "lighting": "warm morning light through tall windows, golden on leather book spines",
        "atmosphere": "reverent silence, old leather and paper, filtered morning light",
        "room_condition": "intact — books undisturbed, desk with scattered papers, first editions visible",
        "characters": {
            "NADIA COLE": {
                "present": True,
                "wardrobe": "jeans, vintage band t-shirt, open flannel shirt",
                "wardrobe_policy": "hard_lock",
                "hair": "natural textured hair",
                "accessories": "camera around neck",
                "props_carried": ["camera", "hidden letter (discovered mid-scene)", "inventory clipboard"],
                "emotional_state": "professional reverence, then shock and urgency (discovery)",
                "physical_state": "moves carefully through room, lifting camera, treating objects gently",
                "knowledge_state": "START: knows nothing of Harriet/Thomas secret. END: knows about secret relationship from letter",
                "injuries": None,
                "wardrobe_negative": "NO formal clothing, NO straight hair",
            },
        },
        "story_progression": {
            "what_just_happened": "Nadia has arrived at the estate as estate photographer/cataloguer",
            "what_happens_here": "Nadia discovers a hidden letter from Harriet to Thomas inside a first-edition book — the first clue to the secret relationship",
            "what_changes_after": "Nadia now possesses Harriet's letter and the knowledge of the secret relationship. She pockets it — a decision.",
            "key_objects": ["floor-to-ceiling bookshelves", "first edition books (Brontë, Dickens, Wilkie Collins)", "hidden folded letter from Harriet to Thomas", "inventory clipboard"],
        },
        "forbidden_mistakes": [
            "NO Eleanor or Thomas in this scene (solo Nadia scene)",
            "NO formal clothing on Nadia",
            "NO disrespectful handling of books",
            "NO modern technology visible",
            "NO camera absent from Nadia",
        ],
    },

    "003": {
        "scene_id": "003",
        "location": "HARGROVE ESTATE - DRAWING ROOM",
        "int_ext": "INT",
        "time_of_day": "MORNING",
        "lighting": "dim, filtered — heavy curtains partially drawn, dust sheets creating ghostly shapes",
        "atmosphere": "ghostly white dust sheets, dim light, menacing undertone",
        "room_condition": "covered in white dust sheets — furniture ghostly shapes, Steinway piano, silver candelabras",
        "characters": {
            "ELEANOR VOSS": {
                "present": True,
                "wardrobe": "tailored charcoal blazer, black turtleneck, dark trousers",
                "wardrobe_policy": "hard_lock",
                "hair": "auburn hair pulled back in severe bun",
                "accessories": "clipboard and numbered stickers for inventory",
                "props_carried": ["clipboard", "numbered stickers"],
                "emotional_state": "professional focus, then defiant steel resolve",
                "physical_state": "moving through room tagging items, then squared stance to face Raymond",
                "knowledge_state": "conducting estate inventory, not yet aware of Harriet's journal",
                "injuries": None,
                "wardrobe_negative": "NO casual clothing, NO blonde hair, NO warm smile",
            },
            "RAYMOND CROSS": {
                "present": True,
                "wardrobe": "expensive black overcoat, burgundy silk shirt, dark trousers, polished shoes",
                "wardrobe_policy": "hard_lock",
                "hair": "thinning dark hair",
                "accessories": "polished shoes, no briefcase",
                "props_carried": [],
                "emotional_state": "smooth intimidation, predatory confidence, veiled threat",
                "physical_state": "initially blocking doorway, arms folded; moves closer to threaten",
                "knowledge_state": "knows about how Harriet died, represents client with claim on estate",
                "injuries": None,
                "wardrobe_negative": "NO friendly smile, NO casual dress, NO sympathetic expression",
            },
        },
        "story_progression": {
            "what_just_happened": "Eleanor has been doing inventory while Nadia photographs library (concurrent timeline)",
            "what_happens_here": "Raymond confronts Eleanor, asserts client's claim to Steinway, reveals he has information about Harriet's death — a direct threat",
            "what_changes_after": "The mystery of Harriet's death is now explicitly on the table. Eleanor knows she's being threatened.",
            "key_objects": ["white dust sheets on furniture", "Steinway piano", "silver candelabras", "clipboard with inventory stickers"],
        },
        "forbidden_mistakes": [
            "NO Nadia or Thomas in this scene",
            "NO friendly interaction between Eleanor and Raymond",
            "NO bright or cheerful lighting",
            "NO uncovered furniture (everything under dust sheets)",
            "NO Raymond without his overcoat",
        ],
    },

    "004": {
        "scene_id": "004",
        "location": "HARGROVE ESTATE - GARDEN",
        "int_ext": "EXT",
        "time_of_day": "MORNING",
        "lighting": "grey overcast sky, flat diffused light, no sun",
        "atmosphere": "overgrown beauty, grey sky, dead roses, isolation, heavy conscience",
        "room_condition": "overgrown — dead roses on rusted iron trellises, dry cracked stone fountain, weathered bench",
        "characters": {
            "THOMAS BLACKWOOD": {
                "present": True,
                "wardrobe": "rumpled navy suit, white shirt open at collar",
                "wardrobe_policy": "hard_lock",
                "hair": "distinguished silver hair",
                "accessories": "small velvet box (emerald ring inside)",
                "props_carried": ["small velvet box"],
                "emotional_state": "private grief, guilt, mourning",
                "physical_state": "seated on weathered bench, turning velvet box in hands; then rises slowly",
                "knowledge_state": "carries the ring — thirty years of secret love and guilt",
                "injuries": None,
                "wardrobe_negative": "NO bright clothing, NO energetic movement",
            },
        },
        "story_progression": {
            "what_just_happened": "Scene 001 — Thomas met Eleanor in the foyer. He has slipped away to the garden.",
            "what_happens_here": "Thomas alone with the emerald ring — private grief before the investigation deepens. Eleanor calls him back inside.",
            "what_changes_after": "Thomas's possession of the ring is established. The ring becomes significant.",
            "key_objects": ["small velvet box with emerald ring", "dry cracked stone fountain", "weathered bench", "dead roses on rusted trellises"],
        },
        "forbidden_mistakes": [
            "NO other characters in garden initially (solo Thomas scene)",
            "NO sunshine or warm lighting (overcast grey only)",
            "NO manicured garden (overgrown dead roses only)",
            "NO ring visible outside the velvet box",
        ],
    },

    "005": {
        "scene_id": "005",
        "location": "HARGROVE ESTATE - MASTER BEDROOM",
        "int_ext": "INT",
        "time_of_day": "DAY",
        "lighting": "dim, heavy velvet curtains, limited daylight",
        "atmosphere": "heavy curtains, ornate bedroom, memories preserved in photographs, intimate discovery",
        "room_condition": "preserved — ornate four-poster bed, velvet curtains drawn, vanity with framed photographs, Harriet's personal items intact",
        "characters": {
            "NADIA COLE": {
                "present": True,
                "wardrobe": "jeans, vintage band t-shirt, open flannel shirt",
                "wardrobe_policy": "hard_lock",
                "hair": "natural textured hair",
                "accessories": "camera around neck",
                "props_carried": ["camera", "Harriet's letter (in pocket from scene 002)", "Harriet's journal (discovered end of scene)"],
                "emotional_state": "cautious reverence, then wonder and discovery",
                "physical_state": "enters carefully, camera raised, then leans to inspect photographs",
                "knowledge_state": "START: has Harriet's letter. END: has found the journal monogrammed H.H.",
                "injuries": None,
                "wardrobe_negative": "NO formal clothing, NO straight hair",
            },
        },
        "story_progression": {
            "what_just_happened": "Scene 002 — Nadia found and pocketed the letter in the library",
            "what_happens_here": "Nadia enters the master bedroom, finds the face-down photograph of young Thomas and Harriet together, then discovers Harriet's journal",
            "what_changes_after": "Nadia now has the journal. The physical evidence chain is complete. She will bring it to Eleanor.",
            "key_objects": ["ornate four-poster bed", "heavy velvet curtains", "vanity with framed photographs", "face-down photograph of young Thomas and Harriet", "leather journal monogrammed H.H."],
        },
        "forbidden_mistakes": [
            "NO bright lighting (heavy curtains block sun)",
            "NO Eleanor, Thomas, or Raymond in this scene",
            "NO journal visible until Nadia opens vanity drawer",
            "NO camera absent from Nadia",
        ],
    },

    "006": {
        "scene_id": "006",
        "location": "HARGROVE ESTATE - KITCHEN",
        "int_ext": "INT",
        "time_of_day": "DAY",
        "lighting": "practical kitchen light, window overlooking garden, working environment",
        "atmosphere": "copper pots hanging from ceiling racks, makeshift command post, professional urgency",
        "room_condition": "working space — large farmhouse table with documents and laptop, copper pots on ceiling racks, window to garden",
        "characters": {
            "ELEANOR VOSS": {
                "present": True,
                "wardrobe": "tailored charcoal blazer, black turtleneck, dark trousers",
                "wardrobe_policy": "hard_lock",
                "hair": "auburn hair pulled back in severe bun",
                "accessories": "phone (active call), laptop on farmhouse table",
                "props_carried": ["phone"],
                "emotional_state": "stressed professional authority, then shocked urgency (journal reveal)",
                "physical_state": "pacing past copper pots, phone to ear; stops dead when Nadia reveals journal",
                "knowledge_state": "START: dealing with probate dispute. END: knows about journal and possible murder",
                "injuries": None,
                "wardrobe_negative": "NO casual clothing, NO warm smile",
            },
            "NADIA COLE": {
                "present": True,
                "wardrobe": "jeans, vintage band t-shirt, open flannel shirt",
                "wardrobe_policy": "hard_lock",
                "hair": "natural textured hair",
                "accessories": "camera around neck",
                "props_carried": ["camera", "Harriet's journal (in bag/hand)", "Harriet's letter (in pocket)"],
                "emotional_state": "deliberate, measured — she knows the weight of what she's about to say",
                "physical_state": "enters through service door, waits for Eleanor to finish call, then delivers revelation",
                "knowledge_state": "has both the letter and the journal, knows about the secret relationship and the possible cover-up",
                "injuries": None,
                "wardrobe_negative": "NO formal clothing, NO straight hair",
            },
        },
        "story_progression": {
            "what_just_happened": "Scene 005 — Nadia found the journal. Scene 003 — Eleanor argued about probate.",
            "what_happens_here": "Eleanor on phone with probate, Nadia arrives and delivers the bombshell: Harriet's journal contradicts the official cause of death",
            "what_changes_after": "Eleanor now knows about the journal. The estate sale transforms into an investigation. Stakes are raised.",
            "key_objects": ["copper pots on ceiling racks", "large farmhouse table with documents and laptop", "phone", "Harriet's journal (revealed end of scene)", "window to garden"],
        },
        "forbidden_mistakes": [
            "NO other characters (Thomas, Raymond) in this scene unless explicit blocking",
            "NO journal absent from Nadia's possession when she arrives",
            "NO warm or casual body language on Eleanor",
            "NO Nadia without camera around neck",
        ],
    },
}


def _load_story_bible(project_dir: str) -> Optional[dict]:
    """Load story bible from project directory. Returns None if not found."""
    path = Path(project_dir) / "story_bible.json"
    if path.exists():
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:
            return None
    return None


def _build_canon_from_bible(story_bible: dict) -> dict[str, dict]:
    """
    V36.5.2: Build FULL canon states from story_bible.json — the story bible
    is the SINGLE SOURCE OF TRUTH. No hardcoding required.

    Extracts: characters, wardrobe, hair, props, emotional/physical state,
    knowledge progression, key objects, forbidden mistakes, atmosphere —
    ALL from story_bible fields and beat analysis.
    """
    dynamic = {}
    scenes = story_bible.get("scenes", [])
    characters = {c["name"]: c for c in story_bible.get("characters", [])}

    for scene in scenes:
        sid = scene.get("scene_id", "")
        if not sid:
            continue

        beats = scene.get("beats", [])
        chars_present = scene.get("characters_present", [])

        # ── Build character canon from story_bible master data + beat context ──
        chars_in_scene = {}
        for char_name in chars_present:
            char_data = characters.get(char_name, {})
            appearance = char_data.get("appearance", "")

            # Extract hair from appearance
            hair = ""
            for token in appearance.split(","):
                if "hair" in token.lower():
                    hair = token.strip()
                    break

            # Extract accessories from appearance
            accessories = ""
            for token in appearance.split(","):
                tok_lower = token.lower().strip()
                if any(kw in tok_lower for kw in ("camera", "briefcase", "watch", "ring",
                    "necklace", "glasses", "hat", "bag", "phone", "clipboard")):
                    accessories = token.strip()
                    break

            # Extract props from beats where this character acts
            props = set()
            emotional_states = []
            physical_states = []
            for beat in beats:
                action = (beat.get("character_action") or "").lower()
                desc = (beat.get("description") or "").lower()
                combined = action + " " + desc
                # Check if this character is mentioned in the beat
                char_words = char_name.lower().split()
                if any(w in combined for w in char_words):
                    # Extract props from action keywords
                    for prop_kw in ("journal", "letter", "camera", "briefcase", "ring",
                                    "box", "phone", "clipboard", "sticker", "book",
                                    "photograph", "photo", "document", "key", "bottle",
                                    "candle", "folder", "newspaper", "note"):
                        if prop_kw in combined:
                            props.add(prop_kw)
                    # Capture physical state from action
                    if action.strip():
                        physical_states.append(beat.get("character_action", ""))
                    # Capture emotional from atmosphere
                    atm = beat.get("atmosphere", "")
                    if atm:
                        emotional_states.append(atm)

            # Derive knowledge state from first/last beat descriptions
            knowledge_start = ""
            knowledge_end = ""
            if beats:
                knowledge_start = beats[0].get("description", "")[:100]
                knowledge_end = beats[-1].get("description", "")[:100]

            chars_in_scene[char_name] = {
                "present": True,
                "wardrobe": char_data.get("wardrobe_default", ""),
                "wardrobe_policy": "hard_lock",
                "hair": hair,
                "accessories": accessories,
                "props_carried": sorted(props),
                "emotional_state": "; ".join(emotional_states[:2]) if emotional_states else scene.get("atmosphere", ""),
                "physical_state": physical_states[0] if physical_states else "",
                "knowledge_state": f"START: {knowledge_start} END: {knowledge_end}" if knowledge_start else "",
                "injuries": None,
                "wardrobe_negative": char_data.get("negative", ""),
            }

        # ── Extract key objects from all beats ─────────────────────────────
        key_objects = set()
        for beat in beats:
            desc = (beat.get("description") or "").lower()
            action = (beat.get("character_action") or "").lower()
            combined = desc + " " + action
            for obj_kw in ("portrait", "journal", "letter", "ring", "piano", "staircase",
                           "photograph", "phone", "briefcase", "candelabra", "book",
                           "dust sheet", "fountain", "bench", "rose", "velvet box",
                           "copper pot", "table", "window", "curtain", "vanity",
                           "door", "clock", "chandelier"):
                if obj_kw in combined:
                    key_objects.add(obj_kw)

        # ── Auto-generate forbidden mistakes ───────────────────────────────
        forbidden = []
        # No teleporting
        forbidden.append("NO characters teleporting between rooms")
        # No characters who shouldn't be here
        all_char_names = set(characters.keys())
        absent = all_char_names - set(chars_present)
        if absent and len(chars_present) <= 2:
            absent_str = ", ".join(sorted(absent)[:3])
            forbidden.append(f"NO {absent_str} in this scene")
        # Wardrobe negatives
        for cn in chars_present:
            neg = characters.get(cn, {}).get("negative", "")
            if neg:
                forbidden.append(f"{cn}: {neg}")
        # Solo scene guard
        if len(chars_present) == 1:
            forbidden.append(f"Solo {chars_present[0]} scene — NO off-camera partner direction")

        # ── Build story progression from beat sequence ─────────────────────
        story_prog = {
            "what_just_happened": "",
            "what_happens_here": scene.get("description", ""),
            "what_changes_after": "",
            "key_objects": sorted(key_objects),
        }
        if beats:
            story_prog["what_just_happened"] = beats[0].get("description", "")[:120]
            story_prog["what_changes_after"] = beats[-1].get("description", "")[:120]

        dynamic[sid] = {
            "scene_id": sid,
            "location": scene.get("location", ""),
            "int_ext": scene.get("int_ext", "INT"),
            "time_of_day": scene.get("time_of_day", ""),
            "lighting": scene.get("atmosphere", ""),
            "atmosphere": scene.get("atmosphere", ""),
            "room_condition": scene.get("description", ""),
            "characters": chars_in_scene,
            "story_progression": story_prog,
            "forbidden_mistakes": forbidden,
        }

    return dynamic


def build_canon(project_dir: str) -> dict[str, dict]:
    """
    V36.5.2: Build full canon for a project.
    Story bible is PRIMARY source of truth (dynamic).
    Static canon only ENRICHES fields the story bible can't derive
    (e.g., hand-authored knowledge_state, forbidden_mistakes detail).
    Dynamic always wins on: characters, location, atmosphere, time_of_day.
    """
    story_bible = _load_story_bible(project_dir)
    if story_bible:
        dynamic = _build_canon_from_bible(story_bible)
    else:
        dynamic = {}

    # V36.5.2: Dynamic (story_bible) is PRIMARY. Static enriches ONLY.
    merged = {}
    all_sids = set(list(dynamic.keys()) + list(_STATIC_CANON.keys()))
    for sid in all_sids:
        dyn = dynamic.get(sid, {})
        stat = _STATIC_CANON.get(sid, {})
        if not dyn:
            # No story bible scene — use static as-is (legacy fallback)
            merged[sid] = stat
            continue
        if not stat:
            # No static enrichment — use dynamic as-is (new projects)
            merged[sid] = dyn
            continue
        # Both exist: dynamic wins on structure, static enriches detail
        merged_scene = dict(dyn)  # start from dynamic
        # Enrich characters: static adds detailed knowledge_state, props,
        # emotional nuance that story_bible beats may not fully capture
        dyn_chars = dyn.get("characters", {})
        stat_chars = stat.get("characters", {})
        merged_chars = {}
        for cn in set(list(dyn_chars.keys()) + list(stat_chars.keys())):
            dc = dyn_chars.get(cn, {})
            sc = stat_chars.get(cn, {})
            if not dc:
                merged_chars[cn] = sc
                continue
            mc = dict(dc)
            # Static enriches ONLY empty fields (doesn't overwrite dynamic)
            for field in ("knowledge_state", "props_carried", "accessories",
                          "emotional_state", "physical_state"):
                dyn_val = mc.get(field)
                stat_val = sc.get(field)
                if not dyn_val and stat_val:
                    mc[field] = stat_val
            # Static forbidden wardrobe is richer — merge
            dyn_neg = mc.get("wardrobe_negative", "")
            stat_neg = sc.get("wardrobe_negative", "")
            if stat_neg and stat_neg != dyn_neg:
                mc["wardrobe_negative"] = stat_neg  # static typically more detailed
            merged_chars[cn] = mc
        merged_scene["characters"] = merged_chars
        # Enrich forbidden_mistakes: union of both
        dyn_fm = set(dyn.get("forbidden_mistakes", []))
        stat_fm = set(stat.get("forbidden_mistakes", []))
        merged_scene["forbidden_mistakes"] = sorted(dyn_fm | stat_fm)
        # Enrich story_progression: static wins if it has more detail
        dyn_sp = dyn.get("story_progression", {})
        stat_sp = stat.get("story_progression", {})
        merged_sp = dict(dyn_sp)
        for field in ("what_just_happened", "what_changes_after", "key_objects"):
            dyn_val = merged_sp.get(field)
            stat_val = stat_sp.get(field)
            if stat_val and (not dyn_val or (isinstance(dyn_val, str) and len(str(stat_val)) > len(str(dyn_val)))):
                merged_sp[field] = stat_val
        merged_scene["story_progression"] = merged_sp
        merged[sid] = merged_scene

    return merged


def get_canon_state(scene_id: str, project_dir: Optional[str] = None) -> Optional[dict]:
    """
    V36.5.2: Get canon state for a scene. Story bible is always consulted first.

    Args:
        scene_id: e.g. "001", "002", "006"
        project_dir: optional path to project directory for dynamic loading

    Returns:
        Canon state dict, or None if scene unknown.
    """
    sid = str(scene_id).zfill(3)

    # V36.5.2: Always try merged canon (story_bible primary + static enrichment)
    if project_dir:
        canon = build_canon(project_dir)
        result = canon.get(sid)
        if result:
            return result

    # Fallback: static only (no project_dir provided)
    if sid in _STATIC_CANON:
        return _STATIC_CANON[sid]

    return None


def validate_against_canon(shot_metadata: dict, canon_state: dict) -> list[str]:
    """
    Validate a shot's metadata against the scene's canon state.
    Returns a list of violation strings. Empty list = clean.

    This is a QA function — returns verdicts only, never mutates.

    Args:
        shot_metadata: dict from shot_plan.json
        canon_state: dict from get_canon_state()

    Returns:
        list of human-readable violation strings
    """
    violations = []

    shot_id = shot_metadata.get("shot_id", "?")
    shot_chars = shot_metadata.get("characters", [])
    nano_prompt = shot_metadata.get("nano_prompt", "") or ""
    description = shot_metadata.get("description", "") or ""
    combined_text = (nano_prompt + " " + description).lower()

    canon_chars = canon_state.get("characters", {})
    forbidden = canon_state.get("forbidden_mistakes", [])

    # ── 1. WARDROBE CHECKS (hard_lock policy) ────────────────────────────────
    for char_name in shot_chars:
        if char_name not in canon_chars:
            continue
        char_canon = canon_chars[char_name]
        policy = char_canon.get("wardrobe_policy", "hard_lock")
        if policy != "hard_lock":
            continue

        wardrobe = char_canon.get("wardrobe", "")
        wardrobe_negative = char_canon.get("wardrobe_negative", "")

        # Check wardrobe is referenced in prompt (key garment tokens)
        garment_tokens = [tok.strip().lower() for tok in wardrobe.split(",") if tok.strip()]
        if garment_tokens and nano_prompt:
            matched = sum(1 for tok in garment_tokens if tok in combined_text)
            if matched == 0:
                violations.append(
                    f"[WARDROBE] {shot_id} / {char_name}: "
                    f"no wardrobe tokens found in prompt. "
                    f"Expected: {wardrobe}"
                )

        # Check negative wardrobe constraints not violated
        if wardrobe_negative and nano_prompt:
            neg_tokens = [tok.strip().lower().lstrip("no ") for tok in wardrobe_negative.split(",") if tok.strip()]
            for neg in neg_tokens:
                if neg and neg in combined_text:
                    violations.append(
                        f"[WARDROBE_NEG] {shot_id} / {char_name}: "
                        f"forbidden wardrobe element found in prompt: '{neg}'"
                    )

    # ── 2. CHARACTER PRESENCE CHECKS ─────────────────────────────────────────
    # Check that characters in the shot are supposed to be in this scene
    for char_name in shot_chars:
        if char_name not in canon_chars:
            # Character not in canon for this scene — flag unless it's a B-roll shot
            is_broll = shot_metadata.get("_is_broll", False) or shot_metadata.get("is_broll", False)
            is_establishing = shot_metadata.get("_is_establishing", False)
            if not is_broll and not is_establishing:
                violations.append(
                    f"[CHAR_PRESENCE] {shot_id}: character '{char_name}' not in canon "
                    f"for scene {canon_state.get('scene_id', '?')}. "
                    f"Canon characters: {list(canon_chars.keys())}"
                )

    # ── 3. LOCATION CHECK ────────────────────────────────────────────────────
    canon_location = canon_state.get("location", "").lower()
    shot_location = (shot_metadata.get("location", "") or "").lower()
    if canon_location and shot_location and canon_location not in shot_location and shot_location not in canon_location:
        # Only flag if significantly different (not a substring match)
        violations.append(
            f"[LOCATION] {shot_id}: shot location '{shot_metadata.get('location')}' "
            f"does not match canon location '{canon_state.get('location')}'"
        )

    # ── 4. FORBIDDEN MISTAKES ────────────────────────────────────────────────
    for mistake in forbidden:
        # Convert mistake to a searchable token
        mistake_lower = mistake.lower().lstrip("no ").strip()
        if len(mistake_lower) > 4 and mistake_lower in combined_text:
            violations.append(
                f"[FORBIDDEN] {shot_id}: potential forbidden element detected: '{mistake}'"
            )

    # ── 5. KEY PROPS CHECK ───────────────────────────────────────────────────
    story_prog = canon_state.get("story_progression", {})
    key_objects = story_prog.get("key_objects", [])

    # For closing shots, check that key scene objects are referenced
    is_closing = shot_metadata.get("_is_closing", False)
    if is_closing and key_objects and nano_prompt:
        key_obj_tokens = [obj.lower() for obj in key_objects]
        # At least one key object should be in the closing shot
        matched_objs = [obj for obj in key_obj_tokens if any(tok in combined_text for tok in obj.split())]
        if not matched_objs:
            violations.append(
                f"[KEY_OBJECTS] {shot_id} (closing shot): "
                f"none of the scene key objects referenced in prompt. "
                f"Expected one of: {key_objects[:3]}"
            )

    return violations


def get_all_scene_ids(project_dir: Optional[str] = None) -> list[str]:
    """Return all scene IDs with canon definitions (dynamic + static)."""
    sids = set(_STATIC_CANON.keys())
    if project_dir:
        canon = build_canon(project_dir)
        sids |= set(canon.keys())
    return sorted(sids)


def add_canon_ref_to_shots(shot_plan: list, project_dir: Optional[str] = None) -> list:
    """
    Add _canon_state_ref field to all shots in shot_plan pointing to their scene's canon.
    Returns the modified shot list (does NOT write to disk — Controller writes).

    Args:
        shot_plan: list of shot dicts
        project_dir: optional path for dynamic canon loading

    Returns:
        Modified shot list with _canon_state_ref added.
    """
    canon_cache: dict[str, Optional[dict]] = {}

    for shot in shot_plan:
        sid = shot.get("shot_id", "")
        scene_id = shot.get("scene_id", sid[:3] if len(sid) >= 3 else "")

        if scene_id not in canon_cache:
            canon_cache[scene_id] = get_canon_state(scene_id, project_dir)

        canon = canon_cache[scene_id]
        if canon:
            shot["_canon_state_ref"] = scene_id
            # Also stamp the canon location for quick reference
            shot["_canon_location"] = canon.get("location", "")
            shot["_canon_time_of_day"] = canon.get("time_of_day", "")
        else:
            shot["_canon_state_ref"] = None

    return shot_plan


def validate_scene(scene_id: str, shots: list, project_dir: Optional[str] = None) -> dict:
    """
    Run canon validation over all shots in a scene.

    Returns:
        {
            "scene_id": str,
            "canon_state": dict,
            "violations": [{"shot_id": str, "issues": [str]}],
            "clean_shots": int,
            "violation_shots": int,
            "total_shots": int,
        }
    """
    canon = get_canon_state(scene_id, project_dir)
    if not canon:
        return {
            "scene_id": scene_id,
            "canon_state": None,
            "error": f"No canon state for scene {scene_id}",
            "violations": [],
            "clean_shots": 0,
            "violation_shots": 0,
            "total_shots": len(shots),
        }

    scene_shots = [s for s in shots if s.get("scene_id") == scene_id
                   or (s.get("shot_id", "").startswith(scene_id))]

    all_violations = []
    clean = 0

    for shot in scene_shots:
        issues = validate_against_canon(shot, canon)
        if issues:
            all_violations.append({"shot_id": shot.get("shot_id", "?"), "issues": issues})
        else:
            clean += 1

    return {
        "scene_id": scene_id,
        "canon_state": canon,
        "violations": all_violations,
        "clean_shots": clean,
        "violation_shots": len(all_violations),
        "total_shots": len(scene_shots),
    }


# ── CROSS-SCENE WARDROBE BLEED DETECTION (V36.3) ─────────────────────────────
# Checks that a shot's generated frame doesn't carry wardrobe from a DIFFERENT
# scene's canon. This catches the contamination where end-frame chaining or
# prompt inheritance causes Scene 001 wardrobe to bleed into Scene 006.

def validate_cross_scene_wardrobe(shot: dict, current_scene_id: str,
                                   project_dir: str = None) -> list[str]:
    """
    Check if a shot's prompt/description accidentally references wardrobe
    from a DIFFERENT scene's canon for the same character.

    Returns list of cross-scene bleed violation strings.
    """
    violations = []
    shot_chars = shot.get("characters") or []
    nano_prompt = (shot.get("nano_prompt") or "").lower()
    description = (shot.get("description") or "").lower()
    combined = nano_prompt + " " + description
    shot_id = shot.get("shot_id", "?")

    if not combined.strip() or not shot_chars:
        return violations

    # Get current scene's canon
    current_canon = get_canon_state(current_scene_id, project_dir)
    if not current_canon:
        return violations

    # Check each character against OTHER scenes' wardrobes
    all_scene_ids = get_all_scene_ids()
    for char_name in shot_chars:
        # Get this character's CORRECT wardrobe for current scene
        current_char = current_canon.get("characters", {}).get(char_name, {})
        correct_wardrobe = current_char.get("wardrobe", "")

        # Scan other scenes for this character's different wardrobes
        for other_sid in all_scene_ids:
            if other_sid == current_scene_id:
                continue
            other_canon = get_canon_state(other_sid, project_dir)
            if not other_canon:
                continue
            other_char = other_canon.get("characters", {}).get(char_name, {})
            other_wardrobe = other_char.get("wardrobe", "")

            if not other_wardrobe or other_wardrobe == correct_wardrobe:
                continue  # Same wardrobe or no wardrobe — no bleed possible

            # Extract distinctive tokens from OTHER scene's wardrobe that differ
            # from current scene's wardrobe
            other_tokens = {tok.strip().lower() for tok in other_wardrobe.split(",") if tok.strip()}
            correct_tokens = {tok.strip().lower() for tok in correct_wardrobe.split(",") if tok.strip()}
            bleed_tokens = other_tokens - correct_tokens  # tokens unique to other scene

            for tok in bleed_tokens:
                if len(tok) > 4 and tok in combined:
                    violations.append(
                        f"[WARDROBE_BLEED] {shot_id} / {char_name}: "
                        f"prompt contains '{tok}' from scene {other_sid} wardrobe "
                        f"('{other_wardrobe}'), but current scene {current_scene_id} "
                        f"requires '{correct_wardrobe}'"
                    )
                    break  # One bleed per character per scene is enough

    return violations


def get_wardrobe_for_scene(char_name: str, scene_id: str,
                            project_dir: str = None) -> str:
    """Get the canonical wardrobe for a character in a specific scene.
    Returns empty string if character not in that scene's canon."""
    canon = get_canon_state(scene_id, project_dir)
    if not canon:
        return ""
    char_data = canon.get("characters", {}).get(char_name, {})
    return char_data.get("wardrobe", "")


# ── CLI DIAGNOSTIC ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    project_dir = sys.argv[1] if len(sys.argv) > 1 else "pipeline_outputs/victorian_shadows_ep1"

    print(f"\n{'='*60}")
    print(f"STORY STATE CANON — ATLAS V36.0")
    print(f"Project: {project_dir}")
    print(f"{'='*60}")

    # Load shot plan
    sp_path = Path(project_dir) / "shot_plan.json"
    if not sp_path.exists():
        print(f"ERROR: shot_plan.json not found at {sp_path}")
        sys.exit(1)

    with open(sp_path) as f:
        sp = json.load(f)
    shots = sp if isinstance(sp, list) else list(sp.values())

    print(f"\nLoaded {len(shots)} shots")
    print(f"Canon scenes defined: {get_all_scene_ids()}\n")

    # Validate scenes 001, 002, 006
    for scene_id in ["001", "002", "006"]:
        result = validate_scene(scene_id, shots, project_dir)
        canon = result.get("canon_state")
        print(f"SCENE {scene_id}: {canon.get('location', '?') if canon else 'NO CANON'}")
        print(f"  Shots: {result['total_shots']} | Clean: {result['clean_shots']} | Violations: {result['violation_shots']}")
        for v in result["violations"]:
            print(f"  [{v['shot_id']}]")
            for issue in v["issues"]:
                print(f"    ⚠  {issue}")
        print()

    print("Done. Canon validation complete.")
