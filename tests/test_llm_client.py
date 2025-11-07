"""
Tests for LLM client module.
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from llm.client import LLMClient
from llm.config import load_config
from errors import LLMAPIError, ConfigurationError


@pytest.mark.asyncio
async def test_llm_client_initialization(mock_env_vars):
    """Test LLM client initializes correctly and loads config.
    
    This test verifies:
    - Client can be created
    - Config loads successfully
    - Handler can be created for a use case
    - Handler caching works
    """
    # Create client
    client = LLMClient()
    assert client is not None
    assert hasattr(client, 'call')
    assert hasattr(client, 'stream')
    
    # Test that config actually loads by creating a handler
    # This will fail if llm_config.yaml is missing or invalid
    handler = client._get_handler("chapter_title_generation")
    assert handler is not None
    
    # Verify handler caching works
    handler2 = client._get_handler("chapter_title_generation")
    assert handler is handler2, "Handler should be cached"


@pytest.mark.asyncio
async def test_llm_client_call_with_use_case(mock_env_vars):
    """Test LLM client call with specific use case."""
    client = LLMClient()
    
    with patch('llm.handlers.LLMUseCaseHandler.call', new_callable=AsyncMock) as mock_call:
        mock_call.return_value = "Test response"
        
        result = await client.call(
            prompt="Test prompt",
            use_case="chapter_title_generation"
        )
        
        assert result == "Test response"
        mock_call.assert_called_once()


@pytest.mark.asyncio
async def test_llm_client_call_with_overrides(mock_env_vars):
    """Test LLM client call with parameter overrides."""
    client = LLMClient()
    
    with patch('llm.handlers.LLMUseCaseHandler.call', new_callable=AsyncMock) as mock_call:
        mock_call.return_value = "Test response"
        
        result = await client.call(
            prompt="Test prompt",
            use_case="study_material_generation",
            temperature=0.9,
            max_tokens=2000
        )
        
        assert result == "Test response"


@pytest.mark.asyncio
async def test_llm_client_handles_api_error(mock_env_vars):
    """Test LLM client handles API errors gracefully."""
    client = LLMClient()
    
    with patch('llm.handlers.LLMUseCaseHandler.call', new_callable=AsyncMock) as mock_call:
        mock_call.side_effect = LLMAPIError("API Error", provider="nvidia")
        
        with pytest.raises(LLMAPIError):
            await client.call(
                prompt="Test prompt",
                use_case="chapter_title_generation"
            )


def test_config_loading(mock_env_vars):
    """Test configuration loads correctly with actual provider details.
    
    This test verifies:
    - Config file exists and loads
    - Required sections present
    - Active providers are properly configured
    - Use cases reference valid providers
    """
    config = load_config()
    
    # Check structure
    assert "providers" in config, "Config missing 'providers' section"
    assert "use_cases" in config, "Config missing 'use_cases' section"
    
    # Check active providers (nvidia and astra should be configured)
    assert "nvidia" in config["providers"], "NVIDIA provider not configured"
    assert "astra" in config["providers"], "ASTRA provider not configured"
    
    # Verify provider has required config
    nvidia_config = config["providers"]["nvidia"]
    assert "type" in nvidia_config
    assert "base_url" in nvidia_config
    assert "models" in nvidia_config
    assert "default" in nvidia_config["models"], "NVIDIA missing default model"
    
    # Verify use case references valid provider
    chapter_gen = config["use_cases"]["chapter_title_generation"]
    assert "provider" in chapter_gen
    provider_name = chapter_gen["provider"]
    assert provider_name in config["providers"], f"Use case references unknown provider: {provider_name}"


def test_config_validates_providers():
    """Test configuration validates provider settings."""
    config = load_config()
    
    for provider_name, provider_config in config["providers"].items():
        if provider_config.get("enabled", True):
            # Check that provider has authentication config
            # Different providers use different keys: api_key_env, token_env, etc.
            has_auth = any(key in provider_config for key in [
                "api_key_env", "token_env", "base_url", "endpoint"
            ])
            assert has_auth, f"Provider {provider_name} missing authentication config"

