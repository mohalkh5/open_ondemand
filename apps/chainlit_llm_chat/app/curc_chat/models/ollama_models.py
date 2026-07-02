import logging
import os
from typing import List, Dict, Any, Optional, Tuple

from ollama import AsyncClient

logger = logging.getLogger(__name__)

_CUSTOM_MODEL_PATHS_DOC = (
    "https://curc.readthedocs.io/en/latest/open_ondemand/llm_chat_interface.html"
)


def _ollama_models_path() -> str:
    return os.environ.get("OLLAMA_MODELS", "CURC LLM Models")


def _model_path_help(path: str, detail: Optional[str] = None) -> str:
    prefix = f"Error fetching models from {path}"
    if detail:
        prefix = f"{prefix}: {detail}"
    return (
        f"{prefix}. For more information on defining custom model paths, please see "
        f"{_CUSTOM_MODEL_PATHS_DOC}"
    )


def _no_models_error(path: str) -> str:
    return (
        f"No models found in {path}. For more information on defining custom model paths, "
        f"please see {_CUSTOM_MODEL_PATHS_DOC}"
    )


def single_available_model_name(
    models: Optional[List[Dict[str, Any]]],
) -> Optional[str]:
    """Return the model name when exactly one completion model is available."""
    if models and len(models) == 1:
        return models[0].get("name")
    return None


async def get_available_models(client: AsyncClient) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Return (models, error_message). error_message is set when listing fails or finds no models."""
    model_path = _ollama_models_path()
    try:
        response = await client.list()
        models = []

        for model_obj in response.models:
            name = model_obj.model

            model_info = await client.show(name)
            capabilities = model_info["capabilities"]

            details = getattr(model_obj, "details", None)
            description_parts = []
            if details:
                if details.parameter_size:
                    description_parts.append(f"Parameter size: {details.parameter_size}")
                if details.quantization_level:
                    description_parts.append(f"Quantization: {details.quantization_level}")

            description = "\n".join(description_parts) if description_parts else ""
            description += f"\nCapabilities: {', '.join(capabilities)}"

            if "completion" in capabilities:
                models.append(
                    {
                        "name": name,
                        "description": description,
                        "capabilities": capabilities,
                    }
                )

        if not models:
            logger.warning("No Ollama models found in %s", model_path)
            return [], _no_models_error(model_path)

        if len(models) == 1:
            logger.info(
                "Single completion model in %s: %s",
                model_path,
                models[0].get("name"),
            )

        return models, None

    except Exception as e:
        logger.warning("Error fetching models from %s: %s", model_path, e)
        return [], _model_path_help(model_path, str(e))


class ModelCache:
    """Cache for available models."""

    def __init__(self):
        self._models: Optional[List[Dict[str, Any]]] = None
        self._load_error: Optional[str] = None

    @property
    def models(self) -> Optional[List[Dict[str, Any]]]:
        return self._models

    @property
    def load_error(self) -> Optional[str]:
        return self._load_error

    async def refresh(self, client: AsyncClient) -> List[Dict[str, Any]]:
        self._models, self._load_error = await get_available_models(client)
        return self._models

    def get_model_info(self, model_name: str) -> Dict[str, Any]:
        if self._models:
            for model in self._models:
                if model["name"] == model_name:
                    return model

        return {
            "name": model_name,
            "description": "Unknown model",
            "capabilities": ["completion"],
        }


model_cache = ModelCache()
