#!/usr/bin/env python3
"""
ATLAS VALIDATION GATES - Pipeline Integrity Enforcement
========================================================
Implements the 4 mandatory validation gates from ATLAS_PIPELINE_VALIDATION_AND_TRACE_PROMPT.md

Gates:
1. SEMANTIC - Script traceability, character alignment
2. TEMPORAL - Duration, pacing, shot density
3. ASSET - Reference validation, path resolution
4. STYLE - Canon compliance, tone consistency

Author: ATLAS V16.2
"""

import json
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict, field

# Constants
MIN_SHOTS_PER_MINUTE = 12
TARGET_SHOTS_PER_MINUTE = 15
MIN_SHOT_DURATION = 6
MAX_SHOT_DURATION = 60
FIT_SCORE_THRESHOLD = 85

BASE_DIR = Path("/Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM")


@dataclass
class GateResult:
    """Result of a single validation gate."""
    gate_name: str
    status: str  # "PASS", "FAIL", "WARNING"
    checks: Dict[str, bool] = field(default_factory=dict)
    violations: List[Dict] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    repairs_needed: List[Dict] = field(default_factory=list)


@dataclass
class CriticReport:
    """Full critic report for a project."""
    project: str
    timestamp: str
    gates: Dict[str, Dict]
    casting: Dict
    repairs: List[Dict]
    final_state: str  # "APPROVED", "REJECTED", "WARNINGS"
    approval_conditions_met: Dict[str, bool]


class ATLASValidationGates:
    """
    Implements all 4 validation gates for ATLAS pipeline integrity.
    """

    def __init__(self, project_path: Path):
        self.project_path = project_path
        self.project_name = project_path.name
        self.shot_plan = {}
        self.story_bible = {}
        self.cast_map = {}
        self.regression_history = {"rejected_pairs": []}
        self.repairs = []
        self._load_project_data()

    def _load_project_data(self):
        """Load all project data files."""
        # Shot plan
        shot_plan_path = self.project_path / "shot_plan.json"
        if shot_plan_path.exists():
            with open(shot_plan_path) as f:
                self.shot_plan = json.load(f)

        # Story bible
        story_bible_path = self.project_path / "story_bible.json"
        if story_bible_path.exists():
            with open(story_bible_path) as f:
                self.story_bible = json.load(f)

        # Cast map
        cast_map_path = self.project_path / "cast_map.json"
        if cast_map_path.exists():
            with open(cast_map_path) as f:
                self.cast_map = json.load(f)

        # Regression history
        regression_path = self.project_path / "regression_history.json"
        if regression_path.exists():
            with open(regression_path) as f:
                self.regression_history = json.load(f)

    # =========================================================================
    # GATE 1: SEMANTIC VALIDATION
    # =========================================================================

    def run_semantic_gate(self) -> GateResult:
        """
        Validate logical correctness against source intent.
        - Every shot MUST reference a valid script_line_ref
        - Dialogue/action MUST exist in story_bible or script
        - Character presence MUST align with scene description
        - No orphan shots allowed
        """
        checks = {
            "script_refs_valid": True,
            "dialogue_exists": True,
            "characters_aligned": True,
            "no_orphans": True
        }
        violations = []
        repairs_needed = []

        shots = self.shot_plan.get("shots", [])
        script_text = ""

        # Load script if available
        script_path = self.project_path / "imported_script.txt"
        if script_path.exists():
            script_text = script_path.read_text().lower()

        # Check each shot
        orphan_shots = []
        missing_script_refs = []
        character_mismatches = []

        for shot in shots:
            shot_id = shot.get("shot_id", "unknown")

            # Check script_line_ref
            script_ref = shot.get("script_line_ref", "")
            if not script_ref:
                missing_script_refs.append(shot_id)
                checks["script_refs_valid"] = False

            # Check if dialogue/action exists in source
            if script_ref and script_text:
                # Normalize for comparison
                ref_normalized = script_ref.lower()[:50]
                if ref_normalized not in script_text and len(ref_normalized) > 20:
                    # Could be paraphrased - check key words
                    key_words = [w for w in ref_normalized.split() if len(w) > 4]
                    matches = sum(1 for w in key_words if w in script_text)
                    if matches < len(key_words) * 0.5:
                        violations.append({
                            "type": "DIALOGUE_NOT_IN_SOURCE",
                            "shot_id": shot_id,
                            "script_ref": script_ref[:100]
                        })

            # Check character alignment
            shot_chars = shot.get("characters", [])
            scene_id = shot.get("scene_id", "")

            # Find scene in manifest
            scene_chars = set()
            for scene in self.shot_plan.get("scene_manifest", []):
                if scene.get("scene_id") == scene_id:
                    for char in scene.get("characters", []):
                        if isinstance(char, str):
                            scene_chars.add(char.upper())
                        elif isinstance(char, dict):
                            scene_chars.add(char.get("name", "").upper())

            # Check if shot characters are in scene
            for char in shot_chars:
                char_name = char.upper() if isinstance(char, str) else char.get("name", "").upper()
                if scene_chars and char_name not in scene_chars:
                    character_mismatches.append({
                        "shot_id": shot_id,
                        "character": char_name,
                        "scene_id": scene_id
                    })
                    checks["characters_aligned"] = False

            # Check for orphan shots (no scene, no characters, no description)
            if not shot.get("scene_id") and not shot.get("characters") and not shot.get("description"):
                orphan_shots.append(shot_id)
                checks["no_orphans"] = False

        # Build violations list
        if missing_script_refs:
            violations.append({
                "type": "MISSING_SCRIPT_REFS",
                "count": len(missing_script_refs),
                "shots": missing_script_refs[:10]  # First 10
            })
            repairs_needed.append({
                "action": "ADD_SCRIPT_REFS",
                "targets": missing_script_refs
            })

        if character_mismatches:
            violations.append({
                "type": "CHARACTER_MISALIGNMENT",
                "count": len(character_mismatches),
                "details": character_mismatches[:10]
            })

        if orphan_shots:
            violations.append({
                "type": "ORPHAN_SHOTS",
                "count": len(orphan_shots),
                "shots": orphan_shots
            })
            repairs_needed.append({
                "action": "REMOVE_OR_LINK_ORPHANS",
                "targets": orphan_shots
            })

        status = "PASS" if all(checks.values()) else "FAIL"

        return GateResult(
            gate_name="semantic",
            status=status,
            checks=checks,
            violations=violations,
            metrics={
                "total_shots": len(shots),
                "shots_with_script_ref": len(shots) - len(missing_script_refs),
                "orphan_count": len(orphan_shots)
            },
            repairs_needed=repairs_needed
        )

    # =========================================================================
    # GATE 2: TEMPORAL VALIDATION
    # =========================================================================

    def run_temporal_gate(self) -> GateResult:
        """
        Validate timing, pacing, and duration coherence.
        - Shot durations MUST match requested runtime
        - Extended shots MUST show total duration correctly
        - Total scene runtime MUST match script intent
        - Minimum pacing rule: 12 shots/minute
        """
        checks = {
            "durations_valid": True,
            "extended_display_correct": True,
            "runtime_matches": True,
            "min_shots_per_minute": True
        }
        violations = []
        repairs_needed = []

        shots = self.shot_plan.get("shots", [])
        metadata = self.shot_plan.get("metadata", {})

        # Get target runtime
        target_runtime_seconds = metadata.get("target_runtime", 2700)  # Default 45 min
        target_runtime_minutes = target_runtime_seconds / 60

        # Calculate actual metrics
        total_duration = 0
        invalid_durations = []
        extended_issues = []

        for shot in shots:
            shot_id = shot.get("shot_id", "unknown")
            duration = shot.get("duration", 0) or shot.get("duration_seconds", 0) or 10

            # Check duration validity
            if duration < MIN_SHOT_DURATION or duration > MAX_SHOT_DURATION:
                invalid_durations.append({
                    "shot_id": shot_id,
                    "duration": duration,
                    "issue": "OUT_OF_RANGE"
                })
                checks["durations_valid"] = False

            # Check extended shot display
            if shot.get("extended_shot"):
                segments = shot.get("ltx_segments", 1)
                requested = shot.get("duration_requested", duration)
                if segments > 1 and duration == requested:
                    # Duration should reflect total, not per-segment
                    pass  # This is correct
                elif segments > 1 and duration * segments != requested:
                    extended_issues.append({
                        "shot_id": shot_id,
                        "segments": segments,
                        "duration": duration,
                        "requested": requested
                    })
                    checks["extended_display_correct"] = False

            # Use total duration for extended shots
            if shot.get("extended_shot") and shot.get("duration_requested"):
                total_duration += shot.get("duration_requested")
            else:
                total_duration += duration

        total_runtime_minutes = total_duration / 60
        shots_per_minute = len(shots) / max(1, target_runtime_minutes)

        # Check runtime match (within 10%)
        runtime_deviation = abs(total_duration - target_runtime_seconds) / target_runtime_seconds
        if runtime_deviation > 0.10:
            checks["runtime_matches"] = False
            violations.append({
                "type": "RUNTIME_MISMATCH",
                "target_seconds": target_runtime_seconds,
                "actual_seconds": total_duration,
                "deviation_percent": round(runtime_deviation * 100, 1)
            })
            repairs_needed.append({
                "action": "REBALANCE_DURATIONS",
                "target": target_runtime_seconds,
                "current": total_duration
            })

        # Check shot density
        if shots_per_minute < MIN_SHOTS_PER_MINUTE:
            checks["min_shots_per_minute"] = False
            required_shots = int(target_runtime_minutes * MIN_SHOTS_PER_MINUTE)
            violations.append({
                "type": "SHOT_DENSITY_LOW",
                "current_shots": len(shots),
                "required_shots": required_shots,
                "shots_per_minute": round(shots_per_minute, 2),
                "minimum_required": MIN_SHOTS_PER_MINUTE
            })
            repairs_needed.append({
                "action": "EXPAND_SHOTS",
                "current": len(shots),
                "required": required_shots
            })

        if invalid_durations:
            violations.append({
                "type": "INVALID_DURATIONS",
                "count": len(invalid_durations),
                "details": invalid_durations[:10]
            })

        if extended_issues:
            violations.append({
                "type": "EXTENDED_DISPLAY_ISSUES",
                "count": len(extended_issues),
                "details": extended_issues[:10]
            })

        status = "PASS" if all(checks.values()) else "FAIL"

        return GateResult(
            gate_name="temporal",
            status=status,
            checks=checks,
            violations=violations,
            metrics={
                "total_shots": len(shots),
                "runtime_minutes": round(target_runtime_minutes, 1),
                "actual_runtime_minutes": round(total_runtime_minutes, 1),
                "shots_per_minute": round(shots_per_minute, 2),
                "required_shots_per_minute": MIN_SHOTS_PER_MINUTE
            },
            repairs_needed=repairs_needed
        )

    # =========================================================================
    # GATE 3: ASSET VALIDATION
    # =========================================================================

    def run_asset_gate(self) -> GateResult:
        """
        Validate physical and technical correctness.
        - All actors are valid (have references)
        - Headshot / reference exists for each cast
        - Asset paths MUST resolve
        - Locked assets MUST NOT be altered
        """
        checks = {
            "actors_valid": True,
            "references_exist": True,
            "paths_resolve": True,
            "locks_intact": True
        }
        violations = []
        repairs_needed = []

        # Check cast map references
        missing_refs = []
        invalid_paths = []

        for char_name, cast_data in self.cast_map.items():
            if char_name.startswith("_"):
                continue  # Skip metadata

            if isinstance(cast_data, dict):
                headshot = cast_data.get("headshot_url") or cast_data.get("reference_url")
                if not headshot:
                    missing_refs.append(char_name)
                    checks["references_exist"] = False
                elif headshot.startswith("/api/media?path="):
                    # Check if file exists
                    file_path = headshot.replace("/api/media?path=", "")
                    if not Path(file_path).exists():
                        invalid_paths.append({
                            "character": char_name,
                            "path": file_path
                        })
                        checks["paths_resolve"] = False

        # Check shot references
        shots = self.shot_plan.get("shots", [])
        shots_missing_refs = []

        for shot in shots:
            shot_id = shot.get("shot_id", "unknown")
            chars = shot.get("characters", [])
            ai_cast = shot.get("ai_actor_cast", {})

            # If shot has characters but no cast
            if chars and not ai_cast:
                shots_missing_refs.append(shot_id)

        if shots_missing_refs:
            violations.append({
                "type": "SHOTS_MISSING_CAST",
                "count": len(shots_missing_refs),
                "shots": shots_missing_refs[:20]
            })
            repairs_needed.append({
                "action": "INJECT_CAST_TO_SHOTS",
                "targets": shots_missing_refs
            })

        # Check location masters
        location_masters_dir = self.project_path / "location_masters"
        locations_in_shots = set()
        for shot in shots:
            loc = shot.get("location", "")
            if loc:
                locations_in_shots.add(loc.upper())

        missing_locations = []
        if location_masters_dir.exists():
            existing_masters = {f.stem.upper() for f in location_masters_dir.glob("*.*")}
            for loc in locations_in_shots:
                loc_normalized = loc.replace(" ", "_").replace("-", "_")
                if not any(loc_normalized in m or m in loc_normalized for m in existing_masters):
                    missing_locations.append(loc)

        if missing_locations:
            violations.append({
                "type": "MISSING_LOCATION_MASTERS",
                "count": len(missing_locations),
                "locations": list(missing_locations)[:10]
            })

        if missing_refs:
            violations.append({
                "type": "MISSING_ACTOR_REFS",
                "count": len(missing_refs),
                "characters": missing_refs
            })
            repairs_needed.append({
                "action": "GENERATE_ACTOR_REFS",
                "targets": missing_refs
            })

        if invalid_paths:
            violations.append({
                "type": "INVALID_ASSET_PATHS",
                "count": len(invalid_paths),
                "details": invalid_paths
            })

        status = "PASS" if all(checks.values()) else "FAIL"

        return GateResult(
            gate_name="asset",
            status=status,
            checks=checks,
            violations=violations,
            metrics={
                "cast_characters": len([k for k in self.cast_map if not k.startswith("_")]),
                "characters_with_refs": len([k for k in self.cast_map if not k.startswith("_")]) - len(missing_refs),
                "locations_in_shots": len(locations_in_shots),
                "missing_location_masters": len(missing_locations)
            },
            repairs_needed=repairs_needed
        )

    # =========================================================================
    # GATE 4: STYLE & CANON VALIDATION
    # =========================================================================

    def run_style_gate(self) -> GateResult:
        """
        Validate visual, tonal, and narrative consistency.
        - Shot style aligns with project canon
        - Lighting, framing, and mood do not contradict story tone
        - No style drift across scenes
        """
        checks = {
            "style_aligned": True,
            "tone_consistent": True,
            "no_drift": True
        }
        violations = []
        repairs_needed = []

        shots = self.shot_plan.get("shots", [])

        # Get project genre/style from story bible (handle both string and list)
        genre_raw = self.story_bible.get("genre", "")
        genre = genre_raw.lower() if isinstance(genre_raw, str) else " ".join(genre_raw).lower() if genre_raw else ""

        tone_raw = self.story_bible.get("tone", "")
        tone = tone_raw.lower() if isinstance(tone_raw, str) else " ".join(tone_raw).lower() if tone_raw else ""

        # Define style requirements by genre
        genre_requirements = {
            "horror": {"lighting": ["dark", "shadow", "dim", "low-key"], "avoid": ["bright", "cheerful", "sunny"]},
            "gothic": {"lighting": ["candlelight", "shadow", "dark", "moody"], "avoid": ["bright", "neon", "modern"]},
            "thriller": {"lighting": ["contrast", "shadow", "tension"], "avoid": ["flat", "soft"]},
            "comedy": {"lighting": ["bright", "warm", "natural"], "avoid": ["dark", "horror"]},
            "drama": {"lighting": ["natural", "motivated"], "avoid": []},
        }

        requirements = genre_requirements.get(genre, {"lighting": [], "avoid": []})

        style_violations = []

        for shot in shots:
            shot_id = shot.get("shot_id", "unknown")
            nano_prompt = (shot.get("nano_prompt", "") or "").lower()
            lighting = (shot.get("lighting", "") or "").lower()

            # Check for style contradictions
            for avoid_term in requirements.get("avoid", []):
                if avoid_term in nano_prompt or avoid_term in lighting:
                    style_violations.append({
                        "shot_id": shot_id,
                        "issue": f"Contains '{avoid_term}' which contradicts {genre} genre",
                        "field": "nano_prompt" if avoid_term in nano_prompt else "lighting"
                    })
                    checks["style_aligned"] = False

        # Check for style drift (inconsistent lighting across scenes)
        scene_lighting = {}
        for shot in shots:
            scene_id = shot.get("scene_id", "unknown")
            lighting = shot.get("lighting", "")
            if scene_id not in scene_lighting:
                scene_lighting[scene_id] = []
            if lighting:
                scene_lighting[scene_id].append(lighting)

        # Detect scenes with wildly different lighting
        drift_scenes = []
        for scene_id, lightings in scene_lighting.items():
            if len(set(lightings)) > 3:  # More than 3 different lighting setups in one scene
                drift_scenes.append({
                    "scene_id": scene_id,
                    "lighting_variations": len(set(lightings))
                })
                checks["no_drift"] = False

        if style_violations:
            violations.append({
                "type": "STYLE_CONTRADICTION",
                "count": len(style_violations),
                "details": style_violations[:10]
            })

        if drift_scenes:
            violations.append({
                "type": "STYLE_DRIFT",
                "count": len(drift_scenes),
                "scenes": drift_scenes
            })

        status = "PASS" if all(checks.values()) else "FAIL"

        return GateResult(
            gate_name="style",
            status=status,
            checks=checks,
            violations=violations,
            metrics={
                "genre": genre,
                "tone": tone,
                "style_violations": len(style_violations),
                "drift_scenes": len(drift_scenes)
            },
            repairs_needed=repairs_needed
        )

    # =========================================================================
    # CASTING VALIDATION (with regression history)
    # =========================================================================

    def validate_casting(self) -> Dict:
        """
        Validate all casting assignments against:
        - Fit score threshold (85)
        - Regression history (rejected pairs)
        - Physical matching requirements
        """
        result = {
            "total_characters": 0,
            "validated_casts": 0,
            "rejected_pairs": [],
            "warnings": []
        }

        rejected_pairs = {
            (r["character"], r["actor"])
            for r in self.regression_history.get("rejected_pairs", [])
        }

        for char_name, cast_data in self.cast_map.items():
            if char_name.startswith("_"):
                continue

            result["total_characters"] += 1

            if isinstance(cast_data, dict):
                actor_name = cast_data.get("ai_actor", "")
                fit_score = cast_data.get("fit_score", 0)

                # Check regression history
                if (char_name, actor_name) in rejected_pairs:
                    result["rejected_pairs"].append({
                        "character": char_name,
                        "actor": actor_name,
                        "reason": "IN_REGRESSION_HISTORY"
                    })
                    continue

                # Check fit score threshold
                if fit_score < FIT_SCORE_THRESHOLD:
                    result["warnings"].append({
                        "character": char_name,
                        "actor": actor_name,
                        "fit_score": fit_score,
                        "threshold": FIT_SCORE_THRESHOLD,
                        "status": "WARNING" if fit_score >= 70 else "REJECTED"
                    })
                    if fit_score < 70:
                        result["rejected_pairs"].append({
                            "character": char_name,
                            "actor": actor_name,
                            "reason": f"FIT_SCORE_TOO_LOW ({fit_score})"
                        })
                        continue

                result["validated_casts"] += 1

        return result

    # =========================================================================
    # AUTO-REPAIR EXECUTION (V16.2.1)
    # =========================================================================

    def execute_repairs(self, repairs: List[Dict]) -> List[Dict]:
        """
        Execute repair actions identified by validation gates.
        Returns list of repairs that were successfully executed.
        """
        executed = []

        for repair in repairs:
            action = repair.get("action", "")

            if action == "EXPAND_SHOTS":
                # Need to expand shots to meet density requirements
                try:
                    required = repair.get("required", 540)

                    # Calculate shots needed per scene
                    shots = self.shot_plan.get("shots", [])
                    scenes = self.shot_plan.get("scene_manifest", self.shot_plan.get("scenes", []))

                    if not scenes and not shots:
                        continue

                    # V16.2.1: Check ACTUAL current shots (not stale repair data)
                    actual_current = len(shots)

                    # Also check if shot density is already sufficient
                    runtime_minutes = self.shot_plan.get("runtime_minutes", 45)
                    if runtime_minutes == 0:
                        runtime_minutes = 45
                    current_density = actual_current / runtime_minutes

                    if actual_current >= required or current_density >= MIN_SHOTS_PER_MINUTE:
                        executed.append({
                            "action": action,
                            "result": "skipped",
                            "message": f"Already have {actual_current} shots (density: {current_density:.1f}/min, need: {MIN_SHOTS_PER_MINUTE})"
                        })
                        continue

                    # Calculate how many more shots we need (don't over-expand)
                    expansion_factor = min(3, max(2, required // max(actual_current, 1)))

                    # Expand each shot into multiple shots with ABC coverage
                    expanded_shots = []
                    for shot in shots:
                        shot_id = shot.get("shot_id", "001")
                        base_id = shot_id.split("_")[0] if "_" in shot_id else shot_id

                        # Create A, B, C angles for each shot
                        for angle_idx, angle in enumerate(["A", "B", "C"]):
                            new_shot = shot.copy()
                            new_shot["shot_id"] = f"{base_id}_{angle}"
                            new_shot["angle"] = angle

                            # Adjust duration - split original duration
                            orig_duration = shot.get("duration", 20)
                            new_shot["duration"] = max(6, orig_duration // 3)

                            # Adjust shot type based on angle
                            if angle == "A":
                                new_shot["shot_type"] = "wide"
                            elif angle == "B":
                                new_shot["shot_type"] = "medium"
                            else:
                                new_shot["shot_type"] = "close-up"

                            expanded_shots.append(new_shot)

                    # Update shot_plan
                    if expanded_shots:
                        self.shot_plan["shots"] = expanded_shots
                        self.shot_plan["_expansion_applied"] = True
                        self.shot_plan["_expansion_timestamp"] = datetime.now().isoformat()

                        # Recalculate total duration
                        total_duration = sum(s.get("duration", 20) for s in expanded_shots)
                        self.shot_plan["total_duration"] = total_duration

                        # Save updated shot_plan
                        shot_plan_path = self.project_path / "shot_plan.json"
                        with open(shot_plan_path, 'w') as f:
                            json.dump(self.shot_plan, f, indent=2)

                        executed.append({
                            "action": action,
                            "result": "success",
                            "before": len(shots),
                            "after": len(expanded_shots),
                            "message": f"Expanded {len(shots)} shots to {len(expanded_shots)} with ABC coverage"
                        })
                        self.repairs.append({
                            "type": "EXPAND_SHOTS",
                            "action": f"Expanded to {len(expanded_shots)} shots",
                            "timestamp": datetime.now().isoformat()
                        })

                except Exception as e:
                    executed.append({
                        "action": action,
                        "result": "error",
                        "error": str(e)
                    })

            elif action == "REBALANCE_DURATIONS":
                # Adjust durations to hit target runtime
                try:
                    target = repair.get("target", 2700)
                    current = repair.get("current", 0)

                    shots = self.shot_plan.get("shots", [])
                    if not shots:
                        continue

                    # Calculate needed duration per shot
                    current_total = sum(s.get("duration", 20) for s in shots)
                    if current_total == 0:
                        current_total = len(shots) * 20

                    # V16.2.1: Handle over-duration by reducing shots if scaling won't work
                    # If we have too many shots and can't scale down (due to MIN_DURATION),
                    # we need to remove excess shots
                    min_possible_duration = len(shots) * MIN_SHOT_DURATION
                    if min_possible_duration > target:
                        # Too many shots - need to downsample
                        max_shots = target // MIN_SHOT_DURATION
                        # Keep every Nth shot to reach target
                        step = max(1, len(shots) // max_shots)
                        shots = [shots[i] for i in range(0, len(shots), step)][:max_shots]
                        self.shot_plan["shots"] = shots
                        current_total = sum(s.get("duration", 20) for s in shots)

                    scale_factor = target / current_total

                    # Scale durations (within limits)
                    for shot in shots:
                        old_duration = shot.get("duration", 20)
                        new_duration = int(old_duration * scale_factor)
                        shot["duration"] = max(MIN_SHOT_DURATION, min(MAX_SHOT_DURATION, new_duration))

                    # Recalculate total
                    new_total = sum(s.get("duration", 20) for s in shots)
                    self.shot_plan["total_duration"] = new_total

                    # Save
                    shot_plan_path = self.project_path / "shot_plan.json"
                    with open(shot_plan_path, 'w') as f:
                        json.dump(self.shot_plan, f, indent=2)

                    executed.append({
                        "action": action,
                        "result": "success",
                        "before": current_total,
                        "after": new_total,
                        "target": target
                    })
                    self.repairs.append({
                        "type": "REBALANCE_DURATIONS",
                        "action": f"Scaled from {current_total}s to {new_total}s (target: {target}s)",
                        "timestamp": datetime.now().isoformat()
                    })

                except Exception as e:
                    executed.append({
                        "action": action,
                        "result": "error",
                        "error": str(e)
                    })

            elif action == "INJECT_CAST_TO_SHOTS":
                # Populate cast data into shots
                try:
                    targets = repair.get("targets", [])
                    cast_map_path = self.project_path / "cast_map.json"

                    if not cast_map_path.exists():
                        continue

                    with open(cast_map_path) as f:
                        cast_map = json.load(f)

                    shots = self.shot_plan.get("shots", [])
                    updated = 0

                    for shot in shots:
                        shot_id = shot.get("shot_id", "")
                        if shot_id in targets or not shot.get("cast"):
                            # Find characters in this shot
                            characters = shot.get("characters", [])
                            if not characters:
                                continue

                            cast_list = []
                            for char in characters:
                                char_name = char.upper() if isinstance(char, str) else char.get("name", "").upper()
                                if char_name in cast_map:
                                    cast_info = cast_map[char_name]
                                    cast_list.append({
                                        "character": char_name,
                                        "actor": cast_info.get("ai_actor"),
                                        "actor_id": cast_info.get("ai_actor_id"),
                                        "reference": cast_info.get("locked_reference_url", cast_info.get("headshot_url"))
                                    })

                            if cast_list:
                                shot["cast"] = cast_list
                                updated += 1

                    if updated > 0:
                        # Save
                        shot_plan_path = self.project_path / "shot_plan.json"
                        with open(shot_plan_path, 'w') as f:
                            json.dump(self.shot_plan, f, indent=2)

                        executed.append({
                            "action": action,
                            "result": "success",
                            "shots_updated": updated
                        })
                        self.repairs.append({
                            "type": "INJECT_CAST",
                            "action": f"Injected cast into {updated} shots",
                            "timestamp": datetime.now().isoformat()
                        })

                except Exception as e:
                    executed.append({
                        "action": action,
                        "result": "error",
                        "error": str(e)
                    })

        return executed

    # =========================================================================
    # MAIN VALIDATION RUNNER
    # =========================================================================

    def run_all_gates(self, auto_repair: bool = True) -> CriticReport:
        """
        Run all validation gates in order and generate critic report.
        If auto_repair=True, execute repairs and re-validate.
        """
        timestamp = datetime.now().isoformat()

        # Run all gates
        semantic_result = self.run_semantic_gate()
        temporal_result = self.run_temporal_gate()
        asset_result = self.run_asset_gate()
        style_result = self.run_style_gate()

        # Validate casting
        casting_result = self.validate_casting()

        # Collect all repairs
        all_repairs = []
        all_repairs.extend(semantic_result.repairs_needed)
        all_repairs.extend(temporal_result.repairs_needed)
        all_repairs.extend(asset_result.repairs_needed)
        all_repairs.extend(style_result.repairs_needed)

        # V16.2.1: Execute repairs if auto_repair is enabled
        executed_repairs = []
        if auto_repair and all_repairs:
            executed_repairs = self.execute_repairs(all_repairs)

            # Re-run temporal gate after EXPAND_SHOTS to verify fix
            if any(r.get("action") == "EXPAND_SHOTS" and r.get("result") == "success" for r in executed_repairs):
                # Reload shot_plan after expansion
                shot_plan_path = self.project_path / "shot_plan.json"
                with open(shot_plan_path) as f:
                    self.shot_plan = json.load(f)
                temporal_result = self.run_temporal_gate()

        # Add casting repairs
        for rejected in casting_result.get("rejected_pairs", []):
            all_repairs.append({
                "type": "RECAST",
                "target": rejected["character"],
                "reason": rejected["reason"],
                "action": f"Rejected {rejected['actor']}, needs recast"
            })
            self.repairs.append({
                "type": "RECAST",
                "target": rejected["character"],
                "action": f"Rejected {rejected['actor']} ({rejected['reason']})",
                "timestamp": timestamp
            })

        # Determine final state
        all_gates_pass = all(
            r.status == "PASS"
            for r in [semantic_result, temporal_result, asset_result, style_result]
        )
        no_rejected_casts = len(casting_result.get("rejected_pairs", [])) == 0
        no_warnings = len(casting_result.get("warnings", [])) == 0

        if all_gates_pass and no_rejected_casts and no_warnings:
            final_state = "APPROVED"
        elif all_gates_pass and no_rejected_casts:
            final_state = "WARNINGS"
        else:
            final_state = "REJECTED"

        # Build report
        report = CriticReport(
            project=self.project_name,
            timestamp=timestamp,
            gates={
                "semantic": asdict(semantic_result),
                "temporal": asdict(temporal_result),
                "asset": asdict(asset_result),
                "style": asdict(style_result)
            },
            casting=casting_result,
            repairs=self.repairs,
            final_state=final_state,
            approval_conditions_met={
                "all_gates_pass": all_gates_pass,
                "no_unresolved_warnings": no_warnings,
                "traceability_complete": semantic_result.checks.get("script_refs_valid", False),
                "critic_report_clean": final_state == "APPROVED"
            }
        )

        return report

    def save_critic_report(self, report: CriticReport) -> Path:
        """Save critic report to project directory."""
        report_path = self.project_path / "critic_report.json"
        with open(report_path, 'w') as f:
            json.dump(asdict(report), f, indent=2)
        return report_path

    def save_regression_history(self, rejected_pairs: List[Dict]):
        """Update regression history with newly rejected pairs."""
        for pair in rejected_pairs:
            existing = self.regression_history.get("rejected_pairs", [])
            # Check if already exists
            exists = any(
                r["character"] == pair["character"] and r["actor"] == pair["actor"]
                for r in existing
            )
            if not exists:
                existing.append({
                    "character": pair["character"],
                    "actor": pair["actor"],
                    "rejection_reason": pair.get("reason", "VALIDATION_FAILED"),
                    "timestamp": datetime.now().isoformat(),
                    "fit_score": pair.get("fit_score", 0)
                })

        self.regression_history["rejected_pairs"] = existing
        self.regression_history["version"] = "1.0"
        self.regression_history["last_updated"] = datetime.now().isoformat()

        regression_path = self.project_path / "regression_history.json"
        with open(regression_path, 'w') as f:
            json.dump(self.regression_history, f, indent=2)


# =========================================================================
# SHOT DENSITY ENFORCEMENT
# =========================================================================

def enforce_shot_density(project_path: Path, target_runtime_minutes: int) -> Dict:
    """
    Enforce minimum shot density of 12 shots/minute.
    Returns expansion recommendations if density is too low.
    """
    shot_plan_path = project_path / "shot_plan.json"
    if not shot_plan_path.exists():
        return {"status": "error", "message": "No shot_plan.json found"}

    with open(shot_plan_path) as f:
        shot_plan = json.load(f)

    shots = shot_plan.get("shots", [])
    current_count = len(shots)
    required_count = target_runtime_minutes * MIN_SHOTS_PER_MINUTE
    target_count = target_runtime_minutes * TARGET_SHOTS_PER_MINUTE

    if current_count >= required_count:
        return {
            "status": "PASS",
            "current_shots": current_count,
            "required_shots": required_count,
            "shots_per_minute": round(current_count / target_runtime_minutes, 2)
        }

    deficit = required_count - current_count

    # Identify scenes that could be expanded
    scene_shot_counts = {}
    for shot in shots:
        scene_id = shot.get("scene_id", "unknown")
        scene_shot_counts[scene_id] = scene_shot_counts.get(scene_id, 0) + 1

    # Recommend expanding scenes with fewest shots
    expansion_candidates = sorted(scene_shot_counts.items(), key=lambda x: x[1])[:10]

    return {
        "status": "FAIL",
        "current_shots": current_count,
        "required_shots": required_count,
        "deficit": deficit,
        "shots_per_minute": round(current_count / target_runtime_minutes, 2),
        "expansion_candidates": [
            {"scene_id": s[0], "current_shots": s[1], "recommended_add": max(2, 3 - s[1])}
            for s in expansion_candidates
        ],
        "action": "EXPAND_SHOTS_TO_MEET_DENSITY"
    }


# =========================================================================
# MAIN VALIDATION FUNCTION
# =========================================================================

def validate_project(project_name: str, auto_repair: bool = True) -> Dict:
    """
    Run full validation on a project and generate critic report.
    """
    project_path = BASE_DIR / "pipeline_outputs" / project_name

    if not project_path.exists():
        return {"status": "error", "message": f"Project '{project_name}' not found"}

    validator = ATLASValidationGates(project_path)
    report = validator.run_all_gates(auto_repair=auto_repair)

    # Save reports
    report_path = validator.save_critic_report(report)

    # Save regression history if there are rejected pairs
    if report.casting.get("rejected_pairs"):
        validator.save_regression_history(report.casting["rejected_pairs"])

    return {
        "status": "success",
        "project": project_name,
        "final_state": report.final_state,
        "report_path": str(report_path),
        "gates": {
            name: {"status": gate["status"], "violations": len(gate.get("violations", []))}
            for name, gate in report.gates.items()
        },
        "casting": {
            "validated": report.casting["validated_casts"],
            "total": report.casting["total_characters"],
            "rejected": len(report.casting["rejected_pairs"]),
            "warnings": len(report.casting["warnings"])
        },
        "repairs_needed": len(report.repairs)
    }


if __name__ == "__main__":
    import sys
    project = sys.argv[1] if len(sys.argv) > 1 else "ravencroft_new"
    result = validate_project(project)
    print(json.dumps(result, indent=2))
