"""Use case handlers for LLM and MCP services."""

from typing import AsyncIterator, Dict, Any, List
from .providers import get_provider_class
from .providers.base import LLMProvider


class LLMUseCaseHandler:
    """Handler for LLM-based use cases."""
    
    def __init__(self, use_case_config: dict, provider_config: dict):
        """Initialize LLM use case handler.
        
        Args:
            use_case_config: Use case configuration from YAML
            provider_config: Provider configuration from YAML
        """
        self.use_case_config = use_case_config
        self.provider_config = provider_config
        
        # Get provider type and instantiate provider class
        provider_type = use_case_config.get("provider")
        ProviderClass = get_provider_class(provider_type)
        
        # Create provider instance
        self.provider: LLMProvider = ProviderClass(provider_config)
        
        # Resolve model override if specified in use case
        if "model" in use_case_config:
            model_key = use_case_config["model"]
            # Look up model name from provider's models dict
            self.provider.model = provider_config["models"].get(
                model_key, 
                model_key  # Fallback to literal model name if not in dict
            )
    
    async def call(self, prompt: str, **kwargs) -> str:
        """Make LLM call.
        
        Args:
            prompt: User prompt string
            **kwargs: Additional parameters (max_tokens, temperature, system_prompt, etc.)
            
        Returns:
            Complete response string
        """
        # Format messages
        messages = self._format_messages(prompt, kwargs.get("system_prompt"))
        
        # Get parameters from config with runtime overrides
        max_tokens = kwargs.get("max_tokens", self.use_case_config.get("max_tokens", 4096))
        temperature = kwargs.get("temperature", self.use_case_config.get("temperature", 0.7))
        
        # Make call via provider (polymorphic!)
        return await self.provider.call(messages, max_tokens, temperature, **kwargs)
    
    async def stream(self, prompt: str, **kwargs) -> AsyncIterator[str]:
        """Stream LLM response.
        
        Args:
            prompt: User prompt string
            **kwargs: Additional parameters
            
        Yields:
            Response chunks as strings
        """
        # Format messages
        messages = self._format_messages(prompt, kwargs.get("system_prompt"))
        
        # Get parameters from config with runtime overrides
        max_tokens = kwargs.get("max_tokens", self.use_case_config.get("max_tokens", 4096))
        temperature = kwargs.get("temperature", self.use_case_config.get("temperature", 0.7))
        
        # Stream via provider (polymorphic!)
        async for chunk in self.provider.stream(messages, max_tokens, temperature, **kwargs):
            yield chunk
    
    def _format_messages(self, prompt: str, system_prompt: str = None) -> List[Dict[str, str]]:
        """Convert prompt to messages format.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt override
            
        Returns:
            List of message dicts
        """
        messages = []
        
        # Use system_prompt from config if not overridden
        if system_prompt is None:
            system_prompt = self.use_case_config.get("system_prompt")
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        return messages
    
    def get_metadata(self) -> Dict[str, Any]:
        """Return handler metadata."""
        return {
            "type": "llm",
            "use_case": self.use_case_config.get("description", ""),
            **self.provider.get_metadata()
        }


class MCPUseCaseHandler:
    """Handler for MCP (Model Context Protocol) service use cases."""
    
    def __init__(self, use_case_config: dict):
        """Initialize MCP use case handler.
        
        Args:
            use_case_config: Use case configuration from YAML
        """
        self.config = use_case_config
        self.endpoint = use_case_config["endpoint"]
        self.tool_name = use_case_config.get("tool_name")
        self.timeout = use_case_config.get("timeout", 30)
    
    async def call(self, prompt: str = None, **kwargs) -> str:
        """Call MCP service.
        
        Args:
            prompt: Optional prompt (converted to 'query' parameter)
            **kwargs: Additional parameters passed to MCP tool
            
        Returns:
            Complete response string
        """
        try:
            from fastmcp import Client
            from fastmcp.client.transports import StreamableHttpTransport
        except ImportError:
            raise ImportError(
                "fastmcp library not installed. Install with: pip install fastmcp"
            )
        
        # Add prompt as query if provided
        if prompt:
            kwargs["query"] = prompt
        
        async with Client(transport=StreamableHttpTransport(self.endpoint)) as client:
            result = await client.call_tool(self.tool_name, kwargs)
            try:
                return result.content[0].text
            except (AttributeError, IndexError):
                return str(result)
    
    async def stream(self, prompt: str = None, **kwargs) -> AsyncIterator[str]:
        """Stream MCP service response.
        
        Note: Most MCP services don't support streaming yet.
        Falls back to complete response.
        
        Args:
            prompt: Optional prompt
            **kwargs: Additional parameters
            
        Yields:
            Response chunks (typically just one chunk with complete response)
        """
        result = await self.call(prompt, **kwargs)
        yield result
    
    def get_metadata(self) -> Dict[str, Any]:
        """Return handler metadata."""
        return {
            "type": "mcp_service",
            "endpoint": self.endpoint,
            "tool_name": self.tool_name,
            "description": self.config.get("description", "")
        }

