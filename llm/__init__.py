"""LLM module - Unified interface for all LLM providers and services.

This module provides a clean, extensible abstraction for working with
multiple LLM providers (NVIDIA, ASTRA, OpenAI, Anthropic) and MCP services.

Quick Start:
    >>> from llm import LLMClient
    >>> 
    >>> llm = LLMClient()
    >>> 
    >>> # Make a call
    >>> response = await llm.call(
    ...     prompt="Generate chapter titles...",
    ...     use_case="chapter_title_generation"
    ... )
    >>> 
    >>> # Stream a response
    >>> async for chunk in llm.stream(
    ...     prompt="Create study material...",
    ...     use_case="study_material_generation"
    ... ):
    ...     print(chunk, end="")

Configuration:
    Create llm_config.yaml in the project root with providers and use_cases.
    See documentation for configuration format.

Adding Custom Providers:
    >>> from llm.providers import register_provider, LLMProvider
    >>> 
    >>> class MyProvider(LLMProvider):
    ...     async def call(self, messages, max_tokens, temperature, **kwargs):
    ...         # Your implementation
    ...         pass
    ...     
    ...     async def stream(self, messages, max_tokens, temperature, **kwargs):
    ...         # Your implementation
    ...         pass
    >>> 
    >>> register_provider("myprovider", MyProvider)
"""

from .client import LLMClient, create_client
from .config import load_config, get_use_case_config, get_provider_config
from .providers import (
    LLMProvider,
    register_provider,
    get_provider_class,
    PROVIDER_REGISTRY,
)

__version__ = "1.0.0"

__all__ = [
    # Main client
    "LLMClient",
    "create_client",
    
    # Configuration
    "load_config",
    "get_use_case_config",
    "get_provider_config",
    
    # Provider extensibility
    "LLMProvider",
    "register_provider",
    "get_provider_class",
    "PROVIDER_REGISTRY",
]

