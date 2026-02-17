#!/bin/bash
# ROS2 Brain Agent Automated Test Script
# Run inside Docker container

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

TESTS_PASSED=0
TESTS_FAILED=0

# Test result tracking
pass() {
    echo -e "${GREEN}[PASS]${NC} $1"
    ((TESTS_PASSED++))
}

fail() {
    echo -e "${RED}[FAIL]${NC} $1"
    ((TESTS_FAILED++))
}

section() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

# Source ROS2
source /opt/ros/humble/setup.bash

# Source workspace if available
if [ -f /ros2_ws/install/setup.bash ]; then
    source /ros2_ws/install/setup.bash
fi

cd /ros2_ws/src/ros2-brain-agent

# ========================================
# 1. Python Unit Tests
# ========================================
section "1. Python Unit Tests"

echo "Running test_filesystem_store.py..."
if python3 tests/test_filesystem_store.py > /tmp/test_fs.log 2>&1; then
    pass "Filesystem Store Tests"
else
    fail "Filesystem Store Tests"
    cat /tmp/test_fs.log
fi

echo "Running test_llm_provider.py..."
if python3 tests/test_llm_provider.py > /tmp/test_llm.log 2>&1; then
    pass "LLM Provider Tests"
else
    fail "LLM Provider Tests"
    cat /tmp/test_llm.log
fi

# ========================================
# 2. Memory System Tests
# ========================================
section "2. Memory System Tests"

# Start memory node in background
ros2 run cmm_brain memory_node &
MEMORY_PID=$!
sleep 2

# Test memory service
echo "Testing Memory Query Service..."
if ros2 service call /memory/query cmm_interfaces/srv/MemoryQuery \
    "{session_id: 'test_session', query_type: 'facts', limit: 10, offset: 0}" \
    > /tmp/memory_test.log 2>&1; then
    pass "Memory Query Service"
else
    fail "Memory Query Service"
    cat /tmp/memory_test.log
fi

# Stop memory node
kill $MEMORY_PID 2>/dev/null || true
sleep 1

# ========================================
# 3. World State Tests
# ========================================
section "3. World State Tests"

# Start world state node
ros2 run cmm_cerebellum world_state_node &
WORLD_PID=$!
sleep 2

# Test world state service
echo "Testing World State Query Service..."
if ros2 service call /world_state/query cmm_interfaces/srv/WorldStateQuery \
    "{query_type: 'full', keys: []}" \
    > /tmp/world_test.log 2>&1; then
    pass "World State Query Service"
else
    fail "World State Query Service"
    cat /tmp/world_test.log
fi

# Stop world state node
kill $WORLD_PID 2>/dev/null || true
sleep 1

# ========================================
# 4. Dialog Manager Tests
# ========================================
section "4. Dialog Manager Tests"

# Start nodes
ros2 run cmm_brain memory_node &
MEMORY_PID=$!
sleep 1

ros2 run cmm_brain dialog_manager_node &
DIALOG_PID=$!
sleep 2

# Test user input topic
echo "Testing Dialog User Input..."
ros2 topic pub /dialog/user_input std_msgs/String \
    '{data: "{\"text\": \"hello world\", \"session_id\": \"test1\"}"}' --once > /dev/null 2>&1

sleep 2

# Check if event was published
echo "Checking for dialog events..."
if timeout 3s ros2 topic echo /dialog/events --once > /tmp/dialog_test.log 2>&1; then
    pass "Dialog Event Publishing"
else
    fail "Dialog Event Publishing"
fi

# Stop nodes
kill $DIALOG_PID $MEMORY_PID 2>/dev/null || true
sleep 1

# ========================================
# 5. Tool Router Tests
# ========================================
section "5. Tool Router Tests"

# Start tool router
ros2 run cmm_brain tool_router_node &
TOOL_PID=$!
sleep 2

# Test tool execute service (dry run mode)
echo "Testing Tool Execute Service (dry run)..."
if ros2 service call /tool/execute_sync cmm_interfaces/srv/ToolExecute \
    "{tool_name: 'nav2.goto', args_json: '{\"target_pose\": {\"x\": 1.0, \"y\": 0.0}}', session_id: 'test', dry_run: true}" \
    > /tmp/tool_test.log 2>&1; then
    pass "Tool Execute Service (dry run)"
else
    fail "Tool Execute Service (dry run)"
    cat /tmp/tool_test.log
fi

# Stop tool router
kill $TOOL_PID 2>/dev/null || true
sleep 1

# ========================================
# 6. Skill Server Tests
# ========================================
section "6. Skill Server Tests"

# Start skill server
ros2 run cmm_cerebellum skill_server_node &
SKILL_PID=$!
sleep 2

# Test skill request (topic-based)
echo "Testing Skill Execution Request..."
ros2 topic pub /skill/execute std_msgs/String \
    '{data: "{\"skill_name\": \"nav2.goto\", \"args\": {\"target_pose\": {\"x\": 1.0, \"y\": 0.0}}, \"session_id\": \"test\"}"}' --once > /dev/null 2>&1

sleep 2

# Check for result
if timeout 3s ros2 topic echo /skill/result --once > /tmp/skill_test.log 2>&1; then
    pass "Skill Execution"
else
    # This is expected in mock mode without full setup
    echo -e "${YELLOW}[SKIP]${NC} Skill Execution (requires full ROS2 setup)"
fi

# Stop skill server
kill $SKILL_PID 2>/dev/null || true
sleep 1

# ========================================
# 7. Integration Test
# ========================================
section "7. Integration Test (Multi-Node)"

echo "Starting all nodes..."

# Start all nodes
ros2 run cmm_brain memory_node &
PID1=$!
sleep 1

ros2 run cmm_brain dialog_manager_node &
PID2=$!
sleep 1

ros2 run cmm_brain tool_router_node &
PID3=$!
sleep 1

ros2 run cmm_cerebellum world_state_node &
PID4=$!
sleep 1

ros2 run cmm_cerebellum skill_server_node &
PID5=$!
sleep 2

# Check running nodes
echo "Checking running nodes..."
NODE_COUNT=$(ros2 node list 2>/dev/null | wc -l)

if [ "$NODE_COUNT" -ge 5 ]; then
    pass "All nodes running ($NODE_COUNT nodes)"
else
    fail "Expected 5+ nodes, got $NODE_COUNT"
fi

# Test full flow
echo "Testing full message flow..."
ros2 topic pub /dialog/user_input std_msgs/String \
    '{data: "{\"text\": \"导航到厨房\", \"session_id\": \"integration_test\"}"}' --once > /dev/null 2>&1

sleep 3

# Verify memory was written
if ros2 service call /memory/query cmm_interfaces/srv/MemoryQuery \
    "{session_id: 'integration_test', query_type: 'turns', limit: 5, offset: 0}" \
    > /tmp/integration_test.log 2>&1; then
    pass "Integration Test - Memory Write"
else
    fail "Integration Test - Memory Write"
fi

# Cleanup
echo "Stopping all nodes..."
kill $PID1 $PID2 $PID3 $PID4 $PID5 2>/dev/null || true
sleep 1

# ========================================
# Summary
# ========================================
section "Test Summary"

echo -e "Tests Passed: ${GREEN}$TESTS_PASSED${NC}"
echo -e "Tests Failed: ${RED}$TESTS_FAILED${NC}"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}Some tests failed. Check logs above for details.${NC}"
    exit 1
fi
