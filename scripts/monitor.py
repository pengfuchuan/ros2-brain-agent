#!/usr/bin/env python3
# Copyright 2026 ROS2 Brain Agent Team
# SPDX-License-Identifier: Apache-2.0

"""
ROS2 系统监控工具 - 一键监听所有关键话题

Usage:
    # 一键启动所有监听
    python3 scripts/monitor.py --all

    # 逐步执行
    python3 scripts/monitor.py --events    # 监听对话事件
    python3 scripts/monitor.py --state     # 监听世界状态
    python3 scripts/monitor.py --skills    # 监听技能执行
    python3 scripts/monitor.py --tools     # 监听工具执行
"""

import subprocess
import sys
import time
import argparse
import json
from datetime import datetime

CONTAINER = "ros2-brain-agent"

TOPICS = {
    "events": "/dialog/events",
    "llm_response": "/dialog/llm_response",
    "state": "/world_state/current",
    "skill_execute": "/skill/execute",
    "skill_result": "/skill/result",
    "tool_execute": "/tool/execute",
    "tool_result": "/tool/result"
}


def check_container():
    """Check if container is running"""
    result = subprocess.run(
        ["docker", "ps", "--filter", f"name={CONTAINER}", "--format", "{{.Names}}: {{.Status}}"],
        capture_output=True, text=True
    )
    return result.stdout.strip()


def format_dialog_event(raw_output: str) -> str:
    """Format dialog event data for better readability."""
    try:
        # Extract JSON from "data: '...'" format
        if "data: '" in raw_output:
            json_str = raw_output.split("data: '", 1)[1]
            if json_str.endswith("'"):
                json_str = json_str[:-1]
            # Also handle the case where it ends with "'\n---"
            if "'\n---" in json_str:
                json_str = json_str.split("'\n---")[0]

            # Parse JSON
            data = json.loads(json_str)

            # Color codes for terminal
            CYAN = '\033[96m'
            GREEN = '\033[92m'
            YELLOW = '\033[93m'
            RED = '\033[91m'
            BOLD = '\033[1m'
            RESET = '\033[0m'

            # Format output
            lines = []
            lines.append(f"\n{BOLD}{'=' * 60}{RESET}")
            event_type = data.get('event_type', 'unknown')
            source = data.get('source', 'unknown')

            # Color based on event type
            if 'error' in event_type.lower():
                type_color = RED
            elif 'result' in event_type.lower() or 'end' in event_type.lower():
                type_color = GREEN
            elif 'start' in event_type.lower():
                type_color = CYAN
            else:
                type_color = YELLOW

            lines.append(f"  {BOLD}Event:{RESET}   {type_color}{event_type}{RESET}")
            lines.append(f"  {BOLD}Source:{RESET}  {source}")
            lines.append(f"{'-' * 60}")
            lines.append(f"  {BOLD}Session:{RESET}  {data.get('session_id', 'N/A')}")
            lines.append(f"  {BOLD}ID:{RESET}      {data.get('event_id', 'N/A')}")
            lines.append(f"  {BOLD}Success:{RESET} {GREEN if data.get('success') else RED}{data.get('success', 'N/A')}{RESET}")

            # Format timestamp
            ts = data.get('timestamp', {})
            if ts:
                sec = ts.get('sec', 0)
                try:
                    dt = datetime.fromtimestamp(sec)
                    lines.append(f"  {BOLD}Time:{RESET}    {dt.strftime('%H:%M:%S')}")
                except:
                    pass

            duration = data.get('duration_ms', 0)
            if duration:
                lines.append(f"  {BOLD}Duration:{RESET} {duration} ms")

            # Format payload
            payload_json = data.get('payload_json', '{}')
            if isinstance(payload_json, str):
                try:
                    payload = json.loads(payload_json)
                    lines.append(f"\n  {BOLD}Payload:{RESET}")
                    for key, value in payload.items():
                        if isinstance(value, (dict, list)):
                            value_str = json.dumps(value, ensure_ascii=False)
                            if len(value_str) > 80:
                                value_str = value_str[:80] + "..."
                        else:
                            value_str = str(value)
                            if len(value_str) > 80:
                                value_str = value_str[:80] + "..."
                        lines.append(f"    {key}: {value_str}")
                except:
                    if len(payload_json) > 200:
                        lines.append(f"    {payload_json[:200]}...")
                    else:
                        lines.append(f"    {payload_json}")

            # Error message if any
            error = data.get('error_message', '')
            if error:
                lines.append(f"\n  {RED}Error: {error}{RESET}")

            lines.append(f"{BOLD}{'=' * 60}{RESET}")
            return "\n".join(lines)
    except Exception as e:
        return raw_output

    return raw_output


def run_ros2_command(topic, once=False, format_output=False):
    """Run ros2 topic echo command in container"""
    cmd = [
        "docker", "exec", CONTAINER, "bash", "-c",
        f"source /opt/ros/humble/setup.bash && "
        f"source /ros2_ws/install/setup.bash && "
        f"ros2 topic echo {topic}" + (" --once --full-length" if once else "")
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10 if once else 300)
        output = result.stdout.strip()

        # Format dialog events specially
        if format_output and topic == "/dialog/events" and output:
            return format_dialog_event(output)

        return output
    except subprocess.TimeoutExpired:
        return None
    except Exception as e:
        return f"Error: {str(e)}"


def print_header():
    """Print monitor header"""
    print("\n" + "=" * 60)
    print("   ROS2 Brain Agent Monitor")
    print("=" * 60)
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Container: {CONTAINER}")
    print("=" * 60 + "\n")


def print_topic_header(topic_name, topic_path):
    """Print topic section header"""
    print(f"\n>>> [{topic_name}] {topic_path}")
    print("-" * 50)


def watch_single_topic(topic_key, once=False):
    """Watch a single topic"""
    if topic_key not in TOPICS:
        print(f"Unknown topic: {topic_key}")
        return

    topic_path = TOPICS[topic_key]
    print_header()
    print_topic_header(topic_key.upper(), topic_path)

    # Enable formatting for events
    format_output = (topic_key == "events")

    if once:
        result = run_ros2_command(topic_path, once=True, format_output=format_output)
        if result:
            print(result)
        else:
            print("(No message or timeout)")
    else:
        print("Listening... (Ctrl+C to exit)\n")
        print("Tip: Send a message via Web UI at http://localhost:8080/chat\n")
        try:
            # For continuous monitoring, use a loop with --once
            while True:
                result = run_ros2_command(topic_path, once=True, format_output=format_output)
                if result and result != "(No message or timeout)":
                    print(result)
                    print()
                time.sleep(0.5)
        except KeyboardInterrupt:
            print("\n\nStopped listening.")


def watch_all_topics():
    """Watch all topics (get one message each)"""
    print_header()

    container_status = check_container()
    if not container_status:
        print("Container not running. Please start it first:")
        print("  docker compose up -d")
        return

    print(f"Container Status: {container_status}\n")

    for key, topic_path in TOPICS.items():
        print_topic_header(key.upper(), topic_path)
        format_output = (key == "events")
        result = run_ros2_command(topic_path, once=True, format_output=format_output)
        if result:
            # Truncate long output for non-events
            if not format_output and len(result) > 500:
                print(result[:500] + "\n... (truncated)")
            else:
                print(result)
        else:
            print("(No message or timeout)")
        time.sleep(0.3)

    print("\n" + "=" * 60)
    print("Monitor complete. Use --<topic> for continuous listening.")
    print("=" * 60)


def continuous_monitor(topics_to_watch):
    """Continuously monitor selected topics"""
    print_header()

    container_status = check_container()
    if not container_status:
        print("Container not running. Please start it first:")
        print("  docker compose up -d")
        return

    print(f"Container Status: {container_status}\n")
    print("Topics to monitor:")
    for key in topics_to_watch:
        print(f"  - {key}: {TOPICS[key]}")
    print("\nListening... (Ctrl+C to exit)\n")

    try:
        # Start with the first topic
        first_topic = topics_to_watch[0]
        topic_path = TOPICS[first_topic]
        print(f"=== Listening to {topic_path} ===\n")
        run_ros2_command(topic_path, once=False)
    except KeyboardInterrupt:
        print("\n\nStopped listening.")


def main():
    parser = argparse.ArgumentParser(
        description="ROS2 System Monitor Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 scripts/monitor.py --all        # Get one message from all topics
  python3 scripts/monitor.py --events     # Listen to dialog events (formatted)
  python3 scripts/monitor.py --state      # Listen to world state
  python3 scripts/monitor.py --skills     # Listen to skill execution
  python3 scripts/monitor.py --tools      # Listen to tool execution
        """
    )

    parser.add_argument("--all", "-a", action="store_true", help="Monitor all topics (one message each)")
    parser.add_argument("--events", "-e", action="store_true", help="Listen to dialog events")
    parser.add_argument("--state", "-s", action="store_true", help="Listen to world state")
    parser.add_argument("--skills", action="store_true", help="Listen to skill execution")
    parser.add_argument("--tools", action="store_true", help="Listen to tool execution")
    parser.add_argument("--once", "-o", action="store_true", help="Get only one message (for single topic)")

    args = parser.parse_args()

    # If no args, show help
    if not any([args.all, args.events, args.state, args.skills, args.tools]):
        parser.print_help()
        print("\n" + "=" * 60)
        print("Quick Start:")
        print("  python3 scripts/monitor.py --all")
        print("  python3 scripts/monitor.py --events  # For formatted events")
        print("=" * 60)
        return

    if args.all:
        watch_all_topics()
    elif args.events:
        watch_single_topic("events", once=args.once)
    elif args.state:
        watch_single_topic("state", once=args.once)
    elif args.skills:
        watch_single_topic("skill_execute", once=args.once)
    elif args.tools:
        watch_single_topic("tool_execute", once=args.once)


if __name__ == "__main__":
    main()
