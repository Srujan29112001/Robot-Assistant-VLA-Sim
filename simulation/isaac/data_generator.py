"""
Synthetic Data Generation using Isaac Sim Replicator
For training vision models with domain randomization
"""

import logging
import numpy as np
from typing import List, Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    import omni.replicator.core as rep
    REPLICATOR_AVAILABLE = True
except ImportError:
    logger.warning("Isaac Sim Replicator not available")
    REPLICATOR_AVAILABLE = False


class SyntheticDataGenerator:
    """
    Generate synthetic training data using Isaac Sim's Replicator
    """

    def __init__(self, output_dir: str = "./synthetic_data"):
        """
        Initialize synthetic data generator

        Args:
            output_dir: Directory to save generated data
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.camera = None
        self.render_products = []

        if not REPLICATOR_AVAILABLE:
            logger.error("Replicator not available")
            return

        logger.info(f"Synthetic data will be saved to: {self.output_dir}")

    def setup_camera(self, resolution: tuple = (1280, 720)):
        """
        Setup camera for data capture

        Args:
            resolution: (width, height) for captured images
        """
        if not REPLICATOR_AVAILABLE:
            return

        try:
            # Create camera
            self.camera = rep.create.camera(
                position=(2.0, 2.0, 1.5),
                look_at=(0.0, 0.0, 0.5)
            )

            # Create render products
            rp = rep.create.render_product(
                self.camera,
                resolution=resolution
            )
            self.render_products.append(rp)

            logger.info(f"Camera setup with resolution {resolution}")

        except Exception as e:
            logger.error(f"Error setting up camera: {e}")

    def randomize_lights(self):
        """
        Randomize lighting conditions
        """
        if not REPLICATOR_AVAILABLE:
            return

        try:
            # Randomize dome light
            with rep.trigger.on_frame():
                lights = rep.get.prims(semantics=[("class", "light")])
                with lights:
                    rep.modify.attribute(
                        "intensity",
                        rep.distribution.uniform(500, 3000)
                    )
                    rep.modify.attribute(
                        "color",
                        rep.distribution.uniform((0.8, 0.8, 0.8), (1.0, 1.0, 1.0))
                    )

            logger.info("Light randomization configured")

        except Exception as e:
            logger.error(f"Error randomizing lights: {e}")

    def randomize_materials(self, objects: List[str]):
        """
        Randomize object materials/textures

        Args:
            objects: List of object prim paths to randomize
        """
        if not REPLICATOR_AVAILABLE:
            return

        try:
            def randomize_color():
                return rep.distribution.uniform(
                    (0.0, 0.0, 0.0),
                    (1.0, 1.0, 1.0)
                )

            with rep.trigger.on_frame():
                for obj_path in objects:
                    obj = rep.get.prims(path_pattern=obj_path)
                    with obj:
                        rep.randomizer.color(
                            colors=randomize_color()
                        )

            logger.info(f"Material randomization configured for {len(objects)} objects")

        except Exception as e:
            logger.error(f"Error randomizing materials: {e}")

    def randomize_poses(self, objects: List[str],
                       position_range: tuple = ((-1, 1), (-1, 1), (0.5, 1.5))):
        """
        Randomize object poses

        Args:
            objects: List of object prim paths
            position_range: ((x_min, x_max), (y_min, y_max), (z_min, z_max))
        """
        if not REPLICATOR_AVAILABLE:
            return

        try:
            with rep.trigger.on_frame():
                for obj_path in objects:
                    obj = rep.get.prims(path_pattern=obj_path)
                    with obj:
                        rep.modify.pose(
                            position=rep.distribution.uniform(
                                (position_range[0][0], position_range[1][0], position_range[2][0]),
                                (position_range[0][1], position_range[1][1], position_range[2][1])
                            ),
                            rotation=rep.distribution.uniform((0, 0, 0), (360, 360, 360))
                        )

            logger.info(f"Pose randomization configured for {len(objects)} objects")

        except Exception as e:
            logger.error(f"Error randomizing poses: {e}")

    def setup_domain_randomization(self, objects: List[str]):
        """
        Setup complete domain randomization pipeline

        Args:
            objects: List of objects to randomize
        """
        logger.info("Setting up domain randomization...")

        self.randomize_lights()
        self.randomize_materials(objects)
        self.randomize_poses(objects)

        logger.info("Domain randomization configured")

    def generate_dataset(self, num_frames: int = 1000,
                        annotations: List[str] = ['rgb', 'depth', 'semantic_segmentation']):
        """
        Generate synthetic dataset

        Args:
            num_frames: Number of frames to generate
            annotations: List of annotation types to capture
        """
        if not REPLICATOR_AVAILABLE:
            return

        try:
            # Setup writers for different annotation types
            writers = []

            if 'rgb' in annotations:
                rgb_writer = rep.WriterRegistry.get("BasicWriter")
                rgb_writer.initialize(
                    output_dir=str(self.output_dir / "rgb"),
                    rgb=True
                )
                writers.append(rgb_writer)

            if 'depth' in annotations:
                depth_writer = rep.WriterRegistry.get("BasicWriter")
                depth_writer.initialize(
                    output_dir=str(self.output_dir / "depth"),
                    distance_to_image_plane=True
                )
                writers.append(depth_writer)

            if 'semantic_segmentation' in annotations:
                seg_writer = rep.WriterRegistry.get("BasicWriter")
                seg_writer.initialize(
                    output_dir=str(self.output_dir / "semantic"),
                    semantic_segmentation=True
                )
                writers.append(seg_writer)

            # Attach writers to render products
            for writer in writers:
                writer.attach(self.render_products)

            logger.info(f"Generating {num_frames} frames...")

            # Run orchestrator
            rep.orchestrator.run(num_frames=num_frames)

            logger.info(f"Dataset generation complete. Saved to {self.output_dir}")

        except Exception as e:
            logger.error(f"Error generating dataset: {e}")

    def generate_grasping_dataset(self, num_samples: int = 5000):
        """
        Generate dataset specifically for grasp training

        Args:
            num_samples: Number of grasp samples to generate
        """
        logger.info(f"Generating grasping dataset with {num_samples} samples")

        # This would:
        # 1. Randomize object poses
        # 2. Randomize robot configuration
        # 3. Capture RGBD images
        # 4. Label successful/unsuccessful grasps
        # 5. Save paired data (image, grasp pose, success)

        logger.info("Grasping dataset generation not fully implemented")
        logger.info("Fallback: Use pre-trained grasp models or collect real data")


# Example usage
if __name__ == "__main__":
    if REPLICATOR_AVAILABLE:
        generator = SyntheticDataGenerator(output_dir="./data/synthetic")

        generator.setup_camera(resolution=(1280, 720))

        objects_to_randomize = [
            "/World/bottle",
            "/World/cup",
            "/World/box"
        ]

        generator.setup_domain_randomization(objects_to_randomize)

        generator.generate_dataset(num_frames=100)

    else:
        print("Replicator not available. Install NVIDIA Isaac Sim for synthetic data generation.")
        print("Alternative: Use real camera data or pre-existing datasets.")
