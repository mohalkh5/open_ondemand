import io
import logging
import os
import wave
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


def pcm_chunks_to_wav(pcm_bytes: bytes, sample_rate: int = 24000) -> bytes:
    """Wrap raw PCM16 mono audio in a WAV container for STT APIs."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_bytes)
    return buffer.getvalue()


def get_whisper_client():
    """Build an OpenAI-compatible client for Whisper transcription."""
    from openai import AsyncOpenAI

    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("WHISPER_API_KEY")
    base_url = os.getenv("WHISPER_BASE_URL")

    if not api_key and not base_url:
        return None

    return AsyncOpenAI(
        api_key=api_key or "not-needed",
        base_url=base_url,
    )


async def transcribe_audio_wav(wav_bytes: bytes) -> str:
    """
    Transcribe WAV audio using an OpenAI-compatible Whisper endpoint.

    Configure on CURC with either:
      - OPENAI_API_KEY (api.openai.com), or
      - WHISPER_BASE_URL + WHISPER_API_KEY for a hosted Whisper endpoint.
    """
    client = get_whisper_client()
    if client is None:
        raise RuntimeError(
            "Speech-to-text is not configured. Set OPENAI_API_KEY or "
            "WHISPER_BASE_URL (and optionally WHISPER_API_KEY) on the compute node."
        )

    model = os.getenv("WHISPER_MODEL", "whisper-1")
    whisper_input: Tuple[str, bytes, str] = ("audio.wav", wav_bytes, "audio/wav")

    response = await client.audio.transcriptions.create(
        model=model,
        file=whisper_input,
    )
    text = getattr(response, "text", None) or str(response)
    return text.strip()
