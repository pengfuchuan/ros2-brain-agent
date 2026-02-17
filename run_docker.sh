#!/bin/bash
# ROS2 Brain Agent Docker Development Environment
# Usage: ./run_docker.sh [build|start|stop|shell|test|clean]

set -e

# Configuration
IMAGE_NAME="ros2-brain-agent"
CONTAINER_NAME="ros2-brain-agent"
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKSPACE_DIR="/ros2_ws"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Build Docker image
build_image() {
    log_info "Building Docker image: ${IMAGE_NAME}"
    docker build -t ${IMAGE_NAME}:latest ${PROJECT_DIR}
    log_info "Build complete!"
}

# Start container
start_container() {
    # Check if container exists
    if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
            log_info "Container ${CONTAINER_NAME} is already running"
        else
            log_info "Starting existing container: ${CONTAINER_NAME}"
            docker start ${CONTAINER_NAME}
        fi
    else
        log_info "Creating and starting new container: ${CONTAINER_NAME}"
        docker run -d \
            --name ${CONTAINER_NAME} \
            --restart unless-stopped \
            --net=host \
            -v ${PROJECT_DIR}:${WORKSPACE_DIR}/src/ros2-brain-agent \
            -w ${WORKSPACE_DIR} \
            -e LLM_API_KEY=mock \
            -e LLM_PROVIDER=mock \
            ${IMAGE_NAME}:latest \
            bash -c "source /opt/ros/humble/setup.bash && tail -f /dev/null"
    fi
    log_info "Container started. Use './run_docker.sh shell' to enter."
}

# Stop container
stop_container() {
    log_info "Stopping container: ${CONTAINER_NAME}"
    docker stop ${CONTAINER_NAME} 2>/dev/null || true
    log_info "Container stopped."
}

# Remove container
remove_container() {
    stop_container
    log_info "Removing container: ${CONTAINER_NAME}"
    docker rm ${CONTAINER_NAME} 2>/dev/null || true
    log_info "Container removed."
}

# Enter container shell
enter_shell() {
    log_info "Entering container shell..."
    docker exec -it ${CONTAINER_NAME} bash -c "
        source /opt/ros/humble/setup.bash
        if [ -f ${WORKSPACE_DIR}/install/setup.bash ]; then
            source ${WORKSPACE_DIR}/install/setup.bash
        fi
        cd ${WORKSPACE_DIR}
        exec bash
    "
}

# Build ROS2 workspace
build_workspace() {
    log_info "Building ROS2 workspace..."
    docker exec ${CONTAINER_NAME} bash -c "
        source /opt/ros/humble/setup.bash
        cd ${WORKSPACE_DIR}

        # Create workspace structure if not exists
        mkdir -p src

        # Build
        colcon build --symlink-install

        echo 'Build complete!'
    "
    log_info "Workspace build complete!"
}

# Run tests
run_tests() {
    log_info "Running tests..."
    docker exec ${CONTAINER_NAME} bash -c "
        source /opt/ros/humble/setup.bash
        cd ${WORKSPACE_DIR}

        # Source workspace if built
        if [ -f install/setup.bash ]; then
            source install/setup.bash
        fi

        echo '========================================'
        echo '1. Running Python Unit Tests'
        echo '========================================'
        cd ${WORKSPACE_DIR}/src/ros2-brain-agent
        python3 -m pytest tests/ -v --tb=short 2>/dev/null || python3 tests/test_filesystem_store.py && python3 tests/test_llm_provider.py

        echo ''
        echo '========================================'
        echo '2. Running ROS2 Node Tests'
        echo '========================================'

        # Test 1: Memory Node
        echo 'Testing Memory Node...'
        timeout 5s ros2 run cmm_brain memory_node &
        sleep 2
        ros2 service call /memory/query cmm_interfaces/srv/MemoryQuery \
            \"{session_id: 'test', query_type: 'facts', limit: 10, offset: 0}\" \
            2>/dev/null && echo 'Memory Node: OK' || echo 'Memory Node: Failed'
        pkill -f memory_node 2>/dev/null || true

        echo ''
        echo '========================================'
        echo '3. Node Launch Test (Dry Run)'
        echo '========================================'
        timeout 10s ros2 launch cmm_brain brain_agent.launch.py dry_run:=true 2>&1 | head -30 &
        sleep 5
        pkill -f brain_agent || true
        echo 'Launch test completed.'

        echo ''
        echo '========================================'
        echo 'All tests completed!'
        echo '========================================'
    "
}

# Quick test - simplified version
quick_test() {
    log_info "Running quick tests..."
    docker exec ${CONTAINER_NAME} bash -c "
        source /opt/ros/humble/setup.bash
        cd ${WORKSPACE_DIR}

        if [ -f install/setup.bash ]; then
            source install/setup.bash
        fi

        echo '=== Unit Tests ==='
        cd ${WORKSPACE_DIR}/src/ros2-brain-agent
        python3 tests/test_filesystem_store.py
        python3 tests/test_llm_provider.py

        echo ''
        echo '=== Node Status Check ==='
        ros2 node list 2>/dev/null || echo 'No nodes running'

        echo ''
        echo 'Quick tests completed!'
    "
}

# Full integration test
integration_test() {
    log_info "Running full integration test..."
    docker exec ${CONTAINER_NAME} bash -c "
        source /opt/ros/humble/setup.bash
        cd ${WORKSPACE_DIR}

        if [ -f install/setup.bash ]; then
            source install/setup.bash
        fi

        echo '========================================'
        echo 'Full Integration Test'
        echo '========================================'

        # Start nodes in background
        echo 'Starting nodes...'
        ros2 run cmm_brain memory_node &
        MEMORY_PID=\$!
        sleep 1

        ros2 run cmm_brain dialog_manager_node &
        DIALOG_PID=\$!
        sleep 1

        ros2 run cmm_brain tool_router_node &
        TOOL_PID=\$!
        sleep 1

        ros2 run cmm_cerebellum world_state_node &
        WORLD_PID=\$!
        sleep 1

        ros2 run cmm_cerebellum skill_server_node &
        SKILL_PID=\$!
        sleep 2

        echo ''
        echo 'Running nodes:'
        ros2 node list

        echo ''
        echo 'Testing topic communication...'

        # Send test message
        ros2 topic pub /dialog/user_input std_msgs/String \
            '{data: \"{\\\"text\\\": \\\"测试消息\\\", \\\"session_id\\\": \\\"test1\\\"}\"}' --once

        sleep 2

        echo ''
        echo 'Checking events topic...'
        timeout 3s ros2 topic echo /dialog/events --once 2>/dev/null || echo 'No events received'

        echo ''
        echo 'Testing memory service...'
        ros2 service call /memory/query cmm_interfaces/srv/MemoryQuery \
            \"{session_id: 'test1', query_type: 'turns', limit: 5, offset: 0}\" 2>/dev/null

        echo ''
        echo 'Testing world state service...'
        ros2 service call /world_state/query cmm_interfaces/srv/WorldStateQuery \
            \"{query_type: 'full', keys: []}\" 2>/dev/null

        # Cleanup
        echo ''
        echo 'Stopping nodes...'
        kill \$MEMORY_PID \$DIALOG_PID \$TOOL_PID \$WORLD_PID \$SKILL_PID 2>/dev/null || true

        echo ''
        echo '========================================'
        echo 'Integration test completed!'
        echo '========================================'
    "
}

# Clean up everything
clean_all() {
    log_warn "This will remove container and images!"
    read -p "Are you sure? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        remove_container
        log_info "Removing images..."
        docker rmi ${IMAGE_NAME}:latest 2>/dev/null || true
        log_info "Cleanup complete!"
    fi
}

# Show logs
show_logs() {
    log_info "Showing container logs..."
    docker logs ${CONTAINER_NAME} --tail 100 -f
}

# Print usage
print_usage() {
    echo "ROS2 Brain Agent Docker Development Environment"
    echo ""
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  build     Build Docker image"
    echo "  start     Start container"
    echo "  stop      Stop container"
    echo "  shell     Enter container shell"
    echo "  build_ws  Build ROS2 workspace inside container"
    echo "  test      Run all tests"
    echo "  quick     Run quick tests (unit tests only)"
    echo "  integration Run full integration test"
    echo "  logs      Show container logs"
    echo "  clean     Remove container and images"
    echo "  all       Build image, start container, build workspace, run tests"
    echo ""
    echo "Examples:"
    echo "  $0 build          # Build Docker image"
    echo "  $0 shell          # Enter container"
    echo "  $0 test           # Run all tests"
    echo "  $0 all            # Full setup and test"
}

# Full setup
full_setup() {
    log_info "Running full setup..."
    build_image
    start_container
    sleep 2
    build_workspace
    run_tests
    log_info "Full setup complete! Use './run_docker.sh shell' to enter the container."
}

# Main
case "${1:-}" in
    build)
        build_image
        ;;
    start)
        start_container
        ;;
    stop)
        stop_container
        ;;
    shell)
        enter_shell
        ;;
    build_ws)
        build_workspace
        ;;
    test)
        run_tests
        ;;
    quick)
        quick_test
        ;;
    integration)
        integration_test
        ;;
    logs)
        show_logs
        ;;
    clean)
        clean_all
        ;;
    all)
        full_setup
        ;;
    *)
        print_usage
        ;;
esac
