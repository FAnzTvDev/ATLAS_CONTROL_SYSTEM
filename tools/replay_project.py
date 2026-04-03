#!/usr/bin/env python3
"""
REPLAY PROJECT - Deterministic Pipeline Replay

Replays a project run and verifies identical output.
Uses execution_ledger.json to track and verify runs.

Usage:
    python3 tools/replay_project.py <project>
    python3 tools/replay_project.py <project> --run-id <id>
"""

import json
import sys
import time
import hashlib
from pathlib import Path
from datetime import datetime

BASE_DIR = Path("/Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM")
sys.path.insert(0, str(BASE_DIR / "atlas_agents_v16_7"))

from atlas_agents.ops_coordinator import OpsCoordinator
from tools.canonical_hash import hash_project_state


def get_ledger_path(project: str) -> Path:
    return BASE_DIR / "pipeline_outputs" / project / "execution_ledger.json"


def load_ledger(project: str) -> list:
    ledger_path = get_ledger_path(project)
    if ledger_path.exists():
        with open(ledger_path) as f:
            return json.load(f)
    return []


def append_ledger(project: str, entry: dict):
    ledger = load_ledger(project)
    ledger.append(entry)
    with open(get_ledger_path(project), 'w') as f:
        json.dump(ledger, f, indent=2)


def run_and_record(project: str, mode: str = "VERIFY") -> dict:
    """Run pipeline and record to ledger."""
    # Hash before
    before_hash = hash_project_state(project)

    # Run pipeline
    start_time = time.time()
    coord = OpsCoordinator(BASE_DIR)
    result = coord.run_pipeline([project], mode=mode, initiated_by="replay")
    duration_ms = int((time.time() - start_time) * 1000)

    # Hash after
    after_hash = hash_project_state(project)

    # Get verdict
    proj_result = result.get("projects", {}).get(project, {})
    verdict = proj_result.get("critic_verdict", "UNKNOWN")

    # Create ledger entry
    entry = {
        "run_id": result.get("run_id"),
        "timestamp": datetime.now().isoformat(),
        "mode": mode,
        "input_hash": before_hash.get("combined_hash"),
        "output_hash": after_hash.get("combined_hash"),
        "verdict": verdict,
        "duration_ms": duration_ms,
        "agents": list(proj_result.get("agents", {}).keys())
    }

    # Append to ledger
    append_ledger(project, entry)

    return entry


def verify_replay(project: str, run_id: str = None) -> dict:
    """Verify that replaying produces identical results."""
    ledger = load_ledger(project)

    if not ledger:
        return {"success": False, "error": "No previous runs in ledger"}

    # Get reference run
    if run_id:
        ref_run = next((e for e in ledger if e.get("run_id") == run_id), None)
        if not ref_run:
            return {"success": False, "error": f"Run {run_id} not found"}
    else:
        ref_run = ledger[-1]  # Last run

    print(f"Reference run: {ref_run.get('run_id')}")
    print(f"Reference output hash: {ref_run.get('output_hash', 'N/A')[:16]}...")
    print(f"Reference verdict: {ref_run.get('verdict')}")

    # Run again
    print("\nReplaying pipeline...")
    new_entry = run_and_record(project, mode=ref_run.get("mode", "VERIFY"))

    # Compare
    match = (
        new_entry.get("output_hash") == ref_run.get("output_hash") and
        new_entry.get("verdict") == ref_run.get("verdict")
    )

    return {
        "success": match,
        "reference_run_id": ref_run.get("run_id"),
        "replay_run_id": new_entry.get("run_id"),
        "reference_hash": ref_run.get("output_hash"),
        "replay_hash": new_entry.get("output_hash"),
        "hash_match": new_entry.get("output_hash") == ref_run.get("output_hash"),
        "reference_verdict": ref_run.get("verdict"),
        "replay_verdict": new_entry.get("verdict"),
        "verdict_match": new_entry.get("verdict") == ref_run.get("verdict")
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 tools/replay_project.py <project> [--run-id <id>]")
        print("\nThis tool:")
        print("  1. Runs the governed pipeline")
        print("  2. Records input/output hashes to execution_ledger.json")
        print("  3. Verifies replay produces identical results")
        sys.exit(1)

    project = sys.argv[1]

    run_id = None
    if "--run-id" in sys.argv:
        idx = sys.argv.index("--run-id")
        if idx + 1 < len(sys.argv):
            run_id = sys.argv[idx + 1]

    # Check if this is first run or replay
    ledger = load_ledger(project)

    if not ledger:
        print(f"First run for {project} - recording baseline...")
        entry = run_and_record(project)
        print(f"\nBaseline recorded:")
        print(f"  Run ID: {entry['run_id']}")
        print(f"  Output Hash: {entry['output_hash'][:16]}...")
        print(f"  Verdict: {entry['verdict']}")
        print(f"  Duration: {entry['duration_ms']}ms")
    else:
        print(f"Verifying replay for {project}...")
        result = verify_replay(project, run_id)

        print(f"\n{'='*50}")
        print(f"REPLAY VERIFICATION RESULT")
        print(f"{'='*50}")
        print(f"Hash Match: {'PASS' if result['hash_match'] else 'FAIL'}")
        print(f"Verdict Match: {'PASS' if result['verdict_match'] else 'FAIL'}")
        print(f"Overall: {'PASS - DETERMINISTIC' if result['success'] else 'FAIL - NON-DETERMINISTIC'}")
        print(f"{'='*50}")

        sys.exit(0 if result['success'] else 1)


if __name__ == "__main__":
    main()
