"""
Tests for perception pipeline
"""

import pytest
from PIL import Image
import numpy as np


def test_vit_dino_import():
    """Test ViT-DINO can be imported"""
    try:
        from perception.vision.vit_dino import ViTDINODetector
        assert ViTDINODetector is not None
    except ImportError:
        pytest.skip("ViT-DINO dependencies not installed")


def test_midas_import():
    """Test MiDaS can be imported"""
    try:
        from perception.depth.midas import MiDaSDepthEstimator
        assert MiDaSDepthEstimator is not None
    except ImportError:
        pytest.skip("MiDaS dependencies not installed")


def test_ocr_import():
    """Test OCR can be imported"""
    try:
        from perception.ocr.text_recognition import TextRecognizer
        assert TextRecognizer is not None
    except ImportError:
        pytest.skip("OCR dependencies not installed")


def test_perception_pipeline_import():
    """Test perception pipeline can be imported"""
    from perception.main import PerceptionPipeline
    assert PerceptionPipeline is not None
