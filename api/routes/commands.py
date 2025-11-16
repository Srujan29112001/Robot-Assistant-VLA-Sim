"""
Command execution endpoints
Handles natural language commands to the robot
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from typing import List
import uuid
import logging
import asyncio
from datetime import datetime

from api.models.schemas import (
    CommandRequest,
    CommandResponse,
    TaskStatus,
    TaskUpdate
)
from api.utils.database import get_redis
from api.mcp.agent_interface import execute_command_with_agent

router = APIRouter()
logger = logging.getLogger(__name__)

# In-memory task storage (in production, use Redis or PostgreSQL)
tasks = {}


@router.post("/command", response_model=CommandResponse)
async def execute_command(
    command: CommandRequest,
    background_tasks: BackgroundTasks
):
    """
    Execute a natural language command

    The command is processed by the LLM agent which:
    1. Parses the intent
    2. Plans the execution steps
    3. Calls appropriate tools (perception, navigation, manipulation)
    4. Returns status updates
    """
    try:
        # Generate unique task ID
        task_id = str(uuid.uuid4())

        # Store task
        tasks[task_id] = {
            "id": task_id,
            "command": command.query,
            "status": TaskStatus.PENDING,
            "created_at": datetime.utcnow(),
            "progress": 0.0
        }

        # Execute command in background
        background_tasks.add_task(
            execute_command_with_agent,
            task_id,
            command.query,
            command.context or {}
        )

        logger.info(f"Command received: {command.query} (Task ID: {task_id})")

        return CommandResponse(
            task_id=task_id,
            status=TaskStatus.PENDING,
            message=f"Command accepted: '{command.query}'",
            estimated_duration=None
        )

    except Exception as e:
        logger.error(f"Error executing command: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/command/{task_id}", response_model=TaskUpdate)
async def get_task_status(task_id: str):
    """Get the status of a task"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    task = tasks[task_id]
    return TaskUpdate(
        task_id=task_id,
        status=task["status"],
        progress=task.get("progress", 0.0),
        current_step=task.get("current_step"),
        error=task.get("error")
    )


@router.get("/commands", response_model=List[TaskUpdate])
async def list_tasks(limit: int = 10, status: str = None):
    """List recent tasks"""
    task_list = list(tasks.values())

    # Filter by status if provided
    if status:
        task_list = [t for t in task_list if t["status"] == status]

    # Sort by creation time
    task_list.sort(key=lambda x: x["created_at"], reverse=True)

    return [
        TaskUpdate(
            task_id=t["id"],
            status=t["status"],
            progress=t.get("progress", 0.0),
            current_step=t.get("current_step"),
            error=t.get("error")
        )
        for t in task_list[:limit]
    ]


@router.delete("/command/{task_id}")
async def cancel_task(task_id: str):
    """Cancel a running task"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    task = tasks[task_id]
    if task["status"] in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
        raise HTTPException(status_code=400, detail="Task already finished")

    task["status"] = TaskStatus.CANCELLED
    logger.info(f"Task {task_id} cancelled")

    return {"message": "Task cancelled successfully"}
