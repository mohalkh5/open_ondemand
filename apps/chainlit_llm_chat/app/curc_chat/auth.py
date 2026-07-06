import os
import uuid
import logging
from pathlib import Path
from typing import Optional

import chainlit as cl

from curc_chat.security import ensure_secure_permissions

logger = logging.getLogger(__name__)


def get_auth_token_path() -> Path:
    """Get the path to the user's private auth token."""
    return Path.home() / ".chainlit_auth_token"


def get_or_create_auth_token() -> str:
    token_path = get_auth_token_path()

    if token_path.exists():
        ensure_secure_permissions(token_path)
        return token_path.read_text().strip()

    token = str(uuid.uuid4())

    try:
        fd = os.open(str(token_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(token)
        logger.info(f"Created new secure auth token at {token_path}")
        return token
    except FileExistsError:
        # Another process created the token between exists() and open().
        ensure_secure_permissions(token_path)
        return token_path.read_text().strip()


def _get_username() -> str:
    return os.getenv("USER") or os.getenv("USERNAME") or "unknown"


def get_current_user() -> Optional[cl.User]:
    try:
        username = _get_username()
        token = get_or_create_auth_token()

        return cl.User(
            identifier=username,
            metadata={
                "username": username,
                "provider": "secure-token",
                "data_id": token,
            },
        )
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        return None


@cl.header_auth_callback
def header_auth_callback(headers: dict) -> Optional[cl.User]:
    """Automatically authenticate users based on private token."""
    return get_current_user()
