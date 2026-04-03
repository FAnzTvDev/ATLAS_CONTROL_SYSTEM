# CANONICAL ROLODEX — Integration with ATLAS Pipeline

This document shows how to integrate the Canonical Rolodex into existing ATLAS generation workflows.

## Integration Points

The Rolodex can be integrated at three key points in the ATLAS V27 pipeline:

1. **Pre-generation validation** (optional) — Audit rolodex before generation starts
2. **Film Engine compilation** — Select refs during prompt compilation
3. **Orchestrator FAL calls** — Pass selected refs as image_urls to FAL API

## Option A: Pre-Generation Audit (Recommended for New Projects)

Before starting a full generation run, audit the rolodex to ensure all required packs exist.

### File: `orchestrator_server.py`

```python
from tools.canonical_rolodex import validate_rolodex_completeness
import json

@app.post("/api/v27/validate-rolodex/{project}")
def validate_rolodex_endpoint(project: str):
    """Audit rolodex completeness before generation."""
    project_path = f"/path/to/pipeline_outputs/{project}"

    # Load required characters/locations from shot_plan
    with open(f"{project_path}/shot_plan.json") as f:
        shot_plan = json.load(f)

    # Extract unique characters and locations
    required_characters = set()
    required_locations = set()

    for scene in shot_plan.get("scenes", []):
        required_locations.add(scene.get("location", "UNKNOWN"))
        for shot in scene.get("shots", []):
            for char in shot.get("characters", []):
                required_characters.add(char)

    # Audit
    audit = validate_rolodex_completeness(
        project_path,
        list(required_characters),
        list(required_locations)
    )

    return audit


@app.post("/api/v27/create-rolodex-packs/{project}")
def create_rolodex_packs_endpoint(project: str):
    """Create empty pack structures for missing packs."""
    from tools.canonical_rolodex import (
        create_empty_character_pack_structure,
        create_empty_location_pack_structure
    )

    project_path = f"/path/to/pipeline_outputs/{project}"

    # Load requirements
    with open(f"{project_path}/shot_plan.json") as f:
        shot_plan = json.load(f)

    created = {
        "character_packs": [],
        "location_packs": []
    }

    # Create character packs
    for scene in shot_plan.get("scenes", []):
        for shot in scene.get("shots", []):
            for char in shot.get("characters", []):
                try:
                    create_empty_character_pack_structure(project_path, char)
                    created["character_packs"].append(char)
                except:
                    pass  # Already exists

    # Create location packs
    for scene in shot_plan.get("scenes", []):
        location = scene.get("location", "UNKNOWN")
        try:
            create_empty_location_pack_structure(project_path, location)
            created["location_packs"].append(location)
        except:
            pass  # Already exists

    return created
```

### Usage

```bash
# 1. Validate rolodex
curl http://localhost:8000/api/v27/validate-rolodex/ravencroft_v22

# Output:
{
  "complete": false,
  "missing_required": [
    "THOMAS_BLACKWOOD (headshot_front)",
    "LIBRARY (master_wide)"
  ],
  "recommendations": [
    "Add headshot_front for THOMAS_BLACKWOOD",
    "Add master_wide for LIBRARY"
  ]
}

# 2. Create empty pack structures
curl -X POST http://localhost:8000/api/v27/create-rolodex-packs/ravencroft_v22

# 3. User manually adds .jpg images to pack directories

# 4. Re-validate to confirm
curl http://localhost:8000/api/v27/validate-rolodex/ravencroft_v22
```

---

## Option B: Integration with Film Engine

Integrate ref selection into the Film Engine prompt compilation path.

### File: `tools/film_engine.py`

```python
from tools.canonical_rolodex import CanonicalRolodex, select_best_refs, ShotType, SceneType
import json
import logging

logger = logging.getLogger("atlas.film_engine")


class FilmEngineWithRolodex:
    """Film Engine with Canonical Rolodex integration."""

    def __init__(self, project_path: str):
        self.project_path = project_path
        self.rolodex = CanonicalRolodex(project_path)

        # Load project data
        with open(f"{project_path}/cast_map.json") as f:
            self.cast_map = json.load(f)

        with open(f"{project_path}/story_bible.json") as f:
            self.story_bible = json.load(f)

    def compile_shot_with_refs(
        self,
        shot: Dict[str, Any],
        model: str = "ltx-2"
    ) -> Dict[str, Any]:
        """
        Compile shot prompt + select best references.

        Returns:
            {
                "nano_prompt": "...",
                "ltx_motion_prompt": "...",
                "_negative_prompt": "...",
                "_selected_character_refs": [...],
                "_selected_location_refs": [...],
                "_ref_selection_reason": "...",
                "_ref_selection_confidence": 0.95,
                ...other film engine fields...
            }
        """

        # Select best references for this shot
        ref_selection = select_best_refs(
            shot,
            self.cast_map,
            self.story_bible,
            self.rolodex
        )

        # Compile prompt as usual
        compiled = self._compile_prompt(shot, model)

        # Inject reference selection metadata
        compiled["_selected_character_refs"] = ref_selection.selected_character_refs
        compiled["_selected_location_refs"] = ref_selection.selected_location_refs
        compiled["_ref_selection_reason"] = ref_selection.selection_reason
        compiled["_ref_selection_confidence"] = ref_selection.confidence
        compiled["_fallback_used"] = ref_selection.fallback_used

        # If emotion was overridden, inject into prompt
        if ref_selection.emotion_override:
            if ref_selection.emotion_override == "vulnerable":
                compiled["ltx_motion_prompt"] += (
                    " The character's expression is vulnerable, fragile, on the edge "
                    "of breaking. Their posture conveys deep emotional pain."
                )

        logger.info(
            f"Compiled shot {shot.get('shot_id')} with refs: "
            f"confidence={ref_selection.confidence:.2%}, "
            f"reason={ref_selection.selection_reason[:50]}..."
        )

        return compiled

    def _compile_prompt(self, shot: Dict[str, Any], model: str) -> Dict[str, Any]:
        """Original Film Engine prompt compilation logic."""
        # ... existing implementation ...
        pass
```

### Usage in Orchestrator

```python
# In orchestrator_server.py

@app.post("/api/v26/render")
def render_scene_with_rolodex(request: RenderRequest):
    """V26 render with Canonical Rolodex integration."""
    from tools.film_engine import FilmEngineWithRolodex

    project_path = f"/path/to/pipeline_outputs/{request.project}"
    scene_id = request.scene_id

    # Initialize Film Engine with Rolodex
    film_engine = FilmEngineWithRolodex(project_path)

    # Load shots
    with open(f"{project_path}/shot_plan.json") as f:
        shot_plan = json.load(f)

    scene = next(s for s in shot_plan["scenes"] if s["scene_id"] == scene_id)

    # Render each shot
    for shot in scene["shots"]:
        # Compile with ref selection
        compiled = film_engine.compile_shot_with_refs(shot)

        # Pass to FAL
        fal_params = {
            "prompt": compiled["nano_prompt"],
            "image_urls": (
                compiled["_selected_character_refs"] +
                compiled["_selected_location_refs"]
            ),
            "resolution": _resolve_resolution(shot),
            ...
        }

        frame = fal.run("fal-ai/nano-banana-pro", fal_params)
        # ... rest of generation ...
```

---

## Option C: Full Integration with sceneController

Integrate into the existing `atlas_scene_controller.py` PreparedShot workflow.

### File: `tools/atlas_scene_controller.py`

```python
from tools.canonical_rolodex import CanonicalRolodex, select_best_refs

class SceneControllerV27(SceneController):
    """Scene Controller with Canonical Rolodex integration."""

    def __init__(self, project_path: str, *args, **kwargs):
        super().__init__(project_path, *args, **kwargs)
        self.rolodex = CanonicalRolodex(project_path)

    def prepare_shot(self, shot: Dict[str, Any]) -> PreparedShot:
        """Prepare shot with reference selection."""

        # Step 1: Resolve standard refs (existing logic)
        prepared = super().prepare_shot(shot)

        # Step 2: Select best refs from rolodex
        ref_selection = select_best_refs(
            shot,
            self.cast_map,
            self.story_bible,
            self.rolodex
        )

        # Step 3: Merge with standard resolution
        # Prefer rolodex-selected refs, fall back to standard resolution

        if ref_selection.selected_character_refs:
            prepared.character_refs = ref_selection.selected_character_refs

        if ref_selection.selected_location_refs:
            prepared.location_refs = ref_selection.selected_location_refs

        # Inject metadata
        prepared.metadata["_ref_selection_reason"] = ref_selection.selection_reason
        prepared.metadata["_ref_selection_confidence"] = ref_selection.confidence
        prepared.metadata["_fallback_used"] = ref_selection.fallback_used

        logger.info(
            f"PreparedShot {prepared.shot_id}: "
            f"{len(prepared.character_refs)} char refs, "
            f"{len(prepared.location_refs)} location refs, "
            f"confidence={ref_selection.confidence:.2%}"
        )

        return prepared

    def resolve_refs(self, shot: Dict[str, Any], cast_map: Dict) -> List[str]:
        """
        Resolve character references with rolodex.

        Fallback chain:
          1. Rolodex selected refs (highest priority)
          2. cast_map character_reference_url (existing)
          3. cast_map headshot_url (existing)
          4. Empty list (will proceed with degradation)
        """

        # Try rolodex first
        ref_selection = select_best_refs(shot, cast_map, self.story_bible, self.rolodex)

        if ref_selection.selected_character_refs:
            return ref_selection.selected_character_refs

        # Fall back to existing resolution
        return super().resolve_refs(shot, cast_map)
```

---

## Option D: Incremental Integration (Recommended for Existing Projects)

For existing projects, integrate incrementally without changing core logic.

### Strategy: Parallel Resolution

Keep existing resolution logic, but add rolodex as an optional enhancement layer.

```python
# In film_engine.py or orchestrator

def get_image_urls_for_shot(shot, cast_map, project_path):
    """
    Get image URLs for FAL call.

    Priority:
      1. If rolodex packs exist: use rolodex-selected refs
      2. Otherwise: fall back to existing resolution logic
    """

    # Try rolodex-based selection
    try:
        rolodex = CanonicalRolodex(project_path)
        with open(f"{project_path}/story_bible.json") as f:
            story_bible = json.load(f)

        ref_selection = select_best_refs(shot, cast_map, story_bible, rolodex)

        if ref_selection.selected_character_refs or ref_selection.selected_location_refs:
            return {
                "image_urls": (
                    ref_selection.selected_character_refs +
                    ref_selection.selected_location_refs
                ),
                "source": "canonical_rolodex",
                "confidence": ref_selection.confidence,
                "reason": ref_selection.selection_reason,
            }
    except Exception as e:
        logger.warning(f"Rolodex selection failed (non-blocking): {e}")

    # Fall back to existing resolution
    return {
        "image_urls": existing_resolution_logic(shot, cast_map),
        "source": "legacy_resolution",
        "confidence": 0.8,
    }
```

---

## Data Flow Diagram (With Rolodex)

```
shot_plan.json + cast_map.json + story_bible.json
    ↓
SceneController.prepare_shot(shot)
    ├── Step 1: Standard ref resolution (existing)
    └── Step 2: Rolodex ref selection (NEW)
            ├── Load CanonicalRolodex
            ├── Call select_best_refs()
            │   ├── Look up DP framing strategy
            │   ├── Get CharacterRefPack
            │   ├── Get LocationRefPack
            │   ├── Apply emotion overrides
            │   └── Apply fallback chain
            └── Return RefSelectionResult
    ↓
PreparedShot
    ├── shot_id
    ├── character_refs: [selected_refs] (from rolodex)
    ├── location_refs: [selected_refs] (from rolodex)
    ├── _ref_selection_confidence: 0.95
    └── _ref_selection_reason: "CU dialogue → headshot_front + detail_a"
    ↓
Film Engine compile_shot_with_refs()
    ├── Compile nano_prompt
    ├── Compile ltx_motion_prompt (with emotion override if needed)
    └── Return compiled + metadata
    ↓
FAL API Call
    {
        "prompt": compiled_nano_prompt,
        "image_urls": [character_refs + location_refs],
        "resolution": "2K",
        ...
    }
    ↓
Generated Frame + metadata
```

---

## Migration Path: V26 → V27

If you have an existing V26 project without rolodex packs:

### Step 1: Set Up Pack Structures (No Generation)

```bash
# Create empty pack directories
POST /api/v27/create-rolodex-packs/ravencroft_v22

# This creates:
# pipeline_outputs/ravencroft_v22/character_packs/{CHAR}/pack_manifest.json
# pipeline_outputs/ravencroft_v22/location_packs/{LOC}/pack_manifest.json
```

### Step 2: Populate Pack Images (Manual or Auto)

Option A: Manual (Quality Control)
```
User adds .jpg files to each pack directory manually
```

Option B: Extract from Existing Renders
```python
# Auto-generate from previously rendered frames (if available)
def extract_character_refs_from_renders(project_path):
    # Find existing first_frames/
    # Use dominant character region (via Vision API) as headshot_front
    # Generate variants (crop, scale) as headshot_34, profile, etc.
```

### Step 3: Run with Rolodex

```bash
# Validate completeness
GET /api/v27/validate-rolodex/ravencroft_v22

# Generate with rolodex
POST /api/v26/render {"project": "ravencroft_v22", "with_rolodex": true}
```

---

## Troubleshooting

### Issue: "Character pack missing"

```
Solution: Run create-rolodex-packs endpoint, then manually add images.
```

### Issue: "Confidence 0.60 (location pack missing)"

```
Solution: Add location pack. Generation proceeds but environment may drift.
```

### Issue: "Fallback used for EXPRESSION_VULNERABLE"

```
Solution: Add expression_vulnerable.jpg to character pack.
Otherwise, system will use expression_neutral or headshot_front.
```

### Issue: "Emotion detection failed, defaulting to neutral"

```
Solution: Add explicit emotion field to shot:
shot["emotion"] = "grief"
or add keywords to beat_summary:
shot["beat_summary"] = "Eleanor realizes her sister's death (grief)"
```

---

## Performance Considerations

- **Rolodex caching**: Packs are cached in memory (first load only)
- **Ref selection overhead**: ~50ms per shot (DPFramingProfile lookup + pack loading)
- **Total per-scene overhead**: ~1s for typical 10-shot scene
- **FAL call overhead**: ~5min per shot (unchanged; GPU-bound)

---

## Compliance with ATLAS Laws

- **C5**: Edit shots IN PLACE. Rolodex works with existing shot_plan.json structure. ✓
- **T2-SA-1..6**: Shot authority + ref caps. Selection respects shot types. ✓
- **T2-OR-9**: Project-local character refs. character_packs/ directory structure. ✓
- **T2-OR-11**: Location masters during first-frame gen. Included in location refs. ✓
- **Editorial Law 4**: Frame reuse + static character. B-roll context aware. ✓
