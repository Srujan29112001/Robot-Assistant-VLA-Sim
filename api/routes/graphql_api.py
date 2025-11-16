"""
GraphQL API for Robot Control
Provides flexible query and mutation interface
"""

import strawberry
from strawberry.fastapi import GraphQLRouter
from typing import List, Optional
from datetime import datetime
import asyncio
import logging
import httpx
import os

from api.utils.robot_state import robot_state, get_robot_status, get_detected_objects

logger = logging.getLogger(__name__)

# GraphRAG client (lazy loaded)
_knowledge_graph = None


async def get_knowledge_graph():
    """Get or create GraphRAG knowledge graph client"""
    global _knowledge_graph
    if _knowledge_graph is None:
        try:
            from memory.graphrag.knowledge_graph import KnowledgeGraph
            neo4j_uri = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
            neo4j_user = os.getenv("NEO4J_USER", "neo4j")
            neo4j_password = os.getenv("NEO4J_PASSWORD", "password")
            _knowledge_graph = KnowledgeGraph(neo4j_uri, neo4j_user, neo4j_password)
            logger.info("GraphRAG knowledge graph initialized")
        except Exception as e:
            logger.warning(f"Could not initialize GraphRAG: {e}")
            _knowledge_graph = None
    return _knowledge_graph


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
    """GraphQL Queries"""

    @strawberry.field
    async def robot_status(self) -> RobotStatus:
        """Get current robot status"""
        # Integrated with actual robot state
        status = await get_robot_status()
        pos = status["position"]

        return RobotStatus(
            position=RobotPosition(
                x=pos["x"],
                y=pos["y"],
                z=pos["z"],
                theta=pos["theta"]
            ),
            battery_level=status["battery_level"],
            is_moving=status["is_moving"],
            current_task=status["current_task"],
            holding_object=status["holding_object"]
        )

    @strawberry.field
    async def detected_objects(self) -> List[ObjectInfo]:
        """Get currently detected objects"""
        # Integrated with perception system
        objects = await get_detected_objects()

        result = []
        for obj in objects:
            pos = None
            if obj.get("position"):
                p = obj["position"]
                pos = RobotPosition(
                    x=p["x"],
                    y=p["y"],
                    z=p["z"],
                    theta=p["theta"]
                )

            result.append(ObjectInfo(
                object_id=obj["object_id"],
                label=obj.get("label"),
                confidence=obj["confidence"],
                position=pos
            ))

        return result

    @strawberry.field
    async def query_memory(self, query: str, limit: int = 10) -> List[MemoryEntry]:
        """Query robot's long-term memory"""
        # Integrated with GraphRAG
        kg = await get_knowledge_graph()

        if kg is None:
            # Fallback if GraphRAG not available
            logger.warning("GraphRAG not available, returning empty results")
            return []

        try:
            facts = await kg.query_graph(query, limit)

            results = []
            for fact in facts:
                # Convert graph result to MemoryEntry
                fact_text = f"{fact.get('entity', 'Unknown')} {fact.get('relation', '-')} {fact.get('target', 'Unknown')}"
                if "location" in fact:
                    fact_text = f"{fact['object']} is at {fact['location']}"

                entities = [
                    fact.get('entity', ''),
                    fact.get('target', ''),
                    fact.get('object', ''),
                    fact.get('location', '')
                ]
                entities = [e for e in entities if e]  # Filter empty strings

                results.append(MemoryEntry(
                    fact=fact_text,
                    timestamp=datetime.fromtimestamp(fact.get('timestamp', datetime.now().timestamp()) / 1000)
                    if 'timestamp' in fact else datetime.now(),
                    confidence=0.9,
                    entities=entities
                ))

            return results

        except Exception as e:
            logger.error(f"GraphRAG query failed: {e}", exc_info=True)
            return []

    @strawberry.field
    async def get_map_info(self) -> str:
        """Get SLAM map information"""
        return "Map: 10x10m, resolution: 0.05m/pixel"

    @strawberry.field
    async def task_history(self, limit: int = 20) -> List[TaskResult]:
        """Get task execution history"""
        return [
            TaskResult(
                task_id="task_001",
                status="completed",
                message="Successfully picked up bottle",
                started_at=datetime.now(),
                completed_at=datetime.now()
            )
        ]


@strawberry.type
class Mutation:
    """GraphQL Mutations"""

    @strawberry.mutation
    async def navigate(self, input: NavigationInput) -> TaskResult:
        """Navigate to a location"""
        logger.info(f"GraphQL: Navigate to {input.target_location}")

        # Call actual navigation system via MCP
        task_id = f"nav_{int(datetime.now().timestamp())}"

        try:
            # Call MCP server for navigation
            mcp_url = os.getenv("MCP_SERVER_URL", "http://localhost:8000/mcp")
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{mcp_url}/execute",
                    json={
                        "action": "NAVIGATE",
                        "parameters": {"location": input.target_location},
                        "context": {}
                    }
                )
                response.raise_for_status()
                result = response.json()

            # Update robot state
            await robot_state.set_moving(True)
            await robot_state.set_current_task(f"Navigating to {input.target_location}")

            status = "in_progress" if result.get("status") == "success" else "failed"
            message = f"Navigating to {input.target_location}"
            if status == "failed":
                message = f"Navigation failed: {result.get('error', 'Unknown error')}"

            return TaskResult(
                task_id=task_id,
                status=status,
                message=message,
                started_at=datetime.now(),
                completed_at=None
            )

        except Exception as e:
            logger.error(f"Navigation request failed: {e}", exc_info=True)
            return TaskResult(
                task_id=task_id,
                status="failed",
                message=f"Navigation error: {str(e)}",
                started_at=datetime.now(),
                completed_at=datetime.now()
            )

    @strawberry.mutation
    async def manipulate(self, input: ManipulationInput) -> TaskResult:
        """Perform manipulation action"""
        logger.info(f"GraphQL: {input.action} object {input.object_id}")

        task_id = f"manip_{int(datetime.now().timestamp())}"

        return TaskResult(
            task_id=task_id,
            status="in_progress",
            message=f"Executing {input.action}",
            started_at=datetime.now(),
            completed_at=None
        )

    @strawberry.mutation
    async def execute_command(self, command: str) -> TaskResult:
        """Execute natural language command"""
        logger.info(f"GraphQL: Execute command '{command}'")

        task_id = f"cmd_{int(datetime.now().timestamp())}"

        # Integrated with LangChain agent via agent interface
        try:
            from api.mcp.agent_interface import execute_command_with_agent

            # Execute command asynchronously (don't wait for completion)
            asyncio.create_task(execute_command_with_agent(task_id, command, {}))

            # Update robot state
            await robot_state.set_current_task(command)

            return TaskResult(
                task_id=task_id,
                status="processing",
                message=f"Processing command: {command}",
                started_at=datetime.now(),
                completed_at=None
            )

        except Exception as e:
            logger.error(f"Command execution failed: {e}", exc_info=True)
            return TaskResult(
                task_id=task_id,
                status="failed",
                message=f"Error: {str(e)}",
                started_at=datetime.now(),
                completed_at=datetime.now()
            )

    @strawberry.mutation
    async def emergency_stop(self) -> str:
        """Emergency stop robot"""
        logger.warn("GraphQL: Emergency stop activated")
        # TODO: Stop all robot motion
        return "Emergency stop activated"

    @strawberry.mutation
    async def add_location(self, name: str, x: float, y: float, theta: float = 0.0) -> str:
        """Add a named location to memory"""
        logger.info(f"GraphQL: Add location '{name}' at ({x}, {y}, {theta})")
        # TODO: Save to memory
        return f"Location '{name}' added"


# Create GraphQL schema
schema = strawberry.Schema(query=Query, mutation=Mutation)

# Create router
graphql_router = GraphQLRouter(schema, path="/graphql")


# Example queries for testing
"""
# Query robot status
query {
  robotStatus {
    position { x y theta }
    batteryLevel
    isMoving
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

# Execute command
mutation {
  executeCommand(command: "Pick up the red bottle from the table") {
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
  }
}
"""
