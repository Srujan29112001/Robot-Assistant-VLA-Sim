"""
Multi-Robot Coordination System
Enables fleet management and collaborative task execution
"""

from .coordinator import RobotCoordinator, FleetManager
from .task_allocation import TaskAllocator
from .communication import RobotCommunicationHub

__all__ = ['RobotCoordinator', 'FleetManager', 'TaskAllocator', 'RobotCommunicationHub']
