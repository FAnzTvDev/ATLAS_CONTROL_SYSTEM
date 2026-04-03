#!/usr/bin/env python3
"""
NARRATIVE RUNTIME GOVERNOR - V17 Intelligence Layer
====================================================
Applies narrative intelligence to duration balancing.

Unlike mechanical rebalancing, this:
- Understands emotional beats
- Protects high-drama sequences
- Weights dialogue-heavy shots
- Preserves climax pacing
- Classifies shot roles

Usage:
    python3 tools/narrative_runtime_governor.py ravencroft_v17 --analyze
    python3 tools/narrative_runtime_governor.py ravencroft_v17 --apply
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple
from collections import defaultdict

# Emotional intensity weights (higher = more important, protect duration)
EMOTIONAL_WEIGHTS = {
    "dread": 1.3,
    "tension": 1.3,
    "revelation": 1.5,
    "confrontation": 1.4,
    "grief": 1.2,
    "hope": 1.1,
    "fear": 1.3,
    "anger": 1.2,
    "love": 1.1,
    "suspense": 1.3,
    "horror": 1.4,
    "mystery": 1.2,
    "default": 1.0
}

# Shot type duration preferences (in seconds)
SHOT_TYPE_DURATIONS = {
    "wide": {"min": 6, "ideal": 10, "max": 15},      # Establishing - moderate
    "medium": {"min": 8, "ideal": 12, "max": 18},    # Dialogue - longer
    "close": {"min": 6, "ideal": 10, "max": 14},     # Emotional - moderate
    "insert": {"min": 3, "ideal": 5, "max": 8},      # Quick cuts
    "establishing": {"min": 5, "ideal": 8, "max": 12},
}

# Shot role classifications (inferred from content)
SHOT_ROLES = {
    "establishing": {"weight": 0.8, "compressible": True},
    "coverage": {"weight": 0.9, "compressible": True},
    "dialogue": {"weight": 1.2, "compressible": False},
    "reaction": {"weight": 0.7, "compressible": True},
    "climax": {"weight": 1.5, "compressible": False},
    "transition": {"weight": 0.6, "compressible": True},
    "insert": {"weight": 0.5, "compressible": True},
    "emotional_anchor": {"weight": 1.4, "compressible": False},
}


def classify_shot_role(shot: Dict) -> str:
    """Infer shot role from available data."""
    shot_type = (shot.get("type") or shot.get("shot_type") or "medium").lower()
    has_dialogue = shot.get("dialogue") or False
    characters = shot.get("characters", [])
    emotional_tone = (shot.get("emotional_tone") or "").lower()
    nano_prompt = (shot.get("nano_prompt") or "").lower()

    # Classification logic
    if shot_type == "wide" and len(characters) == 0:
        return "establishing"

    if has_dialogue and len(characters) >= 2:
        if emotional_tone in ["confrontation", "tension", "anger"]:
            return "climax"
        return "dialogue"

    if has_dialogue and len(characters) == 1:
        return "dialogue"

    if shot_type == "close" and emotional_tone in ["dread", "fear", "grief", "revelation"]:
        return "emotional_anchor"

    if shot_type == "close" and not has_dialogue:
        return "reaction"

    if "insert" in nano_prompt or shot_type == "insert":
        return "insert"

    if shot_type == "wide":
        return "establishing"

    return "coverage"


def calculate_scene_priority(scene_shots: List[Dict], scene_id: str,
                            total_scenes: int, scene_index: int) -> float:
    """Calculate scene priority score based on narrative factors."""
    priority = 1.0

    # Act structure weighting
    act_position = scene_index / total_scenes
    if act_position < 0.15:  # Opening
        priority *= 1.1
    elif 0.45 < act_position < 0.55:  # Midpoint
        priority *= 1.2
    elif act_position > 0.85:  # Climax/Resolution
        priority *= 1.3

    # Dialogue density
    dialogue_shots = sum(1 for s in scene_shots if s.get("dialogue"))
    dialogue_ratio = dialogue_shots / len(scene_shots) if scene_shots else 0
    priority *= (1 + dialogue_ratio * 0.3)

    # Emotional intensity
    emotional_scores = []
    for shot in scene_shots:
        tone = (shot.get("emotional_tone") or "default").lower()
        emotional_scores.append(EMOTIONAL_WEIGHTS.get(tone, 1.0))
    avg_emotional = sum(emotional_scores) / len(emotional_scores) if emotional_scores else 1.0
    priority *= avg_emotional

    # Character density (more characters = more important)
    all_chars = set()
    for shot in scene_shots:
        all_chars.update(shot.get("characters", []))
    if len(all_chars) >= 3:
        priority *= 1.15
    elif len(all_chars) >= 2:
        priority *= 1.05

    return round(priority, 2)


def analyze_project(project_path: Path) -> Dict:
    """Analyze project for narrative intelligence."""
    shot_plan_path = project_path / "shot_plan.json"
    story_bible_path = project_path / "story_bible.json"

    with open(shot_plan_path) as f:
        shot_plan = json.load(f)

    story_bible = {}
    if story_bible_path.exists():
        with open(story_bible_path) as f:
            story_bible = json.load(f)

    shots = shot_plan.get("shots", [])
    target_runtime = shot_plan.get("metadata", {}).get("target_runtime", 2700)

    # Group by scene
    scenes = defaultdict(list)
    for shot in shots:
        scene_id = shot.get("scene_id", "UNKNOWN")
        scenes[scene_id].append(shot)

    scene_ids = sorted(scenes.keys())
    total_scenes = len(scene_ids)

    analysis = {
        "project": project_path.name,
        "target_runtime": target_runtime,
        "total_shots": len(shots),
        "total_scenes": total_scenes,
        "scenes": {},
        "protected_shots": [],
        "compressible_shots": [],
        "recommendations": []
    }

    total_duration = 0
    protected_duration = 0

    for idx, scene_id in enumerate(scene_ids):
        scene_shots = scenes[scene_id]
        scene_duration = sum(s.get("duration", 10) for s in scene_shots)
        total_duration += scene_duration

        # Calculate priority
        priority = calculate_scene_priority(scene_shots, scene_id, total_scenes, idx)

        # Classify shots
        shot_analysis = []
        for shot in scene_shots:
            role = classify_shot_role(shot)
            role_info = SHOT_ROLES.get(role, SHOT_ROLES["coverage"])

            shot_info = {
                "shot_id": shot.get("shot_id"),
                "duration": shot.get("duration", 10),
                "role": role,
                "weight": role_info["weight"],
                "compressible": role_info["compressible"],
                "emotional_tone": shot.get("emotional_tone", "default"),
                "has_dialogue": bool(shot.get("dialogue")),
                "characters": len(shot.get("characters", []))
            }

            shot_analysis.append(shot_info)

            if not role_info["compressible"]:
                analysis["protected_shots"].append(shot.get("shot_id"))
                protected_duration += shot.get("duration", 10)
            else:
                analysis["compressible_shots"].append(shot.get("shot_id"))

        analysis["scenes"][scene_id] = {
            "shot_count": len(scene_shots),
            "duration": scene_duration,
            "priority": priority,
            "shots": shot_analysis,
            "protected_count": sum(1 for s in shot_analysis if not s["compressible"]),
            "dialogue_count": sum(1 for s in shot_analysis if s["has_dialogue"])
        }

    analysis["current_duration"] = total_duration
    analysis["protected_duration"] = protected_duration
    analysis["compressible_duration"] = total_duration - protected_duration

    # Generate recommendations
    variance = (total_duration - target_runtime) / target_runtime * 100

    if variance > 10:
        analysis["recommendations"].append(
            f"Over target by {variance:.1f}%. Compress only compressible shots."
        )
    elif variance < -10:
        analysis["recommendations"].append(
            f"Under target by {abs(variance):.1f}%. Extend emotional anchor shots."
        )

    # Find top priority scenes
    sorted_scenes = sorted(
        analysis["scenes"].items(),
        key=lambda x: x[1]["priority"],
        reverse=True
    )
    top_3 = [s[0] for s in sorted_scenes[:3]]
    analysis["recommendations"].append(
        f"Highest priority scenes (protect duration): {', '.join(top_3)}"
    )

    return analysis


def apply_narrative_balancing(project_path: Path, analysis: Dict) -> Dict:
    """Apply narrative-aware duration adjustments."""
    shot_plan_path = project_path / "shot_plan.json"

    with open(shot_plan_path) as f:
        shot_plan = json.load(f)

    shots = shot_plan.get("shots", [])
    target_runtime = analysis["target_runtime"]
    current_duration = analysis["current_duration"]

    # Build lookup for shot roles
    shot_roles = {}
    for scene_id, scene_data in analysis["scenes"].items():
        for shot_info in scene_data["shots"]:
            shot_roles[shot_info["shot_id"]] = shot_info

    # Calculate adjustment needed
    deficit = target_runtime - current_duration

    changes = []

    if deficit < -100:  # Over budget - need to compress
        surplus = -deficit
        compressible_shots = [
            (s.get("shot_id"), s.get("duration", 10))
            for s in shots
            if s.get("shot_id") in analysis["compressible_shots"]
        ]

        # Compress proportionally, respecting minimums
        total_compressible = sum(d for _, d in compressible_shots)
        reduction_ratio = surplus / total_compressible if total_compressible else 0

        for shot in shots:
            sid = shot.get("shot_id")
            if sid in analysis["compressible_shots"]:
                old_dur = shot.get("duration", 10)
                role = shot_roles.get(sid, {}).get("role", "coverage")
                min_dur = SHOT_TYPE_DURATIONS.get(role, {"min": 6})["min"]

                reduction = int(old_dur * reduction_ratio * 0.7)  # 70% of calculated
                new_dur = max(min_dur, old_dur - reduction)

                if new_dur != old_dur:
                    shot["duration"] = new_dur
                    changes.append({
                        "shot_id": sid,
                        "old": old_dur,
                        "new": new_dur,
                        "role": role,
                        "reason": "compressible"
                    })

    elif deficit > 100:  # Under budget - extend protected shots
        shortage = deficit
        protected_shots = [
            s for s in shots
            if s.get("shot_id") in analysis["protected_shots"]
        ]

        # Extend emotional anchors and dialogue shots
        extension_per_shot = shortage / len(protected_shots) if protected_shots else 0

        for shot in shots:
            sid = shot.get("shot_id")
            if sid in analysis["protected_shots"]:
                old_dur = shot.get("duration", 10)
                role = shot_roles.get(sid, {}).get("role", "dialogue")
                max_dur = SHOT_TYPE_DURATIONS.get(role, {"max": 20})["max"]
                weight = shot_roles.get(sid, {}).get("weight", 1.0)

                extension = int(extension_per_shot * weight * 0.5)
                new_dur = min(max_dur, old_dur + extension)

                if new_dur != old_dur:
                    shot["duration"] = new_dur
                    changes.append({
                        "shot_id": sid,
                        "old": old_dur,
                        "new": new_dur,
                        "role": role,
                        "reason": "protected_extension"
                    })

    # Add narrative metadata to shots
    for shot in shots:
        sid = shot.get("shot_id")
        if sid in shot_roles:
            shot["_narrative"] = {
                "role": shot_roles[sid]["role"],
                "weight": shot_roles[sid]["weight"],
                "protected": not shot_roles[sid]["compressible"]
            }

    # Save updated shot plan
    import shutil
    from datetime import datetime

    backup_path = shot_plan_path.with_suffix(f".backup_narrative_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    shutil.copy(shot_plan_path, backup_path)

    with open(shot_plan_path, 'w') as f:
        json.dump(shot_plan, f, indent=2)

    new_duration = sum(s.get("duration", 10) for s in shots)

    return {
        "success": True,
        "backup": str(backup_path),
        "changes": changes,
        "old_duration": current_duration,
        "new_duration": new_duration,
        "target": target_runtime,
        "variance_pct": abs(new_duration - target_runtime) / target_runtime * 100
    }


def print_analysis(analysis: Dict):
    """Print analysis in readable format."""
    print("\n" + "=" * 70)
    print("  NARRATIVE RUNTIME GOVERNOR - ANALYSIS")
    print("=" * 70)

    print(f"\nProject: {analysis['project']}")
    print(f"Target Runtime: {analysis['target_runtime']//60}m ({analysis['target_runtime']}s)")
    print(f"Current Runtime: {analysis['current_duration']//60}m ({analysis['current_duration']}s)")
    variance = (analysis['current_duration'] - analysis['target_runtime']) / analysis['target_runtime'] * 100
    print(f"Variance: {variance:+.1f}%")

    print(f"\nTotal Shots: {analysis['total_shots']}")
    print(f"  Protected (non-compressible): {len(analysis['protected_shots'])}")
    print(f"  Compressible: {len(analysis['compressible_shots'])}")

    print(f"\nProtected Duration: {analysis['protected_duration']}s ({analysis['protected_duration']/analysis['current_duration']*100:.0f}%)")
    print(f"Compressible Duration: {analysis['compressible_duration']}s ({analysis['compressible_duration']/analysis['current_duration']*100:.0f}%)")

    print("\n" + "-" * 70)
    print("SCENE PRIORITIES (Highest = Protect Duration)")
    print("-" * 70)

    sorted_scenes = sorted(
        analysis["scenes"].items(),
        key=lambda x: x[1]["priority"],
        reverse=True
    )

    print(f"{'Scene':<12} {'Priority':>8} {'Duration':>10} {'Protected':>10} {'Dialogue':>10}")
    print("-" * 70)

    for scene_id, data in sorted_scenes:
        dur_str = f"{data['duration']//60}:{data['duration']%60:02d}"
        print(f"{scene_id:<12} {data['priority']:>8.2f} {dur_str:>10} {data['protected_count']:>10} {data['dialogue_count']:>10}")

    print("\n" + "-" * 70)
    print("RECOMMENDATIONS")
    print("-" * 70)
    for rec in analysis["recommendations"]:
        print(f"  • {rec}")

    print()


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 narrative_runtime_governor.py <project> [--analyze|--apply]")
        sys.exit(1)

    project_name = sys.argv[1]
    mode = sys.argv[2] if len(sys.argv) > 2 else "--analyze"

    project_path = Path(f"/Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM/pipeline_outputs/{project_name}")

    if not project_path.exists():
        print(f"Error: Project '{project_name}' not found")
        sys.exit(1)

    analysis = analyze_project(project_path)
    print_analysis(analysis)

    if mode == "--apply":
        print("\n" + "=" * 70)
        print("  APPLYING NARRATIVE BALANCING")
        print("=" * 70)

        result = apply_narrative_balancing(project_path, analysis)

        print(f"\nBackup created: {result['backup']}")
        print(f"Changes applied: {len(result['changes'])}")
        print(f"Duration: {result['old_duration']}s → {result['new_duration']}s")
        print(f"New variance: {result['variance_pct']:.1f}%")

        if result['changes']:
            print("\nSample changes:")
            for change in result['changes'][:10]:
                print(f"  {change['shot_id']}: {change['old']}s → {change['new']}s ({change['role']}, {change['reason']})")
            if len(result['changes']) > 10:
                print(f"  ... and {len(result['changes']) - 10} more")


if __name__ == "__main__":
    main()
