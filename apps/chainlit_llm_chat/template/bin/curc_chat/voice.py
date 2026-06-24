"""Speech-to-text: local Whisper on GPU (free, no API key)."""

import asyncio
import io
import logging
import os
import tempfile
import wave
from typing import Optional

logger = logging.getLogger(__name__)

_whisper_model = None


def pcm_chunks_to_wav(pcm_bytes: bytes, sample_rate: int = 24000) -> bytes:
    """Wrap raw PCM16 mono audio in a WAV container for STT."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_bytes)
    return buffer.getvalue()


def _get_whisper_model():
    """Load faster-whisper once per process (downloads model to HF_HOME on first run)."""
    global _whisper_model
    if _whisper_model is not None:
        return _whisper_model

    from faster_whisper import WhisperModel

    size = os.getenv("CURC_WHISPER_MODEL_SIZE", "base")
    device = os.getenv("CURC_WHISPER_DEVICE", "cuda")
    compute_type = os.getenv("CURC_WHISPER_COMPUTE_TYPE", "float16")

    if device == "cuda":
        try:
            _whisper_model = WhisperModel(size, device="cuda", compute_type=compute_type)
            logger.info("Loaded faster-whisper model=%s device=cuda", size)
            return _whisper_model
        except Exception:
            logger.warning("CUDA unavailable for Whisper; falling back to CPU", exc_info=True)

    _whisper_model = WhisperModel(size, device="cpu", compute_type="int8")
    logger.info("Loaded faster-whisper model=%s device=cpu", size)
    return _whisper_model


def _transcribe_wav_sync(wav_bytes: bytes) -> str:
    model = _get_whisper_model()
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp:
        tmp.write(wav_bytes)
        tmp.flush()
        segments, _ = model.transcribe(tmp.name)
        return "".join(segment.text for segment in segments).strip()


async def transcribe_audio_wav(wav_bytes: bytes) -> str:
    """
  Transcribe WAV audio with local faster-whisper (free, runs on the job GPU).

  First run downloads the model into HF_HOME (default: /projects/$USER/.cache/huggingface).
  """
    return await asyncio.to_thread(_transcribe_wav_sync, wav_bytes)


def whisper_model_status() -> Optional[str]:
    """Return a short status string if the model is already loaded."""
    if _whisper_model is None:
        return None
    return os.getenv("CURC_WHISPER_MODEL_SIZE", "base")
