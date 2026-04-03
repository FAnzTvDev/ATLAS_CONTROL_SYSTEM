#!/usr/bin/env python3
"""
ATLAS Gemini Video Analysis — Full MP4 Upload to Gemini Files API
Analyzes all production videos for identity, location, motion quality,
temporal consistency, composition, and prompt adherence.
"""

import json
import os
import sys
import time
import urllib.request as _req
import urllib.error
from pathlib import Path

# ── Config ──────────────────────────────────────────────────────────────────
BASE = Path("/Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM/pipeline_outputs/victorian_shadows_ep1")
KLING_LITE = BASE / "videos_kling_lite"
SEEDANCE_LITE = BASE / "videos_seedance_lite"

# Load env
env_path = Path("/Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM/.env")
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
GEMINI_MODEL = "gemini-2.5-flash"

# ── Shot plan ────────────────────────────────────────────────────────────────
with open(BASE / "shot_plan.json") as f:
    raw = json.load(f)
shots_list = raw if isinstance(raw, list) else raw.get("shots", [])
shots_by_id = {s["shot_id"]: s for s in shots_list}

# ── Cast map ─────────────────────────────────────────────────────────────────
with open(BASE / "cast_map.json") as f:
    cast_map = json.load(f)

CHAR_APPEARANCES = {
    "NADIA COLE": "young woman, 28, dark brown skin, intelligent brown eyes, natural textured hair, jeans and vintage band t-shirt under open flannel",
    "THOMAS BLACKWOOD": "man, 62, distinguished silver hair, weathered face lined with grief, rumpled navy suit",
    "ELEANOR VOSS": "woman, 34, sharp features, auburn hair pulled back severely, tailored charcoal blazer over black turtleneck",
    "RAYMOND CROSS": "man, 45, stocky build, thinning dark hair, sharp suspicious eyes, expensive overcoat over silk shirt",
    "HARRIET HARGROVE": "stern woman in Victorian dress, aristocratic bearing, imposing presence",
}

# ── Build video → shot mapping ───────────────────────────────────────────────
# Scene 001 kling videos (in kling_lite, not in shot_plan video_path)
SCENE_001_KLING = {
    "001_M01": KLING_LITE / "multishot_g1_001_M01.mp4",
    "001_M02": KLING_LITE / "multishot_g2_001_M02.mp4",
    "001_M03": KLING_LITE / "multishot_g3_001_M03.mp4",
    "001_M04": KLING_LITE / "multishot_g4_001_M04.mp4",
    "001_M05": KLING_LITE / "multishot_g5_001_M05.mp4",
}
# Scene 002 kling videos
SCENE_002_KLING = {
    "002_E01": KLING_LITE / "multishot_g1_002_E01.mp4",
    "002_E02": KLING_LITE / "multishot_g2_002_E02.mp4",
    "002_E03": KLING_LITE / "multishot_g3_002_E03.mp4",
    "002_M01": KLING_LITE / "multishot_g4_002_M01.mp4",
    "002_M02": KLING_LITE / "multishot_g5_002_M02.mp4",
    "002_M03": KLING_LITE / "multishot_g6_002_M03.mp4",
    "002_M04": KLING_LITE / "multishot_g7_002_M04.mp4",
}
# Scene 006 kling videos
SCENE_006_KLING = {
    "006_E01": KLING_LITE / "multishot_g1_006_E01.mp4",
    "006_E02": KLING_LITE / "multishot_g2_006_E02.mp4",
    "006_E03": KLING_LITE / "multishot_g3_006_E03.mp4",
    "006_M01": KLING_LITE / "multishot_g4_006_M01.mp4",
    "006_M02": KLING_LITE / "multishot_g5_006_M02.mp4",
    "006_M03": KLING_LITE / "multishot_g6_006_M03.mp4",
    "006_M04": KLING_LITE / "multishot_g7_006_M04.mp4",
}

ALL_VIDEOS = {}
ALL_VIDEOS.update(SCENE_001_KLING)
ALL_VIDEOS.update(SCENE_002_KLING)
ALL_VIDEOS.update(SCENE_006_KLING)


# ── Gemini Files API ─────────────────────────────────────────────────────────

def upload_video_to_gemini(video_path: Path) -> str | None:
    """Upload a video file to Gemini Files API. Returns fileUri or None on failure."""
    if not video_path.exists():
        print(f"  [SKIP] File not found: {video_path.name}")
        return None

    file_size = video_path.stat().st_size
    print(f"  Uploading {video_path.name} ({file_size/1024/1024:.1f} MB)...")

    # Step 1: initiate resumable upload
    url = f"https://generativelanguage.googleapis.com/upload/v1beta/files?uploadType=resumable&key={GOOGLE_API_KEY}"
    init_payload = json.dumps({
        "file": {"display_name": video_path.name, "mimeType": "video/mp4"}
    }).encode("utf-8")

    try:
        init_req = _req.Request(url, data=init_payload, headers={
            "Content-Type": "application/json",
            "X-Goog-Upload-Protocol": "resumable",
            "X-Goog-Upload-Command": "start",
            "X-Goog-Upload-Header-Content-Type": "video/mp4",
            "X-Goog-Upload-Header-Content-Length": str(file_size),
        })
        with _req.urlopen(init_req, timeout=30) as resp:
            upload_url = resp.getheader("X-Goog-Upload-URL")
        if not upload_url:
            print(f"  [ERROR] No upload URL in response headers")
            return None
    except Exception as e:
        print(f"  [ERROR] Init upload failed: {e}")
        return None

    # Step 2: upload the bytes
    try:
        video_bytes = video_path.read_bytes()
        upload_req = _req.Request(upload_url, data=video_bytes, headers={
            "Content-Type": "video/mp4",
            "X-Goog-Upload-Command": "upload, finalize",
            "X-Goog-Upload-Offset": "0",
        }, method="PUT")
        with _req.urlopen(upload_req, timeout=120) as resp:
            result = json.loads(resp.read())
        file_uri = result.get("file", {}).get("uri", "")
        if file_uri:
            print(f"  ✓ Uploaded → {file_uri}")
            return file_uri
        else:
            print(f"  [ERROR] Upload succeeded but no URI: {result}")
            return None
    except Exception as e:
        print(f"  [ERROR] Upload bytes failed: {e}")
        return None


def wait_for_file_active(file_uri: str, max_wait: int = 120) -> bool:
    """Poll until the Gemini file is in ACTIVE state (processing complete)."""
    # Extract file name from URI: files/{name}
    file_name = file_uri.replace("https://generativelanguage.googleapis.com/v1beta/", "")
    url = f"https://generativelanguage.googleapis.com/v1beta/{file_name}?key={GOOGLE_API_KEY}"
    waited = 0
    while waited < max_wait:
        try:
            with _req.urlopen(url, timeout=10) as resp:
                data = json.loads(resp.read())
            state = data.get("state", "UNKNOWN")
            if state == "ACTIVE":
                return True
            if state == "FAILED":
                print(f"  [ERROR] File processing FAILED")
                return False
            print(f"  Waiting for processing (state={state})...")
            time.sleep(5)
            waited += 5
        except Exception as e:
            print(f"  [WARN] Status poll failed: {e}")
            time.sleep(5)
            waited += 5
    print(f"  [TIMEOUT] File not active after {max_wait}s")
    return False


def delete_gemini_file(file_uri: str) -> None:
    """Clean up uploaded file after analysis."""
    file_name = file_uri.replace("https://generativelanguage.googleapis.com/v1beta/", "")
    url = f"https://generativelanguage.googleapis.com/v1beta/{file_name}?key={GOOGLE_API_KEY}"
    try:
        req = _req.Request(url, method="DELETE")
        _req.urlopen(req, timeout=10)
    except Exception:
        pass  # Best-effort cleanup


def analyze_video_with_gemini(file_uri: str, shot_id: str, shot_data: dict) -> dict:
    """Send uploaded video to Gemini for comprehensive analysis."""
    characters = shot_data.get("characters", [])
    shot_type = shot_data.get("shot_type", "")
    nano_prompt = shot_data.get("nano_prompt", "")[:300]
    dialogue = shot_data.get("dialogue_text", "") or ""
    location = shot_data.get("location", "")
    beat_action = shot_data.get("_beat_action", "") or ""
    scene_id = shot_id[:3]

    # Build character block
    char_lines = []
    for c in characters:
        app = CHAR_APPEARANCES.get(c, cast_map.get(c, {}).get("appearance", "unknown") if isinstance(cast_map.get(c), dict) else "unknown")
        char_lines.append(f"- {c}: {app}")
    char_block = "\n".join(char_lines) if char_lines else "None (establishing/B-roll shot)"

    # Build character identity key list for prompt
    char_keys = ", ".join(f'"{c}"' for c in characters) if characters else ""
    has_dialogue = bool(dialogue)

    # Build the analysis prompt
    analysis_prompt = f"""You are a professional film quality control analyst for a Victorian gothic drama.
Analyze this video clip and return a single JSON object.

SHOT INFO:
Shot ID: {shot_id} | Type: {shot_type} | Location: {location}
Beat: {beat_action}
Dialogue: {dialogue if dialogue else 'None'}
Expected characters: {', '.join(characters) if characters else 'None (establishing/empty shot)'}

Character appearances:
{char_block}

Intended content (nano_prompt):
{nano_prompt}

Return ONLY a JSON object with these exact string keys:
- identity_scores: object with score 0.0-1.0 per expected character (empty object if no characters)
- identity_issues: string describing any identity drift, wrong person, phantom characters
- location_accuracy: number 0.0-1.0
- location_issues: string describing room/setting problems
- motion_quality: number 0.0-1.0 (1.0=smooth natural motion, 0.0=completely frozen)
- motion_issues: string describing frozen frames, stuttering, morphing artifacts
- temporal_consistency: number 0.0-1.0 (lighting, costume, reality stability across clip)
- temporal_issues: string
- composition_quality: number 0.0-1.0 (framing, blocking, shot type match)
- composition_issues: string
- prompt_adherence: number 0.0-1.0 (does video match intended prompt)
- prompt_issues: string
- dialogue_sync: number 0.0-1.0 or "no_dialogue" if no dialogue expected
- dialogue_sync_issues: string
- pacing: number 0.0-1.0
- pacing_issues: string
- overall_score: number 0.0-1.0
- verdict: string, one of PASS WARN or FAIL
- primary_issue: string, the single most critical problem
- fix_approach: string, specific actionable fix
- regen_priority: string, one of HIGH MEDIUM or LOW"""

    # Call Gemini API — force JSON output mode
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GOOGLE_API_KEY}"
    payload = json.dumps({
        "contents": [{"parts": [
            {"fileData": {"mimeType": "video/mp4", "fileUri": file_uri}},
            {"text": analysis_prompt},
        ]}],
        "generationConfig": {
            "maxOutputTokens": 2048,
            "temperature": 0.1,
            "responseMimeType": "application/json",
        },
    }).encode("utf-8")

    try:
        req = _req.Request(url, data=payload, headers={"Content-Type": "application/json"})
        with _req.urlopen(req, timeout=90) as resp:
            result = json.loads(resp.read())
        text = result["candidates"][0]["content"]["parts"][0]["text"].strip()

        # Primary parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Strip markdown fences
        if "```" in text:
            import re as _re
            m = _re.search(r'```(?:json)?\s*([\s\S]+?)```', text)
            if m:
                try:
                    return json.loads(m.group(1).strip())
                except Exception:
                    pass

        # Find outermost JSON object by brace matching
        import re as _re
        start = text.find('{')
        if start >= 0:
            depth = 0
            for i, ch in enumerate(text[start:], start):
                if ch == '{':
                    depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(text[start:i+1])
                        except Exception:
                            break

        return {"error": f"Could not parse JSON", "raw": text[:800]}

    except Exception as e:
        return {"error": str(e)}


# ── Semantic embedding comparison ────────────────────────────────────────────

def embed_text(text: str) -> list | None:
    """Get Gemini embedding for text."""
    url = (f"https://generativelanguage.googleapis.com/v1beta"
           f"/models/gemini-embedding-001:embedContent?key={GOOGLE_API_KEY}")
    payload = json.dumps({
        "content": {"parts": [{"text": text[:4000]}]},
        "taskType": "SEMANTIC_SIMILARITY",
    }).encode("utf-8")
    try:
        req = _req.Request(url, data=payload, headers={"Content-Type": "application/json"})
        with _req.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
        return result["embedding"]["values"]
    except Exception as e:
        return None


def cosine_sim(a, b) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x*y for x,y in zip(a,b))
    ma = sum(x*x for x in a)**0.5
    mb = sum(x*x for x in b)**0.5
    return max(0.0, min(1.0, dot/(ma*mb))) if ma and mb else 0.0


# ── Main analysis loop ───────────────────────────────────────────────────────

def run_analysis():
    if not GOOGLE_API_KEY:
        print("ERROR: GOOGLE_API_KEY not set")
        sys.exit(1)

    print(f"\n{'='*70}")
    print("ATLAS GEMINI VIDEO QUALITY ANALYSIS")
    print(f"Model: {GEMINI_MODEL} | Videos: {len(ALL_VIDEOS)} shots")
    print(f"{'='*70}\n")

    results = []
    total = len(ALL_VIDEOS)

    for idx, (shot_id, video_path) in enumerate(sorted(ALL_VIDEOS.items()), 1):
        print(f"\n[{idx}/{total}] Analyzing {shot_id} — {video_path.name}")

        # Get shot data
        shot_data = shots_by_id.get(shot_id, {})
        if not shot_data:
            print(f"  [WARN] No shot data found for {shot_id}")
            shot_data = {
                "shot_type": "unknown",
                "characters": [],
                "nano_prompt": shot_id,
                "dialogue_text": None,
                "location": "unknown",
            }

        if not video_path.exists():
            print(f"  [SKIP] Video not found: {video_path}")
            results.append({
                "shot_id": shot_id, "filename": video_path.name,
                "error": "file_not_found", "verdict": "ERROR"
            })
            continue

        # Upload video
        file_uri = upload_video_to_gemini(video_path)
        if not file_uri:
            results.append({
                "shot_id": shot_id, "filename": video_path.name,
                "error": "upload_failed", "verdict": "ERROR"
            })
            continue

        # Wait for processing
        if not wait_for_file_active(file_uri):
            delete_gemini_file(file_uri)
            results.append({
                "shot_id": shot_id, "filename": video_path.name,
                "error": "processing_failed", "verdict": "ERROR"
            })
            continue

        # Analyze
        print(f"  Analyzing with Gemini {GEMINI_MODEL}...")
        analysis = analyze_video_with_gemini(file_uri, shot_id, shot_data)

        # Prompt adherence via embedding (optional enrichment)
        nano_prompt = shot_data.get("nano_prompt", "")
        prompt_embed_score = None
        if nano_prompt and not analysis.get("error"):
            prompt_issues = str(analysis.get("prompt_issues") or "")
            if prompt_issues and prompt_issues != "none":
                vec_prompt = embed_text(nano_prompt)
                vec_pi = embed_text(prompt_issues)
                if vec_prompt and vec_pi:
                    # Low similarity between prompt and issues description = issues are off-topic = better match
                    prompt_embed_score = round(1.0 - cosine_sim(vec_prompt, vec_pi), 3)

        # Cleanup
        delete_gemini_file(file_uri)

        # Store result
        result = {
            "shot_id": shot_id,
            "filename": video_path.name,
            "scene_id": shot_id[:3],
            "shot_type": shot_data.get("shot_type",""),
            "characters": shot_data.get("characters",[]),
            "location": shot_data.get("location",""),
            "nano_prompt": (nano_prompt or "")[:150],
            "analysis": analysis,
        }
        if prompt_embed_score is not None:
            result["prompt_embed_score"] = prompt_embed_score
        results.append(result)

        # Print summary
        if "error" in analysis:
            print(f"  [ERROR] {analysis.get('error','unknown')}")
        else:
            verdict = analysis.get("verdict", "?")
            overall = analysis.get("overall_score", 0)
            try:
                overall_f = f"{float(overall):.2f}"
            except (TypeError, ValueError):
                overall_f = str(overall)
            primary = str(analysis.get("primary_issue") or "")
            regen_pri = analysis.get("regen_priority", "?")
            print(f"  → Verdict: {verdict} | Overall: {overall_f} | Regen: {regen_pri}")
            if primary:
                print(f"  → Primary issue: {primary[:100]}")

        # Incremental save after each shot
        results_path_tmp = BASE / "gemini_video_analysis_results.json"
        with open(results_path_tmp, "w") as f:
            json.dump(results, f, indent=2)

        # Rate limit respect (free tier: 15 RPM)
        time.sleep(4)

    return results


def generate_report(results: list) -> str:
    """Generate the comprehensive markdown report."""
    lines = []
    lines.append("# ATLAS GEMINI VIDEO QUALITY ANALYSIS REPORT")
    lines.append(f"**Date:** 2026-03-25 | **Model:** {GEMINI_MODEL} | **Total shots:** {len(results)}")
    lines.append("")

    # Summary table
    lines.append("## SUMMARY TABLE\n")
    lines.append("| Shot ID | Filename | Verdict | Overall | Regen Priority | Primary Issue |")
    lines.append("|---------|----------|---------|---------|----------------|---------------|")

    for r in results:
        a = r.get("analysis", {})
        if "error" in a:
            lines.append(f"| {r['shot_id']} | {r['filename']} | ERROR | — | — | {a.get('error','')} |")
        else:
            verdict = a.get("verdict", "?")
            overall = a.get("overall_score", 0)
            regen = a.get("regen_priority", "?")
            primary = (a.get("primary_issue", "") or "")[:60]
            lines.append(f"| {r['shot_id']} | {r['filename']} | {verdict} | {overall:.2f} | {regen} | {primary} |")

    lines.append("")

    # Score breakdown
    lines.append("## SCORE BREAKDOWN BY SCENE\n")
    score_fields = ["identity_scores", "location_accuracy", "motion_quality",
                    "temporal_consistency", "composition_quality", "prompt_adherence", "overall_score"]

    current_scene = None
    for r in results:
        scene = r["scene_id"]
        if scene != current_scene:
            lines.append(f"\n### Scene {scene}")
            current_scene = scene

        a = r.get("analysis", {})
        if "error" in a:
            lines.append(f"\n**{r['shot_id']}** ({r['shot_type']}) — ERROR: {a.get('error','')}")
            continue

        lines.append(f"\n#### {r['shot_id']} — {r['shot_type'].upper()} | {r['filename']}")
        lines.append(f"**Location:** {r['location']}")
        if r['characters']:
            lines.append(f"**Characters:** {', '.join(r['characters'])}")
        lines.append(f"**Prompt:** _{r['nano_prompt'][:120]}..._")
        lines.append("")

        # Scores grid
        lines.append("| Metric | Score | Issues |")
        lines.append("|--------|-------|--------|")

        # Identity scores (per-character)
        id_scores = a.get("identity_scores", {})
        if id_scores:
            for char, score in id_scores.items():
                lines.append(f"| Identity: {char} | {score:.2f} | {a.get('identity_issues','')[:80]} |")
        elif r['characters']:
            lines.append(f"| Identity | — | {a.get('identity_issues','')[:80]} |")

        lines.append(f"| Location Accuracy | {a.get('location_accuracy',0):.2f} | {a.get('location_issues','')[:80]} |")
        lines.append(f"| Motion Quality | {a.get('motion_quality',0):.2f} | {a.get('motion_issues','')[:80]} |")
        lines.append(f"| Temporal Consistency | {a.get('temporal_consistency',0):.2f} | {a.get('temporal_issues','')[:80]} |")
        lines.append(f"| Composition | {a.get('composition_quality',0):.2f} | {a.get('composition_issues','')[:80]} |")
        lines.append(f"| Prompt Adherence | {a.get('prompt_adherence',0):.2f} | {a.get('prompt_issues','')[:80]} |")
        if a.get('dialogue_sync') not in (None, "N/A — no dialogue", "N/A"):
            lines.append(f"| Dialogue Sync | {a.get('dialogue_sync',0)} | {a.get('dialogue_sync_issues','')[:80]} |")
        lines.append(f"| **OVERALL** | **{a.get('overall_score',0):.2f}** | |")
        lines.append("")

        lines.append(f"**Verdict:** `{a.get('verdict','?')}` | **Regen Priority:** `{a.get('regen_priority','?')}`")
        lines.append(f"**Primary Issue:** {a.get('primary_issue','')}")
        lines.append(f"**Fix Approach:** {a.get('fix_approach','')}")
        lines.append("")

    # HIGH priority regen list
    lines.append("\n## HIGH PRIORITY REGEN LIST\n")
    high_priority = [r for r in results if r.get("analysis",{}).get("regen_priority") == "HIGH"]
    if high_priority:
        for r in high_priority:
            a = r["analysis"]
            lines.append(f"### {r['shot_id']} ({r['filename']})")
            lines.append(f"- **Issue:** {a.get('primary_issue','')}")
            lines.append(f"- **Fix:** {a.get('fix_approach','')}")
            lines.append("")
    else:
        lines.append("_No HIGH priority regen shots found._")

    # Stats summary
    lines.append("\n## AGGREGATE STATS\n")
    valid = [r for r in results if "analysis" in r and "error" not in r["analysis"]]
    if valid:
        def avg(field):
            vals = [r["analysis"].get(field, 0) for r in valid if isinstance(r["analysis"].get(field), (int, float))]
            return sum(vals)/len(vals) if vals else 0

        lines.append(f"| Metric | Average Score |")
        lines.append(f"|--------|--------------|")
        lines.append(f"| Location Accuracy | {avg('location_accuracy'):.2f} |")
        lines.append(f"| Motion Quality | {avg('motion_quality'):.2f} |")
        lines.append(f"| Temporal Consistency | {avg('temporal_consistency'):.2f} |")
        lines.append(f"| Composition | {avg('composition_quality'):.2f} |")
        lines.append(f"| Prompt Adherence | {avg('prompt_adherence'):.2f} |")
        lines.append(f"| Overall | {avg('overall_score'):.2f} |")
        lines.append("")

        verdict_counts = {}
        for r in valid:
            v = r["analysis"].get("verdict", "?")
            verdict_counts[v] = verdict_counts.get(v, 0) + 1
        lines.append(f"**Verdict distribution:** " + ", ".join(f"{k}: {v}" for k,v in sorted(verdict_counts.items())))

    return "\n".join(lines)


# ── Entry point ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    results = run_analysis()

    # Save JSON results
    results_path = BASE / "gemini_video_analysis_results.json"
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n✓ Raw results saved → {results_path}")

    # Generate and save report
    report = generate_report(results)
    report_path = BASE / "GEMINI_VIDEO_ANALYSIS_REPORT.md"
    with open(report_path, "w") as f:
        f.write(report)
    print(f"✓ Report saved → {report_path}")

    # Print report to stdout
    print("\n" + "="*70)
    print(report)
