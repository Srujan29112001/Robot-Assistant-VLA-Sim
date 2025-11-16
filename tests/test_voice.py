"""
Tests for voice interface (STT/TTS)
"""

import pytest
import torch
import numpy as np
from PIL import Image


class TestVoiceInterface:
    """Test voice interface components"""

    def test_stt_initialization(self):
        """Test STT model initialization"""
        try:
            from perception.voice.stt import WhisperSTT
            stt = WhisperSTT(model_size="tiny")
            assert stt.model is not None
            assert stt.device in ["cuda", "cpu"]
        except ImportError:
            pytest.skip("Whisper not installed")

    def test_tts_initialization(self):
        """Test TTS initialization"""
        try:
            from perception.voice.tts import SimpleTTS
            tts = SimpleTTS()
            assert tts is not None
        except ImportError:
            pytest.skip("TTS not installed")

    def test_voice_api_endpoints(self):
        """Test voice API endpoints exist"""
        from api.routes import voice
        assert hasattr(voice, 'router')
        assert hasattr(voice, 'initialize_voice_services')


class TestMamba2:
    """Test Mamba2 SSM architecture"""

    def test_mamba2_block(self):
        """Test Mamba2 block forward pass"""
        from cognition.llm.mamba2_model import Mamba2Block

        block = Mamba2Block(d_model=256, d_state=32)
        x = torch.randn(2, 10, 256)  # (batch, seq, dim)

        output = block(x)
        assert output.shape == x.shape

    def test_mamba2_lm(self):
        """Test Mamba2 language model"""
        from cognition.llm.mamba2_model import Mamba2LM

        model = Mamba2LM(vocab_size=1000, d_model=256, n_layers=2)
        input_ids = torch.randint(0, 1000, (2, 10))

        logits, _ = model(input_ids)
        assert logits.shape == (2, 10, 1000)

    def test_hybrid_model(self):
        """Test hybrid Mamba2+Transformer"""
        from cognition.llm.mamba2_integration import HybridMamba2Transformer

        model = HybridMamba2Transformer(
            vocab_size=1000,
            d_model=256,
            n_mamba_layers=2,
            n_transformer_layers=2
        )

        input_ids = torch.randint(0, 1000, (2, 10))
        output = model(input_ids)

        assert "logits" in output
        assert output["logits"].shape == (2, 10, 1000)


class TestDeepSeekOCR:
    """Test DeepSeek OCR implementation"""

    def test_text_to_image_encoder(self):
        """Test text-to-image encoding"""
        from perception.ocr.deepseek_ocr import TextToImageEncoder

        encoder = TextToImageEncoder()
        text = "Test robotic command text"

        img = encoder.encode_text_to_image(text)
        assert isinstance(img, Image.Image)
        assert img.size == (encoder.image_width, encoder.image_height)

    def test_token_savings(self):
        """Test token savings estimation"""
        from perception.ocr.deepseek_ocr import TextToImageEncoder

        encoder = TextToImageEncoder()
        text = "A" * 1000  # 1000 characters

        savings = encoder.estimate_token_savings(text)
        assert savings["compression_ratio"] > 1.0
        assert savings["tokens_saved"] > 0

    def test_deepseek_ocr_integration(self):
        """Test DeepSeek OCR class"""
        from perception.ocr.deepseek_ocr import DeepSeekOCR

        ocr = DeepSeekOCR(use_compression=True)
        assert ocr.use_compression == True


class Test3DGS:
    """Test 3D Gaussian Splatting"""

    def test_gaussian_scene_init(self):
        """Test Gaussian scene initialization"""
        from perception.reconstruction.gaussian_splatting import GaussianScene

        scene = GaussianScene(num_gaussians=100, use_spherical_harmonics=True)
        assert scene.num_gaussians == 100
        assert scene.positions.shape == (100, 3)

    def test_gaussian_splatter(self):
        """Test Gaussian splatter renderer"""
        from perception.reconstruction.gaussian_splatting import GaussianSplatter, GaussianScene

        scene = GaussianScene(num_gaussians=50)
        renderer = GaussianSplatter(image_width=320, image_height=240)

        camera_pos = torch.tensor([0., 0., 5.])
        camera_rot = torch.eye(3)
        camera_intrinsics = torch.tensor([
            [250., 0., 160.],
            [0., 250., 120.],
            [0., 0., 1.]
        ])

        image = renderer.render(scene, camera_pos, camera_rot, camera_intrinsics)
        assert image.shape == (240, 320, 3)


class TestSayCan:
    """Test SayCan planning"""

    def test_saycan_planner_init(self):
        """Test SayCan planner initialization"""
        from cognition.planning.saycan import SayCanPlanner

        class MockLLM:
            pass

        planner = SayCanPlanner(llm_model=MockLLM())
        assert planner.action_library is not None
        assert len(planner.action_library) > 0

    def test_affordance_function(self):
        """Test affordance function"""
        from cognition.planning.saycan import AffordanceFunction

        model = AffordanceFunction(state_dim=64, action_dim=16)
        state = torch.randn(2, 64)
        action = torch.randn(2, 16)

        affordance = model(state, action)
        assert affordance.shape == (2, 1)
        assert (affordance >= 0).all() and (affordance <= 1).all()


class TestMultiRobot:
    """Test multi-robot coordination"""

    def test_fleet_manager(self):
        """Test fleet manager"""
        from control.multi_robot.coordinator import FleetManager, RobotStatus

        fleet = FleetManager()

        # Register robots
        assert fleet.register_robot("r1", "Robot-1", ["nav", "grasp"])
        assert len(fleet.robots) == 1

        # Add task
        task = fleet.add_task("t1", "Pick object", ["grasp"], priority=1)
        assert task.task_id == "t1"

        # Allocate
        allocations = fleet.allocate_tasks()
        assert "t1" in allocations

    def test_robot_coordinator(self):
        """Test robot coordinator"""
        from control.multi_robot.coordinator import RobotCoordinator, FleetManager

        fleet = FleetManager()
        coordinator = RobotCoordinator(fleet)
        assert coordinator.fleet == fleet


class TestSecurity:
    """Test security components"""

    def test_jwt_creation(self):
        """Test JWT token creation"""
        from api.security.jwt_auth import JWTAuthenticator

        auth = JWTAuthenticator()
        token = auth.create_access_token({"sub": "test_user"})

        assert isinstance(token, str)
        assert len(token) > 0

    def test_jwt_verification(self):
        """Test JWT verification"""
        from api.security.jwt_auth import JWTAuthenticator

        auth = JWTAuthenticator()
        token = auth.create_access_token({"sub": "test_user", "role": "admin"})

        payload = auth.verify_token(token)
        assert payload["sub"] == "test_user"
        assert payload["role"] == "admin"

    def test_password_hashing(self):
        """Test password hashing"""
        from api.security.jwt_auth import JWTAuthenticator

        auth = JWTAuthenticator()
        password = "secure_password_123"

        hashed = auth.hash_password(password)
        assert hashed != password
        assert auth.verify_password(password, hashed)
        assert not auth.verify_password("wrong_password", hashed)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
