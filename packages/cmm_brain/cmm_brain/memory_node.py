# Copyright 2026 ROS2 Brain Agent Team
# SPDX-License-Identifier: Apache-2.0

"""
Memory Node - Provides memory services to other nodes.

Responsibilities:
- Expose MemoryQuery service
- Handle memory write operations
- Session management
- Context building for LLM
"""

import json
import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup
from std_msgs.msg import String
from cmm_interfaces.srv import MemoryQuery
from cmm_interfaces.msg import ErrorInfo

from cmm_brain.memory import FileSystemMemoryStore, MemoryStore


class MemoryNode(Node):
    """Memory Service ROS2 Node."""

    def __init__(self):
        super().__init__('memory_node')

        # Declare parameters
        self.declare_parameter('memory_base_path', 'memory')
        self.declare_parameter('max_turns_context', 20)
        self.declare_parameter('summary_threshold', 50)

        # Get parameters
        self.memory_path = self.get_parameter('memory_base_path').value
        self.max_turns_context = self.get_parameter('max_turns_context').value
        self.summary_threshold = self.get_parameter('summary_threshold').value

        # Callback group
        self.callback_group = ReentrantCallbackGroup()

        # Initialize memory store
        self.memory = FileSystemMemoryStore(self.memory_path)

        # Service server
        self.memory_query_srv = self.create_service(
            MemoryQuery,
            '/memory/query',
            self.handle_memory_query,
            callback_group=self.callback_group
        )

        # Subscribers for memory operations
        self.memory_write_sub = self.create_subscription(
            String,
            '/memory/write',
            self.handle_memory_write,
            10,
            callback_group=self.callback_group
        )

        self.get_logger().info(
            f'Memory Node initialized with path: {self.memory_path}'
        )

    def handle_memory_query(
        self,
        request: MemoryQuery.Request,
        response: MemoryQuery.Response
    ) -> MemoryQuery.Response:
        """Handle memory query service."""
        try:
            result = self._process_query(
                session_id=request.session_id,
                query_type=request.query_type,
                limit=request.limit if request.limit > 0 else 100
            )

            response.success = True
            response.result_json = json.dumps(result, ensure_ascii=False)

        except Exception as e:
            self.get_logger().error(f'Memory query error: {e}')
            response.success = False
            response.error.code = 'QUERY_ERROR'
            response.error.message = str(e)
            response.result_json = '{}'

        return response

    def _process_query(
        self,
        session_id: str,
        query_type: str,
        limit: int
    ) -> dict:
        """Process memory query and return result."""
        result = {}

        if query_type == 'turns':
            turns = self.memory.get_all_turns(session_id)
            result['turns'] = [t.to_dict() for t in turns]

        elif query_type == 'recent':
            turns = self.memory.get_recent_turns(session_id, limit=limit)
            facts = self.memory.get_session_facts(session_id)
            global_facts = self.memory.get_global_facts()

            result['turns'] = [t.to_dict() for t in turns]
            result['facts'] = {**global_facts.facts, **facts.facts}

        elif query_type == 'events':
            events = self.memory.get_events(session_id, limit=limit)
            result['events'] = [e.to_dict() for e in events]

        elif query_type == 'summary':
            summary = self.memory.get_summary(session_id)
            if summary:
                result['summary'] = summary.to_dict()
            else:
                result['summary'] = None

        elif query_type == 'facts':
            session_facts = self.memory.get_session_facts(session_id)
            global_facts = self.memory.get_global_facts()
            result['facts'] = {
                'session': session_facts.facts,
                'global': global_facts.facts
            }

        elif query_type == 'full':
            # Full context for LLM
            turns = self.memory.get_recent_turns(session_id, limit=limit)
            summary = self.memory.get_summary(session_id)
            session_facts = self.memory.get_session_facts(session_id)
            global_facts = self.memory.get_global_facts()

            result['turns'] = [t.to_dict() for t in turns]
            result['summary'] = summary.to_dict() if summary else None
            result['facts'] = {**global_facts.facts, **session_facts.facts}

        else:
            raise ValueError(f'Unknown query type: {query_type}')

        return result

    def handle_memory_write(self, msg: String) -> None:
        """Handle memory write operation from topic."""
        try:
            data = json.loads(msg.data)
        except json.JSONDecodeError:
            self.get_logger().error(f'Invalid JSON in memory write: {msg.data[:100]}')
            return

        session_id = data.get('session_id', '')
        operation = data.get('operation', 'upsert')
        key = data.get('key', '')
        value = data.get('value')

        if not key:
            self.get_logger().error('Memory write missing key')
            return

        try:
            if operation == 'upsert':
                # Determine if session or global
                scope = data.get('scope', 'session')

                if scope == 'global':
                    self.memory.upsert_global_facts(key, value)
                    self.get_logger().info(f'Updated global fact: {key}')
                else:
                    if not session_id:
                        session_id = 'default'
                    self.memory.upsert_session_facts(session_id, key, value)
                    self.get_logger().info(f'Updated session fact: {key}')

            elif operation == 'delete':
                scope = data.get('scope', 'session')

                if scope == 'global':
                    deleted = self.memory.delete_global_fact(key)
                    self.get_logger().info(f'Deleted global fact: {key} ({deleted})')
                else:
                    if not session_id:
                        session_id = 'default'
                    deleted = self.memory.delete_session_fact(session_id, key)
                    self.get_logger().info(f'Deleted session fact: {key} ({deleted})')

            else:
                self.get_logger().error(f'Unknown memory operation: {operation}')

        except Exception as e:
            self.get_logger().error(f'Memory write error: {e}')

    def create_session(self, session_id: str) -> bool:
        """Create a new session."""
        try:
            if not self.memory.session_exists(session_id):
                self.memory.create_session(session_id)
                self.get_logger().info(f'Created session: {session_id}')
            return True
        except Exception as e:
            self.get_logger().error(f'Failed to create session: {e}')
            return False

    def list_sessions(self) -> list:
        """List all sessions."""
        return self.memory.list_sessions()

    def get_session_stats(self, session_id: str) -> dict:
        """Get statistics for a session."""
        if not self.memory.session_exists(session_id):
            return {}

        turns = self.memory.get_all_turns(session_id)
        events = self.memory.get_events(session_id)

        return {
            'session_id': session_id,
            'turn_count': len(turns),
            'event_count': len(events),
            'has_summary': self.memory.get_summary(session_id) is not None
        }


def main(args=None):
    rclpy.init(args=args)
    node = MemoryNode()

    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, Exception) as e:
        # Handle both KeyboardInterrupt and ExternalShutdownException
        if 'ExternalShutdownException' not in str(type(e)):
            pass  # Only log if it's not the expected shutdown
    finally:
        try:
            node.destroy_node()
            if rclpy.ok():
                rclpy.shutdown()
        except Exception:
            pass  # Ignore shutdown errors


if __name__ == '__main__':
    main()
