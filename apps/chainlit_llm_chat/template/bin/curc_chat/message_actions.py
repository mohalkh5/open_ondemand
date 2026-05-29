"""Build Chainlit message action buttons for assistant replies."""

import re
from typing import Any, Dict, List, Optional

import chainlit as cl

from curc_chat.models import model_cache

ACTION_REGENERATE = "curc_regenerate"
ACTION_COPY_CODE = "curc_copy_code_block"
ACTION_SWITCH_VISION = "curc_switch_vision_model"
ACTION_NEW_CHAT = "curc_new_chat"

_CODE_BLOCK_RE = re.compile(r"```(?:[\w+-]*)?\n(.*?)```", re.DOTALL)


def extract_code_blocks(text: str) -> List[str]:
    """Return fenced code block bodies from markdown (may be empty)."""
    if not text:
        return []
    return [block.strip() for block in _CODE_BLOCK_RE.findall(text) if block.strip()]


def find_vision_model_name() -> Optional[str]:
    """First Ollama model that reports vision capability."""
    models = model_cache.models or []
    for model in models:
        if "vision" in model.get("capabilities", []):
            name = model.get("name", "")
            if name and not name.startswith("No models"):
                return name
    return None


def build_assistant_actions(
    *,
    message_id: str,
    content: str,
    model: str,
    model_info: Dict[str, Any],
) -> List[cl.Action]:
    """Action buttons shown under an assistant message."""
    actions: List[cl.Action] = [
        cl.Action(
            name=ACTION_REGENERATE,
            label="Regenerate",
            icon="refresh-cw",
            description="Generate the last reply again",
            payload={"message_id": message_id},
        ),
        cl.Action(
            name=ACTION_NEW_CHAT,
            label="New chat",
            icon="message-square-plus",
            description="Start a fresh conversation",
            payload={},
        ),
    ]

    code_blocks = extract_code_blocks(content)
    if code_blocks:
        actions.insert(
            1,
            cl.Action(
                name=ACTION_COPY_CODE,
                label="Copy code block",
                icon="clipboard-copy",
                description="Copy the first code block from this reply",
                payload={
                    "message_id": message_id,
                    "code": code_blocks[0],
                },
            ),
        )

    if "vision" not in model_info.get("capabilities", []):
        vision_model = find_vision_model_name()
        if vision_model:
            actions.append(
                cl.Action(
                    name=ACTION_SWITCH_VISION,
                    label="Switch to vision model",
                    icon="eye",
                    description=f"Use {vision_model} for image attachments",
                    payload={"model": vision_model, "message_id": message_id},
                )
            )

    return actions


def remember_message_content(message_id: str, content: str) -> None:
    """Cache assistant text for action callbacks (keyed by Chainlit message id)."""
    if not message_id:
        return
    cache: Dict[str, str] = cl.user_session.get("assistant_message_cache") or {}
    cache[message_id] = content
    cl.user_session.set("assistant_message_cache", cache)


def get_cached_message_content(message_id: str) -> Optional[str]:
    cache: Dict[str, str] = cl.user_session.get("assistant_message_cache") or {}
    return cache.get(message_id)
