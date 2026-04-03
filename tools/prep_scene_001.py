#!/usr/bin/env python3
"""
SCENE 001 PREPARATION — Inject real blocking data before monitored run.

What this fixes:
1. state_in/state_out with REAL poses, emotions, positions (not generic defaults)
2. gaze_direction for every shot (was 0% across entire project)
3. screen_position for Lady Margaret (frame placement)
4. body_orientation (facing camera, facing altar, profile)
5. Spatial context injected into prompts so the model knows WHERE Margaret is

Scene 001: Lady Margaret performs a ritual in the manor's ritual room.
She is ALONE — single character, no eyeline-to-other-character needed.
But gaze direction (altar, candles, journal, camera) changes per beat.
"""

import json
import os
import shutil
from datetime import datetime
from pathlib import Path

PROJECT = "ravencroft_v22"
PP = Path(f"pipeline_outputs/{PROJECT}")
SHOT_PLAN = PP / "shot_plan.json"

# ═══════════════════════════════════════════════════════════════
# SCENE 001 BLOCKING PLAN — from story bible beats
# ═══════════════════════════════════════════════════════════════
# Location: INT. RAVENCROFT MANOR RITUAL ROOM - NIGHT
# Character: Lady Margaret Ravencroft (alone)
# Journey: standing at circle center → kneeling → chanting →
#          writing in journal → candles extinguish → collapse

BLOCKING_PLAN = {
    "001_001A": {
        # Beat 0: Wide establishing — Margaret stands at center of binding circle
        "state_in": {
            "LADY MARGARET RAVENCROFT": {
                "pose": "standing_upright",
                "screen_position": "center",
                "body_orientation": "three-quarter-left",
                "gaze_direction": "down_at_circle",
                "emotion": "resolve",
                "emotion_intensity": 6,
                "depth_plane": "mid",
                "gesture": "arms at sides, ceremonial posture"
            }
        },
        "state_out": {
            "LADY MARGARET RAVENCROFT": {
                "pose": "standing_upright",
                "screen_position": "center",
                "body_orientation": "three-quarter-left",
                "gaze_direction": "down_at_circle",
                "emotion": "resolve",
                "emotion_intensity": 6
            }
        },
        "gaze_direction": "down_at_binding_circle",
        "spatial_context": "Lady Margaret stands at the center of a circular ash binding circle, "
                          "surrounded by candles on stone floor. She is frame-center, "
                          "three-quarter angle facing left. Candlelight from below casts upward "
                          "shadows on her gaunt face. The ritual room's stone walls visible behind her.",
    },
    "001_002B": {
        # Beat 0-1: Detail/b-roll — Margaret kneels, begins ritual
        "state_in": {
            "LADY MARGARET RAVENCROFT": {
                "pose": "kneeling",
                "screen_position": "center-left",
                "body_orientation": "profile_left",
                "gaze_direction": "down_at_hands",
                "emotion": "concentration",
                "emotion_intensity": 7,
                "depth_plane": "foreground",
                "gesture": "hands positioned over binding circle"
            }
        },
        "state_out": {
            "LADY MARGARET RAVENCROFT": {
                "pose": "kneeling",
                "screen_position": "center-left",
                "body_orientation": "profile_left",
                "gaze_direction": "down_at_hands",
                "emotion": "concentration",
                "emotion_intensity": 7
            }
        },
        "gaze_direction": "down_at_hands_over_circle",
        "spatial_context": "Margaret kneels at the circle's edge, frame center-left in profile. "
                          "Her hands hover over the ash markings. Candles flicker around her. "
                          "Camera is low, near floor level, capturing her silhouette against candlelight.",
    },
    "001_003B": {
        # Beat 1: The whispered words — candles flare
        "state_in": {
            "LADY MARGARET RAVENCROFT": {
                "pose": "kneeling",
                "screen_position": "center",
                "body_orientation": "frontal",
                "gaze_direction": "straight_ahead_unfocused",
                "emotion": "intensity",
                "emotion_intensity": 8,
                "depth_plane": "mid",
                "gesture": "lips moving, hands trembling over circle"
            }
        },
        "state_out": {
            "LADY MARGARET RAVENCROFT": {
                "pose": "kneeling",
                "screen_position": "center",
                "body_orientation": "frontal",
                "gaze_direction": "straight_ahead_unfocused",
                "emotion": "intensity",
                "emotion_intensity": 8
            }
        },
        "gaze_direction": "straight_ahead_unfocused_trance",
        "spatial_context": "Close on Margaret kneeling, frame center, facing camera. "
                          "Her lips move with ancient words. Candles flare white behind her. "
                          "Her eyes are open but unfocused, deep in the ritual.",
    },
    "001_004B": {
        # Beat 2: Child's voice — Margaret reacts
        "state_in": {
            "LADY MARGARET RAVENCROFT": {
                "pose": "kneeling_upright",
                "screen_position": "center-right",
                "body_orientation": "three-quarter-right",
                "gaze_direction": "up_and_right_toward_darkness",
                "emotion": "fear",
                "emotion_intensity": 8,
                "depth_plane": "mid",
                "gesture": "head snaps up, listening"
            }
        },
        "state_out": {
            "LADY MARGARET RAVENCROFT": {
                "pose": "kneeling_upright",
                "screen_position": "center-right",
                "body_orientation": "three-quarter-right",
                "gaze_direction": "up_and_right_toward_darkness",
                "emotion": "fear",
                "emotion_intensity": 8
            }
        },
        "gaze_direction": "up_toward_darkness_where_voice_came_from",
        "spatial_context": "Margaret's head snaps up from the ritual, looking toward the dark corner "
                          "of the room (off-screen right). She is frame center-right, kneeling, "
                          "three-quarter angle. The child's voice echoes from the shadows she looks toward.",
    },
    "001_005B": {
        # Beat 3: Margaret's eyes close — the tear
        "state_in": {
            "LADY MARGARET RAVENCROFT": {
                "pose": "kneeling",
                "screen_position": "center",
                "body_orientation": "frontal",
                "gaze_direction": "eyes_closed",
                "emotion": "grief",
                "emotion_intensity": 9,
                "depth_plane": "foreground",
                "gesture": "eyes shut, single tear on cheek"
            }
        },
        "state_out": {
            "LADY MARGARET RAVENCROFT": {
                "pose": "kneeling",
                "screen_position": "center",
                "body_orientation": "frontal",
                "gaze_direction": "eyes_closed",
                "emotion": "grief",
                "emotion_intensity": 9
            }
        },
        "gaze_direction": "eyes_closed",
        "spatial_context": "Tight on Margaret's face, frame center, completely frontal. "
                          "Her eyes close. A single silver tear tracks down her gaunt cheek. "
                          "Candlelight plays across her skin. Deep grief visible in her expression.",
    },
    "001_006B": {
        # Beat 4: The journal — writing
        "state_in": {
            "LADY MARGARET RAVENCROFT": {
                "pose": "kneeling_hunched",
                "screen_position": "center-left",
                "body_orientation": "three-quarter-left",
                "gaze_direction": "down_at_journal",
                "emotion": "desperate_determination",
                "emotion_intensity": 9,
                "depth_plane": "foreground",
                "gesture": "hand trembling, writing in journal on floor"
            }
        },
        "state_out": {
            "LADY MARGARET RAVENCROFT": {
                "pose": "kneeling_hunched",
                "screen_position": "center-left",
                "body_orientation": "three-quarter-left",
                "gaze_direction": "down_at_journal",
                "emotion": "desperate_determination",
                "emotion_intensity": 9
            }
        },
        "gaze_direction": "down_at_journal_she_writes_in",
        "spatial_context": "Margaret hunched over an open journal on the stone floor, frame center-left. "
                          "Her trembling hand writes. Black ink floods across white pages. "
                          "Camera looks down over her shoulder. Binding circle visible around her.",
    },
    "001_007C": {
        # Beat 4-5: "No... it's too strong" — desperation
        "state_in": {
            "LADY MARGARET RAVENCROFT": {
                "pose": "kneeling_recoiling",
                "screen_position": "center",
                "body_orientation": "frontal",
                "gaze_direction": "up_at_camera_desperate",
                "emotion": "terror",
                "emotion_intensity": 10,
                "depth_plane": "extreme_foreground",
                "gesture": "pulling back from the circle, hands raised defensively"
            }
        },
        "state_out": {
            "LADY MARGARET RAVENCROFT": {
                "pose": "kneeling_recoiling",
                "screen_position": "center",
                "body_orientation": "frontal",
                "gaze_direction": "up_at_camera_desperate",
                "emotion": "terror",
                "emotion_intensity": 10
            }
        },
        "gaze_direction": "directly_at_camera_breaking_fourth_wall",
        "spatial_context": "Extreme close-up of Margaret's face, frame center, looking directly into camera. "
                          "Pure terror. She mouths 'No... it's too strong.' "
                          "Candle flames distort around her. This is the emotional peak.",
    },
    "001_008A": {
        # Beat 5: Candles extinguish — darkness — collapse
        "state_in": {
            "LADY MARGARET RAVENCROFT": {
                "pose": "collapsing",
                "screen_position": "center",
                "body_orientation": "frontal_falling",
                "gaze_direction": "eyes_rolling_back",
                "emotion": "overwhelmed",
                "emotion_intensity": 10,
                "depth_plane": "mid",
                "gesture": "body going limp, falling forward"
            }
        },
        "state_out": {
            "LADY MARGARET RAVENCROFT": {
                "pose": "collapsed_on_floor",
                "screen_position": "center-low",
                "body_orientation": "prone",
                "gaze_direction": "unconscious",
                "emotion": "void",
                "emotion_intensity": 0
            }
        },
        "gaze_direction": "eyes_rolling_back_before_collapse",
        "spatial_context": "Wide shot — all candles extinguish simultaneously. For a beat, total darkness. "
                          "Then moonlight through a high window reveals Margaret collapsed on the floor "
                          "inside the binding circle. The journal lies open beside her. She is still.",
    },
}


def main():
    print("═══ SCENE 001 PREPARATION — INJECTING REAL BLOCKING DATA ═══")
    print()

    # Backup
    backup = SHOT_PLAN.with_suffix(f".json.backup_prep001_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    shutil.copy2(SHOT_PLAN, backup)
    print(f"Backup: {backup}")

    with open(SHOT_PLAN) as f:
        data = json.load(f)

    shots = data.get("shots", [])
    modified = 0

    for shot in shots:
        sid = shot.get("shot_id", "")
        if sid not in BLOCKING_PLAN:
            continue

        plan = BLOCKING_PLAN[sid]

        # 1. Inject real state_in / state_out
        shot["state_in"] = plan["state_in"]
        shot["state_out"] = plan["state_out"]

        # 2. Inject gaze_direction (was 0% across project)
        shot["gaze_direction"] = plan["gaze_direction"]

        # 3. Inject spatial_context into nano_prompt
        spatial = plan["spatial_context"]
        nano = shot.get("nano_prompt", "") or ""

        # Add spatial context AFTER the composition/camera info but BEFORE negatives
        if "spatial_context:" not in nano:
            # Find a good injection point — before "NO " negatives
            neg_idx = nano.find("NO ")
            if neg_idx > 50:
                nano = nano[:neg_idx] + f"spatial_context: {spatial} " + nano[neg_idx:]
            else:
                nano = nano + f" spatial_context: {spatial}"
            shot["nano_prompt"] = nano

        # 4. Inject spatial into ltx_motion_prompt too
        ltx = shot.get("ltx_motion_prompt", "") or ""
        if "spatial:" not in ltx:
            # Get the key gaze/pose info for motion prompt
            char_state = plan["state_in"].get("LADY MARGARET RAVENCROFT", {})
            motion_spatial = (
                f"spatial: Margaret {char_state.get('pose','')}, "
                f"looking {char_state.get('gaze_direction','ahead')}, "
                f"{char_state.get('gesture','')}. "
            )
            ltx = motion_spatial + ltx
            shot["ltx_motion_prompt"] = ltx

        modified += 1
        print(f"  ✅ {sid}: state_in/out + gaze + spatial injected")
        print(f"     Pose: {plan['state_in']['LADY MARGARET RAVENCROFT']['pose']}")
        print(f"     Gaze: {plan['gaze_direction']}")
        print(f"     Emotion: {plan['state_in']['LADY MARGARET RAVENCROFT']['emotion']} "
              f"({plan['state_in']['LADY MARGARET RAVENCROFT']['emotion_intensity']})")

    # Save
    with open(SHOT_PLAN, "w") as f:
        json.dump(data, f, indent=2)

    print(f"\n═══ RESULT: {modified}/8 Scene 001 shots updated with real blocking ═══")
    return modified


if __name__ == "__main__":
    main()
