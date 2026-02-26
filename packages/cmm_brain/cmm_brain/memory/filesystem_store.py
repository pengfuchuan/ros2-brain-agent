# Copyright 2026 ROS2 Brain Agent Team
# SPDX-License-Identifier: Apache-2.0

"""
FileSystemMemoryStore - File-based implementation of MemoryStore.

Storage structure:
    memory/
      sessions/
        <session_id>/
          turns.jsonl
          events.jsonl
          summary.json
          facts.json
      global/
        user_facts.json
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from .memory_store import (
    Event,
    Facts,
    MemoryStore,
    Summary,
    Turn
)


class FileSystemMemoryStore(MemoryStore):
    """
    File-based memory storage implementation.

    Uses JSONL for append-only data (turns, events) and JSON for
    structured data (summary, facts).
    """

    def __init__(self, base_path: str = "memory"):
        """
        Initialize FileSystemMemoryStore.

        Args:
            base_path: Base directory for memory storage
        """
        self.base_path = Path(base_path)
        self.sessions_path = self.base_path / "sessions"
        self.global_path = self.base_path / "global"

        # Ensure directories exist
        self.sessions_path.mkdir(parents=True, exist_ok=True)
        self.global_path.mkdir(parents=True, exist_ok=True)

        # Initialize global facts if not exists
        self._init_global_facts()

    def _init_global_facts(self) -> None:
        """Initialize global facts file if it doesn't exist."""
        global_facts_path = self.global_path / "user_facts.json"
        if not global_facts_path.exists():
            self._write_json(global_facts_path, Facts(
                schema_version=1,
                facts={}
            ).to_dict())

    def _get_session_path(self, session_id: str) -> Path:
        """Get path to session directory."""
        return self.sessions_path / session_id

    def _ensure_session_dir(self, session_id: str) -> Path:
        """Ensure session directory exists and return path."""
        session_path = self._get_session_path(session_id)
        session_path.mkdir(parents=True, exist_ok=True)
        return session_path

    def _read_json(self, path: Path) -> Dict[str, Any]:
        """Read JSON file."""
        if not path.exists():
            return {}
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    def _write_json(self, path: Path, data: Dict[str, Any]) -> None:
        """Write JSON file atomically."""
        temp_path = path.with_suffix('.tmp')
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        temp_path.replace(path)

    def _append_jsonl(self, path: Path, data: Dict[str, Any]) -> None:
        """Append a line to JSONL file."""
        with open(path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(data, ensure_ascii=False) + '\n')

    def _read_jsonl(self, path: Path, limit: int = -1, offset: int = 0) -> List[Dict[str, Any]]:
        """Read lines from JSONL file."""
        if not path.exists():
            return []

        results = []
        with open(path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # Apply offset and limit
        if offset > 0:
            lines = lines[offset:]
        if limit > 0:
            lines = lines[:limit]

        for line in lines:
            line = line.strip()
            if line:
                try:
                    results.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

        return results

    # ===================
    # Turn Operations
    # ===================

    def append_turn(self, session_id: str, turn: Turn) -> None:
        """Append a turn to the session's conversation history."""
        self._ensure_session_dir(session_id)
        turns_path = self._get_session_path(session_id) / "turns.jsonl"
        self._append_jsonl(turns_path, turn.to_dict())

    def get_recent_turns(
        self,
        session_id: str,
        limit: int = 20,
        offset: int = 0
    ) -> List[Turn]:
        """Get recent turns from a session."""
        turns_path = self._get_session_path(session_id) / "turns.jsonl"
        data_list = self._read_jsonl(turns_path, limit=limit, offset=offset)
        return [Turn.from_dict(data) for data in data_list]

    def get_all_turns(self, session_id: str) -> List[Turn]:
        """Get all turns from a session."""
        turns_path = self._get_session_path(session_id) / "turns.jsonl"
        data_list = self._read_jsonl(turns_path)
        return [Turn.from_dict(data) for data in data_list]

    # ===================
    # Event Operations
    # ===================

    def append_event(self, session_id: str, event: Event) -> None:
        """Append an event to the session's event log."""
        self._ensure_session_dir(session_id)
        events_path = self._get_session_path(session_id) / "events.jsonl"
        self._append_jsonl(events_path, event.to_dict())

    def get_events(
        self,
        session_id: str,
        event_type: Optional[str] = None,
        limit: int = 100
    ) -> List[Event]:
        """Get events from a session."""
        events_path = self._get_session_path(session_id) / "events.jsonl"
        data_list = self._read_jsonl(events_path, limit=limit)

        events = [Event.from_dict(data) for data in data_list]

        if event_type:
            events = [e for e in events if e.event_type == event_type]

        return events

    # ===================
    # Summary Operations
    # ===================

    def get_summary(self, session_id: str) -> Optional[Summary]:
        """Get the summary for a session."""
        summary_path = self._get_session_path(session_id) / "summary.json"
        data = self._read_json(summary_path)
        if not data:
            return None
        return Summary.from_dict(data)

    def set_summary(self, session_id: str, summary: Summary) -> None:
        """Set or update the summary for a session."""
        self._ensure_session_dir(session_id)
        summary_path = self._get_session_path(session_id) / "summary.json"
        self._write_json(summary_path, summary.to_dict())

    # ===================
    # Facts Operations
    # ===================

    def get_session_facts(self, session_id: str) -> Facts:
        """Get facts for a specific session."""
        facts_path = self._get_session_path(session_id) / "facts.json"
        data = self._read_json(facts_path)
        if not data:
            return Facts(schema_version=1, facts={})
        return Facts.from_dict(data)

    def get_global_facts(self) -> Facts:
        """Get global user facts."""
        facts_path = self.global_path / "user_facts.json"
        data = self._read_json(facts_path)
        if not data:
            return Facts(schema_version=1, facts={})
        return Facts.from_dict(data)

    def upsert_session_facts(
        self,
        session_id: str,
        key: str,
        value: Any
    ) -> None:
        """Upsert a fact in the session facts."""
        self._ensure_session_dir(session_id)
        facts = self.get_session_facts(session_id)
        facts.facts[key] = value
        facts_path = self._get_session_path(session_id) / "facts.json"
        self._write_json(facts_path, facts.to_dict())

    def upsert_global_facts(self, key: str, value: Any) -> None:
        """Upsert a fact in the global facts."""
        facts = self.get_global_facts()
        facts.facts[key] = value
        facts_path = self.global_path / "user_facts.json"
        self._write_json(facts_path, facts.to_dict())

    def delete_session_fact(self, session_id: str, key: str) -> bool:
        """Delete a fact from session facts."""
        facts = self.get_session_facts(session_id)
        if key not in facts.facts:
            return False
        del facts.facts[key]
        facts_path = self._get_session_path(session_id) / "facts.json"
        self._write_json(facts_path, facts.to_dict())
        return True

    def delete_global_fact(self, key: str) -> bool:
        """Delete a fact from global facts."""
        facts = self.get_global_facts()
        if key not in facts.facts:
            return False
        del facts.facts[key]
        facts_path = self.global_path / "user_facts.json"
        self._write_json(facts_path, facts.to_dict())
        return True

    # ===================
    # Session Management
    # ===================

    def session_exists(self, session_id: str) -> bool:
        """Check if a session exists."""
        session_path = self._get_session_path(session_id)
        return session_path.exists() and session_path.is_dir()

    def create_session(self, session_id: str) -> None:
        """Create a new session."""
        session_path = self._ensure_session_dir(session_id)

        # Initialize empty files
        turns_path = session_path / "turns.jsonl"
        events_path = session_path / "events.jsonl"

        if not turns_path.exists():
            turns_path.touch()

        if not events_path.exists():
            events_path.touch()

        # Create metadata with creation timestamp
        metadata_path = session_path / "metadata.json"
        if not metadata_path.exists():
            from datetime import datetime
            metadata = {
                "session_id": session_id,
                "created_at": datetime.now().isoformat()
            }
            self._write_json(metadata_path, metadata)

    def get_session_metadata(self, session_id: str) -> Dict[str, Any]:
        """Get metadata for a session."""
        metadata_path = self._get_session_path(session_id) / "metadata.json"
        return self._read_json(metadata_path)

    def list_sessions_with_metadata(self) -> List[Dict[str, Any]]:
        """List all sessions with their metadata."""
        if not self.sessions_path.exists():
            return []

        sessions = []
        for item in self.sessions_path.iterdir():
            if item.is_dir():
                session_id = item.name
                metadata = self.get_session_metadata(session_id)
                sessions.append({
                    "session_id": session_id,
                    "created_at": metadata.get("created_at", "")
                })

        # Sort by created_at descending (newest first)
        sessions.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return sessions

    def list_sessions(self) -> List[str]:
        """List all session IDs."""
        if not self.sessions_path.exists():
            return []

        sessions = []
        for item in self.sessions_path.iterdir():
            if item.is_dir():
                sessions.append(item.name)

        return sorted(sessions)

    # ===================
    # Additional Utility Methods
    # ===================

    def get_turn_count(self, session_id: str) -> int:
        """Get the number of turns in a session."""
        turns_path = self._get_session_path(session_id) / "turns.jsonl"
        if not turns_path.exists():
            return 0

        count = 0
        with open(turns_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    count += 1
        return count

    def get_next_turn_id(self, session_id: str) -> int:
        """Get the next turn ID for a session."""
        return self.get_turn_count(session_id) + 1

    def clear_session(self, session_id: str) -> bool:
        """Clear all data for a session."""
        import shutil
        session_path = self._get_session_path(session_id)
        if session_path.exists():
            shutil.rmtree(session_path)
            return True
        return False

    def delete_session(self, session_id: str) -> bool:
        """Delete a session and all its data (alias for clear_session)."""
        return self.clear_session(session_id)
