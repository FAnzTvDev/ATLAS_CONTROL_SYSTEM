"""
Unified Quality Gate (V27.3)
============================
Collects ALL post-generation quality signals into a SINGLE verdict per frame.

PROBLEM IT SOLVES:
Three quality systems (LOA identity, Cinematic Aesthetic, Doctrine compliance)
run independently. A frame can pass identity but fail aesthetics. A frame can
look cinematic but have wrong identity. Without a unified gate, the operator
has to cross-reference 5+ separate results manually.

THIS SYSTEM:
1. Collects verdicts from ALL quality sub-systems
2. Computes a single UNIFIED verdict: PASS / REGEN / FLAG
3. If REGEN: builds escalation plan (prompt injection + resolution bump + seed swap)
4. If FLAG: surfaces actionable diagnostics for operator
5. Tracks failure patterns across shots → identifies root causes

WIRING:
Called ONCE per shot, AFTER all post-gen quality checks complete.
Returns a UnifiedVerdict that the generation loop uses to decide:
  PASS → continue to next shot
  REGEN → regenerate with escalation (max 2 retries)
  FLAG → mark for operator review, continue to next shot

NON-BLOCKING FALLBACK: If unified gate throws, frame is PASS (degrade gracefully).
"""

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from collections import Counter

logger = logging.getLogger("atlas.unified_quality_gate")


# ═══════════════════════════════════════════════════════════
# VERDICT TYPES
# ═══════════════════════════════════════════════════════════

@dataclass
class QualitySignal:
    """Single quality signal from one sub-system."""
    source: str              # "loa", "aesthetic", "doctrine", "vision", "qa", "ots"
    passed: bool             # True if this sub-system is happy
    score: float = 0.0       # 0-1 normalized score (if applicable)
    reason: str = ""         # Human-readable reason for pass/fail
    blocking: bool = False   # If True, failure = mandatory regen
    fix_action: str = ""     # What to do if failed (prompt injection text, etc.)


@dataclass
class UnifiedVerdict:
    """The single quality verdict for a generated frame."""
    shot_id: str
    verdict: str = "PASS"                    # PASS / REGEN / FLAG
    attempt: int = 1                         # Which generation attempt this is
    signals: List[QualitySignal] = field(default_factory=list)
    composite_score: float = 1.0             # 0-1 unified quality score
    regen_plan: Optional[Dict] = None        # Escalation plan if REGEN
    diagnostics: List[str] = field(default_factory=list)  # Human-readable issues
    elapsed_ms: float = 0.0

    @property
    def signal_summary(self) -> Dict[str, str]:
        return {s.source: "PASS" if s.passed else "FAIL" for s in self.signals}


# ═══════════════════════════════════════════════════════════
# UNIFIED GATE CONFIGURATION
# ═══════════════════════════════════════════════════════════

# Weight each quality system in the composite score
SIGNAL_WEIGHTS = {
    "aesthetic": 0.35,      # Cinematic quality is the hardest problem
    "loa": 0.25,            # Identity correctness is critical
    "vision": 0.15,         # Vision gate (empty room, character presence)
    "doctrine": 0.10,       # Rule compliance
    "qa": 0.10,             # Face/composition/sharpness
    "ots": 0.05,            # OTS speaker verification
}

# Verdict thresholds
PASS_THRESHOLD = 0.65       # Composite score >= this = PASS
REGEN_THRESHOLD = 0.40      # Composite score >= this but < PASS = FLAG for review
                            # Composite score < this = mandatory REGEN

# Max regen attempts before giving up and flagging
MAX_REGEN_ATTEMPTS = 2

# Which sub-systems can trigger mandatory regen on their own
BLOCKING_SOURCES = {"loa", "aesthetic"}  # Identity wrong or AI-generic = must regen


# ═══════════════════════════════════════════════════════════
# SIGNAL COLLECTION — Normalize each sub-system's output
# ═══════════════════════════════════════════════════════════

def _collect_loa_signal(result_entry: Dict) -> QualitySignal:
    """Extract quality signal from LOA post-gen verdict."""
    loa = result_entry.get("loa_verdict") or {}
    if not loa:
        return QualitySignal(source="loa", passed=True, score=1.0, reason="LOA not available")

    # LOA returns identity_score (0-1) and location_score (0-1)
    id_score = loa.get("identity_score", 0.7)
    loc_score = loa.get("location_score", 0.5)
    combined = id_score * 0.7 + loc_score * 0.3

    passed = combined >= 0.5
    reason = f"identity={id_score:.2f}, location={loc_score:.2f}"
    fix = ""
    if not passed:
        if id_score < 0.4:
            fix = "Character identity failed — check ref pack quality"
        elif loc_score < 0.3:
            fix = "Location mismatch — verify room-lock resolution"

    return QualitySignal(
        source="loa", passed=passed, score=combined,
        reason=reason, blocking=(id_score < 0.3), fix_action=fix
    )


def _collect_aesthetic_signal(result_entry: Dict) -> QualitySignal:
    """Extract quality signal from cinematic aesthetic gate."""
    aes = result_entry.get("cinematic_aesthetic") or {}
    if not aes:
        # Try to score now if not yet done
        return QualitySignal(source="aesthetic", passed=True, score=0.7,
                           reason="Aesthetic gate not run")

    composite = aes.get("composite_score", 7.0)
    verdict = aes.get("verdict", "APPROVED")
    normalized = composite / 10.0  # Convert 0-10 to 0-1

    passed = verdict == "APPROVED"
    fix = ""
    if not passed:
        # Build prompt injection from dimension scores
        fixes = aes.get("fixes_needed", [])
        if fixes:
            fix = f"Cinematic fixes needed: {', '.join(fixes)}"

    return QualitySignal(
        source="aesthetic", passed=passed, score=normalized,
        reason=f"composite={composite:.1f}/10 ({verdict})",
        blocking=(verdict == "REJECTED"), fix_action=fix
    )


def _collect_doctrine_signal(result_entry: Dict) -> QualitySignal:
    """Extract quality signal from doctrine post-gen hook."""
    doc = result_entry.get("doctrine_verdict") or {}
    if not doc:
        return QualitySignal(source="doctrine", passed=True, score=1.0,
                           reason="Doctrine not available")

    accepted = doc.get("accepted", True)
    gates = doc.get("gates_checked", 0)
    excs = len(doc.get("phase_exceptions", []))

    score = 1.0 if accepted else 0.3
    if excs > 0:
        score *= 0.8  # Penalize phase exceptions

    return QualitySignal(
        source="doctrine", passed=accepted, score=score,
        reason=f"accepted={accepted}, gates={gates}, exceptions={excs}",
        blocking=False, fix_action=doc.get("reject_gate", "")
    )


def _collect_vision_signal(result_entry: Dict) -> QualitySignal:
    """Extract quality signal from vision gate."""
    vg = result_entry.get("vision_gate") or {}
    if not vg:
        return QualitySignal(source="vision", passed=True, score=0.7,
                           reason="Vision gate not run")

    passed = vg.get("pass", True)
    issues = vg.get("issues", [])
    score = 1.0 if passed else 0.3

    fix = ""
    if issues:
        fix = "; ".join(issues[:2])

    return QualitySignal(
        source="vision", passed=passed, score=score,
        reason=f"pass={passed}, issues={len(issues)}",
        blocking=False, fix_action=fix
    )


def _collect_qa_signal(result_entry: Dict) -> QualitySignal:
    """Extract quality signal from lightweight QA (face/composition/sharpness)."""
    qa = result_entry.get("qa_scores") or {}
    if not qa:
        return QualitySignal(source="qa", passed=True, score=0.7,
                           reason="QA not run")

    face = qa.get("face_score", 0.7)
    comp = qa.get("composition_score", 0.7)
    sharp = qa.get("sharpness_score", 0.7)
    avg = (face + comp + sharp) / 3

    return QualitySignal(
        source="qa", passed=(avg >= 0.5), score=avg,
        reason=f"face={face:.2f}, comp={comp:.2f}, sharp={sharp:.2f}",
        blocking=False
    )


def _collect_ots_signal(result_entry: Dict) -> QualitySignal:
    """Extract quality signal from OTS post-gen verification."""
    ots = result_entry.get("ots_verify") or {}
    if not ots:
        return QualitySignal(source="ots", passed=True, score=1.0,
                           reason="Not an OTS shot")

    passed = ots.get("speaker_facing_camera", True)
    return QualitySignal(
        source="ots", passed=passed,
        score=1.0 if passed else 0.2,
        reason=f"speaker_facing_camera={passed}",
        blocking=False
    )


# ═══════════════════════════════════════════════════════════
# REGEN PLAN BUILDER
# ═══════════════════════════════════════════════════════════

def build_regen_plan(
    shot: Dict,
    signals: List[QualitySignal],
    attempt: int,
    cast_map: Dict = None,
) -> Dict:
    """
    Build an escalation plan for regeneration.

    Attempt 1 → prompt injection + new seed
    Attempt 2 → prompt injection + resolution bump + new seed
    """
    plan = {
        "attempt": attempt + 1,
        "escalations": [],
        "prompt_injections": [],
        "resolution_bump": False,
        "new_seed": True,  # Always try new seed on regen
    }

    # Collect prompt injections from failing signals
    for sig in signals:
        if not sig.passed and sig.fix_action:
            plan["prompt_injections"].append(sig.fix_action)

    # Try to get cinematic override from aesthetic gate
    try:
        from tools.cinematic_aesthetic_gate import build_cinematic_prompt_injection, AestheticScore
        # Reconstruct score from result entry if possible
        aes_sig = next((s for s in signals if s.source == "aesthetic"), None)
        if aes_sig and not aes_sig.passed:
            plan["escalations"].append("cinematic_prompt_injection")
    except ImportError:
        pass

    # Attempt 2: bump resolution
    if attempt >= 1:
        plan["resolution_bump"] = True
        plan["escalations"].append("resolution_bump_1K_to_2K")

    # Identity failure: try re-resolving refs
    loa_sig = next((s for s in signals if s.source == "loa"), None)
    if loa_sig and not loa_sig.passed and loa_sig.score < 0.3:
        plan["escalations"].append("re_resolve_character_refs")

    return plan


# ═══════════════════════════════════════════════════════════
# MAIN UNIFIED GATE
# ═══════════════════════════════════════════════════════════

def evaluate_frame(
    shot_id: str,
    result_entry: Dict,
    shot: Dict,
    attempt: int = 1,
    cast_map: Dict = None,
) -> UnifiedVerdict:
    """
    The SINGLE quality gate that collects ALL sub-system signals
    and returns ONE verdict: PASS / REGEN / FLAG.

    Called ONCE per shot, AFTER all individual quality checks have run.
    """
    t0 = time.time()
    verdict = UnifiedVerdict(shot_id=shot_id, attempt=attempt)

    # 1. Collect signals from all sub-systems
    collectors = [
        _collect_loa_signal,
        _collect_aesthetic_signal,
        _collect_doctrine_signal,
        _collect_vision_signal,
        _collect_qa_signal,
        _collect_ots_signal,
    ]

    for collector in collectors:
        try:
            signal = collector(result_entry)
            verdict.signals.append(signal)
        except Exception as e:
            logger.debug(f"[UQG] Signal collection error ({collector.__name__}): {e}")

    # 2. Compute weighted composite score
    total_weight = 0.0
    weighted_sum = 0.0
    for sig in verdict.signals:
        w = SIGNAL_WEIGHTS.get(sig.source, 0.05)
        weighted_sum += sig.score * w
        total_weight += w

    verdict.composite_score = weighted_sum / total_weight if total_weight > 0 else 1.0

    # 3. Check for blocking failures (override composite)
    has_blocking_failure = any(
        not sig.passed and sig.blocking for sig in verdict.signals
    )

    # 4. Determine verdict
    if has_blocking_failure and attempt <= MAX_REGEN_ATTEMPTS:
        verdict.verdict = "REGEN"
        verdict.regen_plan = build_regen_plan(shot, verdict.signals, attempt, cast_map)
        for sig in verdict.signals:
            if not sig.passed and sig.blocking:
                verdict.diagnostics.append(f"BLOCKING: [{sig.source}] {sig.reason}")

    elif verdict.composite_score >= PASS_THRESHOLD:
        verdict.verdict = "PASS"

    elif verdict.composite_score >= REGEN_THRESHOLD:
        verdict.verdict = "FLAG"
        for sig in verdict.signals:
            if not sig.passed:
                verdict.diagnostics.append(f"REVIEW: [{sig.source}] {sig.reason}")

    else:
        if attempt <= MAX_REGEN_ATTEMPTS:
            verdict.verdict = "REGEN"
            verdict.regen_plan = build_regen_plan(shot, verdict.signals, attempt, cast_map)
        else:
            verdict.verdict = "FLAG"
            verdict.diagnostics.append(f"Max regen attempts ({MAX_REGEN_ATTEMPTS}) reached")

        for sig in verdict.signals:
            if not sig.passed:
                verdict.diagnostics.append(f"ISSUE: [{sig.source}] {sig.reason}")

    verdict.elapsed_ms = (time.time() - t0) * 1000
    return verdict


# ═══════════════════════════════════════════════════════════
# AESTHETIC GATE INLINE RUNNER
# Runs the cinematic aesthetic gate and stores results on result_entry
# ═══════════════════════════════════════════════════════════

def run_aesthetic_check(
    frame_path: str,
    shot_id: str,
    shot: Dict,
    result_entry: Dict,
    story_bible: Dict = None,
    reference_image_path: str = None,
) -> None:
    """
    Run the cinematic aesthetic gate and store results on result_entry.
    Non-blocking — if it fails, result_entry just won't have aesthetic data.
    """
    try:
        from tools.cinematic_aesthetic_gate import score_frame_aesthetic

        scene_genre = "gothic_horror"
        if story_bible:
            scene_genre = (story_bible.get("genre") or "gothic_horror").lower()

        shot_type = (shot.get("shot_type") or shot.get("type") or "medium").lower()

        score = score_frame_aesthetic(
            image_path=frame_path,
            shot_id=shot_id,
            shot_type=shot_type,
            scene_genre=scene_genre,
            reference_image_path=reference_image_path,
        )

        result_entry["cinematic_aesthetic"] = {
            "verdict": score.verdict,
            "composite_score": score.composite_score,
            "dimensions": {
                "depth_of_field": score.depth_of_field,
                "lighting_integration": score.lighting_integration,
                "composition": score.composition,
                "skin_texture": score.skin_texture,
                "environment_embedding": score.environment_embedding,
                "film_aesthetic": score.film_aesthetic,
            },
            "reasoning": score.reasoning,
            "fixes_needed": score.fixes_needed,
        }

        logger.info(f"[AESTHETIC] {shot_id}: {score.verdict} (composite={score.composite_score:.1f})")

    except Exception as e:
        logger.warning(f"[AESTHETIC] Non-blocking for {shot_id}: {e}")


# ═══════════════════════════════════════════════════════════
# APPLY REGEN ESCALATION — Modify shot/prompt for retry
# ═══════════════════════════════════════════════════════════

def apply_regen_escalation(
    shot: Dict,
    regen_plan: Dict,
    result_entry: Dict,
) -> Dict:
    """
    Apply regen escalation to shot data before retry.
    Returns modified shot dict.

    Escalations:
    1. Cinematic prompt injection → append [CINEMATIC OVERRIDE: ...] to nano_prompt
    2. Resolution bump → set _authority_resolution to 2K
    3. New seed → increment seed
    """
    shot = dict(shot)  # Don't mutate original

    # 1. Inject cinematic fixes into prompt
    aes = result_entry.get("cinematic_aesthetic") or {}
    if aes.get("fixes_needed"):
        try:
            from tools.cinematic_aesthetic_gate import build_cinematic_prompt_injection, AestheticScore
            # Reconstruct minimal score object
            dims = aes.get("dimensions", {})
            mock_score = AestheticScore(
                shot_id=shot.get("shot_id", ""),
                depth_of_field=dims.get("depth_of_field", 5.0),
                lighting_integration=dims.get("lighting_integration", 5.0),
                composition=dims.get("composition", 5.0),
                skin_texture=dims.get("skin_texture", 5.0),
                environment_embedding=dims.get("environment_embedding", 5.0),
                film_aesthetic=dims.get("film_aesthetic", 5.0),
            )
            injection = build_cinematic_prompt_injection(mock_score)
            if injection:
                nano = shot.get("nano_prompt", "")
                if "[CINEMATIC OVERRIDE:" not in nano:
                    shot["nano_prompt"] = nano + " " + injection
                    logger.info(f"[REGEN] Injected cinematic override for {shot.get('shot_id')}")
        except Exception as e:
            logger.debug(f"[REGEN] Cinematic injection failed: {e}")

    # 2. Resolution bump
    if regen_plan.get("resolution_bump"):
        current = shot.get("_authority_resolution", "1K")
        if current == "1K":
            shot["_authority_resolution"] = "2K"
        elif current == "2K":
            shot["_authority_resolution"] = "4K"
        logger.info(f"[REGEN] Resolution bump: {current} → {shot['_authority_resolution']}")

    # 3. Seed change
    if regen_plan.get("new_seed"):
        current_seed = shot.get("seed", 42)
        shot["seed"] = current_seed + 1000 + int(time.time()) % 10000
        logger.info(f"[REGEN] New seed: {current_seed} → {shot['seed']}")

    return shot


# ═══════════════════════════════════════════════════════════
# ERROR PATTERN AGGREGATOR
# ═══════════════════════════════════════════════════════════

class ErrorPatternAggregator:
    """
    Tracks failure patterns across shots to identify root causes.

    If 3+ shots fail on the same dimension (e.g., "depth_of_field < 4"),
    the root cause is likely the ref pack or the location master, not
    individual prompts. This triggers escalation to auto-recast.
    """

    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.failures: List[Dict] = []
        self._pattern_log_path = self.project_path / "reports" / "error_patterns.jsonl"
        self._pattern_log_path.parent.mkdir(parents=True, exist_ok=True)

    def record_failure(self, verdict: UnifiedVerdict, shot: Dict):
        """Record a failed frame for pattern analysis."""
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "shot_id": verdict.shot_id,
            "verdict": verdict.verdict,
            "composite_score": verdict.composite_score,
            "failing_signals": {
                s.source: {"score": s.score, "reason": s.reason}
                for s in verdict.signals if not s.passed
            },
            "characters": shot.get("characters", []),
            "shot_type": shot.get("shot_type") or shot.get("type", ""),
            "scene_id": shot.get("scene_id", ""),
        }
        self.failures.append(entry)

        # Append to persistent log
        try:
            with open(self._pattern_log_path, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass

    def detect_patterns(self) -> List[Dict]:
        """
        Analyze accumulated failures for patterns.

        Returns list of detected patterns with suggested root cause + fix.
        """
        if len(self.failures) < 2:
            return []

        patterns = []

        # Pattern 1: Same character fails identity repeatedly
        char_failures = Counter()
        for f in self.failures:
            loa = f.get("failing_signals", {}).get("loa", {})
            if loa:
                for char in f.get("characters", []):
                    char_failures[char] += 1

        for char, count in char_failures.items():
            if count >= 2:
                patterns.append({
                    "pattern": "REPEATED_IDENTITY_FAILURE",
                    "entity": char,
                    "occurrences": count,
                    "root_cause": f"Character ref pack for {char} may not match appearance description",
                    "suggested_fix": "auto_recast",
                    "priority": 1,
                })

        # Pattern 2: Same aesthetic dimension fails across shots
        dim_failures = Counter()
        for f in self.failures:
            aes = f.get("failing_signals", {}).get("aesthetic", {})
            if aes and "reason" in aes:
                # Parse out which dimensions failed
                reason = aes.get("reason", "")
                for dim in ["depth_of_field", "lighting", "composition", "skin_texture",
                           "environment", "film_aesthetic"]:
                    if dim.lower() in reason.lower():
                        dim_failures[dim] += 1

        for dim, count in dim_failures.items():
            if count >= 3:
                patterns.append({
                    "pattern": "SYSTEMATIC_AESTHETIC_FAILURE",
                    "entity": dim,
                    "occurrences": count,
                    "root_cause": f"Systematic {dim} issue — likely location master quality or prompt template",
                    "suggested_fix": "regen_location_masters" if "environment" in dim else "prompt_template_fix",
                    "priority": 2,
                })

        # Pattern 3: Entire scene fails (>50% of shots)
        scene_failures = Counter()
        scene_totals = Counter()
        for f in self.failures:
            sid = f.get("scene_id", "")
            if sid:
                scene_failures[sid] += 1

        # Would need total shot count per scene for percentage, use failures alone
        for scene, count in scene_failures.items():
            if count >= 3:
                patterns.append({
                    "pattern": "SCENE_WIDE_FAILURE",
                    "entity": scene,
                    "occurrences": count,
                    "root_cause": f"Scene {scene} has systemic quality issues — check location masters and lighting setup",
                    "suggested_fix": "regen_scene_location_masters",
                    "priority": 1,
                })

        return sorted(patterns, key=lambda p: p["priority"])

    def get_summary(self) -> Dict:
        """Summary of all recorded failures and detected patterns."""
        return {
            "total_failures": len(self.failures),
            "patterns_detected": self.detect_patterns(),
            "by_verdict": dict(Counter(f["verdict"] for f in self.failures)),
            "by_scene": dict(Counter(f.get("scene_id", "unknown") for f in self.failures)),
        }


# ═══════════════════════════════════════════════════════════
# CROSS-SCENE COLOR GRADING CORRECTOR
# ═══════════════════════════════════════════════════════════

def build_color_grade_injection(
    consistency_report: Dict,
    target_scene_id: str,
    reference_scene_id: str,
) -> str:
    """
    Build a prompt injection that forces color grading alignment between scenes.

    Uses the cross-scene consistency report to identify which dimensions drifted
    and generates corrective prompt text.
    """
    issues = consistency_report.get("consistency_issues", [])
    if not issues:
        return ""

    corrections = []
    for issue in issues:
        issue_type = issue.get("type", "").upper()
        detail = issue.get("detail", "")

        if "COLOR_TEMPERATURE" in issue_type:
            corrections.append(
                f"[COLOR MATCH: Match warm/cool balance of Scene {reference_scene_id}. "
                f"{detail}]"
            )
        elif "GRAIN" in issue_type or "TEXTURE" in issue_type:
            corrections.append(
                f"[GRAIN MATCH: Maintain consistent film grain density with Scene {reference_scene_id}]"
            )
        elif "CONTRAST" in issue_type:
            corrections.append(
                f"[CONTRAST MATCH: Shadow depth and highlight rolloff consistent with Scene {reference_scene_id}]"
            )
        elif "DOF" in issue_type:
            corrections.append(
                f"[DOF MATCH: Depth-of-field philosophy consistent — same lens language as Scene {reference_scene_id}]"
            )

    return " ".join(corrections) if corrections else ""


# ═══════════════════════════════════════════════════════════
# CONVENIENCE: Full pipeline integration helper
# ═══════════════════════════════════════════════════════════

def run_unified_quality_gate(
    shot_id: str,
    shot: Dict,
    result_entry: Dict,
    frame_path: str,
    attempt: int = 1,
    cast_map: Dict = None,
    story_bible: Dict = None,
    ref_path: str = None,
    error_aggregator: Optional[ErrorPatternAggregator] = None,
) -> UnifiedVerdict:
    """
    Full unified quality gate — runs aesthetic check if not done,
    collects all signals, returns single verdict.

    This is the ONE function the generation loop calls.
    """
    # Run aesthetic gate if not already done
    if "cinematic_aesthetic" not in result_entry:
        run_aesthetic_check(
            frame_path=frame_path,
            shot_id=shot_id,
            shot=shot,
            result_entry=result_entry,
            story_bible=story_bible,
            reference_image_path=ref_path,
        )

    # Evaluate all signals
    verdict = evaluate_frame(
        shot_id=shot_id,
        result_entry=result_entry,
        shot=shot,
        attempt=attempt,
        cast_map=cast_map,
    )

    # Record failures for pattern detection
    if error_aggregator and verdict.verdict in ("REGEN", "FLAG"):
        error_aggregator.record_failure(verdict, shot)

    # Log unified verdict
    level = logging.INFO if verdict.verdict == "PASS" else logging.WARNING
    logger.log(level,
        f"[UQG] {shot_id}: {verdict.verdict} "
        f"(composite={verdict.composite_score:.2f}, "
        f"signals={verdict.signal_summary})"
    )
    if verdict.diagnostics:
        for diag in verdict.diagnostics:
            logger.warning(f"[UQG]   → {diag}")

    return verdict
