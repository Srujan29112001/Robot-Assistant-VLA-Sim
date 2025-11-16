"""
MoveIt2 Interface for Robot Manipulation
Provides high-level API for motion planning and execution
"""

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from geometry_msgs.msg import Pose, PoseStamped, Point, Quaternion
from moveit_msgs.action import MoveGroup
from moveit_msgs.msg import (
    MotionPlanRequest,
    Constraints,
    PositionConstraint,
    OrientationConstraint,
    JointConstraint,
    RobotState,
    PlanningOptions
)
from sensor_msgs.msg import JointState
from std_msgs.msg import Header
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint
import numpy as np
from typing import List, Optional, Dict, Tuple
import logging

logger = logging.getLogger(__name__)


class MoveItInterface:
    """
    High-level interface for MoveIt2 motion planning and execution
    """

    def __init__(self, node: Optional[Node] = None):
        """
        Initialize MoveIt interface

        Args:
            node: ROS2 node (creates one if not provided)
        """
        if node is None:
            rclpy.init()
            self.node = Node('moveit_interface')
            self.owns_node = True
        else:
            self.node = node
            self.owns_node = False

        # MoveIt action client
        self._move_group_client = ActionClient(
            self.node,
            MoveGroup,
            '/move_group'
        )

        # Joint state subscriber
        self._joint_states = None
        self._joint_state_sub = self.node.create_subscription(
            JointState,
            '/joint_states',
            self._joint_state_callback,
            10
        )

        # Gripper control publisher
        self._gripper_pub = self.node.create_publisher(
            JointTrajectory,
            '/gripper_controller/joint_trajectory',
            10
        )

        # Configuration
        self.arm_group = "arm"
        self.gripper_group = "gripper"
        self.end_effector_link = "tool_frame"
        self.planning_time = 5.0
        self.num_planning_attempts = 10
        self.max_velocity_scaling = 0.5
        self.max_acceleration_scaling = 0.5

        # Wait for action server
        logger.info("Waiting for MoveGroup action server...")
        self._move_group_client.wait_for_server()
        logger.info("MoveIt2 Interface initialized")

    def _joint_state_callback(self, msg: JointState):
        """Callback for joint state updates"""
        self._joint_states = msg

    def get_current_joint_states(self) -> Optional[Dict[str, float]]:
        """
        Get current joint positions

        Returns:
            Dictionary of joint name to position, or None if not available
        """
        if self._joint_states is None:
            return None

        return dict(zip(self._joint_states.name, self._joint_states.position))

    def move_to_pose(self, target_pose: Pose,
                     frame_id: str = "base_link",
                     wait: bool = True) -> bool:
        """
        Move end-effector to target pose

        Args:
            target_pose: Target pose for end-effector
            frame_id: Reference frame for pose
            wait: Wait for execution to complete

        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Planning to pose in frame {frame_id}")

        # Create pose stamped
        pose_stamped = PoseStamped()
        pose_stamped.header = Header()
        pose_stamped.header.frame_id = frame_id
        pose_stamped.header.stamp = self.node.get_clock().now().to_msg()
        pose_stamped.pose = target_pose

        # Create position constraint
        position_constraint = PositionConstraint()
        position_constraint.header = pose_stamped.header
        position_constraint.link_name = self.end_effector_link
        position_constraint.target_point_offset.x = 0.0
        position_constraint.target_point_offset.y = 0.0
        position_constraint.target_point_offset.z = 0.0

        # Create goal
        goal = MoveGroup.Goal()
        goal.request.group_name = self.arm_group
        goal.request.num_planning_attempts = self.num_planning_attempts
        goal.request.allowed_planning_time = self.planning_time
        goal.request.max_velocity_scaling_factor = self.max_velocity_scaling
        goal.request.max_acceleration_scaling_factor = self.max_acceleration_scaling

        goal.request.goal_constraints.append(Constraints())
        goal.request.goal_constraints[0].position_constraints.append(position_constraint)

        goal.planning_options.plan_only = False
        goal.planning_options.replan = True
        goal.planning_options.replan_attempts = 5

        # Send goal
        future = self._move_group_client.send_goal_async(goal)

        if wait:
            rclpy.spin_until_future_complete(self.node, future)
            goal_handle = future.result()

            if not goal_handle.accepted:
                logger.error("Goal rejected by MoveGroup")
                return False

            result_future = goal_handle.get_result_async()
            rclpy.spin_until_future_complete(self.node, result_future)
            result = result_future.result().result

            if result.error_code.val == result.error_code.SUCCESS:
                logger.info("Motion planning and execution succeeded")
                return True
            else:
                logger.error(f"Motion planning failed with error code: {result.error_code.val}")
                return False

        return True

    def move_to_joint_positions(self, joint_positions: Dict[str, float],
                                wait: bool = True) -> bool:
        """
        Move arm to specific joint positions

        Args:
            joint_positions: Dictionary of joint names to target positions (radians)
            wait: Wait for execution to complete

        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Planning to joint positions: {joint_positions}")

        # Create goal with joint constraints
        goal = MoveGroup.Goal()
        goal.request.group_name = self.arm_group
        goal.request.num_planning_attempts = self.num_planning_attempts
        goal.request.allowed_planning_time = self.planning_time
        goal.request.max_velocity_scaling_factor = self.max_velocity_scaling
        goal.request.max_acceleration_scaling_factor = self.max_acceleration_scaling

        # Add joint constraints
        constraints = Constraints()
        for joint_name, position in joint_positions.items():
            joint_constraint = JointConstraint()
            joint_constraint.joint_name = joint_name
            joint_constraint.position = position
            joint_constraint.tolerance_above = 0.01
            joint_constraint.tolerance_below = 0.01
            joint_constraint.weight = 1.0
            constraints.joint_constraints.append(joint_constraint)

        goal.request.goal_constraints.append(constraints)
        goal.planning_options.plan_only = False
        goal.planning_options.replan = True

        # Send goal
        future = self._move_group_client.send_goal_async(goal)

        if wait:
            rclpy.spin_until_future_complete(self.node, future)
            goal_handle = future.result()

            if not goal_handle.accepted:
                logger.error("Joint position goal rejected")
                return False

            result_future = goal_handle.get_result_async()
            rclpy.spin_until_future_complete(self.node, result_future)
            result = result_future.result().result

            return result.error_code.val == result.error_code.SUCCESS

        return True

    def move_to_named_target(self, target_name: str, wait: bool = True) -> bool:
        """
        Move to a predefined named target (configured in SRDF)

        Args:
            target_name: Name of the target configuration (e.g., 'home', 'ready')
            wait: Wait for execution to complete

        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Moving to named target: {target_name}")

        goal = MoveGroup.Goal()
        goal.request.group_name = self.arm_group
        goal.request.num_planning_attempts = self.num_planning_attempts
        goal.request.allowed_planning_time = self.planning_time

        # Named targets are defined in SRDF
        # For now, we'll define some common positions
        named_targets = {
            'home': {
                'shoulder_joint': 0.0,
                'elbow_joint': 0.0,
                'wrist_joint': 0.0,
                'gripper_base_joint': 0.0
            },
            'ready': {
                'shoulder_joint': 0.0,
                'elbow_joint': -0.5,
                'wrist_joint': -0.3,
                'gripper_base_joint': 0.0
            },
            'tucked': {
                'shoulder_joint': 1.57,
                'elbow_joint': -1.57,
                'wrist_joint': 0.0,
                'gripper_base_joint': 0.0
            }
        }

        if target_name not in named_targets:
            logger.error(f"Unknown named target: {target_name}")
            return False

        return self.move_to_joint_positions(named_targets[target_name], wait=wait)

    def set_gripper(self, position: float, wait: bool = True) -> bool:
        """
        Control gripper opening/closing

        Args:
            position: Gripper position (0.0 = closed, 0.04 = fully open)
            wait: Wait for completion

        Returns:
            True if successful
        """
        logger.info(f"Setting gripper to position: {position}")

        # Create trajectory message
        traj = JointTrajectory()
        traj.header.stamp = self.node.get_clock().now().to_msg()
        traj.joint_names = ['left_finger_joint', 'right_finger_joint']

        point = JointTrajectoryPoint()
        point.positions = [position, position]
        point.time_from_start.sec = 1
        traj.points.append(point)

        self._gripper_pub.publish(traj)

        if wait:
            self.node.get_clock().sleep_for(rclpy.duration.Duration(seconds=1.5))

        return True

    def open_gripper(self, wait: bool = True) -> bool:
        """Open gripper fully"""
        return self.set_gripper(0.04, wait=wait)

    def close_gripper(self, wait: bool = True) -> bool:
        """Close gripper"""
        return self.set_gripper(0.0, wait=wait)

    def pick_object(self, object_pose: Pose, approach_distance: float = 0.1) -> bool:
        """
        Pick up an object at given pose

        Args:
            object_pose: Pose of the object in base_link frame
            approach_distance: Distance to approach from above (meters)

        Returns:
            True if pick successful
        """
        logger.info("Executing pick operation")

        # Open gripper
        if not self.open_gripper():
            logger.error("Failed to open gripper")
            return False

        # Move to pre-grasp pose (above object)
        pre_grasp_pose = Pose()
        pre_grasp_pose.position = Point(
            x=object_pose.position.x,
            y=object_pose.position.y,
            z=object_pose.position.z + approach_distance
        )
        pre_grasp_pose.orientation = Quaternion(x=0.0, y=0.707, z=0.0, w=0.707)  # Pointing down

        if not self.move_to_pose(pre_grasp_pose):
            logger.error("Failed to move to pre-grasp pose")
            return False

        # Move to grasp pose
        grasp_pose = object_pose
        grasp_pose.orientation = pre_grasp_pose.orientation

        if not self.move_to_pose(grasp_pose):
            logger.error("Failed to move to grasp pose")
            return False

        # Close gripper
        if not self.close_gripper():
            logger.error("Failed to close gripper")
            return False

        # Lift object
        lift_pose = Pose()
        lift_pose.position = Point(
            x=grasp_pose.position.x,
            y=grasp_pose.position.y,
            z=grasp_pose.position.z + approach_distance
        )
        lift_pose.orientation = grasp_pose.orientation

        if not self.move_to_pose(lift_pose):
            logger.error("Failed to lift object")
            return False

        logger.info("Pick operation completed successfully")
        return True

    def place_object(self, target_pose: Pose, retreat_distance: float = 0.1) -> bool:
        """
        Place object at target pose

        Args:
            target_pose: Target pose for placing object
            retreat_distance: Distance to retreat after placing

        Returns:
            True if place successful
        """
        logger.info("Executing place operation")

        # Move to pre-place pose (above target)
        pre_place_pose = Pose()
        pre_place_pose.position = Point(
            x=target_pose.position.x,
            y=target_pose.position.y,
            z=target_pose.position.z + retreat_distance
        )
        pre_place_pose.orientation = Quaternion(x=0.0, y=0.707, z=0.0, w=0.707)

        if not self.move_to_pose(pre_place_pose):
            logger.error("Failed to move to pre-place pose")
            return False

        # Move to place pose
        place_pose = target_pose
        place_pose.orientation = pre_place_pose.orientation

        if not self.move_to_pose(place_pose):
            logger.error("Failed to move to place pose")
            return False

        # Open gripper
        if not self.open_gripper():
            logger.error("Failed to open gripper")
            return False

        # Retreat
        if not self.move_to_pose(pre_place_pose):
            logger.error("Failed to retreat from place pose")
            return False

        logger.info("Place operation completed successfully")
        return True

    def get_end_effector_pose(self) -> Optional[Pose]:
        """
        Get current end-effector pose

        Returns:
            Current pose or None if not available
        """
        # This would typically use tf2 to get the transform
        # For now, return None (implement with tf2 in production)
        logger.warning("get_end_effector_pose not fully implemented")
        return None

    def compute_cartesian_path(self, waypoints: List[Pose],
                               eef_step: float = 0.01,
                               jump_threshold: float = 0.0) -> Optional[JointTrajectory]:
        """
        Compute cartesian path through waypoints

        Args:
            waypoints: List of waypoint poses
            eef_step: Step size for discretization (meters)
            jump_threshold: Threshold for detecting configuration jumps

        Returns:
            Computed trajectory or None if failed
        """
        logger.info(f"Computing cartesian path through {len(waypoints)} waypoints")
        # Implement cartesian path planning
        logger.warning("compute_cartesian_path not fully implemented")
        return None

    def shutdown(self):
        """Cleanup resources"""
        if self.owns_node:
            self.node.destroy_node()
            rclpy.shutdown()


if __name__ == "__main__":
    # Example usage
    moveit = MoveItInterface()

    # Move to home position
    moveit.move_to_named_target('home')

    # Example pick operation
    object_pose = Pose()
    object_pose.position = Point(x=0.5, y=0.0, z=0.3)
    moveit.pick_object(object_pose)

    moveit.shutdown()
