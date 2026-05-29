import asyncio
import logging
import os
from typing import List, Optional

import chainlit as cl
from ollama import AsyncClient

from curc_chat.auth import get_current_user, get_or_create_auth_token, header_auth_callback
from curc_chat.models import model_cache
from curc_chat.settings import get_ollama_host, get_system_prompt_path
from curc_chat.message_actions import build_assistant_actions, remember_message_content
from curc_chat.storage.sqlite_layer import get_data_layer
from curc_chat.uploads import process_uploaded_files

logger = logging.getLogger(__name__)

if not os.getenv("CHAINLIT_AUTH_SECRET"):
    os.environ["CHAINLIT_AUTH_SECRET"] = get_or_create_auth_token()

client = AsyncClient(host=f"http://{get_ollama_host()}")


def load_system_prompt() -> str:
    prompt_path = get_system_prompt_path()
    if prompt_path.exists():
        return prompt_path.read_text().strip()
    return "You are a helpful AI assistant."


def resolve_user_data_layer():
    user = get_current_user()
    if user:
        data_id = user.metadata.get("data_id", user.identifier)
        return get_data_layer(data_id)
    return None


@cl.set_chat_profiles
async def chat_profiles():
    models = await model_cache.refresh(client)

    profiles = []
    for model in models:
        profiles.append(
            cl.ChatProfile(
                name=model["name"],
                markdown_description=model["description"],
            )
        )
    return profiles


@cl.data_layer
def get_user_data_layer():
    return resolve_user_data_layer()


def init_chat_session() -> None:
    """Reset per-chat session state (used on start and 'New chat' action)."""
    chat_profile = cl.user_session.get("chat_profile") or "llama3.2"
    model_info = model_cache.get_model_info(chat_profile)

    cl.user_session.set("model", chat_profile)
    cl.user_session.set("model_info", model_info)
    cl.user_session.set("message_history", [])
    cl.user_session.set("system_prompt", load_system_prompt())
    cl.user_session.set("assistant_message_cache", {})
    cl.user_session.set("thread_created", False)


async def send_welcome_message() -> None:
    """Welcome copy with a New chat action (also available on each assistant reply)."""
    from curc_chat.message_actions import ACTION_NEW_CHAT

    model = cl.user_session.get("model", "llama3.2")
    await cl.Message(
        content=(
            f"**CURC LLM Chat** — model: `{model}`\n\n"
            "- Choose a model from the profile menu\n"
            "- Attach files or images (use a vision model for images)\n"
            "- Hold **P** to record voice input\n"
            "- Use action buttons under replies to regenerate or start a new chat"
        ),
        actions=[
            cl.Action(
                name=ACTION_NEW_CHAT,
                label="New chat",
                icon="message-square-plus",
                description="Clear this session and start fresh",
                payload={},
            )
        ],
    ).send()


@cl.on_chat_start
async def on_chat_start():
    init_chat_session()
    await send_welcome_message()


@cl.on_chat_resume
async def on_chat_resume(thread: dict):
    message_history = []

    for step in thread.get("steps", []):
        step_type = step.get("type")
        if step_type == "user_message":
            message_history.append({"role": "user", "content": step.get("output", "")})
        elif step_type == "assistant_message":
            message_history.append({"role": "assistant", "content": step.get("output", "")})

    cl.user_session.set("message_history", message_history)
    cl.user_session.set("system_prompt", load_system_prompt())

    metadata = thread.get("metadata", {})
    model = metadata.get("model", "llama3.2")
    cl.user_session.set("model", model)
    cl.user_session.set("model_info", model_cache.get_model_info(model))


async def send_animated_message(
    msg: cl.Message,
    base_msg: str,
    frames: List[str],
    interval: float = 0.8,
) -> None:
    if not msg.id:
        await msg.send()

    progress = 0

    try:
        while True:
            current_frame = frames[progress % len(frames)]
            msg.content = f"{current_frame} {base_msg}"
            await msg.update()

            progress += 1
            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        pass


async def _ensure_thread_created(title: str, model: str) -> None:
    if cl.user_session.get("thread_created", False):
        return

    try:
        thread_id = cl.context.session.thread_id
        user = cl.user_session.get("user")
        user_id = user.identifier if user else None

        thread_name = title[:50].strip()
        if len(title) > 50:
            thread_name += "..."

        data_layer = resolve_user_data_layer()
        if data_layer and thread_id:
            await data_layer.create_thread(
                thread_id=thread_id,
                user_id=user_id,
                name=thread_name,
                metadata={"model": model},
            )
        cl.user_session.set("thread_created", True)
    except Exception as e:
        logger.warning(f"Error creating thread: {e}")


async def handle_user_turn(
    user_content: str,
    images: Optional[List[str]] = None,
    *,
    skip_user_append: bool = False,
) -> None:
    """Run one chat turn against Ollama (shared by text and voice input)."""
    model = cl.user_session.get("model", "llama3.2")
    model_info = cl.user_session.get("model_info", {})
    message_history = cl.user_session.get("message_history", [])
    system_prompt = cl.user_session.get("system_prompt", "")

    user_message = {"role": "user", "content": user_content}
    if images:
        user_message["images"] = images

    if not skip_user_append:
        message_history.append(user_message)
        cl.user_session.set("message_history", message_history)

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.extend(message_history)

    response_message = cl.Message(content="")
    await response_message.send()

    animation_task = asyncio.create_task(
        send_animated_message(
            response_message,
            "Thinking...",
            ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"],
            0.2,
        )
    )

    try:
        full_response = ""
        stream = await client.chat(model=model, messages=messages, stream=True)

        first_chunk = True
        async for chunk in stream:
            if first_chunk:
                animation_task.cancel()
                try:
                    await animation_task
                except asyncio.CancelledError:
                    pass
                first_chunk = False
                response_message.content = ""
                await response_message.update()

            if "message" in chunk and "content" in chunk["message"]:
                content = chunk["message"]["content"]
                full_response += content
                await response_message.stream_token(content)

        if not first_chunk:
            response_message.content = full_response
            response_message.actions = build_assistant_actions(
                message_id=response_message.id or "",
                content=full_response,
                model=model,
                model_info=model_info,
            )
            if response_message.id:
                remember_message_content(response_message.id, full_response)
            await response_message.update()
        else:
            animation_task.cancel()
            try:
                await animation_task
            except asyncio.CancelledError:
                pass

        message_history.append({"role": "assistant", "content": full_response})
        cl.user_session.set("message_history", message_history)

    except Exception as e:
        animation_task.cancel()
        error_msg = (
            f"❌ Error communicating with Ollama: {str(e)}\n\n"
            f"Make sure Ollama is running and the model **{model}** is available.\n"
            f"You can pull the model with: `ollama pull {model}`"
        )
        response_message.content = error_msg
        await response_message.update()


@cl.on_message
async def on_message(message: cl.Message):
    model = cl.user_session.get("model", "llama3.2")
    model_info = cl.user_session.get("model_info", {})

    await _ensure_thread_created(message.content, model)

    additional_context, images = process_uploaded_files(message.elements)

    if images and "vision" not in model_info.get("capabilities"):
        await cl.Message(
            content=(
                f"⚠️ **{model}** doesn't support vision. "
                f"Please switch to a vision-capable model using the model selector."
            )
        ).send()
        return

    user_content = message.content
    if additional_context:
        user_content += additional_context

    vision_images = None
    if images and "vision" in model_info.get("capabilities", []):
        vision_images = images

    await handle_user_turn(user_content, images=vision_images)


__all__ = [
    "header_auth_callback",
    "on_chat_start",
    "on_message",
    "on_chat_resume",
    "chat_profiles",
    "get_user_data_layer",
    "handle_user_turn",
    "init_chat_session",
    "send_welcome_message",
    "_ensure_thread_created",
]
