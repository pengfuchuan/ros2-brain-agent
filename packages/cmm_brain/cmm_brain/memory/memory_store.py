# Copyright 2026 ROS2 Brain Agent Team
# SPDX-License-Identifier: Apache-2.0

"""
MemoryStore - Abstract base class for memory storage.

This module defines the abstract interface for memory storage backends.
Implementations can use file system, SQLite, Redis, or other storage systems.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class EventType(Enum):
    """Event types for dialog events."""
    TURN_START = "turn_start"
    TURN_END = "turn_end"
    TOOL_INVOKE = "tool_invoke"
    TOOL_RESULT = "tool_result"
    SKILL_EXECUTE = "skill_execute"
    SKILL_RESULT = "skill_result"
    ERROR = "error"
    MEMORY_WRITE = "memory_write"
    LLM_CALL = "llm_call"
    LLM_RESULT = "llm_result"


@dataclass
class Turn:
    """Represents a single conversation turn."""
    turn_id: int
    ts: str  # ISO format timestamp
    speaker: str  # "user" or "assistant"
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "turn_id": self.turn_id,
            "ts": self.ts,
            "speaker": self.speaker,
            "text": self.text,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Turn":
        return cls(
            turn_id=data["turn_id"],
            ts=data["ts"],
            speaker=data["speaker"],
            text=data["text"],
            metadata=data.get("metadata", {})
        )


@dataclass
class Event:
    """Represents a system event for audit and replay."""
    event_id: str
    ts: str  # ISO format timestamp
    event_type: str
    session_id: str
    payload: Dict[str, Any]
    duration_ms: Optional[int] = None
    success: bool = True
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "ts": self.ts,
            "type": self.event_type,
            "session_id": self.session_id,
            "payload": self.payload,
            "duration_ms": self.duration_ms,
            "ok": self.success,
            "error_message": self.error_message
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Event":
        return cls(
            event_id=data["event_id"],
            ts=data["ts"],
            event_type=data["type"],
            session_id=data["session_id"],
            payload=data["payload"],
            duration_ms=data.get("duration_ms"),
            success=data.get("ok", True),
            error_message=data.get("error_message")
        )


@dataclass
class Summary:
    """Represents a session summary for long context compression."""
    version: int
    updated_at: str
    summary_text: str
    key_points: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "updated_at": self.updated_at,
            "summary_text": self.summary_text,
            "key_points": self.key_points
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Summary":
        return cls(
            version=data["version"],
            updated_at=data["updated_at"],
            summary_text=data["summary_text"],
            key_points=data.get("key_points", [])
        )


@dataclass
class Facts:
    """Represents user facts/profile data."""
    schema_version: int
    facts: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "facts": self.facts
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Facts":
        return cls(
            schema_version=data["schema_version"],
            facts=data.get("facts", {})
        )


class MemoryStore(ABC):
    """
    Abstract base class for memory storage.

    Provides interface for:
    - Turn management (conversation history)
    - Event logging (audit trail)
    - Summary management (context compression)
    - Facts management (user profile/preferences)
    """

    # ===================
    # Turn Operations
    # ===================

    @abstractmethod
    def append_turn(self, session_id: str, turn: Turn) -> None:
        """
        Append a turn to the session's conversation history.

        Args:
            session_id: Session identifier
            turn: Turn object to append
        """
        pass

    @abstractmethod
    def get_recent_turns(
        self,
        session_id: str,
        limit: int = 20,
        offset: int = 0
    ) -> List[Turn]:
        """
        Get recent turns from a session.

        Args:
            session_id: Session identifier
            limit: Maximum number of turns to return
            offset: Number of turns to skip

        Returns:
            List of Turn objects
        """
        pass

    @abstractmethod
    def get_all_turns(self, session_id: str) -> List[Turn]:
        """
        Get all turns from a session.

        Args:
            session_id: Session identifier

        Returns:
            List of all Turn objects
        """
        pass

    # ===================
    # Event Operations
    # ===================

    @abstractmethod
    def append_event(self, session_id: str, event: Event) -> None:
        """
        Append an event to the session's event log.

        Args:
            session_id: Session identifier
            event: Event object to append
        """
        pass

    @abstractmethod
    def get_events(
        self,
        session_id: str,
        event_type: Optional[str] = None,
        limit: int = 100
    ) -> List[Event]:
        """
        Get events from a session.

        Args:
            session_id: Session identifier
            event_type: Filter by event type (optional)
            limit: Maximum number of events to return

        Returns:
            List of Event objects
        """
        pass

    # ===================
    # Summary Operations
    # ===================

    @abstractmethod
    def get_summary(self, session_id: str) -> Optional[Summary]:
        """
        Get the summary for a session.

        Args:
            session_id: Session identifier

        Returns:
            Summary object or None if not exists
        """
        pass

    @abstractmethod
    def set_summary(self, session_id: str, summary: Summary) -> None:
        """
        Set or update the summary for a session.

        Args:
            session_id: Session identifier
            summary: Summary object to save
        """
        pass

    # ===================
    # Facts Operations
    # ===================

    @abstractmethod
    def get_session_facts(self, session_id: str) -> Facts:
        """
        Get facts for a specific session.

        Args:
            session_id: Session identifier

        Returns:
            Facts object
        """
        pass

    @abstractmethod
    def get_global_facts(self) -> Facts:
        """
        Get global user facts.

        Returns:
            Facts object
        """
        pass

    @abstractmethod
    def upsert_session_facts(
        self,
        session_id: str,
        key: str,
        value: Any
    ) -> None:
        """
        Upsert a fact in the session facts.

        Args:
            session_id: Session identifier
            key: Fact key
            value: Fact value
        """
        pass

    @abstractmethod
    def upsert_global_facts(self, key: str, value: Any) -> None:
        """
        Upsert a fact in the global facts.

        Args:
            key: Fact key
            value: Fact value
        """
        pass

    @abstractmethod
    def delete_session_fact(self, session_id: str, key: str) -> bool:
        """
        Delete a fact from session facts.

        Args:
            session_id: Session identifier
            key: Fact key to delete

        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    def delete_global_fact(self, key: str) -> bool:
        """
        Delete a fact from global facts.

        Args:
            key: Fact key to delete

        Returns:
            True if deleted, False if not found
        """
        pass

    # ===================
    # Session Management
    # ===================

    @abstractmethod
    def session_exists(self, session_id: str) -> bool:
        """
        Check if a session exists.

        Args:
            session_id: Session identifier

        Returns:
            True if session exists
        """
        pass

    @abstractmethod
    def create_session(self, session_id: str) -> None:
        """
        Create a new session.

        Args:
            session_id: Session identifier
        """
        pass

    @abstractmethod
    def list_sessions(self) -> List[str]:
        """
        List all session IDs.

        Returns:
            List of session IDs
        """
        pass

    # ===================
    # Utility Methods
    # ===================

    @staticmethod
    def generate_event_id() -> str:
        """Generate a unique event ID."""
        import uuid
        return f"e-{uuid.uuid4().hex[:12]}"

    @staticmethod
    def get_timestamp() -> str:
        """Get current timestamp in ISO format."""
        return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
