#!/usr/bin/env python3
"""
ATLAS V27.6 — Story Judge (Post-Compilation LLM Story Conscience)
==================================================================

The Scene Intent Verifier (V27.4) runs BEFORE compilation — deterministic
pattern matching that catches wrong characters, wrong rooms, missing constraints.
It stays. It's fast and cheap.

The Story Judge runs AFTER the full compilation pipeline:
  Film Engine → Identity Injection → Scene DNA → Dialogue Cinematography → Beat Injection

It reads the FINAL compiled prompt + story bible + screenplay context and asks
an LLM one question: "Would a viewer watching this shot understand what's
happening in the story?"

This is NOT about technical quality (that's Doctrine, CPC, Vision Judge).
This is about NARRATIVE COHERENCE — the story logic the viewer experiences.

Architecture:
  DETERMINISTIC INGESTION (fast, cheap, runs every shot):
    - Extract scene intent from story_bible (characters, room, mood, props, actions)
    - Extract compiled prompt state (identity blocks, DNA blocks, dialogue, refs)
    - Build constraint checklist (character present? room correct? dialogue matches?)
    - Score deterministic pass/fail on hard constraints

  LLM EVALUATION (deep, costs ~$0.01/shot, runs on flagged shots):
    - Feed: screenplay beat + story bible scene + compiled prompt + constraint results
    - Ask: "Does this prompt tell the story this beat needs to tell?"
    - Judge: viewer_clarity (would viewer understand?), emotional_truth (right feeling?),
             narrative_flow (does it connect to what came before/after?)
    - Return: PASS / REVISE / BLOCK with specific notes

The LLM is NOT rewriting prompts. It's a JUDGE — it reads what the pipeline
produced and says whether the story comes through. If not, it says WHY, and
the deterministic systems fix it.

Usage:
    from tools.story_judge import StoryJudge
    judge = StoryJudge(project_path)

    # After full compilation, before FAL call:
    verdict = judge.evaluate_shot(shot, compiled_prompt, scene_context)
    # verdict.decision = "PASS" | "REVISE" | "BLOCK"
    # verdict.viewer_clarity = 0.0 - 1.0
    # verdict.notes = "The viewer won't understand why Nadia is suddenly angry..."

    # Batch evaluate entire scene:
    scene_verdict = judge.evaluate_scene(scene_id, compiled_shots)
"""

import json
import os
import re
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime

logger = logging.getLogger("atlas.story_judge")


# ═══════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════

@dataclass
class StoryConstraint:
    """A single deterministic constraint check."""
    name: str
    passed: bool
    detail: str
    severity: str = "WARNING"  # BLOCKING, WARNING, INFO


@dataclass
class ShotStoryState:
    """Extracted state of a compiled shot for story evaluation."""
    shot_id: str
    shot_type: str
    characters: List[str]
    has_identity_block: bool
    has_room_dna: bool
    has_lighting_rig: bool
    has_dialogue: bool
    dialogue_text: str
    has_negative_people: bool
    nano_prompt: str
    location_ref: str
    beat_text: str
    emotional_beat: str
    constraints: List[StoryConstraint]
    deterministic_score: float  # 0.0 - 1.0 from constraint checks


@dataclass
class StoryVerdict:
    """LLM verdict on whether the story comes through."""
    shot_id: str
    decision: str              # PASS, REVISE, BLOCK
    viewer_clarity: float      # 0.0 - 1.0: would a viewer understand what's happening?
    emotional_truth: float     # 0.0 - 1.0: does the feeling match the story beat?
    narrative_flow: float      # 0.0 - 1.0: does it connect to previous/next shots?
    deterministic_score: float # from constraint checks
    composite_score: float     # weighted combination
    notes: str                 # LLM explanation of what's working/missing
    revise_suggestions: List[str]  # specific actionable fixes if REVISE
    constraint_results: List[StoryConstraint]
    llm_used: bool            # True if LLM was called, False if deterministic-only
    elapsed_ms: float


@dataclass
class SceneStoryVerdict:
    """Full scene story evaluation."""
    scene_id: str
    shot_verdicts: List[StoryVerdict]
    scene_coherence: float     # Does the scene tell a coherent story across shots?
    pass_count: int
    revise_count: int
    block_count: int
    total_shots: int
    elapsed_ms: float


# ═══════════════════════════════════════════════════════════════
# STORY JUDGE ENGINE
# ═══════════════════════════════════════════════════════════════

class StoryJudge:
    """
    Post-compilation story coherence evaluator.

    Two tiers:
      Tier 1 (Deterministic): Fast constraint checks on every shot.
              Catches: missing characters, wrong room, empty dialogue shots,
              identity blocks missing, DNA missing on character shots.

      Tier 2 (LLM): Deep narrative evaluation on flagged shots.
              Asks: Does the compiled prompt tell the story this beat needs?
              Only runs when deterministic score < threshold or shot is hero.
    """

    def __init__(self, project_path: str, llm_provider: str = "anthropic"):
        self.project_path = Path(project_path)
        self.project_name = self.project_path.name
        self.llm_provider = llm_provider

        # Load project data
        self.story_bible = self._load_json("story_bible.json")
        self.cast_map = self._load_json("cast_map.json")
        self.shot_plan = self._load_json("shot_plan.json")

        # Extract scene intents from story bible
        self.scene_intents = {}
        for sc in self.story_bible.get("scenes", []):
            sid = sc.get("scene_id", "")
            if sid:
                self.scene_intents[sid] = self._extract_scene_intent(sc)

        # LLM threshold — shots below this get LLM evaluation
        self.llm_threshold = 0.75
        # Hero shot types always get LLM evaluation
        self.hero_types = {"close_up", "medium_close", "reaction", "dialogue"}

    def _load_json(self, filename: str) -> dict:
        path = self.project_path / filename
        if path.exists():
            try:
                with open(path) as f:
                    data = json.load(f)
                if isinstance(data, list) and filename == "shot_plan.json":
                    return {"shots": data}
                return data
            except Exception as e:
                logger.warning(f"[STORY JUDGE] Failed to load {filename}: {e}")
        return {}

    def _extract_scene_intent(self, scene_data: dict) -> dict:
        """Extract narrative intent from story bible scene."""
        location = scene_data.get("location", "")
        room = location.split(" - ", 1)[1].strip() if " - " in location else location

        beats = scene_data.get("beats", [])
        beat_texts = []
        characters = set()
        key_actions = []
        key_props = []
        mood = scene_data.get("atmosphere", "") or scene_data.get("mood", "")

        for beat in beats:
            if isinstance(beat, dict):
                bt = beat.get("description", "") or beat.get("text", "")
                beat_texts.append(bt)
                # Extract character names (CAPS words that match cast_map)
                for char_name in self.cast_map:
                    if char_name.upper() in bt.upper():
                        characters.add(char_name)
                # Extract action verbs
                for verb in ["discovers", "reads", "opens", "enters", "speaks",
                             "confronts", "photographs", "examines", "pockets",
                             "walks", "turns", "reveals", "hides", "argues"]:
                    if verb in bt.lower():
                        key_actions.append(f"{verb}: {bt[:60]}")
            elif isinstance(beat, str):
                beat_texts.append(beat)

        return {
            "location": location,
            "room": room,
            "characters": list(characters),
            "time_of_day": scene_data.get("time_of_day", ""),
            "mood": mood,
            "beats": beat_texts,
            "key_actions": key_actions,
            "key_props": key_props,
            "beat_count": len(beats),
        }

    # ─────────────────────────────────────────────────────────
    # TIER 1: DETERMINISTIC CONSTRAINT CHECKS
    # ─────────────────────────────────────────────────────────

    def extract_shot_state(self, shot: dict) -> ShotStoryState:
        """Extract the compiled state of a shot for evaluation."""
        nano = shot.get("nano_prompt", "") or ""
        chars = []
        for c in (shot.get("characters") or []):
            if isinstance(c, str):
                chars.append(c)
            elif isinstance(c, dict):
                chars.append(c.get("name", ""))

        dialogue = shot.get("dialogue_text", "") or ""
        beat_text = shot.get("beat", "") or shot.get("emotional_beat", "") or ""
        refs = shot.get("_controller_refs", [])
        loc_ref = ""
        for r in refs:
            if "location_masters" in str(r) or "ESTATE" in str(r).upper():
                loc_ref = str(r).split("/")[-1]

        constraints = self._check_constraints(shot, nano, chars, dialogue, loc_ref)
        det_score = sum(1 for c in constraints if c.passed) / max(len(constraints), 1)

        return ShotStoryState(
            shot_id=shot.get("shot_id", ""),
            shot_type=shot.get("shot_type", ""),
            characters=chars,
            has_identity_block="[CHARACTER:" in nano,
            has_room_dna="[ROOM DNA:" in nano,
            has_lighting_rig="[LIGHTING" in nano,
            has_dialogue=bool(dialogue),
            dialogue_text=dialogue,
            has_negative_people="No people" in nano or "no people" in nano,
            nano_prompt=nano,
            location_ref=loc_ref,
            beat_text=beat_text,
            emotional_beat=shot.get("emotional_beat", "") or "",
            constraints=constraints,
            deterministic_score=det_score,
        )

    def _check_constraints(self, shot: dict, nano: str, chars: List[str],
                           dialogue: str, loc_ref: str) -> List[StoryConstraint]:
        """Run deterministic constraint checks."""
        constraints = []
        shot_id = shot.get("shot_id", "")
        scene_id = shot_id[:3] if shot_id else ""
        intent = self.scene_intents.get(scene_id, {})
        shot_type = shot.get("shot_type", "")

        # C1: Character shots must have identity injection
        if chars:
            constraints.append(StoryConstraint(
                name="identity_injection",
                passed="[CHARACTER:" in nano,
                detail=f"Character shot {'has' if '[CHARACTER:' in nano else 'MISSING'} [CHARACTER:] block",
                severity="BLOCKING" if shot_type in ("close_up", "medium_close") else "WARNING",
            ))

        # C2: Empty shots must have negative people constraint
        if not chars:
            constraints.append(StoryConstraint(
                name="negative_people",
                passed="No people" in nano or "no people" in nano or "no figures" in nano.lower(),
                detail=f"Empty shot {'has' if 'No people' in nano else 'MISSING'} negative people constraint",
                severity="WARNING",
            ))

        # C3: Location ref matches scene room
        if intent and loc_ref:
            room = intent.get("room", "").upper().replace(" ", "_")
            loc_upper = loc_ref.upper()
            constraints.append(StoryConstraint(
                name="room_match",
                passed=room in loc_upper,
                detail=f"Location ref {'matches' if room in loc_upper else 'WRONG'} scene room {intent.get('room', '?')} (ref: {loc_ref})",
                severity="BLOCKING",
            ))

        # C4: Dialogue shots must have character
        if dialogue and not chars:
            constraints.append(StoryConstraint(
                name="dialogue_character",
                passed=False,
                detail="Dialogue shot has no character assigned",
                severity="BLOCKING",
            ))

        # C5: Character shots should have room DNA
        if chars and shot_type not in ("insert", "detail"):
            constraints.append(StoryConstraint(
                name="room_dna",
                passed="[ROOM DNA:" in nano,
                detail=f"Character shot {'has' if '[ROOM DNA:' in nano else 'MISSING'} room DNA",
                severity="WARNING",
            ))

        # C6: Beat/narrative exists — shot has a purpose
        beat = shot.get("beat", "") or shot.get("emotional_beat", "") or shot.get("description", "")
        constraints.append(StoryConstraint(
            name="narrative_purpose",
            passed=bool(beat),
            detail=f"Shot {'has' if beat else 'LACKS'} narrative purpose (beat/description)",
            severity="INFO",
        ))

        # C7: Prompt length sanity (too short = likely garbage)
        constraints.append(StoryConstraint(
            name="prompt_length",
            passed=len(nano) > 50,
            detail=f"Prompt length: {len(nano)} chars ({'OK' if len(nano) > 50 else 'TOO SHORT'})",
            severity="WARNING",
        ))

        # C8: No location proper names in prompt (T2-FE-28)
        has_proper = bool(re.search(r'\b(HARGROVE|BLACKWOOD|RAVENCROFT|MANOR|EST\.\s*\d{4})\b', nano))
        constraints.append(StoryConstraint(
            name="no_proper_names",
            passed=not has_proper,
            detail=f"Prompt {'CONTAINS' if has_proper else 'clean of'} location proper names",
            severity="WARNING",
        ))

        return constraints

    # ─────────────────────────────────────────────────────────
    # TIER 2: LLM STORY EVALUATION
    # ─────────────────────────────────────────────────────────

    def _build_llm_prompt(self, state: ShotStoryState, intent: dict,
                          prev_shot: Optional[dict] = None,
                          next_shot: Optional[dict] = None) -> str:
        """Build the LLM evaluation prompt."""
        beats_text = "\n".join(f"  - {b}" for b in intent.get("beats", []))
        actions_text = "\n".join(f"  - {a}" for a in intent.get("key_actions", []))

        constraint_text = "\n".join(
            f"  {'✓' if c.passed else '✗'} [{c.severity}] {c.name}: {c.detail}"
            for c in state.constraints
        )

        prev_context = ""
        if prev_shot:
            prev_desc = prev_shot.get("description", "") or prev_shot.get("nano_prompt", "")[:100]
            prev_context = f"\nPREVIOUS SHOT ({prev_shot.get('shot_id', '?')}): {prev_desc}"

        next_context = ""
        if next_shot:
            next_desc = next_shot.get("description", "") or next_shot.get("nano_prompt", "")[:100]
            next_context = f"\nNEXT SHOT ({next_shot.get('shot_id', '?')}): {next_desc}"

        return f"""You are a story editor reviewing an AI-generated film frame prompt.

SCENE INTENT (from story bible):
  Location: {intent.get('location', '?')}
  Room: {intent.get('room', '?')}
  Time: {intent.get('time_of_day', '?')}
  Mood: {intent.get('mood', '?')}
  Characters expected: {intent.get('characters', [])}
  Story beats:
{beats_text}
  Key actions:
{actions_text}

SHOT BEING EVALUATED:
  Shot ID: {state.shot_id}
  Shot type: {state.shot_type}
  Characters in shot: {state.characters}
  Has dialogue: {state.has_dialogue}
  Dialogue text: "{state.dialogue_text[:200]}"
  Beat context: "{state.beat_text[:200]}"
  Emotional beat: "{state.emotional_beat}"
{prev_context}
{next_context}

COMPILED PROMPT (what FAL will generate from):
{state.nano_prompt[:800]}

DETERMINISTIC CONSTRAINT RESULTS:
{constraint_text}
  Score: {state.deterministic_score:.2f}

EVALUATION CRITERIA — Answer as a story editor, not a technician:
1. VIEWER CLARITY (0-10): If a viewer saw this frame in the film, would they understand what's happening in the story at this moment? Would they know who this person is and why they're here?
2. EMOTIONAL TRUTH (0-10): Does the prompt's visual direction match the emotional state the story needs? Would the lighting, framing, and character performance convey the right feeling?
3. NARRATIVE FLOW (0-10): Does this shot connect naturally to what comes before and after? Would the cut feel motivated?

Respond in this EXACT format (no markdown, no extra text):
DECISION: PASS|REVISE|BLOCK
VIEWER_CLARITY: [0-10]
EMOTIONAL_TRUTH: [0-10]
NARRATIVE_FLOW: [0-10]
NOTES: [1-2 sentences explaining your evaluation — what works and what doesn't]
REVISE: [If REVISE, 1-2 specific actionable changes. If PASS/BLOCK, write "none"]"""

    def _call_llm(self, prompt: str) -> Optional[str]:
        """Call LLM for evaluation. Returns raw response text."""
        try:
            import anthropic
            client = anthropic.Anthropic()
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        except ImportError:
            logger.warning("[STORY JUDGE] anthropic SDK not installed — LLM tier unavailable")
            return None
        except Exception as e:
            logger.warning(f"[STORY JUDGE] LLM call failed: {e}")
            return None

    def _parse_llm_response(self, response: str) -> dict:
        """Parse structured LLM response."""
        result = {
            "decision": "PASS",
            "viewer_clarity": 7.0,
            "emotional_truth": 7.0,
            "narrative_flow": 7.0,
            "notes": "",
            "revise_suggestions": [],
        }
        for line in response.strip().split("\n"):
            line = line.strip()
            if line.startswith("DECISION:"):
                d = line.split(":", 1)[1].strip().upper()
                if d in ("PASS", "REVISE", "BLOCK"):
                    result["decision"] = d
            elif line.startswith("VIEWER_CLARITY:"):
                try:
                    result["viewer_clarity"] = float(line.split(":", 1)[1].strip())
                except ValueError:
                    pass
            elif line.startswith("EMOTIONAL_TRUTH:"):
                try:
                    result["emotional_truth"] = float(line.split(":", 1)[1].strip())
                except ValueError:
                    pass
            elif line.startswith("NARRATIVE_FLOW:"):
                try:
                    result["narrative_flow"] = float(line.split(":", 1)[1].strip())
                except ValueError:
                    pass
            elif line.startswith("NOTES:"):
                result["notes"] = line.split(":", 1)[1].strip()
            elif line.startswith("REVISE:"):
                rev = line.split(":", 1)[1].strip()
                if rev.lower() != "none":
                    result["revise_suggestions"] = [rev]
        return result

    # ─────────────────────────────────────────────────────────
    # PUBLIC API
    # ─────────────────────────────────────────────────────────

    def evaluate_shot(self, shot: dict, prev_shot: dict = None,
                      next_shot: dict = None, force_llm: bool = False) -> StoryVerdict:
        """
        Evaluate a single compiled shot for story coherence.

        Tier 1 (always): Deterministic constraint checks.
        Tier 2 (conditional): LLM evaluation if:
          - deterministic score < threshold, OR
          - shot is a hero type, OR
          - force_llm=True
        """
        import time
        t0 = time.time()

        state = self.extract_shot_state(shot)
        scene_id = state.shot_id[:3]
        intent = self.scene_intents.get(scene_id, {})

        # Decide whether to call LLM
        needs_llm = (
            force_llm or
            state.deterministic_score < self.llm_threshold or
            state.shot_type in self.hero_types or
            (state.has_dialogue and state.characters)  # dialogue shots always get deep eval
        )

        llm_used = False
        llm_result = None

        if needs_llm:
            llm_prompt = self._build_llm_prompt(state, intent, prev_shot, next_shot)
            raw_response = self._call_llm(llm_prompt)
            if raw_response:
                llm_result = self._parse_llm_response(raw_response)
                llm_used = True

        # Build verdict
        if llm_result:
            viewer = llm_result["viewer_clarity"] / 10.0
            emotion = llm_result["emotional_truth"] / 10.0
            flow = llm_result["narrative_flow"] / 10.0
            # Composite: 40% viewer clarity, 30% emotional truth, 20% narrative flow, 10% deterministic
            composite = (viewer * 0.4) + (emotion * 0.3) + (flow * 0.2) + (state.deterministic_score * 0.1)
            decision = llm_result["decision"]
            notes = llm_result["notes"]
            revise = llm_result["revise_suggestions"]
        else:
            viewer = state.deterministic_score
            emotion = state.deterministic_score
            flow = 0.7  # default assumption for flow without context
            composite = state.deterministic_score
            # Deterministic-only decision
            blocking = [c for c in state.constraints if not c.passed and c.severity == "BLOCKING"]
            warnings = [c for c in state.constraints if not c.passed and c.severity == "WARNING"]
            if blocking:
                decision = "BLOCK"
                notes = f"Blocking constraints failed: {', '.join(c.name for c in blocking)}"
            elif len(warnings) >= 2:
                decision = "REVISE"
                notes = f"Multiple warnings: {', '.join(c.name for c in warnings)}"
            else:
                decision = "PASS"
                notes = "All critical constraints passed (deterministic-only evaluation)"
            revise = [c.detail for c in state.constraints if not c.passed]

        elapsed = (time.time() - t0) * 1000

        verdict = StoryVerdict(
            shot_id=state.shot_id,
            decision=decision,
            viewer_clarity=viewer,
            emotional_truth=emotion,
            narrative_flow=flow,
            deterministic_score=state.deterministic_score,
            composite_score=composite,
            notes=notes,
            revise_suggestions=revise,
            constraint_results=state.constraints,
            llm_used=llm_used,
            elapsed_ms=elapsed,
        )

        logger.info(f"[STORY JUDGE] {state.shot_id}: {decision} "
                     f"(clarity={viewer:.2f} emotion={emotion:.2f} flow={flow:.2f} "
                     f"composite={composite:.2f} llm={'YES' if llm_used else 'NO'})")

        return verdict

    def evaluate_scene(self, scene_id: str, force_llm: bool = False) -> SceneStoryVerdict:
        """Evaluate all shots in a scene for story coherence."""
        import time
        t0 = time.time()

        shots = [s for s in self.shot_plan.get("shots", [])
                 if (s.get("shot_id", "")[:3] == scene_id)]
        shots.sort(key=lambda s: s.get("shot_id", ""))

        verdicts = []
        for i, shot in enumerate(shots):
            prev_shot = shots[i - 1] if i > 0 else None
            next_shot = shots[i + 1] if i < len(shots) - 1 else None
            v = self.evaluate_shot(shot, prev_shot, next_shot, force_llm=force_llm)
            verdicts.append(v)

        elapsed = (time.time() - t0) * 1000
        pass_count = sum(1 for v in verdicts if v.decision == "PASS")
        revise_count = sum(1 for v in verdicts if v.decision == "REVISE")
        block_count = sum(1 for v in verdicts if v.decision == "BLOCK")

        # Scene coherence = average composite score
        scene_coherence = (sum(v.composite_score for v in verdicts) / len(verdicts)) if verdicts else 0.0

        return SceneStoryVerdict(
            scene_id=scene_id,
            shot_verdicts=verdicts,
            scene_coherence=scene_coherence,
            pass_count=pass_count,
            revise_count=revise_count,
            block_count=block_count,
            total_shots=len(shots),
            elapsed_ms=elapsed,
        )

    def print_scene_report(self, sv: SceneStoryVerdict):
        """Print human-readable scene story verdict."""
        print(f"\n{'=' * 70}")
        print(f"  STORY JUDGE — Scene {sv.scene_id}")
        print(f"  Coherence: {sv.scene_coherence:.2f} | {sv.pass_count} PASS, {sv.revise_count} REVISE, {sv.block_count} BLOCK")
        print(f"{'=' * 70}")
        for v in sv.shot_verdicts:
            icon = {"PASS": "✓", "REVISE": "⚠", "BLOCK": "✗"}.get(v.decision, "?")
            llm_tag = " [LLM]" if v.llm_used else ""
            print(f"  {icon} {v.shot_id:12s} {v.decision:6s} clarity={v.viewer_clarity:.2f} "
                  f"emotion={v.emotional_truth:.2f} flow={v.narrative_flow:.2f} "
                  f"composite={v.composite_score:.2f}{llm_tag}")
            if v.notes:
                print(f"    → {v.notes[:100]}")
            if v.revise_suggestions:
                for rs in v.revise_suggestions:
                    print(f"    ⟳ {rs[:100]}")
        print(f"\n  Total: {sv.elapsed_ms:.0f}ms")


# ═══════════════════════════════════════════════════════════════
# STANDALONE TEST
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    project = sys.argv[1] if len(sys.argv) > 1 else "victorian_shadows_ep1"
    scene = sys.argv[2] if len(sys.argv) > 2 else "002"
    force = "--llm" in sys.argv

    project_path = f"pipeline_outputs/{project}"
    if not Path(project_path).exists():
        project_path = project

    judge = StoryJudge(project_path)
    print(f"Story Judge loaded: {len(judge.scene_intents)} scenes, {len(judge.cast_map)} characters")

    sv = judge.evaluate_scene(scene, force_llm=force)
    judge.print_scene_report(sv)

    # Save report
    report_dir = Path(project_path) / "reports"
    report_dir.mkdir(exist_ok=True)
    report = {
        "scene_id": sv.scene_id,
        "coherence": sv.scene_coherence,
        "pass": sv.pass_count,
        "revise": sv.revise_count,
        "block": sv.block_count,
        "total": sv.total_shots,
        "elapsed_ms": sv.elapsed_ms,
        "shots": [{
            "shot_id": v.shot_id,
            "decision": v.decision,
            "viewer_clarity": v.viewer_clarity,
            "emotional_truth": v.emotional_truth,
            "narrative_flow": v.narrative_flow,
            "composite": v.composite_score,
            "deterministic": v.deterministic_score,
            "llm_used": v.llm_used,
            "notes": v.notes,
            "revise": v.revise_suggestions,
            "constraints": [{"name": c.name, "passed": c.passed, "detail": c.detail} for c in v.constraint_results],
        } for v in sv.shot_verdicts],
    }
    report_path = report_dir / f"story_judge_scene_{scene}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\n  Report saved: {report_path}")
