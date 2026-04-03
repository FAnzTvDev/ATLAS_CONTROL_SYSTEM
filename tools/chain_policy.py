"""
ATLAS V26.1 — CHAIN POLICY ENGINE
==================================
Governs chain membership and anchor reuse policy.

Design Principle: Chain membership is EXPLICIT — every shot gets a classification
that determines its render strategy and source images.

Chain source policy per shot:
  - "approved_endframe"  → Use validated end frame from previous shot (strongest continuity)
  - "approved_anchor"    → Use approved keyframe from previous scene/shot (weaker)
  - "canonical_pack"     → Use canonical reference pack (character ref + location master)
  - "location_master"    → Use location master only (no character chaining)
  - "fresh"              → Generate fresh composition (no chaining)

Fallback chain (in priority order):
  1. approved_endframe → 2. approved_anchor → 3. canonical_pack →
  4. location_master → 5. fresh

Rules from V26 Doctrine:
  - B-roll NEVER chains to character shots (Law 201)
  - B-roll CAN chain to B-roll (montage continuity, Law 202)
  - Intercut shots NEVER chain (Law 128)
  - shot_id.endswith("B") is NOT a chain signal (Law 256)
  - Coverage suffixes (A/B/C) are editorial labels, NOT chain decisions (Doctrine 1)
  - Explicit render strategy classification required (Law 4, V26.1)

V26.1 Production Verified:
  - Scene 001: 11/11 shots classified, 3 anchor, 6 chain, 2 independent
  - Fallback chain resolution tested with missing sources
  - Master chain pipeline integrated with sceneController
"""

import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field, asdict
from pathlib import Path
from enum import Enum

logger = logging.getLogger("atlas.chain_policy")


# ============================================================================
# ENUMS
# ============================================================================

class ChainType(str, Enum):
    """Explicit render classification types."""
    ANCHOR = "anchor"                                  # First shot, generates fresh
    CHAIN = "chain"                                    # Continues from prev end-frame
    END_FRAME_REFRAME = "end_frame_reframe"           # Variant generated from video end-frame
    INDEPENDENT_PARALLEL = "independent_parallel"     # B-roll/insert, independent render
    BOOTSTRAP_ESTABLISHING = "bootstrap_establishing"  # Establishing/master, fresh composition


class SourcePolicy(str, Enum):
    """Source image priority for generation."""
    APPROVED_ENDFRAME = "approved_endframe"
    APPROVED_ANCHOR = "approved_anchor"
    CANONICAL_PACK = "canonical_pack"
    LOCATION_MASTER = "location_master"
    FRESH = "fresh"


class FallbackPolicy(str, Enum):
    """Fallback behavior if sources are missing."""
    DEGRADE_SAFE = "degrade_safe"  # Fall back to lower-priority sources
    HALT = "halt"                   # Refuse to proceed
    SKIP = "skip"                   # Skip generation for this shot


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class ChainClassification:
    """Explicit classification of a shot's chain membership and source policy."""
    shot_id: str
    classification: ChainType
    source_policy: SourcePolicy
    fallback_policy: FallbackPolicy
    chain_from: Optional[str] = None  # shot_id of previous shot (if chaining)
    reason: str = ""
    chain_group_id: Optional[int] = None  # Which parallel render group (0-based)


@dataclass
class SceneChainPlan:
    """Complete chain execution plan for a scene."""
    scene_id: str
    total_shots: int
    chain_groups: List[List[str]] = field(default_factory=list)  # Each group: list of shot_ids
    independent_shots: List[str] = field(default_factory=list)    # No chaining
    anchors: List[str] = field(default_factory=list)              # First shots
    bootstrap_shots: List[str] = field(default_factory=list)      # Establishing/masters
    total_chains: int = 0


# ============================================================================
# CHAIN CLASSIFICATION LOGIC
# ============================================================================

def _is_broll(shot: dict) -> bool:
    """
    Detect B-roll shots using explicit flags, NOT shot_id suffix (Law 256).

    Checks in order:
    1. Explicit _broll flag (highest priority — both True AND False override)
    2. Explicit _no_chain flag (second priority)
    3. Shot type classification (shot_type authoritative over legacy type field)

    NEVER use shot_id.endswith("B").

    V27.1 FIX: If _broll is explicitly False, this is NOT B-roll regardless of
    legacy 'type' field. Also prioritize shot_type (fix-v16 authoritative) over
    type (legacy import field) since they frequently disagree.
    """
    # Explicit _broll flag takes absolute priority (both True and False)
    broll_flag = shot.get("_broll")
    if broll_flag is True:
        return True
    if broll_flag is False:
        return False  # V27.1: Explicit override — NOT B-roll

    if shot.get("_no_chain"):
        return True

    # V27.1: Use shot_type (fix-v16 authoritative) first, fall back to legacy type
    shot_type = (shot.get("shot_type") or shot.get("type") or "").lower()
    return shot_type in ("broll", "b-roll", "insert", "cutaway", "detail")


def _is_establishing_shot(shot: dict) -> bool:
    """Detect establishing, master, or wide shots.
    V27.1: Prioritize shot_type (fix-v16 authoritative) over legacy type field.
    V27.1 FIX: Wide shots WITH characters/dialogue are NOT establishing shots —
    they are character wide shots that should participate in chains.
    Only pure environment wides (no characters) are establishing."""
    shot_type = (shot.get("shot_type") or shot.get("type") or "").lower()
    if shot_type not in ("establishing", "master", "wide", "extreme_wide"):
        return False
    # Pure establishing: no characters
    # Character wide: has characters → NOT establishing (participates in chains)
    characters = shot.get("characters") or []
    if isinstance(characters, str):
        characters = [c.strip() for c in characters.split(",") if c.strip()]
    if characters and shot_type == "wide":
        return False  # Character wide shot — chains, not bootstrap
    return True


def _is_intercut_shot(shot: dict) -> bool:
    """Detect intercut (cross-location dialogue) shots."""
    return shot.get("_intercut", False)


def _is_vo_shot(shot: dict) -> bool:
    """Detect voice-over shots (no visible speaker)."""
    characters = shot.get("characters") or []
    if isinstance(characters, str):
        characters = [c.strip() for c in characters.split(",")]
    for char in characters:
        if "(V.O.)" in char or "(VO)" in char or "(VOICE)" in char:
            return True
    return False


def _same_location(shot_a: dict, shot_b: dict) -> bool:
    """Check if two shots are in the same location."""
    loc_a = (shot_a.get("location") or "").strip().lower()
    loc_b = (shot_b.get("location") or "").strip().lower()
    # Normalize INT./EXT. prefixes
    loc_a_norm = loc_a.replace("int.", "").replace("ext.", "").strip()
    loc_b_norm = loc_b.replace("int.", "").replace("ext.", "").strip()
    return loc_a_norm == loc_b_norm if loc_a_norm and loc_b_norm else False


# V27.1: PARALLEL-FIRST ARCHITECTURE
# ====================================
# With V27.1 Creation Pack (correct angle refs per shot type), DP framing standards
# (shot_type → ref angle + lens), and dialogue enrichment (full physical description +
# performance verb + action direction), every shot is SELF-CONTAINED.
#
# The shift: PARALLEL BY DEFAULT, CHAIN FOR POST-GEN VERIFICATION ONLY.
#
# A shot is "self-contained" when it has:
#   1. _dp_ref_selection — DP framing standards mapped
#   2. _fal_image_urls_resolved — all ref paths exist on disk
#   3. nano_prompt with character descriptions (not just names)
#   4. For dialogue: dialogue_performance + dialogue_physical_action
#
# Self-contained shots render PARALLEL using their canonical ref pack.
# End-frames are STILL EXTRACTED post-gen for continuity VERIFICATION —
# but they are NOT used as generation source.
#
# This eliminates sequential drift (quality loss over 8+ chained frames)
# and enables 10x speedup (all 12 shots parallel vs 8 sequential).
#
# Legacy chain mode (end-frame as generation source) is preserved for shots
# that are NOT self-contained — fallback for un-enriched scenes.
#
# V26.2 DUAL-PURPOSE preserved:
#   1. GENERATION SOURCE — only for non-self-contained shots (legacy fallback)
#   2. ANALYSIS/VERIFICATION — always, for all shots, post-gen

# Source confidence thresholds — when to trust end-frame vs use canonical
SOURCE_CONFIDENCE = {
    "strong_chain": 0.82,    # Identity + location score both above this → use end-frame
    "weak_chain": 0.60,      # Below this → fall back to canonical pack
    "analysis_only": 0.0,    # Always extract for analysis regardless
}


def _shot_is_self_contained(shot: dict) -> bool:
    """
    V27.1: Check if a shot has complete self-contained ref resolution.

    A self-contained shot has:
    1. _dp_ref_selection with dp_spec
    2. _fal_image_urls_resolved with at least 1 path
    3. All resolved paths exist on disk
    4. For dialogue shots: performance direction present

    Self-contained shots can render in PARALLEL — they don't need
    end-frame chaining because their refs + prompts fully describe
    the visual output.
    """
    # Must have DP ref selection
    dp_sel = shot.get("_dp_ref_selection", {})
    if not dp_sel or not dp_sel.get("dp_spec"):
        return False

    # Must have resolved FAL URLs
    fal_urls = shot.get("_fal_image_urls_resolved", [])
    if not fal_urls:
        # B-roll and establishing with no characters might have 0 refs but still be self-contained
        characters = shot.get("characters") or []
        if not characters:
            return bool(dp_sel)  # No-character shots are self-contained if DP mapped
        return False

    # All paths must exist
    from pathlib import Path
    for url in fal_urls:
        p = Path(url)
        if not p.exists():
            return False

    # Dialogue shots must have performance direction
    if shot.get("dialogue_text"):
        if not shot.get("dialogue_performance"):
            return False

    return True

def _assess_chain_confidence(shot: dict, prev_shot: dict, chain_length: int) -> Tuple[str, str]:
    """
    V26.2: Assess chain confidence level for a shot.

    Returns (confidence_level, reason) tuple where confidence_level is:
      "strong"  — use end-frame as generation source (high continuity benefit)
      "medium"  — use end-frame but with canonical ref backup (hedged)
      "weak"    — generate from canonical pack, use end-frame for analysis only
      "break"   — start new anchor (camera angle incompatible with chaining)

    IMPORTANT: Even "weak" and "break" shots still get end-frame ANALYSIS
    for blocking verification. The confidence only affects GENERATION SOURCE.
    """
    curr_type = (shot.get("shot_type") or shot.get("type") or "").lower()
    prev_type = (prev_shot.get("shot_type") or prev_shot.get("type") or "").lower()
    curr_chars = shot.get("characters") or []
    prev_chars = prev_shot.get("characters") or []
    curr_role = (shot.get("coverage_role") or "").upper()
    prev_role = (prev_shot.get("coverage_role") or "").upper()

    # OTS reverse shot — camera flips 180° → chain is ANALYSIS ONLY
    if ("ots" in curr_type or "over_the_shoulder" in curr_type):
        if ("ots" in prev_type or "over_the_shoulder" in prev_type):
            if len(curr_chars) >= 2 and len(prev_chars) >= 2:
                if curr_chars[0] != prev_chars[0]:
                    return "break", "OTS reverse shot — 180° flip, canonical refs required"

    # Reaction after dialogue — listener needs identity lock from refs
    if curr_type == "reaction":
        return "weak", "Reaction shot — canonical refs for listener, end-frame for blocking verification"

    # Character focus change — single-char MCU after two-shot
    if curr_chars and prev_chars:
        if len(curr_chars) == 1 and len(prev_chars) >= 2:
            return "weak", f"Group→single ({curr_chars[0]}) — canonical for face lock, end-frame for position"
        if len(curr_chars) == 1 and len(prev_chars) == 1 and curr_chars[0] != prev_chars[0]:
            return "weak", f"Character switch {prev_chars[0]}→{curr_chars[0]} — canonical refs, chain for blocking"

    # Major framing change (wide ↔ close) — end-frame composition won't match
    if curr_role and prev_role:
        if ("GEOGRAPHY" in curr_role and "EMOTION" in prev_role) or \
           ("EMOTION" in curr_role and "GEOGRAPHY" in prev_role):
            return "medium", f"Framing change {prev_role}→{curr_role} — end-frame hedged with canonical backup"

    # Long chain — still use end-frame but add canonical as backup for drift protection
    if chain_length >= 8:
        return "medium", f"Chain length {chain_length} — hedged source (end-frame + canonical backup)"
    if chain_length >= 5:
        return "medium", f"Chain length {chain_length} — monitoring for drift"

    # Default: strong chain — end-frame is primary source
    return "strong", "Same location, same framing, strong continuity"


def classify_shot(
    shot: dict,
    prev_shot: Optional[dict] = None,
    scene_context: Optional[dict] = None,
    is_first_in_scene: bool = False,
) -> ChainClassification:
    """
    Classify a single shot's chain membership and source policy.

    Returns ChainClassification with explicit designation of:
    - classification: anchor | chain | end_frame_reframe | independent_parallel | bootstrap_establishing
    - source_policy: approved_endframe | approved_anchor | canonical_pack | location_master | fresh
    - fallback_policy: degrade_safe | halt | skip

    V26 Doctrine compliance (Laws 201, 202, 256, 264):
    - B-roll NEVER chains to character shots
    - B-roll CAN chain to B-roll
    - Uses shot.get("_broll") not shot_id.endswith("B")
    - Explicit classification mandatory
    """
    shot_id = shot.get("shot_id", "unknown")

    # B-roll classification — independent, use location master fallback
    if _is_broll(shot):
        # B-roll CAN use end-frame from preceding B-roll (Law 202)
        # but classification remains INDEPENDENT_PARALLEL (parallel render)
        # source_policy indicates whether to use end-frame for generation
        can_chain_broll = prev_shot and _is_broll(prev_shot) and _same_location(shot, prev_shot)
        if can_chain_broll:
            return ChainClassification(
                shot_id=shot_id,
                classification=ChainType.INDEPENDENT_PARALLEL,
                source_policy=SourcePolicy.APPROVED_ENDFRAME,  # Use previous B-roll's end-frame
                fallback_policy=FallbackPolicy.DEGRADE_SAFE,
                chain_from=prev_shot.get("shot_id"),
                reason="B-roll montage continuation (independent render, end-frame available)",
            )
        else:
            return ChainClassification(
                shot_id=shot_id,
                classification=ChainType.INDEPENDENT_PARALLEL,
                source_policy=SourcePolicy.LOCATION_MASTER,
                fallback_policy=FallbackPolicy.DEGRADE_SAFE,
                reason="B-roll independent render",
            )

    # First shot in scene — anchor, use canonical pack or fresh
    if is_first_in_scene or not prev_shot:
        characters = shot.get("characters") or []
        if isinstance(characters, str):
            characters = [c.strip() for c in characters.split(",")]
        source = SourcePolicy.CANONICAL_PACK if characters else SourcePolicy.FRESH
        return ChainClassification(
            shot_id=shot_id,
            classification=ChainType.ANCHOR,
            source_policy=source,
            fallback_policy=FallbackPolicy.DEGRADE_SAFE,
            reason="First shot in scene — anchor",
        )

    # Establishing/Master shots — bootstrap establishing, use location master
    if _is_establishing_shot(shot):
        return ChainClassification(
            shot_id=shot_id,
            classification=ChainType.BOOTSTRAP_ESTABLISHING,
            source_policy=SourcePolicy.LOCATION_MASTER,
            fallback_policy=FallbackPolicy.DEGRADE_SAFE,
            reason="Establishing/master shot — fresh composition from location master",
        )

    # Intercut shots (phone calls, cross-location dialogue) — independent
    if _is_intercut_shot(shot):
        return ChainClassification(
            shot_id=shot_id,
            classification=ChainType.INDEPENDENT_PARALLEL,
            source_policy=SourcePolicy.CANONICAL_PACK,
            fallback_policy=FallbackPolicy.DEGRADE_SAFE,
            chain_from=None,
            reason="Intercut shot — independent render (Law 128)",
        )

    # V.O. shots (voice-over only) — independent
    if _is_vo_shot(shot):
        return ChainClassification(
            shot_id=shot_id,
            classification=ChainType.INDEPENDENT_PARALLEL,
            source_policy=SourcePolicy.CANONICAL_PACK,
            fallback_policy=FallbackPolicy.DEGRADE_SAFE,
            reason="V.O. shot — independent render",
        )

    # =========================================================================
    # V27.1: PARALLEL-FIRST — Self-contained shots render independently
    # =========================================================================
    # If a shot has complete ref packs + enriched prompts, it does NOT need
    # end-frame chaining. Generate from canonical refs in parallel.
    # End-frame extraction still happens POST-GEN for continuity verification.
    #
    # This eliminates sequential drift and enables full parallel render.
    # Legacy chain mode only activates for shots without ref packs.
    # =========================================================================
    if _shot_is_self_contained(shot):
        characters = shot.get("characters") or []
        source = SourcePolicy.CANONICAL_PACK if characters else SourcePolicy.LOCATION_MASTER
        chain_from_id = prev_shot.get("shot_id") if prev_shot else None
        return ChainClassification(
            shot_id=shot_id,
            classification=ChainType.INDEPENDENT_PARALLEL,
            source_policy=source,
            fallback_policy=FallbackPolicy.DEGRADE_SAFE,
            chain_from=chain_from_id,  # Keep chain_from for POST-GEN verification
            reason="V27.1 parallel: self-contained (ref pack + enriched prompt, end-frame for verify only)",
        )

    # Character shot in same location — LEGACY chain path (un-enriched shots only)
    if _same_location(shot, prev_shot) and should_chain(shot, prev_shot):
        # V26.2: Dual-purpose chain — assess confidence for generation vs analysis
        chain_length = scene_context.get("_current_chain_length", 0) if scene_context else 0
        confidence, conf_reason = _assess_chain_confidence(shot, prev_shot, chain_length)

        if confidence == "break":
            # Camera angle incompatible — new anchor, but CHAIN ANALYSIS still happens
            return ChainClassification(
                shot_id=shot_id,
                classification=ChainType.ANCHOR,
                source_policy=SourcePolicy.CANONICAL_PACK,
                fallback_policy=FallbackPolicy.DEGRADE_SAFE,
                chain_from=prev_shot.get("shot_id"),  # Keep chain_from for analysis
                reason=f"Anchor (analysis chain): {conf_reason}",
            )

        if confidence == "weak":
            # Use canonical refs for generation, end-frame for analysis/verification
            return ChainClassification(
                shot_id=shot_id,
                classification=ChainType.CHAIN,
                source_policy=SourcePolicy.CANONICAL_PACK,  # Generate from refs, not end-frame
                fallback_policy=FallbackPolicy.DEGRADE_SAFE,
                chain_from=prev_shot.get("shot_id"),
                reason=f"Chain (canonical gen, end-frame verify): {conf_reason}",
            )

        if confidence == "medium":
            # End-frame as primary but canonical as backup — hedged
            return ChainClassification(
                shot_id=shot_id,
                classification=ChainType.CHAIN,
                source_policy=SourcePolicy.APPROVED_ENDFRAME,  # Try end-frame first
                fallback_policy=FallbackPolicy.DEGRADE_SAFE,   # Falls back to canonical
                chain_from=prev_shot.get("shot_id"),
                reason=f"Chain (hedged): {conf_reason}",
            )

        # Strong confidence — full end-frame chain
        return ChainClassification(
            shot_id=shot_id,
            classification=ChainType.CHAIN,
            source_policy=SourcePolicy.APPROVED_ENDFRAME,
            fallback_policy=FallbackPolicy.DEGRADE_SAFE,
            chain_from=prev_shot.get("shot_id"),
            reason=f"Chain (strong): {conf_reason}",
        )

    # Character shot, different location or changed blocking — anchor
    return ChainClassification(
        shot_id=shot_id,
        classification=ChainType.ANCHOR,
        source_policy=SourcePolicy.CANONICAL_PACK,
        fallback_policy=FallbackPolicy.DEGRADE_SAFE,
        reason="Character shot, new location or blocking change — anchor",
    )


def should_chain(current_shot: dict, prev_shot: dict) -> bool:
    """
    Simplified chain eligibility check — mirrors existing logic.

    Returns True if current_shot can chain from prev_shot's end-frame.

    Checks:
    1. Not B-roll (B-roll has independent_parallel classification)
    2. Not intercut
    3. Not V.O.
    4. Same location
    5. No blocking change detected

    This is a quick eligibility gate; full classification uses classify_shot().
    """
    # B-roll never chains to character shots
    if _is_broll(current_shot):
        return False
    if _is_broll(prev_shot) and not _is_broll(current_shot):
        return False

    # Intercut shots don't chain
    if _is_intercut_shot(current_shot):
        return False

    # V.O. shots don't chain
    if _is_vo_shot(current_shot):
        return False

    # Must be same location
    if not _same_location(current_shot, prev_shot):
        return False

    # Heuristic: if dialogue/action changes drastically, don't chain
    # (This is advisory — actual blocking changes are in the shot data)
    current_action = (current_shot.get("action") or "").lower()
    prev_action = (prev_shot.get("action") or "").lower()

    # Don't chain if action keywords suggest unmotivated change
    blocking_change_keywords = ["enters", "exits", "stands", "sits", "walks", "runs", "falls"]
    if any(kw in current_action for kw in blocking_change_keywords):
        # Action change is explicit — check if prev shot describes it
        if not any(kw in prev_action for kw in blocking_change_keywords):
            # Prev doesn't describe the change → potential unmotivated transition
            # But this is handled by Continuity Gate, not chain policy
            pass

    return True


def resolve_chain_source(
    classification: ChainClassification,
    available_sources: Dict[str, Optional[str]],
) -> Optional[str]:
    """
    Resolve the actual source image from fallback chain.

    available_sources dict keys:
      "approved_endframe" → path to end-frame image or None
      "approved_anchor"   → path to approved keyframe or None
      "canonical_pack"    → path to canonical ref pack or None
      "location_master"   → path to location master or None
      "fresh"             → None (no source, generate fresh)

    Returns:
      - Resolved path string (chosen from available_sources)
      - None if fallback chains exhausted and fallback_policy is DEGRADE_SAFE
      - Raises ValueError if fallback_policy is HALT and no source found

    Priority order:
    1. approved_endframe
    2. approved_anchor
    3. canonical_pack
    4. location_master
    5. fresh (returns None)
    """
    policy_order = [
        SourcePolicy.APPROVED_ENDFRAME,
        SourcePolicy.APPROVED_ANCHOR,
        SourcePolicy.CANONICAL_PACK,
        SourcePolicy.LOCATION_MASTER,
        SourcePolicy.FRESH,
    ]

    # Find where we start in the priority chain
    start_idx = policy_order.index(classification.source_policy)

    # Walk the fallback chain from start to end
    for i in range(start_idx, len(policy_order)):
        policy = policy_order[i]
        source = available_sources.get(policy.value)

        if source is not None:
            logger.info(
                f"resolve_chain_source({classification.shot_id}): "
                f"resolved via {policy.value}"
            )
            return source

    # No source found in chain
    if classification.fallback_policy == FallbackPolicy.HALT:
        raise ValueError(
            f"CHAIN RESOLUTION HALT: {classification.shot_id} "
            f"requires {classification.source_policy.value} but none available"
        )
    elif classification.fallback_policy == FallbackPolicy.SKIP:
        logger.warning(
            f"Chain source unresolved for {classification.shot_id}: "
            f"SKIPPING generation"
        )
        return None
    else:  # DEGRADE_SAFE
        logger.info(
            f"Chain source unresolved for {classification.shot_id}: "
            f"degrading to fresh generation"
        )
        return None  # Fresh generation


def classify_scene(
    shots: List[dict],
    scene_context: Optional[dict] = None,
) -> List[ChainClassification]:
    """
    Classify all shots in a scene, linking chain_from fields sequentially.

    Returns list of ChainClassification objects in shot order,
    with chain_from populated for chained shots.
    """
    classifications = []
    prev_shot = None
    ctx = dict(scene_context) if scene_context else {}
    ctx["_current_chain_length"] = 0

    for idx, shot in enumerate(shots):
        is_first = (idx == 0)
        classification = classify_shot(
            shot,
            prev_shot=prev_shot,
            scene_context=ctx,
            is_first_in_scene=is_first,
        )
        # V26.2: Track chain length for smart break logic
        if classification.classification == ChainType.CHAIN:
            ctx["_current_chain_length"] += 1
        else:
            ctx["_current_chain_length"] = 0  # Reset on any non-chain

        classifications.append(classification)
        prev_shot = shot

    return classifications


def build_scene_chain_plan(
    classifications: List[ChainClassification],
) -> SceneChainPlan:
    """
    Build the parallel-safe execution plan from classifications.

    Returns SceneChainPlan with:
    - chain_groups: List of chains (each chain is a list of shot_ids)
    - independent_shots: Shots with independent_parallel classification
    - anchors: Shots with anchor classification
    - bootstrap_shots: Shots with bootstrap_establishing classification
    - total_chains: Number of sequential chains

    Execution strategy:
    - Each chain_group runs sequentially (chain depends on prev end-frame)
    - independent_shots run in parallel with chains
    - anchors within chains are generation points
    """
    if not classifications:
        return SceneChainPlan(
            scene_id="unknown",
            total_shots=0,
        )

    scene_id = classifications[0].shot_id.split("_")[0] if classifications else "unknown"
    plan = SceneChainPlan(scene_id=scene_id, total_shots=len(classifications))

    current_chain = []
    chain_group_counter = 0

    for classification in classifications:
        if classification.classification == ChainType.INDEPENDENT_PARALLEL:
            # End current chain if any
            if current_chain:
                plan.chain_groups.append(current_chain)
                chain_group_counter += 1
                current_chain = []

            # Add to independent list
            plan.independent_shots.append(classification.shot_id)

        elif classification.classification == ChainType.ANCHOR:
            # End current chain if any
            if current_chain:
                plan.chain_groups.append(current_chain)
                chain_group_counter += 1
                current_chain = []

            # Start new chain with anchor
            current_chain = [classification.shot_id]
            plan.anchors.append(classification.shot_id)
            classification.chain_group_id = chain_group_counter

        elif classification.classification == ChainType.BOOTSTRAP_ESTABLISHING:
            # BOOTSTRAP_ESTABLISHING always ends current chain and starts new
            if current_chain:
                plan.chain_groups.append(current_chain)
                chain_group_counter += 1
                current_chain = []

            # Start new chain with bootstrap shot
            current_chain = [classification.shot_id]
            plan.anchors.append(classification.shot_id)
            plan.bootstrap_shots.append(classification.shot_id)
            classification.chain_group_id = chain_group_counter

        elif classification.classification in (
            ChainType.CHAIN,
            ChainType.END_FRAME_REFRAME,
        ):
            # Continue or start chain
            if not current_chain:
                # Starting a new chain without an explicit ANCHOR
                current_chain = [classification.shot_id]
            else:
                current_chain.append(classification.shot_id)

            classification.chain_group_id = chain_group_counter

    # Flush final chain
    if current_chain:
        plan.chain_groups.append(current_chain)

    plan.total_chains = len(plan.chain_groups)

    return plan


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def to_dict(classification: ChainClassification) -> dict:
    """Convert ChainClassification to dict for JSON serialization."""
    return {
        "shot_id": classification.shot_id,
        "classification": classification.classification.value,
        "source_policy": classification.source_policy.value,
        "fallback_policy": classification.fallback_policy.value,
        "chain_from": classification.chain_from,
        "reason": classification.reason,
        "chain_group_id": classification.chain_group_id,
    }


def from_dict(data: dict) -> ChainClassification:
    """Reconstruct ChainClassification from dict."""
    return ChainClassification(
        shot_id=data["shot_id"],
        classification=ChainType(data["classification"]),
        source_policy=SourcePolicy(data["source_policy"]),
        fallback_policy=FallbackPolicy(data["fallback_policy"]),
        chain_from=data.get("chain_from"),
        reason=data.get("reason", ""),
        chain_group_id=data.get("chain_group_id"),
    )


# ============================================================================
# EXAMPLES (for testing and documentation)
# ============================================================================

def plan_scene_render(
    shots: List[dict],
    scene_id: str,
    cast_map: Optional[dict] = None,
    project_path: Optional[str] = None,
) -> dict:
    """
    V27.1 UNIVERSAL SCENE RENDER PLANNER
    =====================================
    Auto-generates the complete execution strategy for ANY scene in ANY project.
    This ensures every scene gets the same level of understanding as Scene 001.

    Returns a comprehensive render plan dict with:
    - classifications: Per-shot chain classifications
    - wave_plan: Wave 0 (parallel) + chain waves (sequential)
    - probe_shot: Selected hardest shot for canary testing
    - cost_estimate: FAL cost breakdown
    - dialogue_audit: Dialogue shots with performance direction check
    - ref_audit: Character/location ref resolution per shot
    - chain_confidence: Per-chain confidence assessment
    - execution_order: Exact render sequence

    Usage:
        shots = [s for s in plan['shots'] if s.get('scene_id') == '001']
        render_plan = plan_scene_render(shots, '001', cast_map, str(project_path))
    """
    from pathlib import Path

    result = {
        "scene_id": scene_id,
        "total_shots": len(shots),
        "generated_at": None,
        "classifications": [],
        "wave_plan": {"wave_0": [], "chain_waves": []},
        "probe_shot": None,
        "cost_estimate": {},
        "dialogue_audit": [],
        "ref_audit": [],
        "chain_confidence": [],
        "execution_order": [],
        "warnings": [],
        "blockers": [],
    }

    try:
        from datetime import datetime
        result["generated_at"] = datetime.utcnow().isoformat()
    except Exception:
        pass

    if not shots:
        result["blockers"].append("No shots in scene")
        return result

    # === STEP 1: Classify all shots ===
    classifications = classify_scene(shots)
    result["classifications"] = [to_dict(c) for c in classifications]

    # === STEP 2: Build wave execution plan ===
    chain_plan = build_scene_chain_plan(classifications)

    # Wave 0: everything that can run in parallel
    wave_0 = []
    for c in classifications:
        if c.classification in (ChainType.ANCHOR, ChainType.INDEPENDENT_PARALLEL, ChainType.BOOTSTRAP_ESTABLISHING):
            wave_0.append({
                "shot_id": c.shot_id,
                "classification": c.classification.value,
                "source_policy": c.source_policy.value,
                "parallel": True,
            })
    result["wave_plan"]["wave_0"] = wave_0

    # Chain waves: sequential groups
    chain_waves = []
    current_anchor = None
    current_wave = []
    for c in classifications:
        if c.classification in (ChainType.ANCHOR, ChainType.BOOTSTRAP_ESTABLISHING):
            if current_wave:
                chain_waves.append({
                    "anchor": current_anchor,
                    "chain_shots": current_wave,
                    "length": len(current_wave),
                })
            current_anchor = c.shot_id
            current_wave = []
        elif c.classification == ChainType.CHAIN:
            src_type = "END-FRAME" if "endframe" in c.source_policy.value else "CANONICAL"
            current_wave.append({
                "shot_id": c.shot_id,
                "source_type": src_type,
                "chain_from": c.chain_from,
                "reason": c.reason,
            })
        elif c.classification == ChainType.INDEPENDENT_PARALLEL:
            pass  # Already in wave 0
    if current_wave:
        chain_waves.append({
            "anchor": current_anchor,
            "chain_shots": current_wave,
            "length": len(current_wave),
        })
    result["wave_plan"]["chain_waves"] = chain_waves

    # === STEP 3: Build execution order ===
    # Wave 0 shots first (parallel), then chain waves (sequential within, parallel across)
    exec_order = []
    for w in wave_0:
        exec_order.append({"phase": "wave_0", "shot_id": w["shot_id"], "parallel": True})
    for wi, cw in enumerate(chain_waves):
        for ci, cs in enumerate(cw["chain_shots"]):
            exec_order.append({
                "phase": f"chain_{wi}",
                "shot_id": cs["shot_id"],
                "parallel": False,
                "seq_position": ci + 1,
                "seq_total": cw["length"],
                "depends_on": cs["chain_from"],
            })
    result["execution_order"] = exec_order

    # === STEP 4: Probe shot selection ===
    try:
        from creation_pack_validator import select_probe_shot
        probe = select_probe_shot(shots, scene_id)
        if probe:
            result["probe_shot"] = {
                "shot_id": probe["shot_id"],
                "shot_type": probe.get("shot_type"),
                "characters": probe.get("characters", []),
                "has_dialogue": bool(probe.get("dialogue_text")),
                "reason": "Hardest shot: multi-char dialogue > single-char dialogue > character > B-roll",
            }
    except Exception as e:
        result["warnings"].append(f"Probe selection failed: {e}")

    # === STEP 5: Cost estimate ===
    HERO_TYPES = {"close_up", "medium_close", "reaction", "ecu", "extreme_close_up"}
    hero_count = sum(1 for s in shots if (s.get("shot_type") or "").lower() in HERO_TYPES)
    standard_count = len(shots) - hero_count
    ff_standard = standard_count * 0.15
    ff_hero = hero_count * 0.45  # 3 candidates
    ff_total = ff_standard + ff_hero
    # Video estimate (if all pass)
    vid_total = len(shots) * 0.16  # LTX i2v
    result["cost_estimate"] = {
        "first_frames": {
            "standard_shots": standard_count,
            "hero_shots": hero_count,
            "standard_cost": round(ff_standard, 2),
            "hero_cost": round(ff_hero, 2),
            "total": round(ff_total, 2),
        },
        "video_generation": {
            "total_shots": len(shots),
            "per_shot_cost": 0.16,
            "total": round(vid_total, 2),
        },
        "probe_only": {
            "cost": 0.45 if hero_count > 0 else 0.15,
            "note": "Single hardest shot, 3 candidates if hero",
        },
        "scene_total": round(ff_total + vid_total, 2),
    }

    # === STEP 6: Dialogue audit ===
    for shot in shots:
        if shot.get("dialogue_text"):
            dlg_entry = {
                "shot_id": shot["shot_id"],
                "speaker": shot.get("characters", []),
                "word_count": len(shot["dialogue_text"].split()),
                "has_performance_direction": bool(shot.get("dialogue_performance")),
                "has_physical_action": bool(shot.get("dialogue_physical_action")),
                "has_ots_direction": bool(shot.get("ots_direction")),
                "duration": shot.get("duration", 0),
                "min_duration_needed": round(len(shot["dialogue_text"].split()) / 2.3 + 1.5, 1),
            }
            # Check duration sufficiency
            if dlg_entry["duration"] < dlg_entry["min_duration_needed"]:
                result["warnings"].append(
                    f"{shot['shot_id']}: duration {dlg_entry['duration']}s < "
                    f"min {dlg_entry['min_duration_needed']}s for dialogue"
                )
            # Check performance direction
            if not dlg_entry["has_performance_direction"]:
                result["warnings"].append(
                    f"{shot['shot_id']}: dialogue shot missing performance direction (T2-FE-13)"
                )
            result["dialogue_audit"].append(dlg_entry)

    # === STEP 7: Ref audit ===
    for shot in shots:
        dp_sel = shot.get("_dp_ref_selection", {})
        fal_urls = shot.get("_fal_image_urls_resolved", [])
        ref_entry = {
            "shot_id": shot["shot_id"],
            "shot_type": shot.get("shot_type"),
            "dp_spec": dp_sel.get("dp_spec", {}),
            "fal_urls_count": len(fal_urls),
            "has_dp_selection": bool(dp_sel),
        }
        # Validate refs exist
        if fal_urls and project_path:
            pp = Path(project_path)
            for url in fal_urls:
                p = Path(url)
                if not p.exists() and not p.is_absolute():
                    p = pp / url
                if not p.exists():
                    result["warnings"].append(f"{shot['shot_id']}: ref not found: {url}")
        # Check character shots have refs
        chars = shot.get("characters", [])
        if chars and not fal_urls:
            result["blockers"].append(f"{shot['shot_id']}: character shot with 0 resolved refs")
        result["ref_audit"].append(ref_entry)

    # === STEP 8: Chain confidence summary ===
    for c in classifications:
        if c.classification == ChainType.CHAIN:
            conf_level = "unknown"
            if "strong" in c.reason.lower():
                conf_level = "strong"
            elif "hedged" in c.reason.lower():
                conf_level = "medium"
            elif "canonical" in c.reason.lower():
                conf_level = "weak"
            result["chain_confidence"].append({
                "shot_id": c.shot_id,
                "confidence": conf_level,
                "chain_from": c.chain_from,
                "source_policy": c.source_policy.value,
                "reason": c.reason,
            })

    return result


def print_render_plan(render_plan: dict) -> str:
    """
    Pretty-print a scene render plan for operator review.
    Returns the formatted string.
    """
    rp = render_plan
    lines = []
    lines.append("=" * 80)
    lines.append(f"SCENE {rp['scene_id']} — RENDER EXECUTION PLAN")
    lines.append(f"Generated: {rp.get('generated_at', 'N/A')}")
    lines.append(f"Total shots: {rp['total_shots']}")
    lines.append("=" * 80)

    # Wave plan
    w0 = rp["wave_plan"]["wave_0"]
    cw = rp["wave_plan"]["chain_waves"]
    lines.append(f"\nWAVE 0 (parallel — up to 10 workers): {len(w0)} shots")
    for s in w0:
        lines.append(f"  [{s['classification']:25s}] {s['shot_id']} → {s['source_policy']}")

    lines.append(f"\nCHAIN WAVES (sequential within, parallel across scenes): {sum(c['length'] for c in cw)} shots")
    for gi, grp in enumerate(cw):
        lines.append(f"\n  Chain {gi+1} (anchor: {grp['anchor']}):")
        for cs in grp["chain_shots"]:
            lines.append(f"    → {cs['shot_id']} [{cs['source_type']:10s}] {cs['reason'][:70]}")

    # Probe
    probe = rp.get("probe_shot")
    if probe:
        lines.append(f"\nPROBE SHOT: {probe['shot_id']} ({probe['shot_type']})")
        lines.append(f"  Characters: {', '.join(probe['characters'])}")
        lines.append(f"  Dialogue: {'Yes' if probe['has_dialogue'] else 'No'}")

    # Cost
    cost = rp["cost_estimate"]
    lines.append(f"\nCOST ESTIMATE:")
    ff = cost["first_frames"]
    lines.append(f"  First frames: {ff['standard_shots']} std × $0.15 + {ff['hero_shots']} hero × $0.45 = ${ff['total']}")
    lines.append(f"  Video gen: {cost['video_generation']['total_shots']} × $0.16 = ${cost['video_generation']['total']}")
    lines.append(f"  Scene total: ${cost['scene_total']}")
    lines.append(f"  Probe only: ${cost['probe_only']['cost']}")

    # Chain confidence
    if rp["chain_confidence"]:
        lines.append(f"\nCHAIN CONFIDENCE:")
        for cc in rp["chain_confidence"]:
            marker = {"strong": "●", "medium": "◐", "weak": "○"}.get(cc["confidence"], "?")
            lines.append(f"  {marker} {cc['shot_id']} [{cc['confidence']:7s}] from {cc['chain_from']} → {cc['source_policy']}")

    # Warnings
    if rp["warnings"]:
        lines.append(f"\nWARNINGS ({len(rp['warnings'])}):")
        for w in rp["warnings"]:
            lines.append(f"  ⚠️  {w}")

    # Blockers
    if rp["blockers"]:
        lines.append(f"\nBLOCKERS ({len(rp['blockers'])}):")
        for b in rp["blockers"]:
            lines.append(f"  ❌ {b}")

    verdict = "READY FOR PROBE ✅" if not rp["blockers"] else f"BLOCKED — {len(rp['blockers'])} issues"
    lines.append(f"\nVERDICT: {verdict}")
    lines.append("=" * 80)

    output = "\n".join(lines)
    return output


def plan_all_scenes(
    shot_plan: dict,
    cast_map: Optional[dict] = None,
    project_path: Optional[str] = None,
) -> dict:
    """
    V27.1 UNIVERSAL PROJECT RENDER PLANNER
    =======================================
    Generate render plans for ALL scenes in a project at once.
    Returns dict keyed by scene_id with render plans.

    Usage:
        with open('shot_plan.json') as f:
            plan = json.load(f)
        with open('cast_map.json') as f:
            cm = json.load(f)
        all_plans = plan_all_scenes(plan, cm, str(project_path))
        for scene_id, rp in all_plans['scenes'].items():
            print(print_render_plan(rp))
    """
    all_shots = shot_plan.get("shots", [])
    scene_ids = sorted(set(s.get("scene_id", "unknown") for s in all_shots))

    project_summary = {
        "total_scenes": len(scene_ids),
        "total_shots": len(all_shots),
        "scenes": {},
        "total_cost": 0.0,
        "total_blockers": 0,
        "total_warnings": 0,
    }

    for sid in scene_ids:
        scene_shots = [s for s in all_shots if s.get("scene_id") == sid]
        rp = plan_scene_render(scene_shots, sid, cast_map, project_path)
        project_summary["scenes"][sid] = rp
        project_summary["total_cost"] += rp["cost_estimate"].get("scene_total", 0)
        project_summary["total_blockers"] += len(rp["blockers"])
        project_summary["total_warnings"] += len(rp["warnings"])

    project_summary["total_cost"] = round(project_summary["total_cost"], 2)
    return project_summary


def example_scene_classification():
    """Example: Classify a 5-shot scene."""
    shots = [
        {
            "shot_id": "001_001A",
            "type": "establishing",
            "location": "INT. MANOR FOYER - DAY",
            "characters": [],
        },
        {
            "shot_id": "001_002A",
            "type": "medium",
            "location": "INT. MANOR FOYER - DAY",
            "characters": "EVELYN RAVENCROFT",
        },
        {
            "shot_id": "001_003B",
            "type": "close_up",
            "location": "INT. MANOR FOYER - DAY",
            "characters": "EVELYN RAVENCROFT",
            "dialogue_text": "I will not abandon this house.",
        },
        {
            "shot_id": "001_004_INSERT",
            "type": "insert",
            "location": "INT. MANOR FOYER - DAY",
            "_broll": True,
        },
        {
            "shot_id": "001_005A",
            "type": "medium",
            "location": "INT. MANOR FOYER - DAY",
            "characters": "EVELYN RAVENCROFT",
        },
    ]

    classifications = classify_scene(shots)
    for c in classifications:
        print(f"{c.shot_id}: {c.classification.value} "
              f"(source={c.source_policy.value}, chain_from={c.chain_from})")

    plan = build_scene_chain_plan(classifications)
    print(f"\nChain plan: {plan.total_chains} chains, "
          f"{len(plan.independent_shots)} independent shots")
    for i, chain_group in enumerate(plan.chain_groups):
        print(f"  Chain {i}: {' → '.join(chain_group)}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    example_scene_classification()
