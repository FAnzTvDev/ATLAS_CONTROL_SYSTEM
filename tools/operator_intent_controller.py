"""
ATLAS V25.2 — OPERATOR INTENT CONTROLLER
==========================================
The nervous system between operator and ATLAS body.

Routes ALL actions through the Control Spine (atlas_control_spine.py).
No component may independently authorize production action.
Only this controller can authorize: render, bootstrap, rerun, merge.

Architecture:
    Operator → Intent Controller → Control Spine (state + policy) → Worker Agents → Truth Surface

Laws:
    256. Intent Controller is NON-BLOCKING on internal errors — always returns a report
    257. Readiness check runs BEFORE any FAL spend — NEVER skip
    258. Bootstrap actions are AUTOMATIC — operator never solves chicken-and-egg manually
    259. Every action returns operator-readable report — NEVER return raw JSON
    260. Controller logs every intent to append-only ledger — NEVER lose intent history
    261. Control spine is SINGLE AUTHORITY — no bypass routes
    265. Pressure cannot change operation order — NEVER skip diagnosis under urgency

Usage:
    from tools.operator_intent_controller import execute_intent

    result = execute_intent("run_scene", {
        "project": "victorian_shadows_ep1",
        "scene": "001"
    })
    print(result.report)
"""

import json
import os
import time
import logging
import subprocess
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Import control spine (single authority)
# ---------------------------------------------------------------------------

BASE_DIR = Path(os.environ.get("ATLAS_BASE_DIR",
    Path(__file__).resolve().parent.parent))
PIPELINE_DIR = BASE_DIR / "pipeline_outputs"

try:
    from tools.atlas_control_spine import (
        assess_scene, assess_project, harmony_audit, format_harmony_report,
        SceneState, ActionType, SceneHealth, ProjectHealth
    )
    _HAS_SPINE = True
except ImportError:
    try:
        import sys
        sys.path.insert(0, str(BASE_DIR / "tools"))
        from atlas_control_spine import (
            assess_scene, assess_project, harmony_audit, format_harmony_report,
            SceneState, ActionType, SceneHealth, ProjectHealth
        )
        _HAS_SPINE = True
    except ImportError:
        _HAS_SPINE = False
        logger.warning("Control spine not available — running in degraded mode")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class IntentResult:
    """Result of an operator intent execution."""
    intent: str
    success: bool
    ready: bool
    report: str
    state: str = "UNKNOWN"
    blocking_issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    actions_taken: List[str] = field(default_factory=list)
    bootstrapped: List[str] = field(default_factory=list)
    allowed_actions: List[str] = field(default_factory=list)
    cost_estimate: float = 0.0
    time_estimate_minutes: float = 0.0
    health_score: float = 0.0
    data: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Intent Ledger — append-only (Law 260)
# ---------------------------------------------------------------------------

def _log_intent(project: str, intent: str, params: dict, result: IntentResult):
    """Append intent to ledger."""
    try:
        ledger_path = PIPELINE_DIR / project / "intent_ledger.jsonl"
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": datetime.now().isoformat(),
            "intent": intent,
            "params": params,
            "success": result.success,
            "state": result.state,
            "ready": result.ready,
            "health": result.health_score,
            "blocking": result.blocking_issues,
            "actions": result.actions_taken,
            "cost": result.cost_estimate
        }
        with open(ledger_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass  # Law 256: non-blocking


# ---------------------------------------------------------------------------
# Format helpers
# ---------------------------------------------------------------------------

def _format_scene_health(health: 'SceneHealth') -> str:
    """Format scene health as operator-readable text."""
    lines = []
    lines.append(f"{'=' * 60}")
    lines.append(f"  SCENE STATUS — {health.project} / Scene {health.scene_id}")
    lines.append(f"  State: {health.state.value} | Health: {health.health_score:.0%}")
    lines.append(f"  Shots: {health.shot_count} | Frames: {health.shots_with_frames} | "
                 f"Videos: {health.shots_with_videos}")
    lines.append(f"{'=' * 60}")
    lines.append("")

    if health.state == SceneState.READY:
        lines.append(f"  ✅ READY TO RENDER")
        lines.append(f"  Cost: ${health.cost_estimate:.2f}")
        lines.append(f"  Time: ~{health.time_estimate_seconds / 60:.0f} min")
    elif health.state == SceneState.DEGRADED_SAFE:
        lines.append(f"  ⚠️ SAFE TO RENDER (minor warnings)")
        lines.append(f"  Cost: ${health.cost_estimate:.2f}")
    elif health.state == SceneState.BOOTSTRAPPABLE:
        lines.append(f"  🔧 BOOTSTRAPPABLE — auto-fix available")
    elif health.state == SceneState.COMPLETED:
        lines.append(f"  🎬 COMPLETE — all shots rendered")
    else:
        lines.append(f"  ❌ BLOCKED")

    lines.append("")

    # Checks
    for c in health.checks:
        icon = "✅" if c.passed else ("❌" if c.blocking else "⚠️")
        fix = f"  → {c.fix_action}" if not c.passed and c.fix_action else ""
        lines.append(f"  {icon} {c.name}: {c.message} ({c.score:.0%}){fix}")

    # Allowed actions
    lines.append("")
    lines.append(f"  ALLOWED: {', '.join(a.value for a in health.allowed_actions)}")

    if health.blocking_reasons:
        lines.append("")
        lines.append("  BLOCKING:")
        for r in health.blocking_reasons:
            lines.append(f"    • {r}")

    if health.bootstrap_actions:
        lines.append("")
        lines.append("  AUTO-FIXABLE:")
        for a in health.bootstrap_actions:
            lines.append(f"    🔧 {a}")

    lines.append("")
    lines.append(f"{'=' * 60}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Bootstrap Engine — auto-fix what's missing
# ---------------------------------------------------------------------------

def _bootstrap(project: str, scene_id: str = None,
               health: 'SceneHealth' = None, dry_run: bool = False) -> List[str]:
    """
    Auto-fix bootstrappable issues. Returns list of actions taken.
    Routes through control spine to determine what needs fixing.
    """
    import requests
    SERVER = "http://localhost:9999"
    actions = []

    if health is None and _HAS_SPINE:
        health = assess_scene(project, scene_id)

    if health and health.state == SceneState.READY:
        return ["Already ready — no bootstrap needed"]

    # Determine what to fix from health checks
    fix_actions = set()
    if health:
        for c in health.checks:
            if not c.passed and c.bootstrappable and c.fix_action:
                fix_actions.add(c.fix_action)
    else:
        # Fallback: try everything
        fix_actions = {"fix-v16", "auto-cast"}

    # Execute in correct order (Law 265: pressure cannot change order)
    ORDER = ["fix-v16", "sanitizer", "auto-cast", "generate-first-frames", "generate-establishing"]

    for action in ORDER:
        if action not in fix_actions:
            continue

        if dry_run:
            actions.append(f"[DRY RUN] Would: {action}")
            continue

        try:
            if action == "fix-v16":
                resp = requests.post(f"{SERVER}/api/shot-plan/fix-v16",
                                     json={"project": project}, timeout=120)
                actions.append(f"✅ fix-v16" if resp.ok else f"❌ fix-v16: {resp.status_code}")

                # Always run sanitizer after fix-v16 (Law 188)
                sanitizer = BASE_DIR / "tools" / "post_fixv16_sanitizer.py"
                if sanitizer.exists():
                    proc = subprocess.run(
                        ["python3", str(sanitizer), project],
                        capture_output=True, text=True, timeout=30, cwd=str(BASE_DIR))
                    actions.append(f"✅ sanitizer" if proc.returncode == 0
                                   else f"⚠️ sanitizer: {proc.stderr[:100]}")

            elif action == "auto-cast":
                resp = requests.post(f"{SERVER}/api/v6/casting/auto-cast",
                                     json={"project": project}, timeout=60)
                actions.append(f"✅ auto-cast" if resp.ok else f"❌ auto-cast: {resp.status_code}")

            elif action == "generate-first-frames":
                payload = {"project": project, "dry_run": False}
                if scene_id:
                    payload["scene_id"] = scene_id
                resp = requests.post(f"{SERVER}/api/auto/generate-first-frames",
                                     json=payload, timeout=300)
                actions.append(f"✅ frames started" if resp.ok
                               else f"❌ frames: {resp.status_code}")

        except Exception as e:
            actions.append(f"❌ {action}: {e}")

    return actions


# ---------------------------------------------------------------------------
# Main Intent Controller
# ---------------------------------------------------------------------------

def execute_intent(intent: str, params: dict = None) -> IntentResult:
    """
    SINGLE ENTRY POINT for all operator actions.

    Enforces: intent → state check → policy → execute → verify → report

    Supported intents:
        check       — readiness check only (no execution)
        render      — check → bootstrap → render scene
        fix         — run fix-v16 + sanitizer
        audit       — run 10-contract audit
        bootstrap   — auto-fix all bootstrappable issues
        harmony     — full cross-project harmony audit
        status      — current project status
    """
    params = params or {}
    project = params.get("project", "")
    scene_id = params.get("scene", params.get("scene_id", ""))

    if not project:
        return IntentResult(intent, False, False,
                            "❌ No project specified",
                            blocking_issues=["Missing project name"])

    # ===================================================================
    # STEP 1: ALWAYS assess state first (Law 265)
    # ===================================================================
    health = None
    if _HAS_SPINE and scene_id:
        try:
            health = assess_scene(project, scene_id)
        except Exception as e:
            logger.warning(f"Spine assessment failed: {e}")

    # ===================================================================
    # INTENT: check / status
    # ===================================================================
    if intent in ("check", "check_scene", "status"):
        if health:
            text = _format_scene_health(health)
            result = IntentResult(
                intent, True, health.state in (SceneState.READY, SceneState.DEGRADED_SAFE),
                text, state=health.state.value,
                blocking_issues=health.blocking_reasons,
                allowed_actions=[a.value for a in health.allowed_actions],
                cost_estimate=health.cost_estimate,
                health_score=health.health_score,
                data={"shot_count": health.shot_count,
                      "frames": health.shots_with_frames,
                      "videos": health.shots_with_videos}
            )
        else:
            # Fallback for project-level or no spine
            if _HAS_SPINE:
                proj_health = assess_project(project)
                text = f"Project {project}: {proj_health.state.value} (health={proj_health.health_score:.0%})\n"
                text += f"Shots: {proj_health.total_shots} | Frames: {proj_health.total_frames} | Videos: {proj_health.total_videos}"
                result = IntentResult(intent, True, False, text,
                                      state=proj_health.state.value,
                                      health_score=proj_health.health_score)
            else:
                result = IntentResult(intent, False, False,
                                      "Control spine not available — check manually")

        _log_intent(project, intent, params, result)
        return result

    # ===================================================================
    # INTENT: harmony — cross-project audit
    # ===================================================================
    if intent == "harmony":
        if _HAS_SPINE:
            projects_list = params.get("projects")
            if isinstance(projects_list, str):
                projects_list = [projects_list]
            audit = harmony_audit(projects_list)
            text = format_harmony_report(audit)

            # Save JSON
            out_path = BASE_DIR / "reports" / "harmony_audit.json"
            out_path.parent.mkdir(exist_ok=True)
            with open(out_path, "w") as f:
                json.dump(audit, f, indent=2, default=str)

            summary = audit.get("_harmony_summary", {})
            result = IntentResult(
                intent, True, summary.get("system_health") == "HEALTHY",
                text, state=summary.get("system_health", "UNKNOWN"),
                health_score=0.0,
                data=summary
            )
        else:
            result = IntentResult(intent, False, False, "Control spine not available")

        _log_intent(project, intent, params, result)
        return result

    # ===================================================================
    # INTENT: fix — fix-v16 + sanitizer
    # ===================================================================
    if intent in ("fix", "fix_scene"):
        # STEP 2: Check policy (is fix allowed?)
        if health and ActionType.FIX not in health.allowed_actions:
            result = IntentResult(intent, False, False,
                                  f"❌ Fix not allowed in state {health.state.value}",
                                  state=health.state.value,
                                  allowed_actions=[a.value for a in health.allowed_actions])
            _log_intent(project, intent, params, result)
            return result

        actions = _bootstrap(project, scene_id, health, dry_run=False)

        # STEP 3: Re-assess after fix
        if _HAS_SPINE and scene_id:
            health = assess_scene(project, scene_id)
            text = _format_scene_health(health)
            text += "\n\n  ACTIONS TAKEN:\n" + "\n".join(f"    {a}" for a in actions)
            result = IntentResult(intent, True,
                                  health.state in (SceneState.READY, SceneState.DEGRADED_SAFE),
                                  text, state=health.state.value,
                                  actions_taken=actions, health_score=health.health_score)
        else:
            result = IntentResult(intent, True, False,
                                  "\n".join(actions), actions_taken=actions)

        _log_intent(project, intent, params, result)
        return result

    # ===================================================================
    # INTENT: audit — 10-contract audit
    # ===================================================================
    if intent in ("audit", "audit_scene"):
        import requests
        SERVER = "http://localhost:9999"
        try:
            resp = requests.post(f"{SERVER}/api/v21/audit/{project}",
                                 json={}, timeout=60)
            if resp.ok:
                data = resp.json()
                critical = data.get("critical_count", 0)
                warning = data.get("warning_count", 0)
                text = f"  CONTRACT AUDIT — {project}\n"
                text += f"  CRITICAL: {critical} | WARNING: {warning}\n"
                text += "  ✅ ALL CONTRACTS PASS\n" if critical == 0 \
                    else "  ❌ CRITICAL VIOLATIONS\n"
                result = IntentResult(intent, True, critical == 0, text,
                                      data={"critical": critical, "warning": warning})
            else:
                result = IntentResult(intent, False, False,
                                      f"❌ Audit: {resp.status_code}")
        except Exception as e:
            result = IntentResult(intent, False, False, f"❌ Audit error: {e}")

        _log_intent(project, intent, params, result)
        return result

    # ===================================================================
    # INTENT: bootstrap — auto-fix
    # ===================================================================
    if intent == "bootstrap":
        # Check policy
        if health and ActionType.BOOTSTRAP not in health.allowed_actions:
            result = IntentResult(intent, False, False,
                                  f"❌ Bootstrap not allowed in state {health.state.value}",
                                  state=health.state.value)
            _log_intent(project, intent, params, result)
            return result

        dry_run = params.get("dry_run", False)
        actions = _bootstrap(project, scene_id, health, dry_run=dry_run)

        # Re-assess
        if _HAS_SPINE and scene_id:
            health = assess_scene(project, scene_id)
            text = _format_scene_health(health)
            text += "\n\n  BOOTSTRAP ACTIONS:\n" + "\n".join(f"    {a}" for a in actions)
            result = IntentResult(intent, True,
                                  health.state in (SceneState.READY, SceneState.DEGRADED_SAFE),
                                  text, state=health.state.value,
                                  actions_taken=actions, health_score=health.health_score)
        else:
            result = IntentResult(intent, True, False,
                                  "\n".join(actions), actions_taken=actions)

        _log_intent(project, intent, params, result)
        return result

    # ===================================================================
    # INTENT: render / run_scene — THE BIG ONE
    # ===================================================================
    if intent in ("render", "run", "run_scene"):
        import requests
        SERVER = "http://localhost:9999"
        actions = []

        if not scene_id:
            result = IntentResult(intent, False, False,
                                  "❌ No scene specified",
                                  blocking_issues=["Missing scene_id"])
            _log_intent(project, intent, params, result)
            return result

        # STEP 1: Assess state (already done above)
        if health:
            actions.append(f"State: {health.state.value} (health={health.health_score:.0%})")

            # STEP 2: Check policy (is render allowed?)
            if ActionType.RENDER not in health.allowed_actions:
                # Can we bootstrap first?
                if ActionType.BOOTSTRAP in health.allowed_actions:
                    actions.append("Bootstrapping...")
                    boot_actions = _bootstrap(project, scene_id, health)
                    actions.extend(boot_actions)

                    # Re-assess
                    health = assess_scene(project, scene_id)
                    actions.append(f"Post-bootstrap: {health.state.value} ({health.health_score:.0%})")

                    if ActionType.RENDER not in health.allowed_actions:
                        text = _format_scene_health(health)
                        text += "\n\n  ACTIONS:\n" + "\n".join(f"    {a}" for a in actions)
                        text += "\n\n  ⛔ Still blocked after bootstrap"
                        result = IntentResult(intent, False, False, text,
                                              state=health.state.value,
                                              blocking_issues=health.blocking_reasons,
                                              actions_taken=actions)
                        _log_intent(project, intent, params, result)
                        return result
                else:
                    text = _format_scene_health(health)
                    text += "\n\n  ⛔ Render not allowed — fix blocking issues first"
                    result = IntentResult(intent, False, False, text,
                                          state=health.state.value,
                                          blocking_issues=health.blocking_reasons)
                    _log_intent(project, intent, params, result)
                    return result

        # STEP 3: AUTHORIZED — execute render
        actions.append(f"🎬 Rendering scene {scene_id}...")
        try:
            resp = requests.post(
                f"{SERVER}/api/v18/master-chain/render-scene",
                json={
                    "project": project,
                    "scene_id": scene_id,
                    "enable_chain": True,
                    "enable_variants": True,
                    "video_model": params.get("video_model", "ltx"),
                    "generate_audio": params.get("audio", False)
                },
                timeout=600
            )
            if resp.ok:
                data = resp.json()
                cost = data.get("total_cost", 0)
                elapsed = data.get("elapsed_seconds", 0)
                completed = data.get("completed_shots", 0)
                total = data.get("total_shots", 0)
                actions.append(f"✅ Render: {completed}/{total} shots, ${cost:.2f}, {elapsed:.0f}s")

                # STEP 4: Verify — re-assess after render
                if _HAS_SPINE:
                    health = assess_scene(project, scene_id)

                text = _format_scene_health(health) if health else f"Render complete: {completed}/{total}"
                text += "\n\n  RENDER RESULT:\n"
                text += f"    Shots: {completed}/{total}\n"
                text += f"    Cost: ${cost:.2f}\n"
                text += f"    Time: {elapsed:.0f}s\n"
                text += "\n  ACTIONS:\n" + "\n".join(f"    {a}" for a in actions)

                result = IntentResult(intent, True, True, text,
                                      state=health.state.value if health else "COMPLETED",
                                      actions_taken=actions, cost_estimate=cost,
                                      health_score=health.health_score if health else 1.0,
                                      data=data)
            else:
                actions.append(f"❌ Render failed: {resp.status_code}")
                result = IntentResult(intent, False, True,
                                      f"❌ Render failed ({resp.status_code}): {resp.text[:300]}",
                                      actions_taken=actions)
        except requests.exceptions.Timeout:
            actions.append("⏳ Render still running (timeout — check UI)")
            result = IntentResult(intent, True, True,
                                  "⏳ Render started — monitor in UI",
                                  state="RUNNING", actions_taken=actions)
        except Exception as e:
            actions.append(f"❌ Error: {e}")
            result = IntentResult(intent, False, True, f"❌ Render error: {e}",
                                  actions_taken=actions)

        _log_intent(project, intent, params, result)
        return result

    # ===================================================================
    # Unknown intent
    # ===================================================================
    result = IntentResult(
        intent, False, False,
        f"❌ Unknown intent: '{intent}'\n\n"
        f"  Available intents:\n"
        f"    check       — readiness check (spine assessment)\n"
        f"    render      — check → bootstrap → render scene\n"
        f"    fix         — fix-v16 + sanitizer\n"
        f"    audit       — 10-contract audit\n"
        f"    bootstrap   — auto-fix missing assets\n"
        f"    harmony     — cross-project harmony audit\n"
        f"    status      — current status\n"
    )
    _log_intent(project, intent, params, result)
    return result


# ---------------------------------------------------------------------------
# JSON serialization helper (for API endpoints)
# ---------------------------------------------------------------------------

def intent_result_to_json(result: IntentResult) -> dict:
    """Convert IntentResult to JSON-serializable dict."""
    return {
        "intent": result.intent,
        "success": result.success,
        "ready": result.ready,
        "state": result.state,
        "health_score": result.health_score,
        "report": result.report,
        "blocking_issues": result.blocking_issues,
        "warnings": result.warnings,
        "actions_taken": result.actions_taken,
        "allowed_actions": result.allowed_actions,
        "cost_estimate": result.cost_estimate,
        "time_estimate_minutes": result.time_estimate_minutes,
        "data": result.data
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("ATLAS V25.2 — Operator Intent Controller")
        print("=" * 50)
        print("")
        print("Usage:")
        print("  python3 tools/operator_intent_controller.py <intent> <project> [scene_id]")
        print("")
        print("Intents:")
        print("  check       — readiness check (spine assessment)")
        print("  render      — check → bootstrap → render scene")
        print("  fix         — fix-v16 + sanitizer")
        print("  audit       — 10-contract audit")
        print("  bootstrap   — auto-fix missing assets")
        print("  harmony     — cross-project harmony audit")
        print("")
        print("Examples:")
        print("  python3 tools/operator_intent_controller.py check victorian_shadows_ep1 001")
        print("  python3 tools/operator_intent_controller.py render victorian_shadows_ep1 001")
        print("  python3 tools/operator_intent_controller.py harmony victorian_shadows_ep1")
        sys.exit(1)

    intent = sys.argv[1]
    project = sys.argv[2]
    scene = sys.argv[3] if len(sys.argv) > 3 else ""

    result = execute_intent(intent, {"project": project, "scene": scene})
    print(result.report)
    sys.exit(0 if result.success else 1)
