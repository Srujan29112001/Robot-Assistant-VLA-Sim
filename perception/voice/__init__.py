"""
Voice perception module for speech-to-text and text-to-speech
"""

from .stt import WhisperSTT
from .tts import CoquiTTS

__all__ = ['WhisperSTT', 'CoquiTTS']
