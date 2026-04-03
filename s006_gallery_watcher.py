#!/usr/bin/env python3
"""
S006 Gallery Watcher — pushes each Kling clip to R2 gallery as soon as it lands.
Watches videos_kling_lite/ for the 7 S006 files, uploads each immediately, then stitches.
"""
import sys, os, time, subprocess
from pathlib import Path

sys.path.insert(0, '/Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM')
from atlas_push_r2 import push_file

PROJECT = "pipeline_outputs/victorian_shadows_ep1"
VIDEO_DIR = Path(PROJECT) / "videos_kling_lite"
STITCH_DIR = Path(PROJECT) / "videos"
STITCH_DIR.mkdir(exist_ok=True)

# Expected files in scene order (group numbers match shot_plan video_url paths)
EXPECTED = [
    "multishot_g1_006_E01.mp4",
    "multishot_g2_006_E02.mp4",
    "multishot_g3_006_E03.mp4",
    "multishot_g4_006_M01.mp4",
    "multishot_g5_006_M02.mp4",
    "multishot_g6_006_M03.mp4",
    "multishot_g7_006_M04.mp4",
]

MIN_BYTES = 5000
POLL_INTERVAL = 8   # seconds
TIMEOUT_MINS = 30

pushed = set()
start = time.time()

# Also get prompts from shot_plan for gallery labels
import json
with open(f"{PROJECT}/shot_plan.json") as f:
    data = json.load(f)
shots = data["shots"]
prompt_map = {}
for s in shots:
    sid = s.get("shot_id", "")
    if "006" in sid:
        prompt_map[sid] = s.get("nano_prompt", s.get("_beat_action", ""))[:200]

def shot_id_from_fname(fname):
    # multishot_g4_006_M01.mp4 → 006_M01
    parts = fname.replace(".mp4", "").split("_")
    # find the "006" part
    for i, p in enumerate(parts):
        if p == "006" and i + 1 < len(parts):
            return f"006_{parts[i+1]}"
    return fname

print(f"[WATCHER] Monitoring {VIDEO_DIR} for {len(EXPECTED)} S006 clips…")
print(f"[WATCHER] Will push each to https://media.rumbletv.com/gallery/index.html on arrival")
print()

while True:
    elapsed = (time.time() - start) / 60
    if elapsed > TIMEOUT_MINS:
        print(f"[WATCHER] Timeout after {TIMEOUT_MINS}min — {len(pushed)}/{len(EXPECTED)} pushed")
        break

    newly_pushed = []
    for fname in EXPECTED:
        if fname in pushed:
            continue
        fpath = VIDEO_DIR / fname
        if fpath.exists() and fpath.stat().st_size > MIN_BYTES:
            sid = shot_id_from_fname(fname)
            prompt = prompt_map.get(sid, f"Victorian Shadows S006 {sid}")
            print(f"[WATCHER] ✓ {fname} ({fpath.stat().st_size//1024}KB) — uploading to gallery…")
            ok = push_file(
                local_path=str(fpath),
                prompt=f"VictorianShadows S006/{sid}: {prompt}",
                type="KLING",
            )
            if ok:
                pushed.add(fname)
                newly_pushed.append(fname)
                print(f"[WATCHER] ✅ {fname} live at https://media.rumbletv.com/gallery/index.html")
            else:
                print(f"[WATCHER] ⚠️  push failed for {fname} — will retry next poll")

    remaining = [f for f in EXPECTED if f not in pushed]
    print(f"[WATCHER] {len(pushed)}/{len(EXPECTED)} uploaded — waiting for: {[shot_id_from_fname(r) for r in remaining]}" if remaining else f"[WATCHER] All {len(EXPECTED)} clips uploaded!")

    if not remaining:
        break

    time.sleep(POLL_INTERVAL)

# ── STITCH ─────────────────────────────────────────────────────────────────────
print()
print("[WATCHER] Starting stitch…")
ready = [VIDEO_DIR / f for f in EXPECTED if (VIDEO_DIR / f).exists() and (VIDEO_DIR / f).stat().st_size > MIN_BYTES]
if len(ready) < 2:
    print(f"[WATCHER] Only {len(ready)} clips ready — skipping stitch")
    sys.exit(0)

concat_list = Path("/tmp/s006_concat.txt")
with open(concat_list, "w") as fp:
    for p in ready:
        fp.write(f"file '{p.resolve()}'\n")

stitch_out = STITCH_DIR / "scene_006_stitch.mp4"
cmd = [
    "ffmpeg", "-y",
    "-f", "concat", "-safe", "0", "-i", str(concat_list),
    "-c:v", "libx264", "-preset", "fast", "-crf", "22",
    "-an",                      # no audio (Kling SEI / no audio track)
    "-movflags", "+faststart",
    str(stitch_out)
]
print(f"[WATCHER] ffmpeg stitching {len(ready)} clips → {stitch_out.name}")
result = subprocess.run(cmd, capture_output=True, text=True)
if result.returncode != 0:
    print(f"[WATCHER] ffmpeg error:\n{result.stderr[-800:]}")
    sys.exit(1)

size_mb = stitch_out.stat().st_size / 1_000_000
print(f"[WATCHER] Stitch done: {stitch_out.name} ({size_mb:.1f}MB)")

# Push stitch to gallery
print("[WATCHER] Uploading stitch to gallery…")
ok = push_file(
    local_path=str(stitch_out),
    prompt="Victorian Shadows EP1 — Scene 006 full stitch (7 Kling clips)",
    type="STITCH",
)
if ok:
    print(f"[WATCHER] ✅ Stitch live: https://media.rumbletv.com/gallery/index.html")
else:
    print(f"[WATCHER] ⚠️  Stitch push failed")

print(f"\n[WATCHER] Done. {len(pushed)} individual clips + 1 stitch pushed to gallery.")
