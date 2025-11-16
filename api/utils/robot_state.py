"""
Shared Robot State Manager
Maintains current robot status accessible across all API endpoints
"""

from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field
from datetime import datetime
import asyncio
import logging

logger = logging.getLogger(__name__)


@dataclass
class RobotPosition:
    """Robot position in world coordinates"""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    theta: float = 0.0  # Orientation in radians


@dataclass
class DetectedObject:
    """Information about a detected object"""
    object_id: str
    label: Optional[str] = None
    confidence: float = 0.0
    position: Optional[RobotPosition] = None
    bbox: Optional[Dict[str, float]] = None
    detected_at: datetime = field(default_factory=datetime.now)


class RobotStateManager:
    """
    Singleton state manager for robot status

    This class maintains:
    - Current position and orientation
    - Battery level
    - Movement status
    - Current task
    - Held object
    - Detected objects from perception
    """

    _instance = None
    _lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        # Position and orientation
        self.position = RobotPosition()

        # Status
        self.battery_level: float = 100.0
        self.is_moving: bool = False
        self.current_task: Optional[str] = None
        self.holding_object: Optional[str] = None

        # Perception data
        self.detected_objects: List[DetectedObject] = []
        self.last_perception_update: Optional[datetime] = None

        # Memory/knowledge cache
        self.memory_cache: Dict[str, Any] = {}

        # Map information
        self.map_info: Dict[str, Any] = {
            "width": 10.0,
            "height": 10.0,
            "resolution": 0.05
        }

        # Known locations
        self.known_locations: Dict[str, RobotPosition] = {
            "home": RobotPosition(0.0, 0.0, 0.0, 0.0),
            "kitchen": RobotPosition(3.0, 2.0, 0.0, 0.0),
            "living_room": RobotPosition(5.0, 5.0, 0.0, 0.0),
            "bedroom": RobotPosition(7.0, 8.0, 0.0, 0.0),
            "left_table": RobotPosition(2.0, 3.0, 0.0, 0.0),
            "right_table": RobotPosition(6.0, 3.0, 0.0, 0.0)
        }

        self._initialized = True
        logger.info("RobotStateManager initialized")

    async def update_position(self, x: float, y: float, z: float = 0.0, theta: float = 0.0):
        """Update robot position"""
        async with self._lock:
            self.position.x = x
            self.position.y = y
            self.position.z = z
            self.position.theta = theta
            logger.debug(f"Position updated: ({x}, {y}, {theta})")

    async def update_battery(self, level: float):
        """Update battery level (0-100)"""
        async with self._lock:
            self.battery_level = max(0.0, min(100.0, level))
            if self.battery_level < 20.0:
                logger.warning(f"Low battery: {self.battery_level}%")

    async def set_moving(self, is_moving: bool):
        """Update movement status"""
        async with self._lock:
            self.is_moving = is_moving

    async def set_current_task(self, task: Optional[str]):
        """Set current active task"""
        async with self._lock:
            self.current_task = task
            logger.info(f"Current task: {task}")

    async def set_holding_object(self, object_id: Optional[str]):
        """Set object currently held by gripper"""
        async with self._lock:
            self.holding_object = object_id
            logger.info(f"Holding object: {object_id}")

    async def update_perception(self, objects: List[Dict[str, Any]]):
        """
        Update detected objects from perception system

        Args:
            objects: List of detected object dictionaries
        """
        async with self._lock:
            self.detected_objects = []
            for obj in objects:
                pos = None
                if "position" in obj:
                    pos_data = obj["position"]
                    pos = RobotPosition(
                        x=pos_data.get("x", 0.0),
                        y=pos_data.get("y", 0.0),
                        z=pos_data.get("z", 0.0),
                        theta=pos_data.get("theta", 0.0)
                    )

                detected_obj = DetectedObject(
                    object_id=obj.get("object_id", f"obj_{len(self.detected_objects)}"),
                    label=obj.get("label"),
                    confidence=obj.get("confidence", 0.0),
                    position=pos,
                    bbox=obj.get("bbox")
                )
                self.detected_objects.append(detected_obj)

            self.last_perception_update = datetime.now()
            logger.debug(f"Perception updated: {len(self.detected_objects)} objects detected")

    async def add_location(self, name: str, x: float, y: float, theta: float = 0.0):
        """Add a named location to memory"""
        async with self._lock:
            self.known_locations[name] = RobotPosition(x, y, 0.0, theta)
            logger.info(f"Location '{name}' added at ({x}, {y}, {theta})")

    def get_status(self) -> Dict[str, Any]:
        """Get current robot status as dictionary"""
        return {
            "position": {
                "x": self.position.x,
                "y": self.position.y,
                "z": self.position.z,
                "theta": self.position.theta
            },
            "battery_level": self.battery_level,
            "is_moving": self.is_moving,
            "current_task": self.current_task,
            "holding_object": self.holding_object
        }

    def get_detected_objects(self) -> List[Dict[str, Any]]:
        """Get detected objects as list of dictionaries"""
        return [
            {
                "object_id": obj.object_id,
                "label": obj.label,
                "confidence": obj.confidence,
                "position": {
                    "x": obj.position.x,
                    "y": obj.position.y,
                    "z": obj.position.z,
                    "theta": obj.position.theta
                } if obj.position else None,
                "bbox": obj.bbox,
                "detected_at": obj.detected_at.isoformat()
            }
            for obj in self.detected_objects
        ]

    def get_known_locations(self) -> Dict[str, Dict[str, float]]:
        """Get all known locations"""
        return {
            name: {
                "x": pos.x,
                "y": pos.y,
                "z": pos.z,
                "theta": pos.theta
            }
            for name, pos in self.known_locations.items()
        }


# Global singleton instance
robot_state = RobotStateManager()


# Convenience functions
async def get_robot_status() -> Dict[str, Any]:
    """Get current robot status"""
    return robot_state.get_status()


async def get_detected_objects() -> List[Dict[str, Any]]:
    """Get currently detected objects"""
    return robot_state.get_detected_objects()


async def update_robot_position(x: float, y: float, z: float = 0.0, theta: float = 0.0):
    """Update robot position"""
    await robot_state.update_position(x, y, z, theta)


async def update_perception_data(objects: List[Dict[str, Any]]):
    """Update perception data"""
    await robot_state.update_perception(objects)
