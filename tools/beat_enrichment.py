#!/usr/bin/env python3
"""
ATLAS V27.6 — Beat Enrichment (Permanent Shot-Level Beat Data)
===============================================================
Takes the rich beat data from story_bible.json and PERMANENTLY
writes it onto each shot in shot_plan.json.

THE GAP THIS FILLS:
  story_bible.json has:
    - beat.character_action: "Nadia catches falling letter, unfolds it, expression shifts to shock"
    - beat.dialogue: "My dearest Thomas..."
    - beat.atmosphere: "discovery, tension, hidden truth"

  shot_plan.json has:
    - beat_ref: (empty)
    - description: (empty)
    - No physical action. No eye-line. No body direction.

  After enrichment, each shot gets:
    - _beat_ref: "beat_2"
    - _beat_action: "Nadia catches falling letter, unfolds it, expression shifts to shock"
    - _eye_line_target: "down at letter in hands"
    - _body_direction: "freezing in place, hands pause on letter"
    - _cut_motivation: "OBJECT INTERACTION — letter falls from book"
    - _beat_dialogue: "My dearest Thomas..."
    - _beat_atmosphere: "discovery, tension, hidden truth"
    - _beat_enriched: true (LOCK — downstream steps must not strip these fields)

IMMUTABILITY:
  Fields prefixed with _beat_ are LOCKED after enrichment.
  The V26 controller, fix-v16, Film Engine, and all enrichment steps
  MUST check for _beat_enriched=True and preserve these fields.
  This is enforced by the pre-run gate (Phase 4).

WHEN TO RUN:
  After fix-v16, before any generation.
  Part of the Production Workflow (new Step 3.5).
  Can be re-run safely — it overwrites beat fields but nothing else.
"""

import json
import re
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# ── Physical action vocabulary (expanded from beat_shot_linker) ──
EYE_LINE_RULES = {
    # Object interactions → eyes on object
    "letter": "down at letter in hands, reading",
    "book": "scanning book spines at eye level",
    "photograph": "through camera viewfinder, scanning scene",
    "camera": "through camera viewfinder, framing shot",
    "note": "down at paper in hands",
    "manuscript": "down at manuscript, studying text",
    "painting": "up at painting on wall",
    "window": "toward window, gazing out",
    "door": "toward door, alert",
    "shelf": "scanning across shelves",
    "desk": "down at desk surface",
    "mirror": "at own reflection",
    "phone": "down at phone screen",

    # Movement verbs → tracking direction
    "enters": "forward, taking in new space",
    "walks": "ahead, direction of movement",
    "turns": "rotating to new focus point",
    "looks toward": "toward mentioned target",
    "glances": "quick shift to target",
    "stares": "fixed, unblinking, at target",
}

BODY_RULES = {
    # Movement — expanded V30.1
    "moves through": "walking slowly through space, weight shifting foot to foot",
    "pushes open": "arms extended forward, weight leaning into door, momentum carrying through",
    "pushes": "arms pressing forward, body leaning into resistance",
    "pauses to scan": "feet planted, torso rotating, head tracking across space",
    "pauses": "weight settling, stillness after movement, breath visible",
    "trails his hand": "arm extended, fingertips lightly grazing surface, body angled inward",
    "trails her hand": "arm extended, fingertips lightly grazing surface, body angled inward",
    "trails": "hand extended to surface, slow deliberate contact",
    "gazes up at": "neck craned back, head tilted upward, weight shifting back on heels",
    "gazes up": "neck craned back, head tilted upward, weight shifting back on heels",
    "gazes": "body stilled, focus locked forward, slight forward lean",
    "stares up": "head back, eyes fixed above, jaw set",
    "opens briefcase": "body bending forward, hands lifting lid, shoulders squaring",
    "opens": "hands working clasps or handles, torso angling toward object",
    "pulls out": "arm reaching into bag or surface, shoulder rotating, weight shifting",
    "pulls": "arm drawing backward, shoulder pulling back, body counterbalancing",
    "stands at": "weight evenly distributed, body squared to subject",
    "enters": "stepping into frame, body transitioning from doorway",
    "walks": "walking, natural gait, arms relaxed or purposeful",
    "crosses": "crossing the space with purpose",
    "turns": "body rotating, shoulders leading",
    "moves": "body in motion, weight shifting with direction of travel",
    "steps": "foot lifting and placing, deliberate or hurried",
    "approaches": "body moving forward, gaining ground on target",
    "backs away": "weight shifting backward, feet retreating",
    "leans forward": "torso tipping forward, chin leading, weight on front foot",
    "leans back": "spine arching back, weight shifting to rear",
    "sits": "lowering motion, weight transferring to seat",
    "rises": "upward motion, legs straightening, standing height",
    "kneels": "one or both knees lowering to ground",

    # Object interaction — expanded V30.1
    "catches": "hands reacting, grabbing, arms snapping to intercept",
    "unfolds": "fingers carefully opening paper, delicate movement",
    "picks up": "bending or reaching, hands closing on object",
    "pockets": "hand moving to pocket, quick tucking motion",
    "folds": "fingers working paper, careful creasing",
    "slips": "smooth, furtive hand movement",
    "lifting": "arms raising, steady motion",
    "lifts": "arms raising to bring object level",
    "reads": "still, eyes moving, slight head tilt",
    "examines": "eyes moving carefully over surface, head tilting for different angle",
    "holds": "arms steady, grip visible, weight balanced",
    "grips": "fingers tightening on object, knuckles defined",
    "places": "lowering object carefully, deliberate hand movement",
    "sets down": "arm lowering, controlled release of weight",
    "reaches for": "arm extending toward object, body leaning",
    "touches": "fingertips making contact, tentative or deliberate",

    # Emotional shifts — expanded V30.1
    "expression shifts": "visible emotional change, micro-expressions",
    "shock": "body stiffening, breath catching, eyes widening",
    "discovery": "forward lean, attention sharpening",
    "furtive": "quick glances, body tense, self-conscious movement",
    "secretive": "shoulders drawing in, movement becoming smaller",
    "reverence": "slow, deliberate movement, careful hands",
    "grief": "shoulders rounded, head bowed, weight sinking",
    "anger": "jaw setting, shoulders squaring, breath deepening",
    "fear": "body drawing in, head lowering, weight on back foot",
    "resolve": "spine straightening, chin rising, stillness before action",
    "hesitation": "weight shifting foot to foot, body half-committed to movement",
    "hesitates": "weight shifting foot to foot, body half-committed, eyes darting",
    "reveals": "body leaning forward, hands presenting, eyes locked on listener",
    "reveal": "body leaning forward, hands presenting, eyes locked on listener",
    "confronts": "body squaring to target, chest forward, ground held",
    "refuses": "arms crossing or dropping, chin setting, weight planted",
    "paces": "restless movement, walking back and forth, weight shifting with agitation",
    "pacing": "restless back-and-forth, energy visible in stride",
    "reports": "body squared to listener, hands gesturing with information",
    "tells": "body oriented toward listener, chin forward, delivering information",
    "speaks": "torso oriented toward conversation partner, natural speech gestures",
    "listens": "body still, head slightly tilted, weight balanced, attention focused",
    "face each other": "bodies squared facing each other, tension in the space between",
    "faces": "body turning to face, shoulders squaring to target",

    # V36.5.1: Scene-specific actions caught by audit
    "absorbs": "jaw tightens, breath held, eyes shift fractionally, controlled composure",
    "appears": "stepping into frame from edge, body arriving beside other character",
    "descends": "moving downward on stairs, hands gripping rail or object, weight lowering step by step",
    "look around": "heads turning slowly, eyes scanning the space, bodies oriented outward",
    "watches": "body still in doorframe or threshold, weight settled, eyes locked forward on subject",
    "watching": "body still in doorframe or threshold, weight settled, eyes locked forward on subject",
    "stands": "weight evenly distributed, body squared to space, grounded and present",
    "stand": "weight evenly distributed, bodies squared to space, grounded and present",
    "alone": "solitary figure, weight settled, stillness filling the space",
    "wide closing": "figures visible in full room context, distance between them readable",
}


@dataclass
class BeatEnrichmentResult:
    shots_enriched: int
    shots_skipped: int
    beats_mapped: int
    issues: List[str]


def extract_eye_line(character_action: str, dialogue: str = "", atmosphere: str = "") -> str:
    """Derive eye-line target from beat's character_action text."""
    text = ((character_action or "") + " " + (dialogue or "")).lower()

    # Check specific object targets first (most specific wins)
    for keyword, eye_line in sorted(EYE_LINE_RULES.items(), key=lambda x: len(x[0]), reverse=True):
        if keyword in text:
            return eye_line

    # Fallback based on atmosphere
    atmo = (atmosphere or "").lower()
    if "discovery" in atmo or "tension" in atmo:
        return "alert, scanning for source of tension"
    if "warm" in atmo or "reverence" in atmo:
        return "soft gaze, taking in surroundings with appreciation"

    return "neutral, present in scene"


def extract_body_direction(character_action: str, atmosphere: str = "") -> str:
    """Derive body action from beat's character_action text."""
    text = (character_action or "").lower()

    # Check body action rules (longest match first)
    for keyword, body in sorted(BODY_RULES.items(), key=lambda x: len(x[0]), reverse=True):
        if keyword in text:
            return body

    # Fallback
    atmo = (atmosphere or "").lower()
    if "tension" in atmo:
        return "still, tension visible in posture"
    if "warm" in atmo:
        return "relaxed, natural presence"

    return "present, natural micro-movements"


def derive_cut_motivation(beat_idx: int, beat: Dict, prev_beat_idx: int,
                          shot_type: str, shot_idx_in_scene: int) -> str:
    """Determine WHY the camera cuts to this shot."""
    if shot_idx_in_scene == 0:
        return "SCENE OPEN — establishing geography and character entry"

    action = (beat.get("character_action") or "").lower()

    # New beat = new physical state
    if beat_idx != prev_beat_idx:
        return f"NEW BEAT — transition to beat {beat_idx + 1}: {beat.get('description', '')[:50]}"

    # Object interaction
    for obj in ["letter", "book", "camera", "phone", "door"]:
        if obj in action:
            return f"OBJECT INTERACTION — character engages with {obj}"

    # Movement
    for verb in ["enters", "walks", "crosses", "turns", "moves"]:
        if verb in action:
            return f"CHARACTER MOVEMENT — {verb}"

    # Emotion shift
    for emotion in ["shock", "discovery", "shifts", "realizes"]:
        if emotion in action:
            return f"EMOTION SHIFT — {emotion}"

    # Shot type change (insert, close-up for detail)
    if shot_type in ("b-roll", "insert"):
        return "DETAIL INSERT — visual emphasis on narrative object"
    if "close" in shot_type:
        return "TIGHTER FRAMING — emotional emphasis"

    return "CONTINUITY — sustaining current dramatic beat"


def enrich_scene(shots: List[Dict], story_bible_scene: Dict,
                 scene_id: str) -> BeatEnrichmentResult:
    """
    Map each shot in a scene to its story bible beat and write
    permanent enrichment data onto the shot.
    """
    beats = story_bible_scene.get("beats", [])
    if not beats:
        return BeatEnrichmentResult(0, 0, 0, [f"Scene {scene_id}: no beats in story bible"])

    scene_shots = [s for s in shots if s.get("shot_id", "").startswith(scene_id)]
    if not scene_shots:
        return BeatEnrichmentResult(0, 0, 0, [f"Scene {scene_id}: no shots in plan"])

    num_shots = len(scene_shots)
    num_beats = len(beats)
    enriched = 0
    skipped = 0
    issues = []
    prev_beat_idx = 0

    for i, shot in enumerate(scene_shots):
        shot_id = shot.get("shot_id", "")
        shot_type = (shot.get("shot_type") or "").lower()
        dialogue = shot.get("dialogue_text", "")

        # ── MAP SHOT TO BEAT ──
        # Strategy: proportional position + dialogue content matching

        # Default: proportional mapping
        proportion = i / max(num_shots - 1, 1)
        beat_idx = min(int(proportion * num_beats), num_beats - 1)

        # Override: first/last shot rules
        if i == 0 and shot_type in ("establishing", "wide"):
            beat_idx = 0
        elif i == num_shots - 1 and shot_type in ("closing", "wide"):
            beat_idx = num_beats - 1

        # Override: dialogue content matching
        for bi, beat in enumerate(beats):
            beat_dialogue = (beat.get("dialogue") or "").lower()
            beat_desc = (beat.get("description") or "").lower()
            dial_lower = dialogue.lower() if dialogue else ""

            if not dial_lower:
                continue

            # Check for distinctive word overlap
            beat_words = set(re.findall(r'\b\w{5,}\b', beat_dialogue + " " + beat_desc))
            dial_words = set(re.findall(r'\b\w{5,}\b', dial_lower))
            common = {"character", "speaks", "scene", "nadia"}
            overlap = (beat_words & dial_words) - common

            if len(overlap) >= 2:
                beat_idx = bi
                break

            # Direct dialogue substring match
            if beat_dialogue and len(beat_dialogue) > 10:
                # Check if any 10+ char segment of beat dialogue appears in shot dialogue
                for start in range(0, len(beat_dialogue) - 10, 5):
                    segment = beat_dialogue[start:start+15]
                    if segment in dial_lower:
                        beat_idx = bi
                        break

        beat = beats[beat_idx]
        char_action = beat.get("character_action", "")
        beat_desc = beat.get("description", "")
        beat_dial = beat.get("dialogue")
        beat_atmo = beat.get("atmosphere", "")

        # ── DERIVE CINEMATOGRAPHIC DATA ──
        eye_line = extract_eye_line(char_action, beat_dial, beat_atmo)
        body_dir = extract_body_direction(char_action, beat_atmo)
        cut_motiv = derive_cut_motivation(beat_idx, beat, prev_beat_idx,
                                          shot_type, i)

        # V30.1: CLOSING SHOT OVERRIDE — closing shots sustain the beat's final
        # emotional/physical state but signal scene resolution, NOT a repeat.
        # If a closing shot shares the same beat as the previous shot, override
        # body_dir to a "holding" version that reads as scene-end, not a repeat.
        if shot_type == "closing" and beat_idx == prev_beat_idx and i > 0:
            # Derive a closing-specific body from beat atmosphere
            atmo_lower = (beat_atmo or "").lower()
            action_lower = (char_action or "").lower()
            if "confrontation" in atmo_lower or "confronts" in action_lower:
                body_dir = "both figures frozen in silent standoff, scene holding in tension"
                eye_line = eye_line or "locked on opposite character, unblinking"
            elif "grief" in atmo_lower or "melancholy" in atmo_lower:
                body_dir = "weight sinking, posture closing inward, the moment held"
                eye_line = eye_line or "downcast, lost in memory"
            elif "furtive" in atmo_lower or "secretive" in atmo_lower:
                body_dir = "body stilled mid-motion, breath held, listening"
                eye_line = "toward door or exit, hyper-alert"
            elif "discovery" in atmo_lower or "tension" in atmo_lower:
                body_dir = "body stilled by weight of discovery, processing"
                eye_line = eye_line or "middle distance, inward gaze"
            else:
                body_dir = "scene holds, final position sustained, breath visible"

        # V36.5.1: INSERT/B-ROLL DIALOGUE GUARD — insert shots (object close-ups)
        # inherit _beat_dialogue from their parent beat, but they have characters=[]
        # so Kling has nobody to speak the line. Strip dialogue from inserts.
        _shot_chars = shot.get("characters") or []
        if not _shot_chars and shot_type in ("insert", "b-roll", "establishing"):
            beat_dial = None  # No characters = no dialogue on this shot

        # V36.5.2: AUTO-POPULATE DIALOGUE SPEAKER FROM BEAT CONTEXT
        # The story bible character_action names who acts → infer who speaks.
        # This eliminates manual speaker assignment.
        _dialogue_speaker = ""
        if beat_dial and _shot_chars:
            # Strategy 1: character_action names someone explicitly
            action_lower = (char_action or "").lower()
            for cname in _shot_chars:
                # Check first name, last name, and full name
                name_parts = cname.lower().split()
                if any(part in action_lower for part in name_parts if len(part) > 2):
                    _dialogue_speaker = cname
                    break
            # Strategy 2: solo character in shot → they speak
            if not _dialogue_speaker and len(_shot_chars) == 1:
                _dialogue_speaker = _shot_chars[0]
            # Strategy 3: scene characters_present from story_bible
            if not _dialogue_speaker and len(_shot_chars) == 2:
                # Two characters: check beat action for speech verbs near a name
                for cname in _shot_chars:
                    name_parts = cname.lower().split()
                    for part in name_parts:
                        if len(part) <= 2:
                            continue
                        idx = action_lower.find(part)
                        if idx >= 0:
                            # Check if speech verb is near this name
                            context = action_lower[max(0,idx-30):idx+len(part)+30]
                            if any(v in context for v in ("says", "tells", "speaks",
                                "replies", "asks", "demands", "whispers", "announces",
                                "reveals", "confronts", "protests", "delivers",
                                "confesses", "reports", "responds")):
                                _dialogue_speaker = cname
                                break
                    if _dialogue_speaker:
                        break
            # Strategy 4: first character in list as default
            if not _dialogue_speaker:
                _dialogue_speaker = _shot_chars[0]

        # V36.5.2: AUTO-POPULATE SCENE CONTEXT from story_bible
        # These fields make every shot self-contained with scene metadata
        _scene_atmo = story_bible_scene.get("atmosphere", "")
        _scene_time = story_bible_scene.get("time_of_day", "")
        _scene_loc = story_bible_scene.get("location", "")

        # ── WRITE TO SHOT (PERMANENT) ──
        shot["_beat_ref"] = f"beat_{beat_idx + 1}"
        shot["_beat_index"] = beat_idx
        shot["_beat_description"] = beat_desc
        shot["_beat_action"] = char_action
        shot["_beat_dialogue"] = beat_dial
        shot["_beat_atmosphere"] = beat_atmo
        shot["_eye_line_target"] = eye_line
        shot["_body_direction"] = body_dir
        shot["_cut_motivation"] = cut_motiv
        shot["_dialogue_speaker"] = _dialogue_speaker
        shot["_scene_atmosphere"] = _scene_atmo
        shot["_scene_time_of_day"] = _scene_time
        shot["_scene_location"] = _scene_loc
        shot["_beat_enriched"] = True  # LOCK flag

        enriched += 1
        prev_beat_idx = beat_idx

        logger.info(f"[BEAT ENRICH] {shot_id} → beat_{beat_idx+1}: "
                    f"eye={eye_line[:30]}, body={body_dir[:30]}")

    # ── DETECT ISSUES ──
    # Adjacent same-type shots in same beat with no physical change
    for i in range(1, len(scene_shots)):
        curr = scene_shots[i]
        prev = scene_shots[i-1]
        if (curr.get("_beat_index") == prev.get("_beat_index") and
            curr.get("shot_type") == prev.get("shot_type") and
            "OBJECT" not in curr.get("_cut_motivation", "") and
            "MOVEMENT" not in curr.get("_cut_motivation", "")):
            issues.append(f"POTENTIAL JUMP CUT: {prev.get('shot_id')} → {curr.get('shot_id')} "
                         f"(same beat {curr.get('_beat_ref')}, same type {curr.get('shot_type')}, "
                         f"no physical motivation)")

    return BeatEnrichmentResult(
        shots_enriched=enriched,
        shots_skipped=skipped,
        beats_mapped=len(set(s.get("_beat_index", -1) for s in scene_shots)),
        issues=issues,
    )


def enrich_project(project_path: str, scene_ids: List[str] = None) -> Dict:
    """
    Enrich all scenes (or specified scenes) in a project.
    Writes results back to shot_plan.json.
    """
    project = Path(project_path)

    # Load data
    with open(project / "shot_plan.json") as f:
        sp = json.load(f)
    is_list = isinstance(sp, list)
    shots = sp if is_list else sp.get("shots", [])

    with open(project / "story_bible.json") as f:
        sb = json.load(f)

    # Determine which scenes to enrich
    if not scene_ids:
        scene_ids = sorted(set(
            s.get("shot_id", "")[:3] for s in shots if s.get("shot_id")
        ))

    results = {}
    total_enriched = 0
    total_issues = []

    for scene_id in scene_ids:
        sb_scene = next((s for s in sb.get("scenes", [])
                        if s.get("scene_id") == scene_id), None)
        if not sb_scene:
            results[scene_id] = {"status": "SKIP", "reason": "No story bible scene"}
            continue

        result = enrich_scene(shots, sb_scene, scene_id)
        results[scene_id] = {
            "status": "OK",
            "enriched": result.shots_enriched,
            "beats_mapped": result.beats_mapped,
            "issues": result.issues,
        }
        total_enriched += result.shots_enriched
        total_issues.extend(result.issues)

    # ── SAVE (preserving format) ──
    # Backup first
    import shutil
    backup_name = f"shot_plan.json.backup_beat_enrich_{Path(sys.argv[0]).stem}" if len(sys.argv) > 0 else "shot_plan.json.backup_beat_enrich"
    shutil.copy2(project / "shot_plan.json", project / backup_name)

    if is_list:
        with open(project / "shot_plan.json", "w") as f:
            json.dump(shots, f, indent=2)
    else:
        sp["shots"] = shots
        with open(project / "shot_plan.json", "w") as f:
            json.dump(sp, f, indent=2)

    print(f"\n{'='*70}")
    print(f"  BEAT ENRICHMENT COMPLETE")
    print(f"  Scenes: {len(scene_ids)} | Shots enriched: {total_enriched}")
    if total_issues:
        print(f"  Issues: {len(total_issues)}")
        for issue in total_issues:
            print(f"    ⚠ {issue}")
    print(f"  Backup: {backup_name}")
    print(f"{'='*70}")

    return {
        "total_enriched": total_enriched,
        "scenes": results,
        "issues": total_issues,
    }


if __name__ == "__main__":
    project = sys.argv[1] if len(sys.argv) > 1 else "pipeline_outputs/victorian_shadows_ep1"
    scene_ids = [sys.argv[2]] if len(sys.argv) > 2 else None

    result = enrich_project(project, scene_ids)

    # Print per-scene summary
    for sid, data in result["scenes"].items():
        if data["status"] == "OK":
            print(f"  Scene {sid}: {data['enriched']} shots enriched, "
                  f"{data['beats_mapped']} beats covered")
