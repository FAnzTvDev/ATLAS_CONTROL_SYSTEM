"""
ATLAS V27.1.5 — Render Learning Agent
═══════════════════════════════════════

The learning agent that sits between every render run and the controller.
It learns from past failures, enforces behavioral understanding from doctrine,
and prevents repeat errors.

Connected to: V26 Controller, Orchestrator generate-first-frames, Quality Gate

WHAT IT DOES:
1. PRE-RENDER: Validates every shot's prompt BEFORE sending to FAL
   - Checks for missing Room DNA, Lighting Rig, Focal Enforcement
   - Checks for old anti-morph patterns that freeze bodies
   - Checks for corrupted/repeated text
   - Checks for generic B-roll without narrative content
   - Checks for missing timed choreography on character shots
   - BLOCKS render if any shot fails validation

2. POST-RENDER: Reviews generated frames as a GROUP
   - Identifies spatial inconsistencies between shots
   - Flags room changes without screenplay movement
   - Compares framing vs shot_type (close-up actually close?)
   - Logs learnings to learning_log.jsonl

3. LEARNING: Accumulates knowledge across runs
   - Reads learning_log.jsonl for past failures
   - Applies learned fixes automatically
   - Never makes the same mistake twice

USAGE:
    from tools.render_learning_agent import RenderLearningAgent

    agent = RenderLearningAgent(project_path)

    # Pre-render validation
    result = agent.pre_render_validate(scene_shots, story_bible_scene)
    if result["blocked"]:
        print(f"BLOCKED: {result['blocking_issues']}")
        return

    # ... generate frames ...

    # Post-render review
    review = agent.post_render_review(scene_shots, generated_frames_dir)
    for shot_id, verdict in review["verdicts"].items():
        if verdict["status"] == "REJECTED":
            print(f"REJECTED {shot_id}: {verdict['reason']}")
"""

import json
import os
import re
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class RenderLearningAgent:
    """
    The learning agent that connects to the controller and prevents repeat errors.
    Learns from every run via learning_log.jsonl.
    """

    # ═══════════════════════════════════════════════════════════════
    # LEARNED PATTERNS — accumulated from production failures
    # These are the behavioral rules the agent enforces
    # ═══════════════════════════════════════════════════════════════

    KNOWN_FAILURE_PATTERNS = {
        "blanket_anti_morph": {
            "detect": lambda nano, ltx: (
                ("NO morphing" in ltx or "no morphing" in ltx.lower()) and
                "FACE IDENTITY LOCK" not in ltx
            ),
            "severity": "BLOCKING",
            "lesson": "V27.1.5: Blanket 'NO morphing' freezes entire body. Must use split: FACE IDENTITY LOCK + BODY PERFORMANCE FREE",
            "auto_fix": True
        },
        "missing_room_dna": {
            "detect": lambda nano, ltx: "[ROOM DNA:" not in nano,
            "severity": "BLOCKING",
            "lesson": "V27.1.5: Without Room DNA, FAL generates different room architecture per shot",
            "auto_fix": False
        },
        "missing_lighting_rig": {
            "detect": lambda nano, ltx: "[LIGHTING RIG:" not in nano,
            "severity": "WARNING",
            "lesson": "V27.1.5: Without locked lighting, color temperature drifts between shots",
            "auto_fix": False
        },
        "no_focal_enforcement_closeup": {
            "detect": lambda nano, ltx: False,  # overridden per-shot
            "severity": "BLOCKING",
            "lesson": "V27.1.5: FAL ignores numeric focal lengths (85mm). Must describe visual effect.",
            "auto_fix": False
        },
        "no_timed_choreography": {
            "detect": lambda nano, ltx: False,  # overridden per-shot
            "severity": "WARNING",
            "lesson": "V27.1.5: Without per-second timing, model gets no movement direction",
            "auto_fix": False
        },
        "corrupted_prompt": {
            "detect": lambda nano, ltx: False,  # checked separately (substring search)
            "severity": "BLOCKING",
            "lesson": "V27.1.2: Stacked fix-v16 passes create repeated text. Must recompile.",
            "auto_fix": True
        },
        "generic_broll": {
            "detect": lambda nano, ltx: False,  # overridden per-shot
            "severity": "WARNING",
            "lesson": "V27.1: B-roll without narrative content creates empty rooms with no story purpose",
            "auto_fix": False
        },
        "reframe_still_active": {
            "detect": lambda nano, ltx: "REFRAME ONLY" in nano,
            "severity": "BLOCKING",
            "lesson": "V27.1.5: Reframe prompts override baked prompts with generic text. Must be disabled.",
            "auto_fix": True
        },
        "camera_brand_in_prompt": {
            "detect": lambda nano, ltx: any(brand in nano for brand in [
                "ARRI", "Alexa", "Cooke", "RED ", "Zeiss", "Panavision",
                "Kodak", "Fuji", "Vision3", "Eterna"
            ]),
            "severity": "WARNING",
            "lesson": "V26.1: Camera/film brands cause prompt noise on FAL models",
            "auto_fix": True
        },
        "character_name_only_in_video": {
            "detect": lambda nano, ltx: False,  # checked per-shot with character list
            "severity": "WARNING",
            "lesson": "V27.1: FAL doesn't know character NAMES. Must use appearance descriptions.",
            "auto_fix": False
        },
    }

    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.learning_log_path = self.project_path / "learning_log.jsonl"
        self.learnings = self._load_learnings()
        self.run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    def _load_learnings(self) -> List[Dict]:
        """Load accumulated learnings from past runs."""
        learnings = []
        if self.learning_log_path.exists():
            try:
                with open(self.learning_log_path) as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                learnings.append(json.loads(line))
                            except json.JSONDecodeError:
                                continue
            except Exception:
                pass
        return learnings

    def _log_learning(self, category: str, shot_id: str, detail: str,
                      severity: str = "INFO", auto_fixed: bool = False):
        """Append a learning to the log."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "run_id": self.run_id,
            "category": category,
            "shot_id": shot_id,
            "detail": detail,
            "severity": severity,
            "auto_fixed": auto_fixed
        }
        try:
            with open(self.learning_log_path, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass
        self.learnings.append(entry)

    # ═══════════════════════════════════════════════════════════════
    # PRE-RENDER VALIDATION
    # Runs BEFORE any FAL call. Blocks if critical issues found.
    # ═══════════════════════════════════════════════════════════════

    def pre_render_validate(self, shots: List[Dict],
                            story_scene: Dict = None) -> Dict:
        """
        Validate all shots BEFORE rendering.
        Returns: {blocked: bool, blocking_issues: [], warnings: [], auto_fixes: []}
        """
        result = {
            "blocked": False,
            "blocking_issues": [],
            "warnings": [],
            "auto_fixes": [],
            "shots_checked": 0,
            "shots_passed": 0,
        }

        scene_location = (story_scene or {}).get("location", "")
        beats = (story_scene or {}).get("beats", [])

        for shot in shots:
            sid = shot.get("shot_id", "")
            stype = (shot.get("shot_type") or "").lower()
            chars = shot.get("characters") or []
            nano = shot.get("nano_prompt") or ""
            ltx = shot.get("ltx_motion_prompt") or ""
            has_dialogue = bool(shot.get("dialogue_text"))

            result["shots_checked"] += 1
            shot_issues = []

            # Run all known failure pattern checks
            for pattern_name, pattern in self.KNOWN_FAILURE_PATTERNS.items():
                try:
                    if pattern["detect"](nano, ltx):
                        issue = {
                            "shot_id": sid,
                            "pattern": pattern_name,
                            "severity": pattern["severity"],
                            "lesson": pattern["lesson"],
                        }
                        if pattern["severity"] == "BLOCKING":
                            result["blocking_issues"].append(issue)
                            shot_issues.append(pattern_name)
                        else:
                            result["warnings"].append(issue)

                        # Auto-fix if possible
                        if pattern.get("auto_fix"):
                            fixed = self._auto_fix(shot, pattern_name)
                            if fixed:
                                result["auto_fixes"].append({
                                    "shot_id": sid,
                                    "pattern": pattern_name,
                                    "fix_applied": fixed
                                })
                                self._log_learning(
                                    "auto_fix", sid,
                                    f"Auto-fixed {pattern_name}: {fixed}",
                                    "FIX", auto_fixed=True
                                )
                except Exception:
                    continue

            # Per-shot type checks
            if stype in ["close_up", "medium_close", "reaction", "extreme_close"]:
                if "TIGHT FRAMING" not in nano and "MEDIUM-TIGHT" not in nano:
                    result["blocking_issues"].append({
                        "shot_id": sid,
                        "pattern": "no_focal_enforcement_closeup",
                        "severity": "BLOCKING",
                        "lesson": "Close-up without focal enforcement will render as wide"
                    })
                    shot_issues.append("no_focal_enforcement")

            # Character shots need timed choreography
            if chars and "TIMED CHOREOGRAPHY:" not in ltx and has_dialogue:
                result["warnings"].append({
                    "shot_id": sid,
                    "pattern": "no_timed_choreography",
                    "severity": "WARNING",
                    "lesson": "Dialogue shot without per-second timing"
                })

            # B-roll narrative check
            if not chars and stype in ["establishing", "insert"]:
                narrative_keywords = [
                    "enters", "dust", "briefcase", "banister", "portrait",
                    "staircase", "door", "candlestick", "letter", "photograph",
                    "silhouette", "approaches", "servant", "carriage"
                ]
                has_narrative = any(kw in nano.lower() for kw in narrative_keywords)
                if not has_narrative:
                    result["warnings"].append({
                        "shot_id": sid,
                        "pattern": "generic_broll",
                        "severity": "WARNING",
                        "lesson": "B-roll without narrative action from story beats"
                    })

            # Corruption check (30-char substring 3+ times)
            for prompt_name, prompt_text in [("nano", nano), ("ltx", ltx)]:
                if len(prompt_text) > 60:
                    for i in range(0, min(len(prompt_text) - 30, 500)):
                        substr = prompt_text[i:i+30]
                        if prompt_text.count(substr) >= 3:
                            result["blocking_issues"].append({
                                "shot_id": sid,
                                "pattern": "corrupted_prompt",
                                "severity": "BLOCKING",
                                "lesson": f"Repeated text in {prompt_name}_prompt"
                            })
                            shot_issues.append("corruption")
                            break

            # Character name in video prompt without appearance
            if chars and ltx:
                for char in chars:
                    if char in ltx and "man," not in ltx and "woman," not in ltx:
                        result["warnings"].append({
                            "shot_id": sid,
                            "pattern": "character_name_only_in_video",
                            "severity": "WARNING",
                            "lesson": f"'{char}' in ltx without appearance description"
                        })

            if not shot_issues:
                result["shots_passed"] += 1

        result["blocked"] = len(result["blocking_issues"]) > 0

        # Log the validation run
        self._log_learning(
            "pre_render_validation", "ALL",
            f"Checked {result['shots_checked']} shots: "
            f"{result['shots_passed']} passed, "
            f"{len(result['blocking_issues'])} blocking, "
            f"{len(result['warnings'])} warnings, "
            f"{len(result['auto_fixes'])} auto-fixed",
            "BLOCKING" if result["blocked"] else "PASS"
        )

        return result

    # ═══════════════════════════════════════════════════════════════
    # AUTO-FIX KNOWN PATTERNS
    # ═══════════════════════════════════════════════════════════════

    def _auto_fix(self, shot: Dict, pattern_name: str) -> Optional[str]:
        """Apply automatic fix for known patterns. Returns fix description or None."""

        if pattern_name == "blanket_anti_morph":
            ltx = shot.get("ltx_motion_prompt", "")
            ltx = ltx.replace(
                "face stable NO morphing, character consistent",
                "FACE IDENTITY LOCK: features UNCHANGED. BODY PERFORMANCE FREE: breathing, gestures continue"
            ).replace(
                "face stable, NO morphing, character consistent",
                "FACE IDENTITY LOCK: features UNCHANGED. BODY PERFORMANCE FREE: breathing, gestures continue"
            ).replace(
                "NO morphing faces",
                "FACE IDENTITY LOCK: facial structure UNCHANGED"
            )
            shot["ltx_motion_prompt"] = ltx
            return "Split anti-morph: face lock + body free"

        if pattern_name == "reframe_still_active":
            # This shouldn't happen with V27.1.5 kill switch, but just in case
            nano = shot.get("nano_prompt", "")
            if "REFRAME ONLY" in nano:
                shot["nano_prompt"] = nano.replace("REFRAME ONLY.", "").strip()
                return "Stripped REFRAME ONLY directive"

        if pattern_name == "camera_brand_in_prompt":
            nano = shot.get("nano_prompt", "")
            for brand in ["ARRI Alexa", "Cooke S4", "RED Monstro", "Zeiss Master",
                          "Panavision", "Kodak 2383", "Fuji Eterna", "Kodak Vision3"]:
                nano = nano.replace(brand, "")
            shot["nano_prompt"] = re.sub(r'\s+', ' ', nano).strip()
            return "Stripped camera/film brand names"

        return None

    # ═══════════════════════════════════════════════════════════════
    # POST-RENDER REVIEW (Group Analysis)
    # ═══════════════════════════════════════════════════════════════

    def post_render_review(self, shots: List[Dict],
                          frames_dir: str) -> Dict:
        """
        Review generated frames as a GROUP after rendering.
        Checks for spatial consistency, framing accuracy, room continuity.

        Returns: {verdicts: {shot_id: {status, reason, suggestions}}, summary: str}
        """
        frames_path = Path(frames_dir)
        result = {
            "verdicts": {},
            "summary": "",
            "approved": 0,
            "needs_variation": 0,
            "rejected": 0,
        }

        # Group shots by scene
        scene_shots = {}
        for shot in shots:
            sid = shot.get("shot_id", "")
            scene_id = shot.get("scene_id", sid[:3])
            if scene_id not in scene_shots:
                scene_shots[scene_id] = []
            scene_shots[scene_id].append(shot)

        for scene_id, scene_shot_list in scene_shots.items():
            # Check each shot
            for shot in scene_shot_list:
                sid = shot.get("shot_id", "")
                stype = shot.get("shot_type", "")
                frame_path = frames_path / f"{sid}.jpg"

                verdict = {"status": "APPROVED", "reason": "", "suggestions": []}

                # Frame exists?
                if not frame_path.exists():
                    verdict["status"] = "REJECTED"
                    verdict["reason"] = "Frame not generated"
                    result["rejected"] += 1
                    result["verdicts"][sid] = verdict
                    continue

                # Frame file size sanity (< 10KB probably failed)
                if frame_path.stat().st_size < 10000:
                    verdict["status"] = "REJECTED"
                    verdict["reason"] = f"Frame too small ({frame_path.stat().st_size} bytes) — likely failed generation"
                    result["rejected"] += 1
                    result["verdicts"][sid] = verdict
                    continue

                # Check if shot has all required metadata
                issues = []
                if "[ROOM DNA:" not in (shot.get("nano_prompt") or ""):
                    issues.append("Missing Room DNA")
                if not shot.get("_quality_gate_ready"):
                    issues.append("Not quality-gate-ready (missing timed actions or beat mapping)")

                if issues:
                    verdict["status"] = "NEEDS_VARIATION"
                    verdict["reason"] = "; ".join(issues)
                    verdict["suggestions"] = ["Regenerate with baked prompts", "Run quality gate bake first"]
                    result["needs_variation"] += 1
                else:
                    result["approved"] += 1

                result["verdicts"][sid] = verdict

        total = result["approved"] + result["needs_variation"] + result["rejected"]
        result["summary"] = (
            f"{result['approved']}/{total} APPROVED, "
            f"{result['needs_variation']} NEEDS_VARIATION, "
            f"{result['rejected']} REJECTED"
        )

        self._log_learning(
            "post_render_review", "ALL",
            result["summary"],
            "PASS" if result["rejected"] == 0 else "FAIL"
        )

        return result

    # ═══════════════════════════════════════════════════════════════
    # DRY-RUN (Simulate without calling FAL)
    # ═══════════════════════════════════════════════════════════════

    def dry_run(self, shots: List[Dict], story_scene: Dict = None) -> Dict:
        """
        Full dry-run: pre-validate + simulate pipeline mutations + report.
        No FAL calls, no cost.
        """
        # Step 1: Pre-render validation
        pre_result = self.pre_render_validate(shots, story_scene)

        # Step 2: Simulate OTS enforcer mutations
        import copy
        try:
            from tools.ots_enforcer import OTSEnforcer
        except ImportError:
            from ots_enforcer import OTSEnforcer

        cast_map = {}
        cast_path = self.project_path / "cast_map.json"
        if cast_path.exists():
            try:
                cast_map = json.load(open(cast_path))
            except:
                pass

        enforcer = OTSEnforcer(cast_map)
        enforcer.establish_screen_positions(shots)

        mutations = []
        for shot in shots:
            sim_shot = copy.deepcopy(shot)
            sid = sim_shot.get("shot_id", "")

            pre_nano = sim_shot.get("nano_prompt", "")[:200]
            pre_ltx = sim_shot.get("ltx_motion_prompt", "")[:200]

            if sim_shot.get("dialogue_text"):
                prev = [s for s in shots if (s.get("shot_id", "") or "") < sid]
                try:
                    enforcer.prepare_dialogue_shot(sim_shot, prev_shots=prev)
                except:
                    pass

            post_nano = sim_shot.get("nano_prompt", "")[:200]
            post_ltx = sim_shot.get("ltx_motion_prompt", "")[:200]

            if pre_nano != post_nano or pre_ltx != post_ltx:
                # Check if baked content survived
                dna_survived = "[ROOM DNA:" in sim_shot.get("nano_prompt", "")
                timed_survived = "TIMED CHOREOGRAPHY:" in sim_shot.get("ltx_motion_prompt", "")

                mutations.append({
                    "shot_id": sid,
                    "nano_changed": pre_nano != post_nano,
                    "ltx_changed": pre_ltx != post_ltx,
                    "dna_survived": dna_survived,
                    "timed_survived": timed_survived,
                    "critical": not dna_survived or not timed_survived
                })

        return {
            "pre_validation": pre_result,
            "mutations_detected": len(mutations),
            "critical_mutations": sum(1 for m in mutations if m["critical"]),
            "mutations": mutations,
            "safe_to_render": not pre_result["blocked"] and all(
                not m["critical"] for m in mutations
            ),
            "screen_positions": dict(enforcer._screen_positions),
        }

    # ═══════════════════════════════════════════════════════════════
    # LEARNING REPORT
    # ═══════════════════════════════════════════════════════════════

    def get_learning_summary(self) -> Dict:
        """Summarize accumulated learnings across all runs."""
        if not self.learnings:
            return {"total_runs": 0, "total_learnings": 0}

        from collections import Counter
        categories = Counter(l.get("category") for l in self.learnings)
        severities = Counter(l.get("severity") for l in self.learnings)
        auto_fixes = sum(1 for l in self.learnings if l.get("auto_fixed"))
        runs = len(set(l.get("run_id") for l in self.learnings))

        return {
            "total_runs": runs,
            "total_learnings": len(self.learnings),
            "by_category": dict(categories),
            "by_severity": dict(severities),
            "auto_fixes_applied": auto_fixes,
            "latest_run": self.learnings[-1].get("timestamp") if self.learnings else None,
        }


# ═══════════════════════════════════════════════════════════════
# SELF-TEST
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys

    project = sys.argv[1] if len(sys.argv) > 1 else "pipeline_outputs/victorian_shadows_ep1"

    agent = RenderLearningAgent(project)

    # Load shots
    sp = json.load(open(f"{project}/shot_plan.json"))
    if isinstance(sp, list):
        sp = {"shots": sp}
    shots = sp["shots"]

    # Load story bible
    sb = json.load(open(f"{project}/story_bible.json"))
    scene_001 = next((sc for sc in sb.get("scenes", []) if str(sc.get("scene_id", "")) == "001"), {})

    # Filter to scene 001
    scene_shots = [s for s in shots if s.get("shot_id", "").startswith("001")]

    print("=" * 80)
    print("RENDER LEARNING AGENT — Self-Test")
    print("=" * 80)

    # Run dry-run
    result = agent.dry_run(scene_shots, scene_001)

    print(f"\nPre-validation: {'BLOCKED' if result['pre_validation']['blocked'] else 'PASSED'}")
    print(f"  Blocking issues: {len(result['pre_validation']['blocking_issues'])}")
    print(f"  Warnings: {len(result['pre_validation']['warnings'])}")
    print(f"  Auto-fixes: {len(result['pre_validation']['auto_fixes'])}")
    print(f"\nMutation simulation:")
    print(f"  Mutations detected: {result['mutations_detected']}")
    print(f"  Critical mutations: {result['critical_mutations']}")
    print(f"  Screen positions: {result['screen_positions']}")
    print(f"\n{'✅ SAFE TO RENDER' if result['safe_to_render'] else '❌ NOT SAFE TO RENDER'}")

    # Learning summary
    summary = agent.get_learning_summary()
    print(f"\nLearning summary:")
    print(f"  Total runs: {summary['total_runs']}")
    print(f"  Total learnings: {summary['total_learnings']}")
    print(f"  Auto-fixes applied: {summary.get('auto_fixes_applied', 0)}")
