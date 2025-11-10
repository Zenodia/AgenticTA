#!/usr/bin/env python3
"""
Health check script for Vault connectivity and permissions.

Usage:
    python vault_health_check.py
"""

import hvac
import os
import sys
from typing import Dict
from dotenv import load_dotenv


# Colors for terminal output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'
    BOLD = '\033[1m'


def print_success(msg):
    """Print success message in green."""
    print(f"{Colors.GREEN}✓{Colors.END} {msg}")


def print_error(msg):
    """Print error message in red."""
    print(f"{Colors.RED}✗{Colors.END} {msg}")


def print_warning(msg):
    """Print warning message in yellow."""
    print(f"{Colors.YELLOW}⚠{Colors.END} {msg}")


def print_header(msg):
    """Print header."""
    print(f"\n{Colors.BOLD}{'=' * 60}{Colors.END}")
    print(f"{Colors.BOLD}{msg}{Colors.END}")
    print(f"{Colors.BOLD}{'=' * 60}{Colors.END}")


def check_vault_health() -> Dict[str, bool]:
    """Comprehensive Vault health check."""
    results = {}
    
    # Load .env if exists
    load_dotenv()
    
    # 1. Check environment variables
    print_header("1. Environment Variables")
    
    required_vars = ['VAULT_ADDR', 'VAULT_TOKEN']
    optional_vars = ['VAULT_NAMESPACE']
    
    for var in required_vars:
        value = os.getenv(var)
        exists = value is not None and value.strip() != ''
        results[f'env_{var}'] = exists
        
        if exists:
            # Show masked value for token
            if var == 'VAULT_TOKEN':
                masked = value[:8] + '...' + value[-4:] if len(value) > 12 else '***'
                print_success(f"{var}: {masked}")
            else:
                print_success(f"{var}: {value}")
        else:
            print_error(f"{var}: Not set")
    
    for var in optional_vars:
        value = os.getenv(var)
        if value is not None:
            if value.strip() == '':
                print_success(f"{var}: (empty - local mode)")
            else:
                print_success(f"{var}: {value}")
        else:
            print_warning(f"{var}: Not set (optional)")
    
    if not all([results.get(f'env_{var}') for var in required_vars]):
        print_error("\nMissing required environment variables. Cannot proceed.")
        return results
    
    # 2. Check connectivity
    print_header("2. Vault Connectivity")
    
    try:
        vault_namespace = os.getenv('VAULT_NAMESPACE', '')
        client_kwargs = {
            'url': os.getenv('VAULT_ADDR'),
            'token': os.getenv('VAULT_TOKEN'),
        }
        # Only add namespace if it's not empty (local Vault doesn't use namespaces)
        if vault_namespace and vault_namespace.strip():
            client_kwargs['namespace'] = vault_namespace
        
        client = hvac.Client(**client_kwargs)
        
        # Check authentication
        authenticated = client.is_authenticated()
        results['authenticated'] = authenticated
        
        if authenticated:
            print_success("Authentication: OK")
        else:
            print_error("Authentication: Failed")
            print_error("  Check if your VAULT_TOKEN is valid")
            return results
        
        # Get token info
        try:
            token_info = client.auth.token.lookup_self()
            ttl = token_info['data']['ttl']
            policies = token_info['data']['policies']
            
            results['token_valid'] = True
            
            # Check TTL
            if ttl > 86400:  # > 1 day
                print_success(f"Token TTL: {ttl} seconds ({ttl/3600:.1f} hours)")
            elif ttl > 3600:  # > 1 hour
                print_warning(f"Token TTL: {ttl} seconds ({ttl/3600:.1f} hours) - Consider renewing soon")
            else:
                print_error(f"Token TTL: {ttl} seconds ({ttl/60:.1f} minutes) - Renew immediately!")
            
            print_success(f"Token Policies: {', '.join(policies)}")
            
        except Exception as e:
            results['token_info'] = False
            print_error(f"Failed to get token info: {e}")
        
    except Exception as e:
        results['connectivity'] = False
        print_error(f"Connection failed: {e}")
        return results
    
    # 3. Check secret access
    print_header("3. Secret Access")
    
    test_paths = [
        'agenticta/api-keys',
        'agenticta/auth-tokens',
        'agenticta/observability'
    ]
    
    for path in test_paths:
        try:
            response = client.secrets.kv.v2.read_secret_version(path=path)
            results[f'access_{path}'] = True
            
            # Show number of keys without revealing values
            secret_data = response['data']['data']
            keys = [k for k in secret_data.keys() if not k.startswith('_')]
            print_success(f"Read access to: {path} ({len(keys)} secrets)")
            
        except hvac.exceptions.InvalidPath:
            results[f'access_{path}'] = False
            print_warning(f"Secret not found: {path} (not yet created)")
        except hvac.exceptions.Forbidden:
            results[f'access_{path}'] = False
            print_error(f"Permission denied: {path}")
            print_error(f"  Your token doesn't have read access to this path")
        except Exception as e:
            results[f'access_{path}'] = False
            print_error(f"Error accessing {path}: {e}")
    
    # 4. Check write permissions (optional)
    print_header("4. Write Permissions (Optional)")
    
    test_path = 'agenticta/healthcheck'
    test_data = {'test': 'healthcheck', 'timestamp': '2025-11-07'}
    
    try:
        # Try to write test data
        client.secrets.kv.v2.create_or_update_secret(
            path=test_path,
            secret=test_data
        )
        results['write_access'] = True
        print_success(f"Write access: OK (test secret created at {test_path})")
        
        # Clean up test secret
        try:
            client.secrets.kv.v2.delete_metadata_and_all_versions(path=test_path)
            print_success(f"Cleanup: Test secret deleted")
        except:
            pass
            
    except hvac.exceptions.Forbidden:
        results['write_access'] = False
        print_warning("Write access: Denied (read-only token)")
        print_warning("  This is OK if you only need to read secrets")
    except Exception as e:
        results['write_access'] = False
        print_error(f"Write test failed: {e}")
    
    # 5. Summary
    print_header("Summary")
    
    total = len([k for k in results.keys() if k.startswith('env_') or k.startswith('access_') or k == 'authenticated'])
    passed = sum([v for k, v in results.items() if k.startswith('env_') or k.startswith('access_') or k == 'authenticated'])
    
    print(f"\nChecks passed: {passed}/{total}")
    
    if passed == total:
        print_success("All critical checks passed!")
        print("\nYou can now:")
        print("  1. Migrate secrets: python migrate_secrets_to_vault.py")
        print("  2. Use Vault in your application")
    else:
        print_error("Some checks failed. Review above output.")
        print("\nCommon issues:")
        print("  - Token expired: Get a new VAULT_TOKEN")
        print("  - Permission denied: Request access to namespace")
        print("  - Secrets not found: Run migration script first")
    
    return results


def main():
    """Main entry point."""
    try:
        results = check_vault_health()
        
        # Exit with error if critical checks failed
        critical_checks = ['authenticated']
        if not all([results.get(check, False) for check in critical_checks]):
            sys.exit(1)
        
        sys.exit(0)
        
    except KeyboardInterrupt:
        print("\n\nHealth check cancelled by user")
        sys.exit(1)
    except Exception as e:
        print_error(f"\nHealth check failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()


