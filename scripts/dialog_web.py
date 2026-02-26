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

# Load .env file if exists
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        print(f"Loaded configuration from {env_path}")
except ImportError:
    pass

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "packages" / "cmm_brain"))

from cmm_brain.memory import Turn, Event, Summary, Facts, MemoryStore
from cmm_brain.memory.filesystem_store import FileSystemMemoryStore

try:
    from cmm_brain.llm_provider import LLMConfig, OpenAICompatibleProvider, MockLLMProvider, create_provider_from_config
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

try:
    from flask import Flask, render_template_string, jsonify, request, redirect, url_for
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False


# Global instances
_llm_provider = None
_llm_config = None
_tools_config = None
_ros2_bridge = None
_world_state = {
    "robot_position": {"x": 0.0, "y": 0.0, "theta": 0.0},
    "battery_level": 85,
    "holding_object": False,
    "localization_ok": True,
    "safety_state": "NORMAL",
    "arm_state": "READY"
}


def get_ros2_bridge():
    """Get or create ROS2 bridge client."""
    global _ros2_bridge

    if _ros2_bridge is not None:
        return _ros2_bridge

    # Import bridge client
    try:
        from ros2_bridge_client import create_bridge_client
        _ros2_bridge = create_bridge_client()
        print(f"ROS2 Bridge initialized: {type(_ros2_bridge).__name__}")
    except ImportError as e:
        print(f"Warning: Could not import ros2_bridge_client: {e}")
        print("Using simulation mode")
        from ros2_bridge_client import SimulationBridge
        _ros2_bridge = SimulationBridge()

    return _ros2_bridge


def publish_event_to_ros2(event_type: str, session_id: str, payload: dict,
                          source: str = "web", success: bool = True,
                          error_message: str = "", duration_ms: int = 0,
                          event_id: str = None):
    """Publish an event to ROS2 /dialog/events topic."""
    try:
        bridge = get_ros2_bridge()
        if not bridge or not hasattr(bridge, 'publish'):
            return False

        # Generate event ID if not provided
        if not event_id:
            event_id = MemoryStore.generate_event_id()

        # Get current timestamp
        ts = MemoryStore.get_timestamp()

        # Build ROS2 DialogEvent message structure
        # Match cmm_interfaces/msg/DialogEvent.msg
        import time
        ts_parts = ts.replace('Z', '+00:00').split('T')
        date_part = ts_parts[0] if len(ts_parts) > 0 else "2026-01-01"
        time_part = ts_parts[1].split('+')[0] if len(ts_parts) > 1 else "00:00:00"

        # Parse to get seconds and nanoseconds
        try:
            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            ts_sec = int(dt.timestamp())
            ts_nanosec = int((dt.timestamp() - ts_sec) * 1e9)
        except:
            ts_sec = int(time.time())
            ts_nanosec = 0

        ros2_msg = {
            "header": {
                "stamp": {
                    "sec": ts_sec,
                    "nanosec": ts_nanosec
                },
                "frame_id": ""
            },
            "event_id": event_id,
            "session_id": session_id,
            "event_type": event_type,
            "source": source,
            "payload_json": json.dumps(payload, ensure_ascii=False),
            "timestamp": {
                "sec": ts_sec,
                "nanosec": ts_nanosec
            },
            "duration_ms": duration_ms,
            "success": success,
            "error_message": error_message
        }

        # Publish to ROS2 with message type (use std_msgs/String for compatibility)
        # Wrap the event data as JSON string
        string_msg = {"data": json.dumps(ros2_msg, ensure_ascii=False)}
        result = bridge.publish("/dialog/events", string_msg, msg_type="std_msgs/msg/String")
        if result:
            print(f"[ROS2] Published event: {event_type} to /dialog/events")
        return result

    except Exception as e:
        print(f"Warning: Failed to publish event to ROS2: {e}")
        return False


def get_llm_provider():
    """Get or create LLM provider instance."""
    global _llm_provider, _llm_config

    if _llm_provider is not None:
        return _llm_provider

    # First, try environment variables directly
    api_key = os.environ.get('LLM_API_KEY', '')
    base_url = os.environ.get('LLM_BASE_URL', '')
    model = os.environ.get('LLM_MODEL', '')

    # If env vars are set, use them directly
    if api_key and base_url:
        llm_config = LLMConfig(
            base_url=base_url,
            api_key=api_key,
            model=model or 'gpt-4o',
            timeout_sec=60.0,
            max_retries=3
        )
        _llm_provider = OpenAICompatibleProvider(llm_config)
        _llm_config = {
            'config': {'base_url': base_url, 'model': model},
            'parameters': {'temperature': 0.7}
        }
        print(f"LLM Provider initialized: {base_url} / {model}")
        return _llm_provider

    # Try to load from config file
    config_path = Path(__file__).parent.parent / 'configs' / 'providers.yaml'

    if YAML_AVAILABLE and config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_content = f.read()

            # Manually expand env vars
            import re
            def expand_env(match):
                var_name = match.group(1)
                default = match.group(2) if match.group(2) else ''
                return os.environ.get(var_name, default)

            config_content = re.sub(r'\$\{(\w+)(?::-([^}]*))?\}', expand_env, config_content)
            config = yaml.safe_load(config_content)

            provider_config = config.get('providers', {}).get('openai_compatible', {})
            provider_config_config = provider_config.get('config', {})

            # Check if we have valid config after expansion
            cfg_api_key = provider_config_config.get('api_key', '')
            cfg_base_url = provider_config_config.get('base_url', '')

            if cfg_api_key and cfg_base_url and not cfg_base_url.startswith('${'):
                _llm_provider = create_provider_from_config(provider_config)
                _llm_config = provider_config
                print(f"LLM Provider loaded from config: {cfg_base_url}")
                return _llm_provider
        except Exception as e:
            print(f"Warning: Failed to load LLM config: {e}")

    # Fallback to mock provider
    print("Warning: No valid LLM configuration found, using mock provider")
    print("Set LLM_API_KEY and LLM_BASE_URL environment variables to enable real LLM")
    _llm_provider = MockLLMProvider(LLMConfig(
        base_url='',
        api_key='',
        model='mock'
    ))
    _llm_config = {'type': 'mock'}

    return _llm_provider


def get_tools_config():
    """Load tools configuration from tools.yaml."""
    global _tools_config

    if _tools_config is not None:
        return _tools_config

    config_path = Path(__file__).parent.parent / 'configs' / 'tools.yaml'

    if YAML_AVAILABLE and config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                _tools_config = yaml.safe_load(f)
                return _tools_config
        except Exception as e:
            print(f"Warning: Failed to load tools config: {e}")

    return {'tools': {}, 'settings': {}}


def get_tools_description() -> str:
    """Generate tools description for system prompt."""
    tools_config = get_tools_config()
    tools = tools_config.get('tools', {})

    descriptions = []
    for tool_name, tool_info in tools.items():
        desc = f"- {tool_name}: {tool_info.get('description', 'No description')}"
        desc += f" (type: {tool_info.get('type', 'unknown')})"
        if tool_info.get('permission_level'):
            desc += f" [permission: {tool_info['permission_level']}]"
        descriptions.append(desc)

    return "\n".join(descriptions) if descriptions else "No tools available"


def get_system_prompt(tools_description: str = "", world_state: dict = None, user_facts: dict = None) -> str:
    """Get system prompt for Brain Agent."""
    if world_state is None:
        world_state = _world_state
    if user_facts is None:
        user_facts = {}

    # Try to load from providers.yaml
    config_path = Path(__file__).parent.parent / 'configs' / 'providers.yaml'

    if YAML_AVAILABLE and config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                prompt_template = config.get('system_prompt', '')

                if prompt_template:
                    # Replace placeholders
                    prompt = prompt_template.replace('{tools_description}', tools_description)
                    prompt = prompt + f"\n\n当前机器人状态：\n{json.dumps(world_state, ensure_ascii=False, indent=2)}\n"
                    if user_facts:
                        prompt += f"\n用户记忆：\n{json.dumps(user_facts, ensure_ascii=False, indent=2)}\n"
                    return prompt
        except Exception as e:
            print(f"Warning: Failed to load system prompt: {e}")

    # Fallback prompt
    return f"""你是一个机器人的智能助手，负责理解用户指令并规划执行步骤。

你必须以严格的 JSON 格式输出，格式如下：
{{
  "assistant_text": "对用户的回复文本",
  "plan": [
    {{"step": 1, "action": "skill_name", "args": {{...}}}},
    {{"step": 2, "action": "skill_name", "args": {{...}}}}
  ],
  "tool_calls": [],
  "memory_write": []
}}

可用工具：
{tools_description}

当前机器人状态：
{json.dumps(world_state, ensure_ascii=False, indent=2)}

执行规则：
- 按顺序执行 plan 中的步骤
- 每个步骤必须使用可用的 skill 或 tool
- 如果任务复杂，拆分为多个简单步骤
- 如果是普通对话，plan 可以为空数组"""


class SimulationExecutor:
    """Executes primitives and skills via ROS2 bridge or simulation."""

    def __init__(self, use_ros2: bool = False):
        self.use_ros2 = use_ros2
        self.world_state = _world_state.copy()
        self.execution_log = []
        self.ros2_bridge = None

        if use_ros2:
            try:
                self.ros2_bridge = get_ros2_bridge()
                print(f"Executor using ROS2 bridge: {type(self.ros2_bridge).__name__}")
            except Exception as e:
                print(f"Warning: Failed to get ROS2 bridge: {e}")
                self.use_ros2 = False

    def execute(self, plan: list, tool_calls: list) -> dict:
        """Execute a plan and return results."""
        results = {
            "success": True,
            "executed_steps": [],
            "errors": [],
            "state_changes": {}
        }

        # Execute plan steps
        for step in plan:
            step_result = self._execute_step(step)
            results["executed_steps"].append(step_result)
            if not step_result.get("success"):
                results["success"] = False
                results["errors"].append(step_result.get("error"))

        # Execute direct tool calls
        for tool_call in tool_calls:
            tool_result = self._execute_tool(tool_call)
            results["executed_steps"].append(tool_result)

        # Update world state from bridge
        if self.use_ros2 and self.ros2_bridge:
            try:
                bridge_state = self.ros2_bridge.get_world_state()
                if bridge_state:
                    self.world_state.update(bridge_state)
            except Exception as e:
                print(f"Warning: Failed to get world state: {e}")

        results["state_changes"] = self.world_state
        results["ros2_mode"] = self.use_ros2
        return results

    def _execute_step(self, step: dict) -> dict:
        """Execute a single plan step."""
        action = step.get("action", "unknown")
        args = step.get("args", {})

        result = {
            "action": action,
            "args": args,
            "success": True,
            "simulation": not self.use_ros2,
            "output": ""
        }

        # Try ROS2 execution first if available
        if self.use_ros2 and self.ros2_bridge:
            ros2_result = self._execute_via_ros2(action, args)
            if ros2_result:
                result.update(ros2_result)
                result["simulation"] = False
                self.execution_log.append(result)
                return result

        # Fall back to simulation
        if action.startswith("nav2."):
            result["output"] = self._simulate_navigation(action, args)
        elif action.startswith("arm."):
            result["output"] = self._simulate_manipulation(action, args)
        elif action.startswith("perception."):
            result["output"] = self._simulate_perception(action, args)
        elif action.startswith("skill."):
            result["output"] = self._simulate_skill(action, args)
        else:
            result["output"] = f"[SIMULATION] Executed {action} with args: {json.dumps(args)}"
            result["success"] = True

        self.execution_log.append(result)
        return result

    def _execute_via_ros2(self, action: str, args: dict) -> Optional[dict]:
        """Execute action via ROS2 bridge."""
        if not self.ros2_bridge:
            return None

        try:
            # Map action to ROS2 topic
            if action.startswith("nav2.goto"):
                # Publish to navigation topic
                target_pose = args.get("target_pose", args.get("location", {}))
                if isinstance(target_pose, str):
                    # Named location, would need resolution
                    return None

                msg = {
                    "target_pose": {
                        "position": {"x": target_pose.get("x", 0), "y": target_pose.get("y", 0), "z": 0},
                        "orientation": {"x": 0, "y": 0, "z": target_pose.get("theta", 0), "w": 1}
                    }
                }
                self.ros2_bridge.publish("/navigate_to_position/goal", msg)
                return {
                    "success": True,
                    "output": f"[ROS2] Sent navigation goal to ({target_pose.get('x', 0)}, {target_pose.get('y', 0)})"
                }

            elif action.startswith("skill."):
                # Execute skill via ROS2 action
                msg = {"skill": action, "args": args}
                self.ros2_bridge.publish("/skill/execute", msg)
                return {
                    "success": True,
                    "output": f"[ROS2] Sent skill execution request: {action}"
                }

            else:
                # Generic action
                msg = {"action": action, "args": args}
                self.ros2_bridge.publish("/tool/execute", msg)
                return {
                    "success": True,
                    "output": f"[ROS2] Sent action request: {action}"
                }

        except Exception as e:
            print(f"ROS2 execution failed: {e}")
            return {"success": False, "error": str(e)}

    def _execute_tool(self, tool_call: dict) -> dict:
        """Execute a direct tool call."""
        tool = tool_call.get("tool", "unknown")
        args = tool_call.get("args", {})

        # Try ROS2 first
        if self.use_ros2 and self.ros2_bridge:
            ros2_result = self._execute_via_ros2(tool, args)
            if ros2_result:
                ros2_result["action"] = tool
                ros2_result["args"] = args
                return ros2_result

        # Simulation fallback
        return {
            "action": tool,
            "args": args,
            "success": True,
            "simulation": True,
            "output": f"[SIMULATION] Tool {tool} executed with args: {json.dumps(args)}"
        }

    def _simulate_navigation(self, action: str, args: dict) -> str:
        """Simulate navigation actions."""
        import random
        import time

        if action == "nav2.goto":
            target = args.get("target_pose", {})
            x, y = target.get("x", 0), target.get("y", 0)

            # Simulate movement
            old_x, old_y = self.world_state["robot_position"]["x"], self.world_state["robot_position"]["y"]
            self.world_state["robot_position"]["x"] = x
            self.world_state["robot_position"]["y"] = y
            self.world_state["robot_position"]["theta"] = target.get("theta", 0)

            distance = ((x - old_x)**2 + (y - old_y)**2)**0.5
            duration = round(distance * 0.5 + random.uniform(0.5, 2.0), 2)

            return f"[SIMULATION] 导航到 ({x}, {y}), 距离 {distance:.2f}m, 耗时 {duration}s"

        elif action == "nav2.stop":
            return "[SIMULATION] 已停止导航"

        return f"[SIMULATION] 导航动作 {action}"

    def _simulate_manipulation(self, action: str, args: dict) -> str:
        """Simulate manipulation actions."""
        import random

        if action == "arm.move_to":
            pose = args.get("target_pose", {})
            return f"[SIMULATION] 机械臂移动到位姿: {json.dumps(pose)}"

        elif action == "arm.grasp":
            self.world_state["holding_object"] = True
            self.world_state["arm_state"] = "HOLDING"
            return "[SIMULATION] 抓取成功，当前持有物体"

        elif action == "arm.release":
            self.world_state["holding_object"] = False
            self.world_state["arm_state"] = "READY"
            return "[SIMULATION] 物体已释放"

        return f"[SIMULATION] 操作动作 {action}"

    def _simulate_perception(self, action: str, args: dict) -> str:
        """Simulate perception actions."""
        import random

        if action == "perception.detect":
            obj_type = args.get("object_type", "unknown")
            # Simulate detection result
            detected = random.random() > 0.2  # 80% success rate
            if detected:
                x = round(random.uniform(-2, 2), 2)
                y = round(random.uniform(-2, 2), 2)
                return f"[SIMULATION] 检测到 {obj_type} 在位置 ({x}, {y})"
            else:
                return f"[SIMULATION] 未检测到 {obj_type}"

        return f"[SIMULATION] 感知动作 {action}"

    def _simulate_skill(self, action: str, args: dict) -> str:
        """Simulate composite skills."""
        if action == "skill.pick_object":
            obj_id = args.get("object_id", "unknown")
            return f"[SIMULATION] 拾取技能执行: {obj_id}\n  → 检测物体\n  → 移动机械臂\n  → 执行抓取"

        elif action == "skill.deliver_object":
            target = args.get("target_location", {})
            return f"[SIMULATION] 递送技能执行到 {target}\n  → 导航到目标\n  → 移动机械臂\n  → 释放物体"

        elif action == "skill.approach_for_pick":
            obj_id = args.get("object_id", "unknown")
            return f"[SIMULATION] 接近物体 {obj_id} 准备拾取"

        return f"[SIMULATION] 复合技能 {action}"


def parse_llm_response(content: str) -> dict:
    """Parse LLM response and extract JSON."""
    import re

    # Try direct parse
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # Try to extract JSON from markdown code block
    code_block_pattern = r'```(?:json)?\s*\n?(.*?)\n?```'
    matches = re.findall(code_block_pattern, content, re.DOTALL)

    for match in matches:
        try:
            return json.loads(match.strip())
        except json.JSONDecodeError:
            continue

    # Try to find JSON object
    json_pattern = r'\{[\s\S]*\}'
    matches = re.findall(json_pattern, content)

    for match in matches:
        try:
            return json.loads(match)
        except json.JSONDecodeError:
            continue

    # Return default structure
    return {
        "assistant_text": content,
        "plan": [],
        "tool_calls": [],
        "memory_write": []
    }


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

        /* Modal Styles */
        .modal-overlay {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.5);
            backdrop-filter: blur(4px);
            z-index: 1000;
            animation: fadeIn 0.2s ease;
        }
        .modal-overlay.active {
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .modal {
            background: white;
            border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            max-width: 420px;
            width: 90%;
            animation: slideUp 0.3s ease;
            overflow: hidden;
        }
        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }
        @keyframes slideUp {
            from { transform: translateY(20px); opacity: 0; }
            to { transform: translateY(0); opacity: 1; }
        }
        .modal-header {
            padding: 24px 24px 16px;
            display: flex;
            align-items: center;
            gap: 16px;
        }
        .modal-icon {
            width: 48px;
            height: 48px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 24px;
            flex-shrink: 0;
        }
        .modal-icon.warning {
            background: #fef3cd;
            color: #856404;
        }
        .modal-icon.success {
            background: #d4edda;
            color: #155724;
        }
        .modal-icon.error {
            background: #f8d7da;
            color: #721c24;
        }
        .modal-icon.info {
            background: #cce5ff;
            color: #004085;
        }
        .modal-title-area {
            flex: 1;
        }
        .modal-title {
            font-size: 18px;
            font-weight: 600;
            color: #333;
            margin: 0;
        }
        .modal-subtitle {
            font-size: 14px;
            color: #666;
            margin-top: 4px;
        }
        .modal-body {
            padding: 0 24px 24px;
        }
        .modal-message {
            font-size: 15px;
            color: #444;
            line-height: 1.6;
        }
        .modal-footer {
            padding: 16px 24px;
            background: #f8f9fa;
            display: flex;
            justify-content: flex-end;
            gap: 12px;
        }
        .btn-cancel {
            background: #fff;
            color: #666;
            border: 1px solid #ddd;
            padding: 10px 20px;
            border-radius: 8px;
            font-size: 14px;
            cursor: pointer;
            transition: all 0.2s;
        }
        .btn-cancel:hover {
            background: #f0f0f0;
            border-color: #ccc;
        }
        .btn-confirm {
            padding: 10px 20px;
            border-radius: 8px;
            font-size: 14px;
            cursor: pointer;
            transition: all 0.2s;
            border: none;
        }
        .btn-confirm.danger {
            background: linear-gradient(135deg, #ff6b6b 0%, #dc3545 100%);
            color: white;
        }
        .btn-confirm.danger:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(220, 53, 69, 0.4);
        }
        .btn-confirm.success {
            background: linear-gradient(135deg, #51cf66 0%, #28a745 100%);
            color: white;
        }
        .btn-confirm.success:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(40, 167, 69, 0.4);
        }
        .btn-confirm.primary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        .btn-confirm.primary:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
        }

        /* New Session Modal Styles */
        .new-session-modal {
            max-width: 440px;
        }
        .new-session-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            margin: 0;
            border-radius: 16px 16px 0 0;
            padding: 24px;
        }
        .new-session-header .modal-title {
            color: white;
        }
        .new-session-header .modal-subtitle {
            color: rgba(255, 255, 255, 0.8);
        }
        .new-session-icon {
            background: rgba(255, 255, 255, 0.2);
            color: white;
            width: 48px;
            height: 48px;
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .new-session-icon svg {
            width: 24px;
            height: 24px;
        }
        .new-session-body {
            padding: 24px;
        }
        .input-group {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }
        .input-label {
            font-size: 14px;
            font-weight: 600;
            color: #333;
        }
        .modal-input {
            width: 100%;
            padding: 12px 16px;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            font-size: 15px;
            transition: all 0.2s ease;
            box-sizing: border-box;
        }
        .modal-input:focus {
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.15);
        }
        .modal-input::placeholder {
            color: #aaa;
        }
        .input-hint {
            font-size: 12px;
            color: #888;
            margin: 4px 0 0 0;
        }
        .new-session-footer {
            padding: 16px 24px;
            background: #f8f9fa;
            border-radius: 0 0 16px 16px;
        }
        .btn-icon {
            font-size: 16px;
            margin-right: 6px;
        }
        .btn-confirm.primary {
            display: flex;
            align-items: center;
        }

        /* Toast Notification */
        .toast-container {
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 2000;
            display: flex;
            flex-direction: column;
            gap: 10px;
        }
        .toast {
            padding: 16px 20px;
            border-radius: 12px;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
            display: flex;
            align-items: center;
            gap: 12px;
            animation: slideInRight 0.3s ease;
            min-width: 300px;
            max-width: 400px;
        }
        @keyframes slideInRight {
            from { transform: translateX(100%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        .toast.success {
            background: linear-gradient(135deg, #d4edda 0%, #c3e6cb 100%);
            border-left: 4px solid #28a745;
        }
        .toast.error {
            background: linear-gradient(135deg, #f8d7da 0%, #f5c6cb 100%);
            border-left: 4px solid #dc3545;
        }
        .toast.info {
            background: linear-gradient(135deg, #cce5ff 0%, #b8daff 100%);
            border-left: 4px solid #007bff;
        }
        .toast-icon {
            font-size: 20px;
        }
        .toast-message {
            flex: 1;
            font-size: 14px;
            color: #333;
        }
        .toast-close {
            background: none;
            border: none;
            font-size: 18px;
            cursor: pointer;
            color: #999;
            padding: 0;
            line-height: 1;
        }
        .toast-close:hover {
            color: #666;
        }
    </style>
</head>
<body>
    <header>
        <div class="container">
            <h1>ROS2 Brain Agent</h1>
            <p>Dialog Management Console</p>
            <nav>
                <a href="/chat" class="{{ 'active' if page == 'chat' else '' }}">Chat</a>
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

    <!-- Toast Container -->
    <div class="toast-container" id="toastContainer"></div>

    <!-- Modal Overlay -->
    <div class="modal-overlay" id="modalOverlay">
        <div class="modal">
            <div class="modal-header">
                <div class="modal-icon warning" id="modalIcon">⚠️</div>
                <div class="modal-title-area">
                    <h3 class="modal-title" id="modalTitle">确认操作</h3>
                    <p class="modal-subtitle" id="modalSubtitle"></p>
                </div>
            </div>
            <div class="modal-body">
                <p class="modal-message" id="modalMessage">您确定要执行此操作吗？</p>
            </div>
            <div class="modal-footer">
                <button class="btn-cancel" id="modalCancel">取消</button>
                <button class="btn-confirm danger" id="modalConfirm">确定</button>
            </div>
        </div>
    </div>

    <!-- New Session Modal -->
    <div class="modal-overlay" id="newSessionModal">
        <div class="modal new-session-modal">
            <div class="modal-header new-session-header">
                <div class="modal-icon new-session-icon">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M12 5v14M5 12h14"/>
                    </svg>
                </div>
                <div class="modal-title-area">
                    <h3 class="modal-title">Create New Session</h3>
                    <p class="modal-subtitle">Start a fresh conversation</p>
                </div>
            </div>
            <div class="modal-body new-session-body">
                <div class="input-group">
                    <label class="input-label" for="newSessionInput">Session Name</label>
                    <input type="text" class="modal-input" id="newSessionInput" placeholder="Enter session name...">
                    <p class="input-hint">Leave empty to auto-generate a name</p>
                </div>
            </div>
            <div class="modal-footer new-session-footer">
                <button class="btn-cancel" id="newSessionCancel">Cancel</button>
                <button class="btn-confirm primary" id="newSessionConfirm">
                    <span class="btn-icon">+</span>
                    Create Session
                </button>
            </div>
        </div>
    </div>

    <script>
    // Toast Notification System
    function showToast(message, type = 'info') {
        const container = document.getElementById('toastContainer');
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;

        const icons = {
            success: '✓',
            error: '✕',
            info: 'ℹ'
        };

        toast.innerHTML = `
            <span class="toast-icon">${icons[type] || 'ℹ'}</span>
            <span class="toast-message">${message}</span>
            <button class="toast-close" onclick="this.parentElement.remove()">×</button>
        `;

        container.appendChild(toast);

        // Auto remove after 3 seconds
        setTimeout(() => {
            toast.style.animation = 'slideInRight 0.3s ease reverse';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }

    // Modal System
    let modalCallback = null;

    function showModal(options) {
        const overlay = document.getElementById('modalOverlay');
        const icon = document.getElementById('modalIcon');
        const title = document.getElementById('modalTitle');
        const subtitle = document.getElementById('modalSubtitle');
        const message = document.getElementById('modalMessage');
        const confirmBtn = document.getElementById('modalConfirm');
        const cancelBtn = document.getElementById('modalCancel');

        // Set icon
        const iconMap = {
            warning: { emoji: '⚠️', class: 'warning' },
            danger: { emoji: '🗑️', class: 'warning' },
            success: { emoji: '✓', class: 'success' },
            error: { emoji: '✕', class: 'error' },
            info: { emoji: 'ℹ', class: 'info' }
        };
        const iconData = iconMap[options.type] || iconMap.info;
        icon.textContent = options.icon || iconData.emoji;
        icon.className = `modal-icon ${iconData.class}`;

        // Set content
        title.textContent = options.title || '确认操作';
        subtitle.textContent = options.subtitle || '';
        subtitle.style.display = options.subtitle ? 'block' : 'none';
        message.textContent = options.message || '您确定要执行此操作吗？';

        // Set button style
        confirmBtn.className = `btn-confirm ${options.confirmType || 'danger'}`;
        confirmBtn.textContent = options.confirmText || '确定';

        // Store callback
        modalCallback = options.onConfirm || null;

        // Show modal
        overlay.classList.add('active');
    }

    function hideModal() {
        document.getElementById('modalOverlay').classList.remove('active');
        modalCallback = null;
    }

    // Modal event listeners
    document.getElementById('modalCancel').addEventListener('click', hideModal);
    document.getElementById('modalOverlay').addEventListener('click', function(e) {
        if (e.target === this) hideModal();
    });
    document.getElementById('modalConfirm').addEventListener('click', function() {
        if (modalCallback) modalCallback();
        hideModal();
    });

    // New Session Modal System
    function showNewSessionModal() {
        const modal = document.getElementById('newSessionModal');
        const input = document.getElementById('newSessionInput');
        modal.classList.add('active');
        // Auto-fill default session name
        input.value = 'session_' + Date.now();
        setTimeout(() => {
            input.focus();
            input.select(); // Select all text for easy editing
        }, 100);
    }

    function hideNewSessionModal() {
        document.getElementById('newSessionModal').classList.remove('active');
    }

    // New Session Modal event listeners
    document.getElementById('newSessionCancel').addEventListener('click', hideNewSessionModal);
    document.getElementById('newSessionModal').addEventListener('click', function(e) {
        if (e.target === this) hideNewSessionModal();
    });
    document.getElementById('newSessionInput').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            document.getElementById('newSessionConfirm').click();
        }
    });

    // Create new session logic
    async function createNewSession() {
        const input = document.getElementById('newSessionInput');
        let sessionName = input.value.trim();

        // Auto-generate name if empty
        if (!sessionName) {
            sessionName = 'session_' + Date.now();
        }

        try {
            const response = await fetch('/api/session/create', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({session_id: sessionName})
            });

            const data = await response.json();
            if (data.success) {
                hideNewSessionModal();
                window.location.href = '/chat/' + data.session_id;
            } else {
                showToast('Failed to create session: ' + data.error, 'error');
            }
        } catch (err) {
            showToast('Error: ' + err.message, 'error');
        }
    }

    document.getElementById('newSessionConfirm').addEventListener('click', createNewSession);
    </script>
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
                <tr id="session-row-{{ session.id }}">
                    <td><code>{{ session.id }}</code></td>
                    <td>{{ session.turns }}</td>
                    <td>{{ session.events }}</td>
                    <td class="timestamp">{{ session.last_update }}</td>
                    <td>
                        <a href="/chat/{{ session.id }}" class="btn btn-primary btn-sm">Chat</a>
                        <a href="/session/{{ session.id }}" class="btn btn-primary btn-sm">View</a>
                        <a href="/session/{{ session.id }}/analyze" class="btn btn-primary btn-sm">Analyze</a>
                        <a href="/api/session/{{ session.id }}/export" class="btn btn-primary btn-sm">Export</a>
                        <button onclick="confirmDelete('{{ session.id }}')" class="btn btn-danger btn-sm">Delete</button>
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

<style>
.btn-danger {
    background: linear-gradient(135deg, #ff6b6b 0%, #dc3545 100%);
    color: white;
    border: none;
}
.btn-danger:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(220, 53, 69, 0.3);
}
</style>

<script>
document.getElementById('searchInput').addEventListener('input', function(e) {
    const search = e.target.value.toLowerCase();
    const rows = document.querySelectorAll('#sessionsTable tbody tr');
    rows.forEach(row => {
        const text = row.textContent.toLowerCase();
        row.style.display = text.includes(search) ? '' : 'none';
    });
});

function confirmDelete(sessionId) {
    showModal({
        type: 'danger',
        icon: '🗑️',
        title: '删除会话',
        subtitle: 'Session: ' + sessionId,
        message: '确定要删除此会话吗？此操作不可撤销，所有对话记录和事件将被永久删除。',
        confirmText: '确认删除',
        confirmType: 'danger',
        onConfirm: function() {
            deleteSession(sessionId);
        }
    });
}

function deleteSession(sessionId) {
    fetch('/api/session/' + sessionId, {
        method: 'DELETE',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Remove row from table with animation
            const row = document.getElementById('session-row-' + sessionId);
            if (row) {
                row.style.transition = 'all 0.3s ease';
                row.style.opacity = '0';
                row.style.transform = 'translateX(-20px)';
                setTimeout(() => row.remove(), 300);
            }
            showToast('会话已成功删除', 'success');
        } else {
            showToast('删除失败: ' + (data.error || '未知错误'), 'error');
        }
    })
    .catch(error => {
        showToast('删除出错: ' + error.message, 'error');
    });
}
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

CHAT_TEMPLATE = """
<div class="chat-container">
    <div class="chat-header">
        <div class="session-info">
            <span class="session-label">Session:</span>
            <span class="session-id" id="currentSession">{{ session_id }}</span>
            <button class="btn btn-primary btn-sm" onclick="newSession()">New Session</button>
        </div>
        <div class="provider-info">
            <span class="badge badge-info">{{ provider_info }}</span>
        </div>
    </div>

    <div class="chat-messages" id="chatMessages">
        {% if turns %}
        {% for turn in turns %}
        <div class="message {{ turn.speaker }}">
            <div class="message-header">
                <span class="speaker">{{ 'User' if turn.speaker == 'user' else 'Assistant' }}</span>
                <span class="timestamp">{{ turn.ts }}</span>
            </div>
            <div class="message-content">{{ turn.text }}</div>
        </div>
        {% endfor %}
        {% else %}
        <div class="empty-chat">
            <p>Start a new conversation</p>
        </div>
        {% endif %}
    </div>

    <div class="chat-input">
        <form id="chatForm" onsubmit="sendMessage(event)">
            <input type="text" id="userInput" placeholder="Type your message..." autocomplete="off">
            <button type="submit" class="btn btn-primary" id="sendBtn">Send</button>
        </form>
    </div>
</div>

<style>
.chat-container {
    display: flex;
    flex-direction: column;
    height: calc(100vh - 200px);
    min-height: 500px;
    background: white;
    border-radius: 12px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    overflow: hidden;
}

.chat-header {
    padding: 15px 20px;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.session-info {
    display: flex;
    align-items: center;
    gap: 10px;
}

.session-label {
    opacity: 0.8;
}

.session-id {
    font-family: monospace;
    background: rgba(255,255,255,0.2);
    padding: 4px 10px;
    border-radius: 4px;
}

.chat-messages {
    flex: 1;
    overflow-y: auto;
    padding: 20px;
    background: #f8f9fa;
}

.message {
    margin-bottom: 15px;
    padding: 12px 16px;
    border-radius: 12px;
    max-width: 80%;
}

.message.user {
    background: #667eea;
    color: white;
    margin-left: auto;
    border-bottom-right-radius: 4px;
}

.message.assistant {
    background: white;
    border: 1px solid #e0e0e0;
    border-bottom-left-radius: 4px;
}

.message-header {
    display: flex;
    justify-content: space-between;
    margin-bottom: 8px;
    font-size: 12px;
    opacity: 0.8;
}

.message.user .message-header {
    color: rgba(255,255,255,0.8);
}

.message.assistant .message-header {
    color: #666;
}

.message-content {
    white-space: pre-wrap;
    word-break: break-word;
    line-height: 1.5;
}

.empty-chat {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100%;
    color: #999;
}

.chat-input {
    padding: 15px 20px;
    background: white;
    border-top: 1px solid #eee;
}

.chat-input form {
    display: flex;
    gap: 10px;
}

.chat-input input {
    flex: 1;
    padding: 12px 16px;
    border: 2px solid #e0e0e0;
    border-radius: 8px;
    font-size: 14px;
    transition: border-color 0.2s;
}

.chat-input input:focus {
    outline: none;
    border-color: #667eea;
}

.chat-input button {
    padding: 12px 24px;
}

.typing-indicator {
    display: none;
    padding: 12px 16px;
    color: #666;
    font-style: italic;
}

.typing-indicator.active {
    display: block;
}

.provider-info {
    font-size: 12px;
}

/* Plan and Execution Styles */
.plan-section, .execution-section, .memory-section {
    margin-top: 12px;
    padding: 10px;
    background: rgba(0,0,0,0.05);
    border-radius: 6px;
    font-size: 13px;
}

.plan-section strong, .execution-section strong, .memory-section strong {
    display: block;
    margin-bottom: 8px;
    color: #667eea;
}

.plan-section ol, .execution-section ul, .memory-section ul {
    margin: 0;
    padding-left: 20px;
}

.plan-section li, .execution-section li, .memory-section li {
    margin: 4px 0;
    line-height: 1.4;
}

.plan-section code, .memory-section code {
    background: rgba(102, 126, 234, 0.2);
    padding: 2px 6px;
    border-radius: 4px;
    font-family: 'Monaco', monospace;
    font-size: 12px;
}

.message .badge {
    background: #28a745;
    color: white;
    padding: 2px 8px;
    border-radius: 10px;
    font-size: 11px;
    margin-left: 8px;
}
</style>

<script>
let currentSession = '{{ session_id }}';

function scrollToBottom() {
    const container = document.getElementById('chatMessages');
    container.scrollTop = container.scrollHeight;
}

function addMessage(speaker, text, ts) {
    const container = document.getElementById('chatMessages');

    // Remove empty state if present
    const emptyState = container.querySelector('.empty-chat');
    if (emptyState) {
        emptyState.remove();
    }

    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${speaker}`;
    messageDiv.innerHTML = `
        <div class="message-header">
            <span class="speaker">${speaker === 'user' ? 'User' : 'Assistant'}</span>
            <span class="timestamp">${ts}</span>
        </div>
        <div class="message-content">${escapeHtml(text)}</div>
    `;

    container.appendChild(messageDiv);
    scrollToBottom();
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showTyping() {
    const container = document.getElementById('chatMessages');
    const typingDiv = document.createElement('div');
    typingDiv.className = 'message assistant typing';
    typingDiv.id = 'typingIndicator';
    typingDiv.innerHTML = '<div class="message-content">...</div>';
    container.appendChild(typingDiv);
    scrollToBottom();
}

function hideTyping() {
    const typing = document.getElementById('typingIndicator');
    if (typing) typing.remove();
}

function addStructuredMessage(speaker, data, ts) {
    const container = document.getElementById('chatMessages');

    // Remove empty state if present
    const emptyState = container.querySelector('.empty-chat');
    if (emptyState) {
        emptyState.remove();
    }

    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${speaker}`;

    let contentHtml = '';

    if (speaker === 'assistant' && typeof data === 'object') {
        // Assistant message with plan and execution
        contentHtml = `<div class="message-content">${escapeHtml(data.response || '')}</div>`;

        // Show plan if exists
        if (data.plan && data.plan.length > 0) {
            contentHtml += '<div class="plan-section"><strong>📋 规划:</strong><ol>';
            data.plan.forEach(step => {
                contentHtml += `<li><code>${step.action}</code> ${JSON.stringify(step.args || {})}</li>`;
            });
            contentHtml += '</ol></div>';
        }

        // Show execution result if exists
        if (data.execution_result && data.execution_result.executed_steps) {
            contentHtml += '<div class="execution-section"><strong>⚡ 执行结果 (仿真):</strong><ul>';
            data.execution_result.executed_steps.forEach(step => {
                contentHtml += `<li>${escapeHtml(step.output || step.action)}</li>`;
            });
            contentHtml += '</ul></div>';
        }

        // Show memory updates if exists
        if (data.memory_write && data.memory_write.length > 0) {
            contentHtml += '<div class="memory-section"><strong>📝 记忆更新:</strong><ul>';
            data.memory_write.forEach(mem => {
                contentHtml += `<li><code>${mem.key}</code>: ${escapeHtml(String(mem.value))}</li>`;
            });
            contentHtml += '</ul></div>';
        }

        messageDiv.innerHTML = `
            <div class="message-header">
                <span class="speaker">Assistant</span>
                <span class="timestamp">${ts}</span>
                <span class="badge">${data.dry_run ? '仿真模式' : '实机模式'}</span>
            </div>
            ${contentHtml}
        `;
    } else {
        // Simple text message
        const text = typeof data === 'string' ? data : data.response || '';
        messageDiv.innerHTML = `
            <div class="message-header">
                <span class="speaker">${speaker === 'user' ? 'User' : 'Assistant'}</span>
                <span class="timestamp">${ts}</span>
            </div>
            <div class="message-content">${escapeHtml(text)}</div>
        `;
    }

    container.appendChild(messageDiv);
    scrollToBottom();
}

async function sendMessage(event) {
    event.preventDefault();

    const input = document.getElementById('userInput');
    const sendBtn = document.getElementById('sendBtn');
    const text = input.value.trim();

    if (!text) return;

    // Disable input
    input.value = '';
    input.disabled = true;
    sendBtn.disabled = true;

    // Add user message
    addMessage('user', text, new Date().toLocaleTimeString());

    // Show typing indicator
    showTyping();

    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                session_id: currentSession,
                message: text,
                dry_run: true
            })
        });

        const data = await response.json();
        hideTyping();

        if (data.error) {
            addMessage('assistant', 'Error: ' + data.error, data.ts || new Date().toLocaleTimeString());
        } else {
            addStructuredMessage('assistant', data, data.ts);
        }
    } catch (err) {
        hideTyping();
        addMessage('assistant', 'Network error: ' + err.message, new Date().toLocaleTimeString());
    }

    // Re-enable input
    input.disabled = false;
    sendBtn.disabled = false;
    input.focus();
}

async function newSession() {
    showNewSessionModal();
}

// Scroll to bottom on load
scrollToBottom();

// Focus input
document.getElementById('userInput').focus();
</script>
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

    @app.route('/chat')
    def chat_new():
        """Redirect to a new chat session."""
        import time
        session_id = f"chat_{int(time.time())}"
        return redirect(f'/chat/{session_id}')

    @app.route('/chat/<session_id>')
    def chat_session(session_id):
        """Chat interface for a session."""
        # Create session if not exists
        if not store.session_exists(session_id):
            store.create_session(session_id)

        turns = store.get_all_turns(session_id)
        turns_data = []
        for t in turns:
            turns_data.append({
                'turn_id': t.turn_id,
                'ts': format_timestamp(t.ts),
                'speaker': t.speaker,
                'text': t.text
            })

        # Get provider info
        provider_info = 'Mock Provider'
        try:
            provider = get_llm_provider()
            if hasattr(provider, 'config'):
                provider_info = provider.config.model
        except:
            pass

        return render_template_string(
            BASE_TEMPLATE.replace('{% block content %}{% endblock %}', CHAT_TEMPLATE),
            title=f'Chat - {session_id}',
            page='chat',
            session_id=session_id,
            turns=turns_data,
            provider_info=provider_info
        )

    # Chat API endpoints
    @app.route('/api/session/create', methods=['POST'])
    def api_create_session():
        """Create a new session."""
        data = request.get_json() or {}
        session_id = data.get('session_id')

        if not session_id:
            import time
            session_id = f"chat_{int(time.time())}"

        if store.session_exists(session_id):
            return jsonify({'success': False, 'error': 'Session already exists'})

        store.create_session(session_id)
        return jsonify({'success': True, 'session_id': session_id})

    @app.route('/api/world_state', methods=['GET'])
    def api_get_world_state():
        """Get current robot world state."""
        bridge = get_ros2_bridge()

        if hasattr(bridge, 'get_world_state'):
            state = bridge.get_world_state()
        else:
            state = _world_state

        return jsonify({
            'success': True,
            'state': state,
            'ros2_connected': hasattr(bridge, 'connected') and bridge.connected
        })

    @app.route('/api/mode', methods=['GET', 'POST'])
    def api_mode():
        """Get or set execution mode (simulation/ros2)."""
        global _ros2_bridge

        if request.method == 'GET':
            try:
                bridge = get_ros2_bridge()
                is_ros2 = hasattr(bridge, 'connected') and getattr(bridge, 'connected', False)
                ws_available = 'WEBSOCKET_AVAILABLE' in globals() and WEBSOCKET_AVAILABLE
            except:
                is_ros2 = False
                ws_available = False

            return jsonify({
                'mode': 'ros2' if is_ros2 else 'simulation',
                'ros2_available': ws_available,
                'rosbridge_url': os.environ.get('ROSBRIDGE_URL', 'ws://localhost:9090')
            })

        elif request.method == 'POST':
            data = request.get_json() or {}
            mode = data.get('mode', 'simulation')
            rosbridge_url = data.get('rosbridge_url')

            if rosbridge_url:
                os.environ['ROSBRIDGE_URL'] = rosbridge_url

            if mode == 'ros2':
                os.environ['USE_SIMULATION'] = 'false'
                _ros2_bridge = None  # Reset bridge
                bridge = get_ros2_bridge()
                connected = hasattr(bridge, 'connected') and bridge.connected
                return jsonify({
                    'success': connected,
                    'mode': 'ros2',
                    'connected': connected,
                    'message': 'Connected to ROS2' if connected else 'Failed to connect to ROS2, using simulation'
                })
            else:
                os.environ['USE_SIMULATION'] = 'true'
                _ros2_bridge = None  # Reset bridge
                return jsonify({
                    'success': True,
                    'mode': 'simulation',
                    'message': 'Switched to simulation mode'
                })

    @app.route('/api/chat', methods=['POST'])
    def api_chat():
        """Send a message and get a Brain Agent response with planning and execution."""
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        session_id = data.get('session_id', 'default')
        message = data.get('message', '')
        dry_run = data.get('dry_run', True)  # Default to simulation mode

        if not message:
            return jsonify({'error': 'No message provided'}), 400

        # Ensure session exists
        if not store.session_exists(session_id):
            store.create_session(session_id)

        # Get user facts for context
        user_facts = {}
        try:
            facts = store.get_session_facts(session_id)
            user_facts = facts.facts if facts else {}
        except:
            pass

        # Build system prompt with tools and state
        tools_description = get_tools_description()
        system_prompt = get_system_prompt(tools_description, _world_state, user_facts)

        # Save user turn
        turn_id = store.get_next_turn_id(session_id)
        user_ts = MemoryStore.get_timestamp()
        user_turn = Turn(
            turn_id=turn_id,
            ts=user_ts,
            speaker='user',
            text=message
        )
        store.append_turn(session_id, user_turn)

        # Publish user turn event to ROS2
        publish_event_to_ros2(
            event_type="turn_start",
            session_id=session_id,
            source="user",
            payload={"turn_id": turn_id, "text": message},
            success=True
        )

        # Get conversation history for context
        recent_turns = store.get_recent_turns(session_id, limit=10)
        messages = [{'role': 'system', 'content': system_prompt}]
        for t in recent_turns:
            role = 'user' if t.speaker == 'user' else 'assistant'
            # For assistant turns, use the original text not the formatted one
            messages.append({'role': role, 'content': t.text})

        # Phase 1: Intent Understanding & Planning
        try:
            provider = get_llm_provider()
            response = provider.call(messages)
            llm_output = parse_llm_response(response.content)

            # Extract structured output
            assistant_text = llm_output.get('assistant_text', response.content)
            plan = llm_output.get('plan', [])
            tool_calls = llm_output.get('tool_calls', [])
            memory_write = llm_output.get('memory_write', [])

            # Save LLM event
            llm_event_id = MemoryStore.generate_event_id()
            llm_ts = MemoryStore.get_timestamp()
            llm_payload = {
                'model': response.model,
                'usage': response.usage,
                'plan': plan,
                'tool_calls': tool_calls
            }
            event = Event(
                event_id=llm_event_id,
                ts=llm_ts,
                event_type='llm_result',
                session_id=session_id,
                payload=llm_payload,
                duration_ms=response.duration_ms,
                success=True
            )
            store.append_event(session_id, event)

            # Publish LLM result event to ROS2
            publish_event_to_ros2(
                event_type="llm_result",
                session_id=session_id,
                source="llm",
                payload=llm_payload,
                success=True,
                duration_ms=response.duration_ms,
                event_id=llm_event_id
            )

        except Exception as e:
            # Log error
            error_event_id = MemoryStore.generate_event_id()
            error_ts = MemoryStore.get_timestamp()
            event = Event(
                event_id=error_event_id,
                ts=error_ts,
                event_type='llm_error',
                session_id=session_id,
                payload={},
                duration_ms=0,
                success=False,
                error_message=str(e)
            )
            store.append_event(session_id, event)

            # Publish error event to ROS2
            publish_event_to_ros2(
                event_type="error",
                session_id=session_id,
                source="llm",
                payload={"error_type": "llm_error"},
                success=False,
                error_message=str(e),
                event_id=error_event_id
            )

            return jsonify({
                'error': f"LLM Error: {str(e)}",
                'session_id': session_id,
                'ts': format_timestamp(MemoryStore.get_timestamp())
            })

        # Phase 2: Execution (ROS2 or Simulation)
        execution_result = None
        if plan or tool_calls:
            # Use ROS2 bridge if not in dry_run mode
            use_ros2 = not dry_run
            executor = SimulationExecutor(use_ros2=use_ros2)
            execution_result = executor.execute(plan, tool_calls)

            # Save execution event
            exec_event_id = MemoryStore.generate_event_id()
            exec_ts = MemoryStore.get_timestamp()
            exec_payload = {
                'plan': plan,
                'tool_calls': tool_calls,
                'execution_result': execution_result
            }
            exec_event = Event(
                event_id=exec_event_id,
                ts=exec_ts,
                event_type='skill_execute',
                session_id=session_id,
                payload=exec_payload,
                duration_ms=0,
                success=execution_result.get('success', True)
            )
            store.append_event(session_id, exec_event)

            # Publish skill execute event to ROS2
            publish_event_to_ros2(
                event_type="skill_execute",
                session_id=session_id,
                source="executor",
                payload=exec_payload,
                success=execution_result.get('success', True),
                event_id=exec_event_id
            )

        # Phase 3: Memory Update
        if memory_write:
            for mem_op in memory_write:
                key = mem_op.get('key')
                value = mem_op.get('value')
                op_type = mem_op.get('type', 'upsert')

                if key and value:
                    try:
                        facts = store.get_session_facts(session_id)
                        if op_type == 'upsert':
                            facts.facts[key] = value
                        elif op_type == 'delete' and key in facts.facts:
                            del facts.facts[key]
                        # Save facts
                        store._save_session_facts(session_id, facts)
                    except Exception as e:
                        print(f"Warning: Failed to update memory: {e}")

        # Build response text with execution results
        response_text = assistant_text
        if execution_result and execution_result.get('executed_steps'):
            response_text += "\n\n--- 执行结果 (仿真模式) ---"
            for step in execution_result['executed_steps']:
                response_text += f"\n• {step.get('output', step.get('action', 'unknown'))}"

        # Save assistant turn
        assistant_ts = MemoryStore.get_timestamp()
        assistant_turn = Turn(
            turn_id=turn_id + 1,
            ts=assistant_ts,
            speaker='assistant',
            text=response_text,
            metadata={
                'model': response.model,
                'plan': plan,
                'tool_calls': tool_calls,
                'execution_result': execution_result
            }
        )
        store.append_turn(session_id, assistant_turn)

        # Publish turn_end event to ROS2
        publish_event_to_ros2(
            event_type="turn_end",
            session_id=session_id,
            source="llm",
            payload={
                'turn_id': turn_id + 1,
                'text': assistant_text,
                'plan': plan,
                'tool_calls': tool_calls,
                'execution_result': execution_result
            },
            success=True
        )

        return jsonify({
            'response': assistant_text,
            'full_response': response_text,
            'plan': plan,
            'tool_calls': tool_calls,
            'execution_result': execution_result,
            'memory_write': memory_write,
            'session_id': session_id,
            'turn_id': turn_id + 1,
            'ts': format_timestamp(assistant_turn.ts),
            'model': response.model,
            'dry_run': dry_run
        })

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

    @app.route('/api/session/<session_id>', methods=['DELETE'])
    def api_delete_session(session_id):
        """Delete a session and all its data."""
        if not store.session_exists(session_id):
            return jsonify({'success': False, 'error': 'Session not found'}), 404

        try:
            deleted = store.delete_session(session_id)
            if deleted:
                return jsonify({'success': True, 'message': f'Session {session_id} deleted'})
            else:
                return jsonify({'success': False, 'error': 'Failed to delete session'}), 500
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

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
