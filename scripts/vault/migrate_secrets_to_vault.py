#!/usr/bin/env python3
"""
Migration script to move secrets from .env to Vault.
Run this once to migrate your secrets.

Usage:
    python migrate_secrets_to_vault.py [--dry-run]
"""

import os
import sys
import argparse
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()
# Add parent directory to path to import vault module
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from vault.client import get_vault_client
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def migrate_secrets(dry_run: bool = False):
    """
    Migrate secrets from .env to Vault.
    
    Args:
        dry_run: If True, show what would be done without actually doing it
    """
    
    # Load .env file
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    if not os.path.exists(env_path):
        logger.error(f".env file not found at: {env_path}")
        logger.info("Looking for .env in parent directories...")
        
        # Try parent directories
        current_dir = os.path.dirname(os.path.abspath(__file__))
        for _ in range(3):  # Check up to 3 levels up
            parent_dir = os.path.dirname(current_dir)
            env_path = os.path.join(parent_dir, '.env')
            if os.path.exists(env_path):
                logger.info(f"Found .env at: {env_path}")
                break
            current_dir = parent_dir
        else:
            logger.error("Could not find .env file")
            sys.exit(1)
    
    load_dotenv(env_path)
    logger.info(f"Loaded environment from: {env_path}")
    
    if dry_run:
        logger.info("=" * 60)
        logger.info("DRY RUN MODE - No changes will be made")
        logger.info("=" * 60)
    
    # Get Vault client
    try:
        vault = get_vault_client()
        logger.info("Connected to Vault successfully")
    except Exception as e:
        logger.error(f"Failed to connect to Vault: {e}")
        logger.error("\nMake sure you have:")
        logger.error("  1. VAULT_TOKEN set in environment")
        logger.error("  2. Network access to Vault server")
        logger.error("  3. Valid token with write permissions")
        sys.exit(1)
    
    # Define secret mappings
    secret_groups = {
        'agenticta/api-keys': {
            'nvidia_api_key': os.getenv('NVIDIA_API_KEY'),
            'hf_token': os.getenv('HF_TOKEN'),
        },
        'agenticta/auth-tokens': {
            'astra_token': os.getenv('ASTRA_TOKEN'),
        },
        'agenticta/observability': {
            'datadog_embedding_api_token': os.getenv('DATADOG_EMBEDDING_API_TOKEN'),
        }
    }
    
    # Statistics
    total_secrets = 0
    migrated_secrets = 0
    skipped_secrets = 0
    failed_secrets = 0
    
    # Migrate each group
    for path, secrets in secret_groups.items():
        logger.info("\n" + "=" * 60)
        logger.info(f"Processing: {path}")
        logger.info("=" * 60)
        
        # Filter out None values
        secrets_to_store = {
            k: v for k, v in secrets.items() 
            if v is not None and v.strip() != ''
        }
        
        if not secrets_to_store:
            logger.warning(f"No secrets found for {path}")
            skipped_secrets += len(secrets)
            continue
        
        total_secrets += len(secrets_to_store)
        
        # Show what will be migrated
        logger.info(f"Found {len(secrets_to_store)} secrets:")
        for key in secrets_to_store.keys():
            value = secrets_to_store[key]
            # Mask the value for security
            masked = value[:4] + '*' * (len(value) - 8) + value[-4:] if len(value) > 8 else '***'
            logger.info(f"  - {key}: {masked}")
        
        if dry_run:
            logger.info(f"Would migrate {len(secrets_to_store)} secrets to {path}")
            migrated_secrets += len(secrets_to_store)
            continue
        
        # Add metadata
        secrets_to_store['_migrated_at'] = '2025-11-07'
        secrets_to_store['_migrated_by'] = 'migrate_secrets_to_vault.py'
        
        # Store in Vault
        try:
            success = vault.set_secret(path, secrets_to_store)
            
            if success:
                logger.info(f"✓ Migrated {len(secrets_to_store) - 2} secrets to {path}")
                migrated_secrets += len(secrets_to_store) - 2  # Exclude metadata
            else:
                logger.error(f"✗ Failed to migrate secrets to {path}")
                failed_secrets += len(secrets_to_store) - 2
        except Exception as e:
            logger.error(f"✗ Error migrating to {path}: {e}")
            failed_secrets += len(secrets_to_store) - 2
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("Migration Summary")
    logger.info("=" * 60)
    logger.info(f"Total secrets found: {total_secrets}")
    logger.info(f"Successfully migrated: {migrated_secrets}")
    logger.info(f"Skipped (empty): {skipped_secrets}")
    logger.info(f"Failed: {failed_secrets}")
    
    if dry_run:
        logger.info("\nThis was a DRY RUN. No changes were made.")
        logger.info("Run without --dry-run to actually migrate secrets.")
        return True  # Dry run is always "successful"
    else:
        # Determine success
        success = (failed_secrets == 0 and migrated_secrets > 0)
        
        if success:
            logger.info("\n✅ Successfully migrated all secrets to Vault!")
        else:
            logger.info("\n⚠️  Migration completed with errors")
        
        logger.info("\n" + "=" * 60)
        logger.info("Next Steps")
        logger.info("=" * 60)
        logger.info("1. Verify secrets in Vault:")
        logger.info("   make vault-check")
        logger.info("")
        logger.info("2. Run tests:")
        logger.info("   make test")
        logger.info("")
        logger.info("3. Your application will now use Vault automatically!")
        logger.info("   The vault module loads secrets from Vault with .env fallback")
        logger.info("")
        logger.info("4. (Optional) Create .env.template for new team members:")
        logger.info("   cp .env .env.template")
        logger.info("   # Then remove actual secret values from .env.template")
    
        return success


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Migrate secrets from .env to Vault'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without actually doing it'
    )
    
    args = parser.parse_args()
    
    try:
        success = migrate_secrets(dry_run=args.dry_run)
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\nMigration cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Migration failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()


