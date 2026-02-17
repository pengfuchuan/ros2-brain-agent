# Copyright 2026 ROS2 Brain Agent Team
# SPDX-License-Identifier: Apache-2.0

"""
ASR Client Node - Automatic Speech Recognition interface.

Responsibilities:
- Receive audio input
- Call ASR service (external API)
- Publish transcribed text to /dialog/user_input
"""

import json
import os
import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup
from std_msgs.msg import String
from audio_msgs.msg import AudioData  # type: ignore


class ASRClientNode(Node):
    """ASR Client ROS2 Node."""

    def __init__(self):
        super().__init__('asr_client_node')

        # Declare parameters
        self.declare_parameter('asr_provider', 'mock')  # mock, whisper, etc.
        self.declare_parameter('asr_api_url', '')
        self.declare_parameter('asr_api_key', '')
        self.declare_parameter('language', 'zh')
        self.declare_parameter('enable_vad', True)

        # Get parameters
        self.asr_provider = self.get_parameter('asr_provider').value
        self.asr_api_url = self.get_parameter('asr_api_url').value
        self.asr_api_key = self.get_parameter('asr_api_key').value
        self.language = self.get_parameter('language').value
        self.enable_vad = self.get_parameter('enable_vad').value

        # Callback group
        self.callback_group = ReentrantCallbackGroup()

        # Publishers
        self.text_output_pub = self.create_publisher(
            String,
            '/dialog/user_input',
            10
        )

        self.asr_event_pub = self.create_publisher(
            String,
            '/asr/events',
            10
        )

        # Subscribers
        self.audio_sub = self.create_subscription(
            String,  # Using String for simplicity, would be AudioData in production
            '/audio/input',
            self.handle_audio_input,
            10,
            callback_group=self.callback_group
        )

        self.get_logger().info(
            f'ASR Client initialized with provider: {self.asr_provider}'
        )

    def handle_audio_input(self, msg: String) -> None:
        """Handle audio input and transcribe."""
        try:
            # In production, msg would be AudioData
            # For now, accept base64 encoded audio or direct text
            if msg.data.startswith('{'):
                data = json.loads(msg.data)
                audio_data = data.get('audio', '')
                session_id = data.get('session_id', 'default')
            else:
                audio_data = msg.data
                session_id = 'default'

            # Transcribe
            text = self._transcribe(audio_data)

            if text:
                # Publish transcribed text
                output_msg = String()
                output_msg.data = json.dumps({
                    'text': text,
                    'session_id': session_id,
                    'source': 'asr'
                })
                self.text_output_pub.publish(output_msg)

                self.get_logger().info(f'Transcribed: {text[:50]}...')

        except Exception as e:
            self.get_logger().error(f'ASR error: {e}')

    def _transcribe(self, audio_data: str) -> str:
        """
        Transcribe audio to text.

        Args:
            audio_data: Audio data (base64 encoded or path)

        Returns:
            Transcribed text
        """
        if self.asr_provider == 'mock':
            return self._mock_transcribe(audio_data)

        elif self.asr_provider == 'whisper':
            return self._whisper_transcribe(audio_data)

        else:
            self.get_logger().warning(
                f'Unknown ASR provider: {self.asr_provider}, using mock'
            )
            return self._mock_transcribe(audio_data)

    def _mock_transcribe(self, audio_data: str) -> str:
        """Mock transcription for testing."""
        # Return mock text for testing
        if audio_data.startswith('mock:'):
            return audio_data[5:]
        return "这是一条模拟的语音识别结果"

    def _whisper_transcribe(self, audio_data: str) -> str:
        """
        Transcribe using Whisper API.

        Args:
            audio_data: Base64 encoded audio or file path

        Returns:
            Transcribed text
        """
        import urllib.request
        import base64

        if not self.asr_api_url:
            self.get_logger().error('Whisper API URL not configured')
            return ''

        try:
            # Prepare request
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self.asr_api_key}'
            }

            payload = {
                'audio': audio_data,
                'language': self.language
            }

            request_body = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                self.asr_api_url,
                data=request_body,
                headers=headers,
                method='POST'
            )

            with urllib.request.urlopen(req, timeout=30.0) as response:
                result = json.loads(response.read().decode('utf-8'))
                return result.get('text', '')

        except Exception as e:
            self.get_logger().error(f'Whisper API error: {e}')
            return ''

    def _publish_event(self, event_type: str, data: dict) -> None:
        """Publish ASR event."""
        msg = String()
        msg.data = json.dumps({
            'type': event_type,
            **data
        })
        self.asr_event_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = ASRClientNode()

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
