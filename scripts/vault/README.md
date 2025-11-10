# Vault Integration for AgenticTA

## Overview

This directory contains scripts for **optional** HashiCorp Vault integration. Vault is used for secure secret management in production environments.

## ⚠️ Important Notes

- **Vault is OPTIONAL** - It's primarily for development testing and production deployments
- **Local vault-dev is for DEVELOPMENT ONLY** - Never use in production
- **Secrets MUST be migrated before use** - Empty Vault won't work
- **AgenticTA works without Vault** - It uses `.env` file by default

## Quick Start (Local Development)

### 1. Start Local Vault Server

```bash
make vault-dev-start
```

This will:
- Start a Vault container in dev mode
- Create network for inter-service communication
- Initialize KV v2 secrets engine
- Create `.env.vault-local` with credentials

### 2. Migrate Secrets from .env

⚠️ **Required before using Vault!**

```bash
# Easy way - using make
make vault-migrate

# Or manually
docker compose exec agenticta python scripts/vault/migrate_secrets_to_vault.py
```

This migrates secrets from your `.env` file to Vault.

### 3. Verify Secrets

```bash
make vault-check
```

Expected output should show all secrets present:
```
📦 agenticta/api-keys
   ✅ nvidia_api_key: ***
   ✅ hf_token: ***
```

### 4. Stop Vault

```bash
make vault-dev-stop
```

## Configuration

**Local Development (vault-dev):**
- Address: `http://localhost:8200`
- Token: `dev-root-token-agenticta`
- UI: `http://localhost:8200/ui`
- Network: `agenticta-vault-network`

**Production (NVIDIA Vault):**
See `NVIDIA_VAULT_SETUP.md` and `TOKEN_RENEWAL_GUIDE.md`

## Scripts

| Script | Purpose |
|--------|---------|
| `start_local_vault.sh` | Start local Vault dev server |
| `stop_local_vault.sh` | Stop local Vault dev server |
| `migrate_secrets_to_vault.py` | Migrate `.env` secrets to Vault |
| `list_secrets.py` | Check what secrets are in Vault |
| `vault_health_check.py` | Comprehensive health check |
| `setup_nvidia_vault.sh` | Setup for NVIDIA production Vault |
| `get_vault_token.sh` | Get token from NVIDIA Vault |
| `check_all.sh` | Full system diagnostics |

## Vault Paths

Secrets are stored in:
```
secret/
└── agenticta/
    ├── api-keys          (nvidia_api_key, hf_token)
    ├── auth-tokens       (astra_token)
    └── observability     (datadog_embedding_api_token)
```

## Troubleshooting

### "Secrets are missing" error

**Cause**: Vault is empty - secrets not migrated

**Fix**:
```bash
docker compose exec agenticta python scripts/vault/migrate_secrets_to_vault.py
```

### "Cannot connect to Vault"

**Cause**: Vault not running or network issue

**Fix**:
```bash
# Check Vault is running
docker ps | grep vault

# Restart if needed
make vault-dev-stop
make vault-dev-start
```

### "AgenticTA container not running"

**Cause**: `make vault-check` needs agenticta container

**Fix**:
```bash
make up  # Start all services
```

## When to Use Vault

**Use Vault if:**
- 🏢 Running in production with centralized secret management
- 🔐 Need secret rotation and audit logging
- 👥 Multiple team members need access to secrets
- ☁️ Deploying to cloud/enterprise environment

**Don't use Vault if:**
- 💻 Local development only
- 🚀 Quick prototyping
- 👤 Solo developer
- 📝 `.env` file is sufficient

## Default Behavior (No Vault)

AgenticTA works perfectly fine without Vault:
1. Reads secrets from `.env` file (via `llm/config.py`)
2. No additional setup required
3. Simple and fast for development

Vault is purely **optional** for enhanced security needs!

## Production Vault Setup

For production NVIDIA Vault integration:
1. Read `NVIDIA_VAULT_SETUP.md`
2. Run `./setup_nvidia_vault.sh`
3. Follow `TOKEN_RENEWAL_GUIDE.md` for token management

## Support

For issues:
1. Run `./check_all.sh` for full diagnostics
2. Check logs: `docker compose logs vault-dev`
3. Verify network: `docker network inspect agenticta-vault-network`

