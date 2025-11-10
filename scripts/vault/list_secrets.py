#!/usr/bin/env python3
"""
List all secrets stored in Vault for AgenticTA.

Usage:
    python scripts/vault/list_secrets.py
"""

import hvac
import os
import sys
from typing import Dict, List


# Expected secrets structure for AgenticTA
# Note: Vault keys are stored in lowercase (as per vault/config.py)
EXPECTED_SECRETS = {
    'agenticta/api-keys': [
        'nvidia_api_key',
        'hf_token',
    ],
    'agenticta/auth-tokens': [
        'astra_token',
    ],
    'agenticta/observability': [
        'datadog_embedding_api_token',
    ],
}


def check_secrets():
    """Check what secrets exist in Vault."""
    
    print("=" * 70)
    print("🔍 Checking Vault Secrets for AgenticTA")
    print("=" * 70)
    print()
    
    # Check environment
    vault_addr = os.getenv('VAULT_ADDR')
    vault_token = os.getenv('VAULT_TOKEN')
    
    if not vault_addr or not vault_token:
        print("❌ Environment not configured!")
        print("   Run: source .env.vault-local")
        return False
    
    print(f"📍 Vault: {vault_addr}")
    print()
    
    # Connect to Vault
    try:
        vault_namespace = os.getenv('VAULT_NAMESPACE', '')
        client_kwargs = {
            'url': vault_addr,
            'token': vault_token,
        }
        if vault_namespace and vault_namespace.strip():
            client_kwargs['namespace'] = vault_namespace
            
        client = hvac.Client(**client_kwargs)
        
        if not client.is_authenticated():
            print("❌ Not authenticated to Vault")
            return False
            
    except Exception as e:
        print(f"❌ Failed to connect to Vault: {e}")
        return False
    
    # Check each secret path
    all_found = True
    total_paths = 0
    total_secrets = 0
    
    for path, expected_secrets in EXPECTED_SECRETS.items():
        print(f"📦 {path}")
        print("-" * 70)
        
        try:
            response = client.secrets.kv.v2.read_secret_version(path=path)
            secrets_data = response['data']['data']
            
            print(f"   ✅ Path exists with {len(secrets_data)} secrets")
            total_paths += 1
            
            # Check each expected secret
            for secret_name in expected_secrets:
                if secret_name in secrets_data:
                    value = secrets_data[secret_name]
                    # Show masked value
                    if len(value) > 12:
                        masked = value[:4] + '...' + value[-4:]
                    else:
                        masked = '***'
                    print(f"      ✅ {secret_name}: {masked}")
                    total_secrets += 1
                else:
                    print(f"      ❌ {secret_name}: MISSING")
                    all_found = False
            
            # Show any extra secrets (excluding migration metadata)
            migration_keys = {'_migrated_by', '_migrated_at'}
            extra_secrets = set(secrets_data.keys()) - set(expected_secrets) - migration_keys
            if extra_secrets:
                print(f"      ℹ️  Extra secrets: {', '.join(extra_secrets)}")
                
        except Exception as e:
            print(f"   ❌ Path not found: {e}")
            for secret_name in expected_secrets:
                print(f"      ❌ {secret_name}: MISSING")
            all_found = False
        
        print()
    
    # Summary
    print("=" * 70)
    print("📊 Summary")
    print("=" * 70)
    expected_total_paths = len(EXPECTED_SECRETS)
    expected_total_secrets = sum(len(secrets) for secrets in EXPECTED_SECRETS.values())
    
    print(f"Paths:   {total_paths}/{expected_total_paths} found")
    print(f"Secrets: {total_secrets}/{expected_total_secrets} found")
    print()
    
    if all_found:
        print("✅ All required secrets are in Vault!")
        return True
    else:
        print("❌ Some secrets are missing!")
        print()
        print("To migrate secrets from .env:")
        print("  python scripts/vault/migrate_secrets_to_vault.py")
        return False


if __name__ == '__main__':
    try:
        success = check_secrets()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
