"""
scene_transition_manager.py — V36.1 Scene Opener + Cross-Scene Entry Context

Pre-designates each scene's opening strategy from story bible intelligence:
  COLD_OPEN       — no warmup, in medias res, action already running
  ACTION_OPENER   — kinetic character entry, motion from frame one
  DIALOGUE_OPENER — mid-conversation, voice precedes image
  BROLL_OPENER    — environment is protagonist, world first
  REVELATION_OPENER — space holds a secret, discovery imminent
  ATMOSPHERE_OPENER — tone before character, mood establishes the world

Also extracts cross-scene exit state from previous scene's last beat and
injects it as entry context on the first character shot (CHAIN_ANCHOR) of
the incoming scene.

Wire point: run_scene() → after inject_tone_shots(), before Wire D.
Injection target: E01/E02/E03 get _opener_prefix. M01 gets _scene_entry_context.
compile_nano() reads both fields — they become part of the spatial header and
beat atmosphere channels.

Authority: ADVISORY + WRITE to shot fields only. Never mutates story bible.
Non-blocking: all errors are caught, generation proceeds without context.
"""

from __future__ import annotations
import re
from typing import Optional

# ═══ OPENER TYPE CATALOGUE ═══════════════════════════════════════════════════

OPENER_PROFILES = {
    "COLD_OPEN": {
        "e01_prefix":  "IN MEDIAS RES — NO ESTABLISHING WARMUP. Action already running.",
        "e02_prefix":  "SPACE ALREADY ALIVE — no slow reveal, room is mid-event.",
        "e03_prefix":  "DETAIL CUTS IN FAST — no gentle approach.",
        "m01_prefix":  "MID-ACTION ENTRY — character already in motion, no pause.",
        "energy":      "high",
        "e_weight":    "light",     # E-shots brief, action carries the scene
        "description": "Slams into action without setup. Time is already running."
    },
    "ACTION_OPENER": {
        "e01_prefix":  "SPACE PREPARES FOR ENTRY — architecture braced for arrival.",
        "e02_prefix":  "ROOM POISED — emptiness charged with imminent movement.",
        "e03_prefix":  "THRESHOLD DETAIL — the crossing point, worn by use.",
        "m01_prefix":  "CHARACTER IN MOTION — kinetic entry, body already committed.",
        "energy":      "kinetic",
        "e_weight":    "medium",
        "description": "Opens with physical action. Character enters or is already moving."
    },
    "DIALOGUE_OPENER": {
        "e01_prefix":  "SOUND PRECEDES IMAGE — voice already audible before the cut.",
        "e02_prefix":  "ROOM FRAMES THE CONVERSATION — architecture as witness.",
        "e03_prefix":  "PROP OF EXCHANGE — object that conversation revolves around.",
        "m01_prefix":  "MID-CONVERSATION — scene opens inside the exchange, no preamble.",
        "energy":      "medium",
        "e_weight":    "medium",
        "description": "Opens mid-speech. Dialogue is the first thing the audience encounters."
    },
    "BROLL_OPENER": {
        "e01_prefix":  "WORLD ESTABLISHES ITSELF — environment is the protagonist here.",
        "e02_prefix":  "ROOM BREATHES ALONE — character has not yet arrived, space owns the frame.",
        "e03_prefix":  "TEXTURE OF PLACE — surface detail that defines this world.",
        "m01_prefix":  "CHARACTER ENTERS A WORLD ALREADY KNOWN — the room was first.",
        "energy":      "slow",
        "e_weight":    "heavy",    # E-shots carry maximum narrative weight
        "description": "Opens on environment, no character. World is established before story enters."
    },
    "REVELATION_OPENER": {
        "e01_prefix":  "SPACE HOLDS A SECRET — architecture conceals what is about to surface.",
        "e02_prefix":  "ROOM BEFORE THE DISCOVERY — stillness charged with implication.",
        "e03_prefix":  "THE OBJECT THAT CHANGES EVERYTHING — close on the reveal.",
        "m01_prefix":  "CHARACTER ON THE EDGE OF KNOWING — one step from the revelation.",
        "energy":      "medium_rising",
        "e_weight":    "heavy",
        "description": "Opens with something about to be discovered. Tension built into the frame."
    },
    "ATMOSPHERE_OPENER": {
        "e01_prefix":  "TONE BEFORE CHARACTER — mood is the first actor on screen.",
        "e02_prefix":  "MOOD FIRST — lighting and texture establish the emotional key.",
        "e03_prefix":  "SENSORY ANCHOR — the detail that names the atmosphere.",
        "m01_prefix":  "CHARACTER ENTERS THE MOOD — arrives into an already-established tone.",
        "energy":      "slow",
        "e_weight":    "heavy",
        "description": "Opens with atmosphere. Emotional register set before any character appears."
    },
}

# ═══ KEYWORD CLASSIFIERS ═════════════════════════════════════════════════════

_ACTION_KEYWORDS = {
    "enters", "enter", "storms", "rushes", "runs", "paces", "strides",
    "descends", "ascends", "climbs", "walks", "moves", "crosses", "bursts",
    "slams", "pushes", "pulls", "grabs", "reaches", "swings", "turns",
    "spins", "lunges", "charges", "dashes", "bolts"
}

_DIALOGUE_KEYWORDS = {
    "says", "speaks", "tells", "asks", "replies", "shouts", "whispers",
    "calls", "announces", "reads aloud", "on the phone", "arguing", "debates",
    "confronts", "demands", "insists", "answers", "interrupts", "orders"
}

_REVELATION_KEYWORDS = {
    "finds", "discovers", "reveals", "uncovers", "exposes", "notices",
    "realises", "realizes", "sees", "spots", "catches", "recognizes",
    "opens", "unlocks", "pulls out", "extracts", "unearths"
}

_ATMOSPHERE_KEYWORDS = {
    "sits", "stands", "waits", "stares", "gazes", "watches", "broods",
    "lingers", "pauses", "surveys", "contemplates", "observes", "studies",
    "looks at", "examines", "feels", "touches gently"
}

_BROLL_KEYWORDS = {
    "photographs", "films", "documents", "records", "surveys the space",
    "takes in", "scans the room", "moves through the space", "explores"
}

_COLD_KEYWORDS = {
    "already", "mid-", "in the middle of", "continues", "still on",
    "hasn't stopped", "ongoing", "picks up", "resumes"
}

# ═══ CLASSIFIER ══════════════════════════════════════════════════════════════

def classify_scene_opener(sb_scene: dict, prev_sb_scene: Optional[dict] = None) -> str:
    """
    Classify a scene's opener type from story bible intelligence.
    Returns one of the OPENER_PROFILES keys.
    Priority:
      1. Explicit `opening_type` field in story bible scene
      2. First beat action/dialogue keyword analysis
      3. Character count + entry pattern
      4. Default: ACTION_OPENER
    """
    # 1. Explicit override in story bible
    explicit = (sb_scene.get("opening_type") or sb_scene.get("opener_type") or "").strip()
    if explicit:
        key = explicit.upper().replace(" ", "_")
        if key in OPENER_PROFILES:
            return key

    beats = sb_scene.get("beats") or []
    first_beat = beats[0] if beats else {}
    first_action = ""
    if isinstance(first_beat, dict):
        first_action = (first_beat.get("action") or first_beat.get("description") or "").lower()
        first_dialogue = (first_beat.get("dialogue") or "").lower()
    elif isinstance(first_beat, str):
        first_action = first_beat.lower()
        first_dialogue = ""
    else:
        first_action = ""
        first_dialogue = ""

    # 2. Cold open detection (explicit "already in progress" language)
    for kw in _COLD_KEYWORDS:
        if kw in first_action:
            return "COLD_OPEN"

    # 3. Phone call / mid-conversation is always DIALOGUE_OPENER
    if "on the phone" in first_action or "phone" in first_action and "arguing" in first_action:
        return "DIALOGUE_OPENER"

    # 4. First beat has dialogue text → DIALOGUE_OPENER
    # SOLO SCENE GUARD: If the scene has ≤1 character, the dialogue is self-directed
    # (narration, muttering, reading aloud) — NOT a mid-conversation cold-open.
    # Self-directed dialogue → DISCOVERY_OPENER or ACTION_OPENER, not DIALOGUE_OPENER.
    _scene_chars = sb_scene.get("characters") or []
    _is_solo_scene = len(_scene_chars) <= 1
    if first_dialogue and len(first_dialogue) > 10:
        if _is_solo_scene:
            # Solo scene: self-directed dialogue — classify as DISCOVERY_OPENER so E-shots are kept
            pass  # fall through to later rules
        else:
            return "DIALOGUE_OPENER"

    # 5. Dialogue action keywords
    for kw in _DIALOGUE_KEYWORDS:
        if kw in first_action:
            return "DIALOGUE_OPENER"

    # 6. Revelation keywords → REVELATION_OPENER
    for kw in _REVELATION_KEYWORDS:
        if kw in first_action:
            return "REVELATION_OPENER"

    # 7. B-roll/documentation pattern → BROLL_OPENER
    for kw in _BROLL_KEYWORDS:
        if kw in first_action:
            return "BROLL_OPENER"

    # 8. Atmosphere keywords → ATMOSPHERE_OPENER
    atm_hits = sum(1 for kw in _ATMOSPHERE_KEYWORDS if kw in first_action)
    action_hits = sum(1 for kw in _ACTION_KEYWORDS if kw in first_action)
    if atm_hits > action_hits and atm_hits >= 1:
        return "ATMOSPHERE_OPENER"

    # 9. Action keywords → ACTION_OPENER
    if action_hits >= 1:
        return "ACTION_OPENER"

    # 10. No beats or empty → BROLL_OPENER (environment carries the scene)
    if not beats or not first_action:
        return "BROLL_OPENER"

    return "ACTION_OPENER"


# ═══ CROSS-SCENE EXIT STATE ═══════════════════════════════════════════════════

_EMOTION_KEYWORDS = {
    "tension":     ["threat", "threatens", "standoff", "standground", "refuses", "insists", "confronts", "demands"],
    "revelation":  ["finds", "discovers", "reveals", "uncovers", "journal", "letter", "secret", "realizes"],
    "grief":       ["grief", "portrait", "refuses to let go", "guilt", "loss", "mourns", "stares"],
    "urgency":     ["paces", "phone", "arguing", "proceed", "auction", "deadline", "regardless"],
    "conspiracy":  ["listening", "floorboard", "watching", "hallway empty", "someone was"],
    "isolation":   ["alone", "empty", "silent", "watches leave", "looks up", "solitude"],
    "unease":      ["shadow", "menace", "implied threat", "creaks", "heard", "unseen"],
    "resolution":  ["rises", "turns", "walks away", "leaves", "exits", "moves on"],
}

def extract_exit_state(sb_scene: dict) -> dict:
    """
    Extract the emotional and spatial state at the END of a scene.
    Used to inform the opening of the following scene.
    Returns: {emotion, beat_action, characters, location, has_dialogue}
    """
    beats = sb_scene.get("beats") or []
    last_beat = beats[-1] if beats else {}

    if isinstance(last_beat, dict):
        last_action = (last_beat.get("action") or last_beat.get("description") or "").strip()
        last_dialogue = (last_beat.get("dialogue") or "").strip()
    elif isinstance(last_beat, str):
        last_action = last_beat.strip()
        last_dialogue = ""
    else:
        last_action = ""
        last_dialogue = ""

    # Detect exit emotion
    exit_emotion = "neutral"
    action_lower = last_action.lower()
    for emotion, keywords in _EMOTION_KEYWORDS.items():
        if any(kw in action_lower for kw in keywords):
            exit_emotion = emotion
            break

    return {
        "emotion":        exit_emotion,
        "beat_action":    last_action,
        "has_dialogue":   bool(last_dialogue),
        "last_line":      last_dialogue[:120] if last_dialogue else "",
        "location":       sb_scene.get("location", ""),
        "scene_id":       str(sb_scene.get("scene_id") or sb_scene.get("id") or ""),
    }


# ═══ ENTRY CONTEXT BUILDER ═══════════════════════════════════════════════════

_ENTRY_CONTEXT_TEMPLATES = {
    # (exit_emotion, opener_type) → entry context prose for M01 spatial header
    ("tension",     "DIALOGUE_OPENER"):  "Scene enters LIVE — previous tension unresolved, characters carry it in.",
    ("tension",     "ACTION_OPENER"):   "TENSION CARRIED IN — body posture shows the weight of what came before.",
    ("tension",     "COLD_OPEN"):       "NO DECOMPRESSION — tension from previous scene still active on entry.",
    ("revelation",  "DIALOGUE_OPENER"): "REVELATION ENTERS THE ROOM — character brings newly discovered knowledge.",
    ("revelation",  "ACTION_OPENER"):   "DISCOVERY IN MOTION — character moving with the urgency of what they found.",
    ("revelation",  "BROLL_OPENER"):    "SPACE BEFORE THE REVELATION — room doesn't yet know what character carries.",
    ("grief",       "ATMOSPHERE_OPENER"): "GRIEF SATURATES THE FRAME — previous loss still visible in body and face.",
    ("grief",       "ACTION_OPENER"):   "GRIEF IN MOTION — moving through it, not past it.",
    ("urgency",     "DIALOGUE_OPENER"): "MID-URGENCY ENTRY — no time for preamble, problem is already active.",
    ("urgency",     "COLD_OPEN"):       "CRISIS CONTINUES — urgency from previous scene carries straight through.",
    ("conspiracy",  "DIALOGUE_OPENER"): "PARANOIA ENTERS — someone may be listening, every word now weighted.",
    ("conspiracy",  "ATMOSPHERE_OPENER"): "WATCHED FEELING — space feels observed even when empty.",
    ("isolation",   "ATMOSPHERE_OPENER"): "SOLITUDE CONTINUES — character carries the quiet of the previous scene.",
    ("isolation",   "BROLL_OPENER"):    "EMPTY ROOMS MIRROR EACH OTHER — one isolation echoes the last.",
    ("unease",      "ATMOSPHERE_OPENER"): "UNEASE PERSISTS — the wrongness from previous scene is still present.",
    ("resolution",  "ACTION_OPENER"):   "RESOLUTION INTO NEXT PROBLEM — one thing settled, another begins.",
    ("neutral",     "ACTION_OPENER"):   "",   # no cross-scene note needed
    ("neutral",     "DIALOGUE_OPENER"): "",
}

def build_entry_context(exit_state: dict, opener_type: str) -> str:
    """Build the cross-scene entry context string for M01's spatial header."""
    emotion = exit_state.get("emotion", "neutral")
    key = (emotion, opener_type)
    context = _ENTRY_CONTEXT_TEMPLATES.get(key, "")

    # If no exact match, build a generic one from the emotion
    if not context and emotion not in ("neutral",):
        context = f"Previous scene exit: {emotion.upper()} — character carries this emotional state into the frame."

    return context


# ═══ SHOT INJECTION ══════════════════════════════════════════════════════════

def inject_scene_entry(
    shots: list,
    scene_id: str,
    sb_scene: dict,
    prev_sb_scene: Optional[dict] = None,
    verbose: bool = True
) -> list:
    """
    Main entry point. Called by run_scene() after inject_tone_shots().

    Classifies opener type → writes _scene_opener_type + _opener_prefix
    onto E01/E02/E03/M01 of this scene.

    If prev_sb_scene is provided, also extracts cross-scene exit state and
    writes _scene_entry_context onto M01.

    Returns: the same shots list (mutated in-place, also returned for clarity).
    Non-blocking: any error → returns shots unchanged.
    """
    try:
        opener_type = classify_scene_opener(sb_scene, prev_sb_scene)
        profile = OPENER_PROFILES[opener_type]

        exit_state: Optional[dict] = None
        entry_context = ""
        if prev_sb_scene and isinstance(prev_sb_scene, dict):
            exit_state = extract_exit_state(prev_sb_scene)
            entry_context = build_entry_context(exit_state, opener_type)

        prefix_map = {
            "E01": profile["e01_prefix"],
            "E02": profile["e02_prefix"],
            "E03": profile["e03_prefix"],
            "M01": profile["m01_prefix"],
        }

        # Identify which shot positions map to which E/M labels
        scene_prefix = scene_id.zfill(3)  # "006"
        e_count = 0
        m_count = 0

        for shot in shots:
            sid = shot.get("shot_id", "")
            if not sid.startswith(scene_prefix + "_"):
                continue

            slot = sid.split("_", 1)[-1]  # "E01", "M01", etc.

            # Classify as E or M series
            if shot.get("_is_broll") or shot.get("_no_char_ref") or slot.startswith("E"):
                e_count += 1
                slot_key = f"E{str(e_count).zfill(2)}"
                prefix = prefix_map.get(slot_key, profile["e01_prefix"])

                shot["_scene_opener_type"]  = opener_type
                shot["_opener_prefix"]      = prefix
                shot["_opener_energy"]      = profile["energy"]
                shot["_opener_e_weight"]    = profile["e_weight"]

            elif slot.startswith("M") or (not shot.get("_is_broll") and shot.get("characters")):
                m_count += 1
                if m_count == 1:
                    # M01 = CHAIN_ANCHOR — gets full entry context
                    shot["_scene_opener_type"]    = opener_type
                    shot["_opener_prefix"]        = profile["m01_prefix"]
                    shot["_opener_energy"]        = profile["energy"]
                    shot["_scene_entry_context"]  = entry_context
                    if exit_state:
                        shot["_prev_scene_exit_emotion"] = exit_state["emotion"]
                        shot["_prev_scene_exit_action"]  = exit_state["beat_action"][:100]
                else:
                    # M02+ — inherit opener type only (no prefix, they're mid-scene)
                    shot["_scene_opener_type"] = opener_type

        if verbose:
            prev_sid = str(prev_sb_scene.get("scene_id") or prev_sb_scene.get("id") or "?") if prev_sb_scene else "none"
            emotion_str = f" | prev_exit={exit_state['emotion']}" if exit_state else ""
            print(f"  [OPENER] Scene {scene_id}: {opener_type} (prev={prev_sid}{emotion_str})")
            if entry_context:
                print(f"  [ENTRY]  M01 context: {entry_context[:80]}...")

        return shots

    except Exception as e:
        if verbose:
            print(f"  [OPENER] WARNING: scene_transition_manager failed ({e}) — proceeding without entry context")
        return shots


# ═══ STORY BIBLE SCENE LOOKUP ════════════════════════════════════════════════

def get_prev_sb_scene(sb: dict, scene_id: str) -> Optional[dict]:
    """
    Given a story bible and a scene_id string, return the scene that
    immediately precedes it (by scene order, not by ID number).
    Returns None if scene_id is the first scene or not found.
    """
    scenes = sb.get("scenes") or []
    for i, sc in enumerate(scenes):
        sid = str(sc.get("scene_id") or sc.get("id") or "")
        # Normalise: "006" == "6"
        if sid.lstrip("0") == scene_id.lstrip("0") or sid == scene_id:
            if i == 0:
                return None
            return scenes[i - 1]
    return None


# ═══ STANDALONE DIAGNOSTIC ════════════════════════════════════════════════════

if __name__ == "__main__":
    import json, sys
    from pathlib import Path

    project = sys.argv[1] if len(sys.argv) > 1 else "victorian_shadows_ep1"
    pdir = Path("pipeline_outputs") / project
    sb_path = pdir / "story_bible.json"
    if not sb_path.exists():
        print(f"No story bible at {sb_path}"); sys.exit(1)

    sb = json.loads(sb_path.read_text())
    scenes = sb.get("scenes", [])

    print(f"\n=== SCENE OPENER ANALYSIS — {project} ===\n")
    for i, sc in enumerate(scenes):
        sid = str(sc.get("scene_id") or sc.get("id") or str(i + 1))
        prev = scenes[i - 1] if i > 0 else None
        opener = classify_scene_opener(sc, prev)
        profile = OPENER_PROFILES[opener]

        exit_info = ""
        if prev:
            es = extract_exit_state(prev)
            ctx = build_entry_context(es, opener)
            exit_info = f"  prev_exit={es['emotion']}"
            if ctx:
                exit_info += f"\n     entry_ctx: {ctx[:70]}..."

        print(f"  Scene {sid:>3}: {opener:<22} | energy={profile['energy']:<14} | e_weight={profile['e_weight']}{exit_info}")

    print()
