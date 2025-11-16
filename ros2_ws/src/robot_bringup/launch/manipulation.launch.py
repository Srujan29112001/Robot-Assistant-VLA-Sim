#!/usr/bin/env python3
"""
Manipulation System Launch File
Launches MoveIt2 and manipulation-related nodes
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    """Generate launch description for manipulation system"""

    # Declare arguments
    use_sim_time_arg = DeclareLaunchArgument(
        'use_sim_time',
        default_value='true',
        description='Use simulation time'
    )

    use_sim_time = LaunchConfiguration('use_sim_time')

    # Package directories
    moveit_config_dir = FindPackageShare('robot_moveit_config')

    # MoveIt2 move_group node
    moveit_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            PathJoinSubstitution([
                moveit_config_dir,
                'launch',
                'move_group.launch.py'
            ])
        ]),
        launch_arguments={
            'use_sim_time': use_sim_time
        }.items()
    )

    # Manipulation service node
    manipulation_service = Node(
        package='robot_bringup',
        executable='manipulation_node.py',
        name='manipulation_service',
        output='screen',
        parameters=[{
            'use_sim_time': use_sim_time,
            'planning_group': 'arm',
            'end_effector_link': 'tool_frame'
        }]
    )

    # Grasp planning service
    grasp_planner = Node(
        package='robot_bringup',
        executable='grasp_planning_node.py',
        name='grasp_planner',
        output='screen',
        parameters=[{
            'use_sim_time': use_sim_time
        }]
    )

    # Build launch description
    ld = LaunchDescription()

    # Add arguments
    ld.add_action(use_sim_time_arg)

    # Add MoveIt2
    ld.add_action(moveit_launch)

    # Add manipulation nodes
    ld.add_action(manipulation_service)
    ld.add_action(grasp_planner)

    return ld
