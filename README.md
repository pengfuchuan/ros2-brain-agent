# ROS2 Brain Agent

> A Governable Brain-Cerebellum Agent Architecture for ROS2

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

**[中文文档](README_CN.md)**

## Overview

ROS2 Brain Agent is an engineering-grade, governable, and extensible ROS2 Agent architecture reference implementation. It adopts a Brain-Cerebellum layered architecture that decouples cognitive planning from motion execution.

### Architecture

```
                ┌────────────────────────┐
                │        Brain           │
                │ Dialog / Agent Core    │
                │ Plan / Memory / Tool   │
                └───────────┬────────────┘
                            │ SkillInvoke
                ┌───────────▼────────────┐
                │      Cerebellum        │
                │   Skill Server Layer   │
                │ Nav2 / MoveIt2 Adapter │
                └───────────┬────────────┘
                            │
                ┌───────────▼────────────┐
                │          ROS2          │
                │ Action / Service / TF  │
                └────────────────────────┘
```

### Voice Pipeline

```
ASR  →  Brain  →  TTS
```

## Features

- **Brain Layer**: Dialog management, LLM orchestration, memory system, tool routing
- **Cerebellum Layer**: Skill execution, world state management, error recovery
- **Memory System**: File-based extensible memory storage
  - Working Memory (turns.jsonl)
  - Session Summary (summary.json)
  - User Facts (facts.json)
  - Event Log (events.jsonl)
- **Tool Governance**: Permission control, rate limiting, audit, dry-run mode
- **Skill Framework**: Primitive/Skill/Task three-layer capability model
- **Error Recovery**: Unified error code system, compensation actions, retry mechanism

## Packages

| Package | Description |
|---------|-------------|
| `cmm_interfaces` | ROS2 msg/srv/action interface definitions |
| `cmm_brain` | Brain layer core nodes (dialog, LLM, memory, tool router) |
| `cmm_cerebellum` | Cerebellum layer skill services (world state, skill execution) |
| `cmm_io` | Voice IO (ASR/TTS) |

## Quick Start

### Using Docker (Recommended)

Docker provides a quick way to set up development and testing environment:

```bash
# One-click build, start, and test
./run_docker.sh all

# Or step by step:
./run_docker.sh build      # Build Docker image
./run_docker.sh start      # Start container
./run_docker.sh build_ws   # Build ROS2 workspace
./run_docker.sh test       # Run tests

# Enter container shell
./run_docker.sh shell

# Other commands
./run_docker.sh quick        # Quick unit tests
./run_docker.sh integration  # Full integration test
./run_docker.sh logs         # View container logs
./run_docker.sh stop         # Stop container
./run_docker.sh clean        # Clean up container and images
```

#### Docker Commands Reference

| Command | Description |
|---------|-------------|
| `./run_docker.sh build` | Build Docker image |
| `./run_docker.sh start` | Start container |
| `./run_docker.sh stop` | Stop container |
| `./run_docker.sh shell` | Enter container shell |
| `./run_docker.sh build_ws` | Build ROS2 workspace |
| `./run_docker.sh test` | Run all tests |
| `./run_docker.sh quick` | Quick unit tests |
| `./run_docker.sh integration` | Full integration test |
| `./run_docker.sh all` | One-click build, start, test |
| `./run_docker.sh clean` | Clean up container and images |

#### Using docker-compose

```bash
# Start
docker-compose up -d

# Enter container
docker exec -it ros2-brain-agent bash

# Stop
docker-compose down
```

### Prerequisites (Without Docker)

- ROS2 Humble or later
- Python 3.10+
- Nav2 (optional, for navigation)
- MoveIt2 (optional, for manipulation)

### Build

```bash
# Create workspace
mkdir -p ros2_ws/src
cd ros2_ws/src

# Clone repository
git clone https://github.com/your-org/ros2-brain-agent.git

# Build
cd ..
colcon build --symlink-install

# Source
source install/setup.bash
```

### Configuration

1. Set LLM API credentials:
```bash
export LLM_API_KEY="your-api-key"
export LLM_BASE_URL="https://api.openai.com/v1"  # optional
export LLM_MODEL="gpt-4o"  # optional
```

2. Configure tools in `configs/tools.yaml`
3. Configure providers in `configs/providers.yaml`

### Run

```bash
# Launch all nodes
ros2 launch cmm_brain brain_agent.launch.py

# Launch with voice enabled
ros2 launch cmm_brain brain_agent.launch.py enable_asr:=true enable_tts:=true

# Launch in dry-run mode (no real robot actions)
ros2 launch cmm_brain brain_agent.launch.py dry_run:=true

# Or run individual nodes
ros2 run cmm_brain dialog_manager_node
ros2 run cmm_brain llm_orchestrator_node
ros2 run cmm_brain tool_router_node
ros2 run cmm_brain memory_node
ros2 run cmm_cerebellum world_state_node
ros2 run cmm_cerebellum skill_server_node
```

## Project Structure

```
ros2-brain-agent/
├── packages/
│   ├── cmm_interfaces/      # ROS2 interfaces
│   │   ├── msg/             # DialogEvent, WorldState, ToolCall, ErrorInfo
│   │   ├── srv/             # WorldStateQuery, MemoryQuery, ToolExecute
│   │   └── action/          # SkillExecute
│   ├── cmm_brain/           # Brain layer
│   │   ├── dialog_manager_node.py
│   │   ├── llm_orchestrator_node.py
│   │   ├── tool_router_node.py
│   │   ├── memory_node.py
│   │   ├── llm_provider.py
│   │   ├── summarizer.py
│   │   └── memory/
│   │       ├── memory_store.py
│   │       └── filesystem_store.py
│   ├── cmm_cerebellum/      # Cerebellum layer
│   │   ├── world_state_node.py
│   │   ├── skill_server_node.py
│   │   └── skills/
│   │       ├── base_skill.py
│   │       ├── nav_primitives.py
│   │       ├── arm_primitives.py
│   │       └── manipulation_skills.py
│   └── cmm_io/              # IO layer
│       ├── asr_client_node.py
│       └── tts_client_node.py
├── configs/
│   ├── tools.yaml           # Tool registry
│   ├── providers.yaml       # LLM providers
│   └── logging.yaml         # Logging config
├── launch/                  # Launch files
├── memory/                  # Memory storage
└── tests/                   # Test suites
```

## ROS2 Interface Reference

### Messages

- `DialogEvent.msg` - Dialog event for /dialog/events topic
- `WorldState.msg` - Robot world state
- `ToolCall.msg` - Tool call specification
- `ErrorInfo.msg` - Unified error information

### Services

- `WorldStateQuery.srv` - Query robot world state
- `MemoryQuery.srv` - Query session memory
- `ToolExecute.srv` - Execute tool synchronously

### Actions

- `SkillExecute.action` - Execute skill with feedback

## Topics

| Topic | Type | Description |
|-------|------|-------------|
| `/dialog/user_input` | String | User input (text or JSON) |
| `/dialog/llm_response` | String | LLM response (JSON) |
| `/dialog/events` | DialogEvent | Dialog events |
| `/tool/execute` | String | Tool execution requests |
| `/tool/result` | String | Tool execution results |
| `/skill/execute` | String | Skill execution requests |
| `/world_state/current` | WorldState | Current world state |
| `/world_state/update` | String | World state updates |

## LLM Output Format

LLM must output structured JSON:

```json
{
  "assistant_text": "Response text to user",
  "plan": [
    {"step": 1, "action": "skill_name", "args": {...}}
  ],
  "tool_calls": [
    {"tool": "tool_name", "args": {...}}
  ],
  "memory_write": [
    {"key": "fact_key", "value": "fact_value", "type": "upsert"}
  ]
}
```

## Error Codes

| Code | Category | Description |
|------|----------|-------------|
| `OBJECT_NOT_FOUND` | perception | Target object not detected |
| `NAV_TIMEOUT` | navigation | Navigation timed out |
| `LOCALIZATION_UNSTABLE` | navigation | Localization quality too low |
| `GRASP_FAILED` | manipulation | Grasp action failed |
| `SAFETY_ESTOP` | safety | Emergency stop activated |
| `TOOL_NOT_FOUND` | system | Requested tool not registered |
| `RATE_LIMITED` | system | Rate limit exceeded |
| `INVALID_ARGS` | system | Invalid tool arguments |

## Testing

```bash
# Run tests
colcon test --packages-select cmm_brain

# Test with simulation
ros2 launch cmm_brain brain_agent.launch.py dry_run:=true
```

### Text Mode Demo

```bash
# Publish a test message
ros2 topic pub /dialog/user_input std_msgs/String "{data: '{\"text\": \"Navigate to kitchen\", \"session_id\": \"test1\"}'}" --once
```

## Extending

### Adding a New Tool

1. Add tool definition to `configs/tools.yaml`:
```yaml
tools:
  my_tool:
    type: primitive
    description: "My custom tool"
    category: custom
    json_schema:
      type: object
      properties:
        param1: { type: string }
      required: [param1]
    permission_level: safe
    timeout_sec: 30.0
```

2. Implement the skill in `cmm_cerebellum/skills/`
3. Register in `skill_server_node.py`

### Adding a New LLM Provider

1. Add provider config to `configs/providers.yaml`
2. Implement provider class extending `LLMProvider` in `llm_provider.py`

## Roadmap

- [ ] SQLite memory backend
- [ ] Redis memory backend
- [ ] Vector-based semantic memory
- [ ] Multi-robot support
- [ ] Web dashboard

## Contributing

Contributions are welcome! Please read our contributing guidelines.

## License

Apache-2.0
