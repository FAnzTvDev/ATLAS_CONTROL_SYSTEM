#!/usr/bin/env python3
"""
Lightweight guardrail for prompt consistency.

Validates that:
  - Dialogue shots specify reference_needed (locks casting)
  - Dialogue entries alternate within a scene (no one-sided conversations)
  - Shot durations obey minimum breathing length (>=6s, >=8s when dialogue)
  - Camera metadata (camera, lens_specs, lighting, character_blocking) are present
  - Period consistency: locations with years (1890) don't get "Present day" or "2025" in prompts

Usage:
    python3 tools/prompt_consistency_checker.py blackwood_parallel_test.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


def validate_period_consistency(shot: Dict) -> List[str]:
    """
    Validate that prompt period markers match location/scene time period.

    Catches issues like:
    - Location says "1890" but prompt says "Present day, 2025"
    - Historical scene with modern period markers
    """
    issues: List[str] = []
    sid = shot.get("shot_id", "unknown")
    prompt = shot.get("prompt", "")
    location = shot.get("location", "")

    # Detect historical year in location (1700-1950)
    year_match = re.search(r'\b(1[789]\d{2}|19[0-4]\d)\b', location)

    # Detect modern/anachronistic markers in prompt
    modern_markers = [
        "Present day",
        "2020", "2021", "2022", "2023", "2024", "2025", "2026",
        "contemporary",
        "modern period",
    ]

    if year_match:
        historical_year = year_match.group(1)
        for marker in modern_markers:
            if marker.lower() in prompt.lower():
                issues.append(
                    f"{sid}: PERIOD MISMATCH - Location has year {historical_year} "
                    f"but prompt contains '{marker}'"
                )

    # Also check for explicit Victorian/historical locations without proper period markers
    historical_keywords = ["victorian", "1890", "1880", "1870", "medieval", "castle", "manor"]
    if any(kw in location.lower() for kw in historical_keywords):
        if "2025" in prompt or "Present day" in prompt:
            issues.append(
                f"{sid}: PERIOD MISMATCH - Historical location '{location[:40]}...' "
                f"but prompt contains modern period markers"
            )

    return issues


def load_manifest(path: Path) -> Dict:
    return json.loads(path.read_text())


def validate_scene(scene: Dict) -> List[str]:
    issues: List[str] = []
    dialogue_turn = None  # Track alternating speaker labels
    speakers: List[str] = []
    for shot in scene.get("shots", []):
        sid = shot.get("shot_id")
        duration = float(shot.get("duration", 0))
        dialogue = shot.get("dialogue")
        reference_needed = shot.get("reference_needed")
        camera = shot.get("camera")
        lens_specs = shot.get("lens_specs")
        lighting = shot.get("lighting")
        blocking = shot.get("character_blocking")

        # Validate period consistency (catches 1890 location with "2025" prompts)
        period_issues = validate_period_consistency(shot)
        issues.extend(period_issues)

        if duration < 6:
            issues.append(f"{sid}: duration {duration}s < 6s minimum")
        if dialogue and duration < 8:
            issues.append(f"{sid}: dialogue present but duration {duration}s < 8s breathing minimum")
        if dialogue and not reference_needed:
            issues.append(f"{sid}: dialogue present but reference_needed missing")
        if dialogue:
            speaker = dialogue.split(":")[0].strip().split()[0] if ":" in dialogue else dialogue.split()[0]
            if speaker not in speakers:
                speakers.append(speaker)
            if dialogue_turn == speaker and len(speakers) >= 2:
                issues.append(f"{sid}: same speaker '{speaker}' twice in a row within scene {scene['scene_id']}")
            dialogue_turn = speaker

        if not all([camera, lens_specs, lighting, blocking]):
            issues.append(f"{sid}: missing camera/lens/lighting/blocking metadata")

        framing = shot.get("framing_matrix")
        if not framing or not framing.get("primary_anchor"):
            issues.append(f"{sid}: framing_matrix missing or lacks primary_anchor")

        if not shot.get("continuity_note"):
            issues.append(f"{sid}: continuity_note missing")

        if not shot.get("timeline_role"):
            issues.append(f"{sid}: timeline_role missing")

        motion_meta = shot.get("ltx_motion_metadata")
        if not motion_meta or not motion_meta.get("start_pose"):
            issues.append(f"{sid}: ltx_motion_metadata missing start_pose/end_pose")

    return issues


def validate_shot_plan(shot_plan: List[Dict], fix_issues: bool = False) -> Dict[str, Any]:
    """
    Validate a shot_plan.json file (list of shots) for period consistency.

    Returns:
        Dict with 'issues' list, 'fixed_count' if fix_issues=True, and 'valid' bool.
    """
    issues: List[str] = []
    fixed_count = 0

    for shot in shot_plan:
        period_issues = validate_period_consistency(shot)
        issues.extend(period_issues)

        if fix_issues and period_issues:
            # Attempt to fix the prompt
            prompt = shot.get("prompt", "")
            location = shot.get("location", "")

            # Detect the correct period from location
            year_match = re.search(r'\b(1[789]\d{2}|19[0-4]\d)\b', location)
            if year_match:
                year = year_match.group(1)
                if year.startswith("18"):
                    correct_period = f"Victorian era {year}, period authentic costumes and props"
                elif year.startswith("19") and int(year) < 1950:
                    correct_period = f"Early 20th century {year}, period authentic"
                else:
                    correct_period = f"{year} period authentic"
            elif any(kw in location.lower() for kw in ["victorian", "1890", "manor"]):
                correct_period = "Victorian era 1890s, period authentic costumes and props"
            else:
                correct_period = "period authentic"

            # Replace wrong period markers
            new_prompt = prompt.replace("Present day, 2025 period authentic", correct_period)
            new_prompt = new_prompt.replace("Present day period authentic", correct_period)
            if new_prompt != prompt:
                shot["prompt"] = new_prompt
                fixed_count += 1

    return {
        "issues": issues,
        "fixed_count": fixed_count,
        "valid": len(issues) == 0,
        "total_shots": len(shot_plan)
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Prompt consistency checker")
    parser.add_argument("manifest", help="Path to manifest JSON")
    args = parser.parse_args()

    manifest_path = Path(args.manifest).expanduser().resolve()
    if not manifest_path.exists():
        print(f"❌ Manifest not found: {manifest_path}", file=sys.stderr)
        sys.exit(2)

    manifest = load_manifest(manifest_path)
    all_issues: List[str] = []
    for scene in manifest.get("scenes", []):
        scene_issues = validate_scene(scene)
        if scene_issues:
            header = f"\n[Scene {scene.get('scene_id')}]"
            all_issues.append(header)
            all_issues.extend(f" - {msg}" for msg in scene_issues)

    if all_issues:
        print("\n".join(all_issues))
        print("\n❌ Prompt consistency guard failed.")
        sys.exit(1)

    print(f"✅ Prompt consistency guard passed for {manifest_path.name}")


if __name__ == "__main__":
    main()
