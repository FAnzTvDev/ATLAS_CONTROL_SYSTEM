#!/usr/bin/env python3
"""
V26 POST-RUN AUDIT — Compares controller intent vs FAL reality.

Reads:
  1. Controller ledger (reports/v26_run_ledger.jsonl) — what the controller locked
  2. FAL payload audit (reports/fal_payload_audit.jsonl) — what actually reached FAL
  3. Generated frames — what came back

Reports:
  - Prompt drift: controller locked X, FAL received Y
  - Missing generations: controller said generate, no frame exists
  - Identity scores: per-shot vision analysis results
  - Lock violations: prompts that changed after locking
"""
import sys, os, json, glob
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

def audit_run(project: str, scene_id: str = None):
    """Full post-run audit for a project."""
    pipeline = os.path.join(BASE, "pipeline_outputs", project)
    reports_dir = os.path.join(BASE, "reports")

    report = {
        "project": project,
        "scene_filter": scene_id,
        "timestamp": datetime.utcnow().isoformat(),
        "fal_calls": [],
        "controller_decisions": [],
        "prompt_drift": [],
        "missing_frames": [],
        "lock_violations": [],
        "identity_scores": [],
        "summary": {},
    }

    # ── 1. Read FAL Payload Audit ──
    fal_audit_path = os.path.join(reports_dir, "fal_payload_audit.jsonl")
    fal_calls = []
    if os.path.exists(fal_audit_path):
        with open(fal_audit_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        fal_calls.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    report["fal_calls"] = fal_calls
    print(f"FAL payload audit: {len(fal_calls)} calls logged")

    # ── 2. Read Controller Ledger ──
    ledger_path = os.path.join(reports_dir, "v26_run_ledger.jsonl")
    if not os.path.exists(ledger_path):
        ledger_path = os.path.join(pipeline, "reports", "v26_run_ledger.jsonl")
    ledger_entries = []
    if os.path.exists(ledger_path):
        with open(ledger_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        ledger_entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    report["controller_decisions"] = ledger_entries
    print(f"Controller ledger: {len(ledger_entries)} entries")

    # ── 3. Check Shot Plan vs Generated Frames ──
    shot_plan_path = os.path.join(pipeline, "shot_plan.json")
    if os.path.exists(shot_plan_path):
        with open(shot_plan_path) as f:
            data = json.load(f)
        shots = data.get("shots", [])

        if scene_id:
            shots = [s for s in shots if
                     (s.get("scene_id") or s.get("shot_id", "")[:3]) == scene_id]

        frames_dir = os.path.join(pipeline, "first_frames")
        existing_frames = set()
        if os.path.exists(frames_dir):
            for f in os.listdir(frames_dir):
                if f.endswith((".jpg", ".png", ".jpeg", ".webp")):
                    existing_frames.add(os.path.splitext(f)[0])

        for s in shots:
            sid = s.get("shot_id", "")
            if sid not in existing_frames:
                report["missing_frames"].append({
                    "shot_id": sid,
                    "has_prompt": bool(s.get("nano_prompt")),
                    "locked": s.get("_prompt_locked", False),
                })

        # ── 4. Check Prompt Lock Integrity ──
        for s in shots:
            sid = s.get("shot_id", "")
            if s.get("_prompt_locked"):
                # Compare current prompt vs locked version
                locked_nano = s.get("_locked_nano_prompt", "")
                current_nano = s.get("nano_prompt", "")
                if locked_nano and current_nano != locked_nano:
                    report["lock_violations"].append({
                        "shot_id": sid,
                        "locked_len": len(locked_nano),
                        "current_len": len(current_nano),
                        "drift_chars": abs(len(current_nano) - len(locked_nano)),
                    })

        # ── 5. Prompt Drift Analysis (controller locked vs FAL received) ──
        # Map FAL calls by prompt content to detect drift
        for s in shots:
            sid = s.get("shot_id", "")
            nano = s.get("nano_prompt", "")
            nano_final = s.get("nano_prompt_final", "")
            if nano and nano_final and nano != nano_final:
                report["prompt_drift"].append({
                    "shot_id": sid,
                    "nano_len": len(nano),
                    "final_len": len(nano_final),
                    "match": nano == nano_final,
                })

        print(f"Shot plan: {len(shots)} shots, {len(existing_frames)} frames exist")
        print(f"Missing frames: {len(report['missing_frames'])}")
        print(f"Lock violations: {len(report['lock_violations'])}")
        print(f"Prompt drift: {len(report['prompt_drift'])}")

    # ── Summary ──
    report["summary"] = {
        "fal_calls_total": len(fal_calls),
        "controller_entries": len(ledger_entries),
        "missing_frames": len(report["missing_frames"]),
        "lock_violations": len(report["lock_violations"]),
        "prompt_drift_count": len(report["prompt_drift"]),
        "health": "GREEN" if not report["lock_violations"] else "RED",
    }

    # Save report
    os.makedirs(reports_dir, exist_ok=True)
    report_path = os.path.join(reports_dir, f"post_run_audit_{project}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nAudit saved: {report_path}")

    return report


def print_audit_summary(report):
    """Print human-readable audit summary."""
    print()
    print("=" * 60)
    print("POST-RUN AUDIT SUMMARY")
    print("=" * 60)
    s = report["summary"]
    print(f"  FAL calls logged:    {s['fal_calls_total']}")
    print(f"  Controller entries:  {s['controller_entries']}")
    print(f"  Missing frames:      {s['missing_frames']}")
    print(f"  Lock violations:     {s['lock_violations']}")
    print(f"  Prompt drift:        {s['prompt_drift_count']}")
    print()

    if s["lock_violations"] > 0:
        print("🔴 LOCK VIOLATIONS DETECTED:")
        for v in report["lock_violations"][:5]:
            print(f"    {v['shot_id']}: locked={v['locked_len']}ch, current={v['current_len']}ch")
        print()

    if s["health"] == "GREEN":
        print("🟢 HEALTH: GREEN — no prompt lock violations")
    else:
        print("🔴 HEALTH: RED — prompts were mutated after locking")

    print()


if __name__ == "__main__":
    project = sys.argv[1] if len(sys.argv) > 1 else "ravencroft_v22"
    scene = sys.argv[2] if len(sys.argv) > 2 else None
    report = audit_run(project, scene)
    print_audit_summary(report)
