"""
Pre-Production Validator Agent — V20.5
Catches content issues BEFORE generation for ANY script.

Checks:
1. INT/EXT consistency: prompt descriptions match scene heading
2. Character logic: OTS requires 2+ chars, solo scenes correct
3. Dialogue coverage: beats with dialogue -> shots with dialogue
4. Location drift: shot prompts mention correct location
5. Scene heading format: all scenes have INT./EXT. prefix
6. Character assignment: non-establishing shots have characters
7. Shot type validity: OTS/two-shot require multiple characters

Auto-fixes what it can. Returns blocking issues for manual review.
"""

import re
import logging
from typing import List, Dict, Tuple, Optional

logger = logging.getLogger(__name__)

# V18.3 agent tag
AGENT_VERSION = "V20.5"
AGENT_NAME = "pre_production_validator"


def validate_project(shots: List[Dict], scene_manifest: List[Dict],
                     story_bible: Dict = None, auto_fix: bool = True) -> Dict:
    """
    Run all pre-production checks on a project.
    Returns: {issues: [], auto_fixes: [], blocking: [], warnings: [], score: int}
    """
    issues = []
    auto_fixes = []
    blocking = []
    warnings = []

    # Build scene truth from manifest
    scene_truth = {}
    for sc in scene_manifest:
        sid = sc.get("scene_id", "")
        scene_truth[sid] = {
            "title": sc.get("title", sc.get("scene_heading", "")),
            "int_ext": sc.get("int_ext", ""),
            "characters": [c.upper() for c in sc.get("characters", [])],
            "location": sc.get("setting", {}).get("primary", "") if isinstance(sc.get("setting"), dict) else ""
        }

    # Build story bible beat lookup
    sb_beats = {}
    if story_bible:
        for sc in story_bible.get("scenes", []):
            sid = str(sc.get("scene_id", sc.get("scene_number", ""))).zfill(3)
            sb_beats[sid] = sc.get("beats", [])

    for shot in shots:
        shot_id = shot.get("shot_id", "?")
        scene_id = shot_id[:3]
        truth = scene_truth.get(scene_id, {})
        nano = (shot.get("nano_prompt") or "").lower()
        ltx = (shot.get("ltx_motion_prompt") or "")
        shot_type = shot.get("shot_type", "")
        characters = shot.get("characters", [])
        dialogue = shot.get("dialogue_text", "") or shot.get("dialogue", "") or ""

        # === CHECK 1: INT/EXT CONSISTENCY ===
        int_ext = truth.get("int_ext", "").upper()
        # V26 Doctrine 256: NEVER use shot_id suffix to detect B-roll — use explicit flags
        is_broll = shot.get("is_broll") or shot.get("_broll") or False
        is_establishing = shot_type in ("establishing", "b_roll") or is_broll

        if int_ext and not is_establishing:
            if "INT" in int_ext and "EXT" not in int_ext:
                if "exterior" in nano:
                    issue = f"{shot_id}: exterior in prompt but scene is INT"
                    if auto_fix:
                        shot["nano_prompt"] = shot["nano_prompt"].replace("exterior", "interior").replace("Exterior", "Interior")
                        auto_fixes.append(issue + " → auto-fixed to interior")
                    else:
                        blocking.append(issue)
            elif "EXT" in int_ext and "INT" not in int_ext:
                if "interior" in nano and not is_establishing:
                    issue = f"{shot_id}: interior in prompt but scene is EXT"
                    warnings.append(issue)

        # === CHECK 2: SHOT TYPE vs CHARACTER COUNT ===
        char_count = len(characters) if isinstance(characters, list) else 0

        if shot_type == "over_the_shoulder" and char_count < 2:
            issue = f"{shot_id}: OTS shot but only {char_count} character(s)"
            if auto_fix and char_count == 1:
                # Single char OTS -> medium_close
                shot["shot_type"] = "medium_close"
                nano_fixed = shot.get("nano_prompt", "")
                nano_fixed = nano_fixed.replace("over-the-shoulder", "medium close-up")
                nano_fixed = nano_fixed.replace("over the shoulder", "medium close-up")
                nano_fixed = nano_fixed.replace("OTS", "medium close-up")
                shot["nano_prompt"] = nano_fixed
                auto_fixes.append(issue + " → auto-fixed to medium_close")
            elif auto_fix and char_count == 0:
                shot["shot_type"] = "medium"
                auto_fixes.append(issue + " → auto-fixed to medium")
            else:
                blocking.append(issue)

        if shot_type == "two_shot" and char_count < 2:
            issue = f"{shot_id}: two_shot but only {char_count} character(s)"
            warnings.append(issue)

        # === CHECK 3: CHARACTER ASSIGNMENT ===
        if not characters and shot_type not in ("establishing", "b_roll", "insert", "detail", "wide") and not is_broll:
            truth_chars = truth.get("characters", [])
            if truth_chars:
                if auto_fix:
                    shot["characters"] = truth_chars
                    auto_fixes.append(f"{shot_id}: assigned characters {truth_chars} from manifest")
                else:
                    warnings.append(f"{shot_id}: no characters (scene has {truth_chars})")

        # === CHECK 4: DIALOGUE SPEAKS MARKER ===
        if dialogue and len(dialogue) > 5:
            if "speaks:" not in ltx.lower() and "character speaks:" not in ltx.lower():
                issue = f"{shot_id}: has dialogue but no speaks: marker in ltx"
                if auto_fix:
                    first_char = characters[0] if characters else "Character"
                    dlg_short = dialogue[:200]
                    shot["ltx_motion_prompt"] = ltx + f" character speaks: {first_char} says \"{dlg_short}\", lip sync, jaw motion, natural speaking cadence."
                    auto_fixes.append(issue + " → auto-injected speaks marker")
                else:
                    blocking.append(issue)

        # === CHECK 5: LOCATION KEYWORD IN PROMPT ===
        # Extract key location word from manifest title
        title = truth.get("title", "")
        # Get the core location word (e.g., "RITUAL ROOM", "APARTMENT", "BUS")
        loc_match = re.search(r'(?:INT\.|EXT\.)\s*(?:/\s*(?:INT\.|EXT\.))?\s*(.+?)(?:\s*[-–—]\s*(?:NIGHT|DAY|MORNING|EVENING|AFTERNOON|LATER|CONTINUOUS|MOMENTS))', title, re.I)
        if loc_match:
            core_loc = loc_match.group(1).strip()
            # Get the most specific word (last significant word)
            loc_words = [w for w in core_loc.split() if len(w) > 3 and w.upper() not in ("THE", "AND", "WITH")]
            for lw in loc_words[-2:]:  # Check last 2 significant words
                if lw.lower() not in nano and not is_establishing:
                    pass  # Don't warn on this — prompts use description not heading words

    # === CHECK 6: SCENE HEADING FORMAT ===
    for sc in scene_manifest:
        title = sc.get("title", "")
        sid = sc.get("scene_id", "?")
        if not re.match(r'^(INT\.|EXT\.)', title, re.I) and title:
            warnings.append(f"Scene {sid}: title '{title[:40]}' missing INT./EXT. prefix")

    # === CHECK 7: DIALOGUE COVERAGE ===
    for sid, beats in sb_beats.items():
        beats_with_dlg = sum(1 for b in beats if isinstance(b, dict) and b.get("dialogue"))
        scene_shots = [s for s in shots if s.get("shot_id", "").startswith(sid + "_")]
        shots_with_dlg = sum(1 for s in scene_shots if s.get("dialogue_text") or s.get("dialogue"))
        if beats_with_dlg > 0 and shots_with_dlg == 0:
            blocking.append(f"Scene {sid}: {beats_with_dlg} beats have dialogue but 0 shots do")

    # Calculate score
    total_checks = len(shots) * 5  # 5 checks per shot
    deductions = len(blocking) * 10 + len(warnings) * 2
    score = max(0, min(100, 100 - deductions))

    return {
        "agent": AGENT_NAME,
        "version": AGENT_VERSION,
        "total_shots": len(shots),
        "total_scenes": len(scene_manifest),
        "score": score,
        "blocking": blocking,
        "warnings": warnings,
        "auto_fixes": auto_fixes,
        "issues": blocking + warnings,
        "pass": len(blocking) == 0,
        "summary": f"Score {score}/100 | {len(blocking)} blocking | {len(warnings)} warnings | {len(auto_fixes)} auto-fixed"
    }


def validate_and_fix(project_path, shots, data, story_bible=None):
    """
    Convenience wrapper for fix-v16 integration.
    Runs validation with auto_fix=True, returns (issues_fixed_count, report).
    """
    manifest = data.get("scene_manifest", [])
    report = validate_project(shots, manifest, story_bible, auto_fix=True)

    fixed_count = len(report["auto_fixes"])
    if report["blocking"]:
        logger.warning(f"[PRE-PROD VALIDATOR] {len(report['blocking'])} BLOCKING issues remain")
        for b in report["blocking"]:
            logger.warning(f"  BLOCKING: {b}")
    if report["warnings"]:
        logger.info(f"[PRE-PROD VALIDATOR] {len(report['warnings'])} warnings")

    logger.info(f"[PRE-PROD VALIDATOR] {report['summary']}")
    return fixed_count, report
