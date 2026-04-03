#!/usr/bin/env bash
LOCKFILE="/Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM/run.lock"
if [ -e "$LOCKFILE" ]; then
  echo "Run already in progress (lockfile $LOCKFILE exists)."
  exit 1
fi
trap 'rm -f "$LOCKFILE"' EXIT
trap 'rm -f "$LOCKFILE"; exit 1' INT TERM
> "$LOCKFILE"
cd /Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM || exit 1
if [ -f "venv/bin/activate" ]; then
  source "venv/bin/activate"
fi
export IBM_QUANTUM_TOKEN="DJ_NwpOAe7ONrzsHgXHLutGyF9nOJF6uTXdaVGEP34bx"
export IBM_QUANTUM_INSTANCE="crn:v1:bluemix:public:quantum-computing:us-east:a/75bf7841da9d45879be7235da4e1698f:72b65202-1106-4632-ac98-75d611a9d8db::"
export MAX_QUANTUM_SECONDS=${MAX_QUANTUM_SECONDS:-40}
export QUANTUM_JOB_SECONDS=${QUANTUM_JOB_SECONDS:-2}
export MAX_FAL_SPEND_USD=${MAX_FAL_SPEND_USD:-40}

# Auto-append guardrail args when not supplied.
AUTO_ARGS=()
FORCE_QUANTUM_ONLY=${ATLAS_FORCE_QUANTUM_ONLY:-1}
DEFAULT_SCENE_LIMIT=${ATLAS_SCENE_LIMIT:-3}

if [ "$FORCE_QUANTUM_ONLY" = "1" ]; then
  found_quantum_flag=0
  for arg in "$@"; do
    if [[ "$arg" == "--quantum-only" ]]; then
      found_quantum_flag=1
      break
    fi
  done
  if [ "$found_quantum_flag" -eq 0 ]; then
    AUTO_ARGS+=("--quantum-only")
  fi
fi

if [ -n "$DEFAULT_SCENE_LIMIT" ]; then
  found_scene_limit=0
  prev_arg=""
  for arg in "$@"; do
    if [[ "$arg" == "--scene-limit" ]]; then
      found_scene_limit=1
      break
    fi
    if [[ "$arg" == --scene-limit=* ]]; then
      found_scene_limit=1
      break
    fi
    # check value following --scene-limit
    if [[ "$prev_arg" == "--scene-limit" ]]; then
      found_scene_limit=1
      break
    fi
    prev_arg="$arg"
  done
  if [ "$found_scene_limit" -eq 0 ]; then
    AUTO_ARGS+=("--scene-limit" "$DEFAULT_SCENE_LIMIT")
  fi
fi

python3 BLACKWOOD_PRODUCTION_SYSTEM.py --episode-path director_outputs/blackwood_parallel_director.json "${AUTO_ARGS[@]}" "$@"
