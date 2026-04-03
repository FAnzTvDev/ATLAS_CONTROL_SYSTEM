"""
V27.5.1 PARITY VERIFICATION TEST
==================================
Verifies that BOTH execution paths (orchestrator + V26 controller)
have all 5 V27.5.1 safety systems wired identically.

Systems checked:
  1. Learning Log regression check at startup
  2. Identity Injection in FAL worker (pre-gen)
  3. Prompt Corruption Detection in FAL worker (pre-gen)
  4. Multi-Candidate Count boost in FAL worker (pre-gen)
  5. Vision Judge post-gen identity verification
  6. Vision Judge fallback candidate scorer
  7. Multi-Candidate Selector best-of-N logic

Run: python3 tools/test_v27_5_1_parity.py
"""

import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PASS = 0
FAIL = 0
WARN = 0

def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name}" + (f" — {detail}" if detail else ""))

def warn(name, detail=""):
    global WARN
    WARN += 1
    print(f"  [WARN] {name}" + (f" — {detail}" if detail else ""))


# ═══════════════════════════════════════════════════════════════
# GROUP 1: Module imports — all V27.5.1 tools must be importable
# ═══════════════════════════════════════════════════════════════
print("\n=== GROUP 1: V27.5.1 MODULE IMPORTS ===\n")

try:
    from tools.prompt_identity_injector import inject_identity_into_prompt
    check("prompt_identity_injector importable", True)
except ImportError as e:
    check("prompt_identity_injector importable", False, str(e))

try:
    from tools.vision_judge import judge_frame, build_regen_plan, JudgeVerdict, extract_identity_markers, score_caption_against_markers
    check("vision_judge importable (all 5 exports)", True)
except ImportError as e:
    check("vision_judge importable", False, str(e))

try:
    from tools.multi_candidate_selector import get_candidate_count, select_best_candidate, CandidateResult
    check("multi_candidate_selector importable (all 3 exports)", True)
except ImportError as e:
    check("multi_candidate_selector importable", False, str(e))

try:
    from tools.atlas_learning_log import LearningLog, KNOWN_FIXES
    check("atlas_learning_log importable", True)
except ImportError as e:
    check("atlas_learning_log importable", False, str(e))


# ═══════════════════════════════════════════════════════════════
# GROUP 2: V26 controller source code verification
# ═══════════════════════════════════════════════════════════════
print("\n=== GROUP 2: V26 CONTROLLER WIRING (source verification) ===\n")

v26_src = open("atlas_v26_controller.py", errors="ignore").read()

# 1. Learning log at init
check("V26: learning log regression check in __init__",
      "from tools.atlas_learning_log import LearningLog" in v26_src
      and "check_regression" in v26_src)

# 2. Identity injection in _exec_fal_shot
check("V26: identity injection in FAL worker",
      "from tools.prompt_identity_injector import inject_identity_into_prompt" in v26_src
      and "inject_identity_into_prompt" in v26_src)

# 3. Corruption detection
check("V26: prompt corruption detection in FAL worker",
      "CORRUPTION" in v26_src
      and "nano_prompt.count(_sub) >= 3" in v26_src)

# 4. Multi-candidate count boost
check("V26: multi-candidate count boost in FAL worker",
      "from tools.multi_candidate_selector import get_candidate_count" in v26_src
      and "get_candidate_count(_orig_shot)" in v26_src)

# 5. Vision Judge post-gen
check("V26: vision judge post-gen Phase 7",
      "from tools.vision_judge import judge_frame" in v26_src
      and "vision_judge" in v26_src)

# 6. Vision Judge fallback scorer
check("V26: vision judge fallback candidate scorer",
      "from tools.multi_candidate_selector import select_best_candidate" in v26_src
      and "select_best_candidate" in v26_src)

# 7. _orig_shot key (not _shot_data)
check("V26: uses _orig_shot key (not _shot_data)",
      '_orig_shot = cs.get("_orig_shot"' in v26_src)


# ═══════════════════════════════════════════════════════════════
# GROUP 3: Orchestrator source code verification (same checks)
# ═══════════════════════════════════════════════════════════════
print("\n=== GROUP 3: ORCHESTRATOR WIRING (source verification) ===\n")

orch_src = open("orchestrator_server.py", errors="ignore").read()

check("ORCH: identity injection wired",
      "inject_identity_into_prompt" in orch_src)

check("ORCH: vision judge post-gen wired",
      "from tools.vision_judge import judge_frame" in orch_src)

check("ORCH: multi-candidate selector fallback",
      "from tools.multi_candidate_selector import select_best_candidate" in orch_src)

check("ORCH: prompt corruption guard (ltx_motion_prompt)",
      "orrupted" in orch_src and "substring appears 3+ times" in orch_src
      or ("_vp_is_corrupted" in orch_src))


# ═══════════════════════════════════════════════════════════════
# GROUP 4: Identity injector functional tests
# ═══════════════════════════════════════════════════════════════
print("\n=== GROUP 4: IDENTITY INJECTOR FUNCTIONAL ===\n")

from tools.prompt_identity_injector import inject_identity_into_prompt

# Test 1: Character shot gets [CHARACTER:] block
cast = {
    "THOMAS BLACKWOOD": {
        "appearance": "man, 62, distinguished, silver hair, navy suit, authoritative"
    }
}
prompt = "50mm lens, desaturated cool tones, interior foyer, cinematic"
result = inject_identity_into_prompt(prompt, ["THOMAS BLACKWOOD"], cast, "close_up", "")
check("Injector: character shot gets [CHARACTER:] block",
      "[CHARACTER:" in result,
      f"Got: {result[:100]}")

# Test 2: Empty shot gets negative constraint
result_empty = inject_identity_into_prompt(prompt, [], cast, "establishing", "")
check("Injector: empty shot gets 'No people visible'",
      "No people" in result_empty or "no people" in result_empty.lower(),
      f"Got: {result_empty[:100]}")

# Test 3: Has_amplified_identity check — already-injected prompt NOT double-injected
already_injected = result  # has [CHARACTER:] block
result_double = inject_identity_into_prompt(already_injected, ["THOMAS BLACKWOOD"], cast, "close_up", "")
# Should NOT have two [CHARACTER: blocks
count_blocks = result_double.count("[CHARACTER:")
check("Injector: no double injection on already-injected prompt",
      count_blocks == 1,
      f"Found {count_blocks} [CHARACTER:] blocks")

# Test 4: Location name stripping
prompt_with_loc = "HARGROVE ESTATE, 50mm lens, cinematic"
result_loc = inject_identity_into_prompt(prompt_with_loc, ["THOMAS BLACKWOOD"], cast, "close_up", "")
check("Injector: HARGROVE ESTATE stripped from prompt",
      "HARGROVE" not in result_loc,
      f"Got: {result_loc[:100]}")


# ═══════════════════════════════════════════════════════════════
# GROUP 5: Multi-candidate selector functional tests
# ═══════════════════════════════════════════════════════════════
print("\n=== GROUP 5: MULTI-CANDIDATE SELECTOR FUNCTIONAL ===\n")

from tools.multi_candidate_selector import get_candidate_count, CandidateResult

# Hero shots = 3
check("Selector: close_up with chars → 3 candidates",
      get_candidate_count({"shot_type": "close_up", "characters": ["THOMAS"]}) == 3)

check("Selector: medium_close with chars → 3 candidates",
      get_candidate_count({"shot_type": "medium_close", "characters": ["ELEANOR"]}) == 3)

# Dialogue boost
check("Selector: medium with dialogue → 3 candidates (dialogue boost)",
      get_candidate_count({"shot_type": "medium", "characters": ["THOMAS"], "dialogue_text": "Hello"}) == 3)

# Production = 2
check("Selector: medium with chars, no dialogue → 2 candidates",
      get_candidate_count({"shot_type": "medium", "characters": ["THOMAS"]}) == 2)

check("Selector: ots with chars → 2 candidates",
      get_candidate_count({"shot_type": "ots", "characters": ["THOMAS", "ELEANOR"]}) == 2)

# B-roll = 1
check("Selector: establishing no chars → 1 candidate",
      get_candidate_count({"shot_type": "establishing", "characters": []}) == 1)

check("Selector: b_roll → 1 candidate",
      get_candidate_count({"shot_type": "b_roll"}) == 1)


# ═══════════════════════════════════════════════════════════════
# GROUP 6: Vision Judge functional tests
# ═══════════════════════════════════════════════════════════════
print("\n=== GROUP 6: VISION JUDGE FUNCTIONAL ===\n")

from tools.vision_judge import extract_identity_markers, score_caption_against_markers

# Test marker extraction — function takes appearance STRING, not dict
markers = extract_identity_markers(cast["THOMAS BLACKWOOD"]["appearance"])
check("VisionJudge: extract markers finds hair",
      any("silver" in m[0] for m in markers),
      f"Markers: {markers}")

check("VisionJudge: extract markers finds suit",
      any("navy" in m[0] or "suit" in m[0] for m in markers),
      f"Markers: {markers}")

# Test scoring — correct person caption (returns (score, matched, missed) tuple)
correct_caption = "a distinguished older man with silver white hair wearing a dark navy suit standing in a grand foyer"
score_correct, matched_c, missed_c = score_caption_against_markers(correct_caption, markers)
check("VisionJudge: correct caption scores > 0.4",
      score_correct > 0.4,
      f"Score: {score_correct:.3f}, matched: {matched_c}, missed: {missed_c}")

# Test scoring — wrong person caption
wrong_caption = "a young woman with curly dark hair wearing jeans and a band t-shirt in a modern office"
score_wrong, matched_w, missed_w = score_caption_against_markers(wrong_caption, markers)
check("VisionJudge: wrong caption scores < 0.2",
      score_wrong < 0.2,
      f"Score: {score_wrong:.3f}, matched: {matched_w}")

# Test scoring — correct beats wrong
check("VisionJudge: correct score > wrong score",
      score_correct > score_wrong,
      f"Correct={score_correct:.3f}, Wrong={score_wrong:.3f}")


# ═══════════════════════════════════════════════════════════════
# GROUP 7: Learning Log functional tests
# ═══════════════════════════════════════════════════════════════
print("\n=== GROUP 7: LEARNING LOG FUNCTIONAL ===\n")

from tools.atlas_learning_log import LearningLog, KNOWN_FIXES

check("LearningLog: 15+ known fixes pre-populated",
      len(KNOWN_FIXES) >= 15,
      f"Found {len(KNOWN_FIXES)}")

# Check key bugs are in the list
bug_ids = {f["bug_id"] for f in KNOWN_FIXES}
check("LearningLog: IDENTITY_SKIP_52PCT in known fixes",
      "IDENTITY_SKIP_52PCT" in bug_ids)

check("LearningLog: ELEANOR_WEAK_SIGNATURE in known fixes",
      "ELEANOR_WEAK_SIGNATURE" in bug_ids)

check("LearningLog: BLANKET_ANTI_MORPH_FREEZE in known fixes",
      "BLANKET_ANTI_MORPH_FREEZE" in bug_ids)

check("LearningLog: STAIRCASE_MATERIAL_DRIFT in known fixes",
      "STAIRCASE_MATERIAL_DRIFT" in bug_ids)

# Verify all fixes have verification_code
all_have_code = all(f.get("verification_code") for f in KNOWN_FIXES)
check("LearningLog: all fixes have verification_code",
      all_have_code)


# ═══════════════════════════════════════════════════════════════
# GROUP 8: Cross-path parity — coverage matrix
# ═══════════════════════════════════════════════════════════════
print("\n=== GROUP 8: CROSS-PATH PARITY MATRIX ===\n")

systems = [
    ("Identity Injection (pre-gen)", "inject_identity_into_prompt", "inject_identity_into_prompt"),
    ("Corruption Detection (pre-gen)", "orrupted", "CORRUPTION"),  # orch uses "corrupted", v26 uses "CORRUPTION"
    ("Multi-Candidate Count (pre-gen)", "get_candidate_count", "get_candidate_count"),
    ("Vision Judge (post-gen)", "judge_frame", "vj_judge_frame"),
    ("Candidate Selector (fallback)", "select_best_candidate", "select_best_candidate"),
]

for name, orch_marker, v26_marker in systems:
    in_orch = orch_marker in orch_src
    in_v26 = v26_marker in v26_src
    if in_orch and in_v26:
        check(f"PARITY: {name}", True)
    elif in_orch and not in_v26:
        check(f"PARITY: {name}", False, "MISSING from V26 controller")
    elif not in_orch and in_v26:
        check(f"PARITY: {name}", False, "MISSING from orchestrator")
    else:
        check(f"PARITY: {name}", False, "MISSING from BOTH paths")


# ═══════════════════════════════════════════════════════════════
# GROUP 9: Identity Injector source integrity
# ═══════════════════════════════════════════════════════════════
print("\n=== GROUP 9: INJECTOR SOURCE INTEGRITY ===\n")

inj_src = open("tools/prompt_identity_injector.py", errors="ignore").read()

check("Injector: uses has_amplified_identity (not has_identity)",
      "has_amplified_identity" in inj_src)

check("Injector: VIVID AUBURN RED in amplification map",
      "VIVID AUBURN RED" in inj_src)

check("Injector: strips HARGROVE location name",
      "HARGROVE" in inj_src)

check("Injector: 'No people visible' for empty shots",
      "No people visible" in inj_src or "No people" in inj_src)


# ═══════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════
print(f"\n{'='*60}")
print(f"V27.5.1 PARITY VERIFICATION: {PASS} PASS / {FAIL} FAIL / {WARN} WARN")
print(f"{'='*60}")

if FAIL == 0:
    print("\nALL SYSTEMS AT PARITY — ready for production run.")
else:
    print(f"\n{FAIL} FAILURE(S) — fix before running production.")

sys.exit(FAIL)
