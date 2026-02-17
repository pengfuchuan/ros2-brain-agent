# Copyright 2026 ROS2 Brain Agent Team
# SPDX-License-Identifier: Apache-2.0

"""
LLM Provider - Abstract interface and implementations for LLM services.

Supports:
- OpenAI-compatible APIs
- JSON Schema validation
- Auto-retry with fix attempts
"""

import json
import os
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import urllib.request
import urllib.error


@dataclass
class LLMResponse:
    """Represents an LLM response."""
    content: str
    raw_response: Dict[str, Any]
    model: str
    usage: Dict[str, int] = field(default_factory=dict)
    duration_ms: int = 0

    def parse_json(self) -> Optional[Dict[str, Any]]:
        """Try to parse content as JSON."""
        try:
            return json.loads(self.content)
        except json.JSONDecodeError:
            return None


@dataclass
class LLMConfig:
    """Configuration for LLM provider."""
    base_url: str
    api_key: str
    model: str
    timeout_sec: float = 60.0
    max_retries: int = 3
    temperature: float = 0.7
    max_tokens: int = 4096
    top_p: float = 1.0


class JSONSchemaValidator:
    """Simple JSON Schema validator for LLM output."""

    @staticmethod
    def validate(data: Dict[str, Any], schema: Dict[str, Any]) -> List[str]:
        """
        Validate data against schema.
        Returns list of error messages, empty if valid.
        """
        errors = []

        if schema.get("type") == "object":
            if not isinstance(data, dict):
                errors.append("Expected object, got " + type(data).__name__)
                return errors

            # Check required fields
            required = schema.get("required", [])
            for field in required:
                if field not in data:
                    errors.append(f"Missing required field: {field}")

            # Check property types
            properties = schema.get("properties", {})
            for key, value in data.items():
                if key in properties:
                    prop_schema = properties[key]
                    prop_errors = JSONSchemaValidator._validate_type(
                        value, prop_schema, key
                    )
                    errors.extend(prop_errors)

        return errors

    @staticmethod
    def _validate_type(value: Any, schema: Dict[str, Any], path: str) -> List[str]:
        """Validate a value against its type schema."""
        errors = []
        expected_type = schema.get("type")

        if expected_type == "string":
            if not isinstance(value, str):
                errors.append(f"{path}: expected string, got {type(value).__name__}")
        elif expected_type == "number":
            if not isinstance(value, (int, float)):
                errors.append(f"{path}: expected number, got {type(value).__name__}")
        elif expected_type == "integer":
            if not isinstance(value, int):
                errors.append(f"{path}: expected integer, got {type(value).__name__}")
        elif expected_type == "boolean":
            if not isinstance(value, bool):
                errors.append(f"{path}: expected boolean, got {type(value).__name__}")
        elif expected_type == "array":
            if not isinstance(value, list):
                errors.append(f"{path}: expected array, got {type(value).__name__}")
        elif expected_type == "object":
            if not isinstance(value, dict):
                errors.append(f"{path}: expected object, got {type(value).__name__}")

        return errors


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    def __init__(self, config: LLMConfig):
        self.config = config
        self.validator = JSONSchemaValidator()

    @abstractmethod
    def call(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Call the LLM with messages.

        Args:
            messages: List of message dicts with 'role' and 'content'
            tools: Optional list of tool definitions
            **kwargs: Additional provider-specific parameters

        Returns:
            LLMResponse object
        """
        pass

    def call_with_json_schema(
        self,
        messages: List[Dict[str, str]],
        schema: Dict[str, Any],
        tools: Optional[List[Dict[str, Any]]] = None,
        max_fix_attempts: int = 3
    ) -> tuple[LLMResponse, Optional[Dict[str, Any]]]:
        """
        Call LLM and validate JSON output against schema.

        Args:
            messages: List of message dicts
            schema: JSON Schema for validation
            tools: Optional tool definitions
            max_fix_attempts: Maximum attempts to fix invalid JSON

        Returns:
            Tuple of (LLMResponse, parsed JSON or None)
        """
        for attempt in range(max_fix_attempts):
            response = self.call(messages, tools)

            # Try to extract JSON from response
            json_content = self._extract_json(response.content)

            if json_content is None:
                # Ask LLM to fix
                messages.append({
                    "role": "assistant",
                    "content": response.content
                })
                messages.append({
                    "role": "user",
                    "content": "Your response must be valid JSON. Please provide only the JSON output, no additional text."
                })
                continue

            # Validate against schema
            errors = self.validator.validate(json_content, schema)

            if not errors:
                return response, json_content

            # Ask LLM to fix schema errors
            messages.append({
                "role": "assistant",
                "content": response.content
            })
            messages.append({
                "role": "user",
                "content": f"Your JSON has schema validation errors: {errors}. Please fix and provide valid JSON."
            })

        return response, None

    def _extract_json(self, content: str) -> Optional[Dict[str, Any]]:
        """Extract JSON from content, handling markdown code blocks."""
        # Try direct parse first
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # Try to extract from markdown code block
        code_block_pattern = r'```(?:json)?\s*\n?(.*?)\n?```'
        matches = re.findall(code_block_pattern, content, re.DOTALL)

        for match in matches:
            try:
                return json.loads(match.strip())
            except json.JSONDecodeError:
                continue

        # Try to find JSON object in content
        json_pattern = r'\{[\s\S]*\}'
        matches = re.findall(json_pattern, content)

        for match in matches:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue

        return None


class OpenAICompatibleProvider(LLMProvider):
    """OpenAI-compatible API provider."""

    def call(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> LLMResponse:
        """Call OpenAI-compatible API."""
        start_time = time.time()

        url = f"{self.config.base_url.rstrip('/')}/chat/completions"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.api_key}"
        }

        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": kwargs.get("temperature", self.config.temperature),
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "top_p": kwargs.get("top_p", self.config.top_p)
        }

        if tools:
            payload["tools"] = tools

        request_body = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            url,
            data=request_body,
            headers=headers,
            method='POST'
        )

        last_error = None
        for attempt in range(self.config.max_retries):
            try:
                with urllib.request.urlopen(req, timeout=self.config.timeout_sec) as response:
                    response_data = json.loads(response.read().decode('utf-8'))

                    content = response_data["choices"][0]["message"]["content"]
                    usage = response_data.get("usage", {})

                    duration_ms = int((time.time() - start_time) * 1000)

                    return LLMResponse(
                        content=content,
                        raw_response=response_data,
                        model=response_data.get("model", self.config.model),
                        usage=usage,
                        duration_ms=duration_ms
                    )

            except urllib.error.HTTPError as e:
                last_error = f"HTTP {e.code}: {e.reason}"
                if e.code == 429:  # Rate limit
                    time.sleep(2 ** attempt)
                elif e.code >= 500:  # Server error
                    time.sleep(1)
                else:
                    break
            except urllib.error.URLError as e:
                last_error = f"URL Error: {e.reason}"
                time.sleep(1)
            except Exception as e:
                last_error = f"Error: {str(e)}"
                break

        duration_ms = int((time.time() - start_time) * 1000)
        raise RuntimeError(f"LLM call failed after {self.config.max_retries} attempts: {last_error}")


class MockLLMProvider(LLMProvider):
    """Mock LLM provider for testing."""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self.responses: List[str] = []
        self.call_count = 0

    def add_response(self, response: str) -> None:
        """Add a mock response."""
        self.responses.append(response)

    def call(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> LLMResponse:
        """Return mock response."""
        self.call_count += 1

        if self.responses:
            content = self.responses.pop(0)
        else:
            # Generate a default response
            content = json.dumps({
                "assistant_text": "I understand your request.",
                "plan": [],
                "tool_calls": [],
                "memory_write": []
            })

        return LLMResponse(
            content=content,
            raw_response={"mock": True},
            model=self.config.model,
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            duration_ms=100
        )


def create_provider_from_config(config_dict: Dict[str, Any]) -> LLMProvider:
    """
    Create an LLM provider from configuration dict.

    Args:
        config_dict: Configuration dictionary from providers.yaml

    Returns:
        LLMProvider instance
    """
    provider_type = config_dict.get("type", "http")
    provider_config = config_dict.get("config", {})

    # Expand environment variables
    base_url = os.path.expandvars(provider_config.get("base_url", ""))
    api_key = os.path.expandvars(provider_config.get("api_key", ""))

    llm_config = LLMConfig(
        base_url=base_url,
        api_key=api_key,
        model=provider_config.get("model", "gpt-4o"),
        timeout_sec=provider_config.get("timeout_sec", 60.0),
        max_retries=provider_config.get("max_retries", 3)
    )

    # Apply parameters
    params = config_dict.get("parameters", {})
    llm_config.temperature = params.get("temperature", 0.7)
    llm_config.max_tokens = params.get("max_tokens", 4096)
    llm_config.top_p = params.get("top_p", 1.0)

    if provider_type == "http":
        return OpenAICompatibleProvider(llm_config)
    elif provider_type == "mock":
        return MockLLMProvider(llm_config)
    else:
        raise ValueError(f"Unknown provider type: {provider_type}")
