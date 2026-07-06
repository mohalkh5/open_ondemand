"""Chainlit action callbacks (message buttons and new chat)."""

import json

import chainlit as cl

from curc_chat.chainlit_handlers import curc_message, handle_user_turn
from curc_chat.message_actions import (
    ACTION_COPY_CODE,
    ACTION_NEW_CHAT,
    ACTION_REGENERATE,
    ACTION_SWITCH_VISION,
    extract_code_blocks,
    find_vision_model_name,
    get_cached_message_content,
)
from curc_chat.models import model_cache


async def _regenerate_last_reply() -> None:
    message_history = cl.user_session.get("message_history", [])
    if not message_history or message_history[-1].get("role") != "assistant":
        await curc_message(content="No assistant reply to regenerate.").send()
        return

    message_history.pop()
    cl.user_session.set("message_history", message_history)

    if not message_history or message_history[-1].get("role") != "user":
        await curc_message(content="Could not find the previous user message.").send()
        return

    last_user = message_history[-1]
    await handle_user_turn(
        last_user.get("_api_content", last_user["content"]),
        images=last_user.get("images"),
        skip_user_append=True,
    )


@cl.action_callback(ACTION_REGENERATE)
async def on_regenerate(action: cl.Action):
    await _regenerate_last_reply()
    await action.remove()


@cl.action_callback(ACTION_COPY_CODE)
async def on_copy_code_block(action: cl.Action):
    payload = action.payload or {}
    code = payload.get("code")
    message_id = payload.get("message_id")

    if not code and message_id:
        content = get_cached_message_content(message_id) or ""
        blocks = extract_code_blocks(content)
        code = blocks[0] if blocks else None

    if not code:
        await curc_message(content="No code block found in that message.").send()
        await action.remove()
        return

    # Clipboard is handled in the browser via custom.js; also show the block in chat.
    await cl.send_window_message(
        json.dumps({"type": "curc_copy_code", "code": code}),
    )
    await curc_message(
        content=(
            "**Code block** (also sent to your clipboard when supported):\n\n"
            f"```\n{code}\n```"
        )
    ).send()
    await action.remove()


@cl.action_callback(ACTION_SWITCH_VISION)
async def on_switch_vision_model(action: cl.Action):
    payload = action.payload or {}
    vision_model = payload.get("model") or find_vision_model_name()

    if not vision_model:
        await curc_message(
            content="No vision-capable model is available on this Ollama server."
        ).send()
        await action.remove()
        return

    model_info = model_cache.get_model_info(vision_model)
    cl.user_session.set("model", vision_model)
    cl.user_session.set("model_info", model_info)

    await curc_message(
        content=(
            f"Switched to **{vision_model}**. "
            "Send a message with an image attachment, or use **Regenerate** "
            "if your last message included images."
        )
    ).send()
    await action.remove()


@cl.action_callback(ACTION_NEW_CHAT)
async def on_new_chat(action: cl.Action):
    """Open a real new Chainlit thread in the browser (do not reset in-place)."""
    await action.remove()
    await cl.send_window_message(json.dumps({"type": "curc_new_chat"}))
