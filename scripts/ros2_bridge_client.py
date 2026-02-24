#!/usr/bin/env python3
# Copyright 2026 ROS2 Brain Agent Team
# SPDX-License-Identifier: Apache-2.0

"""
ROS2 Bridge Client - Connects Web UI to ROS2 system via rosbridge.

This module provides a bridge between the Flask Web UI and ROS2 topics/services.
It can work in two modes:
1. Simulation mode - Uses local simulation (no ROS2 required)
2. Bridge mode - Connects to ROS2 via rosbridge WebSocket
"""

import json
import asyncio
import threading
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
import os

# Try to import websocket client
try:
    import websocket
    WEBSOCKET_AVAILABLE = True
except ImportError:
    WEBSOCKET_AVAILABLE = False


@dataclass
class ROS2Topic:
    """Represents a ROS2 topic."""
    name: str
    type: str
    subscribers: List[str] = field(default_factory=list)
    publishers: List[str] = field(default_factory=list)


@dataclass
class WorldState:
    """Robot world state."""
    robot_position: Dict[str, float] = field(default_factory=lambda: {"x": 0.0, "y": 0.0, "theta": 0.0})
    battery_level: int = 85
    holding_object: bool = False
    localization_ok: bool = True
    safety_state: str = "NORMAL"
    arm_state: str = "READY"
    detected_objects: List[Dict] = field(default_factory=list)


class RosBridgeClient:
    """
    Client for communicating with ROS2 via rosbridge WebSocket.

    Usage:
        client = RosBridgeClient("ws://localhost:9090")
        client.connect()
        client.publish("/dialog/user_input", {"text": "Hello", "session_id": "test"})
        client.subscribe("/dialog/events", callback_function)
    """

    def __init__(self, url: str = "ws://localhost:9090"):
        self.url = url
        self.ws: Optional[websocket.WebSocket] = None
        self.connected = False
        self.callbacks: Dict[str, List[Callable]] = {}
        self._lock = threading.Lock()
        self._message_id = 0
        self._advertised_topics: Dict[str, str] = {}  # topic -> type mapping

    def connect(self) -> bool:
        """Connect to rosbridge server."""
        if not WEBSOCKET_AVAILABLE:
            print("Warning: websocket-client not installed, using simulation mode")
            return False

        try:
            self.ws = websocket.create_connection(self.url, timeout=5)
            self.connected = True
            print(f"Connected to rosbridge at {self.url}")
            return True
        except Exception as e:
            print(f"Failed to connect to rosbridge: {e}")
            self.connected = False
            return False

    def disconnect(self):
        """Disconnect from rosbridge server."""
        if self.ws:
            self.ws.close()
            self.connected = False

    def _get_message_id(self) -> str:
        """Generate unique message ID."""
        self._message_id += 1
        return f"msg_{self._message_id}"

    def advertise(self, topic: str, msg_type: str) -> bool:
        """Advertise a topic with its message type."""
        if not self.connected or not self.ws:
            return False

        if topic in self._advertised_topics:
            return True  # Already advertised

        msg = {
            "op": "advertise",
            "topic": topic,
            "type": msg_type
        }

        try:
            self.ws.send(json.dumps(msg))
            self._advertised_topics[topic] = msg_type
            print(f"[ROS2] Advertised topic: {topic} ({msg_type})")
            return True
        except Exception as e:
            print(f"Failed to advertise: {e}")
            return False

    def publish(self, topic: str, message: Dict[str, Any], msg_type: str = None) -> bool:
        """Publish a message to a ROS2 topic."""
        if not self.connected or not self.ws:
            return False

        # Auto-advertise if message type provided and not yet advertised
        if msg_type and topic not in self._advertised_topics:
            self.advertise(topic, msg_type)

        msg = {
            "op": "publish",
            "topic": topic,
            "msg": message
        }

        try:
            self.ws.send(json.dumps(msg))
            return True
        except Exception as e:
            print(f"Failed to publish: {e}")
            return False

    def subscribe(self, topic: str, callback: Callable[[Dict], None]) -> bool:
        """Subscribe to a ROS2 topic."""
        if not self.connected or not self.ws:
            return False

        if topic not in self.callbacks:
            self.callbacks[topic] = []
        self.callbacks[topic].append(callback)

        msg = {
            "op": "subscribe",
            "topic": topic
        }

        try:
            self.ws.send(json.dumps(msg))
            return True
        except Exception as e:
            print(f"Failed to subscribe: {e}")
            return False

    def call_service(self, service: str, request: Dict[str, Any]) -> Optional[Dict]:
        """Call a ROS2 service."""
        if not self.connected or not self.ws:
            return None

        msg = {
            "op": "call_service",
            "service": service,
            "args": request,
            "id": self._get_message_id()
        }

        try:
            self.ws.send(json.dumps(msg))
            # Wait for response (simplified)
            response = self.ws.recv()
            return json.loads(response)
        except Exception as e:
            print(f"Failed to call service: {e}")
            return None

    def listen(self, timeout: float = 0.1):
        """Listen for incoming messages (non-blocking)."""
        if not self.connected or not self.ws:
            return

        try:
            self.ws.settimeout(timeout)
            data = self.ws.recv()
            if data:
                msg = json.loads(data)
                if msg.get("op") == "publish":
                    topic = msg.get("topic")
                    if topic in self.callbacks:
                        for callback in self.callbacks[topic]:
                            callback(msg.get("msg", {}))
        except websocket.WebSocketTimeoutException:
            pass
        except Exception as e:
            print(f"Listen error: {e}")


class SimulationBridge:
    """
    Simulation bridge for testing without ROS2.
    Simulates ROS2 topics and services locally.
    """

    def __init__(self):
        self.connected = True
        self.world_state = WorldState()
        self.message_log: List[Dict] = []

    def publish(self, topic: str, message: Dict[str, Any]) -> bool:
        """Simulate publishing to a topic."""
        self.message_log.append({
            "timestamp": datetime.utcnow().isoformat(),
            "topic": topic,
            "message": message
        })

        # Simulate topic effects
        if topic == "/dialog/user_input":
            return self._handle_user_input(message)
        elif topic == "/skill/execute":
            return self._handle_skill_execute(message)

        return True

    def _handle_user_input(self, message: Dict) -> bool:
        """Handle user input message."""
        print(f"[SIM] User input: {message.get('text', '')[:50]}...")
        return True

    def _handle_skill_execute(self, message: Dict) -> bool:
        """Handle skill execution request."""
        skill_name = message.get("skill", "unknown")
        args = message.get("args", {})

        # Simulate skill execution
        import random

        if skill_name.startswith("nav2.goto"):
            target = args.get("target_pose", {})
            x, y = target.get("x", 0), target.get("y", 0)
            old_x = self.world_state.robot_position["x"]
            old_y = self.world_state.robot_position["y"]

            self.world_state.robot_position["x"] = x
            self.world_state.robot_position["y"] = y

            distance = ((x - old_x)**2 + (y - old_y)**2)**0.5
            print(f"[SIM] Navigated to ({x}, {y}), distance: {distance:.2f}m")

        elif skill_name.startswith("arm.grasp"):
            self.world_state.holding_object = True
            self.world_state.arm_state = "HOLDING"
            print(f"[SIM] Grasped object")

        elif skill_name.startswith("arm.release"):
            self.world_state.holding_object = False
            self.world_state.arm_state = "READY"
            print(f"[SIM] Released object")

        elif skill_name.startswith("perception.detect"):
            obj_type = args.get("object_type", "unknown")
            # Simulate detection
            detected = random.random() > 0.2
            if detected:
                x = round(random.uniform(-2, 2), 2)
                y = round(random.uniform(-2, 2), 2)
                self.world_state.detected_objects.append({
                    "type": obj_type,
                    "position": {"x": x, "y": y}
                })
                print(f"[SIM] Detected {obj_type} at ({x}, {y})")
            else:
                print(f"[SIM] No {obj_type} detected")

        return True

    def subscribe(self, topic: str, callback: Callable[[Dict], None]) -> bool:
        """Simulate subscribing to a topic."""
        return True

    def call_service(self, service: str, request: Dict[str, Any]) -> Optional[Dict]:
        """Simulate calling a service."""
        if service == "/world_state/query":
            return {
                "success": True,
                "state": {
                    "robot_position": self.world_state.robot_position,
                    "battery_level": self.world_state.battery_level,
                    "holding_object": self.world_state.holding_object,
                    "localization_ok": self.world_state.localization_ok,
                    "safety_state": self.world_state.safety_state,
                    "arm_state": self.world_state.arm_state
                }
            }
        return {"success": True}

    def get_world_state(self) -> Dict:
        """Get current world state."""
        return {
            "robot_position": self.world_state.robot_position,
            "battery_level": self.world_state.battery_level,
            "holding_object": self.world_state.holding_object,
            "localization_ok": self.world_state.localization_ok,
            "safety_state": self.world_state.safety_state,
            "arm_state": self.world_state.arm_state,
            "detected_objects": self.world_state.detected_objects
        }


def create_bridge_client() -> RosBridgeClient | SimulationBridge:
    """
    Create appropriate bridge client based on configuration.

    Returns:
        RosBridgeClient if rosbridge is available, SimulationBridge otherwise
    """
    rosbridge_url = os.environ.get("ROSBRIDGE_URL", "ws://localhost:9090")

    # Check if we should use simulation mode
    use_simulation = os.environ.get("USE_SIMULATION", "true").lower() == "true"

    if use_simulation:
        print("Using simulation bridge (USE_SIMULATION=true)")
        return SimulationBridge()

    client = RosBridgeClient(rosbridge_url)
    if client.connect():
        return client
    else:
        print("Falling back to simulation bridge")
        return SimulationBridge()
