# COMPOSITION CACHE — V21.10 Reference

**Module:** `tools/composition_cache.py` (712 lines)  
**Status:** Production | **ATLAS V21.10** | **Created:** 2026-03-04

## Overview

The Composition Cache identifies shots with **identical framing/composition** and enables **plate reuse** — only generating new LTX motion, not new first frames for matching framings.

### Core Concept

```
Scene 001:
  Shot A (wide, eye level, EVELYN + ARTHUR): Generate fresh nano frame
  Shot B (wide, eye level, EVELYN + ARTHUR): REUSE frame from Shot A, generate new LTX
  Shot C (medium, eye level, EVELYN only): Generate fresh nano frame
  Shot D (medium, eye level, EVELYN only): REUSE frame from Shot C, generate new LTX

Savings: 2 nano-banana calls out of 4 (50% reduction)
```

## Data Structures

### `CompositionKey` (Frozen Dataclass)

Immutable hashable identifier for a unique framing. Two shots match if **ALL fields are identical**.

```python
@dataclass(frozen=True)
class CompositionKey:
    scene_id: str                          # e.g., "001"
    shot_type: str                         # e.g., "wide", "medium", "close"
    lens_class: str                        # "wide" (≤35mm), "normal" (36-65mm), "tele" (66mm+)
    characters_present: FrozenSet[str]     # Sorted immutable set: {"ARTHUR", "EVELYN"}
    camera_angle: str                      # "eye_level", "low", "high"
    location: str                          # Normalized scene location
```

**Serialization:**
```python
key.to_dict()  # → {"scene_id": "001", "shot_type": "wide", ...}
CompositionKey.from_dict(data)  # Reconstruct from dict
```

### `CacheEntry` (Dataclass)

Metadata for a cached composition frame.

```python
@dataclass
class CacheEntry:
    shot_id: str            # First shot to generate this composition (anchor)
    frame_path: str         # Local file path: pipeline_outputs/{project}/first_frames/001_shot_a.jpg
    frame_url: str          # Serving URL: /api/media?path=/first_frames/001_shot_a.jpg
    timestamp: str          # ISO 8601 creation time
    usage_count: int = 0    # Number of shots reusing this frame (increments on apply)
```

## Main Class: `CompositionCache`

### Initialization

```python
from tools.composition_cache import CompositionCache

cache = CompositionCache(
    project="ravencroft_v17",
    pipeline_outputs_dir="~/Desktop/ATLAS_CONTROL_SYSTEM/pipeline_outputs"
)
```

### Core Methods

#### `compute_key(shot) → CompositionKey`

Computes the composition key for a shot.

```python
shot = {
    "shot_id": "001_shot_a",
    "scene_id": "001",
    "shot_type": "wide",
    "lens_specs": "24mm",
    "camera_angle": "eye_level",
    "location": "RAVENCROFT MANOR - FOYER",
    "characters": ["EVELYN RAVENCROFT", "ARTHUR GRAY"],
}

key = cache.compute_key(shot)
# CompositionKey(
#   scene_id="001",
#   shot_type="wide",
#   lens_class="wide",
#   characters_present=frozenset({"ARTHUR GRAY", "EVELYN RAVENCROFT"}),
#   camera_angle="eye_level",
#   location="RAVENCROFT MANOR - FOYER"
# )
```

**Lens Classification:**
- `wide`: ≤35mm
- `normal`: 36-65mm
- `tele`: 66mm+

**Camera Angle Extraction:**
- Explicit field: `shot["camera_angle"]`
- Inferred from `shot_type`: "pov" → "high", "low angle" → "low"
- Default: "eye_level"

**Characters Extraction:**
- From `shot["characters"]` array
- From `shot["dialogue_text"]` (speaker markers)
- Normalized, sorted, frozen into immutable set

#### `lookup(shot) → Optional[CacheEntry]`

Look up cached frame for shot's composition.

```python
entry = cache.lookup(shot)

if entry:
    print(f"Cache HIT: reuse frame from {entry.shot_id}")
    print(f"  Path: {entry.frame_path}")
    print(f"  URL: {entry.frame_url}")
    print(f"  Reuses: {entry.usage_count}")
else:
    print("Cache MISS: no matching composition")
```

#### `register(shot, frame_path, frame_url) → None`

Register a generated frame in cache.

```python
cache.register(
    shot=shot_001_a,
    frame_path="/pipeline_outputs/ravencroft_v17/first_frames/001_shot_a.jpg",
    frame_url="/api/media?path=/first_frames/001_shot_a.jpg"
)
# [COMP_CACHE] Cache REGISTER: 001_shot_a composition [001|wide|wide|eye_level] → /pipeline_outputs/...
```

#### `get_reuse_plan(shots) → Dict[shot_id, Optional[source_shot_id]]`

Pre-compute which shots can reuse which frames.

**Strategy:**
1. Group shots by `CompositionKey`
2. First shot in each group = **anchor** (generates fresh nano frame)
3. Remaining shots in group = **reusers** (reuse anchor's frame, generate new LTX)

```python
reuse_plan = cache.get_reuse_plan(shots)
# {
#   "001_shot_a": None,           # Anchor: generate fresh
#   "001_shot_b": "001_shot_a",   # Reuser: from anchor
#   "001_shot_c": None,           # Anchor: different composition
#   "001_shot_d": "001_shot_c",   # Reuser: from different anchor
#   ...
# }
```

#### `apply_reuse_to_shot_plan(shots, cache_only=False) → List[dict]`

Modify shot plan to mark reusable shots with metadata.

```python
shots = cache.apply_reuse_to_shot_plan(shots, cache_only=False)

# For reusers, shot now has:
# {
#   "_reuse_frame_from": "001_shot_a",
#   "_reuse_frame_path": "/pipeline_outputs/.../first_frames/001_shot_a.jpg",
#   "_skip_nano_generation": True
# }
```

**Integration:**
- Anchor shots: no metadata, generate fresh nano frame, register in cache
- Reuser shots: has `_reuse_frame_from`, skip nano generation, copy frame, generate LTX motion

#### `save(path=None) → str`

Persist cache to JSON.

```python
path = cache.save()
# Default: pipeline_outputs/{project}/composition_cache.json

# Or specify custom path:
path = cache.save("/tmp/backup.json")
```

**Serialized Format:**
```json
{
  "project": "ravencroft_v17",
  "version": "21.10",
  "timestamp": "2026-03-04T14:32:18.123456Z",
  "entries": {
    "{\"camera_angle\":\"eye_level\",\"characters_present\":[...],\"lens_class\":\"wide\",...}": {
      "shot_id": "001_shot_a",
      "frame_path": "/pipeline_outputs/ravencroft_v17/first_frames/001_shot_a.jpg",
      "frame_url": "/api/media?path=/first_frames/001_shot_a.jpg",
      "timestamp": "2026-03-04T14:30:00Z",
      "usage_count": 2
    }
  },
  "reuse_plan": {
    "001_shot_a": null,
    "001_shot_b": "001_shot_a"
  }
}
```

#### `load(path=None) → None`

Load cache from JSON.

```python
cache.load()
# Default: pipeline_outputs/{project}/composition_cache.json

cache.load("/tmp/backup.json")
```

Idempotent — can be called multiple times safely.

#### `stats() → dict`

Get cache statistics.

```python
stats = cache.stats()
# {
#   "total_shots": 289,
#   "unique_compositions": 47,
#   "reusable_shots": 242,
#   "total_reuses": 156,
#   "savings_pct": 83.7,
#   "entries": [
#     {
#       "shot_id": "001_shot_a",
#       "composition": {"scene_id": "001", "shot_type": "wide", ...},
#       "usage_count": 8,
#       "timestamp": "2026-03-04T14:30:00Z"
#     },
#     ...
#   ]
# }
```

#### `invalidate_for_wardrobe_change(character, scene_id=None) → int`

Flush cache entries when wardrobe changes for a character.

```python
# Invalidate EVELYN's composition entries in Scene 001
count = cache.invalidate_for_wardrobe_change("EVELYN RAVENCROFT", scene_id="001")
# [COMP_CACHE] Invalidated composition entry: 001_shot_a (wardrobe change: EVELYN RAVENCROFT)
# Returns: 1

# Invalidate all ARTHUR's compositions across all scenes
count = cache.invalidate_for_wardrobe_change("ARTHUR GRAY")
# Returns: 3
```

### Static Methods

#### `classify_lens(focal_length_mm) → str`

Classify focal length into lens class.

```python
CompositionCache.classify_lens(24)  # → "wide"
CompositionCache.classify_lens(50)  # → "normal"
CompositionCache.classify_lens(85)  # → "tele"
CompositionCache.classify_lens(None)  # → "normal" (default)
```

#### `extract_camera_angle(shot) → str`

Extract camera angle from shot data.

```python
CompositionCache.extract_camera_angle(shot)
# → "eye_level" (default), "low", or "high"
```

Checks: explicit `camera_angle` field, then infers from `shot_type`.

#### `extract_characters(shot) → FrozenSet[str]`

Extract and normalize character list from shot.

```python
CompositionCache.extract_characters(shot)
# → frozenset({"ARTHUR GRAY", "EVELYN RAVENCROFT"})
```

Sources: `shot["characters"]` array and `shot["dialogue_text"]` (speaker markers).

## Helper Functions

### `analyze_reuse_opportunities(shots) → dict`

Analyze composition grouping to identify reuse opportunities.

```python
report = analyze_reuse_opportunities(shots)
# {
#   "total_shots": 289,
#   "unique_compositions": 47,
#   "reuse_groups": [
#     {
#       "composition": {
#         "scene_id": "001",
#         "shot_type": "wide",
#         "lens_class": "wide",
#         "characters_present": ["ARTHUR GRAY", "EVELYN RAVENCROFT"],
#         "camera_angle": "eye_level",
#         "location": "RAVENCROFT MANOR - FOYER"
#       },
#       "anchor_shot": "001_shot_a",
#       "reuse_candidates": ["001_shot_b", "001_shot_f"],
#       "group_size": 3,
#       "savings": 2
#     },
#     ...
#   ],
#   "total_reusable_shots": 242,
#   "estimated_savings": "242 nano-banana calls out of 289",
#   "savings_pct": 83.7
# }
```

### `should_reuse(shot) → bool`

Check if shot should reuse a cached frame.

```python
if should_reuse(shot):
    print(f"Copy frame from {get_reuse_source(shot)}")
```

### `get_reuse_source(shot) → Optional[str]`

Get the source shot ID for frame reuse.

```python
source = get_reuse_source(shot)
# → "001_shot_a" or None
```

## Integration Example

### Full Workflow

```python
from tools.composition_cache import CompositionCache, analyze_reuse_opportunities

# 1. Initialize cache
cache = CompositionCache(project="ravencroft_v17")

# 2. Load existing cache if available
cache.load()

# 3. Analyze reuse opportunities in upcoming shots
report = analyze_reuse_opportunities(shots)
print(f"Estimated savings: {report['estimated_savings']}")
print(f"Savings percentage: {report['savings_pct']}%")

# 4. Generate reuse plan
reuse_plan = cache.get_reuse_plan(shots)

# 5. Apply reuse metadata to shot plan
shots = cache.apply_reuse_to_shot_plan(shots, cache_only=False)

# 6. Render first frames
for shot in shots:
    if should_reuse(shot):
        # Copy frame from cache
        source_path = shot["_reuse_frame_path"]
        dest_path = f"pipeline_outputs/{project}/first_frames/{shot['shot_id']}.jpg"
        shutil.copy2(source_path, dest_path)
        print(f"{shot['shot_id']}: Reused frame from {get_reuse_source(shot)}")
    else:
        # Generate fresh nano frame
        frame = fal_client.run("fal-ai/nano-banana-pro", {"prompt": shot["nano_prompt"]})
        frame_path = f"pipeline_outputs/{project}/first_frames/{shot['shot_id']}.jpg"
        cache.register(shot, frame_path, f"/api/media?path=/first_frames/{shot['shot_id']}.jpg")
        print(f"{shot['shot_id']}: Generated fresh nano frame")

# 7. Generate LTX videos (all shots, including reusers)
for shot in shots:
    video = fal_client.run("fal-ai/ltx-2/image-to-video/fast", {
        "image_url": f"/api/media?path=/first_frames/{shot['shot_id']}.jpg",
        "prompt": shot["ltx_motion_prompt"]
    })
    print(f"{shot['shot_id']}: Generated LTX video")

# 8. Save cache for next run
cache.save()
stats = cache.stats()
print(f"Cache stats: {stats['unique_compositions']} compositions, "
      f"{stats['reusable_shots']} reused, {stats['savings_pct']}% savings")

# 9. Handle wardrobe changes
if wardrobe_changed_for_evelyn_scene_001:
    cache.invalidate_for_wardrobe_change("EVELYN RAVENCROFT", scene_id="001")
    cache.save()
```

### Server Integration

**In `orchestrator_server.py`:**

```python
from tools.composition_cache import CompositionCache, should_reuse, get_reuse_source
from tools.composition_cache import analyze_reuse_opportunities

@app.post("/api/v21/composition-cache/analyze")
def analyze_compositions(project: str):
    """Analyze reuse opportunities in current project."""
    shot_plan = load_shot_plan(project)
    report = analyze_reuse_opportunities(shot_plan["shots"])
    return {"status": "ok", "report": report}

@app.post("/api/v21/composition-cache/apply")
def apply_composition_cache(project: str):
    """Apply composition-based reuse plan to shot plan."""
    cache = CompositionCache(project=project)
    cache.load()
    
    shot_plan = load_shot_plan(project)
    shots = cache.apply_reuse_to_shot_plan(shot_plan["shots"])
    shot_plan["shots"] = shots
    save_shot_plan(project, shot_plan)
    
    stats = cache.stats()
    return {"status": "ok", "stats": stats}
```

## Logging

All operations logged with `[COMP_CACHE]` prefix at INFO/DEBUG levels.

```
[COMP_CACHE] 14:32:18 | INFO     | Initialized CompositionCache for project 'ravencroft_v17'
[COMP_CACHE] 14:32:19 | INFO     | Composition group [scene=001|type=wide|lens=wide|angle=eye_level]: 3 shots, anchor=001_shot_a
[COMP_CACHE] 14:32:19 | DEBUG    |   001_shot_a: ANCHOR (generate fresh)
[COMP_CACHE] 14:32:19 | DEBUG    |   001_shot_b: REUSE from 001_shot_a
[COMP_CACHE] 14:32:19 | DEBUG    |   001_shot_f: REUSE from 001_shot_a
[COMP_CACHE] 14:32:20 | INFO     | Cache REGISTER: 001_shot_a composition [001|wide|wide|eye_level] → /pipeline_outputs/.../first_frames/001_shot_a.jpg
[COMP_CACHE] 14:32:21 | INFO     | 001_shot_b: REUSE frame from 001_shot_a (usage count: 1)
[COMP_CACHE] 14:32:22 | INFO     | Applied reuse markings to 242 shots
[COMP_CACHE] 14:32:23 | INFO     | Saved composition cache to /pipeline_outputs/ravencroft_v17/composition_cache.json (47 entries)
```

## Performance Notes

- **Memory:** O(n) where n = unique compositions (typically 5-20% of total shots)
- **Lookup:** O(1) per shot (hash-based cache)
- **Compute Key:** O(m) where m = number of characters (typically 2-8)
- **Savings:** 50-85% nano-banana reduction for multi-take/coverage-heavy scenes

## Version & Metadata

| Field | Value |
|-------|-------|
| Module | `tools/composition_cache.py` |
| Version | 21.10 |
| Lines | 712 |
| Status | Production |
| Author | ATLAS Engineering |
| Created | 2026-03-04 |
| Storage | `pipeline_outputs/{project}/composition_cache.json` |

---

**ATLAS V21.10 — AAA Production Factory — Composition Reuse Active**
