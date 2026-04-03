#!/usr/bin/env python3
"""
ATLAS V21.9 — MOVIE LOCK MODE
================================
Autonomous, error-proof, no-regression enforcement system.

Three pillars:
  1. UI Lock Contract — user_locked fields are IMMUTABLE
  2. Actor Bio Bleed Block — forbidden tokens never reach FAL
  3. Gate Snapshot — immutable pre-FAL payload with SHA256 verification

This module is the SINGLE source of truth for lock enforcement.
All generation endpoints MUST call gate_snapshot_create() before FAL
and gate_snapshot_verify() before sending any payload.

Design: FAIL FAST. If anything looks wrong, block and report.
"""

import hashlib
import json
import os
import re
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from core.project_config import get_project_config

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════
# CONTRACT A: UI LOCK — IMMUTABLE FIELDS
# ═══════════════════════════════════════════════════════════════════

# These fields CANNOT be changed on a user_locked shot
LOCKED_FIELDS = [
    "nano_prompt", "ltx_motion_prompt", "characters", "location",
    "duration", "duration_seconds", "character_reference_url",
    "location_master_url", "shot_type", "blocking_role",
    "dialogue_text", "dialogue", "negative_prompt"
]


def check_ui_lock_violations(shots_before: List[dict], shots_after: List[dict]) -> List[dict]:
    """
    CONTRACT A: Check if any user_locked fields were modified.
    Returns list of violations. Empty list = PASS.

    Call this AFTER any mutation (fix-v16, enrichment, etc.) to verify
    no locked fields were changed.
    """
    violations = []
    before_map = {s.get("shot_id", ""): s for s in shots_before}

    for shot_after in shots_after:
        sid = shot_after.get("shot_id", "")
        if not shot_after.get("user_locked"):
            continue

        shot_before = before_map.get(sid)
        if not shot_before:
            continue

        for field in LOCKED_FIELDS:
            val_before = shot_before.get(field)
            val_after = shot_after.get(field)
            if val_before != val_after:
                violations.append({
                    "shot_id": sid,
                    "field": field,
                    "before_hash": _hash_value(val_before),
                    "after_hash": _hash_value(val_after),
                    "before_len": len(str(val_before or "")),
                    "after_len": len(str(val_after or "")),
                    "rule": "CONTRACT_A_UI_LOCK",
                    "severity": "CRITICAL"
                })

    return violations


def lock_shot(shot: dict) -> dict:
    """Mark a shot as user_locked. Returns the shot with lock applied."""
    shot["user_locked"] = True
    shot["_locked_at"] = datetime.now().isoformat()
    shot["_locked_hash"] = _compute_shot_hash(shot)
    return shot


def unlock_shot(shot: dict) -> dict:
    """Remove user_locked from a shot. Requires explicit user action."""
    shot["user_locked"] = False
    shot.pop("_locked_at", None)
    shot.pop("_locked_hash", None)
    return shot


def is_locked(shot: dict) -> bool:
    """Check if a shot is user_locked."""
    return bool(shot.get("user_locked"))


# ═══════════════════════════════════════════════════════════════════
# CONTRACT C: ACTOR BIO BLEED BLOCK
# ═══════════════════════════════════════════════════════════════════

# These patterns are FORBIDDEN in any final prompt sent to FAL.
# If detected: generation BLOCKED for that shot.
BIO_BLEED_PATTERNS = [
    # Age patterns
    r'\b\d{1,2}\s*(?:years?\s*old|year-old|yo)\b',
    r'\bage[d]?\s*\d{1,2}\b',
    r'\bin\s+(?:his|her|their)\s+(?:early|mid|late)\s+\d{1,2}s\b',

    # Nationality phrases (AI actor bios)
    r'\b(?:French|Italian|English|Spanish|German|Russian|Japanese|Chinese|Brazilian|Swedish|Norwegian)\s+(?:man|woman|person|lady|gentleman|actor|actress)\b',

    # Specific AI actor contamination
    r'\bIsabella\s+Moretti\b',
    r'\bGauloise\b',
    r'\bprofessor\s+(?:of|at|from|emeritus)\b',  # AI actor bio indicator (not character title)

    # Long bio paragraph indicators (>100 char descriptions with bio markers)
    r'(?:born\s+in|grew\s+up|studied\s+at|graduated\s+from|career\s+in)',

    # Film stock / camera body contamination (shouldn't be in nano_prompt)
    # NOTE: RED camera pattern is case-SENSITIVE to avoid matching "red hair", "red candles"
    r'\b(?:Kodak|Fujifilm|ARRI|Sony)\s+[A-Z][\w\-]+\b',
    r'\bfilm\s+stock\b',
]

# RED camera brand pattern — case-sensitive (won't match "red hair")
_RED_CAMERA_PATTERN = re.compile(r'\bRED\s+[A-Z][\w\-]+\b')  # Case-sensitive

# Compiled with IGNORECASE for most patterns
_BIO_BLEED_COMPILED = [re.compile(p, re.IGNORECASE) for p in BIO_BLEED_PATTERNS]
BIO_BLEED_PATTERNS.append(r'\bRED\b')  # V21.9.1: Keep patterns list in sync with compiled list
_BIO_BLEED_COMPILED.append(_RED_CAMERA_PATTERN)  # Add case-sensitive RED at end


def check_bio_bleed(prompt: str, shot_id: str = "") -> List[dict]:
    """
    CONTRACT C: Scan a prompt for forbidden actor bio tokens.
    Returns list of violations. Empty list = CLEAN.
    """
    violations = []
    for i, pattern in enumerate(_BIO_BLEED_COMPILED):
        matches = pattern.findall(prompt)
        for match in matches:
            violations.append({
                "shot_id": shot_id,
                "pattern_index": i,
                "pattern": BIO_BLEED_PATTERNS[i],
                "match": match,
                "rule": "CONTRACT_C_BIO_BLEED",
                "severity": "CRITICAL"
            })
    return violations


def strip_bio_bleed(prompt: str) -> Tuple[str, int]:
    """
    Emergency strip of bio bleed tokens from a prompt.
    Returns (cleaned_prompt, strip_count).
    Use check_bio_bleed() first — this is the safety net.
    """
    count = 0
    cleaned = prompt
    for pattern in _BIO_BLEED_COMPILED:
        result, n = pattern.subn("", cleaned)
        if n > 0:
            cleaned = result
            count += n
    # Clean up double spaces and orphaned commas
    cleaned = re.sub(r'\s{2,}', ' ', cleaned)
    cleaned = re.sub(r',\s*,', ',', cleaned)
    cleaned = re.sub(r'\.\s*\.', '.', cleaned)
    return cleaned.strip(), count


# ═══════════════════════════════════════════════════════════════════
# CONTRACT D: LOCATION LOCK
# ═══════════════════════════════════════════════════════════════════

# Default location keywords (used as fallback if project_config fails to load).
# V26.1: These are Ravencroft-specific examples and only activate when project_config
# is unavailable. For new projects, get_project_config() overrides these entirely.
# These are MULTI-WORD PHRASES that strongly indicate a specific location.
# Single generic words (desk, door, window) are excluded — they're too common.
_DEFAULT_LOCATION_KEYWORDS = {
    "LAW OFFICE": ["law office", "filing cabinet", "law books",
                    "conference table", "legal pad", "legal documents on desk"],
    "CITY APARTMENT": ["tiny kitchen", "city apartment",
                       "cramped apartment", "stack of bills"],
    "COASTAL ROAD": ["coastal road", "winding coastal", "bus journey",
                     "countryside bus", "cliff path", "seaside road"],
    "RAVENCROFT MANOR": ["grand entrance hall", "portrait hall",
                         "oak doors", "stone walls of the manor",
                         "ancestral portraits", "manor entrance"],
    "VILLAGE PUB": ["village pub", "pub interior", "pint glass",
                    "pub fireplace", "locals drinking"],
    # NOTE: LIBRARY, STUDY, HALLWAY, GUEST BEDROOM are rooms WITHIN Ravencroft Manor.
    # They should NOT trigger cross-location bleed with RAVENCROFT MANOR.
    # Only check these against clearly DIFFERENT locations (LAW OFFICE, CITY APARTMENT, etc.)
    "LIBRARY": ["manor library", "towering bookshelves", "leather-bound volumes"],
    "STUDY": ["manor study", "study desk", "writing desk"],
    "HALLWAY": ["manor hallway", "portrait-lined hallway"],
    "GUEST BEDROOM": ["four-poster bed", "bedroom mirror"],
}

# Default sub-rooms (used as fallback if project_config fails to load).
# Rooms that are INSIDE the main location — don't flag these as cross-location
# when the shot is at the main location.
_DEFAULT_MANOR_ROOMS = {"LIBRARY", "STUDY", "HALLWAY", "GUEST BEDROOM"}


def check_location_bleed(shot: dict, project_name: str = "") -> List[dict]:
    """
    CONTRACT D: Check if prompt VISUAL DESCRIPTION mentions keywords from a DIFFERENT location.
    Dialogue content is excluded from the check (characters can TALK about other locations).

    Args:
        shot: The shot dictionary to check
        project_name: Optional project name to load location config (uses fallback if not provided)

    Returns list of violations. Empty list = CLEAN.
    """
    violations = []
    location = (shot.get("location", "") or "").upper()
    nano = (shot.get("nano_prompt", "") or shot.get("nano_prompt_final", "") or "").lower()

    # Strip dialogue content from the check — characters can mention other locations
    # Remove everything between quotes and after "character speaks:" markers
    nano = re.sub(r'"[^"]*"', '', nano)  # Remove quoted dialogue
    nano = re.sub(r"'[^']*'", '', nano)  # Remove single-quoted
    nano = re.sub(r'character speaks:[^,]*,?', '', nano, flags=re.IGNORECASE)
    nano = re.sub(r'says\s+"[^"]*"', '', nano)  # Remove "says ..." patterns

    if not location or not nano:
        return violations

    # Load project config if provided, otherwise use defaults
    location_keywords = _DEFAULT_LOCATION_KEYWORDS
    main_location = ""
    sub_rooms = _DEFAULT_MANOR_ROOMS
    config = None

    if project_name:
        try:
            config = get_project_config(project_name)
            location_keywords = config.location_keywords
            main_location = config.main_location_name
            sub_rooms = config.sub_rooms
        except Exception as e:
            logger.warning(f"[location_bleed] Failed to load config for {project_name}: {e}. Using defaults.")
            # Fall through to use defaults

    # Find which location group this shot belongs to
    shot_loc_group = None
    for loc_key in location_keywords:
        if loc_key in location:
            shot_loc_group = loc_key
            break

    if not shot_loc_group:
        return violations  # Unknown location, can't check

    # Check for keywords from OTHER locations
    for loc_key, keywords in location_keywords.items():
        if loc_key == shot_loc_group:
            continue  # Skip own location's keywords

        # V23: Don't flag sub-room keywords when shot is at the main location
        # (e.g., LIBRARY, STUDY, HALLWAY, GUEST BEDROOM are rooms inside the main location)
        # This covers TWO cases:
        #   1. Shot location IS a sub-room → don't flag main location keywords
        #   2. Shot location IS the main location → don't flag sub-room keywords
        #   3. Both shot and "foreign" are sub-rooms of the same main location → don't flag
        if config:
            shot_is_sub = config.is_sub_room(location)
            foreign_is_sub = config.is_sub_room(loc_key)
            main_loc = config.main_location_name

            # If both are within the same main location, skip
            if main_loc:
                shot_in_main = main_loc in location or location in main_loc
                foreign_in_main = main_loc in loc_key or loc_key in main_loc
                if shot_in_main and foreign_in_main:
                    continue

            # Legacy fallback: sub-room check
            if shot_is_sub and loc_key in sub_rooms:
                continue
        elif not config:
            # Fallback for unparameterized projects
            if location in sub_rooms or any(room in location for room in sub_rooms):
                if loc_key in sub_rooms:
                    continue

        for kw in keywords:
            if kw in nano:
                violations.append({
                    "shot_id": shot.get("shot_id", ""),
                    "shot_location": location,
                    "foreign_location": loc_key,
                    "keyword": kw,
                    "rule": "CONTRACT_D_LOCATION_BLEED",
                    "severity": "CRITICAL"
                })

    return violations


# ═══════════════════════════════════════════════════════════════════
# CONTRACT E: SCENE↔SHOT ALIGNMENT
# ═══════════════════════════════════════════════════════════════════

def check_scene_alignment(shots: List[dict], scene_manifest: List[dict]) -> List[dict]:
    """
    CONTRACT E: Verify every scene_id in shots has a manifest entry
    and shot counts match.
    Returns list of violations. Empty list = PASS.
    """
    violations = []

    # Build shot counts by scene
    shot_scene_counts = {}
    for s in shots:
        sid = s.get("scene_id", "")
        shot_scene_counts[sid] = shot_scene_counts.get(sid, 0) + 1

    # Build manifest scene IDs
    manifest_scenes = {}
    for sc in scene_manifest:
        if isinstance(sc, dict):
            sid = sc.get("scene_id", "")
            manifest_scenes[sid] = sc

    # Check: every shot scene_id must be in manifest
    for sid, count in shot_scene_counts.items():
        if sid not in manifest_scenes:
            violations.append({
                "scene_id": sid,
                "shot_count": count,
                "rule": "CONTRACT_E_SCENE_ALIGNMENT",
                "detail": f"Scene {sid} has {count} shots but no manifest entry",
                "severity": "WARNING"
            })

    # Check: manifest entries without shots
    for sid in manifest_scenes:
        if sid not in shot_scene_counts:
            violations.append({
                "scene_id": sid,
                "shot_count": 0,
                "rule": "CONTRACT_E_SCENE_ALIGNMENT",
                "detail": f"Scene {sid} in manifest but has 0 shots",
                "severity": "WARNING"
            })

    return violations


# ═══════════════════════════════════════════════════════════════════
# GATE SNAPSHOT — IMMUTABLE PRE-FAL PAYLOAD
# ═══════════════════════════════════════════════════════════════════

def gate_snapshot_create(
    shots: List[dict],
    project_path: Path,
    scene_filter: Optional[List[str]] = None
) -> Dict:
    """
    Create an immutable gate snapshot. This is what FAL sees.

    Returns:
        {
            "success": bool,
            "snapshot_path": str,
            "snapshot_id": str,
            "shot_count": int,
            "violations": [...],  # Any issues found
            "payloads": {shot_id: {nano_prompt_final, ltx_prompt_final, ...}}
        }
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    snapshot_id = f"gate_{timestamp}"

    all_violations = []
    payloads = {}

    for shot in shots:
        sid = shot.get("shot_id", "")
        scene_id = shot.get("scene_id", "")

        # Apply scene filter if provided
        if scene_filter and scene_id not in scene_filter:
            continue

        # Get the prompt that will go to FAL
        nano_final = shot.get("nano_prompt_final") or shot.get("nano_prompt", "")
        ltx_final = shot.get("ltx_motion_prompt_final") or shot.get("ltx_motion_prompt", "")

        # CONTRACT C: Bio bleed check
        bio_violations = check_bio_bleed(nano_final, sid)
        if bio_violations:
            # Auto-strip as safety net
            nano_final, _strip_count = strip_bio_bleed(nano_final)
            for v in bio_violations:
                v["action"] = "AUTO_STRIPPED"
            all_violations.extend(bio_violations)

        ltx_bio = check_bio_bleed(ltx_final, sid)
        if ltx_bio:
            ltx_final, _ = strip_bio_bleed(ltx_final)
            for v in ltx_bio:
                v["action"] = "AUTO_STRIPPED"
            all_violations.extend(ltx_bio)

        # CONTRACT D: Location bleed check
        _check_shot = dict(shot)
        _check_shot["nano_prompt"] = nano_final
        loc_violations = check_location_bleed(_check_shot)
        all_violations.extend(loc_violations)

        # Build payload
        payload = {
            "shot_id": sid,
            "scene_id": scene_id,
            "nano_prompt_final": nano_final,
            "ltx_prompt_final": ltx_final,
            "location": shot.get("location", ""),
            "characters": shot.get("characters", []),
            "duration": shot.get("duration", 5),
            "character_reference_url": shot.get("character_reference_url"),
            "location_master_url": shot.get("location_master_url"),
            "shot_type": shot.get("shot_type", ""),
            "negative_prompt": shot.get("negative_prompt", ""),
            "user_locked": shot.get("user_locked", False),
        }

        # SHA256 hash of the payload for verification
        payload["_hash"] = _compute_payload_hash(payload)
        payloads[sid] = payload

    # Save snapshot to disk
    reports_dir = project_path / "reports"
    reports_dir.mkdir(exist_ok=True)

    snapshot_data = {
        "snapshot_id": snapshot_id,
        "created_at": datetime.now().isoformat(),
        "shot_count": len(payloads),
        "scene_filter": scene_filter,
        "violations": all_violations,
        "critical_count": sum(1 for v in all_violations if v.get("severity") == "CRITICAL"),
        "payloads": payloads
    }

    snapshot_path = reports_dir / f"gate_snapshot_{timestamp}.json"
    with open(snapshot_path, "w") as f:
        json.dump(snapshot_data, f, indent=2)

    # Also save as "latest" for quick access
    latest_path = project_path / "gate_snapshot.json"
    with open(latest_path, "w") as f:
        json.dump(snapshot_data, f, indent=2)

    logger.info(f"[GATE_SNAPSHOT] Created {snapshot_id}: {len(payloads)} shots, "
                f"{len(all_violations)} violations ({snapshot_data['critical_count']} critical)")

    return {
        "success": snapshot_data["critical_count"] == 0,
        "snapshot_path": str(snapshot_path),
        "snapshot_id": snapshot_id,
        "shot_count": len(payloads),
        "violations": all_violations,
        "critical_count": snapshot_data["critical_count"],
        "payloads": payloads
    }


def gate_snapshot_verify(shot_id: str, nano_prompt: str, project_path: Path) -> Dict:
    """
    Verify that a prompt about to be sent to FAL matches the gate snapshot.
    Call this RIGHT BEFORE the FAL API call.

    Returns:
        {"pass": bool, "reason": str}
    """
    snapshot_path = project_path / "gate_snapshot.json"
    if not snapshot_path.exists():
        return {"pass": False, "reason": "No gate snapshot exists. Run gate_snapshot_create() first."}

    try:
        with open(snapshot_path) as f:
            snapshot = json.load(f)
    except Exception as e:
        return {"pass": False, "reason": f"Failed to read gate snapshot: {e}"}

    payloads = snapshot.get("payloads", {})
    if shot_id not in payloads:
        return {"pass": False, "reason": f"Shot {shot_id} not in gate snapshot"}

    expected = payloads[shot_id].get("nano_prompt_final", "")

    # Compare (allow minor whitespace differences)
    if expected.strip() != nano_prompt.strip():
        return {
            "pass": False,
            "reason": f"Prompt mismatch for {shot_id}. "
                      f"Expected hash: {_hash_value(expected)}, "
                      f"Got hash: {_hash_value(nano_prompt)}, "
                      f"Expected len: {len(expected)}, Got len: {len(nano_prompt)}"
        }

    return {"pass": True, "reason": "Prompt matches gate snapshot"}


# ═══════════════════════════════════════════════════════════════════
# UNIVERSAL AUDIT — RUN BEFORE ANY GENERATION
# ═══════════════════════════════════════════════════════════════════

def run_full_audit(
    shots: List[dict],
    scene_manifest: List[dict],
    project_path: Path,
    project_name: str = ""
) -> Dict:
    """
    Run ALL contracts as a single audit pass.
    Returns a structured report with pass/fail per contract.

    FAIL FAST: If any CRITICAL violation exists, generation should be blocked.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    report = {
        "audit_id": f"audit_{timestamp}",
        "project": project_name,
        "timestamp": datetime.now().isoformat(),
        "shot_count": len(shots),
        "contracts": {},
        "all_violations": [],
        "critical_count": 0,
        "warning_count": 0,
        "pass": True
    }

    # CONTRACT B: Single enrichment check (detect duplicate markers)
    dup_violations = _check_duplicate_enrichment(shots)
    report["contracts"]["B_SINGLE_ENRICHMENT"] = {
        "violations": len(dup_violations),
        "pass": len(dup_violations) == 0,
        "details": dup_violations[:10]
    }
    report["all_violations"].extend(dup_violations)

    # CONTRACT C: Actor bio bleed
    bio_violations = []
    for shot in shots:
        nano = shot.get("nano_prompt", "") or ""
        bio_violations.extend(check_bio_bleed(nano, shot.get("shot_id", "")))
    report["contracts"]["C_BIO_BLEED"] = {
        "violations": len(bio_violations),
        "pass": len(bio_violations) == 0,
        "details": bio_violations[:10]
    }
    report["all_violations"].extend(bio_violations)

    # CONTRACT D: Location bleed
    loc_violations = []
    for shot in shots:
        loc_violations.extend(check_location_bleed(shot, project_name=project_name))
    report["contracts"]["D_LOCATION_BLEED"] = {
        "violations": len(loc_violations),
        "pass": len(loc_violations) == 0,
        "details": loc_violations[:10]
    }
    report["all_violations"].extend(loc_violations)

    # CONTRACT E: Scene alignment
    align_violations = check_scene_alignment(shots, scene_manifest)
    report["contracts"]["E_SCENE_ALIGNMENT"] = {
        "violations": len(align_violations),
        "pass": len(align_violations) == 0,
        "details": align_violations[:10]
    }
    report["all_violations"].extend(align_violations)

    # Prompt health checks
    bloat_violations = _check_prompt_bloat(shots)
    # V21.9.1: PROMPT_HEALTH passes if no CRITICAL violations (>3000 chars)
    # Over 2000 is WARNING only — nano-banana handles up to 3000 fine
    critical_bloat = [v for v in bloat_violations if v.get("severity") == "CRITICAL"]
    report["contracts"]["PROMPT_HEALTH"] = {
        "violations": len(bloat_violations),
        "pass": len(critical_bloat) == 0,
        "details": bloat_violations[:10]
    }
    report["all_violations"].extend(bloat_violations)

    # CONTRACT F: Landscape safety (no human language in no-character shots)
    landscape_violations = check_landscape_safety(shots)
    report["contracts"]["F_LANDSCAPE_SAFETY"] = {
        "violations": len(landscape_violations),
        "pass": len(landscape_violations) == 0,
        "details": landscape_violations[:10]
    }
    report["all_violations"].extend(landscape_violations)

    # CONTRACT G: Concatenation integrity (no merged phrases)
    concat_violations = check_concatenation_integrity(shots)
    report["contracts"]["G_CONCAT_INTEGRITY"] = {
        "violations": len(concat_violations),
        "pass": len(concat_violations) == 0,
        "details": concat_violations[:10]
    }
    report["all_violations"].extend(concat_violations)

    # CONTRACT H: Dialogue marker consistency (dialogue shots need "character speaks:" in LTX)
    dialogue_violations = check_dialogue_marker_consistency(shots)
    report["contracts"]["H_DIALOGUE_MARKER"] = {
        "violations": len(dialogue_violations),
        "pass": len(dialogue_violations) == 0,
        "details": dialogue_violations[:10]
    }
    report["all_violations"].extend(dialogue_violations)

    # CONTRACT I: Performance markers (character shots need performs/speaks/reacts)
    perf_violations = check_performance_markers(shots)
    report["contracts"]["I_PERFORMANCE_MARKER"] = {
        "violations": len(perf_violations),
        "pass": len(perf_violations) == 0,
        "details": perf_violations[:10]
    }
    report["all_violations"].extend(perf_violations)

    # CONTRACT J: Intercut integrity (no dual-visible in phone calls)
    intercut_violations = check_intercut_integrity(shots)
    report["contracts"]["J_INTERCUT_INTEGRITY"] = {
        "violations": len(intercut_violations),
        "pass": len(intercut_violations) == 0,
        "details": intercut_violations[:10]
    }
    report["all_violations"].extend(intercut_violations)

    # Count severity
    for v in report["all_violations"]:
        if v.get("severity") == "CRITICAL":
            report["critical_count"] += 1
        else:
            report["warning_count"] += 1

    report["pass"] = report["critical_count"] == 0

    # Save report
    reports_dir = project_path / "reports"
    reports_dir.mkdir(exist_ok=True)

    json_path = reports_dir / f"{project_name}_{timestamp}_audit.json"
    with open(json_path, "w") as f:
        json.dump(report, f, indent=2)

    # Also save human-readable markdown
    md_path = reports_dir / f"{project_name}_{timestamp}_audit.md"
    with open(md_path, "w") as f:
        f.write(f"# ATLAS Audit Report — {project_name}\n")
        f.write(f"**Date:** {report['timestamp']}\n")
        f.write(f"**Shots:** {report['shot_count']}\n")
        f.write(f"**Result:** {'PASS' if report['pass'] else 'FAIL'}\n")
        f.write(f"**Critical:** {report['critical_count']} | **Warnings:** {report['warning_count']}\n\n")
        for contract, data in report["contracts"].items():
            status = "✅ PASS" if data["pass"] else "❌ FAIL"
            f.write(f"## {contract}: {status} ({data['violations']} issues)\n")
            for d in data["details"][:5]:
                f.write(f"- {d.get('shot_id', '?')}: {d.get('rule', '?')} — {d.get('detail', d.get('match', d.get('keyword', '?')))}\n")
            f.write("\n")

    logger.info(f"[AUDIT] {project_name}: {'PASS' if report['pass'] else 'FAIL'} — "
                f"{report['critical_count']} critical, {report['warning_count']} warnings")

    return report


# ═══════════════════════════════════════════════════════════════════
# MOVIE LOCK MODE TOGGLE
# ═══════════════════════════════════════════════════════════════════

def enable_movie_lock(project_path: Path) -> Dict:
    """
    Enable Movie Lock Mode for a project.
    Creates a release snapshot and disables all auto-modifiers.
    """
    lock_file = project_path / ".movie_lock_mode"
    lock_data = {
        "enabled": True,
        "enabled_at": datetime.now().isoformat(),
        "rules": [
            "NO_AUTO_ENRICHMENT",
            "NO_PROMPT_REWRITING",
            "UI_LOCKS_IMMUTABLE",
            "GATE_SNAPSHOT_REQUIRED",
            "BIO_BLEED_BLOCKED",
            "LOCATION_BLEED_BLOCKED",
            "ALL_MUTATIONS_LOGGED"
        ]
    }
    with open(lock_file, "w") as f:
        json.dump(lock_data, f, indent=2)

    # Create release snapshot
    shot_plan_path = project_path / "shot_plan.json"
    if shot_plan_path.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        snapshot_path = project_path / f"release_snapshot_{timestamp}.json"
        import shutil
        shutil.copy2(shot_plan_path, snapshot_path)
        lock_data["release_snapshot"] = str(snapshot_path)

    logger.info(f"[MOVIE_LOCK] Enabled for {project_path.name}")
    return lock_data


def is_movie_lock_active(project_path: Path) -> bool:
    """Check if Movie Lock Mode is active for a project."""
    lock_file = project_path / ".movie_lock_mode"
    if not lock_file.exists():
        return False
    try:
        with open(lock_file) as f:
            data = json.load(f)
        return data.get("enabled", False)
    except Exception:
        return False


def disable_movie_lock(project_path: Path) -> Dict:
    """Disable Movie Lock Mode. Requires explicit user action."""
    lock_file = project_path / ".movie_lock_mode"
    if lock_file.exists():
        os.remove(lock_file)
    logger.info(f"[MOVIE_LOCK] Disabled for {project_path.name}")
    return {"enabled": False, "disabled_at": datetime.now().isoformat()}


# ═══════════════════════════════════════════════════════════════════
# MUTATION LOGGER — EVERY CHANGE TRACKED
# ═══════════════════════════════════════════════════════════════════

def log_mutation(
    project_path: Path,
    shot_id: str,
    field: str,
    before_value: Any,
    after_value: Any,
    reason: str,
    source: str = "unknown"
) -> None:
    """
    Log every field mutation to an append-only log file.
    This is the regression detection backbone.
    """
    log_path = project_path / "reports" / "mutation_log.jsonl"
    log_path.parent.mkdir(exist_ok=True)

    entry = {
        "timestamp": datetime.now().isoformat(),
        "shot_id": shot_id,
        "field": field,
        "before_hash": _hash_value(before_value),
        "after_hash": _hash_value(after_value),
        "before_len": len(str(before_value or "")),
        "after_len": len(str(after_value or "")),
        "reason": reason,
        "source": source
    }

    with open(log_path, "a") as f:
        f.write(json.dumps(entry) + "\n")


def check_for_regressions(project_path: Path) -> List[dict]:
    """
    Scan mutation log for patterns that indicate regressions
    (same shot/field being changed back and forth).
    """
    log_path = project_path / "reports" / "mutation_log.jsonl"
    if not log_path.exists():
        return []

    # Build history per shot+field
    history = {}  # (shot_id, field) → [entries]
    with open(log_path) as f:
        for line in f:
            try:
                entry = json.loads(line.strip())
                key = (entry["shot_id"], entry["field"])
                history.setdefault(key, []).append(entry)
            except Exception:
                continue

    regressions = []
    for (sid, field), entries in history.items():
        if len(entries) < 3:
            continue
        # Check for A→B→A pattern (hash of first == hash of third)
        hashes = [e["after_hash"] for e in entries]
        for i in range(2, len(hashes)):
            if hashes[i] == hashes[i-2] and hashes[i] != hashes[i-1]:
                regressions.append({
                    "shot_id": sid,
                    "field": field,
                    "pattern": "A→B→A regression detected",
                    "first_change": entries[i-2]["timestamp"],
                    "reversion": entries[i]["timestamp"],
                    "source_a": entries[i-2]["source"],
                    "source_b": entries[i-1]["source"],
                    "severity": "REGRESSION"
                })

    return regressions


# ═══════════════════════════════════════════════════════════════════
# INTERNAL HELPERS
# ═══════════════════════════════════════════════════════════════════

def _hash_value(value) -> str:
    """SHA256 hash of any value for comparison."""
    return hashlib.sha256(str(value).encode()).hexdigest()[:16]


def _compute_shot_hash(shot: dict) -> str:
    """Hash the locked fields of a shot for integrity checking."""
    data = {f: shot.get(f) for f in LOCKED_FIELDS}
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:32]


def _compute_payload_hash(payload: dict) -> str:
    """Hash a gate snapshot payload entry."""
    # Exclude _hash from the hash computation
    data = {k: v for k, v in payload.items() if k != "_hash"}
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:32]


def _check_duplicate_enrichment(shots: List[dict]) -> List[dict]:
    """
    CONTRACT B: Detect duplicate enrichment markers in prompts.
    Signs of double-enrichment: repeated "composition:", "subtext:",
    "performance:", "CINEMATIC:", etc.
    """
    violations = []
    dup_markers = [
        "composition:", "subtext:", "performance:", "pacing:",
        "CINEMATIC:", "character performs:", "character speaks:",
        "wearing:", "background:", "Timing:"
    ]

    for shot in shots:
        sid = shot.get("shot_id", "")
        nano = shot.get("nano_prompt", "") or ""
        ltx = shot.get("ltx_motion_prompt", "") or ""

        for marker in dup_markers:
            nano_count = nano.lower().count(marker.lower())
            if nano_count > 1:
                violations.append({
                    "shot_id": sid,
                    "field": "nano_prompt",
                    "marker": marker,
                    "count": nano_count,
                    "rule": "CONTRACT_B_SINGLE_ENRICHMENT",
                    "detail": f"'{marker}' appears {nano_count}x in nano_prompt",
                    "severity": "WARNING"
                })

            ltx_count = ltx.lower().count(marker.lower())
            if ltx_count > 1:
                violations.append({
                    "shot_id": sid,
                    "field": "ltx_motion_prompt",
                    "marker": marker,
                    "count": ltx_count,
                    "rule": "CONTRACT_B_SINGLE_ENRICHMENT",
                    "detail": f"'{marker}' appears {ltx_count}x in ltx_motion_prompt",
                    "severity": "WARNING"
                })

    return violations


def _check_prompt_bloat(shots: List[dict]) -> List[dict]:
    """Check for prompt bloat (>2000 chars is suspicious, >3000 is bad)."""
    violations = []
    for shot in shots:
        sid = shot.get("shot_id", "")
        nano = shot.get("nano_prompt", "") or ""
        if len(nano) > 2000:
            violations.append({
                "shot_id": sid,
                "field": "nano_prompt",
                "length": len(nano),
                "rule": "PROMPT_BLOAT",
                "detail": f"nano_prompt is {len(nano)} chars (max recommended: 2000)",
                "severity": "CRITICAL" if len(nano) > 3000 else "WARNING"
            })
    return violations


# ═══════════════════════════════════════════════════════════════════
# CONTRACT F: LANDSCAPE SAFETY — NO HUMAN LANGUAGE IN NO-CHARACTER SHOTS
# Historical Issue #16: breathing, micro-expression, blinks in landscape shots
# ═══════════════════════════════════════════════════════════════════

HUMAN_BODY_PATTERNS = [
    r'\bbreathing\b', r'\bmicro[- ]?expression', r'\bblinks?\b',
    r'\bchest\s+rise\b', r'\bpupil\b', r'\bnostril\b', r'\blip\s+quiver\b',
    r'\bswallow\b', r'\bjaw\s+(?:clench|tight)', r'\bfurrowed?\s+brow\b',
    r'\beye\s*line\b', r'\bgaze\s+shift\b', r'\bsubtle\s+nod\b',
    r'\bface\s+stable\b', r'\bcharacter\s+performs\b',
    r'\bcharacter\s+speaks\b', r'\bcharacter\s+reacts\b',
    r'\bperformance:\b', r'\bsubtext:\b',
]
_HUMAN_BODY_COMPILED = [re.compile(p, re.IGNORECASE) for p in HUMAN_BODY_PATTERNS]


def check_landscape_safety(shots: List[dict]) -> List[dict]:
    """
    CONTRACT F: No human performance language in shots with 0 characters.
    Historical: Dec-Feb had 'breathing', 'micro-expression' in establishing/B-roll shots.
    """
    violations = []
    for shot in shots:
        chars = shot.get("characters", [])
        if chars and len(chars) > 0:
            continue  # Has characters, skip

        # CHILD V.O. shots may have dialogue-direction markers (e.g., "no blink on final words")
        # These are about voice delivery, not visible performance — skip.
        if shot.get("_child_vo"):
            continue

        sid = shot.get("shot_id", "")
        nano = (shot.get("nano_prompt", "") or "").lower()
        ltx = (shot.get("ltx_motion_prompt", "") or "").lower()
        combined = nano + " " + ltx

        # Strip negative instructions ("no blink", "NO morphing") before checking
        # These are telling the model NOT to do something, not injecting human language
        import re as _re_f
        combined = _re_f.sub(r'\bno\s+', '', combined)
        combined = _re_f.sub(r'\bnot?\s+', '', combined)

        for i, pat in enumerate(_HUMAN_BODY_COMPILED):
            matches = pat.findall(combined)
            for m in matches:
                violations.append({
                    "shot_id": sid,
                    "match": m,
                    "rule": "CONTRACT_F_LANDSCAPE_SAFETY",
                    "detail": f"Human body language '{m}' in no-character shot",
                    "severity": "CRITICAL"
                })
    return violations


# ═══════════════════════════════════════════════════════════════════
# CONTRACT G: CONCATENATION INTEGRITY — NO MERGED PHRASES
# Historical Issue #20: "character consistentmeasured deliberate tempo"
# ═══════════════════════════════════════════════════════════════════

# Patterns that indicate broken concatenation (word:word without space)
_CONCAT_BUG_PATTERNS = [
    # Lowercase letter immediately followed by uppercase (no space)
    r'[a-z][A-Z]',
    # Known broken concatenations from December audits
    r'consistent(?:measured|subtle|slow|static)',
    r'appearance(?:measured|subtle|slow|static)',
    r'screen(?:creep|static|slow|push)',
    r'morphing(?:face|NO|character)',
    r'stable(?:NO|measured|character)',
]
_CONCAT_BUG_COMPILED = [re.compile(p) for p in _CONCAT_BUG_PATTERNS]


def check_concatenation_integrity(shots: List[dict]) -> List[dict]:
    """
    CONTRACT G: Detect phrases merged without separators.
    Historical: Dedup/strip operations removed separating whitespace.
    """
    violations = []
    for shot in shots:
        sid = shot.get("shot_id", "")
        nano = shot.get("nano_prompt", "") or ""
        ltx = shot.get("ltx_motion_prompt", "") or ""

        for prompt_field, prompt_text in [("nano_prompt", nano), ("ltx_motion_prompt", ltx)]:
            if not prompt_text:
                continue
            # Check for known broken concatenation patterns
            for i, pat in enumerate(_CONCAT_BUG_COMPILED[1:], 1):  # Skip camelCase check for now
                matches = pat.findall(prompt_text)
                for m in matches:
                    violations.append({
                        "shot_id": sid,
                        "field": prompt_field,
                        "match": m,
                        "rule": "CONTRACT_G_CONCAT_INTEGRITY",
                        "detail": f"Broken concatenation '{m}' in {prompt_field}",
                        "severity": "WARNING"
                    })

    return violations


# ═══════════════════════════════════════════════════════════════════
# CONTRACT H: DIALOGUE MARKER CONSISTENCY
# Historical Issue #9: 8 shots with dialogue but no "character speaks:" in LTX
# ═══════════════════════════════════════════════════════════════════

def check_dialogue_marker_consistency(shots: List[dict]) -> List[dict]:
    """
    CONTRACT H: Every shot with dialogue_text AND visible characters MUST have
    'character speaks:' in LTX. Without this, LTX-2 generates static faces.
    Historical: V17.7.6 fixed 98 shots missing this marker.

    Excludes: V.O.-only shots (no visible characters), CHILD V.O. shots.
    """
    violations = []
    for shot in shots:
        sid = shot.get("shot_id", "")
        dialogue = (shot.get("dialogue_text", "") or shot.get("dialogue", "") or "").strip()
        if not dialogue:
            continue

        # Skip shots with no visible characters (V.O., CHILD V.O., landscape)
        chars = shot.get("characters", [])
        if not chars or len(chars) == 0:
            continue
        if shot.get("_child_vo"):
            continue

        ltx = (shot.get("ltx_motion_prompt", "") or "").lower()
        if "character speaks:" not in ltx:
            violations.append({
                "shot_id": sid,
                "rule": "CONTRACT_H_DIALOGUE_MARKER",
                "detail": f"Shot has dialogue + characters but LTX lacks 'character speaks:' marker",
                "severity": "CRITICAL"
            })
    return violations


# ═══════════════════════════════════════════════════════════════════
# CONTRACT I: PERFORMANCE MARKER REQUIREMENT
# Historical Issue: Shots with characters but no performance/speaks/reacts marker
# Rule 142: Every character shot MUST have a performance marker
# ═══════════════════════════════════════════════════════════════════

def check_performance_markers(shots: List[dict]) -> List[dict]:
    """
    CONTRACT I: Every shot with characters[] must have at least ONE of:
      - 'character performs:'
      - 'character speaks:'
      - 'character reacts:'
    in the LTX motion prompt.
    """
    violations = []
    for shot in shots:
        chars = shot.get("characters", [])
        if not chars or len(chars) == 0:
            continue

        sid = shot.get("shot_id", "")
        ltx = (shot.get("ltx_motion_prompt", "") or "").lower()

        has_performs = "character performs:" in ltx
        has_speaks = "character speaks:" in ltx
        has_reacts = "character reacts:" in ltx

        if not (has_performs or has_speaks or has_reacts):
            violations.append({
                "shot_id": sid,
                "characters": chars,
                "rule": "CONTRACT_I_PERFORMANCE_MARKER",
                "detail": f"Character shot has no performance marker in LTX (needs performs/speaks/reacts)",
                "severity": "WARNING"
            })
    return violations


# ═══════════════════════════════════════════════════════════════════
# CONTRACT J: INTERCUT INTEGRITY — NO DUAL-VISIBLE IN PHONE CALLS
# Historical Issue #6: Both characters visible in intercut shots
# ═══════════════════════════════════════════════════════════════════

def check_intercut_integrity(shots: List[dict]) -> List[dict]:
    """
    CONTRACT J: In intercut scenes, each shot should show exactly ONE visible character.
    Historical: Scene 002 phone call had both EVELYN and LAWYER visible in same shot.
    """
    violations = []
    for shot in shots:
        sid = shot.get("shot_id", "")
        is_intercut = shot.get("_intercut") or shot.get("is_intercut")
        if not is_intercut:
            continue

        chars = shot.get("characters", [])
        if len(chars) > 1:
            violations.append({
                "shot_id": sid,
                "characters": chars,
                "rule": "CONTRACT_J_INTERCUT_INTEGRITY",
                "detail": f"Intercut shot has {len(chars)} visible characters (should be 1): {chars}",
                "severity": "CRITICAL"
            })
    return violations
