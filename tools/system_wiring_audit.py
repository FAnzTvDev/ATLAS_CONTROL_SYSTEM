#!/usr/bin/env python3
"""ATLAS V25 Full System Wiring Audit — maps what's live, built, and planned."""
import json, os

print("=" * 70)
print("  ATLAS V25 — FULL SYSTEM WIRING MAP + UPGRADE PHASE PLAN")
print("  Autonomous Build Covenant Cross-Reference")
print("=" * 70)

with open("orchestrator_server.py") as _f:

    server = _f.read()

# =============================================
# BRAIN MODULES
# =============================================
print("\n" + "=" * 70)
print("  SECTION 1: BRAIN MODULE INVENTORY")
print("=" * 70)

modules = [
    ("Film Engine",          "film_engine.py",               "cortex"),
    ("Basal Ganglia",        "basal_ganglia_engine.py",      "selection"),
    ("Meta Director",        "meta_director.py",             "oversight"),
    ("Vision Analyst",       "vision_analyst.py",            "visual"),
    ("Continuity Memory",    "continuity_memory.py",         "spatial"),
    ("Shot Authority",       "shot_authority.py",            "quality"),
    ("CPC (Immune)",         "creative_prompt_compiler.py",  "immune"),
    ("Editorial Intel",      "editorial_intelligence.py",    "cerebellum"),
    ("Prompt Authority",     "prompt_authority_gate.py",     "filter"),
    ("Movie Lock",           "movie_lock_mode.py",           "contract"),
    ("Doctrine Engine",      "doctrine_engine.py",           "governance"),
    ("Post-Fix Sanitizer",   "post_fixv16_sanitizer.py",    "hygiene"),
    ("Scene Intent",         "scene_intent_engine.py",       "frontal"),
    ("Behavior Mapper",      "cinematic_behavior_mapper.py", "motor"),
    ("Character State",      "character_state_engine.py",    "limbic"),
    ("Audience Model",       "audience_model.py",            "mirror"),
]

for name, fname, role in modules:
    exists = os.path.exists(os.path.join("tools", fname))
    mod_name = fname.replace(".py", "")
    wired = mod_name in server
    if exists and wired:
        status = "[LIVE]  "
    elif exists:
        status = "[BUILT] "
    else:
        status = "[----]  "
    ef = "Y" if exists else "N"
    wf = "Y" if wired else "N"
    print(f"  {status} {name:25s}  role={role:12s}  file={ef}  server={wf}")

# =============================================
# PIPELINE INTEGRATION POINTS
# =============================================
print("\n" + "=" * 70)
print("  SECTION 2: PIPELINE INTEGRATION POINTS")
print("=" * 70)

hooks = [
    ("fix-v16",               "fix-v16",               "Enrichment pipeline"),
    ("generate-first-frames", "generate-first-frames", "Frame generation"),
    ("render-videos",         "render-videos",          "Video generation"),
    ("master-chain",          "master-chain",           "Chain pipeline"),
    ("audit",                 "v21/audit",              "Contract validation"),
    ("creative-audit",        "v25/creative-audit",     "CPC scoring"),
    ("editorial-plan",        "v25/editorial-plan",     "Editorial analysis"),
    ("pre-generation-gate",   "pre-generation-gate",    "System readiness"),
    ("continuity-gate",       "continuity-gate",        "State validation"),
]

for name, pattern, desc in hooks:
    found = pattern in server
    tag = "[LIVE]  " if found else "[----]  "
    print(f"  {tag} {name:25s}  {desc}")

# =============================================
# DOCTRINE LAWS
# =============================================
print("\n" + "=" * 70)
print("  SECTION 3: DOCTRINE LAW RANGES")
print("=" * 70)

law_ranges = [
    ("1-49",    "Core infrastructure (V17)"),
    ("50-94",   "LOA + Wardrobe + Fidelity (V17.5-V17.8)"),
    ("95-118",  "Master Chain + Continuity Gate (V18)"),
    ("119-134", "Continuity Tightener + V21 Authority (V18.3-V21)"),
    ("135-177", "Auto-enrichment + Movie Lock + Import (V21.8-V21.9)"),
    ("178-195", "Regression Prevention + Sanitizer (V22)"),
    ("196-218", "Brain Architecture + Shot Authority (V24)"),
    ("219-230", "Doctrine System + Production Laws"),
    ("231-235", "V25 CURE Laws (dialogue, duration, coverage)"),
    ("236-245", "CPC Immune System Laws"),
    ("246-255", "Editorial Intelligence Laws"),
]
for r, desc in law_ranges:
    print(f"  Laws {r:10s}  {desc}")

# =============================================
# PROJECT STATE
# =============================================
print("\n" + "=" * 70)
print("  SECTION 4: PROJECT STATE (victorian_shadows_ep1)")
print("=" * 70)

proj = "pipeline_outputs/victorian_shadows_ep1"
sp_path = os.path.join(proj, "shot_plan.json")
if os.path.exists(sp_path):
    d = json.load(open(sp_path))
    shots = d.get("shots", d.get("shot_plan", []))
    scenes = sorted(set(s.get("scene_id", "?") for s in shots))
    chars = sorted(set(c for s in shots for c in (s.get("characters") or [])))
    enriched = sum(1 for s in shots if "composition:" in (s.get("nano_prompt") or ""))
    has_gold = sum(1 for s in shots if "NO morphing" in (s.get("ltx_motion_prompt") or ""))
    has_speaks = sum(1 for s in shots if "character speaks:" in (s.get("ltx_motion_prompt") or ""))
    has_performs = sum(1 for s in shots if "character performs:" in (s.get("ltx_motion_prompt") or ""))
    dialogue = sum(1 for s in shots if s.get("dialogue_text"))
    has_coverage = sum(1 for s in shots if s.get("coverage_role"))
    has_state = sum(1 for s in shots if s.get("state_in"))

    print(f"  Total shots:      {len(shots)}")
    print(f"  Scenes:           {len(scenes)} {scenes}")
    print(f"  Characters:       {len(chars)} {chars}")
    print(f"  Dialogue shots:   {dialogue}")
    print(f"  Enriched (comp):  {enriched}/{len(shots)}  {'OK' if enriched > len(shots)*0.7 else 'NEEDS FIX-V16'}")
    print(f"  Gold standard:    {has_gold}/{len(shots)}  {'OK' if has_gold > len(shots)*0.8 else 'NEEDS FIX-V16'}")
    print(f"  Speaks markers:   {has_speaks}")
    print(f"  Performs markers:  {has_performs}")
    print(f"  Coverage roles:   {has_coverage}/{len(shots)}")
    print(f"  State tracking:   {has_state}/{len(shots)}")

    # Scene 001 detail
    s001 = [s for s in shots if s.get("scene_id") == "001"]
    print(f"\n  Scene 001 detail:")
    print(f"    Shots: {len(s001)}")
    for s in s001:
        sid = s.get("shot_id", "?")
        st = (s.get("shot_type") or "?")[:15]
        cr = s.get("coverage_role", "?")[:12]
        ch = len(s.get("characters") or [])
        dl = "DLG" if s.get("dialogue_text") else "---"
        gs = "GOLD" if "NO morphing" in (s.get("ltx_motion_prompt") or "") else "----"
        print(f"    {sid:12s} {st:15s} {cr:12s} chars={ch} {dl} {gs}")

cm_path = os.path.join(proj, "cast_map.json")
if os.path.exists(cm_path):
    cm = json.load(open(cm_path))
    real_cast = {k: v for k, v in cm.items() if not v.get("_is_alias_of")}
    print(f"\n  Cast mapped:      {len(real_cast)} characters")
    for name in sorted(real_cast.keys()):
        has_hs = bool(real_cast[name].get("headshot_url"))
        print(f"    {name:30s} headshot={'Y' if has_hs else 'N'}")

lm = os.path.join(proj, "location_masters")
ff = os.path.join(proj, "first_frames")
vd = os.path.join(proj, "videos")
print(f"\n  Location masters: {'Y (' + str(len(os.listdir(lm))) + ')' if os.path.exists(lm) and os.listdir(lm) else 'N (fumigated)'}")
print(f"  First frames:     {'Y (' + str(len(os.listdir(ff))) + ')' if os.path.exists(ff) and os.listdir(ff) else 'N (fumigated)'}")
print(f"  Videos:           {'Y (' + str(len(os.listdir(vd))) + ')' if os.path.exists(vd) and os.listdir(vd) else 'N (fumigated)'}")

# =============================================
# PHASE PLAN
# =============================================
print("\n" + "=" * 70)
print("  SECTION 5: PHASED UPGRADE PLAN")
print("  (Autonomous Build Covenant: A=Diagnose, B=Law-Gate, C=Real-Data)")
print("=" * 70)

print("""
  PHASE 0 — CURRENT STATE (12 LIVE modules, 4 PLANNED)
    The body has a cortex, immune system, cerebellum, spatial memory,
    governance, and quality gates. It lacks the frontal lobe (intent),
    limbic system (character emotion), mirror neurons (audience model),
    and motor cortex (behavior mapping).

    These 4 PLANNED modules are Phase 5 — they need REAL render data
    to calibrate. Building them before the first render violates
    Covenant Rule C (calibration from enforced sessions only).

  PHASE 1 — PIPELINE READINESS [NO FAL SPEND]
    [a] Verify fix-v16 enrichment landed (composition markers > 70%)
    [b] Auto-cast verified (5 characters with headshots)
    [c] 10-contract audit = 0 CRITICAL
    [d] Creative audit < 5% contamination
    → Covenant Rule C: audit pass is necessary but not sufficient

  PHASE 2 — FIRST FRAMES (Scene 001, ~$2-3 FAL cost)
    [a] generate-first-frames scene_filter=001
    [b] Creates location masters + character reference frames
    [c] UI rehydrates — verify filmstrip shows new frames
    [d] Screenshot baseline
    → Covenant Rule A: if frame fails, diagnose root cause first

  PHASE 3 — LTX MASTER CHAIN (Scene 001, ~$5-8 FAL cost)
    [a] master-chain/render-scene scene=001 model=ltx
    [b] Archive to BASELINE_LTX_001/
    [c] Read doctrine ledger — first REAL calibration data
    [d] Read Murch scores — first REAL editorial data
    → Covenant Rule B: threshold changes require law amendment

  PHASE 4 — KLING COMPARISON (Scene 001, ~$5-8 FAL cost)
    [a] Same scene, same shots, model=kling
    [b] Archive to BASELINE_KLING_001/
    [c] Comparison grid: identity, dialogue, motion, chain continuity
    [d] This grid becomes the Film Engine routing policy

  PHASE 5 — COGNITION STACK (built FROM Phase 3-4 data)
    [a] character_state_engine.py — from real state_in/state_out data
    [b] audience_model.py — from real Murch scores + editorial tags
    [c] cinematic_behavior_mapper.py — from real coverage/emotion data
    [d] scene_intent_engine.py wiring (file exists, needs server hooks)
    → Covenant Rule C: these modules CONSUME render data, not theory

  PHASE 6 — DOCTRINE TUNING + LAW UPDATE
    [a] Tune identity_floor, reject_limit from real ledger
    [b] Add Laws 219-255 to canonical CLAUDE.md on Mac
    [c] Wire editorial Phase 2 into generation endpoints
    [d] Wire CPC into fix-v16 decontamination step
""")
print("=" * 70)
