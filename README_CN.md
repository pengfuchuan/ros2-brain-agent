# ROS2 Brain Agent

> 一个可治理的 Brain-Cerebellum 机器人智能体架构

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

**[English Version](README.md)**

> 💡 提示：GitHub README 页面支持 [中英文切换](README.md)，点击上方链接可切换语言。

## 概述

ROS2 Brain Agent 是一个可工程化、可治理、可扩展的 ROS2 Agent 架构参考实现。采用 Brain-Cerebellum（大脑-小脑）分层架构，将认知规划与运动执行解耦，实现更清晰的责任分离和更好的可维护性。

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

### 语音交互链路

```
语音识别(ASR)  →  大脑(Brain)  →  语音合成(TTS)
```

## 核心特性

- **Brain 层（大脑）**：对话管理、LLM 调用编排、记忆系统、工具路由
- **Cerebellum 层（小脑）**：技能执行、世界状态管理、错误恢复
- **记忆系统**：基于文件系统的可扩展记忆存储
  - 短期记忆 (turns.jsonl) - 对话轮次记录
  - 会话摘要 (summary.json) - 长对话压缩
  - 用户事实 (facts.json) - 用户偏好存储
  - 事件日志 (events.jsonl) - 审计追踪
- **工具治理**：权限控制、限流策略、审计日志、dry-run 模式
- **技能框架**：Primitive/Skill/Task 三层能力模型
- **错误恢复**：统一错误码体系、补偿动作、自动重试机制
- **Web UI**：基于浏览器的对话管理控制台，支持实时 ROS2 集成

## 包结构

| 包名 | 说明 |
|------|------|
| `cmm_interfaces` | ROS2 消息/服务/动作接口定义 |
| `cmm_brain` | Brain 层核心节点（对话、LLM、记忆、工具路由） |
| `cmm_cerebellum` | Cerebellum 层技能服务（世界状态、技能执行） |
| `cmm_io` | 语音输入输出（ASR/TTS） |

## 快速开始

### 前置条件

- Docker 和 Docker Compose
- LLM API Key（阿里云百炼、OpenAI 等）

### 1. 配置 LLM

在项目根目录创建 `.env` 文件：

```bash
# .env 配置文件
LLM_API_KEY=your-api-key-here
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen3-max-2026-01-23

# OpenAI 配置示例：
# LLM_BASE_URL=https://api.openai.com/v1
# LLM_MODEL=gpt-4o
```

### 2. 使用 Docker（推荐）

```bash
# 一键构建、启动、测试并启动 Web UI
./run_docker.sh all

# 完成后访问：
# - Web UI: http://localhost:8081
# - Rosbridge: ws://localhost:9090
```

**或分步执行：**

```bash
./run_docker.sh build      # 构建 Docker 镜像
./run_docker.sh start      # 启动容器（端口 8081, 9090）
./run_docker.sh build_ws   # 构建 ROS2 工作空间
./run_docker.sh test       # 运行测试（16+ 单元测试）
./run_docker.sh web        # 启动 Web UI

# 其他常用命令：
./run_docker.sh monitor    # 监听 ROS2 事件
./run_docker.sh shell      # 进入容器 shell
./run_docker.sh logs       # 查看容器日志
./run_docker.sh stop       # 停止容器
```

#### Docker 命令一览

| 命令 | 说明 |
|------|------|
| `./run_docker.sh all` | 一键构建、启动、测试、启动 Web UI |
| `./run_docker.sh build` | 构建 Docker 镜像 |
| `./run_docker.sh start` | 启动容器 |
| `./run_docker.sh stop` | 停止容器 |
| `./run_docker.sh shell` | 进入容器 shell |
| `./run_docker.sh web` | 启动 Web UI |
| `./run_docker.sh monitor` | 监听 ROS2 事件 |
| `./run_docker.sh build_ws` | 构建 ROS2 工作空间 |
| `./run_docker.sh test` | 运行所有测试（16+ 单元测试） |
| `./run_docker.sh quick` | 快速单元测试 |
| `./run_docker.sh integration` | 完整集成测试 |
| `./run_docker.sh logs` | 查看容器日志 |
| `./run_docker.sh clean` | 清理容器和镜像 |

#### 使用 docker-compose

```bash
# 启动
docker-compose up -d

# 进入容器
docker exec -it ros2-brain-agent bash

# 停止
docker-compose down
```

### 3. 访问 Web UI

在浏览器中打开 http://localhost:8081

## Web UI 功能

基于 Web 的 Brain Agent 控制台，支持完整的认知规划与执行流程。

### 架构设计

```
用户输入 → [意图理解] → [规划] → [执行] → 响应
              ↓            ↓        ↓
        LLM 解析     生成 Action Plan   仿真/实机执行
                    (JSON 格式)
```

### 功能特性

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

### 功能页面

| 页面 | 路径 | 说明 |
|------|------|------|
| 聊天测试 | `/chat` | Brain Agent 聊天界面（规划+执行） |
| 聊天会话 | `/chat/{id}` | 指定会话的聊天界面 |
| 会话列表 | `/` | 所有会话列表，支持搜索 |
| 统计概览 | `/stats` | 全局统计数据 |
| 会话详情 | `/session/{id}` | 对话轮次查看 |
| 事件日志 | `/session/{id}/events` | 事件记录，支持过滤 |
| 性能分析 | `/session/{id}/analyze` | 响应质量分析报告 |
| 事实数据 | `/session/{id}/facts` | 会话事实存储 |

### 可用原语与技能

| 类别 | 动作 |
|------|------|
| 导航 | `nav2.goto`, `nav2.stop` |
| 操作 | `arm.move_to`, `arm.grasp`, `arm.release` |
| 感知 | `perception.detect` |
| 复合技能 | `skill.pick_object`, `skill.deliver_object`, `skill.approach_for_pick` |

## ROS2 集成

### 话题列表

| 话题 | 类型 | 说明 |
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

## 项目结构

```
ros2-brain-agent/
├── packages/
│   ├── cmm_interfaces/      # ROS2 接口定义
│   │   ├── msg/             # DialogEvent, WorldState, ToolCall, ErrorInfo
│   │   ├── srv/             # WorldStateQuery, MemoryQuery, ToolExecute
│   │   └── action/          # SkillExecute
│   ├── cmm_brain/           # Brain 层
│   │   ├── dialog_manager_node.py    # 对话管理
│   │   ├── llm_orchestrator_node.py  # LLM 编排
│   │   ├── tool_router_node.py       # 工具路由
│   │   ├── memory_node.py            # 记忆服务
│   │   ├── llm_provider.py           # LLM 提供者
│   │   ├── summarizer.py             # 摘要生成
│   │   └── memory/
│   │       ├── memory_store.py       # 记忆抽象接口
│   │       └── filesystem_store.py   # 文件系统实现
│   ├── cmm_cerebellum/      # Cerebellum 层
│   │   ├── world_state_node.py       # 世界状态
│   │   ├── skill_server_node.py      # 技能服务
│   │   └── skills/
│   │       ├── base_skill.py         # 技能基类
│   │       ├── nav_primitives.py     # 导航原语
│   │       ├── arm_primitives.py     # 机械臂原语
│   │       └── manipulation_skills.py # 操作技能
│   └── cmm_io/              # IO 层
│       ├── asr_client_node.py        # 语音识别
│       └── tts_client_node.py        # 语音合成
├── scripts/
│   ├── dialog_web.py         # Web UI 服务器
│   ├── dialog_viewer.py      # 命令行会话查看器
│   ├── monitor.py            # ROS2 话题监控
│   ├── event_viewer.py       # 格式化事件查看器
│   └── ros2_bridge_client.py # WebSocket 桥接客户端
├── configs/
│   ├── tools.yaml           # 工具注册表
│   ├── providers.yaml       # LLM 提供者配置
│   └── logging.yaml         # 日志配置
├── tests/                   # 单元测试（16+ 测试）
├── launch/                  # 启动文件
├── memory/                  # 记忆存储目录
├── docs/                    # 文档
│   ├── ROS2_COMMANDS.md     # ROS2 命令参考
│   ├── TEST_DEMO.md         # 测试演示指南
│   └── project-requirements/ # 项目需求文档
├── .env.example             # 环境变量模板
├── docker-compose.yml       # Docker Compose 配置
└── run_docker.sh            # Docker 管理脚本
```

## 测试

```bash
./run_docker.sh test           # 运行所有测试（16+ 单元测试）
./run_docker.sh quick          # 仅快速单元测试
./run_docker.sh integration    # 完整集成测试
```

**测试覆盖：**
- 记忆存储（FileSystemMemoryStore）
- LLM 提供者（MockLLMProvider、JSONSchemaValidator）
- ROS2 节点（Memory Node 等）

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

## 贡献指南

欢迎贡献代码！请阅读贡献指南了解更多信息。

## 许可证

Apache-2.0
