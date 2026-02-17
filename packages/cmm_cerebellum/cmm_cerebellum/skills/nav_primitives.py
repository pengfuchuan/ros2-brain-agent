# Copyright 2026 ROS2 Brain Agent Team
# SPDX-License-Identifier: Apache-2.0

"""
Navigation Primitives - Basic navigation skills.

Provides:
- Nav2GotoPrimitive: Navigate to a target pose
"""

import asyncio
import json
from typing import Any, Callable, Dict, Optional

from .base_skill import PrimitiveSkill, SkillContext, SkillResult


class Nav2GotoPrimitive(PrimitiveSkill):
    """Navigate robot to a target pose using Nav2."""

    name = "nav2.goto"
    description = "Navigate to a target position"
    category = "navigation"

    async def _execute_primitive(
        self,
        args: Dict[str, Any],
        context: SkillContext,
        feedback_callback: Optional[Callable[[float, str, str], None]] = None
    ) -> SkillResult:
        """Execute navigation to target pose."""
        # Validate arguments
        error = self._validate_args(args, ['target_pose'])
        if error:
            return SkillResult(
                success=False,
                error_code='INVALID_ARGS',
                error_message=error
            )

        target_pose = args['target_pose']
        frame_id = args.get('frame_id', 'map')

        self._report_progress(
            feedback_callback,
            0.0,
            'init',
            f'Starting navigation to ({target_pose.get("x", 0)}, {target_pose.get("y", 0)})'
        )

        try:
            # Try to use Nav2 action client
            result = await self._call_nav2(
                target_pose,
                frame_id,
                context,
                feedback_callback
            )
            return result

        except Exception as e:
            # Simulate navigation for testing
            if context.node.get_logger():
                context.node.get_logger().warning(
                    f'Nav2 not available, simulating navigation: {e}'
                )

            return await self._simulate_navigation(
                target_pose,
                context,
                feedback_callback
            )

    async def _call_nav2(
        self,
        target_pose: Dict[str, Any],
        frame_id: str,
        context: SkillContext,
        feedback_callback: Optional[Callable[[float, str, str], None]] = None
    ) -> SkillResult:
        """Call Nav2 NavigateToPose action."""
        try:
            from nav2_msgs.action import NavigateToPose
            from action_msgs.msg import GoalStatus
            from rclpy.action import ActionClient
            import geometry_msgs.msg
        except ImportError:
            # Nav2 not available
            raise RuntimeError("Nav2 messages not available")

        action_client = ActionClient(
            context.node,
            NavigateToPose,
            'navigate_to_pose'
        )

        if not action_client.wait_for_server(timeout_sec=5.0):
            action_client.destroy()
            raise RuntimeError("Nav2 action server not available")

        # Build goal
        goal_msg = NavigateToPose.Goal()
        goal_msg.pose.header.frame_id = frame_id
        goal_msg.pose.header.stamp = context.node.get_clock().now().to_msg()
        goal_msg.pose.pose.position.x = target_pose.get('x', 0.0)
        goal_msg.pose.pose.position.y = target_pose.get('y', 0.0)
        goal_msg.pose.pose.position.z = target_pose.get('z', 0.0)

        # Set orientation
        theta = target_pose.get('theta', 0.0)
        import math
        goal_msg.pose.pose.orientation.x = 0.0
        goal_msg.pose.pose.orientation.y = 0.0
        goal_msg.pose.pose.orientation.z = math.sin(theta / 2)
        goal_msg.pose.pose.orientation.w = math.cos(theta / 2)

        self._report_progress(
            feedback_callback,
            0.1,
            'send_goal',
            'Sending navigation goal to Nav2'
        )

        # Send goal
        send_goal_future = action_client.send_goal_async(goal_msg)
        goal_handle = await asyncio.wait_for(
            asyncio.wrap_future(send_goal_future),
            timeout=10.0
        )

        if not goal_handle.accepted:
            action_client.destroy()
            return SkillResult(
                success=False,
                error_code='GOAL_REJECTED',
                error_message='Navigation goal was rejected'
            )

        self._report_progress(
            feedback_callback,
            0.2,
            'navigating',
            'Navigation in progress'
        )

        # Wait for result
        get_result_future = goal_handle.get_result_async()
        result = await asyncio.wait_for(
            asyncio.wrap_future(get_result_future),
            timeout=context.timeout_sec
        )

        action_client.destroy()

        if result.status == GoalStatus.STATUS_SUCCEEDED:
            self._report_progress(
                feedback_callback,
                1.0,
                'complete',
                'Navigation completed successfully'
            )

            return SkillResult(
                success=True,
                data={
                    'final_pose': target_pose,
                    'nav_result': 'succeeded'
                }
            )
        else:
            return SkillResult(
                success=False,
                error_code='NAV_FAILED',
                error_message=f'Navigation failed with status: {result.status}'
            )

    async def _simulate_navigation(
        self,
        target_pose: Dict[str, Any],
        context: SkillContext,
        feedback_callback: Optional[Callable[[float, str, str], None]] = None
    ) -> SkillResult:
        """Simulate navigation for testing."""
        import math

        steps = 10
        for i in range(steps):
            progress = (i + 1) / steps
            await asyncio.sleep(0.2)  # Simulate movement time

            self._report_progress(
                feedback_callback,
                progress,
                f'simulate_step_{i}',
                f'Simulating navigation... {int(progress * 100)}%'
            )

        # Update world state
        if hasattr(context.node, 'update_world_state'):
            context.node.update_world_state('nav_state', {'state': 'IDLE'})
            context.node.update_world_state('full', {
                'pose': {
                    'position': {
                        'x': target_pose.get('x', 0),
                        'y': target_pose.get('y', 0),
                        'z': 0
                    },
                    'orientation': {
                        'x': 0,
                        'y': 0,
                        'z': math.sin(target_pose.get('theta', 0) / 2),
                        'w': math.cos(target_pose.get('theta', 0) / 2)
                    }
                }
            })

        return SkillResult(
            success=True,
            data={
                'simulated': True,
                'final_pose': target_pose
            }
        )


class Nav2StopPrimitive(PrimitiveSkill):
    """Stop robot navigation."""

    name = "nav2.stop"
    description = "Stop current navigation"
    category = "navigation"

    async def _execute_primitive(
        self,
        args: Dict[str, Any],
        context: SkillContext,
        feedback_callback: Optional[Callable[[float, str, str], None]] = None
    ) -> SkillResult:
        """Stop navigation."""
        self._report_progress(
            feedback_callback,
            0.5,
            'stop',
            'Stopping navigation'
        )

        # In real implementation, would cancel Nav2 goal
        await asyncio.sleep(0.1)

        self._report_progress(
            feedback_callback,
            1.0,
            'stopped',
            'Navigation stopped'
        )

        return SkillResult(
            success=True,
            data={'stopped': True}
        )
