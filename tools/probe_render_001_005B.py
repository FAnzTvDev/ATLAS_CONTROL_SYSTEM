#!/usr/bin/env python3
"""
ATLAS V27.1 — PROBE RENDER: 001_005B
=====================================
Full end-to-end probe: generate first frame → LTX video → Kling video → vision score all.
This is the REAL test — actual FAL calls with canonical ref packs.

Run:
    python3 tools/probe_render_001_005B.py
"""

import json
import os
import sys
import time
import logging
from pathlib import Path
from datetime import datetime

# Setup
os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/..")
sys.path.insert(0, "tools")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("PROBE")

# FAL key
if not os.environ.get("FAL_KEY"):
    os.environ["FAL_KEY"] = "6c394797-d2ed-4238-a303-7b1179a0aaf5:ccce2ccede50e31794c205aad4439ccc"

import fal_client

# Project paths
PROJ = "pipeline_outputs/victorian_shadows_ep1"
FRAMES_DIR = os.path.join(PROJ, "first_frames")
VIDEOS_DIR = os.path.join(PROJ, "videos")
REPORTS_DIR = os.path.join(PROJ, "reports")

# Model strings (from LOCKED_MODELS_CONFIG)
MODEL_NANO = "fal-ai/nano-banana-pro"
MODEL_LTX = "fal-ai/ltx-2.3/image-to-video/fast"
MODEL_KLING = "fal-ai/kling-video/v3/pro/image-to-video"


def upload_ref(local_path):
    """Upload a local file to FAL and return the hosted URL."""
    logger.info(f"  Uploading: {os.path.basename(local_path)}")
    url = fal_client.upload_file(str(local_path))
    logger.info(f"  → {url[:80]}...")
    return url


def generate_first_frame(shot, cast_map):
    """
    STAGE 1: Generate first frame via nano-banana-pro with canonical refs.
    """
    logger.info("=" * 60)
    logger.info("STAGE 1: FIRST FRAME GENERATION (nano-banana-pro)")
    logger.info("=" * 60)

    # Upload refs to FAL
    fal_urls = shot.get("_fal_image_urls_resolved", [])
    uploaded_urls = []
    for local_path in fal_urls:
        if Path(local_path).exists():
            uploaded_urls.append(upload_ref(local_path))
        else:
            logger.error(f"  REF MISSING: {local_path}")

    # Build prompt
    nano_prompt = shot.get("nano_prompt", "")
    logger.info(f"  Prompt ({len(nano_prompt)} chars): {nano_prompt[:120]}...")
    logger.info(f"  Refs: {len(uploaded_urls)} uploaded")

    # FAL call — nano-banana-pro
    # T2-SA-1: correct params: prompt, image_urls, resolution, aspect_ratio, output_format
    # T2-SA-2: OTS dialogue = hero shot → 2K resolution
    # T2-SA-4: dialogue boost → 2K minimum
    payload = {
        "prompt": nano_prompt,
        "image_urls": uploaded_urls,
        "resolution": "2K",  # MUST be uppercase per FAL API
        "aspect_ratio": "16:9",
        "output_format": "jpeg",
        "num_images": 3,  # Multi-candidate (T2-FE-11)
        "safety_tolerance": 6,
    }

    logger.info(f"  Calling FAL: {MODEL_NANO}")
    logger.info(f"  Resolution: 2K | Aspect: 16:9 | Candidates: 3")
    start = time.time()

    try:
        # Route through orchestrator's key rotation for production path test
        try:
            sys.path.insert(0, os.getcwd())
            from orchestrator_server import fal_run_with_key_rotation
            result = fal_run_with_key_rotation(MODEL_NANO, payload)
            logger.info("  (routed through orchestrator key rotation)")
        except ImportError:
            result = fal_client.run(MODEL_NANO, arguments=payload)
        elapsed = round(time.time() - start, 2)
        logger.info(f"  FAL returned in {elapsed}s")

        images = result.get("images", [])
        logger.info(f"  Got {len(images)} candidate frames")

        # Save all candidates
        saved_paths = []
        for i, img in enumerate(images):
            img_url = img.get("url", "")
            if img_url:
                # Download the image
                import urllib.request
                filename = f"001_005B_candidate_{i}.jpg"
                save_path = os.path.join(FRAMES_DIR, filename)
                urllib.request.urlretrieve(img_url, save_path)
                saved_paths.append(save_path)
                logger.info(f"  Saved: {filename} ({img.get('width', '?')}x{img.get('height', '?')})")

        # Pick best candidate (for now: first one, later: vision scoring picks best)
        best_path = saved_paths[0] if saved_paths else None
        if best_path:
            # Copy as the canonical frame
            import shutil
            canonical = os.path.join(FRAMES_DIR, "001_005B.jpg")
            shutil.copy2(best_path, canonical)
            logger.info(f"  Canonical frame: 001_005B.jpg")

        return {
            "status": "SUCCESS",
            "elapsed": elapsed,
            "candidates": len(images),
            "paths": saved_paths,
            "canonical": os.path.join(FRAMES_DIR, "001_005B.jpg"),
            "fal_result": {
                "images": [{"url": img.get("url", "")[:80], "width": img.get("width"), "height": img.get("height")} for img in images]
            },
        }
    except Exception as e:
        elapsed = round(time.time() - start, 2)
        logger.error(f"  FAL ERROR after {elapsed}s: {e}")
        return {"status": "FAIL", "error": str(e), "elapsed": elapsed}


def generate_ltx_video(frame_path):
    """
    STAGE 2A: Generate video via LTX-2.3 from the first frame.
    """
    logger.info("=" * 60)
    logger.info("STAGE 2A: LTX VIDEO GENERATION")
    logger.info("=" * 60)

    # Upload frame
    frame_url = upload_ref(frame_path)

    # Load shot for prompt
    sp = json.load(open(os.path.join(PROJ, "shot_plan.json")))
    shots = sp if isinstance(sp, list) else sp.get("shots", [])
    shot = next((s for s in shots if s.get("shot_id") == "001_005B"), None)
    ltx_prompt = shot.get("ltx_motion_prompt", "") if shot else ""

    # LTX payload — T2-SA-1 compliant
    # LTX API: image_url (singular), duration (int), prompt
    payload = {
        "image_url": frame_url,
        "prompt": ltx_prompt,
        "duration": 8,  # 10s shot, LTX max practical = 8-10
        "aspect_ratio": "16:9",
    }

    # Add negative prompt if available
    neg = shot.get("_negative_prompt", "worst quality, blurry, morphing, face distortion, deformed")
    if neg:
        payload["negative_prompt"] = neg

    logger.info(f"  Calling FAL: {MODEL_LTX}")
    logger.info(f"  Duration: {payload['duration']}s | Prompt: {ltx_prompt[:80]}...")
    start = time.time()

    try:
        result = fal_client.run(MODEL_LTX, arguments=payload)
        elapsed = round(time.time() - start, 2)
        logger.info(f"  FAL returned in {elapsed}s")

        video = result.get("video", {})
        video_url = video.get("url", "")
        if video_url:
            import urllib.request
            save_path = os.path.join(VIDEOS_DIR, "001_005B_ltx.mp4")
            urllib.request.urlretrieve(video_url, save_path)
            file_size = os.path.getsize(save_path)
            logger.info(f"  Saved: 001_005B_ltx.mp4 ({file_size // 1024}KB)")
            return {
                "status": "SUCCESS",
                "elapsed": elapsed,
                "path": save_path,
                "model": "LTX-2.3",
                "duration": payload["duration"],
                "size_kb": file_size // 1024,
            }
        else:
            return {"status": "FAIL", "error": "no video URL in response", "elapsed": elapsed}
    except Exception as e:
        elapsed = round(time.time() - start, 2)
        logger.error(f"  FAL ERROR after {elapsed}s: {e}")
        return {"status": "FAIL", "error": str(e), "elapsed": elapsed}


def generate_kling_video(frame_path):
    """
    STAGE 2B: Generate video via Kling 3.0 from the same first frame.
    """
    logger.info("=" * 60)
    logger.info("STAGE 2B: KLING 3.0 VIDEO GENERATION")
    logger.info("=" * 60)

    frame_url = upload_ref(frame_path)

    sp = json.load(open(os.path.join(PROJ, "shot_plan.json")))
    shots = sp if isinstance(sp, list) else sp.get("shots", [])
    shot = next((s for s in shots if s.get("shot_id") == "001_005B"), None)
    ltx_prompt = shot.get("ltx_motion_prompt", "") if shot else ""

    # Kling payload — T2-SA-1 compliant
    # Kling API: start_image_url, duration (STRING), prompt
    KLING_VALID = [3, 5, 8, 10, 12, 15]
    target_dur = min(KLING_VALID, key=lambda x: abs(x - 10))  # snap to nearest

    payload = {
        "start_image_url": frame_url,  # Kling uses start_image_url
        "prompt": ltx_prompt,
        "duration": str(target_dur),   # Kling takes string
        "aspect_ratio": "16:9",
    }

    neg = shot.get("_negative_prompt", "worst quality, blurry, morphing, face distortion")
    if neg:
        payload["negative_prompt"] = neg

    logger.info(f"  Calling FAL: {MODEL_KLING}")
    logger.info(f"  Duration: {target_dur}s | Prompt: {ltx_prompt[:80]}...")
    start = time.time()

    try:
        result = fal_client.run(MODEL_KLING, arguments=payload)
        elapsed = round(time.time() - start, 2)
        logger.info(f"  FAL returned in {elapsed}s")

        video = result.get("video", {})
        video_url = video.get("url", "")
        if video_url:
            import urllib.request
            save_path = os.path.join(VIDEOS_DIR, "001_005B_kling.mp4")
            urllib.request.urlretrieve(video_url, save_path)
            file_size = os.path.getsize(save_path)
            logger.info(f"  Saved: 001_005B_kling.mp4 ({file_size // 1024}KB)")
            return {
                "status": "SUCCESS",
                "elapsed": elapsed,
                "path": save_path,
                "model": "Kling-3.0",
                "duration": target_dur,
                "size_kb": file_size // 1024,
            }
        else:
            return {"status": "FAIL", "error": "no video URL in response", "elapsed": elapsed}
    except Exception as e:
        elapsed = round(time.time() - start, 2)
        logger.error(f"  FAL ERROR after {elapsed}s: {e}")
        return {"status": "FAIL", "error": str(e), "elapsed": elapsed}


def score_outputs(frame_path, video_paths):
    """
    STAGE 3: Vision scoring on all outputs.
    """
    logger.info("=" * 60)
    logger.info("STAGE 3: VISION SCORING")
    logger.info("=" * 60)

    from vision_service import get_vision_service
    from vision_models import get_vision_models

    vs = get_vision_service(provider="local")
    vm = get_vision_models()

    results = {}

    # Score first frame
    if frame_path and Path(frame_path).exists():
        logger.info(f"  Scoring frame: {os.path.basename(frame_path)}")

        # Fast QA
        qa = vs.fast_qa(frame_path)
        results["fast_qa"] = qa
        logger.info(f"  Fast QA: sharpness={qa.get('sharpness')}, exposure={qa.get('exposure')}, passed={qa.get('passed')}")

        # Identity: Thomas Blackwood
        thomas_ref = os.path.join(PROJ, "character_library_locked", "THOMAS_BLACKWOOD_CHAR_REFERENCE.jpg")
        if Path(thomas_ref).exists():
            thomas_id = vm.face_similarity(frame_path, thomas_ref)
            results["thomas_identity"] = thomas_id
            logger.info(f"  Thomas identity: {thomas_id.get('similarity')} (faces: {thomas_id.get('frame_face_count')})")

        # Identity: Eleanor Voss
        eleanor_ref = os.path.join(PROJ, "character_library_locked", "ELEANOR_VOSS_CHAR_REFERENCE.jpg")
        if Path(eleanor_ref).exists():
            eleanor_id = vm.face_similarity(frame_path, eleanor_ref)
            results["eleanor_identity"] = eleanor_id
            logger.info(f"  Eleanor identity: {eleanor_id.get('similarity')} (faces: {eleanor_id.get('frame_face_count')})")

        # Location
        loc_master = os.path.join(PROJ, "location_masters", "HARGROVE_ESTATE___GRAND_FOYER_reverse_angle.jpg")
        if Path(loc_master).exists():
            loc_sim = vm.image_similarity(frame_path, loc_master)
            results["location_similarity"] = loc_sim
            logger.info(f"  Location similarity: {loc_sim}")

    # Score candidate frames
    for i in range(3):
        cand = os.path.join(FRAMES_DIR, f"001_005B_candidate_{i}.jpg")
        if Path(cand).exists():
            qa = vs.fast_qa(cand)
            results[f"candidate_{i}_qa"] = qa

            # Thomas identity per candidate
            if Path(thomas_ref).exists():
                tid = vm.face_similarity(cand, thomas_ref)
                results[f"candidate_{i}_thomas"] = tid

    # Score video frames (extract frame 0 and middle frame)
    for vid_path in video_paths:
        if not Path(vid_path).exists():
            continue
        vid_name = Path(vid_path).stem
        logger.info(f"  Scoring video: {vid_name}")

        try:
            import subprocess
            # Extract frame 0
            frame0 = os.path.join(VIDEOS_DIR, f"{vid_name}_frame0.jpg")
            subprocess.run([
                "ffmpeg", "-y", "-i", vid_path,
                "-vf", "select=eq(n\\,0)", "-vframes", "1",
                frame0
            ], capture_output=True, timeout=30)

            # Extract middle frame
            frame_mid = os.path.join(VIDEOS_DIR, f"{vid_name}_frame_mid.jpg")
            subprocess.run([
                "ffmpeg", "-y", "-i", vid_path,
                "-vf", "select=eq(n\\,60)", "-vframes", "1",
                frame_mid
            ], capture_output=True, timeout=30)

            # Score first video frame
            if Path(frame0).exists():
                qa0 = vs.fast_qa(frame0)
                results[f"{vid_name}_frame0_qa"] = qa0
                logger.info(f"  {vid_name} frame0: sharpness={qa0.get('sharpness')}")

                if Path(thomas_ref).exists():
                    tid = vm.face_similarity(frame0, thomas_ref)
                    results[f"{vid_name}_frame0_thomas"] = tid
                    logger.info(f"  {vid_name} frame0 Thomas: {tid.get('similarity')}")

            # Score mid frame
            if Path(frame_mid).exists():
                qa_mid = vs.fast_qa(frame_mid)
                results[f"{vid_name}_mid_qa"] = qa_mid

                if Path(thomas_ref).exists():
                    tid = vm.face_similarity(frame_mid, thomas_ref)
                    results[f"{vid_name}_mid_thomas"] = tid
                    logger.info(f"  {vid_name} mid Thomas: {tid.get('similarity')}")

        except Exception as e:
            logger.warning(f"  Video scoring error for {vid_name}: {e}")

    return results


def main():
    start_total = time.time()

    # Load shot + cast map
    sp = json.load(open(os.path.join(PROJ, "shot_plan.json")))
    shots = sp if isinstance(sp, list) else sp.get("shots", [])
    cm = json.load(open(os.path.join(PROJ, "cast_map.json")))
    shot = next((s for s in shots if s.get("shot_id") == "001_005B"), None)

    if not shot:
        logger.error("001_005B not found!")
        return

    os.makedirs(FRAMES_DIR, exist_ok=True)
    os.makedirs(VIDEOS_DIR, exist_ok=True)
    os.makedirs(REPORTS_DIR, exist_ok=True)

    probe_report = {
        "shot_id": "001_005B",
        "timestamp": datetime.now().isoformat(),
        "shot_type": shot.get("shot_type"),
        "characters": shot.get("characters"),
        "dialogue": shot.get("dialogue_text", "")[:100],
        "stages": {},
    }

    # STAGE 1: Generate first frame
    logger.info("\n" + "=" * 60)
    logger.info("PROBE RENDER: 001_005B — OTS DIALOGUE (THOMAS + ELEANOR)")
    logger.info("=" * 60)

    frame_result = generate_first_frame(shot, cm)
    probe_report["stages"]["first_frame"] = frame_result

    if frame_result["status"] != "SUCCESS":
        logger.error("FIRST FRAME GENERATION FAILED — aborting probe")
        probe_report["verdict"] = "FAIL_FRAME"
        save_report(probe_report)
        return

    canonical_frame = frame_result["canonical"]

    # STAGE 2A: LTX Video
    ltx_result = generate_ltx_video(canonical_frame)
    probe_report["stages"]["ltx_video"] = ltx_result

    # STAGE 2B: Kling Video
    kling_result = generate_kling_video(canonical_frame)
    probe_report["stages"]["kling_video"] = kling_result

    # STAGE 3: Vision scoring
    video_paths = []
    if ltx_result.get("path"):
        video_paths.append(ltx_result["path"])
    if kling_result.get("path"):
        video_paths.append(kling_result["path"])

    vision_results = score_outputs(canonical_frame, video_paths)
    probe_report["stages"]["vision"] = vision_results

    # STAGE 4: Comparison summary
    elapsed_total = round(time.time() - start_total, 2)

    comparison = {
        "first_frame_elapsed": frame_result.get("elapsed"),
        "ltx_elapsed": ltx_result.get("elapsed"),
        "kling_elapsed": kling_result.get("elapsed"),
        "ltx_status": ltx_result.get("status"),
        "kling_status": kling_result.get("status"),
        "total_elapsed": elapsed_total,
        "total_cost_estimate": 0.15 + 0.16 + 0.56,  # frame + ltx + kling
    }

    # Identity comparison across models
    for key in ["thomas_identity", "location_similarity"]:
        val = vision_results.get(key)
        if val:
            comparison[f"frame_{key}"] = val.get("similarity", val) if isinstance(val, dict) else val

    probe_report["comparison"] = comparison
    probe_report["total_elapsed"] = elapsed_total
    probe_report["verdict"] = "SUCCESS" if frame_result["status"] == "SUCCESS" else "PARTIAL"

    save_report(probe_report)

    # Print summary
    logger.info("\n" + "=" * 60)
    logger.info("PROBE COMPLETE")
    logger.info("=" * 60)
    logger.info(f"  Total time: {elapsed_total}s")
    logger.info(f"  First frame: {frame_result['status']} ({frame_result.get('elapsed')}s, {frame_result.get('candidates')} candidates)")
    logger.info(f"  LTX video: {ltx_result.get('status')} ({ltx_result.get('elapsed')}s)")
    logger.info(f"  Kling video: {kling_result.get('status')} ({kling_result.get('elapsed')}s)")

    qa = vision_results.get("fast_qa", {})
    logger.info(f"  Frame quality: sharpness={qa.get('sharpness')}, passed={qa.get('passed')}")

    thomas = vision_results.get("thomas_identity", {})
    eleanor = vision_results.get("eleanor_identity", {})
    logger.info(f"  Thomas identity: {thomas.get('similarity', 'N/A')}")
    logger.info(f"  Eleanor identity: {eleanor.get('similarity', 'N/A')}")
    logger.info(f"  Location: {vision_results.get('location_similarity', 'N/A')}")


def save_report(report):
    path = os.path.join(REPORTS_DIR, "probe_render_001_005B.json")
    with open(path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    logger.info(f"  Report saved: {path}")


if __name__ == "__main__":
    main()
