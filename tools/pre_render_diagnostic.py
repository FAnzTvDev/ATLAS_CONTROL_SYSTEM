#!/usr/bin/env python3
"""
ATLAS Pre-Render Diagnostic
============================
The nervous system between operator intent and render execution.
Runs BEFORE any FAL spend. Reports in operator language, not JSON.

Exit codes:
    0 = READY to render
    1 = BLOCKED — issues must be fixed first
    2 = WARNING — can render but quality may suffer

Usage:
    python3 tools/pre_render_diagnostic.py {project} [scene_id]

Laws:
    256. Pre-render diagnostic is MANDATORY before any FAL spend
    257. Diagnostic reports in OPERATOR LANGUAGE, not JSON or server logs
    258. BLOCKED result prevents render — no override without explicit operator approval
    259. Diagnostic is FAST (<5 seconds) — never becomes a bottleneck
    260. Diagnostic checks PROMPT CONTENT, not just metadata presence
"""

import json
import sys
import os
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

# ─── CONFIGURATION ─────────────────────────────────────────────────────

PIPELINE_DIR = Path(__file__).parent.parent / "pipeline_outputs"

# Generic timing patterns that indicate V13 virus (not V25 enrichment)
GENERIC_TIMING_PATTERNS = [
    r"0-\d+s static hold, \d+-\d+s slow dolly, \d+-\d+s settle",
    r"0-\d+s static hold, \d+-\d+s slow push",
    r"0-\d+s static hold, \d+-\d+s subtle movement",
]

# CPC generic patterns (from creative_prompt_compiler.py Law 238)
CPC_GENERIC_PATTERNS = [
    "experiences the moment",
    "present and engaged",
    "natural movement begins",
    "subtle drift",
    "micro-expression",  # only flagged in no-character shots
]

# Bio bleed patterns
BIO_BLEED_PATTERNS = [
    r"Isabella\s+Moretti", r"Sophia\s+Chen", r"Marcus\s+Sterling",
    r"Amara\s+Okafor", r"Elena\s+Vasquez", r"James\s+Hartford",
]

# Camera brand patterns (Law 235)
CAMERA_BRAND_PATTERNS = [
    r"ARRI\s+Alexa", r"RED\s+(?:DSMC|Monstro|Komodo)",
    r"Sony\s+Venice", r"Panavision", r"Cooke\s+S[47]",
    r"Zeiss\s+Master", r"Kodak\s+Vision3", r"Fuji\s+Eterna",
]

# FAL forbidden params (Law 211)
FAL_FORBIDDEN_PARAMS = ["guidance_scale", "num_inference_steps", "image_size"]


# ─── DATA STRUCTURES ───────────────────────────────────────────────────

@dataclass
class CheckResult:
    name: str
    passed: bool
    blocking: bool
    message: str
    details: List[str] = field(default_factory=list)
    count: int = 0
    total: int = 0

@dataclass
class DiagnosticReport:
    project: str
    scene_id: Optional[str]
    ready: bool
    checks: List[CheckResult]
    shot_count: int = 0
    estimated_cost: float = 0.0
    estimated_time_minutes: float = 0.0

    def blocking_count(self) -> int:
        return sum(1 for c in self.checks if not c.passed and c.blocking)

    def warning_count(self) -> int:
        return sum(1 for c in self.checks if not c.passed and not c.blocking)

    def to_operator_string(self) -> str:
        """Human-readable diagnostic — NOT JSON, NOT server logs."""
        lines = []
        lines.append("=" * 60)
        lines.append(f"  ATLAS PRE-RENDER DIAGNOSTIC")
        lines.append(f"  Project: {self.project}")
        if self.scene_id:
            lines.append(f"  Scene: {self.scene_id}")
        lines.append(f"  Shots: {self.shot_count}")
        lines.append("=" * 60)
        lines.append("")

        if self.ready:
            lines.append(f"  ✅ READY TO RENDER")
            lines.append(f"  Estimated cost: ${self.estimated_cost:.2f}")
            lines.append(f"  Estimated time: ~{self.estimated_time_minutes:.0f} minutes")
        else:
            blocking = self.blocking_count()
            warnings = self.warning_count()
            if blocking > 0:
                lines.append(f"  ❌ BLOCKED — {blocking} issue(s) must be fixed")
            else:
                lines.append(f"  ⚠️  WARNINGS — {warnings} issue(s) may affect quality")

        lines.append("")
        lines.append("  CHECKS:")

        for c in self.checks:
            if c.passed:
                icon = "✅"
            elif c.blocking:
                icon = "❌"
            else:
                icon = "⚠️ "

            count_str = f" ({c.count}/{c.total})" if c.total > 0 else ""
            lines.append(f"    {icon} {c.name}{count_str}")

            if not c.passed:
                lines.append(f"       {c.message}")
                for d in c.details[:5]:  # Max 5 details per check
                    lines.append(f"       • {d}")
                if len(c.details) > 5:
                    lines.append(f"       ... and {len(c.details) - 5} more")

        lines.append("")
        lines.append("=" * 60)
        return "\n".join(lines)


# ─── DIAGNOSTIC CHECKS ────────────────────────────────────────────────

def check_prompt_quality(shots: List[dict]) -> CheckResult:
    """Check 1: Are prompts V25-enriched or generic V13 timing templates?"""
    generic_shots = []
    for s in shots:
        ltx = s.get("ltx_motion_prompt", "") or ""
        for pattern in GENERIC_TIMING_PATTERNS:
            if re.search(pattern, ltx):
                # Only flag if there's NO real content alongside the timing
                has_action = "character performs:" in ltx or "key motion:" in ltx
                has_dialogue = "character speaks:" in ltx
                if not has_action and not has_dialogue:
                    generic_shots.append(s.get("shot_id", "?"))
                    break

    total = len(shots)
    clean = total - len(generic_shots)
    return CheckResult(
        name="Prompt Quality (V25 enrichment)",
        passed=len(generic_shots) == 0,
        blocking=True,
        message=f"{len(generic_shots)} shots have generic timing templates instead of V25 action-driven prompts",
        details=[f"{sid}: generic timing template (no character action or dialogue)" for sid in generic_shots[:10]],
        count=clean,
        total=total
    )


def check_dialogue_markers(shots: List[dict]) -> CheckResult:
    """Check 2: Do all dialogue shots have 'character speaks:' in LTX?"""
    missing = []
    dialogue_shots = [s for s in shots if s.get("dialogue_text")]
    for s in dialogue_shots:
        ltx = s.get("ltx_motion_prompt", "") or ""
        if "character speaks:" not in ltx:
            missing.append(s.get("shot_id", "?"))

    total = len(dialogue_shots)
    return CheckResult(
        name="Dialogue Markers",
        passed=len(missing) == 0,
        blocking=True,
        message=f"{len(missing)} dialogue shots missing 'character speaks:' — LTX will generate frozen faces",
        details=[f"{sid}: has dialogue but no speech marker in LTX" for sid in missing[:10]],
        count=total - len(missing),
        total=total
    )


def check_performance_markers(shots: List[dict]) -> CheckResult:
    """Check 3: Do all character shots have performs/speaks/reacts?"""
    missing = []
    char_shots = [s for s in shots if s.get("characters")]
    for s in char_shots:
        ltx = s.get("ltx_motion_prompt", "") or ""
        has_marker = any(m in ltx for m in ["character performs:", "character speaks:", "character reacts:"])
        if not has_marker:
            missing.append(s.get("shot_id", "?"))

    total = len(char_shots)
    return CheckResult(
        name="Performance Markers",
        passed=len(missing) == 0,
        blocking=True,
        message=f"{len(missing)} character shots have no performance direction — LTX will generate static figures",
        details=[f"{sid}: no performs/speaks/reacts marker" for sid in missing[:10]],
        count=total - len(missing),
        total=total
    )


def check_composition(shots: List[dict]) -> CheckResult:
    """Check 4: Do nano prompts have 'composition:' marker?"""
    missing = []
    for s in shots:
        nano = s.get("nano_prompt", "") or ""
        if "composition:" not in nano and s.get("characters"):
            missing.append(s.get("shot_id", "?"))

    total = len([s for s in shots if s.get("characters")])
    return CheckResult(
        name="Composition Markers",
        passed=len(missing) == 0,
        blocking=False,  # Warning, not blocking
        message=f"{len(missing)} character shots missing composition direction",
        details=[f"{sid}: no 'composition:' in nano_prompt" for sid in missing[:5]],
        count=total - len(missing),
        total=total
    )


def check_contamination(shots: List[dict]) -> CheckResult:
    """Check 5: Are prompts free of bio bleed, camera brands, generic CPC patterns?"""
    contaminated = []
    for s in shots:
        nano = s.get("nano_prompt", "") or ""
        ltx = s.get("ltx_motion_prompt", "") or ""
        combined = nano + " " + ltx

        issues = []
        for pattern in BIO_BLEED_PATTERNS:
            if re.search(pattern, combined, re.IGNORECASE):
                issues.append("bio bleed")
                break
        for pattern in CAMERA_BRAND_PATTERNS:
            if re.search(pattern, combined):
                issues.append("camera brand")
                break

        # CPC generic check (only for character shots)
        if s.get("characters"):
            for generic in CPC_GENERIC_PATTERNS:
                if generic in ltx.lower():
                    issues.append(f"generic pattern: '{generic}'")
                    break

        if issues:
            contaminated.append((s.get("shot_id", "?"), ", ".join(issues)))

    total = len(shots)
    return CheckResult(
        name="Contamination Check",
        passed=len(contaminated) == 0,
        blocking=True,
        message=f"{len(contaminated)} shots have contamination (bio bleed, camera brands, or generic patterns)",
        details=[f"{sid}: {issue}" for sid, issue in contaminated[:10]],
        count=total - len(contaminated),
        total=total
    )


def check_asset_readiness(project_path: Path, shots: List[dict]) -> CheckResult:
    """Check 6: Do first frames and location masters exist?"""
    issues = []

    # First frames
    ff_dir = project_path / "first_frames"
    if not ff_dir.exists():
        issues.append("first_frames/ directory does not exist")
    else:
        missing_frames = []
        for s in shots:
            sid = s.get("shot_id", "")
            frame = ff_dir / f"{sid}.jpg"
            if not frame.exists():
                frame_png = ff_dir / f"{sid}.png"
                if not frame_png.exists():
                    missing_frames.append(sid)
        if missing_frames:
            issues.append(f"{len(missing_frames)} shots missing first frames: {', '.join(missing_frames[:5])}")

    # Location masters
    loc_dir = project_path / "location_masters"
    if not loc_dir.exists() or not any(loc_dir.glob("*.jpg")) and not any(loc_dir.glob("*.png")):
        issues.append("No location masters found — shots will have inconsistent environments")

    # Cast map
    cast_path = project_path / "cast_map.json"
    if not cast_path.exists():
        issues.append("cast_map.json missing — no character references for generation")

    return CheckResult(
        name="Asset Readiness",
        passed=len(issues) == 0,
        blocking=True,
        message="Missing required assets for generation",
        details=issues,
        count=0,
        total=0
    )


def check_contract_audit(project_path: Path, shots: List[dict]) -> CheckResult:
    """Check 7: Run lightweight contract checks (no server needed)."""
    criticals = []

    # F_LANDSCAPE_SAFETY: human body language in no-character shots
    human_words = ["blink", "breathing", "micro-expression", "chest rise", "brows:", "body:", "delivery:"]
    for s in shots:
        if not s.get("characters"):
            ltx = s.get("ltx_motion_prompt", "") or ""
            for hw in human_words:
                if hw in ltx.lower():
                    criticals.append(f"{s.get('shot_id','?')}: F_LANDSCAPE_SAFETY — '{hw}' in no-character shot")
                    break

    # H_DIALOGUE_MARKER: dialogue shots without speaks marker (already checked above, but contracts need it)
    for s in shots:
        if s.get("dialogue_text") and s.get("characters"):
            ltx = s.get("ltx_motion_prompt", "") or ""
            if "character speaks:" not in ltx and "speaks:" not in ltx:
                criticals.append(f"{s.get('shot_id','?')}: H_DIALOGUE_MARKER — dialogue without speech marker")

    # C_BIO_BLEED
    for s in shots:
        nano = s.get("nano_prompt", "") or ""
        for pattern in BIO_BLEED_PATTERNS:
            if re.search(pattern, nano, re.IGNORECASE):
                criticals.append(f"{s.get('shot_id','?')}: C_BIO_BLEED — AI actor name in prompt")
                break

    return CheckResult(
        name="Contract Audit (lightweight)",
        passed=len(criticals) == 0,
        blocking=True,
        message=f"{len(criticals)} CRITICAL contract violations",
        details=criticals[:10],
        count=0,
        total=0
    )


def check_coverage_grammar(shots: List[dict]) -> CheckResult:
    """Check 8: Does the scene have proper A/B/C coverage distribution?"""
    roles = {}
    for s in shots:
        role = s.get("coverage_role", s.get("shot_role", ""))
        if role:
            roles[role] = roles.get(role, 0) + 1

    issues = []
    if not roles:
        issues.append("No coverage roles assigned — run fix-v16")
    elif "A_GEOGRAPHY" not in roles and "GEOGRAPHY" not in roles:
        issues.append("No A_GEOGRAPHY (wide/master) shot — scene has no visual anchor")

    # Check all shots have same role
    unique_roles = set(roles.keys())
    if len(unique_roles) == 1 and len(shots) > 1:
        issues.append(f"All shots have same role ({list(unique_roles)[0]}) — no coverage variety")

    return CheckResult(
        name="Coverage Grammar (A/B/C)",
        passed=len(issues) == 0,
        blocking=False,  # Warning
        message="Coverage distribution issues detected",
        details=issues,
        count=len(unique_roles),
        total=3  # A, B, C
    )


def check_fal_params(shots: List[dict]) -> CheckResult:
    """Check 9: Verify no forbidden FAL params in shot data."""
    # This checks shot metadata for params that would be sent to FAL
    issues = []
    for s in shots:
        for param in FAL_FORBIDDEN_PARAMS:
            if param in s:
                issues.append(f"{s.get('shot_id','?')}: has forbidden FAL param '{param}'")

    return CheckResult(
        name="FAL API Params",
        passed=len(issues) == 0,
        blocking=True,
        message="Shots contain FAL params that don't exist in 2026 API",
        details=issues[:10],
        count=0,
        total=0
    )


def estimate_cost(shots: List[dict]) -> Tuple[float, float]:
    """Check 10: Estimate render cost and time."""
    # nano-banana-pro: ~$0.02/image
    # LTX-2.3 fast: ~$0.20/video (5s), ~$0.35 (10s), ~$0.50 (20s)
    frame_cost = len(shots) * 0.02
    video_cost = 0
    total_time = 0
    for s in shots:
        dur = s.get("duration", s.get("duration_seconds", 6))
        if dur <= 5:
            video_cost += 0.20
            total_time += 3
        elif dur <= 10:
            video_cost += 0.35
            total_time += 5
        else:
            video_cost += 0.50
            total_time += 8

    total_cost = frame_cost + video_cost
    total_minutes = total_time / 60
    return total_cost, total_minutes


# ─── MAIN DIAGNOSTIC ──────────────────────────────────────────────────

def run_diagnostic(project: str, scene_id: Optional[str] = None) -> DiagnosticReport:
    """Run all 10 diagnostic checks and return operator-ready report."""

    project_path = PIPELINE_DIR / project
    if not project_path.exists():
        return DiagnosticReport(
            project=project,
            scene_id=scene_id,
            ready=False,
            checks=[CheckResult(
                name="Project Exists",
                passed=False,
                blocking=True,
                message=f"Project directory not found: {project_path}"
            )]
        )

    # Load shot plan
    sp_path = project_path / "shot_plan.json"
    if not sp_path.exists():
        return DiagnosticReport(
            project=project,
            scene_id=scene_id,
            ready=False,
            checks=[CheckResult(
                name="Shot Plan Exists",
                passed=False,
                blocking=True,
                message=f"shot_plan.json not found"
            )]
        )

    sp = json.load(open(sp_path))
    shots = sp.get("shots", sp.get("shot_plan", []))

    # Filter by scene if specified
    if scene_id:
        shots = [s for s in shots if s.get("scene_id") == scene_id]
        if not shots:
            return DiagnosticReport(
                project=project,
                scene_id=scene_id,
                ready=False,
                checks=[CheckResult(
                    name="Scene Exists",
                    passed=False,
                    blocking=True,
                    message=f"No shots found for scene {scene_id}"
                )]
            )

    # Run all checks
    checks = [
        check_prompt_quality(shots),
        check_dialogue_markers(shots),
        check_performance_markers(shots),
        check_composition(shots),
        check_contamination(shots),
        check_asset_readiness(project_path, shots),
        check_contract_audit(project_path, shots),
        check_coverage_grammar(shots),
        check_fal_params(shots),
    ]

    # Cost estimate
    cost, time_min = estimate_cost(shots)

    # Determine readiness
    blocking = any(not c.passed and c.blocking for c in checks)

    return DiagnosticReport(
        project=project,
        scene_id=scene_id,
        ready=not blocking,
        checks=checks,
        shot_count=len(shots),
        estimated_cost=cost,
        estimated_time_minutes=time_min
    )


# ─── CLI ENTRY POINT ──────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 tools/pre_render_diagnostic.py {project} [scene_id]")
        sys.exit(1)

    project = sys.argv[1]
    scene_id = sys.argv[2] if len(sys.argv) > 2 else None

    # Change to project root
    script_dir = Path(__file__).parent.parent
    os.chdir(script_dir)

    report = run_diagnostic(project, scene_id)
    print(report.to_operator_string())

    if report.ready:
        sys.exit(0)
    elif report.blocking_count() > 0:
        sys.exit(1)
    else:
        sys.exit(2)  # Warnings only
