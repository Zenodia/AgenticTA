"""NVIDIA API provider (OpenAI-compatible endpoint)."""

from typing import AsyncIterator, List, Dict
from openai import AsyncOpenAI
from .base import LLMProvider
from vault import get_secrets_config


class NvidiaProvider(LLMProvider):
    """Provider for NVIDIA's OpenAI-compatible API at integrate.api.nvidia.com."""
    
    def __init__(self, config: dict):
        """Initialize NVIDIA provider.
        
        Args:
            config: Provider configuration with base_url, api_key_env, models
        """
        super().__init__(config)
        
        # Get API key from Vault (falls back to environment if Vault unavailable)
        secrets = get_secrets_config()
        api_key = secrets.get('NVIDIA_API_KEY')
        if not api_key:
            raise ValueError("NVIDIA_API_KEY not found in Vault or environment")
        
        self.client = AsyncOpenAI(
            base_url=config["base_url"],
            api_key=api_key
        )
    
    async def call(
        self, 
        messages: List[Dict[str, str]], 
        max_tokens: int, 
        temperature: float, 
        **kwargs
    ) -> str:
        """Make completion call to NVIDIA API."""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=False
            )
            return response.choices[0].message.content
        except Exception as e:
            raise RuntimeError(f"NVIDIA API call failed: {str(e)}") from e
    
    async def stream(
        self, 
        messages: List[Dict[str, str]], 
        max_tokens: int, 
        temperature: float, 
        **kwargs
    ) -> AsyncIterator[str]:
        """Stream completion chunks from NVIDIA API."""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=True
            )
            async for chunk in response:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            raise RuntimeError(f"NVIDIA API streaming failed: {str(e)}") from e

