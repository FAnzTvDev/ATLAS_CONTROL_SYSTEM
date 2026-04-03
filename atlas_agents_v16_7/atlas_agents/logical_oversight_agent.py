"""
ATLAS V18.3 — Logical Oversight Agent (LOA)
Policy engine for cinematography coherence enforcement.
Separates POLICY (this file) from PERCEPTION (vision_service.py).

4 gate points:
  1. pre_generation_gate() — blocking refs/location checks
  2. post_generation_qa() — vision scoring + auto-regen policy
  3. rank_variants() — weighted multi-angle selection
  4. pre_stitch_gate() — consistency enforcement before FFmpeg

Design: every check returns (verdict, evidence, actions)
  - verdict: "pass" | "fail" | "warn" | "insufficient_evidence"
  - evidence: dict of scores/detections
  - actions: list of deterministic API operations
"""

import os
import json
import logging
import hashlib
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger("atlas.loa")

# ─── Feature flags ───
FEATURE_VISION_SERVICE = os.environ.get("FEATURE_VISION_SERVICE", "true").lower() == "true"
FEATURE_LOA = os.environ.get("FEATURE_LOA", "true").lower() == "true"
FEATURE_MULTI_ANGLE_AUTORANK = os.environ.get("FEATURE_MULTI_ANGLE_AUTORANK", "true").lower() == "true"
FEATURE_AUTO_REGEN = os.environ.get("FEATURE_AUTO_REGEN", "true").lower() == "true"

# ─── Thresholds (project-configurable) ───
DEFAULT_THRESHOLDS = {
    "identity_pass": 0.82,      # ArcFace cosine similarity
    "identity_warn": 0.70,
    "location_pass": 0.70,      # DINOv2 cosine similarity
    "location_warn": 0.55,
    "presence_min_conf": 0.35,  # people detection confidence
    "clip_alignment": 0.28,     # CLIPScore (weak signal)
    "sharpness_min": 0.15,      # Laplacian variance normalized
    "max_regen_attempts": 2,    # bounded regen loop
    "min_face_pixels": 64,      # minimum face size for identity check
}

# ─── Variant scoring weights ───
VARIANT_WEIGHTS = {
    "identity": 0.60,
    "location": 0.20,
    "clip_alignment": 0.10,
    "composition": 0.10,
}


class LOAVerdict:
    """Standardized verdict object returned by all LOA checks."""
    def __init__(self, verdict: str, evidence: Dict, actions: List[Dict] = None, shot_id: str = ""):
        self.verdict = verdict  # "pass" | "fail" | "warn" | "insufficient_evidence"
        self.evidence = evidence
        self.actions = actions or []
        self.shot_id = shot_id
        self.timestamp = time.time()

    def to_dict(self) -> Dict:
        return {
            "verdict": self.verdict,
            "evidence": self.evidence,
            "actions": self.actions,
            "shot_id": self.shot_id,
            "timestamp": self.timestamp,
        }

    @property
    def passed(self) -> bool:
        return self.verdict in ("pass", "warn", "insufficient_evidence")

    @property
    def blocking(self) -> bool:
        return self.verdict == "fail"


class LogicalOversightAgent:
    """
    Policy engine for ATLAS cinematography enforcement.
    Calls Vision Service for perception, applies rules for verdicts.
    """

    def __init__(self, project_path: str, thresholds: Dict = None, cast_map: Dict = None):
        self.project_path = Path(project_path)
        self.thresholds = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
        self.cast_map = cast_map or {}
        self._vision_service = None
        self._embedding_cache = {}
        self.action_log = []

    def _get_vision_service(self):
        """Lazy-load vision service."""
        if self._vision_service is None and FEATURE_VISION_SERVICE:
            try:
                from tools.vision_service import get_vision_service
                self._vision_service = get_vision_service(provider="auto")
            except Exception as e:
                logger.warning(f"[LOA] Vision service unavailable: {e}")
        return self._vision_service

    def _log_action(self, action: Dict):
        """Append to audit trail."""
        action["timestamp"] = time.time()
        self.action_log.append(action)

    # ═══════════════════════════════════════════════════
    # GATE 1: PRE-GENERATION (blocking)
    # ═══════════════════════════════════════════════════

    def pre_generation_gate(self, shots: List[Dict], location_masters: Dict = None,
                            scene_manifest: List[Dict] = None) -> Dict:
        """
        Validate ALL shots are renderable before generation starts.
        Returns {passed: bool, verdicts: [...], auto_fixes: [...], blocking_errors: [...]}

        Checks:
        - Character reference presence (characters → locked ref)
        - Location master coherence (scene → location master)
        - Scene manifest location cross-check (V17.7.4)
        - Wardrobe tag match (soft check)
        - Blocking continuity (eyeline/screen direction consistency)
        """
        if not FEATURE_LOA:
            return {"passed": True, "verdicts": [], "auto_fixes": [], "blocking_errors": [], "skipped": True}

        location_masters = location_masters or {}
        verdicts = []
        auto_fixes = []
        blocking_errors = []

        # V17.7.4: Build scene_id → location truth map from scene_manifest
        # This catches corrupted shot-level location fields BEFORE generation
        _scene_loc_truth = {}
        if scene_manifest:
            for sc in scene_manifest:
                sid = sc.get("scene_id", "")
                loc = sc.get("location", "")
                if sid and loc:
                    _scene_loc_truth[sid] = loc

        # V17.7.4: If no scene_manifest passed, try loading from shot_plan.json
        if not _scene_loc_truth:
            try:
                sp_path = self.project_path / "shot_plan.json"
                if sp_path.exists():
                    import json
                    with open(sp_path) as f:
                        sp = json.load(f)
                    for sc in sp.get("scene_manifest", sp.get("scenes", [])):
                        sid = sc.get("scene_id", "")
                        loc = sc.get("location", "")
                        if sid and loc:
                            _scene_loc_truth[sid] = loc
            except Exception:
                pass

        if _scene_loc_truth:
            logger.info(f"[LOA] V17.7.4: Scene location truth loaded — {len(_scene_loc_truth)} scenes")

        for shot in shots:
            # V17.7.4: Cross-check shot location against scene manifest FIRST
            shot_id = shot.get("shot_id", "unknown")
            scene_id_prefix = shot_id.split("_")[0] if "_" in shot_id else ""
            if scene_id_prefix and scene_id_prefix in _scene_loc_truth:
                manifest_loc = _scene_loc_truth[scene_id_prefix]
                shot_loc = shot.get("location", "")
                # Normalize for comparison
                def _norm(s):
                    s = s.upper().strip()
                    for pfx in ["INT.", "EXT.", "INT/EXT.", "INT ", "EXT "]:
                        if s.startswith(pfx): s = s[len(pfx):]
                    for tod in [" — NIGHT", " — DAY", " — EVENING", " — MORNING", " — DAWN", " — DUSK",
                                " - NIGHT", " - DAY", " - EVENING", " - MORNING"]:
                        if s.upper().endswith(tod.upper()): s = s[:-len(tod)]
                    return s.strip(" -—–").replace("–", "-").replace("—", "-").strip()
                if shot_loc and _norm(shot_loc) != _norm(manifest_loc):
                    # Auto-fix: override with scene manifest truth
                    auto_fixes.append({
                        "type": "scene_manifest_location_override",
                        "shot_id": shot_id,
                        "was": shot_loc,
                        "corrected_to": manifest_loc,
                        "source": "scene_manifest",
                    })
                    shot["location"] = manifest_loc
                    logger.info(f"[LOA] V17.7.4: Shot {shot_id} location corrected: '{shot_loc}' → '{manifest_loc}'")
            characters = shot.get("characters", [])
            char_ref = shot.get("character_reference_url", "")
            loc_master = shot.get("location_master_url", "")
            shot_type = shot.get("shot_type", "medium")

            # ── Check 1: Character reference presence ──
            if characters and not char_ref:
                # Try auto-resolve from cast_map
                resolved = False
                for char_name in characters:
                    cast_entry = self.cast_map.get(char_name, {})
                    ref_url = cast_entry.get("character_reference_url", "") or cast_entry.get("headshot_url", "")
                    if ref_url:
                        # V17.6: Normalize to /api/media?path= format before persisting
                        if ref_url and not ref_url.startswith("/api/"):
                            ref_url = f"/api/media?path={ref_url}"
                        # Auto-fix: populate from cast_map
                        auto_fixes.append({
                            "type": "auto_resolve_character_ref",
                            "shot_id": shot_id,
                            "character": char_name,
                            "resolved_url": ref_url,
                            "source": "cast_map",
                        })
                        shot["character_reference_url"] = ref_url
                        resolved = True
                        break

                if not resolved:
                    blocking_errors.append({
                        "type": "missing_character_ref",
                        "shot_id": shot_id,
                        "characters": characters,
                        "message": f"Shot {shot_id} has characters {characters} but no resolvable character reference. Generation will produce empty scene.",
                        "suggested_action": "assign_character_ref",
                    })
                    verdicts.append(LOAVerdict("fail",
                        {"check": "character_ref_presence", "characters": characters},
                        [{"action": "assign_character_ref", "shot_id": shot_id, "characters": characters}],
                        shot_id=shot_id
                    ))
                    continue

            # ── Check 2: Location master coherence ──
            scene_id = shot_id.split("_")[0] if "_" in shot_id else ""
            if not loc_master and scene_id:
                # Try resolve from location_masters dict
                scene_location = shot.get("location", "") or shot.get("setting", "")
                if scene_location:
                    scene_loc_upper = scene_location.upper().strip()
                    # Split compound locations (e.g., "COASTAL ROAD / COUNTRYSIDE")
                    loc_parts = [p.strip() for p in scene_loc_upper.replace("/", ",").replace(" - ", ",").split(",")]
                    loc_parts = [p for p in loc_parts if len(p) > 2]

                    best_match = None
                    best_score = 0
                    for loc_key, loc_url in location_masters.items():
                        loc_key_upper = loc_key.upper().strip()
                        # Exact match is best
                        if loc_key_upper == scene_loc_upper:
                            best_match = (loc_key, loc_url)
                            best_score = 100
                            break
                        # Check compound part exact match
                        for part in loc_parts:
                            if loc_key_upper == part:
                                score = 90
                                if score > best_score:
                                    best_match = (loc_key, loc_url)
                                    best_score = score
                        # Substring match only if key is long enough (avoid "MANOR" matching everything)
                        if len(loc_key_upper) >= 8:
                            if loc_key_upper in scene_loc_upper:
                                score = 50 + len(loc_key_upper)  # Longer match = better
                                if score > best_score:
                                    best_match = (loc_key, loc_url)
                                    best_score = score

                    if best_match:
                        auto_fixes.append({
                            "type": "auto_resolve_location_master",
                            "shot_id": shot_id,
                            "location": scene_location,
                            "resolved_url": best_match[1],
                            "source": "location_masters_map",
                            "matched_key": best_match[0],
                        })
                        shot["location_master_url"] = best_match[1]

            # ── Check 3: Wardrobe tag consistency (soft) ──
            # Future: compare shot scene tag vs character wardrobe_tag
            # For now, this is a warn-only placeholder

            # ── Check 4: Blocking continuity (eyeline/direction) ──
            eyeline = shot.get("eyeline_target", "")
            screen_dir = shot.get("screen_direction", "")
            blocking_role = shot.get("blocking_role", "")

            # All checks passed for this shot
            verdicts.append(LOAVerdict("pass",
                {"check": "pre_generation", "has_char_ref": bool(char_ref or auto_fixes),
                 "has_loc_master": bool(loc_master), "shot_type": shot_type},
                shot_id=shot_id
            ))

        # Blocking continuity: check consecutive shots in same scene
        continuity_warnings = self._check_blocking_continuity(shots)
        for warn in continuity_warnings:
            verdicts.append(LOAVerdict("warn", warn, shot_id=warn.get("shot_id", "")))

        # V17.7.4: Script fidelity check (non-blocking, warning-only)
        fidelity_warnings = []
        try:
            from atlas_agents.script_fidelity_agent import validate_scene_fidelity
            # Load story bible
            sb_path = self.project_path / "story_bible.json"
            if sb_path.exists():
                import json as _json
                with open(sb_path) as f:
                    sb = _json.load(f)
                sb_scenes = sb.get("scenes", [])
                fidelity = validate_scene_fidelity(shots, sb_scenes)
                fidelity_score = fidelity.get("overall_fidelity_score", 100)
                if fidelity_score < 60:
                    fidelity_warnings.append({
                        "check": "script_fidelity",
                        "overall_score": fidelity_score,
                        "generic_prompts": fidelity.get("summary", {}).get("generic_prompts", 0),
                        "missing_actions": fidelity.get("summary", {}).get("missing_actions", 0),
                        "message": f"Script fidelity score {fidelity_score}/100 — {fidelity.get('summary', {}).get('generic_prompts', 0)} generic prompts, {fidelity.get('summary', {}).get('missing_actions', 0)} missing actions",
                    })
                    for warn in fidelity_warnings:
                        verdicts.append(LOAVerdict("warn", warn, shot_id=""))
                logger.info(f"[LOA] V17.7.4: Script fidelity score: {fidelity_score}/100")
        except Exception as e:
            logger.warning(f"[LOA] Script fidelity check failed (non-blocking): {e}")

        passed = len(blocking_errors) == 0

        result = {
            "passed": passed,
            "verdicts": [v.to_dict() for v in verdicts],
            "auto_fixes": auto_fixes,
            "blocking_errors": blocking_errors,
            "fidelity_warnings": fidelity_warnings,
            "stats": {
                "total_shots": len(shots),
                "passed": sum(1 for v in verdicts if v.passed),
                "failed": sum(1 for v in verdicts if v.blocking),
                "warned": sum(1 for v in verdicts if v.verdict == "warn"),
                "auto_fixed": len(auto_fixes),
            }
        }

        self._log_action({"gate": "pre_generation", "result": result["stats"]})
        return result

    def _check_blocking_continuity(self, shots: List[Dict]) -> List[Dict]:
        """Check consecutive shots in same scene for blocking breaks."""
        warnings = []
        scenes = {}
        for shot in shots:
            sid = shot.get("shot_id", "")
            scene_id = sid.split("_")[0] if "_" in sid else "000"
            scenes.setdefault(scene_id, []).append(shot)

        for scene_id, scene_shots in scenes.items():
            prev_dir = None
            for shot in scene_shots:
                curr_dir = shot.get("screen_direction", "")
                if prev_dir and curr_dir and prev_dir == curr_dir:
                    # Same direction consecutive shots is fine
                    pass
                elif prev_dir and curr_dir and prev_dir != curr_dir:
                    # Direction change — check if there's a cutaway between
                    shot_type = shot.get("shot_type", "")
                    if shot_type not in ("establishing", "insert", "b_roll", "cutaway"):
                        warnings.append({
                            "check": "blocking_continuity",
                            "shot_id": shot.get("shot_id", ""),
                            "scene_id": scene_id,
                            "message": f"Screen direction changed from '{prev_dir}' to '{curr_dir}' without cutaway",
                            "suggestion": "add_cutaway_between",
                        })
                prev_dir = curr_dir

        return warnings

    # ═══════════════════════════════════════════════════
    # GATE 2: POST-GENERATION QA (scoring + regen policy)
    # ═══════════════════════════════════════════════════

    def post_generation_qa(self, shot: Dict, frame_path: str,
                           ref_path: str = None, location_master_path: str = None) -> LOAVerdict:
        """
        Score a generated first frame against references.
        Returns verdict with vision scores + auto-regen actions if needed.
        """
        if not FEATURE_LOA:
            return LOAVerdict("pass", {"skipped": True}, shot_id=shot.get("shot_id", ""))

        shot_id = shot.get("shot_id", "unknown")
        characters = shot.get("characters", [])
        evidence = {
            "check": "post_generation_qa",
            "frame_path": frame_path,
            "scores": {},
        }
        actions = []
        issues = []

        vs = self._get_vision_service()

        # ── Identity scoring ──
        if characters and ref_path and vs:
            try:
                id_result = vs.score_identity(frame_path, ref_path)
                # V27.1 FIX: vision_service returns "face_similarity" not "score"
                score = id_result.get("face_similarity", id_result.get("score", 0))
                logger.info(f"[LOA] Identity score for {shot_id}: {score:.3f} (raw: {list(id_result.keys())})")
                evidence["scores"]["identity"] = score
                evidence["scores"]["identity_pass"] = score >= self.thresholds["identity_pass"]

                if score < self.thresholds["identity_warn"]:
                    issues.append(f"Identity score {score:.2f} below warn threshold {self.thresholds['identity_warn']}")
                    if FEATURE_AUTO_REGEN:
                        actions.append({"action": "regen_frame", "shot_id": shot_id, "reason": "identity_mismatch"})
            except Exception as e:
                logger.warning(f"[LOA] Identity scoring failed for {shot_id}: {e}")
                evidence["scores"]["identity"] = None
                evidence["scores"]["identity_error"] = str(e)

        # ── Location scoring ──
        if location_master_path and vs:
            try:
                loc_result = vs.score_location(frame_path, location_master_path)
                # V27.1 FIX: vision_service returns "location_similarity" not "score"
                score = loc_result.get("location_similarity", loc_result.get("score", 0))
                evidence["scores"]["location"] = score
                evidence["scores"]["location_pass"] = score >= self.thresholds["location_pass"]

                if score < self.thresholds["location_warn"]:
                    issues.append(f"Location score {score:.2f} below warn threshold")
            except Exception as e:
                logger.warning(f"[LOA] Location scoring failed for {shot_id}: {e}")
                evidence["scores"]["location"] = None

        # ── Presence check (empty room detection) ──
        if characters and vs:
            try:
                presence = vs.detect_empty_room(frame_path)
                # V27.1 FIX: vision_service returns "person_detected" not "is_empty"
                is_empty = presence.get("is_empty", not presence.get("person_detected", True))
                evidence["scores"]["presence"] = "empty" if is_empty else "ok"
                evidence["scores"]["skin_ratio"] = presence.get("skin_ratio", 0)

                if is_empty:
                    issues.append("Empty room detected — expected character(s) present")
                    actions.append({"action": "regen_frame", "shot_id": shot_id, "reason": "empty_room"})
            except Exception as e:
                logger.warning(f"[LOA] Presence check failed for {shot_id}: {e}")
                evidence["scores"]["presence"] = "unknown"

        # ── Fast QA (sharpness/exposure) ──
        if vs:
            try:
                qa = vs.fast_qa(frame_path)
                evidence["scores"]["sharpness"] = qa.get("sharpness", 0)
                evidence["scores"]["brightness"] = qa.get("brightness", 0)
                evidence["scores"]["contrast"] = qa.get("contrast", 0)

                if qa.get("sharpness", 1) < self.thresholds["sharpness_min"]:
                    issues.append("Frame appears blurry")
            except Exception as e:
                logger.warning(f"[LOA] Fast QA failed for {shot_id}: {e}")

        # ── Determine verdict ──
        if any(a.get("action") == "regen_frame" for a in actions):
            verdict = "fail"
        elif issues:
            verdict = "warn"
        else:
            verdict = "pass"

        evidence["issues"] = issues
        evidence["needs_review"] = verdict != "pass"

        result = LOAVerdict(verdict, evidence, actions, shot_id=shot_id)
        self._log_action({"gate": "post_gen_qa", "shot_id": shot_id, "verdict": verdict, "issues": issues})
        return result

    # ═══════════════════════════════════════════════════
    # GATE 3: MULTI-ANGLE VARIANT RANKING
    # ═══════════════════════════════════════════════════

    def rank_variants(self, shot: Dict, variant_paths: List[str],
                      ref_path: str = None, location_master_path: str = None) -> Dict:
        """
        Rank multi-angle variants by weighted scoring.
        Returns {ranked: [{path, scores, total}], best: path, auto_regen: bool}

        Weights: identity=0.60, location=0.20, clip=0.10, composition=0.10
        """
        if not FEATURE_MULTI_ANGLE_AUTORANK or not FEATURE_LOA:
            return {"ranked": [], "best": variant_paths[0] if variant_paths else None, "auto_regen": False, "skipped": True}

        shot_id = shot.get("shot_id", "unknown")
        characters = shot.get("characters", [])
        vs = self._get_vision_service()

        scored = []
        for vpath in variant_paths:
            scores = {"identity": 0.5, "location": 0.5, "clip_alignment": 0.5, "composition": 0.5}

            # Identity
            if characters and ref_path and vs:
                try:
                    id_r = vs.score_identity(vpath, ref_path)
                    scores["identity"] = id_r.get("score", 0.5)
                except Exception:
                    pass

            # Location
            if location_master_path and vs:
                try:
                    loc_r = vs.score_location(vpath, location_master_path)
                    scores["location"] = loc_r.get("score", 0.5)
                except Exception:
                    pass

            # Fast QA (composition proxy)
            if vs:
                try:
                    qa = vs.fast_qa(vpath)
                    scores["composition"] = min(1.0, (qa.get("sharpness", 0.5) + qa.get("contrast", 0.5)) / 2)
                except Exception:
                    pass

            # Weighted total
            total = sum(scores[k] * VARIANT_WEIGHTS[k] for k in VARIANT_WEIGHTS)
            scored.append({"path": vpath, "scores": scores, "total": round(total, 4)})

        # Sort descending
        scored.sort(key=lambda x: x["total"], reverse=True)
        best = scored[0]["path"] if scored else None
        best_total = scored[0]["total"] if scored else 0

        # Auto-regen if ALL variants below threshold
        auto_regen = False
        if best_total < self.thresholds["identity_warn"] and FEATURE_AUTO_REGEN:
            auto_regen = True

        result = {
            "ranked": scored,
            "best": best,
            "best_score": best_total,
            "auto_regen": auto_regen,
            "shot_id": shot_id,
        }

        self._log_action({"gate": "rank_variants", "shot_id": shot_id, "best_score": best_total})
        return result

    # ═══════════════════════════════════════════════════
    # GATE 4: PRE-STITCH CONSISTENCY
    # ═══════════════════════════════════════════════════

    def pre_stitch_gate(self, shots: List[Dict]) -> Dict:
        """
        Validate scene/project consistency before FFmpeg stitch.
        Checks:
        - All shots approved
        - Vision scores present for approved shots (if vision enabled)
        - Extended shots have valid segments
        - No dangling variant state (selected variant must exist)
        """
        if not FEATURE_LOA:
            return {"passed": True, "skipped": True}

        issues = []
        warnings = []

        for shot in shots:
            shot_id = shot.get("shot_id", "unknown")

            # Must be approved
            if not shot.get("approved", False):
                issues.append({"shot_id": shot_id, "issue": "not_approved", "message": f"Shot {shot_id} is not approved"})

            # Must have video
            if not shot.get("video_path", ""):
                issues.append({"shot_id": shot_id, "issue": "no_video", "message": f"Shot {shot_id} has no video"})

            # Vision scores present (if enabled and shot was generated)
            if FEATURE_VISION_SERVICE and shot.get("first_frame_url", ""):
                vision = shot.get("vision", {})
                if not vision and shot.get("characters", []):
                    warnings.append({"shot_id": shot_id, "issue": "no_vision_scores",
                                    "message": f"Shot {shot_id} has no vision scores — run QA first"})

            # Extended shots: valid segments
            duration = shot.get("duration", 0)
            if duration > 20:
                segments = shot.get("segments", [])
                if not segments:
                    issues.append({"shot_id": shot_id, "issue": "missing_segments",
                                  "message": f"Shot {shot_id} is {duration}s but has no segments"})

            # Variant consistency
            variants = shot.get("_variants", [])
            if variants and not shot.get("first_frame_url", ""):
                warnings.append({"shot_id": shot_id, "issue": "dangling_variants",
                                "message": f"Shot {shot_id} has variants but no selected first frame"})

        passed = len(issues) == 0
        result = {
            "passed": passed,
            "issues": issues,
            "warnings": warnings,
            "stats": {
                "total": len(shots),
                "approved": sum(1 for s in shots if s.get("approved")),
                "with_video": sum(1 for s in shots if s.get("video_path")),
                "blocking_issues": len(issues),
                "warnings": len(warnings),
            }
        }

        self._log_action({"gate": "pre_stitch", "result": result["stats"]})
        return result

    # ═══════════════════════════════════════════════════
    # UTILITY: Persist vision scores to shot
    # ═══════════════════════════════════════════════════

    def persist_vision_scores(self, shot: Dict, verdict: LOAVerdict) -> Dict:
        """
        Write vision scores into shot metadata for bundle hydration.
        Returns the vision_badges dict that goes into bundle v2.
        """
        scores = verdict.evidence.get("scores", {})

        vision_badges = {
            "identity": scores.get("identity"),
            "location": scores.get("location"),
            "presence": scores.get("presence", "unknown"),
            "sharpness": scores.get("sharpness"),
            "needs_review": verdict.evidence.get("needs_review", False),
            "verdict": verdict.verdict,
            "timestamp": verdict.timestamp,
        }

        shot["vision"] = vision_badges
        shot["needs_review"] = vision_badges["needs_review"]

        return vision_badges

    # ═══════════════════════════════════════════════════
    # HEALTH CHECK
    # ═══════════════════════════════════════════════════

    def health(self) -> Dict:
        """Return LOA health status for the AAA health dashboard."""
        vs = self._get_vision_service()
        return {
            "loa_enabled": FEATURE_LOA,
            "vision_service_available": vs is not None,
            "feature_flags": {
                "FEATURE_VISION_SERVICE": FEATURE_VISION_SERVICE,
                "FEATURE_LOA": FEATURE_LOA,
                "FEATURE_MULTI_ANGLE_AUTORANK": FEATURE_MULTI_ANGLE_AUTORANK,
                "FEATURE_AUTO_REGEN": FEATURE_AUTO_REGEN,
            },
            "thresholds": self.thresholds,
            "variant_weights": VARIANT_WEIGHTS,
            "action_log_size": len(self.action_log),
        }


# ═══════════════════════════════════════════════════
# CONVENIENCE: one-call gate functions for server wiring
# ═══════════════════════════════════════════════════

def run_loa_pre_generation(shots: List[Dict], project_path: str,
                           cast_map: Dict = None, location_masters: Dict = None,
                           scene_manifest: List[Dict] = None) -> Dict:
    """Convenience: run LOA pre-gen gate. Returns {passed, auto_fixes, blocking_errors}."""
    loa = LogicalOversightAgent(project_path, cast_map=cast_map or {})
    return loa.pre_generation_gate(shots, location_masters=location_masters,
                                   scene_manifest=scene_manifest)


def run_loa_post_gen_qa(shot: Dict, frame_path: str, project_path: str,
                        ref_path: str = None, location_master_path: str = None,
                        cast_map: Dict = None) -> Dict:
    """Convenience: run LOA post-gen QA on single shot."""
    loa = LogicalOversightAgent(project_path, cast_map=cast_map or {})
    verdict = loa.post_generation_qa(shot, frame_path, ref_path, location_master_path)
    loa.persist_vision_scores(shot, verdict)
    return verdict.to_dict()


def run_loa_rank_variants(shot: Dict, variant_paths: List[str], project_path: str,
                          ref_path: str = None, location_master_path: str = None,
                          cast_map: Dict = None) -> Dict:
    """Convenience: rank multi-angle variants."""
    loa = LogicalOversightAgent(project_path, cast_map=cast_map or {})
    return loa.rank_variants(shot, variant_paths, ref_path, location_master_path)


def run_loa_pre_stitch(shots: List[Dict], project_path: str) -> Dict:
    """Convenience: run pre-stitch consistency gate."""
    loa = LogicalOversightAgent(project_path)
    return loa.pre_stitch_gate(shots)
