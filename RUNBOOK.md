# ATLAS V17 RUNBOOK

Quick troubleshooting guide for production issues.

---

## Quick Checks

```bash
# Is server running?
curl http://localhost:9999/api/health

# Run full smoke test
python3 tools/smoke_test_v17.py kord_v17

# Check server logs
tail -100 /tmp/atlas_server.log | grep -E "\[FIRST_FRAME\]|\[VIDEO_RENDER\]|\[STITCH\]|\[ERROR\]"
```

---

## Common Issues

### 1. Server Won't Start

**Symptom:** `Connection refused` on port 9999

**Check:**
```bash
lsof -i :9999
ps aux | grep orchestrator
```

**Fix:**
```bash
cd /Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM
python3 orchestrator_server.py > /tmp/atlas_server.log 2>&1 &
```

---

### 2. First Frame Generation Fails

**Symptom:** 500 error from `/api/auto/generate-first-frames`

**Log Marker:** `[FIRST_FRAME]`

**Common Causes:**
1. Missing `nano_prompt` in shot_plan.json
2. FAL API rate limit
3. Invalid character reference URL

**Check:**
```bash
# Verify shot has prompts
cat pipeline_outputs/kord_v17/shot_plan.json | python3 -c "
import sys,json
d=json.load(sys.stdin)
for s in d['shots'][:3]:
    print(f\"{s['shot_id']}: nano={bool(s.get('nano_prompt'))}\")
"
```

**Fix:**
- Run `/api/shot-plan/fix-v16` to regenerate prompts
- Check FAL API key is valid in environment

---

### 3. Video Generation Fails

**Symptom:** 500 error from `/api/auto/render-videos`

**Log Marker:** `[VIDEO_RENDER]`

**Common Causes:**
1. First frame doesn't exist
2. Wrong parameter name (`image` vs `image_url`)
3. Base64 encoding failure

**Check:**
```bash
# Verify first frame exists
ls -la pipeline_outputs/kord_v17/first_frames/E011_S01_000A.jpg
```

**Fix:**
- Ensure first frame exists before video generation
- Parameter is `image_url` not `image` for LTX-2

---

### 4. Auto-Cast Returns 500

**Symptom:** `/api/v6/casting/auto-cast` fails

**Log Marker:** `[AUTO_CAST]`

**Common Causes:**
1. `scene.beats` is int instead of array (V17 format)
2. Missing ai_actors_library.json

**Check:**
```bash
# Check beats format
cat pipeline_outputs/kord_v17/story_bible.json | python3 -c "
import sys,json
d=json.load(sys.stdin)
for s in d.get('scenes',[])[:2]:
    print(f\"Scene {s.get('scene_id')}: beats type = {type(s.get('beats')).__name__}\")
"
```

**Fix:**
- The V17 fix adds `isinstance(beats, list)` check
- Group characters map to EXTRAS POOL automatically

---

### 5. Stitch Reports 0 Videos

**Symptom:** Dry-run shows `ready_count: 0` but videos exist

**Log Marker:** `[STITCH]`

**Common Causes:**
1. Videos in `videos/` but stitch looks in `renders/`
2. shot_plan.json `video_path` not updated

**Check:**
```bash
ls pipeline_outputs/kord_v17/videos/
ls pipeline_outputs/kord_v17/renders/
```

**Fix:**
- Stitch now checks both `renders/` and `videos/` directories
- Invalidate cache: `POST /api/v16/ui/invalidate-cache/kord_v17`

---

### 6. UI Shows Stale Data

**Symptom:** UI doesn't reflect new generations

**Log Marker:** `[REHYDRATE]`

**Check:**
- Browser console for errors
- Network tab for bundle requests

**Fix:**
```bash
# Force cache invalidation
curl -X POST http://localhost:9999/api/v16/ui/invalidate-cache/kord_v17

# Or in browser console:
rehydrateCurrentProject()
```

---

### 7. Cast Thumbnails Missing

**Symptom:** Cast panel shows broken images

**Check:**
```bash
# Verify headshot paths
cat pipeline_outputs/kord_v17/cast_map.json | python3 -c "
import sys,json
d=json.load(sys.stdin)
for name, data in list(d.items())[:3]:
    print(f\"{name}: {data.get('headshot_url', 'MISSING')}\")
"
```

**Fix:**
- Headshot URLs must use `/api/media?path=` format
- Verify file exists at referenced path

---

## Golden Log Markers

When debugging, grep for these markers in server logs:

| Marker | Component | Example |
|--------|-----------|---------|
| `[GCS]` | Cloud storage | `[GCS] Uploading to bucket...` |
| `[MEDIA]` | Media serving | `[MEDIA] Serving /api/media?path=...` |
| `[AUTO_CAST]` | Casting | `[AUTO_CAST] Mapped 15 characters` |
| `[FIRST_FRAME]` | Frame gen | `[FIRST_FRAME] Generated E011_S01_000A` |
| `[VIDEO_RENDER]` | Video gen | `[VIDEO_RENDER] Completed E011_S01_000A` |
| `[STITCH]` | Stitching | `[STITCH] 5 videos ready` |
| `[REHYDRATE]` | Cache | `[REHYDRATE] Bundle rebuilt for kord_v17` |
| `[VALIDATION]` | Input validation | `[VALIDATION] Missing nano_prompt` |

---

## Emergency Recovery

If everything is broken:

```bash
# 1. Kill any stuck processes
pkill -f orchestrator_server

# 2. Clear caches
rm -rf pipeline_outputs/*/ui_cache/

# 3. Restart server
python3 orchestrator_server.py > /tmp/atlas_server.log 2>&1 &

# 4. Wait for startup
sleep 5

# 5. Verify health
curl http://localhost:9999/api/health

# 6. Run smoke test
python3 tools/smoke_test_v17.py kord_v17
```

---

## Escalation

If issues persist after trying above fixes:
1. Save full server log: `cat /tmp/atlas_server.log > atlas_debug_$(date +%Y%m%d).log`
2. Export project state: `cp -r pipeline_outputs/kord_v17 ~/Desktop/kord_v17_debug/`
3. Note exact endpoint, request body, and response

---

**Last Updated:** 2026-02-10

---

# GOVERNED AGENT OPERATIONS

> This section is an operational interface for agent governance.
> Follow verbatim to run projects safely.

---

## EXECUTION MODES

| Mode | Writes | Use Case |
|------|--------|----------|
| `LOCKED` | No | Audit, verify state without changes |
| `VERIFY` | No | Pre-render validation |
| `REPAIR` | Yes | Fix critic-identified issues |
| `OVERWRITE` | Yes | Force regenerate all artifacts |

---

## STANDARD GOVERNED RUN

### Step 1: Start Pipeline

```bash
cd /Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM
python3 -c "
import sys
sys.path.insert(0, 'atlas_agents_v16_7')
from atlas_agents.ops_coordinator import OpsCoordinator

coord = OpsCoordinator(repo_root='.')
result = coord.run_pipeline(
    projects=['kord_v17', 'ravencroft_v17'],
    mode='VERIFY',
    initiated_by='human'
)
print(f'Final verdict: {result[\"final_verdict\"]}')
"
```

### Step 2: Check Execution Context

```bash
cat execution_context.json | python3 -m json.tool
```

### Step 3: Verify Agent Status Logs

```bash
cat pipeline_outputs/kord_v17/_agent_status.json | python3 -m json.tool
```

---

## VERDICT HANDLING

### READY
Proceed to render.

### NEEDS_REPAIR
Ops Coordinator re-runs automatically in REPAIR mode.

### NEEDS_HUMAN_JUDGMENT
1. Read critic report:
   ```bash
   cat pipeline_outputs/kord_v17/critic_report.json | python3 -m json.tool
   ```
2. Address `human_judgment_issues` manually
3. Re-run pipeline

---

## GOVERNANCE INVARIANTS

1. **Execution context is immutable during run** - mode cannot change mid-execution
2. **Agent status log is append-only** - never delete or modify entries
3. **Critic is final authority** - Ops Coordinator obeys critic verdict
4. **Humans only escalated by Critic** - not by Ops Coordinator guessing

---

## EMERGENCY OVERRIDES

### Force Complete Stuck Run
```bash
python3 -c "
import sys
sys.path.insert(0, 'atlas_agents_v16_7')
from atlas_agents.execution_context import ExecutionContext
ctx = ExecutionContext('.')
ctx.load()
ctx.complete_run('ABORTED')
"
```

### Human Override of Critic Verdict
```bash
python3 -c "
import json
with open('pipeline_outputs/kord_v17/freeze_verdict.json', 'r+') as f:
    v = json.load(f)
    v['safe_to_render'] = True
    v['needs_human'] = False
    v['_human_override'] = True
    f.seek(0)
    json.dump(v, f, indent=2)
    f.truncate()
"
```

---

## SIGN-OFF

```
Run ID: ___________
Date: ______________
Operator: __________
Projects: __________
Final Verdict: [ ] READY  [ ] NEEDS_HUMAN_JUDGMENT
```

---

*ATLAS V17 - Governed Agent Collaboration*
