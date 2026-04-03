"""
ATLAS V25.2 — CONTROL SPINE
============================
Centralized authority, decentralized execution.

This is the ONE layer that decides:
    1. CURRENT STATE — what is true right now
    2. ALLOWED NEXT ACTION — what the system may do
    3. OPERATOR-VISIBLE TRUTH — what the operator sees

No component may independently authorize production action.
Only the control spine can authorize: render, bootstrap, rerun, merge, report success.
Everything else can only: recommend, report, execute assigned work.

Architecture:
    operator_intent_controller.py  — WHAT is being asked (intent)
    atlas_control_spine.py         — IS IT ALLOWED (state + policy + truth)
    worker agents                  — DO IT (execution)
    UI readiness panel             — SEE IT (truth surface)

State Machine:
    UNKNOWN → BLOCKED → BOOTSTRAPPABLE → DEGRADED_SAFE → READY → RUNNING → COMPLETED
                                                                      ↓
                                                              FAILED_RECOVERABLE
                                                                      ↓
                                                              FAILED_HARD

Laws:
    261. Control spine is SINGLE AUTHORITY — no bypass routes — NEVER let endpoints self-authorize
    262. State transitions are LOGGED — every state change to append-only ledger
    263. Policy engine is DETERMINISTIC — same state always produces same allowed actions
    264. Truth surface reflects REAL state — NEVER cache stale state in UI
    265. Pressure cannot change operation order — NEVER skip diagnosis under urgency
"""

import json
import os
import time
import hashlib
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Set, Tuple, Any
from pathlib import Path
from datetime import datetime
from enum import Enum

# ---------------------------------------------------------------------------
# State Model — canonical state enums (Hour 1)
# ---------------------------------------------------------------------------

class SceneState(str, Enum):
    """Canonical scene states. One state per scene at any time."""
    UNKNOWN = "UNKNOWN"                     # Never assessed
    BLOCKED = "BLOCKED"                     # Has blocking issues, cannot render
    BOOTSTRAPPABLE = "BOOTSTRAPPABLE"       # Has issues, all auto-fixable
    DEGRADED_SAFE = "DEGRADED_SAFE"         # Minor warnings, can render
    READY = "READY"                         # All checks pass, authorized to render
    RUNNING = "RUNNING"                     # Generation in progress
    COMPLETED = "COMPLETED"                 # All shots rendered
    FAILED_RECOVERABLE = "FAILED_RECOVERABLE"  # Some shots failed, can retry
    FAILED_HARD = "FAILED_HARD"             # Fatal error, needs manual intervention


class ActionType(str, Enum):
    """What the operator can do."""
    RENDER = "render"                # Full scene render
    BOOTSTRAP = "bootstrap"          # Auto-fix missing assets
    FIX = "fix"                      # Run fix-v16 + sanitizer
    AUDIT = "audit"                  # Run 10-contract audit
    RETRY_FAILED = "retry_failed"    # Retry failed shots
    STITCH = "stitch"                # Stitch completed scene
    DIAGNOSE = "diagnose"            # Read status only
    NONE = "none"                    # No action allowed


@dataclass
class StateTransition:
    """Record of a state change."""
    from_state: str
    to_state: str
    reason: str
    timestamp: str
    action: str = ""


@dataclass
class CheckResult:
    """Single check with pass/fail, severity, and fix hint."""
    name: str
    passed: bool
    blocking: bool
    message: str
    score: float = 1.0              # 0-1 health score
    bootstrappable: bool = False
    fix_action: str = ""
    details: Dict = field(default_factory=dict)


@dataclass
class SceneHealth:
    """Full health assessment for one scene."""
    project: str
    scene_id: str
    state: SceneState
    checks: List[CheckResult]
    shot_count: int = 0
    shots_with_frames: int = 0
    shots_with_videos: int = 0
    shots_with_enrichment: int = 0
    coverage_roles: Dict[str, int] = field(default_factory=dict)
    allowed_actions: List[ActionType] = field(default_factory=list)
    blocking_reasons: List[str] = field(default_factory=list)
    bootstrap_actions: List[str] = field(default_factory=list)
    cost_estimate: float = 0.0
    time_estimate_seconds: float = 0.0
    health_score: float = 0.0       # 0-1 aggregate


@dataclass
class ProjectHealth:
    """Full health assessment for entire project."""
    project: str
    scenes: Dict[str, SceneHealth]
    total_shots: int = 0
    total_frames: int = 0
    total_videos: int = 0
    cast_count: int = 0
    missing_cast: List[str] = field(default_factory=list)
    fal_ready: bool = False
    state: SceneState = SceneState.UNKNOWN
    health_score: float = 0.0
    cost_estimate: float = 0.0


# ---------------------------------------------------------------------------
# Base paths
# ---------------------------------------------------------------------------

BASE_DIR = Path(os.environ.get("ATLAS_BASE_DIR",
    Path(__file__).resolve().parent.parent))
PIPELINE_DIR = BASE_DIR / "pipeline_outputs"


# ---------------------------------------------------------------------------
# Data loaders (cached per assessment)
# ---------------------------------------------------------------------------

def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _get_shots(plan, scene_id: str = None) -> list:
    # Bare-list guard: shot_plan.json may be a bare list
    if isinstance(plan, list):
        shots = plan
    else:
        shots = plan.get("shots", plan.get("shot_plan", []))
    if scene_id:
        return [s for s in shots if s.get("scene_id") == scene_id]
    return shots


# ---------------------------------------------------------------------------
# Readiness Checks — each returns a CheckResult
# ---------------------------------------------------------------------------

def _check_enrichment(shots: list) -> CheckResult:
    """Check if shots have V25 enrichment markers."""
    total = len(shots)
    if total == 0:
        return CheckResult("enrichment", False, True, "No shots", 0.0)

    enriched = 0
    for s in shots:
        nano = (s.get("nano_prompt") or s.get("nano_prompt_final") or "").lower()
        ltx = (s.get("ltx_motion_prompt") or "").lower()
        has_markers = any(m in ltx for m in ["performs", "speaks", "reacts"])
        has_comp = "composition:" in nano
        if has_markers or has_comp:
            enriched += 1

    ratio = enriched / total
    passed = ratio > 0.7
    return CheckResult(
        "enrichment", passed, not passed,
        f"{enriched}/{total} shots enriched ({ratio:.0%})",
        ratio, bootstrappable=not passed, fix_action="fix-v16"
    )


def _check_generic_contamination(shots: list) -> CheckResult:
    """Check for generic timing virus and other contaminants."""
    GENERIC_PATTERNS = [
        "0-2s static hold", "0-3s static hold",
        "static, micro-expression", "natural movement begins",
        "experiences the moment", "present and engaged",
        "subtle drift", "gentle ambient"
    ]
    CONTAMINANT_PATTERNS = [
        "ARRI Alexa", "RED DSMC", "Sony Venice", "Panavision",
        "Kodak Vision3", "Fuji Eterna", "35mm film stock",
        "Isabella Moretti", "Sophia Chen", "Marcus Sterling"
    ]

    total = len(shots)
    generic_count = 0
    contaminant_count = 0

    for s in shots:
        ltx = (s.get("ltx_motion_prompt") or "").lower()
        nano = (s.get("nano_prompt") or s.get("nano_prompt_final") or "")

        for p in GENERIC_PATTERNS:
            if p.lower() in ltx:
                generic_count += 1
                break

        for p in CONTAMINANT_PATTERNS:
            if p.lower() in nano.lower() or p.lower() in ltx:
                contaminant_count += 1
                break

    clean = total - generic_count - contaminant_count
    ratio = clean / total if total else 0
    passed = generic_count == 0 and contaminant_count == 0

    return CheckResult(
        "contamination", passed, generic_count > 0,
        f"{generic_count} generic, {contaminant_count} contaminant, {clean}/{total} clean",
        ratio, bootstrappable=True, fix_action="sanitizer"
    )


def _check_frames(shots: list, project: str) -> CheckResult:
    """Check first frame coverage."""
    frames_dir = PIPELINE_DIR / project / "first_frames"
    total = len(shots)
    found = 0

    for s in shots:
        sid = s.get("shot_id", "")
        has = False
        if frames_dir.exists():
            for ext in [".jpg", ".png", ".jpeg"]:
                if (frames_dir / f"{sid}{ext}").exists():
                    has = True
                    break
        if s.get("first_frame_path") and Path(str(s["first_frame_path"])).exists():
            has = True
        if has:
            found += 1

    ratio = found / total if total else 0
    return CheckResult(
        "first_frames", found == total, found == 0,
        f"{found}/{total} frames",
        ratio, bootstrappable=True, fix_action="generate-first-frames"
    )


def _check_videos(shots: list, project: str) -> CheckResult:
    """Check video coverage."""
    videos_dir = PIPELINE_DIR / project / "videos"
    total = len(shots)
    found = 0

    for s in shots:
        sid = s.get("shot_id", "")
        if videos_dir.exists():
            if (videos_dir / f"{sid}.mp4").exists():
                found += 1

    ratio = found / total if total else 0
    return CheckResult(
        "videos", found == total, False,
        f"{found}/{total} videos",
        ratio
    )


def _check_coverage_grammar(shots: list) -> CheckResult:
    """Check A/B/C coverage role distribution."""
    roles = {}
    for s in shots:
        role = s.get("coverage_role", "")
        key = role.split("_")[0] if "_" in role else (role or "NONE")
        roles[key] = roles.get(key, 0) + 1

    has_a = roles.get("A", 0) > 0
    has_variety = len([r for r in roles if r not in ("NONE", "")]) >= 2

    passed = has_a or len(shots) <= 2
    return CheckResult(
        "coverage_grammar", passed, not passed and len(shots) > 2,
        f"Roles: {dict(roles)}",
        1.0 if passed else 0.3,
        bootstrappable=not passed, fix_action="fix-v16",
        details=roles
    )


def _check_dialogue_markers(shots: list) -> CheckResult:
    """Check that dialogue shots have speaking markers in LTX."""
    dialogue_shots = [s for s in shots if s.get("dialogue_text") or s.get("dialogue")]
    if not dialogue_shots:
        return CheckResult("dialogue_markers", True, False, "No dialogue shots", 1.0)

    marked = 0
    for s in dialogue_shots:
        ltx = (s.get("ltx_motion_prompt") or "").lower()
        if "speaks:" in ltx or "speaking" in ltx:
            marked += 1

    ratio = marked / len(dialogue_shots) if dialogue_shots else 1
    passed = ratio > 0.8
    return CheckResult(
        "dialogue_markers", passed, not passed,
        f"{marked}/{len(dialogue_shots)} dialogue shots have speaking markers",
        ratio, bootstrappable=True, fix_action="fix-v16"
    )


def _check_performance_markers(shots: list) -> CheckResult:
    """Check that character shots have performance markers."""
    char_shots = [s for s in shots if s.get("characters")]
    if not char_shots:
        return CheckResult("performance_markers", True, False, "No character shots", 1.0)

    marked = 0
    for s in char_shots:
        ltx = (s.get("ltx_motion_prompt") or "").lower()
        if any(m in ltx for m in ["performs:", "speaks:", "reacts:"]):
            marked += 1

    ratio = marked / len(char_shots) if char_shots else 1
    passed = ratio > 0.7
    return CheckResult(
        "performance_markers", passed, False,
        f"{marked}/{len(char_shots)} character shots have markers",
        ratio, bootstrappable=True, fix_action="fix-v16"
    )


def _check_landscape_safety(shots: list) -> CheckResult:
    """Check no human language in no-character shots."""
    HUMAN_PATTERNS = ["blink", "brows", "breath", "chest", "lip", "gesture",
                      "micro-expression", "bio-real", "ACTING", "posture"]
    no_char_shots = [s for s in shots if not s.get("characters")]
    violations = 0

    for s in no_char_shots:
        ltx = (s.get("ltx_motion_prompt") or "").lower()
        if any(p.lower() in ltx for p in HUMAN_PATTERNS):
            violations += 1

    passed = violations == 0
    total = len(no_char_shots)
    return CheckResult(
        "landscape_safety", passed, violations > 0,
        f"{violations} violations in {total} no-character shots",
        1.0 if passed else 0.0
    )


def _check_cast(shots: list, cast_map: dict) -> CheckResult:
    """Check all characters are in cast map."""
    all_chars = set()
    for s in shots:
        for c in (s.get("characters") or []):
            all_chars.add(c)

    cast_names = set(cast_map.keys()) if cast_map else set()
    # Filter out alias entries
    cast_names = {k for k, v in cast_map.items()
                  if not (isinstance(v, dict) and v.get("_is_alias_of"))} if cast_map else set()
    missing = all_chars - cast_names

    passed = len(missing) == 0
    return CheckResult(
        "cast_map", passed, False,
        f"{len(all_chars)} chars, {len(missing)} missing: {', '.join(sorted(missing)[:5])}",
        1.0 if passed else 0.5,
        bootstrappable=len(missing) > 0, fix_action="auto-cast",
        details={"missing": sorted(missing)}
    )


def _check_fal() -> CheckResult:
    """Check FAL client availability."""
    try:
        import fal_client
        key = os.environ.get("FAL_KEY") or os.environ.get("FAL_KEY_1")
        if key:
            return CheckResult("fal_client", True, False, "FAL ready", 1.0)
        return CheckResult("fal_client", False, True, "FAL_KEY not set", 0.0)
    except ImportError:
        return CheckResult("fal_client", False, True, "fal_client not installed", 0.0)


# ---------------------------------------------------------------------------
# Scene Health Assessment
# ---------------------------------------------------------------------------

def assess_scene(project: str, scene_id: str,
                 plan: dict = None, cast_map: dict = None) -> SceneHealth:
    """
    Full health assessment for one scene.
    Returns state, allowed actions, blocking reasons.
    """
    if plan is None:
        plan = _load_json(PIPELINE_DIR / project / "shot_plan.json")
    if cast_map is None:
        cast_map = _load_json(PIPELINE_DIR / project / "cast_map.json")

    shots = _get_shots(plan, scene_id)

    if not shots:
        return SceneHealth(
            project, scene_id, SceneState.UNKNOWN, [],
            allowed_actions=[ActionType.DIAGNOSE],
            blocking_reasons=[f"No shots for scene {scene_id}"]
        )

    # Run all checks
    checks = [
        _check_enrichment(shots),
        _check_generic_contamination(shots),
        _check_frames(shots, project),
        _check_videos(shots, project),
        _check_coverage_grammar(shots),
        _check_dialogue_markers(shots),
        _check_performance_markers(shots),
        _check_landscape_safety(shots),
        _check_cast(shots, cast_map),
        _check_fal(),
    ]

    # Count assets
    frames_dir = PIPELINE_DIR / project / "first_frames"
    videos_dir = PIPELINE_DIR / project / "videos"
    frame_count = sum(1 for s in shots if any(
        (frames_dir / f"{s.get('shot_id','')}{ext}").exists()
        for ext in [".jpg", ".png", ".jpeg"]
    )) if frames_dir.exists() else 0
    video_count = sum(1 for s in shots if
        (videos_dir / f"{s.get('shot_id','')}.mp4").exists()
    ) if videos_dir.exists() else 0

    # Coverage roles
    roles = {}
    for s in shots:
        r = s.get("coverage_role", "NONE")
        roles[r] = roles.get(r, 0) + 1

    enriched = sum(1 for s in shots if "composition:" in
                   (s.get("nano_prompt") or s.get("nano_prompt_final") or "").lower())

    # Classify state
    blocking = [c for c in checks if not c.passed and c.blocking]
    bootstrappable = [c for c in checks if not c.passed and c.bootstrappable]
    warnings = [c for c in checks if not c.passed and not c.blocking]

    blocking_reasons = [f"{c.name}: {c.message}" for c in blocking]
    bootstrap_actions = [c.fix_action for c in bootstrappable if c.fix_action]

    # Determine state
    if blocking:
        if all(c.bootstrappable for c in blocking):
            state = SceneState.BOOTSTRAPPABLE
        else:
            state = SceneState.BLOCKED
    elif video_count == len(shots):
        state = SceneState.COMPLETED
    elif video_count > 0 and video_count < len(shots):
        state = SceneState.FAILED_RECOVERABLE
    elif warnings:
        state = SceneState.DEGRADED_SAFE
    else:
        state = SceneState.READY

    # Determine allowed actions based on state (POLICY)
    allowed = _compute_allowed_actions(state, checks)

    # Health score: weighted average of check scores
    weights = {
        "enrichment": 0.20, "contamination": 0.15, "first_frames": 0.15,
        "coverage_grammar": 0.10, "dialogue_markers": 0.10,
        "performance_markers": 0.10, "landscape_safety": 0.05,
        "cast_map": 0.05, "fal_client": 0.05, "videos": 0.05
    }
    health = sum(c.score * weights.get(c.name, 0.05) for c in checks)

    cost = len(shots) * 0.45
    time_s = len(shots) * 8

    return SceneHealth(
        project=project,
        scene_id=scene_id,
        state=state,
        checks=checks,
        shot_count=len(shots),
        shots_with_frames=frame_count,
        shots_with_videos=video_count,
        shots_with_enrichment=enriched,
        coverage_roles=roles,
        allowed_actions=allowed,
        blocking_reasons=blocking_reasons,
        bootstrap_actions=list(set(bootstrap_actions)),
        cost_estimate=round(cost, 2),
        time_estimate_seconds=time_s,
        health_score=round(health, 3)
    )


def _compute_allowed_actions(state: SceneState, checks: list) -> List[ActionType]:
    """Policy engine: what actions are allowed from this state."""
    actions = [ActionType.DIAGNOSE]  # Always allowed

    if state == SceneState.READY:
        actions.extend([ActionType.RENDER, ActionType.AUDIT])
    elif state == SceneState.DEGRADED_SAFE:
        actions.extend([ActionType.RENDER, ActionType.FIX, ActionType.AUDIT])
    elif state == SceneState.BOOTSTRAPPABLE:
        actions.extend([ActionType.BOOTSTRAP, ActionType.FIX, ActionType.AUDIT])
    elif state == SceneState.BLOCKED:
        actions.extend([ActionType.FIX, ActionType.AUDIT])
    elif state == SceneState.COMPLETED:
        actions.extend([ActionType.STITCH, ActionType.AUDIT])
    elif state == SceneState.FAILED_RECOVERABLE:
        actions.extend([ActionType.RETRY_FAILED, ActionType.RENDER, ActionType.AUDIT])
    elif state == SceneState.FAILED_HARD:
        actions.extend([ActionType.FIX])

    return actions


# ---------------------------------------------------------------------------
# Project Health Assessment
# ---------------------------------------------------------------------------

def assess_project(project: str) -> ProjectHealth:
    """Assess entire project health."""
    plan = _load_json(PIPELINE_DIR / project / "shot_plan.json")
    cast_map = _load_json(PIPELINE_DIR / project / "cast_map.json")

    all_shots = _get_shots(plan)
    scenes = sorted(set(s.get("scene_id", "") for s in all_shots))

    scene_health = {}
    total_frames = 0
    total_videos = 0
    total_cost = 0

    for sid in scenes:
        health = assess_scene(project, sid, plan, cast_map)
        scene_health[sid] = health
        total_frames += health.shots_with_frames
        total_videos += health.shots_with_videos
        total_cost += health.cost_estimate

    # Project-level state = worst scene state
    states_priority = [
        SceneState.BLOCKED, SceneState.BOOTSTRAPPABLE, SceneState.FAILED_HARD,
        SceneState.FAILED_RECOVERABLE, SceneState.DEGRADED_SAFE,
        SceneState.RUNNING, SceneState.READY, SceneState.COMPLETED
    ]

    project_state = SceneState.COMPLETED
    for sp in states_priority:
        if any(sh.state == sp for sh in scene_health.values()):
            project_state = sp
            break

    # Missing cast
    all_chars = set()
    for s in all_shots:
        for c in (s.get("characters") or []):
            all_chars.add(c)
    cast_names = {k for k, v in cast_map.items()
                  if not (isinstance(v, dict) and v.get("_is_alias_of"))} if cast_map else set()
    missing = sorted(all_chars - cast_names)

    fal_check = _check_fal()

    avg_health = (sum(sh.health_score for sh in scene_health.values()) /
                  len(scene_health)) if scene_health else 0

    return ProjectHealth(
        project=project,
        scenes=scene_health,
        total_shots=len(all_shots),
        total_frames=total_frames,
        total_videos=total_videos,
        cast_count=len(cast_names),
        missing_cast=missing,
        fal_ready=fal_check.passed,
        state=project_state,
        health_score=round(avg_health, 3),
        cost_estimate=round(total_cost, 2)
    )


# ---------------------------------------------------------------------------
# Harmony Audit — synthetic + real project insight
# ---------------------------------------------------------------------------

def create_synthetic_project(name: str = "_synthetic_test") -> str:
    """Create a minimal synthetic project for testing the pipeline."""
    project_dir = PIPELINE_DIR / name
    project_dir.mkdir(parents=True, exist_ok=True)

    # Synthetic shot plan with 6 shots across 2 scenes
    plan = {
        "_schema_version": "V25.2",
        "_synthetic": True,
        "scene_manifest": {
            "001": {"location": "INT. TEST ROOM - DAY", "int_ext": "INT",
                    "time_of_day": "DAY", "characters": ["ALICE", "BOB"]},
            "002": {"location": "EXT. TEST GARDEN - NIGHT", "int_ext": "EXT",
                    "time_of_day": "NIGHT", "characters": ["ALICE"]}
        },
        "shots": [
            # Scene 001: 4 shots with proper ABC coverage
            {
                "shot_id": "001_001A", "scene_id": "001", "shot_type": "wide",
                "coverage_role": "A_GEOGRAPHY", "duration": 6, "duration_seconds": 6,
                "characters": ["ALICE", "BOB"],
                "nano_prompt": "composition: Wide master shot of ALICE and BOB in test room. Character action: ALICE turns to face BOB.",
                "ltx_motion_prompt": "character performs: ALICE turns to face BOB, eye contact established. face stable NO morphing. timed motion: 0-6s motivated turn.",
                "dialogue_text": ""
            },
            {
                "shot_id": "001_002B", "scene_id": "001", "shot_type": "medium",
                "coverage_role": "B_ACTION", "duration": 5, "duration_seconds": 5,
                "characters": ["ALICE"],
                "nano_prompt": "composition: Medium shot of ALICE speaking with concern.",
                "ltx_motion_prompt": "character speaks: ALICE delivers dialogue with worried expression. face stable NO morphing.",
                "dialogue_text": "I can't believe what you're saying."
            },
            {
                "shot_id": "001_003C", "scene_id": "001", "shot_type": "close_up",
                "coverage_role": "C_EMOTION", "duration": 4, "duration_seconds": 4,
                "characters": ["BOB"],
                "nano_prompt": "composition: Close up of BOB reacting to ALICE.",
                "ltx_motion_prompt": "character reacts: BOB processes ALICE's words, jaw tightens. face stable NO morphing.",
                "dialogue_text": ""
            },
            {
                "shot_id": "001_004B", "scene_id": "001", "shot_type": "insert",
                "coverage_role": "B_ACTION", "duration": 3, "duration_seconds": 3,
                "characters": [],
                "nano_prompt": "composition: Detail insert of hands gripping table edge.",
                "ltx_motion_prompt": "slow push on hands, white-knuckle grip. NO morphing.",
                "dialogue_text": ""
            },
            # Scene 002: 2 shots
            {
                "shot_id": "002_001A", "scene_id": "002", "shot_type": "wide",
                "coverage_role": "A_GEOGRAPHY", "duration": 5, "duration_seconds": 5,
                "characters": ["ALICE"],
                "nano_prompt": "composition: Wide establishing shot of ALICE in moonlit garden.",
                "ltx_motion_prompt": "character performs: ALICE walks through garden, moonlight casting shadows. face stable NO morphing.",
                "dialogue_text": ""
            },
            {
                "shot_id": "002_002C", "scene_id": "002", "shot_type": "MCU",
                "coverage_role": "C_EMOTION", "duration": 4, "duration_seconds": 4,
                "characters": ["ALICE"],
                "nano_prompt": "composition: MCU of ALICE looking up at stars, tears forming.",
                "ltx_motion_prompt": "character performs: ALICE lifts gaze to night sky, moisture in eyes catches moonlight. face stable NO morphing.",
                "dialogue_text": ""
            }
        ]
    }

    # Synthetic cast map
    cast_map = {
        "ALICE": {
            "actor_name": "Test Actor A",
            "appearance": "woman in her 30s, dark hair, green eyes",
            "headshot_url": "/test/alice.jpg"
        },
        "BOB": {
            "actor_name": "Test Actor B",
            "appearance": "man in his 40s, grey temples, strong jaw",
            "headshot_url": "/test/bob.jpg"
        }
    }

    with open(project_dir / "shot_plan.json", "w") as f:
        json.dump(plan, f, indent=2)
    with open(project_dir / "cast_map.json", "w") as f:
        json.dump(cast_map, f, indent=2)

    return name


def harmony_audit(projects: List[str] = None,
                  include_synthetic: bool = True) -> Dict[str, Any]:
    """
    Run harmony audit across synthetic and real projects.
    Returns insight map showing system health before any FAL spend.

    Blackwell mindset: measure everything, correct before executing.
    """
    results = {}

    # Create and assess synthetic project
    if include_synthetic:
        syn_name = create_synthetic_project()
        syn_health = assess_project(syn_name)
        results["_synthetic_test"] = {
            "type": "synthetic",
            "state": syn_health.state.value,
            "health_score": syn_health.health_score,
            "shots": syn_health.total_shots,
            "scenes": len(syn_health.scenes),
            "scene_details": {
                sid: {
                    "state": sh.state.value,
                    "health": sh.health_score,
                    "shots": sh.shot_count,
                    "checks": {c.name: {"pass": c.passed, "score": c.score, "msg": c.message}
                               for c in sh.checks}
                }
                for sid, sh in syn_health.scenes.items()
            },
            "insight": _generate_insight(syn_health, is_synthetic=True)
        }

    # Assess real projects
    if projects is None:
        projects = [d for d in os.listdir(PIPELINE_DIR)
                    if (PIPELINE_DIR / d / "shot_plan.json").exists()
                    and not d.startswith("_")]

    for proj in projects:
        try:
            health = assess_project(proj)
            results[proj] = {
                "type": "real",
                "state": health.state.value,
                "health_score": health.health_score,
                "shots": health.total_shots,
                "frames": health.total_frames,
                "videos": health.total_videos,
                "cast": health.cast_count,
                "missing_cast": health.missing_cast,
                "fal_ready": health.fal_ready,
                "cost_estimate": health.cost_estimate,
                "scenes": len(health.scenes),
                "scene_details": {
                    sid: {
                        "state": sh.state.value,
                        "health": sh.health_score,
                        "shots": sh.shot_count,
                        "frames": sh.shots_with_frames,
                        "videos": sh.shots_with_videos,
                        "enriched": sh.shots_with_enrichment,
                        "roles": sh.coverage_roles,
                        "allowed": [a.value for a in sh.allowed_actions],
                        "blocking": sh.blocking_reasons,
                        "bootstrap": sh.bootstrap_actions,
                        "cost": sh.cost_estimate,
                        "checks": {c.name: {"pass": c.passed, "score": c.score, "msg": c.message}
                                   for c in sh.checks}
                    }
                    for sid, sh in health.scenes.items()
                },
                "insight": _generate_insight(health, is_synthetic=False)
            }
        except Exception as e:
            results[proj] = {"type": "real", "error": str(e)}

    # Cross-project insight
    results["_harmony_summary"] = _harmony_summary(results)

    return results


def _generate_insight(health: ProjectHealth, is_synthetic: bool) -> Dict[str, Any]:
    """Generate actionable insight from project health."""
    insight = {
        "verdict": "",
        "next_action": "",
        "blockers": [],
        "quick_wins": [],
        "risk_areas": []
    }

    if health.state == SceneState.READY:
        insight["verdict"] = "READY — all scenes can render"
        insight["next_action"] = "render"
    elif health.state == SceneState.DEGRADED_SAFE:
        insight["verdict"] = "SAFE TO RENDER — minor warnings present"
        insight["next_action"] = "render (optional: fix warnings first)"
    elif health.state == SceneState.BOOTSTRAPPABLE:
        insight["verdict"] = "NOT READY — but all issues are auto-fixable"
        insight["next_action"] = "bootstrap"
    elif health.state == SceneState.BLOCKED:
        insight["verdict"] = "BLOCKED — manual fixes required"
        insight["next_action"] = "fix blocking issues"
    elif health.state == SceneState.COMPLETED:
        insight["verdict"] = "COMPLETE — all shots rendered"
        insight["next_action"] = "stitch"
    else:
        insight["verdict"] = f"State: {health.state.value}"
        insight["next_action"] = "diagnose"

    # Identify blockers
    for sid, sh in health.scenes.items():
        for reason in sh.blocking_reasons:
            insight["blockers"].append(f"Scene {sid}: {reason}")

    # Quick wins: scenes closest to ready
    for sid, sh in health.scenes.items():
        if sh.state in (SceneState.DEGRADED_SAFE, SceneState.BOOTSTRAPPABLE):
            insight["quick_wins"].append(
                f"Scene {sid}: {sh.state.value} (health={sh.health_score:.0%}) "
                f"— {', '.join(sh.bootstrap_actions)}"
            )

    # Risk areas: low health scores
    for sid, sh in health.scenes.items():
        if sh.health_score < 0.5:
            low_checks = [c for c in sh.checks if c.score < 0.5]
            insight["risk_areas"].append(
                f"Scene {sid}: health={sh.health_score:.0%} — "
                f"low: {', '.join(c.name for c in low_checks)}"
            )

    return insight


def _harmony_summary(results: dict) -> Dict[str, Any]:
    """Cross-project summary."""
    real_projects = {k: v for k, v in results.items()
                     if not k.startswith("_") and isinstance(v, dict) and v.get("type") == "real"}

    synthetic = results.get("_synthetic_test", {})

    summary = {
        "timestamp": datetime.now().isoformat(),
        "system_health": "UNKNOWN",
        "real_projects": len(real_projects),
        "synthetic_pass": synthetic.get("health_score", 0) > 0.8 if synthetic else None,
        "total_shots": sum(p.get("shots", 0) for p in real_projects.values()),
        "total_frames": sum(p.get("frames", 0) for p in real_projects.values()),
        "total_videos": sum(p.get("videos", 0) for p in real_projects.values()),
        "total_cost_estimate": sum(p.get("cost_estimate", 0) for p in real_projects.values()),
        "ready_scenes": 0,
        "blocked_scenes": 0,
        "bootstrappable_scenes": 0,
        "recommendation": ""
    }

    for proj in real_projects.values():
        for sid, sd in proj.get("scene_details", {}).items():
            state = sd.get("state", "")
            if state == "READY":
                summary["ready_scenes"] += 1
            elif state == "BLOCKED":
                summary["blocked_scenes"] += 1
            elif state == "BOOTSTRAPPABLE":
                summary["bootstrappable_scenes"] += 1

    # System health verdict
    if summary["blocked_scenes"] == 0 and summary["ready_scenes"] > 0:
        summary["system_health"] = "HEALTHY"
        summary["recommendation"] = "System ready for rendering. Start with highest-health scenes."
    elif summary["bootstrappable_scenes"] > 0:
        summary["system_health"] = "RECOVERABLE"
        summary["recommendation"] = "Run bootstrap on bootstrappable scenes, then render."
    else:
        summary["system_health"] = "NEEDS_ATTENTION"
        summary["recommendation"] = "Fix blocking issues before any FAL spend."

    return summary


# ---------------------------------------------------------------------------
# Formatted output — operator-readable truth surface
# ---------------------------------------------------------------------------

def format_harmony_report(audit: Dict[str, Any]) -> str:
    """Format harmony audit as operator-readable report."""
    lines = []
    summary = audit.get("_harmony_summary", {})

    lines.append("=" * 72)
    lines.append("  ATLAS HARMONY AUDIT — SYSTEM HEALTH BEFORE FAL SPEND")
    lines.append(f"  {summary.get('timestamp', '')[:19]}")
    lines.append("=" * 72)
    lines.append("")

    # System status
    health = summary.get("system_health", "UNKNOWN")
    icon = {"HEALTHY": "✅", "RECOVERABLE": "🔧", "NEEDS_ATTENTION": "❌"}.get(health, "❓")
    lines.append(f"  {icon} SYSTEM: {health}")
    lines.append(f"  Shots: {summary.get('total_shots', 0)} | "
                 f"Frames: {summary.get('total_frames', 0)} | "
                 f"Videos: {summary.get('total_videos', 0)}")
    lines.append(f"  Render cost estimate: ${summary.get('total_cost_estimate', 0):.2f}")
    lines.append(f"  Ready: {summary.get('ready_scenes', 0)} | "
                 f"Blocked: {summary.get('blocked_scenes', 0)} | "
                 f"Bootstrappable: {summary.get('bootstrappable_scenes', 0)}")
    lines.append(f"  → {summary.get('recommendation', '')}")
    lines.append("")

    # Synthetic test
    syn = audit.get("_synthetic_test", {})
    if syn:
        syn_pass = "✅ PASS" if syn.get("health_score", 0) > 0.8 else "❌ FAIL"
        lines.append(f"  SYNTHETIC TEST: {syn_pass} (health={syn.get('health_score', 0):.0%})")
        lines.append("")

    # Per-project details
    for proj_name, proj_data in sorted(audit.items()):
        if proj_name.startswith("_") or not isinstance(proj_data, dict):
            continue
        if proj_data.get("type") != "real":
            continue
        if "error" in proj_data:
            lines.append(f"  ❌ {proj_name}: ERROR — {proj_data['error']}")
            continue

        lines.append(f"  {'─' * 68}")
        state_icon = {"READY": "✅", "DEGRADED_SAFE": "⚠️", "BLOCKED": "❌",
                      "BOOTSTRAPPABLE": "🔧", "COMPLETED": "🎬",
                      "FAILED_RECOVERABLE": "🔄"}.get(proj_data.get("state", ""), "❓")
        lines.append(f"  {state_icon} {proj_name} — {proj_data.get('state', 'UNKNOWN')} "
                     f"(health={proj_data.get('health_score', 0):.0%})")
        lines.append(f"     {proj_data.get('shots', 0)} shots | "
                     f"{proj_data.get('frames', 0)} frames | "
                     f"{proj_data.get('videos', 0)} videos | "
                     f"${proj_data.get('cost_estimate', 0):.2f}")

        if proj_data.get("missing_cast"):
            lines.append(f"     Missing cast: {', '.join(proj_data['missing_cast'][:5])}")

        # Scene breakdown
        insight = proj_data.get("insight", {})
        if insight.get("blockers"):
            lines.append(f"     BLOCKERS:")
            for b in insight["blockers"][:5]:
                lines.append(f"       • {b}")
        if insight.get("quick_wins"):
            lines.append(f"     QUICK WINS:")
            for w in insight["quick_wins"][:5]:
                lines.append(f"       🔧 {w}")

        # Per-scene compact view
        lines.append(f"     SCENES:")
        for sid, sd in sorted(proj_data.get("scene_details", {}).items()):
            s_icon = {"READY": "✅", "DEGRADED_SAFE": "⚠️", "BLOCKED": "❌",
                      "BOOTSTRAPPABLE": "🔧", "COMPLETED": "🎬"}.get(sd.get("state", ""), "❓")
            lines.append(
                f"       {s_icon} {sid}: {sd.get('shots', 0)} shots | "
                f"frames={sd.get('frames', 0)} | "
                f"vids={sd.get('videos', 0)} | "
                f"health={sd.get('health', 0):.0%} | "
                f"${sd.get('cost', 0):.2f}"
            )

    lines.append("")
    lines.append("=" * 72)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "harmony":
        projects = sys.argv[2:] if len(sys.argv) > 2 else None
        audit = harmony_audit(projects)
        print(format_harmony_report(audit))

        # Save JSON
        out_path = BASE_DIR / "reports" / "harmony_audit.json"
        out_path.parent.mkdir(exist_ok=True)
        with open(out_path, "w") as f:
            json.dump(audit, f, indent=2, default=str)
        print(f"\n  JSON saved: {out_path}")

    elif len(sys.argv) > 2 and sys.argv[1] == "scene":
        project = sys.argv[2]
        scene_id = sys.argv[3] if len(sys.argv) > 3 else None
        if scene_id:
            health = assess_scene(project, scene_id)
            print(f"\n  Scene {scene_id}: {health.state.value} "
                  f"(health={health.health_score:.0%})")
            print(f"  Shots: {health.shot_count} | "
                  f"Frames: {health.shots_with_frames} | "
                  f"Videos: {health.shots_with_videos}")
            print(f"  Allowed: {[a.value for a in health.allowed_actions]}")
            if health.blocking_reasons:
                print(f"  BLOCKING: {health.blocking_reasons}")
            for c in health.checks:
                icon = "✅" if c.passed else "❌"
                print(f"    {icon} {c.name}: {c.message} ({c.score:.0%})")
        else:
            health = assess_project(project)
            print(f"\n  {project}: {health.state.value} "
                  f"(health={health.health_score:.0%})")

    else:
        print("Usage:")
        print("  python3 tools/atlas_control_spine.py harmony [project...]")
        print("  python3 tools/atlas_control_spine.py scene <project> [scene_id]")
