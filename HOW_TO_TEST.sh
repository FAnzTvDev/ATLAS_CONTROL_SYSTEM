#!/usr/bin/env bash
# HOW TO TEST THE RAVENCROFT PIPELINE (Phase 8.9)
set -euo pipefail

cat <<'INSTRUCTIONS'
1. Ensure dependencies are installed:
   pip install -r requirements.txt

2. Activate the orchestrator sandbox (optional but recommended for UI verification):
   PYTHONPATH=. python3 orchestrator_server.py

3. Run the strict 14-slot validation pass (fails fast if any asset slot is empty):
   PYTHONPATH=. python3 run_episode_parallel_scenes.py \
     --shot-plan pipeline_outputs/ravencroft_ep1_cinematographer/shot_plan.json \
     --max-workers 7 --images-only

4. Inspect results:
   - Logs must show "Slots 1-14" filled for every shot (no "underfilled" warnings).
   - /api/gallery/shots?project=ravencroft_manor should list rendered frames per scene.
   - atlas_output/nano_banana/ stores the rendered JPEGs.

If any shot stops with "asset_grid_invalid" fix the referenced manifest entry (characters, props, or location library) and rerun step 3.
INSTRUCTIONS
