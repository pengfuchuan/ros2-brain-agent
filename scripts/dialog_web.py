#!/usr/bin/env python3
# Copyright 2026 ROS2 Brain Agent Team
# SPDX-License-Identifier: Apache-2.0

"""
Dialog Web UI - Web interface for viewing and managing conversation records.

Usage:
    python dialog_web.py                    # Start server on port 8080
    python dialog_web.py --port 3000        # Start on custom port
    python dialog_web.py --host 0.0.0.0     # Allow external access
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

try:
    from flask import Flask, render_template_string, jsonify, request, redirect, url_for
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False


# HTML Templates
BASE_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }} - ROS2 Brain Agent</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: #f5f7fa;
            color: #333;
            line-height: 1.6;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }
        header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px 0;
            margin-bottom: 30px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        header h1 {
            font-size: 24px;
            font-weight: 600;
        }
        header p {
            opacity: 0.9;
            font-size: 14px;
            margin-top: 5px;
        }
        nav {
            display: flex;
            gap: 15px;
            margin-top: 15px;
        }
        nav a {
            color: white;
            text-decoration: none;
            padding: 8px 16px;
            border-radius: 6px;
            background: rgba(255,255,255,0.1);
            transition: background 0.2s;
        }
        nav a:hover {
            background: rgba(255,255,255,0.2);
        }
        nav a.active {
            background: rgba(255,255,255,0.3);
        }
        .card {
            background: white;
            border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            margin-bottom: 20px;
            overflow: hidden;
        }
        .card-header {
            padding: 20px;
            border-bottom: 1px solid #eee;
            font-weight: 600;
            font-size: 16px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .card-body {
            padding: 20px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th, td {
            padding: 12px 15px;
            text-align: left;
            border-bottom: 1px solid #eee;
        }
        th {
            background: #f8f9fa;
            font-weight: 600;
            font-size: 13px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: #666;
        }
        tr:hover {
            background: #f8f9fa;
        }
        .badge {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 500;
        }
        .badge-success { background: #d4edda; color: #155724; }
        .badge-danger { background: #f8d7da; color: #721c24; }
        .badge-info { background: #d1ecf1; color: #0c5460; }
        .badge-warning { background: #fff3cd; color: #856404; }
        .badge-primary { background: #cce5ff; color: #004085; }
        .btn {
            display: inline-block;
            padding: 8px 16px;
            border-radius: 6px;
            border: none;
            cursor: pointer;
            font-size: 14px;
            text-decoration: none;
            transition: all 0.2s;
        }
        .btn-primary {
            background: #667eea;
            color: white;
        }
        .btn-primary:hover {
            background: #5a6fd6;
        }
        .btn-sm {
            padding: 5px 10px;
            font-size: 12px;
        }
        .turn-user {
            background: #e8f5e9;
            border-left: 4px solid #4caf50;
        }
        .turn-assistant {
            background: #e3f2fd;
            border-left: 4px solid #2196f3;
        }
        .turn {
            padding: 15px 20px;
            margin-bottom: 15px;
            border-radius: 8px;
        }
        .turn-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 10px;
            font-size: 13px;
            color: #666;
        }
        .turn-speaker {
            font-weight: 600;
            text-transform: uppercase;
        }
        .turn-user .turn-speaker { color: #4caf50; }
        .turn-assistant .turn-speaker { color: #2196f3; }
        .turn-content {
            white-space: pre-wrap;
            word-break: break-word;
        }
        .event-item {
            padding: 12px 15px;
            border-left: 3px solid #ddd;
            margin-bottom: 10px;
            background: #fafafa;
            border-radius: 4px;
        }
        .event-llm_call { border-color: #ffc107; }
        .event-llm_result { border-color: #28a745; }
        .event-tool_invoke { border-color: #17a2b8; }
        .event-tool_result { border-color: #6f42c1; }
        .event-skill_execute { border-color: #fd7e14; }
        .event-skill_result { border-color: #20c997; }
        .event-error { border-color: #dc3545; background: #fff5f5; }
        .stat-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }
        .stat-card {
            background: white;
            padding: 20px;
            border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }
        .stat-value {
            font-size: 32px;
            font-weight: 700;
            color: #667eea;
        }
        .stat-label {
            color: #666;
            font-size: 14px;
            margin-top: 5px;
        }
        .json-view {
            background: #1e1e1e;
            color: #d4d4d4;
            padding: 15px;
            border-radius: 8px;
            font-family: 'Monaco', 'Menlo', monospace;
            font-size: 13px;
            overflow-x: auto;
            white-space: pre-wrap;
            word-break: break-all;
        }
        .empty-state {
            text-align: center;
            padding: 60px 20px;
            color: #666;
        }
        .empty-state-icon {
            font-size: 48px;
            margin-bottom: 15px;
        }
        .search-box {
            padding: 10px 15px;
            border: 1px solid #ddd;
            border-radius: 8px;
            width: 300px;
            font-size: 14px;
        }
        .search-box:focus {
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }
        .tabs {
            display: flex;
            border-bottom: 2px solid #eee;
            margin-bottom: 20px;
        }
        .tab {
            padding: 12px 20px;
            cursor: pointer;
            border-bottom: 2px solid transparent;
            margin-bottom: -2px;
            color: #666;
            text-decoration: none;
        }
        .tab:hover {
            color: #333;
        }
        .tab.active {
            color: #667eea;
            border-bottom-color: #667eea;
        }
        .timestamp {
            color: #999;
            font-size: 12px;
        }
        .duration {
            font-family: monospace;
            background: #f0f0f0;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 12px;
        }
        footer {
            text-align: center;
            padding: 20px;
            color: #999;
            font-size: 13px;
            margin-top: 40px;
        }
    </style>
</head>
<body>
    <header>
        <div class="container">
            <h1>ROS2 Brain Agent</h1>
            <p>Dialog Management Console</p>
            <nav>
                <a href="/" class="{{ 'active' if page == 'home' else '' }}">Sessions</a>
                <a href="/stats" class="{{ 'active' if page == 'stats' else '' }}">Statistics</a>
            </nav>
        </div>
    </header>
    <main class="container">
        {% block content %}{% endblock %}
    </main>
    <footer>
        ROS2 Brain Agent &copy; 2026 | <a href="https://github.com/iampfc/ros2-brain-agent">GitHub</a>
    </footer>
</body>
</html>
"""

SESSIONS_TEMPLATE = """
<div class="card">
    <div class="card-header">
        <span>All Sessions</span>
        <input type="text" class="search-box" placeholder="Search sessions..." id="searchInput">
    </div>
    <div class="card-body">
        {% if sessions %}
        <table id="sessionsTable">
            <thead>
                <tr>
                    <th>Session ID</th>
                    <th>Turns</th>
                    <th>Events</th>
                    <th>Last Update</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
                {% for session in sessions %}
                <tr>
                    <td><code>{{ session.id }}</code></td>
                    <td>{{ session.turns }}</td>
                    <td>{{ session.events }}</td>
                    <td class="timestamp">{{ session.last_update }}</td>
                    <td>
                        <a href="/session/{{ session.id }}" class="btn btn-primary btn-sm">View</a>
                        <a href="/session/{{ session.id }}/analyze" class="btn btn-primary btn-sm">Analyze</a>
                        <a href="/api/session/{{ session.id }}/export" class="btn btn-primary btn-sm">Export</a>
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        {% else %}
        <div class="empty-state">
            <div class="empty-state-icon">📭</div>
            <p>No sessions found</p>
            <p style="font-size: 14px; margin-top: 10px;">Start a conversation to create sessions</p>
        </div>
        {% endif %}
    </div>
</div>

<script>
document.getElementById('searchInput').addEventListener('input', function(e) {
    const search = e.target.value.toLowerCase();
    const rows = document.querySelectorAll('#sessionsTable tbody tr');
    rows.forEach(row => {
        const text = row.textContent.toLowerCase();
        row.style.display = text.includes(search) ? '' : 'none';
    });
});
</script>
"""

SESSION_DETAIL_TEMPLATE = """
<div class="card">
    <div class="card-header">
        <span>Session: {{ session_id }}</span>
        <div>
            <a href="/session/{{ session_id }}" class="btn btn-primary btn-sm">Turns</a>
            <a href="/session/{{ session_id }}/events" class="btn btn-primary btn-sm">Events</a>
            <a href="/session/{{ session_id }}/analyze" class="btn btn-primary btn-sm">Analyze</a>
            <a href="/session/{{ session_id }}/facts" class="btn btn-primary btn-sm">Facts</a>
        </div>
    </div>
    <div class="card-body">
        {% if summary %}
        <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin-bottom: 20px;">
            <strong>Summary:</strong> {{ summary.summary_text }}
            {% if summary.key_points %}
            <div style="margin-top: 10px;">
                {% for point in summary.key_points %}
                <span class="badge badge-info">{{ point }}</span>
                {% endfor %}
            </div>
            {% endif %}
        </div>
        {% endif %}

        {% if turns %}
        <h3 style="margin-bottom: 15px;">Conversation Turns ({{ turns|length }})</h3>
        {% for turn in turns %}
        <div class="turn turn-{{ turn.speaker }}">
            <div class="turn-header">
                <span class="turn-speaker">{{ turn.speaker }}</span>
                <span>{{ turn.ts }} | Turn #{{ turn.turn_id }}</span>
            </div>
            <div class="turn-content">{{ turn.text }}</div>
            {% if turn.metadata %}
            <details style="margin-top: 10px;">
                <summary style="cursor: pointer; color: #666; font-size: 12px;">Metadata</summary>
                <div class="json-view" style="margin-top: 10px;">{{ turn.metadata_json }}</div>
            </details>
            {% endif %}
        </div>
        {% endfor %}
        {% else %}
        <div class="empty-state">
            <div class="empty-state-icon">💬</div>
            <p>No conversation turns</p>
        </div>
        {% endif %}
    </div>
</div>
"""

EVENTS_TEMPLATE = """
<div class="card">
    <div class="card-header">
        <span>Events - {{ session_id }}</span>
        <div style="display: flex; gap: 10px;">
            <select id="typeFilter" class="search-box" style="width: auto;" onchange="filterEvents()">
                <option value="">All Types</option>
                <option value="llm_call">LLM Call</option>
                <option value="llm_result">LLM Result</option>
                <option value="tool_invoke">Tool Invoke</option>
                <option value="tool_result">Tool Result</option>
                <option value="skill_execute">Skill Execute</option>
                <option value="skill_result">Skill Result</option>
                <option value="error">Error</option>
            </select>
        </div>
    </div>
    <div class="card-body">
        {% if events %}
        {% for event in events %}
        <div class="event-item event-{{ event.event_type }} {% if not event.success %}event-error{% endif %}" data-type="{{ event.event_type }}">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span>
                    <span class="badge badge-{{ 'danger' if event.event_type == 'error' else 'primary' }}">{{ event.event_type }}</span>
                    {% if not event.success %}<span class="badge badge-danger">FAILED</span>{% endif %}
                </span>
                <span>
                    {% if event.duration_ms %}<span class="duration">{{ event.duration_ms }}ms</span>{% endif %}
                    <span class="timestamp">{{ event.ts }}</span>
                </span>
            </div>
            {% if event.payload %}
            <details style="margin-top: 10px;">
                <summary style="cursor: pointer; font-size: 13px; color: #666;">Payload</summary>
                <div class="json-view" style="margin-top: 10px;">{{ event.payload_json }}</div>
            </details>
            {% endif %}
            {% if event.error_message %}
            <div style="margin-top: 10px; color: #dc3545; font-size: 13px;">
                <strong>Error:</strong> {{ event.error_message }}
            </div>
            {% endif %}
        </div>
        {% endfor %}
        {% else %}
        <div class="empty-state">
            <div class="empty-state-icon">📋</div>
            <p>No events recorded</p>
        </div>
        {% endif %}
    </div>
</div>

<script>
function filterEvents() {
    const filter = document.getElementById('typeFilter').value;
    const events = document.querySelectorAll('.event-item');
    events.forEach(e => {
        if (!filter || e.dataset.type === filter) {
            e.style.display = '';
        } else {
            e.style.display = 'none';
        }
    });
}
</script>
"""

ANALYZE_TEMPLATE = """
<div class="stat-grid">
    <div class="stat-card">
        <div class="stat-value">{{ stats.total_turns }}</div>
        <div class="stat-label">Total Turns</div>
    </div>
    <div class="stat-card">
        <div class="stat-value">{{ stats.user_turns }}</div>
        <div class="stat-label">User Messages</div>
    </div>
    <div class="stat-card">
        <div class="stat-value">{{ stats.assistant_turns }}</div>
        <div class="stat-label">Assistant Responses</div>
    </div>
    <div class="stat-card">
        <div class="stat-value">{{ stats.total_events }}</div>
        <div class="stat-label">Total Events</div>
    </div>
</div>

<div class="card">
    <div class="card-header">Event Statistics</div>
    <div class="card-body">
        {% for type, count in stats.event_types.items() %}
        <div style="display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #eee;">
            <span class="badge badge-primary">{{ type }}</span>
            <span><strong>{{ count }}</strong></span>
        </div>
        {% endfor %}
    </div>
</div>

<div class="card">
    <div class="card-header">LLM Performance</div>
    <div class="card-body">
        <div class="stat-grid">
            <div class="stat-card">
                <div class="stat-value">{{ stats.llm.calls }}</div>
                <div class="stat-label">LLM Calls</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{{ stats.llm.avg_latency }}ms</div>
                <div class="stat-label">Avg Latency</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{{ stats.llm.max_latency }}ms</div>
                <div class="stat-label">Max Latency</div>
            </div>
        </div>
    </div>
</div>

{% if stats.errors %}
<div class="card">
    <div class="card-header" style="background: #fff5f5;">Error Analysis</div>
    <div class="card-body">
        {% for error in stats.errors %}
        <div class="event-item event-error">
            <span class="badge badge-danger">{{ error.type }}</span>
            <span style="margin-left: 10px;">{{ error.message }}</span>
        </div>
        {% endfor %}
    </div>
</div>
{% endif %}

{% if stats.response_lengths %}
<div class="card">
    <div class="card-header">Response Length Analysis</div>
    <div class="card-body">
        <p>Average: <strong>{{ stats.response_lengths.avg }} chars</strong></p>
        <p>Max: <strong>{{ stats.response_lengths.max }} chars</strong></p>
        <p>Min: <strong>{{ stats.response_lengths.min }} chars</strong></p>
    </div>
</div>
{% endif %}
"""

FACTS_TEMPLATE = """
<div class="card">
    <div class="card-header">Facts - {{ session_id }}</div>
    <div class="card-body">
        {% if facts %}
        <div class="json-view">{{ facts_json }}</div>
        {% else %}
        <div class="empty-state">
            <div class="empty-state-icon">📝</div>
            <p>No facts recorded</p>
        </div>
        {% endif %}
    </div>
</div>
"""

STATS_TEMPLATE = """
<div class="stat-grid">
    <div class="stat-card">
        <div class="stat-value">{{ stats.total_sessions }}</div>
        <div class="stat-label">Total Sessions</div>
    </div>
    <div class="stat-card">
        <div class="stat-value">{{ stats.total_turns }}</div>
        <div class="stat-label">Total Turns</div>
    </div>
    <div class="stat-card">
        <div class="stat-value">{{ stats.total_events }}</div>
        <div class="stat-label">Total Events</div>
    </div>
    <div class="stat-card">
        <div class="stat-value">{{ stats.avg_turns_per_session }}</div>
        <div class="stat-label">Avg Turns/Session</div>
    </div>
</div>

{% if stats.event_distribution %}
<div class="card">
    <div class="card-header">Event Distribution</div>
    <div class="card-body">
        {% for type, count in stats.event_distribution.items() %}
        <div style="display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #eee;">
            <span class="badge badge-primary">{{ type }}</span>
            <span><strong>{{ count }}</strong></span>
        </div>
        {% endfor %}
    </div>
</div>
{% endif %}
"""


def get_memory_store(base_path: Optional[str] = None) -> FileSystemMemoryStore:
    """Get memory store instance."""
    if base_path is None:
        base_path = os.environ.get(
            'MEMORY_BASE_PATH',
            str(Path(__file__).parent.parent / 'memory')
        )
    return FileSystemMemoryStore(base_path)


def format_timestamp(ts: str) -> str:
    """Format ISO timestamp for display."""
    try:
        dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except:
        return ts


def create_app(memory_path: Optional[str] = None) -> 'Flask':
    """Create Flask application."""
    if not FLASK_AVAILABLE:
        raise ImportError("Flask is required. Install with: pip install flask")

    app = Flask(__name__)
    store = get_memory_store(memory_path)

    # Template filter
    app.jinja_env.globals['page'] = ''

    @app.template_filter('tojson_pretty')
    def tojson_pretty(value):
        return json.dumps(value, indent=2, ensure_ascii=False)

    @app.route('/')
    def index():
        sessions = []
        for session_id in store.list_sessions():
            turns = store.get_all_turns(session_id)
            events = store.get_events(session_id)
            last_turn = turns[-1] if turns else None

            sessions.append({
                'id': session_id,
                'turns': len(turns),
                'events': len(events),
                'last_update': format_timestamp(last_turn.ts) if last_turn else 'N/A'
            })

        return render_template_string(
            BASE_TEMPLATE.replace('{% block content %}{% endblock %}', SESSIONS_TEMPLATE),
            title='Sessions',
            page='home',
            sessions=sessions
        )

    @app.route('/stats')
    def stats():
        sessions = store.list_sessions()
        total_turns = 0
        total_events = 0
        event_distribution = {}

        for session_id in sessions:
            turns = store.get_all_turns(session_id)
            events = store.get_events(session_id)
            total_turns += len(turns)
            total_events += len(events)

            for event in events:
                event_distribution[event.event_type] = event_distribution.get(event.event_type, 0) + 1

        stats_data = {
            'total_sessions': len(sessions),
            'total_turns': total_turns,
            'total_events': total_events,
            'avg_turns_per_session': round(total_turns / len(sessions), 1) if sessions else 0,
            'event_distribution': dict(sorted(event_distribution.items(), key=lambda x: -x[1]))
        }

        return render_template_string(
            BASE_TEMPLATE.replace('{% block content %}{% endblock %}', STATS_TEMPLATE),
            title='Statistics',
            page='stats',
            stats=stats_data
        )

    @app.route('/session/<session_id>')
    def session_detail(session_id):
        if not store.session_exists(session_id):
            return "Session not found", 404

        turns = store.get_all_turns(session_id)
        summary = store.get_summary(session_id)

        turns_data = []
        for t in turns:
            turns_data.append({
                'turn_id': t.turn_id,
                'ts': format_timestamp(t.ts),
                'speaker': t.speaker,
                'text': t.text,
                'metadata': t.metadata,
                'metadata_json': json.dumps(t.metadata, indent=2, ensure_ascii=False) if t.metadata else None
            })

        return render_template_string(
            BASE_TEMPLATE.replace('{% block content %}{% endblock %}', SESSION_DETAIL_TEMPLATE),
            title=f'Session: {session_id}',
            page='session',
            session_id=session_id,
            turns=turns_data,
            summary=summary
        )

    @app.route('/session/<session_id>/events')
    def session_events(session_id):
        if not store.session_exists(session_id):
            return "Session not found", 404

        events = store.get_events(session_id, limit=500)

        events_data = []
        for e in events:
            events_data.append({
                'event_id': e.event_id,
                'ts': format_timestamp(e.ts),
                'event_type': e.event_type,
                'payload': e.payload,
                'payload_json': json.dumps(e.payload, indent=2, ensure_ascii=False) if e.payload else None,
                'duration_ms': e.duration_ms,
                'success': e.success,
                'error_message': e.error_message
            })

        return render_template_string(
            BASE_TEMPLATE.replace('{% block content %}{% endblock %}', EVENTS_TEMPLATE),
            title=f'Events: {session_id}',
            page='events',
            session_id=session_id,
            events=events_data
        )

    @app.route('/session/<session_id>/analyze')
    def session_analyze(session_id):
        if not store.session_exists(session_id):
            return "Session not found", 404

        turns = store.get_all_turns(session_id)
        events = store.get_events(session_id)

        user_turns = [t for t in turns if t.speaker == 'user']
        assistant_turns = [t for t in turns if t.speaker == 'assistant']

        # Event stats
        event_types = {}
        for e in events:
            event_types[e.event_type] = event_types.get(e.event_type, 0) + 1

        # LLM stats
        llm_results = [e for e in events if e.event_type == 'llm_result']
        durations = [e.duration_ms for e in llm_results if e.duration_ms]

        # Errors
        errors = []
        for e in events:
            if not e.success or e.event_type == 'error':
                errors.append({
                    'type': e.event_type,
                    'message': e.error_message or 'Unknown error'
                })

        # Response lengths
        response_lengths = None
        if assistant_turns:
            lengths = [len(t.text) for t in assistant_turns]
            response_lengths = {
                'avg': int(sum(lengths) / len(lengths)),
                'max': max(lengths),
                'min': min(lengths)
            }

        stats_data = {
            'total_turns': len(turns),
            'user_turns': len(user_turns),
            'assistant_turns': len(assistant_turns),
            'total_events': len(events),
            'event_types': dict(sorted(event_types.items(), key=lambda x: -x[1])),
            'llm': {
                'calls': len([e for e in events if e.event_type == 'llm_call']),
                'avg_latency': int(sum(durations) / len(durations)) if durations else 0,
                'max_latency': max(durations) if durations else 0,
            },
            'errors': errors[:10],
            'response_lengths': response_lengths
        }

        return render_template_string(
            BASE_TEMPLATE.replace('{% block content %}{% endblock %}', ANALYZE_TEMPLATE),
            title=f'Analyze: {session_id}',
            page='analyze',
            session_id=session_id,
            stats=stats_data
        )

    @app.route('/session/<session_id>/facts')
    def session_facts(session_id):
        if not store.session_exists(session_id):
            return "Session not found", 404

        facts = store.get_session_facts(session_id)
        facts_dict = facts.facts if facts else {}

        return render_template_string(
            BASE_TEMPLATE.replace('{% block content %}{% endblock %}', FACTS_TEMPLATE),
            title=f'Facts: {session_id}',
            page='facts',
            session_id=session_id,
            facts=facts_dict,
            facts_json=json.dumps(facts_dict, indent=2, ensure_ascii=False)
        )

    # API endpoints
    @app.route('/api/sessions')
    def api_sessions():
        sessions = []
        for session_id in store.list_sessions():
            turns = store.get_all_turns(session_id)
            events = store.get_events(session_id)
            last_turn = turns[-1] if turns else None

            sessions.append({
                'id': session_id,
                'turns': len(turns),
                'events': len(events),
                'last_update': last_turn.ts if last_turn else None
            })

        return jsonify(sessions)

    @app.route('/api/session/<session_id>')
    def api_session(session_id):
        if not store.session_exists(session_id):
            return jsonify({'error': 'Session not found'}), 404

        turns = store.get_all_turns(session_id)
        events = store.get_events(session_id)
        summary = store.get_summary(session_id)
        facts = store.get_session_facts(session_id)

        return jsonify({
            'session_id': session_id,
            'turns': [t.to_dict() for t in turns],
            'events': [e.to_dict() for e in events],
            'summary': summary.to_dict() if summary else None,
            'facts': facts.to_dict()
        })

    @app.route('/api/session/<session_id>/export')
    def api_export(session_id):
        if not store.session_exists(session_id):
            return jsonify({'error': 'Session not found'}), 404

        turns = store.get_all_turns(session_id)
        events = store.get_events(session_id)
        summary = store.get_summary(session_id)
        facts = store.get_session_facts(session_id)

        export_data = {
            'session_id': session_id,
            'exported_at': datetime.utcnow().isoformat() + 'Z',
            'turns': [t.to_dict() for t in turns],
            'events': [e.to_dict() for e in events],
            'summary': summary.to_dict() if summary else None,
            'facts': facts.to_dict()
        }

        response = app.response_class(
            response=json.dumps(export_data, indent=2, ensure_ascii=False),
            status=200,
            mimetype='application/json'
        )
        response.headers['Content-Disposition'] = f'attachment; filename={session_id}_export.json'
        return response

    return app


def main():
    parser = argparse.ArgumentParser(
        description='Dialog Web UI - Web interface for conversation management'
    )
    parser.add_argument('--host', default='127.0.0.1', help='Host to bind to')
    parser.add_argument('--port', type=int, default=8080, help='Port to bind to')
    parser.add_argument('--memory-path', help='Path to memory storage directory')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')

    args = parser.parse_args()

    if not FLASK_AVAILABLE:
        print("Error: Flask is required.")
        print("Install with: pip install flask")
        sys.exit(1)

    app = create_app(args.memory_path)

    print(f"""
╔══════════════════════════════════════════════════════════╗
║           ROS2 Brain Agent - Dialog Web UI               ║
╠══════════════════════════════════════════════════════════╣
║  URL:  http://{args.host}:{args.port}
║  API:  http://{args.host}:{args.port}/api/sessions
╚══════════════════════════════════════════════════════════╝
    """)

    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == '__main__':
    main()
