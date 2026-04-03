#!/usr/bin/env python3
"""
ATLAS V17 FACTORY BATCH RUNNER

Runs multiple projects through the factory pipeline.
Pauses cleanly when human judgment is needed.

Usage:
    python3 tools/run_factory_batch_v17.py kord_v17 ravencroft_v17 project3

    # With options:
    python3 tools/run_factory_batch_v17.py --skip-frames --dry-run project1 project2

Exit codes:
    0 = All projects completed or at approval gates
    1 = Critical failures detected
"""

import sys
import json
import argparse
import requests
from pathlib import Path
from datetime import datetime
from typing import List, Dict

BASE_URL = "http://localhost:9999"
BASE_DIR = Path("/Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM")

# ANSI colors
class Color:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'


def color(text: str, c: str) -> str:
    return f"{c}{text}{Color.RESET}"


def check_server() -> bool:
    """Check if server is running."""
    try:
        r = requests.get(f"{BASE_URL}/api/health", timeout=5)
        return r.status_code == 200
    except:
        return False


def run_project_pipeline(project: str, options: dict) -> Dict:
    """
    Run a single project through the pipeline.
    Returns status dict with current state.
    """
    result = {
        "project": project,
        "status": "unknown",
        "stage": "unknown",
        "pending_tasks": [],
        "errors": []
    }

    try:
        # Step 1: Check approval status
        r = requests.get(f"{BASE_URL}/api/v17/approval/{project}", timeout=30)
        approval = r.json()

        result["stage"] = approval.get("current_stage", "unknown")
        result["pending_tasks"] = approval.get("human_tasks", [])

        # If pending human review, stop here
        if approval.get("status") == "PENDING":
            result["status"] = "pending_approval"
            return result

        # If rejected, stop here
        if approval.get("status") == "REJECTED":
            result["status"] = "rejected"
            result["errors"] = approval.get("reasons", [])
            return result

        # Step 2: Run critic to check current state
        r = requests.post(
            f"{BASE_URL}/api/v15/run-critics",
            json={"project": project},
            timeout=60
        )
        critic = r.json()

        verdict = critic.get("verdict", "UNKNOWN")

        if verdict == "NEEDS_HUMAN_JUDGMENT":
            result["status"] = "needs_human"
            result["pending_tasks"] = critic.get("human_judgment_issues", [])
            return result

        if verdict == "NEEDS_REPAIR":
            # Auto-repair
            if not options.get("dry_run"):
                # Run cast propagation
                r = requests.post(
                    f"{BASE_URL}/api/v6/casting/auto-cast",
                    json={"project": project},
                    timeout=30
                )

                # Run fix-v16
                r = requests.post(
                    f"{BASE_URL}/api/shot-plan/fix-v16",
                    json={"project": project},
                    timeout=60
                )

            result["status"] = "repaired"
            return result

        # Step 3: If READY, proceed through stages
        if verdict == "READY" or options.get("force"):

            # Check what stage we're at and proceed
            stage = approval.get("current_stage", "INGEST")

            if stage in ["INGEST", "CAST"] and not options.get("skip_frames"):
                # Generate first frames
                if not options.get("dry_run"):
                    r = requests.post(
                        f"{BASE_URL}/api/auto/generate-first-frames",
                        json={"project": project, "dry_run": False},
                        timeout=300
                    )
                result["status"] = "generating_frames"

            elif stage == "FRAMES" and not options.get("skip_videos"):
                # Check for pending frame approvals
                r = requests.get(f"{BASE_URL}/api/v17/approval/{project}/pending?stage=FRAMES", timeout=10)
                pending = r.json()

                if pending.get("count", 0) > 0:
                    result["status"] = "pending_frame_approval"
                    result["pending_tasks"] = [f"Approve frames for {pending['count']} scene(s)"]
                else:
                    # Generate videos
                    if not options.get("dry_run"):
                        r = requests.post(
                            f"{BASE_URL}/api/auto/render-videos",
                            json={"project": project, "dry_run": False},
                            timeout=600
                        )
                    result["status"] = "generating_videos"

            elif stage == "VIDEOS":
                # Check for pending video approvals
                r = requests.get(f"{BASE_URL}/api/v17/approval/{project}/pending?stage=VIDEOS", timeout=10)
                pending = r.json()

                if pending.get("count", 0) > 0:
                    result["status"] = "pending_video_approval"
                    result["pending_tasks"] = [f"Approve videos for {pending['count']} scene(s)"]
                else:
                    # Stitch
                    if not options.get("dry_run"):
                        r = requests.post(
                            f"{BASE_URL}/api/v16/stitch/run",
                            json={"project": project},
                            timeout=300
                        )
                    result["status"] = "stitching"

            elif stage == "STITCH":
                result["status"] = "pending_stitch_approval"
                result["pending_tasks"] = ["Approve final stitched output"]

            elif stage == "COMPLETE":
                result["status"] = "complete"

    except Exception as e:
        result["status"] = "error"
        result["errors"].append(str(e))

    return result


def print_dashboard(results: List[Dict]) -> None:
    """Print summary dashboard."""
    print("\n" + "=" * 70)
    print("  ATLAS V17 FACTORY BATCH RUNNER - DASHBOARD")
    print("  " + datetime.now().isoformat())
    print("=" * 70)

    # Group by status
    complete = [r for r in results if r["status"] == "complete"]
    pending = [r for r in results if "pending" in r["status"]]
    working = [r for r in results if r["status"] in ["generating_frames", "generating_videos", "stitching", "repaired"]]
    errors = [r for r in results if r["status"] == "error" or r["errors"]]
    needs_human = [r for r in results if r["status"] == "needs_human"]

    # Print summary table
    print(f"\n  {'PROJECT':<30} {'STATUS':<25} {'STAGE':<15}")
    print("  " + "-" * 70)

    for r in results:
        status = r["status"]
        if status == "complete":
            status_str = color("✓ COMPLETE", Color.GREEN)
        elif "pending" in status:
            status_str = color("⏸ PENDING", Color.YELLOW)
        elif status == "needs_human":
            status_str = color("👤 HUMAN NEEDED", Color.YELLOW)
        elif status == "error":
            status_str = color("✗ ERROR", Color.RED)
        else:
            status_str = color(f"⚙ {status.upper()}", Color.BLUE)

        print(f"  {r['project']:<30} {status_str:<35} {r['stage']:<15}")

        # Print pending tasks
        for task in r.get("pending_tasks", [])[:2]:
            print(f"    └─ {task}")

        # Print errors
        for err in r.get("errors", [])[:2]:
            print(f"    └─ {color(err, Color.RED)}")

    # Summary
    print("\n" + "-" * 70)
    print(f"  COMPLETE: {len(complete)}  |  PENDING: {len(pending)}  |  "
          f"WORKING: {len(working)}  |  ERRORS: {len(errors)}  |  HUMAN: {len(needs_human)}")
    print("=" * 70)

    # Human tasks summary
    if pending or needs_human:
        print("\n  HUMAN TASKS REQUIRED:")
        for r in pending + needs_human:
            for task in r.get("pending_tasks", []):
                print(f"    [{r['project']}] {task}")


def main():
    parser = argparse.ArgumentParser(description="ATLAS V17 Factory Batch Runner")
    parser.add_argument("projects", nargs="*", help="Project names to process")
    parser.add_argument("--dry-run", action="store_true", help="Check status without generating")
    parser.add_argument("--skip-frames", action="store_true", help="Skip frame generation")
    parser.add_argument("--skip-videos", action="store_true", help="Skip video generation")
    parser.add_argument("--force", action="store_true", help="Force proceed even if not READY")
    parser.add_argument("--all", action="store_true", help="Run all projects in pipeline_outputs")

    args = parser.parse_args()

    # Get project list
    if args.all:
        pipeline_dir = BASE_DIR / "pipeline_outputs"
        projects = [
            p.name for p in pipeline_dir.iterdir()
            if p.is_dir() and (p / "shot_plan.json").exists()
        ]
    elif args.projects:
        projects = args.projects
    else:
        print("Usage: python3 tools/run_factory_batch_v17.py [--all] project1 project2 ...")
        print("\nAvailable projects:")
        pipeline_dir = BASE_DIR / "pipeline_outputs"
        for p in sorted(pipeline_dir.iterdir()):
            if p.is_dir() and (p / "shot_plan.json").exists():
                print(f"  - {p.name}")
        sys.exit(1)

    # Check server
    if not check_server():
        print(color("ERROR: Server not running at localhost:9999", Color.RED))
        sys.exit(1)

    print(f"\nProcessing {len(projects)} project(s)...")
    if args.dry_run:
        print(color("(DRY RUN - no generation)", Color.YELLOW))

    options = {
        "dry_run": args.dry_run,
        "skip_frames": args.skip_frames,
        "skip_videos": args.skip_videos,
        "force": args.force
    }

    # Run each project
    results = []
    for i, project in enumerate(projects):
        print(f"\n[{i+1}/{len(projects)}] Processing {project}...")
        result = run_project_pipeline(project, options)
        results.append(result)

    # Print dashboard
    print_dashboard(results)

    # Exit code
    errors = [r for r in results if r["status"] == "error"]
    if errors:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
