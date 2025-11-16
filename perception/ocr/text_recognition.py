"""
OCR Text Recognition
Uses EasyOCR for reading text in images
"""

import easyocr
from PIL import Image
import numpy as np
from typing import List, Dict, Tuple
import logging

logger = logging.getLogger(__name__)


class TextRecognizer:
    """
    OCR text recognition using EasyOCR
    Detects and recognizes text in images
    """

    def __init__(self, languages: List[str] = ['en'], gpu: bool = True):
        """
        Initialize EasyOCR reader

        Args:
            languages: List of language codes
            gpu: Use GPU if available
        """
        logger.info(f"Initializing EasyOCR with languages: {languages}")

        self.reader = easyocr.Reader(
            languages,
            gpu=gpu,
            model_storage_directory='./models/easyocr'
        )

        logger.info("EasyOCR initialized successfully")

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


# Example usage
if __name__ == "__main__":
    recognizer = TextRecognizer()

    # Test with dummy image (in practice, load real image)
    test_image = Image.new('RGB', (640, 480), color='white')
    texts = recognizer.get_text_only(test_image)
    print(f"Recognized texts: {texts}")
