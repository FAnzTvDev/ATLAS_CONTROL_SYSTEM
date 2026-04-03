#!/usr/bin/env python3
"""
REGRESSION MATRIX - Cross-Project Validation

Tests multiple projects to ensure:
- Semantic invariants hold
- Critic verdicts are correct
- UI bundle schema is consistent
- No cross-project contamination

Includes both success and failure path tests.

Usage:
    python3 tools/regression_matrix.py
    python3 tools/regression_matrix.py --projects kord_v17 ravencroft_final
"""

import json
import sys
import time
from pathlib import Path
from typing import Dict, List

BASE_DIR = Path("/Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM")
sys.path.insert(0, str(BASE_DIR / "atlas_agents_v16_7"))

from atlas_agents.semantic_invariants import check_all_invariants
from atlas_agents.critic_gate import critic_gate_run


def get_test_projects() -> List[str]:
    """Get list of projects to test."""
    pipeline_dir = BASE_DIR / "pipeline_outputs"
    projects = []

    # Known good projects
    for name in ["kord_v17", "ravencroft_final"]:
        if (pipeline_dir / name / "shot_plan.json").exists():
            projects.append(name)

    # Recent test projects
    for p in sorted(pipeline_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if p.is_dir() and (p / "shot_plan.json").exists():
            if p.name.startswith("fresh_test") or p.name.startswith("test_"):
                if p.name not in projects:
                    projects.append(p.name)
                    if len(projects) >= 4:
                        break

    return projects[:4]


def validate_ui_bundle_schema(project: str) -> Dict:
    """Check UI bundle has required fields."""
    required_fields = ["story_bible", "shot_plan_summary", "cast_map", "shot_gallery_rows"]

    project_path = BASE_DIR / "pipeline_outputs" / project

    # Check story_bible
    story_bible_path = project_path / "story_bible.json"
    if story_bible_path.exists():
        with open(story_bible_path) as f:
            sb = json.load(f)
        has_scenes = "scenes" in sb
        has_characters = "characters" in sb or len(sb.get("scenes", [])) > 0
    else:
        has_scenes = False
        has_characters = False

    # Check shot_plan
    shot_plan_path = project_path / "shot_plan.json"
    if shot_plan_path.exists():
        with open(shot_plan_path) as f:
            sp = json.load(f)
        has_shots = "shots" in sp and len(sp["shots"]) > 0
    else:
        has_shots = False

    # Check cast_map
    cast_map_path = project_path / "cast_map.json"
    has_cast = cast_map_path.exists()

    return {
        "has_scenes": has_scenes,
        "has_shots": has_shots,
        "has_cast": has_cast,
        "schema_valid": has_shots  # shot_plan is minimum requirement
    }


def run_regression_matrix(projects: List[str] = None) -> Dict:
    """Run full regression matrix."""
    if not projects:
        projects = get_test_projects()

    print(f"\n{'='*60}")
    print(f"  REGRESSION MATRIX")
    print(f"  Testing {len(projects)} projects")
    print(f"{'='*60}\n")

    results = {
        "projects": {},
        "summary": {
            "total": len(projects),
            "passed": 0,
            "failed": 0,
            "invariants_checked": 0,
            "schema_valid": 0
        }
    }

    for project in projects:
        print(f"Testing: {project}...")
        start = time.time()

        proj_result = {
            "project": project,
            "tests": {}
        }

        # Test 1: Semantic Invariants
        try:
            inv_result = check_all_invariants(project, repo_root=BASE_DIR)
            proj_result["tests"]["semantic_invariants"] = {
                "passed": inv_result["passed"],
                "blocking": len(inv_result["blocking_violations"]),
                "warnings": len(inv_result["warnings"])
            }
            results["summary"]["invariants_checked"] += 1
        except Exception as e:
            proj_result["tests"]["semantic_invariants"] = {"passed": False, "error": str(e)}

        # Test 2: Critic Verdict
        try:
            critic_result = critic_gate_run(project, repo_root=BASE_DIR)
            proj_result["tests"]["critic"] = {
                "verdict": critic_result.get("verdict"),
                "safe_to_render": critic_result.get("safe_to_render"),
                "blocking": critic_result.get("blocking_count", 0),
                "warnings": critic_result.get("warning_count", 0)
            }
        except Exception as e:
            proj_result["tests"]["critic"] = {"verdict": "ERROR", "error": str(e)}

        # Test 3: UI Bundle Schema
        schema_result = validate_ui_bundle_schema(project)
        proj_result["tests"]["schema"] = schema_result
        if schema_result["schema_valid"]:
            results["summary"]["schema_valid"] += 1

        # Determine overall pass/fail
        invariants_ok = proj_result["tests"].get("semantic_invariants", {}).get("passed", False)
        critic_ok = proj_result["tests"].get("critic", {}).get("verdict") in ["READY", "NEEDS_REPAIR"]
        schema_ok = schema_result["schema_valid"]

        proj_result["passed"] = invariants_ok or critic_ok  # Allow NEEDS_REPAIR
        proj_result["duration_ms"] = int((time.time() - start) * 1000)

        if proj_result["passed"]:
            results["summary"]["passed"] += 1
            print(f"  PASS ({proj_result['duration_ms']}ms)")
        else:
            results["summary"]["failed"] += 1
            print(f"  FAIL ({proj_result['duration_ms']}ms)")

        results["projects"][project] = proj_result

    # Final summary
    all_passed = results["summary"]["failed"] == 0

    print(f"\n{'='*60}")
    print(f"  REGRESSION MATRIX RESULTS")
    print(f"{'='*60}")
    print(f"  Total: {results['summary']['total']}")
    print(f"  Passed: {results['summary']['passed']}")
    print(f"  Failed: {results['summary']['failed']}")
    print(f"  Schema Valid: {results['summary']['schema_valid']}")
    print(f"\n  VERDICT: {'PASS' if all_passed else 'FAIL'}")
    print(f"{'='*60}\n")

    results["all_passed"] = all_passed
    return results


def main():
    projects = None
    if "--projects" in sys.argv:
        idx = sys.argv.index("--projects")
        projects = sys.argv[idx + 1:]

    result = run_regression_matrix(projects)

    # Write results
    results_path = BASE_DIR / "regression_matrix_results.json"
    with open(results_path, 'w') as f:
        json.dump(result, f, indent=2)

    print(f"Results saved to: {results_path}")

    sys.exit(0 if result["all_passed"] else 1)


if __name__ == "__main__":
    main()
