"""Configuration loader for LLM module."""

import os
import yaml
from pathlib import Path
from typing import Dict, Any
from dotenv import load_dotenv

# Load environment variables once when module is imported
load_dotenv()

_CONFIG_CACHE = None


def load_config(config_path: str = None, force_reload: bool = False) -> Dict[str, Any]:
    """Load LLM configuration from YAML file.
    
    Args:
        config_path: Path to config file (defaults to llm_config.yaml in repo root)
        force_reload: Force reload config even if cached
        
    Returns:
        Configuration dictionary
        
    Raises:
        FileNotFoundError: If config file doesn't exist
        yaml.YAMLError: If config file is invalid YAML
    """
    global _CONFIG_CACHE
    
    # Return cached config if available
    if _CONFIG_CACHE is not None and not force_reload:
        return _CONFIG_CACHE
    
    # Determine config file path
    if config_path is None:
        # Default: llm_config.yaml in the same directory as this file's parent
        config_path = Path(__file__).parent.parent / "llm_config.yaml"
    else:
        config_path = Path(config_path)
    
    if not config_path.exists():
        raise FileNotFoundError(
            f"Config file not found: {config_path}\n"
            f"Create llm_config.yaml in the project root or specify config_path"
        )
    
    # Load YAML config
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    
    # Apply environment variable overrides
    config = _apply_env_overrides(config)
    
    # Validate config structure
    _validate_config(config)
    
    # Cache and return
    _CONFIG_CACHE = config
    return config


def _apply_env_overrides(config: Dict[str, Any]) -> Dict[str, Any]:
    """Apply environment variable overrides to config.
    
    Environment variables:
        LLM_DEFAULT_PROVIDER: Override default provider
        LLM_<USE_CASE>_PROVIDER: Override provider for specific use case
        
    Args:
        config: Base configuration
        
    Returns:
        Configuration with environment overrides applied
    """
    # Override default provider
    default_provider = os.getenv("LLM_DEFAULT_PROVIDER")
    if default_provider:
        if "defaults" not in config:
            config["defaults"] = {}
        config["defaults"]["provider"] = default_provider
    
    # Override providers for specific use cases
    if "use_cases" in config:
        for use_case_name, use_case_config in config["use_cases"].items():
            # Skip MCP services
            if use_case_config.get("type") == "mcp_service":
                continue
            
            # Check for environment override
            env_var = f"LLM_{use_case_name.upper()}_PROVIDER"
            override = os.getenv(env_var)
            if override:
                use_case_config["provider"] = override
    
    return config


def _validate_config(config: Dict[str, Any]):
    """Validate configuration structure.
    
    Args:
        config: Configuration to validate
        
    Raises:
        ValueError: If configuration is invalid
    """
    if "providers" not in config:
        raise ValueError("Config must have 'providers' section")
    
    if "use_cases" not in config:
        raise ValueError("Config must have 'use_cases' section")
    
    # Validate providers
    for provider_name, provider_config in config["providers"].items():
        if "type" not in provider_config:
            raise ValueError(f"Provider '{provider_name}' must have 'type' field")
        if "models" not in provider_config:
            raise ValueError(f"Provider '{provider_name}' must have 'models' section")
    
    # Validate use cases
    for use_case_name, use_case_config in config["use_cases"].items():
        use_case_type = use_case_config.get("type", "llm")
        
        if use_case_type == "llm":
            if "provider" not in use_case_config:
                raise ValueError(f"Use case '{use_case_name}' must have 'provider' field")
            # Check provider exists
            provider = use_case_config["provider"]
            if provider not in config["providers"]:
                raise ValueError(
                    f"Use case '{use_case_name}' references unknown provider '{provider}'"
                )
        elif use_case_type == "mcp_service":
            if "endpoint" not in use_case_config:
                raise ValueError(f"MCP use case '{use_case_name}' must have 'endpoint' field")
            if "tool_name" not in use_case_config:
                raise ValueError(f"MCP use case '{use_case_name}' must have 'tool_name' field")


def get_use_case_config(use_case_name: str) -> Dict[str, Any]:
    """Get configuration for a specific use case.
    
    Args:
        use_case_name: Name of the use case
        
    Returns:
        Use case configuration dictionary
        
    Raises:
        ValueError: If use case doesn't exist
    """
    config = load_config()
    
    if use_case_name not in config["use_cases"]:
        available = list(config["use_cases"].keys())
        raise ValueError(
            f"Unknown use case: '{use_case_name}'. "
            f"Available use cases: {available}"
        )
    
    return config["use_cases"][use_case_name]


def get_provider_config(provider_name: str) -> Dict[str, Any]:
    """Get configuration for a specific provider.
    
    Args:
        provider_name: Name of the provider
        
    Returns:
        Provider configuration dictionary
        
    Raises:
        ValueError: If provider doesn't exist
    """
    config = load_config()
    
    if provider_name not in config["providers"]:
        available = list(config["providers"].keys())
        raise ValueError(
            f"Unknown provider: '{provider_name}'. "
            f"Available providers: {available}"
        )
    
    return config["providers"][provider_name]

