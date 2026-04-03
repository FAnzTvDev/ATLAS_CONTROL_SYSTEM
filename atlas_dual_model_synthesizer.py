"""
ATLAS LITE SYNTHESIZER — Dual-Model Edition
=========================================
V23 upgrade: system now has two model pathways.
No LoRAs yet → identity via NB keyframe anchor (image_url).
Higgsfield-validated: prompt compiler IS the moat, not the gear selector.

Architecture shift:
  OLD: 7 enrichment layers → gate → deduplicate → prompt (redundant, conflicting)
  NEW: 7 isolated token zones → compile once → route → fire

Model routing (no LoRA tiers yet):
  KLING O3  → identity-critical shots (CU, dialogue, emotional peaks)
  LTX-2.3   → atmosphere, wide, extend-chains, QC retakes
"""

import json, time, asyncio, hashlib
from dataclasses import dataclass, field, asdict
from typing      import Optional
import fal_client as fal


# ─── CINEMATIC TOKEN LIBRARY ─────────────────────────────────────────────────
# Higgsfield moat insight: simple UI inputs → compiled text modifiers.
# Camera brands (ARRI, RED) do NOT condition models. These do.

TOKENS = {
    "lens": {
        "wide_28mm":      "28mm slight barrel distortion, expansive FOV, environmental context",
        "normal_50mm":    "50mm natural perspective, eye-level intimacy, undistorted geometry",
        "portrait_85mm":  "85mm f/1.8 shallow depth, subject isolation, compressed background",
        "tele_135mm":     "135mm compression, collapsed depth planes, voyeuristic distance",
        "anamorphic":     "anamorphic oval bokeh, horizontal lens flare, cinematic 2.39:1 feel",
    },
    "camera_move": {
        "static":         "locked-off tripod, absolute stillness, composed geometric frame",
        "dolly_in":       "slow forward dolly, focal compression, encroaching intimacy",
        "dolly_out":      "retreating reveal dolly, expanding context, subject diminished",
        "tracking":       "lateral tracking shot, parallel motion, subject held in frame",
        "handheld":       "organic handheld drift, 2-pixel subtle shake, documentary truth",
        "push_in":        "creeping push-in, measured approach, dread accumulation",
    },
    "emotion": {
        "dread":          "microexpression of controlled fear, jaw tight, pupils searching",
        "grief":          "suppressed emotion at jaw, breath shallow, eyes glistening, held",
        "rage":           "stillness before eruption, lips pressed, temple vein faint",
        "wonder":         "pupils dilated, slight lip part, head tilts, breath held",
        "resolve":        "jaw set, eyes level, breath steady, hands still",
        "deceit":         "carefully neutral expression masking calculation, brief tell flicker",
    },
    "light": {
        "candle":         "warm 2200K candle practicals, guttering shadows, unstable warmth",
        "moonlight":      "cool 5600K window bars, silver edge rim, deep shadow pools",
        "fireplace":      "amber 2700K flicker, dynamic shadow dance, radiant warmth",
        "overcast":       "diffused 4300K, no hard shadow, even melancholy",
        "storm_flash":    "strobed 6500K bursts, deep shadow recovery, temporal disorientation",
        "magic_hour":     "golden 3200K oblique rake, 30-degree angle, extended warmth",
    },
    "grade": {
        # Ravencroft Manor — project-locked, appended to every prompt
        "ravencroft":     "desaturated cool tones, teal in shadows, amber warm practicals, "
                          "Kodak 2383 print look, 35mm grain, slight vignette",
    },
    "guard": {
        # Anti-contamination — replaces the old Gold Standard Negatives layer
        "photorealism":   "photorealistic, no CGI artifacts, no synthetic skin texture, "
                          "no uncanny valley, film grain present, no digital smoothing",
    }
}

COLOR_ANCHOR = TOKENS["grade"]["ravencroft"]  # appended to EVERY shot regardless of model


# ─── SHOT DATA ────────────────────────────────────────────────────────────────
@dataclass
class Shot:
    shot_id:          str
    scene_id:         str
    shot_type:        str               # WS, MS, MCU, CU, OTS, INSERT
    characters:       list[str]
    location:         str
    action:           str               # brief action description
    has_dialogue:     bool
    duration_seconds: int               # 3–20
    nb_frame_url:     Optional[str] = None   # Nano Banana keyframe
    end_frame_url:    Optional[str] = None   # optional bookend
    location_ref_url: Optional[str] = None   # environment reference
    lens_choice:      str = "normal_50mm"
    move_choice:      str = "static"
    emotion_choice:   Optional[str] = None
    light_choice:     str = "candle"
    # Populated by router
    model:            Optional[str] = None   # "KLING" | "LTX"
    routing_mode:     Optional[str] = None   # "identity" | "i2v" | "atmosphere" | "extend"
    compiled_prompt:  Optional[str] = None
    output_url:       Optional[str] = None
    cost:             float = 0.0
    status:           str = "waiting"


# ─── ROUTING LOGIC ────────────────────────────────────────────────────────────
def route_shot(shot: Shot) -> Shot:
    """
    No LoRAs → two pathways only.
    Kling:  identity-critical (CU, dialogue, emotional peaks first/last shots)
    LTX:    everything else — atmosphere, wide, extend-chains, QC retakes
    """
    is_identity_critical = (
        shot.shot_type in ("CU", "MCU") and len(shot.characters) > 0
    ) or shot.has_dialogue or (
        shot.emotion_choice in ("dread", "grief", "rage")
    )

    if is_identity_critical:
        shot.model        = "KLING"
        shot.routing_mode = "identity"
        shot.cost         = 0.56  # Kling O3 Pro base per 5s
    elif len(shot.characters) == 0:
        shot.model        = "LTX"
        shot.routing_mode = "atmosphere"
        shot.cost         = 0.12
    else:
        shot.model        = "LTX"
        shot.routing_mode = "i2v"
        shot.cost         = 0.20

    return shot


# ─── PROMPT COMPILER (Higgsfield-validated approach) ─────────────────────────
class LITESynthesizer:
    """
    5 isolated zones. No enrichment layer stacking. No deduplication needed
    because each zone writes exactly once to its zone only.

    Zone map:
      Z1  SUBJECT    — who, what action, where
      Z2  LENS       — focal length + optical character (no brand names)
      Z3  MOTION     — camera movement descriptor
      Z4  EMOTION    — performance direction (physical, not abstract)
      Z5  LIGHT      — color temp + quality + source behavior
      Z6  GRADE      — project-locked color anchor (Ravencroft)
      Z7  GUARD      — anti-contamination tokens
    """

    def compile(self, shot: Shot) -> str:
        zones = []

        # Z1 — Subject
        if shot.characters:
            subject = f"{shot.characters[0]} — {shot.action} — {shot.location}"
        else:
            subject = f"{shot.location} — {shot.action}"
        zones.append(subject)

        # Z2 — Lens
        zones.append(TOKENS["lens"].get(shot.lens_choice, TOKENS["lens"]["normal_50mm"]))

        # Z3 — Motion
        zones.append(TOKENS["camera_move"].get(shot.move_choice, TOKENS["camera_move"]["static"]))

        # Z4 — Emotion (only when character present, only when defined)
        if shot.characters and shot.emotion_choice:
            zones.append(TOKENS["emotion"][shot.emotion_choice])

        # Z5 — Light
        zones.append(TOKENS["light"].get(shot.light_choice, TOKENS["light"]["candle"]))

        # Z6 — Grade (project-locked, every shot)
        zones.append(COLOR_ANCHOR)

        # Z7 — Guard
        zones.append(TOKENS["guard"]["photorealism"])

        prompt = ". ".join(zones)

        # Target: 70–120 words for LTX, 50–100 for Kling
        words = len(prompt.split())
        target = (70, 120) if shot.model == "LTX" else (50, 100)
        if words < target[0] or words > target[1]:
            print(f"  ⚠ {shot.shot_id}: prompt {words}w (target {target[0]}–{target[1]}w)")

        return prompt


# ─── PAYLOAD BUILDERS ─────────────────────────────────────────────────────────
class KlingPayloadBuilder:
    """Builds payload for fal-ai/kling-video/o3/pro/reference-to-video"""

    def build(self, shot: Shot, canonical_chars: dict) -> dict:
        char_name = shot.characters[0] if shot.characters else None
        char_data = canonical_chars.get(char_name, {}) if char_name else {}

        elements = []
        if char_data:
            elements.append({
                "frontal_image_url":    char_data["frontal_image_url"],
                "reference_image_urls": char_data["reference_image_urls"],
            })

        # Character tag in prompt only if element present
        prompt = shot.compiled_prompt
        if elements and "@Element1" not in prompt:
            prompt = f"@Element1 — {prompt}"

        payload = {
            "prompt":          prompt,
            "duration":        min(shot.duration_seconds, 15),
            "shot_type":       "customize",
            "generate_audio":  shot.has_dialogue,
            "elements":        elements,
        }

        if shot.nb_frame_url:   payload["start_image_url"] = shot.nb_frame_url
        if shot.end_frame_url:  payload["end_image_url"]   = shot.end_frame_url

        if shot.has_dialogue and char_data.get("voice_id"):
            payload["voice_ids"] = [char_data["voice_id"]]
            payload["prompt"]   += f" <<<voice_1>>>"

        return payload


class LTXPayloadBuilder:
    """Builds payload for fal-ai/ltx-2.3/image-to-video/fast"""

    def build(self, shot: Shot, extend_from_url: Optional[str] = None) -> dict:
        if extend_from_url:
            # Extend mode — temporal continuity, no fresh generation cost
            return {
                "video_url":  extend_from_url,
                "prompt":     shot.compiled_prompt,
                "duration":   shot.duration_seconds,
                "mode":       "end",
                "context":    min(4.0, shot.duration_seconds),
            }

        # Fresh I2V or atmosphere
        anchor = shot.nb_frame_url or shot.location_ref_url
        payload = {
            "prompt":         shot.compiled_prompt,
            "duration":       min(shot.duration_seconds, 20),
            "resolution":     "1440p" if shot.routing_mode == "atmosphere" else "1080p",
            "fps":            48 if "slow" in shot.action.lower() else 25,
            "generate_audio": shot.routing_mode == "atmosphere",
            "aspect_ratio":   "16:9",
        }
        if anchor:
            payload["image_url"] = anchor
        if shot.end_frame_url:
            payload["end_image_url"] = shot.end_frame_url

        return payload


# ─── QC + RETAKE ─────────────────────────────────────────────────────────────
async def qc_and_retake(shot: Shot, video_url: str, dino_threshold: float = 0.70) -> str:
    """
    For LTX shots: surgical retake instead of full regen.
    DINO score < 0.56 → retake that segment only.
    No ArcFace for Kling — identity enforced by elements[] array.
    """
    if shot.model == "KLING":
        return video_url  # identity guaranteed by elements[], no QC needed

    # Mock DINO check (replace with actual fal DINO call)
    dino_score = 0.65 + (hash(video_url) % 100) / 1000
    print(f"  QC {shot.shot_id}: DINO={dino_score:.3f}")

    if dino_score < 0.56:
        print(f"  ↳ RETAKE: below reject threshold")
        result = await fal.run_async(
            "fal-ai/ltx-2.3/image-to-video/fast/retake",
            arguments={
                "video_url":    video_url,
                "prompt":       shot.compiled_prompt,
                "start_time":   0,
                "duration":     shot.duration_seconds,
                "retake_mode":  "replace_video",  # keep audio if present
            }
        )
        return result["video"]["url"]

    return video_url


# ─── SCENE RENDERER ───────────────────────────────────────────────────────────
class SceneRenderer:
    def __init__(self, canonical_chars: dict):
        self.canonical_chars    = canonical_chars
        self.synthesizer        = LITESynthesizer()
        self.kling_builder      = KlingPayloadBuilder()
        self.ltx_builder        = LTXPayloadBuilder()

    async def render_scene(self, shots: list[Shot]) -> list[Shot]:
        """
        Kling shots: sequential (identity chain)
        LTX shots:   extend-chain where possible, parallel elsewhere
        """
        # Route + compile all shots first
        for shot in shots:
            shot = route_shot(shot)
            shot.compiled_prompt = self.synthesizer.compile(shot)

        kling_shots = [s for s in shots if s.model == "KLING"]
        ltx_shots   = [s for s in shots if s.model == "LTX"]

        # ── Kling: sequential with reference threading ────────────────────────
        last_kling_frame = None
        for shot in kling_shots:
            if last_kling_frame:
                shot.nb_frame_url = last_kling_frame  # chain identity frames
            payload = self.kling_builder.build(shot, self.canonical_chars)
            result = await fal.run_async(
                "fal-ai/kling-video/o3/pro/reference-to-video",
                arguments=payload
            )
            shot.output_url = result["video"]["url"]
            shot.status     = "done"
            last_kling_frame = shot.end_frame_url  # or extract last frame
            print(f"  ✓ KLING {shot.shot_id}")

        # ── LTX: build extend chains or parallel ─────────────────────────────
        ltx_chains = self._build_extend_chains(ltx_shots)

        async def render_chain(chain):
            prev_url = None
            for shot in chain:
                payload = self.ltx_builder.build(shot, extend_from_url=prev_url if prev_url else None)
                endpoint = (
                    "fal-ai/ltx-2.3/image-to-video/fast/extend"
                    if prev_url else
                    "fal-ai/ltx-2.3/image-to-video/fast"
                )
                result = await fal.run_async(endpoint, arguments=payload)
                url = result["video"]["url"]
                url = await qc_and_retake(shot, url)
                shot.output_url = url
                shot.status     = "done"
                prev_url = url
                print(f"  ✓ LTX {shot.shot_id} ({'extend' if prev_url else 'fresh'})")

        await asyncio.gather(*[render_chain(chain) for chain in ltx_chains])

        return shots

    def _build_extend_chains(self, shots: list[Shot]) -> list[list[Shot]]:
        """Group LTX shots into extend chains where character + location continuous."""
        chains, current = [], []
        for shot in shots:
            if not current:
                current.append(shot)
            else:
                prev = current[-1]
                can_extend = (
                    prev.location == shot.location and
                    set(prev.characters) == set(shot.characters) and
                    prev.duration_seconds < 20
                )
                if can_extend:
                    current.append(shot)
                else:
                    chains.append(current)
                    current = [shot]
        if current:
            chains.append(current)
        return chains


# ─── COST ESTIMATOR ───────────────────────────────────────────────────────────
def estimate_cost(shots: list[Shot]) -> dict:
    routed = [route_shot(s) for s in shots]
    kling  = [s for s in routed if s.model == "KLING"]
    ltx    = [s for s in routed if s.model == "LTX"]

    # Estimate extend savings: ~60% of LTX shots can chain
    ltx_fresh  = int(len(ltx) * 0.4)
    ltx_extend = int(len(ltx) * 0.6)

    kling_cost  = len(kling)      * 0.56
    fresh_cost  = ltx_fresh       * 0.20
    extend_cost = ltx_extend      * 0.10
    qc_retakes  = (len(routed) * 0.08) * 0.15  # 8% fail rate, partial retake cost

    total = kling_cost + fresh_cost + extend_cost + qc_retakes

    return {
        "kling_shots":      len(kling),
        "ltx_shots":        len(ltx),
        "ltx_extend_chain": ltx_extend,
        "kling_cost":       round(kling_cost, 2),
        "ltx_fresh_cost":   round(fresh_cost, 2),
        "ltx_extend_cost":  round(extend_cost, 2),
        "qc_retake_cost":   round(qc_retakes, 2),
        "total_estimated":  round(total, 2),
    }


# ─── USAGE EXAMPLE ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Example shots — Victorian Shadows EP1
    CANONICAL = {
        "Eleanor": {
            "frontal_image_url":    "https://fal.media/files/eleanor_frontal.png",
            "reference_image_urls": ["https://fal.media/files/eleanor_3q.png"],
            "voice_id":             "eleanor_custom_voice_001",
        },
        "Victor": {
            "frontal_image_url":    "https://fal.media/files/victor_frontal.png",
            "reference_image_urls": ["https://fal.media/files/victor_3q.png"],
            "voice_id":             "victor_custom_voice_002",
        },
    }

    shots = [
        Shot("S03_01","S03","WS",   ["Eleanor","Victor"],"INT - Drawing Room","Eleanor enters, Victor stands", False, 8),
        Shot("S03_02","S03","MCU",  ["Eleanor"],          "INT - Drawing Room","Eleanor reads the letter",       False, 6, emotion_choice="dread"),
        Shot("S03_03","S03","CU",   ["Victor"],           "INT - Drawing Room","Victor watches her",             False, 5, emotion_choice="deceit"),
        Shot("S03_04","S03","OTS",  ["Eleanor","Victor"], "INT - Drawing Room","Victor speaks, Eleanor turns",   True,  7),
        Shot("S03_05","S03","INSERT",[],                  "INT - Drawing Room","Candle flame flickers",          False, 4),
        Shot("S03_06","S03","MS",   ["Eleanor"],          "INT - Drawing Room","Eleanor moves to the window",   False, 6),
        Shot("S03_07","S03","WS",   [],                   "INT - Drawing Room","Room empty, door ajar",          False, 5),
    ]

    # Estimate
    costs = estimate_cost(shots)
    print("\n─── COST ESTIMATE ─────────────────────────────")
    for k, v in costs.items():
        print(f"  {k:<22} {v}")

    # Compile prompts
    synth = LITESynthesizer()
    print("\n─── COMPILED PROMPTS ──────────────────────────")
    for shot in shots:
        shot = route_shot(shot)
        prompt = synth.compile(shot)
        words  = len(prompt.split())
        print(f"\n  [{shot.shot_id}] {shot.model} · {shot.routing_mode}")
        print(f"  Words: {words}")
        print(f"  {prompt[:160]}...")
