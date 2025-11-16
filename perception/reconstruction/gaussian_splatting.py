"""
3D Gaussian Splatting for Photorealistic Scene Reconstruction
Reference: "3D Gaussian Splatting for Real-Time Radiance Field Rendering"
https://repo-sam.inria.fr/fungraph/3d-gaussian-splatting/
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from typing import Optional, Tuple, List, Dict, Any
from dataclasses import dataclass
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class GaussianParams:
    """Parameters for a 3D Gaussian"""
    position: torch.Tensor  # (N, 3) - xyz positions
    rotation: torch.Tensor  # (N, 4) - quaternions
    scale: torch.Tensor  # (N, 3) - log scales
    opacity: torch.Tensor  # (N, 1) - sigmoid opacities
    color: torch.Tensor  # (N, 3) or (N, SH_coeffs, 3) - RGB or SH coefficients


class GaussianScene(nn.Module):
    """
    3D Scene represented as 3D Gaussians
    Enables photorealistic novel view synthesis
    """

    def __init__(
        self,
        num_gaussians: int = 10000,
        use_spherical_harmonics: bool = True,
        sh_degree: int = 3,
        device: str = "cuda" if torch.cuda.is_available() else "cpu",
    ):
        """
        Initialize Gaussian scene

        Args:
            num_gaussians: Initial number of Gaussians
            use_spherical_harmonics: Use SH for view-dependent color
            sh_degree: Degree of spherical harmonics
            device: Device to store Gaussians
        """
        super().__init__()

        self.num_gaussians = num_gaussians
        self.use_sh = use_spherical_harmonics
        self.sh_degree = sh_degree
        self.device = device

        # Calculate SH coefficients
        self.sh_coeffs = (sh_degree + 1) ** 2 if use_spherical_harmonics else 1

        # Initialize Gaussian parameters as learnable
        self._init_gaussians()

        logger.info(
            f"Initialized Gaussian scene with {num_gaussians} Gaussians "
            f"(SH degree {sh_degree if use_spherical_harmonics else 'none'})"
        )

    def _init_gaussians(self):
        """Initialize Gaussian parameters randomly"""
        # Positions - uniformly in a unit cube
        self.positions = nn.Parameter(
            torch.rand(self.num_gaussians, 3, device=self.device) * 2 - 1
        )

        # Rotations - identity quaternions
        self.rotations = nn.Parameter(
            torch.tensor([[1., 0., 0., 0.]], device=self.device).repeat(self.num_gaussians, 1)
        )

        # Scales - small random scales (log space)
        self.scales = nn.Parameter(
            torch.randn(self.num_gaussians, 3, device=self.device) * 0.01 - 4
        )

        # Opacity - mostly opaque
        self.opacities = nn.Parameter(
            torch.ones(self.num_gaussians, 1, device=self.device) * 0.1
        )

        # Colors - random (or SH coefficients)
        color_dim = 3 * self.sh_coeffs if self.use_sh else 3
        self.colors = nn.Parameter(
            torch.rand(self.num_gaussians, color_dim, device=self.device)
        )

    def get_gaussians(self) -> GaussianParams:
        """
        Get Gaussian parameters with activations applied

        Returns:
            GaussianParams with properly activated parameters
        """
        return GaussianParams(
            position=self.positions,  # No activation
            rotation=F.normalize(self.rotations, dim=-1),  # Normalize quaternions
            scale=torch.exp(self.scales),  # Exp for positive scales
            opacity=torch.sigmoid(self.opacities),  # Sigmoid for [0, 1]
            color=self.colors if self.use_sh else torch.sigmoid(self.colors)  # SH or RGB
        )

    def add_gaussians(self, n: int):
        """Add new Gaussians (for adaptive refinement)"""
        new_positions = nn.Parameter(
            torch.rand(n, 3, device=self.device) * 2 - 1
        )
        new_rotations = nn.Parameter(
            torch.tensor([[1., 0., 0., 0.]], device=self.device).repeat(n, 1)
        )
        new_scales = nn.Parameter(
            torch.randn(n, 3, device=self.device) * 0.01 - 4
        )
        new_opacities = nn.Parameter(
            torch.ones(n, 1, device=self.device) * 0.1
        )
        color_dim = 3 * self.sh_coeffs if self.use_sh else 3
        new_colors = nn.Parameter(
            torch.rand(n, color_dim, device=self.device)
        )

        # Concatenate with existing
        self.positions = nn.Parameter(torch.cat([self.positions, new_positions]))
        self.rotations = nn.Parameter(torch.cat([self.rotations, new_rotations]))
        self.scales = nn.Parameter(torch.cat([self.scales, new_scales]))
        self.opacities = nn.Parameter(torch.cat([self.opacities, new_opacities]))
        self.colors = nn.Parameter(torch.cat([self.colors, new_colors]))

        self.num_gaussians += n
        logger.info(f"Added {n} Gaussians, total: {self.num_gaussians}")

    def prune_gaussians(self, mask: torch.Tensor):
        """Prune Gaussians based on boolean mask"""
        self.positions = nn.Parameter(self.positions[mask])
        self.rotations = nn.Parameter(self.rotations[mask])
        self.scales = nn.Parameter(self.scales[mask])
        self.opacities = nn.Parameter(self.opacities[mask])
        self.colors = nn.Parameter(self.colors[mask])

        pruned = (~mask).sum().item()
        self.num_gaussians = mask.sum().item()
        logger.info(f"Pruned {pruned} Gaussians, remaining: {self.num_gaussians}")


class GaussianSplatter:
    """
    3D Gaussian Splatting renderer
    Renders novel views from 3D Gaussian scene
    """

    def __init__(
        self,
        image_width: int = 640,
        image_height: int = 480,
        device: str = "cuda" if torch.cuda.is_available() else "cpu",
    ):
        """
        Initialize Gaussian splatter renderer

        Args:
            image_width: Output image width
            image_height: Output image height
            device: Rendering device
        """
        self.width = image_width
        self.height = image_height
        self.device = device

    def render(
        self,
        scene: GaussianScene,
        camera_position: torch.Tensor,
        camera_rotation: torch.Tensor,
        camera_intrinsics: torch.Tensor,
    ) -> torch.Tensor:
        """
        Render scene from camera viewpoint

        Args:
            scene: Gaussian scene to render
            camera_position: Camera position (3,)
            camera_rotation: Camera rotation matrix (3, 3)
            camera_intrinsics: Camera intrinsics (3, 3)

        Returns:
            Rendered image (H, W, 3)
        """
        gaussians = scene.get_gaussians()

        # Transform Gaussians to camera space
        positions_cam = self._world_to_camera(
            gaussians.position,
            camera_position,
            camera_rotation
        )

        # Project to image plane
        positions_2d = self._project_to_image(positions_cam, camera_intrinsics)

        # Compute Gaussian splats in image space
        image = self._rasterize_gaussians(
            positions_2d,
            positions_cam[:, 2],  # Depths
            gaussians.scale,
            gaussians.rotation,
            gaussians.opacity,
            gaussians.color,
            camera_rotation
        )

        return image

    def _world_to_camera(
        self,
        positions: torch.Tensor,
        camera_pos: torch.Tensor,
        camera_rot: torch.Tensor,
    ) -> torch.Tensor:
        """Transform world positions to camera space"""
        # Translate
        positions_centered = positions - camera_pos.unsqueeze(0)

        # Rotate
        positions_cam = torch.matmul(positions_centered, camera_rot.T)

        return positions_cam

    def _project_to_image(
        self,
        positions_cam: torch.Tensor,
        intrinsics: torch.Tensor,
    ) -> torch.Tensor:
        """Project camera space positions to image plane"""
        # Perspective projection
        positions_proj = positions_cam / (positions_cam[:, 2:3] + 1e-6)

        # Apply intrinsics
        positions_2d = torch.matmul(positions_proj, intrinsics.T)

        return positions_2d[:, :2]  # Return (x, y)

    def _rasterize_gaussians(
        self,
        positions_2d: torch.Tensor,
        depths: torch.Tensor,
        scales: torch.Tensor,
        rotations: torch.Tensor,
        opacities: torch.Tensor,
        colors: torch.Tensor,
        camera_rotation: torch.Tensor,
    ) -> torch.Tensor:
        """
        Rasterize Gaussians to image (simplified version)
        Full implementation would use CUDA kernels for efficiency
        """
        # Sort by depth (painter's algorithm)
        sorted_indices = torch.argsort(depths, descending=True)

        # Initialize output image
        image = torch.zeros(self.height, self.width, 3, device=self.device)
        alpha_accumulated = torch.zeros(self.height, self.width, 1, device=self.device)

        # Render each Gaussian (back to front)
        for idx in sorted_indices[:1000]:  # Limit for efficiency in CPU/simplified version
            pos_2d = positions_2d[idx]
            scale = scales[idx]
            opacity = opacities[idx]
            color = colors[idx][:3] if colors.shape[1] > 3 else colors[idx]

            # Compute 2D covariance from 3D Gaussian
            # Simplified: use scale directly as 2D Gaussian std
            sigma_x = scale[0] * 10  # Scale factor for visibility
            sigma_y = scale[1] * 10

            # Create 2D Gaussian kernel
            x = torch.arange(self.width, device=self.device).float()
            y = torch.arange(self.height, device=self.device).float()
            grid_x, grid_y = torch.meshgrid(x, y, indexing='xy')

            # Gaussian function
            gaussian = torch.exp(
                -(
                    ((grid_x - pos_2d[0]) ** 2) / (2 * sigma_x ** 2 + 1e-6) +
                    ((grid_y - pos_2d[1]) ** 2) / (2 * sigma_y ** 2 + 1e-6)
                )
            ).unsqueeze(-1)

            # Alpha blending
            alpha = gaussian * opacity
            alpha = alpha * (1 - alpha_accumulated)  # Account for accumulated alpha

            # Composite color
            image = image + alpha * color.view(1, 1, 3)
            alpha_accumulated = alpha_accumulated + alpha

        # Clamp to valid range
        image = torch.clamp(image, 0, 1)

        return image

    def render_from_rgbd(
        self,
        rgb_image: torch.Tensor,
        depth_image: torch.Tensor,
        camera_intrinsics: torch.Tensor,
    ) -> GaussianScene:
        """
        Initialize Gaussian scene from RGB-D image

        Args:
            rgb_image: RGB image (H, W, 3)
            depth_image: Depth image (H, W)
            camera_intrinsics: Camera intrinsics (3, 3)

        Returns:
            Initialized Gaussian scene
        """
        H, W = depth_image.shape

        # Create pixel grid
        y, x = torch.meshgrid(
            torch.arange(H, device=self.device),
            torch.arange(W, device=self.device),
            indexing='ij'
        )

        # Back-project to 3D
        fx, fy = camera_intrinsics[0, 0], camera_intrinsics[1, 1]
        cx, cy = camera_intrinsics[0, 2], camera_intrinsics[1, 2]

        z = depth_image
        x_3d = (x - cx) * z / fx
        y_3d = (y - cy) * z / fy

        # Stack to point cloud
        points = torch.stack([x_3d, y_3d, z], dim=-1).reshape(-1, 3)
        colors = rgb_image.reshape(-1, 3)

        # Subsample for manageable number of Gaussians
        num_points = points.shape[0]
        sample_rate = max(1, num_points // 10000)
        points = points[::sample_rate]
        colors = colors[::sample_rate]

        # Create scene
        scene = GaussianScene(
            num_gaussians=points.shape[0],
            use_spherical_harmonics=False,
            device=self.device
        )

        # Initialize with point cloud
        scene.positions.data = points
        scene.colors.data = colors

        logger.info(f"Initialized Gaussian scene from RGB-D with {points.shape[0]} Gaussians")

        return scene


class GaussianSceneOptimizer:
    """
    Optimizer for Gaussian scene reconstruction
    Optimizes Gaussian parameters from multi-view images
    """

    def __init__(
        self,
        scene: GaussianScene,
        renderer: GaussianSplatter,
        learning_rate: float = 0.01,
    ):
        self.scene = scene
        self.renderer = renderer

        # Separate optimizers for different parameters (different learning rates)
        self.optimizer = torch.optim.Adam([
            {'params': [scene.positions], 'lr': learning_rate},
            {'params': [scene.rotations], 'lr': learning_rate * 0.1},
            {'params': [scene.scales], 'lr': learning_rate * 0.1},
            {'params': [scene.opacities], 'lr': learning_rate * 0.1},
            {'params': [scene.colors], 'lr': learning_rate},
        ])

    def optimize_step(
        self,
        gt_image: torch.Tensor,
        camera_position: torch.Tensor,
        camera_rotation: torch.Tensor,
        camera_intrinsics: torch.Tensor,
    ) -> float:
        """
        Single optimization step

        Args:
            gt_image: Ground truth image
            camera_position: Camera position
            camera_rotation: Camera rotation
            camera_intrinsics: Camera intrinsics

        Returns:
            Loss value
        """
        self.optimizer.zero_grad()

        # Render
        rendered = self.renderer.render(
            self.scene,
            camera_position,
            camera_rotation,
            camera_intrinsics
        )

        # Compute loss
        loss = F.l1_loss(rendered, gt_image)

        # Backpropagate
        loss.backward()
        self.optimizer.step()

        return loss.item()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Test 3D Gaussian Splatting
    print("\n=== Testing 3D Gaussian Splatting ===")

    # Create scene
    scene = GaussianScene(num_gaussians=1000, use_spherical_harmonics=True)

    # Create renderer
    renderer = GaussianSplatter(image_width=640, image_height=480)

    # Define camera
    camera_pos = torch.tensor([0., 0., 5.], device=scene.device)
    camera_rot = torch.eye(3, device=scene.device)
    camera_intrinsics = torch.tensor([
        [500., 0., 320.],
        [0., 500., 240.],
        [0., 0., 1.]
    ], device=scene.device)

    # Render
    print("Rendering scene...")
    image = renderer.render(scene, camera_pos, camera_rot, camera_intrinsics)
    print(f"Rendered image shape: {image.shape}")
    print(f"Image range: [{image.min():.3f}, {image.max():.3f}]")

    print("\n=== 3D Gaussian Splatting test completed ===")
