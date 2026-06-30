import logging
from typing import List, Dict, Any, Optional, Tuple

from ollama import AsyncClient

logger = logging.getLogger(__name__)

_MODEL_FETCH_ERROR = "Error fetching models."


async def get_available_models(client: AsyncClient) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Return (models, error_message). error_message is set when listing fails or finds no models."""
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
            logger.warning("No Ollama models found")
            return [], _MODEL_FETCH_ERROR

        return models, None

    except Exception as e:
        logger.warning("Error fetching models from Ollama: %s", e)
        return [], _MODEL_FETCH_ERROR


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
