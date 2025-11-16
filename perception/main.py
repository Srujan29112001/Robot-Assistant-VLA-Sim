"""
Main Perception Pipeline
Integrates ViT-DINO, MiDaS, and OCR for comprehensive scene understanding
"""

from perception.vision.vit_dino import ViTDINODetector
from perception.depth.midas import MiDaSDepthEstimator
from perception.ocr.text_recognition import TextRecognizer
from PIL import Image
import numpy as np
from typing import Dict, List, Any
import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PerceptionPipeline:
    """
    Integrated perception pipeline combining vision, depth, and text recognition
    """

    def __init__(self):
        """Initialize all perception models"""
        logger.info("Initializing Perception Pipeline...")

        # Load models
        self.vit_dino = ViTDINODetector()
        self.depth_estimator = MiDaSDepthEstimator()
        self.text_recognizer = TextRecognizer()

        logger.info("Perception Pipeline ready!")

    def process_frame(self, image: Image.Image) -> Dict[str, Any]:
        """
        Process a single camera frame through full pipeline

        Args:
            image: PIL Image from camera

        Returns:
            Dict containing all perception results
        """
        start_time = time.time()
        logger.info("Processing frame...")

        results = {
            "timestamp": time.time(),
            "objects": [],
            "depth_map": None,
            "text": [],
            "scene_embedding": None,
            "processing_time": 0.0
        }

        try:
            # 1. Object Detection with ViT-DINO
            logger.info("Running object detection...")
            objects = self.vit_dino.detect_objects(image)

            # 2. Depth Estimation
            logger.info("Estimating depth...")
            depth_map = self.depth_estimator.estimate_depth(image)

            # 3. Add 3D positions to objects
            for obj in objects:
                bbox = obj["bbox"]
                distance = self.depth_estimator.estimate_object_distance(image, bbox)
                obj["distance"] = float(distance)
                obj["position_3d"] = self._estimate_3d_position(bbox, distance)

            # 4. Text Recognition
            logger.info("Recognizing text...")
            text_results = self.text_recognizer.recognize_text(image)

            # 5. Get global scene embedding
            scene_embedding = self.vit_dino.get_global_embedding(image)

            # Compile results
            results["objects"] = objects
            results["depth_map"] = depth_map.tolist() if isinstance(depth_map, np.ndarray) else depth_map
            results["text"] = text_results
            results["scene_embedding"] = scene_embedding.tolist() if isinstance(scene_embedding, np.ndarray) else scene_embedding
            results["processing_time"] = time.time() - start_time

            logger.info(f"Frame processed in {results['processing_time']:.2f}s")
            logger.info(f"Found {len(objects)} objects and {len(text_results)} text regions")

        except Exception as e:
            logger.error(f"Error processing frame: {e}", exc_info=True)
            results["error"] = str(e)

        return results

    def _estimate_3d_position(self, bbox: dict, distance: float) -> dict:
        """
        Estimate 3D position from 2D bbox and distance

        Args:
            bbox: Bounding box dict
            distance: Depth value

        Returns:
            Estimated (x, y, z) position
        """
        # Simple projection (assumes centered camera)
        center_x = (bbox["x_min"] + bbox["x_max"]) / 2
        center_y = (bbox["y_min"] + bbox["y_max"]) / 2

        # Convert to normalized coordinates (-1 to 1)
        # Assuming image width/height of 640x480
        norm_x = (center_x - 320) / 320
        norm_y = (center_y - 240) / 240

        # Estimate 3D position (simplified)
        return {
            "x": float(norm_x * distance),
            "y": float(-norm_y * distance),  # Negative for typical camera frame
            "z": float(distance)
        }

    def detect_specific_object(
        self,
        image: Image.Image,
        object_description: str
    ) -> List[Dict]:
        """
        Look for specific object based on description

        Args:
            image: PIL Image
            object_description: Text description

        Returns:
            List of matching objects
        """
        # Process frame
        results = self.process_frame(image)

        # In a full implementation, would use CLIP or similar
        # to match text description to visual features
        # For now, return all detected objects
        return results["objects"]


def main():
    """Main entry point for perception service"""
    logger.info("Starting Perception Service...")

    pipeline = PerceptionPipeline()

    # In production, this would subscribe to ROS2 camera topics
    # For testing, use a dummy image
    logger.info("Perception service running. Waiting for images...")

    # Example: process test image
    test_image = Image.new('RGB', (640, 480), color='green')
    results = pipeline.process_frame(test_image)
    logger.info(f"Test results: {len(results['objects'])} objects detected")


if __name__ == "__main__":
    main()
