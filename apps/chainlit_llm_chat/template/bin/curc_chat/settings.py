import os
from pathlib import Path

def get_ollama_host() -> str:
    return os.getenv("OLLAMA_HOST", "localhost:11434")


def get_system_prompt_path() -> Path:
    return Path(__file__).resolve().parent.parent / "system_prompt.txt"


def get_audio_sample_rate() -> int:
    return int(os.getenv("CHAINLIT_AUDIO_SAMPLE_RATE", "24000"))


def get_max_attach_size_bytes() -> int:
    """Max attachment size per file (default 500 MB)."""
    mb = int(os.getenv("CURC_CHAT_MAX_ATTACH_MB", "500"))
    return mb * 1024 * 1024


def get_max_attach_files() -> int:
    return int(os.getenv("CURC_CHAT_MAX_ATTACH_FILES", "20"))


def get_whisper_model_size() -> str:
    return os.getenv("CURC_WHISPER_MODEL_SIZE", "base")


def is_voice_tts_enabled() -> bool:
    return os.getenv("CURC_VOICE_TTS", "edge").lower() not in ("none", "off", "false", "0")
