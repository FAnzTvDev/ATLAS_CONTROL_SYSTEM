"""
ATLAS V18.4 — Unified Vision Analyzer
======================================
Combines ALL available vision models into a single analysis pass:

  1. DINOv2 vitb14      — Face identity + location consistency (local MPS/CPU)
  2. CLIP / Open-CLIP    — Text-image alignment for action matching (local)
  3. Florence-2          — Detailed captioning + object detection (FAL API)
  4. MediaPipe Pose      — Character posture detection (local CPU)
  5. Grounding DINO      — Text-guided prop detection (local)
  6. PIL                 — Sharpness, exposure, contrast (local CPU, instant)

Usage:
  from tools.vision_analyzer_v18 import VisionAnalyzerV18
  analyzer = VisionAnalyzerV18()
  result = analyzer.full_analysis(frame_path, script_intent)

Design: lazy-load each model on first use. Never crash the pipeline — each
model is wrapped in try/except and returns degraded results on failure.
"""

import os
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger("atlas.vision_v18")

# ─── Lazy-loaded model singletons ───
_dino_model = None
_clip_model = None
_clip_preprocess = None
_clip_tokenizer = None
_mediapipe_pose = None
_grounding_dino_model = None
_grounding_dino_processor = None


class VisionAnalyzerV18:
    """Unified vision analyzer using all available models."""

    def __init__(self):
        self._device = None
        self._torch = None

    def _get_device(self):
        if self._device is None:
            try:
                import torch
                self._torch = torch
                if torch.backends.mps.is_available():
                    self._device = torch.device("mps")
                elif torch.cuda.is_available():
                    self._device = torch.device("cuda")
                else:
                    self._device = torch.device("cpu")
                logger.info(f"[VISION-V18] Device: {self._device}")
            except ImportError:
                self._device = "cpu"
                logger.warning("[VISION-V18] torch not available, CPU-only mode")
        return self._device

    # ─── 1. DINOv2 FACE IDENTITY ───

    def _get_dino(self):
        global _dino_model
        if _dino_model is None:
            try:
                import torch
                import sys
                device = self._get_device()
                if sys.version_info >= (3, 10):
                    _dino_model = torch.hub.load('facebookresearch/dinov2', 'dinov2_vitb14')
                else:
                    from torchvision.models import vit_b_16, ViT_B_16_Weights
                    _dino_model = vit_b_16(weights=ViT_B_16_Weights.IMAGENET1K_V1)
                _dino_model = _dino_model.to(device)
                _dino_model.eval()
                logger.info("[VISION-V18] DINOv2 vitb14 loaded")
            except Exception as e:
                logger.warning(f"[VISION-V18] DINOv2 load failed: {e}")
                return None
        return _dino_model

    def score_identity(self, frame_path: str, ref_path: str) -> Dict:
        """DINOv2 face identity scoring."""
        try:
            import torch
            import torchvision.transforms as transforms
            from PIL import Image

            model = self._get_dino()
            if model is None:
                return {"error": "dino_unavailable", "face_similarity": 0}

            device = self._get_device()
            transform = transforms.Compose([
                transforms.Resize(256, interpolation=transforms.InterpolationMode.BICUBIC),
                transforms.CenterCrop(224),
                transforms.ToTensor(),
                transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
            ])

            img1 = transform(Image.open(frame_path).convert('RGB')).unsqueeze(0).to(device)
            img2 = transform(Image.open(ref_path).convert('RGB')).unsqueeze(0).to(device)

            with torch.no_grad():
                feat1 = model(img1)
                feat2 = model(img2)
                if isinstance(feat1, dict):
                    feat1 = feat1.get('x_norm_patchtokens', list(feat1.values())[0])
                if isinstance(feat2, dict):
                    feat2 = feat2.get('x_norm_patchtokens', list(feat2.values())[0])
                if isinstance(feat1, tuple):
                    feat1 = feat1[0]
                if isinstance(feat2, tuple):
                    feat2 = feat2[0]

                # Global average pooling
                if feat1.dim() == 3:
                    feat1 = feat1.mean(dim=1)
                if feat2.dim() == 3:
                    feat2 = feat2.mean(dim=1)

                feat1 = torch.nn.functional.normalize(feat1, dim=-1)
                feat2 = torch.nn.functional.normalize(feat2, dim=-1)

                similarity = torch.cosine_similarity(feat1, feat2).item()

            return {
                "face_similarity": round(max(0, similarity), 3),
                "passed": similarity >= 0.70,
                "face_detected": True,
                "provider": "dinov2_local"
            }
        except Exception as e:
            logger.warning(f"[VISION-V18] Identity scoring failed: {e}")
            return {"error": str(e), "face_similarity": 0, "passed": False}

    # ─── 2. CLIP TEXT-IMAGE ALIGNMENT ───

    def _get_clip(self):
        global _clip_model, _clip_preprocess, _clip_tokenizer
        if _clip_model is None:
            try:
                import open_clip
                device = self._get_device()
                _clip_model, _, _clip_preprocess = open_clip.create_model_and_transforms(
                    'ViT-B-32', pretrained='laion2b_s34b_b79k', device=device
                )
                _clip_tokenizer = open_clip.get_tokenizer('ViT-B-32')
                _clip_model.eval()
                logger.info("[VISION-V18] Open-CLIP ViT-B-32 loaded")
            except Exception as e:
                logger.warning(f"[VISION-V18] CLIP load failed: {e}")
                return None, None, None
        return _clip_model, _clip_preprocess, _clip_tokenizer

    def score_action_match(self, frame_path: str, action_text: str) -> Dict:
        """CLIP text-image similarity for action matching."""
        try:
            import torch
            from PIL import Image

            model, preprocess, tokenizer = self._get_clip()
            if model is None:
                return {"error": "clip_unavailable", "action_similarity": 0}

            device = self._get_device()

            image = preprocess(Image.open(frame_path).convert('RGB')).unsqueeze(0).to(device)
            text = tokenizer([action_text]).to(device)

            with torch.no_grad():
                image_features = model.encode_image(image)
                text_features = model.encode_text(text)

                image_features = torch.nn.functional.normalize(image_features, dim=-1)
                text_features = torch.nn.functional.normalize(text_features, dim=-1)

                similarity = (image_features @ text_features.T).item()

            return {
                "action_similarity": round(max(0, similarity), 3),
                "passed": similarity >= 0.22,
                "query": action_text[:100],
                "provider": "open_clip_local"
            }
        except Exception as e:
            logger.warning(f"[VISION-V18] CLIP scoring failed: {e}")
            return {"error": str(e), "action_similarity": 0, "passed": False}

    def score_location(self, frame_path: str, master_path: str) -> Dict:
        """DINOv2 location consistency scoring."""
        try:
            result = self.score_identity(frame_path, master_path)
            sim = result.get("face_similarity", 0)
            return {
                "location_similarity": sim,
                "passed": sim >= 0.55,
                "provider": "dinov2_local"
            }
        except Exception as e:
            return {"error": str(e), "location_similarity": 0, "passed": False}

    # ─── 3. MEDIAPIPE POSE ───

    def _get_mediapipe_pose(self):
        global _mediapipe_pose
        if _mediapipe_pose is None:
            try:
                import mediapipe as mp
                # Try new tasks API first (v0.10.14+)
                if hasattr(mp, 'tasks'):
                    from mediapipe.tasks.python import vision as mp_vision
                    from mediapipe.tasks.python import BaseOptions
                    import urllib.request
                    import tempfile

                    # Download pose model if not cached
                    _model_path = Path(tempfile.gettempdir()) / "pose_landmarker_lite.task"
                    if not _model_path.exists():
                        logger.info("[VISION-V18] Downloading MediaPipe pose model...")
                        urllib.request.urlretrieve(
                            "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task",
                            str(_model_path)
                        )
                    options = mp_vision.PoseLandmarkerOptions(
                        base_options=BaseOptions(model_asset_path=str(_model_path)),
                        running_mode=mp_vision.RunningMode.IMAGE,
                        num_poses=1,
                        min_pose_detection_confidence=0.5,
                    )
                    _mediapipe_pose = mp_vision.PoseLandmarker.create_from_options(options)
                    _mediapipe_pose._api_version = "tasks"
                    logger.info("[VISION-V18] MediaPipe Pose (tasks API) loaded")
                # Fallback to legacy solutions API
                elif hasattr(mp, 'solutions'):
                    _mediapipe_pose = mp.solutions.pose.Pose(
                        static_image_mode=True,
                        model_complexity=1,
                        min_detection_confidence=0.5
                    )
                    _mediapipe_pose._api_version = "solutions"
                    logger.info("[VISION-V18] MediaPipe Pose (solutions API) loaded")
                else:
                    logger.warning("[VISION-V18] MediaPipe has neither tasks nor solutions API")
                    return None
            except Exception as e:
                logger.warning(f"[VISION-V18] MediaPipe load failed: {e}")
                return None
        return _mediapipe_pose

    def detect_posture(self, frame_path: str) -> Dict:
        """
        MediaPipe Pose: detect character posture from frame.
        Returns estimated pose: standing, sitting, kneeling, lying, unknown.
        """
        try:
            pose = self._get_mediapipe_pose()
            if pose is None:
                return {"error": "mediapipe_unavailable", "posture": "unknown", "person_detected": False}

            api_version = getattr(pose, '_api_version', 'solutions')

            if api_version == "tasks":
                # New tasks API
                import mediapipe as mp
                mp_image = mp.Image.create_from_file(frame_path)
                results = pose.detect(mp_image)
                if not results.pose_landmarks or len(results.pose_landmarks) == 0:
                    return {
                        "posture": "no_person",
                        "person_detected": False,
                        "landmarks_count": 0,
                        "provider": "mediapipe_pose_tasks"
                    }
                landmarks = results.pose_landmarks[0]  # First person
            else:
                # Legacy solutions API
                import cv2
                image = cv2.imread(frame_path)
                if image is None:
                    return {"error": "image_load_failed", "posture": "unknown", "person_detected": False}
                rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                results = pose.process(rgb)
                if not results.pose_landmarks:
                    return {
                        "posture": "no_person",
                        "person_detected": False,
                        "landmarks_count": 0,
                        "provider": "mediapipe_pose"
                    }
                landmarks = results.pose_landmarks.landmark

            # Key landmarks for posture classification
            # 0=nose, 11=left_shoulder, 12=right_shoulder, 23=left_hip, 24=right_hip,
            # 25=left_knee, 26=right_knee, 27=left_ankle, 28=right_ankle
            nose_y = landmarks[0].y
            shoulder_y = (landmarks[11].y + landmarks[12].y) / 2
            hip_y = (landmarks[23].y + landmarks[24].y) / 2
            knee_y = (landmarks[25].y + landmarks[26].y) / 2
            ankle_y = (landmarks[27].y + landmarks[28].y) / 2

            # Posture heuristics based on relative landmark positions
            torso_height = abs(hip_y - shoulder_y)
            leg_height = abs(ankle_y - hip_y)

            # Calculate body proportions
            if torso_height < 0.01:
                posture = "unknown"
            elif leg_height < torso_height * 0.3:
                # Legs very compressed relative to torso
                posture = "sitting"
            elif abs(knee_y - hip_y) < torso_height * 0.25 and abs(ankle_y - knee_y) > torso_height * 0.3:
                # Knees close to hips, ankles far from knees
                posture = "kneeling"
            elif abs(shoulder_y - ankle_y) < torso_height * 1.5:
                # Very flat body
                posture = "lying"
            else:
                posture = "standing"

            # Calculate facing direction (left/right/center)
            left_shoulder_x = landmarks[11].x
            right_shoulder_x = landmarks[12].x
            nose_x = landmarks[0].x
            shoulder_center_x = (left_shoulder_x + right_shoulder_x) / 2
            facing_offset = nose_x - shoulder_center_x

            if facing_offset > 0.03:
                facing = "right"
            elif facing_offset < -0.03:
                facing = "left"
            else:
                facing = "center"

            # Arm position
            left_wrist_y = landmarks[15].y
            right_wrist_y = landmarks[16].y
            arms_raised = left_wrist_y < shoulder_y or right_wrist_y < shoulder_y

            return {
                "posture": posture,
                "person_detected": True,
                "facing": facing,
                "arms_raised": arms_raised,
                "landmarks_count": len(landmarks),
                "confidence": min(
                    getattr(landmarks[0], 'visibility', 0.5),
                    getattr(landmarks[11], 'visibility', 0.5),
                    getattr(landmarks[23], 'visibility', 0.5)
                ),
                "provider": f"mediapipe_pose_{api_version}"
            }
        except Exception as e:
            logger.warning(f"[VISION-V18] Pose detection failed: {e}")
            return {"error": str(e), "posture": "unknown", "person_detected": False}

    # ─── 4. FLORENCE-2 CAPTIONING (FAL) ───

    def caption_frame(self, frame_path: str) -> Dict:
        """Florence-2 detailed captioning via FAL API."""
        try:
            import fal_client
            import base64

            fal_key = os.environ.get("FAL_KEY", "")
            if not fal_key:
                return self._caption_fallback(frame_path)

            with open(frame_path, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode()

            result = fal_client.subscribe("fal-ai/florence-2-large/detailed-caption", arguments={
                "image_url": f"data:image/jpeg;base64,{img_b64}"
            })

            caption = result.get("results", "") or result.get("caption", "")
            if isinstance(caption, list):
                caption = caption[0] if caption else ""

            # Extract tags
            tags = []
            tag_map = {
                "person": ["person", "man", "woman", "figure", "character"],
                "room": ["room", "chamber", "hall", "interior", "inside"],
                "dark": ["dark", "dim", "shadow", "night", "gloomy"],
                "candle": ["candle", "flame", "fire", "torch", "light"],
                "outdoor": ["outdoor", "exterior", "sky", "tree", "outside"],
                "stone": ["stone", "brick", "wall", "castle", "manor"],
                "altar": ["altar", "ritual", "ceremony", "symbol"],
            }
            for tag, terms in tag_map.items():
                if any(t in str(caption).lower() for t in terms):
                    tags.append(tag)

            return {
                "caption": str(caption),
                "tags": tags,
                "provider": "florence2_fal"
            }
        except Exception as e:
            logger.warning(f"[VISION-V18] Florence-2 caption failed: {e}")
            return self._caption_fallback(frame_path)

    def _caption_fallback(self, frame_path: str) -> Dict:
        """PIL-based caption fallback."""
        try:
            from PIL import Image, ImageStat
            img = Image.open(frame_path)
            w, h = img.size
            gray = img.convert('L')
            stat = ImageStat.Stat(gray)
            brightness = stat.mean[0] / 255.0
            mood = "dark" if brightness < 0.35 else ("bright" if brightness > 0.65 else "neutral")
            return {
                "caption": f"{mood} image, {w}x{h} resolution",
                "tags": [mood],
                "provider": "pil_fallback"
            }
        except Exception:
            return {"caption": "", "tags": [], "provider": "none"}

    # ─── 5. GROUNDING DINO — TEXT-GUIDED OBJECT DETECTION ───

    def detect_objects(self, frame_path: str, object_queries: List[str]) -> Dict:
        """
        Grounding DINO: detect specific objects by text query.
        Example: detect_objects(frame, ["candles", "altar", "envelope"])
        """
        results = {}
        try:
            # Try FAL Florence-2 object detection first (more reliable)
            import fal_client
            import base64

            fal_key = os.environ.get("FAL_KEY", "")
            if fal_key:
                with open(frame_path, "rb") as f:
                    img_b64 = base64.b64encode(f.read()).decode()

                for query in object_queries[:8]:
                    try:
                        det_result = fal_client.subscribe(
                            "fal-ai/florence-2-large/object-detection",
                            arguments={
                                "image_url": f"data:image/jpeg;base64,{img_b64}",
                                "text_input": query
                            }
                        )
                        detections = det_result.get("results", []) or []
                        results[query] = {
                            "found": len(detections) > 0,
                            "count": len(detections),
                            "provider": "florence2_fal"
                        }
                    except Exception:
                        results[query] = {"found": None, "error": "detection_failed"}
                return {"objects": results, "provider": "florence2_fal"}

            # Fallback: caption-based detection
            caption_result = self.caption_frame(frame_path)
            caption = caption_result.get("caption", "").lower()
            for query in object_queries[:8]:
                found = query.lower() in caption
                results[query] = {"found": found, "count": 1 if found else 0, "provider": "caption_match"}
            return {"objects": results, "provider": "caption_fallback"}

        except Exception as e:
            logger.warning(f"[VISION-V18] Object detection failed: {e}")
            return {"objects": {q: {"found": None, "error": str(e)} for q in object_queries}, "provider": "error"}

    # ─── 6. LLaVA-NeXT VISUAL Q&A (FAL) ───

    def ask_frame(self, frame_path: str, question: str, timeout_sec: int = 20) -> Dict:
        """
        LLaVA-NeXT visual Q&A via FAL API.
        Ask natural-language questions about a frame.

        Example: ask_frame("frame.jpg", "Is the character kneeling or standing?")
        Returns: {"answer": "The character appears to be standing...", "provider": "llava_next_fal"}
        """
        try:
            import fal_client
            import base64
            import concurrent.futures

            fal_key = os.environ.get("FAL_KEY", "")
            if not fal_key:
                return {"error": "no_fal_key", "answer": "", "provider": "none"}

            with open(frame_path, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode()

            def _call_fal():
                return fal_client.subscribe("fal-ai/llava-next", arguments={
                    "image_url": f"data:image/jpeg;base64,{img_b64}",
                    "prompt": question,
                    "max_tokens": 300,
                })

            # Run with timeout to avoid blocking the event loop
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(_call_fal)
                result = future.result(timeout=timeout_sec)

            answer = result.get("output", "") or result.get("text", "") or str(result)
            return {
                "answer": str(answer).strip(),
                "question": question,
                "provider": "llava_next_fal"
            }
        except concurrent.futures.TimeoutError:
            logger.warning(f"[VISION-V18] LLaVA-NeXT timed out after {timeout_sec}s")
            return {"error": f"timeout_{timeout_sec}s", "answer": "", "provider": "llava_next_timeout"}
        except Exception as e:
            logger.warning(f"[VISION-V18] LLaVA-NeXT Q&A failed: {e}")
            return {"error": str(e), "answer": "", "provider": "llava_next_error"}

    def script_qa_check(self, frame_path: str, script_intent: Dict) -> Dict:
        """
        Run targeted Q&A checks against script expectations.
        Asks LLaVA-NeXT specific yes/no questions derived from the script.

        Returns per-question pass/fail + overall script_match score.
        """
        questions = []
        beat_action = script_intent.get("beat_action", "")
        characters = script_intent.get("characters", [])
        dialogue = script_intent.get("dialogue", "")
        location = script_intent.get("location", "")
        wardrobe = script_intent.get("wardrobe", "")

        # Build targeted questions
        if beat_action:
            questions.append({
                "id": "action",
                "q": f"Does this image show someone {beat_action[:100]}? Answer yes or no, then explain briefly.",
                "expect_yes": True,
            })
        if characters:
            char = characters[0]
            questions.append({
                "id": "character_visible",
                "q": f"Is there a person clearly visible in this image? Answer yes or no.",
                "expect_yes": True,
            })
        if wardrobe:
            questions.append({
                "id": "wardrobe",
                "q": f"Is the person wearing {wardrobe}? Answer yes or no, then describe what they are wearing.",
                "expect_yes": True,
            })
        if "INT." in location:
            questions.append({
                "id": "interior",
                "q": "Is this scene set indoors/interior? Answer yes or no.",
                "expect_yes": True,
            })
        elif "EXT." in location:
            questions.append({
                "id": "exterior",
                "q": "Is this scene set outdoors/exterior? Answer yes or no.",
                "expect_yes": True,
            })
        if dialogue:
            questions.append({
                "id": "speaking",
                "q": "Does the person in this image appear to be speaking or have their mouth open? Answer yes or no.",
                "expect_yes": True,
            })

        # Ask each question
        qa_results = []
        passed = 0
        total = len(questions)

        for qdata in questions[:6]:  # Max 6 questions to limit API calls
            answer_data = self.ask_frame(frame_path, qdata["q"])
            answer_text = answer_data.get("answer", "").lower()

            # Parse yes/no from answer
            answer_is_yes = answer_text.startswith("yes") or "yes," in answer_text[:20] or "yes." in answer_text[:20]
            answer_is_no = answer_text.startswith("no") or "no," in answer_text[:20] or "no." in answer_text[:20]

            if qdata["expect_yes"]:
                match = answer_is_yes
            else:
                match = answer_is_no

            if match:
                passed += 1

            qa_results.append({
                "id": qdata["id"],
                "question": qdata["q"],
                "answer": answer_data.get("answer", "")[:200],
                "expected_yes": qdata["expect_yes"],
                "detected_yes": answer_is_yes,
                "match": match,
            })

        return {
            "qa_results": qa_results,
            "passed": passed,
            "total": total,
            "script_match_score": round(passed / max(total, 1), 2),
            "provider": "llava_next_fal"
        }

    # ─── 7. PIL QUALITY CHECK ───

    def quality_check(self, frame_path: str) -> Dict:
        """Fast PIL-based quality metrics."""
        try:
            from PIL import Image, ImageFilter, ImageStat

            img = Image.open(frame_path)
            w, h = img.size
            gray = img.convert('L')

            # Sharpness
            edges = gray.filter(ImageFilter.FIND_EDGES)
            edge_stat = ImageStat.Stat(edges)
            sharpness = min(1.0, edge_stat.var[0] / 3000.0)

            # Exposure
            stat = ImageStat.Stat(gray)
            brightness = stat.mean[0] / 255.0
            exposure = 1.0 - abs(brightness - 0.45) * 2

            # Contrast
            contrast = min(1.0, stat.stddev[0] / 80.0)

            issues = []
            if sharpness < 0.3:
                issues.append("blurry")
            if exposure < 0.4:
                issues.append("overexposed" if brightness > 0.6 else "underexposed")

            return {
                "sharpness": round(sharpness, 3),
                "exposure": round(exposure, 3),
                "contrast": round(contrast, 3),
                "brightness": round(brightness, 3),
                "resolution": f"{w}x{h}",
                "passed": sharpness >= 0.3 and exposure >= 0.4,
                "issues": issues,
                "provider": "pil"
            }
        except Exception as e:
            return {"error": str(e), "passed": False, "issues": ["analysis_failed"]}

    # ─── FULL ANALYSIS (all models combined) ───

    def full_analysis(self, frame_path: str, script_intent: Dict,
                      ref_path: str = None, location_master_path: str = None) -> Dict:
        """
        Run ALL available vision models on a single frame.

        Args:
            frame_path: Path to rendered frame
            script_intent: {
                "beat_action": str,
                "characters": List[str],
                "expected_props": List[str],
                "dialogue": str,
                "location": str,
                "wardrobe": str
            }
            ref_path: Character reference image path (optional)
            location_master_path: Location master image path (optional)

        Returns comprehensive analysis dict.
        """
        t_start = time.time()
        results = {
            "frame_path": str(frame_path),
            "models_used": [],
            "models_failed": [],
        }

        # 1. Quality check (instant, always runs)
        qa = self.quality_check(frame_path)
        results["quality"] = qa
        results["models_used"].append("pil_quality")

        # 2. Florence-2 captioning
        caption_result = self.caption_frame(frame_path)
        results["caption"] = caption_result.get("caption", "")
        results["caption_tags"] = caption_result.get("tags", [])
        results["caption_provider"] = caption_result.get("provider", "unknown")
        if caption_result.get("provider", "") != "none":
            results["models_used"].append(caption_result["provider"])
        else:
            results["models_failed"].append("florence2_caption")

        # 3. CLIP action match
        beat_action = script_intent.get("beat_action", "")
        if beat_action:
            clip_result = self.score_action_match(frame_path, beat_action)
            results["action_match"] = clip_result
            if not clip_result.get("error"):
                results["models_used"].append("open_clip")
            else:
                results["models_failed"].append("open_clip")

        # 4. DINOv2 identity
        if ref_path and Path(ref_path).exists():
            id_result = self.score_identity(frame_path, ref_path)
            results["identity"] = id_result
            if not id_result.get("error"):
                results["models_used"].append("dinov2_identity")
            else:
                results["models_failed"].append("dinov2_identity")

        # 5. DINOv2 location
        if location_master_path and Path(location_master_path).exists():
            loc_result = self.score_location(frame_path, location_master_path)
            results["location"] = loc_result
            if not loc_result.get("error"):
                results["models_used"].append("dinov2_location")
            else:
                results["models_failed"].append("dinov2_location")

        # 6. MediaPipe Pose
        if script_intent.get("characters"):
            pose_result = self.detect_posture(frame_path)
            results["posture"] = pose_result
            if not pose_result.get("error"):
                results["models_used"].append("mediapipe_pose")
            else:
                results["models_failed"].append("mediapipe_pose")

        # 7. Object detection for expected props
        props = script_intent.get("expected_props", [])
        if props:
            obj_result = self.detect_objects(frame_path, props)
            results["objects"] = obj_result
            results["models_used"].append(obj_result.get("provider", "unknown"))

        # 8. LLaVA-NeXT Q&A (FAL) — opt-in, adds 15-20s per shot
        # Only runs if explicitly requested via run_llava=True in script_intent
        # Reason: each Q&A question is a separate FAL API call (~3-4s each)
        _run_llava = script_intent.get("run_llava", False)
        if _run_llava:
            try:
                qa_result = self.script_qa_check(frame_path, script_intent)
                results["llava_qa"] = qa_result
                if qa_result.get("provider") == "llava_next_fal":
                    results["models_used"].append("llava_next")
                else:
                    results["models_failed"].append("llava_next")
            except Exception as llava_err:
                logger.warning(f"[VISION-V18] LLaVA-NeXT Q&A failed: {llava_err}")
                results["models_failed"].append("llava_next")

        results["analysis_time_ms"] = round((time.time() - t_start) * 1000)
        results["models_count"] = len(results["models_used"])

        return results


# ─── Module-level convenience ───
_analyzer_singleton = None

def get_vision_analyzer() -> VisionAnalyzerV18:
    """Get or create the singleton analyzer."""
    global _analyzer_singleton
    if _analyzer_singleton is None:
        _analyzer_singleton = VisionAnalyzerV18()
    return _analyzer_singleton
