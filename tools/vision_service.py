"""
ATLAS V17.6 — Vision Service (Plug-and-Play Eyes)
===================================================

Provider-agnostic vision layer that can swap between:
  - LOCAL: DINOv2 + CLIP + InsightFace/ArcFace + GroundingDINO (GPU)
  - FAL:   Florence-2 caption/detect + managed inference (API)
  - LITE:  PIL-only fallback (CPU, no ML)

Architecture (from Deep Research Report):
  ATLAS → VisionService → Provider → Results (always same schema)
  Policy (LOA) is SEPARATE from Perception (this file)

  Models per task:
    Identity   → ArcFace embeddings via InsightFace (primary) + DINOv2 face crop (fallback)
    Location   → DINOv2 image embeddings (cosine similarity vs master)
    Presence   → Florence-2 object detection (hosted) or GroundingDINO (local)
    Captioning → Florence-2 (hosted) or BLIP-2 (local)
    Blocking   → MediaPipe Pose/Face Mesh for head pose proxy (future)
    Aesthetic  → CLIP aesthetic predictor (WEAK signal only — never blocking)

  Caching:
    All assets keyed by sha256. Embeddings cached to avoid recomputation.
    Cache stored in pipeline_outputs/{project}/.vision_cache/

4 Core Layers:
  Layer 1 — Fast QA (blur, exposure, composition)
  Layer 2 — Identity + Continuity (ArcFace face match, outfit, cross-shot)
  Layer 3 — Scene/Location Consistency (DINOv2 embedding match)
  Layer 4 — Coverage + Blocking Intelligence (presence, people count)

Usage:
  from tools.vision_service import get_vision_service
  vs = get_vision_service(provider="local")  # or "fal" or "lite"
  result = vs.score_identity(frame_path, ref_path)
  result = vs.detect_empty_room(frame_path, expected_characters=["EVELYN"])
  result = vs.score_location(frame_path, location_master_path)
  result = vs.fast_qa(frame_path)
"""

import os
import json
import hashlib
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# =============================================================================
# RESPONSE SCHEMAS — Same shape regardless of provider
# =============================================================================

"""
FastQAResult:
{
    "passed": bool,
    "sharpness": float,        # 0-1 (1 = tack sharp)
    "exposure": float,         # 0-1 (0.5 = ideal)
    "contrast": float,         # 0-1
    "has_subject": bool,       # detected any foreground subject
    "composition_score": float,# 0-1 (rule of thirds, centering)
    "issues": ["blurry", "overexposed", "no_subject"]
}

IdentityResult:
{
    "passed": bool,
    "face_similarity": float,  # 0-1 (vs reference)
    "outfit_similarity": float,# 0-1 (vs reference, embedding)
    "face_detected": bool,
    "face_count": int,
    "expected_face_count": int,
    "is_blurred_face": bool,
    "identity_drift_risk": bool,
    "issues": ["face_mismatch", "wrong_face_count", "blurred_face"]
}

LocationResult:
{
    "passed": bool,
    "location_similarity": float,  # 0-1 (vs location master)
    "environment_match": bool,     # coarse: interior/exterior match
    "lighting_match": float,       # 0-1 (vs expected time_of_day)
    "issues": ["wrong_location", "lighting_mismatch"]
}

EmptyRoomResult:
{
    "passed": bool,              # True = NOT empty (person detected)
    "person_detected": bool,
    "person_count": int,
    "expected_person_count": int,
    "confidence": float,         # 0-1
    "issues": ["empty_room_expected_character", "too_many_people"]
}

CaptionResult:
{
    "caption": str,              # Free-form description of frame
    "tags": ["person", "room", "candle", "dark"],
    "mood": str,                 # "tense", "calm", "mysterious"
    "provider": str              # "blip2", "florence2", "fal"
}
"""


class VisionService:
    """Base class — all providers implement this interface."""

    def __init__(self, provider: str = "local"):
        self.provider = provider
        self._initialized = False

    def fast_qa(self, frame_path: str) -> Dict:
        """Layer 1: Fast quality check (blur, exposure, composition)."""
        raise NotImplementedError

    def score_identity(self, frame_path: str, ref_path: str,
                       expected_face_count: int = 1) -> Dict:
        """Layer 2: Face identity match against locked reference."""
        raise NotImplementedError

    def score_location(self, frame_path: str, location_master_path: str) -> Dict:
        """Layer 3: Location consistency against master image."""
        raise NotImplementedError

    def detect_empty_room(self, frame_path: str,
                          expected_characters: List[str] = None) -> Dict:
        """Layer 4: Detect if frame is missing expected characters."""
        raise NotImplementedError

    def caption(self, frame_path: str) -> Dict:
        """Utility: Generate description of frame contents."""
        raise NotImplementedError

    def batch_qa(self, frame_paths: List[str], ref_paths: Dict[str, str] = None) -> List[Dict]:
        """Run fast_qa + identity on multiple frames. Returns list of results."""
        results = []
        for fp in frame_paths:
            r = self.fast_qa(fp)
            if ref_paths and fp in ref_paths:
                r["identity"] = self.score_identity(fp, ref_paths[fp])
            results.append(r)
        return results


class LocalVisionService(VisionService):
    """
    Local GPU/CPU vision using:
    - DINOv2 for face embeddings
    - CLIP for prompt alignment
    - InsightFace / ArcFace for identity (optional)
    - PIL for fast QA metrics
    """

    def __init__(self):
        super().__init__(provider="local")
        self._analyzer = None
        self._vision_models = None

    def _get_vision_models(self):
        """V27.1: Load real DINOv2 + ArcFace via vision_models.py."""
        if self._vision_models is None:
            try:
                from tools.vision_models import get_vision_models
                self._vision_models = get_vision_models()
                self._initialized = True
                logger.info("[VISION] V27.1 vision models loaded (DINOv2 + ArcFace)")
            except ImportError:
                try:
                    from vision_models import get_vision_models
                    self._vision_models = get_vision_models()
                    self._initialized = True
                except ImportError:
                    logger.warning("[VISION] vision_models not available")
        return self._vision_models

    def _get_analyzer(self):
        if self._analyzer is None:
            try:
                from dino_clip_analyzer import get_hybrid_analyzer
                self._analyzer = get_hybrid_analyzer()
                self._initialized = True
                logger.info("[VISION] Local analyzer initialized (DINOv2 + CLIP)")
            except ImportError:
                logger.warning("[VISION] dino_clip_analyzer not available, trying V27.1 vision_models")
                return None
        return self._analyzer

    def fast_qa(self, frame_path: str) -> Dict:
        """PIL-based fast quality metrics."""
        try:
            from PIL import Image, ImageFilter, ImageStat
            img = Image.open(frame_path)
            w, h = img.size

            # Sharpness via Laplacian variance
            gray = img.convert('L')
            edges = gray.filter(ImageFilter.FIND_EDGES)
            edge_stat = ImageStat.Stat(edges)
            sharpness = min(1.0, edge_stat.var[0] / 3000.0)

            # Exposure via mean brightness
            stat = ImageStat.Stat(gray)
            brightness = stat.mean[0] / 255.0
            exposure = 1.0 - abs(brightness - 0.45) * 2  # 0.45 is ideal

            # Contrast via stddev
            contrast = min(1.0, stat.stddev[0] / 80.0)

            # Subject detection (simple center crop vs border brightness)
            center_crop = gray.crop((w//4, h//4, 3*w//4, 3*h//4))
            center_stat = ImageStat.Stat(center_crop)
            has_subject = abs(center_stat.mean[0] - stat.mean[0]) > 8  # Different from background

            issues = []
            if sharpness < 0.3:
                issues.append("blurry")
            if exposure < 0.4:
                issues.append("overexposed" if brightness > 0.6 else "underexposed")
            if not has_subject:
                issues.append("no_distinct_subject")

            passed = sharpness >= 0.3 and exposure >= 0.4

            return {
                "passed": passed,
                "sharpness": round(sharpness, 3),
                "exposure": round(exposure, 3),
                "contrast": round(contrast, 3),
                "has_subject": has_subject,
                "composition_score": round((sharpness + exposure + contrast) / 3, 3),
                "issues": issues,
                "resolution": f"{w}x{h}"
            }
        except Exception as e:
            return {"passed": False, "error": str(e), "issues": ["analysis_failed"]}

    def score_identity(self, frame_path: str, ref_path: str,
                       expected_face_count: int = 1) -> Dict:
        """DINOv2 + ArcFace face/identity scoring. V27.1: real model backends."""
        # V27.1: Try real vision models first
        vm = self._get_vision_models()
        if vm is not None:
            try:
                sim_result = vm.face_similarity(frame_path, ref_path)
                face_sim = sim_result.get("similarity", 0)
                face_count = sim_result.get("frame_face_count", 0)
                issues = []
                if face_sim < 0.50:
                    issues.append("face_mismatch")
                if face_count != expected_face_count:
                    issues.append(f"wrong_face_count_{face_count}_expected_{expected_face_count}")
                if sim_result.get("error"):
                    issues.append(sim_result["error"])
                return {
                    "passed": face_sim >= 0.50 and not issues,
                    "face_similarity": round(face_sim, 3),
                    "outfit_similarity": 0.0,  # not yet scored
                    "face_detected": face_count > 0,
                    "face_count": face_count,
                    "expected_face_count": expected_face_count,
                    "is_blurred_face": False,
                    "identity_drift_risk": face_sim < 0.60,
                    "hybrid_score": round(face_sim, 3),
                    "backend": "arcface_v27.1",
                    "issues": issues,
                }
            except Exception as e:
                logger.warning(f"[VISION] V27.1 ArcFace scoring failed: {e}, trying legacy")

        # Legacy fallback
        analyzer = self._get_analyzer()
        if not analyzer:
            return {"passed": False, "error": "analyzer_unavailable", "issues": ["no_vision_model"]}

        try:
            result = analyzer.analyze_comprehensive(frame_path, ref_path, "")
            face_sim = result.get("dino_face", 0)
            hybrid = result.get("hybrid_score", 0)
            is_blurred = result.get("is_face_blurred", False)
            face_sharpness = result.get("face_sharpness", 0)

            issues = []
            if face_sim < 0.70:
                issues.append("face_mismatch")
            if is_blurred:
                issues.append("blurred_face")
            if result.get("needs_regeneration", False):
                issues.append("needs_regeneration")

            return {
                "passed": face_sim >= 0.70 and not is_blurred,
                "face_similarity": round(face_sim, 3),
                "outfit_similarity": round(result.get("clip_alignment", 0), 3),
                "face_detected": face_sim > 0.1,
                "face_count": 1 if face_sim > 0.1 else 0,
                "expected_face_count": expected_face_count,
                "is_blurred_face": is_blurred,
                "identity_drift_risk": face_sim < 0.75,
                "hybrid_score": round(hybrid, 3),
                "issues": issues
            }
        except Exception as e:
            return {"passed": False, "error": str(e), "issues": ["scoring_failed"]}

    def score_location(self, frame_path: str, location_master_path: str) -> Dict:
        """DINOv2-based location similarity scoring. V27.1: real model backend."""
        # V27.1: Try real DINOv2 first
        vm = self._get_vision_models()
        if vm is not None:
            try:
                loc_sim = vm.image_similarity(frame_path, location_master_path)
                issues = []
                if loc_sim < 0.50:
                    issues.append("wrong_location")
                return {
                    "passed": loc_sim >= 0.50,
                    "location_similarity": round(loc_sim, 3),
                    "environment_match": loc_sim >= 0.60,
                    "issues": issues,
                    "backend": "dinov2_v27.1",
                }
            except Exception as e:
                logger.warning(f"[VISION] V27.1 DINOv2 location scoring failed: {e}, trying legacy")

        # Legacy fallback
        analyzer = self._get_analyzer()
        if not analyzer:
            return {"passed": False, "error": "analyzer_unavailable", "issues": ["no_vision_model"]}

        try:
            result = analyzer.analyze_comprehensive(
                frame_path, location_master_path, "location scene"
            )
            loc_sim = result.get("clip_alignment", 0)
            hybrid = result.get("hybrid_score", 0)

            issues = []
            if loc_sim < 0.60:
                issues.append("wrong_location")

            return {
                "passed": loc_sim >= 0.60,
                "location_similarity": round(loc_sim, 3),
                "environment_match": loc_sim >= 0.50,
                "lighting_match": round(hybrid, 3),
                "issues": issues
            }
        except Exception as e:
            return {"passed": False, "error": str(e), "issues": ["scoring_failed"]}

    def detect_empty_room(self, frame_path: str,
                          expected_characters: List[str] = None) -> Dict:
        """
        Detect if frame is missing expected characters.
        Uses a combination of:
        1. Face detection (is there a face at all?)
        2. Brightness/contrast analysis of center region (person creates contrast)
        3. If DINO available, use feature activation to detect human-like regions
        """
        expected_count = len(expected_characters) if expected_characters else 0

        try:
            from PIL import Image, ImageStat, ImageFilter
            img = Image.open(frame_path)
            w, h = img.size
            gray = img.convert('L')

            # Method 1: Skin tone detection (simple heuristic)
            rgb = img.convert('RGB')
            pixels = list(rgb.getdata())
            skin_count = 0
            sample_size = min(len(pixels), 10000)
            step = max(1, len(pixels) // sample_size)
            for i in range(0, len(pixels), step):
                r, g, b = pixels[i]
                # Simple skin tone heuristic
                if r > 95 and g > 40 and b > 20 and r > g and r > b and abs(r - g) > 15 and r - b > 15:
                    skin_count += 1
            skin_ratio = skin_count / (sample_size or 1)
            has_skin = skin_ratio > 0.02  # At least 2% skin-tone pixels

            # Method 2: Center region complexity (people create texture)
            center = gray.crop((w//4, h//4, 3*w//4, 3*h//4))
            center_edges = center.filter(ImageFilter.FIND_EDGES)
            edge_stat = ImageStat.Stat(center_edges)
            center_complexity = edge_stat.var[0]
            has_complex_center = center_complexity > 800

            # Method 3: DINOv2 features (if available)
            person_detected_dino = False
            analyzer = self._get_analyzer()
            if analyzer and expected_characters:
                # Use CLIP to check for "person" in the image
                try:
                    # Score against a generic "person standing in a room" prompt
                    result = analyzer.analyze_comprehensive(
                        frame_path, frame_path, "a person standing in a room"
                    )
                    clip_score = result.get("clip_alignment", 0)
                    person_detected_dino = clip_score > 0.25
                except Exception:
                    pass

            # Combine signals
            person_detected = has_skin or person_detected_dino
            person_count = 1 if person_detected else 0

            issues = []
            if expected_count > 0 and not person_detected:
                issues.append(f"empty_room_expected_{','.join(expected_characters[:3])}")

            passed = not (expected_count > 0 and not person_detected)

            return {
                "passed": passed,
                "person_detected": person_detected,
                "person_count": person_count,
                "expected_person_count": expected_count,
                "confidence": round(skin_ratio * 10, 3) if has_skin else round(0.1 if has_complex_center else 0.0, 3),
                "signals": {
                    "skin_tone": has_skin,
                    "center_complexity": has_complex_center,
                    "dino_person": person_detected_dino,
                    "skin_ratio": round(skin_ratio, 4)
                },
                "issues": issues
            }
        except Exception as e:
            return {"passed": False, "error": str(e), "issues": ["detection_failed"]}

    def caption(self, frame_path: str) -> Dict:
        """Basic caption using CLIP scores against common descriptors."""
        try:
            tags = []
            from PIL import Image
            img = Image.open(frame_path)

            # Use fast_qa for basic info
            qa = self.fast_qa(frame_path)
            if qa.get("has_subject"):
                tags.append("subject_present")
            if qa.get("sharpness", 0) > 0.6:
                tags.append("sharp")

            # Try empty room detection
            er = self.detect_empty_room(frame_path)
            if er.get("person_detected"):
                tags.append("person")
            else:
                tags.append("empty_scene")

            return {
                "caption": f"{'Person in scene' if 'person' in tags else 'Empty scene'}, {'sharp' if 'sharp' in tags else 'soft'} image",
                "tags": tags,
                "mood": "unknown",
                "provider": "local_basic"
            }
        except Exception as e:
            return {"caption": "", "tags": [], "mood": "unknown", "provider": "error", "error": str(e)}


class LiteVisionService(VisionService):
    """
    Lightweight PIL-only fallback. No ML models required.
    Only supports Layer 1 (fast QA) and basic empty room detection.
    """

    def __init__(self):
        super().__init__(provider="lite")
        self._initialized = True

    def fast_qa(self, frame_path: str) -> Dict:
        return LocalVisionService().fast_qa(frame_path)

    def score_identity(self, frame_path: str, ref_path: str,
                       expected_face_count: int = 1) -> Dict:
        return {
            "passed": False,
            "error": "lite_mode_no_identity_scoring",
            "face_similarity": 0,
            "issues": ["vision_lite_mode"]
        }

    def score_location(self, frame_path: str, location_master_path: str) -> Dict:
        return {
            "passed": False,
            "error": "lite_mode_no_location_scoring",
            "location_similarity": 0,
            "issues": ["vision_lite_mode"]
        }

    def detect_empty_room(self, frame_path: str,
                          expected_characters: List[str] = None) -> Dict:
        # Use PIL-based skin detection from LocalVisionService
        return LocalVisionService().detect_empty_room(frame_path, expected_characters)

    def caption(self, frame_path: str) -> Dict:
        return {"caption": "", "tags": [], "mood": "unknown", "provider": "lite"}


class FALVisionService(VisionService):
    """
    FAL.ai hosted inference provider.
    Uses Florence-2 for captioning + object detection/phrase grounding.
    Uses InsightFace/ArcFace for identity scoring (local preferred, FAL fallback).

    Research recommendation: Florence-2 is uniquely aligned with ATLAS because it's
    a unified prompt-based model supporting captioning, detection, grounding, and
    segmentation under one consistent interface.
    """

    def __init__(self):
        super().__init__(provider="fal")
        self._fal_key = os.environ.get("FAL_KEY", "")
        self._initialized = bool(self._fal_key)
        self._cache_dir = None
        if not self._fal_key:
            logger.warning("[VISION-FAL] FAL_KEY not set — FAL provider unavailable")

    def _init_cache(self, project_path: str = None):
        if project_path and not self._cache_dir:
            self._cache_dir = Path(project_path) / ".vision_cache"
            self._cache_dir.mkdir(exist_ok=True)

    def _file_hash(self, path: str) -> str:
        """SHA256 hash for cache keying."""
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()[:16]

    def _call_fal(self, model_id: str, payload: Dict) -> Dict:
        """Call FAL API synchronously."""
        try:
            import fal_client
            result = fal_client.subscribe(model_id, arguments=payload)
            return result
        except ImportError:
            logger.warning("[VISION-FAL] fal_client not installed")
            return {"error": "fal_client_not_installed"}
        except Exception as e:
            logger.warning(f"[VISION-FAL] API call failed: {e}")
            return {"error": str(e)}

    def fast_qa(self, frame_path: str) -> Dict:
        """PIL-based fast QA (same as local — no need for hosted inference)."""
        return LocalVisionService().fast_qa(frame_path)

    def score_identity(self, frame_path: str, ref_path: str,
                       expected_face_count: int = 1) -> Dict:
        """
        Identity scoring. Tries local InsightFace/ArcFace first,
        falls back to DINOv2 face crop similarity.

        Research: ArcFace is designed for discriminative face embeddings;
        InsightFace provides production toolchains. ArcFace similarity
        should be the PRIMARY identity metric with threshold 0.82.
        """
        # Try local analyzer first (preferred for identity)
        try:
            local = LocalVisionService()
            result = local.score_identity(frame_path, ref_path, expected_face_count)
            if result.get("face_similarity", 0) > 0:
                result["provider"] = "local_dino"
                return result
        except Exception:
            pass

        # Fallback: use FAL Florence-2 for person detection + basic scoring
        if self._fal_key:
            try:
                import base64
                with open(frame_path, "rb") as f:
                    img_b64 = base64.b64encode(f.read()).decode()

                # Florence-2 phrase grounding for "person" detection
                result = self._call_fal("fal-ai/florence-2-large/detailed-caption", {
                    "image_url": f"data:image/jpeg;base64,{img_b64}"
                })
                caption = result.get("results", "") or result.get("caption", "")

                # Parse caption for person-related terms
                person_terms = ["person", "man", "woman", "figure", "character", "face"]
                has_person = any(term in str(caption).lower() for term in person_terms)

                return {
                    "passed": has_person,
                    "face_similarity": 0.5 if has_person else 0.0,
                    "face_detected": has_person,
                    "face_count": 1 if has_person else 0,
                    "expected_face_count": expected_face_count,
                    "is_blurred_face": False,
                    "identity_drift_risk": True,  # FAL can't do precise identity
                    "issues": [] if has_person else ["no_person_detected_fal"],
                    "provider": "fal_florence2",
                    "caption": str(caption)[:200]
                }
            except Exception as e:
                return {"passed": False, "error": str(e), "issues": ["fal_scoring_failed"], "provider": "fal_error"}

        return {"passed": False, "error": "no_provider_available", "issues": ["no_identity_provider"]}

    def score_location(self, frame_path: str, location_master_path: str) -> Dict:
        """
        Location scoring. Uses local DINOv2 embeddings preferred.
        Research: DINOv2 is strong for "visual similarity without text" —
        trained for robust all-purpose visual features.
        """
        try:
            local = LocalVisionService()
            result = local.score_location(frame_path, location_master_path)
            if result.get("location_similarity", 0) > 0:
                result["provider"] = "local_dino"
                return result
        except Exception:
            pass

        return {"passed": False, "location_similarity": 0, "issues": ["no_location_provider"], "provider": "none"}

    def detect_empty_room(self, frame_path: str,
                          expected_characters: List[str] = None) -> Dict:
        """
        Empty room detection via Florence-2 object detection.
        Research: Florence-2 supports open-vocabulary detection and
        phrase grounding — "expected people count" derived from shot.characters.
        """
        expected_count = len(expected_characters) if expected_characters else 0

        # Try local first
        local_result = LocalVisionService().detect_empty_room(frame_path, expected_characters)

        # If local says person detected OR no FAL key, return local
        if local_result.get("person_detected", False) or not self._fal_key:
            local_result["provider"] = "local_pil"
            return local_result

        # FAL Florence-2 detection for "person"
        if self._fal_key and expected_count > 0:
            try:
                import base64
                with open(frame_path, "rb") as f:
                    img_b64 = base64.b64encode(f.read()).decode()

                result = self._call_fal("fal-ai/florence-2-large/object-detection", {
                    "image_url": f"data:image/jpeg;base64,{img_b64}",
                    "text_input": "person"
                })

                detections = result.get("results", []) or []
                person_count = len([d for d in detections if "person" in str(d).lower()])

                return {
                    "passed": person_count >= 1,
                    "person_detected": person_count >= 1,
                    "person_count": person_count,
                    "expected_person_count": expected_count,
                    "confidence": 0.8 if person_count >= 1 else 0.1,
                    "signals": {"fal_detections": person_count, "local_skin": local_result.get("signals", {})},
                    "issues": [] if person_count >= 1 else [f"empty_room_fal_expected_{','.join(expected_characters[:3])}"],
                    "provider": "fal_florence2"
                }
            except Exception as e:
                logger.warning(f"[VISION-FAL] Detection failed: {e}")

        local_result["provider"] = "local_pil_fallback"
        return local_result

    def caption(self, frame_path: str) -> Dict:
        """
        Caption via Florence-2 (hosted on FAL).
        Research: Florence-2 is explicitly designed as unified prompt-based model
        supporting captioning. FAL exposes Florence-2 caption endpoints.
        """
        if not self._fal_key:
            return LocalVisionService().caption(frame_path)

        try:
            import base64
            with open(frame_path, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode()

            result = self._call_fal("fal-ai/florence-2-large/detailed-caption", {
                "image_url": f"data:image/jpeg;base64,{img_b64}"
            })

            caption_text = result.get("results", "") or result.get("caption", "")

            # Extract tags from caption
            tags = []
            tag_terms = {
                "person": ["person", "man", "woman", "figure"],
                "room": ["room", "chamber", "hall", "interior"],
                "dark": ["dark", "dim", "shadow", "night"],
                "candle": ["candle", "flame", "fire", "torch"],
                "outdoor": ["outdoor", "exterior", "sky", "tree"],
            }
            for tag, terms in tag_terms.items():
                if any(t in str(caption_text).lower() for t in terms):
                    tags.append(tag)

            return {
                "caption": str(caption_text)[:500],
                "tags": tags,
                "mood": "unknown",
                "provider": "fal_florence2"
            }
        except Exception as e:
            return {"caption": "", "tags": [], "mood": "unknown", "provider": "fal_error", "error": str(e)}


# =============================================================================
# EMBEDDING CACHE — sha256-keyed for reuse
# =============================================================================

class EmbeddingCache:
    """
    On-disk cache for vision embeddings keyed by sha256.
    Stored in pipeline_outputs/{project}/.vision_cache/
    """

    def __init__(self, cache_dir: str = None):
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self._memory = {}

    def _key(self, file_path: str) -> str:
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()[:16]

    def get(self, file_path: str, model: str = "default") -> Optional[Dict]:
        key = f"{self._key(file_path)}_{model}"
        if key in self._memory:
            return self._memory[key]
        if self.cache_dir:
            cache_file = self.cache_dir / f"{key}.json"
            if cache_file.exists():
                try:
                    data = json.loads(cache_file.read_text())
                    self._memory[key] = data
                    return data
                except Exception:
                    pass
        return None

    def put(self, file_path: str, model: str, data: Dict):
        key = f"{self._key(file_path)}_{model}"
        self._memory[key] = data
        if self.cache_dir:
            try:
                self.cache_dir.mkdir(parents=True, exist_ok=True)
                cache_file = self.cache_dir / f"{key}.json"
                cache_file.write_text(json.dumps(data))
            except Exception:
                pass


# =============================================================================
# FACTORY — Get the best available vision service
# =============================================================================

_cached_service = None

def get_vision_service(provider: str = "auto") -> VisionService:
    """
    Get the best available vision service.

    provider:
      "auto"  — try local (GPU), fall back to lite
      "local" — force local (requires dino_clip_analyzer)
      "lite"  — PIL-only, no ML
      "fal"   — (future) FAL API managed inference
    """
    global _cached_service

    if _cached_service and (provider == "auto" or _cached_service.provider == provider):
        return _cached_service

    if provider == "auto":
        # Priority: local GPU → FAL hosted → lite PIL
        try:
            svc = LocalVisionService()
            svc._get_analyzer()  # Test if ML models load
            if svc._initialized:
                _cached_service = svc
                logger.info("[VISION] Using local provider (DINOv2 + CLIP)")
                return svc
        except Exception:
            pass
        # Try FAL if key available
        fal_key = os.environ.get("FAL_KEY", "")
        if fal_key:
            svc = FALVisionService()
            if svc._initialized:
                _cached_service = svc
                logger.info("[VISION] Using FAL provider (Florence-2)")
                return svc
        _cached_service = LiteVisionService()
        logger.info("[VISION] Using lite provider (PIL-only)")
        return _cached_service

    elif provider == "local":
        svc = LocalVisionService()
        _cached_service = svc
        return svc

    elif provider == "lite":
        svc = LiteVisionService()
        _cached_service = svc
        return svc

    elif provider == "fal":
        svc = FALVisionService()
        if svc._initialized:
            _cached_service = svc
            return svc
        logger.warning("[VISION] FAL provider needs FAL_KEY, falling back to lite")
        svc = LiteVisionService()
        _cached_service = svc
        return svc

    else:
        raise ValueError(f"Unknown vision provider: {provider}")


# =============================================================================
# CONVENIENCE — Vision gate for generation pipeline
# =============================================================================

def vision_gate_check(frame_path: str, shot: dict, ref_path: str = None,
                      location_master_path: str = None) -> Dict:
    """
    Run all applicable vision checks on a generated frame.
    Returns a combined result with pass/fail + all issues.

    Used after generation to detect:
    - Empty rooms when characters expected
    - Face mismatch against locked reference
    - Location mismatch against master
    - Basic quality issues (blur, exposure)
    """
    vs = get_vision_service("auto")
    result = {
        "passed": True,
        "shot_id": shot.get("shot_id", ""),
        "checks": {},
        "issues": [],
        "suggestions": []
    }

    # Layer 1: Fast QA
    qa = vs.fast_qa(frame_path)
    result["checks"]["fast_qa"] = qa
    if not qa.get("passed", True):
        result["passed"] = False
        result["issues"].extend(qa.get("issues", []))
        result["suggestions"].append("Regenerate: image quality below threshold")

    # Layer 2: Identity (if ref available)
    if ref_path and Path(ref_path).exists():
        identity = vs.score_identity(frame_path, ref_path)
        result["checks"]["identity"] = identity
        if not identity.get("passed", True):
            result["passed"] = False
            result["issues"].extend(identity.get("issues", []))
            result["suggestions"].append("Regenerate: face doesn't match reference")

    # Layer 3: Location (if master available)
    if location_master_path and Path(location_master_path).exists():
        location = vs.score_location(frame_path, location_master_path)
        result["checks"]["location"] = location
        if not location.get("passed", True):
            result["issues"].extend(location.get("issues", []))
            # Location mismatch is a warning, not blocking
            result["suggestions"].append("Review: location may not match master")

    # Layer 4: Empty room detection
    characters = shot.get("characters", [])
    if characters:
        empty_check = vs.detect_empty_room(frame_path, characters)
        result["checks"]["empty_room"] = empty_check
        if not empty_check.get("passed", True):
            result["passed"] = False
            result["issues"].extend(empty_check.get("issues", []))
            result["suggestions"].append(
                f"CRITICAL: Expected {', '.join(characters[:3])} but frame appears empty — add character reference and regenerate"
            )

    return result
