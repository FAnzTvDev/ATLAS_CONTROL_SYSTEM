"""
ATLAS Scene Strip Analyzer — V36 OBSERVE ONLY
Builds a horizontal filmstrip of all scene frames and sends to Gemini for
relational/scene-level visual analysis. Does NOT modify any files.
"""
import json, os, sys, base64, requests
from pathlib import Path
from PIL import Image
from dotenv import load_dotenv

# Load env from project root
ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / '.env')

GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY')
GEMINI_MODEL = 'gemini-2.5-flash'
GEMINI_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent?key={GOOGLE_API_KEY}"
)

FRAMES_DIR = ROOT / 'pipeline_outputs/victorian_shadows_ep1/first_frames'
SHOT_PLAN  = ROOT / 'pipeline_outputs/victorian_shadows_ep1/shot_plan.json'
STRIP_DIR  = Path('/tmp/atlas_strips')
STRIP_DIR.mkdir(exist_ok=True)

STRIP_HEIGHT = 256
GAP = 4


def load_all_shots():
    with open(SHOT_PLAN) as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    if 'shots' in data:
        return data['shots']
    # fallback: flatten all list values
    all_shots = []
    for v in data.values():
        if isinstance(v, list):
            all_shots.extend(v)
    return all_shots


def get_scene_frames(all_shots, scene_id):
    """Return (shot_id, PIL.Image) pairs for clean E/M frames of the scene."""
    prefix = scene_id + '_'
    scene_shots = sorted(
        [s for s in all_shots if s.get('shot_id', '').startswith(prefix)],
        key=lambda x: x['shot_id']
    )
    results = []
    for s in scene_shots:
        sid = s['shot_id']
        matches = sorted([
            f for f in FRAMES_DIR.iterdir()
            if f.name.startswith(sid) and f.suffix in ('.jpg', '.png', '.jpeg')
            and 'seedance' not in f.name and 'lastframe' not in f.name
        ])
        if matches:
            img = Image.open(matches[0]).convert('RGB')
            ratio = STRIP_HEIGHT / img.height
            img = img.resize((int(img.width * ratio), STRIP_HEIGHT))
            results.append((sid, img))
    return results


def build_strip(frames_list, scene_id):
    """Stitch frames into a horizontal strip and save to /tmp."""
    total_w = sum(img.width for _, img in frames_list) + GAP * (len(frames_list) - 1)
    strip = Image.new('RGB', (total_w, STRIP_HEIGHT), (0, 0, 0))
    x = 0
    for _, img in frames_list:
        strip.paste(img, (x, 0))
        x += img.width + GAP
    path = STRIP_DIR / f'scene_{scene_id}_strip.jpg'
    strip.save(path, quality=85)
    return path


def analyze_strip(strip_path, labels, scene_id):
    n = len(labels)
    prompt = f"""You are a veteran film editor reviewing a filmstrip of {n} sequential first frames from Scene {scene_id} of a Victorian mystery thriller.

The shots from left to right are: {', '.join(labels)}

Analyze this STRIP AS A WHOLE — not individual frames. Answer:

1. VISUAL CONTINUITY: Do all frames look like they belong in the SAME scene, same room, same film? Any frame that breaks the visual flow?

2. CAMERA PROGRESSION: Does the camera angle progress logically? (Should go: establishing wide → interior atmosphere → insert detail → character medium → close-up → OTS). Any angle that feels out of order?

3. CHARACTER CONSISTENCY: If the same character appears in multiple frames, do they look like the SAME PERSON? Same wardrobe, same build, same hair?

4. LOCATION LOCK: Is this consistently ONE room throughout, or does the room architecture shift between frames?

5. LIGHTING CONSISTENCY: Is the light source direction and color temperature consistent across all frames?

6. WEAKEST FRAME: Which single frame is the weakest link in this sequence? Why? Should it be regenerated?

7. STRONGEST FRAME: Which single frame is the best? What makes it work cinematically?

8. OVERALL SCENE GRADE: A (production ready) / B (minor fixes) / C (significant rework) / D (major problems)

Be specific. Name exact shot IDs when noting issues."""

    with open(strip_path, 'rb') as f:
        img_b64 = base64.b64encode(f.read()).decode('utf-8')

    payload = {
        "contents": [{"parts": [
            {"inline_data": {"mime_type": "image/jpeg", "data": img_b64}},
            {"text": prompt}
        ]}],
        "generationConfig": {
            "maxOutputTokens": 16384,
            # thinkingConfig inside generationConfig for v1beta
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }

    resp = requests.post(GEMINI_URL, json=payload, timeout=120)
    resp.raise_for_status()
    return resp.json()['candidates'][0]['content']['parts'][0]['text']


def run(scene_ids=None):
    if not GOOGLE_API_KEY:
        print("ERROR: No GOOGLE_API_KEY found in .env")
        sys.exit(1)

    all_shots = load_all_shots()
    target_scenes = scene_ids or ['001', '002', '006']

    for scene_id in target_scenes:
        frames_list = get_scene_frames(all_shots, scene_id)
        if not frames_list:
            print(f"Scene {scene_id}: No frames found — skipping")
            continue

        labels = [sid for sid, _ in frames_list]
        strip_path = build_strip(frames_list, scene_id)
        w = sum(img.width for _, img in frames_list) + GAP * (len(frames_list) - 1)
        print(f"Scene {scene_id}: {len(frames_list)} frames → {strip_path} ({w}x{STRIP_HEIGHT})")
        print(f"  Shots: {', '.join(labels)}")

        out_path = STRIP_DIR / f'scene_{scene_id}_analysis.txt'
        try:
            analysis = analyze_strip(strip_path, labels, scene_id)
            header = f"\n{'='*64}\n  SCENE {scene_id} — STRIP ANALYSIS\n{'='*64}\n"
            sys.stdout.write(header + analysis + '\n')
            sys.stdout.flush()
            with open(out_path, 'w') as fh:
                fh.write(header + analysis + '\n')
            print(f"  [saved → {out_path}]")
        except Exception as e:
            print(f"Scene {scene_id} ERROR: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print("Response body:", e.response.text[:600])
        print()


if __name__ == '__main__':
    # Usage: python3 tools/scene_strip_analyzer.py [scene_id ...]
    scenes = sys.argv[1:] if len(sys.argv) > 1 else None
    run(scenes)
