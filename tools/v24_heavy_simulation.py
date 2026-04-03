#!/usr/bin/env python3
"""
ATLAS V24 HEAVY SIMULATION SUITE
Pre-FAL stress test — runs ALL checks without calling FAL APIs.
Tests: enrichment parity, Film Engine routing, brain architecture,
       cast integrity, prompt quality, contract audit, dry-run gen.
"""
import json, os, sys, re, time, hashlib
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PROJECT = "victorian_shadows_ep1"
BASE = f"pipeline_outputs/{PROJECT}"

# ═══════════════════════════════════════════════════════
# LOAD ALL DATA
# ═══════════════════════════════════════════════════════
def load_json(path):
    with open(path) as f:
        return json.load(f)

sp_raw = load_json(f"{BASE}/shot_plan.json")
shots = sp_raw if isinstance(sp_raw, list) else sp_raw.get("shots", [])
cm_raw = load_json(f"{BASE}/cast_map.json")
cast_map = {k: v for k, v in cm_raw.items() if isinstance(v, dict) and not v.get("_is_alias_of")}
sb = load_json(f"{BASE}/story_bible.json") if os.path.exists(f"{BASE}/story_bible.json") else {}
sb_scenes = sb.get("scenes", []) if isinstance(sb, dict) else sb

scenes_by_id = defaultdict(list)
for s in shots:
    scenes_by_id[s.get("scene_id", "???")].append(s)

TOTAL = len(shots)
SCENES = sorted(scenes_by_id.keys())
BLOCKERS = []
WARNINGS = []
STATS = {}

def blocker(msg):
    BLOCKERS.append(msg)
    print(f"  ❌ BLOCKER: {msg}")

def warn(msg):
    WARNINGS.append(msg)
    print(f"  ⚠️  WARNING: {msg}")

def ok(msg):
    print(f"  ✅ {msg}")

# ═══════════════════════════════════════════════════════
print("=" * 70)
print("ATLAS V24 HEAVY SIMULATION — PRE-FAL STRESS TEST")
print(f"Project: {PROJECT} | {TOTAL} shots | {len(SCENES)} scenes | {len(cast_map)} cast")
print("=" * 70)

# ═══════════════════════════════════════════════════════
# SIM 1: ENRICHMENT PARITY (every shot, every field)
# ═══════════════════════════════════════════════════════
print("\n" + "─" * 70)
print("SIM 1: ENRICHMENT PARITY — Per-Shot Field Audit")
print("─" * 70)

REQUIRED_FIELDS = ["nano_prompt", "ltx_motion_prompt", "duration", "shot_type", "scene_id"]
ENRICHMENT_MARKERS = {
    "gold_standard_nano": "NO morphing",
    "gold_standard_ltx": "face stable",
    "composition": "composition:",
    "performance": ["character performs:", "character speaks:", "character reacts:"],
    "subtext": "subtext:",
    "camera_body": None,  # field check
}

field_coverage = Counter()
marker_coverage = Counter()
per_scene_issues = defaultdict(list)

for s in shots:
    sid = s.get("shot_id", "???")
    scene = s.get("scene_id", "???")
    chars = s.get("characters", [])
    has_chars = len(chars) > 0
    nano = s.get("nano_prompt", "") or ""
    ltx = s.get("ltx_motion_prompt", "") or ""

    # Required fields
    for f in REQUIRED_FIELDS:
        if s.get(f):
            field_coverage[f] += 1
        else:
            per_scene_issues[scene].append(f"{sid}: missing {f}")

    # Gold standard
    if "NO morphing" in nano:
        marker_coverage["gold_nano"] += 1
    elif has_chars:
        per_scene_issues[scene].append(f"{sid}: missing 'NO morphing' in nano")

    if "face stable" in ltx:
        marker_coverage["gold_ltx"] += 1
    elif has_chars:
        per_scene_issues[scene].append(f"{sid}: missing 'face stable' in ltx")

    # Composition
    if "composition:" in nano.lower():
        marker_coverage["composition"] += 1

    # Performance markers (character shots only)
    if has_chars:
        has_perf = any(m in ltx for m in ["character performs:", "character speaks:", "character reacts:"])
        if has_perf:
            marker_coverage["performance"] += 1
        else:
            per_scene_issues[scene].append(f"{sid}: char shot missing performance marker")

    # Subtext
    if "subtext:" in nano.lower():
        marker_coverage["subtext"] += 1

    # Camera
    if s.get("camera_body"):
        marker_coverage["camera"] += 1

    # Duration sanity
    dur = s.get("duration", 0)
    if dur and (dur < 2 or dur > 30):
        per_scene_issues[scene].append(f"{sid}: suspicious duration {dur}s")

char_shots = [s for s in shots if s.get("characters")]
STATS["enrichment"] = {
    "nano_prompt": field_coverage.get("nano_prompt", 0),
    "ltx_motion": field_coverage.get("ltx_motion_prompt", 0),
    "duration": field_coverage.get("duration", 0),
    "gold_nano": marker_coverage.get("gold_nano", 0),
    "gold_ltx": marker_coverage.get("gold_ltx", 0),
    "composition": marker_coverage.get("composition", 0),
    "performance": marker_coverage.get("performance", 0),
    "subtext": marker_coverage.get("subtext", 0),
    "camera": marker_coverage.get("camera", 0),
}

ok(f"nano_prompt: {field_coverage['nano_prompt']}/{TOTAL} ({100*field_coverage['nano_prompt']//TOTAL}%)")
ok(f"ltx_motion:  {field_coverage['ltx_motion_prompt']}/{TOTAL} ({100*field_coverage['ltx_motion_prompt']//TOTAL}%)")
ok(f"duration:    {field_coverage['duration']}/{TOTAL} ({100*field_coverage['duration']//TOTAL}%)")
ok(f"gold_nano:   {marker_coverage['gold_nano']}/{TOTAL} ({100*marker_coverage['gold_nano']//TOTAL}%)")
ok(f"gold_ltx:    {marker_coverage['gold_ltx']}/{TOTAL} ({100*marker_coverage['gold_ltx']//TOTAL}%)")

comp_pct = 100 * marker_coverage["composition"] // TOTAL
if comp_pct < 70:
    warn(f"composition: {marker_coverage['composition']}/{TOTAL} ({comp_pct}%) — below 70% threshold")
else:
    ok(f"composition: {marker_coverage['composition']}/{TOTAL} ({comp_pct}%)")

perf_pct = 100 * marker_coverage["performance"] // max(1, len(char_shots))
ok(f"performance: {marker_coverage['performance']}/{len(char_shots)} char shots ({perf_pct}%)")
ok(f"camera:      {marker_coverage['camera']}/{TOTAL} ({100*marker_coverage['camera']//TOTAL}%)")

# Scene-level issue summary
issue_scenes = {k: v for k, v in per_scene_issues.items() if v}
if issue_scenes:
    print(f"\n  Per-scene enrichment issues ({sum(len(v) for v in issue_scenes.values())} total):")
    for scene_id in sorted(issue_scenes.keys()):
        issues = issue_scenes[scene_id]
        print(f"    Scene {scene_id}: {len(issues)} issues")
        for iss in issues[:3]:
            print(f"      → {iss}")
        if len(issues) > 3:
            print(f"      → ... and {len(issues)-3} more")

# ═══════════════════════════════════════════════════════
# SIM 2: FILM ENGINE ROUTING — ALL 151 SHOTS
# ═══════════════════════════════════════════════════════
print("\n" + "─" * 70)
print("SIM 2: FILM ENGINE — Smart Routing All 151 Shots")
print("─" * 70)

try:
    from tools.film_engine import route_shot, compile_shot_for_model, translate_camera_tokens, estimate_project_cost

    routing_results = []
    routing_errors = []
    model_counter = Counter()
    mode_counter = Counter()
    reason_counter = Counter()
    confidence_scores = []

    for s in shots:
        try:
            r = route_shot(s)
            routing_results.append(r)
            model_counter[r.model] += 1
            mode_counter[r.mode] += 1
            reason_counter[r.reason] += 1
            confidence_scores.append(r.confidence)
        except Exception as e:
            routing_errors.append(f"{s.get('shot_id','???')}: {e}")

    if routing_errors:
        blocker(f"Film Engine routing failed on {len(routing_errors)} shots")
        for err in routing_errors[:5]:
            print(f"      → {err}")
    else:
        ok(f"All {TOTAL} shots routed successfully")

    ok(f"Model split: Kling={model_counter['kling']} ({100*model_counter['kling']//TOTAL}%), LTX={model_counter['ltx']} ({100*model_counter['ltx']//TOTAL}%)")
    ok(f"Mode breakdown: {dict(mode_counter)}")
    avg_conf = sum(confidence_scores) / max(1, len(confidence_scores))
    ok(f"Avg confidence: {avg_conf:.2f}")

    # Compile test — run on all shots
    compile_errors = []
    prompt_lengths = {"kling": [], "ltx": []}
    for i, s in enumerate(shots):
        try:
            result = compile_shot_for_model(s)
            model = result.get("model", "ltx")
            nano = result.get("nano_prompt_compiled", "")
            prompt_lengths[model].append(len(nano))
        except Exception as e:
            compile_errors.append(f"{s.get('shot_id','???')}: {e}")

    if compile_errors:
        warn(f"Compilation warnings on {len(compile_errors)} shots")
        for err in compile_errors[:3]:
            print(f"      → {err}")
    else:
        ok(f"All {TOTAL} shots compiled successfully")

    for model in ["kling", "ltx"]:
        if prompt_lengths[model]:
            avg_len = sum(prompt_lengths[model]) // len(prompt_lengths[model])
            max_len = max(prompt_lengths[model])
            over_limit = sum(1 for l in prompt_lengths[model] if l > 3000)
            ok(f"{model.upper()} prompts: avg={avg_len} chars, max={max_len}, over 3000={over_limit}")
            if over_limit:
                warn(f"{over_limit} {model.upper()} prompts exceed 3000 chars — may get truncated")

    # Camera token translation test
    camera_brands_found = 0
    for s in shots:
        nano = s.get("nano_prompt", "") or ""
        if re.search(r'(?i)(ARRI|Alexa|RED\s+DSMC|Sony Venice|Panavision|Cooke S7|Zeiss)', nano):
            camera_brands_found += 1

    if camera_brands_found:
        warn(f"{camera_brands_found} shots still have camera brand names in nano_prompt (Film Engine will translate at compile time)")
    else:
        ok("No camera brand names in prompts (clean)")

    # Cost estimate
    est = estimate_project_cost(shots)
    STATS["film_engine"] = {
        "kling": model_counter["kling"],
        "ltx": model_counter["ltx"],
        "cost": est["estimated_total_cost"],
        "savings": est["smart_routing_savings"],
        "avg_confidence": round(avg_conf, 3),
    }
    ok(f"Cost estimate: ${est['estimated_total_cost']:.2f} (saves ${est['smart_routing_savings']:.2f} vs all-Kling)")

except ImportError as e:
    blocker(f"Film Engine import failed: {e}")

# ═══════════════════════════════════════════════════════
# SIM 3: BRAIN ARCHITECTURE STRESS TEST
# ═══════════════════════════════════════════════════════
print("\n" + "─" * 70)
print("SIM 3: V24 BRAIN ARCHITECTURE — Full Integration Stress Test")
print("─" * 70)

# 3A: ProjectTruth (Hippocampus)
try:
    from tools.project_truth import ProjectTruth
    pt = ProjectTruth(shots, cast_map, sb_scenes)

    # Test character memory
    chars = pt.get_all_characters()
    ok(f"ProjectTruth: {len(chars)} characters tracked")
    for char_name in chars:
        appearances = pt.get_character_appearances(char_name)
        ok(f"  {char_name}: {len(appearances)} appearances")

    # Test scene memory
    for scene_id in SCENES[:3]:
        scene_data = pt.get_scene_context(scene_id)
        if scene_data:
            ok(f"  Scene {scene_id} context: {len(str(scene_data))} bytes")
        else:
            warn(f"  Scene {scene_id}: no context in ProjectTruth")

    # Test continuity queries
    for scene_id in SCENES:
        scene_shots = scenes_by_id[scene_id]
        for s in scene_shots:
            chars_in_shot = s.get("characters", [])
            for c in chars_in_shot:
                hist = pt.get_character_history(c, up_to_scene=scene_id)
                # Just verify it doesn't crash
    ok(f"ProjectTruth: all continuity queries passed ({TOTAL} shots × avg chars)")

    STATS["project_truth"] = {"characters": len(chars), "scenes": len(SCENES)}

except Exception as e:
    blocker(f"ProjectTruth stress test failed: {e}")

# 3B: Basal Ganglia (competitive scoring)
try:
    from tools.basal_ganglia_engine import BasalGangliaEngine
    bg = BasalGangliaEngine()

    scores = []
    bg_errors = []
    for s in shots:
        try:
            score = bg.score_shot(s)
            scores.append(score)
        except Exception as e:
            bg_errors.append(f"{s.get('shot_id','???')}: {e}")

    if bg_errors:
        warn(f"BasalGanglia scoring failed on {len(bg_errors)} shots")
        for err in bg_errors[:3]:
            print(f"      → {err}")
    else:
        ok(f"BasalGanglia: scored all {TOTAL} shots")

    if scores:
        # Extract total scores
        total_scores = [sc.get("total", 0) if isinstance(sc, dict) else sc for sc in scores]
        avg_score = sum(total_scores) / len(total_scores)
        max_score = max(total_scores)
        min_score = min(total_scores)
        ok(f"  Score range: {min_score:.2f} – {max_score:.2f}, avg={avg_score:.2f}")

    STATS["basal_ganglia"] = {"scored": len(scores), "errors": len(bg_errors)}

except Exception as e:
    blocker(f"BasalGanglia stress test failed: {e}")

# 3C: VisionAnalyst (Visual Cortex) — dry run
try:
    from tools.vision_analyst import VisionAnalyst
    va = VisionAnalyst()

    # Test scene health scoring (without actual images)
    health_scores = []
    va_errors = []
    for scene_id in SCENES:
        try:
            scene_shots = scenes_by_id[scene_id]
            health = va.evaluate_scene_health(scene_shots, dry_run=True)
            health_scores.append(health)
        except Exception as e:
            va_errors.append(f"Scene {scene_id}: {e}")

    if va_errors:
        warn(f"VisionAnalyst dry-run issues on {len(va_errors)} scenes")
        for err in va_errors[:3]:
            print(f"      → {err}")
    else:
        ok(f"VisionAnalyst: evaluated all {len(SCENES)} scenes (dry run)")

    STATS["vision_analyst"] = {"scenes_evaluated": len(health_scores), "errors": len(va_errors)}

except Exception as e:
    warn(f"VisionAnalyst stress test: {e} (non-blocking)")

# 3D: MetaDirector (Prefrontal Cortex)
try:
    from tools.meta_director import MetaDirector
    md = MetaDirector()

    # Test render planning
    plan = md.plan_render_order(shots, cast_map, scenes_by_id)
    if plan:
        ok(f"MetaDirector: render plan generated ({len(plan)} stages)")
        for stage in plan[:3]:
            if isinstance(stage, dict):
                ok(f"  Stage: {stage.get('name', stage.get('scene_id','?'))} — {stage.get('reason','')}")
    else:
        warn("MetaDirector: no render plan returned")

    STATS["meta_director"] = {"plan_stages": len(plan) if plan else 0}

except Exception as e:
    warn(f"MetaDirector stress test: {e} (non-blocking)")

# 3E: LITE Synthesizer (Motor Cortex)
try:
    from tools.atlas_lite_synthesizer import synthesize_shot, synthesize_deterministic

    lite_errors = []
    lite_results = []
    for s in shots[:20]:  # Test first 20 for speed
        try:
            result = synthesize_shot(s, cast_map=cast_map, enable_film_engine=True)
            lite_results.append(result)
        except Exception as e:
            lite_errors.append(f"{s.get('shot_id','???')}: {e}")

    if lite_errors:
        warn(f"LITE Synthesizer errors on {len(lite_errors)}/20 test shots")
        for err in lite_errors[:3]:
            print(f"      → {err}")
    else:
        ok(f"LITE Synthesizer: all 20 test shots compiled (sample of {TOTAL})")

    # Verify Film Engine metadata is attached
    fe_attached = sum(1 for r in lite_results if isinstance(r, dict) and r.get("_film_engine"))
    ok(f"  Film Engine metadata attached: {fe_attached}/20")

    STATS["lite_synthesizer"] = {"tested": 20, "errors": len(lite_errors), "fe_attached": fe_attached}

except Exception as e:
    warn(f"LITE Synthesizer stress test: {e} (non-blocking)")

# ═══════════════════════════════════════════════════════
# SIM 4: CAST / CHARACTER INTEGRITY
# ═══════════════════════════════════════════════════════
print("\n" + "─" * 70)
print("SIM 4: CAST & CHARACTER INTEGRITY")
print("─" * 70)

# 4A: Every character in shots must be in cast_map
chars_in_shots = set()
orphan_chars = set()
for s in shots:
    for c in (s.get("characters") or []):
        chars_in_shots.add(c)
        if c not in cast_map:
            orphan_chars.add(c)

if orphan_chars:
    blocker(f"Characters in shots but NOT in cast_map: {orphan_chars}")
else:
    ok(f"All {len(chars_in_shots)} characters in shots have cast_map entries")

# 4B: Cast map headshot URLs
for name, data in cast_map.items():
    hs = data.get("headshot_url", "")
    if not hs:
        warn(f"Cast '{name}': no headshot_url")
    elif "/sessions/" in hs:
        blocker(f"Cast '{name}': stale session path in headshot_url: {hs[:80]}")
    elif not (hs.startswith("/") or hs.startswith("http")):
        warn(f"Cast '{name}': unusual headshot_url format: {hs[:80]}")

# 4C: Character name consistency
name_variants = defaultdict(set)
for s in shots:
    for c in (s.get("characters") or []):
        # Check for short name variants
        parts = c.split()
        if len(parts) == 1 and c.upper() == c:
            # Might be a short name
            for full_name in cast_map.keys():
                if c in full_name and c != full_name:
                    name_variants[c].add(full_name)

if name_variants:
    for short, fulls in name_variants.items():
        warn(f"Possible short name '{short}' may need normalization to: {fulls}")
else:
    ok("No short name variants detected — all canonical")

# 4D: Duplicate character detection in cast_map  
cast_names_lower = defaultdict(list)
for name in cast_map.keys():
    cast_names_lower[name.lower().strip()].append(name)
dupes = {k: v for k, v in cast_names_lower.items() if len(v) > 1}
if dupes:
    blocker(f"Duplicate cast entries (case-insensitive): {dupes}")
else:
    ok(f"No duplicate cast entries")

STATS["cast"] = {
    "total": len(cast_map),
    "chars_in_shots": len(chars_in_shots),
    "orphans": len(orphan_chars),
}

# ═══════════════════════════════════════════════════════
# SIM 5: PROMPT QUALITY DEEP SCAN
# ═══════════════════════════════════════════════════════
print("\n" + "─" * 70)
print("SIM 5: PROMPT QUALITY — Bio Bleed / Location Bleed / Contamination")
print("─" * 70)

# 5A: Bio bleed detection (AI actor names/nationalities in prompts)
BIO_BLEED_PATTERNS = [
    r"Isabella\s+Moretti", r"Sophia\s+Chen", r"Marcus\s+Sterling",
    r"Elena\s+Vasquez", r"James\s+Okonkwo", r"Yuki\s+Tanaka",
    r"Aisha\s+Mbeki", r"Liam\s+O'Sullivan", r"Priya\s+Sharma",
    r"(?<!\w)Italian(?!\s+(?:architecture|villa|renaissance|marble|style))",
    r"(?<!\w)Nigerian(?!\s+(?:art|literature|music))",
    r"(?<!\w)Korean(?!\s+(?:cinema|war|food))",
    r"(?<!\w)Japanese(?!\s+(?:garden|maple|cherry|style|design))",
]

bio_bleed_count = 0
bio_bleed_details = []
for s in shots:
    nano = s.get("nano_prompt", "") or ""
    ltx = s.get("ltx_motion_prompt", "") or ""
    combined = nano + " " + ltx
    for pat in BIO_BLEED_PATTERNS:
        matches = re.findall(pat, combined, re.IGNORECASE)
        if matches:
            bio_bleed_count += 1
            bio_bleed_details.append(f"{s.get('shot_id','???')}: {pat} → '{matches[0]}'")
            break

if bio_bleed_count:
    warn(f"Bio bleed detected in {bio_bleed_count} shots")
    for d in bio_bleed_details[:5]:
        print(f"      → {d}")
else:
    ok("Zero bio bleed — no AI actor contamination")

# 5B: Camera brand contamination
CAMERA_BRANDS = [r"ARRI\s+Alexa", r"RED\s+DSMC", r"Sony\s+Venice", r"Panavision", r"Cooke\s+S7"]
camera_contam = 0
for s in shots:
    nano = s.get("nano_prompt", "") or ""
    for pat in CAMERA_BRANDS:
        if re.search(pat, nano):
            camera_contam += 1
            break

if camera_contam:
    warn(f"{camera_contam} shots have camera brand names (Film Engine strips at compile)")
else:
    ok("No camera brand contamination in prompts")

# 5C: Location bleed (foreign locations in wrong scenes)
scene_locations = {}
for s in shots:
    scene = s.get("scene_id", "???")
    loc = s.get("location", "")
    if loc and scene not in scene_locations:
        scene_locations[scene] = loc

location_keywords = defaultdict(set)
for scene_id, loc in scene_locations.items():
    # Extract key words from location
    words = set(re.findall(r'\b[A-Z][a-z]+\b', loc))
    location_keywords[scene_id] = words

loc_bleed_count = 0
for s in shots:
    scene = s.get("scene_id", "???")
    nano = (s.get("nano_prompt", "") or "").lower()
    for other_scene, keywords in location_keywords.items():
        if other_scene == scene:
            continue
        for kw in keywords:
            if len(kw) > 4 and kw.lower() in nano:
                # Check it's not a common word
                if kw.lower() not in {"night", "day", "room", "the", "dark", "light", "door", "window", "table", "chair", "wall", "floor"}:
                    loc_bleed_count += 1
                    break

if loc_bleed_count:
    warn(f"Potential location bleed in {loc_bleed_count} shots (needs review)")
else:
    ok("No location bleed detected")

# 5D: Prompt length analysis
prompt_lengths = []
over_2k = 0
over_3k = 0
for s in shots:
    nano = s.get("nano_prompt", "") or ""
    plen = len(nano)
    prompt_lengths.append(plen)
    if plen > 2000: over_2k += 1
    if plen > 3000: over_3k += 1

avg_len = sum(prompt_lengths) // max(1, len(prompt_lengths))
max_len = max(prompt_lengths)
ok(f"Prompt lengths: avg={avg_len}, max={max_len}")
if over_3k:
    warn(f"{over_3k} prompts over 3000 chars (CRITICAL — will be truncated)")
elif over_2k:
    warn(f"{over_2k} prompts over 2000 chars (may need trimming)")
else:
    ok("All prompts within safe length")

# 5E: Human language in no-character shots (Landscape Safety)
landscape_violations = []
HUMAN_BODY_PATTERNS = [r"breath", r"micro-expression", r"blinks?", r"chest rise", r"jaw\s+clench", r"pupils?\s+dilat"]
for s in shots:
    chars = s.get("characters", [])
    if not chars:
        ltx = (s.get("ltx_motion_prompt", "") or "").lower()
        nano = (s.get("nano_prompt", "") or "").lower()
        combined = ltx + " " + nano
        for pat in HUMAN_BODY_PATTERNS:
            if re.search(pat, combined):
                # Check it's not in a negative
                if "no " + pat not in combined and "NO " + pat not in combined:
                    landscape_violations.append(f"{s.get('shot_id','???')}: '{pat}' in no-character shot")
                    break

if landscape_violations:
    warn(f"Landscape safety: {len(landscape_violations)} no-char shots have human body language")
    for v in landscape_violations[:5]:
        print(f"      → {v}")
else:
    ok("Landscape safety: clean — no human language in no-character shots")

# 5F: Dialogue marker presence
dialogue_shots = [s for s in shots if (s.get("dialogue_text") or s.get("dialogue"))]
dlg_with_marker = 0
for s in dialogue_shots:
    ltx = (s.get("ltx_motion_prompt", "") or "")
    if "character speaks:" in ltx:
        dlg_with_marker += 1

if dialogue_shots:
    dlg_pct = 100 * dlg_with_marker // len(dialogue_shots)
    if dlg_pct < 80:
        warn(f"Dialogue shots with 'character speaks:' marker: {dlg_with_marker}/{len(dialogue_shots)} ({dlg_pct}%)")
    else:
        ok(f"Dialogue markers: {dlg_with_marker}/{len(dialogue_shots)} ({dlg_pct}%)")
else:
    ok("No dialogue shots detected")

STATS["prompt_quality"] = {
    "bio_bleed": bio_bleed_count,
    "camera_contam": camera_contam,
    "location_bleed": loc_bleed_count,
    "over_2k": over_2k,
    "over_3k": over_3k,
    "landscape_violations": len(landscape_violations),
    "dialogue_markers": f"{dlg_with_marker}/{len(dialogue_shots)}",
}

# ═══════════════════════════════════════════════════════
# SIM 6: STRUCTURAL INTEGRITY
# ═══════════════════════════════════════════════════════
print("\n" + "─" * 70)
print("SIM 6: STRUCTURAL INTEGRITY — Shots, Scenes, Bible, Assets")
print("─" * 70)

# 6A: Story bible scene count vs shot plan scenes
bible_scene_ids = set()
if sb_scenes:
    for sc in sb_scenes:
        if isinstance(sc, dict):
            bible_scene_ids.add(sc.get("scene_id", ""))

shot_scene_ids = set(SCENES)
missing_in_bible = shot_scene_ids - bible_scene_ids
missing_in_shots = bible_scene_ids - shot_scene_ids

if missing_in_bible:
    warn(f"Scenes in shots but NOT in story bible: {missing_in_bible}")
if missing_in_shots:
    warn(f"Scenes in bible but NOT in shots: {missing_in_shots}")
if not missing_in_bible and not missing_in_shots:
    ok(f"Scene alignment: {len(shot_scene_ids)} scenes match between shots and bible")

# 6B: Shot ID uniqueness
shot_ids = [s.get("shot_id", "") for s in shots]
dupes = [sid for sid, count in Counter(shot_ids).items() if count > 1]
if dupes:
    blocker(f"Duplicate shot IDs found: {dupes}")
else:
    ok(f"All {TOTAL} shot IDs unique")

# 6C: Scene-to-shot mapping sanity
for scene_id in SCENES:
    scene_shots = scenes_by_id[scene_id]
    if len(scene_shots) < 1:
        warn(f"Scene {scene_id}: 0 shots (empty scene)")
    elif len(scene_shots) > 30:
        warn(f"Scene {scene_id}: {len(scene_shots)} shots (unusually high)")

# 6D: First frames / video asset check
ff_dir = f"{BASE}/first_frames"
vid_dir = f"{BASE}/videos"
existing_ff = set()
existing_vid = set()
if os.path.isdir(ff_dir):
    for f in os.listdir(ff_dir):
        if f.endswith((".jpg", ".png")):
            sid = f.rsplit(".", 1)[0]
            existing_ff.add(sid)
if os.path.isdir(vid_dir):
    for f in os.listdir(vid_dir):
        if f.endswith(".mp4"):
            sid = f.rsplit(".", 1)[0]
            existing_vid.add(sid)

ok(f"Existing first frames: {len(existing_ff)}")
ok(f"Existing videos: {len(existing_vid)}")

# Check for orphan assets (files that don't match current shot IDs)
shot_id_set = set(shot_ids)
orphan_ff = existing_ff - shot_id_set
orphan_vid = existing_vid - shot_id_set
if orphan_ff:
    warn(f"Orphan first frames (no matching shot): {len(orphan_ff)}")
if orphan_vid:
    warn(f"Orphan videos (no matching shot): {len(orphan_vid)}")

# 6E: Duration totals
total_duration = sum(s.get("duration", 0) for s in shots)
minutes = total_duration / 60
ok(f"Total runtime: {total_duration}s ({minutes:.1f} minutes)")

STATS["structure"] = {
    "shots": TOTAL,
    "scenes": len(SCENES),
    "bible_scenes": len(bible_scene_ids),
    "unique_ids": TOTAL - len(dupes),
    "first_frames": len(existing_ff),
    "videos": len(existing_vid),
    "runtime_seconds": total_duration,
}

# ═══════════════════════════════════════════════════════
# SIM 7: GENERATION DRY-RUN SIMULATION
# ═══════════════════════════════════════════════════════
print("\n" + "─" * 70)
print("SIM 7: GENERATION DRY-RUN — Simulated Pipeline Execution")
print("─" * 70)

# Simulate the exact generation order
gen_order = []
for scene_id in SCENES:
    scene_shots = scenes_by_id[scene_id]
    for s in scene_shots:
        sid = s.get("shot_id", "???")
        nano = s.get("nano_prompt", "")
        if not nano:
            blocker(f"DRY-RUN: {sid} would fail — no nano_prompt")
            continue
        
        # Check refs
        chars = s.get("characters", [])
        needs_ref = len(chars) > 0
        has_ref = bool(s.get("character_reference_url"))
        
        # Check model routing
        try:
            routing = route_shot(s)
            model = routing.model
        except:
            model = "ltx"
        
        gen_order.append({
            "shot_id": sid,
            "scene": scene_id,
            "model": model,
            "has_chars": needs_ref,
            "has_ref": has_ref,
            "has_first_frame": sid in existing_ff,
            "has_video": sid in existing_vid,
            "duration": s.get("duration", 5),
        })

# Simulate FAL calls
total_fal_calls = 0
frame_gen_needed = 0
video_gen_needed = 0
scenes_needing_frames = set()
for g in gen_order:
    if not g["has_first_frame"]:
        frame_gen_needed += 1
        total_fal_calls += 1  # nano call
        scenes_needing_frames.add(g["scene"])
    if not g["has_video"]:
        video_gen_needed += 1
        total_fal_calls += 1  # LTX/Kling call

ok(f"First frames to generate: {frame_gen_needed}/{TOTAL}")
ok(f"Videos to generate: {video_gen_needed}/{TOTAL}")
ok(f"Total FAL API calls needed: {total_fal_calls}")
ok(f"Scenes needing frame gen: {len(scenes_needing_frames)} ({sorted(scenes_needing_frames)})")

# Time estimate
# nano: ~8s, LTX: ~15s, Kling: ~45s
kling_frames = sum(1 for g in gen_order if g["model"] == "kling" and not g["has_first_frame"])
ltx_frames = frame_gen_needed - kling_frames
kling_videos = sum(1 for g in gen_order if g["model"] == "kling" and not g["has_video"])
ltx_videos = video_gen_needed - kling_videos

est_time_s = (frame_gen_needed * 8) + (ltx_videos * 15) + (kling_videos * 45)
est_time_min = est_time_s / 60
ok(f"Estimated render time: ~{est_time_min:.0f} minutes ({est_time_s}s)")
ok(f"  Frame gen: {frame_gen_needed} × ~8s = {frame_gen_needed*8}s")
ok(f"  LTX video: {ltx_videos} × ~15s = {ltx_videos*15}s")
ok(f"  Kling video: {kling_videos} × ~45s = {kling_videos*45}s")

# ═══════════════════════════════════════════════════════
# FINAL REPORT
# ═══════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("ATLAS V24 SIMULATION REPORT — FINAL VERDICT")
print("=" * 70)

print(f"\n  Project:    {PROJECT}")
print(f"  Shots:      {TOTAL}")
print(f"  Scenes:     {len(SCENES)}")
print(f"  Cast:       {len(cast_map)}")
print(f"  Runtime:    {total_duration}s ({minutes:.1f} min)")
print(f"  Cost est:   ${STATS.get('film_engine',{}).get('cost', 'N/A')}")
print(f"  Render time: ~{est_time_min:.0f} min")

print(f"\n  BLOCKERS:   {len(BLOCKERS)}")
for b in BLOCKERS:
    print(f"    ❌ {b}")

print(f"\n  WARNINGS:   {len(WARNINGS)}")
for w in WARNINGS:
    print(f"    ⚠️  {w}")

if BLOCKERS:
    print(f"\n  🚫 VERDICT: NOT READY — {len(BLOCKERS)} blockers must be resolved")
    print(f"  Run these steps first:")
    print(f"    1. POST /api/shot-plan/fix-v16 {{\"project\":\"{PROJECT}\"}}")
    print(f"    2. python3 tools/post_fixv16_sanitizer.py {PROJECT}")
    print(f"    3. POST /api/v21/audit/{PROJECT}")
    print(f"    4. Re-run this simulation")
elif len(WARNINGS) > 10:
    print(f"\n  ⚠️  VERDICT: READY WITH CAUTION — {len(WARNINGS)} warnings (review recommended)")
    print(f"  You CAN load FAL and go. Warnings are non-blocking.")
else:
    print(f"\n  ✅ VERDICT: READY TO RENDER — Load FAL credits and go!")

print(f"\n" + "=" * 70)

# Save report
report = {
    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    "project": PROJECT,
    "version": "V24.0",
    "shots": TOTAL,
    "scenes": len(SCENES),
    "cast": len(cast_map),
    "blockers": BLOCKERS,
    "warnings": WARNINGS,
    "stats": STATS,
    "verdict": "BLOCKED" if BLOCKERS else ("CAUTION" if len(WARNINGS) > 10 else "READY"),
}
report_path = f"{BASE}/v24_simulation_report.json"
with open(report_path, "w") as f:
    json.dump(report, f, indent=2)
print(f"Report saved: {report_path}")
