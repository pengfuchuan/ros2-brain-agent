# Copyright 2026 ROS2 Brain Agent Team
# SPDX-License-Identifier: Apache-2.0

"""
Tests for FileSystemMemoryStore.
"""

import json
import os
import tempfile
import unittest
import sys

# Add packages to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'packages', 'cmm_brain'))

from cmm_brain.memory import FileSystemMemoryStore, Turn, Event, Summary, Facts


class TestFileSystemMemoryStore(unittest.TestCase):
    """Test cases for FileSystemMemoryStore."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.store = FileSystemMemoryStore(self.temp_dir)

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_create_session(self):
        """Test session creation."""
        session_id = "test_session_1"

        self.assertFalse(self.store.session_exists(session_id))
        self.store.create_session(session_id)
        self.assertTrue(self.store.session_exists(session_id))

    def test_append_and_get_turns(self):
        """Test turn append and retrieval."""
        session_id = "test_session_2"
        self.store.create_session(session_id)

        # Append turns
        turn1 = Turn(
            turn_id=1,
            ts="2026-02-17T10:00:00Z",
            speaker="user",
            text="Hello"
        )
        turn2 = Turn(
            turn_id=2,
            ts="2026-02-17T10:00:05Z",
            speaker="assistant",
            text="Hi there!"
        )

        self.store.append_turn(session_id, turn1)
        self.store.append_turn(session_id, turn2)

        # Get turns
        turns = self.store.get_recent_turns(session_id, limit=10)
        self.assertEqual(len(turns), 2)
        self.assertEqual(turns[0].text, "Hello")
        self.assertEqual(turns[1].text, "Hi there!")

    def test_append_and_get_events(self):
        """Test event append and retrieval."""
        session_id = "test_session_3"
        self.store.create_session(session_id)

        # Append event
        event = Event(
            event_id="e-001",
            ts="2026-02-17T10:00:03Z",
            event_type="tool_invoke",
            session_id=session_id,
            payload={"tool": "nav2.goto", "args": {}}
        )

        self.store.append_event(session_id, event)

        # Get events
        events = self.store.get_events(session_id)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, "tool_invoke")

    def test_summary_operations(self):
        """Test summary operations."""
        session_id = "test_session_4"
        self.store.create_session(session_id)

        # Initially no summary
        summary = self.store.get_summary(session_id)
        self.assertIsNone(summary)

        # Set summary
        summary = Summary(
            version=1,
            updated_at="2026-02-17T10:05:00Z",
            summary_text="Test summary",
            key_points=["point1", "point2"]
        )
        self.store.set_summary(session_id, summary)

        # Get summary
        retrieved = self.store.get_summary(session_id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.summary_text, "Test summary")
        self.assertEqual(len(retrieved.key_points), 2)

    def test_facts_operations(self):
        """Test facts operations."""
        session_id = "test_session_5"
        self.store.create_session(session_id)

        # Upsert session fact
        self.store.upsert_session_facts(session_id, "user_name", "Test User")
        self.store.upsert_session_facts(session_id, "language", "en")

        # Get session facts
        facts = self.store.get_session_facts(session_id)
        self.assertEqual(facts.facts["user_name"], "Test User")
        self.assertEqual(facts.facts["language"], "en")

        # Upsert global fact
        self.store.upsert_global_facts("global_setting", "value1")
        global_facts = self.store.get_global_facts()
        self.assertEqual(global_facts.facts["global_setting"], "value1")

        # Delete fact
        deleted = self.store.delete_session_fact(session_id, "language")
        self.assertTrue(deleted)

        facts = self.store.get_session_facts(session_id)
        self.assertNotIn("language", facts.facts)

    def test_list_sessions(self):
        """Test listing sessions."""
        self.store.create_session("session_a")
        self.store.create_session("session_b")
        self.store.create_session("session_c")

        sessions = self.store.list_sessions()
        self.assertEqual(len(sessions), 3)
        self.assertIn("session_a", sessions)
        self.assertIn("session_b", sessions)
        self.assertIn("session_c", sessions)

    def test_get_turn_count(self):
        """Test turn count."""
        session_id = "test_session_6"
        self.store.create_session(session_id)

        self.assertEqual(self.store.get_turn_count(session_id), 0)

        self.store.append_turn(session_id, Turn(
            turn_id=1, ts="", speaker="user", text="t1"
        ))
        self.store.append_turn(session_id, Turn(
            turn_id=2, ts="", speaker="assistant", text="t2"
        ))

        self.assertEqual(self.store.get_turn_count(session_id), 2)


class TestTurn(unittest.TestCase):
    """Test cases for Turn dataclass."""

    def test_to_dict(self):
        """Test turn serialization."""
        turn = Turn(
            turn_id=1,
            ts="2026-02-17T10:00:00Z",
            speaker="user",
            text="Hello",
            metadata={"key": "value"}
        )

        data = turn.to_dict()
        self.assertEqual(data["turn_id"], 1)
        self.assertEqual(data["speaker"], "user")
        self.assertEqual(data["text"], "Hello")
        self.assertEqual(data["metadata"]["key"], "value")

    def test_from_dict(self):
        """Test turn deserialization."""
        data = {
            "turn_id": 2,
            "ts": "2026-02-17T10:00:05Z",
            "speaker": "assistant",
            "text": "Response",
            "metadata": {}
        }

        turn = Turn.from_dict(data)
        self.assertEqual(turn.turn_id, 2)
        self.assertEqual(turn.speaker, "assistant")
        self.assertEqual(turn.text, "Response")


if __name__ == '__main__':
    unittest.main()
