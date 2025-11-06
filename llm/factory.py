"""Factory for creating use case handlers."""

from typing import Union
from .handlers import LLMUseCaseHandler, MCPUseCaseHandler
from .config import load_config


def create_handler(use_case_name: str) -> Union[LLMUseCaseHandler, MCPUseCaseHandler]:
    """Create the appropriate handler for a use case.
    
    This factory function:
    1. Loads configuration
    2. Looks up the use case
    3. Determines the type (llm vs mcp_service)
    4. Creates and returns the appropriate handler
    
    Args:
        use_case_name: Name of the use case from config
        
    Returns:
        Handler instance (LLMUseCaseHandler or MCPUseCaseHandler)
        
    Raises:
        ValueError: If use case doesn't exist or has invalid configuration
    """
    config = load_config()
    
    # Look up use case configuration
    if use_case_name not in config["use_cases"]:
        available = list(config["use_cases"].keys())
        raise ValueError(
            f"Unknown use case: '{use_case_name}'. "
            f"Available use cases: {available}"
        )
    
    use_case_config = config["use_cases"][use_case_name]
    
    # Determine use case type (default to 'llm' if not specified)
    use_case_type = use_case_config.get("type", "llm")
    
    # Create appropriate handler
    if use_case_type == "llm":
        # Get provider configuration
        provider_name = use_case_config["provider"]
        
        if provider_name not in config["providers"]:
            available = list(config["providers"].keys())
            raise ValueError(
                f"Use case '{use_case_name}' references unknown provider '{provider_name}'. "
                f"Available providers: {available}"
            )
        
        provider_config = config["providers"][provider_name]
        return LLMUseCaseHandler(use_case_config, provider_config)
    
    elif use_case_type == "mcp_service":
        return MCPUseCaseHandler(use_case_config)
    
    else:
        raise ValueError(
            f"Unknown use case type: '{use_case_type}'. "
            f"Supported types: 'llm', 'mcp_service'"
        )

