# Copyright 2026 ROS2 Brain Agent Team
# SPDX-License-Identifier: Apache-2.0

"""
TTS Client Node - Text-to-Speech interface.

Responsibilities:
- Subscribe to LLM responses
- Call TTS service (external API)
- Publish audio output
"""

import json
import os
import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup
from std_msgs.msg import String


class TTSClientNode(Node):
    """TTS Client ROS2 Node."""

    def __init__(self):
        super().__init__('tts_client_node')

        # Declare parameters
        self.declare_parameter('tts_provider', 'mock')  # mock, elevenlabs, azure, etc.
        self.declare_parameter('tts_api_url', '')
        self.declare_parameter('tts_api_key', '')
        self.declare_parameter('voice_id', 'default')
        self.declare_parameter('language', 'zh')
        self.declare_parameter('output_format', 'wav')

        # Get parameters
        self.tts_provider = self.get_parameter('tts_provider').value
        self.tts_api_url = self.get_parameter('tts_api_url').value
        self.tts_api_key = self.get_parameter('tts_api_key').value
        self.voice_id = self.get_parameter('voice_id').value
        self.language = self.get_parameter('language').value
        self.output_format = self.get_parameter('output_format').value

        # Callback group
        self.callback_group = ReentrantCallbackGroup()

        # Publishers
        self.audio_output_pub = self.create_publisher(
            String,
            '/audio/output',
            10
        )

        self.tts_event_pub = self.create_publisher(
            String,
            '/tts/events',
            10
        )

        # Subscribers
        self.text_input_sub = self.create_subscription(
            String,
            '/dialog/llm_response',
            self.handle_text_input,
            10,
            callback_group=self.callback_group
        )

        # Also subscribe to direct TTS requests
        self.tts_request_sub = self.create_subscription(
            String,
            '/tts/synthesize',
            self.handle_tts_request,
            10,
            callback_group=self.callback_group
        )

        self.get_logger().info(
            f'TTS Client initialized with provider: {self.tts_provider}'
        )

    def handle_text_input(self, msg: String) -> None:
        """Handle LLM response and synthesize speech."""
        try:
            data = json.loads(msg.data)
            text = data.get('assistant_text', '')
            session_id = data.get('session_id', 'default')

            if not text:
                return

            # Synthesize speech
            audio = self._synthesize(text)

            if audio:
                # Publish audio output
                output_msg = String()
                output_msg.data = json.dumps({
                    'audio': audio,
                    'text': text,
                    'session_id': session_id,
                    'format': self.output_format
                })
                self.audio_output_pub.publish(output_msg)

                self._publish_event('synthesis_complete', {
                    'session_id': session_id,
                    'text_length': len(text)
                })

        except json.JSONDecodeError:
            # Plain text response
            text = msg.data
            if text:
                audio = self._synthesize(text)
                if audio:
                    output_msg = String()
                    output_msg.data = json.dumps({
                        'audio': audio,
                        'text': text,
                        'format': self.output_format
                    })
                    self.audio_output_pub.publish(output_msg)

        except Exception as e:
            self.get_logger().error(f'TTS error: {e}')
            self._publish_event('synthesis_error', {'error': str(e)})

    def handle_tts_request(self, msg: String) -> None:
        """Handle direct TTS synthesis request."""
        try:
            data = json.loads(msg.data) if msg.data.startswith('{') else {
                'text': msg.data
            }

            text = data.get('text', '')
            session_id = data.get('session_id', 'default')
            voice_id = data.get('voice_id', self.voice_id)

            if not text:
                return

            audio = self._synthesize(text, voice_id=voice_id)

            if audio:
                output_msg = String()
                output_msg.data = json.dumps({
                    'audio': audio,
                    'text': text,
                    'session_id': session_id,
                    'format': self.output_format
                })
                self.audio_output_pub.publish(output_msg)

        except Exception as e:
            self.get_logger().error(f'TTS request error: {e}')

    def _synthesize(self, text: str, voice_id: str = None) -> str:
        """
        Synthesize speech from text.

        Args:
            text: Text to synthesize
            voice_id: Optional voice ID override

        Returns:
            Audio data (base64 encoded) or empty string on error
        """
        if self.tts_provider == 'mock':
            return self._mock_synthesize(text)

        elif self.tts_provider == 'elevenlabs':
            return self._elevenlabs_synthesize(text, voice_id)

        elif self.tts_provider == 'azure':
            return self._azure_synthesize(text, voice_id)

        else:
            self.get_logger().warning(
                f'Unknown TTS provider: {self.tts_provider}, using mock'
            )
            return self._mock_synthesize(text)

    def _mock_synthesize(self, text: str) -> str:
        """Mock synthesis for testing."""
        # Return mock audio data
        return f"mock_audio_data_for:_{text[:20]}"

    def _elevenlabs_synthesize(self, text: str, voice_id: str = None) -> str:
        """Synthesize using ElevenLabs API."""
        import urllib.request
        import base64

        if not self.tts_api_url:
            # Default ElevenLabs URL
            vid = voice_id or self.voice_id
            self.tts_api_url = f"https://api.elevenlabs.io/v1/text-to-speech/{vid}"

        try:
            headers = {
                'Content-Type': 'application/json',
                'xi-api-key': self.tts_api_key
            }

            payload = {
                'text': text,
                'voice_settings': {
                    'stability': 0.5,
                    'similarity_boost': 0.75
                }
            }

            request_body = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                self.tts_api_url,
                data=request_body,
                headers=headers,
                method='POST'
            )

            with urllib.request.urlopen(req, timeout=30.0) as response:
                audio_data = response.read()
                return base64.b64encode(audio_data).decode('utf-8')

        except Exception as e:
            self.get_logger().error(f'ElevenLabs API error: {e}')
            return ''

    def _azure_synthesize(self, text: str, voice_id: str = None) -> str:
        """Synthesize using Azure Speech API."""
        # Placeholder for Azure implementation
        self.get_logger().warning('Azure TTS not implemented, using mock')
        return self._mock_synthesize(text)

    def _publish_event(self, event_type: str, data: dict) -> None:
        """Publish TTS event."""
        msg = String()
        msg.data = json.dumps({
            'type': event_type,
            **data
        })
        self.tts_event_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = TTSClientNode()

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
