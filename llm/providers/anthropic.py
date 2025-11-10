"""Anthropic Claude provider."""

import os
import warnings
from typing import AsyncIterator, List, Dict
from .base import LLMProvider

try:
    from anthropic import AsyncAnthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

# Try to import Vault integration
try:
    from vault import get_secrets_config
    VAULT_AVAILABLE = True
except ImportError:
    VAULT_AVAILABLE = False


class AnthropicProvider(LLMProvider):
    """Provider for Anthropic's Claude API."""
    
    def __init__(self, config: dict):
        """Initialize Anthropic provider.
        
        Args:
            config: Provider configuration with api_key_env, models
        """
        if not ANTHROPIC_AVAILABLE:
            raise ImportError(
                "Anthropic library not installed. Install with: pip install anthropic"
            )
        
        super().__init__(config)
        
        # Try Vault first, then fallback to environment
        api_key = None
        api_key_name = config.get("api_key_env", "ANTHROPIC_API_KEY")
        
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
        
        self.client = AsyncAnthropic(api_key=api_key)
    
    async def call(
        self, 
        messages: List[Dict[str, str]], 
        max_tokens: int, 
        temperature: float, 
        **kwargs
    ) -> str:
        """Make completion call to Anthropic API."""
        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=messages
            )
            return response.content[0].text
        except Exception as e:
            raise RuntimeError(f"Anthropic API call failed: {str(e)}") from e
    
    async def stream(
        self, 
        messages: List[Dict[str, str]], 
        max_tokens: int, 
        temperature: float, 
        **kwargs
    ) -> AsyncIterator[str]:
        """Stream completion chunks from Anthropic API."""
        try:
            async with self.client.messages.stream(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=messages
            ) as stream:
                async for text in stream.text_stream:
                    yield text
        except Exception as e:
            raise RuntimeError(f"Anthropic API streaming failed: {str(e)}") from e

