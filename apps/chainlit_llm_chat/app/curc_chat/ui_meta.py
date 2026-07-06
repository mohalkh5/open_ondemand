"""Small JSON endpoint for CURC frontend UI hints (custom.js)."""

from chainlit.server import app
from fastapi.responses import JSONResponse
from ollama import AsyncClient

from curc_chat.models import model_cache
from curc_chat.settings import get_ollama_host

_client = AsyncClient(host=f"http://{get_ollama_host()}")


@app.get("/curc/ui-meta")
async def curc_ui_meta():
    """Expose model list for the welcome-screen active model hint."""
    if not model_cache.models:
        await model_cache.refresh(_client)

    models = model_cache.models or []
    names = [m["name"] for m in models if m.get("name")]
    return JSONResponse(
        {
            "models": names,
            "defaultModel": names[0] if names else None,
            "modelCount": len(names),
        }
    )
