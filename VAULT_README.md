# Vault Integration for AgenticTA

Simple Vault integration for managing API keys and tokens securely.

## 🎯 Overview

AgenticTA uses HashiCorp Vault to store sensitive credentials like API keys and tokens instead of `.env` files.

**In Production**: Use NVIDIA's Vault with OIDC authentication  
**For Testing**: Optional local Vault server available

## 📖 Complete Setup Guide

**First time setup?** See the comprehensive guide:
- **[scripts/vault/NVIDIA_VAULT_SETUP.md](scripts/vault/NVIDIA_VAULT_SETUP.md)** - Complete walkthrough from authentication to secret migration

This includes:
- ✅ OIDC authentication
- ✅ Enabling KV secrets engine
- ✅ Creating policies and application tokens
- ✅ Migrating secrets from .env
- ✅ Troubleshooting common issues

## 📦 Python Module

The `vault/` module provides a simple interface to retrieve secrets:

```python
from vault import get_secrets_config

# Get secrets (automatically connects to configured Vault)
secrets = get_secrets_config()
NVIDIA_API_KEY = secrets.get('NVIDIA_API_KEY')
HF_TOKEN = secrets.get('HF_TOKEN')
```

That's it! The module handles all the Vault connection details.

## 🔧 Configuration

Set these environment variables to configure Vault:

```bash
export VAULT_ADDR='https://stg.internal.vault.nvidia.com'
export VAULT_TOKEN='hvs.YOUR_TOKEN_HERE'
export VAULT_NAMESPACE='wwfo-self-ta'
```

### Getting a Vault Token (Production)

For NVIDIA Vault (staging/production):

```bash
# Staging
export VAULT_ADDR=https://stg.internal.vault.nvidia.com
export VAULT_NAMESPACE=wwfo-self-ta
vault login -method=oidc -path=oidc-admins role=namespace-admin

# Production
export VAULT_ADDR=https://prod.internal.vault.nvidia.com
export VAULT_NAMESPACE=wwfo-self-ta
vault login -method=oidc -path=oidc-admins role=namespace-admin
```

This will open your browser for NVIDIA SSO authentication and provide a token.

## 🧪 Local Testing (Optional)

Want to test Vault integration locally without connecting to NVIDIA Vault? We provide a local dev server:

```bash
# 1. Activate your venv
source /path/to/.venv/bin/activate

# 2. Start local Vault (runs in Docker on port 8200, auto-migrates from .env)
make vault-dev-start

# 3. ⚠️  IMPORTANT: Source the vault config (required!)
source .env.vault-local

# 4. Your app can now connect to local Vault
python your_app.py

# Stop when done
make vault-dev-stop
```

> **⚠️ Important**: The `source .env.vault-local` step is **required** after starting Vault. The startup script can't automatically set environment variables in your terminal session - you must source the file manually.

**Note**: 
- Local Vault is for **development/testing only**
- Uses a dev root token and stores secrets **in memory** (lost on restart)
- Automatically migrates secrets from `.env` on startup
- **Activate your venv** before running `make vault-dev-start`

## 📁 Repository Structure

```
AgenticTA/
├── vault/                           # Python module
│   ├── __init__.py
│   ├── client.py                    # Vault client
│   ├── config.py                    # Secrets configuration
│   └── README.md                    # Module documentation
│
├── scripts/vault/                   # Utility scripts
│   ├── start_local_vault.sh        # Start local Vault (testing)
│   ├── stop_local_vault.sh         # Stop local Vault
│   ├── vault_health_check.py       # Check Vault connection
│   ├── migrate_secrets_to_vault.py # Migrate from .env to Vault
│   └── README.md                    # Scripts documentation
│
└── docker-compose.vault-dev.yml    # Local Vault container (testing)
```

## 📚 Documentation

- **[`vault/README.md`](vault/README.md)** - Python module API reference
- **[`vault/EXAMPLE_INTEGRATION.md`](vault/EXAMPLE_INTEGRATION.md)** - Code examples
- **[`scripts/vault/README.md`](scripts/vault/)** - Scripts and utilities
- **[`scripts/vault/QUICKSTART.md`](scripts/vault/QUICKSTART.md)** - Quick setup guide

## 🚀 Quick Start

### For Production Use

1. **Get Vault token** (see "Getting a Vault Token" above)
2. **Set environment variables** with your token
3. **Import and use** the vault module in your code

### For Local Testing

1. **Start local Vault**: `make vault-dev-start`
2. **Activate config**: `source .env.vault-local`
3. **Test your code** with the local Vault
4. **Stop when done**: `make vault-dev-stop`

## 🔐 Security Notes

- **Never commit** `.env`, `.env.vault-local`, or real tokens to git
- **Local Vault** is for testing only - don't use in production
- **Production tokens** expire - use the OIDC method to get new ones
- **Vault namespace** for AgenticTA: `wwfo-self-ta`

## ❓ FAQ

**Q: Do I need to run local Vault to use AgenticTA?**  
A: No! Local Vault is optional and only for testing Vault integration. In production, use NVIDIA's Vault.

**Q: How do I get a production Vault token?**  
A: Use the OIDC method shown above. It will open your browser for NVIDIA SSO.

**Q: What if my Vault token expires?**  
A: Run the `vault login` command again to get a new token.

**Q: Where are the secrets stored in Vault?**  
A: Under the path `agenticta/` in the configured namespace.

## 🛠️ Utilities

Useful scripts in `scripts/vault/`:

- `vault_health_check.py` - Verify Vault connection and permissions
- `migrate_secrets_to_vault.py` - Move secrets from `.env` to Vault
- `test_vault_integration.py` - Test the Vault integration

Run with Python after activating your venv and sourcing Vault config.

---

**For detailed documentation**, see the files in `vault/` and `scripts/vault/` directories.
