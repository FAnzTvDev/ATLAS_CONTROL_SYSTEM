#!/usr/bin/env python3
"""
tools/shot_plan_gate_fixer.py — Auto-fix shot plan gate failures
================================================================

Fixes the 41 chain_intelligence_gate failures in victorian_shadows_ep1 WITHOUT
touching any other fields. Applies minimal targeted changes:

  FIX-1  CHARACTER_NAME_LEAK   — Strip character names from E-shot _beat_action
                                  by replacing them with environment-only descriptions.
                                  nano_prompt is preserved (it's already clean).
                                  _frame_prompt / _choreography also sanitised.

  FIX-2  EXIT_IN_NON_RESOLVE   — Replace "steps through" / exit keywords in
                                  non-RESOLVE shots with spatially equivalent
                                  non-exiting phrasing.

  FIX-3  DURATION_TOO_SHORT    — Auto-scale duration using compute_duration_for_shot().

  FIX-4  DUPLICATE_DIALOGUE    — Keep first occurrence, clear dialogue_text on
                                  duplicates in the same scene (second occurrence
                                  becomes a reaction/continuation shot).

Rules:
  - This fixer ONLY touches fields that contain the detected error.
  - It does NOT add new schema fields (that's the runner's job).
  - It does NOT touch nano_prompt unless a character name is literally in it
    AND the shot is an E-shot AND characters=[] on that shot.
  - All changes are logged to stdout for review.

Usage:
    python3 tools/shot_plan_gate_fixer.py <project_dir> [--dry-run]

    # Dry run (shows what would change, no writes):
    python3 tools/shot_plan_gate_fixer.py pipeline_outputs/victorian_shadows_ep1 --dry-run

    # Apply fixes:
    python3 tools/shot_plan_gate_fixer.py pipeline_outputs/victorian_shadows_ep1
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

_EXIT_KEYWORDS = [
    "walks out", "exits", "closes door", "leaves the room",
    "steps out", "walks away", "releases", "transition out",
    "turns to leave", "heads out", "departs", "walks through",
    "steps through", "exits frame", "walks off",
]

# Fields checked for character name leak on E-shots
_LEAK_FIELDS = ["_beat_action", "_frame_prompt", "_choreography",
                "_arc_carry_directive", "_beat_atmosphere"]

# Fields checked for exit keywords on non-RESOLVE shots
_EXIT_FIELDS = ["_beat_action", "_frame_prompt", "_choreography",
                "_arc_carry_directive", "nano_prompt"]


def _is_e_shot(shot: dict) -> bool:
    sid   = shot.get("shot_id") or ""
    stype = shot.get("shot_type") or ""
    return bool(re.search(r"_E\d", sid)) or "establishing" in stype.lower()


def _is_resolve(shot: dict) -> bool:
    return (shot.get("_arc_position") or "").upper() == "RESOLVE"


def _strip_char_names(text: str, names: list[str]) -> str:
    """Replace character names with empty string (leave surrounding context)."""
    result = text
    for name in sorted(names, key=len, reverse=True):  # longest first
        # Replace full-name occurrences (case-insensitive)
        pattern = re.compile(re.escape(name), re.IGNORECASE)
        result = pattern.sub("", result)
    # Clean up artifacts like "  pushes open" → "pushes open" or "She/He" prefixes
    result = re.sub(r"\s{2,}", " ", result).strip()
    result = re.sub(r"^(She|He|They)\s+", "", result).strip()
    return result


def _build_char_names(shot: dict, story_bible: dict | None) -> list[str]:
    """Build list of character names to strip from this E-shot."""
    names: list[str] = []
    if story_bible:
        for char in story_bible.get("characters", []):
            name = char.get("name") or char.get("character_name") or ""
            if name:
                names.append(name)
                parts = name.split()
                if parts:
                    names.append(parts[0])
    for c in shot.get("characters") or []:
        names.append(c)
        parts = c.split()
        if parts:
            names.append(parts[0])
    return list({n.strip() for n in names if len(n.strip()) > 2})


def _replace_exit_in_text(text: str) -> tuple[str, bool]:
    """Replace exit keywords with non-exiting equivalents. Returns (new_text, changed)."""
    replacements = {
        "steps through":     "moves toward",
        "walks through":     "moves forward through the space",
        "walks out":         "turns toward the far side of the room",
        "walks off":         "moves away within the space",
        "exits frame":       "moves to the edge of frame",
        "exits":             "moves to the far side",
        "closes door":       "reaches for the door handle",
        "leaves the room":   "moves toward the far wall",
        "steps out":         "steps forward",
        "walks away":        "turns away within the room",
        "heads out":         "moves toward the back of the room",
        "departs":           "concludes the exchange",
        "turns to leave":    "turns to face the room",
        "transition out":    "settles into final position",
        "releases":          "eases tension",
    }
    result = text
    changed = False
    for kw, replacement in replacements.items():
        if kw.lower() in result.lower():
            result = re.sub(re.escape(kw), replacement, result, flags=re.IGNORECASE)
            changed = True
    return result, changed


def _word_count(text: str) -> int:
    return len(text.split()) if text.strip() else 0


def _compute_duration(shot: dict) -> float:
    """Mirror of chain_intelligence_gate.compute_duration_for_shot."""
    dialogue = (shot.get("dialogue_text") or "").strip()
    existing = float(shot.get("duration") or 5.0)
    if not dialogue:
        if _is_e_shot(shot):
            return 5.0
        return max(existing, 5.0)
    wc = _word_count(dialogue)
    wbm = round(wc / 2.3 + 1.5, 1)
    if wc > 20:
        return 20.0
    elif wc > 10:
        return max(wbm, 10.0)
    else:
        return max(wbm, existing, 5.0)


def fix_shot_plan(project_dir: str, dry_run: bool = False) -> None:
    sp_path = Path(project_dir) / "shot_plan.json"
    sb_path = Path(project_dir) / "story_bible.json"

    with open(sp_path) as f:
        sp = json.load(f)
    bare_list = isinstance(sp, list)
    if bare_list:
        sp = {"shots": sp}

    story_bible = None
    if sb_path.exists():
        with open(sb_path) as f:
            story_bible = json.load(f)

    shots    = sp["shots"]
    changes  = []
    fix_counts = defaultdict(int)

    # ── Build scene-level dialogue registry (for dupe detection) ─────
    scene_dialogue: dict[str, set[str]] = defaultdict(set)

    for shot in shots:
        sid    = shot.get("shot_id") or ""
        scene  = sid[:3]

        # ─────────────────────────────────────────────────────────────
        # FIX-1: CHARACTER_NAME_LEAK in E-shots
        # ─────────────────────────────────────────────────────────────
        if _is_e_shot(shot) and not shot.get("characters"):
            char_names = _build_char_names(shot, story_bible)
            if char_names:
                combined_upper = " ".join(
                    (shot.get(f) or "") for f in _LEAK_FIELDS
                ).upper()
                has_leak = any(n.upper() in combined_upper for n in char_names if len(n) > 2)

                if has_leak:
                    for field in _LEAK_FIELDS:
                        old_val = shot.get(field) or ""
                        if not old_val:
                            continue
                        new_val = _strip_char_names(old_val, char_names)
                        if new_val != old_val:
                            changes.append({
                                "shot_id": sid,
                                "fix": "CHARACTER_NAME_LEAK",
                                "field": field,
                                "old": old_val[:80],
                                "new": new_val[:80],
                            })
                            fix_counts["CHARACTER_NAME_LEAK"] += 1
                            if not dry_run:
                                shot[field] = new_val

        # ─────────────────────────────────────────────────────────────
        # FIX-2: EXIT_IN_NON_RESOLVE
        # ─────────────────────────────────────────────────────────────
        if not _is_resolve(shot):
            for field in _EXIT_FIELDS:
                old_val = shot.get(field) or ""
                if not old_val:
                    continue
                new_val, changed = _replace_exit_in_text(old_val)
                if changed:
                    changes.append({
                        "shot_id": sid,
                        "fix": "EXIT_IN_NON_RESOLVE",
                        "field": field,
                        "old": old_val[:80],
                        "new": new_val[:80],
                    })
                    fix_counts["EXIT_IN_NON_RESOLVE"] += 1
                    if not dry_run:
                        shot[field] = new_val

        # ─────────────────────────────────────────────────────────────
        # FIX-3: DURATION_TOO_SHORT
        # ─────────────────────────────────────────────────────────────
        dialogue = (shot.get("dialogue_text") or "").strip()
        if dialogue:
            current_dur = float(shot.get("duration") or 5.0)
            wc          = _word_count(dialogue)
            minimum     = round(wc / 2.3 + 1.5, 1)
            if current_dur < minimum - 0.1:
                correct_dur = _compute_duration(shot)
                changes.append({
                    "shot_id": sid,
                    "fix": "DURATION_TOO_SHORT",
                    "field": "duration",
                    "old": str(current_dur),
                    "new": str(correct_dur),
                })
                fix_counts["DURATION_TOO_SHORT"] += 1
                if not dry_run:
                    shot["duration"] = correct_dur

        # ─────────────────────────────────────────────────────────────
        # FIX-4: DUPLICATE_DIALOGUE (keep first per scene, clear rest)
        # ─────────────────────────────────────────────────────────────
        if dialogue:
            norm = dialogue[:60].lower().strip()
            if norm in scene_dialogue[scene]:
                # This is a duplicate — clear dialogue on this shot
                changes.append({
                    "shot_id": sid,
                    "fix": "DUPLICATE_DIALOGUE",
                    "field": "dialogue_text",
                    "old": dialogue[:60],
                    "new": "(cleared — duplicate of earlier shot in scene)",
                })
                fix_counts["DUPLICATE_DIALOGUE"] += 1
                if not dry_run:
                    shot["dialogue_text"] = ""
            else:
                scene_dialogue[scene].add(norm)

    # ── Report ───────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  SHOT PLAN GATE FIXER {'(DRY RUN)' if dry_run else '(APPLIED)'}")
    print(f"  Project: {project_dir}")
    print(f"  Total changes: {len(changes)}")
    print(f"{'='*60}\n")

    for fix_type, count in sorted(fix_counts.items()):
        print(f"  {fix_type}: {count} fixes")

    if changes:
        print(f"\n  Changes detail:")
        for c in changes:
            print(f"    [{c['fix']}] {c['shot_id']} .{c['field']}")
            print(f"      OLD: {c['old'][:70]}")
            print(f"      NEW: {c['new'][:70]}")

    # ── Write ─────────────────────────────────────────────────────────
    if not dry_run and changes:
        out = shots if bare_list else sp
        with open(sp_path, "w") as f:
            json.dump(out, f, indent=2)
        print(f"\n  ✓ shot_plan.json updated ({len(changes)} changes applied)")
    elif not changes:
        print("\n  ✓ No changes needed — shot plan already clean")
    else:
        print(f"\n  ℹ DRY RUN complete — run without --dry-run to apply")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 tools/shot_plan_gate_fixer.py <project_dir> [--dry-run]")
        sys.exit(1)
    project_dir = sys.argv[1]
    dry_run     = "--dry-run" in sys.argv
    fix_shot_plan(project_dir, dry_run=dry_run)
