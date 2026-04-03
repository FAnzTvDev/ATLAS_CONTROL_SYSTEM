#!/usr/bin/env python3
"""
Generate videos for specific independent shots (E-shots, inserts) using Kling v3/pro.
Each shot generates independently from its own first frame — no chaining.

Usage:
    python3 tools/gen_independent_videos.py <project> <shot_id> [shot_id ...]
"""
import sys, os, json, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── ENV SETUP ──────────────────────────────────────────────────────
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    for line in _env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

import fal_client

KLING_MODEL = "fal-ai/kling-video/v3/pro/image-to-video"


def gen_video_for_shot(shot, frame_dir, video_dir):
    """Generate a Kling video from a shot's first frame."""
    sid = shot["shot_id"]

    # Find first frame
    frame_path = shot.get("first_frame_path", "")
    if not frame_path or not os.path.exists(frame_path):
        frame_path = os.path.join(frame_dir, f"{sid}.jpg")
    if not os.path.exists(frame_path):
        print(f"  [SKIP] {sid}: no first frame at {frame_path}")
        return None

    # Build video prompt from shot data
    desc = shot.get("description", "")
    beat_action = shot.get("_beat_action", "")
    prompt_text = beat_action if beat_action else desc

    # For E-shots/inserts: slow atmospheric movement
    is_broll = shot.get("_is_broll", False)
    no_char = shot.get("_no_char_ref", False)
    chars = shot.get("characters", [])

    if not chars or is_broll or no_char:
        # Atmospheric E-shot: slow camera movement, no character action
        if "exterior" in desc.lower() or "ext " in desc.lower():
            motion = "Slow push-in. Atmospheric exterior. No people. Gentle wind."
        elif "close" in desc.lower() or "ecu" in desc.lower() or "insert" in desc.lower():
            motion = "Slow drift. Extreme close detail. Subtle light shift. No people."
        else:
            motion = "Slow dolly forward. Empty interior. Dust motes in light. No people."
        video_prompt = f"{prompt_text[:300]}. {motion}"
    else:
        video_prompt = prompt_text[:450]

    # Trim to Kling limit
    video_prompt = video_prompt[:512]

    # Upload first frame
    try:
        start_url = fal_client.upload_file(frame_path)
    except Exception as e:
        print(f"  [FAIL] {sid}: frame upload failed: {e}")
        return None

    # Duration: E-shots = 5s, inserts = 5s
    duration = "5"

    payload = {
        "start_image_url": start_url,
        "multi_prompt": [{"prompt": video_prompt, "duration": duration}],
        "aspect_ratio": "16:9",
        "negative_prompt": "blurry, distorted, deformed, extra limbs, text overlay, watermark, logo, static, frozen, people, figures, humans",
        "cfg_scale": 0.5,
    }

    print(f"  [VIDEO] {sid}: Kling v3/pro, {duration}s, {len(video_prompt)} chars")

    t0 = time.time()
    try:
        result = fal_client.subscribe(KLING_MODEL, arguments=payload)
        video_data = result.get("video", {})
        video_url = video_data.get("url", "")
        if not video_url:
            print(f"  [FAIL] {sid}: no video URL returned")
            return None

        # Download video
        import urllib.request
        out_path = os.path.join(video_dir, f"{sid}.mp4")
        urllib.request.urlretrieve(video_url, out_path)
        elapsed = time.time() - t0
        fsize = os.path.getsize(out_path) // (1024 * 1024)
        print(f"  [VIDEO] {sid}: OK — {fsize}MB — {elapsed:.1f}s")
        return out_path

    except Exception as e:
        print(f"  [FAIL] {sid}: Kling error: {e}")
        return None


def main():
    if len(sys.argv) < 3:
        print("Usage: python3 tools/gen_independent_videos.py <project> <shot_id> [shot_id ...]")
        sys.exit(1)

    project = sys.argv[1]
    target_sids = set(sys.argv[2:])

    proj_dir = Path("pipeline_outputs") / project
    sp_path = proj_dir / "shot_plan.json"
    frame_dir = proj_dir / "first_frames"
    video_dir = proj_dir / "videos_kling_lite"
    video_dir.mkdir(exist_ok=True)

    sp = json.load(open(sp_path))
    if isinstance(sp, list):
        shots_list = sp
    else:
        shots_list = sp.get("shots", [])

    targets = [s for s in shots_list if s.get("shot_id") in target_sids]
    if not targets:
        print(f"No shots found matching: {target_sids}")
        sys.exit(1)

    print(f"\n{'='*70}")
    print(f"  INDEPENDENT VIDEO GENERATOR — {len(targets)} shots")
    print(f"  Project: {project} | Model: Kling v3/pro")
    print(f"  Targets: {[s['shot_id'] for s in targets]}")
    print(f"{'='*70}\n")

    # Generate in parallel (independent shots, no chain deps)
    results = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        futs = {pool.submit(gen_video_for_shot, s, str(frame_dir), str(video_dir)): s["shot_id"] for s in targets}
        for f in as_completed(futs):
            sid = futs[f]
            try:
                result = f.result()
                if result:
                    results[sid] = result
            except Exception as e:
                print(f"  [ERROR] {sid}: {e}")

    # Write results back to shot_plan
    if results:
        updated = 0
        for s in shots_list:
            sid = s.get("shot_id", "")
            if sid in results:
                s["video_url"] = f"/api/media?path={results[sid]}"
                s["video_path"] = results[sid]
                updated += 1

        if isinstance(sp, list):
            json.dump(shots_list, open(sp_path, 'w'), indent=2)
        else:
            sp["shots"] = shots_list
            json.dump(sp, open(sp_path, 'w'), indent=2)

        # Cost estimate: $2.80 per 5s Kling v3/pro call
        cost = len(results) * 2.80
        print(f"\n  ✅ {updated}/{len(targets)} videos generated")
        print(f"  Estimated cost: ${cost:.2f}")
    else:
        print(f"\n  ❌ No videos generated")

    return results


if __name__ == "__main__":
    main()
