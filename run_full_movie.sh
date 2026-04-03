#!/bin/bash
# ATLAS V18.3 Full Movie Generation Pipeline
# Runs all 18 scenes sequentially, logs timing and cost

PROJ="ravencroft_v17"
BASE="http://127.0.0.1:9999"
LOG="/tmp/atlas_full_movie.log"
FRAMES_DIR="/Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM/pipeline_outputs/${PROJ}/first_frames"
VIDEOS_DIR="/Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM/pipeline_outputs/${PROJ}/videos"

echo "========================================" > "$LOG"
echo "ATLAS V18.3 FULL MOVIE BENCHMARK" >> "$LOG"
echo "Started: $(date)" >> "$LOG"
echo "Project: $PROJ" >> "$LOG"
echo "========================================" >> "$LOG"
echo "" >> "$LOG"

TOTAL_START=$(date +%s)
TOTAL_FRAMES=0
TOTAL_VIDEOS=0
TOTAL_FAILS=0

# PHASE 1: Generate First Frames (all 18 scenes)
echo "=== PHASE 1: FIRST FRAME GENERATION ===" >> "$LOG"
for SCENE in 001 002 003 004 005 006 007 008 009 010 011 012 013 014 015 016 017 018; do
    SCENE_START=$(date +%s)
    echo "" >> "$LOG"
    echo "--- Scene $SCENE: Starting at $(date '+%H:%M:%S') ---" >> "$LOG"

    RESULT=$(curl -s "$BASE/api/auto/generate-first-frames" \
        -X POST -H "Content-Type: application/json" \
        -d "{\"project\":\"$PROJ\",\"scene_filter\":\"$SCENE\",\"dry_run\":false}" \
        --max-time 600 2>&1)

    SCENE_END=$(date +%s)
    SCENE_ELAPSED=$((SCENE_END - SCENE_START))

    # Parse result
    GEN=$(echo "$RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('generated_count',0))" 2>/dev/null || echo "0")
    TOTAL=$(echo "$RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('total_shots',0))" 2>/dev/null || echo "?")
    FAILS=$(echo "$RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('failed_count',0))" 2>/dev/null || echo "0")

    TOTAL_FRAMES=$((TOTAL_FRAMES + GEN))
    TOTAL_FAILS=$((TOTAL_FAILS + FAILS))

    echo "  Scene $SCENE: $GEN/$TOTAL generated, $FAILS failed, ${SCENE_ELAPSED}s" >> "$LOG"
    echo "  Scene $SCENE: $GEN/$TOTAL generated, $FAILS failed, ${SCENE_ELAPSED}s"
done

PHASE1_END=$(date +%s)
PHASE1_ELAPSED=$((PHASE1_END - TOTAL_START))
FRAME_COUNT=$(ls "$FRAMES_DIR" 2>/dev/null | wc -l | tr -d ' ')

echo "" >> "$LOG"
echo "=== PHASE 1 COMPLETE ===" >> "$LOG"
echo "Total frames generated: $TOTAL_FRAMES" >> "$LOG"
echo "Total frames on disk: $FRAME_COUNT" >> "$LOG"
echo "Total failures: $TOTAL_FAILS" >> "$LOG"
echo "Phase 1 time: ${PHASE1_ELAPSED}s ($(echo "scale=1; $PHASE1_ELAPSED/60" | bc)min)" >> "$LOG"

# PHASE 2: Generate Videos (all 18 scenes)
echo "" >> "$LOG"
echo "=== PHASE 2: VIDEO GENERATION ===" >> "$LOG"
for SCENE in 001 002 003 004 005 006 007 008 009 010 011 012 013 014 015 016 017 018; do
    SCENE_START=$(date +%s)
    echo "" >> "$LOG"
    echo "--- Scene $SCENE videos: Starting at $(date '+%H:%M:%S') ---" >> "$LOG"

    RESULT=$(curl -s "$BASE/api/auto/render-videos" \
        -X POST -H "Content-Type: application/json" \
        -d "{\"project\":\"$PROJ\",\"scene_filter\":\"$SCENE\",\"dry_run\":false}" \
        --max-time 1200 2>&1)

    SCENE_END=$(date +%s)
    SCENE_ELAPSED=$((SCENE_END - SCENE_START))

    GEN=$(echo "$RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('rendered_count',d.get('generated_count',0)))" 2>/dev/null || echo "0")
    FAILS=$(echo "$RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('failed_count',0))" 2>/dev/null || echo "0")

    TOTAL_VIDEOS=$((TOTAL_VIDEOS + GEN))

    echo "  Scene $SCENE: $GEN videos rendered, $FAILS failed, ${SCENE_ELAPSED}s" >> "$LOG"
    echo "  Scene $SCENE videos: $GEN rendered, $FAILS failed, ${SCENE_ELAPSED}s"
done

PHASE2_END=$(date +%s)
PHASE2_ELAPSED=$((PHASE2_END - PHASE1_END))
VIDEO_COUNT=$(ls "$VIDEOS_DIR"/*.mp4 2>/dev/null | wc -l | tr -d ' ')

echo "" >> "$LOG"
echo "=== PHASE 2 COMPLETE ===" >> "$LOG"
echo "Total videos rendered: $TOTAL_VIDEOS" >> "$LOG"
echo "Total videos on disk: $VIDEO_COUNT" >> "$LOG"
echo "Phase 2 time: ${PHASE2_ELAPSED}s ($(echo "scale=1; $PHASE2_ELAPSED/60" | bc)min)" >> "$LOG"

# PHASE 3: Stitch
echo "" >> "$LOG"
echo "=== PHASE 3: STITCHING ===" >> "$LOG"
STITCH_START=$(date +%s)

STITCH_RESULT=$(curl -s "$BASE/api/v16/stitch/run" \
    -X POST -H "Content-Type: application/json" \
    -d "{\"project\":\"$PROJ\"}" \
    --max-time 300 2>&1)

STITCH_END=$(date +%s)
STITCH_ELAPSED=$((STITCH_END - STITCH_START))

echo "Stitch result: $(echo "$STITCH_RESULT" | head -c 500)" >> "$LOG"
echo "Stitch time: ${STITCH_ELAPSED}s" >> "$LOG"

# FINAL REPORT
TOTAL_END=$(date +%s)
TOTAL_ELAPSED=$((TOTAL_END - TOTAL_START))

echo "" >> "$LOG"
echo "========================================" >> "$LOG"
echo "FINAL BENCHMARK REPORT" >> "$LOG"
echo "========================================" >> "$LOG"
echo "Total time: ${TOTAL_ELAPSED}s ($(echo "scale=1; $TOTAL_ELAPSED/60" | bc)min)" >> "$LOG"
echo "Phase 1 (frames): ${PHASE1_ELAPSED}s ($(echo "scale=1; $PHASE1_ELAPSED/60" | bc)min)" >> "$LOG"
echo "Phase 2 (videos): ${PHASE2_ELAPSED}s ($(echo "scale=1; $PHASE2_ELAPSED/60" | bc)min)" >> "$LOG"
echo "Phase 3 (stitch): ${STITCH_ELAPSED}s" >> "$LOG"
echo "Frames on disk: $FRAME_COUNT" >> "$LOG"
echo "Videos on disk: $VIDEO_COUNT" >> "$LOG"
echo "Total failures: $TOTAL_FAILS" >> "$LOG"
echo "Completed: $(date)" >> "$LOG"
echo "" >> "$LOG"
echo "BENCHMARK COMPLETE" >> "$LOG"

echo ""
echo "BENCHMARK COMPLETE - Full log at $LOG"
echo "Total: ${TOTAL_ELAPSED}s | Frames: $FRAME_COUNT | Videos: $VIDEO_COUNT"
