import asyncio
import logging
import os
from typing import List, Optional

import chainlit as cl
from ollama import AsyncClient

from curc_chat.auth import get_current_user, get_or_create_auth_token, header_auth_callback
from curc_chat.models import model_cache
from curc_chat.models.ollama_models import single_available_model_name
from curc_chat.settings import (
    get_ollama_host,
    get_ollama_num_ctx,
    get_ollama_num_predict,
    get_system_prompt_path,
)
from curc_chat.hpc_files import process_hpc_attachments
from curc_chat.uploads import PDF_EMPTY_MARKER
from curc_chat.message_actions import build_assistant_actions, remember_message_content
from curc_chat.storage.sqlite_layer import get_data_layer

logger = logging.getLogger(__name__)

if not os.getenv("CHAINLIT_AUTH_SECRET"):
    os.environ["CHAINLIT_AUTH_SECRET"] = get_or_create_auth_token()

client = AsyncClient(host=f"http://{get_ollama_host()}")


def curc_message(content: str = "", **kwargs) -> cl.Message:
    """Create a Chainlit message. Feedback buttons are hidden via public/custom.css and custom.js."""
    kwargs.pop("disable_human_feedback", None)
    return cl.Message(content=content, **kwargs)


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


def _profile_description(model: dict) -> str:
    """Short blurb for the model picker (header / chat profile menu)."""
    caps = model.get("capabilities", [])
    tags = []
    if "completion" in caps:
        tags.append("Chat")
    if "vision" in caps:
        tags.append("Vision")
    tag_line = " · ".join(tags) if tags else "Chat"

    detail_lines = [
        ln.strip()
        for ln in model.get("description", "").split("\n")
        if ln.strip() and not ln.strip().lower().startswith("capabilities:")
    ]
    summary = "\n".join(detail_lines) if detail_lines else "Available on this Ollama server."

    return f"**{model['name']}** - {tag_line}\n\n{summary}"


@cl.set_chat_profiles
async def chat_profiles():
    models = await model_cache.refresh(client)

    profiles = []
    for model in models:
        profiles.append(
            cl.ChatProfile(
                name=model["name"],
                markdown_description=_profile_description(model),
            )
        )
    return profiles


@cl.data_layer
def get_user_data_layer():
    return resolve_user_data_layer()


def init_chat_session() -> None:
    """Reset per-chat session state (used on start and 'New chat' action)."""
    models = model_cache.models or []
    chat_profile = cl.user_session.get("chat_profile")
    if not chat_profile and models:
        chat_profile = models[0]["name"]
    model_info = (
        model_cache.get_model_info(chat_profile) if chat_profile else {}
    )

    cl.user_session.set("model", chat_profile)
    cl.user_session.set("model_info", model_info)
    cl.user_session.set("message_history", [])
    cl.user_session.set("system_prompt", load_system_prompt())
    cl.user_session.set("assistant_message_cache", {})
    cl.user_session.set("thread_created", False)


async def _send_single_model_settings() -> None:
    """Expose the active model in chat settings when the profile dropdown is hidden."""
    model_name = single_available_model_name(model_cache.models)
    if not model_name or model_cache.load_error:
        return

    await cl.ChatSettings(
        [
            cl.input_widget.Select(
                id="ollama_model",
                label="Active Ollama model",
                values=[model_name],
                initial_index=0,
            )
        ]
    ).send()


@cl.on_chat_start
async def on_chat_start():
    if not model_cache.models:
        await model_cache.refresh(client)
    init_chat_session()
    # Welcome disclaimer is injected on the empty-state screen in public/custom.js.
    if model_cache.load_error:
        await curc_message(content=f"❌ **{model_cache.load_error}**").send()
        return

    await _send_single_model_settings()


@cl.on_chat_resume
async def on_chat_resume(thread: dict):
    message_history = []

    for step in thread.get("steps", []):
        step_type = step.get("type")
        output = step.get("output", "") or ""
        # Resume with slim history — do not reload huge file bodies from SQLite.
        if len(output) > 2000 and "--- PDF:" in output:
            output = output.split("\n", 1)[0] or "[Attached file — content not reloaded on resume]"
        if step_type == "user_message":
            message_history.append({"role": "user", "content": output})
        elif step_type == "assistant_message":
            message_history.append({"role": "assistant", "content": output})

    cl.user_session.set("message_history", message_history)
    cl.user_session.set("system_prompt", load_system_prompt())
    cl.user_session.set("thread_created", True)

    metadata = thread.get("metadata", {})
    model = metadata.get("model")
    cl.user_session.set("model", model)
    cl.user_session.set(
        "model_info",
        model_cache.get_model_info(model) if model else {},
    )

    if model_cache.load_error:
        await curc_message(content=f"❌ **{model_cache.load_error}**").send()
        return

    await _send_single_model_settings()


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


def _build_ollama_messages(
    system_prompt: str,
    message_history: List[dict],
    *,
    skip_user_append: bool = False,
    override_user_content: Optional[str] = None,
    override_images: Optional[List[str]] = None,
) -> List[dict]:
    """Build Ollama messages; file bodies stay in _api_content for the latest user turn only."""
    messages: List[dict] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    for i, msg in enumerate(message_history):
        is_last = i == len(message_history) - 1
        if is_last and msg.get("role") == "user":
            content = msg.get("_api_content", msg.get("content", ""))
            if skip_user_append and override_user_content is not None:
                content = override_user_content
            entry: dict = {"role": "user", "content": content}
            imgs = override_images if skip_user_append else msg.get("images")
            if imgs:
                entry["images"] = imgs
            messages.append(entry)
        else:
            messages.append({"role": msg["role"], "content": msg.get("content", "")})

    return messages


def _history_label_for_attachments(
    clean_message: str, attached_paths: List[str]
) -> str:
    """Short text stored in session history (avoids re-sending large files every turn)."""
    path_note = ", ".join(f"`{p}`" for p in attached_paths)
    attach_line = f"[Attached: {path_note}]"
    if clean_message.strip():
        return f"{clean_message.strip()}\n{attach_line}"
    return attach_line


async def handle_user_turn(
    user_content: str,
    images: Optional[List[str]] = None,
    *,
    skip_user_append: bool = False,
    history_content: Optional[str] = None,
) -> None:
    """Run one chat turn against Ollama."""
    if model_cache.load_error:
        await curc_message(content=f"❌ **{model_cache.load_error}**").send()
        return

    model = cl.user_session.get("model")
    if not model:
        await curc_message(
            content="❌ **Error fetching models.**"
        ).send()
        return

    model_info = cl.user_session.get("model_info", {})
    message_history = cl.user_session.get("message_history", [])
    system_prompt = cl.user_session.get("system_prompt", "")

    slim = history_content if history_content is not None else user_content

    if not skip_user_append:
        entry: dict = {"role": "user", "content": slim, "_api_content": user_content}
        if images:
            entry["images"] = images
        message_history.append(entry)
        cl.user_session.set("message_history", message_history)

    messages = _build_ollama_messages(
        system_prompt,
        message_history,
        skip_user_append=skip_user_append,
        override_user_content=user_content if skip_user_append else None,
        override_images=images if skip_user_append else None,
    )

    approx_chars = sum(len(m.get("content", "")) for m in messages)
    logger.info(
        "Ollama chat turn: model=%s messages=%d approx_chars=%d",
        model,
        len(messages),
        approx_chars,
    )

    response_message = curc_message(content="")
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
        stream = await client.chat(
            model=model,
            messages=messages,
            stream=True,
            options={
                "num_ctx": get_ollama_num_ctx(),
                "num_predict": get_ollama_num_predict(),
            },
        )

        stream_started = False
        async for chunk in stream:
            msg = chunk.get("message") or {}
            content = msg.get("content") or chunk.get("response") or ""
            if not content:
                continue

            if not stream_started:
                stream_started = True
                animation_task.cancel()
                try:
                    await animation_task
                except asyncio.CancelledError:
                    pass
                response_message.content = ""
                await response_message.update()

            full_response += content
            await response_message.stream_token(content)

        if full_response.strip():
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
            logger.info("Ollama reply: model=%s chars=%d", model, len(full_response))
        else:
            animation_task.cancel()
            try:
                await animation_task
            except asyncio.CancelledError:
                pass
            response_message.content = (
                "⚠️ **The model returned an empty response.**\n\n"
                "Common causes:\n"
                "- The PDF has no extractable text (scanned/image PDF)\n"
                "- The prompt is too large for the model context\n"
                "- The model timed out\n\n"
                "Try **New chat**, attach one file, or ask a shorter question."
            )
            await response_message.update()
            full_response = response_message.content
            logger.warning(
                "Ollama empty stream: model=%s messages=%d approx_chars=%d",
                model,
                len(messages),
                approx_chars,
            )

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
    if model_cache.load_error:
        await curc_message(content=f"❌ **{model_cache.load_error}**").send()
        return

    model = cl.user_session.get("model")
    if not model:
        await curc_message(
            content="❌ **Error fetching models.**"
        ).send()
        return

    model_info = cl.user_session.get("model_info", {})

    if message.elements:
        await curc_message(
            content=(
                "⚠️ **Browser upload is disabled** and was ignored.\n\n"
                "Attach files with an Alpine **file** path, for example:\n\n"
                "`/file /projects/$USER/myfile.pdf`\n\n"
                "Use the **Files** app in Open OnDemand to find the full path."
            )
        ).send()

    clean_text, additional_context, images, path_errors, attached_paths = (
        process_hpc_attachments(message.content)
    )

    if path_errors:
        error_text = "\n".join(f"- {err}" for err in path_errors)
        await curc_message(
            content=(
                "❌ **Could not attach file(s). Your message was not sent to the model.**\n\n"
                f"{error_text}"
            )
        ).send()
        return

    if additional_context or images:
        attached = []
        if images:
            attached.append(f"{len(images)} image(s)")
        if additional_context:
            attached.append("text/PDF content")
        await curc_message(
            content=f"📎 **File attached from Alpine filesystem:** {', '.join(attached)}"
        ).send()

    if additional_context and PDF_EMPTY_MARKER in additional_context:
        await curc_message(
            content=f"⚠️ **Could not read PDF text.**\n{additional_context.strip()}"
        ).send()
        if not clean_text.strip():
            return

    await _ensure_thread_created(clean_text or message.content, model)

    if images and "vision" not in model_info.get("capabilities"):
        await curc_message(
            content=(
                f"⚠️ **{model}** doesn't support vision. "
                f"Please switch to a vision-capable model using the model selector."
            )
        ).send()
        return

    api_user_content = clean_text.strip()
    if additional_context:
        if not api_user_content:
            api_user_content = "Please analyze the attached file(s)."
        api_user_content += additional_context

    history_content = (
        _history_label_for_attachments(clean_text, attached_paths)
        if attached_paths
        else None
    )

    vision_images = None
    if images and "vision" in model_info.get("capabilities", []):
        vision_images = images

    if not api_user_content.strip() and not vision_images:
        await curc_message(
            content="Please enter a message or valid Alpine file path(s)."
        ).send()
        return

    await handle_user_turn(
        api_user_content,
        images=vision_images,
        history_content=history_content,
    )


__all__ = [
    "header_auth_callback",
    "on_chat_start",
    "on_message",
    "on_chat_resume",
    "chat_profiles",
    "get_user_data_layer",
    "handle_user_turn",
    "init_chat_session",
    "_ensure_thread_created",
]
