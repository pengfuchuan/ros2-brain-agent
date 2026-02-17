# ToolCall.msg - 工具调用消息

string tool_name         # 工具名称
string args_json         # JSON格式的参数
string call_id           # 调用ID

string permission_level  # safe, confirm, dangerous
float32 timeout_sec      # 超时时间

bool requires_confirm    # 是否需要确认
