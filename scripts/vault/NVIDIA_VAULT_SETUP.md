# NVIDIA Vault Setup Guide for AgenticTA

This guide walks through setting up NVIDIA Vault for AgenticTA, from initial authentication to migrating all secrets.

## 📋 Prerequisites

1. **Vault CLI installed**:
   ```bash
   brew install vault
   ```

2. **Access to NVIDIA Vault**:
   - Staging: `https://stg.internal.vault.nvidia.com`
   - Production: `https://prod.internal.vault.nvidia.com`

3. **Namespace**: `wwfo-self-ta`

4. **Required Role**: `namespace-admin` (for initial setup)

---

## 🚀 Quick Setup (Automated)

For a new namespace, run this one-time setup script:

```bash
# 1. Get authentication
./scripts/vault/get_vault_token.sh staging

# 2. Activate the environment
source .env.vault-local

# 3. Run the automated setup
./scripts/vault/setup_nvidia_vault.sh

# 4. Migrate your secrets
python scripts/vault/migrate_secrets_to_vault.py

# 5. Verify
make vault-check
```

**Done!** Your secrets are now in NVIDIA Vault.

---

## 📖 Manual Setup (Step by Step)

If you want to understand each step or troubleshoot issues:

### Step 1: Authenticate with OIDC

```bash
# Set environment for staging
export VAULT_ADDR=https://stg.internal.vault.nvidia.com
export VAULT_NAMESPACE=wwfo-self-ta

# Login (this will open a browser for SSO)
vault login -method=oidc -path=oidc-admins role=namespace-admin
```

This creates a `namespace-admin` token in `~/.vault-token`.

### Step 2: Save Token to .env

```bash
# Get the token
TOKEN=$(cat ~/.vault-token)

# Add to .env
echo "VAULT_TOKEN=${TOKEN}" >> .env

# Or use the helper script
./scripts/vault/get_vault_token.sh staging
```

### Step 3: Enable KV Secrets Engine

```bash
# Check what's currently enabled
vault secrets list

# Enable KV v2 at 'secret/' path
vault secrets enable -version=2 -path=secret kv

# Verify
vault secrets list
# Should see: secret/  kv  ...
```

### Step 4: Create Application Policy

The `namespace-admin` role manages infrastructure but **cannot access secret data**. 
We need a separate policy for application access.

```bash
# Create policy file
cat > agenticta-secrets.hcl << 'EOF'
# Policy for AgenticTA application secrets
# Allows read/write to agenticta/* paths in the secret/ KV engine

# Allow full access to agenticta secrets
path "secret/data/agenticta/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}

# Allow listing agenticta paths
path "secret/metadata/agenticta/*" {
  capabilities = ["list", "read", "delete"]
}
EOF

# Upload the policy
vault policy write agenticta-secrets agenticta-secrets.hcl
```

### Step 5: Create Application Token

```bash
# Create a token with the agenticta-secrets policy
vault token create \
    -policy=agenticta-secrets \
    -display-name="agenticta-app" \
    -ttl=720h \
    -format=json | jq -r '.auth.client_token'

# Save the output token to .env
echo "VAULT_TOKEN=<your-app-token>" >> .env
```

### Step 6: Test Access

```bash
# Export the new token
source .env.vault-local

# Test write
vault kv put secret/agenticta/test hello=world

# Test read
vault kv get secret/agenticta/test

# Clean up test
vault kv delete secret/agenticta/test
```

### Step 7: Migrate Secrets

```bash
# Run the migration script
python scripts/vault/migrate_secrets_to_vault.py

# Verify all secrets
make vault-check
```

---

## 🔍 Key Concepts

### Why Two Tokens?

1. **namespace-admin token**:
   - For infrastructure management
   - Can enable secret engines, create policies
   - **Cannot** access secret data
   - Used during initial setup

2. **Application token** (agenticta-secrets):
   - For application use
   - Can read/write secrets in `secret/data/agenticta/*`
   - Used by your AgenticTA application
   - Longer TTL (720 hours / 30 days)

### Token Management

```bash
# Check token info
vault token lookup

# Check token TTL
vault token lookup -format=json | jq '.data.ttl'

# Renew token (before it expires)
vault token renew
```

### Secret Paths

AgenticTA uses these paths in Vault:

```
secret/data/agenticta/api-keys        # NVIDIA_API_KEY, HF_TOKEN
secret/data/agenticta/auth-tokens     # ASTRA_TOKEN
secret/data/agenticta/observability   # DATADOG_EMBEDDING_API_TOKEN
```

---

## 🛠️ Troubleshooting

### "permission denied" when writing secrets

**Problem**: Using `namespace-admin` token instead of application token.

**Solution**:
```bash
# Create an application token (Step 5 above)
# Update .env with the new token
# Run: source .env.vault-local
```

### "invalid mount path"

**Problem**: KV secrets engine not enabled at `secret/` path.

**Solution**:
```bash
vault secrets enable -version=2 -path=secret kv
```

### "no KV v2 engine found"

**Problem**: Wrong mount point or KV version.

**Solution**:
```bash
# Check what's enabled
vault secrets list

# Look for KV v2 engines
# If 'secret/' is not listed, enable it:
vault secrets enable -version=2 -path=secret kv
```

### Token Expired

**Problem**: Token TTL expired.

**Solution**:
```bash
# Get a new token
./scripts/vault/get_vault_token.sh staging

# Or renew if not expired yet
vault token renew
```

---

## 📝 For New Team Members

When onboarding a new team member:

1. **They need namespace-admin access** (contact Vault admin)

2. **Run the quick setup**:
   ```bash
   ./scripts/vault/get_vault_token.sh staging
   source .env.vault-local
   ```

3. **They don't need to run setup_nvidia_vault.sh** (one-time only)

4. **Their app will automatically use Vault**:
   - The `vault` Python module is already integrated
   - Secrets are loaded from Vault automatically
   - `.env` is used as a fallback for local dev

---

## 🎯 Production Deployment

For production:

1. **Use production Vault**:
   ```bash
   ./scripts/vault/get_vault_token.sh prod
   source .env.vault-local
   ```

2. **Create production application token** with appropriate TTL

3. **Set environment variables**:
   ```bash
   export VAULT_ADDR=https://prod.internal.vault.nvidia.com
   export VAULT_NAMESPACE=wwfo-self-ta
   export VAULT_TOKEN=<prod-app-token>
   export VAULT_MOUNT_POINT=secret
   ```

4. **Verify secrets exist in production Vault**:
   ```bash
   make vault-check
   ```

---

## 📚 Additional Resources

- [NVIDIA Vault Documentation](https://gitlab-master.nvidia.com/kaizen/services/vault/docs)
- [NVIDIA Vault Quickstart](https://gitlab-master.nvidia.com/kaizen/services/vault/docs/-/blob/main/guides/namespace-admin/quickstart.md)
- [HashiCorp Vault Documentation](https://www.vaultproject.io/docs)

---

## ✅ Summary Checklist

- [ ] Vault CLI installed
- [ ] Authenticated with OIDC (`vault login`)
- [ ] KV secrets engine enabled (`vault secrets enable`)
- [ ] Policy created (`vault policy write agenticta-secrets`)
- [ ] Application token created (`vault token create`)
- [ ] Token saved to `.env`
- [ ] Environment activated (`source .env.vault-local`)
- [ ] Secrets migrated (`python scripts/vault/migrate_secrets_to_vault.py`)
- [ ] Secrets verified (`make vault-check`)
- [ ] Application tested with Vault

**🎉 You're all set!**

