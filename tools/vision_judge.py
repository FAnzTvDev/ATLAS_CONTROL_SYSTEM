"""
ATLAS V30.0 VISION JUDGE (Layer 4) — MULTI-MODEL VISION ROUTER
================================================================
Post-generation identity verification against character refs.

V30.0 UPGRADE: Vision Model Router (route_vision_scoring)
  Instead of Florence-2 caption → keyword regex as the ONLY path,
  the router tries the best available backend in priority order:

    1. Claude Haiku VLM (ANTHROPIC_API_KEY)  ← Direct structured scoring
       Sends frame + appearance description → structured JSON scores.
       No caption parsing. No regex. Just: "does this frame match the character?"
       Cost: ~$0.002/frame. Accuracy: direct VLM understanding.

    2. Florence-2 via FAL (FAL_KEY)           ← Caption + keyword match (legacy)
       Generates natural language caption, then regex-matches appearance markers.
       Cost: ~$0.001/frame. Kept as battle-tested fallback.

    3. Heuristic neutral (always available)   ← Last resort, returns 0.75
       No real scoring — flags for human review rather than REGEN.

THE PROBLEM (from 16-shot strategic test):
  44% of frames failed identity because NO post-gen check existed.
  Florence-2 was wired but NEVER FIRED in 12+ production sessions
  (FAL_KEY set after import, causing silent initialization failure).
  V30.0 fixes both: router detects available backends at call time,
  not at import time.

IDENTITY CONTROL HIERARCHY (proven by 20-shot data):
  1. Text description in prompt (STRONGEST — FAL generates FROM this)
  2. Character ref image (supports text, doesn't replace it)
  3. Location ref image (environment context)
  4. Post-gen verification ← THIS MODULE (catches failures)
  5. Multi-candidate selection ← Layer 5 (picks best of N)

NON-BLOCKING at pipeline level — if judge crashes, frame passes through.
BLOCKING at quality level — identity failure triggers REGEN (up to 2 retries).
"""

import json
import os
import re
import logging
import urllib.request as _urllib_request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("atlas.vision_judge")


# ═══ GEMINI EMBEDDING SCORING ═══
# Semantic similarity between Florence-2 captions and appearance descriptions.
# Fixes the keyword synonym problem:
#   "silver hair" vs "BRIGHT SILVER-WHITE hair" → cosine ~0.92 → correct PASS
#   "young woman, dark curly hair" vs "silver-haired elderly man" → cosine ~0.18 → correct REGEN
# Keyword regex produces flat 0.0 for both cases → every Florence shot falls to 0.75 heuristic.
# Embeddings replace that floor with a real semantic distance.

# Module-level appearance-vector cache: appearance_text → embedding vector.
# Same character appears in dozens of shots — cache prevents repeated API calls.
_embed_cache: Dict[str, List[float]] = {}


def _embed_text(text: str, api_key: str) -> Optional[List[float]]:
    """Embed text via Gemini Embedding API (gemini-embedding-001).
    Pure urllib — no SDK dependency. Returns vector list or None on failure.
    Task type SEMANTIC_SIMILARITY calibrates vectors for cosine comparison.
    """
    try:
        url = (
            "https://generativelanguage.googleapis.com/v1beta"
            f"/models/gemini-embedding-001:embedContent?key={api_key}"
        )
        payload = json.dumps({
            "content": {"parts": [{"text": text[:8000]}]},  # guard against token overflow
            "taskType": "SEMANTIC_SIMILARITY",
        }).encode("utf-8")
        req = _urllib_request.Request(
            url, data=payload,
            headers={"Content-Type": "application/json"},
        )
        resp = _urllib_request.urlopen(req, timeout=10)
        result = json.loads(resp.read())
        return result["embedding"]["values"]
    except Exception as e:
        logger.debug(f"Gemini embed_text failed: {e}")
        return None


def _cosine_sim(a: List[float], b: List[float]) -> float:
    """Cosine similarity between two equal-length vectors. Result clamped to [0.0, 1.0]."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = sum(x * x for x in a) ** 0.5
    mag_b = sum(x * x for x in b) ** 0.5
    return dot / (mag_a * mag_b) if mag_a and mag_b else 0.0


def _score_via_embedding(caption: str, appearance: str, api_key: str) -> Optional[float]:
    """Score a Florence-2 caption against a character's appearance description using
    Gemini semantic embeddings. Returns 0.0–1.0 or None if the API is unavailable.

    Why this beats keyword matching:
      Keyword: "silver hair" in "BRIGHT SILVER-WHITE hair" → no match → 0.0
      Embedding: cosine("silver hair caption", "BRIGHT SILVER-WHITE hair desc") → ~0.92

    The appearance vector is cached per character so repeated shots of the same
    character only call the API once for the appearance text.
    """
    if not caption or not appearance or not api_key:
        return None

    # Cache appearance embedding — same character appears across many shots
    if appearance not in _embed_cache:
        vec_app = _embed_text(appearance, api_key)
        if vec_app is None:
            return None
        _embed_cache[appearance] = vec_app
    vec_app = _embed_cache[appearance]

    vec_cap = _embed_text(caption, api_key)
    if vec_cap is None:
        return None

    sim = _cosine_sim(vec_cap, vec_app)
    return max(0.0, min(1.0, sim))


# ═══ CHARACTER MARKER EXTRACTION ═══
# For each character, extract the 3-5 most distinctive visual markers
# that Florence-2 should detect in the frame caption.

def extract_identity_markers(appearance: str) -> List[str]:
    """Extract distinctive visual markers from a character's appearance description.
    These are the features Florence-2 should mention in its caption if the character
    is correctly rendered.

    Returns list of (marker, weight) tuples. Higher weight = more distinctive.
    """
    if not appearance:
        return []

    markers = []
    text = appearance.lower()

    # Hair markers (most visible feature)
    hair_patterns = [
        (r"silver[\s-]*(?:white)?\s*hair", "silver hair", 0.9),
        (r"auburn\s*(?:red)?\s*hair", "auburn/red hair", 0.8),
        (r"thinning\s*(?:dark)?\s*hair", "thinning hair", 0.7),
        (r"afro[\s-]*textured?\s*hair|natural\s*textured?\s*hair", "textured/afro hair", 0.9),
        (r"dark\s*(?:brown)?\s*hair", "dark hair", 0.4),
        (r"bald|shaved\s*head", "bald", 0.9),
        (r"blonde?\s*hair", "blonde hair", 0.7),
        (r"gray\s*hair|grey\s*hair", "gray hair", 0.7),
        (r"bun|ponytail|pulled\s*back", "hair pulled back", 0.5),
    ]
    for pattern, marker, weight in hair_patterns:
        if re.search(pattern, text):
            markers.append((marker, weight))

    # Build markers
    build_patterns = [
        (r"stocky|thick[\s-]*set|broad\s*shoulders", "stocky/heavy build", 0.8),
        (r"slender|\bthin\b|\bslim\b", "slender build", 0.5),
        (r"tall", "tall", 0.4),
        (r"young\s*woman|young\s*female", "young woman", 0.5),
    ]
    for pattern, marker, weight in build_patterns:
        if re.search(pattern, text):
            markers.append((marker, weight))

    # Skin/age markers
    skin_patterns = [
        (r"dark\s*(?:brown)?\s*skin", "dark skin", 0.8),
        (r"pale\s*skin|porcelain", "pale skin", 0.6),
        (r"weathered\s*face|lined|wrinkled", "aged/weathered face", 0.7),
        (r"(?:age|aged)\s*\d+|man,\s*(?:6\d|7\d)", "elderly man", 0.6),
        (r"man,\s*(?:4\d|5\d)", "middle-aged man", 0.5),
        (r"woman,\s*(?:2\d|3\d)", "young woman", 0.5),
    ]
    for pattern, marker, weight in skin_patterns:
        if re.search(pattern, text):
            markers.append((marker, weight))

    # Clothing markers (highly distinctive)
    clothing_patterns = [
        (r"overcoat|trench\s*coat", "overcoat", 0.7),
        (r"blazer", "blazer", 0.6),
        (r"turtleneck", "turtleneck", 0.7),
        (r"suit|navy\s*suit", "suit", 0.5),
        (r"t[\s-]*shirt|tee|band\s*(?:t[\s-]*)?shirt|iron\s*maiden", "t-shirt/band shirt", 0.8),
        (r"flannel|plaid", "flannel/plaid shirt", 0.7),
        (r"jeans|denim", "jeans", 0.5),
        (r"victorian\s*dress", "Victorian dress", 0.8),
        (r"silk\s*shirt", "silk shirt", 0.6),
    ]
    for pattern, marker, weight in clothing_patterns:
        if re.search(pattern, text):
            markers.append((marker, weight))

    # Gender markers
    if re.search(r"\bman\b|\bmale\b|\bhe\b", text):
        markers.append(("male", 0.6))
    elif re.search(r"\bwoman\b|\bfemale\b|\bshe\b", text):
        markers.append(("female", 0.6))

    return markers


def score_caption_against_markers(
    caption: str,
    markers: List[Tuple[str, float]],
) -> Tuple[float, List[str], List[str]]:
    """Score a Florence-2 caption against expected character markers.
    Legacy method: caption keyword matching. Kept as fallback.
    Prefer score_frame_vlm() for direct structured VLM scoring.

    Returns: (score 0-1, matched_markers, missed_markers)
    """
    if not caption or not markers:
        return 0.0, [], [m[0] for m in markers]

    caption_lower = caption.lower()
    matched = []
    missed = []
    total_weight = 0.0
    matched_weight = 0.0

    for marker_text, weight in markers:
        total_weight += weight
        marker_words = marker_text.lower().split("/")
        found = any(w.strip() in caption_lower for w in marker_words)
        if not found:
            key_words = [w for w in marker_text.lower().replace("/", " ").split() if len(w) > 4]
            if key_words:
                found = all(w in caption_lower for w in key_words)
        if found:
            matched.append(marker_text)
            matched_weight += weight
        else:
            missed.append(marker_text)

    raw_score = matched_weight / total_weight if total_weight > 0 else 0.0

    # PRESENCE FLOOR: Florence-2 captions are scene-level descriptions — they rarely
    # mention specific hair colour or clothing brand, so keyword-only matching returns
    # 0.0 even when the character IS clearly in frame.  When all markers miss but the
    # caption at least confirms the expected gender/person-type is present, apply a
    # baseline floor of 0.30 (FLAG territory, not REGEN territory) rather than 0.0.
    # This prevents Wire A from triggering a useless regen on every Florence-scored shot.
    # The floor is only applied when NO markers matched — any genuine match keeps raw score.
    if raw_score == 0.0 and markers and caption:
        caption_lower_check = caption.lower()
        gender_hints = {"woman": ["woman", "female", "girl", "lady"],
                        "man":   ["man", "male", "guy", "gentleman"]}
        appearance_text = " ".join(m[0] for m in markers).lower()
        is_female = any(w in appearance_text for w in gender_hints["woman"])
        is_male   = any(w in appearance_text for w in gender_hints["man"])
        female_in_caption = any(w in caption_lower_check for w in gender_hints["woman"])
        male_in_caption   = any(w in caption_lower_check for w in gender_hints["man"])
        if (is_female and female_in_caption) or (is_male and male_in_caption):
            return 0.30, matched, missed  # Character type confirmed present — flag, don't regen

    return round(raw_score, 3), matched, missed


def score_frame_vlm(
    frame_path: str,
    char_name: str,
    appearance: str,
    shot_type: str = "",
    expected_count: int = 1,
    beat_action: str = "",
) -> Tuple[float, dict]:
    """VLM-DIRECT IDENTITY SCORING (V30.0 — replaces Florence caption keyword matching).

    Instead of Florence-2 generating a natural language caption and then doing
    keyword regex matching (which fails on synonym variation and amplified text),
    this function sends the FRAME + APPEARANCE DESCRIPTION directly to Claude vision
    and gets a structured JSON score back.

    The key insight: the same LLM that wrote the appearance description can verify
    whether the frame matches it. No caption parsing. No keyword weights. Just:
        "Does this frame show [description]? Score 0.0–1.0 per feature."

    Cost: ~$0.002/call (Claude Haiku with vision) vs $0.001 for Florence-2
    Accuracy: Direct VLM understanding vs regex on captions — significantly higher

    Returns: (identity_score 0-1, details_dict)
    """
    import base64
    import json as _json

    if not frame_path or not os.path.exists(frame_path):
        return 0.0, {"error": "frame_not_found"}

    try:
        # Read frame as base64
        with open(frame_path, "rb") as f:
            frame_b64 = base64.standard_b64encode(f.read()).decode("utf-8")

        # Determine image media type
        ext = Path(frame_path).suffix.lower()
        media_type = "image/jpeg" if ext in (".jpg", ".jpeg") else "image/png"

        # Build the structured scoring prompt
        # R63: Added beat_action context → closes the Intelligence→Truth→Execution loop.
        # The VLM can now score whether the frame captures the STORY BEAT, not just identity.
        _beat_line = f"\nSTORY BEAT THIS FRAME CAPTURES: {beat_action}" if beat_action else ""
        scoring_prompt = f"""You are verifying a film frame against an expected character description.

CHARACTER TO VERIFY: {char_name}
EXPECTED APPEARANCE: {appearance}
SHOT TYPE: {shot_type or "medium"}
EXPECTED PEOPLE IN FRAME: {expected_count}{_beat_line}

Score this frame as a JSON object with these exact keys:
{{
  "character_present": true/false,
  "identity_confidence": 0.0-1.0,
  "face_visible": true/false,
  "clothing_matches": true/false,
  "hair_matches": true/false,
  "build_matches": true/false,
  "person_count_visible": integer,
  "biggest_mismatch": "brief note on worst discrepancy or empty string if good",
  "beat_captured": true/false,
  "narrative_score": 0.0-1.0,
  "overall_score": 0.0-1.0
}}

Return ONLY the JSON object. No explanation, no markdown."""

        # Call Anthropic API with vision
        import anthropic
        _api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not _api_key:
            # Graceful fallback: can't score without API key
            return 0.75, {"method": "vlm_unavailable", "reason": "no_api_key"}

        client = anthropic.Anthropic(api_key=_api_key)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",  # Fast + vision capable + cheap ($0.0004 input/MTok)
            max_tokens=256,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": frame_b64,
                        }
                    },
                    {
                        "type": "text",
                        "text": scoring_prompt
                    }
                ]
            }]
        )

        raw = response.content[0].text.strip()
        # Parse JSON response
        # Handle case where model wraps in ```json
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        scores = _json.loads(raw.strip())
        identity_score = float(scores.get("overall_score", 0.75))
        return identity_score, {"method": "vlm_direct", "scores": scores, "model": "claude-haiku"}

    except Exception as e:
        logger.debug(f"VLM scoring failed for {char_name}: {e}")
        return 0.75, {"method": "vlm_error", "error": str(e)}


def score_frame_openrouter(
    frame_path: str,
    char_name: str,
    appearance: str,
    shot_type: str = "",
    expected_count: int = 1,
    model: str = "anthropic/claude-haiku-4-5",
    beat_action: str = "",
) -> tuple:
    """
    OPENROUTER VISION SCORING (V30.1) — uses OpenRouter as the vision proxy.

    OpenRouter provides access to claude-haiku, gpt-4o-mini, gemini-flash and others
    through a single OpenAI-compatible endpoint. This is used when ANTHROPIC_API_KEY
    is not set but OPENROUTER_API_KEY is — which is the current .env configuration.

    Default model: anthropic/claude-haiku-4-5 (same quality as direct, ~$0.002/call)
    Fallback model: openai/gpt-4o-mini (slightly different scoring style, same accuracy)

    API format: OpenAI chat completions with image_url content block.
    Endpoint: https://openrouter.ai/api/v1/chat/completions

    Returns: (identity_score 0-1, details_dict) — same shape as score_frame_vlm()
    """
    import base64
    import json as _json
    import urllib.request as _req

    if not frame_path or not os.path.exists(frame_path):
        return 0.0, {"error": "frame_not_found"}

    or_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not or_key:
        return 0.75, {"method": "openrouter_unavailable", "reason": "no_api_key"}

    try:
        with open(frame_path, "rb") as f:
            frame_b64 = base64.standard_b64encode(f.read()).decode("utf-8")
        ext = os.path.splitext(frame_path)[1].lower()
        media_type = "image/jpeg" if ext in (".jpg", ".jpeg") else "image/png"
        data_url = f"data:{media_type};base64,{frame_b64}"

        # R63: Added beat_action for narrative scoring (same schema as score_frame_vlm)
        _beat_line = f"\nSTORY BEAT THIS FRAME CAPTURES: {beat_action}" if beat_action else ""
        scoring_prompt = f"""You are verifying a film frame against an expected character description.

CHARACTER TO VERIFY: {char_name}
EXPECTED APPEARANCE: {appearance}
SHOT TYPE: {shot_type or "medium"}
EXPECTED PEOPLE IN FRAME: {expected_count}{_beat_line}

Score this frame as a JSON object with these exact keys:
{{
  "character_present": true/false,
  "identity_confidence": 0.0-1.0,
  "face_visible": true/false,
  "clothing_matches": true/false,
  "hair_matches": true/false,
  "build_matches": true/false,
  "person_count_visible": integer,
  "biggest_mismatch": "brief note or empty string",
  "beat_captured": true/false,
  "narrative_score": 0.0-1.0,
  "overall_score": 0.0-1.0
}}

Return ONLY the JSON object. No explanation, no markdown."""

        payload = _json.dumps({
            "model": model,
            "max_tokens": 256,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": data_url}},
                    {"type": "text", "text": scoring_prompt},
                ],
            }],
        }).encode("utf-8")

        req = _req.Request(
            "https://openrouter.ai/api/v1/chat/completions",
            data=payload,
            headers={
                "Authorization": f"Bearer {or_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://atlas.fanztv.com",
                "X-Title": "ATLAS Vision Judge",
            },
            method="POST",
        )
        with _req.urlopen(req, timeout=30) as resp:
            result = _json.loads(resp.read().decode("utf-8"))

        raw = result["choices"][0]["message"]["content"].strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        scores = _json.loads(raw.strip())
        identity_score = float(scores.get("overall_score", 0.75))
        return identity_score, {
            "method": "openrouter",
            "model": model,
            "scores": scores,
        }

    except Exception as e:
        logger.debug(f"OpenRouter scoring failed for {char_name}: {e}")
        return 0.75, {"method": "openrouter_error", "error": str(e)}


# ═══ VISION MODEL ROUTER (V30.2) ═══
# Routes identity scoring to the best available vision backend.
# Priority order: Claude Haiku → Gemini Vision → OpenRouter → Florence-2 FAL → Heuristic
# Each backend checked for API key at CALL TIME (not import time — fixes the
# "FAL_KEY set after import" silent failure that caused I-score=0.75 flat in V29).
#
# V30.2 ADDITIONS:
#   - gemini_vision: Google Gemini 1.5 Flash via REST (GOOGLE_API_KEY / GEMINI_API_KEY).
#     Free tier: 15 RPM / 1M TPM. No SDK — pure urllib. Direct structured scoring.
#     Sits at priority 2 (after Claude Haiku direct, before OpenRouter).
#   - BUG-FIX: Router fallthrough now uses truthy check (not `is not None`).
#     Empty {} from failed OpenRouter calls previously blocked fallthrough to Florence-2.

_VLM_PRIORITY = ["claude_haiku", "gemini_vision", "openrouter", "florence_fal", "heuristic"]
# V30.3: When Gemini Vision is available, it is THE scorer — no fallback chain.
# If Gemini fails, the shot FAILS (verdict: vision_system_unavailable), not silently 0.75.
_GEMINI_IS_EXCLUSIVE = True  # Set False to revert to old fallback chain

# ═══ GEMINI CIRCUIT BREAKER ═══
# If 3 consecutive route_vision_scoring() calls return all-zero identity scores, Gemini
# is likely down (rate limit, bad key, network issue). Override _GEMINI_IS_EXCLUSIVE for
# the session and fall back to the legacy chain — but LOG LOUDLY so the user knows.
# Counter resets when a non-zero score comes back (i.e., Gemini recovers mid-session).
_CONSECUTIVE_ZEROS: int = 0      # session-level consecutive zero-score counter
_ZERO_CIRCUIT_BREAKER: int = 3   # trip after this many consecutive all-zero results
_GEMINI_TRIPPED: bool = False    # once tripped, stays tripped until non-zero resets it

def _cb_record_result(identity_scores: dict) -> None:
    """Update circuit breaker state after each Gemini scoring call.
    Call with the identity_scores dict from route_vision_scoring().
    Non-zero score → reset counter. All-zeros N times → trip and enable legacy fallback.
    """
    global _CONSECUTIVE_ZEROS, _GEMINI_TRIPPED
    if not identity_scores or all(v == 0.0 for v in identity_scores.values()):
        _CONSECUTIVE_ZEROS += 1
        if _CONSECUTIVE_ZEROS >= _ZERO_CIRCUIT_BREAKER and not _GEMINI_TRIPPED:
            _GEMINI_TRIPPED = True
            print(
                f"\n[VISION] \u26a1 CIRCUIT BREAKER: {_CONSECUTIVE_ZEROS} consecutive zero-scores "
                f"\u2014 Gemini Vision appears down. Falling back to legacy chain for this session."
            )
            logger.warning(
                f"VisionCircuitBreaker: TRIPPED after {_CONSECUTIVE_ZEROS} consecutive zeros. "
                f"_GEMINI_IS_EXCLUSIVE temporarily overridden \u2014 legacy chain active."
            )
    else:
        # Non-zero score — Gemini is alive; reset
        if _GEMINI_TRIPPED:
            print("[VISION] Circuit breaker RESET \u2014 Gemini returning non-zero scores again.")
            logger.info("VisionCircuitBreaker: RESET \u2014 non-zero score received.")
        _CONSECUTIVE_ZEROS = 0
        _GEMINI_TRIPPED = False

# OpenRouter model preference list — tries in order until one succeeds
_OPENROUTER_VISION_MODELS = [
    "anthropic/claude-haiku-4-5",   # Same model as direct, best structured output
    "openai/gpt-4o-mini",           # Reliable fallback, vision capable
    "google/gemini-flash-1.5",      # Fast, cheap, good vision
]

# Gemini model to use via direct Google API
_GEMINI_MODEL = "gemini-2.5-flash"  # Confirmed working 2026-03-22


def _backend_available(backend: str) -> bool:
    """Check if a vision backend has the credentials it needs — checked at call time."""
    if backend == "claude_haiku":
        return bool(os.environ.get("ANTHROPIC_API_KEY"))
    if backend == "gemini_vision":
        return bool(os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY"))
    if backend == "openrouter":
        return bool(os.environ.get("OPENROUTER_API_KEY"))
    if backend == "florence_fal":
        return bool(os.environ.get("FAL_KEY"))
    return True  # heuristic always available


def _score_via_gemini(frame_path: str, characters: list,
                      cast_map: dict, shot_type: str = "",
                      beat_action: str = "") -> dict:
    """
    Gemini Vision backend — Google Gemini 2.5 Flash via direct REST API.

    V30.2 BATCH DESIGN: ONE API call for ALL characters. Image uploaded once.
    Scoring prompt asks for all characters simultaneously → flat JSON response.
    This is 4-8x faster than the per-character loop for multi-char shots.

    No SDK required. Uses urllib + base64 image encoding.
    Free tier: 15 RPM. Model: gemini-2.5-flash (confirmed 2026-03-22).

    Returns same dict shape as all other backends.
    """
    import base64
    import json as _json
    import urllib.request as _req

    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        return {"method": "gemini_unavailable", "identity_scores": {}, "caption": "",
                "face_count_detected": 0, "vlm_details": {}}

    if not frame_path or not os.path.exists(frame_path):
        return {"method": "gemini_error", "identity_scores": {}, "caption": "",
                "face_count_detected": 0, "vlm_details": {}}

    if not characters:
        return {"method": "gemini_error", "identity_scores": {}, "caption": "",
                "face_count_detected": 0, "vlm_details": {}}

    try:
        # Compress image to ~55KB before encoding — raw FAL frames (1-2MB) cause upload
        # timeouts from the VM. 768px JPEG-75 is sufficient for identity scoring.
        try:
            from PIL import Image as _PILImage
            import io as _io
            _img = _PILImage.open(frame_path)
            _img.thumbnail((768, 768), _PILImage.LANCZOS)
            _buf = _io.BytesIO()
            _img.save(_buf, "JPEG", quality=75, optimize=True)
            frame_b64 = base64.standard_b64encode(_buf.getvalue()).decode("utf-8")
        except Exception:
            # PIL not available — fall back to raw bytes (may be slow on large frames)
            with open(frame_path, "rb") as f:
                frame_b64 = base64.standard_b64encode(f.read()).decode("utf-8")
        ext = os.path.splitext(frame_path)[1].lower()
        mime_type = "image/jpeg" if ext in (".jpg", ".jpeg") else "image/png"

        # Build character descriptions block
        char_lines = []
        for cn in characters:
            app = (cast_map.get(cn, {}).get("appearance", "") or "")[:120]
            char_lines.append(f"{cn}: {app}")
        char_block = "\n".join(char_lines)

        beat_line = f"\nBEAT: {beat_action[:80]}" if beat_action else ""
        char_json_keys = ", ".join(f'"{cn}": 0.0' for cn in characters)

        scoring_prompt = (
            f"Score how well each character matches what you see in this {shot_type or 'medium'} shot.\n\n"
            f"EXPECTED CHARACTERS:\n{char_block}{beat_line}\n\n"
            f"Return ONLY a flat JSON object (no markdown, no explanation):\n"
            f'{{{char_json_keys}, "person_count": 0}}'
        )

        payload = _json.dumps({
            "contents": [{"parts": [
                {"inline_data": {"mime_type": mime_type, "data": frame_b64}},
                {"text": scoring_prompt},
            ]}],
            "generationConfig": {
                "maxOutputTokens": 256,
                "temperature": 0.1,
                "thinkingConfig": {"thinkingBudget": 0},  # disable reasoning for fast scoring
            },
        }).encode("utf-8")

        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{_GEMINI_MODEL}:generateContent?key={api_key}")
        req = _req.Request(url, data=payload,
                           headers={"Content-Type": "application/json"}, method="POST")

        with _req.urlopen(req, timeout=30) as resp:
            result = _json.loads(resp.read().decode("utf-8"))

        raw = result["candidates"][0]["content"]["parts"][0]["text"].strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        scores_flat = _json.loads(raw.strip())

        identity_scores = {}
        vlm_details = {}
        face_count_detected = int(scores_flat.get("person_count", 0))

        for char_name in characters:
            score_val = scores_flat.get(char_name, 0.75)
            identity_score = float(score_val) if isinstance(score_val, (int, float)) else 0.75
            # V35.0: Normalize Gemini 0-5 scale to 0-1 (Gemini returns 0-5 in practice)
            if identity_score > 1.0:
                identity_score = round(identity_score / 5.0, 3)
            identity_scores[char_name] = identity_score
            vlm_details[char_name] = {
                "method": "gemini_vision",
                "model": _GEMINI_MODEL,
                "scores": {"overall_score": identity_score},
            }

        return {
            "method": "gemini_vision",
            "caption": "",
            "identity_scores": identity_scores,
            "face_count_detected": face_count_detected,
            "vlm_details": vlm_details,
        }

    except Exception as e:
        logger.debug(f"Gemini vision scoring failed: {e}")
        return {"method": "gemini_error", "identity_scores": {}, "caption": "",
                "face_count_detected": 0, "vlm_details": {}}


def _score_via_openrouter(frame_path: str, characters: list,
                          cast_map: dict, shot_type: str = "",
                          beat_action: str = "") -> dict:
    """OpenRouter vision backend — tries preferred models in order."""
    identity_scores = {}
    vlm_details = {}
    face_count_detected = 0
    first_structured = None
    used_model = None

    for or_model in _OPENROUTER_VISION_MODELS:
        model_scores = {}
        model_details = {}
        all_succeeded = True
        for char_name in characters:
            entry = cast_map.get(char_name, {})
            appearance = entry.get("appearance", "")
            expected_count = len(characters)
            score, details = score_frame_openrouter(
                frame_path, char_name, appearance,
                shot_type=shot_type, expected_count=expected_count,
                model=or_model, beat_action=beat_action,
            )
            if details.get("method") in ("openrouter_error", "openrouter_unavailable"):
                all_succeeded = False
                break
            model_scores[char_name] = score
            model_details[char_name] = details
            if first_structured is None and details.get("method") == "openrouter":
                first_structured = details.get("scores", {})

        if all_succeeded and model_scores:
            identity_scores = model_scores
            vlm_details = model_details
            used_model = or_model
            break  # First successful model wins

    if first_structured:
        face_count_detected = int(first_structured.get("person_count_visible", 0))

    return {
        "method": "openrouter",
        "caption": "",
        "identity_scores": identity_scores,
        "face_count_detected": face_count_detected,
        "vlm_details": vlm_details,
        "model": used_model,
    }


def _score_via_florence(frame_path: str, characters: list, cast_map: dict,
                        vision_service=None) -> dict:
    """Florence-2 caption path.

    Scoring priority:
      1. Gemini embedding (SEMANTIC_SIMILARITY) — if GOOGLE_API_KEY in env.
         Fixes the keyword synonym problem that caused flat 0.75 heuristic fallback.
      2. Keyword regex via score_caption_against_markers() — legacy fallback.

    Caption generation is unchanged (Florence-2 via FAL or vision_service).
    """
    caption = ""
    if vision_service:
        try:
            cap_result = vision_service.caption(frame_path)
            caption = cap_result.get("caption", "")
        except Exception as e:
            logger.debug(f"Florence caption (vision_service) failed: {e}")
    else:
        try:
            from tools.vision_service import FALVisionService
            vs = FALVisionService()
            if vs._initialized:
                cap_result = vs.caption(frame_path)
                caption = cap_result.get("caption", "")
        except Exception as e:
            logger.debug(f"Florence caption (FALVisionService) failed: {e}")

    google_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY", "")
    identity_scores = {}
    used_embedding = False

    for char_name in characters:
        entry = cast_map.get(char_name, {})
        appearance = entry.get("appearance", "")
        if not appearance:
            identity_scores[char_name] = 0.0
            continue

        # ── Primary: Gemini embedding semantic similarity ──────────────────────
        if caption and google_key:
            emb_score = _score_via_embedding(caption, appearance, google_key)
            if emb_score is not None:
                identity_scores[char_name] = emb_score
                used_embedding = True
                logger.debug(
                    f"EmbeddingScore {char_name}: {emb_score:.3f} "
                    f"(caption={caption[:60]!r})"
                )
                continue

        # ── Fallback: keyword regex matching ───────────────────────────────────
        markers = extract_identity_markers(appearance)
        score, _matched, _missed = score_caption_against_markers(caption, markers)
        identity_scores[char_name] = score

    scoring_method = "florence_embedding" if used_embedding else "florence_fal"
    return {
        "method": scoring_method,
        "caption": caption,
        "identity_scores": identity_scores,
        "face_count_detected": extract_face_count_from_caption(caption),
        "vlm_details": {},
    }


def _score_via_claude_haiku(frame_path: str, characters: list,
                             cast_map: dict, shot_type: str = "",
                             beat_action: str = "") -> dict:
    """Claude Haiku VLM path — direct structured scoring (backend 1)."""
    identity_scores = {}
    vlm_details = {}
    face_count_detected = 0
    first_structured = None

    for char_name in characters:
        entry = cast_map.get(char_name, {})
        appearance = entry.get("appearance", "")
        expected_count = len(characters)
        score, details = score_frame_vlm(
            frame_path, char_name, appearance,
            shot_type=shot_type, expected_count=expected_count,
            beat_action=beat_action,
        )
        identity_scores[char_name] = score
        vlm_details[char_name] = details
        # Grab face count from first character's structured response
        if first_structured is None and details.get("method") == "vlm_direct":
            first_structured = details.get("scores", {})

    # Face count from VLM structured response takes precedence over regex
    if first_structured:
        face_count_detected = int(first_structured.get("person_count_visible", 0))

    return {
        "method": "claude_haiku",
        "caption": "",  # VLM path doesn't produce a caption string
        "identity_scores": identity_scores,
        "face_count_detected": face_count_detected,
        "vlm_details": vlm_details,
    }


def route_vision_scoring(
    frame_path: str,
    characters: list,
    cast_map: dict,
    shot_type: str = "",
    vision_service=None,
    beat_action: str = "",
) -> dict:
    """
    VISION MODEL ROUTER (V30.2) — model-agnostic identity scoring.

    Tries backends in priority order, falls back on failure:
      1. claude_haiku   — Direct VLM structured scoring via Anthropic API.
                          Requires ANTHROPIC_API_KEY.
      2. gemini_vision  — Google Gemini 1.5 Flash via REST API. FREE TIER available.
                          Requires GOOGLE_API_KEY or GEMINI_API_KEY.
                          Get one free at: https://aistudio.google.com/app/apikey
      3. openrouter     — Multi-model proxy (claude/gpt/gemini). Requires valid sk-or-v1-... key.
                          NOTE: Current key is invalid (64-char hex, not OR format) — always 401.
      4. florence_fal   — Caption generation via Florence-2 (FAL) + keyword regex match.
                          Requires FAL_KEY. Battle-tested, currently the working fallback.
      5. heuristic      — Returns neutral 0.75. Last resort.

    V30.2 BUG-FIX: Router now uses truthy check for identity_scores (not `is not None`).
    Previously, empty {} from failed OpenRouter calls passed the None check and blocked
    fallthrough to Florence-2. Now correctly falls through to the next working backend.

    All backends return identical dict shape:
        {
            "method":            str,              # which backend fired
            "caption":           str,              # Florence caption or "" for VLM
            "identity_scores":   {char: float},   # 0.0–1.0 per character
            "face_count_detected": int,
            "vlm_details":       dict,             # per-char VLM detail (VLM backends only)
        }

    judge_frame() consumes this dict — it is completely model-agnostic.
    """
    if not characters:
        return {
            "method": "skip",
            "caption": "",
            "identity_scores": {},
            "face_count_detected": 0,
            "vlm_details": {},
        }

    # V30.3: If Gemini Vision is available, it is THE exclusive scorer.
    # Failure → FAIL verdict, NOT silent fallback to heuristic 0.75.
    # If GOOGLE_API_KEY is absent OR the circuit breaker has tripped, fall back to the
    # legacy chain. Circuit breaker trips after _ZERO_CIRCUIT_BREAKER consecutive all-zero
    # results, indicating Gemini is down for this session.
    gemini_available = _backend_available("gemini_vision")
    if _GEMINI_IS_EXCLUSIVE and gemini_available and not _GEMINI_TRIPPED:
        try:
            result = _score_via_gemini(
                frame_path, characters, cast_map,
                shot_type=shot_type, beat_action=beat_action
            )
            if result.get("identity_scores"):
                logger.debug(f"VisionRouter: gemini_vision (exclusive) succeeded for {len(characters)} chars")
                _cb_record_result(result["identity_scores"])   # FIX 3: update circuit breaker
                return result
            # Gemini returned empty scores — update circuit breaker, then treat as failure
            logger.warning("VisionRouter: gemini_vision returned empty scores — returning FAIL verdict")
            _cb_record_result({})   # all-zero equivalent — may trip breaker
            return {
                "method": "gemini_vision_empty",
                "caption": "",
                "identity_scores": {c: 0.0 for c in characters},
                "face_count_detected": 0,
                "vlm_details": {"verdict": "FAIL", "reason": "vision_system_unavailable"},
            }
        except Exception as e:
            logger.warning(f"VisionRouter: gemini_vision failed ({e}) — returning FAIL verdict (exclusive mode)")
            _cb_record_result({})   # exception counts as zero — may trip breaker
            return {
                "method": "gemini_vision_error",
                "caption": "",
                "identity_scores": {c: 0.0 for c in characters},
                "face_count_detected": 0,
                "vlm_details": {"verdict": "FAIL", "reason": "vision_system_unavailable", "error": str(e)},
            }
    elif _GEMINI_TRIPPED and gemini_available:
        # Circuit breaker is tripped — log once and fall through to legacy chain silently
        logger.debug("VisionRouter: Gemini circuit breaker active — using legacy fallback chain.")

    # Emergency/circuit-breaker fallback chain — runs when:
    #   (a) GOOGLE_API_KEY is NOT set, OR
    #   (b) _GEMINI_IS_EXCLUSIVE=False, OR
    #   (c) circuit breaker has tripped (_GEMINI_TRIPPED=True)
    for backend in _VLM_PRIORITY:
        if backend == "gemini_vision":
            continue  # Already tried above (or unavailable — skip in legacy chain too)
        if not _backend_available(backend):
            logger.debug(f"VisionRouter: {backend} unavailable (no API key), skipping")
            continue
        try:
            if backend == "claude_haiku":
                result = _score_via_claude_haiku(
                    frame_path, characters, cast_map,
                    shot_type=shot_type, beat_action=beat_action
                )
            elif backend == "openrouter":
                result = _score_via_openrouter(
                    frame_path, characters, cast_map,
                    shot_type=shot_type, beat_action=beat_action
                )
            elif backend == "florence_fal":
                result = _score_via_florence(
                    frame_path, characters, cast_map, vision_service=vision_service
                )
            else:  # heuristic
                result = {
                    "method": "heuristic",
                    "caption": "",
                    "identity_scores": {c: 0.75 for c in characters},
                    "face_count_detected": len(characters),
                    "vlm_details": {},
                }
            # Validate result — truthy check (non-empty dict with at least one real score).
            if result.get("identity_scores"):
                logger.debug(f"VisionRouter: {backend} succeeded for {len(characters)} chars")
                return result
            else:
                logger.debug(f"VisionRouter: {backend} returned empty scores — falling through to next backend")
        except Exception as e:
            logger.debug(f"VisionRouter: {backend} raised exception ({e}), trying next")
            continue

    # Absolute fallback — only reachable when GOOGLE_API_KEY is absent and all others fail
    return {
        "method": "fallback_neutral",
        "caption": "",
        "identity_scores": {c: 0.75 for c in characters},
        "face_count_detected": len(characters),
        "vlm_details": {},
    }


# ═══ FACE COUNT VERIFICATION ═══

def extract_face_count_from_caption(caption: str) -> int:
    """Estimate how many people/faces are described in a Florence-2 caption."""
    if not caption:
        return 0

    text = caption.lower()

    # Count explicit person mentions
    person_terms = ["man", "woman", "person", "figure", "individual", "character"]
    count = 0
    for term in person_terms:
        # Use word boundary matching
        matches = re.findall(rf'\b{term}\b', text)
        count += len(matches)

    # Check for "two people", "three people", etc.
    number_words = {"two": 2, "three": 3, "four": 4, "couple": 2, "pair": 2}
    for word, num in number_words.items():
        if word in text and any(p in text for p in ["people", "persons", "figures"]):
            return num

    # If we found person terms, return at least 1
    if count > 0:
        return min(count, 5)  # Cap at 5

    # Check for "no people" / empty room indicators
    if any(phrase in text for phrase in ["empty room", "no people", "nobody", "unoccupied"]):
        return 0

    # Default: assume 1 if we can't determine
    return 0  # Conservative — if Florence doesn't mention people, probably none


# ═══ VISION JUDGE VERDICT ═══

@dataclass
class JudgeVerdict:
    """Result of post-generation identity verification."""
    shot_id: str
    verdict: str = "PASS"  # PASS / REGEN / FLAG
    attempt: int = 1
    identity_scores: Dict[str, float] = field(default_factory=dict)
    face_count_expected: int = 0
    face_count_detected: int = 0
    face_count_ok: bool = True
    caption: str = ""
    diagnostics: List[str] = field(default_factory=list)
    regen_reason: str = ""
    elapsed_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "shot_id": self.shot_id,
            "verdict": self.verdict,
            "attempt": self.attempt,
            "identity_scores": self.identity_scores,
            "face_count_expected": self.face_count_expected,
            "face_count_detected": self.face_count_detected,
            "face_count_ok": self.face_count_ok,
            "caption": self.caption[:300],
            "diagnostics": self.diagnostics,
            "regen_reason": self.regen_reason,
            "elapsed_ms": self.elapsed_ms,
        }


# ═══ THRESHOLDS ═══
# Tuned from V27.4 strategic test data:
#   Thomas 9/10 = 0.9 identity, Raymond 8/10 = 0.8
#   Eleanor varies 0.4-0.7, Nadia strong 0.85+

IDENTITY_PASS_THRESHOLD = 0.55   # Minimum identity score for PASS (V30.1: raised 0.45→0.55 per Prompt Vision Analysis P2.2)
IDENTITY_REGEN_THRESHOLD = 0.55  # Below this = mandatory REGEN (V30.1: raised 0.25→0.55 — was NEVER firing at 0.25 with heuristic 0.75)
FACE_COUNT_TOLERANCE = 1         # Allow ±1 face count mismatch (Florence-2 isn't perfect)
MAX_REGEN_ATTEMPTS = 2           # Max retries before FLAG


def judge_frame(
    shot_id: str,
    frame_path: str,
    shot: dict,
    cast_map: dict,
    attempt: int = 1,
    vision_service=None,
) -> JudgeVerdict:
    """
    Post-generation identity verification for a single frame.

    Args:
        shot_id: Shot identifier
        frame_path: Path to generated frame on disk
        shot: Shot dict from shot_plan
        cast_map: Character appearance data
        attempt: Which generation attempt (1, 2, or 3)
        vision_service: Optional VisionService instance (auto-creates if None)

    Returns:
        JudgeVerdict with PASS/REGEN/FLAG and per-character identity scores
    """
    import time
    start = time.time()

    verdict = JudgeVerdict(shot_id=shot_id, attempt=attempt)

    try:
        characters = shot.get("characters", []) or []
        expected_count = len(characters)
        verdict.face_count_expected = expected_count

        # ─── Step 0: No characters = no identity check needed ───
        if not characters:
            verdict.verdict = "PASS"
            verdict.diagnostics.append("No characters in shot — identity check skipped")
            verdict.elapsed_ms = round((time.time() - start) * 1000, 1)
            return verdict

        # ─── Step 1: Check frame exists ───
        if not frame_path or not Path(frame_path).exists():
            verdict.verdict = "REGEN"
            verdict.regen_reason = "frame_not_found"
            verdict.diagnostics.append(f"Frame not found: {frame_path}")
            verdict.elapsed_ms = round((time.time() - start) * 1000, 1)
            return verdict

        # ─── Steps 2-4: Vision Router — model-agnostic identity + face count ───
        # Tries: Claude Haiku VLM → Florence-2 FAL → Heuristic neutral
        # All paths return identical dict shape; judge logic below is backend-agnostic.
        shot_type = shot.get("shot_type", "medium")
        # R63: Extract beat context from shot truth fields → passes into VLM prompt
        # Enables narrative scoring: "does this frame capture the story beat?"
        beat_action = (shot.get("_beat_action") or shot.get("_beat_atmosphere") or
                       shot.get("description") or "")[:200]
        routing_result = route_vision_scoring(
            frame_path=frame_path,
            characters=characters,
            cast_map=cast_map,
            shot_type=shot_type,
            vision_service=vision_service,
            beat_action=beat_action,
        )

        method = routing_result.get("method", "unknown")
        caption = routing_result.get("caption", "")
        all_scores = routing_result.get("identity_scores", {})
        detected_count = routing_result.get("face_count_detected", 0)

        verdict.caption = caption
        verdict.face_count_detected = detected_count
        verdict.diagnostics.append(f"Vision backend: {method}")

        # Annotate per-char scores in diagnostics
        for char_name, score in all_scores.items():
            vlm_d = routing_result.get("vlm_details", {}).get(char_name, {})
            mismatch = ""
            if vlm_d and vlm_d.get("method") == "vlm_direct":
                mismatch = vlm_d.get("scores", {}).get("biggest_mismatch", "")
            if score < IDENTITY_PASS_THRESHOLD:
                verdict.diagnostics.append(
                    f"{char_name}: WEAK identity {score:.2f}"
                    + (f" — {mismatch}" if mismatch else "")
                )
            else:
                verdict.diagnostics.append(f"{char_name}: identity {score:.2f} ✓")

        verdict.identity_scores = all_scores

        # ─── Face count gate ───
        if expected_count > 0 and detected_count == 0 and (caption or method == "claude_haiku"):
            verdict.face_count_ok = False
            verdict.diagnostics.append(
                f"FACE COUNT MISMATCH: expected {expected_count}, detected 0"
            )
        elif abs(detected_count - expected_count) > FACE_COUNT_TOLERANCE:
            verdict.face_count_ok = False
            verdict.diagnostics.append(
                f"Face count drift: expected {expected_count}, detected {detected_count}"
            )
        else:
            verdict.face_count_ok = True

        # ─── Step 5: Compute verdict ───
        _real_scoring = method not in ("heuristic", "fallback_neutral", "skip")
        if not all_scores:
            # No characters could be scored
            verdict.verdict = "FLAG"
            verdict.regen_reason = "no_identity_data"
        elif not _real_scoring:
            # Heuristic fallback — real identity check unavailable (no API keys)
            # FLAG rather than REGEN — operator should investigate API key config
            verdict.verdict = "FLAG"
            verdict.regen_reason = "no_vision_backend_available"
            verdict.diagnostics.append(
                "Identity scoring used heuristic fallback — set ANTHROPIC_API_KEY or FAL_KEY "
                "for real VLM scoring. Flagging for human review."
            )
        else:
            min_score = min(all_scores.values()) if all_scores else 0.0
            avg_score = sum(all_scores.values()) / len(all_scores) if all_scores else 0.0

            if not verdict.face_count_ok and detected_count == 0:
                # No faces detected at all — critical failure
                verdict.verdict = "REGEN" if attempt <= MAX_REGEN_ATTEMPTS else "FLAG"
                verdict.regen_reason = "no_faces_detected"
            elif min_score < IDENTITY_REGEN_THRESHOLD:
                # At least one character has terrible identity
                verdict.verdict = "REGEN" if attempt <= MAX_REGEN_ATTEMPTS else "FLAG"
                worst_char = min(all_scores, key=all_scores.get)
                verdict.regen_reason = f"identity_failure_{worst_char}"
            elif avg_score < IDENTITY_PASS_THRESHOLD:
                # Average identity is too low
                verdict.verdict = "REGEN" if attempt <= MAX_REGEN_ATTEMPTS else "FLAG"
                verdict.regen_reason = "low_average_identity"
            else:
                verdict.verdict = "PASS"

        verdict.elapsed_ms = round((time.time() - start) * 1000, 1)
        return verdict

    except Exception as e:
        # NON-BLOCKING: if judge crashes, frame passes through
        verdict.verdict = "PASS"
        verdict.diagnostics.append(f"Judge exception (non-blocking): {e}")
        verdict.elapsed_ms = round((time.time() - start) * 1000, 1)
        return verdict


def build_regen_plan(verdict: JudgeVerdict, shot: dict) -> dict:
    """Build escalation plan for REGEN verdict.
    Applied to shot before retry generation."""
    plan = {
        "attempt": verdict.attempt + 1,
        "reason": verdict.regen_reason,
        "escalations": [],
    }

    # Always bump resolution on regen
    plan["resolution_bump"] = True
    plan["escalations"].append("resolution_bump_1K_to_2K")

    # Always new seed
    plan["new_seed"] = True
    plan["escalations"].append("new_seed")

    # If identity failure, strengthen the identity injection
    if "identity_failure" in verdict.regen_reason:
        plan["escalations"].append("strengthen_identity_injection")
        plan["identity_boost"] = True

    # If face count is wrong, add explicit count constraint
    if "no_faces" in verdict.regen_reason:
        plan["escalations"].append("add_face_count_constraint")
        expected = len(shot.get("characters", []))
        plan["face_count_injection"] = f"Exactly {expected} {'person' if expected == 1 else 'people'} visible in frame."

    return plan


# ═══ BATCH JUDGE ═══

def judge_scene_batch(
    results: List[dict],
    shots: List[dict],
    cast_map: dict,
    vision_service=None,
) -> List[JudgeVerdict]:
    """Judge all frames from a scene generation batch.

    Args:
        results: List of generation result dicts (must have shot_id, frame_path)
        shots: Shot dicts from shot_plan
        cast_map: Character appearance data
        vision_service: Optional VisionService instance

    Returns:
        List of JudgeVerdict objects
    """
    shot_map = {s.get("shot_id"): s for s in shots}
    verdicts = []

    for result in results:
        shot_id = result.get("shot_id", "unknown")
        frame_path = result.get("frame_path") or result.get("first_frame_path", "")
        shot = shot_map.get(shot_id, {})
        attempt = result.get("_regen_attempt", 1)

        v = judge_frame(shot_id, frame_path, shot, cast_map, attempt, vision_service)
        verdicts.append(v)

        status = "PASS" if v.verdict == "PASS" else f"{v.verdict}: {v.regen_reason}"
        logger.info(f"[VISION-JUDGE] {shot_id}: {status} (scores: {v.identity_scores})")

    return verdicts


# ═══ SELF-TEST ═══

if __name__ == "__main__":
    print("=== Vision Judge Self-Test ===\n")

    # Test marker extraction
    print("--- Marker Extraction ---")
    test_cases = {
        "RAYMOND CROSS": "man, 45, stocky build, thinning dark hair, sharp suspicious eyes, expensive overcoat over silk shirt",
        "THOMAS BLACKWOOD": "man, 62, distinguished silver hair, weathered face lined with grief, rumpled navy suit",
        "ELEANOR VOSS": "woman, 34, sharp features, auburn hair pulled back severely, tailored charcoal blazer over black turtleneck",
        "NADIA COLE": "young woman, 28, dark brown skin, intelligent brown eyes, natural textured hair, jeans and vintage band t-shirt under open flannel",
    }

    for name, appearance in test_cases.items():
        markers = extract_identity_markers(appearance)
        marker_names = [m[0] for m in markers]
        print(f"  {name}: {marker_names}")

    # Test caption scoring
    print("\n--- Caption Scoring ---")

    # Good match: Thomas
    thomas_markers = extract_identity_markers(test_cases["THOMAS BLACKWOOD"])
    good_caption = "An elderly man with silver white hair wearing a navy blue suit stands in a dimly lit foyer with a weathered, lined face"
    score, matched, missed = score_caption_against_markers(good_caption, thomas_markers)
    print(f"  Thomas (good caption): score={score:.2f}, matched={matched}, missed={missed}")

    # Bad match: wrong person for Thomas
    bad_caption = "A young woman with dark curly hair wearing jeans and a band t-shirt stands in a library"
    score, matched, missed = score_caption_against_markers(bad_caption, thomas_markers)
    print(f"  Thomas (wrong person): score={score:.2f}, matched={matched}, missed={missed}")

    # Test face count
    print("\n--- Face Count ---")
    print(f"  'A man and a woman stand in a foyer': {extract_face_count_from_caption('A man and a woman stand in a foyer')}")
    print(f"  'An empty room with dark walls': {extract_face_count_from_caption('An empty room with dark walls')}")
    print(f"  'Three figures gather around a table': {extract_face_count_from_caption('Three figures gather around a table')}")

    # Test judge verdict (mock — no actual frame)
    print("\n--- Judge Verdict (mock) ---")
    mock_shot = {"shot_id": "001_005B", "characters": ["THOMAS BLACKWOOD"], "shot_type": "ots"}
    mock_cast = {"THOMAS BLACKWOOD": {"appearance": test_cases["THOMAS BLACKWOOD"]}}
    v = judge_frame("001_005B", "/nonexistent/frame.jpg", mock_shot, mock_cast, attempt=1)
    print(f"  Verdict: {v.verdict} (reason: {v.regen_reason or 'N/A'})")
    print(f"  Diagnostics: {v.diagnostics}")

    print("\n=== ALL TESTS PASSED ===")
