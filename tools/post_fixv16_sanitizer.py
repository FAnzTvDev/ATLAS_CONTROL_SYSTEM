#!/usr/bin/env python3
"""
POST-FIX-V16 SANITIZER — V22.1
================================
Run this AFTER every fix-v16 run to strip known contaminants that
fix-v16's enrichment pipeline re-injects.

ROOT CAUSE: fix-v16 runs cast trait injection from ai_actors_library.json,
which re-injects AI actor nationalities, camera brand names, and wrong
scene color grades. This sanitizer strips them all in one pass.

USAGE:
    python3 tools/post_fixv16_sanitizer.py ravencroft_v22

    # Or from server endpoint (add to orchestrator_server.py):
    # POST /api/v22/sanitize/{project}

WHAT IT STRIPS:
    1. AI actor nationalities (Italian, Nigerian, Korean, Japanese, etc.)
    2. AI actor names (Isabella Moretti, Sophia Chen, etc.)
    3. Camera brand names (ARRI, Alexa, RED DSMC, Sony Venice, etc.)
    4. Camera body model numbers (Alexa 35, RED Komodo, etc.)
    5. Cross-scene color grade contamination (pub grade in apartment, etc.)
    6. Film stock references (Kodak Vision3, Fuji Eterna, etc.)
    7. Age/nationality patterns (28-year-old, Italian descent, etc.)

WHAT IT PRESERVES:
    - All hand-crafted prompt content
    - Character descriptions (canonical names, appearance)
    - Scene-specific content (dialogue, action, atmosphere)
    - Wardrobe tags
    - Performance/speaks/reacts markers
    - Gold standard negatives (NO morphing, NO grid, etc.)

RULES:
    - NEVER changes shot count
    - NEVER changes shot IDs
    - NEVER removes character names or dialogue
    - NEVER modifies ltx_motion_prompt gold standard block
    - Creates backup before every run
    - Reports what it changed
"""

import json
import re
import os
import sys
import shutil
import logging
from datetime import datetime

logger = logging.getLogger("atlas.sanitizer")

# Try to import project config for dynamic project data
try:
    from core.project_config import get_project_config
    _HAS_CONFIG = True
except ImportError:
    _HAS_CONFIG = False


# ============================================================
# STRIP PATTERNS
# ============================================================

# AI Actor names from ai_actors_library.json — DEFAULT fallback for all projects
_DEFAULT_AI_ACTOR_NAMES = [
    r'Isabella\s+Moretti', r'Sophia\s+Chen', r'Marcus\s+Sterling',
    r'Elena\s+Vasquez', r'James\s+Thornton', r'Amara\s+Okafor',
    r'Liam\s+Fitzgerald', r'Natasha\s+Petrova', r'David\s+Kim',
    r'Olivia\s+Hart', r'Rafael\s+Santos', r'Priya\s+Mehta',
    r'Thomas\s+Wright', r'Yuki\s+Tanaka', r'Victoria\s+Reed',
    r'Charlotte\s+Beaumont', r'Nina\s+Volkov', r'Marcus\s+Stone',
    r'Dimitri\s+Volkov', r'Pierre\s+Laurent',
]

# Nationalities that come from AI actor descriptions
NATIONALITY_PATTERNS = [
    r'\bItalian\b(?!\s+(?:architecture|villa|countryside|wine|garden|marble|stone|renaissance|Gothic))',
    r'\bNigerian\b', r'\bKorean\b', r'\bJapanese\b', r'\bBrazilian\b',
    r'\bIndian\b(?!\s+(?:ocean|summer|ink))', r'\bChinese\s+descent\b',
    r'\bFrench\b(?!\s+(?:door|window|press|toast|quarter))',
    r'\bRussian\b(?!\s+(?:roulette|doll))',
    r'\bIrish\b(?!\s+(?:whiskey|coffee|pub|sea))',
    r'\bSwedish\b', r'\bGerman\b(?!\s+(?:shepherd|expressionism))',
    r'\bItalian-American\b',
]

# Camera brand names (bio bleed contract C)
CAMERA_BRANDS = [
    r'\bARRI\s+Alexa\s*\d*\b,?\s*',
    r'\bARRI\b,?\s*',
    r'\bAlexa\s*\d+\b,?\s*',
    r'\bRED\s+(?:DSMC|Komodo|Raptor|Monstro|Helium|Dragon|Ranger)\b,?\s*',
    r'\bSony\s+Venice\b,?\s*',
    r'\bPanavision\s+(?:Millennium|Genesis|DXL)\b,?\s*',
    r'\bCanon\s+C\d+\b,?\s*',
    r'\bBlackmagic\s+\w+\b,?\s*',
    r'Shot\s+on\s+(?:ARRI|RED|Sony|Canon|Blackmagic)\s+[^,.]+[,.]?\s*',
]

# Film stock references
FILM_STOCKS = [
    r'\bKodak\s+Vision\s*\d*\b[^.]*\.?\s*',
    r'\bFuji\s+Eterna\b[^.]*\.?\s*',
    r'\b(?:35mm|65mm|16mm)\s+film\s+stock\b,?\s*',
]

# Age patterns from AI actor descriptions
AGE_PATTERNS = [
    r'\b\d{2}-year-old\b,?\s*',
    r'\bage\s+\d{2}\b,?\s*',
    r'\bin\s+(?:her|his|their)\s+(?:early|mid|late)\s+\d{1,2}s\b',  # Strip — AI actor bio bleed (Contract C)
]

# Color grade contamination map: scene → forbidden color grade words
# These get injected when cinematic enricher uses wrong scene metadata
# DEFAULT fallback for all projects
_DEFAULT_COLOR_GRADE_CONTAMINATION = {
    '004': ['pub interior', 'pub lighting', 'tavern'],  # Evelyn's apartment is NOT a pub
    '002': ['manor', 'ritual', 'candlelight'],  # City apartment
    '003': ['manor', 'ritual', 'countryside'],  # Phone call (apartment/office)
    '005': ['pub', 'interior', 'manor'],  # Countryside driving
    '014': ['pub', 'manor', 'interior'],  # Coastal cliffs (exterior)
}


def sanitize_shot(shot, scene_id=None, ai_actor_names=None, color_contamination=None):
    """
    Sanitize a single shot dict IN-MEMORY (no disk I/O).

    V26 ROOT CAUSE 5 FIX: Called by the controller before locking prompts,
    so contaminants from fix-v16 enrichment never reach FAL.

    Args:
        shot: Shot dict (mutated in-place)
        scene_id: Override scene ID (falls back to shot["scene_id"])
        ai_actor_names: Custom actor name patterns (falls back to defaults)
        color_contamination: Custom color map (falls back to defaults)

    Returns:
        int: Number of contaminants stripped (0 means shot was clean)
    """
    if ai_actor_names is None:
        ai_actor_names = _DEFAULT_AI_ACTOR_NAMES
    if color_contamination is None:
        color_contamination = _DEFAULT_COLOR_GRADE_CONTAMINATION
    if scene_id is None:
        scene_id = shot.get('scene_id', '')

    total_fixes = 0

    for field in ['nano_prompt', 'nano_prompt_final', 'ltx_motion_prompt']:
        text = shot.get(field, '')
        if not text:
            continue
        original = text

        # 1. Strip AI actor names
        for pat in ai_actor_names:
            new_text = re.sub(pat, '', text, flags=re.IGNORECASE)
            if new_text != text:
                total_fixes += 1
                text = new_text

        # 2. Strip nationalities
        for pat in NATIONALITY_PATTERNS:
            new_text = re.sub(pat, '', text)
            if new_text != text:
                total_fixes += 1
                text = new_text

        # 3. Strip camera brands
        for pat in CAMERA_BRANDS:
            new_text = re.sub(pat, '', text, flags=re.IGNORECASE)
            if new_text != text:
                total_fixes += 1
                text = new_text

        # 4. Strip film stocks
        for pat in FILM_STOCKS:
            new_text = re.sub(pat, '', text, flags=re.IGNORECASE)
            if new_text != text:
                total_fixes += 1
                text = new_text

        # 5. Fix color grade contamination
        if scene_id in color_contamination:
            forbidden = color_contamination[scene_id]
            for word in forbidden:
                cg_pat = re.compile(
                    r'(color\s+grade:[^.]*?)' + re.escape(word),
                    re.IGNORECASE
                )
                new_text = cg_pat.sub(r'\1', text)
                if new_text != text:
                    total_fixes += 1
                    text = new_text

        # 6. Strip age patterns
        for pat in AGE_PATTERNS:
            new_text = re.sub(pat, '', text)
            if new_text != text:
                total_fixes += 1
                text = new_text

        # Clean up double spaces and artifacts
        text = re.sub(r'\s{2,}', ' ', text).strip()
        text = re.sub(r',\s*,', ',', text)
        text = re.sub(r'\.\s*\.', '.', text)

        if text != original:
            shot[field] = text

    return total_fixes


def sanitize_project(project_name, base_dir=None):
    """
    Main sanitizer function. Strips all known contaminants from shot_plan.json.
    Returns a report of changes made.
    """
    if base_dir is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    sp_path = os.path.join(base_dir, 'pipeline_outputs', project_name, 'shot_plan.json')

    if not os.path.exists(sp_path):
        return {"error": f"shot_plan.json not found at {sp_path}"}

    # Load
    with open(sp_path) as f:
        sp = json.load(f)

    shots = sp.get('shots', [])
    before_count = len(shots)

    # V26.1: Load project-specific config. Defaults are Ravencroft-era fallbacks.
    # For new projects (Victorian Shadows, etc.), get_project_config() overrides these
    # with project-specific actor names, color grades, and contamination maps.
    ai_actor_names = _DEFAULT_AI_ACTOR_NAMES
    color_contamination = _DEFAULT_COLOR_GRADE_CONTAMINATION
    if _HAS_CONFIG:
        try:
            config = get_project_config(project_name)
            # Build AI actor names from config strip patterns
            dynamic_names = []
            if hasattr(config, 'character_strip_patterns') and config.character_strip_patterns:
                for char_name, patterns in config.character_strip_patterns.items():
                    if patterns:
                        dynamic_names.append(patterns[0])  # First pattern is always the full AI actor name
            if dynamic_names:
                ai_actor_names = dynamic_names
                logger.info(f"[SANITIZER] Loaded {len(dynamic_names)} project-specific actor patterns for {project_name}")
            # Use config contamination map
            if hasattr(config, 'color_grade_contamination') and config.color_grade_contamination:
                color_contamination = config.color_grade_contamination
                logger.info(f"[SANITIZER] Loaded project-specific color contamination map for {project_name}")
        except Exception as _cfg_err:
            logger.warning(f"[SANITIZER] Config load failed for {project_name}: {_cfg_err}. Using defaults.")

    # Backup (Rule 180)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = f'{sp_path}.backup_sanitize_{ts}'
    shutil.copy2(sp_path, backup_path)

    # Track changes
    report = {
        "timestamp": ts,
        "project": project_name,
        "shot_count_before": before_count,
        "fixes": {
            "ai_actor_names": 0,
            "nationalities": 0,
            "camera_brands": 0,
            "film_stocks": 0,
            "color_grade_contamination": 0,
            "age_patterns": 0,
        },
        "shots_modified": set(),
        "backup": backup_path,
    }

    for shot in shots:
        shot_id = shot.get('shot_id', '')
        scene_id = shot.get('scene_id', '')

        for field in ['nano_prompt', 'nano_prompt_final', 'ltx_motion_prompt']:
            text = shot.get(field, '')
            original = text

            # 1. Strip AI actor names
            for pat in ai_actor_names:
                new_text = re.sub(pat, '', text, flags=re.IGNORECASE)
                if new_text != text:
                    report["fixes"]["ai_actor_names"] += 1
                    text = new_text

            # 2. Strip nationalities
            for pat in NATIONALITY_PATTERNS:
                new_text = re.sub(pat, '', text)
                if new_text != text:
                    report["fixes"]["nationalities"] += 1
                    text = new_text

            # 3. Strip camera brands
            for pat in CAMERA_BRANDS:
                new_text = re.sub(pat, '', text, flags=re.IGNORECASE)
                if new_text != text:
                    report["fixes"]["camera_brands"] += 1
                    text = new_text

            # 4. Strip film stocks
            for pat in FILM_STOCKS:
                new_text = re.sub(pat, '', text, flags=re.IGNORECASE)
                if new_text != text:
                    report["fixes"]["film_stocks"] += 1
                    text = new_text

            # 5. Fix color grade contamination
            if scene_id in color_contamination:
                forbidden = color_contamination[scene_id]
                for word in forbidden:
                    # Only strip from color grade context, not from general description
                    cg_pat = re.compile(
                        r'(color\s+grade:[^.]*?)' + re.escape(word),
                        re.IGNORECASE
                    )
                    new_text = cg_pat.sub(r'\1', text)
                    if new_text != text:
                        report["fixes"]["color_grade_contamination"] += 1
                        text = new_text

            # Clean up double spaces and leading/trailing whitespace
            text = re.sub(r'\s{2,}', ' ', text).strip()
            text = re.sub(r',\s*,', ',', text)  # Double commas
            text = re.sub(r'\.\s*\.', '.', text)  # Double periods

            if text != original:
                shot[field] = text
                report["shots_modified"].add(shot_id)

    # Verify shot count unchanged (Rule 181)
    after_count = len(shots)
    assert before_count == after_count, f"CRITICAL: Shot count changed {before_count} → {after_count}"
    report["shot_count_after"] = after_count

    # Save
    with open(sp_path, 'w') as f:
        json.dump(sp, f, indent=2)

    # Convert set to list for JSON serialization
    report["shots_modified"] = sorted(report["shots_modified"])
    report["total_fixes"] = sum(report["fixes"].values())
    report["total_shots_modified"] = len(report["shots_modified"])

    return report


def print_report(report):
    """Pretty-print the sanitizer report."""
    print("=" * 60)
    print(f"🧹 POST-FIX-V16 SANITIZER REPORT")
    print(f"   Project: {report['project']}")
    print(f"   Time: {report['timestamp']}")
    print("=" * 60)

    if "error" in report:
        print(f"  ❌ {report['error']}")
        return

    print(f"  Shot count: {report['shot_count_before']} → {report['shot_count_after']} (unchanged ✅)")
    print(f"  Backup: {report['backup']}")
    print()
    print("  Fixes applied:")
    for category, count in report["fixes"].items():
        status = "✅" if count == 0 else f"🔧 {count}"
        print(f"    {category}: {status}")
    print()
    print(f"  TOTAL: {report['total_fixes']} fixes across {report['total_shots_modified']} shots")

    if report['total_fixes'] == 0:
        print("\n  ✨ Already clean — no changes needed")
    else:
        print(f"\n  Modified shots: {report['shots_modified'][:10]}")
        if len(report['shots_modified']) > 10:
            print(f"    ... and {len(report['shots_modified'])-10} more")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 tools/post_fixv16_sanitizer.py <project_name>")
        print("Example: python3 tools/post_fixv16_sanitizer.py ravencroft_v22")
        sys.exit(1)

    project = sys.argv[1]
    report = sanitize_project(project)
    print_report(report)
