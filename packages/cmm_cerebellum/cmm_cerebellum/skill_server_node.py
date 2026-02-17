# Copyright 2026 ROS2 Brain Agent Team
# SPDX-License-Identifier: Apache-2.0

"""
Skill Server Node - Executes skills and primitives.

Responsibilities:
- Receive skill execution requests
- Execute primitive and composite skills
- Provide feedback during execution
- Handle errors and recovery
- Report results to tool_router
"""

import json
import rclpy
from rclpy.node import Node
from rclpy.action import ActionServer
from rclpy.callback_groups import ReentrantCallbackGroup
from std_msgs.msg import String
from cmm_interfaces.action import SkillExecute
from cmm_interfaces.msg import ErrorInfo

from .skills.base_skill import SkillContext, SkillResult
from .skills.nav_primitives import Nav2GotoPrimitive
from .skills.arm_primitives import ArmMoveToPrimitive
from .skills.manipulation_skills import PickObjectSkill


class SkillServerNode(Node):
    """Skill Server ROS2 Node."""

    def __init__(self):
        super().__init__('skill_server_node')

        # Declare parameters
        self.declare_parameter('default_timeout_sec', 120.0)
        self.declare_parameter('max_retry_attempts', 3)

        # Get parameters
        self.default_timeout = self.get_parameter('default_timeout_sec').value
        self.max_retry = self.get_parameter('max_retry_attempts').value

        # Callback group
        self.callback_group = ReentrantCallbackGroup()

        # Initialize skill registry
        self._init_skill_registry()

        # Action server for skill execution
        self.skill_action_server = ActionServer(
            self,
            SkillExecute,
            '/skill/execute',
            self.execute_skill_callback,
            callback_group=self.callback_group
        )

        # Subscribers
        self.skill_request_sub = self.create_subscription(
            String,
            '/skill/execute',
            self.handle_skill_request,
            10,
            callback_group=self.callback_group
        )

        # Publishers
        self.skill_result_pub = self.create_publisher(
            String,
            '/skill/result',
            10
        )

        self.world_state_update_pub = self.create_publisher(
            String,
            '/world_state/update',
            10
        )

        self.get_logger().info(
            f'Skill Server initialized with {len(self.skill_registry)} skills'
        )

    def _init_skill_registry(self) -> None:
        """Initialize skill registry with available skills."""
        self.skill_registry = {}

        # Register primitives
        self._register_skill('nav2.goto', Nav2GotoPrimitive)
        self._register_skill('arm.move_to', ArmMoveToPrimitive)

        # Register composite skills
        self._register_skill('skill.pick_object', PickObjectSkill)

    def _register_skill(self, name: str, skill_class) -> None:
        """Register a skill class."""
        self.skill_registry[name] = skill_class
        self.get_logger().debug(f'Registered skill: {name}')

    def handle_skill_request(self, msg: String) -> None:
        """Handle async skill request from topic."""
        try:
            data = json.loads(msg.data)
        except json.JSONDecodeError:
            self._publish_error('Invalid JSON in skill request')
            return

        skill_name = data.get('skill_name', '')
        args = data.get('args', {})
        session_id = data.get('session_id', '')
        skill_type = data.get('skill_type', 'primitive')

        result = self._execute_skill_sync(
            skill_name=skill_name,
            args=args,
            session_id=session_id,
            dry_run=False
        )

        # Publish result
        result_msg = String()
        result_msg.data = json.dumps({
            'skill_name': skill_name,
            'session_id': session_id,
            **result
        })
        self.skill_result_pub.publish(result_msg)

    async def execute_skill_callback(self, goal_handle) -> None:
        """Handle skill execution action."""
        goal = goal_handle.request

        self.get_logger().info(
            f'Executing skill: {goal.skill_name} (dry_run={goal.dry_run})'
        )

        # Create context
        context = SkillContext(
            node=self,
            session_id=goal.session_id,
            dry_run=goal.dry_run,
            timeout_sec=goal.timeout_sec if goal.timeout_sec > 0 else self.default_timeout
        )

        # Get skill class
        if goal.skill_name not in self.skill_registry:
            goal_handle.abort()
            result = SkillExecute.Result()
            result.success = False
            result.error_code = 'SKILL_NOT_FOUND'
            result.error_message = f'Skill not found: {goal.skill_name}'
            return result

        skill_class = self.skill_registry[goal.skill_name]
        skill = skill_class()

        try:
            # Execute skill with feedback
            result = await skill.execute(
                args=json.loads(goal.args_json) if goal.args_json else {},
                context=context,
                feedback_callback=lambda p, s, m: self._send_feedback(
                    goal_handle, p, s, m
                )
            )

            if result.success:
                goal_handle.succeed()
            else:
                goal_handle.abort()

            # Build result
            action_result = SkillExecute.Result()
            action_result.success = result.success
            action_result.result_json = json.dumps(result.data)
            action_result.error_code = result.error_code or ''
            action_result.error_message = result.error_message or ''
            action_result.duration_ms = result.duration_ms
            action_result.executed_steps = result.executed_steps

            return action_result

        except Exception as e:
            self.get_logger().error(f'Skill execution error: {e}')
            goal_handle.abort()

            action_result = SkillExecute.Result()
            action_result.success = False
            action_result.error_code = 'EXECUTION_ERROR'
            action_result.error_message = str(e)

            return action_result

    def _send_feedback(self, goal_handle, progress: float, step: str, message: str) -> None:
        """Send feedback during skill execution."""
        feedback = SkillExecute.Feedback()
        feedback.progress = progress
        feedback.current_step = step
        feedback.message = message
        goal_handle.publish_feedback(feedback)

    def _execute_skill_sync(
        self,
        skill_name: str,
        args: dict,
        session_id: str,
        dry_run: bool
    ) -> dict:
        """Execute skill synchronously (for topic-based requests)."""
        import time
        start_time = time.time()

        if skill_name not in self.skill_registry:
            return {
                'success': False,
                'error_code': 'SKILL_NOT_FOUND',
                'error_message': f'Skill not found: {skill_name}',
                'duration_ms': 0
            }

        skill_class = self.skill_registry[skill_name]
        skill = skill_class()

        context = SkillContext(
            node=self,
            session_id=session_id,
            dry_run=dry_run,
            timeout_sec=self.default_timeout
        )

        try:
            # Run skill (simplified for sync execution)
            result = skill.execute_sync(args, context)
            result['duration_ms'] = int((time.time() - start_time) * 1000)
            return result

        except Exception as e:
            return {
                'success': False,
                'error_code': 'EXECUTION_ERROR',
                'error_message': str(e),
                'duration_ms': int((time.time() - start_time) * 1000)
            }

    def _publish_error(self, message: str) -> None:
        """Publish error result."""
        result_msg = String()
        result_msg.data = json.dumps({
            'success': False,
            'error_code': 'INVALID_REQUEST',
            'error_message': message
        })
        self.skill_result_pub.publish(result_msg)

    def update_world_state(self, update_type: str, payload: dict) -> None:
        """Update world state."""
        msg = String()
        msg.data = json.dumps({
            'type': update_type,
            'payload': payload
        })
        self.world_state_update_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = SkillServerNode()

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
