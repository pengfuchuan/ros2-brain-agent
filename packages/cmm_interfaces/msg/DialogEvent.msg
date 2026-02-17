# DialogEvent.msg - 对话事件消息
# 用于 /dialog/events topic

std_msgs/Header header

string event_id          # 事件唯一ID
string session_id        # 会话ID
string event_type        # 事件类型: turn_start, turn_end, tool_invoke, skill_execute, error, memory_write

string source            # 来源: user, llm, tool, skill, system

string payload_json      # JSON格式的负载数据

builtin_interfaces/Time timestamp
int64 duration_ms        # 持续时间(毫秒)

bool success             # 是否成功
string error_message     # 错误信息
