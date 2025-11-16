"""
Grasp Planning for Object Manipulation
Computes optimal grasp poses for different object types
"""

import numpy as np
from geometry_msgs.msg import Pose, Point, Quaternion
from typing import List, Tuple, Optional, Dict
import logging

logger = logging.getLogger(__name__)


class GraspPlanner:
    """
    Compute grasp poses for objects based on perception data
    """

    def __init__(self):
        """Initialize grasp planner"""
        # Gripper parameters
        self.gripper_width = 0.04  # Maximum gripper opening (meters)
        self.gripper_depth = 0.08  # Gripper finger length
        self.approach_distance = 0.1  # Distance to approach from

        # Object type to grasp strategy mapping
        self.grasp_strategies = {
            'bottle': self._plan_cylinder_grasp,
            'cup': self._plan_cylinder_grasp,
            'box': self._plan_box_grasp,
            'ball': self._plan_sphere_grasp,
            'unknown': self._plan_generic_grasp
        }

        logger.info("Grasp Planner initialized")

    def plan_grasp(self, object_info: Dict) -> List[Pose]:
        """
        Plan grasps for an object

        Args:
            object_info: Dictionary containing:
                - 'type': Object type (str)
                - 'pose': Object pose (Pose)
                - 'dimensions': Object dimensions dict (optional)
                - 'orientation': Object orientation (optional)

        Returns:
            List of candidate grasp poses, ranked by quality
        """
        object_type = object_info.get('type', 'unknown')
        object_pose = object_info['pose']
        dimensions = object_info.get('dimensions', {})

        logger.info(f"Planning grasp for {object_type} object")

        # Get strategy for object type
        strategy = self.grasp_strategies.get(
            object_type,
            self._plan_generic_grasp
        )

        # Generate candidate grasps
        grasps = strategy(object_pose, dimensions)

        # Rank grasps by quality
        ranked_grasps = self._rank_grasps(grasps, object_info)

        logger.info(f"Generated {len(ranked_grasps)} candidate grasps")
        return ranked_grasps

    def _plan_cylinder_grasp(self, pose: Pose, dimensions: Dict) -> List[Pose]:
        """
        Plan grasps for cylindrical objects (bottles, cups)

        Args:
            pose: Object center pose
            dimensions: height, radius

        Returns:
            List of grasp poses
        """
        grasps = []
        height = dimensions.get('height', 0.2)
        radius = dimensions.get('radius', 0.03)

        # Check if object fits in gripper
        if radius * 2 > self.gripper_width:
            logger.warning(f"Object too large for gripper: diameter={radius*2}")
            return grasps

        # Side grasp at multiple heights
        for z_offset in [0.0, height * 0.25, height * 0.5]:
            # Grasp from multiple angles
            for angle in np.linspace(0, 2 * np.pi, 8, endpoint=False):
                grasp_pose = Pose()

                # Position: offset from center at grasp height
                grasp_pose.position = Point(
                    x=pose.position.x,
                    y=pose.position.y,
                    z=pose.position.z + z_offset
                )

                # Orientation: approach from side
                # Convert angle to quaternion (rotation around z-axis)
                qw = np.cos(angle / 2)
                qz = np.sin(angle / 2)
                grasp_pose.orientation = Quaternion(
                    x=0.0,
                    y=0.707,  # Point fingers down
                    z=qz,
                    w=qw
                )

                grasps.append(grasp_pose)

        # Top grasp (for short cylinders)
        if height < 0.15:
            top_grasp = Pose()
            top_grasp.position = Point(
                x=pose.position.x,
                y=pose.position.y,
                z=pose.position.z + height / 2
            )
            top_grasp.orientation = Quaternion(x=0.0, y=0.707, z=0.0, w=0.707)
            grasps.append(top_grasp)

        return grasps

    def _plan_box_grasp(self, pose: Pose, dimensions: Dict) -> List[Pose]:
        """
        Plan grasps for box-shaped objects

        Args:
            pose: Object center pose
            dimensions: width, length, height

        Returns:
            List of grasp poses
        """
        grasps = []
        width = dimensions.get('width', 0.1)
        length = dimensions.get('length', 0.1)
        height = dimensions.get('height', 0.1)

        # Check graspability
        min_dim = min(width, length)
        if min_dim > self.gripper_width:
            logger.warning("Box too large to grasp")
            return grasps

        # Side grasps along width
        if width < self.gripper_width:
            for z_offset in [0.0, height * 0.5]:
                grasp_pose = Pose()
                grasp_pose.position = Point(
                    x=pose.position.x,
                    y=pose.position.y,
                    z=pose.position.z + z_offset
                )
                grasp_pose.orientation = Quaternion(x=0.0, y=0.707, z=0.0, w=0.707)
                grasps.append(grasp_pose)

        # Top grasp
        if height < 0.1 and max(width, length) < self.gripper_width:
            top_grasp = Pose()
            top_grasp.position = Point(
                x=pose.position.x,
                y=pose.position.y,
                z=pose.position.z + height / 2 + 0.02
            )
            top_grasp.orientation = Quaternion(x=0.0, y=0.707, z=0.0, w=0.707)
            grasps.append(top_grasp)

        return grasps

    def _plan_sphere_grasp(self, pose: Pose, dimensions: Dict) -> List[Pose]:
        """
        Plan grasps for spherical objects (balls)

        Args:
            pose: Object center pose
            dimensions: radius

        Returns:
            List of grasp poses
        """
        grasps = []
        radius = dimensions.get('radius', 0.05)

        if radius * 2 > self.gripper_width:
            logger.warning("Sphere too large for gripper")
            return grasps

        # Multiple approach angles
        for angle in np.linspace(0, 2 * np.pi, 12, endpoint=False):
            grasp_pose = Pose()
            grasp_pose.position = Point(
                x=pose.position.x,
                y=pose.position.y,
                z=pose.position.z
            )

            # Approach from various angles
            qw = np.cos(angle / 2)
            qz = np.sin(angle / 2)
            grasp_pose.orientation = Quaternion(x=0.0, y=0.707, z=qz, w=qw)
            grasps.append(grasp_pose)

        return grasps

    def _plan_generic_grasp(self, pose: Pose, dimensions: Dict) -> List[Pose]:
        """
        Generic grasp planner for unknown objects
        Attempts top and side grasps

        Args:
            pose: Object pose
            dimensions: Any available dimensions

        Returns:
            List of grasp poses
        """
        grasps = []

        # Top grasp (most universal)
        top_grasp = Pose()
        top_grasp.position = Point(
            x=pose.position.x,
            y=pose.position.y,
            z=pose.position.z + 0.05  # Slightly above center
        )
        top_grasp.orientation = Quaternion(x=0.0, y=0.707, z=0.0, w=0.707)
        grasps.append(top_grasp)

        # Side grasps from 4 directions
        for angle in [0, np.pi/2, np.pi, 3*np.pi/2]:
            side_grasp = Pose()
            side_grasp.position = Point(
                x=pose.position.x,
                y=pose.position.y,
                z=pose.position.z
            )
            qw = np.cos(angle / 2)
            qz = np.sin(angle / 2)
            side_grasp.orientation = Quaternion(x=0.0, y=0.707, z=qz, w=qw)
            grasps.append(side_grasp)

        return grasps

    def _rank_grasps(self, grasps: List[Pose], object_info: Dict) -> List[Pose]:
        """
        Rank grasp candidates by quality metrics

        Args:
            grasps: List of candidate grasps
            object_info: Object information

        Returns:
            Ranked list of grasps (best first)
        """
        if not grasps:
            return grasps

        # Simple ranking: prefer top grasps, then based on accessibility
        scored_grasps = []

        for grasp in grasps:
            score = 0.0

            # Prefer higher z positions (top grasps)
            score += grasp.position.z * 10.0

            # Prefer grasps closer to robot base (simplified)
            distance = np.sqrt(grasp.position.x**2 + grasp.position.y**2)
            score -= distance * 5.0

            # Prefer forward reach (positive x)
            if grasp.position.x > 0:
                score += 5.0

            scored_grasps.append((score, grasp))

        # Sort by score (descending)
        scored_grasps.sort(key=lambda x: x[0], reverse=True)

        # Return just the grasps
        return [grasp for _, grasp in scored_grasps]

    def validate_grasp(self, grasp_pose: Pose,
                      object_pose: Pose,
                      collision_check: bool = True) -> bool:
        """
        Validate if a grasp is feasible

        Args:
            grasp_pose: Proposed grasp pose
            object_pose: Object pose
            collision_check: Whether to check for collisions

        Returns:
            True if grasp is valid
        """
        # Check reach (simplified - should use actual kinematic limits)
        distance = np.sqrt(
            grasp_pose.position.x**2 +
            grasp_pose.position.y**2 +
            grasp_pose.position.z**2
        )

        max_reach = 0.8  # Maximum arm reach (adjust based on actual robot)
        if distance > max_reach:
            logger.debug(f"Grasp out of reach: {distance}m > {max_reach}m")
            return False

        # Check minimum reach
        min_reach = 0.2
        if distance < min_reach:
            logger.debug(f"Grasp too close: {distance}m < {min_reach}m")
            return False

        # Check height
        if grasp_pose.position.z < 0.0 or grasp_pose.position.z > 1.5:
            logger.debug(f"Grasp height out of range: {grasp_pose.position.z}m")
            return False

        # TODO: Implement actual collision checking with environment
        if collision_check:
            pass

        return True

    def compute_pre_grasp_pose(self, grasp_pose: Pose,
                               approach_distance: Optional[float] = None) -> Pose:
        """
        Compute pre-grasp pose (before final approach)

        Args:
            grasp_pose: Final grasp pose
            approach_distance: Distance to offset (uses default if None)

        Returns:
            Pre-grasp pose
        """
        if approach_distance is None:
            approach_distance = self.approach_distance

        # Offset along approach direction (typically -Z in gripper frame)
        # Simplified: offset in world Z
        pre_grasp = Pose()
        pre_grasp.position = Point(
            x=grasp_pose.position.x,
            y=grasp_pose.position.y,
            z=grasp_pose.position.z + approach_distance
        )
        pre_grasp.orientation = grasp_pose.orientation

        return pre_grasp

    def visualize_grasps(self, grasps: List[Pose], marker_topic: str = "/grasp_markers"):
        """
        Publish visualization markers for grasps (ROS visualization)

        Args:
            grasps: List of grasp poses to visualize
            marker_topic: Topic to publish markers on
        """
        # TODO: Implement ROS marker visualization
        logger.info(f"Would visualize {len(grasps)} grasps on {marker_topic}")
        pass


# Example usage
if __name__ == "__main__":
    planner = GraspPlanner()

    # Example: plan grasp for a bottle
    bottle_pose = Pose()
    bottle_pose.position = Point(x=0.5, y=0.2, z=0.3)

    object_info = {
        'type': 'bottle',
        'pose': bottle_pose,
        'dimensions': {'height': 0.25, 'radius': 0.035}
    }

    grasps = planner.plan_grasp(object_info)
    print(f"Generated {len(grasps)} grasps for bottle")

    # Validate first grasp
    if grasps:
        is_valid = planner.validate_grasp(grasps[0], bottle_pose)
        print(f"First grasp valid: {is_valid}")
