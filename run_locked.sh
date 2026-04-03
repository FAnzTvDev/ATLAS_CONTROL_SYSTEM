#!/bin/bash
# ATLAS V37 Locked Run — Regression-proof execution
# Usage: ./run_locked.sh <project> <scene_start> [scene_end] [--frames-only|--videos-only] [--mode lite|full]

set -e

echo "🔒 ATLAS V37 LOCKED RUN"
echo "========================"
echo "Only verified 7/7 systems will fire."
echo "Blocked: V26 orchestrator, Seedance, old frame reuse, independent M-frames"
echo ""

# Validate args
if [ -z "$1" ] || [ -z "$2" ]; then
    echo "Usage: ./run_locked.sh <project> <scene_start> [scene_end] [--mode lite] [--frames-only|--videos-only]"
    exit 1
fi

PROJECT=$1
SCENE_START=$2
shift 2

# If next arg is a bare scene number, treat it as scene_end
SCENE_END=""
if [[ "$1" =~ ^[0-9]+$ ]]; then
    SCENE_END=$1
    shift
fi

echo "Project: $PROJECT"
if [ -n "$SCENE_END" ]; then
    echo "Scenes:  $SCENE_START → $SCENE_END"
else
    echo "Scene:   $SCENE_START"
fi
echo ""

# Run with lock engaged (--locked is default-on in the runner, but we pass it explicitly)
if [ -n "$SCENE_END" ]; then
    python3 atlas_universal_runner.py "$PROJECT" "$SCENE_START" "$SCENE_END" --locked "$@"
else
    python3 atlas_universal_runner.py "$PROJECT" "$SCENE_START" --locked "$@"
fi

echo ""
echo "🔒 Run Lock Report: check logs above for any blocked system attempts."
