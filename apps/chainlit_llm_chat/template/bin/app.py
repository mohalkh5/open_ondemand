import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.info(
    "CURC LLM chat starting: HPC /file path attachments ON, browser upload OFF"
)

try:
    from curc_chat.voice_deps import ensure_voice_packages

    if not ensure_voice_packages():
        logger.warning("Voice input/output disabled (packages not installed).")
except Exception as exc:
    logger.warning("Voice dependency check skipped: %s", exc)

from curc_chat.chainlit_handlers import (
    chat_profiles,
    get_user_data_layer,
    header_auth_callback,
    on_chat_resume,
    on_chat_start,
    on_message,
)
from curc_chat import action_handlers  # noqa: F401 — registers @cl.action_callback hooks
from curc_chat import starters  # noqa: F401 — registers @cl.set_starters

try:
    from curc_chat import voice_handlers  # noqa: F401 — registers @cl.on_audio_* hooks
except Exception as exc:
    logger.warning("Voice handlers not loaded: %s", exc)

__all__ = [
    "header_auth_callback",
    "on_chat_start",
    "on_message",
    "on_chat_resume",
    "chat_profiles",
    "get_user_data_layer",
]
