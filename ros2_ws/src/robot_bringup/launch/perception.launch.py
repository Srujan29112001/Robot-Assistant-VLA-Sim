#!/usr/bin/env python3
"""
Perception System Launch File
Launches all perception-related nodes (camera, depth, OCR, object detection)
"""

from launch import LaunchDescription
from launch_ros.actions import Node
from launch.substitutions import LaunchConfiguration
from launch.actions import DeclareLaunchArgument


def generate_launch_description():
    """Generate launch description for perception system"""

    # Declare arguments
    use_sim_time_arg = DeclareLaunchArgument(
        'use_sim_time',
        default_value='true',
        description='Use simulation time'
    )

    use_sim_time = LaunchConfiguration('use_sim_time')

    # Camera driver (or sim camera bridge)
    camera_node = Node(
        package='usb_cam',
        executable='usb_cam_node_exe',
        name='camera',
        output='screen',
        parameters=[{
            'video_device': '/dev/video0',
            'image_width': 1280,
            'image_height': 720,
            'pixel_format': 'yuyv',
            'camera_frame_id': 'camera_optical_frame',
            'framerate': 30.0,
            'use_sim_time': use_sim_time
        }],
        remappings=[
            ('/image', '/camera/image_raw')
        ]
    )

    # Depth camera (if available)
    depth_camera_node = Node(
        package='realsense2_camera',
        executable='realsense2_camera_node',
        name='depth_camera',
        output='screen',
        parameters=[{
            'enable_depth': True,
            'enable_color': True,
            'align_depth': True,
            'use_sim_time': use_sim_time
        }]
    )

    # Image processing pipeline
    image_proc_node = Node(
        package='image_proc',
        executable='image_proc',
        name='image_proc',
        remappings=[
            ('image', '/camera/image_raw'),
            ('camera_info', '/camera/camera_info')
        ]
    )

    # Object detection node (YOLO or similar)
    object_detector = Node(
        package='robot_bringup',
        executable='object_detection_node.py',
        name='object_detector',
        output='screen',
        parameters=[{
            'model_path': '/models/yolov8n.pt',
            'confidence_threshold': 0.5,
            'use_sim_time': use_sim_time
        }],
        remappings=[
            ('/image_raw', '/camera/image_raw')
        ]
    )

    # Build launch description
    ld = LaunchDescription()

    # Add arguments
    ld.add_action(use_sim_time_arg)

    # Add nodes
    # Note: Choose either simulated camera or real camera
    # ld.add_action(camera_node)  # Uncomment for real hardware
    # ld.add_action(depth_camera_node)  # Uncomment for RealSense
    ld.add_action(image_proc_node)
    ld.add_action(object_detector)

    return ld
