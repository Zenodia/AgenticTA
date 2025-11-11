# AgenticTA Production Deployment - Quick Start

## 🚀 Build and Deploy in 5 Minutes

### Prerequisites Check
```bash
✅ Docker installed and running
✅ NVIDIA Artifactory credentials
✅ Vault token for production secrets
```

---

## Option A: Automated Build (Recommended)

```bash
# 1. Login to Artifactory
docker login artifactory.nvidia.com
# Username: <your-nvidia-username>
# Password: <your-artifactory-token>

# 2. Build and push (one command!)
./build-and-push.sh 1.0.0

# 3. Deploy
# Set VAULT_ADDR for staging or production:
# export VAULT_ADDR=https://stg.internal.vault.nvidia.com   # For staging
# export VAULT_ADDR=https://prod.internal.vault.nvidia.com  # For production

docker run -d -p 7860:7860 \
  -e VAULT_TOKEN=$VAULT_TOKEN \
  -e VAULT_ADDR=$VAULT_ADDR \
  -e VAULT_NAMESPACE=wwfo-self-ta \
  -e VAULT_MOUNT_POINT=secret \
  artifactory.nvidia.com/it-continum/agenticta:1.0.0
```

---

## Option B: Manual Build

```bash
# 1. Build production image
docker build -f Dockerfile.prod -t agenticta:1.0.0 .

# 2. Tag for Artifactory
docker tag agenticta:1.0.0 artifactory.nvidia.com/it-continum/agenticta:1.0.0
docker tag agenticta:1.0.0 artifactory.nvidia.com/it-continum/agenticta:latest

# 3. Login to Artifactory
docker login artifactory.nvidia.com

# 4. Push
docker push artifactory.nvidia.com/it-continum/agenticta:1.0.0
docker push artifactory.nvidia.com/it-continum/agenticta:latest

# 5. Deploy
docker run -d -p 7860:7860 \
  -e VAULT_TOKEN=$VAULT_TOKEN \
  -e VAULT_ADDR=$VAULT_ADDR \
  -e VAULT_NAMESPACE=wwfo-self-ta \
  -e VAULT_MOUNT_POINT=secret \
  artifactory.nvidia.com/it-continum/agenticta:1.0.0
```

---

## Verify Deployment

```bash
# Check container is running
docker ps | grep agenticta

# Check logs
docker logs -f <container-id>

# Test endpoint
curl http://localhost:7860/
```

Expected output:
```
🔐 SECRETS MANAGEMENT: Using HashiCorp Vault
* Running on local URL:  http://0.0.0.0:7860
```

---

## What's Baked Into the Image?

✅ **Included:**
- All Python files (*.py)
- `llm/` module
- `vault/` module  
- `rag/` module
- `study_buddy_agent/` module
- `scripts/` directory
- `tests/` directory
- Configuration files (llm_config.yaml, pytest.ini, etc.)

❌ **NOT Included (injected at runtime):**
- `.env` files (secrets!)
- `VAULT_TOKEN` (injected via -e flag)
- API keys
- User data (`mnt/`, `volumes/`)

---

## Key Differences: Dev vs. Prod

| Aspect | Development | Production |
|--------|-------------|------------|
| **Dockerfile** | `Dockerfile` | `Dockerfile.prod` |
| **Code** | Volume mount | Baked into image |
| **Build time** | ~2 min | ~5 min |
| **Image size** | 1.5 GB | 2.1 GB |
| **Secrets** | .env file | Runtime injection |
| **Command** | `make up` | `docker run -e VAULT_TOKEN=...` |

---

## Troubleshooting

### "Cannot import vault"
**Fix:** Rebuild with Dockerfile.prod
```bash
docker build -f Dockerfile.prod -t agenticta:latest .
```

### "Permission denied" on Artifactory
**Fix:** Login with correct credentials
```bash
docker login artifactory.nvidia.com
# Username: <your-nvidia-username>
# Password: <your-artifactory-token>
```

### "No such file: gradioUI.py"
**Fix:** Files not copied. Check .dockerignore and rebuild
```bash
docker build -f Dockerfile.prod -t agenticta:latest .
```

### Secrets visible in image
**Fix:** Never bake secrets into image!
```bash
# Check what's in image
docker run --rm agenticta:latest env
# Should NOT see VAULT_TOKEN, NVIDIA_API_KEY
```

---

## Next Steps

📖 **Full Documentation:**
- [ARTIFACTORY_DEPLOYMENT.md](docs/ARTIFACTORY_DEPLOYMENT.md) - Complete deployment guide
- [VAULT_DEPLOYMENT_GUIDE.md](docs/VAULT_DEPLOYMENT_GUIDE.md) - Vault setup and token management

🔐 **Security:**
- Never commit `.env` files
- Never bake secrets into images  
- Always inject secrets at runtime
- Rotate tokens every 90 days

🚢 **Production Deployment:**
- Use Kubernetes for scalability
- Implement health checks
- Set up monitoring and logging
- Use CI/CD for automated deployments

---

## Quick Commands Reference

```bash
# Build
docker build -f Dockerfile.prod -t agenticta:1.0.0 .

# Tag
docker tag agenticta:1.0.0 artifactory.nvidia.com/it-continum/agenticta:1.0.0

# Push
docker push artifactory.nvidia.com/it-continum/agenticta:1.0.0

# Pull
docker pull artifactory.nvidia.com/it-continum/agenticta:1.0.0

# Run (with Vault)
docker run -d -p 7860:7860 \
  -e VAULT_TOKEN=$VAULT_TOKEN \
  -e VAULT_ADDR=$VAULT_ADDR \
  -e VAULT_NAMESPACE=wwfo-self-ta \
  -e VAULT_MOUNT_POINT=secret \
  artifactory.nvidia.com/it-continum/agenticta:1.0.0

# Stop
docker stop <container-id>

# Logs
docker logs -f <container-id>
```

---

**Questions?** See [docs/ARTIFACTORY_DEPLOYMENT.md](docs/ARTIFACTORY_DEPLOYMENT.md) for detailed instructions.

