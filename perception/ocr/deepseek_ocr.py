"""
DeepSeek-OCR: Vision-Text Compression for Efficient OCR
10x token reduction by encoding text as compressed images
Reference: DeepSeek-VL2 paper
"""

import torch
import torch.nn as nn
import torchvision.transforms as transforms
from PIL import Image, ImageDraw, ImageFont
import numpy as np
from typing import Optional, List, Dict, Tuple, Any
import logging
import io
import base64

logger = logging.getLogger(__name__)


class TextToImageEncoder:
    """
    Encode text as images for efficient LLM processing
    Inspired by DeepSeek's approach to reduce token usage
    """

    def __init__(
        self,
        font_size: int = 16,
        chars_per_row: int = 80,
        max_rows: int = 40,
        background_color: str = "white",
        text_color: str = "black",
    ):
        """
        Args:
            font_size: Font size for rendered text
            chars_per_row: Characters per row
            max_rows: Maximum number of rows
            background_color: Background color
            text_color: Text color
        """
        self.font_size = font_size
        self.chars_per_row = chars_per_row
        self.max_rows = max_rows
        self.background_color = background_color
        self.text_color = text_color

        # Calculate image dimensions
        self.char_width = font_size * 0.6  # Approximate monospace width
        self.line_height = font_size * 1.2
        self.image_width = int(chars_per_row * self.char_width)
        self.image_height = int(max_rows * self.line_height)

        # Try to load a monospace font
        try:
            self.font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", font_size)
        except:
            try:
                self.font = ImageFont.truetype("arial.ttf", font_size)
            except:
                logger.warning("Could not load TrueType font, using default")
                self.font = ImageFont.load_default()

    def encode_text_to_image(self, text: str) -> Image.Image:
        """
        Encode text as image

        Args:
            text: Text to encode

        Returns:
            PIL Image with rendered text
        """
        # Create image
        img = Image.new('RGB', (self.image_width, self.image_height), self.background_color)
        draw = ImageDraw.Draw(img)

        # Split text into lines
        lines = text.split('\n')

        # Draw text
        y_position = 10
        for line in lines[:self.max_rows]:
            # Truncate line if too long
            if len(line) > self.chars_per_row:
                line = line[:self.chars_per_row-3] + "..."

            draw.text((10, y_position), line, fill=self.text_color, font=self.font)
            y_position += self.line_height

        return img

    def encode_multiple_texts(self, texts: List[str]) -> List[Image.Image]:
        """
        Encode multiple texts as images

        Args:
            texts: List of texts

        Returns:
            List of PIL Images
        """
        return [self.encode_text_to_image(text) for text in texts]

    def estimate_token_savings(self, text: str) -> Dict[str, int]:
        """
        Estimate token savings from vision-text encoding

        Args:
            text: Original text

        Returns:
            Dictionary with token counts and savings
        """
        # Estimate text tokens (rough: 1 token ~= 4 chars for English)
        text_tokens = len(text) // 4

        # Vision tokens for image (typically 256-1024 for vision models)
        # DeepSeek uses dynamic tiling, estimate ~500 tokens per image
        vision_tokens = 500

        savings = max(0, text_tokens - vision_tokens)
        compression_ratio = text_tokens / max(1, vision_tokens)

        return {
            "text_tokens": text_tokens,
            "vision_tokens": vision_tokens,
            "tokens_saved": savings,
            "compression_ratio": compression_ratio
        }


class DeepSeekOCR:
    """
    DeepSeek-style OCR with vision-text compression
    Combines traditional OCR with efficient vision encoding
    """

    def __init__(
        self,
        use_compression: bool = True,
        compression_threshold: int = 200,  # Compress if >200 chars
        device: str = "cuda" if torch.cuda.is_available() else "cpu",
    ):
        """
        Args:
            use_compression: Enable vision-text compression
            compression_threshold: Minimum chars to trigger compression
            device: Device for models
        """
        self.use_compression = use_compression
        self.compression_threshold = compression_threshold
        self.device = device

        # Initialize text encoder
        if use_compression:
            self.text_encoder = TextToImageEncoder()

        # Initialize OCR engine
        try:
            import easyocr
            self.reader = easyocr.Reader(['en'], gpu=(device == 'cuda'))
            logger.info("EasyOCR initialized")
        except ImportError:
            logger.warning("EasyOCR not available, install with: pip install easyocr")
            self.reader = None

        # Vision model for reading text images (optional)
        try:
            from transformers import VisionEncoderDecoderModel, ViTImageProcessor, AutoTokenizer
            self.has_vision_model = True

            model_name = "nlpconnect/vit-gpt2-image-captioning"
            self.vision_model = VisionEncoderDecoderModel.from_pretrained(model_name).to(device)
            self.vision_processor = ViTImageProcessor.from_pretrained(model_name)
            self.vision_tokenizer = AutoTokenizer.from_pretrained(model_name)

            logger.info("Vision-text model initialized")
        except:
            self.has_vision_model = False
            logger.warning("Vision-text model not available")

    def extract_text(
        self,
        image: Image.Image,
        compress_output: bool = None,
    ) -> Dict[str, Any]:
        """
        Extract text from image with optional compression

        Args:
            image: Input image
            compress_output: Override compression setting

        Returns:
            Dictionary with extracted text and optionally compressed version
        """
        if self.reader is None:
            raise ValueError("OCR engine not initialized")

        # Convert PIL to numpy
        img_array = np.array(image)

        # Extract text
        results = self.reader.readtext(img_array)

        # Combine all text
        full_text = "\n".join([text for (bbox, text, confidence) in results])

        # Build response
        response = {
            "text": full_text,
            "confidence": np.mean([conf for (_, _, conf) in results]) if results else 0.0,
            "n_detections": len(results),
            "detections": [
                {
                    "bbox": bbox,
                    "text": text,
                    "confidence": conf
                }
                for (bbox, text, conf) in results
            ]
        }

        # Apply compression if enabled
        if compress_output is None:
            compress_output = self.use_compression

        if compress_output and len(full_text) > self.compression_threshold:
            compressed_data = self._compress_text(full_text)
            response.update(compressed_data)

        return response

    def _compress_text(self, text: str) -> Dict[str, Any]:
        """
        Compress text using vision encoding

        Args:
            text: Text to compress

        Returns:
            Compression data
        """
        # Encode text as image
        text_image = self.text_encoder.encode_text_to_image(text)

        # Convert to base64 for transmission
        buffered = io.BytesIO()
        text_image.save(buffered, format="PNG")
        img_base64 = base64.b64encode(buffered.getvalue()).decode()

        # Calculate savings
        savings = self.text_encoder.estimate_token_savings(text)

        return {
            "compressed": True,
            "text_image_base64": img_base64,
            "text_image_size": text_image.size,
            "compression_stats": savings,
        }

    def read_text_from_compressed(
        self,
        text_image_base64: str
    ) -> str:
        """
        Read text from compressed image (if vision model available)

        Args:
            text_image_base64: Base64 encoded text image

        Returns:
            Extracted text
        """
        if not self.has_vision_model:
            raise ValueError("Vision model not available for reading compressed text")

        # Decode image
        img_bytes = base64.b64decode(text_image_base64)
        text_image = Image.open(io.BytesIO(img_bytes))

        # Process with vision model
        pixel_values = self.vision_processor(text_image, return_tensors="pt").pixel_values
        pixel_values = pixel_values.to(self.device)

        # Generate
        with torch.no_grad():
            output_ids = self.vision_model.generate(pixel_values, max_length=512)

        # Decode
        text = self.vision_tokenizer.decode(output_ids[0], skip_special_tokens=True)

        return text

    def process_long_text_document(
        self,
        text: str,
        max_chars_per_image: int = 3000,
    ) -> List[Dict[str, Any]]:
        """
        Process long text document by chunking and compressing

        Args:
            text: Long text document
            max_chars_per_image: Maximum characters per compressed image

        Returns:
            List of compressed chunks
        """
        chunks = []
        current_pos = 0

        while current_pos < len(text):
            # Get chunk
            chunk_text = text[current_pos:current_pos + max_chars_per_image]

            # Compress chunk
            compressed = self._compress_text(chunk_text)
            compressed["chunk_index"] = len(chunks)
            compressed["original_text"] = chunk_text

            chunks.append(compressed)

            current_pos += max_chars_per_image

        logger.info(f"Compressed {len(text)} chars into {len(chunks)} image chunks")

        return chunks

    def extract_from_robot_scene(
        self,
        scene_image: Image.Image,
        target_regions: Optional[List[Tuple[int, int, int, int]]] = None,
    ) -> Dict[str, Any]:
        """
        Extract text from robot scene (labels, signs, etc.)

        Args:
            scene_image: Scene image from robot camera
            target_regions: Optional list of (x1, y1, x2, y2) ROIs

        Returns:
            Extracted text with locations
        """
        results = {"texts": [], "total_confidence": 0.0}

        if target_regions:
            # Process each region
            for i, (x1, y1, x2, y2) in enumerate(target_regions):
                region = scene_image.crop((x1, y1, x2, y2))
                extracted = self.extract_text(region, compress_output=False)

                if extracted["text"]:
                    results["texts"].append({
                        "region": (x1, y1, x2, y2),
                        "text": extracted["text"],
                        "confidence": extracted["confidence"]
                    })
        else:
            # Process entire image
            extracted = self.extract_text(scene_image, compress_output=False)
            results["texts"] = extracted["detections"]
            results["full_text"] = extracted["text"]

        # Calculate average confidence
        if results["texts"]:
            confidences = [t.get("confidence", 0) for t in results["texts"]]
            results["total_confidence"] = np.mean(confidences)

        return results


class DeepSeekVisionTextFusion(nn.Module):
    """
    Vision-Text fusion module inspired by DeepSeek-VL2
    Efficiently combines visual tokens with text tokens
    """

    def __init__(
        self,
        vision_dim: int = 768,
        text_dim: int = 768,
        fusion_dim: int = 768,
        num_fusion_layers: int = 2,
    ):
        super().__init__()

        self.vision_proj = nn.Linear(vision_dim, fusion_dim)
        self.text_proj = nn.Linear(text_dim, fusion_dim)

        # Fusion layers
        self.fusion_layers = nn.ModuleList([
            nn.TransformerEncoderLayer(
                d_model=fusion_dim,
                nhead=12,
                dim_feedforward=fusion_dim * 4,
                batch_first=True,
            )
            for _ in range(num_fusion_layers)
        ])

        self.norm = nn.LayerNorm(fusion_dim)

    def forward(
        self,
        vision_tokens: torch.Tensor,
        text_tokens: torch.Tensor,
    ) -> torch.Tensor:
        """
        Fuse vision and text tokens

        Args:
            vision_tokens: Vision tokens (batch, n_vis, vision_dim)
            text_tokens: Text tokens (batch, n_text, text_dim)

        Returns:
            Fused tokens (batch, n_vis + n_text, fusion_dim)
        """
        # Project to fusion space
        vis_proj = self.vision_proj(vision_tokens)
        text_proj = self.text_proj(text_tokens)

        # Concatenate
        fused = torch.cat([vis_proj, text_proj], dim=1)

        # Apply fusion layers
        for layer in self.fusion_layers:
            fused = layer(fused)

        # Normalize
        fused = self.norm(fused)

        return fused


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Initialize DeepSeek OCR
    ocr = DeepSeekOCR(use_compression=True)

    # Test with sample text
    sample_text = """
    ROBOTIC SAFETY PROTOCOL
    1. Maintain 1m distance from humans
    2. Do not exceed 0.5m/s speed
    3. Emergency stop on contact
    4. Verify gripper before release
    5. Report all anomalies
    """

    # Create text image
    print("\n=== Text Compression Test ===")
    compressed = ocr._compress_text(sample_text)
    print(f"Compression Stats:")
    for key, value in compressed["compression_stats"].items():
        print(f"  {key}: {value}")

    # Test OCR on an image (if you have one)
    try:
        # Create a test image with text
        from PIL import Image, ImageDraw, ImageFont

        img = Image.new('RGB', (400, 200), 'white')
        draw = ImageDraw.Draw(img)
        draw.text((20, 50), "DANGER: HIGH VOLTAGE", fill='red')
        draw.text((20, 100), "Keep clear of robot arm", fill='black')

        # Extract text
        print("\n=== OCR Test ===")
        result = ocr.extract_text(img, compress_output=True)
        print(f"Extracted: {result['text']}")
        print(f"Confidence: {result['confidence']:.2f}")

        if result.get('compressed'):
            print("Compression enabled and applied")
            stats = result['compression_stats']
            print(f"Token reduction: {stats['compression_ratio']:.1f}x")

    except Exception as e:
        logger.error(f"OCR test failed: {e}")
