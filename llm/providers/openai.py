"""OpenAI provider."""

from typing import AsyncIterator, List, Dict
from openai import AsyncOpenAI
from .base import LLMProvider
from vault import get_secret


class OpenAIProvider(LLMProvider):
    """Provider for OpenAI's API."""
    
    def __init__(self, config: dict):
        """Initialize OpenAI provider.
        
        Args:
            config: Provider configuration with api_key_env, models
        """
        super().__init__(config)
        
        # Get API key (automatic Vault/env fallback)
        api_key_name = config.get("api_key_env", "OPENAI_API_KEY")
        api_key = get_secret(api_key_name, required=False)
        
        if not api_key:
            raise ValueError(f"API key not found in Vault or environment: {api_key_name}")
        
        self.client = AsyncOpenAI(api_key=api_key)
    
    async def call(
        self, 
        messages: List[Dict[str, str]], 
        max_tokens: int, 
        temperature: float, 
        **kwargs
    ) -> str:
        """Make completion call to OpenAI API."""
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
            raise RuntimeError(f"OpenAI API call failed: {str(e)}") from e
    
    async def stream(
        self, 
        messages: List[Dict[str, str]], 
        max_tokens: int, 
        temperature: float, 
        **kwargs
    ) -> AsyncIterator[str]:
        """Stream completion chunks from OpenAI API."""
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
            raise RuntimeError(f"OpenAI API streaming failed: {str(e)}") from e

