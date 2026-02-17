# Copyright 2026 ROS2 Brain Agent Team
# SPDX-License-Identifier: Apache-2.0

"""
World State Node - Maintains robot world state.

Responsibilities:
- Track robot pose and localization state
- Monitor navigation state
- Monitor arm/manipulation state
- Track perceived objects
- Manage safety state
- Provide WorldStateQuery service
- Publish WorldState messages
"""

import json
import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup
from std_msgs.msg import String
from geometry_msgs.msg import PoseWithCovarianceStamped
from cmm_interfaces.srv import WorldStateQuery
from cmm_interfaces.msg import WorldState, ErrorInfo


class WorldStateNode(Node):
    """World State ROS2 Node."""

    def __init__(self):
        super().__init__('world_state_node')

        # Declare parameters
        self.declare_parameter('publish_rate', 10.0)  # Hz
        self.declare_parameter('state_timeout_sec', 5.0)

        # Get parameters
        self.publish_rate = self.get_parameter('publish_rate').value
        self.state_timeout = self.get_parameter('state_timeout_sec').value

        # Callback group
        self.callback_group = ReentrantCallbackGroup()

        # Initialize state
        self._init_state()

        # Service server
        self.world_state_srv = self.create_service(
            WorldStateQuery,
            '/world_state/query',
            self.handle_world_state_query,
            callback_group=self.callback_group
        )

        # Publishers
        self.world_state_pub = self.create_publisher(
            WorldState,
            '/world_state/current',
            10
        )

        # Subscribers for state updates
        self.pose_sub = self.create_subscription(
            PoseWithCovarianceStamped,
            '/amcl_pose',
            self.handle_pose_update,
            10,
            callback_group=self.callback_group
        )

        # Subscribe to state updates from other nodes
        self.state_update_sub = self.create_subscription(
            String,
            '/world_state/update',
            self.handle_state_update,
            10,
            callback_group=self.callback_group
        )

        # Timer for periodic state publishing
        self.publish_timer = self.create_timer(
            1.0 / self.publish_rate,
            self.publish_world_state
        )

        self.get_logger().info('World State Node initialized')

    def _init_state(self) -> None:
        """Initialize state variables."""
        self.robot_pose = {
            'position': {'x': 0.0, 'y': 0.0, 'z': 0.0},
            'orientation': {'x': 0.0, 'y': 0.0, 'z': 0.0, 'w': 1.0}
        }
        self.localization_ok = False
        self.nav_state = 'UNKNOWN'
        self.arm_state = 'UNKNOWN'
        self.holding_object = False
        self.held_object_id = ''
        self.perceived_objects = []
        self.safety_state = 'UNKNOWN'
        self.last_pose_time = None
        self.last_update_time = None

    def handle_pose_update(self, msg: PoseWithCovarianceStamped) -> None:
        """Handle pose update from AMCL."""
        self.robot_pose = {
            'position': {
                'x': msg.pose.pose.position.x,
                'y': msg.pose.pose.position.y,
                'z': msg.pose.pose.position.z
            },
            'orientation': {
                'x': msg.pose.pose.orientation.x,
                'y': msg.pose.pose.orientation.y,
                'z': msg.pose.pose.orientation.z,
                'w': msg.pose.pose.orientation.w
            }
        }

        # Check covariance for localization quality
        covariance = msg.pose.covariance
        # Diagonal elements for x, y, theta
        x_var = covariance[0]
        y_var = covariance[7]
        theta_var = covariance[35]

        # Threshold for "good" localization
        self.localization_ok = (
            x_var < 0.5 and
            y_var < 0.5 and
            theta_var < 0.2
        )

        self.last_pose_time = self.get_clock().now()

    def handle_state_update(self, msg: String) -> None:
        """Handle state update from other nodes."""
        try:
            data = json.loads(msg.data)
        except json.JSONDecodeError:
            self.get_logger().error(f'Invalid JSON in state update: {msg.data[:100]}')
            return

        update_type = data.get('type', '')
        payload = data.get('payload', {})

        if update_type == 'nav_state':
            self.nav_state = payload.get('state', 'UNKNOWN')

        elif update_type == 'arm_state':
            self.arm_state = payload.get('state', 'UNKNOWN')
            self.holding_object = payload.get('holding', False)
            self.held_object_id = payload.get('object_id', '')

        elif update_type == 'perception':
            self.perceived_objects = payload.get('objects', [])

        elif update_type == 'safety':
            self.safety_state = payload.get('state', 'UNKNOWN')

        elif update_type == 'full':
            # Full state update
            self.nav_state = payload.get('nav_state', self.nav_state)
            self.arm_state = payload.get('arm_state', self.arm_state)
            self.holding_object = payload.get('holding_object', self.holding_object)
            self.held_object_id = payload.get('held_object_id', self.held_object_id)
            self.perceived_objects = payload.get('perceived_objects', self.perceived_objects)
            self.safety_state = payload.get('safety_state', self.safety_state)

        self.last_update_time = self.get_clock().now()

    def handle_world_state_query(
        self,
        request: WorldStateQuery.Request,
        response: WorldStateQuery.Response
    ) -> WorldStateQuery.Response:
        """Handle world state query service."""
        query_type = request.query_type
        keys = list(request.keys) if request.keys else []

        try:
            if query_type == 'full':
                result = self._get_full_state()

            elif query_type == 'pose':
                result = {'pose': self.robot_pose}

            elif query_type == 'nav_state':
                result = {
                    'nav_state': self.nav_state,
                    'localization_ok': self.localization_ok
                }

            elif query_type == 'arm_state':
                result = {
                    'arm_state': self.arm_state,
                    'holding_object': self.holding_object,
                    'held_object_id': self.held_object_id
                }

            elif query_type == 'objects':
                result = {'perceived_objects': self.perceived_objects}

            elif query_type == 'safety':
                result = {'safety_state': self.safety_state}

            else:
                # Default to full state
                result = self._get_full_state()

            # Filter by keys if specified
            if keys:
                result = {k: v for k, v in result.items() if k in keys}

            response.success = True
            response.state_json = json.dumps(result, ensure_ascii=False)

        except Exception as e:
            self.get_logger().error(f'World state query error: {e}')
            response.success = False
            response.error.code = 'QUERY_ERROR'
            response.error.message = str(e)
            response.state_json = '{}'

        return response

    def _get_full_state(self) -> dict:
        """Get full world state."""
        return {
            'pose': self.robot_pose,
            'localization_ok': self.localization_ok,
            'nav_state': self.nav_state,
            'arm_state': self.arm_state,
            'holding_object': self.holding_object,
            'held_object_id': self.held_object_id,
            'perceived_objects': self.perceived_objects,
            'safety_state': self.safety_state
        }

    def publish_world_state(self) -> None:
        """Publish current world state."""
        msg = WorldState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'map'

        msg.localization_ok = self.localization_ok
        msg.nav_state = self.nav_state

        msg.robot_pose.position.x = self.robot_pose['position']['x']
        msg.robot_pose.position.y = self.robot_pose['position']['y']
        msg.robot_pose.position.z = self.robot_pose['position']['z']
        msg.robot_pose.orientation.x = self.robot_pose['orientation']['x']
        msg.robot_pose.orientation.y = self.robot_pose['orientation']['y']
        msg.robot_pose.orientation.z = self.robot_pose['orientation']['z']
        msg.robot_pose.orientation.w = self.robot_pose['orientation']['w']

        msg.arm_state = self.arm_state
        msg.holding_object = self.holding_object
        msg.held_object_id = self.held_object_id
        msg.perceived_objects = self.perceived_objects
        msg.safety_state = self.safety_state
        msg.last_update = self.get_clock().now().to_msg()

        self.world_state_pub.publish(msg)

    def update_nav_state(self, state: str) -> None:
        """Update navigation state."""
        self.nav_state = state
        self.get_logger().debug(f'Nav state updated: {state}')

    def update_arm_state(self, state: str, holding: bool = False, object_id: str = '') -> None:
        """Update arm state."""
        self.arm_state = state
        self.holding_object = holding
        self.held_object_id = object_id
        self.get_logger().debug(f'Arm state updated: {state}, holding: {holding}')

    def update_safety_state(self, state: str) -> None:
        """Update safety state."""
        self.safety_state = state
        if state == 'ESTOP':
            self.get_logger().warning('Safety E-STOP activated!')
        else:
            self.get_logger().debug(f'Safety state updated: {state}')

    def add_perceived_object(self, object_id: str) -> None:
        """Add a perceived object."""
        if object_id not in self.perceived_objects:
            self.perceived_objects.append(object_id)

    def remove_perceived_object(self, object_id: str) -> None:
        """Remove a perceived object."""
        if object_id in self.perceived_objects:
            self.perceived_objects.remove(object_id)

    def clear_perceived_objects(self) -> None:
        """Clear all perceived objects."""
        self.perceived_objects = []


def main(args=None):
    rclpy.init(args=args)
    node = WorldStateNode()

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
