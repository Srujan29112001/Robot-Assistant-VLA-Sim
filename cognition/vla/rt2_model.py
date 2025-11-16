"""
RT-2 (Robotics Transformer 2) - Vision-Language-Action Model
Inspired by DeepMind's RT-2 for end-to-end vision-language-action policy
"""

import torch
import torch.nn as nn
from transformers import AutoModel, AutoTokenizer, AutoImageProcessor
from typing import Dict, List, Any, Tuple
from PIL import Image
import logging
import numpy as np

logger = logging.getLogger(__name__)


class RT2VLAModel(nn.Module):
    """
    Vision-Language-Action Model
    Combines vision encoder + language model to output robot actions
    """

    def __init__(
        self,
        vision_model: str = "google/vit-base-patch16-224",
        language_model: str = "google/flan-t5-base",
        action_dim: int = 7,  # e.g., 3 for base (x,y,theta) + 4 for arm joints
        num_action_bins: int = 256,  # Discretize continuous actions
    ):
        super().__init__()

        self.action_dim = action_dim
        self.num_action_bins = num_action_bins

        # Vision encoder
        logger.info(f"Loading vision encoder: {vision_model}")
        self.vision_encoder = AutoModel.from_pretrained(vision_model)
        self.vision_processor = AutoImageProcessor.from_pretrained(vision_model)
        vision_hidden_size = self.vision_encoder.config.hidden_size

        # Language model
        logger.info(f"Loading language model: {language_model}")
        self.language_model = AutoModel.from_pretrained(language_model)
        self.tokenizer = AutoTokenizer.from_pretrained(language_model)
        language_hidden_size = self.language_model.config.d_model

        # Multimodal fusion
        self.fusion_layer = nn.Sequential(
            nn.Linear(vision_hidden_size + language_hidden_size, 512),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(512, 512),
        )

        # Action head - predicts discretized actions
        # Each action dimension is binned into num_action_bins classes
        self.action_head = nn.ModuleList([
            nn.Linear(512, num_action_bins) for _ in range(action_dim)
        ])

        logger.info(f"RT-2 VLA model initialized: action_dim={action_dim}, bins={num_action_bins}")

    def encode_vision(self, images: torch.Tensor) -> torch.Tensor:
        """
        Encode images to visual features

        Args:
            images: Batch of images [B, C, H, W]

        Returns:
            Visual embeddings [B, vision_dim]
        """
        outputs = self.vision_encoder(pixel_values=images)
        # Use CLS token or mean pooling
        if hasattr(outputs, 'pooler_output'):
            visual_features = outputs.pooler_output
        else:
            visual_features = outputs.last_hidden_state[:, 0, :]  # CLS token
        return visual_features

    def encode_language(self, text_inputs: Dict[str, torch.Tensor]) -> torch.Tensor:
        """
        Encode language instructions

        Args:
            text_inputs: Tokenized text

        Returns:
            Language embeddings [B, language_dim]
        """
        outputs = self.language_model(**text_inputs)
        # Use last hidden state mean or specific token
        language_features = outputs.last_hidden_state.mean(dim=1)
        return language_features

    def forward(
        self,
        images: torch.Tensor,
        text_inputs: Dict[str, torch.Tensor],
    ) -> torch.Tensor:
        """
        Forward pass: image + text -> action logits

        Args:
            images: Batch of images [B, C, H, W]
            text_inputs: Tokenized instructions

        Returns:
            Action logits [B, action_dim, num_action_bins]
        """
        # Encode vision and language
        visual_features = self.encode_vision(images)
        language_features = self.encode_language(text_inputs)

        # Fuse multimodal features
        combined = torch.cat([visual_features, language_features], dim=-1)
        fused_features = self.fusion_layer(combined)

        # Predict actions
        action_logits = [head(fused_features) for head in self.action_head]
        action_logits = torch.stack(action_logits, dim=1)  # [B, action_dim, num_bins]

        return action_logits

    def predict_action(
        self,
        image: Image.Image,
        instruction: str,
        temperature: float = 1.0,
    ) -> np.ndarray:
        """
        Predict robot action from image and instruction

        Args:
            image: PIL Image
            instruction: Natural language instruction
            temperature: Sampling temperature

        Returns:
            Predicted action vector (normalized to [-1, 1])
        """
        self.eval()
        with torch.no_grad():
            # Preprocess image
            image_inputs = self.vision_processor(images=image, return_tensors="pt")
            images = image_inputs['pixel_values'].to(next(self.parameters()).device)

            # Tokenize instruction
            text_inputs = self.tokenizer(
                instruction,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=128
            )
            text_inputs = {k: v.to(next(self.parameters()).device) for k, v in text_inputs.items()}

            # Forward pass
            action_logits = self.forward(images, text_inputs)

            # Sample or take argmax for each action dimension
            if temperature > 0:
                probs = torch.softmax(action_logits / temperature, dim=-1)
                action_bins = torch.multinomial(probs.view(-1, self.num_action_bins), 1)
                action_bins = action_bins.view(self.action_dim)
            else:
                action_bins = action_logits.argmax(dim=-1).squeeze(0)

            # Convert bins to continuous actions [-1, 1]
            actions = (action_bins.float() / (self.num_action_bins - 1)) * 2 - 1

            return actions.cpu().numpy()


class VLAPolicy:
    """
    High-level policy wrapper for VLA model
    """

    def __init__(
        self,
        model_path: str = None,
        device: str = "cuda" if torch.cuda.is_available() else "cpu"
    ):
        self.device = torch.device(device)

        # Initialize model
        self.model = RT2VLAModel()
        self.model.to(self.device)

        # Load pretrained weights if provided
        if model_path:
            logger.info(f"Loading VLA model from {model_path}")
            self.model.load_state_dict(torch.load(model_path, map_location=self.device))

        self.model.eval()
        logger.info("VLA Policy initialized")

    def get_action(
        self,
        image: Image.Image,
        instruction: str,
        robot_state: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Get robot action for given observation and instruction

        Args:
            image: Current camera image
            instruction: Language command
            robot_state: Current robot state (optional, for context)

        Returns:
            Action dictionary with base and arm commands
        """
        # Predict raw action vector
        action = self.model.predict_action(image, instruction)

        # Parse action into robot commands
        # Assuming action[0:3] = base (x, y, theta), action[3:7] = arm joints
        result = {
            "base_velocity": {
                "linear_x": float(action[0] * 0.5),  # Scale to max speed
                "linear_y": float(action[1] * 0.5),
                "angular_z": float(action[2] * 1.0),
            },
            "arm_joints": action[3:7].tolist() if len(action) > 3 else [],
            "gripper": "close" if len(action) > 7 and action[7] > 0 else "open",
            "confidence": 0.9,  # Could compute from logits entropy
        }

        return result

    def save(self, path: str):
        """Save model weights"""
        torch.save(self.model.state_dict(), path)
        logger.info(f"VLA model saved to {path}")


# Example usage and training stub
if __name__ == "__main__":
    # Initialize policy
    policy = VLAPolicy()

    # Test inference
    test_image = Image.new('RGB', (224, 224), color='blue')
    instruction = "Pick up the red bottle from the table"

    action = policy.get_action(test_image, instruction)
    print(f"Predicted action: {action}")
