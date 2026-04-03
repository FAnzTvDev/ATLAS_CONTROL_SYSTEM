#!/usr/bin/env python3
"""
SCENE INTENT ENGINE — ATLAS Cinematic Cognition Stack
=====================================================
Frontal Cortex: Declares what each scene is TRYING TO DO.

Every scene has a dramatic purpose — reveal, confront, grieve, establish,
deceive, confess, escape, discover. The intent engine reads the scene's
story bible data, character roster, dialogue, and atmosphere to determine:

  1. narrative_function — the dramatic verb (reveal, confront, grieve...)
  2. primary_emotion — emotional center of gravity
  3. tension_curve — shape of the scene's tension (rising, falling, spike...)
  4. audience_target — what the scene wants the viewer to feel
  5. pacing_intent — fast/measured/slow/building
  6. key_beats — which beats carry the scene's dramatic weight

Without scene intent, every shot gets the same generic treatment.
With it, the behavior mapper can derive specific shot language.

V25 NEW | 2026-03-12
Author: ATLAS Doctrine Command System

Laws:
    256. Scene intent is derived from content — not assigned randomly.
         Every intent field has a source: dialogue, atmosphere, beat
         descriptions, or character presence.
    257. Intent is READ-ONLY after derivation — downstream modules
         consume but never modify scene intent. The scene says what it
         says.
    258. Unknown intent defaults to "establish" with "neutrality" —
         NEVER to high-drama defaults. Generic is safer than wrong.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
import re


# ==============================================================================
# NARRATIVE FUNCTION VOCABULARY
# ==============================================================================

NARRATIVE_FUNCTIONS = {
    "reveal":      "truth is disclosed — character or audience learns something hidden",
    "confront":    "direct conflict between characters, positions clash",
    "grieve":      "loss is felt — character processes death, failure, or absence",
    "establish":   "world-building — location, mood, situation introduced",
    "deceive":     "character hides truth, manipulates, or misleads",
    "confess":     "character admits truth they've been holding",
    "escape":      "physical or emotional flight from threat or pressure",
    "discover":    "character finds evidence, artifact, or knowledge",
    "seduce":      "emotional or physical pull between characters",
    "mourn":       "collective grief — funeral, memorial, aftermath of loss",
    "investigate": "active searching for answers, examining evidence",
    "threaten":    "danger implied or stated, power wielded",
    "negotiate":   "characters bargain, trade, or seek compromise",
    "reminisce":   "memory invoked — flashback quality, past recalled",
    "transform":   "character changes state — realization shifts identity",
}

# Keywords that signal narrative function from dialogue/description
FUNCTION_SIGNALS = {
    "reveal":      ["truth", "secret", "discover", "realize", "learn", "uncover", "hidden",
                    "reveal", "confession", "disclose", "expose", "found out"],
    "confront":    ["confront", "argue", "demand", "accuse", "challenge", "face",
                    "clash", "fight", "oppose", "stand against"],
    "grieve":      ["grieve", "mourn", "loss", "death", "gone", "funeral", "tears",
                    "cry", "weep", "miss", "absence", "empty"],
    "establish":   ["arrive", "enter", "establish", "setting", "morning", "dawn",
                    "exterior", "first time", "approach"],
    "deceive":     ["lie", "deceive", "hide", "pretend", "mask", "cover", "fake",
                    "mislead", "manipulate"],
    "confess":     ["confess", "admit", "tell you", "truth is", "I did", "my fault",
                    "forgive", "I'm sorry"],
    "escape":      ["run", "flee", "escape", "leave", "get out", "hurry", "chase"],
    "discover":    ["find", "discover", "evidence", "clue", "letter", "document",
                    "photograph", "artifact", "examine"],
    "threaten":    ["threat", "warn", "danger", "kill", "destroy", "consequence",
                    "if you", "or else"],
    "investigate": ["search", "look for", "investigate", "examine", "inspect",
                    "question", "interrogate"],
    "negotiate":   ["deal", "offer", "trade", "bargain", "compromise", "terms",
                    "agree", "condition"],
    "reminisce":   ["remember", "recall", "memory", "used to", "back then", "once",
                    "when we were", "long ago"],
    "transform":   ["change", "transform", "become", "realize", "shift", "turn into",
                    "no longer", "from now on"],
}

# Emotion keywords from atmosphere/dialogue
EMOTION_SIGNALS = {
    "dread":        ["dread", "ominous", "foreboding", "dark", "shadow", "looming",
                     "creeping", "menace"],
    "horror":       ["horror", "terror", "scream", "blood", "nightmare", "monstrous"],
    "fear":         ["fear", "afraid", "scared", "panic", "anxious", "nervous", "dread"],
    "grief":        ["grief", "sorrow", "loss", "mourn", "weep", "tears", "empty"],
    "anger":        ["anger", "furious", "rage", "outraged", "bitter", "resentful"],
    "suspicion":    ["suspicious", "distrust", "doubt", "wary", "watchful", "uneasy"],
    "hope":         ["hope", "light", "warm", "gentle", "promise", "dawn", "bright"],
    "revelation":   ["truth", "reveal", "realize", "understand", "clarity", "epiphany"],
    "guilt":        ["guilt", "shame", "regret", "fault", "blame", "responsible"],
    "love":         ["love", "tender", "gentle", "embrace", "warm", "affection"],
    "desperation":  ["desperate", "urgent", "last chance", "no choice", "must", "please"],
    "neutrality":   [],  # default when nothing strong detected
}

# Tension curve detection from scene structure
TENSION_PATTERNS = {
    "rising":   ["builds", "intensifies", "grows", "escalates", "mounting", "increasing"],
    "falling":  ["settles", "calms", "resolves", "eases", "fades", "diminishes"],
    "spike":    ["sudden", "shock", "explosion", "snap", "breaks", "crashes", "scream"],
    "plateau":  ["sustained", "steady", "continues", "remains", "holds", "endures"],
    "valley":   ["pause", "breath", "respite", "moment", "quiet before"],
}


# ==============================================================================
# DATACLASSES
# ==============================================================================

@dataclass
class SceneIntent:
    """
    Declares what a scene is trying to accomplish dramatically.
    Read-only after derivation (Law 257).
    """
    scene_id: str
    narrative_function: str = "establish"      # dramatic verb
    primary_emotion: str = "neutrality"        # emotional center
    secondary_emotion: str = ""                # supporting emotion
    tension_curve: str = "flat"                # shape of tension
    audience_target: str = ""                  # what viewer should feel
    pacing_intent: str = "measured"            # fast/measured/slow/building
    key_beats: List[str] = field(default_factory=list)  # important beat IDs
    character_focus: str = ""                  # primary character this scene serves
    has_dialogue: bool = False
    has_confrontation: bool = False
    is_transition: bool = False                # purely transitional scene
    confidence: float = 0.0                    # 0-1 derivation confidence
    derived_from: List[str] = field(default_factory=list)  # reasoning trail
    generated_at: str = ""

    def __post_init__(self):
        if not self.generated_at:
            self.generated_at = datetime.utcnow().isoformat()

    def to_dict(self) -> Dict:
        from dataclasses import asdict
        return asdict(self)


# ==============================================================================
# ENGINE
# ==============================================================================

class SceneIntentEngine:
    """
    Frontal Cortex — reads scene data and declares dramatic purpose.

    Usage:
        engine = SceneIntentEngine()
        intent = engine.analyze_scene(scene_data, shots, story_bible_scene)
    """

    def analyze_scene(
        self,
        scene_id: str,
        shots: List[Dict],
        bible_scene: Optional[Dict] = None,
    ) -> SceneIntent:
        """
        Derive scene intent from shots + story bible data.
        Law 256: Every field has a documented source.
        Law 258: Unknown → establish + neutrality (safe defaults).
        """
        reasoning = []

        # Collect all text for analysis
        all_dialogue = []
        all_descriptions = []
        all_atmosphere = []
        characters_present = set()
        shot_types = []

        for s in shots:
            if s.get("dialogue_text"):
                all_dialogue.append(s["dialogue_text"])
            desc = s.get("nano_prompt", "") or s.get("description", "")
            if desc:
                all_descriptions.append(desc)
            for c in (s.get("characters") or []):
                characters_present.add(c)
            shot_types.append((s.get("shot_type") or "medium").lower())

        # Story bible enrichment
        if bible_scene:
            atmo = bible_scene.get("atmosphere", "")
            if atmo:
                all_atmosphere.append(atmo)
            scene_desc = bible_scene.get("description", "")
            if scene_desc:
                all_descriptions.append(scene_desc)
            beats = bible_scene.get("beats", [])
            for b in beats:
                bd = b.get("description", "")
                if bd:
                    all_descriptions.append(bd)
                ba = b.get("atmosphere", "")
                if ba:
                    all_atmosphere.append(ba)

        # Combine all text for keyword analysis
        all_text = " ".join(all_dialogue + all_descriptions + all_atmosphere).lower()
        has_dialogue = len(all_dialogue) > 0

        # 1. Derive narrative function
        narrative_function, func_conf = self._detect_function(all_text, reasoning)

        # 2. Derive primary emotion
        primary_emotion, secondary_emotion, emo_conf = self._detect_emotion(
            all_text, all_atmosphere, reasoning
        )

        # 3. Derive tension curve
        tension_curve, tens_conf = self._detect_tension(
            all_text, all_atmosphere, shots, reasoning
        )

        # 4. Audience target
        audience_target = self._derive_audience_target(
            narrative_function, primary_emotion, reasoning
        )

        # 5. Pacing
        pacing = self._derive_pacing(tension_curve, narrative_function, len(shots), reasoning)

        # 6. Key beats
        key_beats = self._identify_key_beats(shots, narrative_function, reasoning)

        # 7. Character focus
        char_focus = self._determine_character_focus(
            shots, characters_present, all_dialogue, reasoning
        )

        # 8. Confrontation detection
        has_confrontation = len(characters_present) >= 2 and narrative_function in (
            "confront", "threaten", "negotiate"
        )

        # 9. Transition scene detection
        is_transition = (
            len(shots) <= 2
            and not has_dialogue
            and narrative_function == "establish"
        )

        confidence = (func_conf + emo_conf + tens_conf) / 3.0

        return SceneIntent(
            scene_id=scene_id,
            narrative_function=narrative_function,
            primary_emotion=primary_emotion,
            secondary_emotion=secondary_emotion,
            tension_curve=tension_curve,
            audience_target=audience_target,
            pacing_intent=pacing,
            key_beats=key_beats,
            character_focus=char_focus,
            has_dialogue=has_dialogue,
            has_confrontation=has_confrontation,
            is_transition=is_transition,
            confidence=confidence,
            derived_from=reasoning,
        )

    def analyze_all_scenes(
        self,
        shots_by_scene: Dict[str, List[Dict]],
        bible_scenes: Optional[Dict[str, Dict]] = None,
    ) -> Dict[str, SceneIntent]:
        """Analyze all scenes in a project."""
        results = {}
        for scene_id, scene_shots in shots_by_scene.items():
            bible_scene = (bible_scenes or {}).get(scene_id)
            results[scene_id] = self.analyze_scene(scene_id, scene_shots, bible_scene)
        return results

    # ------------------------------------------------------------------
    # PRIVATE DETECTION METHODS
    # ------------------------------------------------------------------

    def _detect_function(self, text: str, trail: List[str]) -> tuple:
        """Score each narrative function by keyword presence."""
        scores = {}
        for func, keywords in FUNCTION_SIGNALS.items():
            count = sum(1 for kw in keywords if kw in text)
            if count > 0:
                scores[func] = count

        if not scores:
            trail.append("function: no strong signals → default 'establish'")
            return "establish", 0.3

        best = max(scores, key=scores.get)
        confidence = min(scores[best] / 5.0, 1.0)  # 5+ hits = full confidence
        trail.append(f"function: '{best}' ({scores[best]} keyword hits, conf={confidence:.2f})")
        return best, confidence

    def _detect_emotion(self, text: str, atmosphere: List[str], trail: List[str]) -> tuple:
        """Detect primary and secondary emotion from text."""
        atmo_text = " ".join(atmosphere).lower()
        combined = text + " " + atmo_text

        scores = {}
        for emotion, keywords in EMOTION_SIGNALS.items():
            if not keywords:
                continue
            count = sum(1 for kw in keywords if kw in combined)
            if count > 0:
                scores[emotion] = count

        if not scores:
            trail.append("emotion: no strong signals → default 'neutrality'")
            return "neutrality", "", 0.3

        sorted_emotions = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        primary = sorted_emotions[0][0]
        secondary = sorted_emotions[1][0] if len(sorted_emotions) > 1 else ""
        confidence = min(sorted_emotions[0][1] / 4.0, 1.0)

        trail.append(f"emotion: primary='{primary}' ({sorted_emotions[0][1]} hits)")
        if secondary:
            trail.append(f"emotion: secondary='{secondary}' ({sorted_emotions[1][1]} hits)")
        return primary, secondary, confidence

    def _detect_tension(
        self, text: str, atmosphere: List[str], shots: List[Dict], trail: List[str]
    ) -> tuple:
        """Detect tension curve shape."""
        atmo_text = " ".join(atmosphere).lower()
        combined = text + " " + atmo_text

        scores = {}
        for curve, keywords in TENSION_PATTERNS.items():
            count = sum(1 for kw in keywords if kw in combined)
            if count > 0:
                scores[curve] = count

        if not scores:
            # Infer from shot count and dialogue density
            dialogue_count = sum(1 for s in shots if s.get("dialogue_text"))
            if dialogue_count > len(shots) * 0.6:
                trail.append("tension: dialogue-heavy → 'rising'")
                return "rising", 0.4
            trail.append("tension: no signals → default 'flat'")
            return "flat", 0.3

        best = max(scores, key=scores.get)
        confidence = min(scores[best] / 3.0, 1.0)
        trail.append(f"tension: '{best}' ({scores[best]} keyword hits)")
        return best, confidence

    def _derive_audience_target(
        self, function: str, emotion: str, trail: List[str]
    ) -> str:
        """What should the viewer feel?"""
        AUDIENCE_MAP = {
            ("reveal", "dread"):       "rising unease as truth approaches",
            ("reveal", "revelation"):  "satisfaction of puzzle pieces connecting",
            ("confront", "anger"):     "tension of unresolved conflict",
            ("grieve", "grief"):       "empathetic sorrow, shared loss",
            ("establish", "neutrality"): "grounding in time and place",
            ("establish", "dread"):    "unease beneath surface calm",
            ("confess", "guilt"):      "weight of truth about to emerge",
            ("discover", "suspicion"): "curiosity sharpening to alarm",
            ("threaten", "fear"):      "visceral threat, protective instinct",
            ("deceive", "suspicion"):  "dramatic irony — viewer knows more",
        }
        target = AUDIENCE_MAP.get((function, emotion))
        if not target:
            target = f"engagement through {emotion} in service of {function}"
        trail.append(f"audience_target: func='{function}' + emo='{emotion}'")
        return target

    def _derive_pacing(
        self, tension: str, function: str, shot_count: int, trail: List[str]
    ) -> str:
        """Derive pacing intent."""
        if tension == "spike":
            return "fast"
        if tension == "rising":
            return "building"
        if function in ("grieve", "mourn", "reminisce"):
            return "slow"
        if shot_count <= 3:
            return "measured"
        return "measured"

    def _identify_key_beats(
        self, shots: List[Dict], function: str, trail: List[str]
    ) -> List[str]:
        """Find the shots that carry the scene's dramatic weight."""
        key = []
        for s in shots:
            sid = s.get("shot_id", "")
            # Dialogue shots in reveal/confront scenes are always key
            if function in ("reveal", "confront", "confess", "threaten"):
                if s.get("dialogue_text"):
                    key.append(sid)
            # Close-ups are key in grief/emotion scenes
            if function in ("grieve", "mourn", "transform"):
                if (s.get("shot_type") or "").lower() in ("close_up", "extreme_close_up"):
                    key.append(sid)
        if not key and shots:
            # Default: first and last shots are key
            key = [shots[0].get("shot_id", ""), shots[-1].get("shot_id", "")]
        trail.append(f"key_beats: {len(key)} shots identified as dramatically key")
        return key

    def _determine_character_focus(
        self,
        shots: List[Dict],
        characters: set,
        dialogue: List[str],
        trail: List[str],
    ) -> str:
        """Who does this scene primarily serve?"""
        if not characters:
            return ""
        # Count dialogue lines per character
        char_dialogue_count = {}
        for s in shots:
            if s.get("dialogue_text") and s.get("characters"):
                for c in s["characters"]:
                    char_dialogue_count[c] = char_dialogue_count.get(c, 0) + 1
        if char_dialogue_count:
            focus = max(char_dialogue_count, key=char_dialogue_count.get)
            trail.append(f"character_focus: '{focus}' ({char_dialogue_count[focus]} dialogue shots)")
            return focus
        # Fallback: most appearances
        char_count = {}
        for s in shots:
            for c in (s.get("characters") or []):
                char_count[c] = char_count.get(c, 0) + 1
        if char_count:
            return max(char_count, key=char_count.get)
        return ""
