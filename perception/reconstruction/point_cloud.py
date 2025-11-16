"""
Point Cloud Reconstruction
Traditional 3D reconstruction from RGB-D or stereo
"""

import torch
import numpy as np
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class PointCloudReconstructor:
    """Reconstruct 3D point clouds from depth images"""

    def __init__(self, device: str = "cuda" if torch.cuda.is_available() else "cpu"):
        self.device = device

    def from_rgbd(
        self,
        rgb: np.ndarray,
        depth: np.ndarray,
        intrinsics: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Reconstruct point cloud from RGB-D

        Args:
            rgb: RGB image (H, W, 3)
            depth: Depth image (H, W)
            intrinsics: Camera intrinsics (3, 3)

        Returns:
            points (N, 3), colors (N, 3)
        """
        H, W = depth.shape
        fx, fy = intrinsics[0, 0], intrinsics[1, 1]
        cx, cy = intrinsics[0, 2], intrinsics[1, 2]

        # Create meshgrid
        y, x = np.meshgrid(np.arange(H), np.arange(W), indexing='ij')

        # Backproject
        z = depth
        x_3d = (x - cx) * z / fx
        y_3d = (y - cy) * z / fy

        # Stack
        points = np.stack([x_3d, y_3d, z], axis=-1).reshape(-1, 3)
        colors = rgb.reshape(-1, 3) / 255.0

        # Remove invalid points
        valid = (points[:, 2] > 0) & (points[:, 2] < 10)
        points = points[valid]
        colors = colors[valid]

        logger.info(f"Reconstructed {len(points)} points")
        return points, colors
