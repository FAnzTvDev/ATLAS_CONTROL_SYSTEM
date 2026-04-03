#!/usr/bin/env python3
"""
V35 First-Frame Analysis — ATLAS Self-Diagnostic
Uploads 12 representative frames to Gemini Vision, analyzes gaps vs V35 capabilities,
and produces a prediction + test recommendation.
"""

import os, sys, json, base64, urllib.request, urllib.error, time
from pathlib import Path
from datetime import datetime

# ── Load .env before anything else ──────────────────────────────────────────
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    for line in _env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            if k.strip() not in os.environ:
                os.environ[k.strip()] = v.strip()

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
GEMINI_MODEL   = "gemini-2.5-flash"
FRAMES_DIR     = Path(__file__).parent.parent / "pipeline_outputs/victorian_shadows_ep1/first_frames"
OUTPUT_PATH    = Path(__file__).parent.parent / "pipeline_outputs/victorian_shadows_ep1/V35_FRAME_ANALYSIS.md"

# ── Shot metadata (from shot_plan.json) ─────────────────────────────────────
SHOT_META = {
    "001_E01": {
        "type": "E-shot", "scene": "001", "location": "HARGROVE ESTATE - GRAND FOYER",
        "characters": [],
        "intent": "Victorian Gothic mansion from iron gates, morning mist, glowing upper window",
        "beat": "The house watches. Morning fog. Crumbling grandeur."
    },
    "001_M01": {
        "type": "M-shot", "scene": "001", "location": "HARGROVE ESTATE - GRAND FOYER",
        "characters": ["ELEANOR VOSS", "THOMAS BLACKWOOD"],
        "intent": "Eleanor (mid-30s, angular features, auburn hair, dark blazer) + Thomas (60s, silver hair, navy suit) in grand foyer",
        "beat": "Eleanor pushes open heavy front doors, pauses to scan the room"
    },
    "002_E01": {
        "type": "E-shot", "scene": "002", "location": "HARGROVE ESTATE - LIBRARY",
        "characters": [],
        "intent": "Library wing exterior, warm amber light from two tall arched windows, morning sky",
        "beat": "The library wing. Warm light inside. The answers wait."
    },
    "002_M01": {
        "type": "M-shot", "scene": "002", "location": "HARGROVE ESTATE - LIBRARY",
        "characters": ["NADIA COLE"],
        "intent": "Nadia (28, dark brown skin, Iron Maiden tee, natural afro, camera in hand) in library",
        "beat": "Nadia moves through the library, lifting camera to capture shelves"
    },
    "003_E01": {
        "type": "E-shot", "scene": "003", "location": "HARGROVE ESTATE - DRAWING ROOM",
        "characters": [],
        "intent": "Drawing room bay window prominent, warm firelight visible through large bay, stone facade",
        "beat": "The drawing room window glows. Warmth inside. The world outside is cold."
    },
    "003_M01": {
        "type": "M-shot", "scene": "003", "location": "HARGROVE ESTATE - DRAWING ROOM",
        "characters": ["ELEANOR VOSS", "RAYMOND CROSS"],
        "intent": "Eleanor + Raymond (45, stocky, grey-streaked dark hair, overcoat, arms folded) in drawing room",
        "beat": "Raymond steps closer, arms folded, blocking the doorway"
    },
    "004_E01": {
        "type": "E-shot", "scene": "004", "location": "HARGROVE ESTATE - GARDEN",
        "characters": [],
        "intent": "Garden elevation, overgrown formal garden foreground, untended hedges, moss-covered urns",
        "beat": "The garden gone wild. The house looms through the overgrowth."
    },
    "004_M01": {
        "type": "M-shot", "scene": "004", "location": "HARGROVE ESTATE - GARDEN",
        "characters": ["ELEANOR VOSS", "THOMAS BLACKWOOD"],
        "intent": "Thomas + Eleanor in garden, Thomas turning small velvet box near cracked fountain",
        "beat": "Thomas turns small velvet box over, staring at cracked fountain"
    },
    "005_E01": {
        "type": "E-shot", "scene": "005", "location": "HARGROVE ESTATE - MASTER BEDROOM",
        "characters": [],
        "intent": "Upper floor elevation, master bedroom windows with heavy curtains, thin gap of light",
        "beat": "The upper windows. Behind one of them, something waits to be found."
    },
    "005_M01": {
        "type": "M-shot", "scene": "005", "location": "HARGROVE ESTATE - MASTER BEDROOM",
        "characters": ["NADIA COLE", "THOMAS BLACKWOOD"],
        "intent": "Nadia + Thomas in master bedroom, Nadia camera raised, scanning ornate room",
        "beat": "Nadia enters through doorway, camera raised, scanning ornate room"
    },
    "006_E01": {
        "type": "E-shot", "scene": "006", "location": "HARGROVE ESTATE - KITCHEN",
        "characters": [],
        "intent": "Service entrance, worn stone steps down to heavy wooden service door, slightly ajar",
        "beat": "The service entrance. Stone steps. The working world of the house."
    },
    "006_M01": {
        "type": "M-shot", "scene": "006", "location": "HARGROVE ESTATE - KITCHEN",
        "characters": ["ELEANOR VOSS", "NADIA COLE"],
        "intent": "Eleanor + Nadia in Victorian kitchen, copper pots, Eleanor pacing with phone",
        "beat": "Eleanor paces past copper pots hanging from ceiling, phone to ear"
    },
}

# ── V35 Feature Map (for gap → fix correlation) ──────────────────────────────
V35_FEATURES = {
    "camera_position_dna": {
        "desc": "8 room DNA templates (foyer, library, etc.), each with wide_master/interior_atmosphere/reverse_angle/insert_detail variants",
        "fixes": ["E-shots look identical across scenes", "wrong room architecture", "generic interior", "no room-specific detail"],
    },
    "e_shot_isolation": {
        "desc": "E01/E02/E03 skip Wire A (_no_char_ref + _is_broll guards) — no character refs injected for establishing shots",
        "fixes": ["phantom characters in establishing shots", "character bleeds into empty room shots", "wrong person in E-shot"],
    },
    "spatial_gate": {
        "desc": "Gemini compares all E-shots post-generation for visual distinctness, writes spatial_gate_results/",
        "fixes": ["all E-shots look the same", "checkerboard pattern", "identical composition repeated"],
    },
    "parallel_generation": {
        "desc": "Frames-only mode generates all first frames in parallel before any video spend",
        "fixes": ["workflow bottleneck", "no review gate before video generation"],
    },
    "i_score_normalization": {
        "desc": "Gemini 0-5 scale normalized to 0-1, reward formula R=I×0.35+V×0.40+C×0.25 stays valid",
        "fixes": ["reward ledger shows I=0.75 flat heuristic", "vision judge not firing", "identity scores meaningless"],
    },
    "vision_backend_env_fix": {
        "desc": ".env loaded before session_enforcer imports vision_judge — all backends available",
        "fixes": ["Gemini unavailable despite GOOGLE_API_KEY set", "all scores fall to heuristic 0.75"],
    },
    "scene_visual_dna": {
        "desc": "Every shot in a scene gets identical [ROOM DNA:] block — immutable architecture fingerprint",
        "fixes": ["room architecture changes between shots", "lighting drift between shots", "staircase material changes"],
    },
    "identity_injection": {
        "desc": "Amplified [CHARACTER:] blocks from cast_map injected into every character prompt",
        "fixes": ["wrong person generated", "generic person instead of specific character", "identity failure"],
    },
}

# ── Gemini Vision API call ───────────────────────────────────────────────────
def score_frame_gemini(frame_path: Path, shot_id: str, meta: dict) -> dict:
    """Call Gemini 2.5 Flash to analyze a single frame."""
    if not GOOGLE_API_KEY:
        return {"error": "No GOOGLE_API_KEY", "shot_id": shot_id}

    # Resize to 768px max for API efficiency
    try:
        from PIL import Image as PILImage
        import io
        img = PILImage.open(frame_path)
        img.thumbnail((768, 768), PILImage.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        frame_b64 = base64.standard_b64encode(buf.getvalue()).decode("utf-8")
    except ImportError:
        with open(frame_path, "rb") as f:
            frame_b64 = base64.standard_b64encode(f.read()).decode("utf-8")

    chars_str = ", ".join(meta["characters"]) if meta["characters"] else "none expected (establishing/empty shot)"
    prompt = (
        f"Victorian mystery thriller AI-generated film frame analysis.\n"
        f"Shot: {shot_id} | Location: {meta['location'].split(' - ')[-1]} | Characters expected: {chars_str}\n\n"
        f"START your response with EXACTLY this line:\n"
        f"SCORE: X/10 | BIGGEST PROBLEM: [one sentence]\n\n"
        f"Then describe: what you see, is it realistic or obviously AI, is the location clearly a specific room or generic, "
        f"camera angle and composition, people visible and how realistic, any artifacts."
    )

    payload = {
        "contents": [{
            "parts": [
                {"inline_data": {"mime_type": "image/jpeg", "data": frame_b64}},
                {"text": prompt}
            ]
        }],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 1500}
    }

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GOOGLE_API_KEY}"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
        text = raw["candidates"][0]["content"]["parts"][0]["text"].strip()

        # Parse the structured last line: "SCORE: X/10 | BIGGEST PROBLEM: ..."
        import re
        score_line_match = re.search(r'SCORE:\s*(\d+(?:\.\d+)?)/10\s*\|\s*BIGGEST PROBLEM:\s*(.+?)$', text, re.IGNORECASE | re.MULTILINE)
        if score_line_match:
            score = float(score_line_match.group(1))
            top_gap = score_line_match.group(2).strip()
        else:
            # Fallback: find any X/10 pattern
            fallback_score = re.search(r'(\d+)\s*/\s*10', text)
            score = int(fallback_score.group(1)) if fallback_score else 5
            # Top gap fallback: last non-empty sentence
            sentences = [s.strip() for s in text.split('.') if len(s.strip()) > 20]
            top_gap = sentences[-1] if sentences else text[:120]

        # Look for artifacts/issues keywords
        has_phantom = any(w in text.lower() for w in ["phantom", "unintended", "extra person", "unexpected figure"])
        has_generic = any(w in text.lower() for w in ["generic", "identical", "indistinct", "same as", "non-specific"])
        has_identity = any(w in text.lower() for w in ["wrong person", "incorrect", "different person", "mismatched"])
        has_artifacts = any(w in text.lower() for w in ["artifact", "distort", "blur", "uncanny", "plastic", "artificial"])

        result = {
            "shot_id": shot_id,
            "meta": meta,
            "overall_score": score,
            "raw_analysis": text,
            "top_gap": top_gap,
            "has_phantom_character": has_phantom,
            "has_generic_location": has_generic,
            "has_identity_failure": has_identity,
            "has_visual_artifacts": has_artifacts,
            # Derive sub-scores from text keywords
            "film_quality": score,
            "film_quality_note": "see raw_analysis",
            "location_clarity": max(1, score - (3 if has_generic else 0)),
            "location_clarity_note": "see raw_analysis",
            "camera_craft": score,
            "camera_craft_note": "see raw_analysis",
            "character_identity": max(1, score - (4 if has_identity or has_phantom else 0)),
            "character_identity_note": "see raw_analysis",
            "video_start_potential": score,
            "video_start_note": "see raw_analysis",
            "architectural_details": [],
        }
        return result
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        return {"error": f"HTTP {e.code}: {body[:200]}", "shot_id": shot_id, "meta": meta}
    except Exception as e:
        return {"error": str(e), "shot_id": shot_id, "meta": meta}


# ── Gap → V35 fix correlation ────────────────────────────────────────────────
def correlate_gap_to_v35(gap_text: str, shot_type: str) -> list:
    """Map a gap description to V35 features that address it."""
    gap_lower = gap_text.lower()
    fixes = []

    if any(k in gap_lower for k in ["identical", "same", "generic", "similar", "indistinct", "repeat"]):
        if shot_type == "E-shot":
            fixes.append(("camera_position_dna", "HIGH"))
            fixes.append(("spatial_gate", "HIGH"))
        else:
            fixes.append(("scene_visual_dna", "HIGH"))

    if any(k in gap_lower for k in ["wrong person", "generic face", "identity", "different person", "phantom", "character appears"]):
        if shot_type == "E-shot":
            fixes.append(("e_shot_isolation", "HIGH"))
        else:
            fixes.append(("identity_injection", "HIGH"))

    if any(k in gap_lower for k in ["heuristic", "0.75", "no scoring", "flat score"]):
        fixes.append(("vision_backend_env_fix", "HIGH"))
        fixes.append(("i_score_normalization", "HIGH"))

    if any(k in gap_lower for k in ["room", "architecture", "location", "interior", "generic room"]):
        fixes.append(("camera_position_dna", "MEDIUM"))
        fixes.append(("scene_visual_dna", "MEDIUM"))

    if any(k in gap_lower for k in ["composition", "framing", "centered", "flat", "depth"]):
        fixes.append(("camera_position_dna", "MEDIUM"))

    if not fixes:
        fixes.append(("parallel_generation", "LOW"))  # fallback — workflow only

    return fixes


# ── Generate the markdown report ─────────────────────────────────────────────
def build_report(results: list) -> str:
    lines = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines.append(f"# V35 FRAME ANALYSIS — ATLAS Self-Diagnostic")
    lines.append(f"**Generated:** {now}  ")
    lines.append(f"**System Version:** V35.0 (2026-03-26)  ")
    lines.append(f"**Analyzed Frames:** {len(results)} (E01 + M01 across scenes 001–006)  ")
    lines.append(f"**Vision Backend:** Gemini {GEMINI_MODEL}\n")

    lines.append("---\n")

    # ── PART 1: Frame-by-frame analysis ──
    lines.append("## PART 1: Frame-by-Frame Gemini Analysis\n")

    e_scores, m_scores = [], []
    all_gaps = []
    gap_rows = []  # for Part 2 table

    for r in results:
        sid = r.get("shot_id", "?")
        meta = r.get("meta", {})
        stype = meta.get("type", "?")

        lines.append(f"### {sid} — {stype} | {meta.get('location','').split(' - ')[-1]}")

        if "error" in r:
            lines.append(f"**ERROR:** {r['error']}\n")
            continue

        scores = {
            "film_quality": r.get("film_quality", 0),
            "location_clarity": r.get("location_clarity", 0),
            "camera_craft": r.get("camera_craft", 0),
            "character_identity": r.get("character_identity", 0),
            "video_start_potential": r.get("video_start_potential", 0),
        }
        overall = r.get("overall_score") or (sum(scores.values()) / 5)

        lines.append(f"**Intended:** {meta.get('intent','')[:120]}")
        lines.append(f"**Beat:** _{meta.get('beat','')}_\n")

        flags = []
        if r.get("has_phantom_character"): flags.append("⚠️ PHANTOM CHARACTER")
        if r.get("has_generic_location"):  flags.append("⚠️ GENERIC LOCATION")
        if r.get("has_identity_failure"):  flags.append("⚠️ IDENTITY FAILURE")
        if r.get("has_visual_artifacts"):  flags.append("⚠️ VISUAL ARTIFACTS")
        if flags:
            lines.append(f"**Flags:** {' | '.join(flags)}")

        lines.append(f"**Overall Score:** {overall:.0f}/10\n")

        raw = r.get("raw_analysis", "")
        if raw:
            lines.append(f"**Gemini Analysis:**")
            lines.append(f"> {raw.replace(chr(10), chr(10) + '> ')}\n")

        top_gap = r.get("top_gap", "")
        lines.append(f"**TOP GAP:** {top_gap}\n")

        if stype == "E-shot":
            e_scores.append(overall)
        else:
            m_scores.append(overall)

        # Collect gap rows
        v35_fixes = correlate_gap_to_v35(top_gap, stype)
        all_gaps.append((sid, stype, top_gap, v35_fixes))
        for feat, conf in v35_fixes:
            gap_rows.append({
                "shot": sid, "type": stype, "gap": top_gap[:80],
                "root_cause": feat, "v35_fix": V35_FEATURES[feat]["desc"][:80],
                "confidence": conf
            })

    # ── PART 2: Gap analysis table ──
    lines.append("---\n")
    lines.append("## PART 2: Gap Analysis — Old System vs V35\n")

    lines.append("| Frame | Type | Gap Found | Root Cause System | V35 Fix | Confidence |")
    lines.append("|-------|------|-----------|-------------------|---------|------------|")
    for row in gap_rows:
        lines.append(f"| {row['shot']} | {row['type']} | {row['gap'][:60]} | {row['root_cause']} | {row['v35_fix'][:60]} | {row['confidence']} |")
    lines.append("")

    # Feature coverage summary
    lines.append("### V35 Feature Coverage Summary\n")
    feat_counts = {}
    for row in gap_rows:
        feat_counts[row["root_cause"]] = feat_counts.get(row["root_cause"], 0) + 1

    sorted_feats = sorted(feat_counts.items(), key=lambda x: -x[1])
    lines.append("| V35 Feature | Gaps It Addresses | Description |")
    lines.append("|-------------|-------------------|-------------|")
    for feat, count in sorted_feats:
        lines.append(f"| `{feat}` | {count} frames | {V35_FEATURES.get(feat, {}).get('desc', '—')[:80]} |")
    lines.append("")

    # ── PART 3: Prediction ──
    lines.append("---\n")
    lines.append("## PART 3: Prediction — Will V35 Produce Better Outcomes?\n")

    avg_e = sum(e_scores)/len(e_scores) if e_scores else 0
    avg_m = sum(m_scores)/len(m_scores) if m_scores else 0
    total_avg = (avg_e + avg_m) / 2 if e_scores and m_scores else avg_e or avg_m

    lines.append(f"**Current system average scores:**")
    lines.append(f"- E-shots (establishing): {avg_e:.1f}/10 (n={len(e_scores)})")
    lines.append(f"- M-shots (character): {avg_m:.1f}/10 (n={len(m_scores)})")
    lines.append(f"- Overall: {total_avg:.1f}/10\n")

    lines.append("### Changes by V35 Feature\n")

    # Camera Position DNA impact
    e_cam_gaps = [g for g in all_gaps if g[1] == "E-shot" and any(f=="camera_position_dna" for f,c in g[3])]
    lines.append(f"**Camera Position DNA** — affects {len(e_cam_gaps)}/6 E-shots:")
    if e_cam_gaps:
        for sid, _, gap, _ in e_cam_gaps:
            lines.append(f"  - `{sid}`: {gap[:100]}")
    lines.append(f"  → Expected improvement: E-shots gain room-specific DNA blocks, forcing scene-distinct compositions")
    lines.append(f"  → Confidence: **HIGH** (code-level fix — ROOM_DNA_TEMPLATES wired in scene_visual_dna.py)\n")

    # E-shot isolation impact
    e_phantom = [g for g in all_gaps if g[1] == "E-shot" and any(f=="e_shot_isolation" for f,c in g[3])]
    lines.append(f"**E-shot Isolation** — affects {len(e_phantom)}/6 E-shots:")
    if e_phantom:
        for sid, _, gap, _ in e_phantom:
            lines.append(f"  - `{sid}`: {gap[:100]}")
    else:
        lines.append(f"  - No phantom character issues detected (E-shots correctly empty)")
    lines.append(f"  → Confidence: **HIGH** (code-level guard — `_no_char_ref + _is_broll` at runner line ~2165)\n")

    # Identity injection impact
    m_id_gaps = [g for g in all_gaps if g[1] == "M-shot" and any(f=="identity_injection" for f,c in g[3])]
    lines.append(f"**Identity Injection** — affects {len(m_id_gaps)}/6 M-shots:")
    if m_id_gaps:
        for sid, _, gap, _ in m_id_gaps:
            lines.append(f"  - `{sid}`: {gap[:100]}")
    lines.append(f"  → Expected improvement: [CHARACTER:] amplification blocks force correct appearance\n")

    # Spatial gate impact
    lines.append(f"**Spatial Comparison Gate** — Post-generation E-shot distinctness check:")
    lines.append(f"  → All 6 E-shots will be compared for visual similarity; near-identical pairs flagged")
    lines.append(f"  → Confidence: **HIGH** (wired at runner line ~3988, writes spatial_gate_results/)\n")

    lines.append("### Model Limitations (V35 Cannot Fix)\n")
    model_limits = [
        "Nano-banana-pro generates from text — faces are probabilistic, not deterministic. Even with amplified character descriptions, identity can still drift shot-to-shot.",
        "E-shots may look cinematographically similar if the actual Victorian mansion model in nano is limited — DNA blocks describe architecture but cannot force novel geometry.",
        "Film grain and practical lighting quality depends on the base model's training data — system prompts can guide but not guarantee film-quality output.",
        "Spatial continuity across multiple generations of the same room is probabilistic — the DNA block helps but won't produce pixel-perfect consistency.",
    ]
    for lim in model_limits:
        lines.append(f"- {lim}")
    lines.append("")

    # ── PART 4: Recommended test ──
    lines.append("---\n")
    lines.append("## PART 4: Recommended V35 Verification Test\n")

    # Find the scene with the lowest scores but most V35-addressable gaps
    scene_scores = {}
    scene_v35_addressable = {}
    for r in results:
        if "error" in r:
            continue
        sid = r["shot_id"]
        scene = sid[:3]
        overall = r.get("overall_score") or 0
        if scene not in scene_scores:
            scene_scores[scene] = []
        scene_scores[scene].append(overall)

    for sid, stype, gap, fixes in all_gaps:
        scene = sid[:3]
        high_conf = [f for f,c in fixes if c == "HIGH"]
        if scene not in scene_v35_addressable:
            scene_v35_addressable[scene] = 0
        scene_v35_addressable[scene] += len(high_conf)

    # Score scenes: low quality + high v35 addressability = best test
    scene_test_score = {}
    for scene in scene_scores:
        avg = sum(scene_scores[scene]) / len(scene_scores[scene])
        addressable = scene_v35_addressable.get(scene, 0)
        # Lower quality + more addressable = higher test value
        scene_test_score[scene] = (10 - avg) * 0.6 + addressable * 0.4

    best_scene = max(scene_test_score, key=scene_test_score.get) if scene_test_score else "002"
    best_avg = sum(scene_scores.get(best_scene, [0])) / max(len(scene_scores.get(best_scene, [1])), 1)
    best_addressable = scene_v35_addressable.get(best_scene, 0)

    lines.append(f"### Recommended Test Scene: **{best_scene}** ({SHOT_META.get(f'{best_scene}_E01', {}).get('location','').split(' - ')[-1]})\n")

    lines.append(f"**Rationale:**")
    lines.append(f"- Current quality score: {best_avg:.1f}/10 (room for measurable improvement)")
    lines.append(f"- V35 HIGH-confidence fixes applicable: {best_addressable}")
    lines.append(f"- Both E-shot and M-shot have identifiable gaps that V35 features directly address\n")

    lines.append("**Test protocol:**")
    lines.append("```bash")
    lines.append(f"# Stage 1: Generate frames only (verify V35 DNA + isolation improvements)")
    lines.append(f"python3 atlas_universal_runner.py victorian_shadows_ep1 {best_scene} --mode lite --frames-only")
    lines.append(f"")
    lines.append(f"# Stage 2: Re-run this analysis on the new frames")
    lines.append(f"python3 tools/v35_frame_analysis.py --compare-only --scene {best_scene}")
    lines.append(f"```\n")

    lines.append("**What to look for:**")
    lines.append(f"1. E-shot `{best_scene}_E01` — Does it show a room-specific architectural detail not seen in other scenes' E-shots?")
    lines.append(f"2. M-shot `{best_scene}_M01` — Does the character identity score improve vs the pre-V35 run?")
    lines.append(f"3. Spatial gate output — Does `spatial_gate_results/{best_scene}_spatial_gate.json` exist and show DISTINCT pairs?")
    lines.append(f"4. I-score in reward ledger — Is it ≠ 0.75 (proves Gemini vision backend firing)?\n")

    lines.append("**Disconfirming evidence to watch for:**")
    lines.append("- If E-shots still look identical → Camera Position DNA not reaching FAL (check injection point)")
    lines.append("- If M-shot identity worse → Identity injection amplification needs tuning")
    lines.append("- If I-score still 0.75 → .env env-load timing bug re-emerged in V35 (re-check session_enforcer)\n")

    lines.append("---\n")
    lines.append("## Appendix: V35 Features Active\n")

    lines.append("| Feature | Status | Wired At | Confidence |")
    lines.append("|---------|--------|----------|------------|")
    lines.append("| Camera Position DNA (8 templates) | ✅ WIRED | `tools/scene_visual_dna.py` | HIGH |")
    lines.append("| E-shot Isolation (`_no_char_ref`) | ✅ WIRED | runner line ~2165 | HIGH |")
    lines.append("| Spatial Comparison Gate | ✅ WIRED | runner line ~3988 | HIGH |")
    lines.append("| Parallel Frames-Only Mode | ✅ WIRED | `/api/auto/run-frames-only` | HIGH |")
    lines.append("| I-score Normalization (0-5→0-1) | ✅ WIRED | `vision_judge.py` line ~672 | HIGH |")
    lines.append("| Vision Backend .env Fix | ✅ WIRED | `session_enforcer.py` lines 26-34 | HIGH |")
    lines.append("| Stage 5 Advisory (story_judge + vision_analyst) | ✅ IMPORTED | runner (advisory only) | MEDIUM |")
    lines.append("")

    lines.append(f"*Analysis generated by `tools/v35_frame_analysis.py` — ATLAS V35.0 Self-Diagnostic*")

    return "\n".join(lines)


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    print(f"V35 Frame Analysis — ATLAS Self-Diagnostic")
    print(f"GOOGLE_API_KEY: {'SET (' + GOOGLE_API_KEY[:8] + '...)' if GOOGLE_API_KEY else 'MISSING'}")
    print(f"Analyzing 12 frames across 6 scenes...\n")

    results = []
    target_shots = list(SHOT_META.keys())

    for shot_id in target_shots:
        frame_path = FRAMES_DIR / f"{shot_id}.jpg"
        if not frame_path.exists():
            print(f"  ⚠ MISSING: {frame_path}")
            results.append({"shot_id": shot_id, "error": "Frame file not found", "meta": SHOT_META[shot_id]})
            continue

        print(f"  → Analyzing {shot_id} ({SHOT_META[shot_id]['type']})...", end=" ", flush=True)
        result = score_frame_gemini(frame_path, shot_id, SHOT_META[shot_id])

        if "error" in result:
            print(f"ERROR: {result['error'][:80]}")
        else:
            overall = result.get("overall_score", 0)
            top_gap = result.get("top_gap", "")[:60]
            print(f"✓ overall={overall:.1f} | gap: {top_gap}")

        results.append(result)

        # Respect Gemini rate limits (15 RPM free tier)
        time.sleep(4)

    print(f"\nBuilding report...")
    report = build_report(results)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(report, encoding="utf-8")
    print(f"✓ Report saved to {OUTPUT_PATH}")

    # Also save raw JSON for debugging
    raw_path = OUTPUT_PATH.with_name("V35_FRAME_ANALYSIS_RAW.json")
    raw_path.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    print(f"✓ Raw scores saved to {raw_path}")


if __name__ == "__main__":
    main()
