# Copyright 2026 ROS2 Brain Agent Team
# SPDX-License-Identifier: Apache-2.0

"""
Memory Enhancements - Summary generation and memory management.

Provides:
- Summary generation for long context compression
- Memory write handling
- Facts management
"""

import json
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from cmm_brain.memory import (
    MemoryStore,
    FileSystemMemoryStore,
    Turn,
    Summary,
    Facts
)


class SummaryGenerator:
    """Generates summaries from conversation turns."""

    def __init__(self, llm_provider=None):
        """
        Initialize summary generator.

        Args:
            llm_provider: Optional LLM provider for AI-based summarization
        """
        self.llm_provider = llm_provider

    def generate_summary(
        self,
        turns: List[Turn],
        existing_summary: Optional[Summary] = None
    ) -> Summary:
        """
        Generate a summary from conversation turns.

        Args:
            turns: List of turns to summarize
            existing_summary: Optional existing summary to extend

        Returns:
            Generated Summary object
        """
        from datetime import datetime

        if not turns:
            return Summary(
                version=1,
                updated_at=datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                summary_text="",
                key_points=[]
            )

        # Build conversation text
        conversation = []
        for turn in turns:
            speaker = "User" if turn.speaker == "user" else "Assistant"
            conversation.append(f"{speaker}: {turn.text}")

        conversation_text = "\n".join(conversation)

        # Use LLM for summarization if available
        if self.llm_provider:
            return self._llm_summarize(conversation_text, existing_summary)

        # Fallback to simple extraction
        return self._simple_summarize(turns, existing_summary)

    def _llm_summarize(
        self,
        conversation_text: str,
        existing_summary: Optional[Summary]
    ) -> Summary:
        """Use LLM to generate summary."""
        from datetime import datetime

        try:
            prompt = f"""Summarize the following conversation concisely.
Focus on key decisions, actions taken, and important information learned.

Conversation:
{conversation_text}

{"Previous summary: " + existing_summary.summary_text if existing_summary else ""}

Provide a brief summary (2-3 sentences) and list up to 5 key points.
Format your response as JSON:
{{"summary_text": "...", "key_points": ["point1", "point2", ...]}}
"""
            response = self.llm_provider.call([
                {"role": "system", "content": "You are a conversation summarizer. Provide concise, accurate summaries."},
                {"role": "user", "content": prompt}
            ])

            result = self.llm_provider._extract_json(response.content)
            if result:
                return Summary(
                    version=(existing_summary.version + 1) if existing_summary else 1,
                    updated_at=datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                    summary_text=result.get('summary_text', ''),
                    key_points=result.get('key_points', [])
                )

        except Exception as e:
            pass  # Fall through to simple summarization

        return self._simple_summarize([], existing_summary)

    def _simple_summarize(
        self,
        turns: List[Turn],
        existing_summary: Optional[Summary]
    ) -> Summary:
        """Simple summary generation without LLM."""
        from datetime import datetime

        # Extract key information
        user_topics = set()
        actions = []

        for turn in turns:
            if turn.speaker == "user":
                # Simple keyword extraction
                text = turn.text.lower()
                if "帮我" in text or "请" in text:
                    user_topics.add("request")
                if "导航" in text or "去" in text:
                    user_topics.add("navigation")
                if "拿" in text or "取" in text or "抓" in text:
                    user_topics.add("manipulation")

            metadata = turn.metadata or {}
            if metadata.get('tool_calls'):
                for tc in metadata['tool_calls']:
                    actions.append(tc.get('tool', 'unknown'))

        # Build summary text
        if existing_summary:
            summary_text = existing_summary.summary_text
            if user_topics:
                summary_text += f" Topics discussed: {', '.join(user_topics)}."
        else:
            summary_text = f"Conversation with {len(turns)} turns."
            if user_topics:
                summary_text += f" Topics: {', '.join(user_topics)}."

        # Build key points
        key_points = []
        if existing_summary:
            key_points.extend(existing_summary.key_points[:3])  # Keep some old points

        if actions:
            key_points.append(f"Actions taken: {', '.join(set(actions[-3:]))}")

        return Summary(
            version=(existing_summary.version + 1) if existing_summary else 1,
            updated_at=datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            summary_text=summary_text,
            key_points=key_points[-5:]  # Keep max 5 points
        )


class MemoryManager:
    """Manages memory operations including writes and compression."""

    def __init__(
        self,
        store: MemoryStore,
        summary_generator: Optional[SummaryGenerator] = None,
        summary_threshold: int = 50
    ):
        """
        Initialize memory manager.

        Args:
            store: Memory store instance
            summary_generator: Optional summary generator
            summary_threshold: Number of turns before triggering summary
        """
        self.store = store
        self.summary_generator = summary_generator or SummaryGenerator()
        self.summary_threshold = summary_threshold

    def process_memory_write(
        self,
        session_id: str,
        memory_writes: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Process memory write operations from LLM output.

        Args:
            session_id: Session identifier
            memory_writes: List of memory write operations

        Returns:
            Dict with results of each operation
        """
        results = []

        for write_op in memory_writes:
            op_type = write_op.get('type', 'upsert')
            key = write_op.get('key', '')
            value = write_op.get('value')
            scope = write_op.get('scope', 'session')

            if not key:
                results.append({
                    'success': False,
                    'error': 'Missing key'
                })
                continue

            try:
                if op_type == 'upsert':
                    if scope == 'global':
                        self.store.upsert_global_facts(key, value)
                    else:
                        self.store.upsert_session_facts(session_id, key, value)

                    results.append({
                        'success': True,
                        'operation': 'upsert',
                        'key': key,
                        'scope': scope
                    })

                elif op_type == 'delete':
                    if scope == 'global':
                        deleted = self.store.delete_global_fact(key)
                    else:
                        deleted = self.store.delete_session_fact(session_id, key)

                    results.append({
                        'success': deleted,
                        'operation': 'delete',
                        'key': key,
                        'scope': scope
                    })

                else:
                    results.append({
                        'success': False,
                        'error': f'Unknown operation: {op_type}'
                    })

            except Exception as e:
                results.append({
                    'success': False,
                    'error': str(e)
                })

        return {
            'session_id': session_id,
            'processed': len(results),
            'results': results
        }

    def check_and_compress(self, session_id: str) -> Optional[Summary]:
        """
        Check if session needs compression and generate summary if needed.

        Args:
            session_id: Session identifier

        Returns:
            Generated Summary if compression occurred, None otherwise
        """
        turn_count = self.store.get_turn_count(session_id)

        if turn_count < self.summary_threshold:
            return None

        # Get turns since last summary
        existing_summary = self.store.get_summary(session_id)
        turns = self.store.get_all_turns(session_id)

        if not turns:
            return None

        # Generate new summary
        new_summary = self.summary_generator.generate_summary(
            turns,
            existing_summary
        )

        # Save summary
        self.store.set_summary(session_id, new_summary)

        return new_summary

    def get_context_for_llm(
        self,
        session_id: str,
        max_turns: int = 20
    ) -> Dict[str, Any]:
        """
        Get context formatted for LLM prompt.

        Args:
            session_id: Session identifier
            max_turns: Maximum number of recent turns to include

        Returns:
            Dict with history, summary, and facts
        """
        # Get recent turns
        turns = self.store.get_recent_turns(session_id, limit=max_turns)

        # Format as message history
        history = []
        for turn in turns:
            role = 'user' if turn.speaker == 'user' else 'assistant'
            history.append({
                'role': role,
                'content': turn.text
            })

        # Get summary
        summary = self.store.get_summary(session_id)
        summary_text = summary.summary_text if summary else None

        # Get facts
        session_facts = self.store.get_session_facts(session_id)
        global_facts = self.store.get_global_facts()

        combined_facts = {
            **global_facts.facts,
            **session_facts.facts
        }

        return {
            'history': history,
            'summary': summary_text,
            'facts': combined_facts,
            'turn_count': len(turns)
        }
