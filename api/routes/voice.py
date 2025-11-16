"""
Voice API endpoints for speech-to-text and text-to-speech
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import logging
import tempfile
import asyncio
from pathlib import Path

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voice", tags=["voice"])

# Global TTS and STT instances (initialized on startup)
_stt_instance = None
_tts_instance = None


class TranscriptionResponse(BaseModel):
    """Transcription result"""
    text: str
    confidence: float
    language: Optional[str] = None


class SpeechRequest(BaseModel):
    """Text-to-speech request"""
    text: str
    speaker: Optional[str] = None
    language: Optional[str] = None
    speed: float = 1.0
    play_audio: bool = False


def initialize_voice_services():
    """Initialize STT and TTS services"""
    global _stt_instance, _tts_instance

    try:
        from perception.voice.stt import WhisperSTT
        from perception.voice.tts import CoquiTTS

        logger.info("Initializing voice services...")

        # Initialize STT
        _stt_instance = WhisperSTT(model_size="base")
        logger.info("STT initialized")

        # Initialize TTS
        try:
            _tts_instance = CoquiTTS()
            logger.info("TTS initialized")
        except Exception as e:
            logger.warning(f"Coqui TTS failed, trying fallback: {e}")
            from perception.voice.tts import SimpleTTS
            _tts_instance = SimpleTTS()

    except Exception as e:
        logger.error(f"Failed to initialize voice services: {e}")


@router.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(
    audio_file: UploadFile = File(...),
    language: Optional[str] = None
):
    """
    Transcribe audio file to text

    Args:
        audio_file: Audio file (wav, mp3, etc.)
        language: Optional language hint

    Returns:
        Transcription result with text and confidence
    """
    if _stt_instance is None:
        raise HTTPException(status_code=503, detail="STT service not initialized")

    # Save uploaded file to temporary location
    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(audio_file.filename).suffix) as tmp:
        content = await audio_file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        # Transcribe
        kwargs = {"language": language} if language else {}
        result = _stt_instance.transcribe_file(tmp_path, **kwargs)

        return TranscriptionResponse(
            text=result["text"],
            confidence=result["confidence"],
            language=result.get("language")
        )

    except Exception as e:
        logger.error(f"Transcription error: {e}")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")

    finally:
        # Clean up temp file
        Path(tmp_path).unlink(missing_ok=True)


@router.post("/synthesize")
async def synthesize_speech(request: SpeechRequest):
    """
    Synthesize speech from text

    Args:
        request: Speech synthesis request

    Returns:
        Audio file or success message
    """
    if _tts_instance is None:
        raise HTTPException(status_code=503, detail="TTS service not initialized")

    try:
        # Create temporary output file
        output_file = tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".wav",
            dir="/tmp"
        )
        output_path = output_file.name
        output_file.close()

        # Synthesize
        _tts_instance.synthesize_to_file(
            text=request.text,
            output_path=output_path,
            speaker=request.speaker,
            language=request.language,
            speed=request.speed
        )

        # Play audio if requested (non-blocking)
        if request.play_audio:
            asyncio.create_task(_play_audio_async(output_path))

        # Return audio file
        return FileResponse(
            output_path,
            media_type="audio/wav",
            filename="speech.wav",
            background=BackgroundTasks().add_task(
                lambda: Path(output_path).unlink(missing_ok=True)
            )
        )

    except Exception as e:
        logger.error(f"Speech synthesis error: {e}")
        raise HTTPException(status_code=500, detail=f"Synthesis failed: {str(e)}")


@router.post("/speak")
async def speak_text(request: SpeechRequest):
    """
    Synthesize and play speech (robot speaks)

    Args:
        request: Speech request

    Returns:
        Success message
    """
    if _tts_instance is None:
        raise HTTPException(status_code=503, detail="TTS service not initialized")

    try:
        # Speak (non-blocking)
        asyncio.create_task(_speak_async(
            request.text,
            request.speaker,
            request.language,
            request.speed
        ))

        return {"status": "speaking", "text": request.text}

    except Exception as e:
        logger.error(f"Speak error: {e}")
        raise HTTPException(status_code=500, detail=f"Speak failed: {str(e)}")


@router.get("/speakers")
async def list_speakers():
    """Get list of available speakers (for multi-speaker models)"""
    if _tts_instance is None:
        raise HTTPException(status_code=503, detail="TTS service not initialized")

    speakers = _tts_instance.list_speakers() if hasattr(_tts_instance, 'list_speakers') else None
    return {"speakers": speakers or []}


@router.get("/languages")
async def list_languages():
    """Get list of available languages"""
    languages = []

    if _tts_instance and hasattr(_tts_instance, 'list_languages'):
        tts_langs = _tts_instance.list_languages()
        if tts_langs:
            languages.extend(tts_langs)

    # Add common STT languages
    stt_languages = ["en", "es", "fr", "de", "it", "pt", "nl", "pl", "ru", "zh", "ja", "ko"]
    languages.extend(stt_languages)

    return {"languages": list(set(languages))}


async def _speak_async(
    text: str,
    speaker: Optional[str],
    language: Optional[str],
    speed: float
):
    """Async wrapper for speaking"""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None,
        lambda: _tts_instance.speak(
            text,
            speaker=speaker,
            language=language,
            speed=speed,
            blocking=True
        )
    )


async def _play_audio_async(audio_path: str):
    """Async audio playback"""
    import sounddevice as sd
    import soundfile as sf

    loop = asyncio.get_event_loop()
    data, samplerate = sf.read(audio_path)
    await loop.run_in_executor(None, lambda: sd.play(data, samplerate) or sd.wait())


# Robot voice command integration
@router.post("/command")
async def voice_command(
    audio_file: UploadFile = File(...),
    execute: bool = True
):
    """
    Process voice command (STT + execute command)

    Args:
        audio_file: Audio file with voice command
        execute: Whether to execute the command

    Returns:
        Transcription and execution result
    """
    # Transcribe
    transcription = await transcribe_audio(audio_file)

    result = {
        "transcription": transcription.text,
        "confidence": transcription.confidence
    }

    if execute and transcription.confidence > 0.5:
        # Execute command via MCP/agent
        try:
            # Import here to avoid circular dependency
            from api.routes.commands import execute_command

            # Execute the transcribed command
            command_result = await execute_command({"query": transcription.text})
            result["execution"] = command_result

            # Speak the response
            if "message" in command_result:
                await speak_text(SpeechRequest(text=command_result["message"]))

        except Exception as e:
            logger.error(f"Command execution error: {e}")
            result["execution"] = {"error": str(e)}

    return result
