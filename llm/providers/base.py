"""Base abstract class for all LLM providers."""

from abc import ABC, abstractmethod
from typing import AsyncIterator, Dict, Any, List


class LLMProvider(ABC):
    """Abstract base class for all LLM providers.
    
    Each provider implementation must handle its own API-specific logic
    for making completion calls and streaming responses.
    """
    
    def __init__(self, config: dict):
        """Initialize provider with configuration.
        
        Args:
            config: Provider configuration dictionary from YAML
        """
        self.config = config
        self.model = config.get("models", {}).get("default", "")
    
    @abstractmethod
    async def call(
        self, 
        messages: List[Dict[str, str]], 
        max_tokens: int, 
        temperature: float, 
        **kwargs
    ) -> str:
        """Make a completion call and return the complete response.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            **kwargs: Additional provider-specific parameters
            
        Returns:
            Complete response string
        """
        pass
    
    @abstractmethod
    async def stream(
        self, 
        messages: List[Dict[str, str]], 
        max_tokens: int, 
        temperature: float, 
        **kwargs
    ) -> AsyncIterator[str]:
        """Stream completion chunks as they arrive.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            **kwargs: Additional provider-specific parameters
            
        Yields:
            Response chunks as strings
        """
        pass
    
    def get_metadata(self) -> Dict[str, Any]:
        """Return provider metadata for logging/debugging.
        
        Returns:
            Dictionary with provider name, model, config info
        """
        return {
            "provider": self.__class__.__name__,
            "model": self.model,
            "config": self.config
        }

