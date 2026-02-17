#!/bin/bash
# Quick test script - runs tests without Docker

set -e

cd "$(dirname "$0")/.."

echo "=== Quick Unit Tests ==="

# Run Python unit tests directly
echo "1. Testing FileSystemMemoryStore..."
python3 tests/test_filesystem_store.py

echo ""
echo "2. Testing LLM Provider..."
python3 tests/test_llm_provider.py

echo ""
echo "=== All unit tests passed! ==="
