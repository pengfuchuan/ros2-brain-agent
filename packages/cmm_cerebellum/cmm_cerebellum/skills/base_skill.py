# Copyright 2026 ROS2 Brain Agent Team
# SPDX-License-Identifier: Apache-2.0

"""
Base Skill - Abstract base class for all skills.

Provides:
- SkillContext: Execution context
- SkillResult: Execution result
- BaseSkill: Abstract base class
"""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class SkillContext:
    """Context for skill execution."""
    node: Any  # ROS2 node reference
    session_id: str
    dry_run: bool = False
    timeout_sec: float = 120.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SkillResult:
    """Result of skill execution."""
    success: bool
    data: Dict[str, Any] = field(default_factory=dict)
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    duration_ms: int = 0
    executed_steps: List[str] = field(default_factory=list)


class BaseSkill(ABC):
    """Abstract base class for skills."""

    # Skill metadata
    name: str = "base_skill"
    description: str = "Base skill class"
    category: str = "general"
    skill_type: str = "primitive"  # primitive or composite

    def __init__(self):
        self.executed_steps: List[str] = []

    @abstractmethod
    async def execute(
        self,
        args: Dict[str, Any],
        context: SkillContext,
        feedback_callback: Optional[Callable[[float, str, str], None]] = None
    ) -> SkillResult:
        """
        Execute the skill.

        Args:
            args: Skill arguments
            context: Execution context
            feedback_callback: Optional callback for progress updates

        Returns:
            SkillResult with execution outcome
        """
        pass

    def execute_sync(
        self,
        args: Dict[str, Any],
        context: SkillContext
    ) -> Dict[str, Any]:
        """
        Synchronous wrapper for skill execution.

        Args:
            args: Skill arguments
            context: Execution context

        Returns:
            Dict with execution result
        """
        import asyncio

        try:
            # Create event loop if needed
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            result = loop.run_until_complete(self.execute(args, context))
            return {
                'success': result.success,
                'data': result.data,
                'error_code': result.error_code,
                'error_message': result.error_message,
                'duration_ms': result.duration_ms,
                'executed_steps': result.executed_steps
            }

        except Exception as e:
            return {
                'success': False,
                'error_code': 'SYNC_EXECUTION_ERROR',
                'error_message': str(e),
                'executed_steps': self.executed_steps
            }

    def _report_progress(
        self,
        callback: Optional[Callable[[float, str, str], None]],
        progress: float,
        step: str,
        message: str
    ) -> None:
        """Report progress if callback is available."""
        if callback:
            callback(progress, step, message)
        self.executed_steps.append(step)

    def _validate_args(
        self,
        args: Dict[str, Any],
        required: List[str]
    ) -> Optional[str]:
        """
        Validate required arguments.

        Args:
            args: Arguments to validate
            required: List of required argument names

        Returns:
            Error message if validation fails, None otherwise
        """
        for arg in required:
            if arg not in args:
                return f"Missing required argument: {arg}"
        return None


class PrimitiveSkill(BaseSkill):
    """Base class for primitive skills."""

    skill_type = "primitive"

    async def execute(
        self,
        args: Dict[str, Any],
        context: SkillContext,
        feedback_callback: Optional[Callable[[float, str, str], None]] = None
    ) -> SkillResult:
        """Execute primitive skill."""
        start_time = time.time()

        if context.dry_run:
            return self._dry_run_result(args)

        result = await self._execute_primitive(args, context, feedback_callback)
        result.duration_ms = int((time.time() - start_time) * 1000)
        result.executed_steps = self.executed_steps

        return result

    @abstractmethod
    async def _execute_primitive(
        self,
        args: Dict[str, Any],
        context: SkillContext,
        feedback_callback: Optional[Callable[[float, str, str], None]] = None
    ) -> SkillResult:
        """Implement primitive execution."""
        pass

    def _dry_run_result(self, args: Dict[str, Any]) -> SkillResult:
        """Return result for dry run mode."""
        return SkillResult(
            success=True,
            data={
                'dry_run': True,
                'message': f'Dry run: would execute {self.name}',
                'args': args
            },
            executed_steps=[f'dry_run:{self.name}']
        )


class CompositeSkill(BaseSkill):
    """Base class for composite skills."""

    skill_type = "composite"

    def __init__(self):
        super().__init__()
        self.primitives: Dict[str, PrimitiveSkill] = {}

    def register_primitive(self, name: str, skill: PrimitiveSkill) -> None:
        """Register a primitive skill for use in this composite."""
        self.primitives[name] = skill

    async def execute(
        self,
        args: Dict[str, Any],
        context: SkillContext,
        feedback_callback: Optional[Callable[[float, str, str], None]] = None
    ) -> SkillResult:
        """Execute composite skill."""
        start_time = time.time()

        if context.dry_run:
            return self._dry_run_result(args)

        result = await self._execute_composite(args, context, feedback_callback)
        result.duration_ms = int((time.time() - start_time) * 1000)
        result.executed_steps = self.executed_steps

        return result

    @abstractmethod
    async def _execute_composite(
        self,
        args: Dict[str, Any],
        context: SkillContext,
        feedback_callback: Optional[Callable[[float, str, str], None]] = None
    ) -> SkillResult:
        """Implement composite execution."""
        pass

    async def execute_step(
        self,
        primitive_name: str,
        args: Dict[str, Any],
        context: SkillContext,
        feedback_callback: Optional[Callable[[float, str, str], None]] = None
    ) -> SkillResult:
        """Execute a primitive step."""
        if primitive_name not in self.primitives:
            return SkillResult(
                success=False,
                error_code='PRIMITIVE_NOT_FOUND',
                error_message=f'Primitive not found: {primitive_name}'
            )

        primitive = self.primitives[primitive_name]
        return await primitive.execute(args, context, feedback_callback)
