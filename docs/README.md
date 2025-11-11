# AgenticTA Documentation

## Vault Documentation

### 📚 Main Guides

1. **[VAULT_DEPLOYMENT_GUIDE.md](VAULT_DEPLOYMENT_GUIDE.md)** ⭐ **START HERE**
   - Comprehensive guide to understanding and deploying Vault
   - Covers token types, permissions, and workflows
   - Includes troubleshooting and best practices
   - ~8,000 words with detailed examples

2. **[vault-workflow-diagram.md](vault-workflow-diagram.md)**
   - Visual workflow diagrams
   - Quick reference for common patterns
   - Decision trees and flowcharts
   - Perfect for quick lookups

### 📖 Additional Resources

- **[NVIDIA_VAULT_SETUP.md](../scripts/vault/NVIDIA_VAULT_SETUP.md)**
  - NVIDIA-specific Vault setup instructions
  - Detailed policy examples
  - NVIDIA internal documentation links

- **[VAULT_SAFETY.md](../vault/VAULT_SAFETY.md)**
  - Safety guidelines for Vault usage
  
- **[VAULT_SWITCHING.md](../vault/VAULT_SWITCHING.md)**
  - Switching between Vault environments
  
- **[VAULT_TIERS.md](../vault/VAULT_TIERS.md)**
  - Vault tier configurations

### 🚀 Quick Start

For first-time setup:
```bash
# 1. Read the deployment guide
cat docs/VAULT_DEPLOYMENT_GUIDE.md | less

# 2. Follow the setup workflow
vault login -method=oidc -path=oidc-admins role=namespace-admin
vault secrets enable -version=2 -path=secret kv
vault policy write agenticta-secrets scripts/vault/agenticta-secrets.hcl
vault token create -policy=agenticta-secrets -ttl=720h

# 3. Save token and migrate secrets
export VAULT_TOKEN=<your-app-token>
python scripts/vault/migrate_secrets_to_vault.py

# 4. Verify
make vault-check
```

### 🔍 Find What You Need

| I want to... | Read this... |
|-------------|-------------|
| Understand token types | [Token Types](../VAULT_DEPLOYMENT_GUIDE.md#vault-token-types) |
| Set up Vault for the first time | [Initial Setup](../VAULT_DEPLOYMENT_GUIDE.md#initial-setup-workflow) |
| Deploy to production | [Production Deployment](../VAULT_DEPLOYMENT_GUIDE.md#production-deployment) |
| Fix "permission denied" | [Troubleshooting](../VAULT_DEPLOYMENT_GUIDE.md#troubleshooting) |
| See workflow diagrams | [Visual Guide](vault-workflow-diagram.md) |
| Quick command reference | [Quick Reference](../VAULT_DEPLOYMENT_GUIDE.md#quick-reference) |

### 🎯 Key Concepts

**Three Token Types:**
1. **OIDC Token** (1h) - For admins to set up Vault
2. **Application Token** (30d) - For apps to access secrets
3. **Root Token** (∞) - Never use (bootstrap only)

**Golden Rule:**
> Use **OIDC tokens** to create **application tokens**.  
> Use **application tokens** in your code.

### ❓ Common Questions

<details>
<summary><b>Why is my test failing with "permission denied"?</b></summary>

You're using an OIDC token (namespace-admin) instead of an application token.

**Solution:**
```bash
vault token create -policy=agenticta-secrets -ttl=720h
export VAULT_TOKEN=<new-token>
```

See: [Troubleshooting - Permission Denied](../VAULT_DEPLOYMENT_GUIDE.md#1-permission-denied-error)
</details>

<details>
<summary><b>What's the difference between OIDC and application tokens?</b></summary>

- **OIDC Token**: Short-lived (1h), for admins, can't read secrets
- **Application Token**: Long-lived (30d), for apps, can read secrets

See: [Vault Token Types](../VAULT_DEPLOYMENT_GUIDE.md#vault-token-types)
</details>

<details>
<summary><b>How do I rotate tokens in production?</b></summary>

```bash
# Create new token
vault token create -policy=agenticta-secrets -ttl=2160h

# Update application
kubectl set env deployment/agenticta VAULT_TOKEN=<new-token>

# Verify
kubectl rollout status deployment/agenticta
```

See: [Token Rotation](../VAULT_DEPLOYMENT_GUIDE.md#7-set-up-token-rotation)
</details>

<details>
<summary><b>Can I use .env files instead of Vault?</b></summary>

Yes for development, but:
- ❌ Not secure for production
- ❌ No audit logging
- ❌ Manual rotation
- ✅ OK as fallback when Vault is unavailable

See: [Why Use Vault](../VAULT_DEPLOYMENT_GUIDE.md#why-use-vault-vs-env-files)
</details>

### 🔗 External Links

- [NVIDIA Vault Documentation](https://gitlab-master.nvidia.com/kaizen/services/vault/docs)
- [HashiCorp Vault Docs](https://www.vaultproject.io/docs)
- [hvac Python Library](https://hvac.readthedocs.io/)

---

**Last Updated:** 2025-11-11  
**Maintainer:** AgenticTA Team

