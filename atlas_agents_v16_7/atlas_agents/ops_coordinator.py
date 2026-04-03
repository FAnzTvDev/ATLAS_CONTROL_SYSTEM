"""
ATLAS Ops Coordinator - Governor Mode

This is no longer just a runner. It is the GOVERNOR of agent execution.

Responsibilities:
1. Begin/complete execution runs with immutable context
2. Set execution mode ONCE, all agents obey
3. Collect structured agent summaries
4. Make decisions based on Critic verdicts
5. Only escalate to humans when Critic says NEEDS_HUMAN_JUDGMENT

Control Flow:
    begin_run(mode, projects)
        → cast_agent → emit_summary
        → propagate_cast → emit_summary
        → plan_fixer → emit_summary
        → critic_gate → emit_summary
        → DECISION POINT:
            - READY → complete_run("READY")
            - NEEDS_REPAIR → re-run in REPAIR mode
            - NEEDS_HUMAN_JUDGMENT → escalate, wait
        → complete_run(verdict)
"""

from __future__ import annotations
import json
import time
import hashlib
from pathlib import Path
from typing import List, Optional, Literal

from .cast_agent import cast_agent_run
from .cast_propagator import propagate_cast_to_shots
from .plan_fixer import plan_fixer_run
from .critic_gate import critic_gate_run
from .live_sync import recent_renders_scan, live_job_create, live_job_update
from .execution_context import ExecutionContext, ExecutionMode
from .agent_status_log import AgentStatusLog, create_agent_summary

# V17 Repair Agents - Run when critic identifies structural violations
from .cast_propagation_agent import run_cast_propagation
from .extended_video_stitch_agent import run_extended_video_stitch
from .ui_consistency_enforcer import run_ui_consistency_enforcer


class SignatureMismatchError(Exception):
    """Raised when LOCKED mode signature verification fails."""
    pass


def _compute_file_hash(file_path: Path) -> str:
    """Compute truncated SHA256 hash of a file."""
    if not file_path.exists():
        return "MISSING"
    content = file_path.read_bytes()
    return hashlib.sha256(content).hexdigest()[:16]


def verify_factory_signature(repo_root: Path) -> dict:
    """
    Verify all component hashes match FACTORY_SIGNATURE.json.

    Returns:
        {"valid": bool, "mismatches": [...], "factory_mode": str}
    """
    sig_path = repo_root / "FACTORY_SIGNATURE.json"
    if not sig_path.exists():
        return {"valid": True, "mismatches": [], "factory_mode": "UNLOCKED"}

    with open(sig_path) as f:
        signature = json.load(f)

    factory_mode = signature.get("factory_mode", "UNLOCKED")
    components = signature.get("components", {})
    mismatches = []

    for name, info in components.items():
        file_path = repo_root / info["file"]
        expected_hash = info["hash"]
        actual_hash = _compute_file_hash(file_path)

        if actual_hash != expected_hash:
            mismatches.append({
                "component": name,
                "file": info["file"],
                "expected": expected_hash,
                "actual": actual_hash
            })

    return {
        "valid": len(mismatches) == 0,
        "mismatches": mismatches,
        "factory_mode": factory_mode
    }


def auto_regenerate_signature(repo_root: Path) -> dict:
    """
    AUTO-HEAL: Regenerate FACTORY_SIGNATURE.json with current file hashes.
    Called when mismatch detected to enable zero-stoppage operation.
    """
    from datetime import datetime

    sig_path = repo_root / "FACTORY_SIGNATURE.json"

    # Load existing signature to preserve structure
    if sig_path.exists():
        with open(sig_path) as f:
            signature = json.load(f)
    else:
        signature = {"components": {}, "factory_mode": "LOCKED"}

    # Get current version and increment patch
    old_version = signature.get("version", "V18.2.0")
    version_parts = old_version.replace("V", "").split(".")
    try:
        major, minor, patch = int(version_parts[0]), int(version_parts[1]), int(version_parts[2])
        new_version = f"V{major}.{minor}.{patch + 1}"
    except:
        new_version = "V18.3.0"

    # Recompute all component hashes
    components = signature.get("components", {})
    combined = ""
    updated_components = {}

    for name, info in components.items():
        file_path = repo_root / info["file"]
        new_hash = _compute_file_hash(file_path)
        updated_components[name] = {
            "file": info["file"],
            "hash": new_hash
        }
        combined += new_hash

    # Update signature
    signature["version"] = new_version
    signature["generated_at"] = datetime.now().isoformat()
    signature["components"] = updated_components
    signature["combined_signature"] = hashlib.sha256(combined.encode()).hexdigest()
    signature["_auto_healed"] = True
    signature["_auto_healed_at"] = datetime.now().isoformat()

    # Write back
    with open(sig_path, 'w') as f:
        json.dump(signature, f, indent=2)

    return {
        "success": True,
        "old_version": old_version,
        "new_version": new_version,
        "components_updated": len(updated_components)
    }


class OpsCoordinator:
    """
    Governor for ATLAS agent pipeline.

    Usage:
        coord = OpsCoordinator(repo_root="/path/to/ATLAS")
        result = coord.run_pipeline(
            projects=["kord_v17", "ravencroft_v17"],
            mode="REPAIR"
        )
    """

    def __init__(self, repo_root: Path):
        self.repo_root = Path(repo_root)
        self.ctx = ExecutionContext(repo_root)

    def run_pipeline(
        self,
        projects: List[str],
        mode: ExecutionMode = "VERIFY",
        initiated_by: str = "human",
        max_repair_attempts: int = 2
    ) -> dict:
        """
        Execute the full agent pipeline with governance.

        Args:
            projects: List of project names to process
            mode: LOCKED, VERIFY, REPAIR, or OVERWRITE
            initiated_by: human, ops_coordinator, or scheduled
            max_repair_attempts: Max times to retry in REPAIR mode

        Returns:
            {
                "run_id": "abc123",
                "final_verdict": "READY" | "NEEDS_HUMAN_JUDGMENT",
                "projects": { ... per-project results ... }
            }
        """
        # 0. V17: Verify factory signature in LOCKED mode
        # MOVIE_MODE: Block drift, don't auto-heal - director must approve changes
        sig_check = verify_factory_signature(self.repo_root)
        if sig_check["factory_mode"] == "LOCKED":
            if not sig_check["valid"]:
                # BLOCK: Do not auto-heal in LOCKED/MOVIE mode - drift must be explicit
                print("\n" + "=" * 60)
                print("🛑 SIGNATURE MISMATCH DETECTED - BLOCKING EXECUTION")
                print("=" * 60)
                print("\nThe following components have changed since factory lock:")
                for m in sig_check["mismatches"]:
                    print(f"  ❌ {m['component']}")
                    print(f"     Expected: {m['expected'][:16]}...")
                    print(f"     Actual:   {m['actual'][:16]}...")

                print("\n⚠️  LOCKED mode prevents automatic signature regeneration.")
                print("    This protects your movie from unintended code drift.")
                print("\nTo resolve:")
                print("  1. Review the changed files above")
                print("  2. If changes are intentional, run: python3 tools/canonical_hash.py --regenerate")
                print("  3. If changes are unintended, revert the files")
                print("=" * 60 + "\n")

                # Log to Sentry if available
                try:
                    import sentry_sdk
                    sentry_sdk.capture_message(
                        f"SIGNATURE_DRIFT_BLOCKED: {len(sig_check['mismatches'])} components changed",
                        level="warning"
                    )
                except ImportError:
                    pass

                # Return failure - do not continue with drifted code
                return {
                    "run_id": "BLOCKED",
                    "final_verdict": "SIGNATURE_DRIFT",
                    "error": "Factory signature mismatch in LOCKED mode",
                    "mismatches": sig_check["mismatches"],
                    "resolution": "Review changes and regenerate signature if intentional"
                }
            else:
                print("[SIGNATURE] ✅ Factory signature verified - all components match")

        # 1. Begin execution run (immutable from here)
        context = self.ctx.begin_run(
            mode=mode,
            projects=projects,
            initiated_by=initiated_by
        )
        run_id = context["run_id"]

        print(f"\n{'='*60}")
        print(f"ATLAS OPS COORDINATOR - RUN {run_id}")
        print(f"Mode: {mode} | Projects: {projects}")
        print(f"{'='*60}\n")

        results = {"run_id": run_id, "projects": {}}
        repair_attempts = 0

        # 2. Process each project
        for project in projects:
            project_result = self._run_project_pipeline(
                project=project,
                run_id=run_id,
                mode=mode
            )
            results["projects"][project] = project_result

        # 3. Aggregate verdicts
        all_verdicts = [r.get("critic_verdict") for r in results["projects"].values()]

        if all(v == "READY" for v in all_verdicts):
            # All projects ready - complete run
            final_verdict = "READY"

        elif any(v == "NEEDS_HUMAN_JUDGMENT" for v in all_verdicts):
            # At least one needs human - escalate
            final_verdict = "NEEDS_HUMAN_JUDGMENT"
            print("\n" + "!"*60)
            print("ESCALATION: Critic requires human judgment")
            print("Projects requiring attention:")
            for proj, res in results["projects"].items():
                if res.get("critic_verdict") == "NEEDS_HUMAN_JUDGMENT":
                    print(f"  - {proj}: {res.get('critic_reason', 'See critic report')}")
            print("!"*60 + "\n")

        elif any(v == "NEEDS_REPAIR" for v in all_verdicts) and repair_attempts < max_repair_attempts:
            # Some need repair - re-run in REPAIR mode
            repair_attempts += 1
            print(f"\n[COORDINATOR] Repair attempt {repair_attempts}/{max_repair_attempts}")

            # Complete current run
            self.ctx.complete_run("NEEDS_REPAIR")

            # Start new repair run
            return self.run_pipeline(
                projects=[p for p, r in results["projects"].items()
                         if r.get("critic_verdict") == "NEEDS_REPAIR"],
                mode="REPAIR",
                initiated_by="ops_coordinator",
                max_repair_attempts=max_repair_attempts - repair_attempts
            )

        else:
            final_verdict = "NEEDS_REPAIR"

        # 4. Complete run
        self.ctx.complete_run(final_verdict)
        results["final_verdict"] = final_verdict

        print(f"\n{'='*60}")
        print(f"RUN {run_id} COMPLETE - VERDICT: {final_verdict}")
        print(f"{'='*60}\n")

        return results

    def _run_project_pipeline(
        self,
        project: str,
        run_id: str,
        mode: ExecutionMode
    ) -> dict:
        """
        Run agent pipeline for a single project.
        Emits structured summaries to status log.
        """
        project_path = self.repo_root / "pipeline_outputs" / project
        status_log = AgentStatusLog(project_path)

        result = {
            "project": project,
            "mode": mode,
            "agents": {}
        }

        # Determine write behavior based on mode
        allow_overwrite = mode in ("REPAIR", "OVERWRITE")

        print(f"\n[{project}] Starting pipeline (mode={mode})")

        # ========== CAST AGENT ==========
        start = time.time()
        status_log.emit("cast_agent", "STARTED", run_id)

        try:
            r1 = cast_agent_run(project, overwrite=allow_overwrite, repo_root=self.repo_root)
            duration = int((time.time() - start) * 1000)

            status_log.emit(
                "cast_agent", "COMPLETE", run_id,
                facts={
                    "characters": r1.get("cast_count", 0),
                    "extras_pools": r1.get("extras_count", 0),
                    "path": str(r1.get("cast_map_path", ""))
                },
                duration_ms=duration
            )
            result["agents"]["cast_agent"] = r1
            print(f"  [cast_agent] {r1.get('cast_count', 0)} characters cast")

        except Exception as e:
            status_log.emit("cast_agent", "FAILED", run_id, error=str(e))
            result["agents"]["cast_agent"] = {"success": False, "error": str(e)}

        # ========== CAST PROPAGATOR ==========
        start = time.time()
        status_log.emit("cast_propagator", "STARTED", run_id)

        try:
            r2 = propagate_cast_to_shots(project, repo_root=self.repo_root)
            duration = int((time.time() - start) * 1000)

            status_log.emit(
                "cast_propagator", "COMPLETE", run_id,
                facts={"shots_updated": r2.get("updated_shots", 0)},
                duration_ms=duration
            )
            result["agents"]["cast_propagator"] = r2
            print(f"  [cast_propagator] {r2.get('updated_shots', 0)} shots updated")

        except Exception as e:
            status_log.emit("cast_propagator", "FAILED", run_id, error=str(e))
            result["agents"]["cast_propagator"] = {"success": False, "error": str(e)}

        # ========== PLAN FIXER ==========
        start = time.time()
        status_log.emit("plan_fixer", "STARTED", run_id)

        try:
            r3 = plan_fixer_run(project, repo_root=self.repo_root)
            duration = int((time.time() - start) * 1000)

            status_log.emit(
                "plan_fixer", "COMPLETE", run_id,
                facts={
                    "shots_fixed": r3.get("fixed_count", 0),
                    "extended_shots": r3.get("extended_count", 0)
                },
                duration_ms=duration
            )
            result["agents"]["plan_fixer"] = r3
            print(f"  [plan_fixer] {r3.get('fixed_count', 0)} shots fixed")

        except Exception as e:
            status_log.emit("plan_fixer", "FAILED", run_id, error=str(e))
            result["agents"]["plan_fixer"] = {"success": False, "error": str(e)}

        # ========== CRITIC GATE (FINAL AUTHORITY) ==========
        start = time.time()
        status_log.emit("critic_gate", "STARTED", run_id)

        try:
            r4 = critic_gate_run(project, repo_root=self.repo_root)
            duration = int((time.time() - start) * 1000)

            # Critic determines the verdict
            if r4.get("safe_to_render"):
                critic_verdict = "READY"
            elif r4.get("needs_human"):
                critic_verdict = "NEEDS_HUMAN_JUDGMENT"
            elif r4.get("blocking_count", 0) > 0:
                critic_verdict = "NEEDS_REPAIR"
            else:
                critic_verdict = "READY"

            status_log.emit(
                "critic_gate", "COMPLETE", run_id,
                facts={
                    "blocking": r4.get("blocking_count", 0),
                    "warnings": r4.get("warning_count", 0),
                    "verdict": critic_verdict
                },
                duration_ms=duration
            )

            result["agents"]["critic_gate"] = r4
            result["critic_verdict"] = critic_verdict
            result["critic_reason"] = r4.get("reason", "")

            print(f"  [critic_gate] Verdict: {critic_verdict} "
                  f"(blocking={r4.get('blocking_count', 0)}, warnings={r4.get('warning_count', 0)})")

        except Exception as e:
            status_log.emit("critic_gate", "FAILED", run_id, error=str(e))
            result["agents"]["critic_gate"] = {"success": False, "error": str(e)}
            result["critic_verdict"] = "NEEDS_HUMAN_JUDGMENT"
            result["critic_reason"] = f"Critic failed: {e}"

        # ========== V17 REPAIR AGENTS (When Critic Demands) ==========
        # If critic says NEEDS_REPAIR, run targeted repair agents
        repairs_required = result["agents"].get("critic_gate", {}).get("repairs_required", [])

        if repairs_required and mode == "REPAIR":
            print(f"  [repair_agents] Running repairs: {repairs_required}")

            # CAST PROPAGATION
            if "cast_propagation" in repairs_required:
                start = time.time()
                status_log.emit("cast_propagation_agent", "STARTED", run_id)
                try:
                    rcp = run_cast_propagation(project, repo_root=self.repo_root)
                    duration = int((time.time() - start) * 1000)
                    status_log.emit(
                        "cast_propagation_agent", "COMPLETE", run_id,
                        facts=rcp.get("facts", {}),
                        duration_ms=duration
                    )
                    result["agents"]["cast_propagation_agent"] = rcp
                    print(f"    [cast_propagation] {rcp.get('facts', {}).get('shots_fixed', 0)} shots fixed")
                except Exception as e:
                    status_log.emit("cast_propagation_agent", "FAILED", run_id, error=str(e))
                    result["agents"]["cast_propagation_agent"] = {"success": False, "error": str(e)}

            # VIDEO STITCH
            if "video_stitch" in repairs_required:
                start = time.time()
                status_log.emit("extended_video_stitch", "STARTED", run_id)
                try:
                    rvs = run_extended_video_stitch(project, repo_root=self.repo_root)
                    duration = int((time.time() - start) * 1000)
                    status_log.emit(
                        "extended_video_stitch", "COMPLETE", run_id,
                        facts=rvs.get("facts", {}),
                        duration_ms=duration
                    )
                    result["agents"]["extended_video_stitch"] = rvs
                    print(f"    [video_stitch] {rvs.get('facts', {}).get('stitched', 0)} videos stitched")
                except Exception as e:
                    status_log.emit("extended_video_stitch", "FAILED", run_id, error=str(e))
                    result["agents"]["extended_video_stitch"] = {"success": False, "error": str(e)}

            # UI CONSISTENCY ENFORCER
            if "ui_consistency_enforcer" in repairs_required:
                start = time.time()
                status_log.emit("ui_consistency_enforcer", "STARTED", run_id)
                try:
                    rue = run_ui_consistency_enforcer(project, repo_root=self.repo_root)
                    duration = int((time.time() - start) * 1000)
                    status_log.emit(
                        "ui_consistency_enforcer", "COMPLETE", run_id,
                        facts=rue.get("facts", {}),
                        duration_ms=duration
                    )
                    result["agents"]["ui_consistency_enforcer"] = rue
                    print(f"    [ui_enforcer] {rue.get('facts', {}).get('beats_created', 0)} beats created")
                except Exception as e:
                    status_log.emit("ui_consistency_enforcer", "FAILED", run_id, error=str(e))
                    result["agents"]["ui_consistency_enforcer"] = {"success": False, "error": str(e)}

            # After repairs, re-run critic to get updated verdict
            print(f"  [critic_gate] Re-running after repairs...")
            try:
                r4_post = critic_gate_run(project, repo_root=self.repo_root)
                result["agents"]["critic_gate_post_repair"] = r4_post

                # Update verdict based on post-repair critic
                if r4_post.get("safe_to_render"):
                    result["critic_verdict"] = "READY"
                elif r4_post.get("needs_human"):
                    result["critic_verdict"] = "NEEDS_HUMAN_JUDGMENT"
                else:
                    result["critic_verdict"] = "NEEDS_REPAIR"

                result["critic_reason"] = r4_post.get("reason", "")
                print(f"  [critic_gate] Post-repair verdict: {result['critic_verdict']}")

            except Exception as e:
                print(f"  [critic_gate] Post-repair check failed: {e}")

        # ========== ASSET SCAN ==========
        try:
            r5 = recent_renders_scan(project, repo_root=self.repo_root)
            result["agents"]["asset_scan"] = r5
        except Exception as e:
            result["agents"]["asset_scan"] = {"success": False, "error": str(e)}

        return result


# ============================================================
# LEGACY INTERFACE (backwards compatibility)
# ============================================================

def ops_autopilot(
    project: str,
    mode: str = "prep",
    overwrite_cast: bool = False,
    repo_root: str | Path | None = None
) -> dict:
    """
    Legacy interface for single-project runs.
    Prefer OpsCoordinator.run_pipeline() for governed execution.
    """
    if repo_root is None:
        repo_root = Path(__file__).parent.parent.parent

    # Map legacy modes to execution modes
    mode_map = {
        "prep": "VERIFY",
        "canary": "VERIFY",
        "full": "REPAIR" if overwrite_cast else "VERIFY"
    }
    exec_mode = mode_map.get(mode, "VERIFY")

    coord = OpsCoordinator(repo_root)

    # For legacy, skip governance and run directly
    result = coord._run_project_pipeline(
        project=project,
        run_id="legacy",
        mode=exec_mode
    )

    # Canary job stub
    if mode == "canary":
        job = live_job_create(
            project, "render-canary",
            {"project": project, "note": "stub job"},
            repo_root=repo_root
        )
        result["canary_job"] = job

    result["success"] = result.get("critic_verdict") in ("READY", None)
    return result
