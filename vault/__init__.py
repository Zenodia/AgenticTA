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

import os
import logging

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

logger = logging.getLogger(__name__)


def log_vault_status():
    """
    Log the current Vault configuration status.
    
    This function should be called at application startup to make it clear
    whether Vault is being used for secrets management.
    """
    vault_token = os.getenv('VAULT_TOKEN')
    
    print("\n" + "=" * 70)
    if vault_token:
        print("🔐 SECRETS MANAGEMENT: Using HashiCorp Vault")
        print("=" * 70)
        logger.info("Vault is enabled for secrets management")
    else:
        print("⚠️  SECRETS MANAGEMENT: Vault NOT available")
        print("⚠️  Using environment variables from .env file")
        print("⚠️  This is INSECURE for production!")
        print("=" * 70)
        print("To enable Vault:")
        print("  1. Stop services: make down")
        print("  2. Start with Vault: make up-with-vault")
        print("  3. Migrate secrets: make vault-migrate")
        print("=" * 70)
        logger.warning("Vault is NOT enabled - using environment variables")
    print()


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
    # Status
    'log_vault_status',
]

__version__ = '1.0.0'

