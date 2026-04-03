#!/usr/bin/env python3
"""
ATLAS V27.4 Strategic Test Render
Generates 16 diagnostic shots across the full movie.
Max 16 FAL calls. Direct FAL API, no server needed.
"""
import json, os, sys, time, base64
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# Load env
from dotenv import load_dotenv
load_dotenv()

FAL_KEY = os.environ.get("FAL_KEY", "")
if not FAL_KEY:
    print("ERROR: FAL_KEY not set"); sys.exit(1)

import fal_client

PROJECT = Path("pipeline_outputs/victorian_shadows_ep1")
CHAR_LIB = PROJECT / "character_library_locked"
LOC_MASTERS = PROJECT / "location_masters"
OUTPUT_DIR = Path("V27_4_StrategicTest")
OUTPUT_DIR.mkdir(exist_ok=True)

# Load data
with open(PROJECT / "shot_plan.json") as f:
    sp = json.load(f)
shots_all = sp if isinstance(sp, list) else sp.get("shots", [])
shots_map = {s["shot_id"]: s for s in shots_all}

with open(PROJECT / "cast_map.json") as f:
    cast_map = json.load(f)

# ============================================================
# STRATEGIC TEST MATRIX — 16 shots, max diagnostic coverage
# ============================================================
TEST_SHOTS = [
    # Scene 003: Drawing Room — Raymond intro
    "003_021A",  # Drawing Room establishing (NEW location)
    "003_027B",  # Raymond MCU (NEW character)
    # Scene 004: Garden — Thomas exterior
    "004_034A",  # Garden establishing (EXTERIOR)
    # Scene 005: Master Bedroom
    "005_043A",  # Master Bedroom establishing (NEW location)
    # Scene 006: Kitchen — 3 characters
    "006_055B",  # 3-char medium (HARDEST shot type)
    # Scene 007: Master Bedroom — Nadia
    "007_070B",  # Nadia MCU (identity in new room)
    # Scene 008: Grand Staircase — Raymond
    "008_075A",  # Staircase establishing (NEW location + Raymond)
    # Scene 009: Front Drive — exterior
    "009_085A",  # Front Drive establishing (EXTERIOR)
    "009_094B",  # Thomas MCU exterior
    # Scene 010: Drawing Room confrontation
    "010_108B",  # Eleanor MCU (emotion peak)
    # Scene 011: Library golden hour — confession
    "011_111A",  # Library establishing (GOLDEN HOUR — different light from Scene 002)
    "011_116B",  # Thomas confession MCU (emotional climax)
    # Scene 012: Foyer twilight — climax
    "012_132B",  # 3-char medium foyer (twilight)
    "012_140B",  # Thomas MCU climax
    # Scene 013: Exterior night — coda
    "013_144A",  # Exterior night (FINAL SHOT)
    # Scene 004: Thomas+Eleanor garden dialogue
    "004_038B",  # Outdoor 2-char dialogue
]

# ============================================================
# LOCATION MAPPING
# ============================================================
SCENE_LOCATIONS = {
    "003": "DRAWING_ROOM", "004": "GARDEN", "005": "MASTER_BEDROOM",
    "006": "KITCHEN", "007": "MASTER_BEDROOM", "008": "GRAND_STAIRCASE",
    "009": "FRONT_DRIVE", "010": "DRAWING_ROOM", "011": "LIBRARY",
    "012": "GRAND_FOYER", "013": "EXTERIOR_WIDE",
}

def find_location_master(scene_id):
    """Find the best location master for a scene."""
    loc_key = SCENE_LOCATIONS.get(scene_id, "")
    # Try exact match first
    for pattern in [
        f"HARGROVE_ESTATE_-_{loc_key}.jpg",
        f"HARGROVE_ESTATE___{loc_key}.jpg",
    ]:
        p = LOC_MASTERS / pattern
        if p.exists():
            return str(p)
    # Fuzzy match
    for f in LOC_MASTERS.iterdir():
        if loc_key.lower().replace("_", "") in f.name.lower().replace("_", ""):
            if "medium" not in f.name and "reverse" not in f.name:
                return str(f)
    return None

def find_char_refs(characters, shot_type):
    """Find character reference images based on shot type."""
    refs = []
    for char_name in characters[:2]:  # max 2 char refs
        safe = char_name.replace(" ", "_")
        # Pick ref by shot type
        if shot_type in ("close_up", "medium_close", "reaction"):
            pref = [f"{safe}_CHAR_REFERENCE.jpg"]
        elif shot_type in ("medium", "two_shot", "over_the_shoulder"):
            pref = [f"{safe}_three_quarter.jpg", f"{safe}_CHAR_REFERENCE.jpg"]
        else:
            pref = [f"{safe}_full_body.jpg", f"{safe}_three_quarter.jpg", f"{safe}_CHAR_REFERENCE.jpg"]

        for ref_name in pref:
            ref_path = CHAR_LIB / ref_name
            if ref_path.exists():
                refs.append(str(ref_path))
                break
    return refs

def upload_to_fal(file_path):
    """Upload a local file to FAL and get a URL."""
    url = fal_client.upload_file(file_path)
    return url

def generate_shot(shot_id):
    """Generate a single first frame via FAL nano-banana-pro."""
    shot = shots_map.get(shot_id)
    if not shot:
        return {"shot_id": shot_id, "error": "Shot not found"}

    scene_id = shot.get("scene_id", shot_id[:3])
    shot_type = shot.get("shot_type", "medium")
    characters = shot.get("characters", [])
    prompt = shot.get("nano_prompt", "")

    if not prompt:
        return {"shot_id": shot_id, "error": "No nano_prompt"}

    # Build image_urls from refs
    image_urls = []

    # Character refs
    char_refs = find_char_refs(characters, shot_type)
    for ref in char_refs:
        try:
            url = upload_to_fal(ref)
            image_urls.append(url)
        except Exception as e:
            print(f"  [WARN] Failed to upload char ref for {shot_id}: {e}")

    # Location ref
    loc_master = find_location_master(scene_id)
    if loc_master:
        try:
            url = upload_to_fal(loc_master)
            image_urls.append(url)
        except Exception as e:
            print(f"  [WARN] Failed to upload loc ref for {shot_id}: {e}")

    # Truncate prompt to 1500 chars (FAL limit)
    prompt = prompt[:1500]

    # Build FAL payload
    payload = {
        "prompt": prompt,
        "aspect_ratio": "16:9",
        "output_format": "jpeg",
        "safety_tolerance": 6,
        "num_images": 1,
    }
    if image_urls:
        payload["image_urls"] = image_urls

    t0 = time.time()
    try:
        result = fal_client.subscribe(
            "fal-ai/nano-banana-pro",
            arguments=payload,
        )
        elapsed = time.time() - t0

        # Save the image
        if result and "images" in result and result["images"]:
            img_url = result["images"][0].get("url", "")
            if img_url:
                import urllib.request
                out_path = OUTPUT_DIR / f"{shot_id}.jpg"
                urllib.request.urlretrieve(img_url, str(out_path))
                return {
                    "shot_id": shot_id,
                    "success": True,
                    "elapsed": round(elapsed, 1),
                    "scene_id": scene_id,
                    "shot_type": shot_type,
                    "characters": characters,
                    "char_refs": len(char_refs),
                    "loc_ref": bool(loc_master),
                    "image_urls_count": len(image_urls),
                    "output": str(out_path),
                }
        return {"shot_id": shot_id, "error": "No image in result", "elapsed": round(elapsed, 1)}
    except Exception as e:
        elapsed = time.time() - t0
        return {"shot_id": shot_id, "error": str(e)[:200], "elapsed": round(elapsed, 1)}


def main():
    print(f"=" * 60)
    print(f"ATLAS V27.4 STRATEGIC TEST RENDER")
    print(f"Shots: {len(TEST_SHOTS)} | Max FAL calls: {len(TEST_SHOTS)}")
    print(f"=" * 60)

    results = []
    # Run in parallel batches of 4 to stay reasonable
    batch_size = 4
    for i in range(0, len(TEST_SHOTS), batch_size):
        batch = TEST_SHOTS[i:i+batch_size]
        print(f"\n--- Batch {i//batch_size + 1}: {batch} ---")

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {executor.submit(generate_shot, sid): sid for sid in batch}
            for future in as_completed(futures):
                r = future.result()
                results.append(r)
                status = "OK" if r.get("success") else f"FAIL: {r.get('error','?')[:60]}"
                elapsed = r.get("elapsed", 0)
                print(f"  [{r['shot_id']}] {status} ({elapsed}s)")

    # Summary
    print(f"\n{'=' * 60}")
    print(f"RESULTS SUMMARY")
    print(f"{'=' * 60}")
    success = [r for r in results if r.get("success")]
    failed = [r for r in results if not r.get("success")]
    print(f"Success: {len(success)}/{len(results)}")
    print(f"Failed:  {len(failed)}/{len(results)}")
    if failed:
        for r in failed:
            print(f"  FAIL: {r['shot_id']} — {r.get('error','?')[:80]}")

    # Save results
    with open(OUTPUT_DIR / "test_results.json", "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nResults saved to {OUTPUT_DIR}/test_results.json")
    print(f"Frames saved to {OUTPUT_DIR}/")

    # Coverage analysis
    print(f"\n--- COVERAGE ANALYSIS ---")
    scenes_hit = set(r.get("scene_id") for r in success)
    chars_hit = set()
    for r in success:
        for c in r.get("characters", []):
            chars_hit.add(c)
    types_hit = set(r.get("shot_type") for r in success)

    print(f"Scenes covered: {sorted(scenes_hit)} ({len(scenes_hit)}/13)")
    print(f"Characters hit: {sorted(chars_hit)} ({len(chars_hit)}/4)")
    print(f"Shot types hit: {sorted(types_hit)} ({len(types_hit)})")

    avg_time = sum(r.get("elapsed", 0) for r in success) / max(len(success), 1)
    print(f"Avg generation time: {avg_time:.1f}s")
    print(f"Total FAL calls: {len(TEST_SHOTS)}")


if __name__ == "__main__":
    main()
