# Copyright 2026 ROS2 Brain Agent Team
# SPDX-License-Identifier: Apache-2.0

"""
Arm Primitives - Basic manipulation skills.

Provides:
- ArmMoveToPrimitive: Move arm to target pose
- ArmGraspPrimitive: Execute grasp
- ArmReleasePrimitive: Release object
"""

import asyncio
import json
from typing import Any, Callable, Dict, Optional

from .base_skill import PrimitiveSkill, SkillContext, SkillResult


class ArmMoveToPrimitive(PrimitiveSkill):
    """Move robot arm to a target pose using MoveIt2."""

    name = "arm.move_to"
    description = "Move arm to target pose"
    category = "manipulation"

    async def _execute_primitive(
        self,
        args: Dict[str, Any],
        context: SkillContext,
        feedback_callback: Optional[Callable[[float, str, str], None]] = None
    ) -> SkillResult:
        """Execute arm movement to target pose."""
        # Validate arguments
        error = self._validate_args(args, ['target_pose'])
        if error:
            return SkillResult(
                success=False,
                error_code='INVALID_ARGS',
                error_message=error
            )

        target_pose = args['target_pose']
        planning_group = args.get('planning_group', 'arm')

        self._report_progress(
            feedback_callback,
            0.0,
            'init',
            f'Starting arm movement to target pose'
        )

        try:
            # Try to use MoveIt2
            result = await self._call_moveit(
                target_pose,
                planning_group,
                context,
                feedback_callback
            )
            return result

        except Exception as e:
            # Simulate for testing
            if context.node.get_logger():
                context.node.get_logger().warning(
                    f'MoveIt2 not available, simulating arm movement: {e}'
                )

            return await self._simulate_arm_move(
                target_pose,
                context,
                feedback_callback
            )

    async def _call_moveit(
        self,
        target_pose: Dict[str, Any],
        planning_group: str,
        context: SkillContext,
        feedback_callback: Optional[Callable[[float, str, str], None]] = None
    ) -> SkillResult:
        """Call MoveIt2 to execute arm movement."""
        # In real implementation, this would use MoveIt2 Python API
        # For now, simulate the movement
        raise RuntimeError("MoveIt2 integration not implemented")

    async def _simulate_arm_move(
        self,
        target_pose: Dict[str, Any],
        context: SkillContext,
        feedback_callback: Optional[Callable[[float, str, str], None]] = None
    ) -> SkillResult:
        """Simulate arm movement for testing."""
        self._report_progress(
            feedback_callback,
            0.2,
            'planning',
            'Planning arm trajectory'
        )

        await asyncio.sleep(0.5)

        self._report_progress(
            feedback_callback,
            0.4,
            'moving',
            'Executing arm trajectory'
        )

        # Simulate movement time
        steps = 5
        for i in range(steps):
            progress = 0.4 + (i + 1) / steps * 0.5
            await asyncio.sleep(0.2)
            self._report_progress(
                feedback_callback,
                progress,
                f'step_{i}',
                f'Arm movement in progress... {int(progress * 100)}%'
            )

        # Update world state
        if hasattr(context.node, 'update_world_state'):
            context.node.update_world_state('arm_state', {'state': 'IDLE'})

        self._report_progress(
            feedback_callback,
            1.0,
            'complete',
            'Arm movement completed'
        )

        return SkillResult(
            success=True,
            data={
                'simulated': True,
                'final_pose': target_pose
            }
        )


class ArmGraspPrimitive(PrimitiveSkill):
    """Execute grasp action."""

    name = "arm.grasp"
    description = "Execute grasp action"
    category = "manipulation"

    async def _execute_primitive(
        self,
        args: Dict[str, Any],
        context: SkillContext,
        feedback_callback: Optional[Callable[[float, str, str], None]] = None
    ) -> SkillResult:
        """Execute grasp."""
        grasp_pose = args.get('grasp_pose', {})
        approach_distance = args.get('approach_distance', 0.1)

        self._report_progress(
            feedback_callback,
            0.0,
            'init',
            'Starting grasp action'
        )

        # Simulate grasp
        self._report_progress(
            feedback_callback,
            0.3,
            'approach',
            'Approaching object'
        )
        await asyncio.sleep(0.5)

        self._report_progress(
            feedback_callback,
            0.5,
            'grasp',
            'Closing gripper'
        )
        await asyncio.sleep(0.3)

        self._report_progress(
            feedback_callback,
            0.7,
            'lift',
            'Lifting object'
        )
        await asyncio.sleep(0.3)

        # Update world state
        if hasattr(context.node, 'update_world_state'):
            context.node.update_world_state('arm_state', {
                'state': 'HOLDING',
                'holding': True,
                'object_id': args.get('object_id', 'unknown')
            })

        self._report_progress(
            feedback_callback,
            1.0,
            'complete',
            'Grasp completed successfully'
        )

        return SkillResult(
            success=True,
            data={
                'simulated': True,
                'grasped': True
            }
        )


class ArmReleasePrimitive(PrimitiveSkill):
    """Release object from gripper."""

    name = "arm.release"
    description = "Release held object"
    category = "manipulation"

    async def _execute_primitive(
        self,
        args: Dict[str, Any],
        context: SkillContext,
        feedback_callback: Optional[Callable[[float, str, str], None]] = None
    ) -> SkillResult:
        """Execute release."""
        self._report_progress(
            feedback_callback,
            0.0,
            'init',
            'Starting release action'
        )

        self._report_progress(
            feedback_callback,
            0.5,
            'open',
            'Opening gripper'
        )
        await asyncio.sleep(0.3)

        # Update world state
        if hasattr(context.node, 'update_world_state'):
            context.node.update_world_state('arm_state', {
                'state': 'IDLE',
                'holding': False,
                'object_id': ''
            })

        self._report_progress(
            feedback_callback,
            1.0,
            'complete',
            'Release completed'
        )

        return SkillResult(
            success=True,
            data={
                'simulated': True,
                'released': True
            }
        )
