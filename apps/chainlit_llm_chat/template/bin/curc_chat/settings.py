import os
from pathlib import Path

def get_ollama_host() -> str:
    return os.getenv("OLLAMA_HOST", "localhost:11434")


def get_system_prompt_path() -> Path:
    return Path(__file__).resolve().parent.parent / "system_prompt.txt"


def get_max_attach_size_bytes() -> int:
    """Max attachment size per file (default 500 MB)."""
    mb = int(os.getenv("CURC_CHAT_MAX_ATTACH_MB", "500"))
    return mb * 1024 * 1024


def get_max_attach_files() -> int:
    return int(os.getenv("CURC_CHAT_MAX_ATTACH_FILES", "20"))


def get_max_pdf_extract_chars() -> int:
    """Max characters injected from a single PDF into one prompt."""
    return int(os.getenv("CURC_CHAT_MAX_PDF_CHARS", "120000"))


def get_ollama_num_ctx() -> int:
    return int(os.getenv("CURC_OLLAMA_NUM_CTX", "32768"))


def get_ollama_num_predict() -> int:
    return int(os.getenv("CURC_OLLAMA_NUM_PREDICT", "4096"))
