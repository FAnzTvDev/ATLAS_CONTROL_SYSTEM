#!/usr/bin/env python3
"""
V20.2 Viewer Retention Engine — Make AI Video Feel Like Real Movies

THE PROBLEM:
AI-generated video sequences have a distinctive "AI ache" — a subtle wrongness
that makes viewers uncomfortable even if they can't articulate why. It comes from:

1. SAME FACE FATIGUE — Same character dominates 4+ consecutive shots (real movies
   cut away to reactions, inserts, environment to let the viewer breathe)
2. EMOTIONAL FLATLINE — Same emotion sustained too long without release (real movies
   use micro-releases: a breath, a glance away, a neutral beat between peaks)
3. VISUAL MONOTONY — Same framing/lens/movement repeated (real movies vary the
   visual rhythm even within the same scene type)
4. REACTION DEFICIT — Dialogue scenes without enough reaction shots (real movies
   show the LISTENER as much as the speaker — reactions ARE the story)
5. CUT OVERLOAD — Too many cuts per minute for the genre (action=fast, drama=slow;
   AI tends to default to uniform rapid cutting)
6. ENSEMBLE NEGLECT — Secondary characters starved of screen time (real movies
   give every named character presence, even if brief)
7. LOCATION STALENESS — Same background for 8+ consecutive shots without a visual
   break (real movies cut to windows, details, establishing shots for air)
8. CROSS-SCENE FATIGUE — Three dialogue-heavy scenes in a row without visual variety
   (real movies alternate rhythm: dialogue → action → atmosphere → dialogue)

DESIGN PRINCIPLE: This is a POST-PROCESSOR that runs after V20.1 Story Intelligence.
It doesn't change shot TYPES (that's V20.1's job). It adjusts shot SEQUENCING,
adds BREATHING ROOM, and flags COMFORT VIOLATIONS that need manual fixes.

It writes metadata to shots that downstream systems (cinematic enricher, continuity
gate, duration scaler) can consume to improve the final output.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# GENRE CUT DENSITY — How fast can you cut before the viewer flinches?
# ═══════════════════════════════════════════════════════════════════

# Cuts per minute by genre — based on real film analysis
# Action movies average 3-4 cuts/min, horror 1.5-2.5, drama 1-2
# Going ABOVE these thresholds creates cognitive overload
GENRE_CUT_DENSITY = {
    "action": {"target": 3.5, "max": 5.0, "min": 2.0},
    "thriller": {"target": 2.5, "max": 4.0, "min": 1.5},
    "horror": {"target": 2.0, "max": 3.0, "min": 1.0},
    "gothic_horror": {"target": 1.8, "max": 2.5, "min": 0.8},
    "drama": {"target": 1.5, "max": 2.5, "min": 0.8},
    "romance": {"target": 1.5, "max": 2.5, "min": 0.8},
    "comedy": {"target": 2.5, "max": 4.0, "min": 1.5},
    "sci_fi": {"target": 2.0, "max": 3.5, "min": 1.0},
    "noir": {"target": 1.8, "max": 2.5, "min": 0.8},
    "period": {"target": 1.5, "max": 2.0, "min": 0.7},
    "documentary": {"target": 1.0, "max": 1.5, "min": 0.5},
    "fantasy": {"target": 2.5, "max": 3.5, "min": 1.5},
    "epic_fantasy": {"target": 2.0, "max": 3.0, "min": 1.0},
    "dark_fantasy": {"target": 2.0, "max": 3.0, "min": 1.0},
    "adventure": {"target": 3.0, "max": 4.5, "min": 2.0},
    "war": {"target": 2.5, "max": 4.0, "min": 1.5},
    "mystery": {"target": 1.8, "max": 2.5, "min": 0.8},
    "supernatural": {"target": 2.0, "max": 3.0, "min": 1.0},
    "western": {"target": 1.5, "max": 2.5, "min": 0.8},
    "musical": {"target": 2.5, "max": 3.5, "min": 1.5},
    "animation": {"target": 3.0, "max": 5.0, "min": 2.0},
}

DEFAULT_CUT_DENSITY = {"target": 2.0, "max": 3.0, "min": 1.0}


# ═══════════════════════════════════════════════════════════════════
# SHOT SIZE PROGRESSION — The Grammar of Comfortable Cuts
# ═══════════════════════════════════════════════════════════════════

# How "tight" each shot type is (1=widest, 10=tightest)
SHOT_SIZE_SCALE = {
    "establishing": 1,
    "wide": 2,
    "medium_wide": 3,
    "medium": 4,
    "medium_close": 5,
    "over_the_shoulder": 5,
    "two_shot": 4,
    "close": 7,
    "extreme_close": 9,
    "insert": 6,
    "detail": 8,
    "reaction": 6,
    "tracking": 4,
    "reverse_medium": 4,
    "pov": 5,
    # Additional types from V9 vocabulary
    "dutch_angle": 4,
    "crane": 2,
    "dolly": 4,
    "whip_pan": 4,
    "drone": 1,
    "low_angle": 4,
    "high_angle": 3,
}

# Comfortable size jumps: how many "sizes" you can jump in one cut
# Jumping wide(2) → close(7) = 5 sizes = jarring without motivation
# Jumping wide(2) → medium(4) = 2 sizes = comfortable
MAX_COMFORTABLE_JUMP = 3  # Beyond this, insert a transition shot
MAX_COMFORTABLE_TIGHTEN = 4  # Can tighten faster than widen (emotional escalation)


# ═══════════════════════════════════════════════════════════════════
# CHARACTER SCREEN TIME — No Face Should Dominate Too Long
# ═══════════════════════════════════════════════════════════════════

MAX_CONSECUTIVE_SAME_CHAR = 4  # After 4 shots of the same primary character, cut away
BREATHING_SHOT_TYPES = {"wide", "establishing", "insert", "detail", "reaction"}


# ═══════════════════════════════════════════════════════════════════
# EMOTIONAL RHYTHM — Peak-Release-Peak Pattern
# ═══════════════════════════════════════════════════════════════════

MAX_PEAK_CONSECUTIVE = 3  # Max shots at emotion ≥7 before requiring a release
RELEASE_THRESHOLD = 4    # Emotion must drop to this level for a "release" beat
MAX_FLATLINE_CONSECUTIVE = 5  # Max shots at SAME intensity (±1) before needing change


# ═══════════════════════════════════════════════════════════════════
# LOCATION FRESHNESS — How Long Before a Background Gets Stale
# ═══════════════════════════════════════════════════════════════════

MAX_SAME_LOCATION_SHOTS = 8  # After 8 shots in same location, suggest a visual break
LOCATION_BREAK_TYPES = {"establishing", "insert", "detail", "wide"}  # Types that refresh visual


# ═══════════════════════════════════════════════════════════════════
# DIALOGUE / REACTION RATIO — Real Movies Show the Listener
# ═══════════════════════════════════════════════════════════════════

# In real movies, dialogue scenes typically show ~40% speaker, ~40% reaction, ~20% other
# AI tends to do ~80% speaker, ~10% reaction, ~10% other
TARGET_REACTION_RATIO = 0.35  # 35% of dialogue scene should be reaction shots
MIN_REACTION_RATIO = 0.20     # Below 20% reaction = viewer discomfort


# ═══════════════════════════════════════════════════════════════════
# CROSS-SCENE RHYTHM — Alternate Scene Energy Levels
# ═══════════════════════════════════════════════════════════════════

# Scene "energy" types — 3 high-energy dialogue scenes in a row is exhausting
SCENE_ENERGY_TYPE = {
    "dialogue_heavy": "high",   # >60% shots have dialogue
    "action": "high",           # Action/chase/fight scenes
    "atmosphere": "low",        # Establishing, montage, environment
    "mixed": "medium",          # Balance of dialogue and visual
    "transition": "low",        # Brief connecting scenes
}

MAX_CONSECUTIVE_HIGH_ENERGY = 2  # After 2 high-energy scenes, need a breather


# ═══════════════════════════════════════════════════════════════════
# ENSEMBLE FAIRNESS — Every Named Character Gets Screen Time
# ═══════════════════════════════════════════════════════════════════

MIN_SCREEN_RATIO = 0.05  # Named characters should appear in at least 5% of shots
# (only applies to characters listed in cast_map, not extras)


# ═══════════════════════════════════════════════════════════════════
# VIEWER RETENTION ANALYZER — The Main Engine
# ═══════════════════════════════════════════════════════════════════

@dataclass
class ComfortViolation:
    """A single viewer comfort violation."""
    rule: str           # Which rule was violated
    severity: str       # "warning" or "critical"
    shot_id: str        # Which shot triggers the violation
    scene_id: str       # Which scene
    description: str    # Human-readable explanation
    fix_type: str       # "insert_break", "swap_order", "add_reaction", "flag_manual"
    fix_detail: str     # Specific fix recommendation


@dataclass
class SceneComfortReport:
    """Comfort analysis for one scene."""
    scene_id: str
    violations: List[ComfortViolation] = field(default_factory=list)
    cut_density: float = 0.0
    reaction_ratio: float = 0.0
    avg_emotion: float = 0.0
    energy_type: str = "mixed"
    dominant_character: str = ""
    max_consecutive_same_char: int = 0
    max_consecutive_peak_emotion: int = 0
    size_jump_violations: int = 0


class ViewerRetentionEngine:
    """
    Analyzes shot sequences for viewer comfort and flags violations.

    Runs AFTER V20.1 Story Intelligence — consumes _emotion_intensity
    and shot_type data to check for comfort violations.

    Does NOT auto-fix most issues (that would require reordering shots,
    which affects narrative). Instead, it:
    1. Writes comfort metadata to each shot (_comfort_* fields)
    2. Flags violations in a report
    3. Auto-inserts BREATHING ROOM markers where safe
    4. Adjusts duration hints for pacing comfort
    """

    def __init__(self, project_path: Path, genre: str = "",
                 story_bible: Dict = None, cast_map: Dict = None):
        self.project_path = Path(project_path)
        self.genre = genre.lower().strip().replace(" ", "_")
        self.story_bible = story_bible or {}
        self.cast_map = cast_map or {}

        # Get genre-appropriate cut density
        self.cut_density = GENRE_CUT_DENSITY.get(self.genre, DEFAULT_CUT_DENSITY)

    def analyze(self, dry_run: bool = False) -> Dict:
        """
        Run full viewer retention analysis on the project.
        Returns a report with violations and comfort scores.
        """
        sp_path = self.project_path / "shot_plan.json"
        if not sp_path.exists():
            return {"error": "shot_plan.json not found"}

        with open(sp_path) as f:
            shot_plan = json.load(f)

        shots = shot_plan if isinstance(shot_plan, list) else shot_plan.get("shots", [])

        # Group shots by scene
        scenes = {}
        for s in shots:
            sid = s.get("scene_id", "?")
            scenes.setdefault(sid, []).append(s)

        # Analyze each scene
        scene_reports = []
        all_violations = []
        total_fixes = 0

        for scene_id in sorted(scenes.keys()):
            scene_shots = scenes[scene_id]
            report = self._analyze_scene(scene_id, scene_shots)
            scene_reports.append(report)
            all_violations.extend(report.violations)

            # Apply non-destructive fixes (metadata only)
            if not dry_run:
                fixes = self._apply_comfort_metadata(scene_shots, report)
                # Camera movement enrichment (break static monotony)
                fixes += self._enrich_camera_movement(scene_shots)
                total_fixes += fixes

        # Cross-scene analysis
        cross_scene_violations = self._analyze_cross_scene(scene_reports)
        all_violations.extend(cross_scene_violations)

        # Ensemble fairness
        ensemble_violations = self._analyze_ensemble_fairness(shots)
        all_violations.extend(ensemble_violations)

        # Save fixes if not dry run
        if not dry_run and total_fixes > 0:
            with open(sp_path, "w") as f:
                json.dump(shot_plan, f, indent=2, default=str)
            logger.info(f"[RETENTION] Applied {total_fixes} comfort metadata fixes")

        # Compute overall comfort score (0-100)
        # Score is relative to total shots — a 300-shot film with 30 warnings
        # is much better than a 30-shot film with 30 warnings
        critical_count = sum(1 for v in all_violations if v.severity == "critical")
        warning_count = sum(1 for v in all_violations if v.severity == "warning")
        total = max(len(shots), 1)
        # Critical violations cost 3 points per occurrence (relative to shot count)
        # Warning violations cost 0.5 points per occurrence
        penalty = (critical_count * 3.0 + warning_count * 0.5) / total * 100
        comfort_score = max(0, min(100, int(100 - penalty)))

        return {
            "status": "dry_run" if dry_run else "applied",
            "comfort_score": comfort_score,
            "total_shots": len(shots),
            "total_scenes": len(scenes),
            "total_violations": len(all_violations),
            "critical_violations": critical_count,
            "warning_violations": warning_count,
            "fixes_applied": total_fixes,
            "genre": self.genre,
            "cut_density_target": self.cut_density["target"],
            "scenes": [
                {
                    "scene_id": r.scene_id,
                    "violations": len(r.violations),
                    "cut_density": round(r.cut_density, 2),
                    "reaction_ratio": round(r.reaction_ratio, 2),
                    "energy_type": r.energy_type,
                    "dominant_character": r.dominant_character,
                    "max_consecutive_same_char": r.max_consecutive_same_char,
                    "size_jump_violations": r.size_jump_violations,
                }
                for r in scene_reports
            ],
            "violations": [
                {
                    "rule": v.rule,
                    "severity": v.severity,
                    "shot_id": v.shot_id,
                    "scene_id": v.scene_id,
                    "description": v.description,
                    "fix_type": v.fix_type,
                    "fix_detail": v.fix_detail,
                }
                for v in all_violations
            ],
        }

    def _analyze_scene(self, scene_id: str, shots: List[Dict]) -> SceneComfortReport:
        """Analyze a single scene for all comfort violations."""
        report = SceneComfortReport(scene_id=scene_id)
        n = len(shots)
        if n == 0:
            return report

        # ── CHECK 1: Character Screen Time (Same Face Fatigue) ──
        self._check_character_fatigue(shots, report)

        # ── CHECK 2: Emotional Rhythm (Flatline + Peak Sustained) ──
        self._check_emotional_rhythm(shots, report)

        # ── CHECK 3: Shot Size Progression (Jarring Jumps) ──
        self._check_size_progression(shots, report)

        # ── CHECK 4: Dialogue/Reaction Ratio ──
        self._check_reaction_ratio(shots, report)

        # ── CHECK 5: Cut Density (Cognitive Overload) ──
        self._check_cut_density(shots, report)

        # ── CHECK 6: Location Staleness ──
        self._check_location_staleness(shots, report)

        # ── CHECK 7: Visual Monotony (same movement/lens repeated) ──
        self._check_visual_monotony(shots, report)

        # Determine scene energy type
        dialogue_ratio = sum(1 for s in shots if (s.get("dialogue_text", "") or "").strip()) / max(n, 1)
        avg_emotion = sum(s.get("_emotion_intensity", 4) for s in shots) / max(n, 1)
        report.avg_emotion = avg_emotion

        if dialogue_ratio > 0.6:
            report.energy_type = "dialogue_heavy"
        elif avg_emotion >= 6:
            report.energy_type = "action"
        elif n <= 3:
            report.energy_type = "transition"
        elif dialogue_ratio < 0.2 and avg_emotion < 4:
            report.energy_type = "atmosphere"
        else:
            report.energy_type = "mixed"

        return report

    # ─────────────────────────────────────────────────────────
    # CHECK 1: Character Screen Time Fatigue
    # ─────────────────────────────────────────────────────────

    def _check_character_fatigue(self, shots: List[Dict], report: SceneComfortReport):
        """Flag when the same character dominates too many consecutive shots."""
        consecutive = 0
        current_primary = ""
        char_counts = {}

        for i, shot in enumerate(shots):
            chars = shot.get("characters", [])
            if isinstance(chars, str):
                chars = [c.strip() for c in chars.split(",")]
            primary = chars[0].upper() if chars else ""
            if isinstance(primary, dict):
                primary = primary.get("name", "").upper()

            # Track overall counts
            if primary:
                char_counts[primary] = char_counts.get(primary, 0) + 1

            if primary == current_primary and primary != "":
                consecutive += 1
            else:
                consecutive = 1
                current_primary = primary

            if consecutive > MAX_CONSECUTIVE_SAME_CHAR:
                report.violations.append(ComfortViolation(
                    rule="CHARACTER_FATIGUE",
                    severity="warning",
                    shot_id=shot.get("shot_id", f"shot_{i}"),
                    scene_id=report.scene_id,
                    description=f"{current_primary} dominates {consecutive} consecutive shots — viewer needs a break",
                    fix_type="insert_break",
                    fix_detail=f"Insert a reaction shot, insert, or cutaway before shot {i} to break {current_primary}'s screen time streak",
                ))

            report.max_consecutive_same_char = max(report.max_consecutive_same_char, consecutive)

        # Track dominant character
        if char_counts:
            report.dominant_character = max(char_counts, key=char_counts.get)

    # ─────────────────────────────────────────────────────────
    # CHECK 2: Emotional Rhythm
    # ─────────────────────────────────────────────────────────

    def _check_emotional_rhythm(self, shots: List[Dict], report: SceneComfortReport):
        """Flag sustained peak emotion (no release) and emotional flatline."""
        peak_streak = 0
        flatline_streak = 0
        prev_intensity = None

        for i, shot in enumerate(shots):
            intensity = shot.get("_emotion_intensity", 4)

            # Peak sustained check
            if intensity >= 7:
                peak_streak += 1
            else:
                peak_streak = 0

            if peak_streak > MAX_PEAK_CONSECUTIVE:
                report.violations.append(ComfortViolation(
                    rule="EMOTIONAL_FATIGUE",
                    severity="warning",
                    shot_id=shot.get("shot_id", f"shot_{i}"),
                    scene_id=report.scene_id,
                    description=f"High emotion sustained for {peak_streak} shots — viewer needs a micro-release",
                    fix_type="add_breathing",
                    fix_detail=f"Reduce emotion intensity or add a neutral beat (look away, exhale, environmental detail) before shot {i}",
                ))

            report.max_consecutive_peak_emotion = max(report.max_consecutive_peak_emotion, peak_streak)

            # Flatline check (same intensity ±1 for too long)
            if prev_intensity is not None:
                if abs(intensity - prev_intensity) <= 1:
                    flatline_streak += 1
                else:
                    flatline_streak = 1
            else:
                flatline_streak = 1

            if flatline_streak > MAX_FLATLINE_CONSECUTIVE:
                report.violations.append(ComfortViolation(
                    rule="EMOTIONAL_FLATLINE",
                    severity="warning",
                    shot_id=shot.get("shot_id", f"shot_{i}"),
                    scene_id=report.scene_id,
                    description=f"Emotion flatlined at intensity ~{intensity} for {flatline_streak} shots — scene feels static",
                    fix_type="flag_manual",
                    fix_detail=f"Consider adding an emotional shift (surprise, pause, or escalation) around shot {i}",
                ))

            prev_intensity = intensity

    # ─────────────────────────────────────────────────────────
    # CHECK 3: Shot Size Progression (Jarring Jumps)
    # ─────────────────────────────────────────────────────────

    def _check_size_progression(self, shots: List[Dict], report: SceneComfortReport):
        """Flag uncomfortable size jumps between consecutive shots."""
        for i in range(1, len(shots)):
            prev_type = shots[i-1].get("shot_type", shots[i-1].get("type", "medium"))
            curr_type = shots[i].get("shot_type", shots[i].get("type", "medium"))

            prev_size = SHOT_SIZE_SCALE.get(prev_type, 4)
            curr_size = SHOT_SIZE_SCALE.get(curr_type, 4)

            jump = abs(curr_size - prev_size)
            direction = "tighten" if curr_size > prev_size else "widen"

            # Tightening is more comfortable than widening (natural escalation)
            threshold = MAX_COMFORTABLE_TIGHTEN if direction == "tighten" else MAX_COMFORTABLE_JUMP

            if jump > threshold:
                report.size_jump_violations += 1
                report.violations.append(ComfortViolation(
                    rule="SIZE_JUMP",
                    severity="critical" if jump > threshold + 2 else "warning",
                    shot_id=shots[i].get("shot_id", f"shot_{i}"),
                    scene_id=report.scene_id,
                    description=f"Jarring size jump: {prev_type}({prev_size}) → {curr_type}({curr_size}) = {jump} sizes ({direction})",
                    fix_type="insert_break",
                    fix_detail=f"Insert a medium or medium_wide transitional shot between shots {i-1} and {i} to smooth the cut",
                ))

    # ─────────────────────────────────────────────────────────
    # CHECK 4: Dialogue/Reaction Ratio
    # ─────────────────────────────────────────────────────────

    def _check_reaction_ratio(self, shots: List[Dict], report: SceneComfortReport):
        """Check if dialogue scenes have enough reaction shots."""
        dialogue_shots = [s for s in shots if (s.get("dialogue_text", "") or "").strip()]
        if len(dialogue_shots) < 3:
            # Not a dialogue-heavy scene, skip
            report.reaction_ratio = 1.0
            return

        # Count reaction/non-speaking shots in dialogue segments
        reaction_count = 0
        for s in shots:
            s_type = s.get("shot_type", s.get("type", ""))
            has_dialogue = bool((s.get("dialogue_text", "") or "").strip())
            if s_type == "reaction" or (not has_dialogue and s_type in ("close", "medium_close", "over_the_shoulder")):
                reaction_count += 1

        total_dialogue_segment = len(shots)  # All shots in scene contribute to rhythm
        ratio = reaction_count / max(total_dialogue_segment, 1)
        report.reaction_ratio = ratio

        if ratio < MIN_REACTION_RATIO:
            report.violations.append(ComfortViolation(
                rule="REACTION_DEFICIT",
                severity="critical",
                shot_id=shots[0].get("shot_id", ""),
                scene_id=report.scene_id,
                description=f"Reaction ratio {ratio:.0%} is below minimum {MIN_REACTION_RATIO:.0%} — viewer can't see the listener",
                fix_type="add_reaction",
                fix_detail=f"Add {max(1, int(total_dialogue_segment * TARGET_REACTION_RATIO) - reaction_count)} reaction shots showing listeners/non-speaking characters",
            ))
        elif ratio < TARGET_REACTION_RATIO:
            report.violations.append(ComfortViolation(
                rule="REACTION_LOW",
                severity="warning",
                shot_id=shots[0].get("shot_id", ""),
                scene_id=report.scene_id,
                description=f"Reaction ratio {ratio:.0%} below target {TARGET_REACTION_RATIO:.0%}",
                fix_type="add_reaction",
                fix_detail=f"Consider adding {max(1, int(total_dialogue_segment * TARGET_REACTION_RATIO) - reaction_count)} more reaction shots",
            ))

    # ─────────────────────────────────────────────────────────
    # CHECK 5: Cut Density (Cognitive Overload)
    # ─────────────────────────────────────────────────────────

    def _check_cut_density(self, shots: List[Dict], report: SceneComfortReport):
        """Check if cuts per minute exceed genre-appropriate ceiling."""
        total_duration = sum(s.get("duration", s.get("duration_seconds", 5)) for s in shots)
        if total_duration <= 0:
            return

        minutes = total_duration / 60.0
        cuts = len(shots) - 1  # N shots = N-1 cuts
        density = cuts / max(minutes, 0.1)
        report.cut_density = density

        if density > self.cut_density["max"]:
            report.violations.append(ComfortViolation(
                rule="CUT_OVERLOAD",
                severity="critical",
                shot_id=shots[0].get("shot_id", ""),
                scene_id=report.scene_id,
                description=f"Cut density {density:.1f} cuts/min exceeds genre max {self.cut_density['max']} ({self.genre or 'default'})",
                fix_type="extend_duration",
                fix_detail=f"Extend shot durations or merge some shots — target {self.cut_density['target']:.1f} cuts/min for {self.genre or 'this genre'}",
            ))
        elif density < self.cut_density["min"]:
            report.violations.append(ComfortViolation(
                rule="CUT_SPARSE",
                severity="warning",
                shot_id=shots[0].get("shot_id", ""),
                scene_id=report.scene_id,
                description=f"Cut density {density:.1f} cuts/min below genre min {self.cut_density['min']}",
                fix_type="flag_manual",
                fix_detail=f"Scene may feel sluggish — consider splitting long shots or adding cutaways",
            ))

    # ─────────────────────────────────────────────────────────
    # CHECK 6: Location Staleness
    # ─────────────────────────────────────────────────────────

    def _check_location_staleness(self, shots: List[Dict], report: SceneComfortReport):
        """Flag when the same background persists too long without visual break."""
        consecutive_same_location = 0
        current_location = ""

        for i, shot in enumerate(shots):
            loc = (shot.get("location", "") or "").strip()
            s_type = shot.get("shot_type", shot.get("type", ""))

            # Visual break types reset the staleness counter
            if s_type in LOCATION_BREAK_TYPES:
                consecutive_same_location = 0
                continue

            if loc == current_location and loc != "":
                consecutive_same_location += 1
            else:
                consecutive_same_location = 1
                current_location = loc

            if consecutive_same_location > MAX_SAME_LOCATION_SHOTS:
                report.violations.append(ComfortViolation(
                    rule="LOCATION_STALE",
                    severity="warning",
                    shot_id=shot.get("shot_id", f"shot_{i}"),
                    scene_id=report.scene_id,
                    description=f"Same location ({current_location[:30]}) for {consecutive_same_location} shots — background feels static",
                    fix_type="insert_break",
                    fix_detail=f"Insert a detail shot, insert, or brief establishing angle to refresh the visual around shot {i}",
                ))

    # ─────────────────────────────────────────────────────────
    # CHECK 7: Visual Monotony (Motion + Lens Repetition)
    # ─────────────────────────────────────────────────────────

    def _check_visual_monotony(self, shots: List[Dict], report: SceneComfortReport):
        """Flag when camera movement or lens type repeats too many times.
        NOTE: Default/generic values like 'static' or 'Cooke S7/i Prime' get a
        higher tolerance since they're pipeline defaults, not intentional choices.
        """
        prev_movement = ""
        prev_lens = ""
        movement_streak = 0
        lens_streak = 0

        # Default values get higher tolerance (they're pipeline defaults, not creative choices)
        DEFAULT_MOVEMENTS = {"static", "locked", "tripod", ""}
        DEFAULT_LENSES = {"cooke s7/i prime", "spherical", "prime", ""}

        for i, shot in enumerate(shots):
            movement = (shot.get("camera_style", "") or "").lower().strip()
            lens = (shot.get("lens_type", "") or "").lower().strip()

            # Movement repetition
            if movement and movement == prev_movement:
                movement_streak += 1
            else:
                movement_streak = 1
                prev_movement = movement

            # Higher threshold for defaults (8 vs 4)
            threshold = 8 if movement in DEFAULT_MOVEMENTS else 4
            if movement_streak > threshold and movement:
                report.violations.append(ComfortViolation(
                    rule="MOVEMENT_MONOTONY",
                    severity="warning",
                    shot_id=shot.get("shot_id", f"shot_{i}"),
                    scene_id=report.scene_id,
                    description=f"Same camera movement '{movement}' for {movement_streak} shots — visually repetitive",
                    fix_type="flag_manual",
                    fix_detail=f"Vary camera movement — try handheld, dolly, or slow push to break the pattern",
                ))

            # Lens repetition
            if lens and lens == prev_lens:
                lens_streak += 1
            else:
                lens_streak = 1
                prev_lens = lens

            # Higher threshold for defaults (10 vs 5)
            threshold = 10 if lens in DEFAULT_LENSES else 5
            if lens_streak > threshold and lens:
                report.violations.append(ComfortViolation(
                    rule="LENS_MONOTONY",
                    severity="warning",
                    shot_id=shot.get("shot_id", f"shot_{i}"),
                    scene_id=report.scene_id,
                    description=f"Same lens '{lens}' for {lens_streak} shots — depth of field becomes invisible",
                    fix_type="flag_manual",
                    fix_detail=f"Vary focal length to create visual rhythm — alternate tight/wide for depth perception",
                ))

    # ─────────────────────────────────────────────────────────
    # CROSS-SCENE ANALYSIS
    # ─────────────────────────────────────────────────────────

    def _analyze_cross_scene(self, scene_reports: List[SceneComfortReport]) -> List[ComfortViolation]:
        """Check for cross-scene fatigue (too many high-energy scenes in a row)."""
        violations = []
        high_energy_streak = 0

        for i, report in enumerate(scene_reports):
            energy = SCENE_ENERGY_TYPE.get(report.energy_type, "medium")
            if energy == "high":
                high_energy_streak += 1
            else:
                high_energy_streak = 0

            if high_energy_streak > MAX_CONSECUTIVE_HIGH_ENERGY:
                violations.append(ComfortViolation(
                    rule="CROSS_SCENE_FATIGUE",
                    severity="warning",
                    shot_id="",
                    scene_id=report.scene_id,
                    description=f"{high_energy_streak} consecutive high-energy scenes — viewer needs a visual/emotional breather",
                    fix_type="flag_manual",
                    fix_detail=f"Consider adding an atmospheric or transitional scene before scene {report.scene_id} to let the viewer recover",
                ))

        return violations

    # ─────────────────────────────────────────────────────────
    # ENSEMBLE FAIRNESS
    # ─────────────────────────────────────────────────────────

    def _analyze_ensemble_fairness(self, shots: List[Dict]) -> List[ComfortViolation]:
        """Check that named cast members get minimum screen time."""
        violations = []
        if not self.cast_map:
            return violations

        total = len(shots)
        if total < 10:
            return violations

        # Count appearances per character (skip metadata keys like _approved_at)
        appearances = {}
        for char_name in self.cast_map:
            if char_name.startswith("_") or not isinstance(self.cast_map[char_name], dict):
                continue
            appearances[char_name.upper()] = 0

        for shot in shots:
            chars = shot.get("characters", [])
            if isinstance(chars, str):
                chars = [c.strip() for c in chars.split(",")]
            for c in chars:
                name = c.upper() if isinstance(c, str) else (c.get("name", "") if isinstance(c, dict) else "").upper()
                if name in appearances:
                    appearances[name] += 1

        # Check each named character
        for char_name, count in appearances.items():
            ratio = count / total
            if ratio < MIN_SCREEN_RATIO and count == 0:
                violations.append(ComfortViolation(
                    rule="ENSEMBLE_ABSENT",
                    severity="warning",
                    shot_id="",
                    scene_id="ALL",
                    description=f"{char_name} appears in 0 shots — named cast member completely absent",
                    fix_type="flag_manual",
                    fix_detail=f"Add at least one establishing or reaction shot featuring {char_name}",
                ))

        return violations

    # ─────────────────────────────────────────────────────────
    # COMFORT METADATA APPLICATION (Non-Destructive)
    # ─────────────────────────────────────────────────────────

    # ─────────────────────────────────────────────────────────
    # CAMERA MOVEMENT ENRICHMENT — Break Static Monotony
    # ─────────────────────────────────────────────────────────

    def _enrich_camera_movement(self, shots: List[Dict]) -> int:
        """
        Break camera movement monotony by assigning motivated movement types.
        Only changes shots that are currently 'static' and would benefit from motion.

        Real movies use camera movement to:
        - Follow action (tracking, dolly)
        - Reveal information (crane, pan)
        - Build tension (slow push, creep)
        - Create intimacy (handheld)
        - Show power (low angle crane up, high angle push down)

        This assigns movement MOTIVATIONS, not random variety.
        """
        fixes = 0
        prev_movement = ""
        static_streak = 0

        # Movement vocabulary by shot context
        MOVEMENT_BY_CONTEXT = {
            "establishing": ["slow_crane", "drone_approach", "slow_pan", "static"],
            "wide": ["slow_dolly", "slow_pan", "static", "crane"],
            "medium": ["static", "slow_push", "handheld_subtle", "dolly_in"],
            "medium_close": ["slow_push", "static", "handheld_subtle"],
            "close": ["static", "micro_push", "handheld_breath"],
            "extreme_close": ["static", "micro_drift"],
            "reaction": ["static", "whip_pan", "snap_focus"],
            "over_the_shoulder": ["static", "slow_orbit", "dolly_lateral"],
            "two_shot": ["slow_dolly", "static", "handheld_subtle"],
            "tracking": ["dolly_forward", "steadicam", "tracking"],
            "insert": ["static", "slow_push", "rack_focus"],
            "detail": ["macro_drift", "static", "slow_tilt"],
            "pov": ["handheld", "steadicam_low", "dutch_drift"],
        }

        # Emotion-driven movement overrides
        EMOTION_MOVEMENT = {
            # High emotion → more intimate/urgent movement
            "high": ["handheld_subtle", "slow_push", "micro_drift"],
            # Tension → creeping, slow push
            "tension": ["creep_forward", "slow_push", "static_locked"],
            # Resolution → pull back, breathe
            "release": ["slow_pullback", "crane_up", "static"],
        }

        for i, shot in enumerate(shots):
            current_movement = (shot.get("camera_style", "") or "").lower().strip()

            if current_movement == "static":
                static_streak += 1
            else:
                static_streak = 0

            # Only change if we're in a static streak > 3 AND it would be motivated
            if static_streak <= 3 or current_movement != "static":
                continue

            s_type = shot.get("shot_type", shot.get("type", "medium"))
            intensity = shot.get("_emotion_intensity", 4)

            # Get context-appropriate movements
            options = MOVEMENT_BY_CONTEXT.get(s_type, ["static"])

            # Emotion override
            if intensity >= 7:
                options = EMOTION_MOVEMENT["high"] + options[:1]
            elif intensity >= 5:
                options = EMOTION_MOVEMENT["tension"] + options[:1]
            elif intensity <= 2 and i > 0:
                prev_intensity = shots[i-1].get("_emotion_intensity", 4)
                if prev_intensity >= 6:
                    options = EMOTION_MOVEMENT["release"] + options[:1]

            # Pick a non-static option if available (cycle through to avoid same one)
            non_static = [o for o in options if o != "static"]
            if non_static:
                pick = non_static[i % len(non_static)]
                shot["_comfort_camera_movement"] = pick
                fixes += 1
                static_streak = 0  # Reset streak after fix

        return fixes

    def _apply_comfort_metadata(self, shots: List[Dict], report: SceneComfortReport) -> int:
        """
        Write comfort metadata to shots for downstream consumption.
        This does NOT change shot types or reorder — it adds hints.

        Metadata written:
        - _comfort_breathing_needed: True if a breathing shot should precede this
        - _comfort_size_from: Previous shot's size scale value
        - _comfort_size_to: This shot's size scale value
        - _comfort_size_jump: How many sizes this cut jumps
        - _comfort_duration_hint: Suggested duration adjustment (+/- seconds)
        - _comfort_score: Per-shot comfort score (0-10)
        """
        fixes = 0

        for i, shot in enumerate(shots):
            # Size progression metadata
            curr_type = shot.get("shot_type", shot.get("type", "medium"))
            curr_size = SHOT_SIZE_SCALE.get(curr_type, 4)

            if i > 0:
                prev_type = shots[i-1].get("shot_type", shots[i-1].get("type", "medium"))
                prev_size = SHOT_SIZE_SCALE.get(prev_type, 4)
                jump = abs(curr_size - prev_size)

                shot["_comfort_size_from"] = prev_size
                shot["_comfort_size_to"] = curr_size
                shot["_comfort_size_jump"] = jump

                # Flag shots that need a breathing transition before them
                if jump > MAX_COMFORTABLE_JUMP:
                    shot["_comfort_breathing_needed"] = True
                    fixes += 1

            # Emotional pacing: if we're in a peak streak, hint at micro-release
            intensity = shot.get("_emotion_intensity", 4)
            if i >= MAX_PEAK_CONSECUTIVE:
                recent = [shots[j].get("_emotion_intensity", 4) for j in range(max(0, i - MAX_PEAK_CONSECUTIVE), i)]
                if all(r >= 7 for r in recent) and intensity >= 7:
                    shot["_comfort_needs_release"] = True
                    # Hint: extend this shot slightly for a "breathing" moment
                    shot["_comfort_duration_hint"] = "+1.5"
                    fixes += 1

            # Duration comfort: very short shots (<3s) in slow genres should be extended
            duration = shot.get("duration", shot.get("duration_seconds", 5))
            if duration < 3 and self.genre in ("drama", "gothic_horror", "period", "noir"):
                shot["_comfort_duration_hint"] = shot.get("_comfort_duration_hint", "+1")
                fixes += 1

            # Duration comfort: very long shots (>12s) without dialogue should be trimmed
            has_dialogue = bool((shot.get("dialogue_text", "") or "").strip())
            if duration > 12 and not has_dialogue and curr_type not in ("establishing", "wide"):
                shot["_comfort_duration_hint"] = shot.get("_comfort_duration_hint", "-2")
                fixes += 1

            # Per-shot comfort score (0-10, 10 = perfectly comfortable)
            score = 10
            if shot.get("_comfort_breathing_needed"):
                score -= 3
            if shot.get("_comfort_needs_release"):
                score -= 2
            if i > 0:
                jump = shot.get("_comfort_size_jump", 0)
                if jump > MAX_COMFORTABLE_JUMP:
                    score -= min(3, jump - MAX_COMFORTABLE_JUMP)
            shot["_comfort_score"] = max(0, score)

        return fixes


# ═══════════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════════

def analyze_viewer_retention(project_path: Path, genre: str = "",
                              story_bible: Dict = None, cast_map: Dict = None,
                              dry_run: bool = False) -> Dict:
    """
    Run viewer retention analysis on a project's shot plan.
    Call this AFTER V20.1 Story Intelligence.

    Args:
        project_path: Path to pipeline_outputs/{project}
        genre: Genre string (e.g., "gothic_horror", "action", "drama")
        story_bible: Story bible data
        cast_map: Cast map data
        dry_run: If True, don't write comfort metadata

    Returns:
        Dict with comfort_score, violations, scene reports
    """
    engine = ViewerRetentionEngine(project_path, genre, story_bible, cast_map)
    return engine.analyze(dry_run=dry_run)
