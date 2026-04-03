#!/bin/bash
# ============================================================
# ATLAS V21 FRESH RUN CLEANUP
# Removes ~5+ GB of old runs, archives, test projects, caches
# KEEPS: shot_plan.json, cast_map.json, story_bible.json,
#        wardrobe.json, extras.json, location_masters/, configs
# ============================================================

set -e
cd /Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM

echo "🧹 ATLAS V21 Cleanup — Starting..."
echo ""

# --- 1. Ravencroft old archives & comparison runs (~1.7 GB) ---
echo "1/8 Removing old archives & comparison runs..."
rm -rf pipeline_outputs/ravencroft_v17/archive/
rm -rf pipeline_outputs/ravencroft_v17/_archive/
rm -rf pipeline_outputs/ravencroft_v17/_archive_v9_run_20260227_1843/
rm -rf pipeline_outputs/ravencroft_v17/comparison_benchmark/
rm -rf pipeline_outputs/ravencroft_v17/runs/

# --- 2. Old backup frames (~350 MB) ---
echo "2/8 Removing old backup frames..."
rm -rf pipeline_outputs/ravencroft_v17/_backup_frames/
rm -rf pipeline_outputs/ravencroft_v17/first_frames_archive_bad_refs/
rm -rf pipeline_outputs/ravencroft_v17/first_frames_archive_v1/
rm -rf pipeline_outputs/ravencroft_v17/scene_001_backup_pre_fresh_run/
rm -rf pipeline_outputs/ravencroft_v17/_analysis_frames/

# --- 3. Old V20 A/B test runs (~135 MB) ---
echo "3/8 Removing V20 test runs..."
rm -rf pipeline_outputs/ravencroft_v17/videos_v20_enriched/
rm -rf pipeline_outputs/ravencroft_v17/videos_v20_clean/
rm -rf pipeline_outputs/ravencroft_v17/first_frame_variants_v20_enriched/
rm -rf pipeline_outputs/ravencroft_v17/first_frame_variants_v20_clean/

# --- 4. Old generated videos & stitches (~980 MB) ---
echo "4/8 Removing old videos & stitches (will regenerate)..."
rm -rf pipeline_outputs/ravencroft_v17/videos/
rm -rf pipeline_outputs/ravencroft_v17/stitched_scenes/
rm -rf pipeline_outputs/ravencroft_v17/videos_kling/
rm -rf pipeline_outputs/ravencroft_v17/director_tools/
rm -rf pipeline_outputs/ravencroft_v17/final/

# --- 5. Old first frames & variants (will regenerate) ---
echo "5/8 Removing old first frames & variants..."
rm -rf pipeline_outputs/ravencroft_v17/first_frames/
rm -rf pipeline_outputs/ravencroft_v17/first_frame_variants/

# --- 6. Old analysis/report files ---
echo "6/8 Removing old analysis files..."
rm -f pipeline_outputs/ravencroft_v17/ANALYSIS_SUMMARY.txt
rm -f pipeline_outputs/ravencroft_v17/REGRESSION_SUMMARY.txt
rm -f pipeline_outputs/ravencroft_v17/REGRESSION_AUDIT_V20.md
rm -f pipeline_outputs/ravencroft_v17/REGRESSION_FIX_ROADMAP.md
rm -f pipeline_outputs/ravencroft_v17/README_REGRESSION_AUDIT.md
rm -f pipeline_outputs/ravencroft_v17/GATE_GAPS_QUICK_REFERENCE.md
rm -f pipeline_outputs/ravencroft_v17/IMPLEMENTATION_CODE_BLOCKS.md
rm -f pipeline_outputs/ravencroft_v17/PROMPT_COMPARISON_V9_vs_ENRICHED.html
rm -f pipeline_outputs/ravencroft_v17/FIX_REPORT.json
rm -f pipeline_outputs/ravencroft_v17/LOCKSMITH_REPORT.json
rm -f pipeline_outputs/ravencroft_v17/_recent_renders.json
rm -f pipeline_outputs/ravencroft_v17/ATLAS_RERUN_FIXED.sh
rm -f pipeline_outputs/ravencroft_v17/ATLAS_RUN_ENRICHED.sh

# --- 7. Global caches (~1.1 GB) ---
echo "7/8 Removing global caches..."
rm -rf stitched_scenes/
rm -rf fal_cache/
rm -rf render_gallery/

# --- 8. Old test projects (~600 MB) ---
echo "8/8 Removing 63 old test projects..."
cd pipeline_outputs
for dir in */; do
    if [ "$dir" != "ravencroft_v17/" ]; then
        rm -rf "$dir"
    fi
done
cd ..

echo ""
echo "✅ Cleanup complete!"
echo ""
echo "Kept in ravencroft_v17/:"
echo "  📄 shot_plan.json"
echo "  📄 cast_map.json"
echo "  📄 story_bible.json"
echo "  📄 wardrobe.json"
echo "  📄 extras.json"
echo "  📁 location_masters/ (15 reference images)"
echo "  📄 ui_cache/ (will auto-rebuild)"
echo "  📄 Config files (PROJECT_LOCK.json, _agent_status.json, _live_jobs.json)"
echo ""
echo "🎬 Ready for V21 fresh run — restart server then generate!"
