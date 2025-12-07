"""
Chainlit LLM Chat with Ollama Integration

A chat interface with:
- Local LLM via Ollama
- Uses a private token file (~/.chainlit_auth_token) for automatic- Secure token authentication.
- Per-user SQLite chat persistence
- File uploads and multi-modal support (vision models)
- Chat profiles for model selection
"""

import logging
import os
import asyncio
from typing import List
from pathlib import Path
from auth import get_or_create_auth_token
import chainlit as cl
from ollama import AsyncClient
from pathlib import Path

from auth import header_auth_callback, get_current_user
from data_layer import get_data_layer
from models import model_cache
from utils import process_uploaded_files

# --- Dynamic Secret Generation ---
if not os.getenv("CHAINLIT_AUTH_SECRET"):
    # Use the secure token as the secret
    os.environ["CHAINLIT_AUTH_SECRET"] = get_or_create_auth_token()
# ---------------------------------

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "localhost:11434")
SYSTEM_PROMPT_FILE = Path(__file__).parent / "system_prompt.txt"

# Initialize Ollama client
client = AsyncClient(host=f"http://{OLLAMA_HOST}")


def load_system_prompt() -> str:
    """Load the system prompt from file."""
    if SYSTEM_PROMPT_FILE.exists():
        return SYSTEM_PROMPT_FILE.read_text().strip()
    return "You are a helpful AI assistant."


@cl.set_chat_profiles
async def chat_profiles():
    """Define available chat profiles (models) by querying Ollama."""
    models = await model_cache.refresh(client)
    
    profiles = []
    for model in models:
        profiles.append(
            cl.ChatProfile(
                name=model["name"],
                markdown_description=f"{model['display_name']}\n\n{model['description']}",
            )
        )
    return profiles


@cl.data_layer
def get_user_data_layer():
    """
    Create a per-user data layer based on secure token.
    Enables the chat history sidebar.
    """
    user = get_current_user()
    if user:
        data_id = user.metadata.get("data_id", user.identifier)
        return get_data_layer(data_id)
    return None


@cl.on_chat_start
async def on_chat_start():
    """Initialize a new chat session."""
    chat_profile = cl.user_session.get("chat_profile") or "llama3.2"
    model_info = model_cache.get_model_info(chat_profile)
    
    # Initialize session state
    cl.user_session.set("model", chat_profile)
    cl.user_session.set("model_info", model_info)
    cl.user_session.set("message_history", [])
    cl.user_session.set("system_prompt", load_system_prompt())
    cl.user_session.set("thread_created", False)


@cl.on_chat_resume
async def on_chat_resume(thread: dict):
    """Resume a previous chat session."""
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
    interval: float = 0.8
    ) -> None:
    """Display animated message with minimal resource usage"""
    # Ensure message is sent
    if not msg.id:
        await msg.send()
    
    progress = 0
    
    try:
        while True:
            # Efficient progress calculation
            current_frame = frames[progress % len(frames)]

            # Single update operation - overwrite entire content
            new_content = f"{current_frame} {base_msg}"
            msg.content = new_content
            await msg.update()
            
            progress += 1
            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        # We don't reset content here to allow the caller to overwrite it immediately
        pass


async def _create_thread_on_first_message(message: cl.Message, model: str):
    """Create thread in data layer on first user message."""
    if cl.user_session.get("thread_created", False):
        return
    
    try:
        thread_id = cl.context.session.thread_id
        user = cl.user_session.get("user")
        user_id = user.identifier if user else None
        
        # Use first ~50 chars of message as thread name
        thread_name = message.content[:50].strip()
        if len(message.content) > 50:
            thread_name += "..."
        
        data_layer = get_user_data_layer()
        if data_layer and thread_id:
            await data_layer.create_thread(
                thread_id=thread_id,
                user_id=user_id,
                name=thread_name,
                metadata={"model": model}
            )
        cl.user_session.set("thread_created", True)
    except Exception as e:
        logger.warning(f"Error creating thread: {e}")


@cl.on_message
async def on_message(message: cl.Message):
    """Handle incoming messages."""
    model = cl.user_session.get("model", "llama3.2")
    model_info = cl.user_session.get("model_info", {})
    message_history = cl.user_session.get("message_history", [])
    system_prompt = cl.user_session.get("system_prompt", "")
    
    # Create thread on first message (like Claude/ChatGPT)
    await _create_thread_on_first_message(message, model)
    
    # Process any uploaded files
    additional_context, images = process_uploaded_files(message.elements)
    
    # Check if images are uploaded but model doesn't support vision
    if images and not model_info.get("vision", False):
        await cl.Message(
            content=f"⚠️ You uploaded images, but **{model}** doesn't support vision. "
                    f"Please switch to a vision-capable model using the model selector."
        ).send()
        return
    
    # Build the user message content
    user_content = message.content
    if additional_context:
        user_content += additional_context
    
    # Build the message for Ollama
    user_message = {"role": "user", "content": user_content}
    if images and model_info.get("vision", False):
        user_message["images"] = images
    
    message_history.append(user_message)
    
    # Build messages for API
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.extend(message_history)
    
    # Stream response from Ollama
    response_message = cl.Message(content="")
    await response_message.send()
    
    # Start thinking animation
    animation_task = asyncio.create_task(
        send_animated_message(
            response_message,
            "Thinking...",
            ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"],
            0.2
        )
    )
    
    try:
        full_response = ""
        stream = await client.chat(model=model, messages=messages, stream=True)
        
        first_chunk = True
        async for chunk in stream:
            if first_chunk:
                # Stop animation on first token
                animation_task.cancel()
                try:
                    await animation_task
                except asyncio.CancelledError:
                    pass
                first_chunk = False
                # Clear thinking message
                response_message.content = ""
                await response_message.update()
            
            if "message" in chunk and "content" in chunk["message"]:
                content = chunk["message"]["content"]
                full_response += content
                await response_message.stream_token(content)
        
        # Ensure animation is cancelled if stream was empty or fast
        if not first_chunk:
             response_message.content = full_response
             await response_message.update()
        else:
             # If we never got a chunk, cancel animation and show empty or error
             animation_task.cancel()
             try:
                await animation_task
             except asyncio.CancelledError:
                pass
        
        # Add assistant response to history
        message_history.append({"role": "assistant", "content": full_response})
        cl.user_session.set("message_history", message_history)
        
    except Exception as e:
        animation_task.cancel() # Ensure animation stops on error
        error_msg = (
            f"❌ Error communicating with Ollama: {str(e)}\n\n"
            f"Make sure Ollama is running and the model **{model}** is available.\n"
            f"You can pull the model with: `ollama pull {model}`"
        )
        response_message.content = error_msg
        await response_message.update()


# Re-export the auth callback so Chainlit finds it
__all__ = ["header_auth_callback", "on_chat_start", "on_message", "on_chat_resume", "chat_profiles"]