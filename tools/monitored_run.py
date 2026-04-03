#!/usr/bin/env python3
"""
MONITORED SCENE RUN — Halt on first failure.

This script:
1. Verifies orchestrator is reachable
2. Verifies all pre-conditions
3. Runs V26 Controller prepare + lock
4. Generates ONE SHOT AT A TIME
5. After EACH shot: checks if frame exists, checks lock integrity
6. On ANY failure: STOPS IMMEDIATELY and reports what went wrong
7. After all shots: runs post-run audit

Usage:
    python3 tools/monitored_run.py ravencroft_v22 001
    python3 tools/monitored_run.py ravencroft_v22 001 --dry-run
"""

import sys
import os
import json
import time
import hashlib
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PROJECT = sys.argv[1] if len(sys.argv) > 1 else "ravencroft_v22"
SCENE_ID = sys.argv[2] if len(sys.argv) > 2 else "001"
DRY_RUN = "--dry-run" in sys.argv

PP = Path(f"pipeline_outputs/{PROJECT}")
ORCH_URL = "http://localhost:9999"

# ═══════════════════════════════════════════════════════════════
# OUTPUT
# ═══════════════════════════════════════════════════════════════

class Colors:
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    BOLD = "\033[1m"
    END = "\033[0m"

def banner(msg):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'═'*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}  {msg}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'═'*60}{Colors.END}\n")

def ok(msg):
    print(f"  {Colors.GREEN}✅ {msg}{Colors.END}")

def fail(msg):
    print(f"  {Colors.RED}❌ {msg}{Colors.END}")

def warn(msg):
    print(f"  {Colors.YELLOW}⚠️  {msg}{Colors.END}")

def halt(msg):
    print(f"\n{Colors.RED}{Colors.BOLD}{'═'*60}{Colors.END}")
    print(f"{Colors.RED}{Colors.BOLD}  HALTED: {msg}{Colors.END}")
    print(f"{Colors.RED}{Colors.BOLD}{'═'*60}{Colors.END}")
    sys.exit(1)

# ═══════════════════════════════════════════════════════════════
# STEP 0: PRE-FLIGHT CHECKS
# ═══════════════════════════════════════════════════════════════

banner(f"MONITORED RUN — {PROJECT} / Scene {SCENE_ID}" + (" [DRY RUN]" if DRY_RUN else " [LIVE]"))

print("STEP 0: Pre-flight checks")

# Check orchestrator is reachable (skip in dry-run — not needed for data validation)
import httpx
if not DRY_RUN:
    try:
        resp = httpx.get(f"{ORCH_URL}/api/auto/projects", timeout=5.0)
        if resp.status_code == 200:
            ok(f"Orchestrator reachable at {ORCH_URL}")
        else:
            halt(f"Orchestrator returned HTTP {resp.status_code}")
    except httpx.ConnectError:
        halt(f"Orchestrator NOT RUNNING at {ORCH_URL}\n"
             f"         Start it first: python3 orchestrator_server.py")
    except Exception as e:
        halt(f"Cannot reach orchestrator: {e}")
else:
    warn(f"DRY RUN — skipping orchestrator check (would need {ORCH_URL})")

# Check project files
for fname in ["shot_plan.json", "cast_map.json", "story_bible.json", "scene_manifest.json"]:
    fpath = PP / fname
    if fpath.exists():
        ok(f"{fname} exists ({fpath.stat().st_size:,} bytes)")
    else:
        halt(f"{fname} MISSING at {fpath}")

# Check prep report
report_path = PP / "atlas_run_report.json"
if report_path.exists():
    ok("atlas_run_report.json exists (prep gate will pass)")
else:
    halt("atlas_run_report.json MISSING — run POST /api/v22/prep/{project} first")

# Load shot plan and check scene exists (bare-list guard: shot_plan.json may be a bare list)
with open(PP / "shot_plan.json") as f:
    sp_data = json.load(f)
if isinstance(sp_data, list):
    sp_data = {"shots": sp_data}  # T2-OR-18: bare-list format guard
shots = sp_data.get("shots", [])
scene_shots = [s for s in shots if (s.get("scene_id") or s.get("shot_id", "")[:3]) == SCENE_ID]

if not scene_shots:
    halt(f"No shots found for scene {SCENE_ID}")
ok(f"Scene {SCENE_ID}: {len(scene_shots)} shots found")

# Check all shots have characters (for blocking)
empty_char_shots = [s.get("shot_id") for s in scene_shots if not (s.get("characters") or [])]
if empty_char_shots:
    warn(f"{len(empty_char_shots)} shots have no characters: {empty_char_shots[:3]}")
else:
    ok("All shots have characters assigned")

# Check blocking data quality
has_gaze = sum(1 for s in scene_shots if s.get("gaze_direction"))
has_spatial = sum(1 for s in scene_shots if "spatial" in (s.get("nano_prompt", "") or "").lower())
ok(f"Gaze direction: {has_gaze}/{len(scene_shots)}")
ok(f"Spatial context in prompts: {has_spatial}/{len(scene_shots)}")

# Check gold standard
has_gold = sum(1 for s in scene_shots if "NO morphing" in (s.get("ltx_motion_prompt", "") or ""))
if has_gold < len(scene_shots):
    warn(f"Gold standard (NO morphing) only on {has_gold}/{len(scene_shots)} shots")
else:
    ok(f"Gold standard: {has_gold}/{len(scene_shots)}")

print()

# ═══════════════════════════════════════════════════════════════
# STEP 1: CONTROLLER PREPARE + LOCK
# ═══════════════════════════════════════════════════════════════

banner("STEP 1: Controller Prepare + Lock")

try:
    from atlas_v26_controller import V26Controller
except ImportError as e:
    halt(f"Cannot import V26Controller: {e}")

pipeline = str(PP)
controller = V26Controller(pipeline)

# Verify cast loaded
if not controller.cast_map:
    halt("Controller has no cast_map — characters won't get references")
ok(f"Cast map: {len(controller.cast_map)} entries")

# Prepare and lock
plan = controller.prepare_and_lock_scene(SCENE_ID)
if not plan.locked:
    halt(f"Scene plan could not be locked")
ok(f"Scene plan LOCKED — {plan.shot_count} shots, hash: {plan.lock_hash[:16]}")

generate_shots = [d for d in plan.shots if d.action == "generate"]
halt_shots = [d for d in plan.shots if d.action == "halt"]
reuse_shots = [d for d in plan.shots if d.action == "reuse"]

ok(f"Generate: {len(generate_shots)}, Halt: {len(halt_shots)}, Reuse: {len(reuse_shots)}")

if halt_shots:
    for h in halt_shots:
        warn(f"HALTED: {h.shot_id} — {h.reason}")

# Persist locked plan to disk
persisted = controller.persist_locked_plan(SCENE_ID)
if not persisted:
    halt("Failed to persist locked plan to disk — orchestrator would overwrite prompts")
ok("Locked plan persisted to shot_plan.json")

# Snapshot locked prompts for post-run audit
locked_snapshots = {}
for d in generate_shots:
    locked_snapshots[d.shot_id] = {
        "nano_hash": hashlib.sha256((d.nano_prompt or "").encode()).hexdigest()[:16],
        "ltx_hash": hashlib.sha256((d.ltx_prompt or "").encode()).hexdigest()[:16],
        "nano_preview": (d.nano_prompt or "")[:100],
    }

print()

# ═══════════════════════════════════════════════════════════════
# STEP 2: GENERATE — ONE SHOT AT A TIME, HALT ON FAILURE
# ═══════════════════════════════════════════════════════════════

if DRY_RUN:
    banner("STEP 2: GENERATION [DRY RUN — SKIPPED]")
    print(f"  Would generate {len(generate_shots)} shots:")
    for d in generate_shots:
        print(f"    {d.shot_id} ({d.action}) — nano_hash: {locked_snapshots[d.shot_id]['nano_hash']}")
    print()
else:
    banner(f"STEP 2: GENERATING {len(generate_shots)} SHOTS — HALT ON FIRST FAILURE")

    results = []
    start_time = time.time()

    for i, decision in enumerate(generate_shots):
        shot_start = time.time()
        print(f"  [{i+1}/{len(generate_shots)}] Generating {decision.shot_id}...", end=" ", flush=True)

        try:
            resp = httpx.post(
                f"{ORCH_URL}/api/auto/generate-first-frames",
                json={
                    "project": PROJECT,
                    "shot_ids": [decision.shot_id],
                    "dry_run": False,
                },
                timeout=120.0,
            )

            elapsed = time.time() - shot_start

            if resp.status_code == 200:
                result = resp.json()
                success = result.get("success", False)

                if success:
                    # Verify frame actually exists on disk
                    frame_path = PP / "first_frames" / f"{decision.shot_id}.jpg"
                    if frame_path.exists():
                        print(f"{Colors.GREEN}OK{Colors.END} ({elapsed:.1f}s)")
                        ok(f"Frame saved: {frame_path.stat().st_size:,} bytes")

                        # Verify prompt lock wasn't broken
                        with open(PP / "shot_plan.json") as f:
                            check_data = json.load(f)
                        if isinstance(check_data, list):  # T2-OR-18: bare-list guard
                            check_data = {"shots": check_data}
                        check_shots = check_data.get("shots", [])
                        current_shot = next((s for s in check_shots if s.get("shot_id") == decision.shot_id), None)
                        if current_shot:
                            current_hash = hashlib.sha256(
                                (current_shot.get("nano_prompt", "") or "").encode()
                            ).hexdigest()[:16]
                            expected_hash = locked_snapshots[decision.shot_id]["nano_hash"]
                            if current_hash == expected_hash:
                                ok(f"Prompt lock INTACT (hash: {current_hash})")
                            else:
                                fail(f"PROMPT LOCK BROKEN! Expected {expected_hash}, got {current_hash}")
                                halt(f"Prompt lock violated on {decision.shot_id} — orchestrator rewrote the prompt")

                        results.append({"shot_id": decision.shot_id, "ok": True, "time": elapsed})
                    else:
                        print(f"{Colors.RED}FRAME MISSING{Colors.END}")
                        halt(f"Orchestrator said success but no frame at {frame_path}")
                else:
                    error = result.get("error", "unknown")
                    print(f"{Colors.RED}FAILED{Colors.END}")
                    fail(f"Orchestrator error: {error}")
                    halt(f"Shot {decision.shot_id} failed: {error}")
            else:
                # Non-200 — extract error body
                try:
                    err = resp.json()
                    error_msg = err.get("error", err.get("detail", str(err)[:300]))
                except Exception:
                    error_msg = resp.text[:300]

                print(f"{Colors.RED}HTTP {resp.status_code}{Colors.END}")
                fail(f"Orchestrator rejected: {error_msg}")
                halt(f"HTTP {resp.status_code} on {decision.shot_id}: {error_msg}")

        except httpx.ConnectError:
            print(f"{Colors.RED}CONNECTION LOST{Colors.END}")
            halt(f"Orchestrator stopped responding during {decision.shot_id}")
        except httpx.TimeoutException:
            print(f"{Colors.RED}TIMEOUT{Colors.END}")
            halt(f"Shot {decision.shot_id} timed out after 120s")
        except Exception as e:
            print(f"{Colors.RED}ERROR{Colors.END}")
            halt(f"Unexpected error on {decision.shot_id}: {e}")

    total_time = time.time() - start_time
    ok(f"ALL {len(results)} shots generated in {total_time:.1f}s")
    print()

# ═══════════════════════════════════════════════════════════════
# STEP 3: POST-RUN AUDIT
# ═══════════════════════════════════════════════════════════════

banner("STEP 3: Post-Run Audit")

# Check FAL payload audit log
fal_log = Path("reports/fal_payload_audit.jsonl")
if fal_log.exists():
    with open(fal_log) as f:
        lines = f.readlines()
    # Count entries from this run (last N minutes)
    recent = [json.loads(l) for l in lines[-20:] if l.strip()]
    ok(f"FAL audit log: {len(lines)} total entries, {len(recent)} recent")

    for entry in recent[-3:]:
        print(f"    Model: {entry.get('model','?')}")
        print(f"    Prompt length: {entry.get('prompt_length',0)}")
        print(f"    Image refs: {entry.get('image_urls_count',0)}")
        print(f"    Resolution: {entry.get('resolution','?')}")
        print(f"    Has locked flag: {entry.get('has_locked_flag', False)}")
        print()
else:
    warn("No FAL audit log found — orchestrator may not have generated")

# Check controller ledger
ledger_path = PP / "v26_ledger.jsonl"
if ledger_path.exists():
    with open(ledger_path) as f:
        entries = [json.loads(l) for l in f if l.strip()]
    scene_entries = [e for e in entries if SCENE_ID in e.get("shot_id", "")]
    ok(f"Ledger: {len(scene_entries)} entries for scene {SCENE_ID}")

    # Identity scores
    id_entries = [e for e in scene_entries if e.get("reason_code") == "IDENTITY_SCORE"]
    if id_entries:
        scores = [e["deviation_score"] for e in id_entries if isinstance(e.get("deviation_score"), (int, float))]
        if scores:
            ok(f"Identity scores: avg={sum(scores)/len(scores):.2f}, range={min(scores):.2f}-{max(scores):.2f}")
        else:
            warn("Identity entries found but no numeric scores")
    else:
        warn("No identity score entries in ledger")
else:
    warn("No ledger file — controller may not have run render_scene()")

# Final prompt lock check
print()
print(f"  {Colors.BOLD}PROMPT LOCK INTEGRITY:{Colors.END}")
with open(PP / "shot_plan.json") as f:
    final_data = json.load(f)
if isinstance(final_data, list):  # T2-OR-18: bare-list guard
    final_data = {"shots": final_data}
final_shots = final_data.get("shots", [])

lock_ok = 0
lock_broken = 0
for shot_id, snapshot in locked_snapshots.items():
    current = next((s for s in final_shots if s.get("shot_id") == shot_id), None)
    if current:
        current_hash = hashlib.sha256((current.get("nano_prompt", "") or "").encode()).hexdigest()[:16]
        if current_hash == snapshot["nano_hash"]:
            ok(f"{shot_id}: lock intact")
            lock_ok += 1
        else:
            fail(f"{shot_id}: LOCK BROKEN — prompt was rewritten!")
            lock_broken += 1
    else:
        warn(f"{shot_id}: shot not found in final plan")

print()

# ═══════════════════════════════════════════════════════════════
# FINAL VERDICT
# ═══════════════════════════════════════════════════════════════

banner("FINAL VERDICT")

if DRY_RUN:
    print(f"  {Colors.YELLOW}DRY RUN — no generation performed{Colors.END}")
    print(f"  Scene {SCENE_ID}: {len(generate_shots)} shots would generate")
    print(f"  Prompt locks: {lock_ok} intact, {lock_broken} broken")
    print(f"  Run without --dry-run when orchestrator is live")
else:
    if lock_broken == 0 and len(results) == len(generate_shots):
        print(f"  {Colors.GREEN}{Colors.BOLD}SUCCESS{Colors.END}")
        print(f"  {len(results)} shots generated, all prompt locks intact")
        print(f"  Frames at: {PP / 'first_frames'}")
        print(f"  Ledger at: {ledger_path}")
        print(f"  FAL audit: {fal_log}")
    elif lock_broken > 0:
        print(f"  {Colors.RED}{Colors.BOLD}LOCK VIOLATION{Colors.END}")
        print(f"  {lock_broken} prompts were rewritten by the orchestrator")
        print(f"  The V26 lock guard may not be active")
    else:
        print(f"  {Colors.RED}{Colors.BOLD}GENERATION INCOMPLETE{Colors.END}")
        print(f"  Only {len(results)}/{len(generate_shots)} shots completed")

print()
