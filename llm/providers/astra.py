"""NVIDIA ASTRA deployment provider."""

import os
import aiohttp
from typing import AsyncIterator, List, Dict
from .base import LLMProvider


class AstraProvider(LLMProvider):
    """Provider for NVIDIA ASTRA custom deployment endpoint."""
    
    def __init__(self, config: dict):
        """Initialize ASTRA provider.
        
        Args:
            config: Provider configuration with endpoint, deployment_id, token_env
        """
        super().__init__(config)
        
        # Format endpoint URL with deployment ID
        deployment_id = config.get("deployment_id", "")
        self.endpoint = config["endpoint"].format(deployment_id=deployment_id)
        
        # Get authentication token
        token = os.getenv(config.get("token_env", "ASTRA_TOKEN"))
        if not token:
            raise ValueError(f"ASTRA token not found in environment: {config.get('token_env')}")
        
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    
    async def call(
        self, 
        messages: List[Dict[str, str]], 
        max_tokens: int, 
        temperature: float, 
        **kwargs
    ) -> str:
        """Make completion call to ASTRA deployment."""
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.endpoint,
                    headers=self.headers,
                    json=payload
                ) as resp:
                    resp.raise_for_status()
                    data = await resp.json()
                    return data["choices"][0]["message"]["content"]
        except aiohttp.ClientError as e:
            raise RuntimeError(f"ASTRA API call failed: {str(e)}") from e
        except (KeyError, IndexError) as e:
            raise RuntimeError(f"ASTRA API response parsing failed: {str(e)}") from e
    
    async def stream(
        self, 
        messages: List[Dict[str, str]], 
        max_tokens: int, 
        temperature: float, 
        **kwargs
    ) -> AsyncIterator[str]:
        """Stream completion chunks from ASTRA.
        
        Note: ASTRA may not support streaming. Falls back to non-streaming.
        """
        # ASTRA doesn't support streaming in the current implementation
        # Fall back to complete response
        result = await self.call(messages, max_tokens, temperature, **kwargs)
        yield result

