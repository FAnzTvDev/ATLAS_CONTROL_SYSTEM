"""
ATLAS V27.2: Scene Continuity Enforcer
======================================
Synchronizes LIGHTING, FRAMING, and BLOCKING across all shots in a scene.
Runs BEFORE generation (pre-gen gate), not after (post-hoc advisory).

Three enforcement layers:
1. LIGHTING LOCK — Scene-level lighting master propagated to every shot
2. FRAMING SYNC — Shot type → lens/DOF/composition rules enforced
3. BLOCKING AUDIT — Every character shot has physical direction

Non-blocking: logs warnings but doesn't halt generation.
Enrichment: injects missing lighting/blocking into prompts automatically.

Wired into orchestrator as Phase E3 (after Film Engine + Dialogue Cinematography).
"""

import json
import re
from typing import Dict, List, Optional, Tuple


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1: SCENE LIGHTING LOCK
# ═══════════════════════════════════════════════════════════════════════════════

# Scene lighting profiles derived from location + time_of_day + story_bible mood
INTERIOR_LIGHTING_PROFILES = {
    "foyer": {
        "key": "dim natural light from tall arched windows, cool daylight filtering through dusty glass",
        "fill": "warm amber glow from ornate wall sconces and chandelier",
        "practical": "antique chandelier overhead casting gentle warm pools of light",
        "shadow": "deep charcoal shadows in corners and under staircase",
        "color_temp": "mixed: cool 5600K window daylight cutting through warm 2800K tungsten practicals",
        "mood": "atmospheric chiaroscuro, dusty light beams, gothic interior",
    },
    "study": {
        "key": "warm lamplight from desk lamp and reading sconces",
        "fill": "soft ambient from curtained windows, muted daylight",
        "practical": "green-shade banker's lamp, leather-warm tones",
        "shadow": "rich dark wood absorbing light, deep pools of shadow",
        "color_temp": "warm dominant: 2800K tungsten with 4000K ambient fill",
        "mood": "intimate, enclosed, claustrophobic warmth",
    },
    "library": {
        "key": "filtered daylight through heavy drapes, dust motes visible",
        "fill": "warm book-spine reflections, amber wood tones",
        "practical": "standing floor lamp, fireplace glow if present",
        "shadow": "tall shelf shadows creating vertical dark stripes",
        "color_temp": "warm: 3200K dominant with cool window accents",
        "mood": "scholarly, hushed, layered depth",
    },
    "bedroom": {
        "key": "soft window light through sheer curtains",
        "fill": "bedside lamp warm glow, fabric-diffused",
        "practical": "table lamp, vanity mirror light",
        "shadow": "gentle, wrapped shadows, soft transitions",
        "color_temp": "warm: 2700K intimate lighting",
        "mood": "private, vulnerable, soft contrast",
    },
    "exterior": {
        "key": "overcast sky providing flat even illumination",
        "fill": "ambient skylight from all directions",
        "practical": "none — natural light only",
        "shadow": "soft diffused shadows, low contrast",
        "color_temp": "cool: 6500K overcast daylight",
        "mood": "grey, muted, atmospheric",
    },
    "cemetery": {
        "key": "overcast dawn light, grey and flat",
        "fill": "ambient fog diffusion softening all edges",
        "practical": "none — natural pre-dawn light only",
        "shadow": "muted, low-contrast, fog-softened",
        "color_temp": "cool desaturated: 7000K overcast dawn",
        "mood": "somber, muted, rain-dampened, grey-blue palette",
    },
    "default": {
        "key": "natural ambient light from windows",
        "fill": "practical room lighting",
        "practical": "visible room lights",
        "shadow": "medium contrast shadows",
        "color_temp": "mixed: 4500K neutral",
        "mood": "cinematic, atmospheric",
    }
}

# Shot type → framing enforcement rules
FRAMING_RULES = {
    "establishing": {"lens": "24-35mm", "dof": "deep", "height": "eye-level or elevated", "composition": "wide, showing full geography"},
    "wide": {"lens": "24-35mm", "dof": "deep", "height": "eye-level", "composition": "full room visible, characters small in frame"},
    "medium": {"lens": "50mm", "dof": "medium", "height": "eye-level", "composition": "waist-up, character in environment context"},
    "medium_close": {"lens": "85mm", "dof": "shallow f/1.4-2.0", "height": "eye-level", "composition": "chest-up, face dominant, background soft"},
    "close_up": {"lens": "85-135mm", "dof": "very shallow f/1.4", "height": "eye-level", "composition": "face fills frame, eyes sharp, heavy bokeh"},
    "over_the_shoulder": {"lens": "50-85mm", "dof": "shallow f/2.0", "height": "eye-level", "composition": "foreground shoulder soft, background character sharp"},
    "two_shot": {"lens": "35-50mm", "dof": "medium f/2.8", "height": "eye-level", "composition": "both characters visible, confrontational blocking"},
    "reaction": {"lens": "85mm", "dof": "shallow f/1.4", "height": "eye-level", "composition": "face reaction, tight on expression, heavy bokeh"},
    "insert": {"lens": "50-100mm", "dof": "very shallow", "height": "varies", "composition": "object detail, context minimal"},
    "closing": {"lens": "35-50mm", "dof": "medium-deep", "height": "eye-level or slightly elevated", "composition": "pull-back, characters in full room geography"},
    "drone": {"lens": "24mm wide", "dof": "deep f/8", "height": "overhead bird's eye", "composition": "top-down, full property visible"},
}

# Physical blocking verbs per character action type
BLOCKING_VERBS = {
    "entering": ["enters through doorway", "steps into frame", "crosses threshold", "pushes through door"],
    "standing": ["stands rigid", "plants feet", "holds position", "remains motionless"],
    "gripping": ["grips banister railing", "clutches document folder", "white-knuckle grip on briefcase handle"],
    "confronting": ["faces opponent squarely", "steps forward into personal space", "squares shoulders"],
    "retreating": ["takes half-step backward", "shifts weight away", "turns shoulder slightly"],
    "reacting": ["jaw tightens", "brow furrows", "eyes narrow", "chin lifts defiantly"],
    "presenting": ["extends document forward", "opens folder on surface", "gestures to evidence"],
    "observing": ["gaze tracks across room", "eyes fixed on portrait", "scans the space"],
}


def resolve_scene_lighting(scene_shots: List[Dict], story_bible_scene: Dict = None) -> Dict:
    """
    Resolve the MASTER LIGHTING PROFILE for a scene.

    Reads location from shots and story_bible to determine room type,
    then returns the lighting lock that every shot must inherit.
    """
    # Determine PRIMARY room type — story_bible location takes priority
    # Then MAJORITY vote from character-containing shots (ignoring cold open / inserts)
    room_type = "default"

    # Priority 1: Story bible scene location (the screenplay's declared location)
    if story_bible_scene:
        sb_loc = (story_bible_scene.get("location", "") or "").lower()
        room_type = _detect_room_type(sb_loc)

    # Priority 2: If story bible didn't resolve, use majority of character shots
    if room_type == "default":
        room_votes = {}
        for s in scene_shots:
            chars = s.get("characters", []) or []
            if not chars:
                continue  # Skip B-roll, establishing, inserts for voting
            loc = (s.get("location", "") or "").lower()
            desc = (s.get("description", "") or "").lower()
            detected = _detect_room_type(loc + " " + desc)
            room_votes[detected] = room_votes.get(detected, 0) + 1
        if room_votes:
            room_type = max(room_votes, key=room_votes.get)

    # Also build per-shot room overrides for opening shots in different locations
    per_shot_rooms = {}
    for s in scene_shots:
        sid = s.get("shot_id", "")
        loc = (s.get("location", "") or "").lower()
        desc = (s.get("description", "") or "").lower()
        shot_room = _detect_room_type(loc + " " + desc)
        if shot_room != "default" and shot_room != room_type:
            per_shot_rooms[sid] = shot_room

    profile = INTERIOR_LIGHTING_PROFILES.get(room_type, INTERIOR_LIGHTING_PROFILES["default"])

    return {
        "room_type": room_type,
        "profile": profile,
        "lighting_lock_phrase": _build_lighting_phrase(profile),
        "per_shot_rooms": per_shot_rooms,  # Shots in different locations get their own profile
    }


def _detect_room_type(text: str) -> str:
    """Detect room type from a text string (location or description).
    V27.3: Specific rooms checked BEFORE generic 'estate' to prevent
    'HARGROVE ESTATE - LIBRARY' matching 'foyer' via 'estate' keyword.
    """
    text = text.lower()
    # V27.3: Check SPECIFIC rooms first (before generic location words like "estate")
    if any(kw in text for kw in ["cemetery", "burial", "graveyard", "grave", "headstone"]):
        return "cemetery"
    if any(kw in text for kw in ["library", "bookshelf", "books"]):
        return "library"
    if any(kw in text for kw in ["study", "office", "desk"]):
        return "study"
    if any(kw in text for kw in ["bedroom", "bed", "chamber", "master bedroom"]):
        return "bedroom"
    if any(kw in text for kw in ["kitchen", "pantry", "scullery", "cooking"]):
        return "kitchen"
    if any(kw in text for kw in ["drawing room", "sitting room", "parlor", "parlour", "salon"]):
        return "drawing_room"
    if any(kw in text for kw in ["garden", "exterior", "outside", "driveway", "front drive", "drone", "aerial", "overhead"]):
        return "exterior"
    if any(kw in text for kw in ["staircase", "grand staircase", "landing"]):
        return "staircase"
    # Generic estate/foyer checked LAST
    if any(kw in text for kw in ["foyer", "entrance hall", "grand hall", "vestibule", "hallway", "estate"]):
        return "foyer"
    return "default"


def _build_lighting_phrase(profile: Dict) -> str:
    """Build a concise lighting phrase for prompt injection (max 120 chars)."""
    key = profile.get("key", "")
    shadow = profile.get("shadow", "")
    mood = profile.get("mood", "")

    # Take the most important elements
    parts = []
    if key:
        # Extract the core of the key light description
        parts.append(key.split(",")[0].strip())
    if shadow:
        parts.append(shadow.split(",")[0].strip())
    if mood:
        parts.append(mood.split(",")[0].strip())

    phrase = ", ".join(parts)
    if len(phrase) > 150:
        phrase = phrase[:147] + "..."
    return phrase


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2: FRAMING CONSISTENCY ENFORCER
# ═══════════════════════════════════════════════════════════════════════════════

def enforce_framing(shot: Dict) -> Dict:
    """
    Check that shot's nano_prompt contains appropriate framing for its shot_type.
    If missing, inject framing guidance into the prompt.
    Returns the shot with framing enrichment applied.
    """
    shot_type = (shot.get("shot_type") or shot.get("type") or "medium").lower()
    nano = shot.get("nano_prompt", "") or ""

    rules = FRAMING_RULES.get(shot_type, FRAMING_RULES.get("medium"))
    if not rules:
        return shot

    injections = []
    flags = shot.get("_continuity_flags", [])

    # Check lens
    lens_pattern = r'\d+mm'
    if not re.search(lens_pattern, nano):
        injections.append(f"{rules['lens']} lens")
        flags.append(f"framing:lens_injected:{rules['lens']}")

    # Check DOF
    dof_keywords = ["f/", "bokeh", "shallow depth", "deep focus", "depth of field"]
    if not any(kw in nano.lower() for kw in dof_keywords):
        injections.append(f"{rules['dof']} depth of field")
        flags.append(f"framing:dof_injected:{rules['dof']}")

    # Check composition hint
    comp_keywords = ["fills frame", "waist-up", "chest-up", "full body", "wide shot", "overhead", "bird"]
    if not any(kw in nano.lower() for kw in comp_keywords):
        injections.append(rules["composition"])
        flags.append("framing:composition_injected")

    if injections:
        framing_clause = ". ".join(injections)
        # Inject BEFORE the last sentence of the prompt
        shot["nano_prompt"] = nano.rstrip(". ") + ". " + framing_clause + "."
        shot["_continuity_flags"] = flags
        shot["_framing_enforced"] = True

    return shot


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3: BLOCKING AUDIT + ENRICHMENT
# ═══════════════════════════════════════════════════════════════════════════════

def audit_blocking(shot: Dict, prev_shot: Optional[Dict] = None) -> Dict:
    """
    Audit a shot's blocking direction. If missing physical verbs
    for character shots, inject blocking from the description and emotional beat.
    """
    chars = shot.get("characters", []) or []
    nano = shot.get("nano_prompt", "") or ""
    desc = (shot.get("description", "") or "").lower()
    beat = (shot.get("emotional_beat", "") or "").lower()
    shot_type = (shot.get("shot_type") or shot.get("type") or "").lower()

    flags = shot.get("_continuity_flags", [])

    # Non-character shots (B-roll, establishing, drone) don't need blocking
    if not chars and shot_type in ["establishing", "insert", "drone", "closing"]:
        return shot

    # Check for physical blocking verbs in nano_prompt
    blocking_verbs = [
        "enters", "exits", "stands", "seated", "leaning", "gripping", "holding",
        "clutching", "facing", "turns", "crosses", "steps", "reaches", "gestures",
        "confronts", "retreats", "advances", "plants", "shifts", "lifts", "lowers",
        "tightens", "clenches", "narrows", "furrows", "squeezes"
    ]

    has_blocking = any(v in nano.lower() for v in blocking_verbs)

    if not has_blocking and chars:
        # Derive blocking from description and emotional beat
        blocking_injection = _derive_blocking(desc, beat, shot_type, chars)
        if blocking_injection:
            shot["nano_prompt"] = nano.rstrip(". ") + ". " + blocking_injection + "."
            flags.append(f"blocking:auto_injected:{blocking_injection[:40]}")
            shot["_blocking_enforced"] = True

    # Check for eye-line direction on character close-ups
    if shot_type in ["close_up", "medium_close", "reaction"] and chars:
        eyeline_words = ["eye-line", "eyeline", "gaze", "looking toward", "looks frame"]
        if not any(ew in nano.lower() for ew in eyeline_words):
            flags.append("blocking:missing_eyeline")

    # Check for screen direction on OTS shots
    if "ots" in shot_type or "over_the_shoulder" in shot_type:
        direction_words = ["frame-left", "frame-right", "foreground", "shoulder"]
        if not any(dw in nano.lower() for dw in direction_words):
            flags.append("blocking:missing_screen_direction")

    shot["_continuity_flags"] = flags
    return shot


def _derive_blocking(desc: str, beat: str, shot_type: str, chars: List[str]) -> str:
    """
    Derive physical blocking direction from description text and emotional beat.
    Returns a blocking phrase to inject, or empty string if can't determine.
    """
    char_name = chars[0] if chars else "character"

    # Check description for movement keywords
    if any(kw in desc for kw in ["enters", "walks in", "steps into", "comes through"]):
        return f"{char_name} enters through doorway, weight shifting forward, purposeful stride"

    if any(kw in desc for kw in ["grips", "gripping", "holds", "grasps", "clutch"]):
        return f"{char_name} grips railing with white-knuckle tension, body rigid"

    if any(kw in desc for kw in ["stares", "gazes", "looks at", "watches", "eyes on"]):
        return f"{char_name} stands motionless, gaze fixed, jaw set"

    if any(kw in desc for kw in ["confronts", "challenges", "demands", "insists"]):
        return f"{char_name} squares shoulders, chin lifted, stance planted"

    if any(kw in desc for kw in ["reacts", "absorbs", "processes", "realizes"]):
        return f"{char_name} jaw tightens, subtle shift in weight, controlled stillness"

    if any(kw in desc for kw in ["presents", "shows", "offers", "hands over"]):
        return f"{char_name} extends document forward, arm steady, eyes locked on recipient"

    # Emotional beat fallback
    if any(kw in beat for kw in ["tension", "confrontation", "anger", "defiance"]):
        return f"{char_name} stands rigid, fists clenched at sides, breathing controlled"

    if any(kw in beat for kw in ["grief", "sorrow", "loss", "mourning"]):
        return f"{char_name} shoulders slightly hunched, gaze downward, weight heavy"

    if any(kw in beat for kw in ["authority", "control", "power", "command"]):
        return f"{char_name} stands tall, posture erect, hands positioned with deliberate control"

    if any(kw in beat for kw in ["vulnerability", "doubt", "uncertainty"]):
        return f"{char_name} weight shifts slightly, hand finds surface for support"

    # Default: minimal but physical
    if shot_type in ["medium", "medium_close"]:
        return f"{char_name} holds position, subtle breathing visible, eyes active"

    return ""


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4: LIGHTING INJECTION INTO PROMPTS
# ═══════════════════════════════════════════════════════════════════════════════

def inject_scene_lighting(shot: Dict, lighting_lock: Dict) -> Dict:
    """
    Inject the scene's lighting lock into a shot's nano_prompt
    if the prompt doesn't already have adequate lighting description.
    Uses per-shot room override if this shot is in a different location.
    """
    nano = shot.get("nano_prompt", "") or ""
    shot_type = (shot.get("shot_type") or shot.get("type") or "").lower()
    sid = shot.get("shot_id", "")

    # Check for per-shot room override (e.g., cemetery opener in a foyer scene)
    per_shot_rooms = lighting_lock.get("per_shot_rooms", {})
    if sid in per_shot_rooms:
        override_room = per_shot_rooms[sid]
        profile = INTERIOR_LIGHTING_PROFILES.get(override_room, lighting_lock.get("profile", {}))
    else:
        profile = lighting_lock.get("profile", {})

    # Check if prompt already has lighting descriptors
    lighting_words = ["light", "shadow", "glow", "illuminat", "lamp", "chandelier",
                      "sconce", "window light", "backlight", "key light", "ambient",
                      "tungsten", "daylight", "overcast", "warm", "cool"]

    has_lighting = sum(1 for w in lighting_words if w in nano.lower())

    flags = shot.get("_continuity_flags", [])

    if has_lighting < 2:
        # Shot needs lighting injection
        light_phrase = lighting_lock.get("lighting_lock_phrase", "")

        # Adapt lighting phrase to shot type
        if shot_type in ["close_up", "medium_close", "reaction"]:
            # Close shots: emphasize facial lighting
            injection = f"{profile.get('key', '').split(',')[0]}, {profile.get('shadow', '').split(',')[0]}"
        elif shot_type in ["establishing", "wide", "closing", "drone"]:
            # Wide shots: emphasize mood and atmosphere
            injection = f"{profile.get('mood', '')}, {profile.get('color_temp', '').split(':')[0] if ':' in profile.get('color_temp','') else profile.get('color_temp','')}"
        else:
            # Medium shots: balanced
            injection = light_phrase

        if injection:
            shot["nano_prompt"] = nano.rstrip(". ") + ". " + injection + "."
            flags.append(f"lighting:scene_lock_injected:{lighting_lock.get('room_type','?')}")
            shot["_lighting_enforced"] = True

    shot["_continuity_flags"] = flags
    return shot


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5: MASTER ENFORCER — RUNS ALL 3 LAYERS
# ═══════════════════════════════════════════════════════════════════════════════

def enforce_scene_continuity(
    shots: List[Dict],
    story_bible_scene: Dict = None,
    cast_map: Dict = None,
) -> Tuple[List[Dict], Dict]:
    """
    Master enforcement function. Runs all 3 continuity layers on a scene's shots.

    Returns:
        (enriched_shots, report)

    Report contains:
        - lighting_lock: the resolved scene lighting profile
        - shots_enriched: count of shots that received injection
        - flags: all continuity flags across all shots
        - grade: A/B/C/F quality grade
    """
    if not shots:
        return shots, {"grade": "N/A", "reason": "no shots"}

    # LAYER 1: Resolve scene lighting
    lighting_lock = resolve_scene_lighting(shots, story_bible_scene)

    # LAYER 2-4: Per-shot enforcement
    total_flags = []
    lighting_enriched = 0
    framing_enriched = 0
    blocking_enriched = 0
    prev_shot = None

    for i, shot in enumerate(shots):
        shot["_continuity_flags"] = shot.get("_continuity_flags", [])

        # Layer 2: Lighting sync
        shot = inject_scene_lighting(shot, lighting_lock)
        if shot.get("_lighting_enforced"):
            lighting_enriched += 1

        # Layer 3: Framing rules
        shot = enforce_framing(shot)
        if shot.get("_framing_enforced"):
            framing_enriched += 1

        # Layer 4: Blocking audit
        shot = audit_blocking(shot, prev_shot)
        if shot.get("_blocking_enforced"):
            blocking_enriched += 1

        total_flags.extend(shot.get("_continuity_flags", []))
        prev_shot = shot

    # Grade the scene
    total_shots = len(shots)
    enrichment_ratio = (lighting_enriched + framing_enriched + blocking_enriched) / max(total_shots * 3, 1)

    # Lower enrichment = better (shots already had what they needed)
    if enrichment_ratio < 0.15:
        grade = "A"
    elif enrichment_ratio < 0.30:
        grade = "B"
    elif enrichment_ratio < 0.50:
        grade = "C"
    else:
        grade = "D"

    missing_eyelines = sum(1 for f in total_flags if "missing_eyeline" in f)
    missing_screen_dir = sum(1 for f in total_flags if "missing_screen_direction" in f)

    report = {
        "grade": grade,
        "lighting_lock": lighting_lock,
        "lighting_enriched": lighting_enriched,
        "framing_enriched": framing_enriched,
        "blocking_enriched": blocking_enriched,
        "total_shots": total_shots,
        "total_flags": len(total_flags),
        "flags": total_flags,
        "missing_eyelines": missing_eyelines,
        "missing_screen_directions": missing_screen_dir,
        "enrichment_ratio": round(enrichment_ratio, 3),
    }

    return shots, report


def generate_continuity_assessment(shots: List[Dict], report: Dict) -> str:
    """Generate a human-readable assessment of scene continuity quality."""
    lines = []
    lines.append(f"=== SCENE CONTINUITY ASSESSMENT ===")
    lines.append(f"Grade: {report['grade']} | Enrichment Ratio: {report['enrichment_ratio']}")
    lines.append(f"Shots: {report['total_shots']} | Flags: {report['total_flags']}")
    lines.append(f"")
    lines.append(f"LIGHTING: {report['lighting_enriched']}/{report['total_shots']} shots needed lighting injection")
    lines.append(f"  Lock: {report['lighting_lock'].get('room_type', '?')} → {report['lighting_lock'].get('lighting_lock_phrase', '?')[:80]}")
    lines.append(f"FRAMING: {report['framing_enriched']}/{report['total_shots']} shots needed framing correction")
    lines.append(f"BLOCKING: {report['blocking_enriched']}/{report['total_shots']} shots needed blocking injection")
    lines.append(f"  Missing eye-lines: {report['missing_eyelines']}")
    lines.append(f"  Missing screen directions: {report['missing_screen_directions']}")
    lines.append(f"")

    # Per-shot detail
    for s in shots:
        sid = s.get("shot_id", "?")
        flags = s.get("_continuity_flags", [])
        markers = []
        if s.get("_lighting_enforced"): markers.append("L")
        if s.get("_framing_enforced"): markers.append("F")
        if s.get("_blocking_enforced"): markers.append("B")

        if markers or flags:
            flag_str = ", ".join(flags[:3])
            lines.append(f"  {sid}: enriched=[{','.join(markers)}] flags=[{flag_str}]")

    return "\n".join(lines)
