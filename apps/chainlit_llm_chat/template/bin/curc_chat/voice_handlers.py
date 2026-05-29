"""
Chainlit voice assistant hooks (microphone → STT → existing Ollama chat).

The microphone button appears in the UI only when @cl.on_audio_chunk is registered.
Users hold **P** to talk, then release to send (see Chainlit multi-modality docs).
"""

import logging
from typing import List

import chainlit as cl

from curc_chat.chainlit_handlers import _ensure_thread_created, handle_user_turn
from curc_chat.settings import get_audio_sample_rate
from curc_chat.voice import pcm_chunks_to_wav, transcribe_audio_wav

logger = logging.getLogger(__name__)

_MIN_AUDIO_SECONDS = 0.5


@cl.on_audio_start
async def on_audio_start():
    cl.user_session.set("audio_chunks", [])
    return True


@cl.on_audio_chunk
async def on_audio_chunk(chunk: cl.InputAudioChunk):
    chunks: List[bytes] = cl.user_session.get("audio_chunks") or []
    if chunk.data:
        chunks.append(chunk.data)
    cl.user_session.set("audio_chunks", chunks)


@cl.on_audio_end
async def on_audio_end():
    chunks: List[bytes] = cl.user_session.get("audio_chunks") or []
    cl.user_session.set("audio_chunks", [])

    if not chunks:
        await cl.Message(
            content="No audio was captured. Hold **P** while speaking, then release."
        ).send()
        return

    sample_rate = get_audio_sample_rate()
    pcm_bytes = b"".join(chunks)
    duration = len(pcm_bytes) / (sample_rate * 2)
    if duration < _MIN_AUDIO_SECONDS:
        await cl.Message(
            content="Recording was too short. Hold **P** a bit longer and try again."
        ).send()
        return

    wav_bytes = pcm_chunks_to_wav(pcm_bytes, sample_rate=sample_rate)
    input_audio = cl.Audio(content=wav_bytes, mime="audio/wav")

    try:
        transcript = await transcribe_audio_wav(wav_bytes)
    except Exception as e:
        logger.exception("Voice transcription failed")
        await cl.Message(
            content=(
                f"Could not transcribe audio: {e}\n\n"
                "Configure `OPENAI_API_KEY` or `WHISPER_BASE_URL` for speech-to-text."
            )
        ).send()
        return

    if not transcript:
        await cl.Message(content="Could not detect speech in the recording.").send()
        return

    model = cl.user_session.get("model", "llama3.2")
    await _ensure_thread_created(transcript, model)

    await cl.Message(
        author="You",
        type="user_message",
        content=transcript,
        elements=[input_audio],
    ).send()

    await handle_user_turn(transcript)
