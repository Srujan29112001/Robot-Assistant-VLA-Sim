"""
Speech-to-Text using OpenAI Whisper
High-accuracy, multilingual speech recognition for robot voice commands
"""

import torch
import whisper
import numpy as np
import logging
from typing import Optional, Dict, Any
import sounddevice as sd
import soundfile as sf
from pathlib import Path
import tempfile

logger = logging.getLogger(__name__)


class WhisperSTT:
    """
    Speech-to-Text using Whisper model
    Supports real-time and batch transcription
    """

    def __init__(
        self,
        model_size: str = "base",  # tiny, base, small, medium, large
        device: str = "cuda" if torch.cuda.is_available() else "cpu",
        language: str = "en",
        sample_rate: int = 16000,
    ):
        """
        Initialize Whisper STT

        Args:
            model_size: Whisper model size (tiny, base, small, medium, large)
            device: Device to run model on
            language: Primary language for transcription
            sample_rate: Audio sample rate
        """
        self.model_size = model_size
        self.device = device
        self.language = language
        self.sample_rate = sample_rate

        logger.info(f"Loading Whisper {model_size} model on {device}...")
        self.model = whisper.load_model(model_size, device=device)
        logger.info("Whisper model loaded successfully")

    def transcribe_file(
        self,
        audio_path: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Transcribe audio file

        Args:
            audio_path: Path to audio file
            **kwargs: Additional whisper transcribe arguments

        Returns:
            Dictionary with transcription results
        """
        logger.info(f"Transcribing audio file: {audio_path}")

        result = self.model.transcribe(
            audio_path,
            language=self.language,
            **kwargs
        )

        return {
            "text": result["text"].strip(),
            "language": result.get("language"),
            "segments": result.get("segments", []),
            "confidence": self._calculate_confidence(result)
        }

    def transcribe_audio(
        self,
        audio_data: np.ndarray,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Transcribe audio data directly

        Args:
            audio_data: Audio numpy array (mono, float32, sample_rate)
            **kwargs: Additional whisper arguments

        Returns:
            Dictionary with transcription results
        """
        # Save to temporary file (Whisper requires file input)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
            sf.write(tmp_path, audio_data, self.sample_rate)

        try:
            result = self.transcribe_file(tmp_path, **kwargs)
        finally:
            Path(tmp_path).unlink()

        return result

    def record_and_transcribe(
        self,
        duration: float = 5.0,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Record audio from microphone and transcribe

        Args:
            duration: Recording duration in seconds
            **kwargs: Additional whisper arguments

        Returns:
            Dictionary with transcription results
        """
        logger.info(f"Recording audio for {duration} seconds...")

        # Record audio
        audio_data = sd.rec(
            int(duration * self.sample_rate),
            samplerate=self.sample_rate,
            channels=1,
            dtype='float32'
        )
        sd.wait()  # Wait for recording to finish

        logger.info("Recording complete, transcribing...")
        return self.transcribe_audio(audio_data.flatten(), **kwargs)

    def stream_transcribe(
        self,
        callback,
        chunk_duration: float = 2.0,
        silence_threshold: float = 0.01,
    ):
        """
        Stream audio and transcribe in real-time

        Args:
            callback: Function to call with transcription results
            chunk_duration: Duration of each audio chunk
            silence_threshold: Threshold below which audio is considered silent
        """
        logger.info("Starting streaming transcription...")

        chunk_samples = int(chunk_duration * self.sample_rate)
        audio_buffer = []

        def audio_callback(indata, frames, time, status):
            if status:
                logger.warning(f"Audio stream status: {status}")

            # Add to buffer
            audio_buffer.append(indata.copy())

            # Check if we have enough audio
            if len(audio_buffer) * len(indata) >= chunk_samples:
                # Concatenate buffer
                audio_chunk = np.concatenate(audio_buffer)
                audio_buffer.clear()

                # Check if not silent
                if np.abs(audio_chunk).mean() > silence_threshold:
                    # Transcribe
                    try:
                        result = self.transcribe_audio(audio_chunk.flatten())
                        if result["text"]:
                            callback(result)
                    except Exception as e:
                        logger.error(f"Transcription error: {e}")

        # Start stream
        with sd.InputStream(
            callback=audio_callback,
            channels=1,
            samplerate=self.sample_rate,
            dtype='float32'
        ):
            logger.info("Streaming... Press Ctrl+C to stop")
            try:
                while True:
                    sd.sleep(100)
            except KeyboardInterrupt:
                logger.info("Stopping stream")

    def _calculate_confidence(self, result: Dict) -> float:
        """
        Calculate average confidence from segments

        Args:
            result: Whisper result dictionary

        Returns:
            Average confidence score
        """
        segments = result.get("segments", [])
        if not segments:
            return 0.0

        # Whisper doesn't provide explicit confidence,
        # use average log probability as proxy
        confidences = []
        for seg in segments:
            if "avg_logprob" in seg:
                # Convert log prob to approximate confidence
                confidence = min(1.0, max(0.0, np.exp(seg["avg_logprob"])))
                confidences.append(confidence)

        return np.mean(confidences) if confidences else 0.5

    def detect_language(self, audio_path: str) -> str:
        """
        Detect language from audio file

        Args:
            audio_path: Path to audio file

        Returns:
            Detected language code
        """
        # Load audio
        audio = whisper.load_audio(audio_path)
        audio = whisper.pad_or_trim(audio)

        # Detect language
        mel = whisper.log_mel_spectrogram(audio).to(self.device)
        _, probs = self.model.detect_language(mel)

        detected_lang = max(probs, key=probs.get)
        logger.info(f"Detected language: {detected_lang} (confidence: {probs[detected_lang]:.2f})")

        return detected_lang


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Initialize STT
    stt = WhisperSTT(model_size="base")

    # Record and transcribe
    result = stt.record_and_transcribe(duration=5.0)
    print(f"Transcription: {result['text']}")
    print(f"Confidence: {result['confidence']:.2f}")
