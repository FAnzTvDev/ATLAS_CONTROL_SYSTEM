# ATLAS Agents (V16.7) — deterministic “hire agents” package

This package gives you **5 narrow agents + 1 coordinator + a CLI** that:
- read canonical project files (pipeline_outputs/<project>/...)
- write canonical outputs back
- produce structured reports
- (optionally) emit Live job + asset feeds for the UI

## Install
```bash
cd /Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM
python3 -m venv .venv && source .venv/bin/activate
pip install -U pip pyyaml
# (optional for server integration)
pip install fastapi uvicorn
```

## Configure
Edit `config.yaml` (paths + policy thresholds).  
Default assumes repo root contains `pipeline_outputs/` and `ai_actors_library.json`.

## Run (Prep-only autopilot — no rendering)
```bash
python3 -m atlas_agents.cli autopilot --project Ravencroft_V6_upload --mode prep
```

## Run (Canary render job placeholder)
This package **does not** call FAL/Comfy by default. It creates a job record so
the UI Live panel is truthful. Plug your real renderer into `live_sync.py`.
```bash
python3 -m atlas_agents.cli autopilot --project Ravencroft_V6_upload --mode canary
```

## Outputs written
- pipeline_outputs/<project>/cast_map.json
- pipeline_outputs/<project>/shot_plan.json (ai_actor_cast + segments)
- pipeline_outputs/<project>/critic_report.json
- pipeline_outputs/<project>/freeze_verdict.json
- pipeline_outputs/<project>/_live_jobs.json
- pipeline_outputs/<project>/_recent_renders.json

## Integration points (server/UI)
- Job feed:  GET /api/agents/renderer/jobs?project=...
- Asset feed: GET /api/recent-renders?project=...
Both can simply return the JSON files written above, or call the functions in `live_sync.py`.
