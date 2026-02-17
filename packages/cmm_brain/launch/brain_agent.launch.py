# Copyright 2026 ROS2 Brain Agent Team
# SPDX-License-Identifier: Apache-2.0

"""
Brain Agent Launch File - Launches all brain agent nodes.
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    """Generate launch description for brain agent."""

    # Launch arguments
    declare_memory_path = DeclareLaunchArgument(
        'memory_path',
        default_value='memory',
        description='Path to memory storage directory'
    )

    declare_config_path = DeclareLaunchArgument(
        'config_path',
        default_value='configs',
        description='Path to configuration directory'
    )

    declare_enable_asr = DeclareLaunchArgument(
        'enable_asr',
        default_value='false',
        description='Enable ASR node'
    )

    declare_enable_tts = DeclareLaunchArgument(
        'enable_tts',
        default_value='false',
        description='Enable TTS node'
    )

    declare_dry_run = DeclareLaunchArgument(
        'dry_run',
        default_value='false',
        description='Enable dry-run mode for all tools'
    )

    # Brain layer nodes
    brain_nodes = GroupAction([
        # Dialog Manager Node
        Node(
            package='cmm_brain',
            executable='dialog_manager_node',
            name='dialog_manager_node',
            output='screen',
            parameters=[{
                'memory_base_path': LaunchConfiguration('memory_path'),
                'default_session_id': 'default'
            }]
        ),

        # LLM Orchestrator Node
        Node(
            package='cmm_brain',
            executable='llm_orchestrator_node',
            name='llm_orchestrator_node',
            output='screen',
            parameters=[{
                'config_path': LaunchConfiguration('config_path'),
                'providers_config': 'providers.yaml',
                'tools_config': 'tools.yaml'
            }]
        ),

        # Tool Router Node
        Node(
            package='cmm_brain',
            executable='tool_router_node',
            name='tool_router_node',
            output='screen',
            parameters=[{
                'config_path': LaunchConfiguration('config_path'),
                'tools_config': 'tools.yaml',
                'dry_run_default': LaunchConfiguration('dry_run')
            }]
        ),

        # Memory Node
        Node(
            package='cmm_brain',
            executable='memory_node',
            name='memory_node',
            output='screen',
            parameters=[{
                'memory_base_path': LaunchConfiguration('memory_path')
            }]
        ),
    ])

    # Cerebellum layer nodes
    cerebellum_nodes = GroupAction([
        # World State Node
        Node(
            package='cmm_cerebellum',
            executable='world_state_node',
            name='world_state_node',
            output='screen',
            parameters=[{
                'publish_rate': 10.0
            }]
        ),

        # Skill Server Node
        Node(
            package='cmm_cerebellum',
            executable='skill_server_node',
            name='skill_server_node',
            output='screen',
            parameters=[{
                'default_timeout_sec': 120.0
            }]
        ),
    ])

    # IO layer nodes (conditional)
    io_nodes = GroupAction([
        # ASR Client Node
        Node(
            package='cmm_io',
            executable='asr_client_node',
            name='asr_client_node',
            output='screen',
            condition=IfCondition(LaunchConfiguration('enable_asr')),
            parameters=[{
                'asr_provider': 'mock',
                'language': 'zh'
            }]
        ),

        # TTS Client Node
        Node(
            package='cmm_io',
            executable='tts_client_node',
            name='tts_client_node',
            output='screen',
            condition=IfCondition(LaunchConfiguration('enable_tts')),
            parameters=[{
                'tts_provider': 'mock',
                'language': 'zh'
            }]
        ),
    ])

    return LaunchDescription([
        declare_memory_path,
        declare_config_path,
        declare_enable_asr,
        declare_enable_tts,
        declare_dry_run,
        brain_nodes,
        cerebellum_nodes,
        io_nodes,
    ])
