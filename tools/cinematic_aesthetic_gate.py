"""
Cinematic Aesthetic Gate (V27.2)
================================
Vision-based quality gate that scores generated frames on CINEMATIC qualities,
not just identity/location matching. Uses OpenRouter vision models (Claude Sonnet)
to detect the difference between "AI-generated headshot on stock background" and
"frame from a professional film."

This gate catches what ArcFace/DINOv2 CANNOT:
- Depth of field (bokeh vs everything-sharp)
- Lighting integration (character matches room light)
- Composition (rule of thirds vs dead-center)
- Skin/texture realism (pores vs airbrushed)
- Environment embedding (character IN room vs pasted ON)
- Film aesthetic (grain, color grade vs sterile digital)

Runs AFTER first-frame generation, BEFORE video generation.
Non-blocking but ADVISORY with strong operator visibility.

Production evidence: V27.2 Scene 002 shot 002_017B scored high on identity (Nadia Cole
face matched ref) but the frame was obviously AI — centered, flat-lit, no DOF, character
composited onto background. This gate would have caught that.
"""

import os
import json
import base64
import logging
import re
from pathlib import Path
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════
# SCORING DIMENSIONS — what makes a frame CINEMATIC vs AI-GENERIC
# ═══════════════════════════════════════════════════════════════════

CINEMATIC_DIMENSIONS = {
    "depth_of_field": {
        "weight": 0.20,
        "description": "Shallow DOF with bokeh separation between subject and background",
        "ai_fail": "Everything equally sharp, no depth separation",
        "cinema_pass": "Subject sharp, background beautifully blurred with organic bokeh"
    },
    "lighting_integration": {
        "weight": 0.20,
        "description": "Light on character matches light source direction in room",
        "ai_fail": "Character front-lit while room has side/back lighting",
        "cinema_pass": "Same light wraps character and environment, shadows consistent"
    },
    "composition": {
        "weight": 0.15,
        "description": "Rule of thirds, asymmetric framing, intentional negative space",
        "ai_fail": "Subject dead center, symmetrical, passport-photo framing",
        "cinema_pass": "Off-center subject, leading lines, breathing room in frame"
    },
    "skin_texture": {
        "weight": 0.15,
        "description": "Realistic skin with pores, micro-detail, subsurface scattering",
        "ai_fail": "Airbrushed smooth skin, waxy, uncanny valley",
        "cinema_pass": "Visible pores, natural imperfections, skin reacts to light realistically"
    },
    "environment_embedding": {
        "weight": 0.15,
        "description": "Character feels physically present IN the room, not pasted on",
        "ai_fail": "Character looks composited, different lighting/perspective from background",
        "cinema_pass": "Character casts shadows in room, perspective matches, light wraps naturally"
    },
    "film_aesthetic": {
        "weight": 0.15,
        "description": "Film grain, color grading, atmospheric haze, practical light sources",
        "ai_fail": "Sterile digital look, over-saturated, no grain, clinical white balance",
        "cinema_pass": "Visible film grain, moody color grade, atmosphere, warmth from practicals"
    }
}

# ═══════════════════════════════════════════════════════════════════
# THRESHOLDS
# ═══════════════════════════════════════════════════════════════════

THRESHOLDS = {
    "composite_pass": 7.0,      # Weighted average ≥ 7.0 → APPROVED
    "composite_warn": 5.0,      # 5.0-6.9 → NEEDS_IMPROVEMENT (advisory)
    "composite_fail": 5.0,      # < 5.0 → REJECTED (regen recommended)
    "dimension_floor": 3.0,     # Any single dimension < 3 → flag regardless of composite
}

# ═══════════════════════════════════════════════════════════════════
# CINEMATIC PROMPT INJECTION — fixes for low-scoring dimensions
# ═══════════════════════════════════════════════════════════════════

CINEMATIC_FIXES = {
    "depth_of_field": "shallow depth of field, f/1.8 aperture, background dissolves into soft bokeh circles, subject razor-sharp against creamy out-of-focus environment",
    "lighting_integration": "motivated practical lighting from visible sources in the room, light wraps naturally around the character matching the environment, consistent shadow direction",
    "composition": "off-center framing following rule of thirds, asymmetric composition with intentional negative space, camera slightly below eye level",
    "skin_texture": "photorealistic skin with visible pores and natural imperfections, subsurface scattering visible in ear tips and nose, no airbrushing, skin reacts to light with natural highlight and shadow",
    "environment_embedding": "character physically present in the room, matching perspective and lighting, natural shadows cast on nearby surfaces, same color temperature on skin as on room walls",
    "film_aesthetic": "35mm film grain texture, moody color grading with lifted blacks, warm practical light sources visible in frame, atmospheric haze, cinematic color science"
}

# Cross-scene aesthetic consistency targets
SCENE_AESTHETIC_PROFILE = {
    "gothic_horror": {
        "color_temp": "cool shadows with warm practicals (candles, lamps)",
        "grain": "medium-heavy film grain, visible in shadows",
        "contrast": "high contrast, deep blacks, limited fill light",
        "palette": "desaturated except warm practicals, teal-orange undertones"
    },
    "drama": {
        "color_temp": "neutral to warm, motivated by time of day",
        "grain": "subtle film grain, organic texture",
        "contrast": "medium contrast, visible shadow detail",
        "palette": "naturalistic, period-appropriate"
    },
    "thriller": {
        "color_temp": "cool steel blues with isolated warm accents",
        "grain": "fine grain, clinical precision",
        "contrast": "high contrast, hard shadows",
        "palette": "desaturated, monochromatic with accent color"
    }
}


@dataclass
class AestheticScore:
    """Result of cinematic aesthetic analysis for a single frame."""
    shot_id: str
    depth_of_field: float = 0.0
    lighting_integration: float = 0.0
    composition: float = 0.0
    skin_texture: float = 0.0
    environment_embedding: float = 0.0
    film_aesthetic: float = 0.0
    composite_score: float = 0.0
    verdict: str = "UNKNOWN"  # APPROVED, NEEDS_IMPROVEMENT, REJECTED
    reasoning: str = ""
    fixes_needed: List[str] = field(default_factory=list)
    raw_analysis: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CrossSceneReport:
    """Aesthetic continuity report across multiple scenes."""
    scenes_analyzed: int = 0
    aesthetic_drift: float = 0.0  # How much look varies across scenes
    consistency_issues: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


def _encode_image_base64(image_path: str) -> Optional[str]:
    """Encode image to base64 for vision API."""
    try:
        path = Path(image_path)
        if not path.exists():
            logger.warning(f"[AESTHETIC] Image not found: {image_path}")
            return None
        with open(path, "rb") as f:
            data = f.read()
        ext = path.suffix.lower()
        mime = "image/jpeg" if ext in (".jpg", ".jpeg") else "image/png"
        return f"data:{mime};base64,{base64.b64encode(data).decode()}"
    except Exception as e:
        logger.error(f"[AESTHETIC] Failed to encode {image_path}: {e}")
        return None


def _call_vision_model(image_b64: str, prompt: str, model: str = "anthropic/claude-3.5-sonnet") -> Optional[str]:
    """Call OpenRouter vision model for aesthetic analysis."""
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        logger.warning("[AESTHETIC] No OPENROUTER_API_KEY — cannot run aesthetic gate")
        return None

    import urllib.request

    payload = {
        "model": model,
        "max_tokens": 1200,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": image_b64}
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }
        ]
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "https://atlas-film-engine.com",
            "X-Title": "ATLAS Cinematic Aesthetic Gate"
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())
            return result["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"[AESTHETIC] OpenRouter call failed: {e}")
        return None


def score_frame_aesthetic(
    image_path: str,
    shot_id: str,
    shot_type: str = "",
    scene_genre: str = "gothic_horror",
    reference_image_path: Optional[str] = None,
) -> AestheticScore:
    """
    Score a generated frame on 6 cinematic aesthetic dimensions.

    Uses OpenRouter vision model to analyze the frame like a cinematographer would.
    Returns structured scores + verdict + specific fixes needed.

    Args:
        image_path: Path to the generated frame
        shot_id: Shot identifier for logging
        shot_type: e.g., "medium_close", "over_the_shoulder", "establishing"
        scene_genre: For aesthetic profile matching
        reference_image_path: Optional reference frame for comparison

    Returns:
        AestheticScore with per-dimension scores (1-10) and verdict
    """
    result = AestheticScore(shot_id=shot_id)

    image_b64 = _encode_image_base64(image_path)
    if not image_b64:
        result.verdict = "ERROR"
        result.reasoning = f"Could not load image: {image_path}"
        return result

    # Build the analysis prompt
    genre_profile = SCENE_AESTHETIC_PROFILE.get(scene_genre, SCENE_AESTHETIC_PROFILE["gothic_horror"])

    prompt = f"""You are a professional cinematographer reviewing a frame from an AI-generated film.
This is a {shot_type or 'character'} shot from a {scene_genre.replace('_', ' ')} production.

Target aesthetic: {genre_profile.get('color_temp', '')}. {genre_profile.get('contrast', '')}. {genre_profile.get('grain', '')}.

Score this frame on each dimension from 1-10 (1=obvious AI, 10=indistinguishable from professional cinema):

1. DEPTH_OF_FIELD: Is there shallow DOF with bokeh? Or is everything equally sharp (AI default)?
2. LIGHTING_INTEGRATION: Does light on the character match the room's light sources? Or does the character look separately lit?
3. COMPOSITION: Is the framing asymmetric, intentional, cinematic? Or dead-center passport-photo style?
4. SKIN_TEXTURE: Does skin look photorealistic with pores? Or airbrushed/waxy/uncanny?
5. ENVIRONMENT_EMBEDDING: Does the character feel physically IN the room? Or composited/pasted on a background?
6. FILM_AESTHETIC: Is there grain, color grading, atmosphere? Or sterile digital look?

IMPORTANT: Be brutally honest. Most AI frames score 3-6. A real film frame scores 8-10. Don't inflate scores.

Respond in EXACTLY this format (one line per score, then reasoning):
DEPTH_OF_FIELD: [score]
LIGHTING_INTEGRATION: [score]
COMPOSITION: [score]
SKIN_TEXTURE: [score]
ENVIRONMENT_EMBEDDING: [score]
FILM_AESTHETIC: [score]
REASONING: [2-3 sentences explaining the main issues and what would fix them]"""

    response = _call_vision_model(image_b64, prompt)
    if not response:
        result.verdict = "ERROR"
        result.reasoning = "Vision model call failed"
        return result

    result.raw_analysis = response

    # Parse scores from response
    score_map = {}
    for dim in CINEMATIC_DIMENSIONS:
        pattern = rf'{dim.upper()}:\s*(\d+(?:\.\d+)?)'
        match = re.search(pattern, response)
        if match:
            score_map[dim] = min(10.0, max(1.0, float(match.group(1))))
        else:
            score_map[dim] = 5.0  # Default if parsing fails

    result.depth_of_field = score_map.get("depth_of_field", 5.0)
    result.lighting_integration = score_map.get("lighting_integration", 5.0)
    result.composition = score_map.get("composition", 5.0)
    result.skin_texture = score_map.get("skin_texture", 5.0)
    result.environment_embedding = score_map.get("environment_embedding", 5.0)
    result.film_aesthetic = score_map.get("film_aesthetic", 5.0)

    # Extract reasoning
    reasoning_match = re.search(r'REASONING:\s*(.+)', response, re.DOTALL)
    if reasoning_match:
        result.reasoning = reasoning_match.group(1).strip()[:500]

    # Compute weighted composite
    composite = 0.0
    for dim, config in CINEMATIC_DIMENSIONS.items():
        composite += score_map.get(dim, 5.0) * config["weight"]
    result.composite_score = round(composite, 2)

    # Determine verdict
    if result.composite_score >= THRESHOLDS["composite_pass"]:
        result.verdict = "APPROVED"
    elif result.composite_score >= THRESHOLDS["composite_warn"]:
        result.verdict = "NEEDS_IMPROVEMENT"
    else:
        result.verdict = "REJECTED"

    # Flag dimensions below floor AND build fix list
    fixes = []
    for dim, score in score_map.items():
        if score < THRESHOLDS["dimension_floor"]:
            result.verdict = max(result.verdict, "NEEDS_IMPROVEMENT")  # Escalate if any dim is very low
            fixes.append(dim)
        elif score < 6.0:
            fixes.append(dim)
    result.fixes_needed = fixes

    logger.info(
        f"[AESTHETIC] {shot_id}: composite={result.composite_score:.1f} "
        f"verdict={result.verdict} "
        f"DOF={result.depth_of_field:.0f} LIGHT={result.lighting_integration:.0f} "
        f"COMP={result.composition:.0f} SKIN={result.skin_texture:.0f} "
        f"EMBED={result.environment_embedding:.0f} FILM={result.film_aesthetic:.0f}"
    )

    return result


def build_cinematic_prompt_injection(score: AestheticScore) -> str:
    """
    Given an AestheticScore with low dimensions, build a prompt injection
    string that addresses exactly the weak points.

    This gets PREPENDED to the nano_prompt on regeneration.
    """
    if not score.fixes_needed:
        return ""

    injections = []
    for dim in score.fixes_needed:
        if dim in CINEMATIC_FIXES:
            injections.append(CINEMATIC_FIXES[dim])

    if not injections:
        return ""

    return "[CINEMATIC OVERRIDE: " + ". ".join(injections) + "]. "


def score_cross_scene_consistency(
    frames: List[Dict],  # [{"shot_id": ..., "image_path": ..., "scene_id": ...}]
    scene_genre: str = "gothic_horror"
) -> CrossSceneReport:
    """
    Analyze aesthetic consistency across scenes.

    Compares frames from different scenes to detect:
    - Color temperature drift
    - Grain/texture inconsistency
    - Lighting style changes
    - DOF philosophy changes

    Uses vision model to compare pairs of frames from adjacent scenes.
    """
    report = CrossSceneReport()

    if len(frames) < 2:
        report.scenes_analyzed = len(frames)
        return report

    # Group by scene
    scenes = {}
    for f in frames:
        sid = f.get("scene_id", "")
        if sid not in scenes:
            scenes[sid] = []
        scenes[sid].append(f)

    report.scenes_analyzed = len(scenes)
    scene_ids = sorted(scenes.keys())

    # Compare adjacent scene pairs
    for i in range(len(scene_ids) - 1):
        s1 = scene_ids[i]
        s2 = scene_ids[i + 1]

        # Pick representative frame from each scene (first character shot)
        f1 = scenes[s1][0]
        f2 = scenes[s2][0]

        img1_b64 = _encode_image_base64(f1["image_path"])
        img2_b64 = _encode_image_base64(f2["image_path"])

        if not img1_b64 or not img2_b64:
            continue

        prompt = f"""Compare these two frames from adjacent scenes in a {scene_genre.replace('_', ' ')} film.
Frame 1 is from scene {s1}. Frame 2 is from scene {s2}.

Are they aesthetically consistent? Check:
1. COLOR_TEMPERATURE: Same warmth/coolness?
2. GRAIN_TEXTURE: Same film grain level?
3. CONTRAST_STYLE: Same shadow depth and highlight handling?
4. DOF_PHILOSOPHY: Same depth of field approach?

Rate overall CONSISTENCY from 1-10 (1=completely different looks, 10=seamless).
List any ISSUES found.

Format:
CONSISTENCY: [score]
ISSUES: [comma-separated list or "none"]"""

        # For cross-scene we send both images
        # OpenRouter supports multiple images in content array
        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        if not api_key:
            continue

        import urllib.request
        payload = {
            "model": "anthropic/claude-3.5-sonnet",
            "max_tokens": 500,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": img1_b64}},
                    {"type": "image_url", "image_url": {"url": img2_b64}},
                    {"type": "text", "text": prompt}
                ]
            }]
        }

        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                "https://openrouter.ai/api/v1/chat/completions",
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                    "HTTP-Referer": "https://atlas-film-engine.com",
                    "X-Title": "ATLAS Cross-Scene Consistency"
                }
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode())
                text = result["choices"][0]["message"]["content"]

            # Parse
            cons_match = re.search(r'CONSISTENCY:\s*(\d+)', text)
            if cons_match:
                consistency = float(cons_match.group(1))
                if consistency < 6:
                    report.aesthetic_drift = max(report.aesthetic_drift, 10 - consistency)

            issues_match = re.search(r'ISSUES:\s*(.+)', text, re.DOTALL)
            if issues_match:
                issues_text = issues_match.group(1).strip()
                if issues_text.lower() != "none":
                    report.consistency_issues.append(f"Scene {s1}→{s2}: {issues_text[:200]}")

        except Exception as e:
            logger.warning(f"[AESTHETIC] Cross-scene comparison {s1}→{s2} failed: {e}")

    return report


def batch_score_scene(
    scene_id: str,
    project_path: str,
    shot_types: Optional[Dict[str, str]] = None,
    scene_genre: str = "gothic_horror"
) -> List[AestheticScore]:
    """
    Score all first frames in a scene. Returns list of AestheticScore.

    This is the main entry point for the post-gen aesthetic gate.
    """
    frames_dir = Path(project_path) / "first_frames"
    if not frames_dir.is_dir():
        logger.warning(f"[AESTHETIC] No first_frames dir: {frames_dir}")
        return []

    results = []
    for frame in sorted(frames_dir.glob(f"{scene_id}_*.jpg")):
        shot_id = frame.stem
        st = (shot_types or {}).get(shot_id, "")
        score = score_frame_aesthetic(
            image_path=str(frame),
            shot_id=shot_id,
            shot_type=st,
            scene_genre=scene_genre
        )
        results.append(score)

    # Summary log
    if results:
        approved = sum(1 for r in results if r.verdict == "APPROVED")
        needs_work = sum(1 for r in results if r.verdict == "NEEDS_IMPROVEMENT")
        rejected = sum(1 for r in results if r.verdict == "REJECTED")
        avg = sum(r.composite_score for r in results) / len(results)
        logger.info(
            f"[AESTHETIC] Scene {scene_id}: {len(results)} frames scored — "
            f"avg={avg:.1f} APPROVED={approved} IMPROVE={needs_work} REJECTED={rejected}"
        )

    return results
