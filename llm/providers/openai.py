"""OpenAI provider."""

import os
import warnings
from typing import AsyncIterator, List, Dict
from openai import AsyncOpenAI
from .base import LLMProvider

# Try to import Vault integration
try:
    from vault import get_secrets_config
    VAULT_AVAILABLE = True
except ImportError:
    VAULT_AVAILABLE = False


class OpenAIProvider(LLMProvider):
    """Provider for OpenAI's API."""
    
    def __init__(self, config: dict):
        """Initialize OpenAI provider.
        
        Args:
            config: Provider configuration with api_key_env, models
        """
        super().__init__(config)
        
        # Try Vault first, then fallback to environment
        api_key = None
        api_key_name = config.get("api_key_env", "OPENAI_API_KEY")
        
        if VAULT_AVAILABLE:
            try:
                secrets = get_secrets_config()
                api_key = secrets.get(api_key_name)
            except Exception as e:
                warnings.warn(
                    f"⚠️  Failed to load {api_key_name} from Vault ({e}). "
                    f"Falling back to environment variable.",
                    RuntimeWarning
                )
        
        # Fallback to environment variable
        if not api_key:
            api_key = os.getenv(api_key_name)
            if api_key:
                warnings.warn(
                    f"⚠️  Using {api_key_name} from environment variable instead of Vault. "
                    f"Consider migrating to Vault: python scripts/vault/migrate_secrets_to_vault.py",
                    RuntimeWarning
                )
        
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

