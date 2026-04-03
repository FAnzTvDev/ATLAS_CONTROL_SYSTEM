#!/usr/bin/env python3
"""
ATLAS SHOT CHOREOGRAPHER — Turns beats into timed action sequences
====================================================================
THE PROBLEM:
  Beat action: "Nadia moves through the library, lifting camera to capture shelves"
  Current prompt: "Nadia moves through the library, lifting camera" (a description)
  Current first frame: Nadia already holding camera up (END state)
  Result: Kling holds the pose for 10 seconds. Static. Dead.

THE FIX:
  First frame: Nadia in the DOORWAY, camera bag on shoulder (ENTRY state)
  Kling prompt: Timed choreography:
    "0-3s: She enters the room, looking around.
     3-6s: She lifts camera and begins photographing the shelves.
     6-10s: She moves deeper into the room, photographing as she walks."
  Result: 10 seconds of CONTINUOUS ACTION.

PRINCIPLE: The first frame is the STARTING POSITION.
The Kling prompt describes what HAPPENS from that starting position.
The video shows the JOURNEY, not the destination.
"""

from typing import Dict, List, Tuple, Optional


# ═══ ACTION VERBS → ENTRY STATE + SEQUENCE ═══
# Maps beat actions to (first_frame_description, timed_choreography)

def choreograph_beat(beat_action: str, beat_desc: str, shot_type: str,
                     duration: int, dialogue: str = "", mood: str = "",
                     props: str = "") -> Tuple[str, str]:
    """
    Convert a beat action into:
      1. First frame description (ENTRY STATE — before the action)
      2. Timed choreography (what happens across the duration)

    Returns (frame_desc, choreography)
    """
    action = (beat_action or beat_desc or "").lower()
    dur = int(duration)

    # ── ENTERING / ARRIVING ──
    if any(w in action for w in ["enters", "arrives", "pushes open", "walks in", "steps into",
                                      "moves through", "moves into"]):
        frame = "Doorway visible. Character about to enter from the side. Room empty, waiting."
        if "camera" in action or "photograph" in action:
            choreo = _build_timed(dur, [
                "She steps into the room from the doorway, looking around in wonder",
                "She walks slowly through the space, absorbing the details",
                "She lifts her camera and begins photographing, moving deeper into the room",
            ])
        else:
            choreo = _build_timed(dur, [
                "She pushes open the door and enters, taking in the space",
                "She walks forward, eyes scanning the room",
                "She pauses, setting down her bag, surveying what's ahead",
            ])

    # ── DISCOVERING / FINDING ──
    elif any(w in action for w in ["catches", "finds", "discovers", "falls", "notices"]):
        frame = "Character reaching toward a shelf, hand extending. Something is about to happen."
        choreo = _build_timed(dur, [
            "Her hand pulls at a book on the shelf. Something shifts inside",
            "A yellowed paper slides out and flutters down. She catches it",
            "She unfolds the paper carefully. Her expression shifts — eyes widen, mouth opens",
            "She reads, shock spreading across her face. She holds the paper closer",
        ])

    # ── READING / EXAMINING ──
    elif any(w in action for w in ["reads", "examines", "studies", "scans"]):
        frame = "Character holding a document, eyes just beginning to scan the text."
        if dialogue:
            choreo = _build_timed(dur, [
                "She reads intently, eyes moving across the text, brow furrowing",
                "Her lips move as she reads aloud, voice barely a whisper",
                "She pauses at a particular line, something registers — her hand comes to her mouth",
            ])
        else:
            choreo = _build_timed(dur, [
                "She reads carefully, eyes scanning left to right, concentration deepening",
                "Her expression shifts as she processes what's written",
                "She looks up from the text, mind racing, then looks back down to re-read",
            ])

    # ── CONCEALING / POCKETING ──
    elif any(w in action for w in ["pockets", "conceals", "hides", "slips", "folds"]):
        frame = "Character holding a folded paper, glancing sideways with a guarded expression."
        choreo = _build_timed(dur, [
            "She folds the letter quickly, creasing it tight",
            "She glances toward the door, listening. Tucks the letter into her back pocket",
            "She smooths her expression, turns back to the shelves. Composing herself",
        ])

    # ── CONFRONTING / DEMANDING ──
    elif any(w in action for w in ["confronts", "demands", "presents", "opens briefcase", "pulls out"]):
        frame = "Two people facing each other in a room. Tension visible in posture. Briefcase on table."
        choreo = _build_timed(dur, [
            "She opens the briefcase on the table, pulls out a thick folder",
            "She holds up the documents, making her case with controlled authority",
            "The other person's jaw tightens, refusing to engage. Standoff",
        ])

    # ── REFUSING / DEFYING ──
    elif any(w in action for w in ["refuses", "stares", "gazes up", "turns away", "defiant"]):
        frame = "Character standing rigid, facing away from the other person. Looking at something on the wall."
        choreo = _build_timed(dur, [
            "He stares at the portrait on the wall, jaw set, refusing to face her",
            "His hand grips the banister. A slow breath. Quiet defiance",
            "He speaks without turning, voice low and steady. The room holds its breath",
        ])

    # ── FOLLOWING / TRAILING ──
    elif any(w in action for w in ["follows", "trails", "touches banister", "hand along"]):
        frame = "Character in a doorway behind another person, hesitating before entering."
        choreo = _build_timed(dur, [
            "He follows her into the room, steps heavy with reluctance",
            "His hand finds the banister, fingers tracing the dark wood",
            "He stops, looking up at the staircase. Grief washes over his face. He doesn't move",
        ])

    # ── DEFAULT (generic but still sequenced) ──
    else:
        frame = f"Character in position, about to begin action. {mood}."
        if dialogue:
            choreo = _build_timed(dur, [
                "The character begins to speak, body language shifting with intention",
                "Gestures accompany the words, natural rhythm of conversation",
                "A pause, a look — the moment lands. The scene breathes",
            ])
        else:
            choreo = _build_timed(dur, [
                "The character shifts position, eyes moving to a new focus",
                "A deliberate action — reaching, turning, or settling into the moment",
                "The beat resolves. Atmosphere shifts subtly. Ready for what comes next",
            ])

    # Add dialogue to choreography if present
    if dialogue:
        # Clean dialogue — keep the actual words
        clean = dialogue
        for name in ["NADIA COLE:", "THOMAS BLACKWOOD:", "ELEANOR VOSS:", "RAYMOND CROSS:", "HARRIET HARGROVE:"]:
            clean = clean.replace(name, "")
        clean = clean.replace("|", " ").strip()[:100]
        choreo += f' Speaking: "{clean}"'

    # Add mood
    if mood:
        choreo += f" Atmosphere: {mood}."

    return frame, choreo


def _build_timed(duration: int, phases: List[str]) -> str:
    """Build timed choreography string from action phases."""
    n = len(phases)
    if n == 0:
        return ""

    phase_dur = duration / n
    parts = []
    for i, phase in enumerate(phases):
        start = int(i * phase_dur)
        end = int((i + 1) * phase_dur)
        if end > duration:
            end = duration
        parts.append(f"{start}-{end}s: {phase}")

    return ". ".join(parts) + "."


def choreograph_scene(beats: List[Dict], characters: List[str],
                      location: str, is_solo: bool) -> List[Dict]:
    """
    Build full scene choreography from beats.
    Adds establishing + closing beats if not present.
    Returns list of choreographed shot dicts.
    """
    shots = []

    # ESTABLISHING BEAT (always add at start)
    if beats:
        first_action = beats[0].get("character_action", "") if isinstance(beats[0], dict) else str(beats[0])
        first_action = first_action or ""  # Guard against None
        if not any(w in first_action.lower() for w in ["enters", "arrives", "pushes"]):
            # Add an explicit establishing shot
            shots.append({
                "type": "establishing",
                "frame_desc": f"Empty {location}. No people. Architecture, atmosphere, light. The room waits.",
                "choreography": "Slow push in. The camera drifts through the empty space. Dust motes. Light through windows. The room breathes.",
                "duration": "5",
                "characters": [],
                "is_establishing": True,
            })

    # BEAT SHOTS
    # Short names for in-prompt use (first name only)
    short_names = [c.split()[0].title() for c in characters[:2]]
    char_label = " and ".join(short_names) if short_names else "the character"
    location_short = location.split(" - ")[-1] if " - " in location else location

    # V29.10: CONTENT-AWARE COVERAGE ARC
    # V29.5 used a mechanical beat-index arc: beat0=medium, beat1=OTS-A, beat2=two_shot, beat3=OTS-B.
    # This is WRONG. The arc was position-based, not content-based.
    #
    # CINEMATIC TRUTH: OTS is for stationary dialogue exchange ONLY.
    # You CANNOT open a scene in OTS — the audience hasn't seen the room or the characters yet.
    # You CANNOT use OTS on a movement beat — you need to see the character moving through space.
    # You CANNOT use OTS on an entry/arrival beat — the viewer is still orienting.
    #
    # CONTENT-AWARE RULES (in priority order):
    #   1. Beat 0 = ALWAYS medium (orient the audience — geography + characters first)
    #   2. Entry/movement/trailing beats = ALWAYS medium (show motion in space, not OTS)
    #   3. Discovery/examination beats = medium_close (intimate but spatial context)
    #   4. Confrontation/standoff beats WITHOUT dialogue = two_shot (see both faces)
    #   5. OTS only when: beat has dialogue + NOT a movement beat + beat_idx >= 1
    #      - OTS-A for odd-numbered dialogue beats
    #      - OTS-B for even-numbered dialogue beats (alternates A/B naturally)
    #   6. Default mid-scene = medium_close (emotional pull, stay close)
    #
    # ARC (solo, any beats): medium → medium_close → close_up → medium_close → close_up
    #
    # WHY THIS MATTERS:
    # Scene 001 Beat 1: "Thomas trails his hand along the banister, eyes downcast" = MOVEMENT.
    # Old code: OTS-A (WRONG — audience hasn't settled yet, and Thomas is mid-movement)
    # New code: medium (show Thomas entering, hand on banister, following Eleanor into the room)
    # Scene 001 Beat 2: Eleanor presents documents. CONFRONTATION + dialogue = ots_a (correct)
    # Scene 001 Beat 3: Thomas refuses, stares at portrait. Dialogue + defiance = ots_b (correct)

    total_beats = len(beats)

    # Keywords that indicate PHYSICAL MOVEMENT through space (never OTS — need to see the traversal)
    # These are LOCOMOTION keywords — character physically moves from A to B.
    # NOTE: "gazes up", "stares at", "looks up", "turns away" are NOT here — those are
    # static emotional gestures, not physical traversal. They belong with dialogue beats.
    _MOVEMENT_KEYWORDS = [
        "enters", "arrives", "pushes open", "walks in", "steps into",
        "moves through", "moves into", "follows", "trails", "touches banister",
        "hand along", "walks to", "crosses to", "moves toward", "walks forward",
        "steps forward", "paces", "approaches",
    ]

    # Keywords that indicate DISCOVERY or EXAMINATION beats (→ medium_close)
    # NOT "opens" (too generic — "opens briefcase" is confrontation, not discovery)
    _DISCOVERY_KEYWORDS = [
        "catches", "finds", "discovers", "falls", "notices", "reads",
        "examines", "studies", "scans", "unfolds",
    ]

    # Keywords that indicate CONFRONTATION without movement (→ two_shot or OTS with dialogue)
    _CONFRONTATION_KEYWORDS = [
        "confronts", "demands", "presents", "pulls out", "opens briefcase",
        "refuses", "defiant", "pockets", "conceals", "holds up",
    ]

    def _arc_for_beat(beat_idx: int, total_beats: int, is_solo: bool,
                      beat_data: dict = None) -> str:
        """
        Content-aware shot type assignment.
        Reads actual beat content — not just beat index position.
        OTS only appears when the beat is a stationary dialogue exchange.
        """
        if is_solo:
            solo_arc = {0: "medium", 1: "medium_close", 2: "close_up",
                        3: "medium_close", 4: "close_up"}
            return solo_arc.get(beat_idx, "medium_close")

        # RULE 1: Beat 0 = ALWAYS medium. No exceptions. Geography first.
        if beat_idx == 0:
            return "medium"

        # Extract beat content for content-aware routing
        action = ""
        desc = ""
        has_dialogue = False
        if beat_data and isinstance(beat_data, dict):
            action = (beat_data.get("character_action", "") or "").lower()
            desc = (beat_data.get("description", "") or "").lower()
            dlg = beat_data.get("dialogue", "") or ""
            has_dialogue = bool(dlg.strip())

        combined = action + " " + desc

        # RULE 2: Movement/entry/trailing beats → medium (show motion in space)
        # Even with dialogue, if the character is mid-movement, show the movement.
        if any(kw in combined for kw in _MOVEMENT_KEYWORDS):
            return "medium"

        # RULE 3: Discovery/examination beats → medium_close
        if any(kw in combined for kw in _DISCOVERY_KEYWORDS):
            return "medium_close"

        # RULE 4: Confrontation WITHOUT dialogue → two_shot (see both faces reacting)
        if any(kw in combined for kw in _CONFRONTATION_KEYWORDS) and not has_dialogue:
            return "two_shot"

        # RULE 5: Stationary beat WITH dialogue → OTS (the core dialogue coverage tool)
        # Alternate A/B across the scene using a simple parity check on beat_idx.
        if has_dialogue:
            # Count preceding dialogue beats to get the OTS alternation right
            # OTS-A first time, OTS-B second time, etc.
            return "ots_a" if beat_idx % 2 == 1 else "ots_b"

        # RULE 6: Confrontation with dialogue → OTS (already caught by Rule 5)
        # Anything else mid-scene → medium_close (emotional pull)
        return "medium_close"

    for beat_idx, beat in enumerate(beats):
        if isinstance(beat, dict):
            action = beat.get("character_action", "")
            desc = beat.get("description", "")
            mood = beat.get("atmosphere", "")
            dialogue = beat.get("dialogue", "")
            props = ", ".join(beat.get("objects", []))
        else:
            action = str(beat)
            desc = action
            mood = ""
            dialogue = ""
            props = ""

        has_dlg = bool(dialogue)
        dur = 15 if has_dlg else 10

        # V29.10: pass beat dict for content-aware routing
        stype = _arc_for_beat(beat_idx, total_beats, is_solo,
                              beat_data=beat if isinstance(beat, dict) else None)

        _, choreo = choreograph_beat(action, desc, stype, dur, dialogue, mood, props)

        # BUILD SPECIFIC FRAME DESC — beat content + camera framing language
        beat_entry = desc or action
        beat_entry = beat_entry.rstrip(".")

        # V29.5: Build frame description based on shot type with EXPLICIT spatial blocking
        # OTS shots must specify WHICH character faces camera and which has back to camera.
        # This is the key instruction FAL needs to generate the correct composition.
        if not is_solo and len(short_names) >= 2:
            char_a, char_b = short_names[0], short_names[1]
            if stype == "medium":
                specific_frame = (
                    f"MEDIUM TWO-SHOT. {char_a} frame-left facing right, {char_b} frame-right facing left. "
                    f"Both waist-up. Room geography visible behind them. {beat_entry}."
                )
            elif stype == "ots_a":
                # Over char B's shoulder — char B back to camera (foreground), char A faces camera
                specific_frame = (
                    f"OVER-THE-SHOULDER SHOT. {char_b} back and shoulder fills left foreground, OUT OF FOCUS. "
                    f"{char_a} faces camera frame-right, SHARP FOCUS, expression fully readable. "
                    f"85mm. Shallow depth of field. {beat_entry}."
                )
            elif stype == "ots_b":
                # Over char A's shoulder — char A back to camera (foreground), char B faces camera
                specific_frame = (
                    f"OVER-THE-SHOULDER SHOT. {char_a} back and shoulder fills right foreground, OUT OF FOCUS. "
                    f"{char_b} faces camera frame-left, SHARP FOCUS, expression fully readable. "
                    f"85mm. Shallow depth of field. {beat_entry}."
                )
            elif stype == "two_shot":
                specific_frame = (
                    f"TIGHT TWO-SHOT. {char_a} and {char_b} face-to-face, inches apart, confrontational. "
                    f"{char_a} frame-left facing right, {char_b} frame-right facing left. "
                    f"Both faces sharp, tension visible. {beat_entry}."
                )
            elif stype == "medium_close":
                # Semi-solo on the character who spoke last — or char_a if no dialogue
                focal_char = char_a
                specific_frame = (
                    f"MEDIUM CLOSE-UP. {focal_char} chest-up, face sharp, expression readable. "
                    f"Shallow focus, {char_b} softly visible or out of frame. "
                    f"85mm. {beat_entry}."
                )
            else:
                specific_frame = f"{char_a} and {char_b} in the {location_short}. {beat_entry}."
        elif short_names:
            # Solo scene arc
            char_a = short_names[0]
            if stype == "medium":
                specific_frame = f"MEDIUM SHOT. {char_a} waist-up, {location_short} visible behind. {beat_entry}."
            elif stype == "medium_close":
                specific_frame = f"MEDIUM CLOSE-UP. {char_a} chest-up, face readable, shallow focus. {beat_entry}."
            elif stype == "close_up":
                specific_frame = f"CLOSE-UP. {char_a} face fills frame. 85mm. Heavy bokeh behind. Eyes sharp. {beat_entry}."
            else:
                specific_frame = f"{char_a} in the {location_short}. {beat_entry}."
        else:
            specific_frame = f"In the {location_short}. {beat_entry}."

        shots.append({
            "frame_desc": specific_frame,
            "choreography": choreo,
            "duration": str(dur),
            "action": action,
            "mood": mood,
            "dialogue": dialogue,
            "type": stype,                  # V29.4: pass shot type through to auto_consolidate
            "_dialogue_speaker": beat.get("_dialogue_speaker", "") if isinstance(beat, dict) else "",
        })

    # CLOSING BEAT — scene-specific
    # V29.3: Use descriptive closing (no location proper names — prevents text rendering in FAL)
    closing_desc = f"Wide shot — {char_label}. The room holds the scene's weight." if char_label else "Wide shot. The room holds its breath."
    shots.append({
        "type": "closing",
        "frame_desc": closing_desc,
        "choreography": "Slow pull back. The space between characters speaks. Atmosphere settles like dust. The scene holds, then releases.",
        "duration": "5",
        "characters": characters,
        "is_closing": True,
    })

    return shots


# ═══ SELF-TEST ═══
if __name__ == "__main__":
    # Test with Scene 002 beats
    beats = [
        {
            "character_action": "Nadia moves through the library, lifting camera to capture shelves",
            "description": "Nadia photographs floor-to-ceiling bookshelves with professional reverence",
            "atmosphere": "warm light on leather spines",
            "dialogue": "First editions. Brontë, Dickens, Wilkie Collins. She had taste.",
            "objects": ["camera"],
        },
        {
            "character_action": "Nadia catches falling letter, unfolds it, expression shifts to shock",
            "description": "A folded letter falls from a book — Nadia reads it",
            "atmosphere": "discovery, tension, hidden truth",
            "dialogue": '"My dearest Thomas, the house keeps our secrets better than we ever could."',
            "objects": ["letter", "book"],
        },
        {
            "character_action": "Nadia folds letter quickly, slips it into back pocket, glances at door",
            "description": "Nadia pockets the letter, looking toward the door",
            "atmosphere": "furtive, secretive",
            "objects": ["letter", "door"],
        },
    ]

    print("="*70)
    print("  CHOREOGRAPHER TEST — Scene 002")
    print("="*70)

    scene_shots = choreograph_scene(beats, ["NADIA COLE"], "HARGROVE ESTATE - LIBRARY", True)

    for i, shot in enumerate(scene_shots):
        print(f"\n  Shot {i+1} ({shot.get('type', 'beat')}):")
        print(f"    Duration: {shot['duration']}s")
        print(f"    First frame: {shot['frame_desc'][:70]}")
        print(f"    Choreography: {shot['choreography'][:120]}...")
        if shot.get('dialogue'):
            print(f"    Dialogue: {shot['dialogue'][:60]}")

    print(f"\n  Total shots: {len(scene_shots)} (including establishing + closing)")
    print(f"  Total duration: {sum(int(s['duration']) for s in scene_shots)}s")
