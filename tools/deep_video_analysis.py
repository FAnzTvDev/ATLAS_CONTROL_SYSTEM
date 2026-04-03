#!/usr/bin/env python3
"""
ATLAS Deep Video Analysis — V1.0
Uses Gemini Vision (gemini-2.5-flash) to analyze full .mp4 videos via the Files API.

Runs three analysis passes per scene:
  1. Per-video: upload full clip → character identity, location, motion, composition quality
  2. Cross-video continuity: compare end of clip N with start of clip N+1
  3. Prompt fidelity: semantic embedding comparison (gemini-embedding-001) between
     intended nano_prompt/beat_action and what Gemini Vision actually describes

Outputs:
  - deep_video_analysis_report.json   (full machine-readable results)
  - deep_video_analysis_summary.md    (human-readable graded summary)
"""

import os
import json
import time
import base64
import pathlib
import datetime
import textwrap
from typing import Optional

import requests

# ── Configuration ─────────────────────────────────────────────────────────────

BASE_DIR = pathlib.Path("/Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM")
PROJECT_DIR = BASE_DIR / "pipeline_outputs" / "victorian_shadows_ep1"
SHOT_PLAN = PROJECT_DIR / "shot_plan.json"
CAST_MAP   = PROJECT_DIR / "cast_map.json"

# Load env file
_env_path = BASE_DIR / ".env"
if _env_path.exists():
    for line in _env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY", "")
if not GOOGLE_API_KEY:
    raise RuntimeError("No GOOGLE_API_KEY found in environment or .env")

GEMINI_FLASH   = "gemini-2.5-flash"
EMBED_MODEL    = "text-embedding-004"  # faster/cheaper than gemini-embedding-001
BASE_URL       = "https://generativelanguage.googleapis.com/v1beta"
UPLOAD_URL     = "https://generativelanguage.googleapis.com/upload/v1beta/files"

# Analysis settings
MAX_WAIT_SECS  = 300      # Max wait for Gemini to process an uploaded video
POLL_INTERVAL  = 5        # Seconds between state polls
RATE_LIMIT_DELAY = 4      # Seconds between generateContent calls (free tier: 15 RPM)


# ── Gemini Files API ──────────────────────────────────────────────────────────

def upload_video(video_path: pathlib.Path) -> Optional[str]:
    """
    Upload a video file to Gemini Files API using resumable upload protocol.
    Returns the file URI (e.g. "files/xxxxxxxxxxxx") or None on failure.
    """
    video_path = pathlib.Path(video_path)
    if not video_path.exists():
        print(f"  [SKIP] Video not found: {video_path}")
        return None

    file_size = video_path.stat().st_size
    display_name = video_path.name
    print(f"  [UPLOAD] {display_name} ({file_size/1024/1024:.1f} MB)...")

    # Step 1: Start resumable upload session
    start_resp = requests.post(
        UPLOAD_URL,
        headers={
            "X-Goog-Upload-Protocol":       "resumable",
            "X-Goog-Upload-Command":        "start",
            "X-Goog-Upload-Header-Content-Length": str(file_size),
            "X-Goog-Upload-Header-Content-Type":   "video/mp4",
            "Content-Type": "application/json",
        },
        params={"key": GOOGLE_API_KEY},
        json={"file": {"display_name": display_name}},
        timeout=30,
    )
    if start_resp.status_code not in (200, 201):
        print(f"  [ERROR] Upload init failed: {start_resp.status_code} {start_resp.text[:200]}")
        return None

    upload_session_url = start_resp.headers.get("X-Goog-Upload-URL")
    if not upload_session_url:
        print(f"  [ERROR] No upload URL in response headers")
        return None

    # Step 2: Upload the actual file bytes
    with open(video_path, "rb") as f:
        video_bytes = f.read()

    upload_resp = requests.post(
        upload_session_url,
        headers={
            "Content-Length":          str(file_size),
            "X-Goog-Upload-Offset":    "0",
            "X-Goog-Upload-Command":   "upload, finalize",
        },
        data=video_bytes,
        timeout=120,
    )
    if upload_resp.status_code not in (200, 201):
        print(f"  [ERROR] Upload failed: {upload_resp.status_code} {upload_resp.text[:200]}")
        return None

    try:
        file_info = upload_resp.json()
        file_uri  = file_info["file"]["uri"]
        file_name = file_info["file"]["name"]
    except Exception as e:
        print(f"  [ERROR] Parsing upload response: {e}")
        return None

    print(f"  [WAIT] Processing {display_name} → {file_name}...")

    # Step 3: Poll until state == ACTIVE
    deadline = time.time() + MAX_WAIT_SECS
    while time.time() < deadline:
        state_resp = requests.get(
            f"{BASE_URL}/{file_name}",
            params={"key": GOOGLE_API_KEY},
            timeout=15,
        )
        if state_resp.status_code == 200:
            state = state_resp.json().get("state", "PROCESSING")
            if state == "ACTIVE":
                print(f"  [OK] {display_name} ready → {file_uri}")
                return file_uri
            elif state == "FAILED":
                print(f"  [ERROR] File processing failed")
                return None
        time.sleep(POLL_INTERVAL)

    print(f"  [TIMEOUT] {display_name} did not become ACTIVE within {MAX_WAIT_SECS}s")
    return None


def delete_file(file_uri: str):
    """Delete an uploaded Gemini file to free quota."""
    # file_uri is like "https://generativelanguage.googleapis.com/v1beta/files/xxxx"
    # or "files/xxxx" — extract the name portion
    if "/files/" in file_uri:
        file_name = "files/" + file_uri.split("/files/")[-1]
    else:
        file_name = file_uri
    requests.delete(
        f"{BASE_URL}/{file_name}",
        params={"key": GOOGLE_API_KEY},
        timeout=15,
    )


def gemini_generate(parts: list, temperature: float = 0.1) -> Optional[str]:
    """
    Call Gemini generateContent. parts is a list of dicts:
    e.g. [{"file_data": {...}}, {"text": "..."}]
    Returns the text response or None.
    """
    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "maxOutputTokens": 1024,
            "temperature": temperature,
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }
    url = f"{BASE_URL}/models/{GEMINI_FLASH}:generateContent"
    resp = requests.post(
        url,
        params={"key": GOOGLE_API_KEY},
        json=payload,
        timeout=60,
    )
    if resp.status_code != 200:
        print(f"  [API ERROR] {resp.status_code}: {resp.text[:300]}")
        return None
    try:
        text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        return text
    except Exception as e:
        print(f"  [PARSE ERROR] {e}: {resp.text[:200]}")
        return None


def get_embedding(text: str) -> Optional[list]:
    """Get text embedding via text-embedding-004."""
    url = f"{BASE_URL}/models/{EMBED_MODEL}:embedContent"
    resp = requests.post(
        url,
        params={"key": GOOGLE_API_KEY},
        json={
            "content": {"parts": [{"text": text}]},
            "taskType": "SEMANTIC_SIMILARITY",
        },
        timeout=30,
    )
    if resp.status_code != 200:
        return None
    try:
        return resp.json()["embedding"]["values"]
    except Exception:
        return None


def cosine_similarity(a: list, b: list) -> float:
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = sum(x * x for x in a) ** 0.5
    mag_b = sum(x * x for x in b) ** 0.5
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def parse_json_response(text: str) -> dict:
    """Robustly parse JSON from a model response (handles markdown code fences)."""
    if not text:
        return {}
    # Strip markdown fences
    stripped = text.strip()
    for fence in ("```json", "```JSON", "```"):
        if stripped.startswith(fence):
            stripped = stripped[len(fence):]
    if stripped.endswith("```"):
        stripped = stripped[:-3]
    stripped = stripped.strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        # Try to find JSON object in the text
        start = stripped.find("{")
        end   = stripped.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(stripped[start:end])
            except Exception:
                pass
    return {"raw_response": text[:500]}


# ── Analysis Prompts ──────────────────────────────────────────────────────────

def build_per_video_prompt(shot: dict, cast_map: dict) -> str:
    """Build the per-video analysis prompt from shot metadata."""
    shot_id   = shot.get("shot_id", "?")
    scene_id  = shot.get("scene_id", "?")
    shot_type = shot.get("shot_type", "unknown")
    chars     = shot.get("characters", [])
    dialogue  = shot.get("dialogue_text") or shot.get("_beat_dialogue") or ""
    beat      = shot.get("_beat_action", "")
    atmo      = shot.get("_beat_atmosphere", "")
    eye_line  = shot.get("_eye_line_target", "")
    body_dir  = shot.get("_body_direction", "")
    location  = shot.get("location", "")
    duration  = shot.get("duration", 0)

    # Build character reference descriptions from cast_map
    char_desc_lines = []
    for c in chars:
        if c in cast_map:
            appearance = cast_map[c].get("appearance", "")
            if appearance:
                char_desc_lines.append(f"  - {c}: {appearance}")

    char_block = "\n".join(char_desc_lines) if char_desc_lines else "  (no character reference)"

    prompt = textwrap.dedent(f"""
    You are a professional film director and cinematographer performing a technical QA review.

    Analyze this video clip and return a detailed JSON assessment.

    SHOT METADATA:
    - Shot ID: {shot_id} (Scene {scene_id})
    - Shot type: {shot_type}
    - Expected duration: {duration}s
    - Location: {location}
    - Characters present: {", ".join(chars) if chars else "NONE (establishing/B-roll)"}
    - Expected beat action: {beat}
    - Expected atmosphere: {atmo}
    - Expected eye-line: {eye_line}
    - Expected body direction: {body_dir}
    - Dialogue: {dialogue if dialogue else "(none)"}

    CHARACTER REFERENCE DESCRIPTIONS (ground truth):
{char_block}

    Analyze the video and return ONLY valid JSON (no markdown fences) with these exact keys:

    {{
      "what_i_see": "2-3 sentence description of what actually happens in the video",
      "character_identity_consistency": {{
        "score": 0.0-1.0,
        "assessment": "Does character appearance remain stable throughout? Note any morphing/drift",
        "issues": []
      }},
      "location_consistency": {{
        "score": 0.0-1.0,
        "assessment": "Does the room/environment stay the same throughout?",
        "issues": []
      }},
      "lighting_consistency": {{
        "score": 0.0-1.0,
        "assessment": "Does lighting color temperature and direction stay stable?",
        "issues": []
      }},
      "object_persistence": {{
        "score": 0.0-1.0,
        "assessment": "Do props stay consistent? Anything appear or disappear unnaturally?",
        "issues": []
      }},
      "motion_quality": {{
        "score": 0.0-1.0,
        "assessment": "Is movement natural, fluid, continuous? Or frozen/robotic/teleporting?",
        "issues": []
      }},
      "composition_quality": {{
        "score": 0.0-1.0,
        "assessment": "Rule of thirds, headroom, lead room, framing appropriateness for shot type",
        "issues": []
      }},
      "beat_action_match": {{
        "score": 0.0-1.0,
        "assessment": "Does what actually happens match the expected beat action?",
        "issues": []
      }},
      "dialogue_lip_sync": {{
        "score": 0.0-1.0,
        "assessment": "For dialogue shots, does mouth movement match expected speech? N/A if no dialogue.",
        "issues": []
      }},
      "screen_position": {{
        "characters_detected": {{"name": "LEFT or RIGHT or CENTER"}},
        "assessment": "Which side of frame are characters positioned?"
      }},
      "character_description_observed": "Describe the physical appearance of each visible character (hair, clothing, build, skin). This will be compared against reference.",
      "overall_grade": "A/B/C/D/F",
      "overall_score": 0.0-1.0,
      "critical_issues": [],
      "recommended_regen": true/false,
      "regen_reason": "Why this shot needs regeneration, or empty string"
    }}
    """).strip()
    return prompt


def build_continuity_prompt(shot_a: dict, shot_b: dict) -> str:
    """Build the cross-video continuity comparison prompt."""
    def _brief(s: dict) -> str:
        return (
            f"Shot {s.get('shot_id')} ({s.get('shot_type')}) — "
            f"characters: {', '.join(s.get('characters', [])) or 'none'} — "
            f"beat: {s.get('_beat_action','')}"
        )

    prompt = textwrap.dedent(f"""
    You are a professional film editor reviewing continuity between two consecutive shots.

    CLIP A (outgoing): {_brief(shot_a)}
    CLIP B (incoming): {_brief(shot_b)}

    Watch both clips carefully. Focus on the TRANSITION from the END of Clip A to the START of Clip B.

    Return ONLY valid JSON (no markdown fences):

    {{
      "character_continuity": {{
        "score": 0.0-1.0,
        "assessment": "Do characters maintain consistent appearance, position, and state across the cut?",
        "issues": []
      }},
      "spatial_continuity": {{
        "score": 0.0-1.0,
        "assessment": "Is the room/set consistent across the cut? No teleportation?",
        "issues": []
      }},
      "lighting_continuity": {{
        "score": 0.0-1.0,
        "assessment": "Does the lighting match across the cut?",
        "issues": []
      }},
      "costume_continuity": {{
        "score": 0.0-1.0,
        "assessment": "Same clothing and props?",
        "issues": []
      }},
      "screen_position_continuity": {{
        "score": 0.0-1.0,
        "assessment": "Do character screen positions (LEFT/RIGHT) remain logical across the cut?",
        "issues": []
      }},
      "motion_logic": {{
        "score": 0.0-1.0,
        "assessment": "Is there spatial/temporal logic connecting how A ends and B begins?",
        "issues": []
      }},
      "overall_continuity_score": 0.0-1.0,
      "continuity_verdict": "PASS/WARNING/FAIL",
      "critical_continuity_issues": [],
      "edit_recommendation": "advice for the editor on this cut"
    }}
    """).strip()
    return prompt


# ── Main Analysis Pipeline ────────────────────────────────────────────────────

def load_data() -> tuple[list, dict]:
    """Load shot_plan.json and cast_map.json."""
    with open(SHOT_PLAN) as f:
        raw = json.load(f)
    shots = raw.get("shots", raw) if isinstance(raw, dict) else raw

    cast_map = {}
    if CAST_MAP.exists():
        with open(CAST_MAP) as f:
            cast_map = json.load(f)
    return shots, cast_map


def resolve_video_path(shot: dict) -> Optional[pathlib.Path]:
    """Resolve the absolute video path from a shot, trying multiple fields."""
    for field in ("video_path", "video_url"):
        v = shot.get(field)
        if v:
            # Strip leading /api/media?path= if present
            if "/api/media?path=" in str(v):
                v = str(v).split("/api/media?path=")[-1]
            p = pathlib.Path(v)
            # Try absolute path first
            if p.is_absolute() and p.exists():
                return p
            # Try relative to BASE_DIR
            rel = BASE_DIR / p
            if rel.exists():
                return rel
    return None


def analyze_all() -> dict:
    """Run the full deep video analysis pipeline."""
    print("=" * 70)
    print("ATLAS DEEP VIDEO ANALYSIS — Gemini 2.5 Flash Video Pipeline")
    print(f"Started: {datetime.datetime.now().isoformat()}")
    print("=" * 70)

    shots, cast_map = load_data()
    print(f"\nLoaded {len(shots)} shots, {len(cast_map)} characters\n")

    # ── Build scene → ordered shots mapping ──────────────────────────────────
    scenes: dict[str, list] = {}
    for shot in shots:
        if not isinstance(shot, dict):
            continue
        sid = shot.get("scene_id", "unknown")
        scenes.setdefault(sid, []).append(shot)

    # ── Collect unique video → shot mappings ─────────────────────────────────
    # A single video file may be referenced by multiple shots (e.g. Seedance groups).
    # We analyze each unique video file once, but store results per-shot.
    video_to_shots: dict[str, list] = {}
    for shot in shots:
        if not isinstance(shot, dict):
            continue
        vp = resolve_video_path(shot)
        if vp:
            key = str(vp)
            video_to_shots.setdefault(key, []).append(shot)

    print(f"Unique video files to analyze: {len(video_to_shots)}")
    for vp, shot_list in sorted(video_to_shots.items()):
        ids = [s["shot_id"] for s in shot_list]
        print(f"  {pathlib.Path(vp).name:45s} → shots: {ids}")

    # ── Results store ─────────────────────────────────────────────────────────
    results = {
        "metadata": {
            "project":    "victorian_shadows_ep1",
            "analyzed_at": datetime.datetime.now().isoformat(),
            "model":       GEMINI_FLASH,
            "total_shots": len(shots),
            "unique_videos": len(video_to_shots),
        },
        "per_video": {},        # keyed by shot_id
        "continuity": {},       # keyed by "scene_{sid}_N_to_N+1"
        "prompt_fidelity": {},  # keyed by shot_id
        "scene_summaries": {},  # keyed by scene_id
    }

    uploaded_uris: dict[str, str] = {}   # video_path_str → file_uri

    # ── PASS 1: Per-video analysis ────────────────────────────────────────────
    print("\n" + "─" * 70)
    print("PASS 1: Per-Video Analysis (uploading + analyzing each clip)")
    print("─" * 70)

    for video_path_str, shot_list in sorted(video_to_shots.items()):
        vp = pathlib.Path(video_path_str)
        print(f"\n[ {vp.name} ]")

        # Upload video
        file_uri = upload_video(vp)
        if not file_uri:
            print(f"  [SKIP] Could not upload {vp.name}")
            for shot in shot_list:
                results["per_video"][shot["shot_id"]] = {
                    "error": "upload_failed",
                    "video": vp.name,
                }
            continue

        uploaded_uris[video_path_str] = file_uri
        time.sleep(1)  # Brief pause after upload

        # Analyze for each shot that references this video
        # (usually 1, but Seedance groups map to multiple shots)
        for shot in shot_list:
            shot_id = shot["shot_id"]
            print(f"  Analyzing {shot_id}...")

            prompt_text = build_per_video_prompt(shot, cast_map)
            parts = [
                {"file_data": {"mime_type": "video/mp4", "file_uri": file_uri}},
                {"text": prompt_text},
            ]

            raw_response = gemini_generate(parts)
            time.sleep(RATE_LIMIT_DELAY)

            if raw_response:
                analysis = parse_json_response(raw_response)
                analysis["shot_id"]    = shot_id
                analysis["scene_id"]   = shot.get("scene_id")
                analysis["shot_type"]  = shot.get("shot_type")
                analysis["video_file"] = vp.name
                analysis["characters"] = shot.get("characters", [])
                analysis["has_dialogue"] = bool(shot.get("dialogue_text") or shot.get("_beat_dialogue"))
                results["per_video"][shot_id] = analysis

                grade = analysis.get("overall_grade", "?")
                score = analysis.get("overall_score", 0)
                regen = "⚠ REGEN" if analysis.get("recommended_regen") else "✓"
                print(f"    → Grade: {grade} | Score: {score:.2f} | {regen}")
                if analysis.get("critical_issues"):
                    for issue in analysis["critical_issues"][:3]:
                        print(f"       ! {issue}")
            else:
                results["per_video"][shot_id] = {"error": "gemini_failed", "video": vp.name}
                print(f"    → [FAILED] Gemini returned no response")

    # ── PASS 2: Cross-video continuity ────────────────────────────────────────
    print("\n" + "─" * 70)
    print("PASS 2: Cross-Video Continuity Analysis")
    print("─" * 70)

    for scene_id, scene_shots in sorted(scenes.items()):
        # Filter to shots with resolved video paths only, keep shot order
        scene_with_video = []
        for shot in scene_shots:
            vp = resolve_video_path(shot)
            if vp and str(vp) in uploaded_uris:
                scene_with_video.append((shot, str(vp)))

        if len(scene_with_video) < 2:
            continue

        print(f"\nScene {scene_id} — {len(scene_with_video)} shots with video")

        for i in range(len(scene_with_video) - 1):
            shot_a, vp_a = scene_with_video[i]
            shot_b, vp_b = scene_with_video[i + 1]

            key = f"scene_{scene_id}_{shot_a['shot_id']}_to_{shot_b['shot_id']}"
            print(f"  {shot_a['shot_id']} → {shot_b['shot_id']}...")

            uri_a = uploaded_uris[vp_a]
            uri_b = uploaded_uris[vp_b]

            prompt_text = build_continuity_prompt(shot_a, shot_b)

            # Send both videos together for side-by-side comparison
            parts = [
                {"text": "VIDEO A (outgoing shot):"},
                {"file_data": {"mime_type": "video/mp4", "file_uri": uri_a}},
                {"text": "VIDEO B (incoming shot):"},
                {"file_data": {"mime_type": "video/mp4", "file_uri": uri_b}},
                {"text": prompt_text},
            ]

            raw_response = gemini_generate(parts)
            time.sleep(RATE_LIMIT_DELAY)

            if raw_response:
                cont = parse_json_response(raw_response)
                cont["from_shot"]  = shot_a["shot_id"]
                cont["to_shot"]    = shot_b["shot_id"]
                cont["scene_id"]   = scene_id
                results["continuity"][key] = cont

                verdict = cont.get("continuity_verdict", "?")
                cscore  = cont.get("overall_continuity_score", 0)
                print(f"    → {verdict} | Score: {cscore:.2f}")
                for issue in cont.get("critical_continuity_issues", [])[:2]:
                    print(f"       ! {issue}")
            else:
                results["continuity"][key] = {"error": "gemini_failed"}
                print(f"    → [FAILED]")

    # ── PASS 3: Prompt Fidelity (semantic embedding) ──────────────────────────
    print("\n" + "─" * 70)
    print("PASS 3: Prompt Fidelity (embedding comparison)")
    print("─" * 70)

    for shot_id, video_result in results["per_video"].items():
        if "error" in video_result or "what_i_see" not in video_result:
            continue

        # Find original shot
        shot = next((s for s in shots if isinstance(s, dict) and s.get("shot_id") == shot_id), None)
        if not shot:
            continue

        intended = " ".join(filter(None, [
            shot.get("_beat_action", ""),
            shot.get("_beat_atmosphere", ""),
            shot.get("description", ""),
        ]))
        observed = video_result.get("what_i_see", "")

        if not intended or not observed:
            continue

        emb_intended = get_embedding(intended)
        emb_observed  = get_embedding(observed)
        similarity    = cosine_similarity(emb_intended, emb_observed)

        results["prompt_fidelity"][shot_id] = {
            "intended": intended[:300],
            "observed":  observed[:300],
            "semantic_similarity": round(similarity, 4),
            "fidelity_grade": (
                "HIGH" if similarity > 0.85 else
                "MEDIUM" if similarity > 0.70 else
                "LOW"
            ),
        }
        print(f"  {shot_id}: similarity={similarity:.3f} → {results['prompt_fidelity'][shot_id]['fidelity_grade']}")
        time.sleep(1)

    # ── PASS 4: Scene-level summaries ─────────────────────────────────────────
    print("\n" + "─" * 70)
    print("PASS 4: Scene-Level Summary Roll-up")
    print("─" * 70)

    for scene_id, scene_shots in sorted(scenes.items()):
        shot_ids    = [s["shot_id"] for s in scene_shots if isinstance(s, dict)]
        analyzed    = [results["per_video"][sid] for sid in shot_ids if sid in results["per_video"] and "error" not in results["per_video"][sid]]
        cont_keys   = [k for k in results["continuity"] if k.startswith(f"scene_{scene_id}_")]

        if not analyzed:
            continue

        scores    = [a.get("overall_score", 0) for a in analyzed]
        avg_score = sum(scores) / len(scores) if scores else 0

        grades    = [a.get("overall_grade", "F") for a in analyzed]
        grade_counts = {g: grades.count(g) for g in "ABCDF"}

        regen_list  = [a["shot_id"] for a in analyzed if a.get("recommended_regen")]
        all_issues  = []
        for a in analyzed:
            all_issues.extend(a.get("critical_issues", []))

        cont_scores = [results["continuity"][k].get("overall_continuity_score", 0)
                       for k in cont_keys if "error" not in results["continuity"].get(k, {})]
        avg_cont    = sum(cont_scores) / len(cont_scores) if cont_scores else None

        cont_fails  = [k for k in cont_keys
                       if results["continuity"].get(k, {}).get("continuity_verdict") == "FAIL"]

        summary = {
            "scene_id":            scene_id,
            "shots_analyzed":      len(analyzed),
            "avg_quality_score":   round(avg_score, 3),
            "grade_distribution":  {k: v for k, v in grade_counts.items() if v > 0},
            "shots_needing_regen": regen_list,
            "avg_continuity_score": round(avg_cont, 3) if avg_cont is not None else None,
            "continuity_failures": cont_fails,
            "top_issues": list(dict.fromkeys(all_issues))[:10],  # deduplicated
        }
        results["scene_summaries"][scene_id] = summary

        grade_str = ", ".join(f"{g}:{n}" for g, n in sorted(grade_counts.items()) if n > 0)
        print(f"  Scene {scene_id}: avg={avg_score:.2f} | grades=[{grade_str}] | regen={len(regen_list)} shots")
        if avg_cont is not None:
            print(f"    continuity={avg_cont:.2f} | failures={len(cont_fails)}")

    # ── Cleanup uploaded files ─────────────────────────────────────────────────
    print("\n[CLEANUP] Deleting uploaded Gemini files...")
    for uri in uploaded_uris.values():
        delete_file(uri)
    print(f"  Deleted {len(uploaded_uris)} files")

    return results


# ── Report Generation ─────────────────────────────────────────────────────────

GRADE_EMOJI = {"A": "✅", "B": "🟡", "C": "🟠", "D": "🔴", "F": "💀", "?": "❓"}
VERDICT_EMOJI = {"PASS": "✅", "WARNING": "⚠️", "FAIL": "❌"}


def generate_markdown_report(results: dict) -> str:
    lines = []
    meta = results["metadata"]

    lines += [
        "# ATLAS Deep Video Analysis Report",
        f"**Project:** {meta['project']}  ",
        f"**Analyzed:** {meta['analyzed_at']}  ",
        f"**Model:** {meta['model']}  ",
        f"**Shots:** {meta['total_shots']} total | {meta['unique_videos']} unique videos  ",
        "",
        "---",
        "",
        "## Executive Summary",
        "",
    ]

    # Overall stats
    all_analyzed = [v for v in results["per_video"].values() if "error" not in v]
    if all_analyzed:
        scores     = [a.get("overall_score", 0) for a in all_analyzed]
        avg        = sum(scores) / len(scores)
        regens     = sum(1 for a in all_analyzed if a.get("recommended_regen"))
        grade_dist = {}
        for a in all_analyzed:
            g = a.get("overall_grade", "?")
            grade_dist[g] = grade_dist.get(g, 0) + 1

        lines += [
            f"- **Videos analyzed:** {len(all_analyzed)}",
            f"- **Average quality score:** {avg:.2f}/1.0",
            f"- **Grade distribution:** " + " | ".join(f"{GRADE_EMOJI.get(g,'?')} {g}: {n}" for g, n in sorted(grade_dist.items())),
            f"- **Shots flagged for regeneration:** {regens}/{len(all_analyzed)}",
            "",
        ]

    # Continuity stats
    cont_results = [v for v in results["continuity"].values() if "error" not in v]
    if cont_results:
        passes  = sum(1 for c in cont_results if c.get("continuity_verdict") == "PASS")
        warns   = sum(1 for c in cont_results if c.get("continuity_verdict") == "WARNING")
        fails   = sum(1 for c in cont_results if c.get("continuity_verdict") == "FAIL")
        lines += [
            f"- **Continuity cuts analyzed:** {len(cont_results)}",
            f"  - {VERDICT_EMOJI['PASS']} PASS: {passes} | {VERDICT_EMOJI['WARNING']} WARNING: {warns} | {VERDICT_EMOJI['FAIL']} FAIL: {fails}",
            "",
        ]

    lines += ["---", "", "## Scene-by-Scene Analysis", ""]

    for scene_id, summary in sorted(results["scene_summaries"].items()):
        lines += [
            f"### Scene {scene_id}",
            f"- **Shots analyzed:** {summary['shots_analyzed']}",
            f"- **Avg quality score:** {summary['avg_quality_score']}",
            f"- **Grade distribution:** {summary['grade_distribution']}",
        ]
        if summary.get("avg_continuity_score") is not None:
            lines.append(f"- **Avg continuity score:** {summary['avg_continuity_score']}")
        if summary["shots_needing_regen"]:
            lines.append(f"- **⚠ Regen needed:** {', '.join(summary['shots_needing_regen'])}")
        if summary["continuity_failures"]:
            lines.append(f"- **❌ Continuity failures:** {', '.join(summary['continuity_failures'])}")
        if summary["top_issues"]:
            lines.append(f"- **Top issues:**")
            for issue in summary["top_issues"][:5]:
                lines.append(f"  - {issue}")
        lines.append("")

    lines += ["---", "", "## Per-Shot Details", ""]

    for shot_id, analysis in sorted(results["per_video"].items()):
        if "error" in analysis:
            lines += [f"### {shot_id} — ⛔ ERROR", f"Error: {analysis.get('error')}", ""]
            continue

        grade = analysis.get("overall_grade", "?")
        score = analysis.get("overall_score", 0)
        emoji = GRADE_EMOJI.get(grade, "❓")
        regen = " 🔄 REGEN" if analysis.get("recommended_regen") else ""

        lines += [
            f"### {shot_id} — {emoji} Grade {grade} (score: {score:.2f}){regen}",
            f"**Shot type:** {analysis.get('shot_type')} | "
            f"**Scene:** {analysis.get('scene_id')} | "
            f"**Characters:** {', '.join(analysis.get('characters', [])) or 'none'}",
            f"**File:** `{analysis.get('video_file', '')}`",
            "",
            f"**What Gemini sees:** {analysis.get('what_i_see', '')}",
            "",
        ]

        if analysis.get("character_description_observed"):
            lines += [f"**Characters observed:** {analysis['character_description_observed']}", ""]

        # Dimension scores
        dims = [
            ("Character Identity", "character_identity_consistency"),
            ("Location Consistency", "location_consistency"),
            ("Lighting Consistency", "lighting_consistency"),
            ("Object Persistence", "object_persistence"),
            ("Motion Quality", "motion_quality"),
            ("Composition", "composition_quality"),
            ("Beat Action Match", "beat_action_match"),
            ("Dialogue/Lip Sync", "dialogue_lip_sync"),
        ]
        for label, key in dims:
            dim = analysis.get(key, {})
            if isinstance(dim, dict):
                dscore = dim.get("score", "N/A")
                dassess = dim.get("assessment", "")
                score_str = f"{dscore:.2f}" if isinstance(dscore, float) else str(dscore)
                lines.append(f"- **{label}:** {score_str} — {dassess}")
                for issue in dim.get("issues", [])[:2]:
                    lines.append(f"  - ⚠ {issue}")

        if analysis.get("screen_position"):
            sp = analysis["screen_position"]
            lines += ["", f"**Screen positions:** {sp.get('characters_detected', {})} — {sp.get('assessment', '')}"]

        if analysis.get("critical_issues"):
            lines += ["", "**Critical issues:**"]
            for issue in analysis["critical_issues"]:
                lines.append(f"- 🚨 {issue}")

        if analysis.get("recommended_regen") and analysis.get("regen_reason"):
            lines += ["", f"**Regen reason:** {analysis['regen_reason']}"]

        # Prompt fidelity
        pf = results["prompt_fidelity"].get(shot_id)
        if pf:
            fgrade = pf["fidelity_grade"]
            sim    = pf["semantic_similarity"]
            fcolor = {"HIGH": "✅", "MEDIUM": "🟡", "LOW": "🔴"}.get(fgrade, "❓")
            lines += ["", f"**Prompt fidelity:** {fcolor} {fgrade} (similarity: {sim:.3f})"]
            if fgrade == "LOW":
                lines += [
                    f"  - Intended: _{pf['intended'][:150]}_",
                    f"  - Observed: _{pf['observed'][:150]}_",
                ]

        lines.append("")

    # Continuity cuts
    if results["continuity"]:
        lines += ["---", "", "## Continuity Analysis (Cut-by-Cut)", ""]

        for key, cont in sorted(results["continuity"].items()):
            if "error" in cont:
                lines += [f"### {cont.get('from_shot','?')} → {cont.get('to_shot','?')} — ⛔ ERROR", ""]
                continue

            verdict = cont.get("continuity_verdict", "?")
            cscore  = cont.get("overall_continuity_score", 0)
            emoji   = VERDICT_EMOJI.get(verdict, "❓")

            lines += [
                f"### {cont.get('from_shot','?')} → {cont.get('to_shot','?')} — {emoji} {verdict} (score: {cscore:.2f})",
                f"**Scene:** {cont.get('scene_id')}",
                "",
            ]

            cont_dims = [
                ("Character Continuity", "character_continuity"),
                ("Spatial Continuity", "spatial_continuity"),
                ("Lighting Continuity", "lighting_continuity"),
                ("Costume Continuity", "costume_continuity"),
                ("Screen Position", "screen_position_continuity"),
                ("Motion Logic", "motion_logic"),
            ]
            for label, key2 in cont_dims:
                dim = cont.get(key2, {})
                if isinstance(dim, dict):
                    dscore = dim.get("score", "N/A")
                    score_str = f"{dscore:.2f}" if isinstance(dscore, float) else str(dscore)
                    lines.append(f"- **{label}:** {score_str} — {dim.get('assessment', '')}")
                    for issue in dim.get("issues", [])[:2]:
                        lines.append(f"  - ⚠ {issue}")

            if cont.get("critical_continuity_issues"):
                lines += ["", "**Critical continuity issues:**"]
                for issue in cont["critical_continuity_issues"]:
                    lines.append(f"- 🚨 {issue}")

            if cont.get("edit_recommendation"):
                lines += ["", f"**Editor recommendation:** {cont['edit_recommendation']}"]

            lines.append("")

    lines += [
        "---",
        "",
        f"*Generated by ATLAS Deep Video Analysis — {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}*",
    ]

    return "\n".join(lines)


# ── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    # Allow passing a specific scene filter: python3 deep_video_analysis.py 002
    scene_filter = sys.argv[1] if len(sys.argv) > 1 else None
    if scene_filter:
        print(f"[INFO] Filtering to scene: {scene_filter}")

    os.chdir(BASE_DIR)  # Ensure relative paths resolve correctly

    results = analyze_all()

    # Save JSON report
    report_json_path = PROJECT_DIR / "deep_video_analysis_report.json"
    with open(report_json_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n[SAVED] JSON report → {report_json_path}")

    # Save Markdown report
    report_md = generate_markdown_report(results)
    report_md_path = PROJECT_DIR / "deep_video_analysis_summary.md"
    with open(report_md_path, "w") as f:
        f.write(report_md)
    print(f"[SAVED] Markdown report → {report_md_path}")

    # Print quick summary
    print("\n" + "=" * 70)
    print("ANALYSIS COMPLETE — QUICK SUMMARY")
    print("=" * 70)
    for scene_id, summary in sorted(results["scene_summaries"].items()):
        regen_str = f"  ⚠ REGEN: {', '.join(summary['shots_needing_regen'])}" if summary["shots_needing_regen"] else ""
        print(f"  Scene {scene_id}: avg={summary['avg_quality_score']:.2f} | grades={summary['grade_distribution']}{regen_str}")

    total_regens = sum(len(s["shots_needing_regen"]) for s in results["scene_summaries"].values())
    print(f"\nTotal shots flagged for regen: {total_regens}")
    print(f"\nFull reports:")
    print(f"  {report_json_path}")
    print(f"  {report_md_path}")
