#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ROS2 Brain Agent Event Viewer - 格式化显示对话事件

运行方式:
  # 在主机上运行
  python3 scripts/event_viewer.py

  # 在容器内运行
  docker exec ros2-brain-agent python3 /ros2_ws/scripts/event_viewer.py --container
"""

import subprocess
import json
import sys
import os
from datetime import datetime

CONTAINER = "ros2-brain-agent"
IN_CONTAINER = os.environ.get('IN_CONTAINER', 'false').lower() == 'true'


def run_in_container(cmd):
    """Run command either directly or via docker."""
    if IN_CONTAINER:
        return subprocess.run(cmd, shell=True, capture_output=True, text=True)
    else:
        return subprocess.run(
            ["docker", "exec", CONTAINER, "bash", "-lc", cmd],
            capture_output=True, text=True
        )


def format_event(raw_output: str) -> str:
    """Format dialog event with colors and structure."""
    try:
        if "data: '" in raw_output:
            json_str = raw_output.split("data: '", 1)[1]
            if "'" in json_str:
                json_str = json_str.split("'")[0]

            data = json.loads(json_str)

            # Colors
            C = {
                'BOLD': '\033[1m', 'RESET': '\033[0m',
                'CYAN': '\033[96m', 'GREEN': '\033[92m',
                'YELLOW': '\033[93m', 'RED': '\033[91m',
                'BLUE': '\033[94m', 'MAGENTA': '\033[95m'
            }

            event_type = data.get('event_type', 'unknown')
            source = data.get('source', 'unknown')

            # Event emoji and color
            event_styles = {
                'turn_start': ('🟢', C['GREEN']),
                'turn_end': ('🔵', C['BLUE']),
                'llm_result': ('🤖', C['MAGENTA']),
                'llm_call': ('💭', C['MAGENTA']),
                'skill_execute': ('⚡', C['YELLOW']),
                'tool_invoke': ('🔧', C['CYAN']),
                'tool_result': ('✅', C['CYAN']),
                'error': ('❌', C['RED']),
                'memory_write': ('📝', C['BLUE'])
            }
            emoji, color = event_styles.get(event_type, ('📋', C['YELLOW']))

            lines = [
                f"\n{C['BOLD']}{'═' * 60}{C['RESET']}",
                f"{emoji} {C['BOLD']}{color}{event_type.upper()}{C['RESET']} via {source}",
                f"{C['BOLD']}{'─' * 60}{C['RESET']}"
            ]

            # Basic info
            lines.append(f"  Session: {data.get('session_id', 'N/A')}")
            lines.append(f"  Event ID: {data.get('event_id', 'N/A')}")

            success = data.get('success', True)
            status = f"{C['GREEN']}✅{C['RESET']}" if success else f"{C['RED']}❌{C['RESET']}"
            lines.append(f"  Status: {status}")

            # Duration
            duration = data.get('duration_ms', 0)
            if duration:
                lines.append(f"  Duration: {duration}ms")

            # Timestamp
            ts = data.get('timestamp', {})
            if ts and ts.get('sec'):
                try:
                    dt = datetime.fromtimestamp(ts['sec'])
                    lines.append(f"  Time: {dt.strftime('%H:%M:%S')}")
                except:
                    pass

            # Payload
            payload_json = data.get('payload_json', '{}')
            if payload_json:
                try:
                    payload = json.loads(payload_json) if isinstance(payload_json, str) else payload_json
                    lines.append(f"\n  {C['BOLD']}Payload:{C['RESET']}")

                    # Format based on event type
                    if event_type == 'turn_start':
                        lines.append(f"    Turn ID: {payload.get('turn_id')}")
                        lines.append(f"    Text: {payload.get('text', '')[:100]}")

                    elif event_type == 'llm_result':
                        lines.append(f"    Model: {payload.get('model', 'N/A')}")
                        usage = payload.get('usage', {})
                        if usage:
                            lines.append(f"    Tokens: {usage.get('total_tokens', 0)} (prompt: {usage.get('prompt_tokens', 0)}, completion: {usage.get('completion_tokens', 0)})")
                        plan = payload.get('plan', [])
                        if plan:
                            lines.append(f"    Plan ({len(plan)} steps):")
                            for step in plan[:5]:
                                lines.append(f"      {step.get('step')}. {step.get('action')}")

                    elif event_type == 'skill_execute':
                        exec_result = payload.get('execution_result', {})
                        lines.append(f"    Success: {exec_result.get('success', False)}")
                        executed = exec_result.get('executed_steps', [])
                        if executed:
                            lines.append(f"    Executed {len(executed)} steps:")
                            for step in executed[:3]:
                                output = step.get('output', '')[:60]
                                lines.append(f"      • {step.get('action')}: {output}...")

                    elif event_type == 'turn_end':
                        lines.append(f"    Turn ID: {payload.get('turn_id')}")
                        text = payload.get('text', '')
                        if text:
                            lines.append(f"    Response: {text[:150]}{'...' if len(text) > 150 else ''}")
                        exec_result = payload.get('execution_result', {})
                        if exec_result.get('executed_steps'):
                            lines.append(f"    Steps executed: {len(exec_result['executed_steps'])}")

                    else:
                        # Generic payload display
                        for key, value in list(payload.items())[:5]:
                            val_str = str(value)[:80]
                            lines.append(f"    {key}: {val_str}")

                except Exception as e:
                    lines.append(f"    {payload_json[:200]}")

            # Error message
            error = data.get('error_message', '')
            if error:
                lines.append(f"\n  {C['RED']}Error: {error}{C['RESET']}")

            lines.append(f"{C['BOLD']}{'═' * 60}{C['RESET']}")
            return "\n".join(lines)

    except Exception as e:
        return f"Parse error: {e}\nRaw: {raw_output[:200]}"

    return raw_output


def main():
    print(f"\n{'=' * 60}")
    print(f"  ROS2 Brain Agent Event Viewer")
    print(f"  Listening to /dialog/events...")
    print(f"  (Ctrl+C to exit)")
    print(f"{'=' * 60}\n")

    try:
        # Run ros2 topic echo continuously
        cmd = [
            "docker", "exec", CONTAINER, "bash", "-c",
            "source /opt/ros/humble/setup.bash && "
            "ros2 topic echo /dialog/events --full-length"
        ]

        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1
        )

        buffer = ""
        for char in iter(lambda: process.stdout.read(1), ''):
            buffer += char

            # Process complete messages (ended by ---)
            if buffer.endswith("---\n"):
                if "data: '" in buffer:
                    print(format_event(buffer))
                buffer = ""

    except KeyboardInterrupt:
        print("\n\nStopped listening.")
        process.terminate()
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
