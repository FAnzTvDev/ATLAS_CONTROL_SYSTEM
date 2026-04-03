# 🎬 ATLAS MULTI-TAB CONTROL SYSTEM

> **Distributed movie generation orchestrator for parallel AI rendering**

Control Atlas from Claude Code with commands that utilize multi-tab browser architecture for massive parallel processing. All tabs communicate together through a central WebSocket orchestrator.

---

## 🚀 Quick Start

### 1. Launch the System

```bash
cd /Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM
chmod +x launch_atlas.sh
./launch_atlas.sh
```

This will:
- ✅ Install dependencies (FastAPI, uvicorn, websockets, requests)
- ✅ Start the orchestrator server on port 8888
- ✅ Open the control dashboard in your browser

### 2. Open Worker Tabs

In the dashboard:
1. Click **"➕ Open Worker Tab"** to open a single worker
2. Click **"➕➕ Open 5 Workers"** to open multiple workers at once
3. Workers automatically connect to the orchestrator and start requesting tasks

### 3. Control from Claude Code

```python
from atlas_commander import AtlasCommander

# Create commander instance
commander = AtlasCommander()

# Check status
commander.print_status()

# Load a manifest and render
commander.load_manifest("/path/to/manifest.json")

# Generate character consistency shots
from atlas_commander import generate_character_consistency_shots

generate_character_consistency_shots(
    character_name="Marcus",
    reference_image_url="gs://temporalmovie/references/MARCUS_ASIAN_REFERENCE.jpg",
    scene_description="futuristic neural laboratory",
    num_angles=12
)
```

---

## 📁 System Architecture

```
ATLAS_CONTROL_SYSTEM/
├── orchestrator_server.py   # Central WebSocket server
├── worker.html               # Browser tab worker interface
├── atlas_commander.py        # Claude Code command interface
├── launch_atlas.sh           # Launcher script
└── README.md                 # This file
```

### How It Works

```
┌─────────────────────────────────────────────────────────────┐
│                    CLAUDE CODE                              │
│             (atlas_commander.py)                            │
└────────────────────┬────────────────────────────────────────┘
                     │ HTTP REST API
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              ORCHESTRATOR SERVER                            │
│           (orchestrator_server.py)                          │
│                                                             │
│  • Task Queue Management                                    │
│  • Worker Registration & Load Balancing                     │
│  • API Key Rotation (7 Replicate keys)                      │
│  • Status Broadcasting                                      │
│  • Result Collection                                        │
└─────────────┬───────────┬───────────┬───────────┬───────────┘
              │           │           │           │
              ▼           ▼           ▼           ▼
         WebSocket   WebSocket   WebSocket   WebSocket
              │           │           │           │
         ┌────┴────┐ ┌───┴────┐ ┌───┴────┐ ┌───┴────┐
         │ Worker  │ │ Worker │ │ Worker │ │ Worker │
         │  Tab 1  │ │  Tab 2 │ │  Tab 3 │ │  Tab 4 │
         └─────────┘ └────────┘ └────────┘ └────────┘
              │           │           │           │
         Calls APIs  Calls APIs  Calls APIs  Calls APIs
              │           │           │           │
         ┌────┴────┐ ┌───┴────┐ ┌───┴────┐ ┌───┴────┐
         │Replicate│ │Minimax │ │Runway  │ │ElevenLabs
         │  Wan    │ │  Flux  │ │FAL.ai  │ │   GCS  │
         └─────────┘ └────────┘ └────────┘ └────────┘
```

---

## 🎮 Command Interface

### Python API (atlas_commander.py)

```python
from atlas_commander import AtlasCommander

commander = AtlasCommander()

# === Status & Monitoring ===
commander.status()              # Get full status dict
commander.print_status()        # Print formatted status

# === Task Management ===
# Add single task
task_id = commander.add_task("minimax_image", {
    "prompt": "Marcus in futuristic lab, cinematic lighting",
    "subject_reference": "gs://temporalmovie/references/MARCUS_ASIAN_REFERENCE.jpg"
})

# Add batch of tasks
task_ids = commander.add_batch([
    {"type": "minimax_image", "params": {...}},
    {"type": "elevenlabs_audio", "params": {...}},
    {"type": "omnihuman_lipsync", "params": {...}}
])

# Load complete manifest
result = commander.load_manifest("/path/to/episode1_scene1_manifest.json")
# Returns: {"task_ids": [...], "total": 248}

# === Utilities ===
commander.test_render()         # Run test render
commander.clear_queue()         # Clear all queued tasks
commander.wait_for_completion() # Block until all tasks done
```

### High-Level Functions

```python
from atlas_commander import (
    generate_character_consistency_shots,
    generate_dialogue_scene,
    render_scene_from_manifest
)

# Generate 12-angle character shots
generate_character_consistency_shots(
    character_name="Marcus",
    reference_image_url="gs://temporalmovie/references/MARCUS_ASIAN_REFERENCE.jpg",
    scene_description="futuristic neural laboratory",
    num_angles=12
)

# Generate dialogue scene with lip sync
generate_dialogue_scene(
    character_name="Dr. Chen",
    character_reference="gs://temporalmovie/references/DR_CHEN_REFERENCE.jpg",
    dialogue_lines=[
        "The neural interface is online.",
        "We're ready to begin the experiment.",
        "Initiating memory transfer protocol."
    ],
    voice_id="EXAVITQu4vr4xnSDxMaL",
    scene_setting="clinical laboratory, sterile lighting"
)

# Render complete scene from manifest
render_scene_from_manifest("/path/to/episode1_scene1_manifest.json")
```

### Command Line Interface

```bash
# Check status
python atlas_commander.py status

# Run test render
python atlas_commander.py test

# Load manifest
python atlas_commander.py load /path/to/manifest.json

# Generate character consistency shots
python atlas_commander.py character Marcus gs://temporalmovie/references/MARCUS_ASIAN_REFERENCE.jpg "futuristic laboratory" 12

# Clear queue
python atlas_commander.py clear
```

---

## 📋 Task Types

The system supports these rendering task types:

### `minimax_image`
Generate photorealistic character images with subject reference.

**Parameters:**
- `prompt` (str): Image description
- `subject_reference` (str): GCS URL to character reference
- `aspect_ratio` (str, optional): "16:9", "9:16", "1:1" (default: "16:9")

### `flux_angles`
Generate multi-angle variations from a base image.

**Parameters:**
- `input_image` (str): URL to base image
- `prompt` (str): Scene description
- `num_angles` (int, optional): Number of angles (default: 5)

### `omnihuman_lipsync`
Generate lip-synced dialogue video.

**Parameters:**
- `reference_image` (str): Character reference URL
- `audio_url` (str): ElevenLabs audio URL
- `scene_setting` (str, optional): Scene description

### `runway_env`
Generate environment/establishing shots.

**Parameters:**
- `prompt` (str): Environment description
- `duration` (int, optional): Video duration in seconds (default: 5)

### `wan_motion`
Convert still image to motion video.

**Parameters:**
- `input_image` (str): GCS URL to image
- `num_frames` (int): Frame count (minimum 121)

### `elevenlabs_audio`
Generate voice audio.

**Parameters:**
- `text` (str): Dialogue text
- `voice_id` (str): ElevenLabs voice ID

### `upload_gcs`
Upload file to Google Cloud Storage.

**Parameters:**
- `path` (str): GCS path (relative to bucket)
- `file_data` (str): Base64-encoded file or local path

---

## 🎯 Real-World Usage Examples

### Example 1: Generate Episode 1, Scene 1

```python
from atlas_commander import render_scene_from_manifest

# Assuming you have a manifest at:
# /Users/quantum/Desktop/UNIVERSAL_MOVIE_SYSTEM/output/manifests/episode1_scene1_manifest.json

render_scene_from_manifest(
    "/Users/quantum/Desktop/UNIVERSAL_MOVIE_SYSTEM/output/manifests/episode1_scene1_manifest.json"
)

# This will:
# 1. Parse the manifest
# 2. Create tasks for all 248 shots
# 3. Distribute across all available worker tabs
# 4. Automatically rotate through 7 Replicate API keys
# 5. Wait for completion
# 6. Print final status
```

### Example 2: Test Character Consistency Pipeline

```python
from atlas_commander import AtlasCommander, generate_character_consistency_shots

commander = AtlasCommander()

# Generate Marcus from 12 angles
task_ids = generate_character_consistency_shots(
    character_name="Marcus",
    reference_image_url="gs://temporalmovie/references/MARCUS_ASIAN_REFERENCE.jpg",
    scene_description="waking up in neural transfer pod, dramatic lighting, cinematic",
    num_angles=12
)

print(f"Queued {len(task_ids)} tasks")

# Wait for completion
commander.wait_for_completion(timeout=3600)  # 1 hour timeout

# Check results
status = commander.status()
print(f"Completed: {status['stats']['completed_tasks']}")
print(f"Failed: {status['stats']['failed_tasks']}")
```

### Example 3: Generate Full Dialogue Scene

```python
from atlas_commander import generate_dialogue_scene

# Dr. Chen's opening monologue
generate_dialogue_scene(
    character_name="Dr. Chen",
    character_reference="gs://temporalmovie/references/DR_CHEN_REFERENCE.jpg",
    dialogue_lines=[
        "Subject 7's neural interface shows 97% synchronization.",
        "Memory transfer protocol is initializing.",
        "We're about to make history, people.",
        "Begin the sequence."
    ],
    voice_id="EXAVITQu4vr4xnSDxMaL",  # Clinical female voice
    scene_setting="clinical control room, multiple monitors, sterile blue lighting"
)
```

### Example 4: Batch Process Multiple Scenes

```python
from atlas_commander import AtlasCommander
import glob

commander = AtlasCommander()

# Load all scene manifests
manifest_dir = "/Users/quantum/Desktop/UNIVERSAL_MOVIE_SYSTEM/output/manifests"
manifests = glob.glob(f"{manifest_dir}/episode1_scene*.json")

print(f"Found {len(manifests)} scene manifests")

for manifest_path in manifests:
    print(f"\nLoading: {manifest_path}")
    result = commander.load_manifest(manifest_path)
    print(f"Queued {result['total']} tasks")

print(f"\nTotal queue size: {commander.status()['queue_size']}")
print("Workers will process tasks in parallel...")

# Monitor progress
import time
while True:
    status = commander.status()
    if status['queue_size'] == 0:
        break

    print(f"Queue: {status['queue_size']} | "
          f"Completed: {status['stats']['completed_tasks']} | "
          f"Failed: {status['stats']['failed_tasks']}")

    time.sleep(10)

print("\n✅ All scenes rendered!")
```

---

## 🔧 Configuration

### API Keys

The orchestrator automatically uses your configured API keys from `.env`:

```bash
# Required in .env file:
REPLICATE_API_TOKEN=<your-token>  # Supports multiple keys via REPLICATE_TOKEN_1, etc.
ELEVENLABS_API_KEY=<your-key>
FAL_KEY=<your-key>
```

**SECURITY**: Never commit API keys to version control. All keys are loaded from `.env` at startup.

### Voice Mappings

From CLAUDE.md:

```python
VOICE_MAP = {
    "Marcus": "21m00Tcm4TlvDq8ikWAM",      # Deep, authoritative
    "Dr. Chen": "EXAVITQu4vr4xnSDxMaL",    # Clinical female
    "System": "onwK4e9ZLuTAKqWW03F9"       # Robotic
}
```

---

## 📊 Monitoring & Dashboard

### Web Dashboard

Open http://localhost:8888 to access the visual dashboard:

- **Real-time statistics**: Active workers, queue size, completed/failed tasks
- **Worker status**: See each worker's current task and performance
- **Activity log**: Live feed of all system events
- **Quick actions**: Open workers, test renders, load manifests

### Status from Claude Code

```python
commander = AtlasCommander()
commander.print_status()
```

Output:
```
============================================================
🎬 ATLAS ORCHESTRATOR STATUS
============================================================

📊 Statistics:
   Active Workers:  5
   Queued Tasks:    142
   Completed Tasks: 106
   Failed Tasks:    2

⚙️  Workers:
   a7f3c2e1: busy (✅ 23 | ❌ 0)
   b9d5e4f2: busy (✅ 19 | ❌ 1)
   c1a8f6d3: idle (✅ 22 | ❌ 0)
   d4b2c7e5: busy (✅ 21 | ❌ 1)
   e6f3d8a4: busy (✅ 21 | ❌ 0)

✅ Recent Results: 10 tasks completed
============================================================
```

---

## 🐛 Troubleshooting

### Server won't start

```bash
# Check if port 8888 is in use
lsof -ti:8888

# Kill any process on that port
lsof -ti:8888 | xargs kill -9

# Restart
./launch_atlas.sh
```

### Workers not connecting

1. Check orchestrator log: `cat atlas_orchestrator.log`
2. Verify server is running: `curl http://localhost:8888/api/status`
3. Check browser console for WebSocket errors

### Tasks failing

Check the worker tab log (in browser) for specific error messages:
- **OmniHuman timeout**: Normal, runs in background (~10-15 min)
- **Wan 2.2 fails**: Must use GCS URLs, not local paths
- **Minimax wrong character**: Verify using Asian Marcus reference

### Queue stuck

```python
from atlas_commander import AtlasCommander

commander = AtlasCommander()
status = commander.status()

# Check for disconnected workers with assigned tasks
print(status['active_workers'])

# If needed, clear and restart
commander.clear_queue()
```

---

## 🚀 Advanced Usage

### Custom Task Types

Add new task types to `orchestrator_server.py`:

```python
class TaskType(str, Enum):
    # ... existing types ...
    CUSTOM_PROCESSOR = "custom_processor"
```

Then implement in `worker.html`:

```javascript
case 'custom_processor':
    result = await processCustomTask(task.params);
    break;
```

### Load Balancing

Workers automatically request tasks when idle. The orchestrator distributes evenly:

```python
async def assign_task_to_worker(self, worker_id: str):
    # Tasks are assigned FIFO from queue
    # Workers request tasks when idle
    # Automatic retry on worker disconnect
```

### Batch Processing Patterns

```python
# Pattern 1: Scene-by-scene
for scene in scenes:
    commander.load_manifest(scene.manifest)
    commander.wait_for_completion()

# Pattern 2: All at once (faster, but more memory)
for scene in scenes:
    commander.load_manifest(scene.manifest)
# All scenes render in parallel
commander.wait_for_completion()

# Pattern 3: Chunked (balanced)
from itertools import islice

def chunked(iterable, size):
    it = iter(iterable)
    while chunk := list(islice(it, size)):
        yield chunk

for chunk in chunked(scenes, 3):
    for scene in chunk:
        commander.load_manifest(scene.manifest)
    commander.wait_for_completion()
```

---

## 📚 Integration with Existing Systems

### With parse_script.py

```python
from atlas_commander import AtlasCommander

# Your existing script parser creates a manifest
manifest = parse_script("/path/to/script.txt")
save_manifest(manifest, "/tmp/manifest.json")

# Now render with Atlas
commander = AtlasCommander()
result = commander.load_manifest("/tmp/manifest.json")

print(f"Rendering {result['total']} shots across {commander.status()['stats']['active_workers']} workers")
```

### With Story Bible

```python
import json
from atlas_commander import generate_character_consistency_shots

# Load story bible
bible = json.load(open("/Users/quantum/Desktop/UNIVERSAL_MOVIE_SYSTEM/output/bible_driven/marcus_story_bible.json"))

# Get character details
marcus = bible["characters"]["Marcus"]

# Generate consistency shots for each episode beat
for episode in bible["episodes"]:
    for beat in episode["beats"]:
        generate_character_consistency_shots(
            character_name="Marcus",
            reference_image_url=marcus["reference_image"],
            scene_description=beat["setting"],
            num_angles=6
        )
```

---

## 🎬 Production Checklist

Before running a full episode:

- [ ] ✅ Orchestrator server running (`./launch_atlas.sh`)
- [ ] ✅ Minimum 5 worker tabs open and connected
- [ ] ✅ All API keys valid (check CLAUDE.md)
- [ ] ✅ Google Cloud Storage authenticated
- [ ] ✅ Character references uploaded to GCS
- [ ] ✅ Manifest validated (use `parse_script.py --validate`)
- [ ] ✅ Disk space available (estimate: 5GB per scene)
- [ ] ✅ Test render successful (`commander.test_render()`)

---

## 📞 Support

For issues or questions:

1. Check `atlas_orchestrator.log`
2. Review worker tab console logs
3. Verify API keys in CLAUDE.md
4. Test with `commander.test_render()`

---

## 🎯 Next Steps

1. **Run your first test:**
   ```bash
   ./launch_atlas.sh
   # Open 5 worker tabs from dashboard
   python3 -c "from atlas_commander import quick_test; quick_test()"
   ```

2. **Generate character consistency shots:**
   ```bash
   python3 atlas_commander.py character Marcus gs://temporalmovie/references/MARCUS_ASIAN_REFERENCE.jpg "futuristic laboratory" 12
   ```

3. **Render a complete scene:**
   ```python
   from atlas_commander import render_scene_from_manifest
   render_scene_from_manifest("/path/to/your/manifest.json")
   ```

4. **Scale up:** Open 10-20 worker tabs for maximum parallel processing!

---

**🎬 You're now ready to control Atlas from Claude Code with full multi-tab parallel processing!**
