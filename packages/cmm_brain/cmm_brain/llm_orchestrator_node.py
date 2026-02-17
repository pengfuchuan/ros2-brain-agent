# Copyright 2026 ROS2 Brain Agent Team
# SPDX-License-Identifier: Apache-2.0

"""
LLM Orchestrator Node - Orchestrates LLM calls and plan execution.

Responsibilities:
- Call LLM with proper context (memory, tools, world state)
- Parse LLM output (JSON)
- Dispatch tool calls to tool_router
- Handle memory_write operations
"""

import json
import os
import yaml
import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup, MutuallyExclusiveCallbackGroup
from std_msgs.msg import String
from cmm_interfaces.srv import ToolExecute, MemoryQuery

from cmm_brain.llm_provider import (
    create_provider_from_config,
    LLMProvider,
    LLMConfig
)


class LLMOrchestratorNode(Node):
    """LLM Orchestrator ROS2 Node."""

    def __init__(self):
        super().__init__('llm_orchestrator_node')

        # Declare parameters
        self.declare_parameter('config_path', 'configs')
        self.declare_parameter('providers_config', 'providers.yaml')
        self.declare_parameter('tools_config', 'tools.yaml')
        self.declare_parameter('default_provider', 'openai_compatible')

        # Get parameters
        self.config_path = self.get_parameter('config_path').value
        self.providers_config = self.get_parameter('providers_config').value
        self.tools_config = self.get_parameter('tools_config').value
        self.default_provider = self.get_parameter('default_provider').value

        # Callback groups
        self.reentrant_group = ReentrantCallbackGroup()
        selfExclusive_group = MutuallyExclusiveCallbackGroup()

        # Load configurations
        self.providers = self._load_yaml(
            os.path.join(self.config_path, self.providers_config)
        )
        self.tools = self._load_yaml(
            os.path.join(self.config_path, self.tools_config)
        )

        # Initialize LLM provider
        self.llm = self._init_llm_provider()

        # LLM output schema
        self.output_schema = {
            "type": "object",
            "properties": {
                "assistant_text": {"type": "string"},
                "plan": {
                    "type": "array",
                    "items": {"type": "object"}
                },
                "tool_calls": {
                    "type": "array",
                    "items": {"type": "object"}
                },
                "memory_write": {
                    "type": "array",
                    "items": {"type": "object"}
                }
            },
            "required": ["assistant_text"]
        }

        # Subscribers
        self.process_input_sub = self.create_subscription(
            String,
            '/dialog/process_input',
            self.handle_process_input,
            10,
            callback_group=self.reentrant_group
        )

        # Publishers
        self.llm_response_pub = self.create_publisher(
            String,
            '/dialog/llm_response',
            10
        )

        self.tool_call_pub = self.create_publisher(
            String,
            '/tool/execute',
            10
        )

        # Service clients
        self.tool_execute_client = self.create_client(
            ToolExecute,
            '/tool/execute_sync',
            callback_group=selfExclusive_group
        )

        self.memory_query_client = self.create_client(
            MemoryQuery,
            '/memory/query',
            callback_group=selfExclusive_group
        )

        self.get_logger().info('LLM Orchestrator initialized')

    def _load_yaml(self, path: str) -> dict:
        """Load YAML configuration file."""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except FileNotFoundError:
            self.get_logger().warning(f'Config file not found: {path}')
            return {}
        except yaml.YAMLError as e:
            self.get_logger().error(f'Error parsing YAML {path}: {e}')
            return {}

    def _init_llm_provider(self) -> LLMProvider:
        """Initialize LLM provider from configuration."""
        providers = self.providers.get('providers', {})

        if self.default_provider not in providers:
            self.get_logger().warning(
                f"Provider '{self.default_provider}' not found, using mock"
            )
            return create_provider_from_config({
                'type': 'mock',
                'config': {'model': 'mock'}
            })

        provider_config = providers[self.default_provider]

        if not provider_config.get('enabled', True):
            self.get_logger().warning(
                f"Provider '{self.default_provider}' is disabled, using mock"
            )
            return create_provider_from_config({
                'type': 'mock',
                'config': {'model': 'mock'}
            })

        return create_provider_from_config(provider_config)

    def _get_system_prompt(
        self,
        tools_description: str,
        world_state: dict,
        user_facts: dict
    ) -> str:
        """Generate system prompt with context."""
        prompt_template = self.providers.get('system_prompt', '')

        return prompt_template.format(
            tools_description=tools_description,
            world_state=json.dumps(world_state, ensure_ascii=False, indent=2),
            user_facts=json.dumps(user_facts, ensure_ascii=False, indent=2)
        )

    def _build_tools_description(self) -> str:
        """Build tools description for LLM prompt."""
        tools_desc = []
        tools_list = self.tools.get('tools', {})

        for name, tool in tools_list.items():
            desc = f"- {name}: {tool.get('description', 'No description')}"
            schema = tool.get('json_schema', {})
            if schema.get('properties'):
                props = ', '.join(schema['properties'].keys())
                desc += f" (args: {props})"
            tools_desc.append(desc)

        return '\n'.join(tools_desc)

    def handle_process_input(self, msg: String) -> None:
        """Handle input from dialog manager."""
        try:
            data = json.loads(msg.data)
        except json.JSONDecodeError:
            self.get_logger().error(f'Invalid JSON in process input: {msg.data[:100]}')
            return

        session_id = data.get('session_id', 'default')
        turn_id = data.get('turn_id', 0)
        text = data.get('text', '')

        # Build context
        context = self._build_context(session_id)

        # Build messages
        messages = [
            {"role": "system", "content": self._get_system_prompt(
                self._build_tools_description(),
                context.get('world_state', {}),
                context.get('facts', {})
            )},
            *context.get('history', [])
        ]

        # Add current user input
        messages.append({"role": "user", "content": text})

        # Call LLM
        try:
            response, parsed = self.llm.call_with_json_schema(
                messages,
                self.output_schema,
                max_fix_attempts=3
            )

            if parsed is None:
                parsed = {
                    "assistant_text": response.content,
                    "plan": [],
                    "tool_calls": [],
                    "memory_write": []
                }

            # Add session info
            parsed['session_id'] = session_id
            parsed['turn_id'] = turn_id

            # Publish response
            response_msg = String()
            response_msg.data = json.dumps(parsed)
            self.llm_response_pub.publish(response_msg)

            # Execute tool calls if any
            tool_calls = parsed.get('tool_calls', [])
            for tool_call in tool_calls:
                self._dispatch_tool_call(session_id, tool_call)

            # Handle memory writes
            memory_writes = parsed.get('memory_write', [])
            for mem_write in memory_writes:
                self._handle_memory_write(session_id, mem_write)

            self.get_logger().info(
                f'LLM response for session {session_id}: '
                f'{parsed.get("assistant_text", "")[:50]}...'
            )

        except Exception as e:
            self.get_logger().error(f'LLM call failed: {e}')
            error_response = {
                'session_id': session_id,
                'turn_id': turn_id,
                'assistant_text': f'Sorry, I encountered an error: {str(e)}',
                'plan': [],
                'tool_calls': [],
                'memory_write': []
            }
            error_msg = String()
            error_msg.data = json.dumps(error_response)
            self.llm_response_pub.publish(error_msg)

    def _build_context(self, session_id: str) -> dict:
        """Build context for LLM call."""
        context = {
            'history': [],
            'world_state': {},
            'facts': {}
        }

        # Try to get memory from service
        if self.memory_query_client.wait_for_service(timeout_sec=0.5):
            # Get recent history
            request = MemoryQuery.Request()
            request.session_id = session_id
            request.query_type = 'recent'
            request.limit = 10

            future = self.memory_query_client.call_async(request)
            rclpy.spin_until_future_complete(self, future, timeout_sec=1.0)

            if future.result() and future.result().success:
                try:
                    result = json.loads(future.result().result_json)
                    for turn in result.get('turns', []):
                        role = 'user' if turn.get('speaker') == 'user' else 'assistant'
                        context['history'].append({
                            'role': role,
                            'content': turn.get('text', '')
                        })
                    context['facts'] = result.get('facts', {})
                except json.JSONDecodeError:
                    pass

        return context

    def _dispatch_tool_call(self, session_id: str, tool_call: dict) -> None:
        """Dispatch a tool call to tool router."""
        tool_msg = String()
        tool_msg.data = json.dumps({
            'session_id': session_id,
            'tool_name': tool_call.get('tool', ''),
            'args': tool_call.get('args', {}),
            'call_id': tool_call.get('call_id', '')
        })
        self.tool_call_pub.publish(tool_msg)
        self.get_logger().debug(
            f'Dispatched tool call: {tool_call.get("tool", "")}'
        )

    def _handle_memory_write(self, session_id: str, mem_write: dict) -> None:
        """Handle memory write operation."""
        # Publish memory write event
        mem_msg = String()
        mem_msg.data = json.dumps({
            'session_id': session_id,
            'operation': mem_write.get('type', 'upsert'),
            'key': mem_write.get('key', ''),
            'value': mem_write.get('value', '')
        })

        # This will be handled by memory_node
        self.get_logger().info(
            f'Memory write: {mem_write.get("key", "")} = {mem_write.get("value", "")}'
        )


def main(args=None):
    rclpy.init(args=args)
    node = LLMOrchestratorNode()

    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, Exception):
        pass
    finally:
        try:
            node.destroy_node()
            if rclpy.ok():
                rclpy.shutdown()
        except Exception:
            pass


if __name__ == '__main__':
    main()
