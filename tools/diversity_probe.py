#!/usr/bin/env python3
"""
ATLAS V27.1 — Diversity Probe
==============================
Generates first frames + LTX video for 7 diverse shot types to stress-test
the pipeline across different aesthetics, failure modes, and shot governance.

Each shot tests a DIFFERENT universal constraint:
  A: Single-character dialogue close-up → identity lock + mouth movement
  B: Multi-character dialogue medium → identity bleed between characters
  C: Single-character no dialogue → identity without performance cue
  D: Establishing shot → location atmosphere preservation
  E: Reaction shot → micro-expression vs frozen face
  F: B-roll → narrative content vs empty room
  G: Closing shot → atmosphere + emotional tone

Runs through the REAL pipeline endpoint (orchestrator generate-first-frames),
then generates LTX video via direct FAL call, then scores everything with
ArcFace + DINOv2.

Usage:
    python3 tools/diversity_probe.py
"""

import json
import os
import sys
import time
import base64
import logging
import urllib.request

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Config
PROJ = "pipeline_outputs/victorian_shadows_ep1"
PROBE_SHOTS = [
    "002_013A",  # D: establishing
    "002_014B",  # F: b-roll
    "002_017B",  # A: single char dialogue CU
    "002_019A",  # C: single char no dialogue
    "002_020A",  # G: closing
    "003_025B",  # B: multi-char dialogue medium
    "003_032C",  # E: reaction
]

# Probe role descriptions
PROBE_ROLES = {
    "002_013A": "D_establishing",
    "002_014B": "F_broll_atmosphere",
    "002_017B": "A_single_char_dialogue_CU",
    "002_019A": "C_single_char_no_dialogue",
    "002_020A": "G_closing_atmosphere",
    "003_025B": "B_multi_char_dialogue_medium",
    "003_032C": "E_reaction_shot",
}

# Load FAL keys
def load_fal_keys():
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ[k.strip()] = v.strip()
    if not os.environ.get("FAL_KEY"):
        os.environ["FAL_KEY"] = "os.environ.get('FAL_KEY', '')"


def generate_first_frames_via_api(shot_ids):
    """Call orchestrator endpoint to generate first frames."""
    import urllib.request

    payload = json.dumps({
        "project": "victorian_shadows_ep1",
        "shot_ids": shot_ids,
        "force_regen": True,
    }).encode()

    req = urllib.request.Request(
        "http://localhost:9999/api/auto/generate-first-frames",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        resp = urllib.request.urlopen(req, timeout=300)
        return json.loads(resp.read().decode())
    except Exception as e:
        logger.error(f"API call failed: {e}")
        return {"error": str(e)}


def generate_ltx_video(shot_id, frame_path, prompt):
    """Generate LTX-2.3 video from a first frame."""
    import fal_client

    with open(frame_path, "rb") as f:
        frame_b64 = "data:image/jpeg;base64," + base64.b64encode(f.read()).decode()

    # Ensure timing prefix
    if not prompt.startswith("0-"):
        prompt = "0-10s: " + prompt
    # Cap at 900 chars
    if len(prompt) > 900:
        prompt = prompt[:897] + "..."

    t0 = time.time()
    result = fal_client.subscribe("fal-ai/ltx-2/image-to-video/fast", arguments={
        "prompt": prompt,
        "image_url": frame_b64,
        "resolution": "1080p",
        "duration": 10,
        "fps": 25,
    })
    elapsed = time.time() - t0

    url = None
    if isinstance(result, dict):
        vid = result.get("video")
        url = vid.get("url") if isinstance(vid, dict) else vid

    if url:
        video_dir = os.path.join(PROJ, "videos")
        os.makedirs(video_dir, exist_ok=True)
        video_path = os.path.join(video_dir, f"{shot_id}_probe_ltx.mp4")
        urllib.request.urlretrieve(url, video_path)
        sz = os.path.getsize(video_path)
        return {
            "status": "success",
            "path": video_path,
            "elapsed_s": round(elapsed, 1),
            "size_mb": round(sz / 1024 / 1024, 1),
            "prompt_length": len(prompt),
        }

    return {"status": "error", "error": "No video URL in response"}


def score_frame(shot_id, frame_path, shot, cast_map):
    """Score a frame with ArcFace + DINOv2."""
    try:
        sys.path.insert(0, os.path.dirname(__file__))
        from vision_models import get_vision_models
        vm = get_vision_models()
    except ImportError:
        return {"error": "vision_models not available"}

    result = {"shot_id": shot_id, "role": PROBE_ROLES.get(shot_id, "?")}

    chars = shot.get("characters", [])
    if isinstance(chars, str):
        chars = [c.strip() for c in chars.split(",") if c.strip()]

    # Character identity scoring
    char_scores = {}
    for char in chars:
        char_name = char if isinstance(char, str) else char.get("name", "")
        char_safe = char_name.replace(" ", "_").upper()

        # Try to find character ref
        ref_paths = [
            os.path.join(PROJ, "character_library_locked", f"{char_safe}_CHAR_REFERENCE.jpg"),
            os.path.join(PROJ, "character_library_locked", f"{char_safe}_three_quarter.jpg"),
        ]

        for rp in ref_paths:
            if os.path.exists(rp):
                sim = vm.face_similarity(frame_path, rp)
                char_scores[char_name] = {
                    "similarity": round(sim["similarity"], 4),
                    "confidence": sim["confidence"],
                    "ref_used": os.path.basename(rp),
                }
                break
        else:
            char_scores[char_name] = {"similarity": 0, "error": "no_ref_found"}

    result["character_scores"] = char_scores

    # Face detection
    faces = vm.detect_faces(frame_path)
    result["faces_detected"] = len(faces)

    # Location scoring
    scene_id = shot_id[:3]
    loc_refs = [
        os.path.join(PROJ, "location_masters", f"scene_{scene_id}_master.jpg"),
    ]
    # Also check by location name
    import glob
    loc_masters = glob.glob(os.path.join(PROJ, "location_masters", "*.jpg"))
    for lm in loc_masters:
        if scene_id in lm:
            loc_refs.append(lm)

    best_loc = 0
    for lr in loc_refs:
        if os.path.exists(lr):
            loc_sim = vm.image_similarity(frame_path, lr)
            if loc_sim > best_loc:
                best_loc = loc_sim

    result["location_similarity"] = round(best_loc, 4)

    # Primary subject check
    if chars and char_scores:
        primary = chars[0] if isinstance(chars[0], str) else chars[0].get("name", "")
        primary_score = char_scores.get(primary, {}).get("similarity", 0)

        # Check if primary subject is actually the strongest face
        all_scores = [(name, sc.get("similarity", 0)) for name, sc in char_scores.items()]
        if all_scores:
            strongest = max(all_scores, key=lambda x: x[1])
            result["primary_subject"] = primary
            result["primary_score"] = primary_score
            result["strongest_face"] = strongest[0]
            result["strongest_score"] = strongest[1]
            result["subject_correct"] = strongest[0] == primary or len(chars) <= 1

    return result


def main():
    load_fal_keys()

    # Load shot plan and cast map
    sp = json.load(open(os.path.join(PROJ, "shot_plan.json")))
    shots = sp if isinstance(sp, list) else sp.get("shots", [])
    cm = json.load(open(os.path.join(PROJ, "cast_map.json")))

    shot_map = {s.get("shot_id"): s for s in shots}

    report = {
        "probe_type": "diversity_v27.1",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "total_shots": len(PROBE_SHOTS),
        "results": {},
    }

    # PHASE 1: Generate first frames
    logger.info("=" * 60)
    logger.info("PHASE 1: GENERATE FIRST FRAMES (via orchestrator)")
    logger.info("=" * 60)

    # Move existing frames out of the way
    frames_dir = os.path.join(PROJ, "first_frames")
    for sid in PROBE_SHOTS:
        existing = os.path.join(frames_dir, f"{sid}.jpg")
        if os.path.exists(existing):
            backup = os.path.join(frames_dir, f"{sid}_pre_diversity_probe.jpg")
            os.rename(existing, backup)
            logger.info(f"  Backed up {sid}.jpg")

    api_result = generate_first_frames_via_api(PROBE_SHOTS)

    if api_result.get("error"):
        logger.error(f"API error: {api_result['error']}")
        report["phase1_error"] = api_result["error"]
    else:
        for r in api_result.get("results", []):
            sid = r.get("shot_id")
            report["results"][sid] = {
                "role": PROBE_ROLES.get(sid, "?"),
                "frame_status": r.get("status"),
                "ots_verification": r.get("ots_verification"),
                "vision_gate": r.get("vision_gate"),
                "needs_review": r.get("needs_review"),
            }
            logger.info(f"  {sid}: {r.get('status')} (review={r.get('needs_review')})")

    # PHASE 2: Score all frames
    logger.info("")
    logger.info("=" * 60)
    logger.info("PHASE 2: SCORE ALL FRAMES (ArcFace + DINOv2)")
    logger.info("=" * 60)

    for sid in PROBE_SHOTS:
        frame_path = os.path.join(frames_dir, f"{sid}.jpg")
        shot = shot_map.get(sid, {})

        if not os.path.exists(frame_path):
            logger.warning(f"  {sid}: frame not found, skipping score")
            continue

        scores = score_frame(sid, frame_path, shot, cm)
        if sid not in report["results"]:
            report["results"][sid] = {"role": PROBE_ROLES.get(sid, "?")}
        report["results"][sid]["scores"] = scores

        # Log key metrics
        chars = scores.get("character_scores", {})
        loc = scores.get("location_similarity", 0)
        faces = scores.get("faces_detected", 0)
        primary_ok = scores.get("subject_correct", "N/A")

        char_str = ", ".join(f"{k}={v.get('similarity',0):.3f}" for k, v in chars.items())
        logger.info(f"  {sid} [{PROBE_ROLES.get(sid,'')}]: faces={faces} loc={loc:.3f} primary_ok={primary_ok} {char_str}")

    # PHASE 3: Generate LTX videos for character shots
    logger.info("")
    logger.info("=" * 60)
    logger.info("PHASE 3: GENERATE LTX VIDEOS (character shots only)")
    logger.info("=" * 60)

    char_shots = [sid for sid in PROBE_SHOTS if shot_map.get(sid, {}).get("characters")]

    for sid in char_shots:
        frame_path = os.path.join(frames_dir, f"{sid}.jpg")
        if not os.path.exists(frame_path):
            logger.warning(f"  {sid}: no frame, skipping video")
            continue

        shot = shot_map[sid]
        prompt = shot.get("ltx_motion_prompt", "") or shot.get("nano_prompt", "")

        logger.info(f"  Generating LTX for {sid} ({len(prompt)} char prompt)...")
        try:
            vid_result = generate_ltx_video(sid, frame_path, prompt)
            if sid not in report["results"]:
                report["results"][sid] = {"role": PROBE_ROLES.get(sid, "?")}
            report["results"][sid]["ltx_video"] = vid_result
            logger.info(f"    {vid_result.get('status')} ({vid_result.get('elapsed_s', 0)}s, {vid_result.get('size_mb', 0)}MB)")
        except Exception as e:
            logger.error(f"    LTX error for {sid}: {e}")
            if sid in report["results"]:
                report["results"][sid]["ltx_video"] = {"status": "error", "error": str(e)}

    # PHASE 4: Summary
    logger.info("")
    logger.info("=" * 60)
    logger.info("PHASE 4: SUMMARY")
    logger.info("=" * 60)

    total_frames = sum(1 for r in report["results"].values() if r.get("frame_status") == "success")
    total_videos = sum(1 for r in report["results"].values() if r.get("ltx_video", {}).get("status") == "success")
    identity_passes = sum(1 for r in report["results"].values()
                         if r.get("scores", {}).get("subject_correct", False))
    review_needed = sum(1 for r in report["results"].values() if r.get("needs_review"))

    report["summary"] = {
        "frames_generated": total_frames,
        "videos_generated": total_videos,
        "identity_passes": identity_passes,
        "review_needed": review_needed,
        "total_probes": len(PROBE_SHOTS),
    }

    logger.info(f"  Frames: {total_frames}/{len(PROBE_SHOTS)}")
    logger.info(f"  Videos: {total_videos}/{len(char_shots)}")
    logger.info(f"  Identity passes: {identity_passes}")
    logger.info(f"  Need review: {review_needed}")

    # Save report
    report_path = os.path.join(PROJ, "reports", "diversity_probe_report.json")
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    logger.info(f"\nReport saved: {report_path}")

    return report


if __name__ == "__main__":
    main()
