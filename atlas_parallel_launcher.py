#!/usr/bin/env python3
"""
atlas_parallel_launcher.py — Parallel scene generation launcher for ATLAS.

Wraps atlas_universal_runner.py with concurrency control, jitter, and logging.
All scenes are cross-scene independent — safe to run any subset concurrently.

Usage:
    python3 atlas_parallel_launcher.py <project> <scene_id> [scene_id ...] [options]

Options:
    --max-concurrent N      Max simultaneous runner processes (default: 4)
    --mode lite|full        Runner mode (default: lite)
    --gen-mode chain|parallel  Video generation strategy (default: chain)
    --frames-only           Stop after first frames
    --videos-only           Skip frame gen, use existing frames
    --dry-run               Print commands only, don't execute
    --jitter N              Seconds between each launch (default: 2)

Examples:
    # Run all 6 scenes, 4 at a time
    python3 atlas_parallel_launcher.py victorian_shadows_ep1 001 002 003 004 005 006

    # Frames-only pass, 6 concurrent (fast, Nano API is generous)
    python3 atlas_parallel_launcher.py victorian_shadows_ep1 001 002 003 004 005 006 --frames-only --max-concurrent 6

    # Parallel video mode (breaks end-frame chain, but fully concurrent)
    python3 atlas_parallel_launcher.py victorian_shadows_ep1 003 004 005 --gen-mode parallel

    # Dry run to see what would execute
    python3 atlas_parallel_launcher.py victorian_shadows_ep1 001 002 003 --dry-run
"""

import os
import sys
import time
import json
import subprocess
import threading
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── Config ──────────────────────────────────────────────────────────────────
RUNNER = Path(__file__).parent / "atlas_universal_runner.py"
LOG_FILE = Path(__file__).parent / "parallel_gen_log.jsonl"


def _build_cmd(project: str, scene_id: str, mode: str, gen_mode: str,
               frames_only: bool, videos_only: bool, dry_run: bool) -> list[str]:
    cmd = [sys.executable, str(RUNNER), project, scene_id, "--mode", mode, "--gen-mode", gen_mode]
    if frames_only:
        cmd.append("--frames-only")
    if videos_only:
        cmd.append("--videos-only")
    if dry_run:
        cmd.append("--dry-run")
    return cmd


def _log(entry: dict):
    """Append a JSONL entry to the log file."""
    entry["ts"] = datetime.utcnow().isoformat()
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")


def _run_scene(project: str, scene_id: str, mode: str, gen_mode: str,
               frames_only: bool, videos_only: bool, dry_run: bool,
               print_lock: threading.Lock) -> dict:
    """Run a single scene in a subprocess. Returns result dict."""
    cmd = _build_cmd(project, scene_id, mode, gen_mode, frames_only, videos_only, dry_run)
    t0 = time.time()

    with print_lock:
        print(f"  [LAUNCH] Scene {scene_id} → {' '.join(cmd[2:])}")

    _log({"event": "scene_start", "project": project, "scene_id": scene_id, "cmd": cmd})

    if dry_run:
        time.sleep(0.1)
        with print_lock:
            print(f"  [DRY-RUN] Scene {scene_id}: would run: {' '.join(cmd)}")
        return {"scene_id": scene_id, "status": "dry_run", "elapsed": 0}

    try:
        result = subprocess.run(
            cmd,
            capture_output=False,  # let output stream to terminal
            text=True,
        )
        elapsed = round(time.time() - t0, 1)
        status = "ok" if result.returncode == 0 else f"exit_{result.returncode}"
        with print_lock:
            icon = "✓" if result.returncode == 0 else "✗"
            print(f"  [{icon}] Scene {scene_id} done in {elapsed}s (exit {result.returncode})")
        _log({"event": "scene_done", "project": project, "scene_id": scene_id,
              "status": status, "elapsed_s": elapsed, "returncode": result.returncode})
        return {"scene_id": scene_id, "status": status, "elapsed": elapsed}
    except Exception as e:
        elapsed = round(time.time() - t0, 1)
        with print_lock:
            print(f"  [✗] Scene {scene_id} ERROR after {elapsed}s: {e}")
        _log({"event": "scene_error", "project": project, "scene_id": scene_id,
              "error": str(e), "elapsed_s": elapsed})
        return {"scene_id": scene_id, "status": "error", "elapsed": elapsed, "error": str(e)}


def run_parallel(project: str, scene_ids: list[str], max_concurrent: int = 4,
                 mode: str = "lite", gen_mode: str = "chain",
                 frames_only: bool = False, videos_only: bool = False,
                 dry_run: bool = False, jitter: float = 2.0):
    """
    Launch scene_ids in parallel, capping at max_concurrent.
    Adds jitter seconds between each launch to avoid API thundering herd.
    """
    if not scene_ids:
        print("No scenes specified.")
        return

    print(f"\n{'='*65}")
    print(f"  ATLAS PARALLEL LAUNCHER")
    print(f"  Project    : {project}")
    print(f"  Scenes     : {scene_ids}")
    print(f"  Concurrent : {min(max_concurrent, len(scene_ids))} / {len(scene_ids)}")
    print(f"  Mode       : {mode} | gen-mode: {gen_mode}")
    flags = []
    if frames_only: flags.append("--frames-only")
    if videos_only: flags.append("--videos-only")
    if dry_run:     flags.append("--dry-run")
    if flags:
        print(f"  Flags      : {' '.join(flags)}")
    print(f"  Jitter     : {jitter}s between launches")
    print(f"{'='*65}\n")

    t_global = time.time()
    print_lock = threading.Lock()
    results = []

    # Submit in batches respecting max_concurrent, with jitter between each submit
    with ThreadPoolExecutor(max_workers=min(max_concurrent, len(scene_ids))) as pool:
        futures = {}
        for i, scene_id in enumerate(scene_ids):
            if i > 0 and jitter > 0:
                time.sleep(jitter)
            fut = pool.submit(
                _run_scene, project, scene_id, mode, gen_mode,
                frames_only, videos_only, dry_run, print_lock
            )
            futures[fut] = scene_id

        for f in as_completed(futures):
            results.append(f.result())

    total = round(time.time() - t_global, 1)
    ok = [r for r in results if r["status"] in ("ok", "dry_run")]
    fail = [r for r in results if r["status"] not in ("ok", "dry_run")]

    print(f"\n{'='*65}")
    print(f"  COMPLETE — {len(ok)}/{len(scene_ids)} scenes OK in {total}s")
    if fail:
        print(f"  FAILED ({len(fail)}): {[r['scene_id'] for r in fail]}")
    print(f"  Log: {LOG_FILE}")
    print(f"{'='*65}\n")

    _log({"event": "batch_done", "project": project, "total_scenes": len(scene_ids),
          "ok": len(ok), "failed": len(fail), "total_s": total})
    return results


def main():
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)

    project = args[0]
    scene_ids = []
    max_concurrent = 4
    mode = "lite"
    gen_mode = "chain"
    frames_only = False
    videos_only = False
    dry_run = False
    jitter = 2.0

    i = 1
    while i < len(args):
        a = args[i]
        if a == "--max-concurrent":
            i += 1; max_concurrent = int(args[i])
        elif a == "--mode":
            i += 1; mode = args[i]
        elif a == "--gen-mode":
            i += 1; gen_mode = args[i]
        elif a == "--jitter":
            i += 1; jitter = float(args[i])
        elif a == "--frames-only":
            frames_only = True
        elif a == "--videos-only":
            videos_only = True
        elif a == "--dry-run":
            dry_run = True
        elif not a.startswith("--"):
            scene_ids.append(a)
        i += 1

    if not scene_ids:
        print("Error: no scene IDs specified.")
        print(__doc__)
        sys.exit(1)

    if not RUNNER.exists():
        print(f"Error: runner not found at {RUNNER}")
        sys.exit(1)

    run_parallel(
        project=project,
        scene_ids=scene_ids,
        max_concurrent=max_concurrent,
        mode=mode,
        gen_mode=gen_mode,
        frames_only=frames_only,
        videos_only=videos_only,
        dry_run=dry_run,
        jitter=jitter,
    )


if __name__ == "__main__":
    main()
