"""
ViT-DINO Model for Object Detection and Segmentation
Self-supervised vision transformer for feature extraction
"""

import torch
import torch.nn as nn
from transformers import AutoModel, AutoImageProcessor
from PIL import Image
import numpy as np
from typing import List, Dict, Tuple
import logging

logger = logging.getLogger(__name__)


class ViTDINODetector:
    """
    ViT-DINO based object detector
    Uses self-supervised vision transformer for object discovery
    """

    def __init__(self, model_name: str = "facebook/dino-vitb16"):
        """
        Initialize ViT-DINO model

        Args:
            model_name: Hugging Face model identifier
        """
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info(f"Loading ViT-DINO model: {model_name} on {self.device}")

        self.processor = AutoImageProcessor.from_pretrained(model_name)
        self.model = AutoModel.from_pretrained(model_name).to(self.device)
        self.model.eval()

        logger.info("ViT-DINO model loaded successfully")

    @torch.no_grad()
    def extract_features(self, image: Image.Image) -> torch.Tensor:
        """
        Extract dense features from image

        Args:
            image: PIL Image

        Returns:
            Feature tensor of shape (num_patches, feature_dim)
        """
        # Preprocess image
        inputs = self.processor(images=image, return_tensors="pt")
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        # Forward pass
        outputs = self.model(**inputs)

        # Get patch features (excluding CLS token)
        features = outputs.last_hidden_state[:, 1:, :]  # [1, num_patches, dim]

        return features.squeeze(0)

    @torch.no_grad()
    def get_attention_maps(self, image: Image.Image) -> np.ndarray:
        """
        Get attention maps from the model
        These can reveal object boundaries

        Args:
            image: PIL Image

        Returns:
            Attention maps as numpy array
        """
        inputs = self.processor(images=image, return_tensors="pt")
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        outputs = self.model(**inputs, output_attentions=True)

        # Get attention from last layer, last head
        # Shape: [batch, num_heads, seq_len, seq_len]
        attentions = outputs.attentions[-1]

        # Average over heads
        attention = attentions.mean(dim=1)  # [batch, seq_len, seq_len]

        # Get CLS token attention to patches
        cls_attention = attention[0, 0, 1:]  # [num_patches]

        # Reshape to spatial grid
        num_patches = int(np.sqrt(cls_attention.shape[0]))
        attention_map = cls_attention.reshape(num_patches, num_patches)

        return attention_map.cpu().numpy()

    def detect_objects(
        self,
        image: Image.Image,
        threshold: float = 0.6
    ) -> List[Dict]:
        """
        Detect objects in image using attention-based segmentation

        Args:
            image: PIL Image
            threshold: Attention threshold for object detection

        Returns:
            List of detected objects with bounding boxes
        """
        # Get attention map
        attention_map = self.get_attention_maps(image)

        # Threshold to get object regions
        binary_mask = attention_map > threshold

        # Find connected components (simple approach)
        from scipy.ndimage import label as label_components
        labeled, num_objects = label_components(binary_mask)

        objects = []
        for obj_id in range(1, num_objects + 1):
            # Get bounding box
            positions = np.where(labeled == obj_id)
            if len(positions[0]) == 0:
                continue

            y_min, y_max = positions[0].min(), positions[0].max()
            x_min, x_max = positions[1].min(), positions[1].max()

            # Convert to image coordinates
            h, w = image.size[1], image.size[0]
            patch_size = h / attention_map.shape[0]

            bbox = {
                "x_min": int(x_min * patch_size),
                "y_min": int(y_min * patch_size),
                "x_max": int((x_max + 1) * patch_size),
                "y_max": int((y_max + 1) * patch_size),
            }

            # Get features for this object region
            features = self.extract_features(image)
            obj_features = features[positions[0] * attention_map.shape[1] + positions[1]].mean(dim=0)

            objects.append({
                "object_id": f"obj_{obj_id}",
                "bbox": bbox,
                "confidence": float(attention_map[positions[0], positions[1]].mean()),
                "embedding": obj_features.cpu().numpy().tolist(),
            })

        logger.info(f"Detected {len(objects)} objects")
        return objects

    def get_global_embedding(self, image: Image.Image) -> np.ndarray:
        """
        Get global image embedding (CLS token)

        Args:
            image: PIL Image

        Returns:
            Global embedding vector
        """
        inputs = self.processor(images=image, return_tensors="pt")
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        outputs = self.model(**inputs)

        # CLS token is first token
        cls_embedding = outputs.last_hidden_state[:, 0, :]

        return cls_embedding.squeeze(0).cpu().numpy()


# Example usage
if __name__ == "__main__":
    detector = ViTDINODetector()

    # Test with dummy image
    test_image = Image.new('RGB', (224, 224), color='red')
    objects = detector.detect_objects(test_image)
    print(f"Detected {len(objects)} objects")
