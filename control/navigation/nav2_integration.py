"""
ROS2 Navigation (Nav2) Integration
Provides autonomous navigation capabilities for the robot
"""

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from geometry_msgs.msg import PoseStamped, Twist
from nav_msgs.msg import Odometry, OccupancyGrid
from nav2_msgs.action import NavigateToPose
from sensor_msgs.msg import LaserScan
from typing import Dict, Tuple, Optional, Callable
import logging
import time
import numpy as np

logger = logging.getLogger(__name__)


class Nav2Controller(Node):
    """
    ROS2 Navigation Stack Controller
    Handles autonomous navigation, path planning, and obstacle avoidance
    """

    def __init__(self, node_name: str = "nav2_controller"):
        super().__init__(node_name)

        # Action client for navigation
        self._navigate_client = ActionClient(
            self,
            NavigateToPose,
            'navigate_to_pose'
        )

        # Publishers
        self._cmd_vel_pub = self.create_publisher(Twist, 'cmd_vel', 10)

        # Subscribers
        self._odom_sub = self.create_subscription(
            Odometry,
            'odom',
            self._odom_callback,
            10
        )

        self._scan_sub = self.create_subscription(
            LaserScan,
            'scan',
            self._scan_callback,
            10
        )

        self._map_sub = self.create_subscription(
            OccupancyGrid,
            'map',
            self._map_callback,
            10
        )

        # State
        self.current_pose: Optional[PoseStamped] = None
        self.current_velocity: Optional[Twist] = None
        self.latest_scan: Optional[LaserScan] = None
        self.map: Optional[OccupancyGrid] = None

        # Navigation goals
        self.navigation_goal: Optional[PoseStamped] = None
        self.navigation_result: Optional[str] = None

        # Known locations (can be loaded from config)
        self.known_locations: Dict[str, Tuple[float, float, float]] = {
            'home': (0.0, 0.0, 0.0),
            'kitchen': (3.0, 2.0, 0.0),
            'living_room': (-2.0, 1.5, 1.57),
            'bedroom': (5.0, -1.0, 3.14),
            'left_table': (2.5, 1.0, 0.0),
            'right_table': (2.5, -1.0, 0.0),
        }

        self.get_logger().info("Nav2 Controller initialized")

    def _odom_callback(self, msg: Odometry):
        """Update robot odometry"""
        pose = PoseStamped()
        pose.header = msg.header
        pose.pose = msg.pose.pose
        self.current_pose = pose
        self.current_velocity = msg.twist.twist

    def _scan_callback(self, msg: LaserScan):
        """Update laser scan data"""
        self.latest_scan = msg

    def _map_callback(self, msg: OccupancyGrid):
        """Update SLAM map"""
        self.map = msg

    def navigate_to_pose(
        self,
        x: float,
        y: float,
        theta: float = 0.0,
        frame_id: str = "map",
        timeout: float = 60.0,
        callback: Optional[Callable] = None
    ) -> bool:
        """
        Navigate to a specific pose

        Args:
            x, y, theta: Target pose
            frame_id: Reference frame
            timeout: Navigation timeout
            callback: Progress callback

        Returns:
            Success status
        """
        # Wait for action server
        if not self._navigate_client.wait_for_server(timeout_sec=5.0):
            self.get_logger().error("Navigate action server not available")
            return False

        # Create goal
        goal_msg = NavigateToPose.Goal()
        goal_msg.pose.header.frame_id = frame_id
        goal_msg.pose.header.stamp = self.get_clock().now().to_msg()
        goal_msg.pose.pose.position.x = x
        goal_msg.pose.pose.position.y = y
        goal_msg.pose.pose.position.z = 0.0

        # Convert theta to quaternion
        goal_msg.pose.pose.orientation.z = np.sin(theta / 2)
        goal_msg.pose.pose.orientation.w = np.cos(theta / 2)

        self.get_logger().info(f"Sending navigation goal: ({x:.2f}, {y:.2f}, {theta:.2f})")

        # Send goal
        send_goal_future = self._navigate_client.send_goal_async(
            goal_msg,
            feedback_callback=self._navigation_feedback_callback if callback else None
        )

        rclpy.spin_until_future_complete(self, send_goal_future, timeout_sec=2.0)

        goal_handle = send_goal_future.result()

        if not goal_handle.accepted:
            self.get_logger().error("Navigation goal rejected")
            return False

        self.get_logger().info("Navigation goal accepted")

        # Wait for result
        result_future = goal_handle.get_result_async()
        rclpy.spin_until_future_complete(self, result_future, timeout_sec=timeout)

        result = result_future.result()

        if result.status == 4:  # SUCCEEDED
            self.get_logger().info("Navigation succeeded!")
            self.navigation_result = "success"
            return True
        else:
            self.get_logger().warn(f"Navigation failed with status: {result.status}")
            self.navigation_result = "failed"
            return False

    def _navigation_feedback_callback(self, feedback_msg):
        """Handle navigation feedback"""
        feedback = feedback_msg.feedback
        current_pose = feedback.current_pose.pose
        self.get_logger().info(
            f"Navigation progress: ({current_pose.position.x:.2f}, {current_pose.position.y:.2f})"
        )

    def navigate_to_location(
        self,
        location_name: str,
        timeout: float = 60.0
    ) -> bool:
        """
        Navigate to a known location by name

        Args:
            location_name: Name of the location
            timeout: Navigation timeout

        Returns:
            Success status
        """
        if location_name not in self.known_locations:
            self.get_logger().error(f"Unknown location: {location_name}")
            return False

        x, y, theta = self.known_locations[location_name]
        return self.navigate_to_pose(x, y, theta, timeout=timeout)

    def add_location(self, name: str, x: float, y: float, theta: float = 0.0):
        """Add a named location"""
        self.known_locations[name] = (x, y, theta)
        self.get_logger().info(f"Added location '{name}' at ({x}, {y}, {theta})")

    def get_current_position(self) -> Optional[Tuple[float, float, float]]:
        """
        Get current robot position

        Returns:
            (x, y, theta) or None
        """
        if self.current_pose is None:
            return None

        pose = self.current_pose.pose
        x = pose.position.x
        y = pose.position.y

        # Extract yaw from quaternion
        q = pose.orientation
        theta = np.arctan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y**2 + q.z**2))

        return (x, y, theta)

    def stop(self):
        """Emergency stop"""
        stop_cmd = Twist()
        self._cmd_vel_pub.publish(stop_cmd)
        self.get_logger().warn("Emergency stop executed")

    def get_obstacle_info(self) -> Dict:
        """
        Get information about nearby obstacles from laser scan

        Returns:
            Dictionary with obstacle information
        """
        if self.latest_scan is None:
            return {"obstacles": False}

        ranges = np.array(self.latest_scan.ranges)
        ranges = ranges[np.isfinite(ranges)]  # Remove inf values

        if len(ranges) == 0:
            return {"obstacles": False}

        min_distance = np.min(ranges)
        mean_distance = np.mean(ranges)

        return {
            "obstacles": min_distance < 0.5,  # Obstacle within 0.5m
            "min_distance": float(min_distance),
            "mean_distance": float(mean_distance),
            "clear_path": min_distance > 1.0
        }

    def get_map_data(self) -> Optional[Dict]:
        """Get SLAM map data"""
        if self.map is None:
            return None

        return {
            "width": self.map.info.width,
            "height": self.map.info.height,
            "resolution": self.map.info.resolution,
            "origin": {
                "x": self.map.info.origin.position.x,
                "y": self.map.info.origin.position.y
            }
        }


# Standalone navigation node
def main(args=None):
    rclpy.init(args=args)

    nav_controller = Nav2Controller()

    try:
        rclpy.spin(nav_controller)
    except KeyboardInterrupt:
        pass
    finally:
        nav_controller.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
