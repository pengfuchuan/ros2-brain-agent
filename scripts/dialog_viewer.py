#!/usr/bin/env python3
# Copyright 2026 ROS2 Brain Agent Team
# SPDX-License-Identifier: Apache-2.0

"""
Dialog Viewer - CLI tool for viewing and analyzing conversation records.

Usage:
    python dialog_viewer.py sessions              # List all sessions
    python dialog_viewer.py turns <session_id>    # View conversation turns
    python dialog_viewer.py events <session_id>   # View events log
    python dialog_viewer.py analyze <session_id>  # Analyze response quality
    python dialog_viewer.py export <session_id>   # Export session as JSON
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "packages" / "cmm_brain"))

from cmm_brain.memory import Turn, Event, Summary, Facts
from cmm_brain.memory.filesystem_store import FileSystemMemoryStore


# ANSI color codes
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    MAGENTA = '\033[95m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'


def colorize(text: str, color: str) -> str:
    """Apply ANSI color to text."""
    return f"{color}{text}{Colors.ENDC}"


def format_timestamp(ts: str) -> str:
    """Format ISO timestamp for display."""
    try:
        dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except:
        return ts


def print_header(title: str) -> None:
    """Print a formatted header."""
    print()
    print(colorize(f"{'=' * 60}", Colors.CYAN))
    print(colorize(f"  {title}", Colors.BOLD + Colors.CYAN))
    print(colorize(f"{'=' * 60}", Colors.CYAN))
    print()


def get_memory_store(base_path: Optional[str] = None) -> FileSystemMemoryStore:
    """Get memory store instance."""
    if base_path is None:
        base_path = os.environ.get(
            'MEMORY_BASE_PATH',
            str(Path(__file__).parent.parent / 'memory')
        )
    return FileSystemMemoryStore(base_path)


def cmd_sessions(args) -> None:
    """List all sessions."""
    store = get_memory_store(args.memory_path)
    sessions = store.list_sessions()

    print_header("Sessions")

    if not sessions:
        print(colorize("No sessions found.", Colors.YELLOW))
        return

    print(f"{'Session ID':<30} {'Turns':<10} {'Last Update':<20}")
    print("-" * 60)

    for session_id in sessions:
        turns = store.get_all_turns(session_id)
        last_turn = turns[-1] if turns else None
        last_update = format_timestamp(last_turn.ts) if last_turn else "N/A"

        print(f"{session_id:<30} {len(turns):<10} {last_update:<20}")

    print()
    print(colorize(f"Total: {len(sessions)} session(s)", Colors.DIM))


def cmd_turns(args) -> None:
    """View conversation turns for a session."""
    store = get_memory_store(args.memory_path)
    session_id = args.session_id

    if not store.session_exists(session_id):
        print(colorize(f"Session not found: {session_id}", Colors.RED))
        return

    turns = store.get_all_turns(session_id)

    print_header(f"Conversation Turns - {session_id}")
    print(colorize(f"Total turns: {len(turns)}", Colors.DIM))
    print()

    # Apply limit
    if args.limit > 0:
        turns = turns[-args.limit:]
        print(colorize(f"(Showing last {len(turns)} turns)", Colors.DIM))
        print()

    for turn in turns:
        ts = format_timestamp(turn.ts)

        if turn.speaker == "user":
            speaker_color = Colors.GREEN
            speaker_label = "USER"
        else:
            speaker_color = Colors.BLUE
            speaker_label = "ASSISTANT"

        print(f"{colorize(f'[{ts}]', Colors.DIM)} "
              f"{colorize(speaker_label, speaker_color + Colors.BOLD)} "
              f"{colorize(f'(turn #{turn.turn_id})', Colors.DIM)}")
        print("-" * 60)

        # Print text with word wrap
        text = turn.text
        if len(text) > 500 and not args.full:
            text = text[:500] + "..."
        print(text)

        # Print metadata if present
        if turn.metadata and args.verbose:
            print()
            print(colorize("Metadata:", Colors.YELLOW))
            print(json.dumps(turn.metadata, indent=2, ensure_ascii=False))

        print()


def cmd_events(args) -> None:
    """View events log for a session."""
    store = get_memory_store(args.memory_path)
    session_id = args.session_id

    if not store.session_exists(session_id):
        print(colorize(f"Session not found: {session_id}", Colors.RED))
        return

    events = store.get_events(session_id, event_type=args.type, limit=args.limit)

    print_header(f"Events Log - {session_id}")
    print(colorize(f"Total events: {len(events)}", Colors.DIM))

    if args.type:
        print(colorize(f"Filtered by type: {args.type}", Colors.DIM))
    print()

    # Event type colors
    type_colors = {
        "llm_call": Colors.YELLOW,
        "llm_result": Colors.GREEN,
        "tool_invoke": Colors.CYAN,
        "tool_result": Colors.BLUE,
        "skill_execute": Colors.MAGENTA,
        "skill_result": Colors.BLUE,
        "error": Colors.RED,
        "memory_write": Colors.DIM,
    }

    for event in events:
        ts = format_timestamp(event.ts)
        type_color = type_colors.get(event.event_type, Colors.ENDC)

        status = colorize("OK", Colors.GREEN) if event.success else colorize("FAIL", Colors.RED)
        duration = f"{event.duration_ms}ms" if event.duration_ms else "N/A"

        print(f"{colorize(f'[{ts}]', Colors.DIM)} "
              f"{colorize(event.event_type, type_color + Colors.BOLD):<15} "
              f"{status:<8} {duration:<10}")

        if args.verbose or not event.success:
            if event.error_message:
                print(colorize(f"  Error: {event.error_message}", Colors.RED))

            if event.payload:
                payload_str = json.dumps(event.payload, indent=2, ensure_ascii=False)
                if len(payload_str) > 300 and not args.full:
                    payload_str = payload_str[:300] + "..."
                print(f"  Payload: {payload_str}")

        print()


def cmd_analyze(args) -> None:
    """Analyze response quality for a session."""
    store = get_memory_store(args.memory_path)
    session_id = args.session_id

    if not store.session_exists(session_id):
        print(colorize(f"Session not found: {session_id}", Colors.RED))
        return

    turns = store.get_all_turns(session_id)
    events = store.get_events(session_id)

    print_header(f"Analysis Report - {session_id}")

    # Basic stats
    user_turns = [t for t in turns if t.speaker == "user"]
    assistant_turns = [t for t in turns if t.speaker == "assistant"]

    print(colorize("Basic Statistics", Colors.BOLD + Colors.YELLOW))
    print("-" * 40)
    print(f"Total turns:           {len(turns)}")
    print(f"User messages:         {len(user_turns)}")
    print(f"Assistant responses:   {len(assistant_turns)}")
    print()

    # Event stats
    print(colorize("Event Statistics", Colors.BOLD + Colors.YELLOW))
    print("-" * 40)

    event_types = {}
    for event in events:
        event_types[event.event_type] = event_types.get(event.event_type, 0) + 1

    for event_type, count in sorted(event_types.items()):
        print(f"{event_type:<20} {count}")

    print()

    # Error analysis
    errors = [e for e in events if not e.success or e.event_type == "error"]
    print(colorize("Error Analysis", Colors.BOLD + Colors.YELLOW))
    print("-" * 40)

    if errors:
        print(colorize(f"Total errors: {len(errors)}", Colors.RED))
        for error in errors[:5]:  # Show first 5 errors
            print(f"  - {error.event_type}: {error.error_message or 'Unknown error'}")
    else:
        print(colorize("No errors found.", Colors.GREEN))

    print()

    # LLM performance
    llm_calls = [e for e in events if e.event_type == "llm_call"]
    llm_results = [e for e in events if e.event_type == "llm_result"]

    print(colorize("LLM Performance", Colors.BOLD + Colors.YELLOW))
    print("-" * 40)
    print(f"LLM calls:     {len(llm_calls)}")
    print(f"LLM results:   {len(llm_results)}")

    if llm_results:
        durations = [e.duration_ms for e in llm_results if e.duration_ms]
        if durations:
            avg_duration = sum(durations) / len(durations)
            max_duration = max(durations)
            min_duration = min(durations)
            print(f"Avg latency:   {avg_duration:.0f}ms")
            print(f"Max latency:   {max_duration}ms")
            print(f"Min latency:   {min_duration}ms")

    print()

    # Response length analysis
    if assistant_turns:
        lengths = [len(t.text) for t in assistant_turns]
        avg_len = sum(lengths) / len(lengths)
        max_len = max(lengths)
        min_len = min(lengths)

        print(colorize("Response Length Analysis", Colors.BOLD + Colors.YELLOW))
        print("-" * 40)
        print(f"Average length:  {avg_len:.0f} chars")
        print(f"Max length:      {max_len} chars")
        print(f"Min length:      {min_len} chars")
        print()

    # Tool usage
    tool_invokes = [e for e in events if e.event_type == "tool_invoke"]
    tool_results = [e for e in events if e.event_type == "tool_result"]

    if tool_invokes:
        print(colorize("Tool Usage", Colors.BOLD + Colors.YELLOW))
        print("-" * 40)

        tool_counts = {}
        for event in tool_invokes:
            tool_name = event.payload.get("tool", "unknown")
            tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1

        for tool_name, count in sorted(tool_counts.items(), key=lambda x: -x[1]):
            print(f"{tool_name:<30} {count}")

        print()


def cmd_export(args) -> None:
    """Export session data as JSON."""
    store = get_memory_store(args.memory_path)
    session_id = args.session_id

    if not store.session_exists(session_id):
        print(colorize(f"Session not found: {session_id}", Colors.RED))
        return

    turns = store.get_all_turns(session_id)
    events = store.get_events(session_id)
    summary = store.get_summary(session_id)
    facts = store.get_session_facts(session_id)

    export_data = {
        "session_id": session_id,
        "exported_at": datetime.utcnow().isoformat() + "Z",
        "turns": [t.to_dict() for t in turns],
        "events": [e.to_dict() for e in events],
        "summary": summary.to_dict() if summary else None,
        "facts": facts.to_dict()
    }

    output_path = args.output or f"{session_id}_export.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(export_data, f, indent=2, ensure_ascii=False)

    print(colorize(f"Exported to: {output_path}", Colors.GREEN))
    print(f"  Turns:   {len(turns)}")
    print(f"  Events:  {len(events)}")


def cmd_summary(args) -> None:
    """View session summary."""
    store = get_memory_store(args.memory_path)
    session_id = args.session_id

    if not store.session_exists(session_id):
        print(colorize(f"Session not found: {session_id}", Colors.RED))
        return

    summary = store.get_summary(session_id)

    print_header(f"Session Summary - {session_id}")

    if not summary:
        print(colorize("No summary available.", Colors.YELLOW))
        return

    print(f"Version:    {summary.version}")
    print(f"Updated:    {format_timestamp(summary.updated_at)}")
    print()
    print(colorize("Summary:", Colors.BOLD))
    print(summary.summary_text)
    print()

    if summary.key_points:
        print(colorize("Key Points:", Colors.BOLD))
        for point in summary.key_points:
            print(f"  - {point}")


def cmd_facts(args) -> None:
    """View session facts."""
    store = get_memory_store(args.memory_path)

    if args.session_id:
        if not store.session_exists(args.session_id):
            print(colorize(f"Session not found: {args.session_id}", Colors.RED))
            return
        facts = store.get_session_facts(args.session_id)
        print_header(f"Session Facts - {args.session_id}")
    else:
        facts = store.get_global_facts()
        print_header("Global Facts")

    print(json.dumps(facts.facts, indent=2, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(
        description="Dialog Viewer - View and analyze conversation records",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s sessions                    List all sessions
  %(prog)s turns session_123           View turns for a session
  %(prog)s events session_123          View events for a session
  %(prog)s analyze session_123         Analyze response quality
  %(prog)s export session_123          Export session as JSON
        """
    )

    parser.add_argument(
        '--memory-path',
        help='Path to memory storage directory',
        default=None
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # sessions command
    p_sessions = subparsers.add_parser('sessions', help='List all sessions')
    p_sessions.set_defaults(func=cmd_sessions)

    # turns command
    p_turns = subparsers.add_parser('turns', help='View conversation turns')
    p_turns.add_argument('session_id', help='Session ID to view')
    p_turns.add_argument('--limit', '-n', type=int, default=0,
                         help='Limit number of turns (0 = all)')
    p_turns.add_argument('--full', '-f', action='store_true',
                         help='Show full text (no truncation)')
    p_turns.add_argument('--verbose', '-v', action='store_true',
                         help='Show metadata')
    p_turns.set_defaults(func=cmd_turns)

    # events command
    p_events = subparsers.add_parser('events', help='View events log')
    p_events.add_argument('session_id', help='Session ID to view')
    p_events.add_argument('--type', '-t', help='Filter by event type')
    p_events.add_argument('--limit', '-n', type=int, default=100,
                          help='Limit number of events')
    p_events.add_argument('--full', '-f', action='store_true',
                          help='Show full payloads')
    p_events.add_argument('--verbose', '-v', action='store_true',
                          help='Show detailed info')
    p_events.set_defaults(func=cmd_events)

    # analyze command
    p_analyze = subparsers.add_parser('analyze', help='Analyze response quality')
    p_analyze.add_argument('session_id', help='Session ID to analyze')
    p_analyze.set_defaults(func=cmd_analyze)

    # export command
    p_export = subparsers.add_parser('export', help='Export session as JSON')
    p_export.add_argument('session_id', help='Session ID to export')
    p_export.add_argument('--output', '-o', help='Output file path')
    p_export.set_defaults(func=cmd_export)

    # summary command
    p_summary = subparsers.add_parser('summary', help='View session summary')
    p_summary.add_argument('session_id', help='Session ID to view')
    p_summary.set_defaults(func=cmd_summary)

    # facts command
    p_facts = subparsers.add_parser('facts', help='View session facts')
    p_facts.add_argument('session_id', nargs='?', help='Session ID (optional, shows global if omitted)')
    p_facts.set_defaults(func=cmd_facts)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    args.func(args)


if __name__ == '__main__':
    main()
