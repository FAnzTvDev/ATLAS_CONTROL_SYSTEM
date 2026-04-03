"""
Higgsfield Renders — Auto Revision Judge Batch Audit
=====================================================
Scores all 10 hf_*.mp4 files against their shot specifications using
AutoRevisionJudge (Gemini 2.5 Flash Files API, 8-dimension analysis).

Shot mapping (timestamp order = shot order from PROMPT_REFERENCE.html):
  hf_20260321_220247 → 001_M01
  hf_20260322_202010 → 001_M02
  hf_20260322_202548 → 001_M03
  hf_20260322_202827 → 001_M04
  hf_20260322_202904 → 001_M05
  hf_20260322_203152 → 002_M01
  hf_20260322_203336 → 002_M02
  hf_20260322_203433 → 002_M03
  hf_20260322_215114 → 002_M04
  hf_20260322_215415 → 003_M01
"""

import json
import os
import sys
import time
from pathlib import Path

# ── Load .env before touching any env-dependent modules ──────────────────────
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    for line in _env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val
    print(f"[AUDIT] Loaded .env — GOOGLE_API_KEY present: {bool(os.environ.get('GOOGLE_API_KEY'))}")

sys.path.insert(0, str(Path(__file__).parent / "tools"))
from auto_revision_judge import AutoRevisionJudge

# ── Constants ─────────────────────────────────────────────────────────────────

RENDERS_DIR = Path(__file__).parent / "pipeline_outputs/victorian_shadows_ep1/higgsfield_renders"
OUTPUT_PATH = Path(__file__).parent / "pipeline_outputs/victorian_shadows_ep1/higgsfield_vision_audit.json"

# ── Shot definitions (derived from HIGGSFIELD_UPLOAD/PROMPT_REFERENCE.html) ───
# Each dict mimics the shot_plan.json shape that AutoRevisionJudge expects.

CAST_MAP = {
    "ELEANOR_VOSS": {
        "appearance": "Woman, 34, sharp angular features, auburn hair pulled back severely in a tight chignon, intense dark eyes, pale skin, tailored charcoal blazer over black turtleneck.",
    },
    "THOMAS_BLACKWOOD": {
        "appearance": "Man, 62, BRIGHT SILVER-WHITE hair, clearly aged, weathered face deeply lined with grief and exhaustion, sad grey eyes, rumpled navy suit with loosened tie.",
    },
    "NADIA_COLE": {
        "appearance": "Young woman, 28, dark brown skin, intelligent warm brown eyes, natural textured afro hair, vintage IRON MAIDEN band t-shirt logo clearly visible, open flannel shirt over it, jeans.",
    },
    "RAYMOND_CROSS": {
        "appearance": "Man, 45, STOCKY THICK-SET build, broad shoulders, thinning dark hair slicked back, sharp suspicious eyes, expensive black overcoat over silk dress shirt.",
    },
}

SHOTS = [
    # ── Scene 001 — Grand Foyer ─────────────────────────────────────────────
    {
        "shot_id":       "001_M01",
        "shot_type":     "wide",
        "location":      "Grand Foyer",
        "_scene_room":   "foyer",
        "duration":      10,
        "characters":    ["ELEANOR_VOSS", "THOMAS_BLACKWOOD"],
        "dialogue_text": "",
        "_beat_action":  "Eleanor pushes open heavy front doors, pauses in the grand foyer entrance, scanning the vast room. Thomas stands at the staircase.",
        "_beat_atmosphere": "Dusty Victorian grandeur. Morning light through arched windows. Stillness of an abandoned manor.",
        "nano_prompt":   "WIDE. Auburn-haired woman in charcoal blazer pushes open heavy front doors, pauses in grand Victorian foyer entrance, scanning the vast room. Silver-haired elder man stands at staircase. Single curved staircase center. Chandelier above. Face locked.",
    },
    {
        "shot_id":       "001_M02",
        "shot_type":     "medium",
        "location":      "Grand Foyer",
        "_scene_room":   "foyer",
        "duration":      10,
        "characters":    ["THOMAS_BLACKWOOD"],
        "dialogue_text": "",
        "_beat_action":  "Thomas trails hand slowly along dark mahogany banister, eyes downcast with grief.",
        "_beat_atmosphere": "Warm amber lamplight. Grief and exhaustion visible in every movement.",
        "nano_prompt":   "MEDIUM. Silver-haired man, 62, trails hand slowly along dark mahogany banister, eyes downcast with grief. Single curved staircase, carved balusters. Warm amber lamplight. Slow deliberate movement.",
    },
    {
        "shot_id":       "001_M03",
        "shot_type":     "medium",
        "location":      "Grand Foyer",
        "_scene_room":   "foyer",
        "duration":      10,
        "characters":    ["ELEANOR_VOSS"],
        "dialogue_text": "",
        "_beat_action":  "Eleanor opens briefcase on dusty console table, pulls out thick folder, begins reviewing documents.",
        "_beat_atmosphere": "Professional focus against Victorian decay. Focused, purposeful.",
        "nano_prompt":   "MEDIUM. Sharp-featured woman with auburn hair opens briefcase on dusty console table, pulls out thick folder, begins reviewing documents. Victorian foyer interior. Focused, professional.",
    },
    {
        "shot_id":       "001_M04",
        "shot_type":     "ots_b",
        "location":      "Grand Foyer",
        "_scene_room":   "foyer",
        "duration":      10,
        "characters":    ["ELEANOR_VOSS", "THOMAS_BLACKWOOD"],
        "dialogue_text": "",
        "_beat_action":  "Thomas gazes up at large oil portrait of stern Victorian woman above staircase landing, complicated grief on his face.",
        "_beat_atmosphere": "Heavy emotional weight. The portrait dominates. Grief and recognition.",
        "nano_prompt":   "OTS-B. Over auburn-haired woman's shoulder, silver-haired man frame-right gazes up at large oil portrait of stern Victorian woman above staircase landing. Grand foyer. He stares with complicated grief.",
    },
    {
        "shot_id":       "001_M05",
        "shot_type":     "closing",
        "location":      "Grand Foyer",
        "_scene_room":   "foyer",
        "duration":      10,
        "characters":    ["ELEANOR_VOSS", "THOMAS_BLACKWOOD"],
        "dialogue_text": "",
        "_beat_action":  "Two figures stand apart in vast Victorian foyer — Eleanor clutches inventory folder, Thomas has eyes lowered from portrait. Architecture dwarfs them both.",
        "_beat_atmosphere": "Silence and distance between two people. The manor envelops them.",
        "nano_prompt":   "WIDE. Two figures stand apart in vast Victorian foyer — auburn-haired woman clutches inventory folder frame-left, silver-haired man frame-right with eyes lowered from portrait. Architecture dwarfs them both. Silence.",
    },
    # ── Scene 002 — Library ─────────────────────────────────────────────────
    {
        "shot_id":       "002_M01",
        "shot_type":     "medium",
        "location":      "Library",
        "_scene_room":   "library",
        "duration":      10,
        "characters":    ["NADIA_COLE"],
        "dialogue_text": "",
        "_beat_action":  "Nadia moves through Victorian library lifting camera to capture bookshelves. Curious, energetic exploration.",
        "_beat_atmosphere": "Warm lamplight, dust motes in shafts of light. Academic wonder meets Victorian mystery.",
        "nano_prompt":   "MEDIUM. Young woman, dark brown skin, natural textured hair, Iron Maiden t-shirt, moves through Victorian library lifting camera to capture bookshelves. Floor-to-ceiling mahogany shelves, rolling brass ladder, dust motes in lamplight. Curious, energetic.",
    },
    {
        "shot_id":       "002_M02",
        "shot_type":     "medium_close",
        "location":      "Library",
        "_scene_room":   "library",
        "duration":      10,
        "characters":    ["NADIA_COLE"],
        "dialogue_text": "",
        "_beat_action":  "Nadia catches falling envelope from shelf, unfolds old letter, expression shifts from curiosity to shock. Eyes scanning paper rapidly.",
        "_beat_atmosphere": "Discovery. The secret surfaces. Shock registering across her face.",
        "nano_prompt":   "MEDIUM CLOSE. Young woman with natural afro catches falling envelope from shelf, unfolds old letter, expression shifts from curiosity to shock. Victorian library. Eyes scanning paper rapidly, brows rising. Hands tremble slightly, breath catches.",
    },
    {
        "shot_id":       "002_M03",
        "shot_type":     "medium",
        "location":      "Library",
        "_scene_room":   "library",
        "duration":      10,
        "characters":    ["NADIA_COLE"],
        "dialogue_text": "",
        "_beat_action":  "Nadia folds letter quickly, slips it into back pocket of jeans, glances toward library door with guarded expression.",
        "_beat_atmosphere": "Secrecy. Decision made. Protective instinct activating.",
        "nano_prompt":   "MEDIUM. Young woman folds letter quickly, slips it into back pocket of jeans, glances toward library door with guarded expression. Victorian library. Decisive, secretive movement.",
    },
    {
        "shot_id":       "002_M04",
        "shot_type":     "closing",
        "location":      "Library",
        "_scene_room":   "library",
        "duration":      10,
        "characters":    ["NADIA_COLE"],
        "dialogue_text": "",
        "_beat_action":  "Nadia alone in vast Victorian library, three-quarter back to camera, surrounded by floor-to-ceiling bookshelves. She has read the letter. Stillness.",
        "_beat_atmosphere": "The weight of the secret. The room is larger than her knowledge. Isolation.",
        "nano_prompt":   "WIDE. Young woman alone in vast Victorian library, three-quarter back to camera, surrounded by floor-to-ceiling bookshelves. She has read the letter. Stillness. The room is larger than her secret.",
    },
    # ── Scene 003 — Drawing Room ─────────────────────────────────────────────
    {
        "shot_id":       "003_M01",
        "shot_type":     "medium",
        "location":      "Drawing Room",
        "_scene_room":   "drawing_room",
        "duration":      10,
        "characters":    ["RAYMOND_CROSS", "ELEANOR_VOSS"],
        "dialogue_text": "",
        "_beat_action":  "Raymond steps closer with arms folded, blocking doorway. Eleanor faces him. Confrontational standoff.",
        "_beat_atmosphere": "Threat and defiance. Dust sheets draped over furniture. Power dynamics made physical.",
        "nano_prompt":   "MEDIUM. STOCKY THICK-SET man, thinning dark hair, expensive overcoat, steps closer with arms folded, blocking doorway. Sharp-featured woman with auburn hair faces him. Victorian drawing room with dust sheets. Confrontational.",
    },
]

# ── File → shot mapping (chronological order) ────────────────────────────────

FILES = sorted(RENDERS_DIR.glob("hf_*.mp4"), key=lambda p: p.name)
assert len(FILES) == 10, f"Expected 10 hf_*.mp4 files, found {len(FILES)}"
assert len(SHOTS) == 10, "Shot list must have exactly 10 entries"

SHOT_FILE_PAIRS = list(zip(SHOTS, FILES))

# ── Run the judge ─────────────────────────────────────────────────────────────

def main():
    judge = AutoRevisionJudge()
    if not judge.available:
        print("[AUDIT] ERROR: GOOGLE_API_KEY not loaded — cannot proceed.")
        sys.exit(1)

    print(f"[AUDIT] AutoRevisionJudge ready. Scoring {len(SHOT_FILE_PAIRS)} renders...\n")

    results = []
    summary = {"APPROVE": 0, "WARN": 0, "REJECT": 0}

    for i, (shot, video_path) in enumerate(SHOT_FILE_PAIRS, 1):
        shot_id = shot["shot_id"]
        print(f"[{i:02d}/10] {shot_id} ← {video_path.name}")

        # Next shot for continuity scoring (None for last in each scene)
        next_shot_idx = i  # pairs are 0-indexed, so next is i (current is i-1)
        next_shot = SHOTS[next_shot_idx] if next_shot_idx < len(SHOTS) else None
        # Don't chain across scenes
        if next_shot and next_shot["shot_id"][:3] != shot_id[:3]:
            next_shot = None

        t0 = time.time()
        try:
            verdict = judge.judge(
                video_path=str(video_path),
                shot=shot,
                cast_map=CAST_MAP,
                next_shot=next_shot,
                delete_after=True,   # clean up Files API after analysis
            )
        except Exception as e:
            print(f"  ⚠️  Judge exception: {e} — recording WARN")
            from auto_revision_judge import VideoVerdict
            verdict = VideoVerdict(
                shot_id=shot_id,
                video_path=str(video_path),
                overall=0.55,
                verdict="WARN",
                backend="exception",
                analysis_ms=int((time.time() - t0) * 1000),
            )
            verdict.regen_instruction = f"Judge exception: {e}"

        elapsed = time.time() - t0
        summary[verdict.verdict] = summary.get(verdict.verdict, 0) + 1

        # Pretty-print result
        icon = {"APPROVE": "✅", "WARN": "⚠️ ", "REJECT": "❌"}.get(verdict.verdict, "❓")
        print(f"  {icon} {verdict.verdict}  overall={verdict.overall:.3f}  ({elapsed:.1f}s)")

        # Per-dimension scores
        for dim, ds in (verdict.dimensions or {}).items():
            bar = "█" * int(ds.score * 10) + "░" * (10 - int(ds.score * 10))
            flag = " ◄ HARD REJECT" if dim in verdict.hard_rejects else ""
            print(f"     {bar} {ds.score:.2f}  {dim}{flag}")
            if ds.observation:
                print(f"          → {ds.observation}")

        if verdict.regen_instruction:
            print(f"  🔧 FIX: {verdict.regen_instruction}")
        print()

        result_dict = verdict.to_dict()
        result_dict["video_filename"] = video_path.name
        result_dict["shot_prompt_excerpt"] = shot["nano_prompt"][:120]
        results.append(result_dict)

        # Brief pause between uploads to stay within Gemini rate limits
        if i < len(SHOT_FILE_PAIRS):
            time.sleep(3)

    # ── Save audit JSON ───────────────────────────────────────────────────────
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    audit = {
        "audit_version": "1.0",
        "project":       "victorian_shadows_ep1",
        "render_source": "higgsfield",
        "total_files":   len(results),
        "summary":       summary,
        "pass_rate":     round(summary["APPROVE"] / len(results), 3),
        "results":       results,
    }
    OUTPUT_PATH.write_text(json.dumps(audit, indent=2))
    print(f"[AUDIT] Results saved → {OUTPUT_PATH}")

    # ── Final summary ─────────────────────────────────────────────────────────
    print("\n" + "═" * 60)
    print(f"  HIGGSFIELD VISION AUDIT — {len(results)} renders scored")
    print("═" * 60)
    print(f"  ✅ APPROVE : {summary['APPROVE']}")
    print(f"  ⚠️  WARN    : {summary['WARN']}")
    print(f"  ❌ REJECT  : {summary['REJECT']}")
    print(f"  Pass rate : {audit['pass_rate']:.0%}")
    print("═" * 60)

    # Highlight rejects
    rejects = [r for r in results if r["verdict"] == "REJECT"]
    if rejects:
        print("\nREJECTED (need regen):")
        for r in rejects:
            print(f"  ❌ {r['shot_id']} ({r['video_filename'][:40]})")
            print(f"     {r['regen_instruction'][:120]}")


if __name__ == "__main__":
    main()
