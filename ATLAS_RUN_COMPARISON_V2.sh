#!/bin/bash
#
# ATLAS V20 A/B COMPARISON RUNNER — V2 (Master Chain + Parallel)
# ================================================================
# Runs scenes 001-003 using the FULL pipeline:
#   - Master Shot Chain (nano master → reframe variants → end-frame chaining)
#   - 3 angle variants per shot
#   - DINO cinematic flow ranking
#   - Parallel scene rendering (all 3 scenes at once)
#   - Video generation (LTX-2)
#   - Auto-stitch per scene + final concat
#
# Two runs:
#   Run A: V20-CLEAN prompts (direct, action-first, ~900 chars)
#   Run B: V20-ENRICHED prompts (full enrichment stack, ~4000 chars)
#
# Usage: ./ATLAS_RUN_COMPARISON_V2.sh [clean|enriched|both]
#

set -e

ATLAS_DIR="/Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM"
PIPE_DIR="$ATLAS_DIR/pipeline_outputs/ravencroft_v17"
SERVER="http://localhost:9999"
PROJECT="ravencroft_v17"
LOG_DIR="$PIPE_DIR/comparison_benchmark"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

mkdir -p "$LOG_DIR"

# ============================================================
# HELPERS
# ============================================================

check_server() {
    echo -e "${BLUE}Checking server...${NC}"
    if ! curl -s --connect-timeout 5 "$SERVER/api/auto/projects" > /dev/null 2>&1; then
        echo -e "${RED}ERROR: Server not running on $SERVER${NC}"
        echo "Start it with: cd $ATLAS_DIR && python3 orchestrator_server.py"
        exit 1
    fi
    echo -e "${GREEN}Server OK${NC}"
}

swap_shot_plan() {
    local version=$1
    local source="$PIPE_DIR/shot_plan_${version}.json"

    if [ ! -f "$source" ]; then
        echo -e "${RED}ERROR: $source not found. Run ATLAS_COMPARISON_PREP.py first.${NC}"
        exit 1
    fi

    cp "$PIPE_DIR/shot_plan.json" "$PIPE_DIR/shot_plan.json.pre_v2swap_${TIMESTAMP}"
    cp "$source" "$PIPE_DIR/shot_plan.json"
    mkdir -p "$PIPE_DIR/ui_cache"
    date > "$PIPE_DIR/ui_cache/.dirty"
    echo -e "${GREEN}Swapped shot_plan to: ${version}${NC}"
}

clean_active_outputs() {
    # Move any active frames/videos out of the way before a new run
    local label=$1
    echo -e "${BLUE}Cleaning active outputs for fresh run...${NC}"
    for dir in first_frames videos; do
        for f in "$PIPE_DIR/$dir"/00[123]_*; do
            [ -f "$f" ] && rm "$f"
        done
    done
}

archive_run() {
    local label=$1
    mkdir -p "$PIPE_DIR/first_frames_${label}" "$PIPE_DIR/videos_${label}"

    for f in "$PIPE_DIR/first_frames"/00[123]_*; do
        [ -f "$f" ] && cp "$f" "$PIPE_DIR/first_frames_${label}/"
    done
    for f in "$PIPE_DIR/videos"/00[123]_*.mp4; do
        [ -f "$f" ] && cp "$f" "$PIPE_DIR/videos_${label}/"
    done

    # Also copy variants
    if [ -d "$PIPE_DIR/first_frame_variants" ]; then
        mkdir -p "$PIPE_DIR/first_frame_variants_${label}"
        for f in "$PIPE_DIR/first_frame_variants"/00[123]_*; do
            [ -f "$f" ] && cp "$f" "$PIPE_DIR/first_frame_variants_${label}/"
        done
    fi

    local frame_ct=$(ls "$PIPE_DIR/first_frames_${label}/" 2>/dev/null | wc -l | tr -d ' ')
    local video_ct=$(ls "$PIPE_DIR/videos_${label}/"*.mp4 2>/dev/null | wc -l | tr -d ' ')
    echo -e "${GREEN}Archived ${label}: ${frame_ct} frames, ${video_ct} videos${NC}"
}

poll_chain_status() {
    # Poll until all 3 scenes complete or timeout
    local label=$1
    local max_wait=1800  # 30 minute timeout
    local poll_interval=15
    local elapsed=0

    echo -e "${CYAN}Polling chain status...${NC}"
    while [ $elapsed -lt $max_wait ]; do
        sleep $poll_interval
        elapsed=$((elapsed + poll_interval))

        # Count frames and videos
        local frames=$(ls "$PIPE_DIR/first_frames"/00[123]_*.jpg 2>/dev/null | wc -l | tr -d ' ')
        local videos=$(ls "$PIPE_DIR/videos"/00[123]_*.mp4 2>/dev/null | wc -l | tr -d ' ')

        # Per-scene breakdown
        local s1f=$(ls "$PIPE_DIR/first_frames"/001_*.jpg 2>/dev/null | wc -l | tr -d ' ')
        local s2f=$(ls "$PIPE_DIR/first_frames"/002_*.jpg 2>/dev/null | wc -l | tr -d ' ')
        local s3f=$(ls "$PIPE_DIR/first_frames"/003_*.jpg 2>/dev/null | wc -l | tr -d ' ')
        local s1v=$(ls "$PIPE_DIR/videos"/001_*.mp4 2>/dev/null | wc -l | tr -d ' ')
        local s2v=$(ls "$PIPE_DIR/videos"/002_*.mp4 2>/dev/null | wc -l | tr -d ' ')
        local s3v=$(ls "$PIPE_DIR/videos"/003_*.mp4 2>/dev/null | wc -l | tr -d ' ')

        printf "${CYAN}[%ds] Frames: S1=%s S2=%s S3=%s (%s total) | Videos: S1=%s S2=%s S3=%s (%s total)${NC}\n" \
            $elapsed "$s1f" "$s2f" "$s3f" "$frames" "$s1v" "$s2v" "$s3v" "$videos"

        # Check if generation is complete (28 frames + 28 videos)
        if [ "$videos" -ge 28 ]; then
            echo -e "${GREEN}All 28 videos complete!${NC}"
            return 0
        fi

        # If frames done but no videos after a while, videos may be queuing
        if [ "$frames" -ge 28 ] && [ "$videos" -eq 0 ] && [ $elapsed -gt 300 ]; then
            echo -e "${YELLOW}All frames done, waiting for video generation...${NC}"
        fi
    done

    echo -e "${RED}TIMEOUT after ${max_wait}s — partial results available${NC}"
    return 1
}

stitch_scenes() {
    local label=$1
    local stitch_out="$PIPE_DIR/${label}_scenes001-003.mp4"

    echo -e "${BLUE}Stitching ${label}...${NC}"

    # Try server stitch first
    curl -s -X POST "$SERVER/api/v16/stitch/run" \
        -H "Content-Type: application/json" \
        -d "{\"project\":\"$PROJECT\",\"scene_filter\":\"001,002,003\"}" \
        --max-time 120 > /dev/null 2>&1

    # Also manual FFmpeg stitch as backup
    local concat_file="/tmp/atlas_concat_${label}.txt"
    > "$concat_file"
    for vf in $(ls "$PIPE_DIR/videos"/00[123]_*.mp4 2>/dev/null | sort); do
        echo "file '$vf'" >> "$concat_file"
    done

    if [ -s "$concat_file" ]; then
        ffmpeg -y -f concat -safe 0 -i "$concat_file" \
            -vf "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2" \
            -c:v libx264 -preset fast -crf 20 -r 24 \
            "$stitch_out" 2>/dev/null

        if [ -f "$stitch_out" ]; then
            local file_size=$(du -h "$stitch_out" | cut -f1)
            local duration=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$stitch_out" 2>/dev/null | cut -d. -f1)
            echo -e "${GREEN}Stitched: ${stitch_out} (${file_size}, ${duration}s)${NC}"
        fi
    fi
    rm -f "$concat_file"
}

run_chain_generation() {
    local label=$1
    local log_file="$LOG_DIR/${label}_chain_${TIMESTAMP}.log"

    echo -e "\n${YELLOW}══════════════════════════════════════════${NC}"
    echo -e "${YELLOW}  MASTER CHAIN: ${label}${NC}"
    echo -e "${YELLOW}  Scenes: 001, 002, 003 (PARALLEL)${NC}"
    echo -e "${YELLOW}  Pipeline: Master→Reframe→Chain→Video→Stitch${NC}"
    echo -e "${YELLOW}══════════════════════════════════════════${NC}\n"

    local start_ts=$(date +%s)
    local start_readable=$(date "+%Y-%m-%d %H:%M:%S")
    echo "START: $start_readable" > "$log_file"
    echo "VERSION: $label" >> "$log_file"
    echo "PIPELINE: master-chain/parallel-render" >> "$log_file"
    echo "" >> "$log_file"

    # Clean any existing frames/videos for scenes 001-003
    clean_active_outputs "$label"

    # STEP 1: Launch parallel chain render for all 3 scenes
    echo -e "${BLUE}[1/2] Launching Master Chain parallel render (3 scenes)...${NC}"
    local chain_start=$(date +%s)

    local chain_response=$(curl -s -X POST "$SERVER/api/v18/master-chain/parallel-render" \
        -H "Content-Type: application/json" \
        -d "{
            \"project\": \"$PROJECT\",
            \"scene_ids\": [\"001\", \"002\", \"003\"],
            \"max_concurrent\": 3,
            \"video_model\": \"ltx\"
        }" \
        --max-time 30)

    echo "Chain launch response: $chain_response" >> "$log_file"
    echo -e "${GREEN}Chain launched: $chain_response${NC}"

    # If async, poll for completion
    if echo "$chain_response" | python3 -c "import sys,json; d=json.load(sys.stdin); sys.exit(0 if d.get('async') else 1)" 2>/dev/null; then
        echo -e "${CYAN}Async mode — polling for completion...${NC}"
        poll_chain_status "$label"
    else
        # Synchronous fallback — might mean it ran inline
        echo -e "${YELLOW}Non-async response — checking if chain used kling_render_scene_batch...${NC}"
        # Wait and poll
        poll_chain_status "$label"
    fi

    local chain_end=$(date +%s)
    local chain_duration=$((chain_end - chain_start))
    echo "CHAIN_RENDER: ${chain_duration}s" >> "$log_file"

    # Count results
    local frame_count=$(ls "$PIPE_DIR/first_frames"/00[123]_*.jpg 2>/dev/null | wc -l | tr -d ' ')
    local video_count=$(ls "$PIPE_DIR/videos"/00[123]_*.mp4 2>/dev/null | wc -l | tr -d ' ')
    echo -e "${GREEN}Chain complete: ${frame_count} frames, ${video_count} videos in ${chain_duration}s${NC}"

    # STEP 2: Stitch
    echo -e "${BLUE}[2/2] Stitching...${NC}"
    local stitch_start=$(date +%s)
    stitch_scenes "$label"
    local stitch_end=$(date +%s)
    local stitch_duration=$((stitch_end - stitch_start))
    echo "STITCH: ${stitch_duration}s" >> "$log_file"

    # Total
    local end_ts=$(date +%s)
    local total=$((end_ts - start_ts))
    local end_readable=$(date "+%Y-%m-%d %H:%M:%S")

    echo "" >> "$log_file"
    echo "END: $end_readable" >> "$log_file"
    echo "TOTAL: ${total}s" >> "$log_file"
    echo "" >> "$log_file"
    echo "SUMMARY:" >> "$log_file"
    echo "  Frames: ${frame_count}" >> "$log_file"
    echo "  Videos: ${video_count}" >> "$log_file"
    echo "  Chain render: ${chain_duration}s" >> "$log_file"
    echo "  Stitch: ${stitch_duration}s" >> "$log_file"
    echo "  Total: ${total}s ($(echo "scale=1; $total / 60" | bc)m)" >> "$log_file"

    echo -e "\n${GREEN}══════════════════════════════════════════${NC}"
    echo -e "${GREEN}  COMPLETE: ${label}${NC}"
    echo -e "${GREEN}  Frames: ${frame_count} | Videos: ${video_count}${NC}"
    echo -e "${GREEN}  Total: ${total}s ($(echo "scale=1; $total / 60" | bc) min)${NC}"
    echo -e "${GREEN}══════════════════════════════════════════${NC}\n"
}

# ============================================================
# MAIN
# ============================================================

MODE=${1:-both}

echo -e "\n${YELLOW}╔════════════════════════════════════════════════╗${NC}"
echo -e "${YELLOW}║  ATLAS V20 A/B — MASTER CHAIN + PARALLEL       ║${NC}"
echo -e "${YELLOW}║  Mode: ${MODE}                                        ║${NC}"
echo -e "${YELLOW}║  Project: ${PROJECT}                             ║${NC}"
echo -e "${YELLOW}║  Scenes: 001, 002, 003 (all parallel)           ║${NC}"
echo -e "${YELLOW}║  Pipeline: Chain + Multi-Angle + DINO + Stitch  ║${NC}"
echo -e "${YELLOW}╚════════════════════════════════════════════════╝${NC}\n"

check_server

if [ "$MODE" = "clean" ] || [ "$MODE" = "both" ]; then
    echo -e "${BLUE}>>> Preparing V20-CLEAN run...${NC}"
    swap_shot_plan "v20_clean"
    run_chain_generation "v20_clean"
    archive_run "v20_clean"
fi

if [ "$MODE" = "enriched" ] || [ "$MODE" = "both" ]; then
    echo -e "${BLUE}>>> Preparing V20-ENRICHED run...${NC}"
    swap_shot_plan "v20_enriched"
    run_chain_generation "v20_enriched"
    archive_run "v20_enriched"
fi

# Restore enriched as production
cp "$PIPE_DIR/shot_plan_v20_enriched.json" "$PIPE_DIR/shot_plan.json"
echo -e "${GREEN}Restored shot_plan to V20 enriched (production)${NC}"

# ============================================================
# FINAL REPORT
# ============================================================
echo -e "\n${YELLOW}╔════════════════════════════════════════════════╗${NC}"
echo -e "${YELLOW}║  COMPARISON COMPLETE                            ║${NC}"
echo -e "${YELLOW}╚════════════════════════════════════════════════╝${NC}\n"

if [ "$MODE" = "both" ]; then
    echo -e "Stitched videos:"
    echo -e "  V20-CLEAN:    $PIPE_DIR/v20_clean_scenes001-003.mp4"
    echo -e "  V20-ENRICHED: $PIPE_DIR/v20_enriched_scenes001-003.mp4"
    echo ""
    echo -e "Frame archives:"
    echo -e "  V20-CLEAN:    $PIPE_DIR/first_frames_v20_clean/"
    echo -e "  V20-ENRICHED: $PIPE_DIR/first_frames_v20_enriched/"
    echo ""
    echo -e "Variant archives:"
    echo -e "  V20-CLEAN:    $PIPE_DIR/first_frame_variants_v20_clean/"
    echo -e "  V20-ENRICHED: $PIPE_DIR/first_frame_variants_v20_enriched/"
    echo ""
    echo -e "Benchmarks:"
    ls -la "$LOG_DIR/"*chain*${TIMESTAMP}*.log 2>/dev/null
fi

echo -e "\n${GREEN}Done! Review both stitched videos side by side.${NC}\n"
