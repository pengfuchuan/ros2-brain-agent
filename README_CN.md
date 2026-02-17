# ROS2 Brain Agent

> 一个可治理的 Brain-Cerebellum 机器人智能体架构

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

**[English](README.md)**

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

## 包结构

| 包名 | 说明 |
|------|------|
| `cmm_interfaces` | ROS2 消息/服务/动作接口定义 |
| `cmm_brain` | Brain 层核心节点（对话、LLM、记忆、工具路由） |
| `cmm_cerebellum` | Cerebellum 层技能服务（世界状态、技能执行） |
| `cmm_io` | 语音输入输出（ASR/TTS） |

## 快速开始

### 使用 Docker（推荐）

使用 Docker 可以快速搭建开发和测试环境：

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

# 其他命令
./run_docker.sh quick        # 快速单元测试
./run_docker.sh integration  # 完整集成测试
./run_docker.sh logs         # 查看容器日志
./run_docker.sh stop         # 停止容器
./run_docker.sh clean        # 清理容器和镜像
```

#### Docker 命令一览

| 命令 | 说明 |
|------|------|
| `./run_docker.sh build` | 构建 Docker 镜像 |
| `./run_docker.sh start` | 启动容器 |
| `./run_docker.sh stop` | 停止容器 |
| `./run_docker.sh shell` | 进入容器 shell |
| `./run_docker.sh build_ws` | 构建 ROS2 工作空间 |
| `./run_docker.sh test` | 运行所有测试 |
| `./run_docker.sh quick` | 快速单元测试 |
| `./run_docker.sh integration` | 完整集成测试 |
| `./run_docker.sh all` | 一键构建、启动、测试 |
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

### 环境要求（不使用 Docker）

- ROS2 Humble 或更高版本
- Python 3.10+
- Nav2（可选，用于导航功能）
- MoveIt2（可选，用于机械臂控制）

### 编译

```bash
# 创建工作空间
mkdir -p ros2_ws/src
cd ros2_ws/src

# 克隆仓库
git clone https://github.com/your-org/ros2-brain-agent.git

# 编译
cd ..
colcon build --symlink-install

# 加载环境
source install/setup.bash
```

### 配置

1. 设置 LLM API 凭证：
```bash
export LLM_API_KEY="your-api-key"
export LLM_BASE_URL="https://api.openai.com/v1"  # 可选
export LLM_MODEL="gpt-4o"  # 可选
```

2. 配置工具：`configs/tools.yaml`
3. 配置 LLM 提供者：`configs/providers.yaml`

### 运行

```bash
# 启动所有节点
ros2 launch cmm_brain brain_agent.launch.py

# 启动并启用语音
ros2 launch cmm_brain brain_agent.launch.py enable_asr:=true enable_tts:=true

# 以 dry-run 模式启动（不执行真实机器人动作）
ros2 launch cmm_brain brain_agent.launch.py dry_run:=true

# 或单独运行各节点
ros2 run cmm_brain dialog_manager_node
ros2 run cmm_brain llm_orchestrator_node
ros2 run cmm_brain tool_router_node
ros2 run cmm_brain memory_node
ros2 run cmm_cerebellum world_state_node
ros2 run cmm_cerebellum skill_server_node
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
├── configs/
│   ├── tools.yaml           # 工具注册表
│   ├── providers.yaml       # LLM 提供者配置
│   └── logging.yaml         # 日志配置
├── launch/                  # 启动文件
├── memory/                  # 记忆存储目录
└── tests/                   # 测试套件
```

## ROS2 接口参考

### 消息类型

- `DialogEvent.msg` - 对话事件，用于 /dialog/events 话题
- `WorldState.msg` - 机器人世界状态
- `ToolCall.msg` - 工具调用规范
- `ErrorInfo.msg` - 统一错误信息

### 服务类型

- `WorldStateQuery.srv` - 查询机器人世界状态
- `MemoryQuery.srv` - 查询会话记忆
- `ToolExecute.srv` - 同步执行工具

### 动作类型

- `SkillExecute.action` - 执行技能并获取反馈

## 话题列表

| 话题 | 类型 | 说明 |
|------|------|------|
| `/dialog/user_input` | String | 用户输入（文本或 JSON） |
| `/dialog/llm_response` | String | LLM 响应（JSON 格式） |
| `/dialog/events` | DialogEvent | 对话事件流 |
| `/tool/execute` | String | 工具执行请求 |
| `/tool/result` | String | 工具执行结果 |
| `/skill/execute` | String | 技能执行请求 |
| `/world_state/current` | WorldState | 当前世界状态 |
| `/world_state/update` | String | 世界状态更新 |

## LLM 输出格式

LLM 必须输出结构化 JSON：

```json
{
  "assistant_text": "对用户的回复文本",
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

## 错误码

| 错误码 | 类别 | 说明 |
|--------|------|------|
| `OBJECT_NOT_FOUND` | 感知 | 目标物体未检测到 |
| `NAV_TIMEOUT` | 导航 | 导航超时 |
| `LOCALIZATION_UNSTABLE` | 导航 | 定位质量过低 |
| `GRASP_FAILED` | 操作 | 抓取失败 |
| `SAFETY_ESTOP` | 安全 | 急停触发 |
| `TOOL_NOT_FOUND` | 系统 | 请求的工具未注册 |
| `RATE_LIMITED` | 系统 | 触发限流 |
| `INVALID_ARGS` | 系统 | 工具参数无效 |

## 测试

```bash
# 运行测试
colcon test --packages-select cmm_brain

# 仿真模式测试
ros2 launch cmm_brain brain_agent.launch.py dry_run:=true
```

### 文本模式演示

```bash
# 发布测试消息
ros2 topic pub /dialog/user_input std_msgs/String "{data: '{\"text\": \"导航到厨房\", \"session_id\": \"test1\"}'}" --once
```

## 扩展开发

### 添加新工具

1. 在 `configs/tools.yaml` 中添加工具定义：
```yaml
tools:
  my_tool:
    type: primitive
    description: "我的自定义工具"
    category: custom
    json_schema:
      type: object
      properties:
        param1: { type: string }
      required: [param1]
    permission_level: safe
    timeout_sec: 30.0
```

2. 在 `cmm_cerebellum/skills/` 中实现技能
3. 在 `skill_server_node.py` 中注册

### 添加新 LLM 提供者

1. 在 `configs/providers.yaml` 中添加配置
2. 在 `llm_provider.py` 中实现继承自 `LLMProvider` 的类

## 路线图

- [ ] SQLite 记忆后端
- [ ] Redis 记忆后端
- [ ] 向量语义记忆
- [ ] 多机器人支持
- [ ] Web 管理面板

## 贡献指南

欢迎贡献代码！请阅读贡献指南了解更多信息。

## 许可证

Apache-2.0
