#!/bin/bash
################################################################################
# 🎬 THE LEDGE - AUTOMATED ASSEMBLY PIPELINE
# Assembles 5 rendered shots into final cinematic sequence
################################################################################

OUTPUT_DIR="/Users/quantum/Desktop/atlas_output/the_ledge"
FINAL_OUTPUT="/Users/quantum/Desktop/the_ledge_opening.mp4"

echo "🎬 THE LEDGE - Automated Assembly Pipeline"
echo "=========================================================================="
echo ""

# Check if images exist
echo "📋 Checking for rendered images..."
if [ ! -d "$OUTPUT_DIR" ]; then
    echo "⚠️  Output directory not found: $OUTPUT_DIR"
    echo "   Renders will appear here once workers complete tasks"
    echo ""
    echo "🎯 CURRENT STATUS:"
    echo "   - 5 shots queued in orchestrator"
    echo "   - Waiting for workers to connect"
    echo "   - Open http://localhost:8888 to add workers"
    echo ""
    exit 1
fi

cd "$OUTPUT_DIR"

echo "✅ Found output directory"
echo ""

# Count available images
IMAGE_COUNT=$(ls -1 ledge_*.jpg 2>/dev/null | wc -l)
echo "📊 Rendered images: $IMAGE_COUNT / 5"
echo ""

if [ "$IMAGE_COUNT" -lt 5 ]; then
    echo "⏳ Still rendering..."
    echo "   Expected: 5 shots"
    echo "   Completed: $IMAGE_COUNT shots"
    echo ""
    echo "   Watch live progress: http://localhost:8888"
    exit 0
fi

echo "✅ All 5 shots rendered! Starting assembly..."
echo ""

################################################################################
# PHASE 1: Image Sequence Assembly
################################################################################
echo "🎞️  PHASE 1: Assembling image sequence..."

ffmpeg -y \
  -loop 1 -t 5 -i ledge_001.jpg \
  -loop 1 -t 3 -i ledge_002.jpg \
  -loop 1 -t 4 -i ledge_003.jpg \
  -loop 1 -t 2 -i ledge_004.jpg \
  -loop 1 -t 3 -i ledge_005.jpg \
  -filter_complex \
  "[0:v]scale=3840:2160,setsar=1,fps=24,fade=t=in:st=0:d=0.5,fade=t=out:st=4.5:d=0.5[v0]; \
   [1:v]scale=3840:2160,setsar=1,fps=24,fade=t=in:st=0:d=0.3,fade=t=out:st=2.7:d=0.3[v1]; \
   [2:v]scale=3840:2160,setsar=1,fps=24,fade=t=in:st=0:d=0.3,fade=t=out:st=3.7:d=0.3[v2]; \
   [3:v]scale=3840:2160,setsar=1,fps=24,fade=t=in:st=0:d=0.2,fade=t=out:st=1.8:d=0.2[v3]; \
   [4:v]scale=3840:2160,setsar=1,fps=24,fade=t=in:st=0:d=0.3,fade=t=out:st=2.7:d=0.3[v4]; \
   [v0][v1][v2][v3][v4]concat=n=5:v=1:a=0,format=yuv420p[v]" \
  -map "[v]" \
  -c:v libx264 -preset slow -crf 18 \
  -movflags +faststart \
  temp_video.mp4

if [ $? -eq 0 ]; then
    echo "   ✅ Image sequence assembled (17 seconds)"
else
    echo "   ❌ FFmpeg assembly failed"
    exit 1
fi

echo ""

################################################################################
# PHASE 2: Color Grading
################################################################################
echo "🎨 PHASE 2: Applying color grade..."

# LUT-based color grading for cold, desaturated thriller look
ffmpeg -y -i temp_video.mp4 \
  -vf "eq=saturation=0.85:contrast=1.1,curves=all='0/0.05 0.5/0.48 1/0.95'" \
  -c:v libx264 -preset slow -crf 18 \
  -movflags +faststart \
  temp_graded.mp4

if [ $? -eq 0 ]; then
    echo "   ✅ Color grading applied (cold thriller look)"
else
    echo "   ❌ Color grading failed"
    exit 1
fi

echo ""

################################################################################
# PHASE 3: Audio Mix (if audio files exist)
################################################################################
echo "🔊 PHASE 3: Audio mix..."

if [ -f "dramatic_score.mp3" ] && [ -f "wind_sfx.mp3" ]; then
    echo "   Adding music and sound effects..."

    ffmpeg -y \
      -i temp_graded.mp4 \
      -i dramatic_score.mp3 \
      -i wind_sfx.mp3 \
      -filter_complex \
      "[1:a]volume=0.7,afade=t=in:st=0:d=1,afade=t=out:st=16:d=1[music]; \
       [2:a]volume=0.5[wind]; \
       [music][wind]amix=inputs=2:duration=first:dropout_transition=2[a]" \
      -map 0:v -map "[a]" \
      -c:v copy -c:a aac -b:a 320k \
      -shortest \
      "$FINAL_OUTPUT"

    if [ $? -eq 0 ]; then
        echo "   ✅ Audio mixed (score + SFX)"
    else
        echo "   ⚠️  Audio mix failed, using video only"
        cp temp_graded.mp4 "$FINAL_OUTPUT"
    fi
else
    echo "   ⚠️  Audio files not found, video only"
    cp temp_graded.mp4 "$FINAL_OUTPUT"
fi

echo ""

################################################################################
# PHASE 4: Cleanup
################################################################################
echo "🧹 PHASE 4: Cleanup..."
rm -f temp_video.mp4 temp_graded.mp4
echo "   ✅ Temporary files removed"

echo ""
echo "=========================================================================="
echo "✅ THE LEDGE - OPENING SEQUENCE COMPLETE!"
echo "=========================================================================="
echo ""
echo "📊 Final Video Stats:"
ffprobe -v quiet -show_format -show_streams "$FINAL_OUTPUT" | grep -E "(duration|width|height|codec_name|bit_rate)" | head -10
echo ""
echo "📁 Output: $FINAL_OUTPUT"
echo "⏱️  Duration: 17 seconds"
echo "📐 Resolution: 3840x2160 (4K)"
echo "🎨 Look: Cold, desaturated thriller"
echo ""
echo "🎬 Ready for review!"
echo ""

# Auto-open if on macOS
if command -v open &> /dev/null; then
    echo "🎥 Opening video..."
    open "$FINAL_OUTPUT"
fi
