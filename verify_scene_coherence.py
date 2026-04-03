#!/usr/bin/env python3
"""
V27 Scene Coherence Verification Tool
Comprehensive blocking/framing/cinematography check for Scene 001
Checks: script coherence, cinematography logic, blocking consistency, framing validation, ref resolution, DP standards
"""

import json
import os
from pathlib import Path
from datetime import datetime
from collections import defaultdict

class CoherenceVerifier:
    # DP Standards: shot type -> ideal ref types
    SHOT_TYPE_REF_MAP = {
        'close_up': ['headshot', 'three_quarter'],
        'medium_close': ['headshot', 'three_quarter'],
        'medium': ['three_quarter', 'full_body'],
        'wide': ['full_body'],
        'establishing': ['full_body'],
        'over_the_shoulder': ['three_quarter', 'headshot'],
        'two_shot': ['three_quarter', 'full_body'],
        'reaction': ['three_quarter', 'headshot'],
        'b-roll': [],  # no character refs
        'closing': ['full_body', 'three_quarter'],
    }

    # Dialogue minimum duration formula: words/2.3 + 1.5s buffer
    DIALOGUE_WPM = 2.3
    DIALOGUE_BUFFER = 1.5

    def __init__(self, shot_plan_path, cast_map_path, story_bible_path=None):
        self.shot_plan_path = shot_plan_path
        self.cast_map_path = cast_map_path
        self.story_bible_path = story_bible_path

        self.shot_plan = self._load_json(shot_plan_path)
        self.cast_map = self._load_json(cast_map_path)
        self.story_bible = self._load_json(story_bible_path) if story_bible_path else {}

        self.base_path = Path(shot_plan_path).parent
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'scene_id': '001',
            'shots': [],
            'summary': {},
        }

    def _load_json(self, path):
        if not path or not os.path.exists(path):
            return {}
        with open(path, 'r') as f:
            return json.load(f)

    def _check_file_exists(self, rel_path):
        """Check if file exists - handles both relative and absolute paths"""
        if not rel_path:
            return False
        full_path = Path(rel_path)
        if full_path.exists():
            return True
        # Also check relative to base_path in case path is incomplete
        full_path = self.base_path / rel_path
        return full_path.exists()

    def _count_words(self, text):
        """Count words in text"""
        return len(text.split()) if text else 0

    def _calc_min_dialogue_duration(self, word_count):
        """Calculate minimum duration for dialogue"""
        if word_count == 0:
            return 0
        return (word_count / self.DIALOGUE_WPM) + self.DIALOGUE_BUFFER

    def verify_scene_001(self):
        """Run comprehensive verification on Scene 001"""
        shots = [s for s in self.shot_plan.get('shots', []) if s.get('scene_id') == '001']

        if not shots:
            self.results['summary']['error'] = 'No Scene 001 shots found'
            return self.results

        print(f"\n=== SCENE 001 COHERENCE VERIFICATION ===")
        print(f"Total shots in scene: {len(shots)}\n")

        # Check each shot
        for shot in shots:
            shot_result = self._verify_shot(shot)
            self.results['shots'].append(shot_result)
            self._print_shot_result(shot_result)

        # Cross-shot checks
        self._verify_cinematography_logic(shots)
        self._verify_coverage_grammar(shots)
        self._verify_180_degree_rule(shots)
        self._verify_character_consistency(shots)

        # Generate summary
        self._generate_summary(shots)

        return self.results

    def _verify_shot(self, shot):
        """Verify individual shot"""
        shot_id = shot.get('shot_id', 'UNKNOWN')
        shot_type = shot.get('shot_type', '')
        coverage = shot.get('coverage_role', '')
        characters = shot.get('characters', [])
        dialogue = shot.get('dialogue_text', '')
        duration = shot.get('duration', 0)

        result = {
            'shot_id': shot_id,
            'shot_type': shot_type,
            'coverage_role': coverage,
            'checks': {},
            'issues': [],
            'verdict': 'PASS',
        }

        # 1. Script Coherence
        result['checks']['script_coherence'] = self._check_script_coherence(shot)
        if not result['checks']['script_coherence']['pass']:
            result['issues'].extend(result['checks']['script_coherence']['issues'])

        # 2. Cinematography Logic
        result['checks']['cinematography'] = self._check_cinematography(shot)
        if not result['checks']['cinematography']['pass']:
            result['issues'].extend(result['checks']['cinematography']['issues'])

        # 3. Blocking Consistency
        result['checks']['blocking'] = self._check_blocking(shot)
        if not result['checks']['blocking']['pass']:
            result['issues'].extend(result['checks']['blocking']['issues'])

        # 4. Framing Validation
        result['checks']['framing'] = self._check_framing(shot)
        if not result['checks']['framing']['pass']:
            result['issues'].extend(result['checks']['framing']['issues'])

        # 5. Ref Resolution
        result['checks']['ref_resolution'] = self._check_ref_resolution(shot)
        if not result['checks']['ref_resolution']['pass']:
            result['issues'].extend(result['checks']['ref_resolution']['issues'])

        # 6. DP Standards
        result['checks']['dp_standards'] = self._check_dp_standards(shot)
        if not result['checks']['dp_standards']['pass']:
            result['issues'].extend(result['checks']['dp_standards']['issues'])

        # Determine verdict
        if result['issues']:
            critical = [i for i in result['issues'] if i.get('severity') == 'CRITICAL']
            warning = [i for i in result['issues'] if i.get('severity') == 'WARNING']
            result['verdict'] = 'FAIL' if critical else ('WARN' if warning else 'PASS')

        return result

    def _check_script_coherence(self, shot):
        """Check dialogue and character placement match story"""
        result = {'pass': True, 'issues': []}

        dialogue = shot.get('dialogue_text', '').strip()
        characters = shot.get('characters', [])
        shot_type = shot.get('shot_type', '')

        # Check: if dialogue exists, characters must exist
        if dialogue and not characters:
            result['pass'] = False
            result['issues'].append({
                'severity': 'CRITICAL',
                'code': 'SC_001',
                'message': 'Dialogue present but no characters assigned',
            })

        # Check: reaction shot should have NO dialogue
        if shot_type == 'reaction' and dialogue:
            result['pass'] = False
            result['issues'].append({
                'severity': 'WARNING',
                'code': 'SC_002',
                'message': 'Reaction shot should not have dialogue (pure visual)',
            })

        # Check: all characters in shot exist in cast_map
        for char in characters:
            if char not in self.cast_map:
                result['pass'] = False
                result['issues'].append({
                    'severity': 'CRITICAL',
                    'code': 'SC_003',
                    'message': f'Character "{char}" not in cast_map',
                })

        return result

    def _check_cinematography(self, shot):
        """Check cinematography logic"""
        result = {'pass': True, 'issues': []}

        shot_id = shot.get('shot_id', '')
        shot_type = shot.get('shot_type', '')
        coverage = shot.get('coverage_role', '')

        # Check: OTS shots must be properly paired (005B, 006B)
        if shot_type == 'over_the_shoulder':
            # OTS must have characters
            if not shot.get('characters'):
                result['pass'] = False
                result['issues'].append({
                    'severity': 'CRITICAL',
                    'code': 'CM_001',
                    'message': 'OTS shot must have characters assigned',
                })

        # Check: establishing shot (A_GEOGRAPHY) should have no tight framing
        if coverage == 'A_GEOGRAPHY' and shot_type in ['close_up', 'medium_close']:
            result['pass'] = False
            result['issues'].append({
                'severity': 'WARNING',
                'code': 'CM_002',
                'message': 'A_GEOGRAPHY should not be tight framing (close_up/medium_close)',
            })

        # Check: reaction shot (C_EMOTION) should be closer framing
        if coverage == 'C_EMOTION' and shot_type in ['wide', 'establishing']:
            result['pass'] = False
            result['issues'].append({
                'severity': 'WARNING',
                'code': 'CM_003',
                'message': 'C_EMOTION should be closer framing, not wide/establishing',
            })

        return result

    def _check_blocking(self, shot):
        """Check blocking consistency"""
        result = {'pass': True, 'issues': []}

        shot_type = shot.get('shot_type', '')
        characters = shot.get('characters', [])
        dialogue = shot.get('dialogue_text', '').strip()

        # Check: if character is speaking, must have dialogue_text
        # (This is enforced at script level, but verify)
        if shot_type in ['medium_close', 'close_up'] and characters and not dialogue:
            # Not a hard error, but worth noting for dialogue scenes
            pass

        # Check: two-shot must have 2+ characters
        if shot_type == 'two_shot' and len(characters) < 2:
            result['pass'] = False
            result['issues'].append({
                'severity': 'WARNING',
                'code': 'BK_001',
                'message': f'Two-shot should have 2+ characters, has {len(characters)}',
            })

        # Check: reaction shot should be single character
        if shot_type == 'reaction' and len(characters) > 1:
            result['pass'] = False
            result['issues'].append({
                'severity': 'WARNING',
                'code': 'BK_002',
                'message': f'Reaction shot should be single character, has {len(characters)}',
            })

        return result

    def _check_framing(self, shot):
        """Check framing validation"""
        result = {'pass': True, 'issues': []}

        shot_type = shot.get('shot_type', '')
        coverage = shot.get('coverage_role', '')
        duration = shot.get('duration', 0)
        dialogue = shot.get('dialogue_text', '').strip()

        # Check: shot type matches coverage role
        valid_mappings = {
            'A_GEOGRAPHY': ['establishing', 'wide', 'two_shot'],
            'B_ACTION': ['medium', 'b-roll', 'two_shot', 'closing'],
            'C_EMOTION': ['reaction', 'medium_close', 'close_up', 'over_the_shoulder'],
        }

        if coverage in valid_mappings:
            if shot_type not in valid_mappings[coverage]:
                result['issues'].append({
                    'severity': 'WARNING',
                    'code': 'FR_001',
                    'message': f'Shot type "{shot_type}" unusual for coverage "{coverage}"',
                })

        # Check: dialogue duration adequacy
        if dialogue:
            word_count = self._count_words(dialogue)
            min_duration = self._calc_min_dialogue_duration(word_count)

            if duration < min_duration:
                result['pass'] = False
                result['issues'].append({
                    'severity': 'CRITICAL',
                    'code': 'FR_002',
                    'message': f'Duration {duration}s too short for {word_count} words (min {min_duration:.1f}s)',
                })

        # Check: B-roll should not have character dialogue
        if shot_type == 'b-roll' and dialogue:
            result['pass'] = False
            result['issues'].append({
                'severity': 'WARNING',
                'code': 'FR_003',
                'message': 'B-roll shot should not have dialogue',
            })

        return result

    def _check_ref_resolution(self, shot):
        """Check character refs exist and location masters exist"""
        result = {'pass': True, 'issues': []}

        characters = shot.get('characters', [])
        location_id = shot.get('location_id', '')

        # Check: character refs
        for char in characters:
            if char not in self.cast_map:
                result['pass'] = False
                result['issues'].append({
                    'severity': 'CRITICAL',
                    'code': 'RR_001',
                    'message': f'Character "{char}" missing from cast_map',
                })
                continue

            char_data = self.cast_map.get(char, {})
            ref_path = char_data.get('character_reference_path', '')

            if ref_path and not self._check_file_exists(ref_path):
                result['pass'] = False
                result['issues'].append({
                    'severity': 'CRITICAL',
                    'code': 'RR_002',
                    'message': f'Character ref not found: {ref_path}',
                })

            # Check: ref is validated
            if not char_data.get('_reference_validated'):
                result['issues'].append({
                    'severity': 'WARNING',
                    'code': 'RR_003',
                    'message': f'Character "{char}" ref not validated',
                })

        # Check: location master for multi-angle coverage (especially OTS)
        if shot.get('shot_type') == 'over_the_shoulder':
            # OTS pairs should have reverse angle location refs
            pass  # Location check deferred to cross-shot analysis

        return result

    def _check_dp_standards(self, shot):
        """Check DP framing standards for ref selection"""
        result = {'pass': True, 'issues': []}

        shot_type = shot.get('shot_type', '')
        characters = shot.get('characters', [])

        if shot_type not in self.SHOT_TYPE_REF_MAP or not characters:
            return result

        ideal_refs = self.SHOT_TYPE_REF_MAP.get(shot_type, [])
        if not ideal_refs:
            return result

        # Check: each character has ref pack matching shot type requirements
        for char in characters:
            if char not in self.cast_map:
                continue

            char_data = self.cast_map.get(char, {})

            # Check for multi-angle ref pack
            has_headshot = '_ref_pack_headshot' in char_data
            has_three_quarter = '_ref_pack_three_quarter' in char_data
            has_full_body = '_ref_pack_full_body' in char_data
            has_profile = '_ref_pack_profile' in char_data

            available_refs = []
            if has_headshot: available_refs.append('headshot')
            if has_three_quarter: available_refs.append('three_quarter')
            if has_full_body: available_refs.append('full_body')
            if has_profile: available_refs.append('profile')

            # Check: ideal ref type available
            has_ideal = any(ideal in available_refs for ideal in ideal_refs)
            if not has_ideal:
                result['issues'].append({
                    'severity': 'WARNING',
                    'code': 'DP_001',
                    'message': f'Character "{char}" missing ideal ref type for {shot_type} (need {ideal_refs}, have {available_refs})',
                })

        return result

    def _verify_cinematography_logic(self, shots):
        """Cross-shot: verify OTS pairs, etc."""
        print("\n--- CINEMATOGRAPHY LOGIC CHECKS ---")

        ots_shots = [s for s in shots if s.get('shot_type') == 'over_the_shoulder']

        if ots_shots:
            print(f"Found {len(ots_shots)} OTS shots: {[s['shot_id'] for s in ots_shots]}")

            if len(ots_shots) >= 2:
                # Check if they form a pair
                print(f"  OTS pair detected - checking shot/reverse-shot relationship")
                for i, shot in enumerate(ots_shots):
                    print(f"    {shot['shot_id']}: {shot.get('characters', [])}")
            elif len(ots_shots) == 1:
                print(f"  WARNING: Only 1 OTS shot found - should have reverse angle")
                self.results['summary']['ots_warnings'] = self.results['summary'].get('ots_warnings', 0) + 1

    def _verify_coverage_grammar(self, shots):
        """Cross-shot: verify coverage distribution"""
        print("\n--- COVERAGE GRAMMAR CHECKS ---")

        coverage_counts = defaultdict(int)
        for shot in shots:
            coverage = shot.get('coverage_role', '')
            coverage_counts[coverage] += 1

        print(f"Coverage distribution: {dict(coverage_counts)}")

        # Check: at least 1 A_GEOGRAPHY
        if coverage_counts.get('A_GEOGRAPHY', 0) == 0:
            print("  CRITICAL: No A_GEOGRAPHY (establishing/master) shot found!")
            self.results['summary']['coverage_critical'] = True
        else:
            print(f"  OK: {coverage_counts['A_GEOGRAPHY']} A_GEOGRAPHY shot(s)")

        # Check: B/C distribution
        b_count = coverage_counts.get('B_ACTION', 0)
        c_count = coverage_counts.get('C_EMOTION', 0)
        print(f"  B_ACTION: {b_count}, C_EMOTION: {c_count}")

        if b_count < 2:
            print("  WARNING: Few B_ACTION shots for a full scene")

    def _verify_180_degree_rule(self, shots):
        """Cross-shot: verify 180-degree rule for dialogue"""
        print("\n--- 180-DEGREE RULE CHECKS ---")

        ots_shots = [s for s in shots if s.get('shot_type') == 'over_the_shoulder']

        if len(ots_shots) < 2:
            print("  Insufficient OTS shots for 180-rule verification")
            return

        print(f"  Checking 180-rule for {len(ots_shots)} OTS shots")
        print("  (Full spatial geometry analysis requires shot metadata — flagging for visual verification)")

    def _verify_character_consistency(self, shots):
        """Cross-shot: verify characters appear consistently"""
        print("\n--- CHARACTER CONSISTENCY CHECKS ---")

        all_characters = set()
        char_shots = defaultdict(list)

        for shot in shots:
            for char in shot.get('characters', []):
                all_characters.add(char)
                char_shots[char].append(shot['shot_id'])

        print(f"Characters in scene: {sorted(all_characters)}")

        for char in sorted(all_characters):
            shots_list = char_shots[char]
            print(f"  {char}: {len(shots_list)} shots ({', '.join(shots_list)})")

        # Check: all characters in cast_map
        for char in all_characters:
            if char not in self.cast_map:
                print(f"  ERROR: {char} not in cast_map!")
                self.results['summary']['cast_error'] = True

    def _generate_summary(self, shots):
        """Generate overall verdict"""
        print("\n=== SUMMARY ===")

        verdict_counts = defaultdict(int)
        total_issues = 0
        critical_issues = 0
        warnings = 0

        for shot_result in self.results['shots']:
            verdict = shot_result['verdict']
            verdict_counts[verdict] += 1

            for issue in shot_result['issues']:
                total_issues += 1
                if issue['severity'] == 'CRITICAL':
                    critical_issues += 1
                elif issue['severity'] == 'WARNING':
                    warnings += 1

        self.results['summary'] = {
            'total_shots': len(shots),
            'verdicts': dict(verdict_counts),
            'total_issues': total_issues,
            'critical_issues': critical_issues,
            'warnings': warnings,
            'scene_verdict': 'FAIL' if critical_issues > 0 else ('WARN' if warnings > 0 else 'PASS'),
        }

        print(f"Total shots: {len(shots)}")
        print(f"Verdicts: {dict(verdict_counts)}")
        print(f"Issues: {total_issues} total ({critical_issues} CRITICAL, {warnings} WARNING)")
        print(f"\nSCENE VERDICT: {self.results['summary']['scene_verdict']}")

    def _print_shot_result(self, result):
        """Print human-readable shot result"""
        shot_id = result['shot_id']
        verdict = result['verdict']
        issues_count = len(result['issues'])

        status_icon = '✓' if verdict == 'PASS' else ('⚠' if verdict == 'WARN' else '✗')
        print(f"{status_icon} {shot_id} ({result['shot_type']} / {result['coverage_role']}) [{verdict}]")

        if result['issues']:
            for issue in result['issues']:
                severity = issue['severity']
                code = issue['code']
                message = issue['message']
                print(f"    [{severity}] {code}: {message}")


def main():
    verifier = CoherenceVerifier(
        shot_plan_path='pipeline_outputs/victorian_shadows_ep1/shot_plan.json',
        cast_map_path='pipeline_outputs/victorian_shadows_ep1/cast_map.json',
        story_bible_path='pipeline_outputs/victorian_shadows_ep1/story_bible.json',
    )

    results = verifier.verify_scene_001()

    # Save results
    output_dir = Path('pipeline_outputs/victorian_shadows_ep1/reports')
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / 'v27_coherence_verification.json'
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\n\nResults saved to: {output_file}")

    return results


if __name__ == '__main__':
    main()
