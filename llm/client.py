"""Main LLM client interface."""

from typing import AsyncIterator, Dict, Any, Optional
from .factory import create_handler


class LLMClient:
    """Unified client for all LLM operations.
    
    This is the main entry point for making LLM calls. It provides a simple,
    consistent interface regardless of the underlying provider or service type.
    
    Example:
        >>> llm = LLMClient()
        >>> response = await llm.call(
        ...     prompt="Generate chapter titles...",
        ...     use_case="chapter_title_generation"
        ... )
        >>> print(response)
    """
    
    def __init__(self):
        """Initialize LLM client."""
        self._handlers = {}  # Cache for handler instances
    
    def _get_handler(self, use_case: str):
        """Get or create handler for a use case.
        
        Handlers are cached to avoid recreating provider instances.
        
        Args:
            use_case: Name of the use case
            
        Returns:
            Handler instance
        """
        if use_case not in self._handlers:
            self._handlers[use_case] = create_handler(use_case)
        return self._handlers[use_case]
    
    async def call(
        self,
        prompt: str,
        use_case: str,
        **kwargs
    ) -> str:
        """Make a completion call and return the complete response.
        
        This works for both LLM providers and MCP services - the interface
        is the same regardless of the backend.
        
        Args:
            prompt: The input prompt/query
            use_case: Name of the use case from config
            **kwargs: Additional parameters:
                - max_tokens: Override max tokens
                - temperature: Override temperature
                - system_prompt: Override system prompt (LLM only)
                - Any other provider-specific parameters
        
        Returns:
            Complete response string
            
        Example:
            >>> response = await llm.call(
            ...     prompt="Explain photosynthesis",
            ...     use_case="study_material_generation",
            ...     max_tokens=10000
            ... )
        """
        handler = self._get_handler(use_case)
        return await handler.call(prompt, **kwargs)
    
    async def stream(
        self,
        prompt: str,
        use_case: str,
        **kwargs
    ) -> AsyncIterator[str]:
        """Stream response chunks as they arrive.
        
        Useful for long-form content where you want to display results
        incrementally (e.g., study material generation, chat).
        
        Args:
            prompt: The input prompt/query
            use_case: Name of the use case from config
            **kwargs: Additional parameters (same as call())
            
        Yields:
            Response chunks as strings
            
        Example:
            >>> async for chunk in llm.stream(
            ...     prompt="Create study material...",
            ...     use_case="study_material_generation"
            ... ):
            ...     print(chunk, end="", flush=True)
        """
        handler = self._get_handler(use_case)
        async for chunk in handler.stream(prompt, **kwargs):
            yield chunk
    
    def get_use_case_info(self, use_case: str) -> Dict[str, Any]:
        """Get metadata about a use case.
        
        Useful for debugging, logging, or displaying provider information.
        
        Args:
            use_case: Name of the use case
            
        Returns:
            Dictionary with metadata (provider, model, type, etc.)
            
        Example:
            >>> info = llm.get_use_case_info("chapter_title_generation")
            >>> print(f"Using {info['provider']} with model {info['model']}")
        """
        handler = self._get_handler(use_case)
        return handler.get_metadata()
    
    def clear_cache(self):
        """Clear the handler cache.
        
        Useful if you've updated configuration and want to force
        recreation of handlers.
        """
        self._handlers.clear()


# Convenience function for simple synchronous-style usage
def create_client() -> LLMClient:
    """Create a new LLM client instance.
    
    Returns:
        LLMClient instance
    """
    return LLMClient()

