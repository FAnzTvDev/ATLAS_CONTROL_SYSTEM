#!/bin/bash
# ATLAS V18 - Kling Video Generation with REAL durations + prompts
# Run on your Mac (not in sandbox)

echo "=============================================="
echo "  KLING VIDEO GENERATION - Scene 001"
echo "  Using REAL durations + prompts from shot_plan"
echo "=============================================="

cd /Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM

# Check server
if ! curl -s http://localhost:9999/health > /dev/null 2>&1; then
    echo "Starting server..."
    python3 orchestrator_server.py > /tmp/atlas_server.log 2>&1 &
    sleep 5
fi

# Generate using Python to access shot_plan data
python3 << 'PYEOF'
import json
import requests
import time
import os

PROJECT = "ravencroft_v17"
BASE_URL = "http://localhost:9999"

# Load shot plan for real durations and prompts
with open(f'pipeline_outputs/{PROJECT}/shot_plan.json') as f:
    sp = json.load(f)

# Get Scene 001 shots
scene01 = [s for s in sp.get('shots', []) if s.get('shot_id', '').startswith('001_')]
scene01 = sorted(scene01, key=lambda x: x['shot_id'])

# Check which have first frames
ff_dir = f'pipeline_outputs/{PROJECT}/first_frames'
shots_with_ff = [s for s in scene01 if os.path.exists(os.path.join(ff_dir, f"{s['shot_id']}.jpg"))]

print(f"Shots to generate: {len(shots_with_ff)}")
print()

start_time = time.time()
success_count = 0
total_duration = 0

for i, shot in enumerate(shots_with_ff):
    shot_id = shot['shot_id']
    duration = min(shot.get('duration', 8), 10)  # Kling max 10s
    
    # Get the real prompt - use ltx_motion_prompt or nano_prompt
    prompt = shot.get('ltx_motion_prompt', shot.get('nano_prompt', 'Cinematic motion'))
    # Clean up prompt for Kling (first 500 chars)
    prompt = prompt[:500] if prompt else "Subtle cinematic motion"
    
    print(f"[{i+1}/{len(shots_with_ff)}] {shot_id} ({duration}s)")
    print(f"    Prompt: {prompt[:80]}...")
    
    shot_start = time.time()
    
    try:
        resp = requests.post(
            f"{BASE_URL}/api/v17/shot/kling-i2v",
            json={
                "project": PROJECT,
                "shot_id": shot_id,
                "prompt": prompt,
                "duration": duration
            },
            timeout=180
        )
        data = resp.json()
        elapsed = time.time() - shot_start
        
        if data.get("success"):
            print(f"    ✓ Success ({elapsed:.1f}s)")
            success_count += 1
            total_duration += duration
        else:
            print(f"    ✗ Failed: {data.get('error', 'unknown')[:60]}")
    except Exception as e:
        print(f"    ✗ Error: {str(e)[:60]}")
    
    print()

total_time = time.time() - start_time

print("==============================================")
print(f"  COMPLETE")
print(f"  Success: {success_count}/{len(shots_with_ff)}")
print(f"  Total video: {total_duration}s")
print(f"  Generation time: {total_time:.0f}s")
print(f"  Est. cost: ~${success_count * 0.15:.2f}")
print("==============================================")
PYEOF

# Open UI
open "http://localhost:9999/?project=ravencroft_v17"
