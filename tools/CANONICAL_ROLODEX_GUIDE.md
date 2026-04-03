# CANONICAL ROLODEX — Reference Pack Management System (V27.0)

## Overview

The Canonical Rolodex replaces the single-image-per-character and single-angle-per-location approach with **multi-image character reference packs** and **multi-angle location reference packs**.

This enables:
- **Character identity continuity** across different shot scales (ECU face vs. wide body shot)
- **Dialogue framing precision** via DP standards (OTS speaker profile, listener away)
- **Location environmental consistency** from multiple camera positions
- **Emotion-aware expression selection** (neutral vs. intense vs. vulnerable)
- **Narrative B-roll direction** (opening context, closing reflection, story details)

## Architecture

### Three Core Components

1. **CharacterRefPack** — 7 image types per character
2. **LocationRefPack** — 5 image types per location
3. **CanonicalRolodex** — Loader + selection engine
4. **DPFramingProfile** — Hollywood DP standards lookup table
5. **RefSelectionResult** — Selected refs + confidence + explanation

---

## Character Reference Packs

Each character gets 7 specialized images:

| Image Type | Usage | Fallback To |
|-----------|-------|-------------|
| `headshot_front` | ECU/CU dialogue, clean singles | N/A (REQUIRED) |
| `headshot_34` | MCU/MS dialogue, OTS speaker | headshot_front |
| `profile` | OTS listener, side angles | headshot_34 → headshot_front |
| `full_body` | Wide shots, establishing, action | headshot_34 → headshot_front |
| `expression_neutral` | Baseline emotional state | headshot_front |
| `expression_intense` | Anger, confrontation, conflict | headshot_front |
| `expression_vulnerable` | Grief, fear, sadness, intimate scenes | headshot_front |

### Directory Structure

```
pipeline_outputs/{project}/
└── character_packs/
    ├── ELEANOR_VOSS/
    │   ├── headshot_front.jpg
    │   ├── headshot_34.jpg
    │   ├── profile.jpg
    │   ├── full_body.jpg
    │   ├── expression_neutral.jpg
    │   ├── expression_intense.jpg
    │   ├── expression_vulnerable.jpg
    │   └── pack_manifest.json
    ├── THOMAS_BLACKWOOD/
    │   └── [same structure]
    └── MARGARET_HASTINGS/
        └── [same structure]
```

### Pack Manifest (Optional Metadata)

```json
{
  "character_name": "ELEANOR_VOSS",
  "created_at": "2026-03-16T10:30:00",
  "pack_version": "1.0",
  "image_specs": {
    "headshot_front": {
      "resolution": "2K",
      "background": "soft_neutral",
      "lighting": "key_3_4",
      "date_shot": "2026-03-12"
    },
    "expression_vulnerable": {
      "emotion": "grief",
      "intensity": 0.8,
      "note": "After diary discovery scene"
    }
  }
}
```

---

## Location Reference Packs

Each location gets 5 specialized images covering different camera positions:

| Image Type | Usage | Fallback To |
|-----------|-------|-------------|
| `master_wide` | Establishing, environment context | N/A (REQUIRED) |
| `reverse_wide` | 180° opposite angle, OTS B-side | master_wide |
| `detail_a` | Architectural detail, fireplace, desk | master_wide |
| `detail_b` | Secondary detail, window, bookshelf | detail_a → master_wide |
| `exterior` | Building exterior, what's outside window | master_wide |

### Directory Structure

```
pipeline_outputs/{project}/
└── location_packs/
    ├── DRAWING_ROOM/
    │   ├── master_wide.jpg
    │   ├── reverse_wide.jpg
    │   ├── detail_a.jpg
    │   ├── detail_b.jpg
    │   ├── exterior.jpg
    │   └── pack_manifest.json
    ├── LIBRARY/
    │   └── [same structure]
    └── HALL/
        └── [same structure]
```

---

## DP Framing Standards (Shot Type × Scene Type Matrix)

The Rolodex encodes Hollywood cinematography rules:

### DIALOGUE Scenes

| Shot Type | Primary Ref | Location Ref | Reason |
|-----------|-----------|-------------|--------|
| OTS_SPEAKER | headshot_34 | master_wide | Speaker facing camera, shows face + depth |
| OTS_LISTENER | profile | reverse_wide | Listener away, shows posture/reaction |
| CU (clean single) | headshot_front | detail_a | No shoulder intrusion, soft background |
| ECU (monologue) | headshot_front | detail_a | Eyes/mouth only, minimal background |
| MS (medium) | headshot_34 | master_wide | Shoulders visible, environment context |
| MWS (two-shot) | full_body | master_wide | Both characters, shows posture |
| REACTION (silent) | headshot_front | detail_b | Tight face, minimal environment |

### ACTION Scenes

| Shot Type | Primary Ref | Location Ref | Reason |
|-----------|-----------|-------------|--------|
| WS (wide) | full_body | master_wide | Full body motion, environment safety |
| MWS | full_body | master_wide | Torso + limbs, dynamic |
| MS | headshot_34 | master_wide | Torso motion, facial reaction |
| CU | headshot_front | detail_a | Face reaction during action |
| INSERT | full_body (context) | detail_a | Hands/object, action focus |

### INTIMATE Scenes (Emotion Override → vulnerable)

| Shot Type | Primary Ref | Location Ref | Override |
|-----------|-----------|-------------|----------|
| CU | headshot_front | detail_b | → expression_vulnerable |
| ECU | headshot_front | detail_a | → expression_vulnerable |
| MS | headshot_34 | master_wide | → expression_vulnerable |
| MWS | full_body | master_wide | → expression_vulnerable |

### ESTABLISHING Scenes

| Shot Type | Primary Ref | Location Ref | Reason |
|-----------|-----------|-------------|--------|
| EWS | full_body | master_wide | Extreme wide, location signature |
| WS | full_body | master_wide | Wide room, character in context |
| INSERT | full_body | detail_a | Detail (door, nameplate, artifact) |

### MONTAGE/TRANSITION

B-roll typically has **no character refs** (pure location/texture).

---

## Usage Examples

### Example 1: Load Rolodex + Select Refs for a Shot

```python
from tools.canonical_rolodex import CanonicalRolodex, select_best_refs
import json

# Initialize
project_path = "/path/to/ATLAS_CONTROL_SYSTEM/pipeline_outputs/ravencroft_v22"
rolodex = CanonicalRolodex(project_path)

# Load project data
with open(f"{project_path}/shot_plan.json") as f:
    shot_plan = json.load(f)

with open(f"{project_path}/cast_map.json") as f:
    cast_map = json.load(f)

with open(f"{project_path}/story_bible.json") as f:
    story_bible = json.load(f)

# Get a shot
shot = shot_plan["scenes"][0]["shots"][0]

# Select best references
result = select_best_refs(shot, cast_map, story_bible, rolodex)

print(f"Shot: {result.shot_id}")
print(f"Selected character refs: {result.selected_character_refs}")
print(f"Selected location refs: {result.selected_location_refs}")
print(f"Reason: {result.selection_reason}")
print(f"Confidence: {result.confidence:.2%}")
print(f"Fallback used: {result.fallback_used}")
```

Output:
```
Shot: 001_A
Selected character refs: ['/path/character_packs/ELEANOR_VOSS/headshot_34.jpg']
Selected location refs: ['/path/location_packs/DRAWING_ROOM/master_wide.jpg']
Reason: medium_close_up dialogue → headshot_34 + master_wide | ELEANOR_VOSS (neutral)
Confidence: 100%
Fallback used: False
```

### Example 2: Create Empty Pack Structures

```python
from tools.canonical_rolodex import (
    create_empty_character_pack_structure,
    create_empty_location_pack_structure
)

project_path = "pipeline_outputs/ravencroft_v22"

# Create for new characters
create_empty_character_pack_structure(project_path, "ELEANOR_VOSS")
create_empty_character_pack_structure(project_path, "THOMAS_BLACKWOOD")

# Create for new locations
create_empty_location_pack_structure(project_path, "DRAWING_ROOM")
create_empty_location_pack_structure(project_path, "LIBRARY")

# Now user manually adds .jpg files to each pack directory
```

### Example 3: Audit Rolodex Completeness

```python
from tools.canonical_rolodex import validate_rolodex_completeness
import json

project_path = "pipeline_outputs/ravencroft_v22"
required_characters = ["ELEANOR_VOSS", "THOMAS_BLACKWOOD"]
required_locations = ["DRAWING_ROOM", "LIBRARY"]

audit = validate_rolodex_completeness(project_path, required_characters, required_locations)

print(f"Complete: {audit['complete']}")
print(f"\nMissing required:")
for item in audit['missing_required']:
    print(f"  - {item}")

print(f"\nRecommendations:")
for rec in audit['recommendations']:
    print(f"  - {rec}")
```

Output:
```
Complete: False

Missing required:
  - THOMAS_BLACKWOOD (headshot_front)
  - LIBRARY (master_wide)

Recommendations:
  - Add headshot_front for THOMAS_BLACKWOOD
  - Add master_wide for LIBRARY
```

### Example 4: Handle Missing Packs (Non-Blocking)

```python
from tools.canonical_rolodex import CanonicalRolodex, select_best_refs

rolodex = CanonicalRolodex("pipeline_outputs/ravencroft_v22")

# This shot references a character whose pack is missing
shot = {
    "shot_id": "001_C",
    "shot_type": "close_up",
    "scene_type": "dialogue",
    "characters": ["MYSTERIOUS_STRANGER"],  # No pack exists
    "location": "DRAWING_ROOM"
}

result = select_best_refs(shot, {}, {}, rolodex)

# Result is still generated, but with degradation:
print(f"Confidence: {result.confidence:.2%}")  # 0.70 (pack_missing penalty)
print(f"Fallback used: {result.fallback_used}")  # True
print(f"Selected refs: {result.selected_character_refs}")  # []

# Generation proceeds, but operator is warned
```

### Example 5: Emotion-Aware Expression Selection

```python
from tools.canonical_rolodex import select_best_refs, ShotType, SceneType

# Intimate grief scene
shot = {
    "shot_id": "006_A",
    "shot_type": "close_up",
    "scene_type": "intimate",  # Triggers emotion override
    "characters": ["ELEANOR_VOSS"],
    "location": "LIBRARY",
    "beat_summary": "Eleanor discovers the truth about her sister's death. Moment of realization and grief."
}

result = select_best_refs(shot, cast_map, story_bible, rolodex)

# Result: System detected grief emotion + intimate scene
# Override applied: expression_vulnerable selected (not headshot_front)
print(f"Emotion override: {result.emotion_override}")  # "vulnerable"
print(f"Reason: {result.selection_reason}")
# Output: "close_up intimate → expression_vulnerable + detail_b | ELEANOR_VOSS (grief)"
```

### Example 6: B-Roll Narrative Context

```python
from tools.canonical_rolodex import select_best_refs

# Opening B-roll of scene (what leads into the scene)
shot = {
    "shot_id": "005_B",
    "shot_type": "wide_shot",
    "scene_type": "montage",
    "characters": [],  # B-roll: no characters
    "location": "DRAWING_ROOM",
    "is_broll": True,
    "shot_index_in_scene": 0,
    "scene_shot_count": 8
}

result = select_best_refs(shot, cast_map, story_bible, rolodex)

print(f"B-roll context: {result.broll_context}")  # BRollContext.SCENE_OPENING
# System adds to prompt: "Show what leads INTO the scene (servants preparing room)"
```

---

## Integration with ATLAS Pipeline

### Pre-Generation Setup (Optional)

```bash
# 1. Create empty pack structures
python3 tools/canonical_rolodex.py ravencroft_v22 create-char-pack "ELEANOR_VOSS"
python3 tools/canonical_rolodex.py ravencroft_v22 create-char-pack "THOMAS_BLACKWOOD"
python3 tools/canonical_rolodex.py ravencroft_v22 create-loc-pack "DRAWING_ROOM"
python3 tools/canonical_rolodex.py ravencroft_v22 create-loc-pack "LIBRARY"

# 2. User manually adds .jpg images to pack directories

# 3. Audit completeness before generation
python3 tools/canonical_rolodex.py ravencroft_v22 audit characters.json locations.json
```

### During Generation (Film Engine Integration)

```python
# In orchestrator_server.py or film_engine.py

from tools.canonical_rolodex import CanonicalRolodex, select_best_refs

def generate_first_frames(project_path, scene_id):
    rolodex = CanonicalRolodex(project_path)

    for shot in scene_shots:
        # Select best references
        result = select_best_refs(shot, cast_map, story_bible, rolodex)

        # Inject into Film Engine context
        shot["_selected_character_refs"] = result.selected_character_refs
        shot["_selected_location_refs"] = result.selected_location_refs
        shot["_ref_selection_reason"] = result.selection_reason

        # Pass to FAL
        fal_params = {
            "prompt": compiled_prompt,
            "image_urls": result.selected_character_refs + result.selected_location_refs,
            "resolution": "2K" if shot_type in [ECU, CU] else "1K",
            # ... other params
        }

        frame = fal.run(fal_params)
```

---

## Non-Blocking Design (ATLAS V27 Law T2-OR-1)

The Canonical Rolodex is **non-blocking**. Missing packs do not halt generation:

| Scenario | Behavior | Confidence Penalty |
|----------|----------|-------------------|
| Character pack fully loaded | Generate with requested refs | 1.0 |
| Some optional refs missing | Use fallback chain | 0.85-0.95 |
| Required (headshot_front) only | Generate with fallback | 0.75 |
| Entire character pack missing | Log warning, proceed | 0.70 |
| Location pack fully loaded | Generate with requested refs | 1.0 |
| Location pack missing | Log warning, proceed | 0.60 |

**Fallback Chain** (in priority order):
1. Requested ref type exists → Use it
2. expression_neutral exists → Use it
3. headshot_34 exists → Use it
4. headshot_front exists (required) → Use it
5. All missing → Empty list (continue generation)

---

## Data Flow Diagram

```
shot_plan.json
    ↓
select_best_refs(shot, cast_map, story_bible, rolodex)
    ├── Parse shot_type + scene_type
    ├── Look up DPFramingProfile strategy
    ├── For each character:
    │   ├── Load CharacterRefPack
    │   ├── Get primary ref type from strategy
    │   ├── Apply emotion override (if intimate/grief/fear)
    │   ├── Apply fallback chain (if missing)
    │   └── Append to selected_character_refs
    ├── For location:
    │   ├── Load LocationRefPack
    │   ├── Get location ref type from strategy
    │   ├── Apply fallback chain (if missing)
    │   └── Append to selected_location_refs
    ├── If B-roll: determine narrative context
    └── Return RefSelectionResult
            ↓
    RefSelectionResult
        ├── selected_character_refs: [paths]
        ├── selected_location_refs: [paths]
        ├── selection_reason: "CU dialogue → headshot_front + detail_a"
        ├── confidence: 0.95
        ├── fallback_used: False
        └── emotion_override: "vulnerable"
            ↓
    FAL API Call
        image_urls: result.selected_character_refs + result.selected_location_refs
```

---

## Laws & Compliance

From ATLAS V27 CLAUDE.md:

- **C5**: NEVER rebuild scenes. Edit shots IN PLACE. ✓ Rolodex preserves existing pack structure.
- **T2-SA-1..6**: Shot authority determines ref caps. ✓ Selection respects shot types (ECU=3 refs, wide=2 refs).
- **T2-OR-9**: Character refs must be project-local `*_CHAR_REFERENCE.jpg`. ✓ Maps to character_packs/ structure.
- **T2-OR-11**: Location masters during first-frame generation. ✓ Includes location_masters/ fallback.
- **Editorial Law 4**: Frame reuse requires blocking + static character. ✓ B-roll narrative context aware.
- **CPC Laws**: Creative Prompt Compiler integration. ✓ Non-blocking imports supported.

---

## Testing

The module includes a command-line interface for testing:

```bash
# Audit rolodex completeness
python3 tools/canonical_rolodex.py ravencroft_v22 audit characters.json locations.json

# Create pack structures
python3 tools/canonical_rolodex.py ravencroft_v22 create-char-pack "ELEANOR_VOSS"
python3 tools/canonical_rolodex.py ravencroft_v22 create-loc-pack "DRAWING_ROOM"
```

---

## Future Extensions

1. **Wardrobe packs** (look_id variants) — expand from character to character+look combinations
2. **Seasonal/aging packs** — age progression over multiple episodes
3. **Multi-ethnic expression profiles** — culture-aware emotion expression
4. **Production cost estimates** — ref generation cost per shot
5. **Vision embeddings** — DINOv2 similarity matching for best ref within pack
6. **Voice/dialogue sync** — expression matching to audio phonemes
7. **Archival search** — find similar packs across projects (studio-wide consistency)
