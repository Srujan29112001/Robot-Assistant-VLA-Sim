"""
Tests for FastAPI backend
"""

import pytest
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


def test_root_endpoint():
    """Test root endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "Vision-Language Robotic Assistant"
    assert "version" in data


def test_health_check():
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_command_execution():
    """Test command execution"""
    response = client.post(
        "/api/v1/command",
        json={"query": "Navigate to the kitchen"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "task_id" in data
    assert data["status"] in ["pending", "in_progress"]


def test_robot_state():
    """Test robot state endpoint"""
    response = client.get("/api/v1/state")
    assert response.status_code == 200
    data = response.json()
    assert "position" in data
    assert "battery_level" in data
    assert "gripper_state" in data


def test_mcp_capabilities():
    """Test MCP capabilities endpoint"""
    response = client.get("/mcp/capabilities")
    assert response.status_code == 200
    data = response.json()
    assert "capabilities" in data
    assert "NAVIGATE" in data["capabilities"]
    assert "GET_PERCEPTION" in data["capabilities"]


def test_mcp_execute():
    """Test MCP execute endpoint"""
    response = client.post(
        "/mcp/execute",
        json={
            "action": "GET_BATTERY",
            "parameters": {}
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["success", "failure"]
    assert "result" in data
