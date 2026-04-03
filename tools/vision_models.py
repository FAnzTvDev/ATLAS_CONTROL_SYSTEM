#!/usr/bin/env python3
"""
ATLAS V27.1 — Vision Models (DINOv2 + ArcFace)
================================================
Actual model backends for identity and location scoring.
Replaces the missing dino_clip_analyzer with real torch implementations.

Usage:
    from tools.vision_models import VisionModels
    vm = VisionModels()  # lazy loads on first use
    sim = vm.face_similarity(frame_path, ref_path)    # ArcFace cosine
    sim = vm.image_similarity(frame_path, ref_path)   # DINOv2 cosine
    faces = vm.detect_faces(frame_path)                # MTCNN bboxes
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# Singleton instance
_instance = None


class VisionModels:
    """Lazy-loading wrapper for DINOv2 (timm) + ArcFace (facenet-pytorch)."""

    def __init__(self):
        self._dino_model = None
        self._dino_transform = None
        self._arcface_model = None
        self._mtcnn = None
        self._device = "cpu"

    # -------------------------------------------------------------------------
    # Lazy loaders
    # -------------------------------------------------------------------------

    def _load_dino(self):
        if self._dino_model is not None:
            return
        import torch
        import timm
        from timm.data import resolve_data_config
        from timm.data.transforms_factory import create_transform

        logger.info("[VISION] Loading DINOv2 (vit_small_patch14_dinov2)...")
        self._dino_model = timm.create_model(
            "vit_small_patch14_dinov2.lvd142m",
            pretrained=True,
            num_classes=0,  # remove classifier head → raw embeddings
        )
        self._dino_model.eval()
        config = resolve_data_config(self._dino_model.pretrained_cfg)
        self._dino_transform = create_transform(**config)
        logger.info("[VISION] DINOv2 ready (384-dim embeddings)")

    def _load_arcface(self):
        if self._arcface_model is not None:
            return
        from facenet_pytorch import MTCNN, InceptionResnetV1

        logger.info("[VISION] Loading ArcFace (InceptionResnetV1 vggface2)...")
        self._mtcnn = MTCNN(
            image_size=160,
            margin=20,
            min_face_size=40,
            thresholds=[0.6, 0.7, 0.7],
            keep_all=True,
            device=self._device,
        )
        self._arcface_model = InceptionResnetV1(pretrained="vggface2").eval()
        logger.info("[VISION] ArcFace ready (512-dim face embeddings)")

    # -------------------------------------------------------------------------
    # Core operations
    # -------------------------------------------------------------------------

    def _load_image(self, path: str):
        """Load PIL image, convert to RGB."""
        from PIL import Image
        return Image.open(path).convert("RGB")

    def dino_embedding(self, image_path: str) -> np.ndarray:
        """Get DINOv2 embedding for a full image (384-dim for vit_small)."""
        import torch
        self._load_dino()
        img = self._load_image(image_path)
        tensor = self._dino_transform(img).unsqueeze(0)
        with torch.no_grad():
            emb = self._dino_model(tensor)
        return emb.squeeze().numpy()

    def detect_faces(self, image_path: str) -> List[Dict]:
        """Detect faces using MTCNN. Returns list of {box, prob, face_tensor}."""
        import torch
        self._load_arcface()
        img = self._load_image(image_path)
        boxes, probs = self._mtcnn.detect(img)
        if boxes is None:
            return []
        faces = []
        for i, (box, prob) in enumerate(zip(boxes, probs)):
            faces.append({
                "box": box.tolist(),
                "prob": float(prob),
                "index": i,
            })
        return faces

    def face_embeddings(self, image_path: str) -> List[np.ndarray]:
        """Extract ArcFace embeddings for all detected faces."""
        import torch
        self._load_arcface()
        img = self._load_image(image_path)
        # Get aligned face tensors
        faces = self._mtcnn(img)
        if faces is None:
            return []
        if faces.dim() == 3:
            faces = faces.unsqueeze(0)
        embeddings = []
        with torch.no_grad():
            for face_tensor in faces:
                emb = self._arcface_model(face_tensor.unsqueeze(0))
                embeddings.append(emb.squeeze().numpy())
        return embeddings

    def face_similarity(self, frame_path: str, ref_path: str) -> Dict:
        """
        Compare faces between a generated frame and a reference image.
        Returns cosine similarity and face count info.
        """
        frame_faces = self.face_embeddings(frame_path)
        ref_faces = self.face_embeddings(ref_path)

        if not ref_faces:
            return {
                "similarity": 0.0,
                "frame_face_count": len(frame_faces),
                "ref_face_count": 0,
                "matched": False,
                "error": "no_face_in_reference",
            }
        if not frame_faces:
            return {
                "similarity": 0.0,
                "frame_face_count": 0,
                "ref_face_count": len(ref_faces),
                "matched": False,
                "error": "no_face_in_frame",
            }

        # Best match: each ref face's best cosine sim against frame faces
        best_sim = 0.0
        for ref_emb in ref_faces:
            for frame_emb in frame_faces:
                cos = float(np.dot(ref_emb, frame_emb) / (
                    np.linalg.norm(ref_emb) * np.linalg.norm(frame_emb) + 1e-8
                ))
                best_sim = max(best_sim, cos)

        return {
            "similarity": round(best_sim, 4),
            "frame_face_count": len(frame_faces),
            "ref_face_count": len(ref_faces),
            "matched": best_sim >= 0.5,
            "confidence": "high" if best_sim >= 0.7 else "medium" if best_sim >= 0.5 else "low",
        }

    def image_similarity(self, path_a: str, path_b: str) -> float:
        """DINOv2 cosine similarity between two images (location/environment matching)."""
        emb_a = self.dino_embedding(path_a)
        emb_b = self.dino_embedding(path_b)
        cos = float(np.dot(emb_a, emb_b) / (
            np.linalg.norm(emb_a) * np.linalg.norm(emb_b) + 1e-8
        ))
        return round(cos, 4)

    def score_frame(self, frame_path: str, char_ref_paths: List[str],
                    location_master_path: Optional[str] = None) -> Dict:
        """
        Full probe scoring for a single generated frame.
        Returns identity scores per character + location score + face detection.
        """
        result = {
            "frame": frame_path,
            "faces_detected": [],
            "identity_scores": [],
            "location_score": None,
            "overall_pass": True,
            "issues": [],
        }

        # Face detection
        faces = self.detect_faces(frame_path)
        result["faces_detected"] = faces
        result["face_count"] = len(faces)

        # Identity per character ref
        for ref_path in char_ref_paths:
            ref_name = Path(ref_path).stem.replace("_CHAR_REFERENCE", "")
            sim = self.face_similarity(frame_path, ref_path)
            sim["character"] = ref_name
            result["identity_scores"].append(sim)
            if sim["similarity"] < 0.5:
                result["issues"].append(f"identity_low_{ref_name}")
                result["overall_pass"] = False

        # Location
        if location_master_path and Path(location_master_path).exists():
            loc_sim = self.image_similarity(frame_path, location_master_path)
            result["location_score"] = loc_sim
            if loc_sim < 0.5:
                result["issues"].append("location_mismatch")

        return result


def get_vision_models() -> VisionModels:
    """Get singleton VisionModels instance."""
    global _instance
    if _instance is None:
        _instance = VisionModels()
    return _instance
