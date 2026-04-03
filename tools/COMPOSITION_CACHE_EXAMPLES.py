#!/usr/bin/env python3
"""
COMPOSITION CACHE — V21.10 Integration Examples
Real-world usage patterns for ATLAS production workflows
"""

import json
import shutil
from pathlib import Path
from typing import List, Dict, Optional


# ============================================================================
# EXAMPLE 1: Pre-Analysis of Reuse Opportunities
# ============================================================================

def example_1_analyze_opportunities():
    """
    Before rendering, analyze what we can save.
    Useful for cost estimation and planning.
    """
    from tools.composition_cache import analyze_reuse_opportunities
    
    # Load project
    project = "ravencroft_v17"
    with open(f"pipeline_outputs/{project}/shot_plan.json") as f:
        shot_plan = json.load(f)
    
    shots = shot_plan["shots"]
    
    # Analyze reuse opportunities
    report = analyze_reuse_opportunities(shots)
    
    print(f"\n[ANALYSIS] Project: {project}")
    print(f"  Total shots: {report['total_shots']}")
    print(f"  Unique compositions: {report['unique_compositions']}")
    print(f"  Reusable shots: {report['total_reusable_shots']}")
    print(f"  Savings: {report['estimated_savings']}")
    print(f"  Savings %: {report['savings_pct']}%")
    
    # Show top reuse groups
    print(f"\n  Top Reuse Groups:")
    for group in report['reuse_groups'][:5]:
        comp = group['composition']
        print(f"    [{comp['scene_id']}|{comp['shot_type']}|{comp['lens_class']}]")
        print(f"      Anchor: {group['anchor_shot']}")
        print(f"      Reuse: {len(group['reuse_candidates'])} shots")
        print(f"      Savings: {group['savings']} nano calls")


# ============================================================================
# EXAMPLE 2: Full Render Pipeline with Composition Cache
# ============================================================================

def example_2_full_pipeline_with_cache():
    """
    Complete render workflow using composition cache.
    Handles frame generation, reuse, video rendering, and cache persistence.
    """
    from tools.composition_cache import CompositionCache, should_reuse, get_reuse_source
    
    project = "ravencroft_v17"
    
    # 1. Initialize and load cache
    print(f"\n[PIPELINE] Project: {project}")
    print("[STEP 1] Initialize cache...")
    
    cache = CompositionCache(project=project)
    cache.load()
    print(f"  Loaded cache: {cache.stats()['unique_compositions']} compositions")
    
    # 2. Load shot plan
    print("[STEP 2] Load shot plan...")
    with open(f"pipeline_outputs/{project}/shot_plan.json") as f:
        shot_plan = json.load(f)
    shots = shot_plan["shots"]
    print(f"  Loaded: {len(shots)} shots")
    
    # 3. Generate reuse plan
    print("[STEP 3] Generate reuse plan...")
    reuse_plan = cache.get_reuse_plan(shots)
    print(f"  Anchors: {sum(1 for v in reuse_plan.values() if v is None)}")
    print(f"  Reusers: {sum(1 for v in reuse_plan.values() if v is not None)}")
    
    # 4. Apply metadata
    print("[STEP 4] Apply reuse metadata...")
    shots = cache.apply_reuse_to_shot_plan(shots)
    
    # 5. Generate first frames
    print("[STEP 5] Generate first frames...")
    for i, shot in enumerate(shots[:10]):  # Demo: first 10 only
        shot_id = shot["shot_id"]
        
        if should_reuse(shot):
            # REUSE: Copy cached frame
            source_path = shot["_reuse_frame_path"]
            dest_path = f"pipeline_outputs/{project}/first_frames/{shot_id}.jpg"
            shutil.copy2(source_path, dest_path)
            print(f"  [{i+1}] {shot_id}: REUSED from {get_reuse_source(shot)}")
        else:
            # GENERATE: Fresh nano frame (simulated)
            dest_path = f"pipeline_outputs/{project}/first_frames/{shot_id}.jpg"
            # frame = fal_client.run("fal-ai/nano-banana-pro", {"prompt": shot["nano_prompt"]})
            # shutil.copy2(frame, dest_path)
            cache.register(shot, dest_path, f"/api/media?path=/first_frames/{shot_id}.jpg")
            print(f"  [{i+1}] {shot_id}: GENERATED")
    
    # 6. Save cache for next run
    print("[STEP 6] Save cache...")
    cache.save()
    stats = cache.stats()
    print(f"  Saved: {stats['unique_compositions']} compositions, "
          f"{stats['reusable_shots']} reused, {stats['savings_pct']}% savings")


# ============================================================================
# EXAMPLE 3: Handling Wardrobe Changes
# ============================================================================

def example_3_wardrobe_change():
    """
    When wardrobe changes for a character, invalidate relevant cache entries.
    Ensures costume consistency.
    """
    from tools.composition_cache import CompositionCache
    
    project = "ravencroft_v17"
    
    print(f"\n[WARDROBE] Project: {project}")
    
    cache = CompositionCache(project=project)
    cache.load()
    
    initial_stats = cache.stats()
    print(f"Initial cache: {initial_stats['unique_compositions']} compositions")
    
    # Scenario: EVELYN's wardrobe changes in Scene 003
    print("\nScenario: EVELYN's wardrobe changes in Scene 003")
    
    count = cache.invalidate_for_wardrobe_change("EVELYN RAVENCROFT", scene_id="003")
    print(f"  Invalidated: {count} cache entries")
    
    # Save updated cache
    cache.save()
    
    after_stats = cache.stats()
    print(f"Final cache: {after_stats['unique_compositions']} compositions")
    print(f"  Removed: {initial_stats['unique_compositions'] - after_stats['unique_compositions']} entries")


# ============================================================================
# EXAMPLE 4: Server Integration Endpoints
# ============================================================================

def example_4_server_endpoints():
    """
    Integration points for orchestrator_server.py
    Three new API endpoints for composition cache management.
    """
    
    endpoint_code = """
# In orchestrator_server.py, add these endpoints:

from tools.composition_cache import CompositionCache, analyze_reuse_opportunities

@app.post("/api/v21/composition-cache/analyze")
def analyze_composition_cache(project: str):
    \"\"\"
    Analyze reuse opportunities in current project.
    
    Returns:
        {
          "status": "ok",
          "report": {
            "total_shots": 289,
            "unique_compositions": 47,
            "reusable_shots": 242,
            "total_reusable_shots": 242,
            "estimated_savings": "242 nano-banana calls out of 289",
            "savings_pct": 83.7,
            "reuse_groups": [...]
          }
        }
    \"\"\"
    try:
        shot_plan = load_shot_plan(project)
        report = analyze_reuse_opportunities(shot_plan["shots"])
        return {"status": "ok", "report": report}
    except Exception as e:
        logger.error(f"Composition analysis failed: {e}")
        return {"status": "error", "message": str(e)}, 400

@app.post("/api/v21/composition-cache/apply")
def apply_composition_cache(project: str):
    \"\"\"
    Apply composition-based reuse plan to shot plan.
    
    Modifies shot plan in-place with reuse metadata.
    
    Returns:
        {
          "status": "ok",
          "stats": {
            "total_shots": 289,
            "unique_compositions": 47,
            "reusable_shots": 242,
            "savings_pct": 83.7
          }
        }
    \"\"\"
    try:
        cache = CompositionCache(project=project)
        cache.load()
        
        shot_plan = load_shot_plan(project)
        shots = cache.apply_reuse_to_shot_plan(shot_plan["shots"], cache_only=False)
        shot_plan["shots"] = shots
        save_shot_plan(project, shot_plan)
        
        stats = cache.stats()
        return {"status": "ok", "stats": stats}
    except Exception as e:
        logger.error(f"Composition cache apply failed: {e}")
        return {"status": "error", "message": str(e)}, 400

@app.post("/api/v21/composition-cache/invalidate-wardrobe")
def invalidate_wardrobe_cache(project: str, character: str, scene_id: Optional[str] = None):
    \"\"\"
    Invalidate cache entries for wardrobe change.
    
    Parameters:
        project: Project name
        character: Character name (e.g., "EVELYN RAVENCROFT")
        scene_id: Optional scene ID (default: all scenes)
    
    Returns:
        {
          "status": "ok",
          "invalidated": 3,
          "stats": {...}
        }
    \"\"\"
    try:
        cache = CompositionCache(project=project)
        cache.load()
        
        count = cache.invalidate_for_wardrobe_change(character, scene_id=scene_id)
        cache.save()
        
        stats = cache.stats()
        return {"status": "ok", "invalidated": count, "stats": stats}
    except Exception as e:
        logger.error(f"Wardrobe invalidation failed: {e}")
        return {"status": "error", "message": str(e)}, 400
    """
    
    print("\n[SERVER] Add these endpoints to orchestrator_server.py:\n")
    print(endpoint_code)


# ============================================================================
# EXAMPLE 5: Integration with generate-first-frames Pipeline
# ============================================================================

def example_5_first_frames_integration():
    """
    Integrate cache into generate-first-frames pipeline.
    Shows frame reuse vs. generation logic.
    """
    
    pipeline_code = """
# In generate_first_frames() function:

from tools.composition_cache import CompositionCache, should_reuse, get_reuse_source
import shutil

def generate_first_frames_with_cache(project: str, shots: List[dict]):
    \"\"\"Generate first frames with composition cache optimization.\"\"\"
    
    # Initialize cache
    cache = CompositionCache(project=project)
    cache.load()
    
    # Ensure output directory
    os.makedirs(f"pipeline_outputs/{project}/first_frames", exist_ok=True)
    
    generated = 0
    reused = 0
    
    for shot in shots:
        shot_id = shot["shot_id"]
        
        if should_reuse(shot):
            # REUSE: Copy cached frame
            try:
                source_path = shot["_reuse_frame_path"]
                dest_path = f"pipeline_outputs/{project}/first_frames/{shot_id}.jpg"
                shutil.copy2(source_path, dest_path)
                
                logger.info(f"Reused: {shot_id} from {get_reuse_source(shot)}")
                reused += 1
                
            except Exception as e:
                logger.warning(f"Reuse failed for {shot_id}, falling back to generation: {e}")
                # Fall through to generation
                pass
            else:
                continue  # Success, move to next shot
        
        # GENERATE: Fresh nano frame
        try:
            logger.info(f"Generating: {shot_id}")
            
            # Call nano-banana-pro
            nano_prompt = shot.get("nano_prompt_final", shot.get("nano_prompt", ""))
            frame = fal_client.run(
                "fal-ai/nano-banana-pro",
                {"prompt": nano_prompt},
                timeout=120
            )
            
            # Save frame
            frame_path = f"pipeline_outputs/{project}/first_frames/{shot_id}.jpg"
            fal_file = fal_client.download_file(frame["image"]["url"])
            with open(frame_path, "wb") as f:
                f.write(fal_file)
            
            # Register in cache
            frame_url = f"/api/media?path=/first_frames/{shot_id}.jpg"
            cache.register(shot, frame_path, frame_url)
            
            generated += 1
            
        except Exception as e:
            logger.error(f"Generation failed for {shot_id}: {e}")
            shot["_needs_review"] = True
    
    # Save cache for next run
    cache.save()
    
    stats = cache.stats()
    logger.info(f"First frames: {generated} generated, {reused} reused, "
                f"savings: {stats['savings_pct']}%")
    
    return shots
    """
    
    print("\n[INTEGRATION] First Frames Pipeline:\n")
    print(pipeline_code)


# ============================================================================
# EXAMPLE 6: Debugging & Inspection
# ============================================================================

def example_6_debugging_and_inspection():
    """
    Tools for debugging and inspecting cache state.
    """
    from tools.composition_cache import CompositionCache
    
    project = "ravencroft_v17"
    
    print(f"\n[DEBUG] Project: {project}\n")
    
    cache = CompositionCache(project=project)
    cache.load()
    
    # 6.1: Full statistics
    print("Cache Statistics:")
    stats = cache.stats()
    for key, value in stats.items():
        if key != "entries":
            print(f"  {key}: {value}")
    
    # 6.2: Top reused compositions
    print("\nTop Reused Compositions:")
    if stats["entries"]:
        for entry in stats["entries"][:5]:
            comp = entry["composition"]
            print(f"  {entry['shot_id']} (used {entry['usage_count']}x)")
            print(f"    [{comp['scene_id']}|{comp['shot_type']}|{comp['lens_class']}]")
            print(f"    Characters: {', '.join(comp['characters_present'])}")
    
    # 6.3: Export cache for inspection
    print("\nExport Cache (JSON):")
    cache_path = f"pipeline_outputs/{project}/composition_cache.json"
    with open(cache_path) as f:
        cache_json = json.load(f)
    print(f"  File: {cache_path}")
    print(f"  Entries: {len(cache_json['entries'])}")
    print(f"  Version: {cache_json['version']}")
    print(f"  Timestamp: {cache_json['timestamp']}")


# ============================================================================
# MAIN: Run All Examples
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("COMPOSITION CACHE — V21.10 Integration Examples")
    print("=" * 70)
    
    # Note: These are code examples — they demonstrate patterns
    # Actual execution would require valid shot_plan.json and FAL credentials
    
    print("\nExample 1: Pre-Analysis of Reuse Opportunities")
    print("-" * 70)
    print("→ See: example_1_analyze_opportunities()")
    
    print("\nExample 2: Full Render Pipeline with Cache")
    print("-" * 70)
    print("→ See: example_2_full_pipeline_with_cache()")
    
    print("\nExample 3: Handling Wardrobe Changes")
    print("-" * 70)
    print("→ See: example_3_wardrobe_change()")
    
    print("\nExample 4: Server Integration Endpoints")
    print("-" * 70)
    example_4_server_endpoints()
    
    print("\nExample 5: First Frames Pipeline Integration")
    print("-" * 70)
    example_5_first_frames_integration()
    
    print("\nExample 6: Debugging & Inspection")
    print("-" * 70)
    print("→ See: example_6_debugging_and_inspection()")
    
    print("\n" + "=" * 70)
    print("For production usage, see COMPOSITION_CACHE_REFERENCE.md")
    print("=" * 70)
