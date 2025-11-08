"""
Vault integration for AgenticTA.

This module provides secure secrets management using HashiCorp Vault.
Secrets can be read from Vault with automatic fallback to environment variables.

Quick Start:
    >>> from vault import get_secrets_config
    >>> secrets = get_secrets_config()
    >>> api_key = secrets.get('NVIDIA_API_KEY')

Production (No Fallback):
    >>> from vault import start_token_manager, get_secrets_config
    >>> # Start automatic token renewal
    >>> start_token_manager(check_interval=300, renew_threshold=7200)
    >>> # Load secrets from Vault only
    >>> secrets = get_secrets_config()

For more details, see the documentation in scripts/vault/
"""

from vault.client import VaultClient, get_vault_client, get_secret_with_fallback
from vault.config import (
    SecretsConfig,
    get_secrets_config,
    get_nvidia_api_key,
    get_hf_token,
    get_astra_token,
    get_datadog_embedding_token,
)
from vault.token_manager import TokenManager, get_token_manager, start_token_manager

__all__ = [
    # Client
    'VaultClient',
    'get_vault_client',
    'get_secret_with_fallback',
    # Config
    'SecretsConfig',
    'get_secrets_config',
    # Convenience functions
    'get_nvidia_api_key',
    'get_hf_token',
    'get_astra_token',
    'get_datadog_embedding_token',
    # Token Management
    'TokenManager',
    'get_token_manager',
    'start_token_manager',
]

__version__ = '1.0.0'

