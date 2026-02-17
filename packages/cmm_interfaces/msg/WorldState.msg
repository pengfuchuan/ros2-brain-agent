# WorldState.msg - 机器人世界状态
# 由 world_state_node 维护并发布

std_msgs/Header header

# 定位状态
bool localization_ok
string nav_state         # IDLE, NAVIGATING, ERROR

# 位姿
geometry_msgs/Pose robot_pose

# 机械臂状态
string arm_state         # IDLE, MOVING, HOLDING, ERROR
bool holding_object
string held_object_id

# 感知
string[] perceived_objects  # 感知到的物体ID列表

# 安全状态
string safety_state      # NORMAL, WARNING, ESTOP

# 时间戳
builtin_interfaces/Time last_update
