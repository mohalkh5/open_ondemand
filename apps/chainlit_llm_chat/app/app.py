import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.info(
    "CURC LLM chat starting: HPC /file path attachments ON, browser upload OFF"
)

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
from curc_chat import ui_meta  # noqa: F401 — registers /curc/ui-meta

__all__ = [
    "header_auth_callback",
    "on_chat_start",
    "on_message",
    "on_chat_resume",
    "chat_profiles",
    "get_user_data_layer",
]
