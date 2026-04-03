#!/usr/bin/env python3
"""
DIALOGUE CUT ENGINE — V17.8 Smart Conversation Pacing
=====================================================

Foundational system for intelligent dialogue scene pacing.
Handles ALL conversation types:
- Two characters in SAME room (standard coverage)
- Two characters in DIFFERENT rooms (phone/intercut)
- Multi-character group conversations
- V.O. (voice-over) conversations

Smart Cut Rules (from professional film grammar):
1. SPEAKER CUT: When speaker changes → cut to new speaker (medium/CU)
2. REACTION CUT: During long speech → cut to listener reaction (CU)
3. TWO-SHOT: Establishing/breathing room → wider two-shot or master
4. INSERT CUT: Dramatic emphasis on prop/object mid-dialogue
5. OTS (Over-The-Shoulder): Classic dialogue coverage angle
6. MATCH CUT: When changing locations in cross-cut conversation

Duration-aware pacing:
- Short dialogue (≤15s): 2-3 cuts (speaker + reaction)
- Medium dialogue (16-30s): 4-6 cuts (speaker + OTS + reaction + master)
- Long dialogue (31-60s): 6-10 cuts (full coverage pattern)
- Extended dialogue (>60s): 10+ cuts with breathing room and inserts

Usage:
    from tools.dialogue_cut_engine import DialogueCutEngine
    engine = DialogueCutEngine(story_bible, shot_plan)
    cuts = engine.generate_dialogue_cuts(scene_id)
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any


class DialogueCutEngine:
    """
    Generates intelligent shot coverage for dialogue scenes.
    Produces a cut list with shot types, framing, and character focus.
    """

    # Standard coverage patterns by number of speakers
    COVERAGE_PATTERNS = {
        1: [  # Monologue / V.O. conversation (one visible character)
            {"type": "medium", "framing": "MS", "lens": "50mm", "focus": "speaker", "description": "Medium shot of speaker"},
            {"type": "close_up", "framing": "CU", "lens": "85mm", "focus": "speaker", "description": "Close-up during emotional beat"},
            {"type": "insert", "framing": "ECU", "lens": "100mm", "focus": "object", "description": "Insert of key prop or detail"},
            {"type": "wide", "framing": "WS", "lens": "24mm", "focus": "environment", "description": "Wide establishing context"},
        ],
        2: [  # Two-person dialogue (classic shot/reverse-shot)
            {"type": "two_shot", "framing": "MS", "lens": "35mm", "focus": "both", "description": "Two-shot establishing geography"},
            {"type": "medium", "framing": "MS", "lens": "50mm", "focus": "speaker_a", "description": "Medium on Speaker A"},
            {"type": "ots", "framing": "OTS", "lens": "50mm", "focus": "speaker_b", "description": "Over-shoulder favoring Speaker B"},
            {"type": "close_up", "framing": "CU", "lens": "85mm", "focus": "speaker_a", "description": "Close-up Speaker A reaction"},
            {"type": "close_up", "framing": "CU", "lens": "85mm", "focus": "speaker_b", "description": "Close-up Speaker B reaction"},
            {"type": "medium", "framing": "MS", "lens": "50mm", "focus": "speaker_b", "description": "Medium on Speaker B"},
            {"type": "ots", "framing": "OTS", "lens": "50mm", "focus": "speaker_a", "description": "Over-shoulder favoring Speaker A"},
            {"type": "two_shot", "framing": "MS", "lens": "35mm", "focus": "both", "description": "Return to two-shot for resolution"},
        ],
        3: [  # Three-person dialogue (triangle coverage)
            {"type": "wide", "framing": "WS", "lens": "24mm", "focus": "all", "description": "Wide master of all three"},
            {"type": "medium", "framing": "MS", "lens": "50mm", "focus": "speaker_a", "description": "Medium on Speaker A"},
            {"type": "two_shot", "framing": "MS", "lens": "35mm", "focus": "listeners", "description": "Two-shot of listeners reacting"},
            {"type": "close_up", "framing": "CU", "lens": "85mm", "focus": "speaker_b", "description": "Close-up Speaker B"},
            {"type": "medium", "framing": "MS", "lens": "50mm", "focus": "speaker_c", "description": "Medium on Speaker C"},
            {"type": "ots", "framing": "OTS", "lens": "50mm", "focus": "speaker_a", "description": "Over-shoulder from C to A"},
            {"type": "close_up", "framing": "CU", "lens": "85mm", "focus": "speaker_a", "description": "Close-up Speaker A reaction"},
            {"type": "wide", "framing": "WS", "lens": "24mm", "focus": "all", "description": "Wide return for resolution"},
        ],
    }

    # Duration brackets for pacing
    PACING_BRACKETS = [
        (15, 2, 3),    # ≤15s: 2-3 cuts
        (30, 4, 6),    # 16-30s: 4-6 cuts
        (60, 6, 10),   # 31-60s: 6-10 cuts
        (120, 10, 16), # 61-120s: 10-16 cuts
        (999, 16, 24), # >120s: 16-24 cuts
    ]

    # Shot type durations (ideal)
    # V17.8: Shot durations matched to LEGACY smart_cut_timing system
    # Legacy averaged 12.6s/shot — V17's 8.84s was too fast
    SHOT_DURATIONS = {
        "wide": (13, 20),       # 13-20s for establishing (legacy: 20s with 3.0s hold)
        "two_shot": (10, 14),   # 10-14s for two-shot
        "medium": (10, 14),     # 10-14s for dialogue (legacy: 13s avg)
        "ots": (10, 13),        # 10-13s for over-shoulder
        "close_up": (8, 13),    # 8-13s for close-up
        "insert": (8, 10),      # 8-10s for detail insert (legacy: 8s with 2.0s hold)
        "reaction": (6, 8),     # 6-8s for reaction (legacy: 8s with 1.5s hold)
    }

    # Legacy smart_cut_timing constants
    DIALOGUE_HOLD_AFTER = 0.8   # Seconds to hold on speaker after dialogue ends
    REACTION_HOLD = 1.5         # Seconds for reaction shot hold
    INSERT_HOLD = 2.0           # Seconds for insert/detail hold
    ESTABLISHING_HOLD = 3.0     # Seconds for establishing shot hold
    WORDS_PER_SECOND = 2.5      # Average speech rate for dialogue timing

    def __init__(self, story_bible: Dict = None, shot_plan: Dict = None):
        self.story_bible = story_bible or {}
        self.shot_plan = shot_plan or {}

    def parse_dialogue_lines(self, dialogue_text: str) -> List[Dict]:
        """
        Parse dialogue text into individual lines with speaker attribution.
        Returns: [{"speaker": "EVELYN", "line": "Hello?", "is_vo": False}, ...]
        """
        lines = []
        if not dialogue_text:
            return lines

        # Pattern: CHARACTER: (optional V.O./O.S.) "dialogue text"
        # Also handles: CHARACTER: dialogue text
        pattern = re.compile(
            r'([A-Z][A-Z\s\.]+?):\s*(?:\(([^)]*)\))?\s*["\']?(.+?)["\']?(?=\s*[A-Z][A-Z\s\.]+?:|$)',
            re.DOTALL
        )

        matches = pattern.findall(dialogue_text)
        if matches:
            for speaker, direction, line in matches:
                speaker = speaker.strip()
                is_vo = bool(direction and ("V.O." in direction.upper() or "VO" in direction.upper()))
                is_os = bool(direction and "O.S." in direction.upper())
                lines.append({
                    "speaker": speaker,
                    "line": line.strip(),
                    "is_vo": is_vo,
                    "is_os": is_os,
                    "direction": direction.strip() if direction else "",
                })
        else:
            # Fallback: treat entire text as single speech
            lines.append({
                "speaker": "UNKNOWN",
                "line": dialogue_text.strip(),
                "is_vo": False,
                "is_os": False,
                "direction": "",
            })

        return lines

    def get_visible_speakers(self, dialogue_lines: List[Dict]) -> List[str]:
        """Get list of speakers who are physically visible (not V.O.)."""
        visible = []
        seen = set()
        for line in dialogue_lines:
            if not line["is_vo"] and line["speaker"] not in seen:
                visible.append(line["speaker"])
                seen.add(line["speaker"])
        return visible

    def compute_smart_cut_timing(self, dialogue_line: str, cut_type: str) -> Dict:
        """
        Compute legacy-compatible smart_cut_timing for a shot.
        Matches the V12 format: {dialogue_ends_at, cut_point} or {hold_duration}.

        Args:
            dialogue_line: The spoken dialogue text (empty for non-dialogue shots)
            cut_type: Shot type (medium, close_up, reaction, insert, wide, etc.)

        Returns:
            Dict with timing data matching legacy format
        """
        if not dialogue_line or cut_type in ("reaction", "insert", "wide"):
            # Non-dialogue shot — use hold_duration
            if cut_type == "wide":
                return {"hold_duration": self.ESTABLISHING_HOLD}
            elif cut_type == "insert":
                return {"hold_duration": self.INSERT_HOLD}
            else:
                return {"hold_duration": self.REACTION_HOLD}

        # Dialogue shot — compute dialogue_ends_at and cut_point
        # Estimate dialogue duration from word count
        word_count = len(dialogue_line.split())
        dialogue_duration = word_count / self.WORDS_PER_SECOND

        return {
            "dialogue_ends_at": round(dialogue_duration, 2),
            "cut_point": round(dialogue_duration + self.DIALOGUE_HOLD_AFTER, 2),
        }

    def calculate_cut_count(self, duration: float) -> Tuple[int, int]:
        """Calculate min/max cuts based on scene/shot duration."""
        for max_dur, min_cuts, max_cuts in self.PACING_BRACKETS:
            if duration <= max_dur:
                return min_cuts, max_cuts
        return 16, 24  # Very long scenes

    def generate_cut_plan(
        self,
        dialogue_text: str,
        total_duration: float,
        characters: List[str] = None,
        location: str = "",
        emotional_tone: str = "neutral",
        is_cross_location: bool = False,
        locations_map: Dict[str, str] = None,
    ) -> List[Dict]:
        """
        Generate a smart cut plan for a dialogue sequence.

        Args:
            dialogue_text: Full dialogue with speaker attributions
            total_duration: Total duration in seconds for this dialogue block
            characters: List of character names in scene
            location: Primary location
            emotional_tone: Emotional tone for lighting/framing choices
            is_cross_location: Whether this is a cross-location conversation (phone, etc.)
            locations_map: {character_name: location} for cross-location scenes

        Returns:
            List of cut dictionaries with shot type, framing, character, duration, prompt hints
        """
        dialogue_lines = self.parse_dialogue_lines(dialogue_text)
        visible_speakers = self.get_visible_speakers(dialogue_lines)
        all_speakers = list(set(line["speaker"] for line in dialogue_lines))

        # Determine coverage pattern
        num_visible = max(1, len(visible_speakers))
        pattern_key = min(num_visible, 3)  # Cap at 3-person pattern
        base_pattern = self.COVERAGE_PATTERNS.get(pattern_key, self.COVERAGE_PATTERNS[2])

        # Calculate cuts needed
        min_cuts, max_cuts = self.calculate_cut_count(total_duration)
        target_cuts = min(max_cuts, max(min_cuts, len(dialogue_lines) + 2))

        cuts = []
        time_cursor = 0.0
        pattern_idx = 0

        # PASS 1: Dialogue-driven cuts (one cut per speaker change + reactions)
        prev_speaker = None
        for i, line in enumerate(dialogue_lines):
            if time_cursor >= total_duration:
                break

            speaker = line["speaker"]
            is_vo = line["is_vo"]
            remaining = total_duration - time_cursor

            # Determine cut type based on speaker change
            if speaker != prev_speaker:
                # Speaker changed — cut to new speaker (or reaction if V.O.)
                if is_vo:
                    # V.O. speaker — show listener reaction
                    cut_type = "reaction"
                    focus_char = visible_speakers[0] if visible_speakers else speaker
                    framing = "CU"
                    lens = "85mm"
                    desc = f"Close-up reaction of {focus_char} listening to {speaker} (V.O.)"
                else:
                    # Visible speaker — cut to them
                    cut_type = "medium"
                    focus_char = speaker
                    framing = "MS"
                    lens = "50mm"
                    desc = f"Medium shot of {speaker} speaking"
            else:
                # Same speaker continuing — add variety
                if i % 3 == 0 and num_visible >= 2:
                    cut_type = "ots"
                    focus_char = speaker
                    framing = "OTS"
                    lens = "50mm"
                    other = [s for s in visible_speakers if s != speaker]
                    other_name = other[0] if other else "listener"
                    desc = f"Over-shoulder from {other_name} to {speaker}"
                elif i % 3 == 1:
                    cut_type = "close_up"
                    focus_char = speaker
                    framing = "CU"
                    lens = "85mm"
                    desc = f"Close-up of {speaker} during emotional delivery"
                else:
                    cut_type = "medium"
                    focus_char = speaker
                    framing = "MS"
                    lens = "50mm"
                    desc = f"Medium shot of {speaker} continuing"

            # Calculate duration for this cut
            dur_range = self.SHOT_DURATIONS.get(cut_type, (5, 8))
            cut_dur = min(dur_range[1], max(dur_range[0], remaining / max(1, target_cuts - len(cuts))))
            cut_dur = min(cut_dur, remaining)

            # Location for cross-cut scenes
            cut_location = location
            if is_cross_location and locations_map:
                cut_location = locations_map.get(focus_char, location)

            # V17.8: Compute legacy-compatible smart_cut_timing
            smart_timing = self.compute_smart_cut_timing(line["line"] if not is_vo else "", cut_type)

            cuts.append({
                "index": len(cuts),
                "type": cut_type,
                "framing": framing,
                "lens": lens,
                "focus_character": focus_char,
                "description": desc,
                "duration": round(cut_dur, 1),
                "start_time": round(time_cursor, 1),
                "dialogue_line": line["line"][:120],
                "location": cut_location,
                "emotional_tone": emotional_tone,
                "is_vo_reaction": is_vo,
                "smart_cut_timing": smart_timing,
            })

            time_cursor += cut_dur
            prev_speaker = speaker

        # PASS 2: Fill remaining time with coverage shots
        while time_cursor < total_duration - 2:
            remaining = total_duration - time_cursor
            if remaining < 3:
                break

            # Cycle through base pattern for additional coverage
            p = base_pattern[pattern_idx % len(base_pattern)]
            pattern_idx += 1

            focus = p["focus"]
            if focus == "speaker_a" and len(visible_speakers) >= 1:
                focus_char = visible_speakers[0]
            elif focus == "speaker_b" and len(visible_speakers) >= 2:
                focus_char = visible_speakers[1]
            elif focus == "speaker_c" and len(visible_speakers) >= 3:
                focus_char = visible_speakers[2]
            elif focus in ("both", "all", "listeners", "environment"):
                focus_char = ", ".join(visible_speakers[:2]) if visible_speakers else "scene"
            else:
                focus_char = visible_speakers[0] if visible_speakers else "scene"

            dur_range = self.SHOT_DURATIONS.get(p["type"], (5, 8))
            cut_dur = min(dur_range[1], remaining)

            cut_location = location
            if is_cross_location and locations_map and isinstance(focus_char, str):
                cut_location = locations_map.get(focus_char, location)

            smart_timing = self.compute_smart_cut_timing("", p["type"])

            cuts.append({
                "index": len(cuts),
                "type": p["type"],
                "framing": p["framing"],
                "lens": p["lens"],
                "focus_character": focus_char,
                "description": p["description"].replace("Speaker A", visible_speakers[0] if visible_speakers else "character"),
                "duration": round(cut_dur, 1),
                "start_time": round(time_cursor, 1),
                "dialogue_line": "",
                "location": cut_location,
                "emotional_tone": emotional_tone,
                "is_vo_reaction": False,
                "smart_cut_timing": smart_timing,
            })

            time_cursor += cut_dur

        return cuts

    def generate_scene_dialogue_shots(
        self,
        scene_id: str,
        scene_beats: List[Dict] = None,
        scene_meta: Dict = None,
    ) -> List[Dict]:
        """
        Generate full shot list for a dialogue scene from story bible beats.
        Returns shots ready for insertion into shot_plan.

        Args:
            scene_id: Scene identifier (e.g., "002")
            scene_beats: List of beat dicts from story bible
            scene_meta: Scene metadata (location, characters, duration, etc.)
        """
        if not scene_meta:
            scene_meta = {}

        location = scene_meta.get("location", "")
        characters = scene_meta.get("characters", [])
        duration = scene_meta.get("estimated_duration", 120)
        emotional_tone = scene_meta.get("emotional_tone", "neutral")

        # Collect all dialogue from beats
        all_dialogue = ""
        for beat in (scene_beats or []):
            dlg = beat.get("dialogue", "")
            if dlg:
                all_dialogue += dlg + " "

        # Detect cross-location (phone conversations)
        is_cross_location = False
        locations_map = {}
        for beat in (scene_beats or []):
            desc = (beat.get("description", "") + " " + beat.get("action", "")).lower()
            if any(kw in desc for kw in ["phone", "call", "intercut", "cross-cut", "v.o.", "voice over"]):
                is_cross_location = True
                break

        # Generate the cut plan
        cuts = self.generate_cut_plan(
            dialogue_text=all_dialogue,
            total_duration=duration,
            characters=characters,
            location=location,
            emotional_tone=emotional_tone,
            is_cross_location=is_cross_location,
            locations_map=locations_map,
        )

        # Convert cuts to shot format
        shots = []
        for cut in cuts:
            shot_id = f"{scene_id}_{cut['index']:03d}{'ABCR'[cut['index'] % 4]}"
            shot = {
                "shot_id": shot_id,
                "scene_id": scene_id,
                "type": cut["framing"],
                "shot_type": cut["type"],
                "duration": cut["duration"],
                "location": cut["location"],
                "characters": [cut["focus_character"]] if cut["focus_character"] != "scene" else characters,
                "nano_prompt": "",  # Will be enriched by pipeline
                "ltx_motion_prompt": "",
                "camera_style": "static" if cut["type"] == "close_up" else "slow_push",
                "lens_specs": cut["lens"],
                "emotional_tone": cut["emotional_tone"],
                "dialogue_text": cut["dialogue_line"],
                "_cut_type": cut["type"],
                "_cut_description": cut["description"],
                "_dialogue_cut_engine": True,
            }
            shots.append(shot)

        return shots

    def explain_cuts(self, cuts: List[Dict]) -> str:
        """
        Generate a human-readable explanation of the cut plan.
        Useful for director review.
        """
        lines = [
            f"DIALOGUE CUT PLAN — {len(cuts)} cuts, {sum(c['duration'] for c in cuts):.0f}s total",
            "=" * 60,
        ]

        for cut in cuts:
            time_str = f"{cut['start_time']:5.1f}s"
            dur_str = f"{cut['duration']:.1f}s"
            vo_marker = " [V.O. REACTION]" if cut.get("is_vo_reaction") else ""
            dlg_preview = f' — "{cut["dialogue_line"][:40]}..."' if cut.get("dialogue_line") else ""

            lines.append(
                f"  {time_str} | {cut['framing']:4s} {cut['lens']:5s} | "
                f"{cut['focus_character'][:20]:20s} | {dur_str:5s} | "
                f"{cut['description'][:40]}{vo_marker}{dlg_preview}"
            )

        return "\n".join(lines)


class SceneTimingAnalyzer:
    """
    V17.8: Analyze scene timing against legacy manifest data.
    Flags unreasonable durations, missing smart_cut_timing, and pacing problems.
    """

    # Legacy Ravencroft timing reference (from V12 FIXED_FINAL manifest)
    LEGACY_REFERENCE = {
        "001": {"shots": 11, "duration": 142, "avg": 12.9, "type": "flashback"},
        "002": {"shots": 6, "duration": 85, "avg": 14.2, "type": "apartment_setup"},
        "003": {"shots": 30, "duration": 350, "avg": 11.7, "type": "phone_intercut"},
        "004": {"shots": 11, "duration": 153, "avg": 13.9, "type": "travel"},
        "005": {"shots": 24, "duration": 293, "avg": 12.2, "type": "dialogue_heavy"},
        "006": {"shots": 21, "duration": 286, "avg": 13.6, "type": "arrival"},
        "007": {"shots": 10, "duration": 125, "avg": 12.5, "type": "exploration"},
        "008": {"shots": 16, "duration": 197, "avg": 12.3, "type": "dialogue_heavy"},
        "009": {"shots": 27, "duration": 304, "avg": 11.3, "type": "dialogue_heavy"},
        "010": {"shots": 12, "duration": 164, "avg": 13.7, "type": "solo"},
        "011": {"shots": 13, "duration": 157, "avg": 12.1, "type": "exploration"},
        "012": {"shots": 8, "duration": 105, "avg": 13.1, "type": "research"},
        "013": {"shots": 12, "duration": 163, "avg": 13.6, "type": "tension"},
        "014": {"shots": 12, "duration": 145, "avg": 12.1, "type": "confrontation"},
        "015": {"shots": 12, "duration": 160, "avg": 13.3, "type": "resolution"},
    }

    # Sanity limits
    MIN_AVG_SHOT_DURATION = 8.0    # Below this = too fast
    MAX_AVG_SHOT_DURATION = 20.0   # Above this = too slow
    MIN_SCENE_DURATION = 30.0      # Below this = too short for a scene
    MAX_PHONE_CALL_DURATION = 180.0  # Phone calls shouldn't exceed 3 minutes
    MAX_DURATION_DRIFT = 0.5       # 50% drift from legacy is a warning

    def analyze_scene(self, scene_id: str, shots: List[Dict]) -> Dict:
        """
        Analyze a scene's timing and return warnings/issues.
        """
        if not shots:
            return {"scene_id": scene_id, "issues": ["No shots in scene"], "score": 0}

        total_dur = sum(s.get("duration", 0) for s in shots)
        avg_dur = total_dur / len(shots)
        has_smart_timing = sum(1 for s in shots if s.get("smart_cut_timing"))

        issues = []
        warnings = []

        # Check average duration
        if avg_dur < self.MIN_AVG_SHOT_DURATION:
            issues.append(f"Average shot duration too low: {avg_dur:.1f}s (min: {self.MIN_AVG_SHOT_DURATION}s)")
        if avg_dur > self.MAX_AVG_SHOT_DURATION:
            warnings.append(f"Average shot duration high: {avg_dur:.1f}s")

        # Check total scene duration
        if total_dur < self.MIN_SCENE_DURATION:
            issues.append(f"Scene too short: {total_dur:.0f}s (min: {self.MIN_SCENE_DURATION}s)")

        # Check smart_cut_timing presence
        if has_smart_timing == 0:
            warnings.append(f"No smart_cut_timing on any of {len(shots)} shots")
        elif has_smart_timing < len(shots) * 0.5:
            warnings.append(f"Only {has_smart_timing}/{len(shots)} shots have smart_cut_timing")

        # Check dialogue shots have proper timing
        dialogue_shots = [s for s in shots if s.get("dialogue_text") or s.get("dialogue")]
        for ds in dialogue_shots:
            timing = ds.get("smart_cut_timing", {})
            if not timing.get("dialogue_ends_at") and not timing.get("hold_duration"):
                issues.append(f"Shot {ds.get('shot_id','?')} has dialogue but no smart_cut_timing")

        # Detect phone conversation scenes with excessive duration
        all_dialogue = " ".join(
            s.get("dialogue_text", s.get("dialogue", "")) or ""
            for s in shots
        ).lower()
        is_phone = any(kw in all_dialogue for kw in ["phone", "v.o.", "calling", "intercut"])
        if is_phone and total_dur > self.MAX_PHONE_CALL_DURATION:
            issues.append(
                f"Phone conversation scene is {total_dur:.0f}s — max recommended: "
                f"{self.MAX_PHONE_CALL_DURATION:.0f}s"
            )

        # Compare against legacy reference
        legacy = self.LEGACY_REFERENCE.get(scene_id)
        legacy_comparison = None
        if legacy:
            dur_drift = abs(total_dur - legacy["duration"]) / legacy["duration"]
            shot_drift = abs(len(shots) - legacy["shots"]) / legacy["shots"]

            legacy_comparison = {
                "legacy_shots": legacy["shots"],
                "legacy_duration": legacy["duration"],
                "legacy_avg": legacy["avg"],
                "duration_drift": round(dur_drift * 100, 1),
                "shot_drift": round(shot_drift * 100, 1),
            }

            if dur_drift > self.MAX_DURATION_DRIFT:
                drift_dir = "shorter" if total_dur < legacy["duration"] else "longer"
                warnings.append(
                    f"Duration drift {dur_drift*100:.0f}% {drift_dir} than legacy "
                    f"({total_dur:.0f}s vs {legacy['duration']}s)"
                )

        # Score (0-100)
        score = 100
        score -= len(issues) * 15
        score -= len(warnings) * 5
        if avg_dur < 10:
            score -= int((10 - avg_dur) * 5)

        return {
            "scene_id": scene_id,
            "shots": len(shots),
            "total_duration": round(total_dur, 1),
            "avg_duration": round(avg_dur, 1),
            "smart_cut_coverage": f"{has_smart_timing}/{len(shots)}",
            "dialogue_shots": len(dialogue_shots),
            "is_phone_scene": is_phone,
            "issues": issues,
            "warnings": warnings,
            "legacy_comparison": legacy_comparison,
            "score": max(0, score),
        }

    def analyze_all_scenes(self, shot_plan: Dict) -> Dict:
        """Analyze all scenes in a shot plan and return comprehensive report."""
        shots = shot_plan.get("shots", [])

        # Group by scene
        by_scene: Dict[str, List] = {}
        for s in shots:
            sid = s.get("scene_id", "?")
            if sid not in by_scene:
                by_scene[sid] = []
            by_scene[sid].append(s)

        results = []
        total_issues = 0
        total_warnings = 0

        for sid in sorted(by_scene.keys()):
            analysis = self.analyze_scene(sid, by_scene[sid])
            results.append(analysis)
            total_issues += len(analysis["issues"])
            total_warnings += len(analysis["warnings"])

        return {
            "scenes": results,
            "total_scenes": len(results),
            "total_issues": total_issues,
            "total_warnings": total_warnings,
            "overall_score": round(sum(r["score"] for r in results) / len(results)) if results else 0,
        }


def main():
    """CLI for testing dialogue cut engine."""
    import sys

    # Example: phone conversation between Evelyn and Lawyer
    test_dialogue = """
    EVELYN: This is Evelyn Ravencroft. I received your letter about an inheritance?
    LAWYER: (V.O.) Ah yes, Ms. Ravencroft. I'm sorry for your loss. Lady Margaret was quite particular about her estate.
    EVELYN: I didn't even know I had any relatives. What can you tell me about her?
    LAWYER: (V.O.) Very little, I'm afraid. She was a recluse. Lived alone in that old manor for decades.
    EVELYN: What's the catch?
    LAWYER: (V.O.) No catch. The property is yours, free and clear. Though I should mention... the locals are quite superstitious about the place.
    EVELYN: Superstitious how?
    LAWYER: (V.O.) Old wives' tales, mostly. Nothing you need concern yourself with.
    EVELYN: Show me the manor.
    """

    engine = DialogueCutEngine()
    cuts = engine.generate_cut_plan(
        dialogue_text=test_dialogue,
        total_duration=75,
        characters=["EVELYN RAVENCROFT", "LAWYER"],
        location="CITY APARTMENT",
        emotional_tone="tension",
        is_cross_location=True,
        locations_map={
            "EVELYN RAVENCROFT": "CITY APARTMENT",
            "EVELYN": "CITY APARTMENT",
            "LAWYER": "LAW OFFICE",
        },
    )

    print(engine.explain_cuts(cuts))


if __name__ == "__main__":
    main()
