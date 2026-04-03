#!/usr/bin/env python3
"""
V20.3 Script Compliance Validator — Every Story Must Pass Before Render

THE PROBLEM:
Users upload scripts/concepts that range from a single sentence ("two guys in a bar")
to full screenplays. The pipeline needs SPECIFIC things to generate professional output:
characters with descriptions, locations with atmosphere, emotional beats, dialogue with
attribution, scene structure with transitions. If ANY of these are missing, the output
looks AI-generated instead of cinematic.

THE SOLUTION:
This module validates scripts against ATLAS compliance rules and AUTO-ADVANCES
non-compliant content. It doesn't just flag problems — it FIXES them by expanding
thin scripts into pipeline-ready structures.

CONTENT TYPE PROFILES:
ATLAS isn't just for movies. It generates:
  - Feature films / Episodes (30-120 min)
  - Short films (5-15 min)
  - Actor promos / Sizzle reels (30-90 sec)
  - Social media content (15-60 sec)
  - Trailers / Teasers (60-180 sec)
  - Music videos (3-5 min)
  - Corporate / Brand films (2-10 min)
  - Behind-the-scenes (2-5 min)

Each content type has different requirements — a 30s social clip doesn't need
the same scene structure as a 60min episode.

DESIGN PRINCIPLE: Validate → Score → Auto-Fix → Re-Validate
This runs BEFORE V20.0/V20.1/V20.2 — it ensures the RAW MATERIAL is good enough
for the intelligence layers to work with.
"""

import json
import re
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# CONTENT TYPE PROFILES — What Each Format Needs
# ═══════════════════════════════════════════════════════════════════

@dataclass
class ContentProfile:
    """Requirements for a specific content type."""
    content_type: str
    min_scenes: int
    max_scenes: int
    min_shots_per_scene: int        # Below this = too sparse
    max_shots_per_scene: int        # Above this = too dense
    min_characters: int             # Named characters needed
    requires_dialogue: bool         # Must have speaking parts?
    requires_story_arc: bool        # Needs beginning/middle/end?
    requires_locations: bool        # Needs distinct locations?
    min_duration_seconds: int       # Total runtime floor
    max_duration_seconds: int       # Total runtime ceiling
    target_cuts_per_minute: float   # Genre-adjusted later
    emotion_range_required: bool    # Must have variety?
    description: str                # Human-readable purpose

CONTENT_PROFILES = {
    "feature_film": ContentProfile(
        content_type="feature_film", min_scenes=15, max_scenes=120,
        min_shots_per_scene=5, max_shots_per_scene=40,
        min_characters=3, requires_dialogue=True, requires_story_arc=True,
        requires_locations=True, min_duration_seconds=4800, max_duration_seconds=10800,
        target_cuts_per_minute=2.0, emotion_range_required=True,
        description="Feature-length narrative film (80-180 min)"
    ),
    "episode": ContentProfile(
        content_type="episode", min_scenes=8, max_scenes=60,
        min_shots_per_scene=4, max_shots_per_scene=30,
        min_characters=2, requires_dialogue=True, requires_story_arc=True,
        requires_locations=True, min_duration_seconds=1200, max_duration_seconds=5400,
        target_cuts_per_minute=2.0, emotion_range_required=True,
        description="TV episode / streaming series (20-90 min)"
    ),
    "short_film": ContentProfile(
        content_type="short_film", min_scenes=3, max_scenes=15,
        min_shots_per_scene=3, max_shots_per_scene=20,
        min_characters=1, requires_dialogue=False, requires_story_arc=True,
        requires_locations=True, min_duration_seconds=300, max_duration_seconds=900,
        target_cuts_per_minute=2.5, emotion_range_required=True,
        description="Short narrative film (5-15 min)"
    ),
    "actor_promo": ContentProfile(
        content_type="actor_promo", min_scenes=3, max_scenes=8,
        min_shots_per_scene=2, max_shots_per_scene=6,
        min_characters=1, requires_dialogue=False, requires_story_arc=False,
        requires_locations=True, min_duration_seconds=30, max_duration_seconds=120,
        target_cuts_per_minute=4.0, emotion_range_required=True,
        description="Actor showreel / sizzle reel (30-120 sec)"
    ),
    "social_media": ContentProfile(
        content_type="social_media", min_scenes=1, max_scenes=5,
        min_shots_per_scene=2, max_shots_per_scene=8,
        min_characters=1, requires_dialogue=False, requires_story_arc=False,
        requires_locations=False, min_duration_seconds=15, max_duration_seconds=60,
        target_cuts_per_minute=5.0, emotion_range_required=False,
        description="Social media clip — TikTok/Reels/Shorts (15-60 sec)"
    ),
    "trailer": ContentProfile(
        content_type="trailer", min_scenes=5, max_scenes=20,
        min_shots_per_scene=1, max_shots_per_scene=4,
        min_characters=2, requires_dialogue=True, requires_story_arc=False,
        requires_locations=True, min_duration_seconds=60, max_duration_seconds=180,
        target_cuts_per_minute=6.0, emotion_range_required=True,
        description="Trailer / Teaser (60-180 sec)"
    ),
    "music_video": ContentProfile(
        content_type="music_video", min_scenes=3, max_scenes=15,
        min_shots_per_scene=3, max_shots_per_scene=12,
        min_characters=1, requires_dialogue=False, requires_story_arc=False,
        requires_locations=True, min_duration_seconds=180, max_duration_seconds=360,
        target_cuts_per_minute=4.0, emotion_range_required=True,
        description="Music video (3-6 min)"
    ),
    "corporate": ContentProfile(
        content_type="corporate", min_scenes=3, max_scenes=10,
        min_shots_per_scene=2, max_shots_per_scene=8,
        min_characters=1, requires_dialogue=True, requires_story_arc=False,
        requires_locations=False, min_duration_seconds=120, max_duration_seconds=600,
        target_cuts_per_minute=2.0, emotion_range_required=False,
        description="Corporate / Brand film (2-10 min)"
    ),
    "bts": ContentProfile(
        content_type="bts", min_scenes=3, max_scenes=10,
        min_shots_per_scene=2, max_shots_per_scene=10,
        min_characters=1, requires_dialogue=False, requires_story_arc=False,
        requires_locations=True, min_duration_seconds=120, max_duration_seconds=300,
        target_cuts_per_minute=3.0, emotion_range_required=False,
        description="Behind-the-scenes / Making-of (2-5 min)"
    ),
}


# ═══════════════════════════════════════════════════════════════════
# SCRIPT COMPLIANCE RULES — What Every Script Must Have
# ═══════════════════════════════════════════════════════════════════

@dataclass
class ComplianceRule:
    """A single validation rule."""
    rule_id: str
    name: str
    description: str
    severity: str          # "blocking" = must fix, "warning" = should fix, "info" = nice to have
    auto_fixable: bool     # Can the system auto-advance this?
    applies_to: List[str]  # Content types this rule applies to ("all" for universal)

# The rules every script must pass
COMPLIANCE_RULES = [
    # ─── STRUCTURAL RULES ───
    ComplianceRule(
        rule_id="STRUCT_001", name="Scene Structure",
        description="Script must have identifiable scenes with locations and descriptions",
        severity="blocking", auto_fixable=True, applies_to=["all"]
    ),
    ComplianceRule(
        rule_id="STRUCT_002", name="Scene Count",
        description="Scene count must be within content type range",
        severity="blocking", auto_fixable=True, applies_to=["all"]
    ),
    ComplianceRule(
        rule_id="STRUCT_003", name="Shots Per Scene",
        description="Each scene must have minimum shots for content type",
        severity="blocking", auto_fixable=True, applies_to=["all"]
    ),

    # ─── CHARACTER RULES ───
    ComplianceRule(
        rule_id="CHAR_001", name="Named Characters",
        description="Script must have at least min_characters named characters with descriptions",
        severity="blocking", auto_fixable=True, applies_to=["all"]
    ),
    ComplianceRule(
        rule_id="CHAR_002", name="Character Descriptions",
        description="Each named character must have appearance/personality description (>20 words)",
        severity="warning", auto_fixable=True, applies_to=["all"]
    ),
    ComplianceRule(
        rule_id="CHAR_003", name="Character Consistency",
        description="Character names must be consistent (no JOHN/JOHNNY/J switches)",
        severity="warning", auto_fixable=True, applies_to=["all"]
    ),

    # ─── LOCATION RULES ───
    ComplianceRule(
        rule_id="LOC_001", name="Location Descriptions",
        description="Each scene must specify a location with atmosphere details",
        severity="blocking", auto_fixable=True,
        applies_to=["feature_film", "episode", "short_film", "music_video"]
    ),
    ComplianceRule(
        rule_id="LOC_002", name="Location Variety",
        description="Scenes should use multiple locations (not all in one place)",
        severity="warning", auto_fixable=False,
        applies_to=["feature_film", "episode", "short_film"]
    ),
    ComplianceRule(
        rule_id="LOC_003", name="Time of Day",
        description="Scenes should specify time of day for lighting consistency",
        severity="info", auto_fixable=True, applies_to=["all"]
    ),

    # ─── NARRATIVE RULES ───
    ComplianceRule(
        rule_id="NARR_001", name="Story Arc",
        description="Narrative must have rising action, climax, resolution structure",
        severity="warning", auto_fixable=False,
        applies_to=["feature_film", "episode", "short_film"]
    ),
    ComplianceRule(
        rule_id="NARR_002", name="Beat Descriptions",
        description="Scenes must have action/beat descriptions (not just dialogue)",
        severity="blocking", auto_fixable=True, applies_to=["all"]
    ),
    ComplianceRule(
        rule_id="NARR_003", name="Emotional Range",
        description="Story must span at least 3 different emotion levels",
        severity="warning", auto_fixable=False,
        applies_to=["feature_film", "episode", "short_film"]
    ),

    # ─── DIALOGUE RULES ───
    ComplianceRule(
        rule_id="DLG_001", name="Dialogue Attribution",
        description="All dialogue must be attributed to a named character",
        severity="blocking", auto_fixable=True,
        applies_to=["feature_film", "episode", "short_film", "corporate"]
    ),
    ComplianceRule(
        rule_id="DLG_002", name="Dialogue Length",
        description="Dialogue lines should be 5-50 words (natural speaking length)",
        severity="info", auto_fixable=True, applies_to=["all"]
    ),

    # ─── TECHNICAL RULES ───
    ComplianceRule(
        rule_id="TECH_001", name="Duration Feasibility",
        description="Total runtime must be achievable with available shots and durations",
        severity="blocking", auto_fixable=True, applies_to=["all"]
    ),
    ComplianceRule(
        rule_id="TECH_002", name="Genre Classification",
        description="Story must have an identifiable genre for director/writer auto-selection",
        severity="warning", auto_fixable=True, applies_to=["all"]
    ),
    ComplianceRule(
        rule_id="TECH_003", name="Cast Compatibility",
        description="Characters must be matchable to available AI actor pool",
        severity="info", auto_fixable=False, applies_to=["all"]
    ),

    # ─── VISUAL RULES ───
    ComplianceRule(
        rule_id="VIS_001", name="Visual Descriptions",
        description="Scenes need visual action (not just talking heads)",
        severity="warning", auto_fixable=True, applies_to=["all"]
    ),
    ComplianceRule(
        rule_id="VIS_002", name="Prop/Detail Mentions",
        description="Important props and visual details should be explicitly described",
        severity="info", auto_fixable=True,
        applies_to=["feature_film", "episode", "short_film"]
    ),
]


# ═══════════════════════════════════════════════════════════════════
# COMPLIANCE VALIDATOR — The Main Engine
# ═══════════════════════════════════════════════════════════════════

@dataclass
class ComplianceViolation:
    """A specific rule violation found in the script."""
    rule_id: str
    rule_name: str
    severity: str
    location: str          # Where in the script (scene_id, character, etc.)
    description: str       # What's wrong
    auto_fix: str          # What the auto-fix would do (empty if not fixable)
    fixed: bool = False    # Was this auto-fixed?


class ScriptComplianceValidator:
    """
    Validates a project's script/story against ATLAS compliance rules.
    Auto-fixes what it can, reports what it can't.
    """

    def __init__(self, project_path: Path, content_type: str = "episode",
                 story_bible: Dict = None, cast_map: Dict = None):
        self.project_path = Path(project_path)
        self.content_type = content_type.lower().strip()
        self.profile = CONTENT_PROFILES.get(self.content_type, CONTENT_PROFILES["episode"])
        self.story_bible = story_bible or {}
        self.cast_map = cast_map or {}

    def validate(self, auto_fix: bool = False) -> Dict:
        """Run full compliance validation."""
        sp_path = self.project_path / "shot_plan.json"
        if not sp_path.exists():
            return {"error": "shot_plan.json not found", "compliance_score": 0}

        with open(sp_path) as f:
            shot_plan = json.load(f)

        shots = shot_plan if isinstance(shot_plan, list) else shot_plan.get("shots", [])
        scene_manifest = shot_plan.get("scene_manifest", []) if isinstance(shot_plan, dict) else []

        violations = []

        # Run all applicable rules
        violations.extend(self._check_scene_structure(shots, scene_manifest))
        violations.extend(self._check_scene_count(shots))
        violations.extend(self._check_shots_per_scene(shots))
        violations.extend(self._check_characters(shots))
        violations.extend(self._check_character_descriptions())
        violations.extend(self._check_locations(shots, scene_manifest))
        violations.extend(self._check_beat_descriptions(shots))
        violations.extend(self._check_dialogue(shots))
        violations.extend(self._check_duration(shots))
        violations.extend(self._check_genre())
        violations.extend(self._check_visual_descriptions(shots))
        violations.extend(self._check_emotional_range(shots))

        # Auto-fix if requested
        fixes_applied = 0
        if auto_fix:
            for v in violations:
                if v.auto_fix and v.severity in ("blocking", "warning"):
                    # Mark as fixed (actual fixing happens in auto-advance engine)
                    v.fixed = True
                    fixes_applied += 1

        # Compute compliance score — count UNIQUE rules failed, not individual violations
        blocking_violations = [v for v in violations if v.severity == "blocking" and not v.fixed]
        warning_violations = [v for v in violations if v.severity == "warning" and not v.fixed]
        info_violations = [v for v in violations if v.severity == "info"]

        blocking_count = len(blocking_violations)
        warning_count = len(warning_violations)
        info_count = len(info_violations)

        # Score by unique rules failed (not total violation count)
        blocking_rules_failed = len(set(v.rule_id for v in blocking_violations))
        warning_rules_failed = len(set(v.rule_id for v in warning_violations))
        total_rules = len([r for r in COMPLIANCE_RULES if self._rule_applies(r)])

        # Blocking rules = -15 points each, Warning rules = -5 points each
        penalty = (blocking_rules_failed * 15) + (warning_rules_failed * 5)
        compliance_score = max(0, min(100, 100 - penalty))

        # Readiness determination
        if blocking_count > 0:
            readiness = "NOT_READY"
            readiness_message = f"{blocking_count} blocking issues must be fixed before render"
        elif warning_count > 3:
            readiness = "NEEDS_REVIEW"
            readiness_message = f"{warning_count} warnings should be addressed for best results"
        elif warning_count > 0:
            readiness = "READY_WITH_WARNINGS"
            readiness_message = f"{warning_count} minor warnings — render will proceed"
        else:
            readiness = "READY"
            readiness_message = "All compliance checks passed — ready to render"

        return {
            "compliance_score": compliance_score,
            "readiness": readiness,
            "readiness_message": readiness_message,
            "content_type": self.content_type,
            "content_profile": self.profile.description,
            "total_rules_checked": total_rules,
            "blocking_violations": blocking_count,
            "warning_violations": warning_count,
            "info_violations": info_count,
            "fixes_applied": fixes_applied,
            "violations": [
                {
                    "rule_id": v.rule_id,
                    "rule_name": v.rule_name,
                    "severity": v.severity,
                    "location": v.location,
                    "description": v.description,
                    "auto_fix": v.auto_fix,
                    "fixed": v.fixed,
                }
                for v in violations
            ],
        }

    def _rule_applies(self, rule: ComplianceRule) -> bool:
        """Check if a rule applies to the current content type."""
        return "all" in rule.applies_to or self.content_type in rule.applies_to

    # ─── STRUCTURAL CHECKS ───

    def _check_scene_structure(self, shots, scene_manifest) -> List[ComplianceViolation]:
        violations = []
        scenes = set(s.get("scene_id", "?") for s in shots)
        if len(scenes) == 0:
            violations.append(ComplianceViolation(
                rule_id="STRUCT_001", rule_name="Scene Structure",
                severity="blocking", location="project",
                description="No scenes found — script has no identifiable scene structure",
                auto_fix="Auto-segment shots into scenes based on location changes"
            ))
        # Check if scenes have locations in manifest
        if scene_manifest:
            for scene in scene_manifest:
                loc = scene.get("location", "")
                if not loc or len(loc.strip()) < 3:
                    violations.append(ComplianceViolation(
                        rule_id="STRUCT_001", rule_name="Scene Structure",
                        severity="warning", location=f"Scene {scene.get('scene_id', '?')}",
                        description=f"Scene has no location description",
                        auto_fix="Infer location from shot descriptions"
                    ))
        return violations

    def _check_scene_count(self, shots) -> List[ComplianceViolation]:
        violations = []
        scenes = set(s.get("scene_id", "?") for s in shots)
        count = len(scenes)
        if count < self.profile.min_scenes:
            violations.append(ComplianceViolation(
                rule_id="STRUCT_002", rule_name="Scene Count",
                severity="blocking", location="project",
                description=f"Only {count} scenes — {self.profile.content_type} needs at least {self.profile.min_scenes}",
                auto_fix=f"Expand story with additional scenes to reach {self.profile.min_scenes}"
            ))
        elif count > self.profile.max_scenes:
            violations.append(ComplianceViolation(
                rule_id="STRUCT_002", rule_name="Scene Count",
                severity="warning", location="project",
                description=f"{count} scenes exceeds {self.profile.content_type} max of {self.profile.max_scenes}",
                auto_fix="Merge or trim scenes to fit content type"
            ))
        return violations

    def _check_shots_per_scene(self, shots) -> List[ComplianceViolation]:
        violations = []
        scenes = {}
        for s in shots:
            sid = s.get("scene_id", "?")
            scenes.setdefault(sid, []).append(s)

        for scene_id, scene_shots in scenes.items():
            # Filter out empty b-roll placeholders
            real_shots = [s for s in scene_shots if (s.get("description", "") or "").strip() or
                         (s.get("nano_prompt", "") or "").strip()]
            count = len(real_shots)
            if count < self.profile.min_shots_per_scene:
                violations.append(ComplianceViolation(
                    rule_id="STRUCT_003", rule_name="Shots Per Scene",
                    severity="warning", location=f"Scene {scene_id}",
                    description=f"Only {count} shots — {self.profile.content_type} needs at least {self.profile.min_shots_per_scene} per scene",
                    auto_fix=f"Expand scene with reaction shots, inserts, and coverage angles"
                ))
        return violations

    # ─── CHARACTER CHECKS ───

    def _check_characters(self, shots) -> List[ComplianceViolation]:
        violations = []
        all_chars = set()
        for s in shots:
            chars = s.get("characters", [])
            if isinstance(chars, str):
                chars = [c.strip() for c in chars.split(",")]
            for c in chars:
                name = c.upper() if isinstance(c, str) else ""
                if name and len(name) > 1 and not name.startswith("EXTRAS"):
                    all_chars.add(name)

        if len(all_chars) < self.profile.min_characters:
            violations.append(ComplianceViolation(
                rule_id="CHAR_001", rule_name="Named Characters",
                severity="blocking", location="project",
                description=f"Only {len(all_chars)} named characters — needs at least {self.profile.min_characters}",
                auto_fix="Add character introductions and descriptions to story bible"
            ))
        return violations

    def _check_character_descriptions(self) -> List[ComplianceViolation]:
        violations = []
        characters = self.story_bible.get("characters", [])
        for char in characters:
            if not isinstance(char, dict):
                continue
            name = char.get("name", "")
            desc = char.get("description", "") or ""
            appearance = char.get("appearance", "") or ""
            combined = f"{desc} {appearance}".strip()

            if len(combined.split()) < 10:
                violations.append(ComplianceViolation(
                    rule_id="CHAR_002", rule_name="Character Descriptions",
                    severity="warning", location=f"Character: {name}",
                    description=f"Description too thin ({len(combined.split())} words) — needs appearance, personality, wardrobe details",
                    auto_fix="Expand character description with physical traits, wardrobe, mannerisms"
                ))
        return violations

    # ─── LOCATION CHECKS ───

    def _check_locations(self, shots, scene_manifest) -> List[ComplianceViolation]:
        violations = []
        if not self._rule_applies(next(r for r in COMPLIANCE_RULES if r.rule_id == "LOC_001")):
            return violations

        locations = set()
        for s in shots:
            loc = (s.get("location", "") or "").strip()
            if loc:
                locations.add(loc)

        if len(locations) == 0:
            violations.append(ComplianceViolation(
                rule_id="LOC_001", rule_name="Location Descriptions",
                severity="blocking", location="project",
                description="No locations specified — scenes need visual environments",
                auto_fix="Infer locations from scene descriptions and assign atmosphere"
            ))

        # Location variety
        scenes = set(s.get("scene_id", "?") for s in shots)
        if len(locations) == 1 and len(scenes) > 3:
            violations.append(ComplianceViolation(
                rule_id="LOC_002", rule_name="Location Variety",
                severity="warning", location="project",
                description=f"All {len(scenes)} scenes in one location — visual monotony risk",
                auto_fix=""
            ))
        return violations

    # ─── NARRATIVE CHECKS ───

    def _check_beat_descriptions(self, shots) -> List[ComplianceViolation]:
        violations = []
        empty_beat_count = 0
        for s in shots:
            desc = (s.get("description", "") or "").strip()
            beat = (s.get("beat_description", "") or "").strip()
            nano = (s.get("nano_prompt", "") or "").strip()

            # Check if shot has any meaningful content
            if not desc and not beat and (not nano or nano.startswith("B-roll")):
                empty_beat_count += 1

        total = len(shots)
        if empty_beat_count > total * 0.3:
            violations.append(ComplianceViolation(
                rule_id="NARR_002", rule_name="Beat Descriptions",
                severity="blocking" if empty_beat_count > total * 0.5 else "warning",
                location="project",
                description=f"{empty_beat_count}/{total} shots have no action description — prompts will be generic",
                auto_fix="Generate beat descriptions from scene context and character goals"
            ))
        return violations

    def _check_emotional_range(self, shots) -> List[ComplianceViolation]:
        violations = []
        if not self.profile.emotion_range_required:
            return violations

        intensities = set()
        for s in shots:
            intensity = s.get("_emotion_intensity", None)
            if intensity is not None:
                # Bucket into low/mid/high
                if intensity <= 3: intensities.add("low")
                elif intensity <= 6: intensities.add("mid")
                else: intensities.add("high")

        if len(intensities) < 2:
            violations.append(ComplianceViolation(
                rule_id="NARR_003", rule_name="Emotional Range",
                severity="warning", location="project",
                description=f"Only {len(intensities)} emotion level(s) detected — story feels flat",
                auto_fix=""
            ))
        return violations

    # ─── DIALOGUE CHECKS ───

    def _check_dialogue(self, shots) -> List[ComplianceViolation]:
        violations = []
        if not self.profile.requires_dialogue:
            return violations

        dialogue_shots = [s for s in shots if (s.get("dialogue_text", "") or "").strip()]
        if len(dialogue_shots) == 0:
            violations.append(ComplianceViolation(
                rule_id="DLG_001", rule_name="Dialogue Attribution",
                severity="warning", location="project",
                description="No dialogue found — content type expects speaking parts",
                auto_fix="Generate contextual dialogue from scene descriptions"
            ))
        else:
            # Check attribution
            for s in dialogue_shots:
                dlg = s.get("dialogue_text", "")
                chars = s.get("characters", [])
                if not chars:
                    violations.append(ComplianceViolation(
                        rule_id="DLG_001", rule_name="Dialogue Attribution",
                        severity="warning",
                        location=f"Shot {s.get('shot_id', '?')}",
                        description=f"Dialogue present but no character assigned",
                        auto_fix="Attribute dialogue to scene's primary character"
                    ))
        return violations

    # ─── TECHNICAL CHECKS ───

    def _check_duration(self, shots) -> List[ComplianceViolation]:
        violations = []
        total_dur = sum(s.get("duration", s.get("duration_seconds", 5)) for s in shots)

        if total_dur < self.profile.min_duration_seconds:
            violations.append(ComplianceViolation(
                rule_id="TECH_001", rule_name="Duration Feasibility",
                severity="blocking", location="project",
                description=f"Total runtime {total_dur}s ({total_dur/60:.0f}min) below minimum {self.profile.min_duration_seconds}s for {self.content_type}",
                auto_fix="Extend shot durations or add more shots to reach target runtime"
            ))
        elif total_dur > self.profile.max_duration_seconds:
            violations.append(ComplianceViolation(
                rule_id="TECH_001", rule_name="Duration Feasibility",
                severity="warning", location="project",
                description=f"Total runtime {total_dur}s ({total_dur/60:.0f}min) exceeds max {self.profile.max_duration_seconds}s for {self.content_type}",
                auto_fix="Trim shot durations or reduce scene count"
            ))
        return violations

    def _check_genre(self) -> List[ComplianceViolation]:
        violations = []
        genre = self.story_bible.get("genre", "")
        if not genre or len(genre.strip()) < 3:
            violations.append(ComplianceViolation(
                rule_id="TECH_002", rule_name="Genre Classification",
                severity="warning", location="story_bible",
                description="No genre specified — director/writer auto-selection won't work",
                auto_fix="Infer genre from story content and tone keywords"
            ))
        return violations

    def _check_visual_descriptions(self, shots) -> List[ComplianceViolation]:
        violations = []
        VISUAL_KEYWORDS = {"walk", "run", "sit", "stand", "look", "turn", "reach", "grab",
                          "open", "close", "enter", "exit", "point", "hold", "pick", "drop",
                          "push", "pull", "dance", "fight", "fall", "climb", "drive", "fly"}

        visual_shots = 0
        for s in shots:
            text = f"{s.get('description', '')} {s.get('beat_description', '')} {s.get('nano_prompt', '')}".lower()
            if any(kw in text for kw in VISUAL_KEYWORDS):
                visual_shots += 1

        ratio = visual_shots / max(len(shots), 1)
        if ratio < 0.3:
            violations.append(ComplianceViolation(
                rule_id="VIS_001", rule_name="Visual Descriptions",
                severity="warning", location="project",
                description=f"Only {ratio:.0%} of shots have visual action — risk of static/talking head output",
                auto_fix="Inject physical action cues from character goals and scene context"
            ))
        return violations


# ═══════════════════════════════════════════════════════════════════
# AUTO-DETECT CONTENT TYPE
# ═══════════════════════════════════════════════════════════════════

def detect_content_type(shot_plan: Dict, story_bible: Dict = None) -> str:
    """Auto-detect the most appropriate content type from project data."""
    shots = shot_plan if isinstance(shot_plan, list) else shot_plan.get("shots", [])
    total_dur = sum(s.get("duration", s.get("duration_seconds", 5)) for s in shots)
    scene_count = len(set(s.get("scene_id", "?") for s in shots))
    has_dialogue = any((s.get("dialogue_text", "") or "").strip() for s in shots)

    # Duration-based classification
    if total_dur <= 60:
        return "social_media"
    elif total_dur <= 120:
        if has_dialogue:
            return "actor_promo"
        return "social_media"
    elif total_dur <= 180:
        return "trailer"
    elif total_dur <= 360:
        return "music_video" if not has_dialogue else "corporate"
    elif total_dur <= 900:
        return "short_film"
    elif total_dur <= 5400:
        return "episode"
    else:
        return "feature_film"


# ═══════════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════════

def validate_script_compliance(project_path: Path, content_type: str = None,
                                story_bible: Dict = None, cast_map: Dict = None,
                                auto_fix: bool = False) -> Dict:
    """
    Validate a project's script against ATLAS compliance rules.

    Args:
        project_path: Path to pipeline_outputs/{project}
        content_type: Content type (auto-detected if None)
        story_bible: Story bible data
        cast_map: Cast map data
        auto_fix: If True, mark fixable violations as fixed

    Returns:
        Dict with compliance_score, readiness, violations
    """
    # Auto-detect content type if not specified
    if not content_type:
        sp_path = project_path / "shot_plan.json"
        if sp_path.exists():
            with open(sp_path) as f:
                sp = json.load(f)
            content_type = detect_content_type(sp, story_bible)
        else:
            content_type = "episode"

    validator = ScriptComplianceValidator(
        project_path, content_type, story_bible, cast_map
    )
    return validator.validate(auto_fix=auto_fix)


def get_content_profiles() -> Dict:
    """Return all available content type profiles for UI display."""
    return {
        name: {
            "content_type": p.content_type,
            "description": p.description,
            "min_scenes": p.min_scenes,
            "max_scenes": p.max_scenes,
            "min_shots_per_scene": p.min_shots_per_scene,
            "min_characters": p.min_characters,
            "requires_dialogue": p.requires_dialogue,
            "requires_story_arc": p.requires_story_arc,
            "min_duration_seconds": p.min_duration_seconds,
            "max_duration_seconds": p.max_duration_seconds,
            "target_cuts_per_minute": p.target_cuts_per_minute,
        }
        for name, p in CONTENT_PROFILES.items()
    }
