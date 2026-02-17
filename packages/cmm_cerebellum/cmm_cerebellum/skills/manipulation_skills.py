# Copyright 2026 ROS2 Brain Agent Team
# SPDX-License-Identifier: Apache-2.0

"""
Manipulation Skills - Composite skills for object manipulation.

Provides:
- PickObjectSkill: Pick up an object
- DeliverObjectSkill: Deliver object to location
"""

import asyncio
from typing import Any, Callable, Dict, Optional

from .base_skill import CompositeSkill, SkillContext, SkillResult
from .nav_primitives import Nav2GotoPrimitive
from .arm_primitives import ArmMoveToPrimitive, ArmGraspPrimitive, ArmReleasePrimitive


class PickObjectSkill(CompositeSkill):
    """Composite skill to pick up an object."""

    name = "skill.pick_object"
    description = "Pick up an object"
    category = "manipulation"
    skill_type = "composite"

    def __init__(self):
        super().__init__()
        # Register primitives
        self.register_primitive('nav2.goto', Nav2GotoPrimitive())
        self.register_primitive('arm.move_to', ArmMoveToPrimitive())
        self.register_primitive('arm.grasp', ArmGraspPrimitive())

    async def _execute_composite(
        self,
        args: Dict[str, Any],
        context: SkillContext,
        feedback_callback: Optional[Callable[[float, str, str], None]] = None
    ) -> SkillResult:
        """Execute pick object skill."""
        object_id = args.get('object_id', '')
        object_type = args.get('object_type', 'unknown')
        object_pose = args.get('object_pose', {})  # If known

        total_steps = 4
        current_step = 0

        def step_progress(step: int, step_name: str) -> float:
            return (step + 0.5) / total_steps

        # Step 1: Navigate to object location (if object_pose provided)
        if object_pose:
            self._report_progress(
                feedback_callback,
                step_progress(current_step, 'navigate'),
                'navigate',
                f'Navigating to object location'
            )

            nav_result = await self.execute_step(
                'nav2.goto',
                {
                    'target_pose': {
                        'x': object_pose.get('x', 0),
                        'y': object_pose.get('y', 0),
                        'theta': object_pose.get('theta', 0)
                    }
                },
                context
            )

            if not nav_result.success:
                return SkillResult(
                    success=False,
                    error_code='NAV_FAILED',
                    error_message=f'Failed to navigate to object: {nav_result.error_message}',
                    executed_steps=self.executed_steps
                )

        current_step += 1

        # Step 2: Move arm to pre-grasp pose
        self._report_progress(
            feedback_callback,
            step_progress(current_step, 'pre_grasp'),
            'pre_grasp',
            'Moving arm to pre-grasp position'
        )

        pre_grasp_pose = args.get('pre_grasp_pose', object_pose)
        if pre_grasp_pose:
            arm_result = await self.execute_step(
                'arm.move_to',
                {'target_pose': pre_grasp_pose},
                context
            )

            if not arm_result.success:
                return SkillResult(
                    success=False,
                    error_code='ARM_MOVE_FAILED',
                    error_message=f'Failed to move arm: {arm_result.error_message}',
                    executed_steps=self.executed_steps
                )

        current_step += 1

        # Step 3: Execute grasp
        self._report_progress(
            feedback_callback,
            step_progress(current_step, 'grasp'),
            'grasp',
            f'Grasping {object_type}'
        )

        grasp_result = await self.execute_step(
            'arm.grasp',
            {
                'grasp_pose': object_pose,
                'object_id': object_id
            },
            context
        )

        if not grasp_result.success:
            return SkillResult(
                success=False,
                error_code='GRASP_FAILED',
                error_message=f'Failed to grasp object: {grasp_result.error_message}',
                executed_steps=self.executed_steps
            )

        current_step += 1

        # Step 4: Retract arm
        self._report_progress(
            feedback_callback,
            step_progress(current_step, 'retract'),
            'retract',
            'Retracting arm'
        )

        retract_pose = args.get('retract_pose', {})
        if retract_pose:
            await self.execute_step(
                'arm.move_to',
                {'target_pose': retract_pose},
                context
            )

        self._report_progress(
            feedback_callback,
            1.0,
            'complete',
            f'Successfully picked up {object_type}'
        )

        return SkillResult(
            success=True,
            data={
                'object_id': object_id,
                'object_type': object_type,
                'picked': True
            },
            executed_steps=self.executed_steps
        )


class DeliverObjectSkill(CompositeSkill):
    """Composite skill to deliver an object to a location."""

    name = "skill.deliver_object"
    description = "Deliver object to target location"
    category = "manipulation"
    skill_type = "composite"

    def __init__(self):
        super().__init__()
        self.register_primitive('nav2.goto', Nav2GotoPrimitive())
        self.register_primitive('arm.move_to', ArmMoveToPrimitive())
        self.register_primitive('arm.release', ArmReleasePrimitive())

    async def _execute_composite(
        self,
        args: Dict[str, Any],
        context: SkillContext,
        feedback_callback: Optional[Callable[[float, str, str], None]] = None
    ) -> SkillResult:
        """Execute deliver object skill."""
        target_location = args.get('target_location', {})
        object_id = args.get('object_id', '')

        total_steps = 3
        current_step = 0

        # Step 1: Navigate to target location
        self._report_progress(
            feedback_callback,
            0.1,
            'navigate',
            'Navigating to delivery location'
        )

        nav_result = await self.execute_step(
            'nav2.goto',
            {'target_pose': target_location},
            context
        )

        if not nav_result.success:
            return SkillResult(
                success=False,
                error_code='NAV_FAILED',
                error_message=f'Failed to navigate to delivery location: {nav_result.error_message}',
                executed_steps=self.executed_steps
            )

        current_step += 1

        # Step 2: Move arm to delivery pose
        self._report_progress(
            feedback_callback,
            0.5,
            'position',
            'Positioning arm for delivery'
        )

        delivery_pose = args.get('delivery_pose', {})
        if delivery_pose:
            arm_result = await self.execute_step(
                'arm.move_to',
                {'target_pose': delivery_pose},
                context
            )

            if not arm_result.success:
                return SkillResult(
                    success=False,
                    error_code='ARM_MOVE_FAILED',
                    error_message=f'Failed to position arm: {arm_result.error_message}',
                    executed_steps=self.executed_steps
                )

        current_step += 1

        # Step 3: Release object
        self._report_progress(
            feedback_callback,
            0.8,
            'release',
            'Releasing object'
        )

        release_result = await self.execute_step(
            'arm.release',
            {},
            context
        )

        if not release_result.success:
            return SkillResult(
                success=False,
                error_code='RELEASE_FAILED',
                error_message=f'Failed to release object: {release_result.error_message}',
                executed_steps=self.executed_steps
            )

        self._report_progress(
            feedback_callback,
            1.0,
            'complete',
            'Object delivered successfully'
        )

        return SkillResult(
            success=True,
            data={
                'object_id': object_id,
                'delivered': True,
                'location': target_location
            },
            executed_steps=self.executed_steps
        )
