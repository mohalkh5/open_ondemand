import logging

logging.basicConfig(level=logging.INFO)

from curc_chat.chainlit_handlers import (
    chat_profiles,
    get_user_data_layer,
    header_auth_callback,
    on_chat_resume,
    on_chat_start,
    on_message,
)
from curc_chat import action_handlers  # noqa: F401 — registers @cl.action_callback hooks
from curc_chat import voice_handlers  # noqa: F401 — registers @cl.on_audio_* hooks

__all__ = [
    "header_auth_callback",
    "on_chat_start",
    "on_message",
    "on_chat_resume",
    "chat_profiles",
    "get_user_data_layer",
]
