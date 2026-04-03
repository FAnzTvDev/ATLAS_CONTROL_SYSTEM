#!/bin/bash
#
# ATLAS V20 A/B COMPARISON RUNNER
# ================================
# Runs scenes 001-003 TWICE:
#   Run A: V20-CLEAN prompts (direct, action-first, ~900 chars)
#   Run B: V20-ENRICHED prompts (full enrichment stack, ~4000 chars)
#
# Both use identical V20 pipeline, gold standard, wardrobe, camera defaults.
# ONLY difference is prompt content/length.
#
# Usage: ./ATLAS_RUN_COMPARISON.sh [clean|enriched|both]
#   Default: both (runs clean first, then enriched)
#
# Prerequisites:
#   - Server running on localhost:9999
#   - FAL API keys working
#   - ATLAS_COMPARISON_PREP.py already run (creates both shot_plan files)
#

set -e

ATLAS_DIR="/Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM"
PIPE_DIR="$ATLAS_DIR/pipeline_outputs/ravencroft_v17"
SERVER="http://localhost:9999"
PROJECT="ravencroft_v17"
SCENE_FILTER="001,002,003"
LOG_DIR="$PIPE_DIR/comparison_benchmark"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

mkdir -p "$LOG_DIR"

# ============================================================
# HELPER FUNCTIONS
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
    local version=$1  # "v20_clean" or "v20_enriched"
    local source="$PIPE_DIR/shot_plan_${version}.json"

    if [ ! -f "$source" ]; then
        echo -e "${RED}ERROR: $source not found. Run ATLAS_COMPARISON_PREP.py first.${NC}"
        exit 1
    fi

    # Backup current
    cp "$PIPE_DIR/shot_plan.json" "$PIPE_DIR/shot_plan.json.pre_swap_${TIMESTAMP}"

    # Swap in the version
    cp "$source" "$PIPE_DIR/shot_plan.json"

    # Touch dirty flag to invalidate cache
    mkdir -p "$PIPE_DIR/ui_cache"
    date > "$PIPE_DIR/ui_cache/.dirty"

    echo -e "${GREEN}Swapped shot_plan to: ${version}${NC}"
}

archive_run() {
    local label=$1  # "v20_clean" or "v20_enriched"
    local dest_frames="$PIPE_DIR/first_frames_${label}"
    local dest_videos="$PIPE_DIR/videos_${label}"

    # Move generated frames
    if [ -d "$PIPE_DIR/first_frames" ] && [ "$(ls -A $PIPE_DIR/first_frames/ 2>/dev/null | grep -E '^00[123]' | head -1)" ]; then
        mkdir -p "$dest_frames"
        for f in "$PIPE_DIR/first_frames"/00[123]_*; do
            [ -f "$f" ] && mv "$f" "$dest_frames/"
        done
        echo -e "${GREEN}Archived frames to: ${dest_frames}${NC}"
    fi

    # Move generated videos
    if [ -d "$PIPE_DIR/videos" ] && [ "$(ls -A $PIPE_DIR/videos/ 2>/dev/null | grep -E '^00[123]' | head -1)" ]; then
        mkdir -p "$dest_videos"
        for f in "$PIPE_DIR/videos"/00[123]_*; do
            [ -f "$f" ] && mv "$f" "$dest_videos/"
        done
        echo -e "${GREEN}Archived videos to: ${dest_videos}${NC}"
    fi
}

run_generation() {
    local label=$1
    local log_file="$LOG_DIR/${label}_${TIMESTAMP}.log"

    echo -e "\n${YELLOW}========================================${NC}"
    echo -e "${YELLOW}  GENERATING: ${label}${NC}"
    echo -e "${YELLOW}  Scene filter: ${SCENE_FILTER}${NC}"
    echo -e "${YELLOW}========================================${NC}\n"

    # Record start time
    local start_ts=$(date +%s)
    local start_readable=$(date "+%Y-%m-%d %H:%M:%S")
    echo "START: $start_readable" > "$log_file"
    echo "VERSION: $label" >> "$log_file"
    echo "" >> "$log_file"

    # STEP 1: Generate first frames
    echo -e "${BLUE}[1/3] Generating first frames...${NC}"
    local frame_start=$(date +%s)

    local frame_response=$(curl -s -X POST "$SERVER/api/auto/generate-first-frames" \
        -H "Content-Type: application/json" \
        -d "{\"project\":\"$PROJECT\",\"dry_run\":false,\"scene_filter\":\"$SCENE_FILTER\"}" \
        --max-time 3600)

    local frame_end=$(date +%s)
    local frame_duration=$((frame_end - frame_start))

    echo "FRAMES: ${frame_duration}s" >> "$log_file"
    echo "Frame response: $frame_response" >> "$log_file"
    echo "" >> "$log_file"

    local frame_count=$(ls "$PIPE_DIR/first_frames"/00[123]_* 2>/dev/null | wc -l | tr -d ' ')
    echo -e "${GREEN}  Frames generated: ${frame_count} in ${frame_duration}s${NC}"

    # STEP 2: Generate videos
    echo -e "${BLUE}[2/3] Generating videos...${NC}"
    local video_start=$(date +%s)

    local video_response=$(curl -s -X POST "$SERVER/api/auto/render-videos" \
        -H "Content-Type: application/json" \
        -d "{\"project\":\"$PROJECT\",\"dry_run\":false,\"scene_filter\":\"$SCENE_FILTER\"}" \
        --max-time 1800)

    local video_end=$(date +%s)
    local video_duration=$((video_end - video_start))

    echo "VIDEOS: ${video_duration}s" >> "$log_file"
    echo "Video response: $video_response" >> "$log_file"
    echo "" >> "$log_file"

    local video_count=$(ls "$PIPE_DIR/videos"/00[123]_*.mp4 2>/dev/null | wc -l | tr -d ' ')
    echo -e "${GREEN}  Videos generated: ${video_count} in ${video_duration}s${NC}"

    # STEP 3: Stitch
    echo -e "${BLUE}[3/3] Stitching...${NC}"
    local stitch_start=$(date +%s)

    local stitch_response=$(curl -s -X POST "$SERVER/api/v16/stitch/run" \
        -H "Content-Type: application/json" \
        -d "{\"project\":\"$PROJECT\",\"scene_filter\":\"$SCENE_FILTER\"}" \
        --max-time 120)

    local stitch_end=$(date +%s)
    local stitch_duration=$((stitch_end - stitch_start))

    echo "STITCH: ${stitch_duration}s" >> "$log_file"
    echo "" >> "$log_file"

    # Also do manual FFmpeg stitch to comparison folder
    echo -e "${BLUE}  Creating comparison stitch...${NC}"
    local stitch_out="$PIPE_DIR/${label}_scenes001-003.mp4"

    # Build file list
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
            echo -e "${GREEN}  Stitched: ${stitch_out} (${file_size})${NC}"
        fi
    fi
    rm -f "$concat_file"

    # Total timing
    local end_ts=$(date +%s)
    local total=$((end_ts - start_ts))
    local end_readable=$(date "+%Y-%m-%d %H:%M:%S")

    echo "END: $end_readable" >> "$log_file"
    echo "TOTAL: ${total}s" >> "$log_file"
    echo "" >> "$log_file"
    echo "SUMMARY:" >> "$log_file"
    echo "  Frames: ${frame_count} in ${frame_duration}s ($(echo "scale=1; $frame_duration / ($frame_count + 1)" | bc)s/frame)" >> "$log_file"
    echo "  Videos: ${video_count} in ${video_duration}s ($(echo "scale=1; $video_duration / ($video_count + 1)" | bc)s/video)" >> "$log_file"
    echo "  Stitch: ${stitch_duration}s" >> "$log_file"
    echo "  Total:  ${total}s ($(echo "scale=1; $total / 60" | bc)m)" >> "$log_file"

    echo -e "\n${GREEN}========================================${NC}"
    echo -e "${GREEN}  COMPLETE: ${label}${NC}"
    echo -e "${GREEN}  Frames: ${frame_count} in ${frame_duration}s${NC}"
    echo -e "${GREEN}  Videos: ${video_count} in ${video_duration}s${NC}"
    echo -e "${GREEN}  Total:  ${total}s ($(echo "scale=1; $total / 60" | bc) min)${NC}"
    echo -e "${GREEN}  Log: ${log_file}${NC}"
    echo -e "${GREEN}========================================${NC}\n"
}

# ============================================================
# MAIN
# ============================================================

MODE=${1:-both}

echo -e "\n${YELLOW}╔════════════════════════════════════════════╗${NC}"
echo -e "${YELLOW}║  ATLAS V20 A/B COMPARISON RUNNER           ║${NC}"
echo -e "${YELLOW}║  Mode: ${MODE}                                  ║${NC}"
echo -e "${YELLOW}║  Project: ${PROJECT}                   ║${NC}"
echo -e "${YELLOW}║  Scenes: ${SCENE_FILTER}                       ║${NC}"
echo -e "${YELLOW}╚════════════════════════════════════════════╝${NC}\n"

check_server

if [ "$MODE" = "clean" ] || [ "$MODE" = "both" ]; then
    echo -e "${BLUE}>>> Preparing V20-CLEAN run...${NC}"
    swap_shot_plan "v20_clean"
    run_generation "v20_clean"
    archive_run "v20_clean"
fi

if [ "$MODE" = "enriched" ] || [ "$MODE" = "both" ]; then
    echo -e "${BLUE}>>> Preparing V20-ENRICHED run...${NC}"
    swap_shot_plan "v20_enriched"
    run_generation "v20_enriched"
    archive_run "v20_enriched"
fi

# Restore original shot_plan
if [ -f "$PIPE_DIR/shot_plan.json.pre_swap_${TIMESTAMP}" ]; then
    cp "$PIPE_DIR/shot_plan_v20_enriched.json" "$PIPE_DIR/shot_plan.json"
    echo -e "${GREEN}Restored shot_plan to V20 enriched (production)${NC}"
fi

# ============================================================
# FINAL REPORT
# ============================================================
echo -e "\n${YELLOW}╔════════════════════════════════════════════╗${NC}"
echo -e "${YELLOW}║  COMPARISON COMPLETE                        ║${NC}"
echo -e "${YELLOW}╚════════════════════════════════════════════╝${NC}\n"

if [ "$MODE" = "both" ]; then
    echo -e "Results:"
    echo -e "  V20-CLEAN:    $PIPE_DIR/v20_clean_scenes001-003.mp4"
    echo -e "  V20-ENRICHED: $PIPE_DIR/v20_enriched_scenes001-003.mp4"
    echo -e ""
    echo -e "Frames:"
    echo -e "  V20-CLEAN:    $PIPE_DIR/first_frames_v20_clean/"
    echo -e "  V20-ENRICHED: $PIPE_DIR/first_frames_v20_enriched/"
    echo -e ""
    echo -e "Benchmarks:"
    ls -la "$LOG_DIR"/*_${TIMESTAMP}.log 2>/dev/null
fi

echo -e "\n${GREEN}Done! Review both stitched videos side by side.${NC}\n"
