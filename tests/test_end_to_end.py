"""
End-to-End Integration Tests
Tests complete workflows from user command to robot execution
"""

import pytest
import httpx
import asyncio
from typing import Dict, Any
import time
import logging

logger = logging.getLogger(__name__)

# Test configuration
API_BASE_URL = "http://localhost:8000"
TIMEOUT = 60.0  # seconds


@pytest.mark.asyncio
@pytest.mark.integration
class TestEndToEndWorkflows:
    """End-to-end workflow tests"""

    @pytest.fixture(autouse=True)
    async def setup(self):
        """Setup test environment"""
        # Wait for services to be ready
        await self._wait_for_api()

    async def _wait_for_api(self, max_retries=30):
        """Wait for API to be ready"""
        for i in range(max_retries):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(f"{API_BASE_URL}/health")
                    if response.status_code == 200:
                        logger.info("API is ready")
                        return
            except:
                pass
            await asyncio.sleep(1)

        raise RuntimeError("API did not become ready in time")

    async def test_health_check(self):
        """Test system health"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{API_BASE_URL}/health")

            assert response.status_code == 200
            data = response.json()

            assert data['status'] == 'healthy'
            assert 'services' in data

    async def test_perception_pipeline(self):
        """Test perception system end-to-end"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            # Get current perception
            response = await client.get(f"{API_BASE_URL}/api/v1/perception/objects")

            assert response.status_code in [200, 404]  # 404 if no objects detected

            if response.status_code == 200:
                data = response.json()
                assert 'objects' in data

                # Verify object structure
                if len(data['objects']) > 0:
                    obj = data['objects'][0]
                    assert 'id' in obj
                    assert 'label' in obj or 'type' in obj
                    assert 'confidence' in obj

    async def test_memory_system(self):
        """Test GraphRAG memory system"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            # Add a fact to memory
            add_response = await client.post(
                f"{API_BASE_URL}/api/v1/memory/add",
                json={
                    "fact": "Test bottle is on table A",
                    "entities": ["bottle", "table_a"]
                }
            )

            assert add_response.status_code in [200, 201]

            # Query memory
            query_response = await client.post(
                f"{API_BASE_URL}/api/v1/memory/query",
                json={
                    "query": "where is the bottle",
                    "limit": 5
                }
            )

            assert query_response.status_code == 200
            data = query_response.json()
            assert 'results' in data

    async def test_navigation_command(self):
        """Test navigation command execution"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            # Send navigation command
            response = await client.post(
                f"{API_BASE_URL}/api/v1/navigation/navigate",
                json={
                    "target": "home",
                    "max_speed": 0.3
                }
            )

            assert response.status_code in [200, 202]  # 202 = Accepted
            data = response.json()

            assert 'task_id' in data or 'status' in data

    async def test_manipulation_command(self):
        """Test manipulation command"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            # Send pick command
            response = await client.post(
                f"{API_BASE_URL}/api/v1/manipulation/execute",
                json={
                    "action": "pick",
                    "object_id": "test_obj_001"
                }
            )

            # May fail if object not found, but should return valid response
            assert response.status_code in [200, 202, 404]

    async def test_natural_language_command(self):
        """Test end-to-end natural language command processing"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            # Send NL command
            command = "Move to the kitchen"

            response = await client.post(
                f"{API_BASE_URL}/api/v1/command",
                json={"query": command}
            )

            assert response.status_code in [200, 202]
            data = response.json()

            assert 'task_id' in data or 'response' in data
            assert 'status' in data

    async def test_complete_pick_and_place_workflow(self):
        """
        Complete pick-and-place workflow test
        1. Perceive object
        2. Plan grasp
        3. Navigate to object
        4. Pick object
        5. Navigate to target
        6. Place object
        """
        async with httpx.AsyncClient(timeout=120.0) as client:
            # Step 1: Get objects from perception
            perception_response = await client.get(
                f"{API_BASE_URL}/api/v1/perception/objects"
            )

            # Step 2: Send complete pick and place command via LangChain agent
            command = "Pick up the bottle and place it on the table"

            response = await client.post(
                f"{API_BASE_URL}/api/v1/command",
                json={"query": command}
            )

            # Command should be accepted
            assert response.status_code in [200, 202]
            data = response.json()

            # Should have task ID
            if 'task_id' in data:
                task_id = data['task_id']

                # Poll for task completion (with timeout)
                for _ in range(30):
                    status_response = await client.get(
                        f"{API_BASE_URL}/api/v1/tasks/{task_id}"
                    )

                    if status_response.status_code == 200:
                        status_data = status_response.json()

                        if status_data.get('status') in ['completed', 'failed', 'error']:
                            logger.info(f"Task {task_id} finished with status: {status_data['status']}")
                            break

                    await asyncio.sleep(2)

    async def test_graphql_query(self):
        """Test GraphQL API"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            # GraphQL query
            query = """
            query {
                robotStatus {
                    position { x y theta }
                    batteryLevel
                    isMoving
                }
            }
            """

            response = await client.post(
                f"{API_BASE_URL}/graphql",
                json={"query": query}
            )

            assert response.status_code == 200
            data = response.json()

            assert 'data' in data
            assert 'robotStatus' in data['data']

    async def test_graphql_mutation(self):
        """Test GraphQL mutation"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            # GraphQL mutation
            mutation = """
            mutation {
                addLocation(name: "test_location", x: 1.0, y: 2.0, theta: 0.0)
            }
            """

            response = await client.post(
                f"{API_BASE_URL}/graphql",
                json={"query": mutation}
            )

            assert response.status_code == 200
            data = response.json()

            assert 'data' in data

    async def test_emergency_stop(self):
        """Test emergency stop functionality"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            # Trigger emergency stop
            response = await client.post(f"{API_BASE_URL}/api/v1/emergency_stop")

            assert response.status_code == 200
            data = response.json()

            assert 'status' in data or 'message' in data


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.slow
class TestSystemPerformance:
    """Performance and load tests"""

    async def test_api_response_time(self):
        """Test API response times"""
        async with httpx.AsyncClient() as client:
            start = time.time()

            response = await client.get(f"{API_BASE_URL}/health")

            elapsed = time.time() - start

            assert response.status_code == 200
            assert elapsed < 1.0  # Should respond in < 1 second

    async def test_concurrent_requests(self):
        """Test handling of concurrent requests"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Send multiple requests concurrently
            tasks = [
                client.get(f"{API_BASE_URL}/health")
                for _ in range(10)
            ]

            responses = await asyncio.gather(*tasks)

            # All should succeed
            assert all(r.status_code == 200 for r in responses)

    async def test_perception_throughput(self):
        """Test perception system throughput"""
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Measure how many perception requests can be handled
            start = time.time()
            num_requests = 10

            tasks = [
                client.get(f"{API_BASE_URL}/api/v1/perception/objects")
                for _ in range(num_requests)
            ]

            responses = await asyncio.gather(*tasks, return_exceptions=True)

            elapsed = time.time() - start

            # Calculate throughput
            successful = sum(1 for r in responses if not isinstance(r, Exception) and r.status_code == 200)
            throughput = successful / elapsed

            logger.info(f"Perception throughput: {throughput:.2f} req/sec")

            # Should handle at least 1 request per second
            assert throughput >= 1.0


@pytest.mark.integration
class TestSystemResilience:
    """Test system resilience and error handling"""

    async def test_invalid_command(self):
        """Test handling of invalid commands"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.post(
                f"{API_BASE_URL}/api/v1/command",
                json={"query": ""}  # Empty command
            )

            # Should return error status
            assert response.status_code in [400, 422]

    async def test_navigation_to_invalid_location(self):
        """Test navigation to non-existent location"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.post(
                f"{API_BASE_URL}/api/v1/navigation/navigate",
                json={"target": "non_existent_location_xyz"}
            )

            # Should handle gracefully
            assert response.status_code in [200, 404]

            if response.status_code == 200:
                data = response.json()
                # Should indicate error or planning failure
                assert 'status' in data


# Test fixtures
@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "-s", "--log-cli-level=INFO"])
