"""
tools/vision_doctrine_prompts.py — Vision Doctrine Layer V1.0 (2026-03-29)
===========================================================================
Cinematography-aware Gemini prompt library for ATLAS VVO (Video Vision Oversight).

Elevates Gemini from QA bot to CINEMATOGRAPHER by evaluating clips on two axes:

  AXIS 1 — PRODUCTION TYPE (the FORMAT rules)
    What are the visual conventions of this production format?
    Movie? Podcast? Fight broadcast? Sports game? Music video?

  AXIS 2 — GENRE DNA (the TONE rules)
    What does horror/sci-fi/drama/action look like emotionally?
    Color palette? Lighting standard? Pacing? Forbidden elements?

Together, these axes form a DOCTRINE MATRIX:
  horror × movie        = dutch angles + slow push-ins + shadow dominant
  horror × podcast      = dark studio + intimate framing + low-key practicals
  action × fight_broadcast = ring clarity + impact shots + kinetic cuts
  sci_fi × series       = geometric compositions + cool LED + strict 180°

ARC POSITION adds the NARRATIVE dimension:
  ESTABLISH must declare location + tone.
  ESCALATE must carry what ESTABLISH declared.
  PIVOT must shift visibly.
  RESOLVE must close the emotional beat.

FILMMAKING GRAMMAR checks apply universally:
  180° rule, eyeline match, rule of thirds, shot motivation,
  screen direction continuity, match cuts, rack focus intent.

Usage (from video_vision_oversight.py):
    from tools.vision_doctrine_prompts import (
        get_doctrine_prompt,
        get_chain_doctrine_prompt,
        get_scene_stitch_doctrine_prompt,
        parse_doctrine_fields,
    )

    # In analyze_full_video():
    doctrine_block = get_doctrine_prompt(shot, genre_id, production_type)
    full_prompt = base_technical_prompt + "\\n\\n" + doctrine_block

    # In analyze_chain_transition():
    chain_block = get_chain_doctrine_prompt(prev_shot, curr_shot, genre_id, production_type)
    full_prompt = base_chain_prompt + "\\n\\n" + chain_block

    # Parse extended fields from Gemini response dict:
    doctrine = parse_doctrine_fields(response_data)

Authority: ADVISORY (QA layer) — returns verdicts + grades, never mutates shot_plan.
Wire: called by video_vision_oversight.py when building Gemini prompts.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

# ═══════════════════════════════════════════════════════════════════════════════
# BROADCAST QC STANDARDS (Netflix / Amazon / Professional Cinematography)
# These are hard numbers that Gemini evaluates against — not descriptions.
# Source: Netflix Partner Delivery Specification, EBU R128, ITU-R BT.2390,
#         ASC manual, SMPTE RP 177, broadcast engineering practice.
# ═══════════════════════════════════════════════════════════════════════════════

BROADCAST_QC_THRESHOLDS = {
    # ── Video Quality Metrics ──────────────────────────────────────────────────
    "vmaf_streaming_min":    75,     # Minimum VMAF for streaming delivery
    "vmaf_excellent":        85,     # Excellent streaming quality
    "vmaf_theatrical":       95,     # Theatrical / master quality target
    "ssim_shot_to_shot":     0.95,   # Minimum SSIM between consecutive shots of same scene
    "ssim_chain_min":        0.90,   # Minimum SSIM across chain handoff

    # ── Color Accuracy ────────────────────────────────────────────────────────
    "delta_e_same_char":     1.5,    # Max ΔE between shots of same character (skin tone drift)
    "delta_e_same_location": 2.0,    # Max ΔE between shots of same location (color consistency)
    "delta_e_chain":         3.0,    # Max ΔE at chain transition (acceptable shift)
    "delta_e_critical":      5.0,    # ΔE above this = visible color mismatch — FAIL

    # ── Audio / Lip-sync ──────────────────────────────────────────────────────
    "audio_sync_max_ms":     22,     # Max lip-sync drift (±22ms per SMPTE/EBU)
    "loudness_lkfs_low":    -26.0,   # Loudness floor (integrated LKFS per EBU R128)
    "loudness_lkfs_high":   -24.0,   # Loudness ceiling (Netflix: -24 LKFS target)
    "true_peak_max_dbtp":   -2.0,    # True peak ceiling (dBTP)

    # ── AI Artifact Detection ─────────────────────────────────────────────────
    "identity_drift_threshold":   0.15,  # Facial recognition confidence drop >15% = morphing
    "temporal_flicker_threshold": 0.02,  # Frame-to-frame pixel variance >2% in stable regions
    "texture_hallucination":      True,  # Objects appearing/disappearing between frames
    "physics_violation":          True,  # Impossible trajectories / object behavior

    # ── Cinematography Rules (pass/fail thresholds) ───────────────────────────
    "headroom_min_px_pct":   0.03,   # Min headroom: 3% of frame height above head
    "headroom_max_px_pct":   0.15,   # Max headroom: 15% of frame height
    "nose_room_pct":         0.10,   # Min nose room: 10% of frame width in gaze direction
    "rack_focus_frames":     2,      # Rack focus tolerance: ±1-2 frames (smooth)
    "rule_of_thirds_tolerance": 0.08, # Subject center within 8% of power points = pass
}

# ── LIGHTING RATIOS BY GENRE ──────────────────────────────────────────────────
# Key-to-fill ratio. Delivered as a visual evaluation standard for Gemini.
# Gemini evaluates the VISIBLE ratio by reading shadow depth relative to key.
GENRE_LIGHTING_RATIOS = {
    "horror":           {"ratio": "8:1",  "description": "Extreme low-key. Deep hard shadows covering 60%+ of face. Near-black fill. Single motivated source. Shadows are DOMINANT element."},
    "thriller":         {"ratio": "6:1",  "description": "Low-key. Strong shadows. Motivated key source. Fill exists but is minimal and cool-toned."},
    "whodunnit_drama":  {"ratio": "4:1",  "description": "Naturalistic. Motivated key (window/lamp). Soft fill where physically motivated. Rich shadows but faces readable."},
    "drama":            {"ratio": "4:1",  "description": "Naturalistic. 4:1 is standard drama ratio. Faces fully lit, shadows present but soft."},
    "sci_fi":           {"ratio": "5:1",  "description": "Hard directional. Cool LED key. Minimal fill. Technical precision — shadows are geometric, not organic."},
    "action":           {"ratio": "variable", "description": "Dynamic. High contrast (up to 8:1 in dark moments), even (2:1) in open exterior. Contrast amplifies impact."},
    "comedy":           {"ratio": "2:1",  "description": "Soft even fill. Minimal shadows. Maximum face visibility. The punchline lives in the expression."},
    "fight_broadcast":  {"ratio": "3:1",  "description": "Arena overhead rigs. Even overall with deep corners. Fighters fully lit, arena periphery darker."},
    "sports_game":      {"ratio": "2:1",  "description": "Stadium even fill. Consistent across field. No dramatic shadows — everything visible."},
    "music_video":      {"ratio": "variable", "description": "Driven by artistic intent. Can be extreme low-key for atmosphere or high-key for energy. Must serve song mood."},
    "podcast":          {"ratio": "3:1",  "description": "Professional three-point. Soft key, minimal fill, gentle rim. Warm, approachable, broadcast-clean."},
    "comedy_special":   {"ratio": "2:1",  "description": "Stage spot on performer. Audience in darkness. Performer fully lit, warm, clean."},
    "_default":         {"ratio": "4:1",  "description": "Standard drama ratio. Naturalistic and motivated."},
}

# ── AI ARTIFACT PATTERNS FOR GEMINI PROMPT ────────────────────────────────────
# Human-readable descriptions of AI generation failure modes.
AI_ARTIFACT_CHECKLIST = """
AI GENERATION ARTIFACT DETECTION (evaluate carefully):
  1. IDENTITY MORPHING: Does the character's facial structure change at any point?
     Threshold: Face shape, bone structure, or skin tone visibly shifts mid-clip = FAIL.
     (This is the AI "identity drift" problem — confidence drop equivalent >15%)

  2. TEMPORAL FLICKER: Does any stable background element flicker or pulse unexpectedly?
     Threshold: Wall texture, floor, furniture randomly changes between frames = FAIL.
     (Frame-to-frame pixel variance >2% in regions that should be static)

  3. TEXTURE HALLUCINATION: Do objects appear or disappear without story motivation?
     Examples: prop materializes on table, door appears in blank wall, window vanishes.
     Any unmotivated object change = FAIL.

  4. PHYSICS VIOLATION: Does anything move in physically impossible ways?
     Examples: hair defying gravity, fabric floating, limbs bending at impossible angles.
     Any obvious physics break = FAIL.

  5. TEMPORAL FREEZE: Does the video freeze for ≥0.5 seconds at any point?
     Threshold: Complete stillness for half a second or more (intentional pause ≠ freeze).

  6. FACE LOCK FAILURE: Does the character's face "drift" or "travel" across the frame
     during what should be a static shot?
     AI face drift = character appears to slide or shift position unnaturally = FAIL.
"""

# ── BROADCAST THRESHOLDS BLOCK (for Gemini prompt injection) ─────────────────
# Pre-formatted text for injecting into Gemini prompts.
BROADCAST_THRESHOLDS_PROMPT_BLOCK = f"""
BROADCAST QC THRESHOLDS (Netflix/Amazon professional standards):
  Video quality:
    • VMAF: streaming minimum=75, excellent=85 (evaluate perceived sharpness/compression)
    • SSIM shot-to-shot: minimum 0.95 between consecutive same-scene shots
    • Color consistency: ΔE ≤1.5 for same character skin tone between shots
    • Color consistency: ΔE ≤2.0 for same location environment between shots
    • Color shift at chain transition: ΔE ≤3.0 (acceptable), >5.0 = FAIL

  Audio/lip-sync:
    • Lip-sync drift: maximum ±22ms (SMPTE/EBU standard)
    • Loudness target: -24 to -26 LKFS integrated (EBU R128)
    • True peak ceiling: -2 dBTP

  Cinematography pass/fail:
    • Headroom: minimum 3%, maximum 15% of frame height above subject's head
    • Nose room: minimum 10% of frame width in direction of gaze
    • Rack focus: must complete within ±2 frames of target — smooth transition
    • Rule of thirds: subject center within ~8% tolerance of power points = PASS
    • 180° rule: camera MUST stay on same side of action axis — zero tolerance
    • Eyeline match: gaze direction in Shot A must logically connect to Shot B target
    • Screen direction: character exits frame-right → enters next frame-left (and vice versa)
"""
# Defines FORMAT rules: how the camera operates, framing conventions,
# what the audience expects from this production format.
# ═══════════════════════════════════════════════════════════════════════════════

PRODUCTION_CRITERIA: Dict[str, Dict[str, str]] = {
    "movie": {
        "display": "Movie / Series (Cinematic)",
        "camera_format": "Full cinematic grammar. Wide shots establish space with depth layers. Motivated camera movement — every move has a story reason. Coverage includes establishing, medium, close-up, reaction, and insert shots.",
        "framing": "Rule of thirds for character placement. Deep focus for establishing shots. Shallow DoF (bokeh) for close-up intimacy. Environmental storytelling — the room tells the story too.",
        "cuts": "Motivated cuts — cut when something changes (action, dialogue, emotion). Match cuts and eyeline continuity across the edit. Murch's rule of six applies: emotion first, then story, then rhythm.",
        "pacing": "Shot length matches emotional content. Drama holds. Action cuts fast. Establish before moving.",
        "required": "Depth, environmental storytelling, motivated camera movement, composition serving the narrative",
        "forbidden": "Unmotivated handheld jitter for drama, flat talking-head framing, cuts mid-sentence for no reason",
        "check": "Does this look like a theatrical feature film? If it looks like a webcam recording or news footage, it has FAILED.",
    },
    "podcast": {
        "display": "Podcast / Interview (Studio)",
        "camera_format": "Three-camera studio format: wide two-shot master, individual medium singles, tight close-ups for key moments. Camera moves ONLY between setups — no motivated moves mid-sentence.",
        "framing": "Host(s) framed medium to medium-close. Eye-level camera. Clear separation between speakers spatially. Subject maintains eye contact with partner or camera (not both at once).",
        "cuts": "Cut between speakers with clean edits. Never cut mid-thought unless intentional. Cut to close-up for emotional emphasis. Wide establisher every scene open.",
        "pacing": "Hold on speaker. Cut to reaction when appropriate. Deliberate, not rushed — let conversations breathe.",
        "required": "Clean eye-level framing, clear speaker separation, professional studio lighting, listener reaction shots",
        "forbidden": "Handheld jitter, cinematic dutch angles, dramatic depth-of-field on speakers, unmotivated camera moves",
        "check": "Does this look like a professional studio conversation? If it looks like a spy thriller, it has FAILED.",
    },
    "fight_broadcast": {
        "display": "Fight / Combat Broadcast (Arena Sports)",
        "camera_format": "Arena multi-camera production. Wide-angle for ring/cage geography. Ringside for action detail. Upper for overhead spatial clarity. Crowd shots for atmosphere. Replay/slow-motion for key moments.",
        "framing": "Both fighters visible in wide. Clear spatial understanding of ring/cage layout. Fighter close-ups during drama, celebration, or injury. Referee position visible.",
        "cuts": "Fast cuts during exchanges. Hold on drama/standoffs. Crowd reactions intercut. Commentary position visible. Round breaks allow slower coverage.",
        "pacing": "Kinetic during action. Pause-hold-release rhythm. Action → reaction → crowd → replay structure.",
        "required": "Ring/cage spatial clarity, both fighters identifiable, crowd energy visible, impact moments readable",
        "forbidden": "Blocking ring geography, confusing spatial orientation, missing key action, losing fighters in frame",
        "check": "Can the viewer understand the fight geography and track who is winning? If the ring layout is unclear, FAILED.",
    },
    "sports_game": {
        "display": "Sports Game Broadcast (Field/Court)",
        "camera_format": "Stadium multi-camera: wide overhead for gameplay, ground-level for intensity, tight on player faces for drama, aerial for team movement and formation.",
        "framing": "Game play visible at all times during action. Ball/puck/object of play trackable. Team colors distinguishable. Field/court geometry readable.",
        "cuts": "Follow the play. Cut to key players. Reaction shots between plays. Scoreboard inserts for context.",
        "pacing": "Play-rhythm driven. Fast during action. Deliberate holds between plays for strategy reads.",
        "required": "Field visibility, ball tracking, team color separation, scoreboard context, player identification",
        "forbidden": "Obscuring game action, confusing viewer about score/situation, losing field geometry",
        "check": "Can you follow the game clearly? Is the sports context unmistakable and the action readable?",
    },
    "music_video": {
        "display": "Music Video (Performance / Conceptual)",
        "camera_format": "Performance-driven: artist is the subject. Conceptual narrative interwoven. Camera movement is expressive — not just functional. Rhythm-synced cuts are expected.",
        "framing": "Artist as central icon. Dynamic composition — rule of thirds, intentional negative space, bold geometry. Wide for performance scale. Tight for emotional intensity.",
        "cuts": "Rhythm-synced to music. Lyric-sync for close-up delivery moments. Fast montage acceptable — this is a visual music experience.",
        "pacing": "Dictated by the music. BPM of cuts matches song energy. Verse = deliberate, Chorus = kinetic.",
        "required": "Artist presence, rhythm-sync cuts, visual style serving the song's emotion, performance energy",
        "forbidden": "Static unmotivated holds disconnected from music, confusing narrative without performance payoff",
        "check": "Does the visual energy match the music's emotional arc? If it feels disconnected from the song, FAILED.",
    },
    "bumper": {
        "display": "Bumper / Commercial (Short-Form Brand)",
        "camera_format": "Quick-cut structure. Brand identity dominant. Call-to-action visual clarity. Every frame must be graphically striking — no throwaway shots.",
        "framing": "Brand-forward compositions. Logo placement anticipated. Product/subject at visual center. High-impact frames only.",
        "cuts": "Fast — 1-3 seconds per shot. Energy building to CTA moment. No lingering.",
        "pacing": "Aggressive pacing with clear beginning-middle-end. Message delivered in under 30 seconds.",
        "required": "Brand clarity, graphic impact, CTA visual emphasis, high-energy composition every frame",
        "forbidden": "Slow establishing shots, ambiguous compositions, frames that don't advance the brand message",
        "check": "Is every single frame worth keeping? Is the brand message impossible to miss?",
    },
    "comedy_special": {
        "display": "Comedy Special (Stage Performance)",
        "camera_format": "Three-camera live-performance format: wide stage master, medium performance single, tight face close-up. Audience reaction shots critical — the laugh is part of the show.",
        "framing": "Performer center stage or rule of thirds. Full body visible for physical comedy. Audience in darkness framing the performer. Stage geography established in opening.",
        "cuts": "Hold on performer through punchline. Cut to audience reaction after beat. Don't cut on the laugh — let it breathe. Wide re-establishes between bits.",
        "pacing": "Comedian controls the rhythm. Hold for beat. Pause before punchline. Cut to crowd to share the laugh.",
        "required": "Performer dominance in frame, audience reaction shots, stage geography clear, punchline timing respected",
        "forbidden": "Cutting mid-punchline, dark horror lighting, confusing the venue geography",
        "check": "Is the comedian clearly the star? Is the performance readable? Does the audience feel present?",
    },
    # Default fallback
    "_default": {
        "display": "General Production",
        "camera_format": "Motivated camera work appropriate to the content. Coverage serves the story.",
        "framing": "Clear subject. Compositionally purposeful. Environment serves context.",
        "cuts": "Cuts motivated by story, emotion, or action. No arbitrary edits.",
        "pacing": "Shot length appropriate to emotional content.",
        "required": "Clarity, motivation, story service",
        "forbidden": "Unmotivated chaos, confusion, hiding the subject",
        "check": "Does this shot serve the story and the audience?",
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# AXIS 2 — GENRE DNA CRITERIA
# Defines TONE rules: what the emotional world looks like visually.
# These overlay ON TOP of production type — same rules, different palette.
# ═══════════════════════════════════════════════════════════════════════════════

GENRE_CRITERIA: Dict[str, Dict[str, str]] = {
    "horror": {
        "display": "Horror",
        "lighting": "Low-key MANDATORY. Single or dual practical sources max. Deep hard shadows dominating 60%+ of frame. Motivated single-source light only — no soft fill, no bounce.",
        "color": "Desaturated cold base. Deep blues and blacks in shadow. Amber ONLY from practical sources (candle, lamp). No warm fill, no golden-hour cheerfulness.",
        "camera_mood": "Slow deliberate push-ins for dread. Static wide holds for isolation. Dutch angles for psychological disorientation. Negative space used intentionally — subject pushed to corner, darkness takes most of frame.",
        "pacing_mood": "Hold longer than comfortable. Silence is a weapon. Sharp cuts ONLY at scare beats, not during tension build.",
        "emotional_standard": "Dread, isolation, vulnerability. The frame should feel like something is watching. Shadows hide threats.",
        "required": "Deep shadows, motivated practical lighting, negative space for tension, slow deliberate movement",
        "forbidden": "Bright even fill lighting, warm cheerful color grading, fast-cut MTV editing during tension",
        "check": "Would this shot work in a cheerful romantic comedy? If YES, it has FAILED as horror.",
    },
    "sci_fi": {
        "display": "Science Fiction",
        "lighting": "Practical LED sources, holographic glow, hard directional light. Clean technological illumination. High contrast — bright surfaces, deep black voids.",
        "color": "Cool blues and teals dominant. Occasional warm amber accents from tech sources. High contrast. Clean blacks — no murky grays.",
        "camera_mood": "Clean motivated moves. Geometric compositions — strong lines, symmetry, right angles. Eye-level for characters (they have authority). Low-angle for machines and technology (awe).",
        "pacing_mood": "Deliberate holds on technology reveals. Brisk cuts during action. Order and precision in movement.",
        "emotional_standard": "Wonder, discovery, scale. The environment is grander than the human. Technology frames the world.",
        "required": "Cool color dominance, geometric composition, practical tech lighting, scale shots for awe",
        "forbidden": "Warm candlelight, organic textures, period costumes, handheld jitter except in chaos sequences",
        "check": "Does this frame convey advanced technology and ordered world? If it looks medieval or naturalistic, FAILED.",
    },
    "whodunnit_drama": {
        "display": "Whodunnit / Period Drama",
        "lighting": "Motivated naturalistic. Window light, fireplace, practical lamps. Soft fill ONLY where a real source would create it. No unmotivated fill — shadows exist in real rooms.",
        "color": "Warm amber interiors, cool exterior contrast. Desaturated shadows with rich jewel tones in props and costumes. Period-appropriate palette.",
        "camera_mood": "Slow deliberate moves. Favors OTS dialogue pairs. Close-ups on significant objects — hands, letters, clues. The camera notices what people overlook.",
        "pacing_mood": "Patient — let scenes breathe. Hold on reaction shots. Mystery rewards patience. An 8-second hold is not too long.",
        "emotional_standard": "Intrigue, intelligence, revelation building. The frame must reward careful watching — clues placed deliberately.",
        "required": "Motivated naturalistic lighting, clue placement in frame, patient pace, objects as important as faces",
        "forbidden": "Neon lighting, fast MTV intercutting, sci-fi elements, unmotivated camera moves",
        "check": "Does this frame honor the intelligence of the mystery? Are there visual details worth noticing?",
    },
    "action": {
        "display": "Action",
        "lighting": "Dynamic — high-key base but motivated chaos. Explosions, dust-filtered sunlight, muzzle flash as accents. High contrast with crushed blacks.",
        "color": "Crushed blacks, high contrast. Golden-hour orange for hero moments. Adrenaline teal in shadows. High saturation.",
        "camera_mood": "Handheld in fights — controlled chaos, not random jitter. Crash zooms for impact. Low-angle for heroes (power). Aerial for scale. The camera feels the impact.",
        "pacing_mood": "Rapid intercutting during action. Brief HOLDS after impact — let the weight land. Setup → action → impact → reaction rhythm.",
        "emotional_standard": "Physical urgency, stakes, momentum. The frame should have kinetic energy even when still. Impact must be readable.",
        "required": "Kinetic energy in frame, spatial clarity despite chaos, impact readable, hero power conveyed",
        "forbidden": "Static talking-head compositions, soft diffused lighting during action, leisurely holds mid-fight",
        "check": "Does this frame have physical urgency? Does the viewer feel tension? If they feel nothing, FAILED.",
    },
    "comedy": {
        "display": "Comedy",
        "lighting": "Bright, even fill. No mysterious shadows — comedy needs visibility. Faces fully lit. The audience needs to see the expression to laugh.",
        "color": "Warm cheerful tones. Saturated. No desaturated noir aesthetics. Color supports the joke, not undermines it.",
        "camera_mood": "Wider than drama — physical comedy needs body in frame. Eye-level mostly. Steady — the joke is in the action, not the camera. Room for full-body performance.",
        "pacing_mood": "Hold after punchline — the pause IS the comedy. Setup-pause-punchline rhythm. Don't cut nervously.",
        "emotional_standard": "Absurdity, timing, surprise. The frame supports the joke. Wider shots for physical comedy. The camera is in on the gag.",
        "required": "Adequate light to see the joke, space for physical performance, steady camera, punchline room",
        "forbidden": "Dark low-key shadows that swallow expressions, tight claustrophobic framing during physical gags",
        "check": "Does this frame have enough light and space to see what's funny? Darkness kills comedy.",
    },
    "fight_broadcast": {
        "display": "Fight / Combat Sports",
        "lighting": "Arena overhead rigs. Hard directional from above. High-key overall with deep shadows in corners. Fighter faces lit for identification.",
        "color": "Arena colors — whatever the venue uses. High contrast. Team/fighter color separation important for viewer tracking.",
        "camera_mood": "Multi-angle kinetic coverage. Impact shots from ringside. Fighter close-ups for drama. Upper camera for spatial geometry. Slow-motion replays for key moments.",
        "pacing_mood": "Fast cuts during exchanges. Hold on standoffs and drama. Round structure dictates rhythm — action bursts with recovery.",
        "emotional_standard": "Physical dominance, momentum shifts, crowd energy. The fight must be readable — viewer tracks who is winning.",
        "required": "Ring/cage spatial clarity, both fighters visible in wide, impact readable, crowd energy present",
        "forbidden": "Losing fighters in frame, blocking ring geometry, confusion about spatial positions",
        "check": "Can you read the fight? Spatial clarity is NON-NEGOTIABLE for combat sports.",
    },
    "sports_game": {
        "display": "Sports / Game",
        "lighting": "Stadium floods. Even field illumination. Consistent across all shots. Natural sports venue light.",
        "color": "Natural stadium light. Team color separation essential. No artificial mood grading — keep it broadcast-clean.",
        "camera_mood": "Wide for gameplay. Tight on player faces for drama. Aerial for team movement. Follow the ball/puck/action object.",
        "pacing_mood": "Follow play rhythm. Hold on key plays. Cut to reactions between plays. Scoreboard context inserts.",
        "emotional_standard": "Competition, teamwork, key moments. The game is the story. Viewer must always know the score and stakes.",
        "required": "Field visibility, action tracking, team identification, scoreboard context",
        "forbidden": "Unmotivated dramatic color grading, obscuring field action, losing the ball",
        "check": "Can you follow the game clearly? Is the sports context unmistakable?",
    },
    "comedy_special": {
        "display": "Stand-up / Sketch Comedy",
        "lighting": "Stage spotlight on performer. Audience in darkness. Clean professional stage lighting — spot on comedian, house dark.",
        "color": "Stage lighting warmth acceptable. Consistent with live venue. No dramatic shifts mid-set.",
        "camera_mood": "Three-camera performance coverage. Wide for room. Medium for delivery. Tight for connection moments and reactions.",
        "pacing_mood": "Hold for laughs. Never cut mid-punchline. Setup-pause-punchline timing sacred. Wide re-establishes between bits.",
        "emotional_standard": "Timing is everything. The pause before the punchline is the most valuable real estate in the frame.",
        "required": "Performer in light, stage geography clear, audience presence felt, punchline timing honored",
        "forbidden": "Dark horror atmosphere, jitter, cutting on the laugh",
        "check": "Is the comedian clearly the star? Does the framing serve the performance timing?",
    },
    "podcast": {
        "display": "Podcast / Interview",
        "lighting": "Soft intimate studio three-point lighting. Professional and warm. Consistent across speakers — no dramatic shifts.",
        "color": "Warm studio tones. Consistent between speakers. No dramatic mood shifts between cuts.",
        "camera_mood": "Three-camera studio: wide two-shot, medium singles. Clean, professional. Minimal movement.",
        "pacing_mood": "Hold on speaker. Cut to reaction. Don't cut mid-sentence. Respect the conversation rhythm.",
        "emotional_standard": "Authenticity, conversation flow, knowledge exchange. The subject is the content.",
        "required": "Professional studio feel, clear speaker framing, listener reactions, eye-line to partner or camera",
        "forbidden": "Cinematic drama moves, dark low-key lighting, film noir atmosphere in a chat show",
        "check": "Does this look like a professional conversation? Would it air on a talk show without adjustment?",
    },
    # Default / drama fallback
    "_default": {
        "display": "Drama",
        "lighting": "Motivated lighting appropriate to the setting and time of day.",
        "color": "Naturalistic color grade. No extreme stylization unless story requires.",
        "camera_mood": "Compositionally motivated camera work serving character and story.",
        "pacing_mood": "Shot length appropriate to emotional content.",
        "emotional_standard": "Story and character drive all visual decisions.",
        "required": "Clarity, motivation, visual storytelling serving the narrative",
        "forbidden": "Unmotivated chaos, composition that confuses the viewer",
        "check": "Does this shot serve the story and reveal something about character?",
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# ARC POSITION CRITERIA
# Per narrative arc position, what must the shot visually accomplish?
# ═══════════════════════════════════════════════════════════════════════════════

ARC_CRITERIA: Dict[str, Dict[str, str]] = {
    "ESTABLISH": {
        "obligation": "This is the OPENING shot. It must DECLARE the scene's visual law — the room, the tone, the emotional baseline.",
        "camera_expectation": "Wide/establishing framing preferred. Camera shows environmental context BEFORE tightening on characters. Deep depth of field reveals full space.",
        "composition_expectation": "Horizon line used deliberately. Depth layers visible (foreground/midground/background). Location architecture fully readable. Viewer understands WHERE we are.",
        "performance_expectation": "Characters entering or arriving — calm, open presence. No extreme emotion yet. The scene is being introduced, not climaxed.",
        "lighting_expectation": "Sets the lighting BASELINE for the entire scene. This color temperature and direction are the LAW for all subsequent shots in this chain.",
        "chain_responsibility": "What this shot declares, the rest of the scene must carry. If lighting is warm amber here, it must stay warm amber. If room is a kitchen, it stays a kitchen.",
        "failure_signs": "Tight close-up with no spatial context, extreme emotion before establishing, location ambiguous or unreadable, lighting baseline not set",
        "verdict_question": "Does this shot answer: WHERE are we, and WHAT is the emotional atmosphere of this scene?",
    },
    "ESCALATE": {
        "obligation": "This MIDDLE shot must CARRY what the opening declared and RAISE the emotional stakes.",
        "camera_expectation": "Tighter than establishing — camera has moved closer to characters. But room architecture still RECOGNIZABLE as the same location.",
        "composition_expectation": "Characters more dominant. Environment secondary but SAME environment. We haven't teleported rooms.",
        "performance_expectation": "Emotional intensity increasing. Body language showing tension, urgency, conflict, or engagement. Stakes are higher than in the ESTABLISH shot.",
        "lighting_expectation": "MUST MATCH the lighting established in ESTABLISH shot. Same color temperature, same primary source direction, same quality (hard/soft).",
        "chain_responsibility": "Carries the chain forward. Emotional temperature HIGHER than opening. Same room. Same lighting. Different intensity.",
        "failure_signs": "Different room visible, lighting temperature changed without story reason, character teleported, lower energy than establishing shot",
        "verdict_question": "Is the SAME room visible from the ESTABLISH shot? Is emotional temperature HIGHER? If not, ESCALATE has failed.",
    },
    "PIVOT": {
        "obligation": "This is the TURNING POINT. Something must visibly SHIFT in this frame — a revelation, decision, confrontation, or reaction.",
        "camera_expectation": "Can shift to a tighter or unusual angle to mark the change. A motivated camera move can emphasize the pivot. Reaction framing acceptable.",
        "composition_expectation": "Reaction shot composition acceptable — tight face to catch the shift. Or unusual angle to mark the pivot moment as different.",
        "performance_expectation": "Visible CHANGE in the character — surprise, revelation, decision, confrontation. Something happened and the character must SHOW it.",
        "lighting_expectation": "Room still same location. Atmospheric mood CAN shift slightly — shadow crossing face, light quality changing — but must be motivated.",
        "chain_responsibility": "The turning point. Everything before this shot led here. Everything after will be different. Must be legible as a CHANGE moment.",
        "failure_signs": "Shot continues exactly as ESCALATE with zero visible change or reaction, static unmotivated framing, nothing different from previous shots",
        "verdict_question": "Is there a visible, readable CHANGE or REACTION happening in this shot? If nothing shifts, PIVOT has failed.",
    },
    "RESOLVE": {
        "obligation": "This CLOSING shot must RELEASE tension and bring the emotional beat to rest.",
        "camera_expectation": "Can widen slightly as a closing gesture — pulling back = emotional release. Camera movement, if any, retreating or settling.",
        "composition_expectation": "Characters settling, departing, or in final pose. Sense of visual CLOSURE. The story beat has landed.",
        "performance_expectation": "Emotional temperature LOWER than PIVOT. Resolution, acceptance, or finality in body language. The scene is arriving somewhere.",
        "lighting_expectation": "Room holds — same lighting as ESTABLISH. Scene ends in the same visual world it began. Consistency completes the arc.",
        "chain_responsibility": "Closes the chain. Prepares for scene release. After this shot, the room lock releases and the next scene can begin fresh.",
        "failure_signs": "Continued escalation with no closure, characters still in active conflict with no resolution, camera still pressing in with no retreat",
        "verdict_question": "Does this shot feel like an ENDING? Does visual energy decrease? Is there closure? If the scene still feels mid-action, RESOLVE has failed.",
    },
    # Fallback for unknown arc positions
    "_default": {
        "obligation": "This shot serves the scene's narrative. It must contribute to the visual story.",
        "camera_expectation": "Camera work motivated by story content.",
        "composition_expectation": "Subject clear. Context readable.",
        "performance_expectation": "Character action consistent with beat description.",
        "lighting_expectation": "Lighting consistent with scene baseline.",
        "chain_responsibility": "Carries the visual chain forward.",
        "failure_signs": "Shot disconnected from narrative, technical failures",
        "verdict_question": "Does this shot serve the story and carry the chain?",
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# DOCTRINE MATRIX OVERRIDES
# Special rules for genre × production_type combinations that need extra guidance
# beyond what the two base criteria provide individually.
# Key: (production_type, genre_id) — both lowercase, use "_default" for fallback.
# ═══════════════════════════════════════════════════════════════════════════════

MATRIX_OVERRIDES: Dict[tuple, Dict[str, str]] = {
    ("podcast", "horror"): {
        "special_note": "HORROR PODCAST: Intimate studio framing (podcast format) with horror atmospheric lighting (genre). Eye-level tight framing with horror color palette. Host is subject — no dutch angles unless supporting a horror storytelling beat. Dialogue continuity is paramount (podcast format) but with low-key mood lighting (horror genre).",
        "lighting_priority": "Low-key studio: practical desk lamp as key, fill non-existent. Amber from sources only. Dark background. FACE fully visible despite dark mood.",
        "camera_priority": "Studio format camera positions, but underexposed and moody. No dutch angles unless host is recounting horror content.",
    },
    ("podcast", "comedy"): {
        "special_note": "COMEDY PODCAST: Bright friendly studio environment. Wider framing to see reactions. Clean even lighting — comedy lives in visible expressions. Both hosts must be framed with space for physical reactions.",
        "lighting_priority": "Bright, even, warm. No dark corners. Faces fully lit. The laugh needs to be visible.",
        "camera_priority": "Studio format but slightly wider to capture double-takes and physical comedy reactions.",
    },
    ("fight_broadcast", "action"): {
        "special_note": "COMBAT ACTION BROADCAST: Fight broadcast format amplified with cinematic action grammar. Kinetic multi-camera with crash zooms and impact emphasis. Ring/cage geography mandatory (fight format) plus action genre's kinetic energy and impact weight.",
        "lighting_priority": "Arena rigs plus dynamic high-contrast action lighting. Explosions/flashes acceptable for dramatic moments.",
        "camera_priority": "Fight broadcast positions PLUS action grammar: low angle for hero fighter, crash zoom on decisive blow, aerial for spatial control.",
    },
    ("sports_game", "action"): {
        "special_note": "ACTION SPORTS BROADCAST: Traditional sports coverage elevated with action genre energy. Key plays get cinematic treatment. Standard coverage during play, action grammar for highlight moments.",
        "lighting_priority": "Stadium floods (sports standard) but key play moments can heighten contrast.",
        "camera_priority": "Sports coverage base with action genre close-ups and impact emphasis on decisive moments.",
    },
    ("music_video", "horror"): {
        "special_note": "HORROR MUSIC VIDEO: Performance-driven (music video) with full horror atmospheric grammar. Artist is subject but horror visual language surrounds them. Rhythm-synced cuts but to horror imagery. Dark, stylized, disturbing beauty.",
        "lighting_priority": "Full horror low-key with artist as the single illuminated subject in darkness. Dramatic, iconic.",
        "camera_priority": "Music video's expressive camera (dramatic moves, slow-motion) but horror framing (negative space, dutch, isolation).",
    },
    ("music_video", "action"): {
        "special_note": "ACTION MUSIC VIDEO: Performance energy synced to music tempo with action grammar. Fast cuts matching BPM. Physical energy in every frame. Artist dominates but action grammar surrounds.",
        "lighting_priority": "High-contrast action lighting. Dynamic. Dramatic. High energy.",
        "camera_priority": "Kinetic music video moves synced to music plus action genre crash zooms and impact shots.",
    },
    ("bumper", "horror"): {
        "special_note": "HORROR BUMPER: Maximum impact in minimum time. Every frame iconically horror. Dark, striking, graphic. The horror brand identity in 15 seconds.",
        "lighting_priority": "Ultra-high-contrast horror single-source. Iconic silhouette or single illuminated element.",
        "camera_priority": "Graphic impact composition every shot. No establishing — pure impact.",
    },
    ("movie", "fight_broadcast"): {
        "special_note": "CINEMATIC FIGHT SCENE: Combat shot with full cinematic grammar. Handheld in action for chaos, but spatial geography maintained. Not broadcast coverage — this is a FILM fight sequence.",
        "lighting_priority": "Cinematic dynamic lighting. Not arena rigs — motivated dramatic sources.",
        "camera_priority": "Cinematic handheld fight coverage with match cuts and clear spatial geography. Not multi-camera broadcast.",
    },
    ("comedy_special", "podcast"): {
        "special_note": "TALK SHOW / LATE NIGHT: Hybrid of comedy special stage performance and podcast conversation. Stage framing with talk-show desk setup. Multiple cameras, audience present, host-guest dynamic.",
        "lighting_priority": "Stage lighting for host/desk area. Warm, professional, broadcast quality.",
        "camera_priority": "Wide for host+guest two-shot, medium singles, tight for punchline delivery.",
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — PROMPT BUILDERS
# ═══════════════════════════════════════════════════════════════════════════════

def _get_production_criteria(production_type: str) -> Dict[str, str]:
    """Get production type criteria, falling back to _default."""
    pt = (production_type or "movie").lower().strip()
    # Normalize aliases
    _aliases = {
        "film": "movie", "series": "movie", "episode": "movie", "tv": "movie",
        "show": "movie", "cinematic": "movie",
        "fight": "fight_broadcast", "combat": "fight_broadcast",
        "sports": "sports_game", "game": "sports_game", "sport": "sports_game",
        "commercial": "bumper", "ad": "bumper", "advertisement": "bumper",
        "music": "music_video", "mv": "music_video",
        "standup": "comedy_special", "stand_up": "comedy_special",
    }
    pt = _aliases.get(pt, pt)
    return PRODUCTION_CRITERIA.get(pt, PRODUCTION_CRITERIA["_default"])


def _get_genre_criteria(genre_id: str) -> Dict[str, str]:
    """Get genre DNA criteria, falling back to _default."""
    g = (genre_id or "").lower().strip()
    # Normalize aliases
    _aliases = {
        "whodunnit": "whodunnit_drama", "mystery": "whodunnit_drama",
        "period": "whodunnit_drama", "gothic": "whodunnit_drama",
        "drama": "_default", "thriller": "horror",
        "sci-fi": "sci_fi", "scifi": "sci_fi", "science_fiction": "sci_fi",
        "action_adventure": "action", "adventure": "action",
        "sitcom": "comedy", "romcom": "comedy",
        "boxing": "fight_broadcast", "mma": "fight_broadcast", "wrestling": "fight_broadcast",
        "basketball": "sports_game", "football": "sports_game", "soccer": "sports_game",
    }
    g = _aliases.get(g, g)
    return GENRE_CRITERIA.get(g, GENRE_CRITERIA["_default"])


def _get_arc_criteria(arc_position: str) -> Dict[str, str]:
    """Get arc position criteria, falling back to _default."""
    return ARC_CRITERIA.get(arc_position or "", ARC_CRITERIA["_default"])


def _get_matrix_override(production_type: str, genre_id: str) -> Optional[Dict[str, str]]:
    """Get matrix override for genre×production_type combination if one exists."""
    pt = (production_type or "movie").lower().strip()
    g = (genre_id or "").lower().strip()
    return MATRIX_OVERRIDES.get((pt, g))


def _build_criteria_block(
    genre_id: str,
    production_type: str,
    arc_position: str = "",
) -> str:
    """
    Build the combined criteria text block for inclusion in a Gemini prompt.
    Combines: production type + genre + arc + matrix overrides.
    """
    prod = _get_production_criteria(production_type)
    genre = _get_genre_criteria(genre_id)
    arc = _get_arc_criteria(arc_position)
    matrix = _get_matrix_override(production_type, genre_id)

    lines = []

    # --- Production Type ---
    lines.append(f"PRODUCTION FORMAT: {prod['display']}")
    lines.append(f"  Format rules: {prod['camera_format']}")
    lines.append(f"  Framing standard: {prod['framing']}")
    lines.append(f"  Cut grammar: {prod['cuts']}")
    lines.append(f"  REQUIRED: {prod['required']}")
    lines.append(f"  FORBIDDEN: {prod['forbidden']}")
    lines.append(f"  Format test: {prod['check']}")

    # --- Genre ---
    lines.append(f"\nGENRE VISUAL STANDARD: {genre['display']}")
    lines.append(f"  Lighting: {genre['lighting']}")
    lines.append(f"  Color palette: {genre['color']}")
    lines.append(f"  Camera mood: {genre['camera_mood']}")
    lines.append(f"  REQUIRED: {genre['required']}")
    lines.append(f"  FORBIDDEN: {genre['forbidden']}")
    lines.append(f"  Genre test: {genre['check']}")

    # --- Matrix Override (if exists) ---
    if matrix:
        lines.append(f"\nSPECIAL COMBINATION RULES ({prod['display']} × {genre['display']}):")
        lines.append(f"  {matrix['special_note']}")
        lines.append(f"  Lighting priority: {matrix.get('lighting_priority', '')}")
        lines.append(f"  Camera priority: {matrix.get('camera_priority', '')}")

    # --- Arc Position ---
    if arc_position and arc_position != "_default":
        lines.append(f"\nARC POSITION OBLIGATION: {arc_position}")
        lines.append(f"  Obligation: {arc['obligation']}")
        lines.append(f"  Camera expectation: {arc['camera_expectation']}")
        lines.append(f"  Performance expectation: {arc['performance_expectation']}")
        lines.append(f"  Lighting expectation: {arc['lighting_expectation']}")
        lines.append(f"  Chain responsibility: {arc['chain_responsibility']}")
        lines.append(f"  Failure signs: {arc['failure_signs']}")
        lines.append(f"  Verdict question: {arc['verdict_question']}")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — MAIN PROMPT GETTERS
# ═══════════════════════════════════════════════════════════════════════════════

def get_doctrine_prompt(
    shot: Dict[str, Any],
    genre_id: str = "",
    production_type: str = "movie",
) -> str:
    """
    Build the DOCTRINE LAYER block to append to VVO's analyze_full_video() prompt.

    This text is APPENDED to the existing technical VVO prompt so Gemini evaluates
    both dimensions (technical + cinematographic) in a single API call.

    Args:
        shot: Shot dict from shot_plan.json (must have _arc_position, shot_type, etc.)
        genre_id: Genre from story_bible or shot._genre_dna_profile (e.g. "horror", "sci_fi")
        production_type: Production format (e.g. "movie", "podcast", "fight_broadcast")

    Returns:
        String block to append to VVO prompt — asks for D8-D14 JSON fields.
    """
    arc_position = (shot.get("_arc_position") or "").strip()
    shot_type = (shot.get("shot_type") or "").lower()
    chars = shot.get("characters") or []
    has_dialogue = bool(shot.get("dialogue_text", "").strip())
    is_multi_char = len(chars) >= 2
    is_empty = len(chars) == 0

    # Atmosphere / soundscape context — read existing fields from shot (backward-compatible)
    _scene_atm   = (shot.get("_scene_atmosphere") or "").strip()
    _beat_atm    = (shot.get("_beat_atmosphere") or "").strip()
    _soundscape  = (shot.get("_soundscape_signature") or "").strip()
    _arc_carry   = (shot.get("_arc_carry_directive") or "").strip()
    _has_atm_ctx = any([_scene_atm, _beat_atm, _soundscape, _arc_carry])

    # Resolve genre from shot if not explicitly provided
    if not genre_id:
        genre_id = (shot.get("_genre_dna_profile") or shot.get("_genre_id") or "").lower()

    criteria_block = _build_criteria_block(genre_id, production_type, arc_position)

    # Build shot-type-specific filmmaking grammar notes
    grammar_notes = []
    if is_empty:
        grammar_notes.append("Empty room shot — NO human figures should be visible. Camera work should evoke environment and mood.")
    if has_dialogue and is_multi_char:
        grammar_notes.append("Multi-character dialogue shot — 180° rule applies. Check: are both characters' positions consistent with shot/reverse-shot grammar?")
    if has_dialogue and not is_multi_char:
        grammar_notes.append("Solo dialogue shot — character speaks to self or off-camera. Eye-line should be directed appropriately (not at camera unless intentional address).")
    if "ots" in shot_type:
        grammar_notes.append("Over-the-shoulder shot — listener shoulder should be in foreground. Speaker faces camera. This is ONE SIDE of the 180° axis.")
    if shot_type in ("close_up", "medium_close", "reaction"):
        grammar_notes.append("Face-centric shot — background should be bokeh/soft, face filling most of frame. Shot type should feel CLOSE, not medium or wide.")
    if shot_type in ("establishing", "wide"):
        grammar_notes.append("Wide/establishing shot — FULL room geography should be visible. Deep focus. Environmental storytelling. NOT a medium shot.")

    grammar_block = ""
    if grammar_notes:
        grammar_block = "\nSHOT-TYPE SPECIFIC RULES:\n" + "\n".join(f"  - {n}" for n in grammar_notes)

    # Build the arc fulfillment check question based on position
    arc_crit = _get_arc_criteria(arc_position)
    arc_check_q = arc_crit.get("verdict_question", "Does this shot serve its arc position?")

    # Genre-specific lighting ratio
    _lighting_ratio = GENRE_LIGHTING_RATIOS.get(
        (genre_id or "").lower(),
        GENRE_LIGHTING_RATIOS["_default"]
    )

    # Build atmosphere/soundscape context section (omitted entirely if no fields set on shot)
    if _has_atm_ctx:
        _atm_lines = ["\nSCENE INTENT CONTEXT:"]
        if _scene_atm:
            _atm_lines.append(f"  Scene Atmosphere: {_scene_atm}")
        if _beat_atm:
            _atm_lines.append(f"  Beat Atmosphere: {_beat_atm}")
        if _soundscape:
            _atm_lines.append(f"  Soundscape Signature: {_soundscape}")
        if _arc_carry:
            _atm_lines.append(f"  Arc Directive: {_arc_carry}")
        _atm_lines.append(
            "\n  Evaluate whether this shot's visual mood, lighting, and composition MATCH the declared "
            "atmosphere and soundscape intent. A technically perfect shot that contradicts the scene's "
            "mood intent should receive a lower filmmaker_grade."
        )
        _atm_lines.append(
            "\nD19. \"atmosphere_alignment\": \"aligned\" | \"partial_mismatch\" | \"contradicts_intent\"\n"
            "     Does the shot's visual mood (lighting, color, composition, energy) match the declared "
            "scene atmosphere and soundscape intent above?\n"
            "     aligned = shot mood matches declared atmosphere\n"
            "     partial_mismatch = minor deviation from declared intent\n"
            "     contradicts_intent = shot's mood directly opposes the declared atmosphere"
        )
        _atm_lines.append(
            "\nD20. \"atmosphere_verdict\": one sentence explaining whether mood/lighting/composition "
            "serves or undermines the declared scene atmosphere and soundscape."
        )
        _atmosphere_section = "\n".join(_atm_lines)
    else:
        _atmosphere_section = ""

    doctrine_block = f"""
--- FILMMAKER EVALUATION (Doctrine Layer V1.0) ---

You are also an experienced cinematographer and film director. In ADDITION to the technical checks above, evaluate this clip on the following CINEMATIC dimensions. Use the criteria below as your professional standard.

{criteria_block}{grammar_block}

GENRE LIGHTING STANDARD (key-to-fill ratio):
  Target ratio for {genre_id or 'this genre'}: {_lighting_ratio['ratio']}
  {_lighting_ratio['description']}

UNIVERSAL FILMMAKING GRAMMAR (applies to all shots):
  - Rule of Thirds: Subject should be placed at a meaningful compositional position (not always dead-center)
    PASS threshold: subject center within ~8% of frame's power points (1/3 and 2/3 divisions)
  - Headroom: Gap between top of subject's head and top frame edge
    PASS: 3%–15% of frame height. FAIL: no headroom (head cut off) or excessive (floating head)
  - Nose Room: Space in front of subject's gaze direction
    PASS: minimum 10% of frame width in gaze direction
  - Shot Motivation: Does the SHOT TYPE match the STORY MOMENT? (wide for establishing, tight for revelation, OTS for dialogue)
  - Lighting Consistency: Does the lighting temperature and direction match what was established for this scene?
  - Camera Motivation: If the camera moves, is there a STORY REASON for the move?
  - Rack Focus: If focus pulls during the clip, is it smooth (completing within ±2 frames of target)? Motivated?
{AI_ARTIFACT_CHECKLIST}
{BROADCAST_THRESHOLDS_PROMPT_BLOCK}

Please ADD these fields to your JSON response (alongside the technical fields already requested):

D8. "arc_fulfilled": true or false — {arc_check_q}
D9. "arc_verdict": one sentence explaining why arc position is or is not fulfilled.
D10. "genre_compliance": "matches" | "partial" | "violated" — Does lighting/color/camera meet {genre_id or 'the genre'} standards?
D11. "genre_verdict": one sentence on genre compliance (e.g. "Horror lighting standard met — shadows dominant.").
D12. "production_format_compliance": "correct" | "minor_deviation" | "wrong_format" — Does this shot match {production_type} conventions?
D13. "cinematography_scores": a nested JSON object with:
    "rule_of_thirds": 0.0-1.0 (1.0=excellent composition, 0.0=subject dead-center with no intent),
    "shot_motivation": 0.0-1.0 (1.0=shot type perfectly serves the moment, 0.0=wrong type entirely),
    "lighting_grammar": 0.0-1.0 (1.0=lighting fully correct for genre and scene, 0.0=completely wrong),
    "camera_motivation": 0.0-1.0 (1.0=every move is story-driven, 0.0=random unmotivated movement),
    "degree_180_rule": 1.0 (maintained) | 0.5 (ambiguous) | 0.0 (violated) | -1.0 (not_applicable),
    "eyeline_match": 1.0 (correct) | 0.5 (ambiguous) | 0.0 (wrong) | -1.0 (not_applicable)
D14. "filmmaker_grade": A, B, C, D, or F — your overall CINEMATOGRAPHER's grade:
    A = Visually excellent. Arc fulfilled, genre correct, grammar clean. Ready for theatrical release.
    B = Good cinematography. Minor issues. Storytelling effective. TV broadcast quality.
    C = Acceptable. Some grammar violations but functional. Would pass basic QA.
    D = Multiple cinematography failures. Pacing or composition broken. Reshoots recommended.
    F = Fundamental failure: wrong location, wrong arc, identity drift, wrong production format, or technical disaster.
D15. "grade_reason": one sentence explaining the filmmaker grade.
D16. "doctrine_issues": array of strings — specific filmmaking violations detected (empty array if none). Examples: "180_degree_rule_violated", "wrong_shot_type_for_arc", "lighting_mismatches_genre", "unmotivated_camera_move", "shot_too_wide_for_resolve", "no_arc_declare_in_establish".

D17. "ai_artifact_report": a nested JSON object with:
    "identity_morphing": true | false (face shape/tone shifts mid-clip),
    "temporal_flicker": true | false (background elements pulse/change unexpectedly),
    "texture_hallucination": true | false (objects appear/disappear without motivation),
    "physics_violation": true | false (impossible movement or object behavior),
    "face_lock_failure": true | false (face drifts/travels across frame unnaturally),
    "artifact_notes": "brief description of any detected artifacts, or empty string"

D18. "broadcast_qc": a nested JSON object evaluating against professional thresholds:
    "perceived_sharpness": "excellent" (≥85 VMAF-equivalent) | "acceptable" (≥75) | "soft" (<75, compression/blur visible),
    "color_consistency": "within_spec" (ΔE ≤2.0 estimated) | "minor_drift" (ΔE 2-5) | "significant_drift" (ΔE >5),
    "headroom_correct": true | false (3%-15% of frame height above head),
    "nose_room_correct": true | false (10%+ of frame width in gaze direction),
    "lighting_ratio_correct": true | false (matches {_lighting_ratio['ratio']} target for this genre),
    "lip_sync_appears_synced": true | false | "not_applicable" (mouth movement aligns with expected audio timing),
    "qc_notes": "brief note on any broadcast standard violations"
{_atmosphere_section}"""
    return doctrine_block


def get_chain_doctrine_prompt(
    prev_shot: Dict[str, Any],
    curr_shot: Dict[str, Any],
    genre_id: str = "",
    production_type: str = "movie",
) -> str:
    """
    Build the CHAIN DOCTRINE LAYER to append to VVO's analyze_chain_transition() prompt.

    Adds filmmaking grammar checks ON TOP of the technical continuity checks:
    - Screen direction (exits right → enters left)
    - Lighting temperature consistency
    - Color grade drift
    - Spatial geography maintenance
    - Cut grammar classification

    Args:
        prev_shot: Previous shot dict
        curr_shot: Current shot dict
        genre_id: Genre DNA for this chain
        production_type: Production format

    Returns:
        String block to append to VVO chain transition prompt.
    """
    if not genre_id:
        genre_id = (
            curr_shot.get("_genre_dna_profile") or
            prev_shot.get("_genre_dna_profile") or
            ""
        ).lower()

    genre = _get_genre_criteria(genre_id)
    prod = _get_production_criteria(production_type)
    prev_arc = (prev_shot.get("_arc_position") or "").strip()
    curr_arc = (curr_shot.get("_arc_position") or "").strip()

    # Determine chain type for additional context
    chain_type_note = ""
    if prev_arc == "ESTABLISH" and curr_arc == "ESCALATE":
        chain_type_note = "This is an ESTABLISH → ESCALATE transition. The current shot must maintain the room and lighting declared by the previous shot while raising stakes."
    elif curr_arc == "PIVOT":
        chain_type_note = "This is a transition INTO the PIVOT beat. A visible shift should be apparent in the current clip's opening moment."
    elif curr_arc == "RESOLVE":
        chain_type_note = "This is the final chain transition. The current shot should feel like closure — reduced tension, settling energy."
    elif prev_arc == curr_arc:
        chain_type_note = f"Both shots share {curr_arc} arc position — this is a continuation cut within the same beat. Continuity is paramount."

    prev_type = (prev_shot.get("shot_type") or "unknown").lower()
    curr_type = (curr_shot.get("shot_type") or "unknown").lower()
    is_shot_reverse = ("ots" in prev_type and "ots" in curr_type)
    is_wide_to_tight = (
        prev_type in ("establishing", "wide") and
        curr_type in ("medium", "medium_close", "close_up", "ots")
    )

    grammar_context = []
    if is_shot_reverse:
        grammar_context.append("Shot/Reverse-Shot pair: The 180° axis must be maintained across both clips. Characters should appear on OPPOSITE SIDES of frame between shots.")
    if is_wide_to_tight:
        grammar_context.append("Wide-to-tight progression: Current shot should show the SAME room as previous, just closer. This is a standard coverage move — same lighting, same room.")
    if (prev_shot.get("characters") or []) != (curr_shot.get("characters") or []):
        grammar_context.append("Character set changes: Normal for reaction cuts or new character introductions. Check that the characters who ARE shared maintain costume/position continuity.")

    grammar_context_str = ""
    if grammar_context:
        grammar_context_str = "\nCHAIN GRAMMAR CONTEXT:\n" + "\n".join(f"  - {n}" for n in grammar_context)

    return f"""
--- CHAIN FILMMAKING GRAMMAR (Doctrine Layer V1.0) ---

Production format: {prod['display']} | Genre: {genre['display']}
{f"Arc transition note: {chain_type_note}" if chain_type_note else ""}
{grammar_context_str}

Genre color/lighting standard for this chain: {genre['lighting']} | Color: {genre['color']}

Please ADD these fields to your chain transition JSON response:

DC1. "screen_direction_correct": true | false | "not_applicable"
     If a character EXITS FRAME in Video 1 (moves left/right to edge), do they ENTER from the OPPOSITE side in Video 2?
     (exits frame-right → enters frame-left = CORRECT. exits right → enters right = VIOLATED)
     "not_applicable" if no character exits the frame boundary.

DC2. "lighting_temperature_match": true | false
     Is the light color temperature consistent between the end of Video 1 and the start of Video 2?
     (warm amber → cool blue = MISMATCH unless story-motivated)

DC3. "color_grade_drift": true | false
     Does the overall color grading (saturation, contrast, overall tone) drift noticeably between clips?
     Small variation is acceptable. Jarring shift is a failure.

DC4. "spatial_geography_maintained": true | false
     Can the viewer maintain a mental map of the space across both clips?
     Does the room feel like the SAME room? Or did the environment teleport?

DC5. "cut_grammar": "match_cut" | "hard_cut" | "motivated_cut" | "jarring_cut"
     Classify the type of cut this chain creates:
     - match_cut: action or visual element matches across the cut (most elegant)
     - motivated_cut: new information or perspective justified the cut (standard)
     - hard_cut: abrupt but acceptable — new scene or beat (normal)
     - jarring_cut: cut breaks spatial or temporal logic without story justification (FAIL)

DC6. "chain_filmmaker_grade": A, B, C, D, or F — cinematographer's grade for this CHAIN TRANSITION:
     A = Perfect chain. Screen direction clean, lighting matches, spatial geography continuous, grammar impeccable.
     B = Good chain. Minor issues but cut is acceptably clean.
     C = Noticeable grammar issue — viewer might notice but won't be lost.
     D = Multiple grammar failures — viewer disoriented.
     F = Spatial logic broken. Viewer would be confused about location or character identity.

DC7. "chain_grade_reason": one sentence explaining the chain filmmaker grade.
DC8. "chain_doctrine_issues": array of specific chain grammar violations detected (empty if none).
     Examples: "screen_direction_violated", "lighting_temperature_mismatch", "spatial_geography_broken", "jarring_cut_unmotivated", "color_grade_drift"

DC9. "chain_color_delta": estimated ΔE color shift between end of Video 1 and start of Video 2:
     "within_spec" (ΔE ≤3.0 — acceptable chain transition), "minor_drift" (ΔE 3-5), "significant_drift" (ΔE >5.0 = FAIL)
     Threshold context: Same character skin tone should stay within ΔE ≤1.5; location color within ΔE ≤2.0.

DC10. "chain_ssim_estimate": estimated structural similarity at the cut point:
      "continuous" (scene appears spatially continuous, SSIM ≥0.90 estimated),
      "acceptable_cut" (visible cut but spatially coherent, SSIM 0.70-0.89),
      "discontinuous" (jarring spatial break, SSIM <0.70 estimated — FAIL)

DC11. "ai_chain_artifacts": nested object for AI-specific chain artifacts:
      "identity_consistency": "maintained" | "minor_drift" | "significant_drift" (character face consistency clip-to-clip),
      "costume_consistency": "maintained" | "changed" (wardrobe continuity),
      "flicker_at_cut": true | false (temporal flicker immediately at the cut point)
"""


def get_scene_stitch_doctrine_prompt(
    scene_shots: list,
    genre_id: str = "",
    production_type: str = "movie",
) -> str:
    """
    Build the SCENE-LEVEL DOCTRINE to append to VVO's analyze_scene_stitch() prompt.

    Evaluates the assembled scene as a DIRECTOR would — does the full sequence
    embody the genre DNA and production format? Does the arc (ESTABLISH→RESOLVE)
    land as a complete narrative unit?

    Args:
        scene_shots: List of shot dicts for this scene
        genre_id: Genre DNA
        production_type: Production format

    Returns:
        String block to append to VVO scene stitch prompt.
    """
    if not genre_id:
        for s in scene_shots:
            cand = s.get("_genre_dna_profile") or s.get("_genre_id") or ""
            if cand:
                genre_id = cand.lower()
                break

    genre = _get_genre_criteria(genre_id)
    prod = _get_production_criteria(production_type)

    # Build arc summary from scene shots
    arc_sequence = [s.get("_arc_position", "?") for s in scene_shots if s.get("_arc_position")]
    arc_summary = " → ".join(arc_sequence) if arc_sequence else "arc positions not available"

    scene_id = scene_shots[0].get("shot_id", "?")[:3] if scene_shots else "?"
    has_dialogue = any(s.get("dialogue_text") for s in scene_shots)
    char_counts = [len(s.get("characters") or []) for s in scene_shots]
    max_chars = max(char_counts) if char_counts else 0

    special_context = []
    if has_dialogue:
        special_context.append("Scene contains dialogue — check: does the shot/reverse-shot coverage maintain 180° rule across all dialogue shots?")
    if max_chars >= 2:
        special_context.append("Multi-character scene — check: do screen positions (frame-left/right) stay consistent for each character throughout the scene?")
    if "podcast" in (production_type or "").lower():
        special_context.append("Podcast format — check: are speaker transitions clean? Is there always a clear single active speaker per shot?")
    if "fight" in (production_type or "").lower():
        special_context.append("Fight broadcast — check: is ring/cage geography always readable? Are both fighters identifiable?")

    special_context_str = ""
    if special_context:
        special_context_str = "\nSCENE-SPECIFIC CHECKS:\n" + "\n".join(f"  - {n}" for n in special_context)

    return f"""
--- SCENE-LEVEL FILMMAKER EVALUATION (Doctrine Layer V1.0) ---

Production format: {prod['display']} | Genre: {genre['display']}
Scene arc sequence: {arc_summary}
{special_context_str}

SCENE-LEVEL CINEMATOGRAPHY STANDARD:
  Format: {prod['camera_format']}
  Genre lighting: {genre['lighting']}
  Genre color: {genre['color']}
  Genre pacing: {genre['pacing_mood']}
  Scene format test: {prod['check']}
  Genre test: {genre['check']}

Please ADD these fields to your scene stitch JSON response:

DS1. "arc_sequence_coherent": true | false
     Does the scene follow a coherent emotional arc? Does the ESTABLISH shot declare correctly?
     Does the RESOLVE shot provide genuine closure?
     Describe what arc structure you observed.
     "arc_sequence_note": one sentence describing the arc you observed.

DS2. "genre_maintained_across_scene": true | false
     Does the genre visual standard ({genre['display']}) hold consistently across all shots?
     Key check: Does lighting stay consistent with genre requirements? Does color grade drift?

DS3. "production_format_coherent": true | false
     Does the assembled scene feel like it belongs to {prod['display']} format?
     Or do individual shots look like they're from different production formats?

DS4. "180_rule_scene_verdict": "maintained" | "minor_violations" | "major_violations" | "not_applicable"
     Across all dialogue/multi-character shots, is the 180° axis consistently respected?

DS5. "scene_filmmaker_grade": A, B, C, D, or F — director's grade for the ASSEMBLED SCENE:
     A = Cinematic excellence. Arc clear, genre consistent, grammar impeccable. Festival-worthy.
     B = Strong filmmaking. Minor issues. TV broadcast quality. Effective storytelling.
     C = Functional. Some inconsistencies but story survives. Needs polish.
     D = Multiple failures. Arc unclear, genre inconsistent, or grammar broken. Significant reshoots needed.
     F = Scene fails as film. Arc absent, genre wrong, or so many grammar violations the story is lost.

DS6. "scene_grade_reason": 2-3 sentence director's note on what works, what fails, and the biggest fix needed.

DS7. "scene_doctrine_issues": array of specific scene-level issues (empty if none).
     Examples: "arc_has_no_establish", "genre_lighting_inconsistent_across_shots", "180_rule_violated_in_dialogue",
     "screen_positions_drift_mid_scene", "format_inconsistency_some_shots_wrong_production_type"
"""


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — RESPONSE PARSER
# ═══════════════════════════════════════════════════════════════════════════════

def parse_doctrine_fields(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract doctrine-layer fields from a Gemini response JSON dict.
    Used by VVO to split technical vs doctrine fields from the combined response.

    Returns a dict with D8-D18 doctrine fields (per-shot analysis).
    Missing fields get safe defaults so callers can always access them.
    """
    cine = data.get("cinematography_scores") or {}
    artifact = data.get("ai_artifact_report") or {}
    qc = data.get("broadcast_qc") or {}

    return {
        # Arc compliance
        "arc_fulfilled": data.get("arc_fulfilled", None),
        "arc_verdict": data.get("arc_verdict", ""),

        # Genre compliance
        "genre_compliance": data.get("genre_compliance", "not_assessed"),
        "genre_verdict": data.get("genre_verdict", ""),

        # Production format compliance
        "production_format_compliance": data.get("production_format_compliance", "not_assessed"),

        # Cinematography grammar scores (0.0-1.0 except 180/eyeline which use -1=N/A)
        "cinematography_scores": {
            "rule_of_thirds": float(cine.get("rule_of_thirds", -1.0)),
            "shot_motivation": float(cine.get("shot_motivation", -1.0)),
            "lighting_grammar": float(cine.get("lighting_grammar", -1.0)),
            "camera_motivation": float(cine.get("camera_motivation", -1.0)),
            "degree_180_rule": float(cine.get("degree_180_rule", -1.0)),
            "eyeline_match": float(cine.get("eyeline_match", -1.0)),
        },

        # Filmmaker grade
        "filmmaker_grade": data.get("filmmaker_grade", ""),
        "grade_reason": data.get("grade_reason", ""),

        # Violations list
        "doctrine_issues": data.get("doctrine_issues") or [],

        # D17 — AI artifact detection (V4.1 broadcast standards)
        "ai_artifact_report": {
            "identity_morphing": artifact.get("identity_morphing", False),
            "temporal_flicker": artifact.get("temporal_flicker", False),
            "texture_hallucination": artifact.get("texture_hallucination", False),
            "physics_violation": artifact.get("physics_violation", False),
            "face_lock_failure": artifact.get("face_lock_failure", False),
            "artifact_notes": artifact.get("artifact_notes", ""),
            # Computed: any artifact detected
            "any_artifact": any([
                artifact.get("identity_morphing", False),
                artifact.get("temporal_flicker", False),
                artifact.get("texture_hallucination", False),
                artifact.get("physics_violation", False),
                artifact.get("face_lock_failure", False),
            ]),
        },

        # D18 — Broadcast QC (V4.1 Netflix/Amazon standards)
        "broadcast_qc": {
            "perceived_sharpness": qc.get("perceived_sharpness", "not_assessed"),
            "color_consistency": qc.get("color_consistency", "not_assessed"),
            "headroom_correct": qc.get("headroom_correct", None),
            "nose_room_correct": qc.get("nose_room_correct", None),
            "lighting_ratio_correct": qc.get("lighting_ratio_correct", None),
            "lip_sync_appears_synced": qc.get("lip_sync_appears_synced", "not_applicable"),
            "qc_notes": qc.get("qc_notes", ""),
            # Computed: broadcast ready
            "broadcast_ready": (
                qc.get("perceived_sharpness") in ("excellent", "acceptable", "not_assessed") and
                qc.get("color_consistency") in ("within_spec", "minor_drift", "not_assessed")
            ),
        },

        # D19-D20 — Atmosphere / Soundscape alignment (present only when shot has intent fields)
        "atmosphere_alignment": data.get("atmosphere_alignment", "not_assessed"),
        "atmosphere_verdict": data.get("atmosphere_verdict", ""),
    }


def parse_chain_doctrine_fields(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract chain doctrine fields (DC1-DC11) from a Gemini chain transition response.
    Used by VVO's analyze_chain_transition() to split technical from doctrine fields.
    """
    chain_art = data.get("ai_chain_artifacts") or {}
    return {
        # DC1-DC8: Core chain filmmaking grammar
        "screen_direction_correct": data.get("screen_direction_correct", None),
        "lighting_temperature_match": data.get("lighting_temperature_match", None),
        "color_grade_drift": data.get("color_grade_drift", None),
        "spatial_geography_maintained": data.get("spatial_geography_maintained", None),
        "cut_grammar": data.get("cut_grammar", ""),
        "chain_filmmaker_grade": data.get("chain_filmmaker_grade", ""),
        "chain_grade_reason": data.get("chain_grade_reason", ""),
        "chain_doctrine_issues": data.get("chain_doctrine_issues") or [],

        # DC9: Color delta at cut (broadcast standard ΔE)
        "chain_color_delta": data.get("chain_color_delta", "not_assessed"),

        # DC10: SSIM estimate at cut
        "chain_ssim_estimate": data.get("chain_ssim_estimate", "not_assessed"),

        # DC11: AI chain artifacts
        "ai_chain_artifacts": {
            "identity_consistency": chain_art.get("identity_consistency", "not_assessed"),
            "costume_consistency": chain_art.get("costume_consistency", "not_assessed"),
            "flicker_at_cut": chain_art.get("flicker_at_cut", False),
        },
    }


def parse_scene_doctrine_fields(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract scene-level doctrine fields (DS1-DS7) from a Gemini scene stitch response.
    Used by VVO's analyze_scene_stitch().
    """
    return {
        "arc_sequence_coherent": data.get("arc_sequence_coherent", None),
        "arc_sequence_note": data.get("arc_sequence_note", ""),
        "genre_maintained_across_scene": data.get("genre_maintained_across_scene", None),
        "production_format_coherent": data.get("production_format_coherent", None),
        "degree_180_rule_scene_verdict": data.get("180_rule_scene_verdict", "not_assessed"),
        "scene_filmmaker_grade": data.get("scene_filmmaker_grade", ""),
        "scene_grade_reason": data.get("scene_grade_reason", ""),
        "scene_doctrine_issues": data.get("scene_doctrine_issues") or [],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5 — UTILITY: RESOLVE GENRE AND PRODUCTION TYPE FROM SHOT/BIBLE
# ═══════════════════════════════════════════════════════════════════════════════

def resolve_genre_and_production(
    shot: Dict[str, Any],
    story_bible: Optional[Dict[str, Any]] = None,
) -> tuple[str, str]:
    """
    Resolve genre_id and production_type from available context.
    Priority order:
      1. shot._genre_dna_profile (injected by network_intake.apply_genre_dna)
      2. story_bible.genre
      3. story_bible.production_type
      4. Defaults: ("", "movie")

    Returns: (genre_id, production_type)
    """
    genre_id = ""
    production_type = "movie"

    # From shot
    genre_id = genre_id or (shot.get("_genre_dna_profile") or "").lower().strip()
    genre_id = genre_id or (shot.get("_genre_id") or "").lower().strip()

    # From story bible
    if story_bible:
        genre_id = genre_id or (story_bible.get("genre") or "").lower().strip()
        production_type = (story_bible.get("production_type") or "movie").lower().strip() or "movie"
        # Network intake may also set production_type on the bible
        production_type = (story_bible.get("format") or production_type).lower().strip() or "movie"

    return genre_id, production_type


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 6 — SCORING UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════

def grade_to_score(grade: str) -> float:
    """Convert filmmaker letter grade to 0.0-1.0 numeric score."""
    _MAP = {"A": 1.0, "B": 0.8, "C": 0.6, "D": 0.4, "F": 0.0}
    return _MAP.get((grade or "").strip().upper(), -1.0)


def compute_doctrine_health(doctrine_fields: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute an overall doctrine health summary from parse_doctrine_fields() output.

    Returns:
        {
            "doctrine_pass": bool,          # True if filmmaker_grade >= C and no hard fails
            "doctrine_score": float,        # 0.0-1.0 from filmmaker_grade
            "arc_pass": bool,
            "genre_pass": bool,
            "broadcast_ready": bool,        # Meets Netflix/Amazon broadcast standards
            "ai_artifact_detected": bool,   # Any AI generation artifact found
            "critical_violations": list,    # Issues warranting regen consideration
        }
    """
    grade = (doctrine_fields.get("filmmaker_grade") or "").strip().upper()
    score = grade_to_score(grade)

    arc_pass = doctrine_fields.get("arc_fulfilled") is not False  # None = not assessed = pass
    genre_pass = doctrine_fields.get("genre_compliance") in ("matches", "partial", "not_assessed")

    # Broadcast readiness from QC fields
    qc = doctrine_fields.get("broadcast_qc") or {}
    broadcast_ready = qc.get("broadcast_ready", True)  # Default True if QC not assessed

    # AI artifact detection
    artifact = doctrine_fields.get("ai_artifact_report") or {}
    ai_artifact_detected = artifact.get("any_artifact", False)

    # Critical violations from doctrine_issues + AI artifacts
    blocking_patterns = {
        "wrong_production_format", "wrong_format",
        "wrong_arc", "no_arc_declare_in_establish",
        "180_degree_rule_violated",
        "spatial_geography_broken", "location_teleport",
    }
    all_issues = [i.lower() for i in (doctrine_fields.get("doctrine_issues") or [])]
    critical = [i for i in all_issues if any(p in i for p in blocking_patterns)]

    # Hard AI artifacts also count as critical
    if artifact.get("identity_morphing"):
        critical.append("ai_identity_morphing_detected")
    if artifact.get("texture_hallucination"):
        critical.append("ai_texture_hallucination_detected")
    if artifact.get("physics_violation"):
        critical.append("ai_physics_violation_detected")

    # Atmosphere contradiction counts as critical (shot actively opposes declared scene intent)
    if doctrine_fields.get("atmosphere_alignment") == "contradicts_intent":
        critical.append("atmosphere_contradicts_scene_intent")

    return {
        "doctrine_pass": grade in ("A", "B", "C") or grade == "",
        "doctrine_score": score,
        "arc_pass": arc_pass,
        "genre_pass": genre_pass,
        "broadcast_ready": broadcast_ready,
        "ai_artifact_detected": ai_artifact_detected,
        "critical_violations": critical,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 7 — SELF-TEST
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    print("=== vision_doctrine_prompts.py self-test ===\n")

    # Test 1: Criteria resolution
    prod = _get_production_criteria("podcast")
    genre = _get_genre_criteria("horror")
    matrix = _get_matrix_override("podcast", "horror")
    assert prod["display"] == "Podcast / Interview (Studio)", f"Wrong prod: {prod['display']}"
    assert genre["display"] == "Horror", f"Wrong genre: {genre['display']}"
    assert matrix is not None, "Matrix override for podcast×horror should exist"
    print("✅ Test 1 PASS: Criteria resolution + matrix override")

    # Test 2: Alias normalization
    prod2 = _get_production_criteria("film")
    assert prod2["display"] == PRODUCTION_CRITERIA["movie"]["display"], "film alias failed"
    genre2 = _get_genre_criteria("thriller")
    assert genre2["display"] == GENRE_CRITERIA["horror"]["display"], "thriller alias failed"
    print("✅ Test 2 PASS: Alias normalization")

    # Test 3: get_doctrine_prompt returns non-empty string with all key fields
    shot = {
        "shot_id": "001_M01",
        "shot_type": "establishing",
        "_arc_position": "ESTABLISH",
        "_beat_action": "Eleanor and Thomas arrive at the manor",
        "dialogue_text": "",
        "characters": ["Eleanor", "Thomas"],
        "_genre_dna_profile": "whodunnit_drama",
    }
    prompt = get_doctrine_prompt(shot, genre_id="whodunnit_drama", production_type="movie")
    assert "FILMMAKER EVALUATION" in prompt, "Missing doctrine header"
    assert "ESTABLISH" in prompt, "Missing arc position"
    assert "D8" in prompt, "Missing D8 field instruction"
    assert "filmmaker_grade" in prompt, "Missing grade instruction"
    assert "doctrine_issues" in prompt, "Missing doctrine_issues instruction"
    print("✅ Test 3 PASS: get_doctrine_prompt generates complete prompt")

    # Test 4: Chain doctrine prompt
    prev = {"shot_id": "001_M01", "_arc_position": "ESTABLISH", "shot_type": "wide",
            "characters": ["Eleanor"], "_genre_dna_profile": "horror"}
    curr = {"shot_id": "001_M02", "_arc_position": "ESCALATE", "shot_type": "medium",
            "characters": ["Eleanor"]}
    chain_p = get_chain_doctrine_prompt(prev, curr, genre_id="horror", production_type="movie")
    assert "screen_direction_correct" in chain_p, "Missing screen direction check"
    assert "chain_filmmaker_grade" in chain_p, "Missing chain grade"
    assert "ESTABLISH → ESCALATE" in chain_p, "Missing arc transition note"
    print("✅ Test 4 PASS: get_chain_doctrine_prompt generates complete chain prompt")

    # Test 5: Scene stitch doctrine
    shots = [
        {"shot_id": "001_M01", "_arc_position": "ESTABLISH", "characters": ["Eleanor"]},
        {"shot_id": "001_M02", "_arc_position": "ESCALATE", "characters": ["Eleanor"],
         "dialogue_text": "What happened here?"},
        {"shot_id": "001_M03", "_arc_position": "RESOLVE", "characters": ["Eleanor"]},
    ]
    stitch_p = get_scene_stitch_doctrine_prompt(shots, genre_id="whodunnit_drama", production_type="movie")
    assert "arc_sequence_coherent" in stitch_p, "Missing arc sequence check"
    assert "scene_filmmaker_grade" in stitch_p, "Missing scene grade"
    print("✅ Test 5 PASS: get_scene_stitch_doctrine_prompt generates complete scene prompt")

    # Test 6: parse_doctrine_fields handles partial data safely
    fake_data = {"filmmaker_grade": "B", "arc_fulfilled": True, "doctrine_issues": ["wrong_format"]}
    parsed = parse_doctrine_fields(fake_data)
    assert parsed["filmmaker_grade"] == "B", "Grade not parsed"
    assert parsed["doctrine_issues"] == ["wrong_format"], "Issues not parsed"
    assert parsed["cinematography_scores"]["rule_of_thirds"] == -1.0, "Default not set"
    print("✅ Test 6 PASS: parse_doctrine_fields handles partial data")

    # Test 7: resolve_genre_and_production
    shot_with_profile = {"_genre_dna_profile": "sci_fi"}
    bible = {"genre": "horror", "production_type": "podcast"}
    g, pt = resolve_genre_and_production(shot_with_profile, bible)
    assert g == "sci_fi", f"Shot profile should override bible genre: got {g}"
    assert pt == "podcast", f"Bible production_type should be used: got {pt}"
    print("✅ Test 7 PASS: resolve_genre_and_production priority order")

    # Test 8: grade_to_score + compute_doctrine_health
    assert grade_to_score("A") == 1.0
    assert grade_to_score("F") == 0.0
    assert grade_to_score("") == -1.0
    health = compute_doctrine_health({"filmmaker_grade": "D", "genre_compliance": "violated",
                                      "doctrine_issues": ["180_degree_rule_violated", "minor_color_drift"]})
    assert not health["doctrine_pass"], "Grade D should be fail"
    assert "180_degree_rule_violated" in health["critical_violations"]
    print("✅ Test 8 PASS: grade_to_score + compute_doctrine_health")

    # Test 9: atmosphere/soundscape context wiring
    # 9a: shot WITH atmosphere fields → section present in prompt + D19/D20 instructions
    shot_atm = {
        "shot_id": "001_M02",
        "shot_type": "medium",
        "_arc_position": "ESCALATE",
        "characters": ["Eleanor"],
        "_scene_atmosphere": "dust-filtered morning light, faded grandeur, professional tension",
        "_beat_atmosphere": "morning light through stained glass, dust sheets, dark chandelier",
        "_soundscape_signature": "low sustained string tension, minor key, slow tempo",
        "_arc_carry_directive": "ESCALATE: carry kitchen DNA, raise emotional stakes",
    }
    prompt_atm = get_doctrine_prompt(shot_atm, genre_id="whodunnit_drama", production_type="movie")
    assert "SCENE INTENT CONTEXT" in prompt_atm, "Atmosphere section missing when fields present"
    assert "dust-filtered morning light" in prompt_atm, "Scene atmosphere text missing"
    assert "low sustained string tension" in prompt_atm, "Soundscape text missing"
    assert "D19" in prompt_atm, "D19 atmosphere_alignment field missing"
    assert "D20" in prompt_atm, "D20 atmosphere_verdict field missing"
    assert "atmosphere_alignment" in prompt_atm, "atmosphere_alignment key missing"
    assert "contradicts_intent" in prompt_atm, "contradicts_intent option missing"

    # 9b: shot WITHOUT atmosphere fields → section omitted entirely
    shot_no_atm = {
        "shot_id": "001_M01",
        "shot_type": "establishing",
        "_arc_position": "ESTABLISH",
        "characters": ["Eleanor"],
    }
    prompt_no_atm = get_doctrine_prompt(shot_no_atm, genre_id="whodunnit_drama", production_type="movie")
    assert "SCENE INTENT CONTEXT" not in prompt_no_atm, "Atmosphere section should be absent when no fields set"
    assert "D19" not in prompt_no_atm, "D19 should be absent when no atmosphere fields"

    # 9c: parse_doctrine_fields returns atmosphere_alignment with safe default
    parsed_atm = parse_doctrine_fields({"atmosphere_alignment": "contradicts_intent", "atmosphere_verdict": "Bright cheerful lighting contradicts the declared dread atmosphere."})
    assert parsed_atm["atmosphere_alignment"] == "contradicts_intent", "atmosphere_alignment not parsed"
    assert "dread" in parsed_atm["atmosphere_verdict"], "atmosphere_verdict not parsed"
    parsed_no_atm = parse_doctrine_fields({})
    assert parsed_no_atm["atmosphere_alignment"] == "not_assessed", "Default atmosphere_alignment wrong"

    # 9d: compute_doctrine_health adds to critical_violations on contradicts_intent
    health_atm = compute_doctrine_health({"filmmaker_grade": "B", "atmosphere_alignment": "contradicts_intent"})
    assert "atmosphere_contradicts_scene_intent" in health_atm["critical_violations"], \
        "contradicts_intent should produce critical violation"
    health_aligned = compute_doctrine_health({"filmmaker_grade": "A", "atmosphere_alignment": "aligned"})
    assert "atmosphere_contradicts_scene_intent" not in health_aligned["critical_violations"], \
        "aligned atmosphere should not produce critical violation"
    health_partial = compute_doctrine_health({"filmmaker_grade": "B", "atmosphere_alignment": "partial_mismatch"})
    assert "atmosphere_contradicts_scene_intent" not in health_partial["critical_violations"], \
        "partial_mismatch should not produce critical violation"
    print("✅ Test 9 PASS: atmosphere/soundscape context — injection, parsing, health wiring")

    print("\n✅ ALL TESTS PASS — vision_doctrine_prompts.py V1.0 ready")
    sys.exit(0)
