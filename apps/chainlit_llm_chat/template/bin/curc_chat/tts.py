"""Free text-to-speech via Microsoft Edge voices (edge-tts; no API key or billing)."""

import io
import logging
import os

logger = logging.getLogger(__name__)

_MAX_TTS_CHARS = int(os.getenv("CURC_TTS_MAX_CHARS", "2000"))


def is_tts_enabled() -> bool:
    return os.getenv("CURC_VOICE_TTS", "edge").lower() not in ("none", "off", "false", "0")


def get_tts_voice() -> str:
    return os.getenv("CURC_TTS_VOICE", "en-US-AriaNeural")


async def synthesize_speech(text: str) -> tuple[bytes, str]:
    """
    Return (audio_bytes, mime_type) for the assistant reply.

    Uses edge-tts (free). Requires outbound HTTPS from the compute node on first use.
    Set CURC_VOICE_TTS=none to disable spoken replies.
    """
    if not is_tts_enabled():
        return b"", ""

    cleaned = (text or "").strip()
    if not cleaned:
        return b"", ""

    if len(cleaned) > _MAX_TTS_CHARS:
        cleaned = cleaned[:_MAX_TTS_CHARS].rsplit(" ", 1)[0] + "…"

    import edge_tts

    voice = get_tts_voice()
    communicate = edge_tts.Communicate(cleaned, voice)
    buffer = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            buffer.write(chunk["data"])

    audio = buffer.getvalue()
    if not audio:
        raise RuntimeError("TTS produced no audio (check outbound network access on the node)")

    return audio, "audio/mpeg"
