#!/usr/bin/env python3
"""
STORY BIBLE PARSER TESTS
========================
Run before ANY server restart: python3 tests/test_story_bible_parser.py

These tests MUST pass or the server should NOT be restarted.
"""

import sys
import json
import unittest
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from UNIVERSAL_SCRIPT_PARSER import UniversalScriptParser, parse_script_to_story_bible


class TestCharacterSanitization(unittest.TestCase):
    """Test that character sanitization removes bad patterns"""

    # Patterns that should NEVER appear as character names
    FORBIDDEN_PATTERNS = {
        'he', 'she', 'they', 'it', 'we', 'you', 'i', 'me', 'him', 'her',
        'them', 'us', 'then', 'now', 'day', 'night', 'continuous', 'later',
        'int', 'ext', 'cut', 'fade', 'suddenly', 'finally'
    }

    def test_pronouns_filtered(self):
        """Pronouns should never be character names"""
        script = """
        SCENE 1: OFFICE - DAY

        He walks in.
        HE: "Hello there."

        She responds.
        SHE: "Welcome back."

        JOHN: "Let's begin."
        """
        result = parse_script_to_story_bible(script, "test", "drama", "5min")
        char_names = [c['name'].lower() for c in result.get('characters', [])]

        self.assertNotIn('he', char_names, "Pronoun 'He' should be filtered")
        self.assertNotIn('she', char_names, "Pronoun 'She' should be filtered")
        self.assertIn('john', char_names, "Valid character 'John' should be kept")

    def test_scene_fragments_filtered(self):
        """Scene heading fragments should not become characters"""
        script = """
        INT. MANSION - DAY

        DAY
        A LAWYER enters the room.

        LAWYER: "I have the documents."

        CONTINUOUS
        ARTHUR GRAY stands by the window.

        ARTHUR: "Show me."
        """
        result = parse_script_to_story_bible(script, "test", "drama", "5min")
        char_names = [c['name'].lower() for c in result.get('characters', [])]

        # "DAY\n\nA LAWYER" should become "LAWYER", not "DAY A LAWYER"
        self.assertNotIn('day', char_names, "Scene term 'DAY' should be filtered")
        self.assertNotIn('continuous', char_names, "Scene term 'CONTINUOUS' should be filtered")

        # Valid characters should remain
        has_lawyer = any('lawyer' in name for name in char_names)
        has_arthur = any('arthur' in name for name in char_names)
        self.assertTrue(has_lawyer, "Valid character 'Lawyer' should be kept")
        self.assertTrue(has_arthur, "Valid character 'Arthur' should be kept")

    def test_newline_contamination_cleaned(self):
        """Names with newlines should extract the real character"""
        script = """
        SCENE 1: MANOR - NIGHT

        DAY

        A LAWYER reads documents.

        LAWYER: "The will is clear."

        CONTINUOUS

        ARTHUR GRAY enters.

        ARTHUR: "What does it say?"
        """
        result = parse_script_to_story_bible(script, "test", "drama", "5min")
        char_names = [c['name'].upper() for c in result.get('characters', [])]

        # Should NOT have contaminated names
        contaminated = [n for n in char_names if '\n' in n or 'DAY' in n.split()[0]]
        self.assertEqual(len(contaminated), 0, f"Found contaminated names: {contaminated}")

    def test_deduplication(self):
        """Duplicate character names should be merged"""
        script = """
        SCENE 1: OFFICE

        EVELYN: "Hello."
        EVELYN RAVENCROFT: "I am Evelyn Ravencroft."
        Evelyn: "Yes, that's me."

        JOHN: "Nice to meet you."
        """
        result = parse_script_to_story_bible(script, "test", "drama", "5min")
        char_names = [c['name'].upper() for c in result.get('characters', [])]

        # Count how many "EVELYN" variants we have
        evelyn_count = sum(1 for n in char_names if 'EVELYN' in n)
        self.assertEqual(evelyn_count, 1, f"Should have 1 Evelyn, found {evelyn_count}: {char_names}")

    def test_action_words_filtered(self):
        """Common action words should not be characters"""
        script = """
        SCENE 1: ROOM

        Then the door opens.
        THEN: "What?"

        Now we see MARY enter.
        MARY: "I'm here."

        Suddenly a noise.
        """
        result = parse_script_to_story_bible(script, "test", "drama", "5min")
        char_names = [c['name'].lower() for c in result.get('characters', [])]

        self.assertNotIn('then', char_names, "'Then' should be filtered")
        self.assertNotIn('now', char_names, "'Now' should be filtered")
        self.assertNotIn('suddenly', char_names, "'Suddenly' should be filtered")
        self.assertIn('mary', char_names, "Valid character 'Mary' should be kept")


class TestRavencroftScript(unittest.TestCase):
    """Test with the actual Ravencroft script if available"""

    @classmethod
    def setUpClass(cls):
        script_path = Path(__file__).parent.parent / "pipeline_outputs" / "ravencroft_v6_upload" / "imported_script.txt"
        if script_path.exists():
            cls.script_text = script_path.read_text()
            cls.result = parse_script_to_story_bible(
                cls.script_text, "ravencroft_test", "gothic_horror", "45min"
            )
        else:
            cls.script_text = None
            cls.result = None

    def test_ravencroft_character_count(self):
        """Ravencroft should have ~7 characters, not 18+"""
        if not self.result:
            self.skipTest("Ravencroft script not available")

        char_count = len(self.result.get('characters', []))
        self.assertLessEqual(char_count, 10, f"Too many characters: {char_count} (expected ~7)")
        self.assertGreaterEqual(char_count, 5, f"Too few characters: {char_count} (expected ~7)")

    def test_ravencroft_no_pronouns(self):
        """Ravencroft should have no pronoun characters"""
        if not self.result:
            self.skipTest("Ravencroft script not available")

        char_names = [c['name'].lower() for c in self.result.get('characters', [])]
        pronouns = ['he', 'she', 'they', 'it', 'you', 'them']

        for pronoun in pronouns:
            self.assertNotIn(pronoun, char_names, f"Pronoun '{pronoun}' found in characters")

    def test_ravencroft_expected_characters(self):
        """Ravencroft should have the main cast"""
        if not self.result:
            self.skipTest("Ravencroft script not available")

        char_names = ' '.join([c['name'].lower() for c in self.result.get('characters', [])])

        # These should be present (partial match)
        expected = ['margaret', 'evelyn', 'clara', 'arthur', 'elias']
        for name in expected:
            self.assertIn(name, char_names, f"Expected character '{name}' not found")


class TestLocationExtraction(unittest.TestCase):
    """Test that locations are properly extracted"""

    def test_locations_extracted(self):
        """Locations should be extracted from scene headings"""
        script = """
        INT. RAVENCROFT MANOR - RITUAL ROOM - NIGHT

        The room is dark.

        EXT. GARDEN - DAY

        Birds sing.

        INT. LIBRARY - CONTINUOUS

        Books everywhere.
        """
        result = parse_script_to_story_bible(script, "test", "gothic", "5min")
        locations = result.get('locations', [])

        self.assertGreater(len(locations), 0, "Should extract at least one location")


class TestAIActorContamination(unittest.TestCase):
    """V13.2: Test that AI Actor names don't appear as story character names"""

    # AI Actor names that should NEVER appear as story character names
    AI_ACTOR_NAMES = {
        'maya chen', 'jackson wright', 'elena rodriguez', 'marcus johnson',
        'sophia williams', 'david kim', 'isabella martinez', 'james thompson',
        'olivia brown', 'michael davis', 'emma wilson', 'william taylor'
    }

    def test_no_ai_actor_names_in_story(self):
        """AI actor names should not be used as story character names"""
        # Import the character generation function
        try:
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from orchestrator_server import _generate_story_characters_with_llm

            # Generate characters for different genres
            for genre in ['gothic_horror', 'scifi_thriller', 'crime_drama']:
                characters = _generate_story_characters_with_llm(
                    "Test story prompt", genre, count=4
                )
                for char in characters:
                    char_name = char['name'].lower() if isinstance(char, dict) else char.lower()
                    for ai_name in self.AI_ACTOR_NAMES:
                        self.assertNotIn(
                            ai_name, char_name,
                            f"AI Actor name '{ai_name}' found in story character for {genre}"
                        )
        except ImportError:
            self.skipTest("orchestrator_server not available for import")

    def test_character_casting_is_separate(self):
        """Casting should map story characters to AI actors, not replace them"""
        try:
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from orchestrator_server import (
                _generate_story_characters_with_llm,
                _cast_ai_actors_to_characters
            )

            # Generate story characters
            story_chars = _generate_story_characters_with_llm(
                "A gothic horror story", "gothic_horror", count=3
            )

            # Cast AI actors
            casting = _cast_ai_actors_to_characters(story_chars, "gothic_horror")

            # Verify casting is separate
            for char in story_chars:
                char_name = char['name'] if isinstance(char, dict) else char
                if char_name in casting:
                    ai_actor = casting[char_name]['ai_actor']
                    # Story character name should NOT equal AI actor name
                    self.assertNotEqual(
                        char_name.lower(), ai_actor.lower(),
                        f"Story character '{char_name}' should not equal AI actor '{ai_actor}'"
                    )
        except ImportError:
            self.skipTest("orchestrator_server not available for import")


class TestCharacterGeneration(unittest.TestCase):
    """V13.2: Test LLM-powered character generation"""

    def test_character_structure(self):
        """Generated characters should have required fields"""
        try:
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from orchestrator_server import _generate_story_characters_with_llm

            characters = _generate_story_characters_with_llm(
                "A mystery thriller", "thriller", count=3
            )

            self.assertGreater(len(characters), 0, "Should generate at least 1 character")

            for char in characters:
                self.assertIn('name', char, "Character must have 'name'")
                self.assertIn('description', char, "Character must have 'description'")
                self.assertIsInstance(char['name'], str, "Name must be a string")
                self.assertGreater(len(char['name']), 2, "Name must be more than 2 chars")
        except ImportError:
            self.skipTest("orchestrator_server not available for import")

    def test_genre_appropriate_names(self):
        """Characters should have genre-appropriate names"""
        try:
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from orchestrator_server import _generate_story_characters_with_llm

            # Gothic horror should have Victorian-style names
            gothic_chars = _generate_story_characters_with_llm(
                "Gothic horror", "gothic_horror", count=3
            )

            # Basic check - names should exist and be reasonable
            for char in gothic_chars:
                name = char['name'] if isinstance(char, dict) else char
                self.assertIsNotNone(name)
                self.assertGreater(len(name), 3)
        except ImportError:
            self.skipTest("orchestrator_server not available for import")


if __name__ == '__main__':
    print("\n" + "="*70)
    print("ATLAS STORY BIBLE PARSER TESTS + V13.2 CHARACTER GENERATION")
    print("="*70)
    print("These tests MUST pass before restarting the server!\n")

    # Run tests
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Summary
    print("\n" + "="*70)
    if result.wasSuccessful():
        print("✅ ALL TESTS PASSED - Safe to restart server!")
        sys.exit(0)
    else:
        print("❌ TESTS FAILED - DO NOT restart server!")
        print(f"   Failures: {len(result.failures)}")
        print(f"   Errors: {len(result.errors)}")
        sys.exit(1)
