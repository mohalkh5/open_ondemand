import logging
from typing import List, Dict, Any, Optional

from ollama import AsyncClient

logger = logging.getLogger(__name__)


async def get_available_models(client: AsyncClient) -> List[Dict[str, Any]]:
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
            return [
                _create_fallback_model(
                    "No models found", "Pull a model e.g. ollama pull llama3.2", ["completion"]
                )
            ]

        return models

    except Exception as e:
        logger.warning(f"Error fetching models from Ollama: {e}")
        return [
            _create_fallback_model(
                "No models found", "Pull a model e.g. ollama pull llama3.2", ["completion"]
            )
        ]


def _create_fallback_model(name: str, description: str, capabilities: List[str]) -> Dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "capabilities": capabilities,
    }


class ModelCache:
    """Cache for available models."""

    def __init__(self):
        self._models: Optional[List[Dict[str, Any]]] = None

    @property
    def models(self) -> Optional[List[Dict[str, Any]]]:
        return self._models

    async def refresh(self, client: AsyncClient) -> List[Dict[str, Any]]:
        self._models = await get_available_models(client)
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
