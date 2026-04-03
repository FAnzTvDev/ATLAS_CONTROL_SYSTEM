#!/usr/bin/env python3
"""
ATLAS V17 DIRECTOR CLI - Quick Control System
=============================================
Control the entire pipeline from command line, even if UI is broken.

Usage:
    python3 tools/director_cli.py status
    python3 tools/director_cli.py scenes
    python3 tools/director_cli.py shots E011_S01
    python3 tools/director_cli.py generate scene E011_S01
    python3 tools/director_cli.py generate all --auto
    python3 tools/director_cli.py review E011_S01_000A
    python3 tools/director_cli.py fix cast
    python3 tools/director_cli.py add-broll E011_S01 "candle close-up"
"""

import sys
import json
import subprocess
import requests
from pathlib import Path
from datetime import datetime

# Configuration
API_BASE = "http://127.0.0.1:9999"  # Use IPv4 explicitly (not localhost)
PROJECT = "ravencroft_v17"  # Default project

# Create session that ignores proxy environment variables
SESSION = requests.Session()
SESSION.trust_env = False  # Fixes "curl works, requests hangs" issue

# ANSI colors for terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'

def c(text, color):
    return f"{color}{text}{Colors.END}"

def api_get(endpoint, timeout=30):
    """GET request using session (no proxy, IPv4)"""
    try:
        resp = SESSION.get(f"{API_BASE}{endpoint}", timeout=timeout)
        return resp.json()
    except Exception as e:
        return {"error": str(e)}

def api_post(endpoint, data, timeout=60):
    """POST request using session (no proxy, IPv4)"""
    try:
        resp = SESSION.post(f"{API_BASE}{endpoint}", json=data, timeout=timeout)
        return resp.json()
    except Exception as e:
        return {"error": str(e)}

def api_post_long(endpoint, data):
    """For generation endpoints that may take a long time"""
    return api_post(endpoint, data, timeout=600)  # 10 minute timeout

# ============================================================
# COMMANDS
# ============================================================

def cmd_status():
    """Show full system status"""
    print(c("\n🎬 ATLAS V17 DIRECTOR CLI", Colors.HEADER + Colors.BOLD))
    print("=" * 60)

    # Check server
    try:
        resp = requests.get(f"{API_BASE}/api/auto/projects", timeout=5)
        projects = resp.json().get("projects", [])
        print(c("✅ Server: ONLINE", Colors.GREEN))
        print(f"   Projects: {len(projects)}")
    except:
        print(c("❌ Server: OFFLINE", Colors.RED))
        print("   Run: python3 orchestrator_server.py")
        return

    # Get project info
    bundle = api_get(f"/api/v16/ui/bundle/{PROJECT}")
    if bundle.get("success"):
        summary = bundle.get("shot_plan_summary", {})
        print(c(f"\n📊 Project: {PROJECT}", Colors.CYAN))
        print(f"   Total Shots: {summary.get('total_shots', 0)}")
        print(f"   Total Duration: {summary.get('total_duration', 0)}s ({summary.get('total_duration', 0)//60}m {summary.get('total_duration', 0)%60}s)")
        print(f"   Scenes: {summary.get('scenes', 0)}")
        print(f"   Characters: {len(bundle.get('characters_list', []))}")
        print(f"   Cast: {len([k for k in bundle.get('cast_map', {}).keys() if not k.startswith('_')])}")

    # Check for first frames
    ff_path = Path(f"pipeline_outputs/{PROJECT}/first_frames")
    if ff_path.exists():
        frames = list(ff_path.glob("*.jpg")) + list(ff_path.glob("*.png"))
        print(f"\n🖼️  First Frames: {len(frames)} generated")

    # Check for videos
    vid_path = Path(f"pipeline_outputs/{PROJECT}/videos")
    if vid_path.exists():
        videos = list(vid_path.glob("*.mp4"))
        print(f"🎬 Videos: {len(videos)} rendered")

    print(c("\n📋 Quick Commands:", Colors.YELLOW))
    print("   status     - This status view")
    print("   scenes     - List all scenes")
    print("   shots X    - Show shots for scene X")
    print("   gen scene X - Generate scene X")
    print("   gen all    - Generate everything (auto)")
    print("   fix cast   - Clean up casting errors")
    print("   add-broll  - Add B-roll shot")
    print()

def cmd_scenes():
    """List all scenes"""
    bundle = api_get(f"/api/v16/ui/bundle/{PROJECT}")
    if not bundle.get("success"):
        print(c("❌ Failed to load project", Colors.RED))
        return

    shots = bundle.get("shot_gallery_rows", [])
    scenes = {}
    for shot in shots:
        scene = shot.get("scene_id", "UNKNOWN")
        if scene not in scenes:
            scenes[scene] = {"shots": 0, "duration": 0}
        scenes[scene]["shots"] += 1
        scenes[scene]["duration"] += shot.get("duration", 0) or shot.get("duration_seconds", 0) or 10

    print(c(f"\n🎬 Scenes in {PROJECT}", Colors.HEADER))
    print("=" * 60)
    print(f"{'Scene':<20} {'Shots':>8} {'Duration':>12}")
    print("-" * 60)

    for scene_id, info in sorted(scenes.items()):
        dur = info["duration"]
        dur_str = f"{dur//60}:{dur%60:02d}"
        print(f"{scene_id:<20} {info['shots']:>8} {dur_str:>12}")

    print("-" * 60)
    total_shots = sum(s["shots"] for s in scenes.values())
    total_dur = sum(s["duration"] for s in scenes.values())
    print(f"{'TOTAL':<20} {total_shots:>8} {total_dur//60}:{total_dur%60:02d}")
    print()

def cmd_shots(scene_id):
    """Show shots for a specific scene"""
    bundle = api_get(f"/api/v16/ui/bundle/{PROJECT}")
    if not bundle.get("success"):
        print(c("❌ Failed to load project", Colors.RED))
        return

    shots = [s for s in bundle.get("shot_gallery_rows", []) if s.get("scene_id") == scene_id]

    print(c(f"\n🎬 Shots in {scene_id}", Colors.HEADER))
    print("=" * 80)

    for shot in shots:
        sid = shot.get("shot_id", "???")
        dur = shot.get("duration", 0) or shot.get("duration_seconds", 0) or 10
        stype = shot.get("type", "?")
        chars = ", ".join(shot.get("characters", [])[:2])
        has_frame = "🖼️" if shot.get("first_frame_url") else "⬜"
        has_video = "🎬" if shot.get("video_path") else "⬜"
        nano = (shot.get("nano_prompt") or "")[:50]

        print(f"{has_frame}{has_video} {sid:<18} {dur:>3}s {stype:<10} {chars:<20}")
        if nano:
            print(f"      └─ {c(nano + '...', Colors.CYAN)}")

    print()

def cmd_previs(scene_id, dry_run=False):
    """
    SCENE PREVIS MODE - Generate one scene for review.

    Workflow:
    1. Scene-level validation and auto-fix
    2. Generate first frames
    3. Generate LTX motion (low quality previs)
    4. Pause for review
    """
    print(c("\n" + "=" * 60, Colors.HEADER))
    print(c("  🎬 SCENE PREVIS MODE", Colors.HEADER + Colors.BOLD))
    print(c("=" * 60, Colors.HEADER))

    if dry_run:
        print(c("  [DRY-RUN] No actual generation", Colors.YELLOW))

    # Step 1: Get scene data and validate
    print(c(f"\n📋 SCENE: {scene_id}", Colors.CYAN))
    bundle = api_get(f"/api/v16/ui/bundle/{PROJECT}", timeout=60)
    if not bundle.get("success"):
        print(c(f"❌ Failed to load project: {bundle.get('error')}", Colors.RED))
        return

    all_shots = bundle.get("shot_gallery_rows", [])
    scene_shots = [s for s in all_shots if s.get("scene_id") == scene_id]

    if not scene_shots:
        print(c(f"❌ Scene '{scene_id}' not found", Colors.RED))
        return

    # Scene stats
    scene_duration = sum(s.get("duration", 10) for s in scene_shots)
    total_duration = sum(s.get("duration", 10) for s in all_shots)
    episode_target = 2700  # 45 minutes
    scene_weight = len(scene_shots) / len(all_shots) if all_shots else 0
    scene_target = int(episode_target * scene_weight)
    deviation = abs(scene_duration - scene_target) / scene_target * 100 if scene_target > 0 else 0

    # Count frames and videos
    has_frames = sum(1 for s in scene_shots if s.get("first_frame_url"))
    has_videos = sum(1 for s in scene_shots if s.get("video_path"))

    print(f"   Shots: {len(scene_shots)}")
    print(f"   Duration: {scene_duration}s ({scene_duration/60:.1f}m)")
    print(f"   Target: {scene_target}s ({scene_target/60:.1f}m)")
    print(f"   Deviation: {deviation:.1f}%", end="")
    if deviation <= 15:
        print(c(" ✓", Colors.GREEN))
    else:
        print(c(" ⚠️ (will auto-fix)", Colors.YELLOW))
    print(f"   Frames: {has_frames}/{len(scene_shots)}")
    print(f"   Videos: {has_videos}/{len(scene_shots)}")

    # Step 2: Scene completion gate (auto-fix)
    print(c("\n🔧 SCENE GATE CHECK", Colors.YELLOW))

    issues = []
    # Check for missing prompts
    missing_prompts = [s.get("shot_id") for s in scene_shots if not s.get("nano_prompt")]
    if missing_prompts:
        issues.append(f"Missing prompts: {len(missing_prompts)}")

    # Check for missing cast
    missing_cast = [s.get("shot_id") for s in scene_shots
                    if s.get("characters") and not any(c in bundle.get("cast_map", {}) for c in s.get("characters", []))]
    if missing_cast:
        issues.append(f"Missing cast: {len(missing_cast)}")

    # Check for duration outliers (>30s for previs)
    outliers = [s.get("shot_id") for s in scene_shots if (s.get("duration") or 10) > 30]
    if outliers:
        issues.append(f"Duration outliers (>30s): {len(outliers)}")

    if issues:
        print(c(f"   Issues found: {', '.join(issues)}", Colors.YELLOW))
        if not dry_run:
            print(c("   Running fix-v16 on scene...", Colors.CYAN))
            result = api_post("/api/shot-plan/fix-v16", {"project": PROJECT})
            if result.get("status") == "success" or result.get("success"):
                print(c("   ✅ Auto-fix applied", Colors.GREEN))
            else:
                print(c(f"   ⚠️ Fix returned: {result.get('message', 'done')}", Colors.YELLOW))
    else:
        print(c("   ✅ All checks passed", Colors.GREEN))

    # Step 3: Generate first frames
    shot_ids = [s.get("shot_id") for s in scene_shots]
    needs_frames = [s.get("shot_id") for s in scene_shots if not s.get("first_frame_url")]

    if needs_frames:
        print(c(f"\n🖼️  GENERATING FIRST FRAMES ({len(needs_frames)} needed)", Colors.YELLOW))
        if not dry_run:
            print(c("   (This may take several minutes...)", Colors.CYAN))
            result = api_post_long("/api/auto/generate-first-frames", {
                "project": PROJECT,
                "shot_ids": needs_frames,
                "dry_run": False
            })
            if result.get("success"):
                print(c(f"   ✅ Generated {result.get('generated', result.get('queued', 0))} frames", Colors.GREEN))
            else:
                print(c(f"   ❌ {result.get('error', 'Unknown error')}", Colors.RED))
        else:
            print(c(f"   [DRY-RUN] Would generate {len(needs_frames)} frames", Colors.CYAN))
    else:
        print(c(f"\n🖼️  FIRST FRAMES: All {len(scene_shots)} complete ✓", Colors.GREEN))

    # Step 4: Generate LTX motion (previs quality)
    needs_videos = [s.get("shot_id") for s in scene_shots if not s.get("video_path")]

    if needs_videos:
        print(c(f"\n🎬 GENERATING LTX MOTION ({len(needs_videos)} needed)", Colors.YELLOW))
        if not dry_run:
            print(c("   (This may take several minutes...)", Colors.CYAN))
            result = api_post_long("/api/auto/render-videos", {
                "project": PROJECT,
                "shot_ids": needs_videos,
                "dry_run": False
            })
            if result.get("success"):
                print(c(f"   ✅ Generated {result.get('generated', result.get('queued', 0))} videos", Colors.GREEN))
            else:
                print(c(f"   ❌ {result.get('error', 'Unknown error')}", Colors.RED))
        else:
            print(c(f"   [DRY-RUN] Would generate {len(needs_videos)} videos", Colors.CYAN))
    else:
        print(c(f"\n🎬 VIDEOS: All {len(scene_shots)} complete ✓", Colors.GREEN))

    # Step 5: Summary and pause
    print(c("\n" + "=" * 60, Colors.HEADER))
    print(c(f"  SCENE {scene_id} PREVIS COMPLETE", Colors.GREEN + Colors.BOLD))
    print(c("=" * 60, Colors.HEADER))
    print(f"\n   Duration: {scene_duration/60:.1f} min")
    print(f"   Shots: {len(scene_shots)}")
    print()
    print(c("📋 REVIEW CHECKLIST:", Colors.CYAN))
    print("   □ Watch scene for blocking issues")
    print("   □ Flag weak angles for reframe")
    print("   □ Flag missing inserts for add-broll")
    print("   □ Flag emotion gaps for prompt edit")
    print()
    print(c("🎬 NEXT STEPS:", Colors.YELLOW))
    print(f"   • Review:  python3 tools/director_cli.py shots {scene_id}")
    print(f"   • Reframe: python3 tools/director_cli.py reframe <shot_id> <angle>")
    print(f"   • Next:    python3 tools/director_cli.py previs <next_scene>")
    print()


def cmd_generate(scope, target=None, auto=False, dry_run=False):
    """Generate frames/videos"""
    if dry_run:
        print(c("\n🔍 DRY-RUN MODE (no actual generation)", Colors.YELLOW))

    if scope == "scene" and target:
        print(c(f"\n🎬 Generating Scene: {target}", Colors.HEADER))

        # Get shots for scene
        bundle = api_get(f"/api/v16/ui/bundle/{PROJECT}")
        shots = [s for s in bundle.get("shot_gallery_rows", []) if s.get("scene_id") == target]
        shot_ids = [s.get("shot_id") for s in shots]

        print(f"   Found {len(shot_ids)} shots")

        # Generate first frames
        print(c("\n1️⃣  Generating First Frames...", Colors.YELLOW))
        if not dry_run:
            print(c("   (This may take several minutes...)", Colors.CYAN))
        result = api_post_long("/api/auto/generate-first-frames", {
            "project": PROJECT,
            "shot_ids": shot_ids,
            "dry_run": dry_run
        })
        if result.get("success"):
            action = "Would queue" if dry_run else "Queued"
            print(c(f"   ✅ {action} {result.get('queued', 0)} frames", Colors.GREEN))
        else:
            print(c(f"   ❌ {result.get('error', 'Unknown error')}", Colors.RED))

        if auto:
            print(c("\n2️⃣  Generating Videos...", Colors.YELLOW))
            if not dry_run:
                print(c("   (This may take several minutes...)", Colors.CYAN))
            result = api_post_long("/api/auto/render-videos", {
                "project": PROJECT,
                "shot_ids": shot_ids,
                "dry_run": dry_run
            })
            if result.get("success"):
                action = "Would queue" if dry_run else "Queued"
                print(c(f"   ✅ {action} {result.get('queued', 0)} videos", Colors.GREEN))
            else:
                print(c(f"   ❌ {result.get('error', 'Unknown error')}", Colors.RED))

    elif scope == "all":
        print(c(f"\n🎬 FULL AUTO GENERATION", Colors.HEADER + Colors.BOLD))
        print("=" * 60)

        if not auto:
            confirm = input("This will generate ALL shots. Continue? [y/N]: ")
            if confirm.lower() != 'y':
                print("Cancelled.")
                return

        # Run full pipeline
        print(c("\n1️⃣  Running Fix-V16...", Colors.YELLOW))
        if not dry_run:
            result = api_post("/api/shot-plan/fix-v16", {"project": PROJECT})
            print(f"   {result.get('message', result.get('error', 'Done'))}")
        else:
            print(c("   [DRY-RUN] Would apply fix-v16", Colors.CYAN))

        print(c("\n2️⃣  Generating First Frames...", Colors.YELLOW))
        if not dry_run:
            print(c("   (This may take several minutes...)", Colors.CYAN))
        result = api_post_long("/api/auto/generate-first-frames", {
            "project": PROJECT,
            "dry_run": dry_run
        })
        action = "Would queue" if dry_run else "Queued"
        print(f"   {action}: {result.get('queued', 0)}")

        if auto:
            print(c("\n3️⃣  Generating Videos...", Colors.YELLOW))
            if not dry_run:
                print(c("   (This may take several minutes...)", Colors.CYAN))
            result = api_post_long("/api/auto/render-videos", {
                "project": PROJECT,
                "dry_run": dry_run
            })
            action = "Would queue" if dry_run else "Queued"
            print(f"   {action}: {result.get('queued', 0)}")

            print(c("\n4️⃣  Running Stitch Dry-Run...", Colors.YELLOW))
            result = api_post("/api/v16/stitch/dry-run", {"project": PROJECT})
            print(f"   Ready: {result.get('ready_count', 0)}/{result.get('total_shots', 0)}")

    print()

def cmd_fix(what):
    """Run fixes"""
    if what == "cast":
        print(c("\n🧹 Cleaning Cast Data...", Colors.HEADER))
        result = api_post("/api/v17/cast/cleanup", {
            "project": PROJECT,
            "normalize_aliases": True,
            "propagate_cast": True
        })
        if result.get("success"):
            print(c(f"✅ Cleaned {result.get('cleaned_shots', 0)} shots", Colors.GREEN))
            if result.get("normalized_characters"):
                print(f"   Normalized: {', '.join(result['normalized_characters'][:5])}")
            if result.get("propagated_cast"):
                for char, actor in list(result["propagated_cast"].items())[:5]:
                    print(f"   {char} → {actor}")
        else:
            print(c(f"❌ {result.get('error', 'Unknown error')}", Colors.RED))

    elif what == "prompts":
        print(c("\n✨ Enhancing Prompts...", Colors.HEADER))
        # Get all shots with BASIC prompts
        bundle = api_get(f"/api/v16/ui/bundle/{PROJECT}")
        shots = bundle.get("shot_gallery_rows", [])
        basic_shots = [s for s in shots if len(s.get("nano_prompt", "")) < 100]
        print(f"   Found {len(basic_shots)} shots with basic prompts")
        # Would enhance each...

    print()

def cmd_add_broll(scene_id, description):
    """Add a B-roll shot"""
    print(c(f"\n➕ Adding B-Roll to {scene_id}", Colors.HEADER))

    result = api_post("/api/v17/shot-plan/add-shot", {
        "project": PROJECT,
        "scene_id": scene_id,
        "type": "insert",
        "nano_prompt": description,
        "ltx_motion_prompt": f"Subtle movement, {description.lower()}, cinematic atmosphere",
        "duration": 6,
        "characters": []
    })

    if result.get("success"):
        print(c(f"✅ Added: {result.get('shot_id')}", Colors.GREEN))
        print(f"   Prompt: {description[:50]}...")
    else:
        print(c(f"❌ {result.get('error', 'Unknown error')}", Colors.RED))
    print()

def cmd_review(shot_id):
    """Review a specific shot"""
    print(c(f"\n🔍 Reviewing: {shot_id}", Colors.HEADER))

    # Get variants (longer timeout for file scanning)
    result = api_get(f"/api/v17/shot/variants/{PROJECT}/{shot_id}", timeout=60)

    if result.get("success"):
        frames = result.get("frames", {})
        videos = result.get("videos", {})

        print(c("\n🖼️  Frame Variants:", Colors.CYAN))
        print(f"   Base: {frames.get('base', 'None')}")
        print(f"   Active: {frames.get('selected', 'base')}")
        for alt in frames.get("alternatives", []):
            print(f"   Alt: {alt}")

        print(c("\n🎬 Video Variants:", Colors.CYAN))
        print(f"   Base: {videos.get('base', 'None')}")
        for name, path in videos.get("variants", {}).items():
            print(f"   {name}: {path}")
    else:
        print(c(f"❌ {result.get('error', 'Unknown error')}", Colors.RED))
    print()

def cmd_reframe(shot_id, angle):
    """Reframe a shot angle"""
    print(c(f"\n🧭 Reframing {shot_id} → {angle}", Colors.HEADER))

    result = api_post("/api/v17/generate-multi-angle", {
        "project": PROJECT,
        "shot_id": shot_id,
        "angle_preset": angle,
        "set_active": True
    })

    if result.get("success"):
        print(c(f"✅ Generated: {result.get('relative_path')}", Colors.GREEN))
    else:
        print(c(f"❌ {result.get('error', 'Unknown error')}", Colors.RED))
    print()

def cmd_help():
    """Show help"""
    print(c("""
🎬 ATLAS V17 DIRECTOR CLI
==========================

SYSTEM:
  status                    System status overview
  scenes                    List all scenes
  shots <scene_id>          Show shots in a scene

PREVIS (Scene-by-Scene Production):
  previs <scene_id>         Scene previs mode (auto-fix → frames → video → pause)
  previs <scene_id> --dry-run   Preview what would generate

GENERATION:
  gen scene <scene_id>      Generate one scene (frames only)
  gen scene <scene_id> --auto   Generate scene (frames + videos)
  gen all                   Generate everything (with confirmation)
  gen all --auto            Generate everything (no confirmation)
  --dry-run                 Test without actually generating

FIXES:
  fix cast                  Clean up casting (removes Maya Chen etc)
  fix prompts               Enhance basic prompts

DIRECTOR TOOLS:
  review <shot_id>          Show all variants for a shot
  reframe <shot_id> <angle> Change shot angle (ots_left, low_angle, etc)
  add-broll <scene> "desc"  Add B-roll/insert shot

MODES:
  Manual: Use 'gen scene X' one at a time, review, fix, continue
  Auto:   Use 'gen all --auto', let it run, review completed work

""", Colors.CYAN))

# ============================================================
# MAIN
# ============================================================

def main():
    global PROJECT

    if len(sys.argv) < 2:
        cmd_status()
        return

    cmd = sys.argv[1].lower()
    args = sys.argv[2:]

    # Check for --project flag
    if "--project" in args:
        idx = args.index("--project")
        if idx + 1 < len(args):
            PROJECT = args[idx + 1]
            args = args[:idx] + args[idx+2:]

    # Route commands
    if cmd == "status":
        cmd_status()
    elif cmd == "scenes":
        cmd_scenes()
    elif cmd == "shots" and args:
        cmd_shots(args[0])
    elif cmd == "previs" and args:
        dry_run = "--dry-run" in args
        scene_id = [a for a in args if not a.startswith("--")][0]
        cmd_previs(scene_id, dry_run)
    elif cmd in ["gen", "generate"]:
        if args:
            auto = "--auto" in args
            dry_run = "--dry-run" in args
            args = [a for a in args if a not in ["--auto", "--dry-run"]]
            if args[0] == "scene" and len(args) > 1:
                cmd_generate("scene", args[1], auto, dry_run)
            elif args[0] == "all":
                cmd_generate("all", None, auto, dry_run)
    elif cmd == "fix" and args:
        cmd_fix(args[0])
    elif cmd == "review" and args:
        cmd_review(args[0])
    elif cmd == "reframe" and len(args) >= 2:
        cmd_reframe(args[0], args[1])
    elif cmd in ["add-broll", "broll"] and len(args) >= 2:
        cmd_add_broll(args[0], " ".join(args[1:]))
    elif cmd == "help":
        cmd_help()
    else:
        cmd_help()

if __name__ == "__main__":
    main()
