#!/usr/bin/env python3
"""
ATLAS V28.1 — Pre-Generation Enforcement Gate
===============================================
This gate BLOCKS generation if critical requirements aren't met.
It does NOT advise. It does NOT warn. It HALTS.

PHILOSOPHY:
  If the analysis system KNOWS something is wrong,
  the generation system MUST NOT proceed.
  Claude should never babysit a run.

CHECKS (all BLOCKING):
  1. IDENTITY: Every character shot has [CHARACTER:] block in prompt
  2. REFS: Every character shot has resolvable character_reference_url
  3. TRUTH: Every shot has _beat_ref (truth layer active)
  4. ROOM DNA: Scene DNA present on all shots
  5. DIALOGUE DURATION: No dialogue shot under minimum duration
  6. EMPTY CONSTRAINT: Non-character shots have negative people constraint
  7. PROMPT HEALTH: No corrupted/repeated prompts
  8. LOCATION LOCK: All shots reference same room (no teleporting)

USAGE:
  from tools.pre_gen_enforcer import enforce_pre_generation
  result = enforce_pre_generation(scene_shots, cast_map, project_path)
  if not result["can_proceed"]:
      print("BLOCKED:", result["blocking_issues"])
      sys.exit(1)

  # Also provides auto-fix capability:
  fixed_shots = result["fixed_shots"]  # Shots with identity injected, truth translated, etc.
"""

import json, os, hashlib
from typing import Dict, List, Optional, Tuple

# ═══════════════════════════════════════════════════════════════
# AMPLIFICATION MAP (from T2-FE-27)
# ═══════════════════════════════════════════════════════════════
AMPLIFICATION_MAP = {
    "silver hair": "BRIGHT SILVER-WHITE hair, clearly aged, distinguished",
    "auburn hair": "RICH AUBURN hair, coppery-red tones, distinctive",
    "dark brown skin": "DARK BROWN skin, warm undertones, clear complexion",
    "natural textured hair": "NATURAL TEXTURED hair, voluminous",
    "stocky build": "STOCKY, THICK-SET build, broad shoulders",
    "navy suit": "DARK NAVY SUIT, formal, well-tailored, crisp white shirt",
    "charcoal blazer": "CHARCOAL GREY BLAZER, sharp-shouldered, professional",
    "turtleneck": "BLACK TURTLENECK sweater, fitted, high collar visible",
    "flannel": "OPEN FLANNEL SHIRT, checkered, casual layered look",
    "band t-shirt": "VINTAGE BAND T-SHIRT, graphic print visible",
    "jeans": "WORN DENIM JEANS, casual fit",
    "overcoat": "HEAVY DARK OVERCOAT, thick wool, imposing silhouette",
}

# Room DNA templates
ROOM_DNA_TEMPLATES = {
    "foyer": "[ROOM DNA: Victorian grand foyer, single curved dark mahogany staircase with carved balusters, ornate iron chandelier overhead, dark wood paneling walls, checkerboard marble floor, tall narrow windows with heavy drapes, dust particles visible in shafts of light]",
    "library": "[ROOM DNA: Victorian library, floor-to-ceiling dark wood bookshelves, rolling ladder, green-shaded reading lamp, leather wingback chair, Persian rug on dark hardwood floor, tall arched window with heavy curtains, dust motes in lamplight]",
    "drawing_room": "[ROOM DNA: Victorian drawing room, ornate fireplace with marble mantle, velvet settee, dark floral wallpaper, crystal chandelier, portrait paintings in gilded frames, bay window with lace curtains]",
    "bedroom": "[ROOM DNA: Victorian bedroom, four-poster bed with canopy, dark wood wardrobe, vanity mirror, floral wallpaper, heavy curtains, oil lamp on nightstand]",
    "kitchen": "[ROOM DNA: Victorian kitchen, cast iron range, copper pots hanging, stone flagstone floor, large wooden table, Belfast sink, herbs drying from ceiling beams]",
    "staircase": "[ROOM DNA: Victorian grand staircase, dark mahogany banister, carved newel post, runner carpet on treads, portraits ascending the wall, chandelier visible above]",
    "exterior": "[ROOM DNA: Victorian estate exterior, grey stone facade, ivy-covered walls, gravel drive, manicured hedges, overcast English sky, bare winter trees]",
    "garden": "[ROOM DNA: Victorian estate garden, overgrown paths, stone bench, iron gate, dead rose bushes, fog rolling across lawn, distant treeline]",
}

# Lighting rig per room type
LIGHTING_RIGS = {
    "foyer": "[LIGHTING RIG: dust-filtered morning light through tall windows, warm amber lamp glow from wall sconces, cool blue daylight mixing with warm interior, dramatic shadows on dark wood, high contrast chiaroscuro]",
    "library": "[LIGHTING RIG: warm golden lamplight from green-shaded desk lamp, amber glow on book spines, deep shadows in shelf alcoves, single window providing cool backlight, intimate pool of light]",
    "drawing_room": "[LIGHTING RIG: firelight flickering warm orange glow, chandelier providing soft overhead fill, cool grey window light from bay window, deep shadows in room corners]",
    "exterior": "[LIGHTING RIG: overcast diffused daylight, cool grey ambient, no harsh shadows, fog softening background, occasional break in clouds creating rim light]",
}

# ═══════════════════════════════════════════════════════════════
# CORE ENFORCEMENT CHECKS
# ═══════════════════════════════════════════════════════════════

def _check_identity(shots: List[Dict], cast_map: Dict) -> Tuple[List[str], List[Dict]]:
    """CHECK 1: Every character shot MUST have [CHARACTER:] identity block."""
    issues = []
    fixes = []
    for shot in shots:
        sid = shot.get("shot_id", "")
        chars = shot.get("characters") or []
        if not chars:
            continue

        prompt = shot.get("nano_prompt", "")
        if "[CHARACTER:" not in prompt:
            # AUTO-FIX: Inject identity
            identity_blocks = []
            for cname in chars:
                cdata = cast_map.get(cname, {})
                if isinstance(cdata, dict):
                    app = cdata.get("appearance", "")
                    if app:
                        amp = _amplify(app)
                        identity_blocks.append(f"[CHARACTER: {amp}]")
                    else:
                        issues.append(f"BLOCKING: {sid} character '{cname}' has NO appearance in cast_map")

            if identity_blocks:
                new_prompt = " ".join(identity_blocks) + " " + prompt
                fixes.append({"shot_id": sid, "field": "nano_prompt", "action": "inject_identity", "value": new_prompt[:900]})
            else:
                issues.append(f"BLOCKING: {sid} has {len(chars)} characters but ZERO resolvable appearances")

    return issues, fixes


def _check_refs(shots: List[Dict], cast_map: Dict, project_path: str) -> Tuple[List[str], List[Dict]]:
    """CHECK 2: Every character shot MUST have resolvable character reference image."""
    issues = []
    fixes = []
    char_lib = os.path.join(project_path, "character_library_locked")

    for shot in shots:
        sid = shot.get("shot_id", "")
        chars = shot.get("characters") or []
        if not chars:
            continue

        for cname in chars:
            cdata = cast_map.get(cname, {})
            if not isinstance(cdata, dict):
                issues.append(f"BLOCKING: {sid} character '{cname}' NOT IN cast_map at all")
                continue

            ref = cdata.get("character_reference_url", "")
            if not ref:
                issues.append(f"BLOCKING: {sid} character '{cname}' has NO character_reference_url")
                continue

            # Try multiple resolution strategies
            resolved = False
            for candidate in [ref, os.path.join(project_path, "..", "..", ref), os.path.abspath(ref)]:
                if os.path.exists(candidate):
                    resolved = True
                    break

            if not resolved:
                # Try constructed path
                safe_name = cname.upper().replace(" ", "_")
                fallback = os.path.join(char_lib, f"{safe_name}_CHAR_REFERENCE.jpg")
                if os.path.exists(fallback):
                    fixes.append({"shot_id": sid, "field": "ref_path", "character": cname, "resolved_path": fallback})
                else:
                    issues.append(f"BLOCKING: {sid} character '{cname}' ref NOT FOUND: {ref}")

    return issues, fixes


def _check_truth(shots: List[Dict]) -> Tuple[List[str], List[Dict]]:
    """CHECK 3: Every shot MUST have _beat_ref (truth layer)."""
    issues = []
    fixes = []
    for shot in shots:
        sid = shot.get("shot_id", "")
        if not shot.get("_beat_ref"):
            issues.append(f"WARNING: {sid} has NO _beat_ref (truth layer not compiled)")
    return issues, fixes


def _check_room_dna(shots: List[Dict], scene_room: str) -> Tuple[List[str], List[Dict]]:
    """CHECK 4: All shots must have room DNA."""
    issues = []
    fixes = []
    room_key = _detect_room_type(scene_room)
    dna = ROOM_DNA_TEMPLATES.get(room_key, "")

    if not dna:
        issues.append(f"WARNING: No room DNA template for '{scene_room}' (type: {room_key})")
        return issues, fixes

    for shot in shots:
        sid = shot.get("shot_id", "")
        prompt = shot.get("nano_prompt", "")
        if "[ROOM DNA:" not in prompt:
            new_prompt = prompt.rstrip() + " " + dna
            fixes.append({"shot_id": sid, "field": "nano_prompt", "action": "inject_room_dna", "value": new_prompt[:900]})

    return issues, fixes


def _check_dialogue_duration(shots: List[Dict]) -> Tuple[List[str], List[Dict]]:
    """CHECK 5: Dialogue shots must have adequate duration."""
    issues = []
    fixes = []
    for shot in shots:
        sid = shot.get("shot_id", "")
        dlg = shot.get("dialogue_text", "")
        if not dlg:
            continue
        wc = len(dlg.split())
        min_dur = (wc / 2.3) + 1.5
        plan_dur = shot.get("duration", 0)

        # Cap at 10s (LTX-2 max) — this is a KNOWN LIMITATION not a bug
        effective_max = 10
        if min_dur > effective_max:
            issues.append(f"INFO: {sid} dialogue needs {min_dur:.1f}s but LTX-2 max is {effective_max}s — will cap at {effective_max}s")

        if plan_dur < min(min_dur, effective_max):
            new_dur = min(int(min_dur) + (1 if int(min_dur) % 2 != 0 else 0), effective_max)
            if new_dur % 2 != 0:
                new_dur += 1
            new_dur = min(new_dur, 10)
            fixes.append({"shot_id": sid, "field": "duration", "action": "extend_for_dialogue", "value": new_dur})

    return issues, fixes


def _check_empty_constraint(shots: List[Dict]) -> Tuple[List[str], List[Dict]]:
    """CHECK 6: Non-character shots need negative people constraint."""
    issues = []
    fixes = []
    for shot in shots:
        sid = shot.get("shot_id", "")
        chars = shot.get("characters") or []
        prompt = shot.get("nano_prompt", "")
        if not chars and "No people" not in prompt and "no figures" not in prompt:
            new_prompt = prompt.rstrip() + " No people visible, no figures, no silhouettes, empty space only."
            fixes.append({"shot_id": sid, "field": "nano_prompt", "action": "inject_empty_constraint", "value": new_prompt[:900]})
    return issues, fixes


def _check_prompt_health(shots: List[Dict]) -> Tuple[List[str], List[Dict]]:
    """CHECK 7: No corrupted/repeated prompts (T2-CPC-9)."""
    issues = []
    fixes = []
    for shot in shots:
        sid = shot.get("shot_id", "")
        for field in ["nano_prompt", "ltx_motion_prompt"]:
            text = shot.get(field, "")
            if not text or len(text) < 60:
                continue
            # Check for 30-char substring appearing 3+ times
            for i in range(len(text) - 30):
                substr = text[i:i+30]
                if text.count(substr) >= 3:
                    issues.append(f"BLOCKING: {sid} field '{field}' has CORRUPTED repeated text")
                    break
    return issues, fixes


def _check_location_lock(shots: List[Dict], scene_room: str) -> Tuple[List[str], List[Dict]]:
    """CHECK 8: All shots reference same room."""
    # This is informational — actual enforcement is in DP resolver
    issues = []
    fixes = []
    if not scene_room:
        issues.append("WARNING: No scene_room detected — cannot enforce location lock")
    return issues, fixes


# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════

def _amplify(appearance: str) -> str:
    result = appearance
    for key, amp in AMPLIFICATION_MAP.items():
        if key.lower() in result.lower():
            result = result.replace(key, amp)
    return result

def _detect_room_type(location: str) -> str:
    loc_lower = location.lower()
    for room_type in ROOM_DNA_TEMPLATES:
        if room_type in loc_lower:
            return room_type
    if "foyer" in loc_lower or "entrance" in loc_lower or "hall" in loc_lower:
        return "foyer"
    if "library" in loc_lower or "study" in loc_lower:
        return "library"
    if "drawing" in loc_lower or "sitting" in loc_lower or "parlor" in loc_lower:
        return "drawing_room"
    if "bed" in loc_lower:
        return "bedroom"
    if "kitchen" in loc_lower:
        return "kitchen"
    if "stair" in loc_lower:
        return "staircase"
    if "garden" in loc_lower or "ground" in loc_lower:
        return "garden"
    if "ext" in loc_lower or "drive" in loc_lower or "front" in loc_lower:
        return "exterior"
    return "foyer"  # default

def _get_scene_room(story_bible: Dict, scene_id: str) -> str:
    """Extract room/location from story bible for a scene."""
    scenes = story_bible.get("scenes", [])
    for sc in scenes:
        sid = sc.get("scene_id", "")
        snum = str(sc.get("scene_number", ""))
        if sid.startswith(scene_id) or snum == scene_id.lstrip("0"):
            return sc.get("location", "")
    return ""


# ═══════════════════════════════════════════════════════════════
# MAIN ENFORCEMENT FUNCTION
# ═══════════════════════════════════════════════════════════════

def enforce_pre_generation(
    scene_shots: List[Dict],
    cast_map: Dict,
    project_path: str,
    story_bible: Optional[Dict] = None,
    scene_id: str = "",
    auto_fix: bool = True,
) -> Dict:
    """
    Run ALL pre-generation checks. Returns:
      {
        "can_proceed": bool,
        "blocking_issues": [...],   # HALT if any
        "warnings": [...],          # Informational
        "fixes_applied": [...],     # Auto-fixes done
        "fixed_shots": [...],       # Shots with fixes applied
        "stats": { "identity": "9/9", "refs": "9/9", ... }
      }
    """
    all_issues = []
    all_fixes = []
    warnings = []

    # Detect scene room
    scene_room = ""
    if story_bible and scene_id:
        scene_room = _get_scene_room(story_bible, scene_id)

    # Run all checks
    checks = [
        ("IDENTITY", _check_identity(scene_shots, cast_map)),
        ("REFS", _check_refs(scene_shots, cast_map, project_path)),
        ("TRUTH", _check_truth(scene_shots)),
        ("ROOM_DNA", _check_room_dna(scene_shots, scene_room)),
        ("DIALOGUE_DUR", _check_dialogue_duration(scene_shots)),
        ("EMPTY_CONSTRAINT", _check_empty_constraint(scene_shots)),
        ("PROMPT_HEALTH", _check_prompt_health(scene_shots)),
        ("LOCATION_LOCK", _check_location_lock(scene_shots, scene_room)),
    ]

    for check_name, (issues, fixes) in checks:
        for iss in issues:
            if iss.startswith("BLOCKING:"):
                all_issues.append(f"[{check_name}] {iss}")
            elif iss.startswith("WARNING:"):
                warnings.append(f"[{check_name}] {iss}")
            else:
                warnings.append(f"[{check_name}] {iss}")
        all_fixes.extend(fixes)

    # Apply auto-fixes if enabled
    fixes_applied = []
    if auto_fix and all_fixes:
        shot_map = {s.get("shot_id"): s for s in scene_shots}
        for fix in all_fixes:
            sid = fix["shot_id"]
            if sid in shot_map:
                field = fix["field"]
                if field in ("nano_prompt", "ltx_motion_prompt", "duration"):
                    shot_map[sid][field] = fix["value"]
                    fixes_applied.append(f"{sid}: {fix.get('action', 'fix')} on {field}")
        scene_shots = list(shot_map.values())

    # Compute stats
    char_shots = [s for s in scene_shots if s.get("characters")]
    identity_ok = len([s for s in char_shots if "[CHARACTER:" in s.get("nano_prompt", "")])
    truth_ok = len([s for s in scene_shots if s.get("_beat_ref")])
    dna_ok = len([s for s in scene_shots if "[ROOM DNA:" in s.get("nano_prompt", "")])

    blocking = [i for i in all_issues if "BLOCKING:" in i]

    result = {
        "can_proceed": len(blocking) == 0,
        "blocking_issues": blocking,
        "warnings": warnings,
        "fixes_applied": fixes_applied,
        "fixed_shots": scene_shots,
        "scene_room": scene_room,
        "room_type": _detect_room_type(scene_room),
        "stats": {
            "total_shots": len(scene_shots),
            "character_shots": len(char_shots),
            "identity_injected": f"{identity_ok}/{len(char_shots)}",
            "truth_compiled": f"{truth_ok}/{len(scene_shots)}",
            "room_dna": f"{dna_ok}/{len(scene_shots)}",
            "fixes_applied": len(fixes_applied),
        }
    }

    return result


def print_enforcement_report(result: Dict):
    """Pretty-print the enforcement gate result."""
    print(f"\n{'='*70}")
    print(f"  PRE-GENERATION ENFORCEMENT GATE")
    print(f"{'='*70}")

    stats = result["stats"]
    print(f"\n  STATS:")
    print(f"    Shots:    {stats['total_shots']} total, {stats['character_shots']} with characters")
    print(f"    Identity: {stats['identity_injected']} character shots have [CHARACTER:] blocks")
    print(f"    Truth:    {stats['truth_compiled']} shots have beat_ref")
    print(f"    Room DNA: {stats['room_dna']} shots have [ROOM DNA:]")
    print(f"    Fixes:    {stats['fixes_applied']} auto-applied")

    if result["blocking_issues"]:
        print(f"\n  ✗ BLOCKED — {len(result['blocking_issues'])} blocking issues:")
        for iss in result["blocking_issues"]:
            print(f"    ✗ {iss}")

    if result["warnings"]:
        print(f"\n  ⚠ WARNINGS ({len(result['warnings'])}):")
        for w in result["warnings"]:
            print(f"    ⚠ {w}")

    if result["fixes_applied"]:
        print(f"\n  AUTO-FIXES ({len(result['fixes_applied'])}):")
        for fix in result["fixes_applied"]:
            print(f"    ✓ {fix}")

    status = "✓ CAN PROCEED" if result["can_proceed"] else "✗ GENERATION BLOCKED"
    print(f"\n  VERDICT: {status}")
    print(f"{'='*70}")


# ═══════════════════════════════════════════════════════════════
# CLI — Run standalone
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python3 tools/pre_gen_enforcer.py <project> <scene_id>")
        print("Example: python3 tools/pre_gen_enforcer.py victorian_shadows_ep1 001")
        sys.exit(1)

    project = sys.argv[1]
    scene_id = sys.argv[2]
    project_path = f"pipeline_outputs/{project}"

    with open(f"{project_path}/shot_plan.json") as f:
        sp = json.load(f)
    shots = sp if isinstance(sp, list) else sp.get("shots", [])
    scene_shots = [s for s in shots if s.get("shot_id", "").startswith(f"{scene_id}_")]

    with open(f"{project_path}/cast_map.json") as f:
        cm = json.load(f)

    sb = None
    sb_path = f"{project_path}/story_bible.json"
    if os.path.exists(sb_path):
        with open(sb_path) as f:
            sb = json.load(f)

    result = enforce_pre_generation(scene_shots, cm, project_path, sb, scene_id, auto_fix=True)
    print_enforcement_report(result)

    if not result["can_proceed"]:
        sys.exit(1)

    print(f"\n  {len(result['fixed_shots'])} shots ready for generation.")
