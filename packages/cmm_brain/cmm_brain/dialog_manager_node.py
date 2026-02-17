# Copyright 2026 ROS2 Brain Agent Team
# SPDX-License-Identifier: Apache-2.0

"""
Dialog Manager Node - Manages conversation sessions and publishes events.

Responsibilities:
- Session lifecycle management
- Turn recording
- Event publishing to /dialog/events
- Coordination between LLM orchestrator and memory
"""

import json
import os
import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup
from std_msgs.msg import String
from cmm_interfaces.msg import DialogEvent

from cmm_brain.memory import FileSystemMemoryStore, MemoryStore, Turn, Event


class DialogManagerNode(Node):
    """Dialog Manager ROS2 Node."""

    def __init__(self):
        super().__init__('dialog_manager_node')

        # Declare parameters
        self.declare_parameter('memory_base_path', 'memory')
        self.declare_parameter('default_session_id', 'default')

        # Get parameters
        self.memory_path = self.get_parameter('memory_base_path').value
        self.default_session_id = self.get_parameter('default_session_id').value

        # Initialize memory store
        self.memory = FileSystemMemoryStore(self.memory_path)

        # Callback group for concurrent execution
        self.callback_group = ReentrantCallbackGroup()

        # Publishers
        self.event_pub = self.create_publisher(
            DialogEvent,
            '/dialog/events',
            10
        )

        # Subscribers
        self.user_input_sub = self.create_subscription(
            String,
            '/dialog/user_input',
            self.handle_user_input,
            10,
            callback_group=self.callback_group
        )

        self.llm_response_sub = self.create_subscription(
            String,
            '/dialog/llm_response',
            self.handle_llm_response,
            10,
            callback_group=self.callback_group
        )

        # Publishers for downstream nodes
        self.process_input_pub = self.create_publisher(
            String,
            '/dialog/process_input',
            10
        )

        # Current session
        self.current_session_id = self.default_session_id

        # Ensure default session exists
        if not self.memory.session_exists(self.current_session_id):
            self.memory.create_session(self.current_session_id)

        self.get_logger().info(
            f'Dialog Manager initialized with memory path: {self.memory_path}'
        )

    def handle_user_input(self, msg: String) -> None:
        """Handle user input from /dialog/user_input topic."""
        try:
            data = json.loads(msg.data) if msg.data.startswith('{') else {
                'text': msg.data,
                'session_id': self.current_session_id
            }
        except json.JSONDecodeError:
            data = {
                'text': msg.data,
                'session_id': self.current_session_id
            }

        session_id = data.get('session_id', self.current_session_id)
        text = data.get('text', '')

        if not text:
            return

        # Ensure session exists
        if not self.memory.session_exists(session_id):
            self.memory.create_session(session_id)

        # Get next turn ID
        turn_id = self.memory.get_next_turn_id(session_id)

        # Create and save turn
        turn = Turn(
            turn_id=turn_id,
            ts=MemoryStore.get_timestamp(),
            speaker='user',
            text=text
        )
        self.memory.append_turn(session_id, turn)

        # Publish event
        self._publish_event(
            session_id=session_id,
            event_type='turn_start',
            source='user',
            payload={'turn_id': turn_id, 'text': text}
        )

        # Forward to processing
        process_msg = String()
        process_msg.data = json.dumps({
            'session_id': session_id,
            'turn_id': turn_id,
            'text': text
        })
        self.process_input_pub.publish(process_msg)

        self.get_logger().debug(f'Processed user input: {text[:50]}...')

    def handle_llm_response(self, msg: String) -> None:
        """Handle LLM response from /dialog/llm_response topic."""
        try:
            data = json.loads(msg.data)
        except json.JSONDecodeError:
            self.get_logger().error(f'Invalid JSON in LLM response: {msg.data[:100]}')
            return

        session_id = data.get('session_id', self.current_session_id)
        turn_id = data.get('turn_id', 0)
        response_text = data.get('assistant_text', '')

        if not response_text:
            return

        # Create and save turn
        turn = Turn(
            turn_id=turn_id + 1,  # Response is next turn
            ts=MemoryStore.get_timestamp(),
            speaker='assistant',
            text=response_text,
            metadata={
                'tool_calls': data.get('tool_calls', []),
                'plan': data.get('plan', []),
                'memory_write': data.get('memory_write', [])
            }
        )
        self.memory.append_turn(session_id, turn)

        # Publish event
        self._publish_event(
            session_id=session_id,
            event_type='turn_end',
            source='llm',
            payload={
                'turn_id': turn.turn_id,
                'text': response_text,
                'tool_calls': data.get('tool_calls', [])
            }
        )

        self.get_logger().debug(f'Processed LLM response: {response_text[:50]}...')

    def _publish_event(
        self,
        session_id: str,
        event_type: str,
        source: str,
        payload: dict,
        duration_ms: int = 0,
        success: bool = True,
        error_message: str = ''
    ) -> None:
        """Publish a dialog event."""
        from builtin_interfaces.msg import Time
        import time as pytime

        event = DialogEvent()
        event.header.stamp = self.get_clock().now().to_msg()
        event.event_id = MemoryStore.generate_event_id()
        event.session_id = session_id
        event.event_type = event_type
        event.source = source
        event.payload_json = json.dumps(payload)
        event.duration_ms = duration_ms
        event.success = success
        event.error_message = error_message

        self.event_pub.publish(event)

        # Also save to memory
        memory_event = Event(
            event_id=event.event_id,
            ts=MemoryStore.get_timestamp(),
            event_type=event_type,
            session_id=session_id,
            payload=payload,
            duration_ms=duration_ms,
            success=success,
            error_message=error_message
        )
        self.memory.append_event(session_id, memory_event)

    def set_session(self, session_id: str) -> bool:
        """Set the current session."""
        if not self.memory.session_exists(session_id):
            self.memory.create_session(session_id)
        self.current_session_id = session_id
        return True

    def get_session_history(self, session_id: str = None, limit: int = 20) -> list:
        """Get recent turns from a session."""
        sid = session_id or self.current_session_id
        turns = self.memory.get_recent_turns(sid, limit=limit)
        return [t.to_dict() for t in turns]


def main(args=None):
    rclpy.init(args=args)
    node = DialogManagerNode()

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
