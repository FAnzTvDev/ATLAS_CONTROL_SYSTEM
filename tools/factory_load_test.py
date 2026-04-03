#!/usr/bin/env python3
"""
FACTORY LOAD TEST

Concurrent pipeline stress test:
- Ingests 10 scripts
- Runs 3 in parallel
- Validates no cross-project contamination
- Measures throughput and failure rates

Usage:
    python3 tools/factory_load_test.py
    python3 tools/factory_load_test.py --scripts 5 --parallel 2
"""

import json
import sys
import time
import hashlib
import threading
import queue
from pathlib import Path
from typing import Dict, List
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_DIR = Path("/Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM")
sys.path.insert(0, str(BASE_DIR / "atlas_agents_v16_7"))

from atlas_agents.ops_coordinator import OpsCoordinator
from tools.canonical_hash import hash_project_state


# Test script templates
TEST_SCRIPTS = [
    ("thriller_subway", """
INT. TOKYO SUBWAY - NIGHT
The last train rattles through tunnels. MAYA (28) clutches her bag.
MAYA
Something is following us.
A shadow moves between cars.
"""),
    ("scifi_lab", """
INT. RESEARCH LAB - DAY
Holographic displays flicker. DR. CHEN (45) studies anomalies.
DR. CHEN
The readings are off the charts.
Warning alarms blare.
"""),
    ("horror_house", """
INT. ABANDONED MANOR - NIGHT
Dust swirls in moonlight. SARAH (32) holds a flashlight.
SARAH
Hello? Is anyone there?
A door creaks open behind her.
"""),
    ("drama_court", """
INT. COURTROOM - DAY
Tension fills the room. ATTORNEY WELLS (50) approaches the witness.
WELLS
Tell us what really happened that night.
The WITNESS hesitates.
"""),
    ("action_rooftop", """
EXT. ROOFTOP - NIGHT
City lights sparkle below. AGENT BLAKE (35) faces the enemy.
BLAKE
This ends now.
They circle each other, ready to fight.
"""),
    ("comedy_office", """
INT. STARTUP OFFICE - DAY
Beanbag chairs and ping-pong tables. TOM (27) spills coffee.
TOM
The investor is here in five minutes!
LISA (26) frantically cleans.
"""),
    ("romance_cafe", """
INT. PARIS CAFE - EVENING
Rain streaks the windows. CLAIRE (29) waits alone.
CLAIRE
He said he'd come.
A figure appears at the door.
"""),
    ("mystery_library", """
INT. OLD LIBRARY - NIGHT
Leather-bound books line the walls. DETECTIVE MOSS (55) examines a note.
MOSS
This changes everything.
The librarian watches nervously.
"""),
    ("fantasy_castle", """
INT. THRONE ROOM - DAY
Banners hang from stone walls. QUEEN ELARA (40) addresses her council.
QUEEN ELARA
War is coming. We must prepare.
Soldiers stand at attention.
"""),
    ("western_saloon", """
INT. SALOON - HIGH NOON
Dust and whiskey. SHERIFF COLE (45) pushes through swinging doors.
SHERIFF COLE
I hear you've been looking for me.
The room goes silent.
""")
]


class LoadTestResult:
    """Container for load test results."""
    def __init__(self):
        self.lock = threading.Lock()
        self.results = []
        self.errors = []
        self.start_time = None
        self.end_time = None


def create_test_script(name: str, content: str) -> Path:
    """Create a test script file."""
    test_dir = BASE_DIR / "test_scripts"
    test_dir.mkdir(exist_ok=True)

    script_path = test_dir / f"loadtest_{name}_{int(time.time())}.txt"
    script_path.write_text(content.strip())
    return script_path


def run_single_pipeline(script_name: str, script_content: str, results: LoadTestResult) -> Dict:
    """Run a single pipeline and collect results."""
    project_name = f"loadtest_{script_name}_{int(time.time() * 1000) % 100000}"
    start_time = time.time()

    try:
        # Create script file
        script_path = create_test_script(script_name, script_content)

        # Create project directory
        project_dir = BASE_DIR / "pipeline_outputs" / project_name
        project_dir.mkdir(parents=True, exist_ok=True)

        # Create minimal shot_plan.json from script
        shot_plan = {
            "project": project_name,
            "shots": [],
            "metadata": {
                "source_script": str(script_path),
                "created_at": datetime.now().isoformat()
            }
        }

        # Parse script for shots (simple extraction)
        lines = script_content.strip().split('\n')
        shot_id = 1
        for i, line in enumerate(lines):
            if line.strip().startswith('INT.') or line.strip().startswith('EXT.'):
                shot_plan["shots"].append({
                    "shot_id": f"{shot_id:03d}_001A",
                    "scene_id": f"{shot_id:03d}",
                    "duration": 20,
                    "nano_prompt": line.strip(),
                    "ltx_motion_prompt": "Subtle camera movement"
                })
                shot_id += 1

        with open(project_dir / "shot_plan.json", 'w') as f:
            json.dump(shot_plan, f, indent=2)

        # Run governed pipeline
        coord = OpsCoordinator(BASE_DIR)
        pipeline_result = coord.run_pipeline([project_name], mode="VERIFY", initiated_by="load_test")

        duration_ms = int((time.time() - start_time) * 1000)

        # Hash final state
        state_hash = hash_project_state(project_name)

        result = {
            "project": project_name,
            "script": script_name,
            "success": True,
            "duration_ms": duration_ms,
            "verdict": pipeline_result.get("projects", {}).get(project_name, {}).get("critic_verdict", "UNKNOWN"),
            "state_hash": state_hash.get("combined_hash", "")[:16],
            "shots_created": len(shot_plan["shots"])
        }

        with results.lock:
            results.results.append(result)

        return result

    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        error = {
            "project": project_name if 'project_name' in dir() else script_name,
            "script": script_name,
            "success": False,
            "duration_ms": duration_ms,
            "error": str(e)
        }

        with results.lock:
            results.errors.append(error)

        return error


def run_load_test(num_scripts: int = 10, parallel: int = 3) -> Dict:
    """Run the full load test."""
    print(f"\n{'='*60}")
    print(f"  FACTORY LOAD TEST")
    print(f"  Scripts: {num_scripts}, Parallel: {parallel}")
    print(f"{'='*60}\n")

    results = LoadTestResult()
    results.start_time = time.time()

    # Select scripts to test
    scripts_to_test = (TEST_SCRIPTS * ((num_scripts // len(TEST_SCRIPTS)) + 1))[:num_scripts]

    print(f"Starting {num_scripts} pipelines...")

    with ThreadPoolExecutor(max_workers=parallel) as executor:
        futures = []
        for name, content in scripts_to_test:
            future = executor.submit(run_single_pipeline, name, content, results)
            futures.append(future)
            # Stagger starts slightly
            time.sleep(0.1)

        # Wait for completion with progress
        completed = 0
        for future in as_completed(futures):
            completed += 1
            result = future.result()
            status = "PASS" if result.get("success") else "FAIL"
            print(f"  [{completed}/{num_scripts}] {result.get('project', 'unknown')}: {status} ({result.get('duration_ms', 0)}ms)")

    results.end_time = time.time()

    # Check for cross-contamination
    contamination_issues = []
    project_hashes = {}
    for r in results.results:
        h = r.get("state_hash", "")
        p = r.get("project", "")
        if h and h in project_hashes:
            contamination_issues.append(f"Hash collision: {p} == {project_hashes[h]}")
        project_hashes[h] = p

    # Calculate stats
    total_duration = int((results.end_time - results.start_time) * 1000)
    success_count = len(results.results)
    failure_count = len(results.errors)
    avg_duration = sum(r.get("duration_ms", 0) for r in results.results) / max(1, success_count)

    summary = {
        "test_config": {
            "num_scripts": num_scripts,
            "parallel_workers": parallel
        },
        "timing": {
            "total_duration_ms": total_duration,
            "avg_pipeline_ms": int(avg_duration),
            "throughput_per_minute": round((success_count / total_duration) * 60000, 2) if total_duration > 0 else 0
        },
        "results": {
            "total": num_scripts,
            "success": success_count,
            "failed": failure_count,
            "success_rate": round(success_count / num_scripts * 100, 1) if num_scripts > 0 else 0
        },
        "isolation": {
            "contamination_issues": len(contamination_issues),
            "issues": contamination_issues
        },
        "all_results": results.results,
        "all_errors": results.errors,
        "pass": failure_count == 0 and len(contamination_issues) == 0
    }

    # Print summary
    print(f"\n{'='*60}")
    print(f"  LOAD TEST RESULTS")
    print(f"{'='*60}")
    print(f"  Total Time: {total_duration}ms ({total_duration/1000:.1f}s)")
    print(f"  Throughput: {summary['timing']['throughput_per_minute']} projects/minute")
    print(f"  Success: {success_count}/{num_scripts} ({summary['results']['success_rate']}%)")
    print(f"  Failed: {failure_count}")
    print(f"  Avg Duration: {int(avg_duration)}ms")
    print(f"  Contamination: {len(contamination_issues)} issues")
    print(f"\n  VERDICT: {'PASS' if summary['pass'] else 'FAIL'}")
    print(f"{'='*60}\n")

    return summary


def main():
    num_scripts = 10
    parallel = 3

    for i, arg in enumerate(sys.argv):
        if arg == "--scripts" and i + 1 < len(sys.argv):
            num_scripts = int(sys.argv[i + 1])
        elif arg == "--parallel" and i + 1 < len(sys.argv):
            parallel = int(sys.argv[i + 1])

    result = run_load_test(num_scripts, parallel)

    # Save results
    results_path = BASE_DIR / "load_test_results.json"
    with open(results_path, 'w') as f:
        json.dump(result, f, indent=2)

    print(f"Results saved to: {results_path}")

    sys.exit(0 if result["pass"] else 1)


if __name__ == "__main__":
    main()
