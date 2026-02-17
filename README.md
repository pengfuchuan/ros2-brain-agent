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
- **Tool Governance**: Permission control, rate limiting, audit, dry-run mode
- **Skill Framework**: Primitive/Skill/Task three-layer capability model

## Quick Start

### Using Docker (Recommended)

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
```

### Build from Source

```bash
# Create workspace
mkdir -p ros2_ws/src && cd ros2_ws/src
git clone https://github.com/iampfc/ros2-brain-agent.git
cd ..
colcon build --symlink-install
source install/setup.bash
```

### Configuration

```bash
export LLM_API_KEY="your-api-key"
```

### Run

```bash
# Launch all nodes
ros2 launch cmm_brain brain_agent.launch.py

# Launch in dry-run mode
ros2 launch cmm_brain brain_agent.launch.py dry_run:=true
```

## Packages

| Package | Description |
|---------|-------------|
| `cmm_interfaces` | ROS2 msg/srv/action interface definitions |
| `cmm_brain` | Brain layer core nodes |
| `cmm_cerebellum` | Cerebellum layer skill services |
| `cmm_io` | Voice IO (ASR/TTS) |

## Testing

```bash
./run_docker.sh test           # All tests
./run_docker.sh integration    # Integration test
```

## Roadmap

- [ ] SQLite memory backend
- [ ] Redis memory backend
- [ ] Vector-based semantic memory
- [ ] Multi-robot support
- [ ] Web dashboard

## License

Apache-2.0

<p align="center"><a href="#中文">切换到中文 →</a></p>

</details>

---

<a name="中文"></a>

<details>
<summary><b>🇨🇳 中文</b></summary>

## 概述

ROS2 Brain Agent 是一个可工程化、可治理、可扩展的 ROS2 Agent 架构参考实现。采用 Brain-Cerebellum（大脑-小脑）分层架构，将认知规划与运动执行解耦。

### 架构设计

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

### 核心特性

- **Brain 层（大脑）**：对话管理、LLM 调用编排、记忆系统、工具路由
- **Cerebellum 层（小脑）**：技能执行、世界状态管理、错误恢复
- **记忆系统**：基于文件系统的可扩展记忆存储
  - 短期记忆 (turns.jsonl)
  - 会话摘要 (summary.json)
  - 用户事实 (facts.json)
  - 事件日志 (events.jsonl)
- **工具治理**：权限控制、限流策略、审计日志、dry-run 模式
- **技能框架**：Primitive/Skill/Task 三层能力模型

## 快速开始

### 使用 Docker（推荐）

```bash
# 一键构建、启动并运行测试
./run_docker.sh all

# 或者分步执行：
./run_docker.sh build      # 构建 Docker 镜像
./run_docker.sh start      # 启动容器
./run_docker.sh build_ws   # 构建 ROS2 工作空间
./run_docker.sh test       # 运行测试

# 进入容器 shell
./run_docker.sh shell
```

### 从源码编译

```bash
# 创建工作空间
mkdir -p ros2_ws/src && cd ros2_ws/src
git clone https://github.com/iampfc/ros2-brain-agent.git
cd ..
colcon build --symlink-install
source install/setup.bash
```

### 配置

```bash
export LLM_API_KEY="your-api-key"
```

### 运行

```bash
# 启动所有节点
ros2 launch cmm_brain brain_agent.launch.py

# 以 dry-run 模式启动
ros2 launch cmm_brain brain_agent.launch.py dry_run:=true
```

## 包结构

| 包名 | 说明 |
|------|------|
| `cmm_interfaces` | ROS2 消息/服务/动作接口定义 |
| `cmm_brain` | Brain 层核心节点 |
| `cmm_cerebellum` | Cerebellum 层技能服务 |
| `cmm_io` | 语音输入输出（ASR/TTS） |

## 测试

```bash
./run_docker.sh test           # 所有测试
./run_docker.sh integration    # 集成测试
```

## 路线图

- [ ] SQLite 记忆后端
- [ ] Redis 记忆后端
- [ ] 向量语义记忆
- [ ] 多机器人支持
- [ ] Web 管理面板

## 许可证

Apache-2.0

<p align="center"><a href="#english">← Switch to English</a></p>

</details>
