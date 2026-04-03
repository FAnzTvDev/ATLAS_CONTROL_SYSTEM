#!/usr/bin/env python3
"""
Generate specific independent shots (E-shots, inserts) that are skipped by cold-open logic.
Uses the same gen_frame infrastructure as atlas_universal_runner.py.

Usage:
    python3 tools/gen_independent_shots.py <project> <shot_id> [shot_id ...]

Example:
    python3 tools/gen_independent_shots.py victorian_shadows_ep1 008_E01 008_E02 008_E03 008_M03b
"""
import sys, os, json, time
from pathlib import Path

# ── ENV SETUP (same as runner) ──────────────────────────────────────
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
from tools.scene_visual_dna import build_scene_dna
from tools.prompt_identity_injector import inject_identity_into_prompt

FAL_KEY = os.environ.get("FAL_KEY", "")

def gen_independent_frame(shot, cast_map, location_masters, scene_id, frame_dir):
    """Generate a single independent frame (E-shot/insert) via nano-banana-pro."""
    sid = shot["shot_id"]
    chars = shot.get("characters", [])
    is_broll = shot.get("_is_broll", False)
    no_char = shot.get("_no_char_ref", False)

    # Build prompt
    prompt = shot.get("nano_prompt", "") or shot.get("description", "")
    if not prompt:
        print(f"  [SKIP] {sid}: no prompt or description")
        return None

    # Room DNA
    dna = shot.get("_room_dna", "")
    if dna:
        prompt += f"\n[ROOM DNA: {dna}]"

    # No-character constraint for empty shots
    if not chars or is_broll or no_char:
        if "no people" not in prompt.lower() and "no figures" not in prompt.lower():
            prompt += "\nNo people visible, no figures, empty space only."

    # Identity injection for shots with characters
    if chars:
        try:
            prompt = inject_identity_into_prompt(prompt, shot, cast_map)
        except Exception as e:
            print(f"  [WARN] {sid}: identity injection failed: {e}")

    # Resolve refs
    image_urls = []

    # Location master
    loc_master = None
    for lm_path in sorted(Path(location_masters).glob(f"{scene_id}*master*")):
        loc_master = str(lm_path)
        break
    if not loc_master:
        for lm_path in sorted(Path(location_masters).glob(f"{scene_id}*")):
            loc_master = str(lm_path)
            break

    if loc_master and os.path.exists(loc_master):
        # Upload location master
        try:
            loc_url = fal_client.upload_file(loc_master)
            image_urls.append(loc_url)
        except Exception as e:
            print(f"  [WARN] {sid}: location upload failed: {e}")

    # Character refs (for M03b which has chars implied)
    if chars and not no_char:
        for char_name in chars[:2]:
            char_key = char_name.upper().replace(" ", "_")
            for cm_char in cast_map.values():
                if isinstance(cm_char, dict):
                    ref_url = cm_char.get("character_reference_url", "")
                    cm_name = (cm_char.get("character_name", "") or cm_char.get("name", "")).upper()
                    if cm_name and cm_name in char_name.upper() and ref_url:
                        if os.path.exists(ref_url):
                            try:
                                uploaded = fal_client.upload_file(ref_url)
                                image_urls.append(uploaded)
                            except:
                                pass
                        break

    # Determine model: edit (with refs) or base (text-only)
    if image_urls:
        model = "fal-ai/nano-banana-pro/edit"
        payload = {
            "prompt": prompt[:2500],
            "image_urls": image_urls,
            "aspect_ratio": "16:9",
            "output_format": "jpeg",
            "safety_tolerance": "5",
            "num_images": 1,
        }
    else:
        model = "fal-ai/nano-banana-pro"
        payload = {
            "prompt": prompt[:2500],
            "aspect_ratio": "16:9",
            "output_format": "jpeg",
            "safety_tolerance": "5",
            "num_images": 1,
        }

    print(f"  [FRAME] {sid}: {model.split('/')[-1]}, {len(image_urls)} refs, {len(prompt)} chars")

    t0 = time.time()
    try:
        result = fal_client.subscribe(model, arguments=payload)
        images = result.get("images", [])
        if not images:
            print(f"  [FAIL] {sid}: no images returned")
            return None

        img_url = images[0].get("url", "")
        if not img_url:
            print(f"  [FAIL] {sid}: no image URL")
            return None

        # Download
        import urllib.request
        out_path = os.path.join(frame_dir, f"{sid}.jpg")
        urllib.request.urlretrieve(img_url, out_path)
        elapsed = time.time() - t0
        fsize = os.path.getsize(out_path) // 1024
        print(f"  [FRAME] {sid}: OK — {fsize}KB — {elapsed:.1f}s")
        return out_path

    except Exception as e:
        print(f"  [FAIL] {sid}: FAL error: {e}")
        return None


def main():
    if len(sys.argv) < 3:
        print("Usage: python3 tools/gen_independent_shots.py <project> <shot_id> [shot_id ...]")
        sys.exit(1)

    project = sys.argv[1]
    target_sids = set(sys.argv[2:])

    proj_dir = Path("pipeline_outputs") / project
    sp_path = proj_dir / "shot_plan.json"
    cm_path = proj_dir / "cast_map.json"
    sb_path = proj_dir / "story_bible.json"
    frame_dir = proj_dir / "first_frames"
    loc_dir = proj_dir / "location_masters"

    frame_dir.mkdir(exist_ok=True)

    sp = json.load(open(sp_path))
    if isinstance(sp, list):
        shots_list = sp
    else:
        shots_list = sp.get("shots", [])

    cast_map = json.load(open(cm_path)) if cm_path.exists() else {}

    # Find target shots
    targets = [s for s in shots_list if s.get("shot_id") in target_sids]
    if not targets:
        print(f"No shots found matching: {target_sids}")
        sys.exit(1)

    print(f"\n{'='*70}")
    print(f"  INDEPENDENT SHOT GENERATOR — {len(targets)} shots")
    print(f"  Project: {project}")
    print(f"  Targets: {[s['shot_id'] for s in targets]}")
    print(f"{'='*70}\n")

    scene_id = targets[0]["shot_id"][:3]
    results = {}

    for shot in targets:
        sid = shot["shot_id"]
        result = gen_independent_frame(shot, cast_map, str(loc_dir), scene_id, str(frame_dir))
        if result:
            results[sid] = result

    # Write results back to shot_plan
    if results:
        updated = 0
        for s in shots_list:
            sid = s.get("shot_id", "")
            if sid in results:
                s["first_frame_url"] = f"/api/media?path={results[sid]}"
                s["first_frame_path"] = results[sid]
                s["_approval_status"] = "AUTO_APPROVED"
                updated += 1

        # Save
        if isinstance(sp, list):
            json.dump(shots_list, open(sp_path, 'w'), indent=2)
        else:
            sp["shots"] = shots_list
            json.dump(sp, open(sp_path, 'w'), indent=2)

        print(f"\n  ✅ {updated}/{len(targets)} frames generated and written to shot_plan")
        print(f"  Status: AUTO_APPROVED (per user directive — opener intelligence trusted)")
    else:
        print(f"\n  ❌ No frames generated")

    return results


if __name__ == "__main__":
    main()
