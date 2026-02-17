# ErrorInfo.msg - 统一错误信息

string code              # 错误码: OBJECT_NOT_FOUND, NAV_TIMEOUT, etc.
string category          # 错误类别: navigation, manipulation, perception, system
bool recoverable         # 是否可恢复
string[] suggested_actions  # 建议的恢复动作
string context_json      # 上下文信息(JSON格式)
string message           # 人类可读的错误描述
