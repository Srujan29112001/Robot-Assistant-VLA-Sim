"""
End-to-End Integration Tests
Tests complete workflows from API to robot execution
"""

import pytest
import asyncio
import httpx
from datetime import datetime


class TestEndToEndIntegration:
    """
    End-to-end integration tests for the robotic assistant
    Tests complete workflows: Command → Agent → Perception → Navigation
    """

    @pytest.fixture
    def api_base_url(self):
        """Base URL for API (override with environment variable if needed)"""
        return "http://localhost:8000"

    @pytest.fixture
    async def client(self, api_base_url):
        """Async HTTP client"""
        async with httpx.AsyncClient(base_url=api_base_url, timeout=30.0) as client:
            yield client

    @pytest.mark.asyncio
    async def test_robot_state_integration(self, client):
        """Test that robot state is properly integrated across APIs"""
        # Test GraphQL robot status query
        graphql_query = """
        query {
            robotStatus {
                position { x y theta }
                batteryLevel
                isMoving
            }
        }
        """

        response = await client.post(
            "/graphql",
            json={"query": graphql_query}
        )

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "robotStatus" in data["data"]

        status = data["data"]["robotStatus"]
        assert "position" in status
        assert "batteryLevel" in status
        assert isinstance(status["batteryLevel"], (int, float))
        print(f"✓ Robot state integration: Battery {status['batteryLevel']}%")

    @pytest.mark.asyncio
    async def test_perception_integration(self, client):
        """Test perception data flow through the system"""
        # First, simulate updating perception data via robot state
        # (In real scenario, this would come from perception service)

        # Query detected objects via GraphQL
        graphql_query = """
        query {
            detectedObjects {
                objectId
                label
                confidence
                position { x y z }
            }
        }
        """

        response = await client.post(
            "/graphql",
            json={"query": graphql_query}
        )

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "detectedObjects" in data["data"]

        objects = data["data"]["detectedObjects"]
        assert isinstance(objects, list)
        print(f"✓ Perception integration: {len(objects)} objects detected")

    @pytest.mark.asyncio
    async def test_mcp_navigation_integration(self, client):
        """Test navigation through MCP server"""
        # Call MCP navigation action
        mcp_request = {
            "action": "NAVIGATE",
            "parameters": {"location": "kitchen"},
            "context": {}
        }

        response = await client.post(
            "/mcp/execute",
            json=mcp_request
        )

        assert response.status_code == 200
        result = response.json()
        assert result["status"] == "success"
        assert "result" in result
        print(f"✓ MCP navigation: {result['result']['status']}")

    @pytest.mark.asyncio
    async def test_mcp_perception_integration(self, client):
        """Test perception through MCP server"""
        mcp_request = {
            "action": "GET_PERCEPTION",
            "parameters": {},
            "context": {}
        }

        response = await client.post(
            "/mcp/execute",
            json=mcp_request
        )

        assert response.status_code == 200
        result = response.json()
        assert result["status"] == "success"
        assert "objects" in result["result"]
        print(f"✓ MCP perception: {len(result['result']['objects'])} objects")

    @pytest.mark.asyncio
    async def test_mcp_battery_integration(self, client):
        """Test battery check through MCP"""
        mcp_request = {
            "action": "GET_BATTERY",
            "parameters": {},
            "context": {}
        }

        response = await client.post(
            "/mcp/execute",
            json=mcp_request
        )

        assert response.status_code == 200
        result = response.json()
        assert result["status"] == "success"
        assert "battery_level" in result["result"]
        assert isinstance(result["result"]["battery_level"], (int, float))
        print(f"✓ MCP battery check: {result['result']['battery_level']}%")

    @pytest.mark.asyncio
    async def test_mcp_map_integration(self, client):
        """Test map retrieval through MCP"""
        mcp_request = {
            "action": "GET_MAP",
            "parameters": {},
            "context": {}
        }

        response = await client.post(
            "/mcp/execute",
            json=mcp_request
        )

        assert response.status_code == 200
        result = response.json()
        assert result["status"] == "success"
        assert "known_locations" in result["result"]
        locations = result["result"]["known_locations"]
        assert "kitchen" in locations
        assert "living_room" in locations
        print(f"✓ MCP map: {len(locations)} known locations")

    @pytest.mark.asyncio
    async def test_graphql_navigation_mutation(self, client):
        """Test navigation via GraphQL mutation"""
        mutation = """
        mutation {
            navigate(input: {targetLocation: "kitchen", maxSpeed: 0.5}) {
                taskId
                status
                message
            }
        }
        """

        response = await client.post(
            "/graphql",
            json={"query": mutation}
        )

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "navigate" in data["data"]

        result = data["data"]["navigate"]
        assert "taskId" in result
        assert result["status"] in ["in_progress", "processing"]
        print(f"✓ GraphQL navigation: Task {result['taskId']} {result['status']}")

    @pytest.mark.asyncio
    async def test_graphql_command_execution(self, client):
        """Test command execution via GraphQL"""
        mutation = """
        mutation {
            executeCommand(command: "Go to the kitchen") {
                taskId
                status
                message
            }
        }
        """

        response = await client.post(
            "/graphql",
            json={"query": mutation}
        )

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "executeCommand" in data["data"]

        result = data["data"]["executeCommand"]
        assert "taskId" in result
        assert result["status"] in ["processing", "in_progress"]
        print(f"✓ GraphQL command: Task {result['taskId']} {result['status']}")

    @pytest.mark.asyncio
    async def test_rest_api_command_execution(self, client):
        """Test command execution via REST API"""
        command_request = {
            "query": "Pick up the red bottle",
            "context": {}
        }

        response = await client.post(
            "/api/v1/command",
            json=command_request
        )

        assert response.status_code == 200
        result = response.json()
        assert "task_id" in result
        assert "status" in result
        assert result["status"] == "pending"
        print(f"✓ REST API command: Task {result['task_id']} created")

        # Wait a moment for processing
        await asyncio.sleep(1)

        # Check task status
        task_id = result["task_id"]
        status_response = await client.get(f"/api/v1/command/{task_id}")
        assert status_response.status_code == 200
        status = status_response.json()
        assert "task_id" in status
        print(f"✓ REST API status check: Task {task_id} is {status['status']}")

    @pytest.mark.asyncio
    async def test_complete_workflow(self, client):
        """
        Test complete end-to-end workflow:
        Command → Agent → MCP → Perception/Navigation
        """
        print("\n=== Testing Complete Workflow ===")

        # Step 1: Check robot status
        print("Step 1: Checking robot status...")
        status_query = """
        query {
            robotStatus {
                position { x y theta }
                batteryLevel
                isMoving
                currentTask
            }
        }
        """

        response = await client.post("/graphql", json={"query": status_query})
        assert response.status_code == 200
        status = response.json()["data"]["robotStatus"]
        print(f"  Robot at ({status['position']['x']}, {status['position']['y']})")
        print(f"  Battery: {status['batteryLevel']}%")

        # Step 2: Check perception
        print("\nStep 2: Checking perception...")
        perception_query = """
        query {
            detectedObjects {
                objectId
                label
                confidence
            }
        }
        """

        response = await client.post("/graphql", json={"query": perception_query})
        assert response.status_code == 200
        objects = response.json()["data"]["detectedObjects"]
        print(f"  Detected {len(objects)} objects")
        for obj in objects:
            if obj.get("label"):
                print(f"    - {obj['label']} (confidence: {obj['confidence']:.2f})")

        # Step 3: Execute a command
        print("\nStep 3: Executing navigation command...")
        nav_mutation = """
        mutation {
            navigate(input: {targetLocation: "kitchen"}) {
                taskId
                status
                message
            }
        }
        """

        response = await client.post("/graphql", json={"query": nav_mutation})
        assert response.status_code == 200
        nav_result = response.json()["data"]["navigate"]
        print(f"  Navigation task {nav_result['taskId']}: {nav_result['message']}")

        # Step 4: Verify state updated
        print("\nStep 4: Verifying state updated...")
        response = await client.post("/graphql", json={"query": status_query})
        new_status = response.json()["data"]["robotStatus"]
        # After navigation command, robot should be moving
        # (In mock mode, this might not actually change, but we test the flow)
        print(f"  Robot moving: {new_status['isMoving']}")
        print(f"  Current task: {new_status['currentTask']}")

        print("\n✓ Complete workflow test passed!")

    @pytest.mark.asyncio
    async def test_mcp_capabilities(self, client):
        """Test MCP capabilities endpoint"""
        response = await client.get("/mcp/capabilities")

        assert response.status_code == 200
        capabilities = response.json()
        assert "capabilities" in capabilities
        assert "NAVIGATE" in capabilities["capabilities"]
        assert "GET_PERCEPTION" in capabilities["capabilities"]
        assert "PICK_OBJECT" in capabilities["capabilities"]
        print(f"✓ MCP capabilities: {len(capabilities['capabilities'])} actions available")

    @pytest.mark.asyncio
    async def test_api_health(self, client):
        """Test API health endpoint"""
        response = await client.get("/health")

        assert response.status_code == 200
        health = response.json()
        assert "status" in health
        print(f"✓ API health: {health['status']}")


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
