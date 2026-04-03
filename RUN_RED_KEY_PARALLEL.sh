#!/bin/bash
# RED KEY EP1 — PARALLEL VIDEO GENERATION + STITCH
# V36 upgrade: no chaining, independent shots, ultra-cinematic prompts
# Run from: ATLAS_CONTROL_SYSTEM/

echo "======================================================"
echo "RED KEY EP1 — PARALLEL MODE (--gen-mode parallel)"
echo "11 shots / 2 scenes / no end-frame chaining"
echo "Each shot starts from its own approved first frame"
echo "======================================================"

cd "$(dirname "$0")"

python3 atlas_universal_runner.py red_key_ep1 001 002 \
  --mode lite \
  --videos-only \
  --gen-mode parallel

echo ""
echo "======================================================"
echo "DONE — check pipeline_outputs/red_key_ep1/videos_kling_lite/"
echo "Full cut: pipeline_outputs/red_key_ep1/RED_KEY_EP1_FULL.mp4"
echo "======================================================"
