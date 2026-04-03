#!/usr/bin/env python3
"""
SCRIPT INSIGHT ENGINE — V21
============================
Ensures every prompt contains actual STORY CONTENT from the script.
This is the missing link between structural validation and content accuracy.

The Prompt Authority Gate strips conflicts.
The Script Insight Engine INJECTS story truth.

6 CHECKS:
1. BEAT ACTION INJECTION — Extract actions from story bible beats, inject into prompts
2. DIALOGUE MARKER ENFORCEMENT — Ensure "character speaks:" in LTX for all dialogue shots
3. STORY SPECIFICITY SCORING — Detect generic template prompts with no story content
4. BEAT COVERAGE VALIDATION — Ensure all beats have at least one visual shot
5. EMOTIONAL ARC CONTINUITY — Validate smooth emotional progression across shots
6. LOCATION ATMOSPHERE INJECTION — Inject scene-specific atmosphere keywords

WIRING: Called from prompt_authority_gate.py AFTER conflict stripping, BEFORE generation.
Or called standalone: enrich_with_script_insight(shots, story_bible)
"""

import json
import re
import os
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("atlas.script_insight")


# ============================================================
# ACTION VERB EXTRACTION (from script_fidelity_agent.py)
# Physical verbs ONLY — no atmosphere words
# ============================================================

ACTION_VERBS = {
    "kneels", "kneel", "kneeling", "stands", "stand", "standing",
    "sits", "sit", "sitting", "walks", "walk", "walking",
    "runs", "run", "running", "picks", "pick", "picking",
    "places", "place", "placing", "holds", "hold", "holding",
    "reaches", "reach", "reaching", "opens", "open", "opening",
    "closes", "close", "closing", "turns", "turn", "turning",
    "looks", "look", "looking", "watches", "watch", "watching",
    "reads", "read", "reading", "speaks", "speak", "speaking",
    "whispers", "whisper", "whispering", "grabs", "grab", "grabbing",
    "drops", "drop", "dropping", "falls", "fall", "falling",
    "rises", "rise", "rising", "leans", "lean", "leaning",
    "presses", "press", "pressing", "lifts", "lift", "lifting",
    "lowers", "lower", "lowering", "pushes", "push", "pushing",
    "pulls", "pull", "pulling", "dials", "dial", "dialing",
    "writes", "write", "writing", "signs", "sign", "signing",
    "nods", "nod", "nodding", "shakes", "shake", "shaking",
    "breathes", "breathe", "breathing", "stares", "stare", "staring",
    "touches", "touch", "touching", "grips", "grip", "gripping",
    "crawls", "crawl", "crawling", "climbs", "climb", "climbing",
    "pours", "pour", "pouring", "drinks", "drink", "drinking",
    "eats", "eat", "eating", "smiles", "smile", "smiling",
    "frowns", "frown", "frowning", "cries", "cry", "crying",
    "screams", "scream", "screaming", "gasps", "gasp", "gasping",
    "stumbles", "stumble", "stumbling", "collapses", "collapse",
    "traces", "trace", "tracing", "carves", "carve", "carving",
    "blows", "blow", "blowing", "flickers", "flicker", "flickering",
    "arranges", "arrange", "arranging", "descends", "descend",
    "winds", "wind", "winding", "passes", "pass", "passing",
}

# Atmosphere words that are NOT actions (removed from V17.7 fix)
NOT_ACTIONS = {
    "ritual", "chanting", "lights", "candles", "burns", "ceremony",
    "darkness", "shadows", "atmosphere", "tone", "mood", "feeling",
    "ancient", "stone", "chamber", "manor", "altar",
}


# ============================================================
# SCENE ATMOSPHERE KEYWORDS
# Injected to ensure location-specific visuals
# ============================================================

SCENE_ATMOSPHERES = {
    "001": {
        "location": "cramped stone ritual chamber",
        "keywords": ["stone walls with carved symbols", "guttering candles",
                     "stone altar", "wax pooling on cold stone",
                     "shadows dancing on carved walls"],
        "time": "night",
        "light": "candlelight only, deep shadows",
    },
    "002": {
        "location": "small cramped city apartment",
        "keywords": ["overdue bills on table", "cheap coffee mug",
                     "morning light through dirty window",
                     "cluttered desk", "stained wallpaper"],
        "time": "morning",
        "light": "cold blue morning light through window",
    },
    "003": {
        "location": "bus traveling along coastal road",
        "keywords": ["rain-streaked bus window", "coastal cliffs below",
                     "winding narrow road", "wild landscape",
                     "twisted trees", "rocky outcrops"],
        "time": "late afternoon",
        "light": "overcast natural daylight, soft diffused",
    },
}


# ============================================================
# EMOTIONAL TONE MAP (for arc validation)
# ============================================================

EMOTION_INTENSITY = {
    "dread": 8, "terror": 9, "horror": 10, "desperation": 7,
    "tension": 6, "anxiety": 5, "unease": 4, "foreboding": 5,
    "curiosity": 3, "surprise": 4, "determination": 5,
    "hope": 3, "anticipation": 4, "arrival": 2,
    "grief": 7, "sorrow": 6, "melancholy": 5, "longing": 4,
    "anger": 7, "fury": 9, "frustration": 5,
    "calm": 1, "peace": 1, "contentment": 2,
    "joy": 3, "excitement": 4, "triumph": 5,
    "confusion": 3, "disbelief": 4, "shock": 6,
}


def extract_beat_actions(beat_description: str) -> List[str]:
    """Extract physical action verbs/phrases from a beat description."""
    words = set(beat_description.lower().split())
    actions = words & ACTION_VERBS - NOT_ACTIONS

    # Also extract full action phrases (e.g., "kneels at stone altar")
    phrases = []
    sentences = re.split(r'[.,;]', beat_description)
    for sent in sentences:
        sent = sent.strip()
        sent_lower = sent.lower()
        # Check if sentence contains an action verb
        for verb in ACTION_VERBS:
            if verb in sent_lower:
                phrases.append(sent)
                break

    return phrases


def extract_key_props(beat_description: str) -> List[str]:
    """Extract props/objects from beat description."""
    prop_patterns = [
        r'\b(letter|letters)\b', r'\b(phone|telephone)\b',
        r'\b(candle|candles)\b', r'\b(altar)\b',
        r'\b(book|books)\b', r'\b(key|keys)\b',
        r'\b(ring|rings)\b', r'\b(pendant|necklace)\b',
        r'\b(cup|mug|glass)\b', r'\b(coffee)\b',
        r'\b(bill|bills)\b', r'\b(sign|signpost)\b',
        r'\b(bag|suitcase|luggage)\b', r'\b(newspaper)\b',
        r'\b(photograph|photo)\b', r'\b(mirror)\b',
        r'\b(door|gate)\b', r'\b(window)\b',
        r'\b(map)\b', r'\b(knife|blade|dagger)\b',
        r'\b(symbols?)\b', r'\b(carved|carvings?)\b',
        r'\b(wax)\b', r'\b(blood)\b',
    ]
    props = []
    desc_lower = beat_description.lower()
    for pattern in prop_patterns:
        match = re.search(pattern, desc_lower)
        if match:
            props.append(match.group())
    return list(set(props))


# ============================================================
# CHECK 1: BEAT ACTION INJECTION
# ============================================================

def inject_beat_actions(shot: dict, beat: dict) -> dict:
    """
    Inject beat action descriptions into shot prompts.
    Returns dict with injection details.
    """
    result = {"injected": False, "action": "", "props": []}

    if not beat:
        return result

    nano = shot.get("nano_prompt", "")
    ltx = shot.get("ltx_motion_prompt", "")
    beat_desc = beat.get("description", "")

    if not beat_desc:
        return result

    # Check if action already present (marker-based detection)
    has_action = ("character action:" in nano.lower() or
                  "character performs:" in nano.lower() or
                  "Character action:" in nano)

    if has_action:
        result["injected"] = True  # Already has it
        return result

    # Extract action phrases from beat
    action_phrases = extract_beat_actions(beat_desc)
    props = extract_key_props(beat_desc)

    # Build injection text
    # Get primary character name for the action
    characters = shot.get("characters", [])
    char_name = characters[0] if characters else ""

    # Inject into nano_prompt (BEFORE negative constraints)
    action_text = beat_desc
    if len(action_text) > 200:
        action_text = action_text[:200]

    nano_injection = f"Character action: {action_text}."

    # Find good injection point: after character description, before negatives
    # Look for "NO " as start of negative block
    no_pos = nano.find("NO ")
    if no_pos > 50:
        # Inject before the negatives
        shot["nano_prompt"] = nano[:no_pos] + nano_injection + " " + nano[no_pos:]
    else:
        # Inject at end
        shot["nano_prompt"] = nano + " " + nano_injection

    # Inject into ltx_motion_prompt
    ltx_verbs = [p.lower() for p in action_phrases[:3]]
    if ltx_verbs:
        ltx_injection = f"character performs: {', '.join(ltx_verbs)}, key motion: physical action."
        if "character performs:" not in ltx.lower():
            shot["ltx_motion_prompt"] = ltx + " " + ltx_injection

    # Inject props
    if props:
        prop_text = f"Key props visible: {', '.join(props)}."
        if not any(p in nano.lower() for p in props[:2]):
            shot["nano_prompt"] += " " + prop_text

    result["injected"] = True
    result["action"] = action_text
    result["props"] = props

    return result


# ============================================================
# CHECK 2: DIALOGUE MARKER ENFORCEMENT
# ============================================================

def enforce_dialogue_markers(shot: dict) -> dict:
    """
    Ensure all shots with dialogue have proper markers in LTX.
    Returns dict with enforcement details.
    """
    result = {"enforced": False, "had_dialogue": False, "marker_added": False}

    dialogue = (shot.get("dialogue_text", "") or
                shot.get("dialogue", "") or "")

    if not dialogue:
        return result

    result["had_dialogue"] = True

    ltx = shot.get("ltx_motion_prompt", "")

    # Check for existing markers
    has_marker = ("character speaks:" in ltx.lower() or
                  "speaks:" in ltx.lower() or
                  "speaking" in ltx.lower())

    if has_marker:
        result["enforced"] = True
        return result

    # Extract speaker and first line
    speaker = ""
    line = dialogue[:80]

    # Try to extract speaker from "CHARACTER: line" format
    dlg_match = re.match(r'([A-Z][A-Z\s]+?):\s*(.*)', dialogue)
    if dlg_match:
        speaker = dlg_match.group(1).strip()
        line = dlg_match.group(2).strip()[:80]

    # Build speaking direction
    if speaker:
        speak_dir = f"character speaks: {speaker} delivers dialogue with emotion, mouth moving naturally, expressive face."
    else:
        speak_dir = f"character speaks: delivers dialogue with emotion, mouth moving naturally."

    shot["ltx_motion_prompt"] = ltx + " " + speak_dir

    # Also add to nano (lip sync hint)
    nano = shot.get("nano_prompt", "")
    if speaker and speaker.lower() not in nano.lower():
        pass  # Character already in prompt

    result["enforced"] = True
    result["marker_added"] = True

    return result


# ============================================================
# CHECK 3: STORY SPECIFICITY SCORING
# ============================================================

def score_story_specificity(shot: dict, beat: dict = None) -> dict:
    """
    Score how much actual story content a prompt contains (vs generic template).
    Returns dict with score (0-100) and flags.
    """
    nano = shot.get("nano_prompt", "")
    nano_lower = nano.lower()

    score = 0
    flags = []

    # +20: Has character action from script
    if "character action:" in nano_lower or "character performs:" in nano_lower:
        score += 20
    else:
        flags.append("NO_ACTION_MARKER")

    # +15: Has specific physical verbs (not just atmosphere)
    action_count = sum(1 for v in ACTION_VERBS if v in nano_lower)
    if action_count >= 2:
        score += 15
    elif action_count >= 1:
        score += 8
    else:
        flags.append("NO_PHYSICAL_VERBS")

    # +15: Has dialogue reference for dialogue shots
    dialogue = shot.get("dialogue_text", shot.get("dialogue", ""))
    if dialogue:
        if "speaks" in nano_lower or "dialogue" in nano_lower or "says" in nano_lower:
            score += 15
        else:
            flags.append("DIALOGUE_NOT_IN_NANO")
    else:
        score += 15  # N/A — no dialogue expected

    # +15: Has props/objects from scene
    props = extract_key_props(nano)
    if len(props) >= 2:
        score += 15
    elif len(props) >= 1:
        score += 8
    else:
        flags.append("NO_PROPS")

    # +10: Has location atmosphere (not just "INT. LOCATION")
    atmo_words = ["shadow", "candle", "light", "dark", "cold", "warm",
                   "rain", "wind", "dust", "smoke", "fog", "mist",
                   "stone", "wood", "metal", "glass", "window"]
    atmo_count = sum(1 for w in atmo_words if w in nano_lower)
    if atmo_count >= 3:
        score += 10
    elif atmo_count >= 1:
        score += 5
    else:
        flags.append("NO_ATMOSPHERE")

    # +10: Has emotional direction
    emotion_words = ["fear", "dread", "tension", "grief", "hope", "desperate",
                     "determined", "curious", "anxious", "calm", "fierce",
                     "haunted", "vulnerable", "defiant", "resigned"]
    if any(w in nano_lower for w in emotion_words):
        score += 10
    else:
        flags.append("NO_EMOTION_DIRECTION")

    # +15: Beat alignment (if beat provided)
    if beat:
        beat_desc = beat.get("description", "").lower()
        beat_words = set(beat_desc.split()) - {"the", "a", "an", "in", "on", "at", "to", "of", "and", "with"}
        nano_words = set(nano_lower.split())
        overlap = beat_words & nano_words - NOT_ACTIONS
        if len(overlap) >= 5:
            score += 15
        elif len(overlap) >= 3:
            score += 10
        elif len(overlap) >= 1:
            score += 5
        else:
            flags.append("NO_BEAT_ALIGNMENT")
    else:
        score += 10  # Partial credit if no beat to compare

    return {
        "score": min(score, 100),
        "grade": "A" if score >= 80 else "B" if score >= 60 else "C" if score >= 40 else "D" if score >= 20 else "F",
        "flags": flags,
    }


# ============================================================
# CHECK 4: BEAT COVERAGE VALIDATION
# ============================================================

def validate_beat_coverage(shots: List[dict], beats: List[dict]) -> dict:
    """
    Check that every story beat has at least one shot covering it.
    Returns coverage report.
    """
    covered_beats = set()
    uncovered_beats = []

    for beat in beats:
        beat_num = beat.get("beat_number", 0)
        beat_desc = beat.get("description", "").lower()
        beat_type = beat.get("beat_type", "")

        # Check if any shot covers this beat
        beat_covered = False
        for shot in shots:
            nano = shot.get("nano_prompt", "").lower()

            # Check beat_id mapping
            shot_beat = shot.get("beat_id", "")
            if shot_beat and str(beat_num) in shot_beat:
                beat_covered = True
                break

            # Check content overlap
            beat_words = set(beat_desc.split()) - {"the", "a", "an", "in", "on", "at"}
            nano_words = set(nano.split())
            overlap = beat_words & nano_words
            if len(overlap) >= 3:
                beat_covered = True
                break

        if beat_covered:
            covered_beats.add(beat_num)
        else:
            uncovered_beats.append({
                "beat_number": beat_num,
                "type": beat_type,
                "description": beat.get("description", "")[:100],
                "characters": beat.get("characters", []),
            })

    total = len(beats)
    covered = len(covered_beats)

    return {
        "total_beats": total,
        "covered": covered,
        "coverage_pct": round(covered / total * 100) if total else 100,
        "uncovered": uncovered_beats,
        "grade": "A" if covered == total else "B" if covered >= total * 0.8 else "C",
    }


# ============================================================
# CHECK 5: EMOTIONAL ARC CONTINUITY
# ============================================================

def validate_emotional_arc(shots: List[dict], beats: List[dict]) -> dict:
    """
    Validate emotional progression is smooth (no sudden jumps).
    Returns arc report.
    """
    arc = []
    jumps = []

    for i, shot in enumerate(shots):
        # Get emotion from beat or shot metadata
        beat_id = shot.get("beat_id", "")
        tone = ""

        # Try to find matching beat
        for beat in beats:
            if str(beat.get("beat_number", "")) in beat_id:
                tone = beat.get("emotional_tone", "")
                break

        if not tone:
            tone = shot.get("emotional_tone", shot.get("emotion", "neutral"))

        intensity = EMOTION_INTENSITY.get(tone.lower(), 3)
        arc.append({"shot_id": shot.get("shot_id", ""), "tone": tone, "intensity": intensity})

        # Check for jumps (>4 intensity change)
        if i > 0 and abs(intensity - arc[i-1]["intensity"]) > 4:
            jumps.append({
                "from_shot": arc[i-1]["shot_id"],
                "to_shot": shot.get("shot_id", ""),
                "from_tone": arc[i-1]["tone"],
                "to_tone": tone,
                "delta": abs(intensity - arc[i-1]["intensity"]),
            })

    return {
        "arc_length": len(arc),
        "jumps": jumps,
        "jump_count": len(jumps),
        "smoothness": "smooth" if not jumps else "choppy" if len(jumps) > 2 else "minor_jumps",
        "arc_summary": [(a["shot_id"], a["tone"], a["intensity"]) for a in arc],
    }


# ============================================================
# CHECK 6: LOCATION ATMOSPHERE INJECTION
# ============================================================

def inject_location_atmosphere(shot: dict, scene_id: str) -> dict:
    """
    Inject scene-specific atmosphere keywords if missing.
    Uses shot's actual location, not just scene default.
    Returns injection details.
    """
    result = {"injected": False, "keywords_added": []}

    sid = scene_id[:3] if scene_id else ""

    # Check if this shot is at a DIFFERENT location (e.g., Lawyer intercut)
    shot_location = (shot.get("location", "") or "").upper()
    if "LAW OFFICE" in shot_location or "OFFICE" in shot_location:
        # Use law office atmosphere, not scene default
        return result  # Law office shots don't need apartment atmosphere

    atmo = SCENE_ATMOSPHERES.get(sid)
    if not atmo:
        return result

    nano = shot.get("nano_prompt", "")
    nano_lower = nano.lower()

    # Check which atmosphere keywords are missing
    missing = []
    for kw in atmo["keywords"]:
        if kw.lower() not in nano_lower:
            # Check if at least the key noun is present
            key_noun = kw.split()[-1]
            if key_noun.lower() not in nano_lower:
                missing.append(kw)

    if not missing:
        return result

    # Inject up to 2 atmosphere keywords
    inject_kws = missing[:2]
    atmo_text = f"Environment: {', '.join(inject_kws)}."

    # Find injection point: after location line, before character
    lines = nano.split(". ")
    if len(lines) > 1:
        # Inject after first sentence (usually the location/shot type line)
        shot["nano_prompt"] = lines[0] + ". " + atmo_text + " " + ". ".join(lines[1:])
    else:
        shot["nano_prompt"] = nano + " " + atmo_text

    result["injected"] = True
    result["keywords_added"] = inject_kws

    return result


# ============================================================
# MASTER FUNCTION: enrich_with_script_insight
# ============================================================

def enrich_with_script_insight(
    shots: List[dict],
    story_bible: dict = None,
    story_bible_path: str = None,
) -> dict:
    """
    Run all 6 script insight checks on shots.
    Modifies shots IN-PLACE with script content.

    Args:
        shots: list of shot dicts
        story_bible: pre-loaded story bible dict
        story_bible_path: path to story_bible.json (loaded if dict not provided)

    Returns:
        Comprehensive report dict
    """
    # Load story bible
    if not story_bible and story_bible_path:
        try:
            with open(story_bible_path) as f:
                story_bible = json.load(f)
        except Exception as e:
            logger.warning(f"[SCRIPT-INSIGHT] Could not load story bible: {e}")
            story_bible = {}

    if not story_bible:
        story_bible = {}

    # Build beat lookup: scene_id → beats
    scene_beats = {}
    for scene in story_bible.get("scenes", []):
        sid = scene.get("scene_id", "")[:3]
        scene_beats[sid] = scene.get("beats", [])

    # Stats
    report = {
        "total_shots": len(shots),
        "actions_injected": 0,
        "dialogue_enforced": 0,
        "dialogue_markers_added": 0,
        "atmosphere_injected": 0,
        "specificity_scores": [],
        "beat_coverage": {},
        "emotional_arc": {},
        "shot_details": [],
    }

    # Group shots by scene
    scene_groups = {}
    for shot in shots:
        sid = shot.get("scene_id", "")[:3]
        if not sid:
            sid = shot.get("shot_id", "").split("_")[0]
        if sid not in scene_groups:
            scene_groups[sid] = []
        scene_groups[sid].append(shot)

    # Process each shot
    for shot in shots:
        shot_id = shot.get("shot_id", "")
        sid = shot.get("scene_id", "")[:3] or shot_id.split("_")[0]
        beats = scene_beats.get(sid, [])

        # Find matching beat (proportional mapping)
        scene_shots = scene_groups.get(sid, [])
        shot_idx = scene_shots.index(shot) if shot in scene_shots else 0
        n_beats = len(beats)
        n_shots = len(scene_shots)

        beat = None
        if n_beats > 0 and n_shots > 0:
            beat_idx = int(shot_idx * n_beats / n_shots)
            beat_idx = min(beat_idx, n_beats - 1)
            beat = beats[beat_idx]

        shot_detail = {"shot_id": shot_id, "scene": sid}

        # CHECK 1: Beat action injection
        action_result = inject_beat_actions(shot, beat)
        if action_result["injected"] and action_result["action"]:
            report["actions_injected"] += 1
        shot_detail["action"] = action_result

        # CHECK 2: Dialogue marker enforcement
        dlg_result = enforce_dialogue_markers(shot)
        if dlg_result["had_dialogue"]:
            report["dialogue_enforced"] += 1
            if dlg_result["marker_added"]:
                report["dialogue_markers_added"] += 1
        shot_detail["dialogue"] = dlg_result

        # CHECK 3: Story specificity scoring
        spec_result = score_story_specificity(shot, beat)
        report["specificity_scores"].append(spec_result["score"])
        shot_detail["specificity"] = spec_result

        # CHECK 6: Location atmosphere
        atmo_result = inject_location_atmosphere(shot, sid)
        if atmo_result["injected"]:
            report["atmosphere_injected"] += 1
        shot_detail["atmosphere"] = atmo_result

        report["shot_details"].append(shot_detail)

    # CHECK 4: Beat coverage per scene
    for sid, scene_shot_list in scene_groups.items():
        beats = scene_beats.get(sid, [])
        if beats:
            coverage = validate_beat_coverage(scene_shot_list, beats)
            report["beat_coverage"][sid] = coverage

    # CHECK 5: Emotional arc per scene
    for sid, scene_shot_list in scene_groups.items():
        beats = scene_beats.get(sid, [])
        if beats:
            arc = validate_emotional_arc(scene_shot_list, beats)
            report["emotional_arc"][sid] = arc

    # Compute averages
    scores = report["specificity_scores"]
    report["avg_specificity"] = round(sum(scores) / len(scores)) if scores else 0
    report["min_specificity"] = min(scores) if scores else 0
    report["max_specificity"] = max(scores) if scores else 0

    grade_map = {s: ("A" if s >= 80 else "B" if s >= 60 else "C" if s >= 40 else "D" if s >= 20 else "F")
                 for s in scores}
    report["grade_distribution"] = {
        "A": sum(1 for s in scores if s >= 80),
        "B": sum(1 for s in scores if 60 <= s < 80),
        "C": sum(1 for s in scores if 40 <= s < 60),
        "D": sum(1 for s in scores if 20 <= s < 40),
        "F": sum(1 for s in scores if s < 20),
    }

    logger.info(
        f"[SCRIPT-INSIGHT] Processed {len(shots)} shots: "
        f"actions={report['actions_injected']}, "
        f"dialogue_markers={report['dialogue_markers_added']}, "
        f"atmosphere={report['atmosphere_injected']}, "
        f"avg_score={report['avg_specificity']}"
    )

    return report


# ============================================================
# STANDALONE TEST / CLI
# ============================================================

if __name__ == "__main__":
    import sys

    project_dir = sys.argv[1] if len(sys.argv) > 1 else "pipeline_outputs/ravencroft_v17"

    # Load data
    sp_path = os.path.join(project_dir, "shot_plan_v21_clean.json")
    if not os.path.exists(sp_path):
        sp_path = os.path.join(project_dir, "shot_plan.json")

    sb_path = os.path.join(project_dir, "story_bible.json")

    sp = json.load(open(sp_path))
    shots = [s for s in sp.get("shots", [])
             if s.get("shot_id", "").split("_")[0] in ("001", "002", "003")]

    print(f"Script Insight Engine — Testing on {len(shots)} shots")
    print(f"Shot plan: {os.path.basename(sp_path)}")
    print(f"Story bible: {os.path.basename(sb_path)}")
    print("=" * 70)

    report = enrich_with_script_insight(shots, story_bible_path=sb_path)

    # Print report
    print(f"\n{'='*70}")
    print("SCRIPT INSIGHT REPORT")
    print(f"{'='*70}")
    print(f"Total shots: {report['total_shots']}")
    print(f"Actions injected: {report['actions_injected']}")
    print(f"Dialogue markers added: {report['dialogue_markers_added']}")
    print(f"Atmosphere injected: {report['atmosphere_injected']}")
    print(f"Avg specificity: {report['avg_specificity']}/100")
    print(f"Min specificity: {report['min_specificity']}")
    print(f"Grade distribution: {report['grade_distribution']}")

    # Beat coverage
    print(f"\nBEAT COVERAGE:")
    for sid, cov in report["beat_coverage"].items():
        print(f"  Scene {sid}: {cov['covered']}/{cov['total_beats']} beats covered ({cov['coverage_pct']}%) — Grade {cov['grade']}")
        for ub in cov["uncovered"]:
            print(f"    ❌ Beat {ub['beat_number']}: {ub['description']}")

    # Emotional arc
    print(f"\nEMOTIONAL ARC:")
    for sid, arc in report["emotional_arc"].items():
        print(f"  Scene {sid}: {arc['smoothness']} ({arc['jump_count']} jumps)")
        for j in arc["jumps"]:
            print(f"    ⚠️  {j['from_shot']} ({j['from_tone']}) → {j['to_shot']} ({j['to_tone']}) delta={j['delta']}")

    # Per-shot details
    print(f"\nPER-SHOT DETAIL:")
    for detail in report["shot_details"]:
        sid = detail["shot_id"]
        spec = detail["specificity"]
        action = detail["action"]
        dlg = detail["dialogue"]
        atmo = detail["atmosphere"]

        markers = []
        if action["injected"] and action["action"]:
            markers.append("📝ACTION")
        if dlg["marker_added"]:
            markers.append("🗣️SPEAK")
        if atmo["injected"]:
            markers.append("🌫️ATMO")

        flags = spec.get("flags", [])
        flag_str = " ".join(f"⚠️{f}" for f in flags) if flags else "✅"

        print(f"  {sid} | Score={spec['score']}/{spec['grade']} | {' '.join(markers) if markers else '—'} | {flag_str}")

    # Show sample enriched prompts
    print(f"\n{'='*70}")
    print("SAMPLE ENRICHED PROMPTS (after script insight)")
    print(f"{'='*70}")
    for shot in shots[:3]:
        print(f"\n--- {shot['shot_id']} ({len(shot['nano_prompt'])} chars) ---")
        print(shot['nano_prompt'][:400])
        print("...")
