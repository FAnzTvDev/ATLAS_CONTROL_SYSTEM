"""
ATLAS V23 Route Modules
Modular endpoint organization — gradually replacing monolithic orchestrator_server.py

Phase 3 Implementation:
- Establishes clean separation of concerns (generation, project, import, editing, media, analysis)
- Each module is independently testable and debuggable
- Routes are thin wrappers around shared service/agent layer
- Orchestrator_server.py gradually imports these as primary implementation

Router Organization:
- routes_generation.py  (~150 lines) — Fix-V16, frame/video generation, multi-angle, autonomous render
- routes_project.py     (~100 lines) — Project management, bundle, state persistence
- routes_import.py      (~80 lines) — Script import, story bible, auto-cast
- routes_editing.py     (~100 lines) — Shot editing, quick-add, variants, timeline, wardrobe
- routes_media.py       (~60 lines) — Media serving, R2 sync, file I/O
- routes_analysis.py    (~80 lines) — QA, LOA, audit, script fidelity, health checks

Each router is registered in orchestrator_server.py via:
    from routes.routes_generation import router as gen_router
    app.include_router(gen_router, prefix="/api")

Status: SCAFFOLDING — ready for gradual migration from monolith
Version: V23.0.0
"""

__all__ = [
    'routes_generation',
    'routes_project',
    'routes_import',
    'routes_editing',
    'routes_media',
    'routes_analysis',
]
