"""Smoke tests for free local voice helpers (run before deploying to OOD)."""

import os
import sys
import wave
import io

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from curc_chat.voice import pcm_chunks_to_wav
from curc_chat.tts import is_tts_enabled, get_tts_voice


def test_pcm_chunks_to_wav():
    pcm = b"\x00\x01" * 12000
    wav_bytes = pcm_chunks_to_wav(pcm, sample_rate=24000)
    assert wav_bytes[:4] == b"RIFF"
    with wave.open(io.BytesIO(wav_bytes), "rb") as wav:
        assert wav.getnchannels() == 1
        assert wav.getframerate() == 24000
    print("OK: pcm_chunks_to_wav")


def test_tts_settings_defaults():
    assert is_tts_enabled()
    assert get_tts_voice() == "en-US-AriaNeural"
    print("OK: TTS defaults")


def test_voice_imports():
    import faster_whisper  # noqa: F401
    import edge_tts  # noqa: F401

    print("OK: faster_whisper and edge_tts importable")


if __name__ == "__main__":
    test_pcm_chunks_to_wav()
    test_tts_settings_defaults()
    test_voice_imports()
    print("All voice smoke tests passed.")
