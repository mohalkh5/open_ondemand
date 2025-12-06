import os
import chainlit as cl
from ollama import AsyncClient
import json
from pathlib import Path
from datetime import datetime

ollama_host = os.getenv("OLLAMA_HOST")
user = os.getenv("USER")

# Initialize Ollama client
client = AsyncClient(host=f"http://{ollama_host}")

# Directory for saved chats
CHATS_DIR = Path(f"/projects/{user}/chainlit_saved_chats")
CHATS_DIR.mkdir(exist_ok=True)

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
    cl.user_session.set("chat_name", None)
    
    await cl.Message(content="💬 Ready to chat!\n\nCommands:\n- `/save` - Save current chat\n- `/load` - Load a saved chat\n- `/new` - Start new chat").send()

@cl.action_callback("save_chat")
async def save_chat(action):
    """Save current chat (action callback)"""
    await save_chat_command()

async def save_chat_command():
    """Save current chat"""
    history = cl.user_session.get("history")
    
    if not history:
        await cl.Message(content="No chat history to save.").send()
        return
    
    # Ask for chat name
    res = await cl.AskUserMessage(content="Enter a name for this chat:", timeout=30).send()
    
    if res:
        chat_name = res['output'].strip()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{chat_name}.json"
        filepath = CHATS_DIR / filename
        
        # Save chat
        chat_data = {
            "name": chat_name,
            "timestamp": timestamp,
            "settings": cl.user_session.get("settings"),
            "history": history
        }
        
        with open(filepath, 'w') as f:
            json.dump(chat_data, f, indent=2)
        
        cl.user_session.set("chat_name", chat_name)
        await cl.Message(content=f"✅ Chat saved as: {chat_name}").send()

@cl.action_callback("load_chat")
async def load_chat(action):
    """Load a saved chat (action callback)"""
    await load_chat_command()

async def load_chat_command():
    """Load a saved chat"""
    # Get list of saved chats
    saved_chats = list(CHATS_DIR.glob("*.json"))
    
    if not saved_chats:
        await cl.Message(content="No saved chats found.").send()
        return
    
    # Create selection list
    chat_names = [f.stem for f in saved_chats]
    
    res = await cl.AskUserMessage(
        content=f"Available chats:\n" + "\n".join(f"- {name}" for name in chat_names) + "\n\nEnter chat name to load:",
        timeout=60
    ).send()
    
    if res:
        selected = res['output'].strip()
        # Find matching file
        matching = [f for f in saved_chats if selected in f.stem]
        
        if matching:
            filepath = matching[0]
            with open(filepath, 'r') as f:
                chat_data = json.load(f)
            
            # Restore chat
            cl.user_session.set("history", chat_data["history"])
            cl.user_session.set("chat_name", chat_data["name"])
            
            # Display chat history
            for msg in chat_data["history"]:
                role = "User" if msg["role"] == "user" else "Assistant"
                await cl.Message(content=msg["content"], author=role).send()
            
            await cl.Message(content=f"✅ Loaded chat: {chat_data['name']}").send()
        else:
            await cl.Message(content="❌ Chat not found.").send()

@cl.action_callback("new_chat")
async def new_chat(action):
    """Start a new chat (action callback)"""
    await new_chat_command()

async def new_chat_command():
    """Start a new chat"""
    cl.user_session.set("history", [])
    cl.user_session.set("chat_name", None)
    await cl.Message(content="🆕 Started new chat!").send()

@cl.on_settings_update
async def update_settings(settings):
    """Handle settings changes"""
    cl.user_session.set("settings", settings)

@cl.on_message
async def main(message: cl.Message):
    """Handle incoming messages"""
    settings = cl.user_session.get("settings")
    history = cl.user_session.get("history")
    
    # Handle commands
    if message.content.startswith("/save"):
        await save_chat_command()
        return
    elif message.content.startswith("/load"):
        await load_chat_command()
        return
    elif message.content.startswith("/new"):
        await new_chat_command()
        return
    
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
