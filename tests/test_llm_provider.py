# Copyright 2026 ROS2 Brain Agent Team
# SPDX-License-Identifier: Apache-2.0

"""
Tests for LLM Provider.
"""

import json
import unittest
import sys
import os

# Add packages to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'packages', 'cmm_brain'))

from cmm_brain.llm_provider import (
    LLMConfig,
    LLMProvider,
    MockLLMProvider,
    JSONSchemaValidator
)


class TestJSONSchemaValidator(unittest.TestCase):
    """Test cases for JSON Schema validator."""

    def setUp(self):
        """Set up test fixtures."""
        self.validator = JSONSchemaValidator()

    def test_validate_valid_object(self):
        """Test validation of valid object."""
        schema = {
            "type": "object",
            "properties": {
                "assistant_text": {"type": "string"},
                "plan": {"type": "array"}
            },
            "required": ["assistant_text"]
        }

        data = {
            "assistant_text": "Hello",
            "plan": []
        }

        errors = self.validator.validate(data, schema)
        self.assertEqual(len(errors), 0)

    def test_validate_missing_required(self):
        """Test validation catches missing required fields."""
        schema = {
            "type": "object",
            "properties": {
                "assistant_text": {"type": "string"}
            },
            "required": ["assistant_text"]
        }

        data = {}

        errors = self.validator.validate(data, schema)
        self.assertGreater(len(errors), 0)
        self.assertIn("Missing required field", errors[0])

    def test_validate_wrong_type(self):
        """Test validation catches type mismatches."""
        schema = {
            "type": "object",
            "properties": {
                "count": {"type": "integer"},
                "name": {"type": "string"}
            }
        }

        data = {
            "count": "not a number",
            "name": 123
        }

        errors = self.validator.validate(data, schema)
        self.assertEqual(len(errors), 2)


class TestMockLLMProvider(unittest.TestCase):
    """Test cases for Mock LLM Provider."""

    def setUp(self):
        """Set up test fixtures."""
        config = LLMConfig(
            base_url="http://mock",
            api_key="mock",
            model="mock-model"
        )
        self.provider = MockLLMProvider(config)

    def test_call_without_preset_response(self):
        """Test call returns default response."""
        response = self.provider.call([
            {"role": "user", "content": "Hello"}
        ])

        self.assertIn("assistant_text", response.content)

        parsed = response.parse_json()
        self.assertIsNotNone(parsed)
        self.assertIn("assistant_text", parsed)

    def test_call_with_preset_response(self):
        """Test call returns preset response."""
        self.provider.add_response(json.dumps({
            "assistant_text": "Custom response",
            "plan": [],
            "tool_calls": [],
            "memory_write": []
        }))

        response = self.provider.call([
            {"role": "user", "content": "Hello"}
        ])

        parsed = response.parse_json()
        self.assertEqual(parsed["assistant_text"], "Custom response")

    def test_call_with_json_schema(self):
        """Test call with JSON schema validation."""
        schema = {
            "type": "object",
            "properties": {
                "assistant_text": {"type": "string"},
                "plan": {"type": "array"}
            },
            "required": ["assistant_text"]
        }

        response, parsed = self.provider.call_with_json_schema(
            [{"role": "user", "content": "Hello"}],
            schema
        )

        self.assertIsNotNone(parsed)
        self.assertIn("assistant_text", parsed)

    def test_extract_json_from_markdown(self):
        """Test JSON extraction from markdown code blocks."""
        content = '''Here's my response:
```json
{"assistant_text": "Hello", "plan": []}
```
Hope that helps!'''

        extracted = self.provider._extract_json(content)
        self.assertIsNotNone(extracted)
        self.assertEqual(extracted["assistant_text"], "Hello")


if __name__ == '__main__':
    unittest.main()
