# AgenticTA Quickstart

Get running in 3 minutes. Choose your configuration mode below.

---

## 🎯 Choose Your Mode

AgenticTA supports **4 configuration modes**:

| Mode | Best For | Setup Time |
|------|----------|------------|
| **[.env (Default)](#-mode-1-using-env-default)** | Fast local dev | 30 seconds |
| **[Local Vault](#-mode-2-using-local-vault)** | Testing vault integration | 2 minutes |
| **[Staging Vault](#-mode-3-using-staging-vault-nvidia-internal)** | NVIDIA internal testing | 1 minute |
| **[Production Vault](#-mode-4-using-production-vault-nvidia-internal)** | Production deployment | 1 minute |

**💡 Recommended**: Start with `.env` mode for fastest setup.

---

## ⚡ Mode 1: Using .env (Default)

**Best for**: Fast local development, demos, testing

```bash
# 1. Set your API key
echo "NVIDIA_API_KEY=nvapi-..." > .env

# 2. Start everything (wait ~30 seconds)
make up

# 3. Start Gradio UI
make gradio

# 4. Open http://localhost:7860
```

That's it! 🎉

### 🧪 Test Your Setup

```bash
# Run unit tests
make test

# Check services
make status
```

**When to use**: Daily development, quick testing, demos

---

## 🔐 Mode 2: Using Local Vault

**Best for**: Testing vault integration locally

```bash
# 1. Set your API key in .env
echo "NVIDIA_API_KEY=nvapi-..." > .env

# 2. Start with vault-dev (includes all services)
make up-with-vault

# 3. Migrate secrets from .env to vault (one-time)
make vault-migrate

# 4. Verify secrets in vault
make vault-check

# 5. Start Gradio UI
make gradio

# 6. Open http://localhost:7860
```

**Features**:
- ✅ Local HashiCorp Vault server
- ✅ Secrets stored in vault KV store
- ✅ Persists across restarts
- ✅ Vault UI: http://localhost:8200 (token: `dev-root-token-agenticta`)

### 🧪 Test Your Setup

```bash
# Check vault is running
docker ps | grep vault-dev

# Verify secrets in vault
make vault-check

# Run unit tests
make test
```

**When to use**: Testing vault features, team development

**Switch back to .env**: `make down && make up`

---

## 🏢 Mode 3: Using Staging Vault (NVIDIA Internal)

**Best for**: NVIDIA internal staging/testing

```bash
# 1. Create vault config file
cat > .env.vault-staging << 'EOF'
# NVIDIA Staging Vault (internal only)
VAULT_ADDR=https://stg.internal.vault.nvidia.com
VAULT_NAMESPACE=wwfo-self-ta
VAULT_TOKEN=<your-staging-token>  # Get from NVIDIA IT
ENVIRONMENT=staging
EOF

# 2. Start with staging vault
docker compose -f docker-compose.yml \
               -f docker-compose.vault-staging.yml up -d

# 3. Start Gradio UI
make gradio

# 4. Open http://localhost:7860
```

**Requirements**:
- NVIDIA network access
- Valid staging vault token
- Secrets already populated in vault path: `secret/agenticta/`

### 🧪 Test Your Setup

```bash
# Check environment variables
docker compose exec agenticta printenv | grep VAULT

# Run unit tests
make test

# Check services
make status
```

**When to use**: Internal staging deployments, pre-production testing

**Stop**: `docker compose down`

---

## 🚀 Mode 4: Using Production Vault (NVIDIA Internal)

**Best for**: Production deployment

```bash
# 1. Create vault config file
cat > .env.vault-prod << 'EOF'
# NVIDIA Production Vault (internal only)
VAULT_ADDR=https://prod.internal.vault.nvidia.com
VAULT_NAMESPACE=wwfo-self-ta
VAULT_TOKEN=<your-production-token>  # Get from NVIDIA IT
ENVIRONMENT=production
REQUIRE_VAULT=true
EOF

# 2. Deploy to production
make deploy-prod

# 3. Verify deployment
docker compose ps

# 4. Check logs
make logs
```

**Production Safety**:
- ⚠️ **REQUIRES** `VAULT_TOKEN` - hard fail if not set
- ⚠️ **No .env fallback** - enforces vault usage
- ✅ All secrets loaded from production vault
- ✅ Full audit logging

**Requirements**:
- NVIDIA network access
- Valid production vault token
- Secrets already populated in vault path: `secret/agenticta/`
- Production k8s cluster (recommended)

### 🧪 Test Your Setup

```bash
# Verify production environment
docker compose exec agenticta printenv | grep -E "ENVIRONMENT|VAULT"

# Run unit tests
make test

# Check services
make status

# View logs
make logs
```

**When to use**: Production deployments only

**Stop**: `docker compose down`

---

## 📖 Upload & Study

1. **Upload PDFs** → Click "Upload PDF files" button
2. **Generate** → Click "Generate Curriculum" (takes 2-3 min)
3. **Study** → Browse chapters, ask Study Buddy questions

---

## 🛠️ Essential Commands

```bash
make help       # Show all commands
make status     # Check what's running
make logs       # View logs
make restart    # Restart everything
make down       # Stop everything
```

---

## 🔧 Quick Config Changes

Want different AI models? Edit `llm_config.yaml`:

```yaml
use_cases:
  study_material_generation:
    provider: nvidia
    model: powerful      # Change to 'fast' for speed
    temperature: 0.7     # Adjust 0.0-1.0
```

Then `make restart`

---

## ⚠️ Common Issues

**Can't connect to port 7860?**
```bash
make restart-gradio && make logs-gradio
```

**No space left?**
```bash
docker system prune -a
```

**Services won't start?**
```bash
make down && make up
```

---

## 📚 Need More Help?

- **Detailed Setup**: See [SETUP_GUIDE.md](SETUP_GUIDE.md)
- **Vault Documentation**: See [vault/](vault/) - Switching, Tiers, Safety
- **LLM Module**: See [llm/README.md](llm/README.md)
- **All Commands**: Run `make help`

---

## 🔄 Mode Comparison

| Feature | .env | Local Vault | Staging Vault | Production Vault |
|---------|------|-------------|---------------|------------------|
| **Setup Time** | 30 sec | 2 min | 1 min | 1 min |
| **Secrets Storage** | .env file | Local vault | NVIDIA vault | NVIDIA vault |
| **Network Required** | ❌ No | ❌ No | ✅ NVIDIA | ✅ NVIDIA |
| **Vault Server** | None | Local Docker | NVIDIA Staging | NVIDIA Production |
| **Fallback to .env** | N/A | ✅ Yes | ✅ Yes | ❌ No |
| **Production Ready** | ❌ No | ❌ No | ⚠️ Testing | ✅ Yes |
| **Best For** | Daily dev | Vault testing | Internal staging | Production |

**💡 Quick Tips**:
- **Daily work**: Use `.env` mode (fastest)
- **Testing vault**: Use local vault mode
- **NVIDIA internal**: Use staging/production vaults
- **Switching modes**: Just `make down` then start with different command
