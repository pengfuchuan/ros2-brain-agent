# ROS2 Brain Agent

> A Governable Brain-Cerebellum Agent Architecture for ROS2

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

<p align="center">
  <a href="#english">English</a> | <a href="#中文">中文</a>
</p>

---

<a name="english"></a>

<details open>
<summary><b>🇺🇸 English</b></summary>

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

### Features

- **Brain Layer**: Dialog management, LLM orchestration, memory system, tool routing
- **Cerebellum Layer**: Skill execution, world state management, error recovery
- **Memory System**: File-based extensible memory storage
  - Working Memory (turns.jsonl)
  - Session Summary (summary.json)
  - User Facts (facts.json)
  - Event Log (events.jsonl)
- **Tool Governance**: Permission control, rate limiting, audit logging, dry-run mode
- **Skill Framework**: Primitive/Skill/Task three-layer capability model
- **Web UI**: Browser-based dialog management console with real-time ROS2 integration

## Quick Start

### Prerequisites

- Docker and Docker Compose
- LLM API Key (Alibaba Cloud DashScope, OpenAI, etc.)

### 1. Configure LLM

Create a `.env` file in the project root:

```bash
# .env file
LLM_API_KEY=your-api-key-here
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen3-max-2026-01-23
```

### 2. Using Docker (Recommended)

```bash
# One-click build, start, and test
./run_docker.sh all

# Or step by step:
./run_docker.sh build      # Build Docker image
./run_docker.sh start      # Start container with port 8080, 9090 exposed
./run_docker.sh build_ws   # Build ROS2 workspace
./run_docker.sh test       # Run tests

# Start Web UI
./run_docker.sh web

# Monitor ROS2 events
./run_docker.sh monitor
```

### 3. Using Docker Compose

```bash
# Start all services (rosbridge + ROS2 nodes)
docker-compose up -d

# View logs
docker-compose logs -f
```

### 4. Access Web UI

Open http://localhost:8081 in your browser.

## Web UI Features

The Web UI provides a complete dialog management console:

- **Chat Interface**: Send messages and receive AI responses with execution plans
- **Session Management**: Create, view, and manage conversation sessions
- **Event Monitoring**: Real-time ROS2 event publishing and monitoring
- **Performance Analysis**: View response times, token usage, and error rates

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/chat` | POST | Send a chat message |
| `/api/sessions` | GET | List all sessions |
| `/api/session/<id>` | GET | Get session details |
| `/api/mode` | GET/POST | Get/set execution mode (simulation/ros2) |
| `/api/world_state` | GET | Get current robot state |

### Example API Usage

```bash
# Send a chat message
curl -X POST http://localhost:8081/api/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test", "message": "Navigate to kitchen", "dry_run": false}'
```

## ROS2 Integration

### Topics

| Topic | Type | Description |
|-------|------|-------------|
| `/dialog/events` | std_msgs/String | Dialog events (turn_start, llm_result, skill_execute, turn_end) |
| `/dialog/llm_response` | std_msgs/String | LLM responses |
| `/world_state/current` | std_msgs/String | Robot world state |
| `/skill/execute` | std_msgs/String | Skill execution requests |
| `/tool/execute` | std_msgs/String | Tool execution requests |

### Monitor Events

```bash
# Enter container
docker exec -it ros2-brain-agent bash
source /opt/ros/humble/setup.bash

# Listen to dialog events
ros2 topic echo /dialog/events --full-length

# Or use the monitor script
python3 scripts/monitor.py --events

# Or use the event viewer for formatted output
python3 scripts/event_viewer.py
```

## Build from Source

```bash
# Create workspace
mkdir -p ros2_ws/src && cd ros2_ws/src
git clone https://github.com/iampfc/ros2-brain-agent.git
cd ..
colcon build --symlink-install
source install/setup.bash
```

## Project Structure

```
ros2-brain-agent/
├── packages/
│   ├── cmm_interfaces/    # ROS2 message/service/action definitions
│   ├── cmm_brain/          # Brain layer core nodes
│   ├── cmm_cerebellum/     # Cerebellum layer skill servers
│   └── cmm_io/             # Voice input/output (ASR/TTS)
├── scripts/
│   ├── dialog_web.py       # Web UI server
│   ├── monitor.py          # ROS2 topic monitor
│   ├── event_viewer.py     # Formatted event viewer
│   └── ros2_bridge_client.py # WebSocket bridge client
├── configs/
│   ├── providers.yaml      # LLM provider configuration
│   └── tools.yaml           # Tool definitions
├── memory/                  # Memory storage directory
├── .env                     # LLM API configuration
├── docker-compose.yml       # Docker Compose configuration
└── run_docker.sh            # Docker management script
```

## Testing

```bash
./run_docker.sh test           # All tests
./run_docker.sh integration    # Integration test
./run_docker.sh quick          # Quick unit tests
```

## Documentation

- [ROS2 Commands Reference](docs/ROS2_COMMANDS.md)
- [Test Demo Guide](docs/TEST_DEMO.md)

## Roadmap

- [ ] SQLite memory backend
- [ ] Redis memory backend
- [ ] Vector semantic memory
- [ ] Multi-robot support
- [x] Web management panel
- [x] ROS2 event publishing
- [x] Real-time monitoring

## License

Apache-2.0

<p align="center"><a href="#english">← Back to Top</a></p>

</details>

---

<a name="中文"></a>

<details>
<summary><b>🇨🇳 中文</b></summary>

## 概述

ROS2 Brain Agent 是一个工程级的、可治理的、可扩展的 ROS2 Agent 架构参考实现。它采用大脑-小脑分层架构，将认知规划与运动执行解耦。

### 架构

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

### 特性

- **Brain 层**：对话管理、LLM 编排、记忆系统、工具路由
- **Cerebellum 层**：技能执行、世界状态管理、错误恢复
- **记忆系统**：基于文件的可扩展记忆存储
  - 工作记忆 (turns.jsonl)
  - 会话摘要 (summary.json)
  - 用户事实 (facts.json)
  - 事件日志 (events.jsonl)
- **工具治理**：权限控制、限流策略、审计日志、dry-run 模式
- **技能框架**：Primitive/Skill/Task 三层能力模型
- **Web UI**：基于浏览器的对话管理控制台，支持实时 ROS2 集成

## 快速开始

### 前置条件

- Docker 和 Docker Compose
- LLM API Key（阿里云百炼、OpenAI 等）

### 1. 配置 LLM

在项目根目录创建 `.env` 文件：

```bash
# .env 文件
LLM_API_KEY=your-api-key-here
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen3-max-2026-01-23
```

### 2. 使用 Docker（推荐）

```bash
# 一键构建、启动并运行测试
./run_docker.sh all

# 或者分步执行：
./run_docker.sh build      # 构建 Docker 镜像
./run_docker.sh start      # 启动容器（暴露端口 8080, 9090）
./run_docker.sh build_ws   # 构建 ROS2 工作空间
./run_docker.sh test       # 运行测试

# 启动 Web UI
./run_docker.sh web

# 监听 ROS2 事件
./run_docker.sh monitor
```

### 3. 使用 Docker Compose

```bash
# 启动所有服务（rosbridge + ROS2 节点）
docker-compose up -d

# 查看日志
docker-compose logs -f
```

### 4. 访问 Web UI

在浏览器中打开 http://localhost:8081

## Web UI 功能

Web UI 提供完整的对话管理控制台：

- **聊天界面**：发送消息并接收带有执行计划的 AI 响应
- **会话管理**：创建、查看和管理对话会话
- **事件监控**：实时 ROS2 事件发布和监控
- **性能分析**：查看响应时间、Token 使用量和错误率

### API 端点

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/chat` | POST | 发送聊天消息 |
| `/api/sessions` | GET | 列出所有会话 |
| `/api/session/<id>` | GET | 获取会话详情 |
| `/api/mode` | GET/POST | 获取/设置执行模式 (simulation/ros2) |
| `/api/world_state` | GET | 获取当前机器人状态 |

### API 使用示例

```bash
# 发送聊天消息
curl -X POST http://localhost:8081/api/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test", "message": "导航到厨房", "dry_run": false}'
```

## ROS2 集成

### 话题

| 话题 | 类型 | 描述 |
|------|------|------|
| `/dialog/events` | std_msgs/String | 对话事件 (turn_start, llm_result, skill_execute, turn_end) |
| `/dialog/llm_response` | std_msgs/String | LLM 响应 |
| `/world_state/current` | std_msgs/String | 机器人世界状态 |
| `/skill/execute` | std_msgs/String | 技能执行请求 |
| `/tool/execute` | std_msgs/String | 工具执行请求 |

### 监控事件

```bash
# 进入容器
docker exec -it ros2-brain-agent bash
source /opt/ros/humble/setup.bash

# 监听对话事件
ros2 topic echo /dialog/events --full-length

# 或使用监控脚本
python3 scripts/monitor.py --events

# 或使用格式化事件查看器
python3 scripts/event_viewer.py
```

## 从源码编译

```bash
# 创建工作空间
mkdir -p ros2_ws/src && cd ros2_ws/src
git clone https://github.com/iampfc/ros2-brain-agent.git
cd ..
colcon build --symlink-install
source install/setup.bash
```

## 测试

```bash
./run_docker.sh test           # 所有测试
./run_docker.sh integration    # 集成测试
./run_docker.sh quick          # 快速单元测试
```

## 文档

- [ROS2 命令参考](docs/ROS2_COMMANDS.md)
- [测试演示指南](docs/TEST_DEMO.md)

## 路线图

- [ ] SQLite 记忆后端
- [ ] Redis 记忆后端
- [ ] 向量语义记忆
- [ ] 多机器人支持
- [x] Web 管理面板
- [x] ROS2 事件发布
- [x] 实时监控

## 许可证

Apache-2.0

<p align="center"><a href="#中文">← 返回顶部</a></p>

</details>
