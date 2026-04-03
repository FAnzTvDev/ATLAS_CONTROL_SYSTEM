#!/usr/bin/env python3
"""
ATLAS API BRIDGE — Connects Universal Runner to the UI
========================================================
Adds endpoints to the orchestrator that call the universal runner.
This bridges the gap between:
  - The UI (calls HTTP endpoints on port 9999)
  - The universal runner (Python script with 17 harmony systems)

Endpoints:
  POST /api/v29/render              — Full scene render (universal runner)
  POST /api/v29/render/parallel     — Multiple scenes in parallel
  GET  /api/v29/render/status       — Check running render status
  GET  /api/v29/render/gate         — Run generation gate without rendering
  GET  /api/v29/harmony             — Show harmony system status

Integration:
  1. Import this file in orchestrator_server.py:
     from atlas_api_bridge import register_v29_routes
     register_v29_routes(app, BASE_DIR)

  2. Or run standalone on port 9998:
     python3 atlas_api_bridge.py

Usage from UI or curl:
  curl -X POST http://localhost:9998/api/v29/render \
    -H "Content-Type: application/json" \
    -d '{"project": "victorian_shadows_ep1", "scene_id": "002", "mode": "lite"}'
"""

import os, sys, json, time, threading
from pathlib import Path
from fastapi import FastAPI, Body
from fastapi.middleware.cors import CORSMiddleware

# Add project root to path
BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "tools"))

app = FastAPI(title="ATLAS V29 Universal Runner API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ═══ Active renders tracking ═══
_active_renders = {}  # {render_id: {status, scene_id, started, log_path, ...}}

# ═══════════════════════════════════════════════════════════════
# POST /api/v29/render — Full scene render via universal runner
# ═══════════════════════════════════════════════════════════════
@app.post("/api/v29/render")
async def v29_render(request: dict = Body(...)):
    """
    Render a scene through the universal runner with all 17 harmony systems.

    Body:
    {
        "project": "victorian_shadows_ep1",
        "scene_id": "002",
        "mode": "lite",           // "lite" or "full"
        "async": true             // Run in background (default true)
    }

    Returns:
    {
        "success": true,
        "render_id": "002_1710799200",
        "status": "running",      // or "completed" if sync
        "log_path": "/tmp/render_002.log"
    }
    """
    project = request.get("project", "")
    scene_id = request.get("scene_id", "")
    mode = request.get("mode", "lite")
    run_async = request.get("async", True)

    if not project or not scene_id:
        return {"success": False, "error": "project and scene_id required"}

    pdir = Path("pipeline_outputs") / project
    if not pdir.exists():
        return {"success": False, "error": f"Project {project} not found"}

    render_id = f"{scene_id}_{int(time.time())}"
    log_path = f"/tmp/render_{scene_id}_{int(time.time())}.log"

    if run_async:
        # Run in background thread
        def _run():
            _active_renders[render_id] = {
                "status": "running", "scene_id": scene_id,
                "project": project, "mode": mode,
                "started": time.time(), "log_path": log_path
            }
            try:
                import subprocess
                cmd = [
                    sys.executable, "-u", str(BASE_DIR / "atlas_universal_runner.py"),
                    project, scene_id, "--mode", mode
                ]
                with open(log_path, "w") as logf:
                    proc = subprocess.run(cmd, stdout=logf, stderr=subprocess.STDOUT,
                                        cwd=str(BASE_DIR))
                _active_renders[render_id]["status"] = "completed" if proc.returncode == 0 else "failed"
                _active_renders[render_id]["returncode"] = proc.returncode
                _active_renders[render_id]["finished"] = time.time()
            except Exception as e:
                _active_renders[render_id]["status"] = "error"
                _active_renders[render_id]["error"] = str(e)

        t = threading.Thread(target=_run, daemon=True)
        t.start()

        return {
            "success": True,
            "render_id": render_id,
            "status": "running",
            "log_path": log_path,
            "message": f"Scene {scene_id} rendering in background ({mode} mode)"
        }
    else:
        # Run synchronously
        from atlas_universal_runner import run_scene
        run_scene(project, scene_id, mode)
        return {"success": True, "render_id": render_id, "status": "completed"}


# ═══════════════════════════════════════════════════════════════
# POST /api/v29/render/parallel — Multiple scenes
# ═══════════════════════════════════════════════════════════════
@app.post("/api/v29/render/parallel")
async def v29_render_parallel(request: dict = Body(...)):
    """
    Render multiple scenes in parallel.

    Body:
    {
        "project": "victorian_shadows_ep1",
        "scene_ids": ["001", "002"],
        "mode": "lite"
    }
    """
    project = request.get("project", "")
    scene_ids = request.get("scene_ids", [])
    mode = request.get("mode", "lite")

    if not project or not scene_ids:
        return {"success": False, "error": "project and scene_ids required"}

    render_id = f"parallel_{int(time.time())}"
    log_path = f"/tmp/render_parallel_{int(time.time())}.log"

    def _run():
        _active_renders[render_id] = {
            "status": "running", "scene_ids": scene_ids,
            "project": project, "mode": mode,
            "started": time.time(), "log_path": log_path
        }
        try:
            import subprocess
            cmd = [
                sys.executable, "-u", str(BASE_DIR / "atlas_universal_runner.py"),
                project, *scene_ids, "--mode", mode
            ]
            with open(log_path, "w") as logf:
                proc = subprocess.run(cmd, stdout=logf, stderr=subprocess.STDOUT,
                                    cwd=str(BASE_DIR))
            _active_renders[render_id]["status"] = "completed" if proc.returncode == 0 else "failed"
            _active_renders[render_id]["finished"] = time.time()
        except Exception as e:
            _active_renders[render_id]["status"] = "error"
            _active_renders[render_id]["error"] = str(e)

    t = threading.Thread(target=_run, daemon=True)
    t.start()

    return {
        "success": True,
        "render_id": render_id,
        "status": "running",
        "scene_ids": scene_ids,
        "log_path": log_path
    }


# ═══════════════════════════════════════════════════════════════
# GET /api/v29/render/status — Check render status
# ═══════════════════════════════════════════════════════════════
@app.get("/api/v29/render/status")
async def v29_render_status(render_id: str = None):
    """Get status of a render, or all active renders."""
    if render_id:
        r = _active_renders.get(render_id)
        if not r:
            return {"success": False, "error": "Render not found"}
        # Read last few lines of log
        log_tail = ""
        if r.get("log_path") and os.path.exists(r["log_path"]):
            with open(r["log_path"]) as f:
                lines = f.readlines()
                log_tail = "".join(lines[-10:])
        return {"success": True, **r, "log_tail": log_tail}
    else:
        return {"success": True, "renders": _active_renders}


# ═══════════════════════════════════════════════════════════════
# GET /api/v29/render/gate — Run generation gate (dry run)
# ═══════════════════════════════════════════════════════════════
@app.get("/api/v29/render/gate/{project}/{scene_id}")
async def v29_gate_check(project: str, scene_id: str):
    """Run generation gate WITHOUT rendering. Shows what would pass/fail."""
    try:
        from generation_gate import run_gate
        from atlas_universal_runner import load_project, get_sb_scene, auto_consolidate
        from shot_truth_contract import compile_scene_truth
        from beat_enrichment import enrich_project

        pdir = Path("pipeline_outputs") / project
        shots, sb, cast, locs = load_project(project)
        sb_scene = get_sb_scene(sb, scene_id)

        if not sb_scene:
            return {"success": False, "error": f"Scene {scene_id} not found"}

        # Ensure enrichment
        cp = pdir / "scene_contracts" / f"{scene_id}_contract.json"
        if not cp.exists():
            enrich_project(str(pdir), [scene_id])
            compile_scene_truth(str(pdir), scene_id)

        contract = json.load(open(cp)) if cp.exists() else {}

        # Reload and consolidate
        shots = json.load(open(pdir / "shot_plan.json"))
        if not isinstance(shots, list): shots = shots.get("shots", [])
        mshots = auto_consolidate(sb_scene, contract, shots, scene_id)

        result = run_gate(str(pdir), scene_id, mshots, cast, contract, locs,
                         sb_scene.get("location", ""))

        return {
            "success": True,
            "can_generate": result["can_generate"],
            "blocking": result["blocking"],
            "warnings": result["warnings"],
            "passed_count": len(result["passed"]),
            "total_checks": result["total_checks"],
            "consolidated_shots": len(mshots),
            "shot_ids": [s["shot_id"] for s in mshots],
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════
# GET /api/v29/harmony — Harmony system status
# ═══════════════════════════════════════════════════════════════
@app.get("/api/v29/harmony")
async def v29_harmony_status():
    """Show status of all 17 harmony systems."""
    systems = {
        "beat_enrichment": {"file": "tools/beat_enrichment.py", "status": "wired", "lines": 390},
        "truth_contracts": {"file": "tools/shot_truth_contract.py", "status": "wired", "lines": 822},
        "scene_visual_dna": {"file": "tools/scene_visual_dna.py", "status": "wired", "lines": 402},
        "identity_injection": {"file": "tools/prompt_identity_injector.py", "status": "wired", "lines": 320},
        "truth_translator": {"file": "tools/truth_prompt_translator.py", "status": "wired", "lines": 368},
        "focal_enforcement": {"file": "tools/scene_visual_dna.py", "status": "wired"},
        "ots_enforcer": {"file": "tools/ots_enforcer.py", "status": "wired", "lines": 1439},
        "kling_prompt_compiler": {"file": "tools/kling_prompt_compiler.py", "status": "wired", "lines": 711},
        "generation_gate": {"file": "tools/generation_gate.py", "status": "wired", "checks": 17},
        "vision_judge": {"file": "tools/vision_judge.py", "status": "wired"},
        "model_selection": {"status": "wired", "note": "/edit for chars, /base for empty"},
        "kling_identity_elements": {"status": "wired", "note": "frontal_image_url per character"},
        "end_frame_chaining": {"status": "wired", "note": "last frame → next start"},
        "location_ref_feeding": {"status": "wired", "note": "base master per scene"},
        "dialogue_integrity": {"status": "wired", "note": "from script only"},
        "prop_chain": {"status": "wired", "note": "first frame = before state"},
        "solo_scene_rules": {"status": "wired", "note": "no phantoms, no OTS"},
    }

    # Check which files actually exist
    for name, info in systems.items():
        if "file" in info:
            path = BASE_DIR / info["file"]
            info["exists"] = path.exists()

    return {
        "success": True,
        "total": len(systems),
        "wired": sum(1 for s in systems.values() if s.get("status") == "wired"),
        "systems": systems,
        "runner": "atlas_universal_runner.py",
        "gate": "tools/generation_gate.py",
        "models": {
            "first_frame_with_refs": "fal-ai/nano-banana-pro/edit",
            "first_frame_no_refs": "fal-ai/nano-banana-pro",
            "character_video": "fal-ai/kling-video/v3/pro/image-to-video",
            "broll_video": "fal-ai/ltx-2/image-to-video/fast",
        }
    }


# ═══════════════════════════════════════════════════════════════
# GET /api/v29/projects — List available projects
# ═══════════════════════════════════════════════════════════════
@app.get("/api/v29/projects")
async def v29_list_projects():
    """List all projects with their scenes."""
    pipeline = BASE_DIR / "pipeline_outputs"
    projects = []
    for d in sorted(pipeline.iterdir()):
        if d.is_dir() and (d / "shot_plan.json").exists():
            sb_path = d / "story_bible.json"
            scenes = []
            if sb_path.exists():
                sb = json.load(open(sb_path))
                for s in sb.get("scenes", []):
                    scenes.append({
                        "scene_id": s.get("scene_id"),
                        "location": s.get("location"),
                        "beats": len(s.get("beats", [])),
                    })
            projects.append({
                "name": d.name,
                "scenes": scenes,
                "has_cast": (d / "cast_map.json").exists(),
                "has_locations": (d / "location_masters").exists(),
            })
    return {"success": True, "projects": projects}


# ═══════════════════════════════════════════════════════════════
# Standalone server
# ═══════════════════════════════════════════════════════════════
@app.post("/api/v29/render/shot")
async def v29_render_shot(request: dict = Body(...)):
    """
    Render a SINGLE SHOT — no chain dependency, no multi_prompt group.
    UI calls this per shot card. Runs gen_frame + gen_video standalone.

    Body:
    {
        "project": "victorian_shadows_ep1",
        "scene_id": "002",
        "shot_index": 2,        // 0-based index in auto_consolidate output
        "mode": "lite"
    }
    """
    project = request.get("project", "")
    scene_id = request.get("scene_id", "")
    shot_index = request.get("shot_index", 0)
    mode = request.get("mode", "lite")

    if not project or not scene_id:
        return {"success": False, "error": "project and scene_id required"}

    pdir = Path("pipeline_outputs") / project
    if not pdir.exists():
        return {"success": False, "error": f"Project {project} not found"}

    render_id = f"shot_{scene_id}_{shot_index}_{int(time.time())}"
    log_path = f"/tmp/shot_{scene_id}_{shot_index}_{int(time.time())}.log"

    def _run():
        _active_renders[render_id] = {
            "status": "running", "scene_id": scene_id, "shot_index": shot_index,
            "project": project, "mode": mode,
            "started": time.time(), "log_path": log_path, "type": "single_shot"
        }
        try:
            import subprocess
            cmd = [
                sys.executable, "-u", str(BASE_DIR / "_run_single_shot.py"),
                project, scene_id, str(shot_index), mode
            ]
            with open(log_path, "w") as logf:
                proc = subprocess.run(cmd, stdout=logf, stderr=subprocess.STDOUT,
                                     cwd=str(BASE_DIR))

            # Read result if written
            result_path = f"/tmp/shot_result_{scene_id}_{shot_index}.json"
            result = {}
            if os.path.exists(result_path):
                with open(result_path) as f:
                    result = json.load(f)

            _active_renders[render_id]["status"] = "completed" if proc.returncode == 0 else "failed"
            _active_renders[render_id]["returncode"] = proc.returncode
            _active_renders[render_id]["finished"] = time.time()
            _active_renders[render_id]["result"] = result
        except Exception as e:
            _active_renders[render_id]["status"] = "error"
            _active_renders[render_id]["error"] = str(e)

    t = threading.Thread(target=_run, daemon=True)
    t.start()

    return {
        "success": True,
        "render_id": render_id,
        "status": "running",
        "scene_id": scene_id,
        "shot_index": shot_index,
        "log_path": log_path,
        "message": f"Shot {shot_index} of scene {scene_id} generating (standalone, no chain)"
    }


@app.get("/api/v29/log/{render_id}")
async def v29_log_tail(render_id: str, lines: int = 20):
    """Get last N lines of a render log for live streaming in UI."""
    r = _active_renders.get(render_id)
    if not r:
        return {"success": False, "error": "Render not found"}
    log_path = r.get("log_path", "")
    if not log_path or not os.path.exists(log_path):
        return {"success": True, "lines": [], "status": r.get("status")}
    with open(log_path) as f:
        all_lines = f.readlines()
    return {
        "success": True,
        "lines": [l.rstrip() for l in all_lines[-lines:]],
        "status": r.get("status"),
        "result": r.get("result", {}),
        "elapsed": round(time.time() - r.get("started", time.time()), 1),
    }


@app.get("/api/v29/scene/shots/{project}/{scene_id}")
async def v29_scene_shots(project: str, scene_id: str):
    """Get the V29 auto_consolidate shot list for a scene — what the runner actually uses."""
    try:
        from atlas_universal_runner import load_project, get_sb_scene, auto_consolidate
        from shot_truth_contract import compile_scene_truth
        from beat_enrichment import enrich_project

        pdir = Path("pipeline_outputs") / project
        shots, sb, cast, locs = load_project(project)
        sb_scene = get_sb_scene(sb, scene_id)
        if not sb_scene:
            return {"success": False, "error": f"Scene {scene_id} not found"}

        cp = pdir / "scene_contracts" / f"{scene_id}_contract.json"
        if not cp.exists():
            enrich_project(str(pdir), [scene_id])
            compile_scene_truth(str(pdir), scene_id)

        contract = json.load(open(cp)) if cp.exists() else {}
        shots_raw = json.load(open(pdir / "shot_plan.json"))
        if not isinstance(shots_raw, list): shots_raw = shots_raw.get("shots", [])
        mshots = auto_consolidate(sb_scene, contract, shots_raw, scene_id)

        # Add frame/video paths if they exist
        tag = "lite"
        frame_dir = pdir / f"first_frames_{tag}"
        video_dir = pdir / f"videos_kling_{tag}"
        for i, s in enumerate(mshots):
            sid = s["shot_id"]
            fp = frame_dir / f"{sid}.jpg"
            vp = video_dir / f"{sid}.mp4"
            s["_has_frame"] = fp.exists()
            s["_has_video"] = vp.exists()
            s["_frame_path"] = str(fp) if fp.exists() else None
            s["_video_path"] = str(vp) if vp.exists() else None
            s["_shot_index"] = i

        return {
            "success": True,
            "scene_id": scene_id,
            "location": sb_scene.get("location", ""),
            "shots": mshots,
            "total": len(mshots),
        }
    except Exception as e:
        import traceback
        return {"success": False, "error": str(e), "trace": traceback.format_exc()[-500:]}


def register_v29_routes(existing_app, base_dir):
    """Register V29 routes on the main orchestrator app."""
    global BASE_DIR
    BASE_DIR = Path(base_dir)
    # Copy all routes to the existing app
    for route in app.routes:
        existing_app.routes.append(route)


if __name__ == "__main__":
    import uvicorn
    print(f"\n{'='*60}")
    print(f"  ATLAS V29 Universal Runner API")
    print(f"  Port: 9998")
    print(f"  Endpoints:")
    print(f"    POST /api/v29/render              — Render a scene")
    print(f"    POST /api/v29/render/parallel      — Render multiple scenes")
    print(f"    GET  /api/v29/render/status         — Check render status")
    print(f"    GET  /api/v29/render/gate/{{proj}}/{{scene}} — Dry-run gate check")
    print(f"    GET  /api/v29/harmony               — System status")
    print(f"    GET  /api/v29/projects               — List projects")
    print(f"{'='*60}\n")
    uvicorn.run(app, host="0.0.0.0", port=9998)
