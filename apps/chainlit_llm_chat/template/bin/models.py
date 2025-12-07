"""
Model Management Module for Chainlit Ollama Chat

Handles model discovery, capability detection, and caching.
Extracts model-related logic from the main app for better separation of concerns.
"""

import logging
from typing import List, Dict, Any, Optional
from ollama import AsyncClient

logger = logging.getLogger(__name__)

# Fallback patterns for vision-capable models (used when API detection fails)
VISION_MODEL_PATTERNS = ["vision", "llava", "minicpm-v", "bakllava", "gemma3"]

def is_vision_model(model_name: str) -> bool:
    """
    Check if a model is vision-capable based on its name.
    
    This is a fallback when API-based detection fails.
    """
    name_lower = model_name.lower()
    return any(pattern in name_lower for pattern in VISION_MODEL_PATTERNS)

async def check_vision_capability(client: AsyncClient, model_name: str) -> bool:
    """
    Check if a model has vision capability by inspecting its modelinfo.
    
    Args:
        client: Ollama AsyncClient instance
        model_name: Name of the model to check
        
    Returns:
        True if model has vision capability, False otherwise
    """
    try:
        model_info = await client.show(model_name)
        if hasattr(model_info, 'modelinfo') and model_info.modelinfo:
            # Check if any key contains '.vision.' indicating vision capability
            return any('.vision.' in key for key in model_info.modelinfo.keys())
    except Exception:
        pass
    
    # Fall back to name-based detection
    return is_vision_model(model_name)


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
            display_name = name.split(":")[0]  # Remove tag suffix
            
            # Extract technical details
            details = getattr(model_obj, 'details', None)
            description_parts = []
            if details:
                if details.parameter_size:
                    description_parts.append(f"{details.parameter_size} Params")
                if details.quantization_level:
                    description_parts.append(details.quantization_level)
            
            description = " • ".join(description_parts) if description_parts else ""

            # Check vision capability
            has_vision = await check_vision_capability(client, name)

            models.append({
                "name": name,
                "display_name": display_name.replace("-", " ").replace("_", " ").title(),
                "description": description,
                "vision": has_vision,
            })
        
        if not models:
            return [_create_fallback_model("No models found", "Pull a model with: ollama pull llama3.2", "⚠️")]
            
        return models
        
    except Exception as e:
        logger.warning(f"Error fetching models from Ollama: {e}")
        return [_create_fallback_model("Llama 3.2 (default)", "Ollama not reachable - using default", "🦙")]


def _create_fallback_model(display_name: str, description: str, icon: str) -> Dict[str, Any]:
    """Create a fallback model entry when Ollama is not available."""
    return {
        "name": "llama3.2",
        "display_name": display_name,
        "description": description,
        "icon": icon,
        "vision": False,
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
            "display_name": model_name,
            "vision": is_vision_model(model_name)
        }


# Global model cache instance
model_cache = ModelCache()
