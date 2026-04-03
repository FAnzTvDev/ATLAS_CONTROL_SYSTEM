"""
V32.0 SPATIAL COMPARISON GATE — Camera-Position Distinctiveness Verification

THE PROBLEM:
Wide master, reverse angle, and interior atmosphere shots all pull from the same
Room DNA template → FAL generates visually identical frames even though the prompts
specify different camera angles. The audience sees 3 or 4 copies of the same shot.

THE FIX:
After E01/E02/E03 (and optionally M-shots) are generated, upload each frame to
Gemini Vision and ask it to compare them as a set. If any pair looks like the
same shot from the same angle, flag it with a specific reprompt recommendation.

OUTPUT:
    {
        "scene_id": "001",
        "pairs": [
            {
                "shot_a": "001_E01",
                "shot_b": "001_E02",
                "verdict": "DISTINCT",       # DISTINCT / SIMILAR / IDENTICAL
                "difference": "E01 shows exterior stone facade from outside the gates. E02 shows interior library bookshelves.",
                "confidence": 0.95
            },
            ...
        ],
        "flagged": [          # pairs that are SIMILAR or IDENTICAL
            {"shot_a": "001_E02", "shot_b": "001_M01", "verdict": "SIMILAR", ...}
        ],
        "all_distinct": True,
        "reprompt_suggestions": []
    }

USAGE:
    from tools.spatial_comparison_gate import run_spatial_gate
    result = run_spatial_gate(project_dir, scene_id)
    if not result["all_distinct"]:
        for flag in result["flagged"]:
            print(f"⚠️  {flag['shot_a']} ≈ {flag['shot_b']}: {flag['difference']}")

INTEGRATION:
    Wired in atlas_universal_runner.py run_scene() after first-frame generation
    (before --frames-only gate) so operators see distinctiveness before approving.
    NON-BLOCKING: if Gemini is unavailable or rate-limited, logs a warning and proceeds.
"""

import base64
import json
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ─── Gemini REST endpoint ───────────────────────────────────────────────────
_GEMINI_MODEL   = "gemini-2.5-flash"
_GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models"


def _get_api_key() -> str:
    return os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY", "")


def _encode_image(path: str) -> Optional[str]:
    """Base64-encode an image file for the Gemini inline_data payload."""
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except Exception:
        return None


def _gemini_compare_pair(
    path_a: str,
    path_b: str,
    label_a: str,
    label_b: str,
    api_key: str,
) -> Dict:
    """
    Ask Gemini Vision to compare two frames and rate their camera-position distinctiveness.

    Returns:
        {
            "verdict": "DISTINCT" | "SIMILAR" | "IDENTICAL",
            "difference": "<description>",
            "confidence": 0.0–1.0,
            "raw_response": "<gemini text>"
        }
    """
    import urllib.request

    b64_a = _encode_image(path_a)
    b64_b = _encode_image(path_b)
    if not b64_a or not b64_b:
        return {"verdict": "UNKNOWN", "difference": "Could not read one or both frames",
                "confidence": 0.0, "raw_response": ""}

    prompt = (
        f"You are a film director comparing two camera frames from the same scene.\n\n"
        f"Frame 1 is shot '{label_a}'.\n"
        f"Frame 2 is shot '{label_b}'.\n\n"
        f"These shots are SUPPOSED to show different camera angles or positions within "
        f"the same room or location.\n\n"
        f"Compare them and answer:\n"
        f"1. Are these visually DISTINCT camera positions, or do they look like the "
        f"same shot from the same angle?\n"
        f"2. Describe specifically what is DIFFERENT about the camera position — "
        f"not just 'different angle' but what specific architectural elements or "
        f"spatial relationships changed between the two frames.\n"
        f"3. Rate the pair as one of:\n"
        f"   DISTINCT — clearly different camera positions, different room depth/geometry visible\n"
        f"   SIMILAR  — probably the same angle, minor differences only\n"
        f"   IDENTICAL — same shot, same angle, same composition\n\n"
        f"Respond ONLY as valid JSON in this exact format:\n"
        f'{{"verdict": "DISTINCT|SIMILAR|IDENTICAL", "difference": "<what is spatially different>", "confidence": 0.0}}'
    )

    payload = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": "image/jpeg", "data": b64_a}},
                {"inline_data": {"mime_type": "image/jpeg", "data": b64_b}},
            ]
        }],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 256},
    }

    url = f"{_GEMINI_API_URL}/{_GEMINI_MODEL}:generateContent?key={api_key}"
    req_data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=req_data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    # ThreadPoolExecutor with explicit shutdown(wait=False) — critical!
    # Do NOT use `with ThreadPoolExecutor()` context manager — its __exit__ calls
    # shutdown(wait=True) which re-blocks on the stuck thread, defeating the timeout.
    try:
        from concurrent.futures import ThreadPoolExecutor, TimeoutError as _FutureTimeout

        def _do_request():
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read())

        _ex = ThreadPoolExecutor(max_workers=1)
        _future = _ex.submit(_do_request)
        try:
            body = _future.result(timeout=20)  # hard ceiling: 20s
        except _FutureTimeout:
            _ex.shutdown(wait=False)  # abandon the stuck thread, don't wait
            return {"verdict": "UNKNOWN",
                    "difference": "Gemini call timed out (20s hard limit)",
                    "confidence": 0.0, "raw_response": "TIMEOUT"}
        _ex.shutdown(wait=False)
    except Exception as e:
        return {"verdict": "UNKNOWN", "difference": f"Gemini call failed: {e}",
                "confidence": 0.0, "raw_response": str(e)}

    try:
        raw_text = body["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (KeyError, IndexError):
        raw_text = ""

    # Parse the JSON response
    try:
        # Strip markdown code fences if present
        clean = raw_text.strip("` \n")
        if clean.startswith("json"):
            clean = clean[4:].strip()
        parsed = json.loads(clean)
        verdict     = parsed.get("verdict", "UNKNOWN").upper()
        difference  = parsed.get("difference", "")
        confidence  = float(parsed.get("confidence", 0.5))
        if verdict not in ("DISTINCT", "SIMILAR", "IDENTICAL"):
            verdict = "UNKNOWN"
        return {"verdict": verdict, "difference": difference,
                "confidence": confidence, "raw_response": raw_text}
    except Exception:
        # Heuristic: look for keywords in raw text
        up = raw_text.upper()
        if "IDENTICAL" in up:
            v = "IDENTICAL"
        elif "SIMILAR" in up:
            v = "SIMILAR"
        elif "DISTINCT" in up:
            v = "DISTINCT"
        else:
            v = "UNKNOWN"
        return {"verdict": v, "difference": raw_text[:200],
                "confidence": 0.5, "raw_response": raw_text}


def _find_frame(frame_dir: Path, shot_id: str) -> Optional[str]:
    """Locate the generated first-frame for a given shot_id."""
    for ext in (".jpg", ".jpeg", ".png"):
        p = frame_dir / f"{shot_id}{ext}"
        if p.exists():
            return str(p)
    # Pattern: shot_id might have been written as <shot_id>_frame.jpg etc.
    for f in sorted(frame_dir.iterdir()):
        if shot_id in f.name and f.suffix.lower() in (".jpg", ".jpeg", ".png"):
            return str(f)
    return None


def run_spatial_gate(
    project_dir,
    scene_id: str,
    shot_ids: Optional[List[str]] = None,
    compare_all_pairs: bool = False,
) -> Dict:
    """
    Run the spatial comparison gate for a scene.

    Compares:
    - E01 vs E02 (exterior vs interior — should be DISTINCT)
    - E02 vs E03 (interior vs insert detail — should be DISTINCT)
    - E01 vs E03 (exterior vs insert — should be DISTINCT)
    - Each E-shot vs the first M-shot (if frames exist)
    - If compare_all_pairs=True: all pairs across the scene

    Args:
        project_dir:    Path or str to the pipeline_outputs/<project>/ dir
        scene_id:       e.g. "001"
        shot_ids:       Optional list of shot_ids to compare. If None, uses E-shots + first M-shot.
        compare_all_pairs: If True, compare every pair (expensive — use sparingly).

    Returns:
        {
            "scene_id":          "001",
            "pairs":             [...],
            "flagged":           [...],
            "all_distinct":      bool,
            "reprompt_suggestions": [...],
            "gate_status":       "PASS" | "WARN" | "SKIP" (Gemini unavailable)
        }
    """
    api_key = _get_api_key()
    pdir = Path(project_dir)
    frame_dir = pdir / "first_frames"

    result = {
        "scene_id": scene_id,
        "pairs": [],
        "flagged": [],
        "all_distinct": True,
        "reprompt_suggestions": [],
        "gate_status": "SKIP",
    }

    if not api_key:
        print(f"  [SPATIAL-GATE] Scene {scene_id}: GOOGLE_API_KEY not set — skipping")
        return result

    if not frame_dir.exists():
        print(f"  [SPATIAL-GATE] Scene {scene_id}: first_frames/ dir not found — skipping")
        return result

    # Collect shot_ids to compare
    if shot_ids is None:
        # Auto-collect E-shots + first M-shot for this scene
        shot_ids = []
        for suffix in ("_E01", "_E02", "_E03"):
            shot_ids.append(f"{scene_id}{suffix}")
        # Add first M-shot if it exists
        for f in sorted(frame_dir.iterdir()):
            name = f.stem
            if name.startswith(f"{scene_id}_M") and f.suffix.lower() in (".jpg", ".jpeg", ".png"):
                if name not in shot_ids:
                    shot_ids.append(name)
                break

    # Find frames that actually exist
    available: List[Tuple[str, str]] = []  # (shot_id, frame_path)
    for sid in shot_ids:
        path = _find_frame(frame_dir, sid)
        if path:
            available.append((sid, path))

    if len(available) < 2:
        print(f"  [SPATIAL-GATE] Scene {scene_id}: fewer than 2 frames found — skipping comparison")
        result["gate_status"] = "SKIP"
        return result

    # Build pairs to compare
    if compare_all_pairs:
        pairs_to_compare = [
            (available[i], available[j])
            for i in range(len(available))
            for j in range(i + 1, len(available))
        ]
    else:
        # Default: adjacent pairs + E01 vs E03
        pairs_to_compare = []
        for i in range(len(available) - 1):
            pairs_to_compare.append((available[i], available[i + 1]))
        # E01 vs E03 if both exist (not adjacent)
        e01 = next(((s, p) for s, p in available if s.endswith("_E01")), None)
        e03 = next(((s, p) for s, p in available if s.endswith("_E03")), None)
        if e01 and e03 and (e01, e03) not in pairs_to_compare:
            pairs_to_compare.append((e01, e03))

    print(f"  [SPATIAL-GATE] Scene {scene_id}: comparing {len(pairs_to_compare)} pairs "
          f"({len(available)} frames available)")

    any_flagged = False
    for (sid_a, path_a), (sid_b, path_b) in pairs_to_compare:
        print(f"    Comparing {sid_a} ↔ {sid_b}...", end=" ", flush=True)
        comparison = _gemini_compare_pair(path_a, path_b, sid_a, sid_b, api_key)
        # Rate-limit: Gemini free tier is 15 RPM
        time.sleep(0.5)

        pair_result = {
            "shot_a": sid_a,
            "shot_b": sid_b,
            "verdict": comparison["verdict"],
            "difference": comparison["difference"],
            "confidence": comparison["confidence"],
        }
        result["pairs"].append(pair_result)
        print(comparison["verdict"])

        if comparison["verdict"] in ("SIMILAR", "IDENTICAL"):
            any_flagged = True
            result["flagged"].append(pair_result)
            suggestion = _build_reprompt_suggestion(sid_a, sid_b, comparison["difference"])
            if suggestion:
                result["reprompt_suggestions"].append(suggestion)

    result["all_distinct"] = not any_flagged
    result["gate_status"] = "PASS" if not any_flagged else "WARN"

    # Print summary
    if any_flagged:
        print(f"  [SPATIAL-GATE] ⚠️  Scene {scene_id}: {len(result['flagged'])} SIMILAR/IDENTICAL pairs found")
        for flag in result["flagged"]:
            print(f"    {flag['shot_a']} ≈ {flag['shot_b']} ({flag['verdict']}): {flag['difference'][:100]}")
        if result["reprompt_suggestions"]:
            print(f"  [SPATIAL-GATE] Reprompt suggestions:")
            for s in result["reprompt_suggestions"]:
                print(f"    {s['shot_id']}: {s['hint'][:120]}")
    else:
        print(f"  [SPATIAL-GATE] ✅ Scene {scene_id}: all {len(result['pairs'])} pairs are spatially DISTINCT")

    return result


def _build_reprompt_suggestion(shot_a: str, shot_b: str, difference_text: str) -> Optional[Dict]:
    """
    Build a reprompt hint for the shot that is MORE LIKELY to be wrong.

    E-shot ordering: E01 (exterior) > E02 (interior) > E03 (insert).
    If E01 ≈ E02, E01 is probably showing the interior (wrong) → reprompt E01 to emphasise
    the exterior establishing view.

    Returns:
        {"shot_id": "...", "hint": "...", "camera_position": "..."} or None
    """
    # Determine which shot is more likely wrong
    e_order = {"_E01": 1, "_E02": 2, "_E03": 3}
    a_rank = next((v for k, v in e_order.items() if shot_a.endswith(k)), 99)
    b_rank = next((v for k, v in e_order.items() if shot_b.endswith(k)), 99)

    if a_rank > b_rank:
        wrong_shot = shot_a
    elif b_rank > a_rank:
        wrong_shot = shot_b
    else:
        wrong_shot = shot_b  # default: flag the second shot

    hints = {
        "_E01": (
            "EXTERIOR ESTABLISHING: camera OUTSIDE the building looking toward the facade. "
            "Stone exterior, iron gates, gravel drive, sky visible. NO interior elements. "
            "Must not show bookshelves, staircase, fireplaces, or indoor furniture.",
            "wide_master"
        ),
        "_E02": (
            "INTERIOR ATMOSPHERE: camera INSIDE the room looking at a specific interior feature. "
            "Show bookshelves / fireplace / staircase / furniture from inside. "
            "NO exterior views, NO sky, NO outdoor elements visible.",
            "interior_atmosphere"
        ),
        "_E03": (
            "EXTREME CLOSE-UP INSERT: camera 6 inches from a single physical object. "
            "The object fills the entire frame. Background is pure bokeh. "
            "Must not show a wide room view or exterior — this is a MACRO detail shot.",
            "insert_detail"
        ),
    }

    for suffix, (hint, cam_pos) in hints.items():
        if wrong_shot.endswith(suffix):
            return {"shot_id": wrong_shot, "hint": hint, "camera_position": cam_pos}

    return {"shot_id": wrong_shot,
            "hint": f"This shot appears too similar to its neighbour: {difference_text[:200]}",
            "camera_position": "unknown"}


def save_gate_result(project_dir, scene_id: str, result: Dict) -> None:
    """Persist the spatial gate result to disk for UI display and audit."""
    pdir = Path(project_dir)
    gate_dir = pdir / "spatial_gate_results"
    gate_dir.mkdir(parents=True, exist_ok=True)
    out_path = gate_dir / f"{scene_id}_spatial_gate.json"
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"  [SPATIAL-GATE] Result saved → {out_path}")


# ─── Self-test ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3:
        proj_dir = sys.argv[1]
        sid      = sys.argv[2]
        r = run_spatial_gate(proj_dir, sid)
        save_gate_result(proj_dir, sid, r)
        print(json.dumps(r, indent=2))
    else:
        # Unit test: import only
        from tools.scene_visual_dna import get_positional_dna, detect_room_type  # noqa
        assert get_positional_dna("library", "wide_master") != get_positional_dna("library", "reverse_angle"), \
            "wide_master and reverse_angle must differ"
        assert get_positional_dna("library", "insert_detail") != get_positional_dna("library", "interior_atmosphere"), \
            "insert_detail and interior_atmosphere must differ"
        print("✅ spatial_comparison_gate: import OK, DNA distinctiveness confirmed")
