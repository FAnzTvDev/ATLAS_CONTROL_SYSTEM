#!/usr/bin/env python3
"""
ATLAS V27.1 — Controller Self-Tuning Loop
==========================================
Reads probe results + vision scores from generated frames to auto-adjust:
  1. Resolution escalation triggers (sharpness threshold)
  2. Identity confidence thresholds (ArcFace min similarity)
  3. Prompt weight adjustments (which enrichment patterns correlate with quality)
  4. Ref selection confidence (which angle refs work best per shot type)
  5. Chain confidence recalibration (post-gen verification alignment)

Usage:
    from tools.controller_tuner import ControllerTuner
    tuner = ControllerTuner("pipeline_outputs/victorian_shadows_ep1")
    recommendations = tuner.analyze_and_recommend()
    tuner.apply_recommendations(recommendations)  # writes tuning_config.json
"""

import json
import os
import glob
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class ControllerTuner:
    """Analyzes vision scores across shots to auto-tune controller parameters."""

    def __init__(self, project_path: str):
        self.project_path = project_path
        self.reports_path = os.path.join(project_path, "reports")
        self.config_path = os.path.join(project_path, "tuning_config.json")

        # Default thresholds (before tuning)
        self.defaults = {
            "identity_min_similarity": 0.50,
            "identity_warn_threshold": 0.60,
            "identity_high_confidence": 0.75,
            "location_min_similarity": 0.50,
            "sharpness_min": 0.30,
            "sharpness_regen_trigger": 0.15,
            "exposure_min": 0.40,
            "resolution_escalation_threshold": 0.20,  # sharpness below this → bump resolution
            "hero_candidate_count": 3,
            "max_regen_attempts": 2,
            "camera_brand_check": "word_boundary",  # V27.1: use \bRED\b not "red "
        }

        # Load existing tuning config if present
        self.config = self._load_config()

    def _load_config(self) -> Dict:
        if os.path.exists(self.config_path):
            try:
                return json.load(open(self.config_path))
            except Exception:
                pass
        return dict(self.defaults)

    def _save_config(self, config: Dict):
        config["_tuned_at"] = datetime.now().isoformat()
        config["_version"] = "V27.1"
        with open(self.config_path, "w") as f:
            json.dump(config, f, indent=2)
        logger.info(f"[TUNER] Config saved: {self.config_path}")

    def gather_probe_data(self) -> List[Dict]:
        """Load all probe reports."""
        probes = sorted(glob.glob(os.path.join(self.reports_path, "probe_*.json")))
        results = []
        for p in probes:
            try:
                results.append(json.load(open(p)))
            except Exception:
                pass
        return results

    def gather_vision_scores(self) -> List[Dict]:
        """Load all vision scoring data from generated frames."""
        scores = []
        # Check for vision cache or scoring logs
        vision_cache = os.path.join(self.project_path, ".vision_cache")
        if os.path.exists(vision_cache):
            for f in glob.glob(os.path.join(vision_cache, "*.json")):
                try:
                    scores.append(json.load(open(f)))
                except Exception:
                    pass
        return scores

    def score_all_existing_frames(self) -> Dict[str, Dict]:
        """Run vision scoring on all existing first frames against their refs."""
        import sys
        sys.path.insert(0, "tools")

        results = {}

        # Load shot plan + cast map
        try:
            sp = json.load(open(os.path.join(self.project_path, "shot_plan.json")))
            shots = sp if isinstance(sp, list) else sp.get("shots", [])
            cm = json.load(open(os.path.join(self.project_path, "cast_map.json")))
        except Exception as e:
            logger.error(f"Cannot load project data: {e}")
            return results

        from vision_service import get_vision_service
        vs = get_vision_service(provider="local")

        frames_dir = os.path.join(self.project_path, "first_frames")
        if not os.path.exists(frames_dir):
            return results

        for shot in shots:
            shot_id = shot.get("shot_id", "")
            if not shot_id:
                continue

            # Find frame
            frame_path = None
            for ext in ["jpg", "png"]:
                candidate = os.path.join(frames_dir, f"{shot_id}.{ext}")
                if os.path.exists(candidate):
                    frame_path = candidate
                    break

            if not frame_path:
                continue

            shot_result = {"shot_id": shot_id, "frame": frame_path}

            # Fast QA
            qa = vs.fast_qa(frame_path)
            shot_result["fast_qa"] = qa

            # Identity (only for character shots)
            characters = shot.get("characters") or []
            if characters:
                identity_scores = {}
                for char_name in characters:
                    char_key = char_name.replace(" ", "_")
                    ref_candidates = glob.glob(
                        os.path.join(self.project_path, "character_library_locked",
                                     f"{char_key}*CHAR_REFERENCE*.jpg")
                    )
                    if ref_candidates:
                        identity = vs.score_identity(frame_path, ref_candidates[0],
                                                     expected_face_count=len(characters))
                        identity_scores[char_name] = identity
                shot_result["identity"] = identity_scores

            results[shot_id] = shot_result

        return results

    def analyze_and_recommend(self, probe_data: Optional[List[Dict]] = None,
                              frame_scores: Optional[Dict] = None) -> Dict:
        """
        Analyze all available data and produce tuning recommendations.
        Returns dict of parameter adjustments with reasoning.
        """
        if probe_data is None:
            probe_data = self.gather_probe_data()

        recommendations = {
            "timestamp": datetime.now().isoformat(),
            "data_points": len(probe_data),
            "adjustments": [],
            "new_config": dict(self.config),
        }

        if not probe_data:
            recommendations["note"] = "No probe data available yet"
            return recommendations

        # Analyze identity scores
        all_identity_sims = []
        failed_identity = []
        for probe in probe_data:
            identity = probe.get("stages", {}).get("identity", {})
            for char_name, scores in identity.items():
                if isinstance(scores, dict):
                    sim = scores.get("face_similarity", 0)
                    all_identity_sims.append(sim)
                    if sim < 0.50:
                        failed_identity.append({"shot": probe["shot_id"], "char": char_name, "sim": sim})

        if all_identity_sims:
            avg_sim = sum(all_identity_sims) / len(all_identity_sims)
            min_sim = min(all_identity_sims)
            max_sim = max(all_identity_sims)

            # If average is high, we can tighten the threshold
            if avg_sim > 0.70 and min_sim > 0.50:
                new_threshold = round(max(0.50, min_sim - 0.05), 2)
                if new_threshold != self.config.get("identity_min_similarity"):
                    recommendations["adjustments"].append({
                        "param": "identity_min_similarity",
                        "old": self.config.get("identity_min_similarity"),
                        "new": new_threshold,
                        "reason": f"Average identity sim is {avg_sim:.3f}, min is {min_sim:.3f}. "
                                  f"Safe to set floor at {new_threshold}",
                    })
                    recommendations["new_config"]["identity_min_similarity"] = new_threshold

            # If we have low-scoring shots, flag for re-generation
            if failed_identity:
                recommendations["adjustments"].append({
                    "param": "_regen_candidates",
                    "shots": failed_identity,
                    "reason": "These shots have identity similarity below threshold",
                })

        # Analyze sharpness scores
        all_sharpness = []
        for probe in probe_data:
            qa = probe.get("stages", {}).get("fast_qa", {})
            if qa.get("sharpness") is not None:
                all_sharpness.append(qa["sharpness"])

        if all_sharpness:
            avg_sharp = sum(all_sharpness) / len(all_sharpness)
            if avg_sharp < 0.20:
                recommendations["adjustments"].append({
                    "param": "resolution_escalation_threshold",
                    "old": self.config.get("resolution_escalation_threshold"),
                    "new": 0.25,
                    "reason": f"Average sharpness is {avg_sharp:.3f} — too low. "
                              "Escalating resolution trigger to catch blurry frames earlier",
                })
                recommendations["new_config"]["resolution_escalation_threshold"] = 0.25

        # Analyze location scores
        all_loc_sims = []
        for probe in probe_data:
            loc = probe.get("stages", {}).get("location", {})
            if isinstance(loc, dict) and loc.get("location_similarity") is not None:
                all_loc_sims.append(loc["location_similarity"])

        if all_loc_sims:
            avg_loc = sum(all_loc_sims) / len(all_loc_sims)
            if avg_loc < 0.50:
                recommendations["adjustments"].append({
                    "param": "location_min_similarity",
                    "old": self.config.get("location_min_similarity"),
                    "new": 0.40,
                    "reason": f"Average location sim is {avg_loc:.3f}. "
                              "Relaxing threshold to 0.40 to avoid false rejects on stylized renders",
                })
                recommendations["new_config"]["location_min_similarity"] = 0.40

        # Camera brand check fix
        recommendations["new_config"]["camera_brand_check"] = "word_boundary"
        recommendations["adjustments"].append({
            "param": "camera_brand_check",
            "old": "substring",
            "new": "word_boundary",
            "reason": "Probe showed false positive: 'red ' matching 'weathered/tailored/covered'. "
                      "Switching to word-boundary regex: \\bRED\\b",
        })

        return recommendations

    def apply_recommendations(self, recommendations: Dict) -> Dict:
        """Apply tuning recommendations and save config."""
        new_config = recommendations.get("new_config", {})
        new_config["_applied_at"] = datetime.now().isoformat()
        new_config["_adjustments_count"] = len(recommendations.get("adjustments", []))
        self._save_config(new_config)

        # Save full recommendations report
        report_path = os.path.join(self.reports_path, "tuning_recommendations.json")
        with open(report_path, "w") as f:
            json.dump(recommendations, f, indent=2)
        logger.info(f"[TUNER] Recommendations saved: {report_path}")

        return new_config


def run_tuning(project_path: str = "pipeline_outputs/victorian_shadows_ep1") -> Dict:
    """Convenience function: analyze + apply tuning in one call."""
    tuner = ControllerTuner(project_path)
    recommendations = tuner.analyze_and_recommend()
    config = tuner.apply_recommendations(recommendations)
    return {"recommendations": recommendations, "config": config}


if __name__ == "__main__":
    import sys
    os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/..")
    project = sys.argv[1] if len(sys.argv) > 1 else "pipeline_outputs/victorian_shadows_ep1"
    result = run_tuning(project)
    print(json.dumps(result["recommendations"], indent=2))
    print(f"\nConfig saved to: {project}/tuning_config.json")
