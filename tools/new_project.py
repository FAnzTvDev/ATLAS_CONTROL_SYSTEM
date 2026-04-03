#!/usr/bin/env python3
"""
ATLAS Project Factory - Create New Projects

This script creates a new project that respects the execution contract.
The project will work identically to Kord/Ravencroft - only content differs.

Usage:
    python3 tools/new_project.py my_new_project
    python3 tools/new_project.py my_new_project --from-script /path/to/script.txt
    python3 tools/new_project.py my_new_project --from-template kord_v17

The only requirement: a valid shot_plan.json
Everything else (story_bible, cast_map) is optional enrichment.
"""

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
PIPELINE_OUTPUTS = REPO_ROOT / "pipeline_outputs"


def create_minimal_shot_plan(project_name: str, num_shots: int = 5) -> dict:
    """Create a minimal valid shot_plan.json"""
    shots = []
    for i in range(num_shots):
        shot_id = f"001_{i+1:03d}A"
        shots.append({
            "shot_id": shot_id,
            "scene_id": "001",
            "type": "medium",
            "duration": 10,
            "characters": [],
            "location": "MAIN LOCATION",
            "nano_prompt": f"[Scene 1, Shot {i+1}] A cinematic shot establishing the scene.",
            "ltx_motion_prompt": "Subtle camera movement, atmospheric lighting.",
            "segments": [],
            "extended_shot": False
        })

    return {
        "project": project_name,
        "version": "v17",
        "created_at": datetime.utcnow().isoformat() + "Z",
        "metadata": {
            "total_shots": num_shots,
            "target_runtime_seconds": num_shots * 10,
            "model_lock": {
                "first_frame": "fal-ai/nano-banana-pro",
                "video": "fal-ai/ltx-2/image-to-video/fast"
            }
        },
        "shots": shots
    }


def create_minimal_story_bible(project_name: str) -> dict:
    """Create a minimal story_bible.json (optional enrichment)"""
    return {
        "project": project_name,
        "title": project_name.replace("_", " ").title(),
        "genre": "drama",
        "logline": "A story waiting to be told.",
        "characters": [],
        "locations": [],
        "scenes": [],
        "setting": {
            "time_period": "contemporary",
            "locations": []
        }
    }


def copy_from_template(source_project: str, target_project: str) -> bool:
    """Copy structure from existing project"""
    source_dir = PIPELINE_OUTPUTS / source_project
    target_dir = PIPELINE_OUTPUTS / target_project

    if not source_dir.exists():
        print(f"Template project not found: {source_project}")
        return False

    # Copy structure only, not generated assets
    target_dir.mkdir(parents=True, exist_ok=True)

    # Copy JSON files but update project name
    for json_file in ["shot_plan.json", "story_bible.json"]:
        src = source_dir / json_file
        if src.exists():
            with open(src) as f:
                data = json.load(f)
            data["project"] = target_project
            with open(target_dir / json_file, "w") as f:
                json.dump(data, f, indent=2)
            print(f"  Copied and updated: {json_file}")

    # Create empty directories
    for subdir in ["first_frames", "videos", "renders", "location_masters", "ui_cache"]:
        (target_dir / subdir).mkdir(exist_ok=True)

    return True


def create_new_project(
    project_name: str,
    from_script: str = None,
    from_template: str = None,
    num_shots: int = 5
) -> dict:
    """Create a new project following the execution contract"""

    project_dir = PIPELINE_OUTPUTS / project_name

    if project_dir.exists():
        print(f"Project already exists: {project_name}")
        print(f"  Path: {project_dir}")
        return {"success": False, "error": "Project exists"}

    print(f"\n=== Creating Project: {project_name} ===\n")

    # Create directory structure
    project_dir.mkdir(parents=True)
    for subdir in ["first_frames", "videos", "renders", "location_masters", "ui_cache"]:
        (project_dir / subdir).mkdir()
    print(f"  Created directory structure")

    if from_template:
        # Copy from existing project
        print(f"  Copying from template: {from_template}")
        copy_from_template(from_template, project_name)

    elif from_script:
        # TODO: Parse script and generate shot_plan
        # For now, create minimal with note
        shot_plan = create_minimal_shot_plan(project_name, num_shots)
        shot_plan["metadata"]["source_script"] = from_script
        shot_plan["metadata"]["note"] = "Run /api/v6/script/full-import to parse script"

        with open(project_dir / "shot_plan.json", "w") as f:
            json.dump(shot_plan, f, indent=2)
        print(f"  Created shot_plan.json (run full-import to parse script)")

    else:
        # Create minimal valid project
        shot_plan = create_minimal_shot_plan(project_name, num_shots)
        story_bible = create_minimal_story_bible(project_name)

        with open(project_dir / "shot_plan.json", "w") as f:
            json.dump(shot_plan, f, indent=2)
        print(f"  Created shot_plan.json ({num_shots} shots)")

        with open(project_dir / "story_bible.json", "w") as f:
            json.dump(story_bible, f, indent=2)
        print(f"  Created story_bible.json (optional)")

    # Verify the contract is met
    shot_plan_path = project_dir / "shot_plan.json"
    if shot_plan_path.exists():
        with open(shot_plan_path) as f:
            sp = json.load(f)
        print(f"\n  CONTRACT VERIFIED:")
        print(f"    shot_plan.json exists: YES")
        print(f"    shots count: {len(sp.get('shots', []))}")
        print(f"    version: {sp.get('version', 'unset')}")

    print(f"\n=== Project Ready ===")
    print(f"  Path: {project_dir}")
    print(f"\n  Next steps:")
    print(f"    1. Edit shot_plan.json with your content")
    print(f"    2. Run: OpsCoordinator.run_pipeline(['{project_name}'], mode='REPAIR')")
    print(f"    3. Generate frames: POST /api/auto/generate-first-frames")
    print(f"    4. Generate videos: POST /api/auto/render-videos")
    print(f"    5. Stitch: POST /api/v16/stitch/run")

    return {
        "success": True,
        "project": project_name,
        "path": str(project_dir),
        "shot_plan": str(project_dir / "shot_plan.json")
    }


def main():
    parser = argparse.ArgumentParser(
        description="Create a new ATLAS project following the execution contract"
    )
    parser.add_argument("project_name", help="Name of the new project (e.g., my_movie_v1)")
    parser.add_argument("--from-script", help="Path to script file to import")
    parser.add_argument("--from-template", help="Existing project to copy structure from")
    parser.add_argument("--shots", type=int, default=5, help="Number of placeholder shots")

    args = parser.parse_args()

    result = create_new_project(
        project_name=args.project_name,
        from_script=args.from_script,
        from_template=args.from_template,
        num_shots=args.shots
    )

    sys.exit(0 if result.get("success") else 1)


if __name__ == "__main__":
    main()
