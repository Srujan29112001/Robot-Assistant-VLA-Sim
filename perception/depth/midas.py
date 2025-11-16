"""
MiDaS Monocular Depth Estimation
Estimates depth from single RGB image
"""

import torch
import cv2
import numpy as np
from PIL import Image
from typing import Tuple
import logging

logger = logging.getLogger(__name__)


class MiDaSDepthEstimator:
    """
    MiDaS depth estimation model
    Provides relative depth maps from monocular images
    """

    def __init__(self, model_type: str = "DPT_Large"):
        """
        Initialize MiDaS model

        Args:
            model_type: Model variant (DPT_Large, DPT_Hybrid, MiDaS_small)
        """
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info(f"Loading MiDaS model: {model_type} on {self.device}")

        # Load model from torch hub
        self.model = torch.hub.load("intel-isl/MiDaS", model_type)
        self.model.to(self.device)
        self.model.eval()

        # Load transforms
        midas_transforms = torch.hub.load("intel-isl/MiDaS", "transforms")
        if model_type in ["DPT_Large", "DPT_Hybrid"]:
            self.transform = midas_transforms.dpt_transform
        else:
            self.transform = midas_transforms.small_transform

        logger.info("MiDaS model loaded successfully")

    @torch.no_grad()
    def estimate_depth(self, image: Image.Image) -> np.ndarray:
        """
        Estimate depth map from image

        Args:
            image: PIL Image (RGB)

        Returns:
            Depth map as numpy array (normalized 0-1)
        """
        # Convert PIL to numpy
        img_np = np.array(image)

        # Apply transforms
        input_batch = self.transform(img_np).to(self.device)

        # Predict
        prediction = self.model(input_batch)

        # Resize to original resolution
        prediction = torch.nn.functional.interpolate(
            prediction.unsqueeze(1),
            size=img_np.shape[:2],
            mode="bicubic",
            align_corners=False,
        ).squeeze()

        depth_map = prediction.cpu().numpy()

        # Normalize to 0-1
        depth_map = (depth_map - depth_map.min()) / (depth_map.max() - depth_map.min())

        return depth_map

    def estimate_depth_with_visualization(
        self,
        image: Image.Image
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Estimate depth and create colorized visualization

        Args:
            image: PIL Image

        Returns:
            (depth_map, colored_depth) tuple
        """
        depth_map = self.estimate_depth(image)

        # Create colored visualization
        depth_colored = cv2.applyColorMap(
            (depth_map * 255).astype(np.uint8),
            cv2.COLORMAP_MAGMA
        )

        return depth_map, depth_colored

    def get_point_cloud(
        self,
        image: Image.Image,
        camera_intrinsics: dict
    ) -> np.ndarray:
        """
        Generate 3D point cloud from depth map

        Args:
            image: PIL Image
            camera_intrinsics: Dict with fx, fy, cx, cy

        Returns:
            Point cloud as (N, 3) array
        """
        depth_map = self.estimate_depth(image)
        h, w = depth_map.shape

        fx = camera_intrinsics.get('fx', w / 2)
        fy = camera_intrinsics.get('fy', h / 2)
        cx = camera_intrinsics.get('cx', w / 2)
        cy = camera_intrinsics.get('cy', h / 2)

        # Create meshgrid
        u, v = np.meshgrid(np.arange(w), np.arange(h))

        # Backproject to 3D
        z = depth_map
        x = (u - cx) * z / fx
        y = (v - cy) * z / fy

        # Stack coordinates
        points = np.stack([x, y, z], axis=-1)
        points = points.reshape(-1, 3)

        return points

    def estimate_object_distance(
        self,
        image: Image.Image,
        bbox: dict
    ) -> float:
        """
        Estimate distance to object given bounding box

        Args:
            image: PIL Image
            bbox: Dict with x_min, y_min, x_max, y_max

        Returns:
            Estimated distance (relative units)
        """
        depth_map = self.estimate_depth(image)

        # Extract region of interest
        roi = depth_map[
            bbox['y_min']:bbox['y_max'],
            bbox['x_min']:bbox['x_max']
        ]

        # Use median depth in ROI
        distance = np.median(roi)

        return float(distance)


# Example usage
if __name__ == "__main__":
    estimator = MiDaSDepthEstimator()

    # Test with dummy image
    test_image = Image.new('RGB', (640, 480), color='blue')
    depth = estimator.estimate_depth(test_image)
    print(f"Depth map shape: {depth.shape}")
