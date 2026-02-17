# Copyright 2026 ROS2 Brain Agent Team
# SPDX-License-Identifier: Apache-2.0

"""
Tool Router Node - Routes tool calls with governance.

Responsibilities:
- Tool whitelist enforcement
- Parameter schema validation
- Permission level control
- Rate limiting
- Audit logging
- Dry-run mode support
- Dispatch to Cerebellum skills
"""

import json
import os
import time
import yaml
import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup
from std_msgs.msg import String
from cmm_interfaces.srv import ToolExecute
from cmm_interfaces.msg import DialogEvent, ErrorInfo


class RateLimiter:
    """Simple rate limiter for tool calls."""

    def __init__(self, max_per_minute: int = 60):
        self.max_per_minute = max_per_minute
        self.calls = []

    def allow(self) -> bool:
        """Check if call is allowed."""
        now = time.time()
        # Remove calls older than 1 minute
        self.calls = [c for c in self.calls if now - c < 60]

        if len(self.calls) >= self.max_per_minute:
            return False

        self.calls.append(now)
        return True

    def wait_time(self) -> float:
        """Get time to wait before next call is allowed."""
        if not self.calls:
            return 0.0

        now = time.time()
        oldest = min(self.calls)
        return max(0.0, 60 - (now - oldest))


class PermissionLevel:
    """Permission levels for tools."""
    SAFE = 'safe'
    CONFIRM = 'confirm'
    DANGEROUS = 'dangerous'


class ToolRouterNode(Node):
    """Tool Router ROS2 Node."""

    def __init__(self):
        super().__init__('tool_router_node')

        # Declare parameters
        self.declare_parameter('config_path', 'configs')
        self.declare_parameter('tools_config', 'tools.yaml')
        self.declare_parameter('audit_enabled', True)
        self.declare_parameter('dry_run_default', False)
        self.declare_parameter('default_timeout_sec', 30.0)

        # Get parameters
        self.config_path = self.get_parameter('config_path').value
        self.tools_config = self.get_parameter('tools_config').value
        self.audit_enabled = self.get_parameter('audit_enabled').value
        self.dry_run_default = self.get_parameter('dry_run_default').value
        self.default_timeout = self.get_parameter('default_timeout_sec').value

        # Callback group
        self.callback_group = ReentrantCallbackGroup()

        # Load tool configurations
        self.tools = self._load_tools_config()

        # Initialize rate limiters per tool
        self.rate_limiters = {}
        self._init_rate_limiters()

        # Pending confirmations (for confirm-level tools)
        self.pending_confirmations = {}

        # Publishers
        self.event_pub = self.create_publisher(
            DialogEvent,
            '/dialog/events',
            10
        )

        self.skill_call_pub = self.create_publisher(
            String,
            '/skill/execute',
            10
        )

        self.result_pub = self.create_publisher(
            String,
            '/tool/result',
            10
        )

        # Subscribers
        self.tool_call_sub = self.create_subscription(
            String,
            '/tool/execute',
            self.handle_tool_call,
            10,
            callback_group=self.callback_group
        )

        self.confirmation_sub = self.create_subscription(
            String,
            '/tool/confirm',
            self.handle_confirmation,
            10,
            callback_group=self.callback_group
        )

        # Service server
        self.tool_execute_srv = self.create_service(
            ToolExecute,
            '/tool/execute_sync',
            self.handle_tool_execute_service,
            callback_group=self.callback_group
        )

        self.get_logger().info(
            f'Tool Router initialized with {len(self.tools)} tools'
        )

    def _load_tools_config(self) -> dict:
        """Load tool configurations from YAML."""
        path = os.path.join(self.config_path, self.tools_config)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f) or {}
                return config.get('tools', {})
        except FileNotFoundError:
            self.get_logger().warning(f'Tools config not found: {path}')
            return {}
        except yaml.YAMLError as e:
            self.get_logger().error(f'Error parsing tools config: {e}')
            return {}

    def _init_rate_limiters(self) -> None:
        """Initialize rate limiters for each tool."""
        for tool_name, tool_config in self.tools.items():
            rate_limit = tool_config.get('rate_limit', {})
            max_per_minute = rate_limit.get('max_per_minute', 60)
            self.rate_limiters[tool_name] = RateLimiter(max_per_minute)

    def handle_tool_call(self, msg: String) -> None:
        """Handle async tool call from topic."""
        try:
            data = json.loads(msg.data)
        except json.JSONDecodeError:
            self._publish_error('Invalid JSON in tool call')
            return

        result = self._execute_tool(
            tool_name=data.get('tool_name', ''),
            args=data.get('args', {}),
            session_id=data.get('session_id', ''),
            dry_run=data.get('dry_run', self.dry_run_default),
            call_id=data.get('call_id', '')
        )

        # Publish result
        result_msg = String()
        result_msg.data = json.dumps(result)
        self.result_pub.publish(result_msg)

    def handle_tool_execute_service(
        self,
        request: ToolExecute.Request,
        response: ToolExecute.Response
    ) -> ToolExecute.Response:
        """Handle synchronous tool execute service."""
        result = self._execute_tool(
            tool_name=request.tool_name,
            args=json.loads(request.args_json) if request.args_json else {},
            session_id=request.session_id,
            dry_run=request.dry_run
        )

        response.success = result.get('success', False)
        response.result_json = json.dumps(result.get('result', {}))

        if not result.get('success', False):
            response.error.code = result.get('error_code', 'UNKNOWN_ERROR')
            response.error.message = result.get('error_message', 'Unknown error')

        response.duration_ms = result.get('duration_ms', 0)

        return response

    def handle_confirmation(self, msg: String) -> None:
        """Handle confirmation response for confirm-level tools."""
        try:
            data = json.loads(msg.data)
        except json.JSONDecodeError:
            return

        call_id = data.get('call_id', '')
        confirmed = data.get('confirmed', False)

        if call_id in self.pending_confirmations:
            pending = self.pending_confirmations.pop(call_id)

            if confirmed:
                # Execute the tool
                result = self._execute_tool_internal(
                    tool_name=pending['tool_name'],
                    args=pending['args'],
                    session_id=pending['session_id'],
                    dry_run=pending.get('dry_run', False)
                )
            else:
                result = {
                    'success': False,
                    'error_code': 'USER_DENIED',
                    'error_message': 'User denied the operation'
                }

            # Publish result
            result_msg = String()
            result_msg.data = json.dumps(result)
            self.result_pub.publish(result_msg)

    def _execute_tool(
        self,
        tool_name: str,
        args: dict,
        session_id: str,
        dry_run: bool,
        call_id: str = ''
    ) -> dict:
        """Execute a tool with full governance checks."""
        start_time = time.time()

        # Check if tool exists
        if tool_name not in self.tools:
            return {
                'success': False,
                'error_code': 'TOOL_NOT_FOUND',
                'error_message': f'Tool not found: {tool_name}'
            }

        tool_config = self.tools[tool_name]

        # Check permission level
        permission = tool_config.get('permission_level', PermissionLevel.SAFE)

        if permission == PermissionLevel.CONFIRM:
            # Need user confirmation
            if not call_id:
                import uuid
                call_id = str(uuid.uuid4())

            self.pending_confirmations[call_id] = {
                'tool_name': tool_name,
                'args': args,
                'session_id': session_id,
                'dry_run': dry_run
            }

            return {
                'success': False,
                'requires_confirmation': True,
                'call_id': call_id,
                'message': f'Tool {tool_name} requires confirmation'
            }

        if permission == PermissionLevel.DANGEROUS:
            return {
                'success': False,
                'error_code': 'DANGEROUS_TOOL',
                'error_message': f'Tool {tool_name} is marked dangerous and blocked'
            }

        # Check rate limit
        if tool_name in self.rate_limiters:
            if not self.rate_limiters[tool_name].allow():
                return {
                    'success': False,
                    'error_code': 'RATE_LIMITED',
                    'error_message': f'Rate limit exceeded for {tool_name}'
                }

        # Validate args against schema
        schema = tool_config.get('json_schema', {})
        if schema:
            validation_errors = self._validate_args(args, schema)
            if validation_errors:
                return {
                    'success': False,
                    'error_code': 'INVALID_ARGS',
                    'error_message': f'Invalid arguments: {validation_errors}'
                }

        # Execute the tool
        result = self._execute_tool_internal(
            tool_name=tool_name,
            args=args,
            session_id=session_id,
            dry_run=dry_run
        )

        # Add duration
        result['duration_ms'] = int((time.time() - start_time) * 1000)

        # Audit log
        if self.audit_enabled:
            self._audit_log(
                session_id=session_id,
                tool_name=tool_name,
                args=args,
                result=result,
                dry_run=dry_run
            )

        return result

    def _execute_tool_internal(
        self,
        tool_name: str,
        args: dict,
        session_id: str,
        dry_run: bool
    ) -> dict:
        """Internal tool execution - dispatches to Cerebellum."""
        tool_config = self.tools[tool_name]
        tool_type = tool_config.get('type', 'primitive')

        if dry_run:
            return {
                'success': True,
                'dry_run': True,
                'message': f'Dry run: would execute {tool_name}',
                'args': args
            }

        # Dispatch to skill executor
        skill_msg = String()
        skill_msg.data = json.dumps({
            'skill_name': tool_name,
            'args': args,
            'session_id': session_id,
            'skill_type': tool_type
        })
        self.skill_call_pub.publish(skill_msg)

        # For now, return success (actual execution is async)
        # In production, this would wait for skill result
        return {
            'success': True,
            'message': f'Dispatched {tool_name} to skill executor',
            'args': args
        }

    def _validate_args(self, args: dict, schema: dict) -> list:
        """Validate arguments against JSON schema."""
        errors = []

        required = schema.get('required', [])
        properties = schema.get('properties', {})

        # Check required fields
        for field in required:
            if field not in args:
                errors.append(f'Missing required field: {field}')

        # Check field types (basic validation)
        for key, value in args.items():
            if key in properties:
                prop_schema = properties[key]
                expected_type = prop_schema.get('type')

                if expected_type == 'string' and not isinstance(value, str):
                    errors.append(f'{key}: expected string')
                elif expected_type == 'number' and not isinstance(value, (int, float)):
                    errors.append(f'{key}: expected number')
                elif expected_type == 'integer' and not isinstance(value, int):
                    errors.append(f'{key}: expected integer')
                elif expected_type == 'boolean' and not isinstance(value, bool):
                    errors.append(f'{key}: expected boolean')
                elif expected_type == 'array' and not isinstance(value, list):
                    errors.append(f'{key}: expected array')
                elif expected_type == 'object' and not isinstance(value, dict):
                    errors.append(f'{key}: expected object')

        return errors

    def _audit_log(
        self,
        session_id: str,
        tool_name: str,
        args: dict,
        result: dict,
        dry_run: bool
    ) -> None:
        """Create audit log entry."""
        event = DialogEvent()
        event.header.stamp = self.get_clock().now().to_msg()
        event.event_id = f'audit-{int(time.time()*1000)}'
        event.session_id = session_id
        event.event_type = 'tool_invoke' if not dry_run else 'tool_dry_run'
        event.source = 'tool_router'
        event.payload_json = json.dumps({
            'tool_name': tool_name,
            'args': args,
            'result': result,
            'dry_run': dry_run
        })
        event.success = result.get('success', False)
        event.duration_ms = result.get('duration_ms', 0)

        self.event_pub.publish(event)

    def _publish_error(self, message: str) -> None:
        """Publish error event."""
        event = DialogEvent()
        event.header.stamp = self.get_clock().now().to_msg()
        event.event_id = f'error-{int(time.time()*1000)}'
        event.event_type = 'error'
        event.source = 'tool_router'
        event.success = False
        event.error_message = message

        self.event_pub.publish(event)


def main(args=None):
    rclpy.init(args=args)
    node = ToolRouterNode()

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
