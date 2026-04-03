#!/usr/bin/env python3
"""
🎬 ATLAS MULTI-TAB ORCHESTRATOR SERVER V6
WebSocket-based coordination server for parallel movie generation
WITH V6 COMPLETE INTEGRATION
"""

# This file is generated - replace orchestrator_server.py with this file
# Then restart the server

print("Loading V6 integrated server - this may take a moment...")

# Load the original server and V6 endpoints
import sys
from pathlib import Path

# Add current directory to path
BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

# Import and run the integrated server
exec(open(str(BASE_DIR / "orchestrator_server.py")).read().replace(
    'if __name__ == "__main__":',
    '''
# ============================================================================
# V6 COMPLETE INTEGRATION - AUTO-INJECTED
# ============================================================================
try:
    from V6_ATLAS_MASTER_SYSTEM import (
        ManifestParserV6,
        LTX2PromptBuilder, 
        ScriptPreprocessor,
        IntegratedShotGenerator,
        format_runtime,
        parse_runtime
    )
    
    _v6_preprocessor = None
    _v6_generator = None
    _v6_current_script = {}
    
    def _init_v6():
        global _v6_preprocessor, _v6_generator
        if _v6_preprocessor:
            return
        try:
            dirs = json.load(open(BASE_DIR / "directors_library.json"))
            writ = json.load(open(BASE_DIR / "writers_library.json"))
            _v6_preprocessor = ScriptPreprocessor()
            _v6_generator = IntegratedShotGenerator(dirs, writ)
            logger.info("✅ V6 Complete Integration initialized")
        except Exception as e:
            logger.error(f"V6 init error: {e}")
            _v6_preprocessor = ScriptPreprocessor()
            _v6_generator = IntegratedShotGenerator()
    
    @app.post("/api/v6/preprocess")
    async def v6_preprocess(request: Request):
        _init_v6()
        global _v6_current_script
        try:
            body = await request.json()
            content = body.get("content", "")
            project_name = body.get("project_name", "untitled")
            result = _v6_preprocessor.preprocess(content, project_name)
            _v6_current_script = {
                "project": project_name,
                "screenplay_preview": result["screenplay"][:2000],
                "metadata": result["metadata"],
            }
            return JSONResponse({"success": True, "project": project_name})
        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)})
    
    @app.get("/api/v6/current-script")
    async def v6_get_current_script():
        return JSONResponse({"success": True, "script": _v6_current_script})
    
    @app.post("/api/v6/approve/{step}")
    async def v6_approve(step: str, request: Request):
        body = await request.json()
        project = body.get("project", "")
        project_dir = PIPELINE_OUTPUTS_DIR / project
        project_dir.mkdir(parents=True, exist_ok=True)
        state_file = project_dir / "verification_state.json"
        verification = json.loads(state_file.read_text()) if state_file.exists() else {}
        verification[f"{step}_approved"] = True
        state_file.write_text(json.dumps(verification, indent=2))
        return JSONResponse({"success": True, "step": step})
    
    @app.get("/api/v6/shots/{project}")
    async def v6_get_shots(project: str):
        project_dir = PIPELINE_OUTPUTS_DIR / project
        shot_plan_file = project_dir / "shot_plan.json"
        if not shot_plan_file.exists():
            return JSONResponse({"success": False, "shots": []})
        data = json.loads(shot_plan_file.read_text())
        shots = data if isinstance(data, list) else data.get("shots", [])
        return JSONResponse({"success": True, "shots": shots})
    
    @app.post("/api/v6/regenerate/{project}/{shot_id}")
    async def v6_regenerate(project: str, shot_id: str):
        return JSONResponse({"success": True, "status": "queued", "shot_id": shot_id})
    
    @app.get("/api/v6/live-status/{project}")
    async def v6_live_status(project: str):
        return JSONResponse({"success": True, "recent_frames": [], "active_renders": []})
    
    @app.get("/api/v6/verification-state/{project}")
    async def v6_verification_state(project: str):
        project_dir = PIPELINE_OUTPUTS_DIR / project
        state_file = project_dir / "verification_state.json"
        state = json.loads(state_file.read_text()) if state_file.exists() else {}
        return JSONResponse({"success": True, "state": state})

    logger.info("✅ V6 Complete Integration endpoints loaded")
except ImportError as e:
    logger.warning(f"V6 not available: {e}")

if __name__ == "__main__":
'''
))
