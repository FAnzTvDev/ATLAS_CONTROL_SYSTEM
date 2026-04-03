# Canonical Rolodex — Quick Reference Card

## Directory Structure

```
pipeline_outputs/{project}/
├── character_packs/
│   └── {CHARACTER_NAME}/
│       ├── headshot_front.jpg (REQUIRED)
│       ├── headshot_34.jpg
│       ├── profile.jpg
│       ├── full_body.jpg
│       ├── expression_neutral.jpg
│       ├── expression_intense.jpg
│       ├── expression_vulnerable.jpg
│       └── pack_manifest.json
└── location_packs/
    └── {LOCATION_ID}/
        ├── master_wide.jpg (REQUIRED)
        ├── reverse_wide.jpg
        ├── detail_a.jpg
        ├── detail_b.jpg
        ├── exterior.jpg
        └── pack_manifest.json
```

## Character Image Types

| Type | Shot Scale | Typical Use | Fallback |
|------|-----------|------------|----------|
| `headshot_front` | ECU/CU | Clean singles, dialogue | N/A (REQUIRED) |
| `headshot_34` | MCU/MS | Over-the-shoulder, med shots | → headshot_front |
| `profile` | OTS listener | Side angle, away angle | → headshot_34 → front |
| `full_body` | WS/EWS | Wide shots, action, establishing | → headshot_34 → front |
| `expression_neutral` | Any | Baseline state | → headshot_front |
| `expression_intense` | Any | Anger, confrontation, conflict | → headshot_front |
| `expression_vulnerable` | Any | Grief, fear, sadness, intimate | → headshot_front |

## Location Image Types

| Type | Coverage | Typical Use | Fallback |
|------|----------|------------|----------|
| `master_wide` | Anchor | Establishing, environment ref | N/A (REQUIRED) |
| `reverse_wide` | Opposite angle | OTS B-side, reaction coverage | → master_wide |
| `detail_a` | Arch/prop detail | Fireplace, desk, architectural | → master_wide |
| `detail_b` | Secondary detail | Window, bookshelf, painting | → detail_a → master |
| `exterior` | Outside view | What's beyond location | → master_wide |

## DP Framing Rules (Shot Type × Scene Type)

### DIALOGUE Scenes

```
OTS SPEAKER   → headshot_34 + master_wide
OTS LISTENER  → profile + reverse_wide
CU (clean)    → headshot_front + detail_a
ECU           → headshot_front + detail_a
MS            → headshot_34 + master_wide
MWS (2-shot)  → full_body + master_wide
REACTION      → headshot_front + detail_b
```

### ACTION Scenes

```
WS      → full_body + master_wide
MWS     → full_body + master_wide
MS      → headshot_34 + master_wide
CU      → headshot_front + detail_a
INSERT  → full_body + detail_a
```

### INTIMATE Scenes (Emotion Override → expression_vulnerable)

```
CU      → expression_vulnerable + detail_b
ECU     → expression_vulnerable + detail_a
MS      → headshot_34 + master_wide (→ vulnerable)
MWS     → full_body + master_wide (→ vulnerable)
```

### ESTABLISHING Scenes

```
EWS     → full_body + master_wide
WS      → full_body + master_wide
INSERT  → full_body + detail_a
```

## Emotion Detection & Overrides

**Auto-detect from:**
- `shot.emotion` (explicit)
- `shot.beat_summary` (keywords)
- `shot.dialogue_text` (keywords)

**Keywords:**
- grief: "grief", "mourn", "loss", "weeping", "devastated"
- fear: "fear", "terror", "dread", "scared", "horrified"
- anger: "anger", "rage", "furious", "wrathful", "hostile"
- sadness: "sadness", "sad", "melancholy", "sorrow", "dejected"
- vulnerable: "vulnerable", "fragile", "broken", "desperate"
- confrontation: "confront", "challenge", "accuse", "demand"

**Intimate Scene Override:**
- If `scene_type == "intimate"` → Override to `expression_vulnerable`
- Applies regardless of shot type

## B-roll Context Determination

**Auto-detect from:**
- `shot.shot_index_in_scene` (position)
- `shot.scene_shot_count` (total)
- `shot.beat_summary` (keywords)

| Index | Context | Meaning |
|-------|---------|---------|
| First (0-1) | SCENE_OPENING | What leads INTO scene |
| Last (n-2 to n) | SCENE_CLOSING | What carries OUT |
| Middle + keywords | CONTEXT | Story-relevant details |
| Middle + no keywords | ATMOSPHERIC | Pure mood/texture |

**Story Keywords:** "packing", "arriving", "leaving", "letter", "photo", "portrait", "heirloom", "servant", "preparing"

## Command Line Usage

```bash
# Create empty character pack
python3 tools/canonical_rolodex.py /path/to/project create-char-pack "CHARACTER_NAME"

# Create empty location pack
python3 tools/canonical_rolodex.py /path/to/project create-loc-pack "LOCATION_ID"

# Audit rolodex completeness
python3 tools/canonical_rolodex.py /path/to/project audit characters.json locations.json
```

## Python API

### Initialize Rolodex

```python
from tools.canonical_rolodex import CanonicalRolodex

rolodex = CanonicalRolodex("/path/to/project")
```

### Load Packs

```python
char_pack = rolodex.get_character_pack("ELEANOR_VOSS")
loc_pack = rolodex.get_location_pack("DRAWING_ROOM")

# Returns None if missing (non-blocking)
if char_pack and char_pack.has_required():
    headshot = char_pack.headshot_front
```

### Select Refs for Shot

```python
from tools.canonical_rolodex import select_best_refs

result = select_best_refs(shot, cast_map, story_bible, rolodex)

# Returns RefSelectionResult:
result.selected_character_refs    # List of file paths
result.selected_location_refs      # List of file paths
result.selection_reason            # String explanation
result.confidence                  # 0.0-1.0 float
result.fallback_used               # Boolean
result.emotion_override            # "vulnerable" or None
result.broll_context               # BRollContext enum or None
```

### Validate Rolodex

```python
from tools.canonical_rolodex import validate_rolodex_completeness

audit = validate_rolodex_completeness(
    "/path/to/project",
    ["ELEANOR_VOSS", "THOMAS_BLACKWOOD"],
    ["DRAWING_ROOM", "LIBRARY"]
)

if audit["complete"]:
    print("Ready for generation")
else:
    for rec in audit["recommendations"]:
        print(rec)
```

## Confidence Scoring

| Scenario | Confidence | Fallback |
|----------|-----------|----------|
| All requested refs exist | 1.0 | No |
| Some optional types missing | 0.90-0.99 | Yes |
| Using required fallback | 0.75-0.85 | Yes |
| Entire character pack missing | 0.70 | Yes |
| Location pack missing | 0.60 | Yes |
| All missing | 0.0 | Yes |

**Generation proceeds at all confidence levels (non-blocking)**

## Key Laws (ATLAS V27)

| Law | Applies |
|-----|---------|
| C5 | Edit shots IN PLACE (preserve shot_plan.json) |
| T2-SA-1..6 | Shot authority + ref caps (respected) |
| T2-OR-9 | Project-local character refs (character_packs/) |
| T2-OR-11 | Location masters during first-frame gen (included) |
| Editorial 4 | Frame reuse + static character (B-roll aware) |
| T2-OR-1 | Non-blocking: missing packs logged, generation proceeds |

## Troubleshooting Checklist

```
☐ Character pack exists?
  → python3 tools/canonical_rolodex.py project create-char-pack NAME
☐ headshot_front.jpg exists?
  → Manually add image to pack directory (required fallback)
☐ Location pack exists?
  → python3 tools/canonical_rolodex.py project create-loc-pack LOCATION
☐ master_wide.jpg exists?
  → Manually add image to pack directory (required fallback)
☐ Emotion detected correctly?
  → Check shot.beat_summary for keywords or add shot.emotion
☐ B-roll context correct?
  → Set is_broll: true, check shot_index_in_scene
☐ Confidence too low (< 0.8)?
  → Add optional image types (expression_*, detail_*, reverse_*)
☐ Fallback used?
  → Check result.fallback_details for which types fell back
```

## DP Framing Rationale Examples

**Why OTS_SPEAKER uses headshot_34 (3/4 view)?**
- Speaker is facing camera
- 3/4 view shows face + reveals depth/shoulder context
- Emotionally readable without full frontal (which feels direct/confrontational)
- Industry standard for dialogue coverage

**Why OTS_LISTENER uses profile?**
- Listener is partially facing away
- Profile shows posture/reaction clearest
- Maintains 180° rule continuity with OTS A
- Emphasizes listening/receiving vs. speaking

**Why CU (clean single) uses detail background (not master)?**
- Tight framing removes environmental context
- Detail (fireplace, lamp, architectural) provides soft, compositional background
- Prevents spatial discontinuity vs. wide shots in scene
- Keeps focus on face, not environment

**Why INTIMATE scenes override to expression_vulnerable?**
- Emotional scenes require nuanced facial expression
- Vulnerable pack image shot with emotion coaching
- Generic headshot_front misses grief/fear subtlety
- Industry standard: "push in on emotion" in intimate moments

## Integration Checklist

```
☐ Standalone audit mode (no code changes)
  → python3 tools/canonical_rolodex.py project audit chars.json locs.json

☐ Film Engine integration
  → Import select_best_refs in film_engine.py
  → Call before FAL API, inject image_urls

☐ SceneController integration
  → Modify resolve_refs() to try rolodex first
  → Fall back to existing resolution

☐ Pre-generation validation endpoint
  → POST /api/v27/validate-rolodex/{project}
  → Audit before generation starts

☐ Pack creation endpoint
  → POST /api/v27/create-rolodex-packs/{project}
  → Auto-generate empty structures
```

## Performance Tips

1. **Cache rolodex instance** — Don't create new instance per shot
2. **Load packs once** — Use rolodex.get_character_pack() (auto-caches)
3. **Batch validate** — Validate all shots before generation, not per-shot
4. **Log warnings only** — Don't spam logs on missing optional images

## Testing

```bash
# Run full test suite
python3 -m pytest tools/test_canonical_rolodex.py -v

# Run specific test
pytest tools/test_canonical_rolodex.py::TestSelectBestRefs::test_dialogue_ots_speaker -v

# Check imports only
python3 -c "from tools.canonical_rolodex import *; print('✓ OK')"
```

## Files

| File | Purpose |
|------|---------|
| `canonical_rolodex.py` | Main module (2100+ lines) |
| `test_canonical_rolodex.py` | Test suite (50+ tests) |
| `CANONICAL_ROLODEX_README.md` | Quick start guide |
| `CANONICAL_ROLODEX_GUIDE.md` | Detailed reference + examples |
| `CANONICAL_ROLODEX_INTEGRATION.md` | Code integration examples |
| `CANONICAL_ROLODEX_QUICK_REFERENCE.md` | This file |

---

**Status**: V27.0 Production Ready | **Tests**: All passing | **Integration**: Ready
