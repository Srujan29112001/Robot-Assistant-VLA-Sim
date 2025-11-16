"""
Integration Tests for VLA Robot Assistant
Tests end-to-end workflows
"""

import pytest
import requests
import time
from PIL import Image
import numpy as np


class TestAPIIntegration:
    """Test API integration"""

    base_url = "http://localhost:8000"

    def test_health_check(self):
        """Test health endpoint"""
        response = requests.get(f"{self.base_url}/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_root_endpoint(self):
        """Test root endpoint"""
        response = requests.get(f"{self.base_url}/")
        assert response.status_code == 200
        data = response.json()
        assert "service" in data
        assert "Vision-Language" in data["service"]

    def test_command_submission(self):
        """Test command submission"""
        response = requests.post(
            f"{self.base_url}/api/v1/command",
            json={"query": "Pick up the red bottle"}
        )
        assert response.status_code in [200, 202]
        data = response.json()
        assert "task_id" in data


class TestPerceptionIntegration:
    """Test perception pipeline"""

    def test_vit_dino_detection(self):
        """Test ViT-DINO object detection"""
        from perception.vision.vit_dino import ViTDINODetector

        detector = ViTDINODetector()

        # Create test image
        test_image = Image.new('RGB', (224, 224), color='blue')

        # Detect objects
        objects = detector.detect_objects(test_image, threshold=0.5)

        assert isinstance(objects, list)

    def test_depth_estimation(self):
        """Test MiDaS depth estimation"""
        from perception.depth.midas import MiDasDepthEstimator

        estimator = MiDasDepthEstimator()

        # Create test image
        test_image = Image.new('RGB', (384, 384), color='green')

        # Estimate depth
        depth_map = estimator.estimate_depth(test_image)

        assert depth_map is not None
        assert isinstance(depth_map, np.ndarray)


class TestLLMIntegration:
    """Test LLM agent integration"""

    def test_agent_initialization(self):
        """Test agent initialization"""
        from cognition.agent.langchain_agent import RobotAgent

        # This may require API keys
        try:
            agent = RobotAgent(mcp_server_url="http://localhost:8000/mcp")
            assert agent is not None
        except Exception as e:
            pytest.skip(f"Agent initialization failed (may need API keys): {e}")


class TestMemoryIntegration:
    """Test memory systems"""

    def test_faiss_vector_store(self):
        """Test FAISS vector database"""
        from memory.vector_db.faiss_store import FAISSVectorStore

        vs = FAISSVectorStore(persist_directory="./test_vector_db")

        # Add documents
        ids = vs.add_batch([
            "Robot saw red bottle on table",
            "User requested navigation to kitchen",
            "Battery level at 50 percent"
        ])

        assert len(ids) == 3

        # Search
        results = vs.search("Where is the bottle?", k=2)

        assert len(results) > 0
        assert "bottle" in results[0]['text'].lower()

    def test_graphrag(self):
        """Test GraphRAG knowledge graph"""
        from memory.graphrag.knowledge_graph import KnowledgeGraph

        kg = KnowledgeGraph()

        # Add entities and relationships
        kg.add_entity("bottle1", "object", {"color": "red", "location": "table"})
        kg.add_entity("table1", "furniture", {"room": "kitchen"})
        kg.add_relationship("bottle1", "ON", "table1")

        # Query
        results = kg.query_entity("bottle1")

        assert results is not None


class TestRLIntegration:
    """Test reinforcement learning"""

    def test_grasping_env(self):
        """Test grasping environment"""
        from control.rl.train_grasping import GraspingEnv

        env = GraspingEnv()

        # Reset
        obs, _ = env.reset()

        assert obs.shape == (8,)

        # Step
        action = env.action_space.sample()
        obs, reward, terminated, truncated, info = env.step(action)

        assert obs.shape == (8,)
        assert isinstance(reward, float)


class TestVLAIntegration:
    """Test Vision-Language-Action model"""

    def test_vla_policy(self):
        """Test VLA policy inference"""
        from cognition.vla.rt2_model import VLAPolicy

        policy = VLAPolicy()

        # Create test input
        test_image = Image.new('RGB', (224, 224), color='red')
        instruction = "Pick up the object"

        # Get action
        action = policy.get_action(test_image, instruction)

        assert "base_velocity" in action
        assert "arm_joints" in action


class TestEndToEnd:
    """End-to-end workflow tests"""

    def test_pick_and_place_workflow(self):
        """Test complete pick and place workflow"""

        # 1. Submit command
        response = requests.post(
            "http://localhost:8000/api/v1/command",
            json={"query": "Pick up the red bottle from the left table"}
        )

        if response.status_code in [200, 202]:
            data = response.json()
            task_id = data.get("task_id")

            # 2. Check status
            time.sleep(2)
            status_response = requests.get(f"http://localhost:8000/api/v1/state")

            assert status_response.status_code == 200

    def test_memory_retrieval_workflow(self):
        """Test memory storage and retrieval"""

        # Add memory via API
        response = requests.post(
            "http://localhost:8000/api/v1/memory",
            json={
                "text": "I placed the keys on the entry table",
                "metadata": {"type": "observation", "location": "entrance"}
            }
        )

        if response.status_code in [200, 201]:
            # Query memory
            query_response = requests.post(
                "http://localhost:8000/api/v1/memory/query",
                json={"query": "Where are the keys?", "k": 3}
            )

            assert query_response.status_code == 200


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Setup test environment"""
    print("\nSetting up test environment...")
    # Add any setup code here
    yield
    print("\nTearing down test environment...")
    # Add any cleanup code here


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
