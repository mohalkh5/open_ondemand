import os
import chainlit as cl
from ollama import AsyncClient

ollama_host = os.getenv("OLLAMA_HOST")
# Initialize Ollama client
client = AsyncClient(host=f"http://{ollama_host}")

@cl.on_chat_start
async def start():
    """Initialize chat with model selection"""
    # Get available models
    models_response = await client.list()
    models = [m.model for m in models_response.models]
    
    # Let user select model
    settings = await cl.ChatSettings([
        cl.input_widget.Select(
            id="model",
            label="Model",
            values=models,
            initial_value=models[0] if models else "llama2"
        ),
        cl.input_widget.Slider(
            id="temperature",
            label="Temperature",
            initial=0.7,
            min=0,
            max=2,
            step=0.1
        )
    ]).send()
    
    cl.user_session.set("settings", settings)
    cl.user_session.set("history", [])

@cl.on_settings_update
async def update_settings(settings):
    """Handle settings changes"""
    cl.user_session.set("settings", settings)

@cl.on_message
async def main(message: cl.Message):
    """Handle incoming messages"""
    settings = cl.user_session.get("settings")
    history = cl.user_session.get("history")
    
    # Add user message to history
    history.append({"role": "user", "content": message.content})
    
    # Create response message
    msg = cl.Message(content="")
    await msg.send()
    
    # Stream response from Ollama
    stream = await client.chat(
        model=settings.get("model", "llama2"),
        messages=history,
        stream=True,
        options={
            "temperature": settings.get("temperature", 0.7)
        }
    )
    
    full_response = ""
    async for chunk in stream:
        if chunk['message']['content']:
            full_response += chunk['message']['content']
            await msg.stream_token(chunk['message']['content'])
    
    # Add assistant response to history
    history.append({"role": "assistant", "content": full_response})
    cl.user_session.set("history", history)
    
    await msg.update()
