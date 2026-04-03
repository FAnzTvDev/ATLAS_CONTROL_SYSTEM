"""
ATLAS V18.3 — Script Fidelity Agent
=====================================
Validates that shot prompts (nano_prompt, ltx_motion_prompt) accurately reflect
what the SCRIPT actually says should happen in each beat.

The LOA checks technical correctness (refs, locations, timing).
THIS agent checks CREATIVE FIDELITY — does the prompt match the story?

Key checks:
1. ACTION FIDELITY — beat says "picks up phone" → prompt must reference phone
2. DIALOGUE FIDELITY — beat has dialogue → prompt must include it or reference it
3. PROP/OBJECT FIDELITY — beat mentions letter, envelope, phone → prompt should too
4. GENERIC PROMPT DETECTION — flags prompts that are just templates with no story specifics
5. CHARACTER ACTION MATCHING — beat says character X does Y → prompt should show X doing Y

Returns per-shot: {fidelity_score, issues[], suggested_fixes[]}
"""

import json
import re
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("atlas.script_fidelity")

# ─── Action verb extraction patterns ───
# These are the kinds of physical actions that MUST appear in visual prompts
ACTION_VERBS = {
    "phone": ["picks up phone", "dials", "answers phone", "phone call", "calling", "holds phone", "on the phone", "speaking on phone", "phone rings"],
    "letter": ["reads letter", "opens letter", "reading letter", "holds letter", "letter in hand", "unfolds letter"],
    "envelope": ["opens envelope", "sealed envelope", "tears open", "wax seal", "opening envelope"],
    "writing": ["writes", "writing", "pen in hand", "scribbling", "taking notes", "signs"],
    "walking": ["walks", "walking", "approaches", "enters", "exits", "steps", "crosses", "strides"],
    "sitting": ["sits", "sitting", "seated", "slumps", "leans back"],
    "standing": ["stands", "standing", "rises", "gets up"],
    "door": ["opens door", "closes door", "knocks", "enters through", "doorway"],
    "looking": ["looks at", "gazes", "stares", "examines", "studies", "peers"],
    "reaching": ["reaches for", "grabs", "picks up", "takes", "holds"],
    "emotional": ["cries", "tears", "trembles", "shakes", "gasps", "freezes"],
    "drinking": ["drinks", "sips", "coffee", "tea", "glass", "pours"],
}

# Objects that should appear in visual prompts when mentioned in beats
KEY_PROPS = [
    "phone", "letter", "envelope", "key", "keys", "book", "document", "map",
    "candle", "lantern", "flashlight", "torch", "knife", "weapon", "gun",
    "photograph", "photo", "picture", "portrait", "mirror", "clock", "watch",
    "bag", "suitcase", "luggage", "car", "vehicle", "door", "window",
    "cup", "mug", "coffee", "glass", "bottle", "food", "newspaper",
    "ring", "necklace", "pendant", "locket", "diary", "journal",
    "computer", "laptop", "screen", "tablet",
]


def extract_key_actions(text: str) -> List[str]:
    """Extract key action phrases from a beat description."""
    if not text:
        return []
    text_lower = text.lower()
    found = []
    for category, patterns in ACTION_VERBS.items():
        for pattern in patterns:
            if pattern.lower() in text_lower:
                found.append(f"{category}:{pattern}")
                break  # One per category
    return found


def extract_key_props(text: str) -> List[str]:
    """Extract key props/objects from a beat description."""
    if not text:
        return []
    text_lower = text.lower()
    found = []
    for prop in KEY_PROPS:
        # Word boundary check to avoid "letter" matching "letterbox" etc.
        if re.search(r'\b' + re.escape(prop) + r'\b', text_lower):
            found.append(prop)
    return found


def extract_dialogue_keywords(dialogue: str) -> List[str]:
    """Extract key words from dialogue that should inform the visual prompt."""
    if not dialogue:
        return []
    # Remove character names and stage directions
    clean = re.sub(r'[A-Z]+:', '', dialogue)
    clean = re.sub(r'\(.*?\)', '', clean)
    clean = clean.strip('" \'')
    # Get meaningful words (4+ chars, not common words)
    stopwords = {"this", "that", "with", "from", "have", "been", "were", "they",
                 "your", "what", "when", "will", "would", "could", "should", "about",
                 "their", "there", "here", "just", "more", "some", "very", "much",
                 "than", "then", "also", "into"}
    words = [w.lower().strip('.,!?;:') for w in clean.split() if len(w) >= 4]
    return [w for w in words if w not in stopwords][:10]


def check_prompt_contains_action(prompt: str, actions: List[str]) -> Tuple[List[str], List[str]]:
    """Check which actions are present/missing in a prompt."""
    if not prompt:
        return [], actions
    prompt_lower = prompt.lower()
    found = []
    missing = []
    for action in actions:
        # Extract the actual action text after the category:
        category, phrase = action.split(":", 1) if ":" in action else ("", action)
        # Check if the action concept is in the prompt
        action_words = phrase.lower().split()
        # At least the key noun should be present
        key_word = category  # "phone", "letter", "envelope", etc.
        if key_word and key_word in prompt_lower:
            found.append(action)
        elif any(w in prompt_lower for w in action_words if len(w) >= 4):
            found.append(action)
        else:
            missing.append(action)
    return found, missing


def check_prompt_contains_props(prompt: str, props: List[str]) -> Tuple[List[str], List[str]]:
    """Check which props are present/missing in a prompt."""
    if not prompt:
        return [], props
    prompt_lower = prompt.lower()
    found = []
    missing = []
    for prop in props:
        if prop.lower() in prompt_lower:
            found.append(prop)
        else:
            missing.append(prop)
    return found, missing


def detect_generic_prompt(nano_prompt: str, ltx_prompt: str) -> List[str]:
    """Detect if prompts are generic templates with no story specifics."""
    issues = []
    if not nano_prompt:
        issues.append("nano_prompt is EMPTY")
        return issues

    nano_lower = nano_prompt.lower()

    # Check for overly generic patterns
    generic_patterns = [
        (r"cinematic shot at \w+ --", "Generic 'Cinematic shot at LOCATION' template"),
        (r"delivering dialogue at", "Generic 'delivering dialogue' without specifying WHAT dialogue"),
        (r"processing what .+ said", "Generic 'processing what X said' without context"),
        (r"close-up reaction of .+\. subtle emotion", "Generic reaction template"),
        (r"atmospheric b-roll at", "Generic B-roll template without specific content"),
    ]
    for pattern, msg in generic_patterns:
        if re.search(pattern, nano_lower):
            issues.append(msg)

    # Check if nano_prompt has any character-specific ACTION (not just "at LOCATION")
    action_words = ["picks up", "opens", "reads", "holds", "dials", "answers",
                    "walks", "enters", "sits", "stands", "reaches", "looks at",
                    "pours", "drinks", "writes", "turns", "grabs", "places"]
    has_action = any(w in nano_lower for w in action_words)
    if not has_action and "establishing" not in nano_lower and "b-roll" not in nano_lower:
        issues.append("No specific CHARACTER ACTION found in nano_prompt")

    # Check LTX for generic motion
    if ltx_prompt:
        ltx_lower = ltx_prompt.lower()
        if "smooth camera motion, environmental detail" in ltx_lower:
            issues.append("LTX uses generic 'smooth camera motion, environmental detail' template")
        if "subtle breathing, lip movement" in ltx_lower and "phone" not in ltx_lower and "letter" not in ltx_lower:
            # Dialogue shot with no action reference
            pass  # This is okay for pure dialogue

    return issues


def build_suggested_fix(shot: Dict, beat: Dict, missing_actions: List[str],
                        missing_props: List[str]) -> Optional[Dict]:
    """Build a suggested prompt fix based on the beat description."""
    beat_desc = beat.get("description", "")
    beat_dialogue = beat.get("dialogue", "")
    shot_type = shot.get("shot_type", "medium")

    if not beat_desc and not beat_dialogue:
        return None

    suggestions = {}

    # Build nano_prompt suggestion incorporating beat actions
    if missing_actions or missing_props:
        action_text = beat_desc
        if missing_props:
            prop_list = ", ".join(missing_props[:3])
            suggestions["nano_prompt_add"] = f"Include: {action_text}. Key props: {prop_list}"
        else:
            suggestions["nano_prompt_add"] = f"Include action: {action_text}"

    # Build ltx_motion suggestion incorporating beat actions
    if missing_actions:
        action_descs = []
        for a in missing_actions:
            cat, phrase = a.split(":", 1) if ":" in a else ("", a)
            action_descs.append(phrase)
        suggestions["ltx_motion_add"] = f"Character motion: {', '.join(action_descs)}"

    if beat_dialogue and not shot.get("dialogue_text"):
        suggestions["dialogue_missing"] = beat_dialogue[:200]

    if suggestions:
        return {
            "shot_id": shot.get("shot_id", ""),
            "beat_description": beat_desc[:200],
            "beat_dialogue": beat_dialogue[:150],
            "suggestions": suggestions,
            "priority": "high" if missing_actions else "medium",
        }
    return None


def validate_scene_fidelity(shots: List[Dict], story_bible_scenes: List[Dict],
                            scene_id: str = None) -> Dict:
    """
    Validate script fidelity for shots against story bible.
    Returns {score, issues[], suggested_fixes[], per_shot: {shot_id: {...}}}
    """
    # Build beat lookup from story bible
    beat_lookup = {}  # beat_number → beat dict, per scene
    scene_beats = {}  # scene_id → [beats]

    for scene in story_bible_scenes:
        sid = scene.get("scene_id", str(scene.get("scene_number", "")))
        if sid and len(sid) < 3:
            sid = sid.zfill(3)
        beats = scene.get("beats", scene.get("story_beats", []))
        scene_beats[sid] = beats
        for beat in beats:
            bn = beat.get("beat_number", 0)
            beat_lookup[f"{sid}_beat_{bn}"] = beat

    # Filter shots if scene_id provided
    if scene_id:
        shots = [s for s in shots if s.get("shot_id", "").startswith(f"{scene_id}_")]

    results = {
        "scene_id": scene_id or "all",
        "total_shots": len(shots),
        "per_shot": {},
        "issues": [],
        "suggested_fixes": [],
        "summary": {
            "fidelity_pass": 0,
            "fidelity_warn": 0,
            "fidelity_fail": 0,
            "generic_prompts": 0,
            "missing_actions": 0,
            "missing_props": 0,
            "missing_dialogue": 0,
        }
    }

    for shot in shots:
        shot_id = shot.get("shot_id", "")
        beat_id = shot.get("beat_id", "")
        shot_type = shot.get("shot_type", "")
        nano = shot.get("nano_prompt", "") or ""
        ltx = shot.get("ltx_motion_prompt", "") or ""

        shot_result = {
            "shot_id": shot_id,
            "beat_id": beat_id,
            "shot_type": shot_type,
            "fidelity_score": 100,
            "issues": [],
            "beat_description": "",
            "beat_dialogue": "",
            "actions_found": [],
            "actions_missing": [],
            "props_found": [],
            "props_missing": [],
        }

        # Find matching beat
        beat = beat_lookup.get(beat_id, {})

        # If no direct beat match, try to find by scene_id + beat number
        if not beat and beat_id:
            # Try variations
            parts = beat_id.split("_")
            if len(parts) >= 3:
                scene_prefix = parts[0]
                beat_num = parts[-1]
                for key in beat_lookup:
                    if key.startswith(scene_prefix) and key.endswith(f"_{beat_num}"):
                        beat = beat_lookup[key]
                        break

        # If still no beat, try matching by scene's beat list order
        if not beat:
            scene_prefix = shot_id.split("_")[0] if "_" in shot_id else ""
            if scene_prefix in scene_beats:
                # Use shot_type to find most likely beat
                beats = scene_beats[scene_prefix]
                for b in beats:
                    bt = b.get("beat_type", "")
                    if bt == shot_type:
                        beat = b
                        break

        beat_desc = beat.get("description", "")
        beat_dialogue = beat.get("dialogue", "")
        shot_result["beat_description"] = beat_desc[:200]
        shot_result["beat_dialogue"] = beat_dialogue[:200]

        if not beat_desc and not beat_dialogue:
            shot_result["issues"].append("NO_BEAT_DATA: Cannot validate — no story bible beat found for this shot")
            shot_result["fidelity_score"] -= 10
            results["per_shot"][shot_id] = shot_result
            continue

        # ── Check 1: Action fidelity ──
        beat_actions = extract_key_actions(beat_desc)
        if beat_actions:
            found, missing = check_prompt_contains_action(nano + " " + ltx, beat_actions)
            shot_result["actions_found"] = found
            shot_result["actions_missing"] = missing
            if missing:
                penalty = min(40, len(missing) * 15)
                shot_result["fidelity_score"] -= penalty
                shot_result["issues"].append(
                    f"MISSING_ACTIONS: Beat says '{beat_desc[:80]}' but prompt missing: {', '.join(m.split(':')[0] for m in missing)}"
                )
                results["summary"]["missing_actions"] += 1

        # ── Check 2: Prop fidelity ──
        beat_props = extract_key_props(beat_desc + " " + beat_dialogue)
        if beat_props:
            found, missing = check_prompt_contains_props(nano + " " + ltx, beat_props)
            shot_result["props_found"] = found
            shot_result["props_missing"] = missing
            if missing:
                penalty = min(25, len(missing) * 8)
                shot_result["fidelity_score"] -= penalty
                shot_result["issues"].append(
                    f"MISSING_PROPS: Beat mentions [{', '.join(missing)}] but not in prompt"
                )
                results["summary"]["missing_props"] += 1

        # ── Check 3: Dialogue fidelity ──
        if beat_dialogue and shot_type in ["dialogue", "reaction", "close-up"]:
            shot_dlg = shot.get("dialogue_text", "") or shot.get("dialogue", "") or ""
            if not shot_dlg:
                shot_result["fidelity_score"] -= 20
                shot_result["issues"].append(
                    f"MISSING_DIALOGUE: Beat has dialogue '{beat_dialogue[:80]}' but shot has none"
                )
                results["summary"]["missing_dialogue"] += 1
            else:
                # Check if key dialogue words appear
                dlg_keywords = extract_dialogue_keywords(beat_dialogue)
                shot_dlg_lower = (shot_dlg + " " + nano + " " + ltx).lower()
                missing_kw = [w for w in dlg_keywords if w not in shot_dlg_lower]
                if len(missing_kw) > len(dlg_keywords) * 0.5:
                    shot_result["fidelity_score"] -= 10
                    shot_result["issues"].append(
                        f"DIALOGUE_DRIFT: Key words from beat dialogue not in prompt"
                    )

        # ── Check 4: Generic prompt detection ──
        generic_issues = detect_generic_prompt(nano, ltx)
        if generic_issues:
            penalty = min(30, len(generic_issues) * 10)
            shot_result["fidelity_score"] -= penalty
            for gi in generic_issues:
                shot_result["issues"].append(f"GENERIC: {gi}")
            results["summary"]["generic_prompts"] += 1

        # Clamp score
        shot_result["fidelity_score"] = max(0, min(100, shot_result["fidelity_score"]))

        # Classify
        if shot_result["fidelity_score"] >= 70:
            results["summary"]["fidelity_pass"] += 1
        elif shot_result["fidelity_score"] >= 40:
            results["summary"]["fidelity_warn"] += 1
        else:
            results["summary"]["fidelity_fail"] += 1

        # Build suggested fix
        if shot_result["fidelity_score"] < 70:
            fix = build_suggested_fix(
                shot, beat,
                shot_result.get("actions_missing", []),
                shot_result.get("props_missing", [])
            )
            if fix:
                results["suggested_fixes"].append(fix)

        results["per_shot"][shot_id] = shot_result

    # Overall score
    total = len(shots)
    if total > 0:
        avg_score = sum(r["fidelity_score"] for r in results["per_shot"].values()) / total
        results["overall_fidelity_score"] = round(avg_score, 1)
    else:
        results["overall_fidelity_score"] = 0

    return results


def run_script_fidelity_check(project_path: str, scene_id: str = None) -> Dict:
    """
    Convenience function: loads project data and runs fidelity check.
    """
    project_path = Path(project_path)

    # Load story bible
    sb_path = project_path / "story_bible.json"
    if not sb_path.exists():
        return {"error": "No story_bible.json found", "overall_fidelity_score": 0}

    with open(sb_path) as f:
        story_bible = json.load(f)
    scenes = story_bible.get("scenes", [])

    # Load shot plan
    sp_path = project_path / "shot_plan.json"
    if not sp_path.exists():
        return {"error": "No shot_plan.json found", "overall_fidelity_score": 0}

    with open(sp_path) as f:
        shot_plan = json.load(f)
    shots = shot_plan.get("shots", [])

    return validate_scene_fidelity(shots, scenes, scene_id=scene_id)


# ═══════════════════════════════════════════════════
# CLI usage
# ═══════════════════════════════════════════════════
if __name__ == "__main__":
    import sys
    project = sys.argv[1] if len(sys.argv) > 1 else "ravencroft_v17"
    scene = sys.argv[2] if len(sys.argv) > 2 else None

    base = Path(__file__).parent.parent / "pipeline_outputs" / project
    result = run_script_fidelity_check(str(base), scene_id=scene)

    print(f"\n{'='*60}")
    print(f"SCRIPT FIDELITY REPORT — {project} {'Scene ' + scene if scene else 'ALL'}")
    print(f"{'='*60}")
    print(f"Overall Score: {result.get('overall_fidelity_score', 0)}/100")
    print(f"Total Shots: {result.get('total_shots', 0)}")
    s = result.get("summary", {})
    print(f"  Pass (≥70): {s.get('fidelity_pass', 0)}")
    print(f"  Warn (40-69): {s.get('fidelity_warn', 0)}")
    print(f"  Fail (<40): {s.get('fidelity_fail', 0)}")
    print(f"  Generic prompts: {s.get('generic_prompts', 0)}")
    print(f"  Missing actions: {s.get('missing_actions', 0)}")
    print(f"  Missing props: {s.get('missing_props', 0)}")
    print(f"  Missing dialogue: {s.get('missing_dialogue', 0)}")

    # Show worst shots
    per_shot = result.get("per_shot", {})
    worst = sorted(per_shot.values(), key=lambda x: x.get("fidelity_score", 100))[:10]
    if worst:
        print(f"\n{'─'*60}")
        print("LOWEST FIDELITY SHOTS:")
        for w in worst:
            score = w.get("fidelity_score", 0)
            if score >= 70:
                continue
            print(f"\n  {w['shot_id']} — Score: {score}/100 ({w.get('shot_type', '')})")
            print(f"    Beat: {w.get('beat_description', 'none')[:100]}")
            if w.get("beat_dialogue"):
                print(f"    Dialogue: {w['beat_dialogue'][:80]}")
            for issue in w.get("issues", []):
                print(f"    ⚠️  {issue[:120]}")

    # Show suggested fixes
    fixes = result.get("suggested_fixes", [])
    if fixes:
        print(f"\n{'─'*60}")
        print(f"SUGGESTED FIXES ({len(fixes)} shots):")
        for f in fixes[:15]:
            print(f"\n  {f['shot_id']} [{f.get('priority', 'medium')}]")
            print(f"    Beat: {f.get('beat_description', '')[:100]}")
            for k, v in f.get("suggestions", {}).items():
                print(f"    → {k}: {v[:120]}")
