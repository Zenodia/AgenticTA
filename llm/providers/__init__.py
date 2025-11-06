"""Provider registry for LLM providers."""

from typing import Dict, Type
from .base import LLMProvider
from .nvidia import NvidiaProvider
from .astra import AstraProvider

# Optional providers (commented out for now)
# from .openai import OpenAIProvider
# from .anthropic import AnthropicProvider

# Provider registry - maps provider type to provider class
# Only register NVIDIA and ASTRA for now
PROVIDER_REGISTRY: Dict[str, Type[LLMProvider]] = {
    "nvidia": NvidiaProvider,
    "astra": AstraProvider,
    # "openai": OpenAIProvider,      # Uncomment when needed
    # "anthropic": AnthropicProvider, # Uncomment when needed
}


def register_provider(name: str, provider_class: Type[LLMProvider]):
    """Register a custom provider.
    
    Args:
        name: Provider name (used in config)
        provider_class: Provider class (must inherit from LLMProvider)
    """
    if not issubclass(provider_class, LLMProvider):
        raise TypeError(f"{provider_class} must inherit from LLMProvider")
    PROVIDER_REGISTRY[name] = provider_class


def get_provider_class(provider_type: str) -> Type[LLMProvider]:
    """Get provider class by type.
    
    Args:
        provider_type: Provider type string from config
        
    Returns:
        Provider class
        
    Raises:
        ValueError: If provider type is unknown
    """
    if provider_type not in PROVIDER_REGISTRY:
        available = list(PROVIDER_REGISTRY.keys())
        raise ValueError(
            f"Unknown provider type: '{provider_type}'. "
            f"Available providers: {available}"
        )
    return PROVIDER_REGISTRY[provider_type]


__all__ = [
    "LLMProvider",
    "NvidiaProvider",
    "AstraProvider",
    # "OpenAIProvider",      # Available but not exported yet
    # "AnthropicProvider",   # Available but not exported yet
    "PROVIDER_REGISTRY",
    "register_provider",
    "get_provider_class",
]

