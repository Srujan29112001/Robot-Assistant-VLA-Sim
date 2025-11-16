#!/usr/bin/env python3
"""
Complete System Launch File
Launches entire Vision-Language Robotic Assistant stack
"""

from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, DeclareLaunchArgument, ExecuteProcess
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
import os


def generate_launch_description():
    """Generate launch description for full system"""

    # Declare arguments
    use_sim_time = LaunchConfiguration('use_sim_time', default='true')
    use_gazebo = LaunchConfiguration('use_gazebo', default='true')
    world_file = LaunchConfiguration('world', default='home_environment.world')

    # Package directories
    robot_description_dir = FindPackageShare('robot_description')
    robot_bringup_dir = FindPackageShare('robot_bringup')

    # Declare launch arguments
    declare_use_sim_time = DeclareLaunchArgument(
        'use_sim_time',
        default_value='true',
        description='Use simulation time'
    )

    declare_use_gazebo = DeclareLaunchArgument(
        'use_gazebo',
        default_value='true',
        description='Launch Gazebo simulation'
    )

    declare_world = DeclareLaunchArgument(
        'world',
        default_value='home_environment.world',
        description='Gazebo world file'
    )

    # ========== Simulation ==========
    gazebo_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            PathJoinSubstitution([
                robot_bringup_dir,
                'launch',
                'gazebo_sim.launch.py'
            ])
        ]),
        launch_arguments={
            'use_sim_time': use_sim_time,
            'world': world_file
        }.items(),
        condition=launch.conditions.IfCondition(use_gazebo)
    )

    # ========== Robot Description ==========
    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='screen',
        parameters=[{
            'use_sim_time': use_sim_time,
            'robot_description': Command([
                'xacro ',
                PathJoinSubstitution([
                    robot_description_dir,
                    'urdf',
                    'mobile_manipulator.urdf.xacro'
                ])
            ])
        }]
    )

    # ========== Navigation Stack (Nav2) ==========
    nav2_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            PathJoinSubstitution([
                FindPackageShare('nav2_bringup'),
                'launch',
                'navigation_launch.py'
            ])
        ]),
        launch_arguments={
            'use_sim_time': use_sim_time,
            'params_file': PathJoinSubstitution([
                robot_bringup_dir,
                'config',
                'nav2_params.yaml'
            ])
        }.items()
    )

    # SLAM Toolbox
    slam_toolbox = Node(
        package='slam_toolbox',
        executable='async_slam_toolbox_node',
        name='slam_toolbox',
        output='screen',
        parameters=[{
            'use_sim_time': use_sim_time,
            'slam_params_file': PathJoinSubstitution([
                robot_bringup_dir,
                'config',
                'slam_params.yaml'
            ])
        }]
    )

    # ========== Perception Nodes ==========
    camera_bridge = Node(
        package='cv_bridge',
        executable='cv_bridge_node',
        name='camera_bridge',
        output='screen',
        parameters=[{'use_sim_time': use_sim_time}]
    )

    # ========== Control Nodes ==========
    # Joint trajectory controller
    joint_controller = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['joint_trajectory_controller'],
        output='screen'
    )

    # Gripper controller
    gripper_controller = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['gripper_controller'],
        output='screen'
    )

    # ========== AI/ML Services ==========
    # Perception service (Python node)
    perception_service = Node(
        package='robot_bringup',
        executable='perception_node.py',
        name='perception_service',
        output='screen',
        parameters=[{'use_sim_time': use_sim_time}]
    )

    # Navigation integration
    navigation_service = Node(
        package='robot_bringup',
        executable='navigation_node.py',
        name='navigation_service',
        output='screen',
        parameters=[{'use_sim_time': use_sim_time}]
    )

    # ========== Visualization ==========
    rviz = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        arguments=['-d', PathJoinSubstitution([
            robot_bringup_dir,
            'config',
            'robot_view.rviz'
        ])],
        parameters=[{'use_sim_time': use_sim_time}],
        condition=launch.conditions.UnlessCondition(
            LaunchConfiguration('headless', default='false')
        )
    )

    # ========== Build Launch Description ==========
    ld = LaunchDescription()

    # Add arguments
    ld.add_action(declare_use_sim_time)
    ld.add_action(declare_use_gazebo)
    ld.add_action(declare_world)

    # Add simulation
    ld.add_action(gazebo_launch)

    # Add robot description
    ld.add_action(robot_state_publisher)

    # Add navigation
    ld.add_action(nav2_launch)
    ld.add_action(slam_toolbox)

    # Add perception
    ld.add_action(camera_bridge)
    ld.add_action(perception_service)

    # Add control
    ld.add_action(joint_controller)
    ld.add_action(gripper_controller)
    ld.add_action(navigation_service)

    # Add visualization
    ld.add_action(rviz)

    return ld
