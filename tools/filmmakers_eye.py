"""
ATLAS V36 — Filmmaker's Eye Analysis
Authority: OBSERVE_ONLY (V36 Section 0)
This module cannot modify shot_plan.json or any generation state.

Translates a cinematographer's instant visual assessment into
structured analysis that the failure_heatmap can consume.
"""

import json
import os
import base64
from pathlib import Path


# The 9-point visual contract (from the filmmaker)
VISUAL_CONTRACT = {
    "location_drift":        "Does this frame match the architectural DNA of this scene's location?",
    "character_position":    "Are characters in natural dynamic positions or frozen/stale mannequin poses?",
    "photorealism":          "Does this look like a real 35mm film frame? Skin texture, lighting, depth of field, grain.",
    "background_consistency":"Are props, furniture, architectural details consistent across shots?",
    "camera_storytelling":   "Does this angle serve the narrative? Close-up=emotion, wide=context, OTS=tension.",
    "motion_readiness":      "Could a character naturally start moving from this position? Room for action?",
    "shot_connection":       "Would this frame cut naturally from/to adjacent shots in the scene?",
    "narrative_read":        "What story does this single frame tell? Character intention visible in posture?",
    "script_fidelity":       "How well does this frame deliver what the prompt asked for?"
}


def build_gemini_prompt(shot_metadata: dict) -> str:
    """Build the Gemini Vision prompt using the filmmaker's 9-point contract."""
    nano = shot_metadata.get("nano_prompt", "No prompt available")
    sid = shot_metadata.get("shot_id", "???")
    location = shot_metadata.get("location", "Unknown")
    chars = shot_metadata.get("characters", [])
    char_names = [c.get("name", c) if isinstance(c, dict) else c for c in chars]
    has_chars = bool(char_names)

    char_line = (
        f"CHARACTERS EXPECTED: {', '.join(char_names)}"
        if has_chars
        else "CHARACTERS EXPECTED: NONE (empty room / B-roll shot)"
    )

    char_q2 = (
        "Are characters in natural poses, not frozen? Any stiff mannequin quality?"
        if has_chars
        else "Is the room truly EMPTY with no people, figures, or shadows of people visible?"
    )

    return f"""You are a veteran cinematographer reviewing a first frame for a Victorian mystery thriller.

SHOT: {sid}
LOCATION: {location}
{char_line}
PROMPT THAT GENERATED THIS: {nano[:500]}

START WITH your overall verdict on line 1 (before anything else):
VERDICT: APPROVE or FLAG or HARD_REGEN
PRIMARY_ISSUE: (LOCATION_DRIFT / STALE_POSE / AI_ARTIFACTS / WRONG_ANGLE / MISSING_CHARACTER / PHANTOM_PERSON / IDENTITY_DRIFT / CONTINUITY_BREAK / NONE)

Then answer each question with 1-2 sentences:
1. LOCATION_DRIFT: Does this look like {location}?
2. CHARACTER_POSITIONS: {char_q2}
3. PHOTOREALISM: Real 35mm film look or obvious AI artifacts?
4. BACKGROUND_CONSISTENCY: Props and set dressing correct for Victorian estate?
5. CAMERA_STORYTELLING: Does this angle serve the story beat?
6. MOTION_READY: Could the action in the prompt naturally begin from here?
7. SHOT_CONNECTION: Would this cut well with adjacent shots?
8. NARRATIVE_READ: One sentence — what story does this frame tell?
9. SCRIPT_FIDELITY: Does it deliver what the prompt asked? What is missing?"""


def analyze_frame(frame_path: str, shot_metadata: dict, gemini_api_key: str) -> dict:
    """
    Upload a frame to Gemini Vision and get the filmmaker's eye analysis.
    OBSERVE_ONLY — returns analysis dict, never writes to disk.
    """
    import requests

    if not os.path.exists(frame_path):
        return {
            "shot_id": shot_metadata.get("shot_id", "???"),
            "frame_path": frame_path,
            "analysis": "Frame file not found on disk.",
            "verdict": "NO_FRAME",
            "success": False,
        }

    with open(frame_path, "rb") as f:
        img_bytes = f.read()
    img_b64 = base64.b64encode(img_bytes).decode("utf-8")

    # Detect mime type by extension
    ext = Path(frame_path).suffix.lower()
    mime = "image/jpeg" if ext in (".jpg", ".jpeg") else "image/png"

    prompt = build_gemini_prompt(shot_metadata)

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.5-flash:generateContent?key={gemini_api_key}"
    )
    payload = {
        "contents": [
            {
                "parts": [
                    {"inline_data": {"mime_type": mime, "data": img_b64}},
                    {"text": prompt},
                ]
            }
        ],
        "generationConfig": {"maxOutputTokens": 2048},
    }

    try:
        resp = requests.post(url, json=payload, timeout=45)
        resp.raise_for_status()
        data = resp.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]

        # Simple keyword scan — no regex, no field parsing
        t = text.upper()
        if "HARD_REGEN" in t or ("REGEN" in t and "APPROVE" not in t and "FLAG" not in t):
            verdict = "HARD_REGEN"
        elif "FLAG" in t and "APPROVE" not in t:
            verdict = "FLAG"
        elif "APPROVE" in t:
            verdict = "APPROVE"
        else:
            verdict = "UNKNOWN"

        return {
            "shot_id": shot_metadata.get("shot_id", "???"),
            "frame_path": frame_path,
            "analysis": text,       # raw Gemini text, no parsing
            "verdict": verdict,
            "success": True,
        }

    except Exception as exc:
        return {
            "shot_id": shot_metadata.get("shot_id", "???"),
            "frame_path": frame_path,
            "analysis": f"ERROR: {exc}",
            "verdict": "ERROR",
            "success": False,
        }



def run_scene_audit(
    scene_id: str,
    shot_plan_path: str,
    frames_dir: str,
    gemini_api_key: str,
    verbose: bool = True,
) -> list:
    """
    Run filmmaker's eye on all frames in a scene.
    Returns a list of result dicts. OBSERVE_ONLY — nothing written.
    """
    with open(shot_plan_path) as f:
        raw = json.load(f)

    # Handle bare list vs {"shots": [...]} vs {shot_id: shot_obj}
    if isinstance(raw, list):
        all_shots = raw
    elif isinstance(raw, dict) and "shots" in raw:
        all_shots = raw["shots"]
    else:
        all_shots = list(raw.values())

    scene_shots = [
        s for s in all_shots
        if isinstance(s, dict) and s.get("shot_id", "").startswith(scene_id)
    ]

    if not scene_shots:
        print(f"[filmmakers_eye] No shots found for scene_id prefix '{scene_id}'")
        return []

    results = []
    for shot in scene_shots:
        sid = shot.get("shot_id", "???")

        # Find matching frame file (prefer exact match, then prefix match)
        frame_files = sorted(
            [f for f in os.listdir(frames_dir) if sid in f and f.lower().endswith((".jpg", ".jpeg", ".png"))]
        )
        if not frame_files:
            entry = {
                "shot_id": sid,
                "verdict": "NO_FRAME",
                "analysis": "Frame file not found in frames directory.",
                "frame_path": None,
                "success": False,
            }
            results.append(entry)
            if verbose:
                print(f"  [NO_FRAME ] {sid}")
            continue

        frame_path = os.path.join(frames_dir, frame_files[0])
        result = analyze_frame(frame_path, shot, gemini_api_key)
        results.append(result)

        if verbose:
            print(f"  [{result['verdict'].ljust(10)}] {sid}")

    return results


def summarise_audit(results: list) -> dict:
    """
    Produce a production-health summary from run_scene_audit results.
    Returns counts and a GREEN/YELLOW/RED rating (mirrors failure_heatmap thresholds).
    """
    total = len(results)
    if total == 0:
        return {"total": 0, "rating": "N/A"}

    approved    = sum(1 for r in results if r.get("verdict") == "APPROVE")
    flagged     = sum(1 for r in results if r.get("verdict") == "FLAG")
    hard_regen  = sum(1 for r in results if r.get("verdict") == "HARD_REGEN")
    errors      = sum(1 for r in results if r.get("verdict") in ("ERROR", "NO_FRAME"))

    first_pass_pct = approved / total * 100

    if first_pass_pct >= 90 and hard_regen == 0:
        rating = "GREEN"
    elif first_pass_pct >= 75 or hard_regen <= 1:
        rating = "YELLOW"
    else:
        rating = "RED"

    return {
        "total": total,
        "approved": approved,
        "flagged": flagged,
        "hard_regen": hard_regen,
        "errors": errors,
        "first_pass_pct": round(first_pass_pct, 1),
        "rating": rating,
    }


# ── CLI entrypoint ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    from dotenv import load_dotenv

    load_dotenv()
    key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not key:
        print("ERROR: GOOGLE_API_KEY not found in environment or .env")
        sys.exit(1)

    scene = sys.argv[1] if len(sys.argv) > 1 else "006"
    project = sys.argv[2] if len(sys.argv) > 2 else "victorian_shadows_ep1"

    base = Path(__file__).parent.parent / "pipeline_outputs" / project
    shot_plan = str(base / "shot_plan.json")
    frames_dir = str(base / "first_frames")

    print(f"\n[Filmmaker's Eye] Scene {scene} — {project}")
    print("=" * 60)

    results = run_scene_audit(scene, shot_plan, frames_dir, key, verbose=True)

    print("\n── Full Analysis ──")
    for r in results:
        print(f"\n{'='*60}")
        print(f"SHOT: {r['shot_id']}  |  VERDICT: {r['verdict']}  |  ISSUE: {r.get('primary_issue','?')}")
        print(r.get("analysis", "")[:600])

    print("\n── Scene Summary ──")
    summary = summarise_audit(results)
    print(json.dumps(summary, indent=2))
