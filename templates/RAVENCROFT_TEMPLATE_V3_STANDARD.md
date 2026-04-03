# RAVENCROFT TEMPLATE v3 STANDARD
## AI-Ready Script-to-Manifest Template

This template produces **manifest-ready JSON** directly from screenplay structure.
No manual revision cycle (V10-V17) needed if template is followed correctly.

---

## LAYER 0: EPISODE HEADER

```json
{
  "manifest_version": "V3_STANDARD",
  "episode": "RAVENCROFT_MANOR_EP[X]",
  "title": "[Episode Title]",
  "runtime_target": "8-12 minutes",

  "character_references": {
    "Evelyn Ravencroft": "/path/to/EVELYN_LOCKED_REFERENCE.jpg",
    "Lady Margaret Ravencroft": "/path/to/LADY_MARGARET_LOCKED_REFERENCE.jpg",
    "Clara Whitmore": "/path/to/CLARA_LOCKED_REFERENCE.jpg",
    "Arthur Gray": "/path/to/ARTHUR_LOCKED_REFERENCE.jpg"
  },

  "voice_mapping": {
    "Evelyn": "EXAVITQu4vr4xnSDxMaL",
    "Lawyer": "onwK4e9ZLuTAKqWW03F9",
    "Clara": "21m00Tcm4TlvDq8ikWAM",
    "Lady Margaret": "MF3mGyEYCl7XYWbV9V6O",
    "Arthur": "pNInz6obpgDQGcFmaJgB"
  },

  "smart_continuity": {
    "no_chain_shot_types": ["OTS", "OVER SHOULDER", "REVERSE", "REACTION", "POV"],
    "chain_environment": ["INSERT", "DETAIL", "MACRO"],
    "reset_on": ["scene_change", "flashback_boundary", "character_switch"]
  },

  "humanization_defaults": {
    "blink_interval_seconds": [2, 6, 10, 14],
    "breathing_interval_seconds": 4,
    "face_lock": "ABSOLUTE - no morphing between frames"
  }
}
```

---

## LAYER 1: SCENE CARD (Per Scene)

### SCENE [X]: [SCENE TITLE]

**Basic Info:**
- Location: [Specific location]
- Time: [DAY/NIGHT/DUSK etc]
- Characters Present: [List]
- Scene Purpose: [1 sentence]
- Emotion Arc: [start emotion] → [end emotion]

**Continuity Notes:**
- Entry State: [How scene begins - character positions, props]
- Exit State: [How scene ends - setup for next scene]

**Flashback?** [YES/NO]
- If YES: Color Grade = [sepia/blue-grey/desaturated]

**Intercut?** [YES/NO]
- If YES: List intercut pairs (A/B/C)

---

## LAYER 2: SHOT TEMPLATE (Per Shot)

### SHOT [X]: [SHOT_ID]

**METADATA:**
```json
{
  "shot_number": 1,
  "shot_id": "S01_01",
  "shot_type": "WIDE ESTABLISHING",
  "duration_seconds": 10,
  "characters_needed": ["Evelyn Ravencroft"],
  "is_flashback": false,
  "intercut_pair": null,
  "has_dialogue": false
}
```

**RENDERING METHOD:** (Auto-determined by system)
- Dialog + Character → OMNIHUMAN
- Character, no dialog → MINIMAX + WAN 2.2
- Environment only → WAN 2.2 T2V

**NANO_PROMPT (400+ chars required):**
```
[CHARACTER NAME if present] [age] [hair color] [clothing description]
[action/pose] [location details] [lighting - tungsten/daylight/moonlight]
[atmosphere keywords] [camera lens - 24mm/35mm/50mm/85mm/100mm]
[aspect ratio - 16:9] [film stock reference - Alexa Mini LF]
[mood keywords] [DO NOT include: IDENTITY LOCKED, FACE LOCKED, etc]
```

Example:
```
EVELYN woman mid-30s auburn hair ponytail NAVY BLUE JACKET beige blouse
KEY NECKLACE seated at small kitchen table FINAL NOTICE bills scattered
frustrated expression rubbing temples small London flat morning light
through grimy window tungsten warmth 16:9 cinematic Alexa Mini LF 35mm
shallow DOF natural skin texture stress visible in posture
```

**LTX_MOTION_PROMPT (separate from image):**
```
[Camera movement - STATIC/PUSH IN/DOLLY/CRANE/PAN/TRACK]
[Subject action with timing - "Evelyn RUBS temples 0-3s"]
[Environment motion - "candles FLICKER", "rain FALLS"]
[Timing markers in seconds]
[DO NOT include visual descriptions - those are in nano_prompt]
```

Example:
```
Evelyn RUBS temples 0-3s visible SIGH at 3s picks up bill EXAMINES 4-6s
TOSSES frustrated 7s reaches for coffee 8-9s phone BUZZES at 9s she LOOKS
camera STATIC observing
```

**HUMANIZATION:**
```json
{
  "applies": true,
  "blink_times": [2, 6],
  "breathing": "visible exhale sigh at 3s normal at 7s",
  "face_lock": "MAINTAIN exact features bone structure stable",
  "micro_expressions": "frustration in brow furrow resignation in mouth",
  "gesture_arc": "rubbing temples → examining bill → tossing → reaching"
}
```

**DIALOGUE (if any):**
```json
{
  "has_dialogue": true,
  "lines": [
    {"character": "Evelyn", "line": "Hello?", "timing": "2s"},
    {"character": "Evelyn", "line": "Who is this?", "timing": "5s"}
  ]
}
```

**CONTINUITY:**
```json
{
  "entry_state": "Phone buzzing on table Evelyn looking at it",
  "exit_state": "Phone at ear confused expression listening"
}
```

---

## LAYER 3: NARRATIVE STRUCTURE REQUIREMENTS

### ACTIVE PROTAGONIST CHECK
Every episode MUST include at least one scene where the protagonist:
- Makes a CHOICE with consequence (not just reacts)
- Takes an ACTION that cannot be undone
- Example: Evelyn burns the bill (Scene S03A)

### VISUAL STAKES CHECK
Every episode MUST include:
- At least 2-3 flashback inserts showing (not telling) the threat
- Visual payoff of prologue elements
- Example: Lady Margaret's ritual echoed during phone call

### SHOW DON'T TELL CHECK
For every exposition line in dialogue:
- Create corresponding FLASHBACK INSERT or VISUAL
- Example: "Lady Margaret passed away" → Show decayed manor

### EARNED CLIFFHANGER CHECK
Cliffhanger requires setup:
- Threat must be SHOWN before it matters
- Stakes must be VISUAL not just verbal
- Hook must reference earlier visual element

---

## LAYER 4: SMART CONTINUITY RULES

### NO_CHAIN Situations (Reset reference)
- `shot_type` = OTS, OVER SHOULDER, REVERSE, REACTION, POV
- `scene_id` changes (new scene)
- `is_flashback` boundary (present ↔ past)
- `characters_needed` differs from previous shot

### CHAIN_ENVIRONMENT Situations
- `shot_type` = INSERT, DETAIL, MACRO
- Same scene, no character change

### CHAIN_CHARACTER Situations
- Same character in consecutive shots
- Same scene
- Not a reverse/reaction angle

---

## LAYER 5: FORBIDDEN PROMPT PHRASES

These phrases get rendered as visible text in images. NEVER include:

```
IDENTITY LOCKED
MUST MATCH REFERENCE
FACE STRUCTURE LOCKED
NO MORPHING
ABSOLUTELY LOCKED
CRITICAL
MAINTAIN EXACT
LOCKED REFERENCE
ABSOLUTE
LOCKED
```

---

## LAYER 6: MODEL SELECTION MATRIX

| Content Type | Image Model | Video Model | Audio |
|-------------|-------------|-------------|-------|
| Dialog + Character | Minimax image-01 | OmniHuman | ElevenLabs |
| Character, no dialog | Minimax image-01 | Wan 2.2 I2V | None |
| Environment only | Nano-Banana Pro | Wan 2.2 T2V | None |
| Flashback | Nano-Banana Pro | Wan 2.2 I2V | None |
| VFX/Supernatural | Nano-Banana Pro | LTX-V2 | SFX |

---

## LAYER 7: DURATION GUIDELINES

| Shot Type | Duration Range | Frame Count (Wan) |
|-----------|---------------|-------------------|
| ESTABLISHING | 8-14s | 193-337 frames |
| WIDE | 8-12s | 193-289 frames |
| MEDIUM | 6-10s | 145-241 frames |
| CLOSE UP | 4-8s | 97-193 frames |
| INSERT/DETAIL | 4-6s | 97-145 frames |
| REACTION | 3-4s | 73-97 frames |

Minimum for Wan 2.2: 121 frames (~5 seconds)
Maximum for Wan 2.2: 241 frames (~10 seconds)

---

## EXAMPLE: COMPLETE SHOT ENTRY

```json
{
  "shot_number": 3,
  "shot_id": "S03_03A",
  "shot_type": "MEDIUM",
  "duration_seconds": 6,
  "characters_needed": ["Evelyn Ravencroft"],
  "is_flashback": false,
  "intercut_pair": "A",
  "has_dialogue": true,

  "nano_prompt": "EVELYN woman mid-30s auburn hair ponytail NAVY BLUE JACKET beige blouse KEY NECKLACE answering phone bringing it to ear expression curious then confused morning window light bills visible background soft focus 16:9 cinematic Alexa Mini LF 50mm shallow DOF natural skin texture warm tungsten interior",

  "ltx_motion_prompt": "Phone RISES to ear 0-1.5s natural arc lips move Hello at 2s listens 3-4s expression shifts confusion says Who is this 5s camera STATIC observing BLINKS at 1.5s 4s breathing subtle",

  "humanization": {
    "applies": true,
    "blink_times": [1.5, 4],
    "breathing": "slight chest rise at 3s",
    "face_lock": "ABSOLUTE stability no morphing",
    "micro_expressions": "neutral then curious then confused",
    "lip_sync": "Hello at 2s Who is this at 5s"
  },

  "dialogue": {
    "lines": [
      {"character": "Evelyn", "line": "Hello?", "timing": "2s"},
      {"character": "Evelyn", "line": "Who is this?", "timing": "5s"}
    ],
    "voice_id": "EXAVITQu4vr4xnSDxMaL"
  },

  "continuity": {
    "entry_state": "Hand lifting phone from table matches S03_02 end",
    "exit_state": "Phone at ear confused expression listening"
  },

  "smart_chain": {
    "use_previous": false,
    "reason": "character shot with dialogue, use char reference only",
    "references": ["Evelyn Ravencroft char_ref"]
  }
}
```

---

## TEMPLATE USAGE

1. Fill in LAYER 0 (episode header) once
2. For each scene, complete LAYER 1 (scene card)
3. For each shot, complete LAYER 2 (shot template)
4. Run LAYER 3 checks before generation
5. Generator uses LAYER 4-7 automatically

This template eliminates the V10→V17 revision cycle by:
- Embedding nano_prompts directly in script
- Specifying motion separately from visuals
- Including humanization parameters per shot
- Defining continuity states explicitly
- Avoiding text-poison phrases
- Pre-mapping dialogue to voice IDs
