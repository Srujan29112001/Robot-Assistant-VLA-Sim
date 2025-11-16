"""
OCR Text Recognition
Uses EasyOCR for reading text in images
Enhanced with DeepSeek-OCR for efficient compression
"""

import easyocr
from PIL import Image
import numpy as np
from typing import List, Dict, Tuple, Optional
import logging

# Import DeepSeek OCR if available
try:
    from .deepseek_ocr import DeepSeekOCR
    DEEPSEEK_AVAILABLE = True
except ImportError:
    DEEPSEEK_AVAILABLE = False

logger = logging.getLogger(__name__)


class TextRecognizer:
    """
    OCR text recognition using EasyOCR
    Detects and recognizes text in images
    """

    def __init__(
        self,
        languages: List[str] = ['en'],
        gpu: bool = True,
        use_deepseek: bool = True,
        enable_compression: bool = True
    ):
        """
        Initialize EasyOCR reader with optional DeepSeek enhancement

        Args:
            languages: List of language codes
            gpu: Use GPU if available
            use_deepseek: Enable DeepSeek OCR for compression
            enable_compression: Enable vision-text compression for long texts
        """
        logger.info(f"Initializing EasyOCR with languages: {languages}")

        self.reader = easyocr.Reader(
            languages,
            gpu=gpu,
            model_storage_directory='./models/easyocr'
        )

        logger.info("EasyOCR initialized successfully")

        # Initialize DeepSeek OCR if available and requested
        self.deepseek_ocr = None
        if use_deepseek and DEEPSEEK_AVAILABLE:
            try:
                self.deepseek_ocr = DeepSeekOCR(
                    use_compression=enable_compression,
                    device="cuda" if gpu else "cpu"
                )
                logger.info("DeepSeek OCR enhancement enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize DeepSeek OCR: {e}")
        elif use_deepseek and not DEEPSEEK_AVAILABLE:
            logger.warning("DeepSeek OCR requested but not available")

    def recognize_text(
        self,
        image: Image.Image,
        detail: int = 1
    ) -> List[Dict]:
        """
        Recognize text in image

        Args:
            image: PIL Image
            detail: 0=simple, 1=detailed

        Returns:
            List of detected text with bounding boxes and confidence
        """
        # Convert PIL to numpy
        img_np = np.array(image)

        # Run OCR
        results = self.reader.readtext(img_np, detail=detail)

        # Parse results
        recognized = []
        for result in results:
            if detail == 1:
                bbox, text, confidence = result
                recognized.append({
                    "text": text,
                    "confidence": float(confidence),
                    "bbox": {
                        "points": bbox,
                        "x_min": int(min([p[0] for p in bbox])),
                        "y_min": int(min([p[1] for p in bbox])),
                        "x_max": int(max([p[0] for p in bbox])),
                        "y_max": int(max([p[1] for p in bbox])),
                    }
                })
            else:
                recognized.append({"text": result[1]})

        logger.info(f"Recognized {len(recognized)} text regions")
        return recognized

    def get_text_only(self, image: Image.Image) -> List[str]:
        """
        Get only the text content (no bounding boxes)

        Args:
            image: PIL Image

        Returns:
            List of recognized text strings
        """
        results = self.recognize_text(image, detail=0)
        return [r["text"] for r in results]

    def find_text(
        self,
        image: Image.Image,
        search_text: str,
        case_sensitive: bool = False
    ) -> List[Dict]:
        """
        Find specific text in image

        Args:
            image: PIL Image
            search_text: Text to search for
            case_sensitive: Whether search is case-sensitive

        Returns:
            List of matches with locations
        """
        results = self.recognize_text(image)

        matches = []
        for result in results:
            text = result["text"]
            if not case_sensitive:
                text = text.lower()
                search_text = search_text.lower()

            if search_text in text:
                matches.append(result)

        logger.info(f"Found {len(matches)} matches for '{search_text}'")
        return matches

    def recognize_with_compression(
        self,
        image: Image.Image
    ) -> Dict:
        """
        Recognize text with DeepSeek compression for efficient LLM processing

        Args:
            image: PIL Image

        Returns:
            Dictionary with text and optional compressed representation
        """
        if self.deepseek_ocr is None:
            # Fallback to regular OCR
            results = self.recognize_text(image)
            full_text = "\n".join([r["text"] for r in results])
            return {
                "text": full_text,
                "compressed": False,
                "detections": results
            }

        # Use DeepSeek OCR with compression
        return self.deepseek_ocr.extract_text(image, compress_output=True)


# Example usage
if __name__ == "__main__":
    recognizer = TextRecognizer()

    # Test with dummy image (in practice, load real image)
    test_image = Image.new('RGB', (640, 480), color='white')
    texts = recognizer.get_text_only(test_image)
    print(f"Recognized texts: {texts}")
