# ATLAS V21.10 — Continuity Store Integration Guide

## Overview

`continuity_store.py` provides persistent, disk-backed continuity state for ATLAS filmmaking pipeline. Unlike the in-memory `SceneState` in `continuity_gate.py`, the Continuity Store survives across pipeline runs, enabling:

- **Durability**: State persists to `continuity_state.json` after each shot generation
- **History Tracking**: Full append-only log of state transitions (for rollback/analysis)
- **Cross-Run Validation**: Subsequent runs can validate shots against stored state
- **Integration**: Seamless compatibility layer with existing `continuity_gate.py`

## Core Classes

### ContinuityStore
Main persistence engine. One instance per project.

```python
from tools.continuity_store import ContinuityStore

# Initialize for a project
store = ContinuityStore("/path/to/project/")

# Update store after generating shot
store.update_from_shot(shot)  # Reads shot.state_out

# Save to disk (atomic write)
store.save()

# Load from disk on startup
store.load()
```

### SceneSnapshot
Complete state for a scene.

```python
@dataclass
class SceneSnapshot:
    scene_id: str
    characters: Dict[str, CharacterSnapshot]  # Per-character state
    props: Dict[str, PropState]               # Props in scene
    camera: CameraState                       # Camera axis, lens, distance
    environment: EnvironmentState             # Color grade, lighting, weather
    last_shot_id: Optional[str]               # Most recent shot
    shot_count: int
    timestamp: str
```

### CharacterSnapshot
Per-character pose/emotion/position state.

```python
@dataclass
class CharacterSnapshot:
    name: str
    pose: str                    # standing, sitting, kneeling, lying, walking, dancing, fallen
    emotion: str                 # grief, determined, fearful, relieved, confused, angry
    emotion_intensity: int       # 0-10 scale
    eyeline: Optional[str]       # Target character/object
    wardrobe_id: Optional[str]   # Look ID for scene
    position: str                # center, left, right, background, foreground, doorway
    facing: str                  # camera, left, right, away, profile_left, profile_right
    hands: str                   # free, holding_X, clasped, praying, covering_face
```

### StateDiff
Structured difference between two snapshots.

```python
@dataclass
class StateDiff:
    pose_changes: Dict[str, Tuple[str, str]]           # char → (from, to)
    emotion_changes: Dict[str, Tuple[int, int]]        # char → (from_intensity, to_intensity)
    position_changes: Dict[str, Tuple[str, str]]       # char → (from, to)
    facing_changes: Dict[str, Tuple[str, str]]         # char → (from, to)
    eyeline_changes: Dict[str, Tuple[Optional[str], Optional[str]]]
    props_added: List[str]
    props_removed: List[str]
    props_moved: Dict[str, Tuple[str, str]]            # prop → (from_pos, to_pos)
    camera_changed: bool
    environment_changed: bool
    
    @property
    def summary(self) -> str:
        # Human-readable: "Poses: EVELYN: standing→kneeling | Emotions: EVELYN: 7→9"
```

### Violation
Continuity breach detected during validation.

```python
@dataclass
class Violation:
    type: str                  # POSE_MISMATCH, EMOTION_JUMP, WARDROBE_DRIFT, PROP_MISSING, POSITION_TELEPORT
    severity: str              # BLOCKING, WARNING
    character: Optional[str]
    expected: Optional[str]    # What was expected
    actual: Optional[str]      # What was found
    message: str               # Human-readable explanation
```

## Integration with orchestrator_server.py

### 1. Initialize on Project Load

```python
# In project initialization (e.g., POST /api/v16/ui/bundle/{project})
from tools.continuity_store import create_continuity_store

project_path = f"pipeline_outputs/{project}"
continuity_store = create_continuity_store(project_path)
continuity_store.load()  # Loads existing state if available
```

### 2. Update After Shot Generation

```python
# In generate-first-frames or render-videos, after shot is created
if shot.get("state_out"):
    continuity_store.update_from_shot(shot)
    continuity_store.save()  # Atomic write to continuity_state.json
```

### 3. Pre-Generation Validation

```python
# In LOA pre_generation_gate() or custom validation
violations = []
for shot in shots:
    shot_violations = continuity_store.validate_continuity(shot)
    violations.extend(shot_violations)

if violations:
    logger.warning(f"Continuity violations: {len(violations)}")
    # Log, but don't block (advisory)
```

### 4. Compatibility with continuity_gate.py

```python
# Convert from continuity_gate.py SceneState to ContinuityStore
from atlas_agents.continuity_gate import SceneState

scene_state = SceneState(...)  # From continuity_gate
continuity_store.import_from_scene_state(scene_state.to_dict())

# Export back to SceneState format for validation
scene_state_dict = continuity_store.export_to_scene_state(scene_id)
```

## API Reference

### ContinuityStore Methods

#### update_from_shot(shot: Dict) → bool
Read `state_out` from shot and update store.
```python
shot = {
    "shot_id": "001_001",
    "scene_id": "001",
    "state_out": {
        "characters": {
            "EVELYN": {
                "pose": "standing",
                "emotion": "determined",
                "emotion_intensity": 7,
                "position": "center",
                "facing": "camera"
            }
        },
        "props": {}
    }
}
continuity_store.update_from_shot(shot)  # Returns True
```

#### get_state_before_shot(scene_id: str, shot_id: Optional[str]) → SceneSnapshot
Retrieve state that should exist before entering a shot.
```python
state = continuity_store.get_state_before_shot("001", "001_002")
print(state.characters["EVELYN"].pose)  # "standing" (from previous shot)
```

#### validate_continuity(shot: Dict) → List[Violation]
Check if shot's `state_in` matches stored state.
```python
shot = {
    "shot_id": "001_002",
    "scene_id": "001",
    "state_in": {
        "characters": {
            "EVELYN": {
                "pose": "standing",
                "emotion": "determined",
                "emotion_intensity": 7,
                "position": "center"
            }
        }
    }
}
violations = continuity_store.validate_continuity(shot)
# Returns [] if valid, or list of Violation objects
```

#### get_state_diff(scene_id: str, shot_id_a: Optional[str], shot_id_b: str) → Optional[StateDiff]
Get structured diff between states around two shots.
```python
diff = continuity_store.get_state_diff("001", "001_001", "001_002")
print(diff.summary)  # "No changes" or structured changes
```

#### save() → bool
Save state to `continuity_state.json` (atomic write with tempfile).
```python
if continuity_store.save():
    logger.info("State persisted")
else:
    logger.error("Save failed")
```

#### load() → bool
Load state from `continuity_state.json`.
```python
if continuity_store.load():
    logger.info(f"Loaded state for {len(continuity_store._state)} scenes")
else:
    logger.debug("No existing state file")
```

#### rollback_to_shot(scene_id: str, shot_id: str) → bool
Revert scene state to what it was after a specific shot.
```python
if continuity_store.rollback_to_shot("001", "001_005"):
    logger.info("Rolled back to after shot 001_005")
```

#### get_history(scene_id: str) → List[StateTransition]
Get full state change log for a scene.
```python
history = continuity_store.get_history("001")
for trans in history:
    print(f"{trans.shot_id}: {trans.changes.summary}")
```

#### clear_scene(scene_id: str) → bool
Reset state for a scene (for regeneration).
```python
continuity_store.clear_scene("001")  # Clears state and history
```

#### import_from_scene_state(scene_state: Dict) → bool
Convert from `continuity_gate.py` SceneState format.
```python
scene_state = {
    "scene_id": "001",
    "characters": {...},
    "props": {...},
    "camera": {...},
    "environment": {...}
}
continuity_store.import_from_scene_state(scene_state)
```

#### export_to_scene_state(scene_id: str) → Dict[str, Any]
Export as SceneState dict for compatibility.
```python
scene_state_dict = continuity_store.export_to_scene_state("001")
# Returns {"characters": {...}, "props": {...}, "camera": {...}, "environment": {...}}
```

## Data Persistence

### continuity_state.json
Stored at `pipeline_outputs/{project}/continuity_state.json`.

```json
{
  "project": "/path/to/project",
  "timestamp": "2026-03-04T14:30:00.123456",
  "state": {
    "001": {
      "scene_id": "001",
      "characters": {
        "EVELYN": {
          "name": "EVELYN",
          "pose": "kneeling",
          "emotion": "grieving",
          "emotion_intensity": 8,
          "eyeline": "ALTAR",
          "wardrobe_id": "EVELYN_S001_DARK_DARK",
          "position": "center",
          "facing": "away",
          "hands": "clasped"
        }
      },
      "props": {
        "CANDLE": {
          "name": "CANDLE",
          "position": "altar",
          "owner": null,
          "visible": true,
          "description": "flickering candle"
        }
      },
      "camera": {
        "axis": "central",
        "last_lens": "85mm",
        "last_angle": "medium",
        "last_distance": 8.5,
        "pan_direction": null
      },
      "environment": {
        "color_grade": "desaturated",
        "lighting": "candlelit",
        "time_of_day": "night",
        "weather": "clear",
        "atmosphere": "reverent"
      },
      "last_shot_id": "001_005",
      "shot_count": 5,
      "timestamp": "2026-03-04T14:30:00.123456"
    }
  },
  "history_count": 5
}
```

### continuity_history.jsonl (Optional)
Append-only line-delimited JSON log of all state transitions.

```jsonl
{"shot_id": "001_001", "timestamp": "2026-03-04T14:29:00", "changes": {...}, "violations": []}
{"shot_id": "001_002", "timestamp": "2026-03-04T14:29:05", "changes": {...}, "violations": []}
{"shot_id": "001_003", "timestamp": "2026-03-04T14:29:10", "changes": {...}, "violations": []}
```

## Violation Types

| Type | Severity | When | Auto-Fix |
|------|----------|------|----------|
| POSE_MISMATCH | BLOCKING | Character pose doesn't match stored state | Insert MWS connector shot |
| EMOTION_JUMP | WARNING | >3-point emotion intensity change | Log, don't block |
| WARDROBE_DRIFT | BLOCKING | Wardrobe ID changed unexpectedly | Regenerate with locked wardrobe |
| PROP_MISSING | WARNING | Prop expected but not in stored state | Log, don't block |
| POSITION_TELEPORT | WARNING | Character position changed unexpectedly | Log (may be motivated by action) |

## Integration Examples

### Example 1: Add to generate-first-frames endpoint

```python
# In orchestrator_server.py, POST /api/auto/generate-first-frames

from tools.continuity_store import create_continuity_store

@app.post("/api/auto/generate-first-frames")
def generate_first_frames(request_data):
    project = request_data["project"]
    project_path = f"pipeline_outputs/{project}"
    
    # Initialize continuity store
    continuity_store = create_continuity_store(project_path)
    continuity_store.load()
    
    # Generate frames...
    for shot in shots:
        # ... frame generation logic ...
        
        # Update continuity state
        if shot.get("state_out"):
            continuity_store.update_from_shot(shot)
    
    # Persist to disk
    continuity_store.save()
    
    return {"status": "ok", "frames_generated": len(shots)}
```

### Example 2: Validation in LOA

```python
# In atlas_agents/logical_oversight_agent.py, pre_generation_gate()

def pre_generation_gate(shots, scene_manifest=None, continuity_store=None):
    """Pre-generation validation gate with continuity check."""
    
    results = []
    
    for shot in shots:
        violations = []
        
        # ... existing validation ...
        
        # Continuity check (if store available)
        if continuity_store:
            cont_violations = continuity_store.validate_continuity(shot)
            violations.extend(cont_violations)
        
        results.append({
            "shot_id": shot["shot_id"],
            "violations": [v.to_dict() for v in violations],
        })
    
    return results
```

### Example 3: Rollback on regeneration

```python
# When user regenerates a scene from shot X onwards

continuity_store = create_continuity_store(project_path)
continuity_store.load()

# Rollback to the shot before regeneration
continuity_store.rollback_to_shot(scene_id, previous_shot_id)

# Clear subsequent shots' state
continuity_store.clear_scene(scene_id)

# Now regenerate from this point
# ... generation logic ...

# Store will be rebuilt as shots are generated
continuity_store.save()
```

## Logging

All module actions logged with `[CONTINUITY_STORE]` prefix:

```
[CONTINUITY_STORE] INFO: Updated continuity for 001_001 in scene 001: Poses: EVELYN: standing→kneeling
[CONTINUITY_STORE] INFO: Saved continuity state to /path/to/continuity_state.json
[CONTINUITY_STORE] DEBUG: Retrieved state before shot 001_002 in scene 001
[CONTINUITY_STORE] DEBUG: Validation for 001_002: 2 violations found
[CONTINUITY_STORE] WARNING: POSE_MISMATCH for MARGARET: expected=standing, actual=sitting
```

## Testing

Comprehensive unit tests available in module:

```bash
python3 tools/continuity_store.py

# Output:
# ✓ Store created
# ✓ Snapshot created with 1 chars, 1 props
# ✓ Serialization round-trip successful
# ✓ Diff computed
# ✓ Shot update successful
# ✓ Validation complete
# ✓ Save/load successful
# ✓ SceneState compatibility working
# ALL TESTS PASSED
```

## DO NOT RE-BREAK (V21.10 Continuity Store Rules)

1. **ContinuityStore uses atomic writes** — tempfile + os.replace for safety
2. **State persists to disk after EVERY shot** — not batched, not cached, ALWAYS persist
3. **SceneSnapshot is immutable after save** — no mutations without update_from_shot()
4. **Violations are advisory, not blocking** — NEVER make continuity validation a hard gate
5. **History is append-only** — rollback truncates, never overwrites
6. **Export/import maintains compatibility** — ContinuityStore ↔ SceneState bidirectional
7. **Logging uses [CONTINUITY_STORE] prefix** — all 8 logging sites must use this prefix
8. **Missing/corrupt state files handled gracefully** — load() returns False, doesn't crash
9. **clear_scene() clears both state and history** — clean slate for regeneration
10. **CharacterSnapshot fields match cinematographic vocabulary** — pose, emotion, position, facing, hands

---

**Version:** V21.10  
**Status:** PRODUCTION READY  
**Lines:** 878  
**Last Updated:** 2026-03-04
