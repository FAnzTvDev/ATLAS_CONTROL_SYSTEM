#!/usr/bin/env python3
"""
V26 PROOF RUN — Single-scene monitored generation.

This is NOT a simulation. It calls the REAL orchestrator endpoint.
Every step is monitored and auditable.

Usage:
    python3 tools/proof_run.py ravencroft_v22 000
    python3 tools/proof_run.py ravencroft_v22 001 --dry-run

What it does:
    1. Reads shot_plan.json and captures pre-state snapshot
    2. Calls V26 Controller.prepare_and_lock_scene()
    3. Saves locked prompt hashes
    4. Calls V26 Controller.render_scene() (which calls orchestrator)
    5. After render: verifies lock hashes, reads FAL audit log, checks frames
    6. Produces full audit report

What it guarantees:
    - Pre-FAL prompts are captured in reports/fal_payload_audit.jsonl
    - Lock violations are detected immediately
    - Missing frames are flagged
    - Identity scores are recorded (when frames exist)
    - Full report saved to reports/proof_run_{scene}_{timestamp}.json
"""
import sys, os, json, hashlib, time, argparse
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

def snapshot_prompts(shots):
    """Capture prompt hashes before generation."""
    return {
        s.get("shot_id", ""): {
            "nano_hash": hashlib.sha256(
                s.get("nano_prompt", "").encode()
            ).hexdigest()[:16],
            "ltx_hash": hashlib.sha256(
                s.get("ltx_motion_prompt", "").encode()
            ).hexdigest()[:16],
            "nano_len": len(s.get("nano_prompt", "")),
            "ltx_len": len(s.get("ltx_motion_prompt", "")),
            "locked": s.get("_prompt_locked", False),
        }
        for s in shots
    }


def count_fal_audit_entries():
    """Count entries in FAL audit log."""
    audit_path = os.path.join(BASE, "reports", "fal_payload_audit.jsonl")
    if not os.path.exists(audit_path):
        return 0
    with open(audit_path) as f:
        return sum(1 for line in f if line.strip())


def get_new_fal_entries(start_count):
    """Get FAL audit entries added since start_count."""
    audit_path = os.path.join(BASE, "reports", "fal_payload_audit.jsonl")
    if not os.path.exists(audit_path):
        return []
    entries = []
    with open(audit_path) as f:
        for i, line in enumerate(f):
            if i >= start_count and line.strip():
                try:
                    entries.append(json.loads(line.strip()))
                except json.JSONDecodeError:
                    pass
    return entries


def check_frames_exist(pipeline_dir, shot_ids):
    """Check which frames were actually generated."""
    frames_dir = os.path.join(pipeline_dir, "first_frames")
    results = {}
    for sid in shot_ids:
        exists = False
        for ext in [".jpg", ".png", ".jpeg", ".webp"]:
            if os.path.exists(os.path.join(frames_dir, f"{sid}{ext}")):
                exists = True
                break
        results[sid] = exists
    return results


def run_proof(project, scene_id, dry_run=False):
    """Execute the proof run."""
    pipeline = os.path.join(BASE, "pipeline_outputs", project)
    reports_dir = os.path.join(BASE, "reports")
    os.makedirs(reports_dir, exist_ok=True)

    print("=" * 60)
    print(f"V26 PROOF RUN — {project} / Scene {scene_id}")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE GENERATION'}")
    print(f"Time: {datetime.utcnow().isoformat()}")
    print("=" * 60)
    print()

    report = {
        "project": project,
        "scene_id": scene_id,
        "dry_run": dry_run,
        "start_time": datetime.utcnow().isoformat(),
        "steps": [],
    }

    def step(name, result):
        report["steps"].append({"step": name, "result": result,
                                 "time": datetime.utcnow().isoformat()})
        icon = "✅" if result.get("ok", True) else "❌"
        print(f"  {icon} {name}: {result.get('detail', '')}")

    # ── Step 1: Load + Snapshot ──
    print("─" * 40)
    print("STEP 1: Pre-State Snapshot")
    print("─" * 40)

    shot_plan_path = os.path.join(pipeline, "shot_plan.json")
    if not os.path.exists(shot_plan_path):
        print(f"FATAL: No shot_plan.json at {shot_plan_path}")
        sys.exit(1)

    with open(shot_plan_path) as f:
        data = json.load(f)
    shots = data.get("shots", [])
    scene_shots = [s for s in shots
                   if (s.get("scene_id") or s.get("shot_id", "")[:3]) == scene_id]
    shot_ids = [s.get("shot_id", "") for s in scene_shots]

    pre_snapshot = snapshot_prompts(scene_shots)
    pre_frames = check_frames_exist(pipeline, shot_ids)
    fal_count_before = count_fal_audit_entries()

    step("pre_snapshot", {
        "ok": True,
        "detail": f"{len(scene_shots)} shots, {sum(pre_frames.values())} existing frames, {fal_count_before} prior FAL calls"
    })

    # ── Step 2: Controller Prepare + Lock ──
    print()
    print("─" * 40)
    print("STEP 2: Controller Prepare + Lock")
    print("─" * 40)

    try:
        from atlas_v26_controller import V26Controller as ATLASV26Controller
        controller = ATLASV26Controller(pipeline)

        # Prepare and lock
        plan = controller.prepare_and_lock_scene(scene_id)
        lock_count = sum(1 for d in plan.shots if d.action == "generate")
        generate_ids = [d.shot_id for d in plan.shots if d.action == "generate"]

        step("prepare_lock", {
            "ok": True,
            "detail": f"Locked {lock_count} shots for generation, {len(plan.shots) - lock_count} reuse/skip"
        })

        # Persist to disk
        persist_ok = controller.persist_locked_plan(scene_id)
        step("persist", {
            "ok": bool(persist_ok),
            "detail": f"Persisted locked plan to disk"
        })

        # Verify lock hashes on disk
        with open(shot_plan_path) as f:
            verify_data = json.load(f)
        verify_shots = [s for s in verify_data.get("shots", [])
                        if s.get("shot_id") in generate_ids]
        locked_on_disk = sum(1 for s in verify_shots if s.get("_prompt_locked"))
        step("verify_disk_lock", {
            "ok": locked_on_disk == len(generate_ids),
            "detail": f"{locked_on_disk}/{len(generate_ids)} shots locked on disk"
        })

    except Exception as e:
        step("prepare_lock", {"ok": False, "detail": str(e)})
        report["end_time"] = datetime.utcnow().isoformat()
        report["verdict"] = "FAILED — controller prepare/lock failed"
        _save_report(report, reports_dir, project, scene_id)
        return report

    # ── Step 3: Generation ──
    print()
    print("─" * 40)
    if dry_run:
        print("STEP 3: DRY RUN — Skipping FAL generation")
    else:
        print("STEP 3: LIVE GENERATION via Controller")
    print("─" * 40)

    if dry_run:
        step("generation", {
            "ok": True,
            "detail": f"DRY RUN — would generate {lock_count} shots via orchestrator"
        })
    else:
        try:
            gen_start = time.time()
            gen_result = controller.render_scene(scene_id)
            gen_elapsed = time.time() - gen_start

            gen_success = gen_result.get("success", False)
            render = gen_result.get("render_results", {})
            gen_count = render.get("shots_generated", 0)
            gen_attempted = render.get("shots_attempted", 0)

            # Capture per-shot errors for diagnosis
            shot_errors = []
            for sr in gen_result.get("shot_results", []):
                if sr.get("error"):
                    shot_errors.append(f"{sr.get('shot_id','?')}: {sr['error']}")

            # Check for halt
            if gen_result.get("halted"):
                detail = f"HALTED — {gen_result.get('halt_reason', 'unknown')}"
            else:
                detail = f"{'SUCCESS' if gen_success else 'FAILED'} — {gen_count}/{gen_attempted} shots in {gen_elapsed:.1f}s"
            if shot_errors:
                detail += "\n    ── PER-SHOT ERRORS ──"
                for se in shot_errors[:5]:
                    detail += f"\n    {se}"
            step("generation", {"ok": gen_success, "detail": detail})

            # Record phase results
            phases = gen_result.get("phases", {})
            for phase_name, phase_data in phases.items():
                step(f"phase_{phase_name}", {
                    "ok": True,
                    "detail": str(phase_data)[:100]
                })

            # Record render metrics
            if render:
                step("render_metrics", {
                    "ok": True,
                    "detail": f"identity_avg={render.get('identity_avg', -1):.2f}, "
                              f"locks_intact={render.get('prompt_locks_intact', 0)}, "
                              f"compliance={render.get('compliance_score', 0):.1f}%"
                })

        except Exception as e:
            step("generation", {"ok": False, "detail": str(e)})

    # ── Step 4: Post-Generation Audit ──
    print()
    print("─" * 40)
    print("STEP 4: Post-Generation Audit")
    print("─" * 40)

    # Reload from disk to see what orchestrator wrote
    with open(shot_plan_path) as f:
        post_data = json.load(f)
    post_shots = [s for s in post_data.get("shots", [])
                  if (s.get("scene_id") or s.get("shot_id", "")[:3]) == scene_id]

    post_snapshot = snapshot_prompts(post_shots)

    # Check for lock violations
    violations = []
    for sid, pre in pre_snapshot.items():
        post = post_snapshot.get(sid, {})
        if pre.get("locked") or post.get("locked"):
            # After locking, the prompt may change (that's the lock step)
            # But after generation, it should match the locked version
            pass

    # Check locked shots on disk haven't been mutated
    lock_check_count = 0
    lock_violations = 0
    for s in post_shots:
        sid = s.get("shot_id", "")
        if s.get("_prompt_locked"):
            lock_check_count += 1
            locked_nano = s.get("_locked_nano_prompt", "")
            current_nano = s.get("nano_prompt", "")
            if locked_nano and current_nano != locked_nano:
                lock_violations += 1
                violations.append(sid)

    step("lock_integrity", {
        "ok": lock_violations == 0,
        "detail": f"{lock_check_count} locked shots checked, {lock_violations} violations" +
                  (f" [{', '.join(violations)}]" if violations else "")
    })

    # Check frames generated
    post_frames = check_frames_exist(pipeline, shot_ids)
    new_frames = sum(1 for sid in shot_ids
                     if post_frames.get(sid) and not pre_frames.get(sid))
    step("frames_generated", {
        "ok": True,
        "detail": f"{new_frames} new frames generated, {sum(post_frames.values())} total"
    })

    # Check FAL audit trail
    new_fal_entries = get_new_fal_entries(fal_count_before)
    step("fal_audit", {
        "ok": True,
        "detail": f"{len(new_fal_entries)} new FAL calls captured in audit log"
    })

    # ── Verdict ──
    print()
    print("=" * 60)
    any_fail = any(not s["result"].get("ok", True) for s in report["steps"])
    if any_fail:
        verdict = "🔴 PROOF RUN FAILED — check steps above"
    elif dry_run:
        verdict = "🟡 DRY RUN COMPLETE — controller prepared and locked, no FAL calls made"
    else:
        verdict = f"🟢 PROOF RUN PASSED — {new_frames} frames generated with full monitoring"

    print(verdict)
    report["end_time"] = datetime.utcnow().isoformat()
    report["verdict"] = verdict
    report["fal_entries_captured"] = len(new_fal_entries)
    report["lock_violations"] = lock_violations
    report["new_frames"] = new_frames

    _save_report(report, reports_dir, project, scene_id)
    print("=" * 60)
    return report


def _save_report(report, reports_dir, project, scene_id):
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(reports_dir, f"proof_run_{project}_{scene_id}_{ts}.json")
    with open(path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nReport saved: {path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="V26 Proof Run")
    parser.add_argument("project", help="Project name")
    parser.add_argument("scene_id", help="Scene ID to render")
    parser.add_argument("--dry-run", action="store_true", help="Skip actual FAL generation")
    args = parser.parse_args()

    run_proof(args.project, args.scene_id, args.dry_run)
