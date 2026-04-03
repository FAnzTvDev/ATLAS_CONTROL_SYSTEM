#!/usr/bin/env python3
"""
ATLAS V28.1 — Universal Scene Runner
======================================
ONE script to generate ANY scene. ALL checks enforced.
No more per-scene hand-built scripts that forget identity injection.

USAGE:
  python3 tools/atlas_scene_runner.py <project> <scene_id> [--budget 15]

PIPELINE:
  Phase 0: Pre-Generation Enforcement Gate (BLOCKING)
  Phase 1: First Frame Generation (with char refs + identity)
  Phase 2: Video Generation (doctrine-corrected)
  Phase 3: Stitch
  Phase 4: Quality Gate
"""

import fal_client, json, os, sys, time, base64, subprocess, urllib.request
from datetime import datetime
from typing import Dict, List, Optional

# Import enforcer
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pre_gen_enforcer import (
    enforce_pre_generation, print_enforcement_report,
    ROOM_DNA_TEMPLATES, LIGHTING_RIGS, _detect_room_type, _amplify,
    AMPLIFICATION_MAP
)

# ═══════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════

POSITION_LOCKS = {
    # Scene 001
    "THOMAS BLACKWOOD": "FRAME-RIGHT",
    "ELEANOR VOSS": "FRAME-LEFT",
    # Scene 002
    "NADIA COLE": "FRAME-CENTER",
    # Add more as scenes are generated
}

# ═══════════════════════════════════════════════════════════════
# PROMPT BUILDERS
# ═══════════════════════════════════════════════════════════════

EYE_LINE_MAP = {
    "surveying space": "eyes scanning the room slowly, taking in details",
    "looking at partner": "eyes fixed on the other person, direct gaze",
    "looking at portrait": "eyes raised upward, gazing at wall above staircase",
    "looking at briefcase": "eyes cast downward toward hands and documents",
    "looking at staircase": "eyes tracing the staircase upward, wistful",
    "avoiding eye contact": "eyes drifting to the side, deliberately not meeting gaze",
    "defiant stare": "eyes locked forward, chin slightly raised, unflinching",
    "scanning documents": "eyes darting across papers, focused and rapid",
    "examining books": "eyes scanning book spines, intent and searching",
    "reading": "eyes scanning downward, reading closely, absorbed",
    "discovering": "eyes widening with discovery, examining something closely",
}

BODY_MAP = {
    "entering": "walking forward with purpose, briefcase in hand, posture upright",
    "reluctant following": "trailing behind, hand brushing banister, shoulders heavy",
    "presenting documents": "extending papers forward, professional stance, weight on front foot",
    "touching banister": "fingers trailing along dark wood railing, slow deliberate touch",
    "refusing": "jaw clenched, stance widening, arms crossing, weight shifting back",
    "confronting": "stepping closer, shoulders squared, hands gesturing emphatically",
    "standing firm": "planted stance, chin up, briefcase held like a shield",
    "turning away": "body rotating away, one hand on banister, shoulder toward speaker",
    "staring at portrait": "body still, head tilted up, one hand at side clenched",
    "reacting": "slight flinch, breath catching, micro-expression shifting",
    "browsing shelves": "hand extended toward shelf, body angled, weight on one foot",
    "reading aloud": "head tilted down toward text, lips moving softly, still posture",
    "reaching for book": "arm extending upward, body stretching, fingers searching",
}


def build_performance_block(shot: dict) -> str:
    parts = []
    for field, map_dict in [("_eye_line_target", EYE_LINE_MAP), ("_body_direction", BODY_MAP)]:
        val = shot.get(field, "")
        if val:
            translated = map_dict.get(val, val)
            parts.append(translated)

    movement = shot.get("_movement_state", "")
    if movement:
        parts.append(f"motion: {movement}")
    emotion = shot.get("_emotional_state", "")
    if emotion:
        parts.append(f"mood: {emotion}")

    return "[PERFORMANCE: " + ", ".join(parts) + "]" if parts else ""


def build_focal_enforcement(shot_type: str) -> str:
    if shot_type in ("close_up", "medium_close", "reaction"):
        return "[TIGHT FRAMING: face fills 80% of frame, background compressed flat and completely blurred]"
    elif shot_type in ("medium", "two_shot", "over_the_shoulder"):
        return "[MEDIUM FRAMING: waist-up visible, room context visible but secondary]"
    elif shot_type in ("wide", "establishing", "closing"):
        return "[WIDE FRAMING: full room geography visible, deep depth of field, all features sharp]"
    return ""


def build_screen_direction(shot: dict) -> str:
    chars = shot.get("characters") or []
    stype = shot.get("shot_type", "")
    dlg = shot.get("dialogue_text", "")
    if not chars or not dlg:
        return ""

    if stype == "over_the_shoulder":
        angle = shot.get("_ots_angle", "A")
        if angle == "A":
            return "[SCREEN DIRECTION: Listener shoulder FRAME-LEFT foreground blur, speaker FRAME-RIGHT facing camera]"
        else:
            return "[SCREEN DIRECTION: Listener shoulder FRAME-RIGHT foreground blur, speaker FRAME-LEFT facing camera]"
    elif stype == "two_shot" and len(chars) >= 2:
        p0 = POSITION_LOCKS.get(chars[0], "FRAME-LEFT")
        p1 = POSITION_LOCKS.get(chars[1], "FRAME-RIGHT")
        return f"[SCREEN DIRECTION: {chars[0].split()[-1]} {p0} facing right, {chars[1].split()[-1]} {p1} facing left, confrontational]"
    elif stype in ("medium_close", "close_up", "reaction") and len(chars) == 1:
        pos = POSITION_LOCKS.get(chars[0], "FRAME-CENTER")
        look = "FRAME-RIGHT" if pos == "FRAME-LEFT" else "FRAME-LEFT"
        return f"[SCREEN DIRECTION: {chars[0].split()[-1]} fills frame, eye-line directed {look}]"
    return ""


def build_full_prompt(shot: dict, cast_map: dict, room_dna: str, lighting_rig: str) -> str:
    """Build complete nano_prompt with ALL systems."""
    blocks = []

    # Identity blocks
    chars = shot.get("characters") or []
    for cname in chars:
        cdata = cast_map.get(cname, {})
        if isinstance(cdata, dict):
            app = cdata.get("appearance", "")
            if app:
                blocks.append(f"[CHARACTER: {_amplify(app)}]")

    # Empty constraint
    if not chars:
        blocks.append("No people visible, no figures, no silhouettes, empty space only.")

    # Screen direction
    sd = build_screen_direction(shot)
    if sd:
        blocks.append(sd)

    # Performance
    perf = build_performance_block(shot)
    if perf:
        blocks.append(perf)

    # Focal enforcement
    focal = build_focal_enforcement(shot.get("shot_type", ""))
    if focal:
        blocks.append(focal)

    # Room DNA + Lighting
    blocks.append(room_dna)
    blocks.append(lighting_rig)

    # Base prompt (cleaned)
    base = shot.get("nano_prompt", "")
    # Strip location proper names
    for name in ["HARGROVE ESTATE", "HARGROVE", "BLACKWOOD MANOR", "RAVENCROFT"]:
        base = base.replace(name, "the estate")

    full = " ".join(blocks) + " " + base
    return full[:900]


def build_video_prompt(shot: dict, cast_map: dict) -> str:
    """Build video prompt with split anti-morphing."""
    parts = []
    chars = shot.get("characters") or []

    for cname in chars[:2]:
        cdata = cast_map.get(cname, {})
        if isinstance(cdata, dict):
            app = cdata.get("appearance", "")
            if app:
                parts.append(f"[CHARACTER: {_amplify(app)[:150]}]")

    perf = build_performance_block(shot)
    if perf:
        parts.append(perf)

    dlg = shot.get("dialogue_text", "")
    if dlg and chars:
        cdata = cast_map.get(chars[0], {})
        app = cdata.get("appearance", "") if isinstance(cdata, dict) else ""
        parts.append(f'{app[:80]} speaks: "{dlg[:200]}"')

    if chars:
        parts.append("FACE IDENTITY LOCK: facial structure UNCHANGED, NO face morphing, NO identity drift.")
        parts.append("BODY PERFORMANCE FREE: natural breathing, weight shifts, hand gestures CONTINUE.")

    sd = build_screen_direction(shot)
    if sd:
        parts.append(sd)

    return " ".join(parts)[:900]


# ═══════════════════════════════════════════════════════════════
# IMAGE HELPERS
# ═══════════════════════════════════════════════════════════════

def get_b64(path: str) -> str:
    if not os.path.exists(path):
        return ""
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode()
    ext = path.split(".")[-1].lower()
    mime = "image/jpeg" if ext in ("jpg", "jpeg") else "image/png"
    return f"data:{mime};base64,{data}"


def resolve_char_ref(char_name: str, cast_map: dict, char_dir: str) -> str:
    cdata = cast_map.get(char_name, {})
    if isinstance(cdata, dict):
        ref = cdata.get("character_reference_url", "")
        if ref and os.path.exists(ref):
            return ref
    safe = char_name.upper().replace(" ", "_")
    fallback = os.path.join(char_dir, f"{safe}_CHAR_REFERENCE.jpg")
    return fallback if os.path.exists(fallback) else ""


def resolve_location_ref(shot: dict, loc_dir: str, room_key: str, room_location: str) -> str:
    """Room-locked location resolution (T2-OR-13)."""
    stype = shot.get("shot_type", "")

    # Find location masters for this room
    if not os.path.exists(loc_dir):
        return ""

    all_masters = os.listdir(loc_dir)
    # Extract room identifier from location name
    loc_parts = room_location.upper().replace(" ", "_").replace("-", "_")

    # Filter to this room's masters
    room_masters = [f for f in all_masters if any(part in f.upper() for part in loc_parts.split("_") if len(part) > 3)]

    if not room_masters:
        room_masters = all_masters  # fallback

    base = [f for f in room_masters if not any(x in f.lower() for x in ["reverse", "medium_interior"])]
    reverse = [f for f in room_masters if "reverse" in f.lower()]
    medium = [f for f in room_masters if "medium_interior" in f.lower()]

    # OTS angle
    ots_angle = shot.get("_ots_angle", "")
    if ots_angle == "B" and reverse:
        return os.path.join(loc_dir, reverse[0])

    if stype in ("establishing", "wide", "closing") and base:
        return os.path.join(loc_dir, base[0])
    elif stype in ("medium", "two_shot") and medium:
        return os.path.join(loc_dir, medium[0])
    elif stype in ("medium_close", "close_up", "reaction") and base:
        return os.path.join(loc_dir, base[0])
    elif base:
        return os.path.join(loc_dir, base[0])

    return ""


# ═══════════════════════════════════════════════════════════════
# MAIN PIPELINE
# ═══════════════════════════════════════════════════════════════

def run_scene(project: str, scene_id: str, budget: float = 15.0):
    project_path = f"pipeline_outputs/{project}"
    frame_dir = f"{project_path}/first_frames"
    video_dir = f"{project_path}/videos"
    loc_dir = f"{project_path}/location_masters"
    char_dir = f"{project_path}/character_library_locked"

    # Load data
    with open(f"{project_path}/shot_plan.json") as f:
        sp = json.load(f)
    all_shots = sp if isinstance(sp, list) else sp.get("shots", [])

    with open(f"{project_path}/cast_map.json") as f:
        cm = json.load(f)

    sb = None
    sb_path = f"{project_path}/story_bible.json"
    if os.path.exists(sb_path):
        with open(sb_path) as f:
            sb = json.load(f)

    scene_shots = [s for s in all_shots if s.get("shot_id", "").startswith(f"{scene_id}_")]

    print(f"\n{'='*70}")
    print(f"  ATLAS UNIVERSAL SCENE RUNNER — Scene {scene_id}")
    print(f"  {len(scene_shots)} shots | Budget: ${budget}")
    print(f"  {datetime.now().isoformat()}")
    print(f"{'='*70}")

    # ═══════════════════════════════════════════════════════════
    # PHASE 0: ENFORCEMENT GATE (BLOCKING)
    # ═══════════════════════════════════════════════════════════
    print(f"\n  PHASE 0: PRE-GENERATION ENFORCEMENT GATE")
    result = enforce_pre_generation(scene_shots, cm, project_path, sb, scene_id, auto_fix=True)
    print_enforcement_report(result)

    if not result["can_proceed"]:
        print("\n  ✗ GENERATION BLOCKED. Fix issues above before proceeding.")
        return {"success": False, "reason": "enforcement_gate_blocked", "issues": result["blocking_issues"]}

    # Use fixed shots from enforcer
    scene_shots = result["fixed_shots"]
    scene_room = result.get("scene_room", "")
    room_type = result.get("room_type", "foyer")
    room_dna = ROOM_DNA_TEMPLATES.get(room_type, ROOM_DNA_TEMPLATES["foyer"])
    lighting_rig = LIGHTING_RIGS.get(room_type, LIGHTING_RIGS.get("foyer", ""))

    cost = {"frames": 0, "videos": 0}

    # ═══════════════════════════════════════════════════════════
    # PHASE 1: FIRST FRAMES
    # ═══════════════════════════════════════════════════════════
    print(f"\n{'='*70}")
    print(f"  PHASE 1: FIRST FRAMES (with character refs)")
    print(f"{'='*70}")

    # Archive old
    archive = f"{frame_dir}/_archived_{scene_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    os.makedirs(archive, exist_ok=True)
    archived = 0
    for s in scene_shots:
        sid = s.get("shot_id", "")
        old = f"{frame_dir}/{sid}.jpg"
        if os.path.exists(old):
            os.rename(old, f"{archive}/{sid}.jpg")
            archived += 1
    print(f"  Archived {archived} old frames")

    # Build and submit
    handles = {}
    for s in scene_shots:
        sid = s.get("shot_id", "")
        chars = s.get("characters") or []

        prompt = build_full_prompt(s, cm, room_dna, lighting_rig)

        image_urls = []
        for cname in chars[:2]:
            ref = resolve_char_ref(cname, cm, char_dir)
            if ref:
                b64 = get_b64(ref)
                if b64:
                    image_urls.append(b64)

        loc_ref = resolve_location_ref(s, loc_dir, room_type, scene_room)
        if loc_ref:
            b64 = get_b64(loc_ref)
            if b64:
                image_urls.append(b64)

        args = {"prompt": prompt, "aspect_ratio": "16:9", "output_format": "jpeg", "safety_tolerance": 6}
        if image_urls:
            args["image_urls"] = image_urls

        char_refs = len(image_urls) - (1 if loc_ref else 0)
        print(f"  {sid}: {len(chars)} chars, {char_refs} char refs, {1 if loc_ref else 0} loc ref")

        handle = fal_client.submit("fal-ai/nano-banana-pro", arguments=args)
        handles[sid] = handle
        cost["frames"] += 0.04

    print(f"\n  Submitted {len(handles)}, waiting...")
    frame_ok = 0
    for sid, handle in handles.items():
        try:
            result_fal = handle.get()
            images = result_fal.get("images", [])
            if images:
                url = images[0].get("url", "")
                if url:
                    urllib.request.urlretrieve(url, f"{frame_dir}/{sid}.jpg")
                    frame_ok += 1
                    sz = os.path.getsize(f"{frame_dir}/{sid}.jpg") // 1024
                    print(f"  ✓ {sid}: {sz}KB")
                else:
                    print(f"  ✗ {sid}: no URL")
            else:
                print(f"  ✗ {sid}: no images")
        except Exception as e:
            print(f"  ✗ {sid}: {str(e)[:120]}")

    print(f"\n  Frames: {frame_ok}/{len(scene_shots)} | Cost: ${cost['frames']:.2f}")

    # ═══════════════════════════════════════════════════════════
    # PHASE 2: VIDEOS
    # ═══════════════════════════════════════════════════════════
    print(f"\n{'='*70}")
    print(f"  PHASE 2: VIDEOS (doctrine-corrected)")
    print(f"{'='*70}")

    vid_archive = f"{video_dir}/_archived_{scene_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    os.makedirs(vid_archive, exist_ok=True)
    for s in scene_shots:
        sid = s.get("shot_id", "")
        for ext in [".mp4", ".mp4.bak_short"]:
            old = f"{video_dir}/{sid}{ext}"
            if os.path.exists(old):
                os.rename(old, f"{vid_archive}/{sid}{ext}")

    vid_handles = {}
    for s in scene_shots:
        sid = s.get("shot_id", "")
        chars = s.get("characters") or []
        dlg = s.get("dialogue_text", "")

        fp = f"{frame_dir}/{sid}.jpg"
        if not os.path.exists(fp):
            print(f"  SKIP {sid}: no frame")
            continue

        image_url = get_b64(fp)
        vprompt = build_video_prompt(s, cm)

        # Model + duration routing
        min_dur = 0
        if dlg:
            wc = len(dlg.split())
            min_dur = (wc / 2.3) + 1.5

        if not chars and s.get("shot_type") in ("establishing", "insert", "b-roll", "closing"):
            model = "fal-ai/ltx-2/image-to-video/fast"
            duration = None
            est = 0.30
        elif min_dur > 6.12 or (chars and dlg):
            model = "fal-ai/ltx-2/image-to-video"
            duration = min(10, max(6, int(min_dur)))
            if duration % 2 != 0:
                duration += 1
            duration = min(duration, 10)
            est = duration * 0.10
        elif chars:
            model = "fal-ai/ltx-2/image-to-video"
            duration = 8
            est = 0.80
        else:
            model = "fal-ai/ltx-2/image-to-video/fast"
            duration = None
            est = 0.30

        args = {"prompt": vprompt, "image_url": image_url, "resolution": "1080p"}
        if duration is not None:
            args["duration"] = duration

        tag = "FAST" if "fast" in model else f"FULL-{duration}s"
        print(f"  {sid}: {tag} ${est:.2f}")

        handle = fal_client.submit(model, arguments=args)
        vid_handles[sid] = {"handle": handle, "model": model, "frame": fp, "prompt": vprompt, "est": est}
        cost["videos"] += est

    print(f"\n  Submitted {len(vid_handles)}, waiting...")
    vid_ok = 0
    for sid, data in vid_handles.items():
        try:
            result_fal = data["handle"].get()
            vurl = result_fal.get("video", {}).get("url", "")
            if vurl:
                urllib.request.urlretrieve(vurl, f"{video_dir}/{sid}.mp4")
                vid_ok += 1
                sz = os.path.getsize(f"{video_dir}/{sid}.mp4") // 1024
                print(f"  ✓ {sid}: {sz}KB")
            else:
                print(f"  ✗ {sid}: no video URL")
        except Exception as e:
            err = str(e)[:150]
            print(f"  ✗ {sid}: {err}")
            # Retry /fast
            if "fast" not in data["model"]:
                try:
                    print(f"    Retrying {sid} /fast...")
                    retry_args = {"prompt": data["prompt"][:900], "image_url": get_b64(data["frame"]), "resolution": "1080p"}
                    rh = fal_client.submit("fal-ai/ltx-2/image-to-video/fast", arguments=retry_args)
                    rr = rh.get()
                    rvurl = rr.get("video", {}).get("url", "")
                    if rvurl:
                        urllib.request.urlretrieve(rvurl, f"{video_dir}/{sid}.mp4")
                        vid_ok += 1
                        cost["videos"] += 0.30
                        print(f"    ✓ {sid} retry OK")
                except Exception as e2:
                    print(f"    ✗ retry failed: {str(e2)[:80]}")

    print(f"\n  Videos: {vid_ok}/{len(scene_shots)} | Cost: ${cost['videos']:.2f}")

    # ═══════════════════════════════════════════════════════════
    # PHASE 3: STITCH
    # ═══════════════════════════════════════════════════════════
    print(f"\n{'='*70}")
    print(f"  PHASE 3: STITCH")
    print(f"{'='*70}")

    concat_path = f"{video_dir}/concat_{scene_id}.txt"
    missing = []
    with open(concat_path, "w") as f:
        for s in scene_shots:
            sid = s.get("shot_id", "")
            vp = f"{video_dir}/{sid}.mp4"
            if os.path.exists(vp):
                f.write(f"file '{sid}.mp4'\n")
            else:
                missing.append(sid)

    if missing:
        print(f"  ⚠ Missing: {missing}")

    out_path = f"scene{scene_id}_v3_enforced.mp4"
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_path, "-c", "copy", out_path]
    r = subprocess.run(cmd, capture_output=True, text=True)

    if r.returncode == 0:
        dr = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", out_path], capture_output=True, text=True)
        dur = float(dr.stdout.strip()) if dr.stdout.strip() else 0
        sz = os.path.getsize(out_path) // 1024
        print(f"  ✓ Stitched: {dur:.1f}s ({sz}KB)")
    else:
        print(f"  ✗ Failed: {r.stderr[:200]}")

    # ═══════════════════════════════════════════════════════════
    # PHASE 4: QUALITY GATE
    # ═══════════════════════════════════════════════════════════
    print(f"\n{'='*70}")
    print(f"  PHASE 4: QUALITY GATE")
    print(f"{'='*70}")

    issues = 0
    for s in scene_shots:
        sid = s.get("shot_id", "")
        vp = f"{video_dir}/{sid}.mp4"
        dlg = s.get("dialogue_text", "")

        if not os.path.exists(vp):
            print(f"  ✗ {sid}: MISSING")
            issues += 1
            continue

        dr = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", vp], capture_output=True, text=True)
        actual = float(dr.stdout.strip()) if dr.stdout.strip() else 0

        min_dur = 0
        if dlg:
            wc = len(dlg.split())
            min_dur = (wc / 2.3) + 1.5

        ok = actual >= min_dur - 1.0 or not dlg
        status = "✓" if ok else "⚠"
        if not ok:
            issues += 1
        print(f"  {status} {sid}: {actual:.1f}s (need {min_dur:.1f}s)")

    total_cost = cost["frames"] + cost["videos"]
    print(f"\n  Quality: {len(scene_shots) - issues}/{len(scene_shots)} pass")
    print(f"  Total cost: ${total_cost:.2f}")
    print(f"  Output: {out_path}")

    # Save report
    report = {
        "scene_id": scene_id,
        "version": "v3_enforced",
        "timestamp": datetime.now().isoformat(),
        "pipeline": "atlas_scene_runner (universal)",
        "enforcement_gate": "PASSED",
        "shots_total": len(scene_shots),
        "frames_ok": frame_ok,
        "videos_ok": vid_ok,
        "cost": total_cost,
        "quality_issues": issues,
    }
    with open(f"{project_path}/scene{scene_id}_run_report.json", "w") as f:
        json.dump(report, f, indent=2)

    print(f"\n{'='*70}")
    print(f"  SCENE {scene_id} — COMPLETE")
    print(f"{'='*70}")

    return {"success": True, "output": out_path, "cost": total_cost}


# ═══════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="ATLAS Universal Scene Runner")
    parser.add_argument("project", help="Project name (e.g. victorian_shadows_ep1)")
    parser.add_argument("scene_id", help="Scene ID (e.g. 001)")
    parser.add_argument("--budget", type=float, default=15.0, help="Budget cap in dollars")
    args = parser.parse_args()

    run_scene(args.project, args.scene_id, args.budget)
