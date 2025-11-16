"""
Text-to-Speech using Coqui TTS
High-quality, natural-sounding speech synthesis for robot responses
"""

import torch
import logging
from typing import Optional, List
import numpy as np
import sounddevice as sd
import soundfile as sf
from pathlib import Path

# Try to import TTS, provide fallback
try:
    from TTS.api import TTS
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False
    logging.warning("Coqui TTS not installed. Install with: pip install TTS")

logger = logging.getLogger(__name__)


class CoquiTTS:
    """
    Text-to-Speech using Coqui TTS
    Supports multi-speaker, multi-lingual synthesis
    """

    def __init__(
        self,
        model_name: str = "tts_models/en/ljspeech/tacotron2-DDC",
        device: str = "cuda" if torch.cuda.is_available() else "cpu",
        vocoder_name: Optional[str] = None,
    ):
        """
        Initialize Coqui TTS

        Args:
            model_name: TTS model identifier
            device: Device to run on
            vocoder_name: Optional vocoder model
        """
        if not TTS_AVAILABLE:
            raise ImportError(
                "Coqui TTS not installed. Install with: pip install TTS"
            )

        self.model_name = model_name
        self.device = device

        logger.info(f"Loading TTS model: {model_name} on {device}...")
        self.tts = TTS(model_name=model_name).to(device)

        # Check if multi-speaker
        self.is_multi_speaker = hasattr(self.tts, 'speakers') and self.tts.speakers
        if self.is_multi_speaker:
            logger.info(f"Multi-speaker model with {len(self.tts.speakers)} speakers")

        # Check if multi-lingual
        self.is_multi_lingual = hasattr(self.tts, 'languages') and self.tts.languages
        if self.is_multi_lingual:
            logger.info(f"Multi-lingual model with {len(self.tts.languages)} languages")

        logger.info("TTS model loaded successfully")

    def synthesize(
        self,
        text: str,
        speaker: Optional[str] = None,
        language: Optional[str] = None,
        speed: float = 1.0,
    ) -> np.ndarray:
        """
        Synthesize speech from text

        Args:
            text: Text to synthesize
            speaker: Speaker identity (for multi-speaker models)
            language: Language code (for multi-lingual models)
            speed: Speech speed multiplier

        Returns:
            Audio waveform as numpy array
        """
        logger.info(f"Synthesizing: '{text[:50]}...'")

        kwargs = {}
        if self.is_multi_speaker and speaker:
            kwargs['speaker'] = speaker
        if self.is_multi_lingual and language:
            kwargs['language'] = language

        # Synthesize
        wav = self.tts.tts(text, **kwargs)

        # Adjust speed if needed
        if speed != 1.0:
            wav = self._adjust_speed(wav, speed)

        return np.array(wav)

    def synthesize_to_file(
        self,
        text: str,
        output_path: str,
        speaker: Optional[str] = None,
        language: Optional[str] = None,
        speed: float = 1.0,
    ):
        """
        Synthesize speech and save to file

        Args:
            text: Text to synthesize
            output_path: Output file path
            speaker: Speaker identity
            language: Language code
            speed: Speech speed multiplier
        """
        wav = self.synthesize(text, speaker, language, speed)

        # Get sample rate
        sample_rate = self.tts.synthesizer.output_sample_rate

        # Save
        sf.write(output_path, wav, sample_rate)
        logger.info(f"Saved audio to {output_path}")

    def speak(
        self,
        text: str,
        speaker: Optional[str] = None,
        language: Optional[str] = None,
        speed: float = 1.0,
        blocking: bool = True,
    ):
        """
        Synthesize and play audio

        Args:
            text: Text to speak
            speaker: Speaker identity
            language: Language code
            speed: Speech speed multiplier
            blocking: Wait for playback to complete
        """
        wav = self.synthesize(text, speaker, language, speed)
        sample_rate = self.tts.synthesizer.output_sample_rate

        # Play audio
        sd.play(wav, sample_rate)
        if blocking:
            sd.wait()

    def batch_synthesize(
        self,
        texts: List[str],
        output_dir: str,
        **kwargs
    ) -> List[str]:
        """
        Batch synthesize multiple texts

        Args:
            texts: List of texts to synthesize
            output_dir: Output directory
            **kwargs: Additional synthesis arguments

        Returns:
            List of output file paths
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        output_paths = []
        for i, text in enumerate(texts):
            output_path = output_dir / f"speech_{i:04d}.wav"
            self.synthesize_to_file(text, str(output_path), **kwargs)
            output_paths.append(str(output_path))

        logger.info(f"Batch synthesized {len(texts)} utterances")
        return output_paths

    def list_speakers(self) -> Optional[List[str]]:
        """Get list of available speakers for multi-speaker models"""
        if self.is_multi_speaker:
            return self.tts.speakers
        return None

    def list_languages(self) -> Optional[List[str]]:
        """Get list of available languages for multi-lingual models"""
        if self.is_multi_lingual:
            return self.tts.languages
        return None

    def _adjust_speed(self, wav: np.ndarray, speed: float) -> np.ndarray:
        """
        Adjust speech speed using resampling

        Args:
            wav: Audio waveform
            speed: Speed multiplier (>1 = faster, <1 = slower)

        Returns:
            Speed-adjusted waveform
        """
        # Simple speed adjustment via resampling
        # For better quality, use librosa's time_stretch
        try:
            import librosa
            wav_adjusted = librosa.effects.time_stretch(wav, rate=speed)
            return wav_adjusted
        except ImportError:
            logger.warning("librosa not available, speed adjustment disabled")
            return wav

    @staticmethod
    def list_available_models() -> List[str]:
        """List all available TTS models"""
        if not TTS_AVAILABLE:
            return []
        return TTS.list_models()


class SimpleTTS:
    """
    Fallback simple TTS using system TTS (for when Coqui is not available)
    """

    def __init__(self):
        logger.warning("Using fallback SimpleTTS - limited functionality")
        try:
            import pyttsx3
            self.engine = pyttsx3.init()
            self.available = True
        except ImportError:
            logger.error("pyttsx3 not available. Install with: pip install pyttsx3")
            self.available = False

    def speak(self, text: str, blocking: bool = True):
        """Speak text using system TTS"""
        if not self.available:
            logger.error("TTS not available")
            return

        self.engine.say(text)
        if blocking:
            self.engine.runAndWait()

    def synthesize_to_file(self, text: str, output_path: str):
        """Save speech to file"""
        if not self.available:
            logger.error("TTS not available")
            return

        self.engine.save_to_file(text, output_path)
        self.engine.runAndWait()


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # List available models
    print("Available TTS models:")
    for model in CoquiTTS.list_available_models()[:5]:
        print(f"  - {model}")

    # Initialize TTS
    try:
        tts = CoquiTTS()

        # Synthesize and play
        tts.speak("Hello! I am your robotic assistant. How can I help you today?")

        # Save to file
        tts.synthesize_to_file(
            "Task completed successfully!",
            "output_speech.wav"
        )
    except Exception as e:
        logger.error(f"TTS initialization failed: {e}")
        logger.info("Trying fallback TTS...")
        tts = SimpleTTS()
        tts.speak("Hello! I am using fallback TTS.")
