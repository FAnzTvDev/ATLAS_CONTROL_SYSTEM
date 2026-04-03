#!/usr/bin/env python3
"""
chain_arc_intelligence.py — V36.5 Three-Act Chain Intelligence

Every shot in a scene occupies a position in the emotional arc:
  ESTABLISH  — Opening. Declares room, identity, tone. Chain anchor.
  ESCALATE   — Middle. Carries what opening declared, raises stakes.
  PIVOT      — Middle turning point. Emotional shift or revelation.
  RESOLVE    — Ending. Closes the emotional beat, releases room lock.

This module computes arc_position per shot from beat structure,
and provides chain-aware context for the runner:

  - Opening shots get full declaration (Room DNA, identity, baseline)
  - Middle shots get carry directives (maintain, escalate)
  - Ending shots get release signals (scene_close=True, outgoing hint)

The runner reads these to adjust:
  1. Reframe prompt intensity (carry vs release)
  2. Kling video prompt emotional modifiers
  3. Scene boundary behavior (release room DNA, clean slate for next)

Authority: ADVISORY (QA layer). Controller reads, decides, acts.
"""

from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Any


# ── ARC POSITION CONSTANTS ──────────────────────────────────────────
ARC_ESTABLISH = "ESTABLISH"
ARC_ESCALATE  = "ESCALATE"
ARC_PIVOT     = "PIVOT"
ARC_RESOLVE   = "RESOLVE"

# Emotional escalation keywords — used to detect pivot beats
PIVOT_KEYWORDS = {
    "reveal", "reveals", "discover", "discovers", "bombshell",
    "contradict", "contradicts", "confronts", "confession",
    "truth", "secret", "shock", "turning", "twist", "betray",
    "betrays", "collapse", "breaks", "sudden", "unexpected",
}

# Escalation keywords — emotional temperature rising
ESCALATE_KEYWORDS = {
    "tension", "urgency", "pressure", "demand", "insist",
    "argue", "conflict", "stakes", "escalat", "intensif",
    "confront", "challenge", "resist", "refuse", "anger",
}


def compute_arc_positions(shots: list[dict], story_bible_scene: dict | None = None) -> list[dict]:
    """
    Compute arc_position for each shot in a scene.

    Args:
        shots: List of shot dicts from shot_plan.json (same scene)
        story_bible_scene: Optional story bible scene dict with beats

    Returns:
        Same shots list with _arc_position, _arc_index, _scene_close,
        _arc_carry_directive, and _arc_release fields added.
    """
    if not shots:
        return shots

    n = len(shots)
    total_beats = _count_unique_beats(shots)

    for i, shot in enumerate(shots):
        beat_idx = shot.get("_beat_index", i)
        beat_atm = (shot.get("_beat_atmosphere") or "").lower()
        beat_act = (shot.get("_beat_action") or "").lower()
        beat_dlg = (shot.get("_beat_dialogue") or "").lower()
        combined_text = f"{beat_atm} {beat_act} {beat_dlg}"

        is_first = (i == 0)
        is_last = (i == n - 1)
        is_second_last = (i == n - 2) and n > 2

        # ── Determine arc position ──────────────────────────
        if is_first:
            arc = ARC_ESTABLISH
        elif is_last:
            arc = ARC_RESOLVE
        elif _has_pivot_signal(combined_text):
            arc = ARC_PIVOT
        elif _has_escalation_signal(combined_text):
            arc = ARC_ESCALATE
        elif beat_idx is not None and total_beats > 0:
            # Position-based fallback: map beat index to arc
            progress = beat_idx / max(total_beats - 1, 1)
            if progress < 0.25:
                arc = ARC_ESTABLISH
            elif progress < 0.7:
                arc = ARC_ESCALATE
            else:
                arc = ARC_PIVOT
        else:
            arc = ARC_ESCALATE  # Default middle shots

        # Override: if second-to-last and last beat has pivot, this is escalate
        if is_second_last and arc == ARC_RESOLVE:
            arc = ARC_ESCALATE

        # ── Write arc metadata ──────────────────────────────
        shot["_arc_position"] = arc
        shot["_arc_index"] = i  # 0-based position in scene
        shot["_arc_total"] = n
        shot["_scene_close"] = is_last

        # ── Carry directive (what the chain must do) ────────
        if arc == ARC_ESTABLISH:
            shot["_arc_carry_directive"] = "DECLARE: Lock room DNA, identity, lighting baseline. This frame sets the law."
        elif arc == ARC_ESCALATE:
            shot["_arc_carry_directive"] = "CARRY: Maintain room architecture from opening. Escalate emotional intensity one beat."
        elif arc == ARC_PIVOT:
            shot["_arc_carry_directive"] = "CARRY+SHIFT: Room holds but emotional tone shifts. This is the turning point."
        elif arc == ARC_RESOLVE:
            shot["_arc_carry_directive"] = "RESOLVE: Room holds for final shot. Close emotional arc. Prepare for scene release."

        # ── Release signal (for scene boundary) ─────────────
        if is_last:
            shot["_arc_release"] = {
                "scene_close": True,
                "release_room_dna": True,
                "outgoing_hint": _build_outgoing_hint(shot, story_bible_scene),
            }
        else:
            shot["_arc_release"] = {"scene_close": False}

    return shots


def get_chain_modifier(arc_position: str, group_index: int) -> dict:
    """
    Get chain-aware modifiers for the runner based on arc position.

    Returns dict with:
        reframe_strength: float (0.0-1.0) how strongly to anchor to location master
        emotional_modifier: str to append to Kling prompt
        room_lock_active: bool whether Room DNA should be enforced
    """
    modifiers = {
        ARC_ESTABLISH: {
            "reframe_strength": 1.0,
            "emotional_modifier": "",  # Opening sets tone, no modifier needed
            "room_lock_active": True,
            "prompt_suffix": "",
        },
        ARC_ESCALATE: {
            "reframe_strength": 0.9,  # Still strong room anchor
            "emotional_modifier": "Intensity builds.",
            "room_lock_active": True,
            "prompt_suffix": "Emotional energy rising from previous beat.",
        },
        ARC_PIVOT: {
            "reframe_strength": 0.85,  # Room holds but allows slight atmosphere shift
            "emotional_modifier": "Emotional turning point.",
            "room_lock_active": True,
            "prompt_suffix": "Key revelation or shift. Stakes change visibly.",
        },
        ARC_RESOLVE: {
            "reframe_strength": 0.8,  # Room still present but focus shifts to characters
            "emotional_modifier": "Scene resolving.",
            "room_lock_active": True,  # Room holds even at close
            "prompt_suffix": "Final emotional beat. Scene closing.",
        },
    }
    return modifiers.get(arc_position, modifiers[ARC_ESCALATE])


def compute_blocking_carry(shots: list[dict]) -> list[dict]:
    """
    V36.5.1: Blocking State Carry — compute the END spatial state of each
    shot and propagate it as the START state of the next shot.

    Without this, the chain reframe knows ROOM DNA and IDENTITY but nothing
    about WHERE characters are relative to each other. The reframe invents
    new blocking from scratch, causing spatial jumps.

    This function writes:
      _blocking_carry: str — "Character A is [position]. Character B is [position]."
      _blocking_end_state: str — What the spatial arrangement is at the END of this shot
    """
    if not shots:
        return shots

    for i, shot in enumerate(shots):
        chars = shot.get("characters") or []
        nchars = len(chars)
        body = shot.get("_body_direction", "")
        action = (shot.get("_beat_action") or "").lower()
        stype = (shot.get("shot_type") or "").lower()
        mv = (shot.get("_movement_state") or "static").lower()

        # ── Compute this shot's END blocking state ──────────
        if nchars == 0:
            end_state = "empty room, no characters"
        elif nchars == 1:
            char_name = chars[0].split()[-1] if chars else "character"
            if "enters" in action or "stepping" in body.lower():
                end_state = f"{char_name} has arrived in the room, standing"
            elif "exits" in action or "leaves" in action:
                end_state = f"{char_name} is leaving or near exit"
            else:
                end_state = f"{char_name} present, {_compact_position(stype, body)}"
        else:
            # Multi-character — derive spatial relationship
            names = [c.split()[-1] for c in chars[:2]]
            if "ots" in stype:
                end_state = f"{names[0]} and {names[1]} face each other in conversation, OTS framing"
            elif "two_shot" in stype:
                end_state = f"{names[0]} FRAME-LEFT and {names[1]} FRAME-RIGHT, facing each other"
            elif "enters" in action:
                # Someone just entered — they're now WITH the other person
                entering = _who_enters(action, names)
                other = names[1] if entering == names[0] else names[0]
                end_state = f"{entering} has arrived, now standing opposite {other} at conversation distance"
            else:
                end_state = f"{names[0]} and {names[1]} in scene together, {_compact_position(stype, body)}"

        shot["_blocking_end_state"] = end_state

        # ── Propagate to NEXT shot as carry ─────────────────
        if i + 1 < len(shots):
            next_shot = shots[i + 1]
            next_chars = next_shot.get("characters") or []
            next_nchars = len(next_chars)

            # Build carry instruction
            if nchars == 0 and next_nchars > 0:
                # E-shot → character shot: characters are ENTERING
                carry = f"Characters now visible in the room. {end_state} transitioning to character shot."
            elif mv == "walking" and (next_shot.get("_movement_state") or "static") == "static":
                # Movement → static: character has ARRIVED
                carry = f"Movement complete. {end_state}. Characters now settled in position."
            elif nchars > 0 and next_nchars > 0:
                # Character → character: carry spatial arrangement
                carry = f"Continuing from: {end_state}."
            else:
                carry = end_state

            next_shot["_blocking_carry"] = carry

    return shots


def get_blocking_carry(shot: dict) -> str | None:
    """Get the blocking carry text for a shot (set by previous shot)."""
    return shot.get("_blocking_carry")


def _compact_position(shot_type: str, body_dir: str) -> str:
    """Derive a compact position description from shot type + body direction."""
    if "close" in shot_type:
        return "tight framing on face"
    if "wide" in shot_type or "closing" in shot_type:
        return "visible in full room context"
    if "medium" in shot_type:
        return "waist-up visible"
    if body_dir and body_dir not in ("present, natural micro-movements", "neutral, present in scene"):
        return body_dir[:50]
    return "standing in scene"


def _who_enters(action: str, names: list[str]) -> str:
    """Determine which character is entering from the action text."""
    action_lower = action.lower()
    for n in names:
        if n.lower() in action_lower:
            # Check if this name is near "enters" or "entering"
            idx_name = action_lower.find(n.lower())
            idx_enters = action_lower.find("enters")
            if idx_enters == -1:
                idx_enters = action_lower.find("enter")
            if idx_enters != -1 and abs(idx_name - idx_enters) < 30:
                return n
    return names[0]  # default to first character


def should_release_room_dna(shot: dict) -> bool:
    """Check if this shot signals room DNA release for next scene."""
    release = shot.get("_arc_release", {})
    return release.get("release_room_dna", False)


def get_outgoing_hint(shot: dict) -> str | None:
    """Get the outgoing hint for scene transition."""
    release = shot.get("_arc_release", {})
    return release.get("outgoing_hint")


def enrich_shots_with_arc(
    shots: list[dict],
    story_bible: dict | None = None,
    scene_id: str | None = None,
    genre_id: str | None = None,
) -> list[dict]:
    """
    High-level entry point: enrich all shots in a scene with arc positions.

    If story_bible is provided, extracts the scene's beat data for richer analysis.
    If genre_id is provided, adds genre-specific display labels alongside the
    canonical _arc_position field (which is NEVER modified — labels are additive).
    """
    sb_scene = None
    if story_bible and scene_id:
        for sc in story_bible.get("scenes", []):
            sid = sc.get("scene_id") or sc.get("scene_number") or ""
            if str(sid).zfill(3) == str(scene_id).zfill(3):
                sb_scene = sc
                break

    shots = compute_arc_positions(shots, sb_scene)
    shots = compute_blocking_carry(shots)

    # ── Genre layer (ADDITIVE — does not modify _arc_position) ──────────
    if genre_id:
        shots = apply_genre_arc_labels(shots, genre_id)

    return shots


# ── INTERNAL HELPERS ────────────────────────────────────────────────

def _count_unique_beats(shots: list[dict]) -> int:
    """Count unique beat indices across shots."""
    indices = set()
    for s in shots:
        bi = s.get("_beat_index")
        if bi is not None:
            indices.add(bi)
    return len(indices) if indices else len(shots)


def _has_pivot_signal(text: str) -> bool:
    """Check if text contains pivot/revelation keywords."""
    words = set(text.lower().split())
    return bool(words & PIVOT_KEYWORDS)


def _has_escalation_signal(text: str) -> bool:
    """Check if text contains escalation keywords."""
    text_lower = text.lower()
    return any(kw in text_lower for kw in ESCALATE_KEYWORDS)


def _build_outgoing_hint(shot: dict, sb_scene: dict | None) -> str:
    """Build a hint for the next scene's chain anchor about what world it's entering."""
    parts = []

    # What emotion are we leaving with?
    atm = shot.get("_beat_atmosphere", "")
    if atm:
        parts.append(f"outgoing_emotion: {atm}")

    # What was the last action?
    act = shot.get("_beat_action", "")
    if act:
        parts.append(f"last_action: {act[:80]}")

    # Scene location (so next scene knows to NOT carry this room)
    if sb_scene:
        loc = sb_scene.get("location", "")
        if loc:
            parts.append(f"releasing_location: {loc}")

    return " | ".join(parts) if parts else "scene_close"


# ═══════════════════════════════════════════════════════════════════
# GENRE-AWARE ARC LAYER (V37.0 FANZ Universe Extension)
#
# THE CONTRACT (from user directive 2026-03-29):
#   - _arc_position field is IMMUTABLE (ESTABLISH/ESCALATE/PIVOT/RESOLVE)
#   - Genre profiles add _arc_display_label and _arc_genre_directive ONLY
#   - Existing drama pipeline behaviour is UNCHANGED
#   - All 4 base arc positions map to genre-specific terminology
#   - If genre_id is unknown/None → silent fallback to drama defaults
# ═══════════════════════════════════════════════════════════════════

# ── GENRE PIVOT / ESCALATION KEYWORD SETS ───────────────────────────

_FIGHT_PIVOT_KEYWORDS = {
    "knockdown", "ko", "knockout", "tko", "stumbles", "stagger",
    "comeback", "reversal", "caught", "clinch breaks", "point deducted",
    "standing eight", "momentum shifts", "counter", "submission attempt",
}
_FIGHT_ESCALATE_KEYWORDS = {
    "exchange", "combination", "pressure", "drives back", "cut", "blood",
    "rounds up", "corner", "jab", "cross", "uppercut", "hook", "body shot",
    "clinch", "ref separates", "crowd rises",
}

_SPORTS_PIVOT_KEYWORDS = {
    "touchdown", "goal", "score changes", "interception", "turnover",
    "overtime", "penalty", "red card", "foul called", "challenge", "replay",
    "overturned", "comeback", "tie broken", "lead changes",
}
_SPORTS_ESCALATE_KEYWORDS = {
    "drive", "possession", "quarter", "half", "set piece", "corner kick",
    "free throw", "field goal attempt", "crowd growing", "momentum",
    "press", "attack", "defense holds", "time running",
}

_COMEDY_PIVOT_KEYWORDS = {
    "but wait", "except", "turns out", "actually", "twist", "plot twist",
    "callback", "running gag", "it gets worse", "the thing is", "awkward",
    "silence", "stare", "double take", "timing beat",
}
_COMEDY_ESCALATE_KEYWORDS = {
    "building", "spiraling", "escalat", "louder", "everyone notices",
    "compounding", "adding to", "making it worse", "can't stop",
    "look on", "reaction shot", "audience reaction",
}

_PODCAST_PIVOT_KEYWORDS = {
    "actually", "the key insight", "what surprised me", "turns out",
    "but here's the thing", "the real question", "disagree", "pushback",
    "revelation", "data shows", "the twist", "nobody talks about",
}
_PODCAST_ESCALATE_KEYWORDS = {
    "building on that", "following up", "and then", "furthermore",
    "the next point", "so what does this mean", "let me add",
    "exactly right", "getting into it", "unpacking",
}


# ── GENRE ARC CONFIGURATION PROFILES ────────────────────────────────
#
# Structure per genre:
#   arc_labels     : maps ARC_ESTABLISH → display string for this genre
#   pivot_keywords : content keywords that signal a pivot beat
#   escalate_keywords : content keywords that signal escalation
#   carry_directives: maps arc position → genre-specific carry directive text
#   chain_modifiers : maps arc position → dict with reframe_strength etc.
#
# NOTE: chain_modifiers override get_chain_modifier() ONLY when genre_id
# is explicitly passed. The base function is never modified.

GENRE_ARC_CONFIGS: dict[str, dict] = {

    # ── DRAMA / WHODUNNIT (base — same behaviour as existing system) ─
    "drama": {
        "arc_labels": {
            ARC_ESTABLISH: "ESTABLISH",
            ARC_ESCALATE:  "ESCALATE",
            ARC_PIVOT:     "PIVOT",
            ARC_RESOLVE:   "RESOLVE",
        },
        "pivot_keywords":    PIVOT_KEYWORDS,
        "escalate_keywords": ESCALATE_KEYWORDS,
        "carry_directives": {
            ARC_ESTABLISH: "DECLARE: Lock room DNA, identity, lighting baseline. This frame sets the law.",
            ARC_ESCALATE:  "CARRY: Maintain room architecture from opening. Escalate emotional intensity one beat.",
            ARC_PIVOT:     "CARRY+SHIFT: Room holds but emotional tone shifts. This is the turning point.",
            ARC_RESOLVE:   "RESOLVE: Room holds for final shot. Close emotional arc. Prepare for scene release.",
        },
        "chain_modifiers": {
            ARC_ESTABLISH: {"reframe_strength": 1.0, "emotional_modifier": "",              "room_lock_active": True, "prompt_suffix": ""},
            ARC_ESCALATE:  {"reframe_strength": 0.9, "emotional_modifier": "Intensity builds.", "room_lock_active": True, "prompt_suffix": "Emotional energy rising from previous beat."},
            ARC_PIVOT:     {"reframe_strength": 0.85,"emotional_modifier": "Emotional turning point.", "room_lock_active": True, "prompt_suffix": "Key revelation or shift. Stakes change visibly."},
            ARC_RESOLVE:   {"reframe_strength": 0.8, "emotional_modifier": "Scene resolving.", "room_lock_active": True, "prompt_suffix": "Final emotional beat. Scene closing."},
        },
    },

    # ── WHODUNNIT DRAMA (alias — same profile as drama) ─────────────
    "whodunnit_drama": None,   # resolved at runtime → "drama"

    # ── HORROR ──────────────────────────────────────────────────────
    "horror": {
        "arc_labels": {
            ARC_ESTABLISH: "DREAD_DECLARE",
            ARC_ESCALATE:  "DREAD_BUILD",
            ARC_PIVOT:     "SCARE_BEAT",
            ARC_RESOLVE:   "AFTERMATH",
        },
        "pivot_keywords": PIVOT_KEYWORDS | {
            "jump", "lunges", "appears", "behind", "suddenly", "scream",
            "blood", "shadow moves", "not alone", "door opens",
        },
        "escalate_keywords": ESCALATE_KEYWORDS | {
            "creak", "footsteps", "breathing", "watching", "followed",
            "wrong", "dark", "cold", "silence", "drip",
        },
        "carry_directives": {
            ARC_ESTABLISH: "DREAD_DECLARE: Lock room atmosphere, darkness, isolation. Audience must feel unsafe from frame 1.",
            ARC_ESCALATE:  "DREAD_BUILD: Carry atmospheric dread. Each shot tightens the screw. Never relieve tension.",
            ARC_PIVOT:     "SCARE_BEAT: The threat reveals. Room geometry may shift to disorient. Audience pays off their dread.",
            ARC_RESOLVE:   "AFTERMATH: Scare over but world changed. Show consequence. Scene releases — but unease persists.",
        },
        "chain_modifiers": {
            ARC_ESTABLISH: {"reframe_strength": 1.0, "emotional_modifier": "Deep dread.",           "room_lock_active": True,  "prompt_suffix": "Slow oppressive atmosphere declared."},
            ARC_ESCALATE:  {"reframe_strength": 0.95,"emotional_modifier": "Dread intensifying.",   "room_lock_active": True,  "prompt_suffix": "Each beat closes in tighter."},
            ARC_PIVOT:     {"reframe_strength": 0.7, "emotional_modifier": "SHOCK CUT.",             "room_lock_active": False, "prompt_suffix": "Disorienting. 180 break permitted."},
            ARC_RESOLVE:   {"reframe_strength": 0.85,"emotional_modifier": "Aftermath. Still tense.","room_lock_active": True,  "prompt_suffix": "World changed. Threat may linger."},
        },
    },

    # ── SCI-FI ───────────────────────────────────────────────────────
    "sci_fi": {
        "arc_labels": {
            ARC_ESTABLISH: "WORLD_DECLARE",
            ARC_ESCALATE:  "SYSTEM_ESCALATE",
            ARC_PIVOT:     "REVELATION",
            ARC_RESOLVE:   "SYSTEM_STATE",
        },
        "pivot_keywords": PIVOT_KEYWORDS | {
            "malfunction", "override", "classified", "unknown signal",
            "virus", "breach", "they know", "first contact", "anomaly",
        },
        "escalate_keywords": ESCALATE_KEYWORDS | {
            "scanning", "processing", "incoming", "threat level",
            "countdown", "alarm", "system alert", "calculating",
        },
        "carry_directives": {
            ARC_ESTABLISH: "WORLD_DECLARE: Establish the technological world's rules. Architecture, scale, power hierarchy.",
            ARC_ESCALATE:  "SYSTEM_ESCALATE: The system's pressure builds. Technology serves the rising stakes.",
            ARC_PIVOT:     "REVELATION: Truth of the world inverted or expanded. The paradigm shifts.",
            ARC_RESOLVE:   "SYSTEM_STATE: New equilibrium. Show what the world is NOW after the revelation.",
        },
        "chain_modifiers": {
            ARC_ESTABLISH: {"reframe_strength": 1.0, "emotional_modifier": "Cold precision.",           "room_lock_active": True,  "prompt_suffix": "Geometric world declared."},
            ARC_ESCALATE:  {"reframe_strength": 0.9, "emotional_modifier": "Pressure mounting.",        "room_lock_active": True,  "prompt_suffix": "System under stress. Precise movement."},
            ARC_PIVOT:     {"reframe_strength": 0.8, "emotional_modifier": "Paradigm shift.",           "room_lock_active": False, "prompt_suffix": "The world's rules rewritten."},
            ARC_RESOLVE:   {"reframe_strength": 0.85,"emotional_modifier": "New equilibrium reached.",  "room_lock_active": True,  "prompt_suffix": "Aftermath of revelation. System adjusts."},
        },
    },

    # ── ACTION / RUMBLE LEAGUE (film narrative) ──────────────────────
    "action": {
        "arc_labels": {
            ARC_ESTABLISH: "THREAT_DECLARE",
            ARC_ESCALATE:  "ACTION_CARRY",
            ARC_PIVOT:     "REVERSAL",
            ARC_RESOLVE:   "IMPACT_LANDING",
        },
        "pivot_keywords": PIVOT_KEYWORDS | {
            "ambush", "cornered", "outnumbered", "weapon jams", "turns",
            "shield fails", "unexpected ally", "sacrifice", "blows past",
        },
        "escalate_keywords": ESCALATE_KEYWORDS | {
            "running", "chasing", "pursuit", "incoming fire", "dodges",
            "crashes", "explosion", "driving fast", "jumps", "rolls",
        },
        "carry_directives": {
            ARC_ESTABLISH: "THREAT_DECLARE: Establish stakes, opponents, arena. Energy must be kinetic from frame 1.",
            ARC_ESCALATE:  "ACTION_CARRY: Physical momentum must carry from previous beat. No dead space between shots.",
            ARC_PIVOT:     "REVERSAL: Tactical or physical reversal. Hero/villain positions invert. Camera can break axis.",
            ARC_RESOLVE:   "IMPACT_LANDING: Final impact or consequence. Show physical result. Bodies settle. Breath.",
        },
        "chain_modifiers": {
            ARC_ESTABLISH: {"reframe_strength": 0.9, "emotional_modifier": "Kinetic energy.",          "room_lock_active": True,  "prompt_suffix": "Arena declared. Stakes immediate."},
            ARC_ESCALATE:  {"reframe_strength": 0.8, "emotional_modifier": "Action accelerating.",     "room_lock_active": False, "prompt_suffix": "Physical momentum carries. No pauses."},
            ARC_PIVOT:     {"reframe_strength": 0.7, "emotional_modifier": "REVERSAL. Stakes invert.", "room_lock_active": False, "prompt_suffix": "180 break permitted for chaos."},
            ARC_RESOLVE:   {"reframe_strength": 0.85,"emotional_modifier": "Impact landed.",           "room_lock_active": True,  "prompt_suffix": "Bodies settle. Physical consequence visible."},
        },
    },

    # ── FIGHT BROADCAST (Rumble League live show) ────────────────────
    # NEW for FANZ Universe — Mon-Fri 8pm broadcast format
    # Arc maps: ESTABLISH=pre-fight intro, ESCALATE=round action,
    #           PIVOT=momentum shift, RESOLVE=post-fight aftermath
    "fight_broadcast": {
        "arc_labels": {
            ARC_ESTABLISH: "FIGHTER_INTRO",
            ARC_ESCALATE:  "ROUND_ACTION",
            ARC_PIVOT:     "MOMENTUM_SHIFT",
            ARC_RESOLVE:   "AFTERMATH",
        },
        "pivot_keywords": _FIGHT_PIVOT_KEYWORDS,
        "escalate_keywords": _FIGHT_ESCALATE_KEYWORDS,
        "carry_directives": {
            ARC_ESTABLISH: (
                "FIGHTER_INTRO: Declare both fighters' identities, arena atmosphere, crowd energy. "
                "Corner colours locked. Ring geometry established. Announcer energy sets broadcast tone."
            ),
            ARC_ESCALATE: (
                "ROUND_ACTION: Carry round momentum from previous shot. Fighter positions must match "
                "end of last clip. Action is CONTINUOUS — no cold starts between round shots."
            ),
            ARC_PIVOT: (
                "MOMENTUM_SHIFT: One fighter's advantage reverses. Physical consequence visible — "
                "knockdown, stagger, cut, or tactical shift. Crowd energy changes direction. "
                "Commentary acknowledges the shift."
            ),
            ARC_RESOLVE: (
                "AFTERMATH: Round or fight concluded. Show winner reaction + loser consequence. "
                "Corner rush, referee interaction, crowd release. "
                "Release ring DNA — next broadcast starts fresh arena."
            ),
        },
        "chain_modifiers": {
            ARC_ESTABLISH: {"reframe_strength": 1.0, "emotional_modifier": "Arena energy declared.",    "room_lock_active": True,  "prompt_suffix": "Fighter intro. Crowd anticipation."},
            ARC_ESCALATE:  {"reframe_strength": 0.85,"emotional_modifier": "Fight action continuing.", "room_lock_active": True,  "prompt_suffix": "Physical continuity from last frame. Mid-fight energy."},
            ARC_PIVOT:     {"reframe_strength": 0.75,"emotional_modifier": "MOMENTUM REVERSED.",       "room_lock_active": True,  "prompt_suffix": "Critical moment. Fight changes here."},
            ARC_RESOLVE:   {"reframe_strength": 0.9, "emotional_modifier": "Fight ended. Aftermath.",  "room_lock_active": True,  "prompt_suffix": "Winner declared. Crowd reaction. Release ring DNA."},
        },
    },

    # ── SPORTS GAME BROADCAST (AI Sports League) ─────────────────────
    # NEW for FANZ Universe — 160 teams, 5 sports
    # Arc maps: ESTABLISH=pregame, ESCALATE=live game action,
    #           PIVOT=score change/key play, RESOLVE=post-game
    "sports_game": {
        "arc_labels": {
            ARC_ESTABLISH: "PREGAME",
            ARC_ESCALATE:  "GAME_ACTION",
            ARC_PIVOT:     "KEY_PLAY",
            ARC_RESOLVE:   "POSTGAME",
        },
        "pivot_keywords": _SPORTS_PIVOT_KEYWORDS,
        "escalate_keywords": _SPORTS_ESCALATE_KEYWORDS,
        "carry_directives": {
            ARC_ESTABLISH: (
                "PREGAME: Declare teams, stadium, starting lineup energy. "
                "Team colours locked. Score = 0-0. Crowd atmosphere established. "
                "Announcers introduce broadcast."
            ),
            ARC_ESCALATE: (
                "GAME_ACTION: Game in motion — carry score and game state forward. "
                "Player positions must reflect active play. Stadium energy continuous. "
                "Running clock visible."
            ),
            ARC_PIVOT: (
                "KEY_PLAY: Score change, turnover, or game-defining moment. "
                "Show the play itself + immediate crowd reaction + bench reaction. "
                "Score graphic update required in this shot."
            ),
            ARC_RESOLVE: (
                "POSTGAME: Final whistle/buzzer. Show final score, winning team celebration, "
                "losing team reaction. Stadium atmosphere transitions from game to post-game. "
                "Release stadium DNA for next match."
            ),
        },
        "chain_modifiers": {
            ARC_ESTABLISH: {"reframe_strength": 1.0, "emotional_modifier": "Pre-game energy.",       "room_lock_active": True,  "prompt_suffix": "Teams presented. Stadium declared. Score 0-0."},
            ARC_ESCALATE:  {"reframe_strength": 0.9, "emotional_modifier": "Game in motion.",        "room_lock_active": True,  "prompt_suffix": "Active play continues from previous shot."},
            ARC_PIVOT:     {"reframe_strength": 0.8, "emotional_modifier": "KEY PLAY. Score shifts.","room_lock_active": True,  "prompt_suffix": "Decisive moment. Crowd erupts. Score graphic."},
            ARC_RESOLVE:   {"reframe_strength": 0.9, "emotional_modifier": "Game over. Final score.","room_lock_active": True,  "prompt_suffix": "Post-game. Celebration or defeat. Stadium release."},
        },
    },

    # ── COMEDY SPECIAL (stand-up + sketch format) ────────────────────
    # NEW for FANZ Universe — Comedy specials and sitcom episodes
    "comedy_special": {
        "arc_labels": {
            ARC_ESTABLISH: "SETUP",
            ARC_ESCALATE:  "BUILD",
            ARC_PIVOT:     "SUBVERSION",
            ARC_RESOLVE:   "PUNCHLINE",
        },
        "pivot_keywords": _COMEDY_PIVOT_KEYWORDS,
        "escalate_keywords": _COMEDY_ESCALATE_KEYWORDS,
        "carry_directives": {
            ARC_ESTABLISH: (
                "SETUP: Establish comedic premise, character energy, setting absurdity. "
                "Audience needs to believe the world before it gets broken. "
                "Energy is WARM and CONFIDENT — the comedian/character owns the space."
            ),
            ARC_ESCALATE: (
                "BUILD: Stack the premise. Each beat adds a layer to the joke without resolving it. "
                "Audience is leaning forward. Carry energy and timing from previous beat. "
                "Reaction shots are gold here."
            ),
            ARC_PIVOT: (
                "SUBVERSION: Expected punchline redirected. Callback lands. Misdirection reveals. "
                "The audience laughs at their own assumption. Beat must be EXACT — timing is law here."
            ),
            ARC_RESOLVE: (
                "PUNCHLINE: The release. Physical comedy, verbal punchline, or silent reaction hold. "
                "Cut ON the laugh or just before. Audience reaction shot follows. "
                "Scene closes — next setup starts clean."
            ),
        },
        "chain_modifiers": {
            ARC_ESTABLISH: {"reframe_strength": 1.0, "emotional_modifier": "Warm confident energy.",    "room_lock_active": True,  "prompt_suffix": "Setup declared. Audience receptive."},
            ARC_ESCALATE:  {"reframe_strength": 0.9, "emotional_modifier": "Building the joke.",        "room_lock_active": True,  "prompt_suffix": "Each beat adds pressure. Don't release yet."},
            ARC_PIVOT:     {"reframe_strength": 0.85,"emotional_modifier": "MISDIRECT. Pivot the joke.","room_lock_active": True,  "prompt_suffix": "Timing is everything. Exact beat."},
            ARC_RESOLVE:   {"reframe_strength": 0.8, "emotional_modifier": "Punchline. Release laugh.", "room_lock_active": False, "prompt_suffix": "Cut on the laugh. Audience reaction follows."},
        },
    },

    # ── PODCAST (conversational/interview format) ─────────────────────
    # NEW for FANZ Universe — podcast and interview content
    "podcast": {
        "arc_labels": {
            ARC_ESTABLISH: "TOPIC_INTRO",
            ARC_ESCALATE:  "DISCUSSION",
            ARC_PIVOT:     "KEY_INSIGHT",
            ARC_RESOLVE:   "OUTRO",
        },
        "pivot_keywords": _PODCAST_PIVOT_KEYWORDS,
        "escalate_keywords": _PODCAST_ESCALATE_KEYWORDS,
        "carry_directives": {
            ARC_ESTABLISH: (
                "TOPIC_INTRO: Establish host, guest, topic, and studio energy. "
                "Viewer must know who these people are and why this conversation matters. "
                "Framing is warm, intimate, conversational."
            ),
            ARC_ESCALATE: (
                "DISCUSSION: Carry conversation forward. Shot/counter-shot rhythm. "
                "Speaker must face camera. Listener reaction visible. "
                "Information builds — each beat adds to the picture."
            ),
            ARC_PIVOT: (
                "KEY_INSIGHT: The moment that reframes the conversation. "
                "A surprising data point, personal revelation, or perspective shift. "
                "Hold on the speaker's face. This is the clip that gets shared."
            ),
            ARC_RESOLVE: (
                "OUTRO: Wrap the conversation. Thank-you exchange, call-to-action, sign-off. "
                "Energy winds down warmly. Studio visual release for next episode."
            ),
        },
        "chain_modifiers": {
            ARC_ESTABLISH: {"reframe_strength": 1.0, "emotional_modifier": "Warm intro energy.",        "room_lock_active": True,  "prompt_suffix": "Host and guest presented. Topic declared."},
            ARC_ESCALATE:  {"reframe_strength": 0.9, "emotional_modifier": "Conversation building.",    "room_lock_active": True,  "prompt_suffix": "Shot/counter-shot. Information accumulating."},
            ARC_PIVOT:     {"reframe_strength": 0.95,"emotional_modifier": "KEY INSIGHT. Hold this.",   "room_lock_active": True,  "prompt_suffix": "Face close-up. This is the shareable moment."},
            ARC_RESOLVE:   {"reframe_strength": 0.85,"emotional_modifier": "Warm close.",               "room_lock_active": True,  "prompt_suffix": "Wrap. Call-to-action. Sign-off energy."},
        },
    },
}

# Resolve "whodunnit_drama" alias at runtime
GENRE_ARC_CONFIGS["whodunnit_drama"] = GENRE_ARC_CONFIGS["drama"]

# comedy alias (network_intake.py uses "comedy" as genre_id)
GENRE_ARC_CONFIGS["comedy"] = GENRE_ARC_CONFIGS["comedy_special"]


# ── GENRE-AWARE HELPERS ──────────────────────────────────────────────

def _resolve_genre_config(genre_id: str | None) -> dict:
    """
    Return the genre config dict for genre_id.
    Falls back to drama defaults if genre_id is unknown or None.
    Never raises — always returns a valid config.
    """
    if not genre_id:
        return GENRE_ARC_CONFIGS["drama"]
    cfg = GENRE_ARC_CONFIGS.get(genre_id)
    if cfg is None:
        return GENRE_ARC_CONFIGS["drama"]
    return cfg


def get_genre_display_labels(genre_id: str | None = None) -> dict[str, str]:
    """
    Return the arc display label mapping for a genre.

    Example return for "fight_broadcast":
        {
            "ESTABLISH": "FIGHTER_INTRO",
            "ESCALATE":  "ROUND_ACTION",
            "PIVOT":     "MOMENTUM_SHIFT",
            "RESOLVE":   "AFTERMATH",
        }

    Always returns a complete 4-key dict. Falls back to drama if genre unknown.
    """
    cfg = _resolve_genre_config(genre_id)
    return dict(cfg["arc_labels"])


def get_genre_carry_directive(arc_position: str, genre_id: str | None = None) -> str:
    """
    Return genre-specific carry directive text for an arc position.
    Falls back to drama defaults if genre_id is unknown.
    This SUPPLEMENTS (does not replace) the base _arc_carry_directive field.
    """
    cfg = _resolve_genre_config(genre_id)
    return cfg["carry_directives"].get(arc_position, "")


def get_genre_chain_modifier(arc_position: str, genre_id: str | None = None) -> dict:
    """
    Return genre-aware chain modifier dict.
    If genre_id is None or unknown, delegates to the base get_chain_modifier().
    """
    if not genre_id:
        return get_chain_modifier(arc_position, 0)

    cfg = _resolve_genre_config(genre_id)
    modifiers = cfg.get("chain_modifiers", {})
    base = get_chain_modifier(arc_position, 0)  # always have a fallback
    return modifiers.get(arc_position, base)


def apply_genre_arc_labels(shots: list[dict], genre_id: str) -> list[dict]:
    """
    Add _arc_display_label and _arc_genre_directive to each shot.

    CRITICAL: This function NEVER modifies _arc_position.
    It only ADDS two new fields alongside existing arc data.

    Fields added:
        _arc_display_label : genre-specific term for this arc position
                             e.g. "FIGHTER_INTRO" instead of "ESTABLISH"
        _arc_genre_directive: genre-specific carry instruction for the runner
        _genre_id          : the genre that was applied (for traceability)

    If genre_id is unknown, drama defaults are used (no exceptions).
    """
    labels = get_genre_display_labels(genre_id)
    cfg = _resolve_genre_config(genre_id)
    directives = cfg.get("carry_directives", {})

    for shot in shots:
        arc = shot.get("_arc_position", ARC_ESCALATE)
        shot["_arc_display_label"]   = labels.get(arc, arc)
        shot["_arc_genre_directive"] = directives.get(arc, "")
        shot["_genre_id"]            = genre_id

    return shots


def compute_arc_positions_for_genre(
    shots: list[dict],
    story_bible_scene: dict | None = None,
    genre_id: str | None = None,
) -> list[dict]:
    """
    Compute arc positions with genre-aware pivot/escalation keyword detection.

    This is an EXTENSION of compute_arc_positions() that temporarily swaps
    the keyword sets based on genre. The base function is never modified.

    Falls back to base compute_arc_positions() if genre_id is None or unknown.
    """
    if not genre_id or genre_id not in GENRE_ARC_CONFIGS:
        return compute_arc_positions(shots, story_bible_scene)

    cfg = _resolve_genre_config(genre_id)
    genre_pivot_kw    = cfg.get("pivot_keywords",    PIVOT_KEYWORDS)
    genre_escalate_kw = cfg.get("escalate_keywords", ESCALATE_KEYWORDS)

    if not shots:
        return shots

    n = len(shots)
    total_beats = _count_unique_beats(shots)

    for i, shot in enumerate(shots):
        beat_idx  = shot.get("_beat_index", i)
        beat_atm  = (shot.get("_beat_atmosphere") or "").lower()
        beat_act  = (shot.get("_beat_action") or "").lower()
        beat_dlg  = (shot.get("_beat_dialogue") or "").lower()
        combined  = f"{beat_atm} {beat_act} {beat_dlg}"

        is_first       = (i == 0)
        is_last        = (i == n - 1)
        is_second_last = (i == n - 2) and n > 2

        # ── Genre-aware arc detection ────────────────────────────────
        if is_first:
            arc = ARC_ESTABLISH
        elif is_last:
            arc = ARC_RESOLVE
        elif any(kw in combined for kw in genre_pivot_kw):
            arc = ARC_PIVOT
        elif any(kw in combined for kw in genre_escalate_kw):
            arc = ARC_ESCALATE
        elif beat_idx is not None and total_beats > 0:
            progress = beat_idx / max(total_beats - 1, 1)
            if progress < 0.25:
                arc = ARC_ESTABLISH
            elif progress < 0.7:
                arc = ARC_ESCALATE
            else:
                arc = ARC_PIVOT
        else:
            arc = ARC_ESCALATE

        if is_second_last and arc == ARC_RESOLVE:
            arc = ARC_ESCALATE

        # ── Write base arc metadata (same as base function) ──────────
        shot["_arc_position"]       = arc
        shot["_arc_index"]          = i
        shot["_arc_total"]          = n
        shot["_scene_close"]        = is_last
        shot["_arc_carry_directive"] = cfg["carry_directives"].get(arc, "")

        if is_last:
            shot["_arc_release"] = {
                "scene_close":    True,
                "release_room_dna": True,
                "outgoing_hint":  _build_outgoing_hint(shot, story_bible_scene),
            }
        else:
            shot["_arc_release"] = {"scene_close": False}

    return shots


# ── CLI DIAGNOSTIC ──────────────────────────────────────────────────

def diagnose_scene(project_dir: str, scene_id: str) -> None:
    """Print arc analysis for a scene's shots."""
    sp_path = os.path.join(project_dir, "shot_plan.json")
    sb_path = os.path.join(project_dir, "story_bible.json")

    with open(sp_path) as f:
        sp = json.load(f)
    if isinstance(sp, list):
        sp = {"shots": sp}

    story_bible = None
    if os.path.exists(sb_path):
        with open(sb_path) as f:
            story_bible = json.load(f)

    prefix = str(scene_id).zfill(3)
    scene_shots = [s for s in sp["shots"] if (s.get("shot_id") or "").startswith(prefix)]

    if not scene_shots:
        print(f"No shots found for scene {prefix}")
        return

    enriched = enrich_shots_with_arc(scene_shots, story_bible, scene_id)

    print(f"\n{'='*60}")
    print(f"  CHAIN ARC INTELLIGENCE — Scene {prefix}")
    print(f"  {len(enriched)} shots, {_count_unique_beats(enriched)} unique beats")
    print(f"{'='*60}\n")

    for s in enriched:
        sid = s.get("shot_id", "?")
        arc = s.get("_arc_position", "?")
        close = "🔚" if s.get("_scene_close") else "  "
        beat = s.get("_beat_ref", "?")
        directive = s.get("_arc_carry_directive", "")[:60]
        print(f"  {close} {sid:12s}  [{arc:10s}]  beat={beat:8s}  {directive}")

    # Show outgoing hint if last shot has one
    last = enriched[-1]
    hint = get_outgoing_hint(last)
    if hint:
        print(f"\n  OUTGOING HINT → {hint}")
    print()


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3:
        diagnose_scene(sys.argv[1], sys.argv[2])
    else:
        print("Usage: python3 chain_arc_intelligence.py <project_dir> <scene_id>")
        print("Example: python3 chain_arc_intelligence.py pipeline_outputs/victorian_shadows_ep1 006")
