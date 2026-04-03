#!/usr/bin/env python3
"""
ATLAS V18 — Master Shot Chain Agent
====================================

Implements the "Master Shot → Angle Chain" pipeline for visually consistent
AI filmmaking. Instead of generating each shot independently (causing drift),
this system:

1. Generates ONE master wide shot per scene (the visual anchor)
2. Reframes that master into different camera angles (CU, MCU, OTS, etc.)
3. Chains shots by using the LAST FRAME of one video as the FIRST FRAME
   of the next shot
4. Detects breaks (scene changes, intercutting, location changes) and
   restarts the chain

Benefits:
- Background/lighting/color grade locked to master frame
- Character posture continuity within scenes
- Prop/wardrobe consistency guaranteed
- Reduces regeneration cost (1 master + N reframes < N independent gens)
- Eliminates "jump cut" artifacts between adjacent shots

Files managed:
  pipeline_outputs/{project}/master_shots/      — Master frames per scene
  pipeline_outputs/{project}/frame_chains/      — Extracted frame chains
  pipeline_outputs/{project}/chain_report.json  — Pipeline report + timings

Integration points:
  - Called from orchestrator_server.py after fix-v16
  - Triggered before generate-first-frames
  - Coordinates with wardrobe/extras agent for prompt injection
  - Reports chaining breaks to LOA for override checking
"""

import json
import logging
import subprocess
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import shutil

try:
    from PIL import Image
except ImportError:
    Image = None

try:
    import fal_client
except ImportError:
    fal_client = None

logger = logging.getLogger("atlas.master_shot_chain")

# ============================================================================
# V24.2: R2 PERMANENT URL UPLOAD — replaces fal_client.upload() temp URLs
# ============================================================================
# fal_client.upload() returns temp URLs (v3b.fal.media) that expire in ~1hr.
# Master chain pipeline runs 10+ minutes → all reframe calls hit dead URLs.
# R2 gives permanent public URLs that never expire.
# Falls back to base64 data URI if R2 not configured.

_r2_client_cache = None
_r2_init_attempted = False

def _get_r2_client():
    """Lazy-init R2 boto3 client from env vars. Cached after first call."""
    global _r2_client_cache, _r2_init_attempted
    if _r2_init_attempted:
        return _r2_client_cache
    _r2_init_attempted = True
    try:
        import os
        acct = os.environ.get("ATLAS_R2_ACCOUNT_ID", "")
        key_id = os.environ.get("ATLAS_R2_ACCESS_KEY_ID", "")
        secret = os.environ.get("ATLAS_R2_SECRET_KEY", "")
        if not (acct and key_id and secret):
            logger.info("[R2-AGENT] R2 env vars not set — will use base64 fallback")
            return None
        import boto3
        from botocore.config import Config as BotoConfig
        cfg = BotoConfig(
            retries={"max_attempts": 3, "mode": "adaptive"},
            connect_timeout=10, read_timeout=60,
            proxies={},  # Bypass sandbox proxy
        )
        _r2_client_cache = boto3.client(
            "s3",
            endpoint_url=f"https://{acct}.r2.cloudflarestorage.com",
            aws_access_key_id=key_id,
            aws_secret_access_key=secret,
            config=cfg,
            region_name="auto",
        )
        logger.info("[R2-AGENT] boto3 R2 client initialized")
        return _r2_client_cache
    except Exception as e:
        logger.warning(f"[R2-AGENT] R2 init failed: {e} — will use base64 fallback")
        return None


def _r2_upload_for_fal(local_path: str, project: str, label: str = "master") -> Optional[str]:
    """
    Upload a local image to R2 and return permanent public URL for FAL API.
    Returns None if R2 not available (caller should fall back to base64).

    URL format: {R2_PUBLIC_URL}/atlas-frames/{project}/chain/{label}_{timestamp}.jpg
    """
    import os
    client = _get_r2_client()
    if not client:
        return None

    bucket = os.environ.get("ATLAS_R2_BUCKET", "rumble-fanz")
    public_url = os.environ.get("ATLAS_R2_PUBLIC_URL", "")
    if not public_url:
        logger.warning("[R2-AGENT] ATLAS_R2_PUBLIC_URL not set — cannot build public URL")
        return None

    local_path = Path(local_path)
    if not local_path.exists():
        return None

    ext = local_path.suffix.lower()
    content_type = "image/png" if ext == ".png" else "image/jpeg"
    ts = int(time.time())
    r2_key = f"atlas-frames/{project}/chain/{label}_{ts}{ext}"

    try:
        client.upload_file(
            str(local_path),
            bucket,
            r2_key,
            ExtraArgs={"ContentType": content_type},
        )
        url = f"{public_url.rstrip('/')}/{r2_key}"
        size_kb = local_path.stat().st_size // 1024
        # V26.1: Verify URL is actually accessible before returning
        # R2 bucket may have public access disabled → 401 errors from FAL
        try:
            import urllib.request as _urllib_req
            _head_req = _urllib_req.Request(url, method="HEAD")
            _head_resp = _urllib_req.urlopen(_head_req, timeout=5)
            if _head_resp.status == 200:
                logger.info(f"[R2-AGENT] ✅ Uploaded + verified {local_path.name} ({size_kb}KB) → {url}")
                return url
            else:
                logger.warning(f"[R2-AGENT] Uploaded but URL returned {_head_resp.status} — falling back to base64")
                return None
        except Exception as _verify_err:
            logger.warning(f"[R2-AGENT] Uploaded but URL not accessible ({_verify_err}) — falling back to base64")
            return None
    except Exception as e:
        logger.error(f"[R2-AGENT] Upload failed: {e}")
        return None


# ============================================================================
# V25.4: DOCTRINE LEDGER — infrastructure events written to JSONL
# ============================================================================
# BUG 03 fix: R2 failures, FAL errors, DINO score misses must all write
# a ledger event so doctrine phases can audit infrastructure health.
# Pattern follows log_mutation() from tools/movie_lock_mode.py.

def _doctrine_ledger_event(
    project_path: Path,
    event_type: str,
    severity: str,
    detail: str,
    shot_id: str = "",
    fallback_taken: str = "",
    source: str = "master_shot_chain_agent"
) -> None:
    """
    Write an infrastructure event to the doctrine ledger (append-only JSONL).

    Events: r2_failure, fal_error, dino_score_missing, base64_fallback,
            identity_pack_missing, reframe_crash, chain_break, etc.
    Severity: INFO, WARNING, CRITICAL
    """
    ledger_path = project_path / "reports" / "doctrine_ledger.jsonl"
    ledger_path.parent.mkdir(exist_ok=True, parents=True)

    entry = {
        "timestamp": datetime.now().isoformat(),
        "event_type": event_type,
        "severity": severity,
        "shot_id": shot_id,
        "detail": detail[:500],  # Cap length to prevent log bloat
        "fallback_taken": fallback_taken,
        "source": source,
        "pipeline_stage": "master_chain"
    }

    try:
        with open(ledger_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        logger.warning(f"[DOCTRINE-LEDGER] Failed to write event: {e}")


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class FrameChainLink:
    """Single link in a shot chain."""
    shot_id: str
    frame_path: str  # Input frame for this shot
    source: str      # "master", "extracted", "manual"
    timestamp: float
    notes: str = ""


@dataclass
class ShotChainReport:
    """Complete report for a scene chain run."""
    project: str
    scene_id: str
    status: str  # "success", "partial", "failed"
    total_shots: int
    chained_shots: int
    chain_breaks: int
    master_frame_path: Optional[str]
    master_generation_cost: float
    reframe_cost: float
    video_cost: float
    total_cost: float
    duration_secs: float
    timestamp: str
    details: Dict[str, Any]


# ============================================================================
# CONTINUITY LOCKS
# ============================================================================

SCENE_CONTINUITY_LOCKS = {
    "location": {
        "description": "Background/set must match master shot",
        "enforcement": "negative prompt: NO background change, NO set change",
        "detection": "DINOv2 embedding similarity > 0.70"
    },
    "posture": {
        "description": "Character posture consistency within action beats",
        "enforcement": "carry posture description from previous shot",
        "detection": "pose estimation comparison"
    },
    "characters": {
        "description": "Same characters visible, same positions",
        "enforcement": "character list + blocking from master",
        "detection": "face detection count match"
    },
    "props": {
        "description": "Props/set dressing unchanged",
        "enforcement": "prop list from master shot description",
        "detection": "object detection comparison"
    },
    "lighting": {
        "description": "Lighting direction and color grade locked",
        "enforcement": "color grade anchor from scene_anchor_system",
        "detection": "histogram comparison"
    },
    "wardrobe": {
        "description": "Clothing unchanged within scene",
        "enforcement": "wardrobe_tag from wardrobe.json",
        "detection": "CLIP clothing similarity"
    }
}

ANGLE_REFRAME_SPEC = {
    "establishing": {
        "crop_region": (0, 0, 1.0, 1.0),  # Full frame
        "description": "Master establishing shot, full scene visible"
    },
    "wide": {
        "crop_region": (0, 0, 1.0, 1.0),  # Full frame
        "description": "Wide angle, entire scene"
    },
    "medium_wide": {
        "crop_region": (0.1, 0.05, 0.9, 0.95),
        "description": "Medium-wide, adjusted framing"
    },
    "medium": {
        "crop_region": (0.2, 0.15, 0.8, 0.85),  # Center 60%
        "description": "Medium shot, center crop"
    },
    "medium_close": {
        "crop_region": (0.25, 0.2, 0.75, 0.8),  # Center 50%
        "description": "Medium-close, tighter framing"
    },
    "close": {
        "crop_region": (0.35, 0.25, 0.65, 0.75),  # Center 30%
        "description": "Close-up, face region"
    },
    "extreme_close": {
        "crop_region": (0.4, 0.3, 0.6, 0.7),  # Center tight 20%
        "description": "Extreme close-up, tight face"
    },
    "detail": {
        "crop_region": (0.3, 0.25, 0.7, 0.75),
        "description": "Detail shot with context"
    },
    "ots": {
        "crop_region": (0.4, 0.15, 0.95, 0.85),  # Right side
        "description": "Over-the-shoulder, subject on right"
    },
    "two_shot": {
        "crop_region": (0.1, 0.1, 0.9, 0.9),
        "description": "Two-shot composition"
    },
    "action": {
        "crop_region": (0, 0, 1.0, 1.0),
        "description": "Action shot, dynamic framing"
    },
    "insert": {
        "crop_region": (0.25, 0.2, 0.75, 0.8),
        "description": "Insert shot, object focus"
    },
}


# ============================================================================
# MASTER SHOT GENERATION
# ============================================================================

def find_or_create_master_shot(
    project: str,
    scene_id: str,
    shot_plan: List[Dict],
    project_path: Path
) -> Tuple[Optional[str], Dict[str, Any]]:
    """
    Find the widest (establishing) shot in the scene to use as master.
    If none exists, create one by auto-generating a wide shot.

    Returns:
        (master_frame_path, metadata_dict)
    """
    metadata = {
        "found_existing": False,
        "created_new": False,
        "master_shot_id": None,
        "master_frame_path": None,
        "cost": 0.0,
        "timing": 0.0,
        "notes": []
    }

    scene_shots = [s for s in shot_plan if s.get("scene_id") == scene_id or
                   s.get("shot_id", "").startswith(f"{scene_id}_")]
    if not scene_shots:
        metadata["notes"].append(f"No shots found for scene {scene_id}")
        return None, metadata

    # Find widest shot — this is the BLOCKING BLUEPRINT for the whole scene
    # Priority: 1) shot_type=establishing, 2) lowest focal length, 3) first shot
    establishing = [s for s in scene_shots
                    if (s.get("shot_type") or s.get("type") or "").lower() in ("establishing", "master", "wide")]
    if establishing:
        widest_shot = establishing[0]
    else:
        widest_shot = min(
            scene_shots,
            key=lambda s: int(s.get("lens_specs", "50").split("mm")[0])
            if s.get("lens_specs") else 50
        )

    master_shot_id = widest_shot.get("shot_id")
    metadata["master_shot_id"] = master_shot_id

    # Check if first frame already exists (nano-banana generates these)
    # The master frame IS the first_frame of the widest shot
    first_frames_dir = project_path / "first_frames"
    if not first_frames_dir.exists():
        # Try nested path structure
        first_frames_dir = project_path / "pipeline_outputs" / project / "first_frames"

    for ext in [".jpg", ".png", ".jpeg"]:
        frame_path = first_frames_dir / f"{master_shot_id}{ext}"
        if frame_path.exists():
            metadata["found_existing"] = True
            metadata["master_frame_path"] = str(frame_path)
            metadata["notes"].append(
                f"Master frame from nano-banana: {frame_path.name} — "
                f"this sets the tone: character positions, background, props, lighting"
            )
            # Save copy to master_shots dir for reference
            master_dir = project_path / "master_shots"
            master_dir.mkdir(exist_ok=True)
            master_copy = master_dir / f"scene_{scene_id}_master.jpg"
            if not master_copy.exists():
                shutil.copy2(str(frame_path), str(master_copy))
            return str(frame_path), metadata

    # Master frame not generated yet — need nano-banana to create it first
    metadata["notes"].append(
        f"Master frame for {master_shot_id} not found in first_frames/. "
        "Run generate-first-frames for this shot first. "
        "Nano-banana sets the tone — blocking, character positions, background."
    )
    return None, metadata


def get_master_shot_prompt(shot: Dict) -> str:
    """Extract/enhance the nano_prompt for master shot generation."""
    nano = shot.get("nano_prompt", "")

    # Inject master shot directives
    master_directives = (
        "MASTER SHOT FOR CHAIN: This is the visual anchor frame for the scene. "
        "All other angles will be reframed from this master. "
        "Ensure complete scene visibility, consistent lighting, "
        "locked color grade (reference scene_anchor_system), "
        "all characters in positions per blocking, all props visible."
    )

    return f"{nano}\n\n{master_directives}"


# ============================================================================
# REFRAMING ENGINE
# ============================================================================

def reframe_to_angles(
    master_frame_path: str,
    scene_shots: List[Dict],
    project: str,
    project_path: Path,
    options: Dict[str, Any] = None,
    cast_map: Dict[str, Any] = None,
) -> Tuple[Dict[str, str], Dict[str, Any]]:
    """
    V25.6: Takes the master frame and reframes it into the SINGLE correct camera
    angle for each shot, DICTATED by coverage_role.

    coverage_role → angle mapping:
        A_GEOGRAPHY → 24mm wide (environment + blocking)
        B_ACTION    → 50mm medium (physical action + interaction)
        C_EMOTION   → 100mm close (face + emotion)

    ONE frame per shot. No variants. The coverage plan IS the shot list.
    If the director wants a different angle, they change coverage_role BEFORE
    generation, not by picking from 3 options after.

    Intercut shots (_intercut=True) are SKIPPED — they need independent generation.
    Falls back to CPU PIL crop if API is unavailable.

    Returns:
        ({shot_id: reframed_frame_path}, metadata_dict)
    """
    if options is None:
        options = {}
    if cast_map is None:
        cast_map = {}

    reframed_frames = {}
    metadata = {
        "total_reframes": 0,
        "cpu_crops": 0,
        "gpu_reframes": 0,
        "failed_reframes": [],
        "cost": 0.0,
        "timing": 0.0,
        "shots": {}
    }

    if not Path(master_frame_path).exists():
        logger.error(f"Master frame not found: {master_frame_path}")
        return {}, metadata

    # Load master image for CPU fallback
    try:
        master_image = Image.open(master_frame_path) if Image else None
    except Exception as e:
        logger.error(f"Failed to load master image: {e}")
        master_image = None

    reframe_dir = project_path / "pipeline_outputs" / project / "first_frame_variants"
    reframe_dir.mkdir(parents=True, exist_ok=True)

    # V24.2: Upload master frame for FAL API — R2 permanent URL preferred, base64 fallback
    # NEVER use fal_client.upload() — it returns temp URLs that expire mid-pipeline.
    # Priority: 1) R2 permanent URL  2) base64 data URI  3) CPU crop fallback
    master_fal_url = None

    # Try R2 first — permanent URL, never expires, works across all pipeline stages
    try:
        _scene_id_for_r2 = scene_shots[0].get("scene_id", "000") if scene_shots else "000"
        master_fal_url = _r2_upload_for_fal(master_frame_path, project, label=f"master_{_scene_id_for_r2}")
        if master_fal_url:
            logger.info(f"[REFRAME] Master frame → R2 permanent URL: {master_fal_url}")
    except Exception as r2_err:
        logger.warning(f"[REFRAME] R2 upload attempt failed: {r2_err}")
        # V25.4 BUG 03: Write doctrine ledger event for R2 failure
        _doctrine_ledger_event(
            project_path, event_type="r2_failure", severity="WARNING",
            detail=f"R2 upload failed for master frame: {r2_err}",
            shot_id=_scene_id_for_r2 if '_scene_id_for_r2' in dir() else "",
            fallback_taken="base64_data_uri",
            source="reframe_to_angles"
        )

    # Base64 fallback if R2 not available
    if not master_fal_url:
        try:
            import base64 as _b64_mod
            with open(master_frame_path, "rb") as _mf:
                _mf_data = _mf.read()
                _mf_ext = Path(master_frame_path).suffix.lower()
                _mf_mime = "image/png" if _mf_ext == ".png" else "image/jpeg"
                master_fal_url = f"data:{_mf_mime};base64,{_b64_mod.b64encode(_mf_data).decode('utf-8')}"
                logger.info(f"[REFRAME] Master frame → base64 fallback: {Path(master_frame_path).name} ({len(_mf_data):,} bytes)")
                # V25.4 BUG 03: Log fallback event
                _doctrine_ledger_event(
                    project_path, event_type="base64_fallback", severity="INFO",
                    detail=f"Using base64 data URI for master frame ({len(_mf_data):,} bytes). R2 unavailable.",
                    shot_id=_scene_id_for_r2 if '_scene_id_for_r2' in dir() else "",
                    fallback_taken="base64_data_uri",
                    source="reframe_to_angles"
                )
        except Exception as upload_err:
            logger.warning(f"[REFRAME] Base64 conversion also failed, will use CPU crop fallback: {upload_err}")
            # V25.4 BUG 03: Log total failure event
            _doctrine_ledger_event(
                project_path, event_type="image_upload_total_failure", severity="CRITICAL",
                detail=f"Both R2 and base64 failed for master frame: {upload_err}",
                shot_id=_scene_id_for_r2 if '_scene_id_for_r2' in dir() else "",
                fallback_taken="cpu_crop",
                source="reframe_to_angles"
            )

    # V21: Load canonical character descriptions (NOT AI actor descriptions)
    canonical_chars = {}
    try:
        from tools.prompt_authority_gate import CANONICAL_CHARACTERS
        canonical_chars = CANONICAL_CHARACTERS
    except ImportError:
        pass

    # V25.6: COVERAGE ROLE DICTATES ANGLE — ONE frame per shot, not 3
    # The coverage_role (A_GEOGRAPHY, B_ACTION, C_EMOTION) already tells us
    # what angle each shot should be. Generating 3 variants per shot was
    # V18 legacy when coverage roles weren't reliable. Now CPC + coverage solver
    # assign roles properly — the system DICTATES, not second-guesses.
    #
    # Mapping: coverage_role → single reframe instruction
    COVERAGE_TO_ANGLE = {
        "A_GEOGRAPHY": {
            "name": "wide_geography",
            "prefix": "CHANGE LENS TO 24mm ultra-wide. PULL BACK camera to show full room. Characters should be small in frame. Show maximum environment. Wide establishing composition."
        },
        "B_ACTION": {
            "name": "medium_action",
            "prefix": "CHANGE LENS TO 50mm standard. Frame waist-up on main character. Show physical action and interaction clearly. Medium shot composition with balanced environment and character."
        },
        "C_EMOTION": {
            "name": "close_emotion",
            "prefix": "CHANGE LENS TO 100mm telephoto. PUSH IN to head-and-shoulders framing on main character. Shallow depth of field. Emotional detail — capture face and expression."
        },
    }
    # Fallback for shots without coverage_role
    DEFAULT_ANGLE = COVERAGE_TO_ANGLE["B_ACTION"]

    for shot in scene_shots:
        shot_id = shot.get("shot_id")
        shot_type = shot.get("shot_type") or shot.get("type") or "medium"

        start_time = time.time()

        # V21: Skip intercut shots — they need independent frames from different locations
        if shot.get("_intercut"):
            logger.info(f"[REFRAME] {shot_id}: SKIPPED (intercut — different location)")
            metadata["shots"][shot_id] = {
                "shot_type": shot_type,
                "reframed": False,
                "skipped": "intercut",
                "timing": 0.0,
            }
            continue

        # V25.6: Pick ONE angle from coverage_role — no variants
        coverage_role = shot.get("coverage_role", "")
        angle = COVERAGE_TO_ANGLE.get(coverage_role, DEFAULT_ANGLE)
        logger.info(f"[REFRAME] {shot_id}: coverage_role={coverage_role} → {angle['name']}")

        # V21: Build character face text from CANONICAL descriptions
        characters = shot.get("characters", [])
        if isinstance(characters, str):
            characters = [c.strip() for c in characters.split(",") if c.strip()]

        _face_text = ""
        for char_name in characters:
            canon = canonical_chars.get(char_name.upper().strip())
            if canon:
                _face_text += f" {char_name}: {canon['appearance']}."
            else:
                _face_text += f" Keep {char_name} in frame."

        # V21: Resolve character reference image URLs for identity preservation
        char_ref_paths = []
        for char_name in characters:
            for cname, cdata in cast_map.items():
                if char_name.upper() in cname.upper() or cname.upper() in char_name.upper():
                    hr = cdata.get("headshot_url") or cdata.get("character_reference_url", "")
                    if hr:
                        if hr.startswith("/api/media?path="):
                            hr = hr.split("path=", 1)[1]
                        if Path(hr).exists():
                            char_ref_paths.append(hr)
                    break

        # ═══ V26.2: DOCTRINE PRE-GENERATION — Before reframe FAL call ═══
        _doctrine_runner = options.get("_doctrine_runner")
        _cast_map_for_doctrine = options.get("_cast_map", cast_map)
        if _doctrine_runner:
            try:
                _doc_pre_ctx = {
                    "cast_map": _cast_map_for_doctrine,
                    "scene_manifest": {},  # Scene manifest not available in chain pipeline
                }
                _doc_pre = _doctrine_runner.pre_generation(shot, _doc_pre_ctx)
                _is_hard_reject = not _doc_pre.get("can_proceed", True) and not _doc_pre.get("phase_exception", False)
                if _is_hard_reject:
                    logger.warning(f"[DOCTRINE-CHAIN] REJECTED {shot_id}: {_doc_pre.get('reject_gate', 'unknown')}")
                    metadata["shots"][shot_id] = {
                        "shot_type": shot_type,
                        "coverage_role": coverage_role,
                        "reframed": False,
                        "rejected": "doctrine_gate",
                        "timing": 0.0,
                    }
                    continue
                elif _doc_pre.get("phase_exception"):
                    logger.warning(f"[DOCTRINE-CHAIN] Phase exception for {shot_id} (non-blocking)")
                else:
                    logger.info(f"[DOCTRINE-CHAIN] PRE-GEN PASSED {shot_id}")
            except Exception as _doc_pre_err:
                logger.warning(f"[DOCTRINE-CHAIN] Pre-gen non-blocking: {_doc_pre_err}")
        # ═══════════════════════════════════════════════════════════════

        # V25.6: Generate ONE frame per shot — coverage_role dictates angle
        if master_fal_url:
            variant_path = reframe_dir / f"{shot_id}_{angle['name']}.jpg"
            try:
                # Build reframe prompt with canonical character descriptions
                reframe_prompt = (
                    "REFRAME ONLY. Use the provided image as the single source of truth. "
                    "Do NOT change environment, room, props, objects, lighting, shadows, or color grade. "
                    "Do NOT add or remove anything. Do NOT relocate characters. "
                    f"Preserve exact face identity, hairstyle, wardrobe, skin tone.{_face_text} "
                    "NO morphing faces, NO grid, NO collage, face stable, identity locked. "
                    f"{angle['prefix']} "
                    "Maintain identical scene composition except camera distance and framing."
                )
                if len(reframe_prompt) > 900:
                    reframe_prompt = reframe_prompt[:897] + "..."

                # V21 FIX: REFRAME uses ONLY the source frame.
                # DO NOT add character reference headshots — they bleed into output
                image_urls = [master_fal_url]

                result = fal_client.run(
                    "fal-ai/nano-banana-pro/edit",
                    arguments={
                        "image_urls": image_urls,
                        "prompt": reframe_prompt,
                        "aspect_ratio": "16:9",
                        "output_format": "jpeg",
                        "num_outputs": 1,
                    }
                )

                img_url = None
                images = result.get("images", [])
                if images:
                    img_url = images[0] if isinstance(images[0], str) else images[0].get("url", "")

                if img_url:
                    import urllib.request
                    urllib.request.urlretrieve(img_url, str(variant_path))
                    reframed_frames[shot_id] = str(variant_path)
                    metadata["gpu_reframes"] += 1
                    metadata["cost"] += 0.15  # ONE reframe, not 3
                    shot["_reframe_method"] = "nano-pro-edit"
                    shot["_reframe_angle"] = angle["name"]
                    shot["_coverage_dictated"] = True
                    logger.info(f"[REFRAME] {shot_id}: ✅ {angle['name']} (coverage-dictated, nano-pro-edit)")

                    # ═══ V26.2: DOCTRINE POST-GENERATION — After successful reframe ═══
                    if _doctrine_runner:
                        try:
                            _doc_post_ctx = {
                                "output_path": str(variant_path),
                                "fal_result": result,
                            }
                            _doc_post = _doctrine_runner.post_generation(shot, _doc_post_ctx)
                            if _doc_post.get("reject_gate"):
                                logger.warning(f"[DOCTRINE-CHAIN] Post-gen rejection for {shot_id}: {_doc_post.get('reject_gate')}")
                            else:
                                logger.info(f"[DOCTRINE-CHAIN] POST-GEN PASSED {shot_id}: {_doc_post.get('status', 'unknown')}")
                        except Exception as _doc_post_err:
                            logger.warning(f"[DOCTRINE-CHAIN] Post-gen non-blocking: {_doc_post_err}")
                    # ═══════════════════════════════════════════════════════════════
                else:
                    logger.warning(f"[REFRAME] {shot_id}: {angle['name']} — no image returned")

            except Exception as angle_err:
                logger.warning(f"[REFRAME] {shot_id}: {angle['name']} failed: {angle_err}")

        # CPU crop fallback if API failed
        if shot_id not in reframed_frames and master_image and Image:
            try:
                spec = ANGLE_REFRAME_SPEC.get(shot_type, ANGLE_REFRAME_SPEC["medium"])
                reframed = _crop_image_to_angle(
                    master_image,
                    spec["crop_region"],
                    shot_type
                )
                output_path = reframe_dir / f"{shot_id}_master_reframe.jpg"
                reframed.save(str(output_path), quality=92)
                reframed_frames[shot_id] = str(output_path)
                metadata["cpu_crops"] += 1
                shot["_reframe_method"] = "cpu_crop_fallback"
                logger.info(f"[REFRAME] {shot_id}: CPU crop fallback ({shot_type})")
            except Exception as e:
                logger.error(f"[REFRAME] {shot_id}: CPU crop also failed: {e}")
                metadata["failed_reframes"].append((shot_id, str(e)))

        elapsed = time.time() - start_time
        metadata["shots"][shot_id] = {
            "shot_type": shot_type,
            "coverage_role": coverage_role,
            "angle_dictated": angle["name"],
            "reframed": shot_id in reframed_frames,
            "method": shot.get("_reframe_method", "none"),
            "timing": elapsed,
        }

    metadata["total_reframes"] = len(reframed_frames)
    metadata["timing"] = time.time()

    return reframed_frames, metadata


def _crop_image_to_angle(
    image: "Image.Image",
    crop_region: Tuple[float, float, float, float],
    shot_type: str
) -> "Image.Image":
    """
    Crop master image to angle-specific region.
    crop_region = (left%, top%, right%, bottom%)
    """
    if not Image:
        return image

    w, h = image.size
    left = int(crop_region[0] * w)
    top = int(crop_region[1] * h)
    right = int(crop_region[2] * w)
    bottom = int(crop_region[3] * h)

    cropped = image.crop((left, top, right, bottom))

    # Resize back to master dimensions (maintain aspect)
    target_width = 1024  # LTX standard
    aspect = cropped.height / cropped.width
    target_height = int(1024 * aspect)

    resized = cropped.resize(
        (target_width, target_height),
        Image.Resampling.LANCZOS
    )

    return resized


# ============================================================================
# FRAME CHAINING
# ============================================================================

def should_chain(shot_a: Dict, shot_b: Dict) -> bool:
    """
    Determine if shot_b should be chained to shot_a's last frame.

    CHAIN = shot has real character blocking/movement that needs continuity.
    NO CHAIN = B-roll, inserts, cutaways, establishing, location change,
               V.O., intercut — these are independent visual contexts.

    The purpose: if Margaret's hands moved during shot_a's video,
    shot_b starts with hands in THAT position. Only matters for
    shots dictating real movement or blocking.

    Returns False if:
    - shot_b is B-roll, insert, or cutaway (no character blocking)
    - Different locations (scene change)
    - V.O./phone/intercut keywords
    - shot_b is establishing (new visual context)
    - Transition keywords present
    - shot_b has no characters (atmospheric/detail shot)
    """
    # V21: INTERCUT DETECTION — shots marked as intercut NEVER chain
    # Scene 002 alternates apartment ↔ law office — chaining across those
    # would merge two different locations into one visual stream
    if shot_b.get("_intercut"):
        return False

    # B-roll, inserts, cutaways DON'T chain — they're independent
    shot_type_b = (shot_b.get("shot_type") or shot_b.get("type") or "").lower()
    shot_id_b = shot_b.get("shot_id", "")

    # V26 DOCTRINE: Coverage suffixes (A/B/C) are editorial labels, NOT runtime behavior
    # Use explicit is_broll/_broll flags instead of shot_id suffix
    if shot_b.get("is_broll", False) or shot_b.get("_broll", False):
        return False

    # Insert/detail/cutaway shot types don't chain
    NO_CHAIN_TYPES = ["insert", "b-roll", "b_roll", "broll", "cutaway",
                      "detail", "atmosphere",
                      "montage", "title", "transition"]
    if any(t in shot_type_b for t in NO_CHAIN_TYPES):
        return False

    # V18.2: Establishing/master shots — SMART chain logic
    # Pure location-setters (no characters, no dialogue) = DON'T chain
    # Interior establishing WITH characters + dialogue = DO chain (real blocking)
    if "establishing" in shot_type_b or "master" in shot_type_b:
        chars_b_check = shot_b.get("characters", [])
        dialogue_b = (shot_b.get("dialogue_text") or shot_b.get("dialogue") or "").strip()
        has_characters = bool(chars_b_check) and len(chars_b_check) > 0
        has_dialogue = len(dialogue_b) > 10
        loc_b = (shot_b.get("location") or "").upper()
        is_exterior = loc_b.startswith("EXT.")
        # Exterior establishing = location-setter, don't chain
        if is_exterior:
            return False
        # Interior with characters + dialogue = real scene, chain it
        if has_characters and has_dialogue:
            pass  # Allow chain — fall through to remaining checks
        else:
            return False  # Pure establishing without blocking — don't chain

    # No characters = no blocking to chain
    chars_b = shot_b.get("characters", [])
    if not chars_b or len(chars_b) == 0:
        return False

    # Location change = break
    # Normalize: strip INT./EXT., dashes (en/em/hyphen), trailing time-of-day, whitespace
    import re
    def _norm_loc(loc):
        loc = (loc or "").lower().strip()
        loc = re.sub(r'^(int\.|ext\.|int/ext\.)\s*', '', loc)
        loc = loc.replace('–', '-').replace('—', '-')  # en/em dash → hyphen
        loc = re.sub(r'\s*-\s*(night|day|dawn|dusk|evening|morning|continuous)\s*$', '', loc)
        loc = re.sub(r'\s+', ' ', loc).strip()
        return loc

    loc_a = _norm_loc(shot_a.get("location"))
    loc_b = _norm_loc(shot_b.get("location"))
    if loc_a != loc_b and loc_a and loc_b:
        # Fuzzy: if one contains the other, treat as same location
        if loc_a not in loc_b and loc_b not in loc_a:
            return False

    # Special transitions
    transition = (shot_b.get("transition") or "").lower()
    if any(x in transition for x in ["cut to", "smash cut", "fade", "dissolve"]):
        return False

    # V.O./intercut keywords
    dialogue = (shot_b.get("dialogue") or shot_b.get("dialogue_text") or "").lower()
    notes = (shot_b.get("notes") or shot_b.get("beat_text") or "").lower()
    for keyword in ["v.o.", "vo", "voice over", "phone", "intercut", "cross-cutting"]:
        if keyword in dialogue or keyword in notes:
            return False

    # Establishing shot = restart from master
    if "establishing" in shot_type_b or "master" in shot_type_b:
        return False

    return True


def extract_last_frame(
    video_path: str,
    output_path: str,
    project_path: Path
) -> Tuple[bool, str]:
    """
    Extract the last frame from a rendered video using ffprobe + ffmpeg.

    Returns:
        (success: bool, frame_path: str)
    """
    try:
        # Get video duration
        probe_cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1:noprint_wrappers=1",
            video_path
        ]

        result = subprocess.run(
            probe_cmd,
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            logger.error(f"ffprobe failed: {result.stderr}")
            return False, ""

        duration = float(result.stdout.strip())

        # Extract last frame (0.1 seconds before end)
        seek_time = max(0, duration - 0.1)

        extract_cmd = [
            "ffmpeg",
            "-ss", str(seek_time),
            "-i", video_path,
            "-vf", "fps=1",
            "-frames:v", "1",
            "-q:v", "2",
            output_path
        ]

        result = subprocess.run(
            extract_cmd,
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode != 0:
            logger.error(f"ffmpeg frame extraction failed: {result.stderr}")
            return False, ""

        if not Path(output_path).exists():
            logger.error(f"Output frame not created: {output_path}")
            return False, ""

        return True, output_path

    except subprocess.TimeoutExpired:
        logger.error(f"Frame extraction timed out for {video_path}")
        return False, ""
    except Exception as e:
        logger.error(f"Error extracting frame: {e}")
        return False, ""


def chain_end_to_start(
    video_path: str,
    next_shot_id: str,
    project: str,
    project_path: Path
) -> Tuple[bool, str]:
    """
    Extract the last frame from video_path and save as first_frame for next_shot_id.

    Returns:
        (success: bool, frame_path: str)
    """
    frame_chain_dir = project_path / "pipeline_outputs" / project / "frame_chains"
    frame_chain_dir.mkdir(parents=True, exist_ok=True)

    output_frame = frame_chain_dir / f"{next_shot_id}_chain_start.jpg"

    success, frame_path = extract_last_frame(
        video_path,
        str(output_frame),
        project_path
    )

    if success:
        logger.info(
            f"Chained {Path(video_path).stem} → {next_shot_id}: "
            f"{output_frame.name}"
        )

    return success, frame_path


# ============================================================================
# MAIN PIPELINE
# ============================================================================

def run_master_chain_pipeline(
    project: str,
    scene_id: str,
    shot_plan: List[Dict],
    project_path: Path,
    options: Dict[str, Any] = None
) -> Tuple[bool, ShotChainReport]:
    """
    Main entry point for Master Shot Chain pipeline.

    Pipeline:
    1. Load scene shots from shot_plan
    2. Find or create master shot
    3. Reframe master to angles for all shots
    4. Inject reframed frames into shot_plan
    5. Store chain metadata for rendering phase

    Returns:
        (success: bool, report: ShotChainReport)
    """
    if options is None:
        options = {}

    start_time = time.time()

    # Filter to scene
    scene_shots = [s for s in shot_plan if s.get("scene_id") == scene_id or
                   s.get("shot_id", "").startswith(f"{scene_id}_")]
    if not scene_shots:
        return False, ShotChainReport(
            project=project,
            scene_id=scene_id,
            status="failed",
            total_shots=0,
            chained_shots=0,
            chain_breaks=0,
            master_frame_path=None,
            master_generation_cost=0.0,
            reframe_cost=0.0,
            video_cost=0.0,
            total_cost=0.0,
            duration_secs=0.0,
            timestamp=datetime.now().isoformat(),
            details={"error": "No shots found for scene"}
        )

    logger.info(
        f"[MASTER CHAIN] Scene {scene_id}: {len(scene_shots)} shots"
    )

    # Step 1: Find master shot
    master_frame_path, master_meta = find_or_create_master_shot(
        project, scene_id, scene_shots, project_path
    )

    if not master_frame_path:
        return False, ShotChainReport(
            project=project,
            scene_id=scene_id,
            status="failed",
            total_shots=len(scene_shots),
            chained_shots=0,
            chain_breaks=0,
            master_frame_path=None,
            master_generation_cost=master_meta.get("cost", 0.0),
            reframe_cost=0.0,
            video_cost=0.0,
            total_cost=master_meta.get("cost", 0.0),
            duration_secs=time.time() - start_time,
            timestamp=datetime.now().isoformat(),
            details={"error": "Master shot not available", "master_meta": master_meta}
        )

    logger.info(f"[MASTER CHAIN] Master shot: {Path(master_frame_path).name}")

    # Step 2: Reframe master to angles
    reframed_frames, reframe_meta = reframe_to_angles(
        master_frame_path, scene_shots, project, project_path, options
    )

    if not reframed_frames:
        logger.warning(f"[MASTER CHAIN] No reframes succeeded for scene {scene_id}")
    else:
        logger.info(
            f"[MASTER CHAIN] Reframed {len(reframed_frames)} shots "
            f"({reframe_meta['cpu_crops']} CPU crops)"
        )

    # Step 3: Inject reframed frames back into shot_plan
    # This is done upstream in orchestrator_server where shot_plan is mutable
    chain_metadata = {
        "master_frame_path": master_frame_path,
        "master_shot_id": master_meta.get("master_shot_id"),
        "reframed_frames": reframed_frames,
        "chain_links": []
    }

    # Step 4: Determine chain links
    for i, shot in enumerate(scene_shots):
        shot_id = shot.get("shot_id")

        if i == 0:
            # First shot uses master frame
            source = "master"
            frame_path = master_frame_path
        else:
            # Check if should chain to previous
            prev_shot = scene_shots[i - 1]
            if should_chain(prev_shot, shot):
                source = "extracted"
                # Would be filled after video generation
                frame_path = ""
            else:
                source = "reframed" if shot_id in reframed_frames else "master"
                frame_path = reframed_frames.get(shot_id, master_frame_path)

        chain_link = FrameChainLink(
            shot_id=shot_id,
            frame_path=frame_path,
            source=source,
            timestamp=time.time(),
            notes=f"Shot {i+1}/{len(scene_shots)}"
        )

        chain_metadata["chain_links"].append(asdict(chain_link))

    # Step 5: Persist chain metadata
    chain_report_path = (
        project_path / "pipeline_outputs" / project / "chain_metadata.json"
    )
    chain_report_path.parent.mkdir(parents=True, exist_ok=True)

    with open(chain_report_path, "w") as f:
        json.dump(chain_metadata, f, indent=2)

    elapsed = time.time() - start_time

    report = ShotChainReport(
        project=project,
        scene_id=scene_id,
        status="success",
        total_shots=len(scene_shots),
        chained_shots=sum(1 for m in chain_metadata["chain_links"] if m["source"] == "extracted"),
        chain_breaks=sum(1 for i in range(1, len(scene_shots)) if not should_chain(scene_shots[i-1], scene_shots[i])),
        master_frame_path=master_frame_path,
        master_generation_cost=master_meta.get("cost", 0.0),
        reframe_cost=reframe_meta.get("cost", 0.0),
        video_cost=0.0,  # Set after video generation
        total_cost=master_meta.get("cost", 0.0) + reframe_meta.get("cost", 0.0),
        duration_secs=elapsed,
        timestamp=datetime.now().isoformat(),
        details={
            "chain_metadata": chain_metadata,
            "master_meta": master_meta,
            "reframe_meta": reframe_meta
        }
    )

    logger.info(
        f"[MASTER CHAIN] Complete: {report.total_shots} shots, "
        f"{report.chained_shots} chained, {report.chain_breaks} breaks, "
        f"{elapsed:.1f}s"
    )

    return True, report


def run_parallel_scenes(
    project: str,
    scene_ids: List[str],
    shot_plan: List[Dict],
    project_path: Path,
    max_concurrent: int = 3,
    options: Dict[str, Any] = None
) -> Tuple[Dict[str, ShotChainReport], float]:
    """
    Run master-chain pipeline for multiple scenes sequentially
    (async support available for future GPU optimization).

    Returns:
        ({scene_id: report}, total_duration_secs)
    """
    if options is None:
        options = {}

    start_time = time.time()
    results = {}

    for scene_id in scene_ids:
        logger.info(f"[MASTER CHAIN] Starting scene {scene_id}")
        success, report = run_master_chain_pipeline(
            project, scene_id, shot_plan, project_path, options
        )
        results[scene_id] = report
        logger.info(f"[MASTER CHAIN] Completed scene {scene_id}: {report.status}")

    total_duration = time.time() - start_time

    return results, total_duration


# ============================================================================
# PERSISTENCE & REPORTING
# ============================================================================

def persist_chain_report(
    report: ShotChainReport,
    project_path: Path
) -> bool:
    """Save chain report to project directory."""
    try:
        report_dir = project_path / "pipeline_outputs" / report.project / "chain_reports"
        report_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = report_dir / f"scene_{report.scene_id}_{timestamp}.json"

        with open(report_path, "w") as f:
            json.dump(asdict(report), f, indent=2)

        logger.info(f"Chain report saved: {report_path}")
        return True

    except Exception as e:
        logger.error(f"Failed to persist chain report: {e}")
        return False
