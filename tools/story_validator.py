#!/usr/bin/env python3
"""
Story Validator - Upstream Quality Control for Blackwood Production

Validates story beats BEFORE rendering to ensure:
1. Goal - What character wants in this beat
2. Conflict - What opposes the goal
3. Turn - How situation changes
4. Reveal - New information or realization
5. Emotional State - Character emotion
6. Ghost Logic - Justifies supernatural appearances

Rejects weak beats to prevent "template fatigue" and random ghost appearances.
"""

import json
from pathlib import Path
from typing import Dict, List, Tuple
from datetime import datetime


class GhostMotifRegister:
    """Track ghost entity rules and appearance logic"""

    def __init__(self):
        self.entities = {
            "Eleanor_Guilt": {
                "type": "manifestation",
                "trigger": "Eleanor touches victim belongings",
                "visual_signature": "cold breath visible, shadows independent",
                "narrative_purpose": "represents Eleanor's guilt over skepticism",
                "frequency_target": "3-4 appearances per episode",
                "escalation": "subtle → overt → physical interaction",
                "current_count": 0
            },
            "Sarah_Protection": {
                "type": "guardian_presence",
                "trigger": "Eleanor in danger",
                "visual_signature": "warm light, child's laughter echo",
                "narrative_purpose": "Sarah Blackwood protecting investigators",
                "frequency_target": "2-3 appearances per episode",
                "escalation": "distant → nearby → direct intervention",
                "current_count": 0
            },
            "Blackwood_Malevolence": {
                "type": "antagonist_force",
                "trigger": "truth about murders discovered",
                "visual_signature": "oppressive shadows, temperature drop",
                "narrative_purpose": "entity preventing truth revelation",
                "frequency_target": "5-6 appearances per episode",
                "escalation": "atmospheric → threatening → attacking",
                "current_count": 0
            }
        }

    def validate_ghost_appearance(self, beat: Dict) -> Tuple[bool, str]:
        """Check if ghost appearance is narratively justified"""
        ghost_motifs = beat.get('visual_motifs', [])
        if not ghost_motifs:
            return True, "No ghost appearance"

        # Check if any motifs match registered entities
        for motif in ghost_motifs:
            motif_lower = motif.lower()

            # Check Eleanor_Guilt triggers
            if any(keyword in motif_lower for keyword in ['cold breath', 'shadow', 'guilt']):
                entity = self.entities['Eleanor_Guilt']
                if self._check_trigger_present(beat, entity['trigger']):
                    entity['current_count'] += 1
                    return True, f"Eleanor_Guilt justified: {entity['trigger']}"
                else:
                    return False, f"Eleanor_Guilt appearance without trigger: {entity['trigger']}"

            # Check Sarah_Protection triggers
            if any(keyword in motif_lower for keyword in ['warm light', 'laughter', 'protection']):
                entity = self.entities['Sarah_Protection']
                if self._check_trigger_present(beat, entity['trigger']):
                    entity['current_count'] += 1
                    return True, f"Sarah_Protection justified: {entity['trigger']}"
                else:
                    return False, f"Sarah_Protection appearance without trigger: {entity['trigger']}"

            # Check Blackwood_Malevolence triggers
            if any(keyword in motif_lower for keyword in ['oppressive', 'malevolent', 'temperature drop']):
                entity = self.entities['Blackwood_Malevolence']
                if self._check_trigger_present(beat, entity['trigger']):
                    entity['current_count'] += 1
                    return True, f"Blackwood_Malevolence justified: {entity['trigger']}"
                else:
                    return False, f"Blackwood_Malevolence appearance without trigger: {entity['trigger']}"

        return True, "Motif doesn't match ghost entities"

    def _check_trigger_present(self, beat: Dict, trigger: str) -> bool:
        """Check if trigger condition is present in beat"""
        beat_text = json.dumps(beat).lower()
        trigger_keywords = trigger.lower().split()
        return any(keyword in beat_text for keyword in trigger_keywords)

    def get_entity_stats(self) -> Dict:
        """Get current ghost appearance counts"""
        return {
            entity_id: {
                "count": data['current_count'],
                "target": data['frequency_target'],
                "percentage": (data['current_count'] / int(data['frequency_target'].split('-')[0])) * 100
            }
            for entity_id, data in self.entities.items()
        }


class StoryValidator:
    """Validates story beats before rendering"""

    def __init__(self, ghost_register: GhostMotifRegister = None):
        self.ghost_register = ghost_register or GhostMotifRegister()
        self.validation_log = []

    def validate_beat(self, beat: Dict, beat_index: int = 0) -> Tuple[bool, List[str]]:
        """
        Validate a single beat against narrative requirements

        Returns:
            (is_valid, list_of_issues)
        """
        issues = []

        # Check 1: Goal
        if not beat.get('goal'):
            issues.append("Missing GOAL - What does the character want in this beat?")

        # Check 2: Conflict
        if not beat.get('conflict'):
            issues.append("Missing CONFLICT - What opposes the goal?")

        # Check 3: Turn
        if not beat.get('turn'):
            issues.append("Missing TURN - How does the situation change?")

        # Check 4: Reveal
        if not beat.get('reveal'):
            issues.append("Missing REVEAL - What new information emerges?")

        # Check 5: Emotional State
        if not beat.get('emotional_state'):
            issues.append("Missing EMOTIONAL_STATE - What does character feel?")

        # Check 6: Ghost Logic
        ghost_valid, ghost_msg = self.ghost_register.validate_ghost_appearance(beat)
        if not ghost_valid:
            issues.append(f"GHOST LOGIC VIOLATION - {ghost_msg}")

        # Log validation
        self.validation_log.append({
            "beat_index": beat_index,
            "beat_id": beat.get('beat_id', 'unknown'),
            "valid": len(issues) == 0,
            "issues": issues,
            "timestamp": datetime.now().isoformat()
        })

        return len(issues) == 0, issues

    def validate_episode(self, episode_data: Dict) -> Dict:
        """
        Validate entire episode structure

        Returns:
            {
                "valid": bool,
                "total_beats": int,
                "valid_beats": int,
                "invalid_beats": int,
                "issues_by_beat": dict,
                "ghost_stats": dict
            }
        """
        results = {
            "valid": True,
            "total_beats": 0,
            "valid_beats": 0,
            "invalid_beats": 0,
            "issues_by_beat": {},
            "ghost_stats": {}
        }

        # Validate each scene's beats
        for scene_idx, scene in enumerate(episode_data.get('scenes', [])):
            for beat_idx, beat in enumerate(scene.get('beats', [])):
                beat_global_idx = results['total_beats']
                is_valid, issues = self.validate_beat(beat, beat_global_idx)

                results['total_beats'] += 1

                if is_valid:
                    results['valid_beats'] += 1
                else:
                    results['invalid_beats'] += 1
                    results['valid'] = False
                    beat_id = beat.get('beat_id', f"scene{scene_idx}_beat{beat_idx}")
                    results['issues_by_beat'][beat_id] = issues

        # Get ghost appearance stats
        results['ghost_stats'] = self.ghost_register.get_entity_stats()

        return results

    def generate_validation_report(self, episode_data: Dict, output_path: str = None) -> str:
        """Generate human-readable validation report"""
        results = self.validate_episode(episode_data)

        report = []
        report.append("="*60)
        report.append("STORY VALIDATION REPORT")
        report.append("="*60)
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        # Summary
        report.append(f"📊 SUMMARY")
        report.append(f"   Total Beats: {results['total_beats']}")
        report.append(f"   Valid Beats: {results['valid_beats']} ✅")
        report.append(f"   Invalid Beats: {results['invalid_beats']} ❌")
        report.append(f"   Overall: {'PASS ✅' if results['valid'] else 'FAIL ❌'}\n")

        # Ghost appearance stats
        report.append(f"👻 GHOST APPEARANCE STATS")
        for entity_id, stats in results['ghost_stats'].items():
            report.append(f"   {entity_id}:")
            report.append(f"      Count: {stats['count']} / {stats['target']}")
            report.append(f"      Progress: {stats['percentage']:.1f}%")

        # Issues by beat
        if results['issues_by_beat']:
            report.append(f"\n❌ BEATS WITH ISSUES:")
            for beat_id, issues in results['issues_by_beat'].items():
                report.append(f"\n   Beat: {beat_id}")
                for issue in issues:
                    report.append(f"      • {issue}")

        # Recommendations
        report.append(f"\n💡 RECOMMENDATIONS:")
        if results['invalid_beats'] > 0:
            report.append(f"   1. Fix {results['invalid_beats']} beats before rendering")
            report.append(f"   2. Add missing narrative elements (Goal/Conflict/Turn/Reveal)")
            report.append(f"   3. Justify all ghost appearances with triggers")
        else:
            report.append(f"   ✅ All beats validated - ready for rendering")

        report_text = "\n".join(report)

        # Save to file if path provided
        if output_path:
            with open(output_path, 'w') as f:
                f.write(report_text)
            print(f"✅ Validation report saved: {output_path}")

        return report_text


def load_episode_for_validation(episode_path: str) -> Dict:
    """Load episode JSON and prepare for validation"""
    with open(episode_path, 'r') as f:
        episode = json.load(f)
    return episode


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Validate Blackwood episode story structure")
    parser.add_argument("episode_file", help="Path to episode JSON file")
    parser.add_argument("--output", "-o", help="Output report path")
    args = parser.parse_args()

    # Load episode
    print(f"Loading episode: {args.episode_file}")
    episode_data = load_episode_for_validation(args.episode_file)

    # Create validator
    validator = StoryValidator()

    # Generate report
    output_path = args.output or args.episode_file.replace('.json', '_validation_report.txt')
    report = validator.generate_validation_report(episode_data, output_path)

    # Print to console
    print("\n" + report)

    # Exit code based on validation
    results = validator.validate_episode(episode_data)
    exit(0 if results['valid'] else 1)
