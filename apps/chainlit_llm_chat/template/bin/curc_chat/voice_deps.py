"""Verify optional voice dependencies (faster-whisper, edge-tts)."""

import logging
import shutil
import subprocess
import sys

logger = logging.getLogger(__name__)

_VOICE_PACKAGES = ("faster-whisper>=1.0.0", "edge-tts>=6.1.0")


def _imports_ok() -> bool:
    try:
        import faster_whisper  # noqa: F401
        import edge_tts  # noqa: F401

        return True
    except ImportError:
        return False


def ensure_voice_packages() -> bool:
    """
    Return True if faster-whisper and edge-tts are importable.

    The shared CURC venv may already include them. If not, try pip only when
    available; never block app startup on install failure.
    """
    if _imports_ok():
        return True

    if not shutil.which("pip") and not shutil.which(f"{sys.executable}"):
        logger.warning("Voice packages missing and pip unavailable; voice features disabled.")
        return False

    logger.warning("Voice packages missing; attempting install in this Python environment...")

    attempts = (
        [sys.executable, "-m", "pip", "install", *_VOICE_PACKAGES],
        [sys.executable, "-m", "pip", "install", "--user", *_VOICE_PACKAGES],
    )
    for cmd in attempts:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        except Exception as exc:
            logger.warning("Voice package install failed: %s", exc)
            continue
        if result.returncode != 0:
            logger.warning(
                "pip install failed (exit %s): %s",
                result.returncode,
                (result.stderr or result.stdout or "").strip()[-800:],
            )
            continue
        if _imports_ok():
            logger.info("Voice packages ready (faster-whisper, edge-tts)")
            return True

    logger.warning(
        "Voice packages not available. Speech input/output stays disabled "
        "(UI is off in config.toml)."
    )
    return False
