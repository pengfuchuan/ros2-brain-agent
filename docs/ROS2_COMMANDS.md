# ROS2 命令速查表

> Brain Agent ROS2 系统常用命令参考

## 快速入口

```bash
# 进入容器
docker exec -it ros2-brain-agent bash

# 加载环境 (进入容器后执行)
source /opt/ros/humble/setup.bash && source /ros2_ws/install/setup.bash
```

---

## 节点操作

| 命令 | 说明 |
|------|------|
| `ros2 node list` | 列出所有节点 |
| `ros2 node info /<node_name>` | 查看节点详细信息 |
| `ros2 param list /<node_name>` | 列出节点参数 |
| `ros2 param get /<node_name> <param>` | 获取参数值 |
| `ros2 param set /<node_name> <param> <value>` | 设置参数值 |

### 示例

```bash
# 查看对话管理节点信息
ros2 node info /dialog_manager_node

# 查看记忆路径参数
ros2 param get /dialog_manager_node memory_base_path
```

---

## 话题操作

| 命令 | 说明 |
|------|------|
| `ros2 topic list` | 列出所有话题 |
| `ros2 topic list -t` | 列出话题及类型 |
| `ros2 topic type /<topic>` | 查看话题类型 |
| `ros2 topic info /<topic>` | 查看话题信息 |
| `ros2 topic echo /<topic>` | 监听话题消息 |
| `ros2 topic echo /<topic> --once` | 监听一条消息 |
| `ros2 topic pub /<topic> <type> '<msg>' --once` | 发布一条消息 |
| `ros2 topic hz /<topic>` | 查看发布频率 |
| `ros2 topic bw /<topic>` | 查看带宽占用 |

### 核心话题

| 话题 | 类型 | 说明 |
|------|------|------|
| `/dialog/user_input` | `std_msgs/String` | 用户输入 |
| `/dialog/llm_response` | `std_msgs/String` | LLM 响应 |
| `/dialog/events` | `cmm_interfaces/msg/DialogEvent` | 对话事件 |
| `/skill/execute` | `cmm_interfaces/action/SkillExecute` | 技能执行 |
| `/skill/result` | `std_msgs/String` | 技能结果 |
| `/tool/execute` | `std_msgs/String` | 工具执行 |
| `/tool/result` | `std_msgs/String` | 工具结果 |
| `/world_state/current` | `cmm_interfaces/msg/WorldState` | 世界状态 |
| `/memory/write` | `std_msgs/String` | 记忆写入 |

### 示例

```bash
# 监听对话事件
ros2 topic echo /dialog/events

# 发送用户消息
ros2 topic pub /dialog/user_input std_msgs/String \
  '{"data": "{\"text\": \"导航到厨房\", \"session_id\": \"test\"}"}' --once

# 监听 LLM 响应
ros2 topic echo /dialog/llm_response --once

# 查看世界状态
ros2 topic echo /world_state/current --once
```

---

## 服务操作

| 命令 | 说明 |
|------|------|
| `ros2 service list` | 列出所有服务 |
| `ros2 service type /<service>` | 查看服务类型 |
| `ros2 service call /<service> <type> '<request>'` | 调用服务 |

### 核心服务

| 服务 | 说明 |
|------|------|
| `/memory/query` | 记忆查询 |
| `/world_state/query` | 世界状态查询 |
| `/tool/execute_sync` | 同步工具执行 |

### 示例

```bash
# 查询记忆
ros2 service call /memory/query cmm_interfaces/srv/MemoryQuery \
  '{"query_type": "get_recent", "session_id": "default", "limit": 10}'

# 查询世界状态
ros2 service call /world_state/query cmm_interfaces/srv/WorldStateQuery \
  '{"query_type": "full"}'
```

---

## 动作操作

| 命令 | 说明 |
|------|------|
| `ros2 action list` | 列出所有动作 |
| `ros2 action type /<action>` | 查看动作类型 |
| `ros2 action send_goal /<action> <type> '<goal>'` | 发送目标 |
| `ros2 action send_goal /<action> <type> '<goal>' --feedback` | 发送目标并接收反馈 |

### 示例

```bash
# 执行技能
ros2 action send_goal /skill/execute cmm_interfaces/action/SkillExecute \
  '{"skill_name": "nav2.goto", "parameters": "{\"x\": 2.0, \"y\": 3.0}"}'
```

---

## 文件与存储

| 路径 | 说明 |
|------|------|
| `/ros2_ws/memory/sessions/` | 会话存储目录 |
| `/ros2_ws/memory/sessions/<id>/turns.jsonl` | 对话轮次 |
| `/ros2_ws/memory/sessions/<id>/events.jsonl` | 事件日志 |
| `/ros2_ws/memory/sessions/<id>/summary.json` | 会话摘要 |
| `/ros2_ws/memory/global/user_facts.json` | 用户事实 |
| `/ros2_ws/configs/` | 配置文件目录 |

### 示例

```bash
# 查看所有会话
ls /ros2_ws/memory/sessions/

# 查看会话对话
cat /ros2_ws/memory/sessions/default/turns.jsonl

# 查看事件日志
cat /ros2_ws/memory/sessions/default/events.jsonl

# 实时监控日志
tail -f /ros2_ws/memory/sessions/default/events.jsonl
```

---

## 系统管理

### 容器操作

```bash
# 启动容器
docker start ros2-brain-agent

# 停止容器
docker stop ros2-brain-agent

# 重启容器
docker restart ros2-brain-agent

# 查看容器日志
docker logs ros2-brain-agent

# 实时查看日志
docker logs -f ros2-brain-agent
```

### 节点启动

```bash
# 启动全部节点
ros2 launch cmm_brain brain_agent.launch.py

# 仿真模式启动
ros2 launch cmm_brain brain_agent.launch.py dry_run:=true

# 带语音启动
ros2 launch cmm_brain brain_agent.launch.py enable_asr:=true enable_tts:=true

# 启动 rosbridge
ros2 launch rosbridge_server rosbridge_websocket_launch.xml port:=9090
```

---

## 调试命令

```bash
# 查看 ROS2 日志
ros2 topic echo /rosout

# 查看参数事件
ros2 topic echo /parameter_events

# 检查 daemon 状态
ros2 daemon status

# 重启 daemon
ros2 daemon stop && ros2 daemon start

# 查看环境变量
env | grep ROS
env | grep RMW

# 检查 DDS 发现
ros2 node list --daemon-only
```

---

## 快速测试脚本

### 一键测试对话

```bash
# 发送消息并查看响应
ros2 topic pub /dialog/user_input std_msgs/String \
  '{"data": "{\"text\": \"你好\", \"session_id\": \"quick_test\"}"}' --once && \
sleep 2 && \
ros2 topic echo /dialog/llm_response --once
```

### 一键测试导航

```bash
# 发送导航命令
ros2 topic pub /dialog/user_input std_msgs.String \
  '{"data": "{\"text\": \"导航到坐标 (2.5, 3.0)\", \"session_id\": \"nav_test\"}"}' --once && \
sleep 3 && \
ros2 topic echo /world_state/current --once
```

### 查看系统状态

```bash
# 一键查看系统概览
echo "=== 节点 ===" && ros2 node list && \
echo "=== 话题 ===" && ros2 topic list && \
echo "=== 世界状态 ===" && ros2 topic echo /world_state/current --once
```

---

## Web UI API

```bash
# 获取世界状态
curl http://localhost:8080/api/world_state

# 获取当前模式
curl http://localhost:8080/api/mode

# 切换到仿真模式
curl -X POST http://localhost:8080/api/mode \
  -H "Content-Type: application/json" \
  -d '{"mode": "simulation"}'

# 切换到 ROS2 模式
curl -X POST http://localhost:8080/api/mode \
  -H "Content-Type: application/json" \
  -d '{"mode": "ros2", "rosbridge_url": "ws://localhost:9090"}'

# 发送聊天消息
curl -X POST http://localhost:8080/api/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "api_test", "message": "你好", "dry_run": true}'
```

---

## 故障排查

### 节点无法启动

```bash
# 检查依赖
ros2 pkg list | grep cmm

# 重新构建
cd /ros2_ws && colcon build --symlink-install
```

### 话题没有消息

```bash
# 检查发布者
ros2 topic info /dialog/user_input -v

# 检查频率
ros2 topic hz /dialog/events
```

### 服务调用失败

```bash
# 检查服务是否存在
ros2 service list | grep memory

# 检查服务节点
ros2 service node /memory/query
```
