# ATLAS V6 COMPLETE SYSTEM OVERVIEW
## Final Integration Documentation
### Generated: 2026-01-09

---

## 🎯 SYSTEM PURPOSE

ATLAS V6 is a comprehensive AI film production system that transforms scripts into rendered video content through:
- **Story Bible parsing** - Extract metadata, characters, locations
- **Screenplay parsing** - Convert dialogue/action into shots
- **AI Casting** - Match characters to 50 AI actors via FIT scores
- **Director/Writer styles** - Apply visual signatures to prompts
- **Human verification gates** - Approve each step before rendering
- **LTX-2 rendering** - Generate first frames and video

---

## 📁 CORE FILES

| File | Purpose |
|------|---------|
| `directors_library.json` | 10 directors with visual signatures |
| `writers_library.json` | 10 writers with dialogue styles |
| `ai_actors_library.json` | 50 actors with appearance, skills |
| `V6_ATLAS_MASTER_SYSTEM.py` | Core classes |
| `V6_ENDPOINTS.py` | 14 API endpoints |
| `V6_GAP_CLOSER.py` | Profile viewer, casting, parser |
| `V6_INTEGRATION.js` | UI wiring |
| `V6_PROFILE_UI.js` | Profile viewer UI |

---

## 🔌 API ENDPOINTS (28 Total)

### Preprocessing & Import
```
POST /api/v6/preprocess         - Split story bible from screenplay
GET  /api/v6/current-script     - Get script being parsed
POST /api/v6/full-import        - Complete import pipeline
POST /api/v6/screenplay/parse   - Parse screenplay into shots
```

### Verification Gates
```
POST /api/v6/approve/story      - Approve story bible
POST /api/v6/approve/locations  - Approve location masters
POST /api/v6/approve/characters - Approve character references
POST /api/v6/approve/casting    - Approve AI actor casting
POST /api/v6/approve/all        - Approve everything
```

### Generation & Shots
```
POST /api/v6/generate/locations       - Queue location images
POST /api/v6/generate/characters      - Queue character images
GET  /api/v6/shots/{project}          - Get all shots
POST /api/v6/shots/{project}/update   - Update shot prompts
POST /api/v6/regenerate/{project}/{id} - Regenerate shot
```

### Profiles & Casting
```
GET  /api/v6/profiles/directors       - All directors
GET  /api/v6/profiles/directors/{id}  - Single director
GET  /api/v6/profiles/writers         - All writers
GET  /api/v6/profiles/writers/{id}    - Single writer
GET  /api/v6/profiles/actors          - All actors (filterable)
GET  /api/v6/profiles/actors/{id}     - Single actor
POST /api/v6/casting/recommend        - Get FIT recommendations
GET  /api/v6/casting/rationale/{proj} - Why actors were cast
```

### Status
```
GET /api/v6/live-status/{project}        - Recent frames
GET /api/v6/verification-state/{project} - Verification state
```

---

## 🔄 SIGNAL FLOW

```
USER UPLOADS DOCUMENT
         │
         ▼
   PREPROCESSOR (splits at ---)
         │
    ┌────┴────┐
    ▼         ▼
STORY      SCREENPLAY
BIBLE      (clean text)
    │         │
    │         ▼
    │    SCREENPLAY PARSER
    │    (extracts dialogue/action)
    │         │
    └────┬────┘
         ▼
    AI CASTING
    (FIT score matching)
         │
         ▼
    DIRECTOR/WRITER STYLES
    (inject visual signatures)
         │
         ▼
    SHOT PLAN
         │
         ▼
    VERIFICATION GATES
    (human approves each)
         │
         ▼
    RENDERING
```

---

## 👤 PROFILES

### Directors (10)
| ID | Name | Specialty | Channel |
|----|------|-----------|---------|
| D001 | Helena Blackwood | Gothic Horror | AMERICAN HORROR CLASSICS |
| D002 | Victor Tanaka | Action/Martial Arts | RUMBLE TV |
| D003 | Sofia Delacroix | Romance/Drama | - |
| D004 | Marcus Chen | Sci-Fi/Dystopia | SCI-FI CLASSICS |
| D005 | Isabella Romano | Comedy | JOKEBOX TV |
| D006 | James Morrison | Crime/Noir | WHO DONE IT TV |
| D007 | Yuki Nakamura | Anime/Fantasy | - |
| D008 | David Sterling | Documentary | - |
| D009 | Elena Volkov | Mystery/Thriller | WHO DONE IT TV |
| D010 | Robert Kim | Space Opera | MARTIAN TV |

### Writers (10)
| ID | Name | Style |
|----|------|-------|
| W001 | Thomas Ashworth | Subtext-heavy, sparse |
| W002 | Sarah Chen | Punchy, kinetic |
| W003 | Marcus Williams | Rapid-fire wit |
| W004 | Elena Vasquez | Emotional depth |
| W005 | James Morrison | Hard-boiled noir |

### Actors (50)
Categorized by specialty: Action, Drama, Comedy, Horror, Sci-Fi, Romance

---

## 📋 SCRIPT FORMAT

```markdown
# Project Title

## Project Info
- **Type:** Episode
- **Runtime:** 45 min
- **Genre:** gothic_horror

## Characters
### Character Name
- **Role:** protagonist
- **Look:** Physical description

## Locations
### Location Name
- **Atmosphere:** Mood description

---

INT. LOCATION - TIME

Action description.

CHARACTER
Dialogue here.
```

---

## 🚀 INSTALLATION

### 1. Add endpoints to orchestrator_server.py
```python
# Before "if __name__" block, add:
# Contents of V6_ENDPOINTS.py
# Contents of V6_GAP_CLOSER.py
```

### 2. Add JavaScript to auto_studio_tab.html
```html
<!-- Before </body>, add: -->
<!-- Contents of V6_INTEGRATION.js -->
<!-- Contents of V6_PROFILE_UI.js -->
```

### 3. Restart server
```bash
lsof -ti tcp:9999 | xargs kill -9
python orchestrator_server.py
```

### 4. Hard refresh browser
`Cmd+Shift+R` (Mac) or `Ctrl+Shift+R` (Windows)

---

## ✅ TASK COMPLETION STATUS

| Task | Status |
|------|--------|
| Script Preprocessor | ✅ Complete |
| Screenplay Parser (actual dialogue) | ✅ Complete |
| Director Profile Viewer | ✅ Complete |
| Writer Profile Viewer | ✅ Complete |
| Actor Profile Viewer | ✅ Complete |
| Casting Rationale + FIT scores | ✅ Complete |
| Verification Gates Wiring | ✅ Complete |
| Shots Tab with Editable Prompts | ✅ Complete |
| Live Renderer Status | ✅ Complete |
| Full Import Pipeline | ✅ Complete |

---

## 📦 FILES TO INTEGRATE

1. **V6_ENDPOINTS.py** - Core verification endpoints
2. **V6_GAP_CLOSER.py** - Profiles, casting, screenplay parser
3. **V6_INTEGRATION.js** - Verification UI wiring
4. **V6_PROFILE_UI.js** - Profile viewer panels

All files are in `/mnt/user-data/outputs/`
