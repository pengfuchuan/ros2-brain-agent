# 测试问题与监听命令

> 从 Web 发送问题，在 ROS2 容器中监听数据流

## 快速测试

### 方式一：使用 run_docker.sh（推荐）

```bash
# 终端 1: 启动容器和 Web UI
./run_docker.sh start   # 启动容器
./run_docker.sh web     # 启动 Web UI

# 终端 2: 监听 ROS2 事件
./run_docker.sh monitor

# 浏览器: 打开 http://localhost:8081/chat 发送消息
```

### 方式二：手动操作

```bash
# 终端 1: 进入容器启动监听
docker exec -it ros2-brain-agent bash
source /opt/ros/humble/setup.bash
source /ros2_ws/install/setup.bash
ros2 topic echo /dialog/events --full-length

# 终端 2: 通过 Web 或 API 发送消息
curl -X POST http://localhost:8081/api/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test", "message": "导航到厨房", "dry_run": false}'
```

---

## 测试问题列表

### 导航类

| 问题 | 预期动作 |
|------|----------|
| `请导航到厨房` | `nav2.goto` |
| `去客厅` | `nav2.goto` |
| `移动到坐标 (2.5, 3.0)` | `nav2.goto` |
| `停止移动` | `nav2.stop` |

### 操作类

| 问题 | 预期动作 |
|------|----------|
| `帮我拿桌上的水杯` | `skill.pick_object` |
| `把这个送到门口` | `skill.deliver_object` |
| `抓取红色物体` | `arm.grasp` |
| `释放物体` | `arm.release` |

### 感知类

| 问题 | 预期动作 |
|------|----------|
| `检测周围的人` | `perception.detect` |
| `看看桌上有什么` | `perception.detect` |
| `找到最近的水杯` | `perception.detect` |

### 混合任务

| 问题 | 预期动作 |
|------|----------|
| `去厨房拿一杯水给我` | `nav2.goto` → `skill.pick_object` → `nav2.goto` → `arm.release` |
| `检查客厅有没有人，然后回来` | `nav2.goto` → `perception.detect` → `nav2.goto` |

---

## 监听命令

### 完整事件流

```bash
# 方式一：使用 run_docker.sh
./run_docker.sh monitor

# 方式二：直接使用 ros2 topic
docker exec -it ros2-brain-agent bash -c "
source /opt/ros/humble/setup.bash &&
ros2 topic echo /dialog/events --full-length
"
```

### 特定话题监听

```bash
# 对话事件
ros2 topic echo /dialog/events --full-length

# LLM 响应
ros2 topic echo /dialog/llm_response

# 世界状态
ros2 topic echo /world_state/current

# 技能执行
ros2 topic echo /skill/execute
ros2 topic echo /skill/result

# 工具执行
ros2 topic echo /tool/execute
ros2 topic echo /tool/result
```

---

## 使用 monitor.py

```bash
# 监听所有话题（获取一条消息）
python3 scripts/monitor.py --all

# 持续监听对话事件
python3 scripts/monitor.py --events

# 持续监听世界状态
python3 scripts/monitor.py --state

# 监听技能执行
python3 scripts/monitor.py --skills

# 监听工具执行
python3 scripts/monitor.py --tools
```

---

## 使用 event_viewer.py（格式化输出）

```bash
# 运行格式化事件查看器
python3 scripts/event_viewer.py

# 发送测试消息
curl -X POST http://localhost:8081/api/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "viewer_test", "message": "导航到厨房", "dry_run": false}'
```

---

## 快速测试脚本

### 通过 API 发送测试

```bash
# 导航测试
curl -X POST http://localhost:8081/api/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test_nav", "message": "请导航到厨房", "dry_run": false}'

# 操作测试
curl -X POST http://localhost:8081/api/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test_pick", "message": "帮我拿桌子上的水杯", "dry_run": false}'

# 复合任务测试
curl -X POST http://localhost:8081/api/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test_complex", "message": "去厨房拿一杯水给我", "dry_run": false}'
```

---

## 数据流图

```
Web UI (8080)                    ROS2 Container
    │
    ▼
┌─────────────────┐
│ /api/chat       │
│ (Flask)         │
└────────┬────────┘
         │
         ▼
┌─────────────────┐         ┌──────────────────┐
│ LLM Provider    │         │ rosbridge        │
│ (qwen3-max)     │◄───────►│ (ws://9090)      │
└────────┬────────┘         └────────┬─────────┘
         │                           │
         │ JSON Plan                 │ ROS2 Topics
         ▼                           ▼
┌─────────────────┐         ┌──────────────────┐
│ Plan Executor   │────────►│ /dialog/events   │
│ (Simulation)    │         │ /skill/execute   │
└─────────────────┘         │ /world_state/*   │
                            └──────────────────┘
```

---

## 实时监控面板

### 多窗口监控 (tmux)

```bash
# 创建 tmux 会话
tmux new -s ros2-monitor

# 窗口 0: 对话事件
docker exec -it ros2-brain-agent bash -c "
source /opt/ros/humble/setup.bash &&
ros2 topic echo /dialog/events --full-length
"

# Ctrl+B C 创建新窗口
# 窗口 1: 世界状态
docker exec -it ros2-brain-agent bash -c "
source /opt/ros/humble/setup.bash &&
ros2 topic echo /world_state/current
"

# Ctrl+B C 创建新窗口
# 窗口 2: LLM 响应
docker exec -it ros2-brain-agent bash -c "
source /opt/ros/humble/setup.bash &&
ros2 topic echo /dialog/llm_response
"
```

---

## 预期输出示例

### 对话事件 (/dialog/events)

事件格式为 JSON 字符串，包含以下字段：

```json
{
  "header": {"stamp": {"sec": 1771932192, "nanosec": 190775763}, "frame_id": ""},
  "event_id": "evt_abc123",
  "session_id": "test_nav",
  "event_type": "turn_start | llm_result | skill_execute | turn_end",
  "source": "user | llm | executor",
  "payload_json": "{...}",
  "timestamp": {"sec": 1771932192, "nanosec": 190775763},
  "duration_ms": 1234,
  "success": true,
  "error_message": ""
}
```

### 事件类型说明

| 事件类型 | 来源 | 描述 |
|----------|------|------|
| `turn_start` | user | 用户发送消息 |
| `llm_result` | llm | LLM 处理完成，包含执行计划 |
| `skill_execute` | executor | 技能执行完成 |
| `turn_end` | llm | 对话轮次结束 |

### 世界状态 (/world_state/current)

```yaml
header:
  stamp: {sec: 1771932192, nanosec: 190775763}
  frame_id: "map"
localization_ok: true
nav_state: "IDLE"
robot_pose:
  position: {x: 0.0, y: 0.0, z: 0.0}
  orientation: {x: 0.0, y: 0.0, z: 0.0, w: 1.0}
arm_state: "READY"
holding_object: false
safety_state: "NORMAL"
```

---

## 故障排除

### 没有收到事件

1. 检查容器是否运行：`docker ps`
2. 检查 Web UI 是否响应：`curl http://localhost:8081/api/mode`
3. 检查 rosbridge 是否运行：`docker exec ros2-brain-agent ros2 node list | grep rosbridge`

### Web UI 报错

1. 检查 `.env` 文件是否配置正确
2. 检查 LLM API Key 是否有效
3. 查看容器日志：`./run_docker.sh logs`

### 话题不存在

确保容器内 ROS2 环境已加载：
```bash
docker exec -it ros2-brain-agent bash
source /opt/ros/humble/setup.bash
source /ros2_ws/install/setup.bash
ros2 topic list
```
