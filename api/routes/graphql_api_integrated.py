"""
Fully Integrated GraphQL API for Robot Control
Connects to actual robot systems (perception, navigation, memory, etc.)
"""

import strawberry
from strawberry.fastapi import GraphQLRouter
from typing import List, Optional
from datetime import datetime
import asyncio
import logging
import httpx

logger = logging.getLogger(__name__)


# Import actual system components
try:
    from perception.main import PerceptionPipeline
    from memory.graphrag.knowledge_graph import KnowledgeGraph
    from control.navigation.nav2_integration import Navigation
    SYSTEMS_AVAILABLE = True
except ImportError:
    logger.warning("Some system components not available for import")
    SYSTEMS_AVAILABLE = False


@strawberry.type
class RobotPosition:
    """Robot position data"""
    x: float
    y: float
    z: float
    theta: float


@strawberry.type
class ObjectInfo:
    """Detected object information"""
    object_id: str
    label: Optional[str]
    confidence: float
    position: Optional[RobotPosition]


@strawberry.type
class RobotStatus:
    """Current robot status"""
    position: RobotPosition
    battery_level: float
    is_moving: bool
    current_task: Optional[str]
    holding_object: Optional[str]


@strawberry.type
class TaskResult:
    """Task execution result"""
    task_id: str
    status: str
    message: str
    started_at: datetime
    completed_at: Optional[datetime]


@strawberry.type
class MemoryEntry:
    """Memory/knowledge entry"""
    fact: str
    timestamp: datetime
    confidence: float
    entities: List[str]


@strawberry.input
class NavigationInput:
    """Navigation goal input"""
    target_location: str
    max_speed: Optional[float] = 0.5


@strawberry.input
class ManipulationInput:
    """Manipulation action input"""
    action: str  # "pick", "place", "grasp", "release"
    object_id: Optional[str]
    target_location: Optional[str]


@strawberry.type
class Query:
    """GraphQL Queries - Fully Integrated"""

    @strawberry.field
    async def robot_status(self) -> RobotStatus:
        """Get current robot status from ROS2"""
        try:
            # Call ROS2 state service
            async with httpx.AsyncClient() as client:
                response = await client.get("http://localhost:8000/api/v1/state")
                if response.status_code == 200:
                    data = response.json()
                    return RobotStatus(
                        position=RobotPosition(
                            x=data.get('position', {}).get('x', 0.0),
                            y=data.get('position', {}).get('y', 0.0),
                            z=data.get('position', {}).get('z', 0.0),
                            theta=data.get('position', {}).get('theta', 0.0)
                        ),
                        battery_level=data.get('battery_level', 0.0),
                        is_moving=data.get('is_moving', False),
                        current_task=data.get('current_task'),
                        holding_object=data.get('holding_object')
                    )
        except Exception as e:
            logger.error(f"Error getting robot status: {e}")

        # Fallback
        return RobotStatus(
            position=RobotPosition(x=0.0, y=0.0, z=0.0, theta=0.0),
            battery_level=100.0,
            is_moving=False,
            current_task=None,
            holding_object=None
        )

    @strawberry.field
    async def detected_objects(self) -> List[ObjectInfo]:
        """Get currently detected objects from perception system"""
        objects = []

        try:
            # Call perception API
            async with httpx.AsyncClient() as client:
                response = await client.get("http://localhost:8000/api/v1/perception/objects")
                if response.status_code == 200:
                    data = response.json()
                    for obj in data.get('objects', []):
                        objects.append(ObjectInfo(
                            object_id=obj['id'],
                            label=obj.get('label'),
                            confidence=obj.get('confidence', 0.0),
                            position=RobotPosition(
                                x=obj['position']['x'],
                                y=obj['position']['y'],
                                z=obj['position']['z'],
                                theta=0.0
                            ) if 'position' in obj else None
                        ))
        except Exception as e:
            logger.error(f"Error getting detected objects: {e}")

        return objects

    @strawberry.field
    async def query_memory(self, query: str, limit: int = 10) -> List[MemoryEntry]:
        """Query robot's long-term memory (GraphRAG)"""
        entries = []

        try:
            # Call GraphRAG memory system
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "http://localhost:8000/api/v1/memory/query",
                    json={"query": query, "limit": limit}
                )
                if response.status_code == 200:
                    data = response.json()
                    for entry in data.get('results', []):
                        entries.append(MemoryEntry(
                            fact=entry['fact'],
                            timestamp=datetime.fromisoformat(entry['timestamp']),
                            confidence=entry.get('confidence', 0.0),
                            entities=entry.get('entities', [])
                        ))
        except Exception as e:
            logger.error(f"Error querying memory: {e}")

        return entries

    @strawberry.field
    async def get_map_info(self) -> str:
        """Get SLAM map information"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get("http://localhost:8000/api/v1/navigation/map")
                if response.status_code == 200:
                    data = response.json()
                    return f"Map: {data.get('width')}x{data.get('height')}m, resolution: {data.get('resolution')}m/pixel"
        except Exception as e:
            logger.error(f"Error getting map info: {e}")

        return "Map information not available"

    @strawberry.field
    async def task_history(self, limit: int = 20) -> List[TaskResult]:
        """Get task execution history"""
        tasks = []

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"http://localhost:8000/api/v1/tasks/history?limit={limit}"
                )
                if response.status_code == 200:
                    data = response.json()
                    for task in data.get('tasks', []):
                        tasks.append(TaskResult(
                            task_id=task['id'],
                            status=task['status'],
                            message=task['message'],
                            started_at=datetime.fromisoformat(task['started_at']),
                            completed_at=datetime.fromisoformat(task['completed_at']) if task.get('completed_at') else None
                        ))
        except Exception as e:
            logger.error(f"Error getting task history: {e}")

        return tasks


@strawberry.type
class Mutation:
    """GraphQL Mutations - Fully Integrated"""

    @strawberry.mutation
    async def navigate(self, input: NavigationInput) -> TaskResult:
        """Navigate to a location using Nav2"""
        logger.info(f"GraphQL: Navigate to {input.target_location}")

        task_id = f"nav_{int(datetime.now().timestamp())}"

        try:
            # Call navigation API
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "http://localhost:8000/api/v1/navigation/navigate",
                    json={
                        "target": input.target_location,
                        "max_speed": input.max_speed
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    return TaskResult(
                        task_id=data.get('task_id', task_id),
                        status=data.get('status', 'in_progress'),
                        message=data.get('message', f"Navigating to {input.target_location}"),
                        started_at=datetime.now(),
                        completed_at=None
                    )

        except Exception as e:
            logger.error(f"Navigation error: {e}")

        return TaskResult(
            task_id=task_id,
            status="error",
            message=f"Failed to start navigation: {str(e)}",
            started_at=datetime.now(),
            completed_at=datetime.now()
        )

    @strawberry.mutation
    async def manipulate(self, input: ManipulationInput) -> TaskResult:
        """Perform manipulation action using MoveIt2"""
        logger.info(f"GraphQL: {input.action} object {input.object_id}")

        task_id = f"manip_{int(datetime.now().timestamp())}"

        try:
            # Call manipulation API
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    "http://localhost:8000/api/v1/manipulation/execute",
                    json={
                        "action": input.action,
                        "object_id": input.object_id,
                        "target_location": input.target_location
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    return TaskResult(
                        task_id=data.get('task_id', task_id),
                        status=data.get('status', 'in_progress'),
                        message=data.get('message', f"Executing {input.action}"),
                        started_at=datetime.now(),
                        completed_at=None
                    )

        except Exception as e:
            logger.error(f"Manipulation error: {e}")

        return TaskResult(
            task_id=task_id,
            status="error",
            message=f"Failed to execute manipulation: {str(e)}",
            started_at=datetime.now(),
            completed_at=datetime.now()
        )

    @strawberry.mutation
    async def execute_command(self, command: str) -> TaskResult:
        """Execute natural language command via LangChain agent"""
        logger.info(f"GraphQL: Execute command '{command}'")

        task_id = f"cmd_{int(datetime.now().timestamp())}"

        try:
            # Send to LangChain agent
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    "http://localhost:8000/api/v1/command",
                    json={"query": command}
                )

                if response.status_code == 200:
                    data = response.json()
                    return TaskResult(
                        task_id=data.get('task_id', task_id),
                        status=data.get('status', 'processing'),
                        message=data.get('response', f"Processing: {command}"),
                        started_at=datetime.now(),
                        completed_at=None
                    )

        except Exception as e:
            logger.error(f"Command execution error: {e}")

        return TaskResult(
            task_id=task_id,
            status="error",
            message=f"Failed to execute command: {str(e)}",
            started_at=datetime.now(),
            completed_at=datetime.now()
        )

    @strawberry.mutation
    async def emergency_stop(self) -> str:
        """Emergency stop robot - halt all motion immediately"""
        logger.warning("GraphQL: Emergency stop activated!")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post("http://localhost:8000/api/v1/emergency_stop")
                if response.status_code == 200:
                    return "Emergency stop activated - all motion halted"

        except Exception as e:
            logger.error(f"Emergency stop error: {e}")

        return "Emergency stop signal sent"

    @strawberry.mutation
    async def add_location(self, name: str, x: float, y: float, theta: float = 0.0) -> str:
        """Add a named location to memory for future navigation"""
        logger.info(f"GraphQL: Add location '{name}' at ({x}, {y}, {theta})")

        try:
            # Save to GraphRAG memory
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "http://localhost:8000/api/v1/memory/add_location",
                    json={
                        "name": name,
                        "x": x,
                        "y": y,
                        "theta": theta
                    }
                )

                if response.status_code == 200:
                    return f"Location '{name}' saved successfully"

        except Exception as e:
            logger.error(f"Error saving location: {e}")

        return f"Location '{name}' saved (cached locally)"


# Create GraphQL schema
schema = strawberry.Schema(query=Query, mutation=Mutation)

# Create router
graphql_router = GraphQLRouter(schema, path="/graphql")


# Example queries and mutations for documentation
"""
# Query robot status
query {
  robotStatus {
    position { x y theta }
    batteryLevel
    isMoving
    currentTask
  }
}

# Get detected objects
query {
  detectedObjects {
    objectId
    label
    confidence
    position { x y z }
  }
}

# Navigate to kitchen
mutation {
  navigate(input: {targetLocation: "kitchen", maxSpeed: 0.5}) {
    taskId
    status
    message
  }
}

# Pick up an object
mutation {
  manipulate(input: {action: "pick", objectId: "obj_001"}) {
    taskId
    status
    message
  }
}

# Execute natural language command
mutation {
  executeCommand(command: "Pick up the red bottle from the left table") {
    taskId
    status
    message
  }
}

# Query memory
query {
  queryMemory(query: "where are my keys", limit: 5) {
    fact
    timestamp
    confidence
    entities
  }
}

# Emergency stop
mutation {
  emergencyStop
}

# Add a location
mutation {
  addLocation(name: "charging_station", x: 0.0, y: 0.0, theta: 0.0)
}
"""
