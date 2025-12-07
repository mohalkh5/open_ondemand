"""
Model Management Module for Chainlit Ollama Chat

Handles model discovery, capability detection, and caching.
Extracts model-related logic from the main app for better separation of concerns.
"""

import logging
from typing import List, Dict, Any, Optional
from ollama import AsyncClient

logger = logging.getLogger(__name__)


async def get_available_models(client: AsyncClient) -> List[Dict[str, Any]]:
    """
    Fetch available models from Ollama with capability detection.
    
    Args:
        client: Ollama AsyncClient instance
        
    Returns:
        List of model info dictionaries with name, display_name, description,
        icon, and vision capability flag.
    """
    try:
        response = await client.list()
        models = []
        
        for model_obj in response.models:
            name = model_obj.model

            # Get capabilities from client
            model_info = await client.show(name)
            capabilities = model_info['capabilities']
            
            # Extract technical details
            details = getattr(model_obj, 'details', None)
            description_parts = []
            if details:
                if details.parameter_size:
                    description_parts.append(f"Parameter size: {details.parameter_size}")
                if details.quantization_level:
                    description_parts.append(f"Quantization: {details.quantization_level}")
            
            description = "\n".join(description_parts) if description_parts else ""
            description += f"\nCapabilities: {', '.join(capabilities)}"

            if "completion" in capabilities:
                models.append({
                    "name": name,
                    "description": description,
                    "capabilities": capabilities,
                })
        
        if not models:
            return [_create_fallback_model("No models found", "Pull a model e.g. ollama pull llama3.2", ["completion"])]
            
        return models
        
    except Exception as e:
        logger.warning(f"Error fetching models from Ollama: {e}")
        return [_create_fallback_model("No models found", "Pull a model e.g. ollama pull llama3.2", ["completion"])]


def _create_fallback_model(name: str, description: str, capabilities: List[str]) -> Dict[str, Any]:
    """Create a fallback model entry when Ollama is not available."""
    return {
        "name": name,
        "description": description,
        "capabilities": capabilities,
    }


class ModelCache:
    """Thread-safe cache for available models."""
    
    def __init__(self):
        self._models: Optional[List[Dict[str, Any]]] = None
    
    @property
    def models(self) -> Optional[List[Dict[str, Any]]]:
        return self._models
    
    async def refresh(self, client: AsyncClient) -> List[Dict[str, Any]]:
        """Refresh the model cache from Ollama."""
        self._models = await get_available_models(client)
        return self._models
    
    def get_model_info(self, model_name: str) -> Dict[str, Any]:
        """Get model info by name, with fallback for unknown models."""
        if self._models:
            for model in self._models:
                if model["name"] == model_name:
                    return model
        
        # Fallback for unknown models
        return {
            "name": model_name,
            "description": "Unknown model",
            "capabilities": ["completion"]
        }


# Global model cache instance
model_cache = ModelCache()
