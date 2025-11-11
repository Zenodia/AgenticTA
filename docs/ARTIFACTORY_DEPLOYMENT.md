# AgenticTA Deployment to NVIDIA Artifactory

## Overview

This guide explains how to build and deploy AgenticTA Docker images to NVIDIA's Artifactory registry.

---

## Prerequisites

```bash
# 1. Docker installed and running
docker --version

# 2. NVIDIA Artifactory credentials
# Get from: https://artifactory.nvidia.com/ui/admin/artifactory/user_profile

# 3. Vault token for secrets (production)
export VAULT_TOKEN=hvs.CAESIL...
```

---

## Image Structure

### Development Image (Current)
```
┌─────────────────────────────┐
│  Development Image          │
├─────────────────────────────┤
│  • Python 3.12              │
│  • Dependencies             │
│  • ❌ NO application code   │  ← Mounted as volume
│  • /workspace (empty)       │
└─────────────────────────────┘
```

### Production Image (Artifactory)
```
┌─────────────────────────────┐
│  Production Image           │
├─────────────────────────────┤
│  • Python 3.12              │
│  • Dependencies             │
│  • ✅ All Python files      │  ← Baked in
│  • ✅ llm/ module           │
│  • ✅ vault/ module         │
│  • ✅ rag/ module           │
│  • ✅ Config files          │
│  • ❌ NO secrets (.env)     │  ← Injected at runtime
│  • ❌ NO user data          │
└─────────────────────────────┘
```

---

## Build Process

### Step 1: Login to Artifactory

```bash
# Option 1: Using Docker CLI
docker login nvcr.io
# Username: $oauthtoken
# Password: <your-artifactory-token>

# Option 2: Using environment variable
export DOCKER_REGISTRY_TOKEN=<your-artifactory-token>
echo $DOCKER_REGISTRY_TOKEN | docker login -u '$oauthtoken' --password-stdin nvcr.io
```

### Step 2: Build Production Image

```bash
# Navigate to project root
cd /home/scratch.kanghwanj_coreai/n/agentic/zenodia/AgenticTA

# Build with production Dockerfile
docker build -f Dockerfile.prod -t agenticta:latest .

# Verify build
docker images | grep agenticta
```

**Expected output:**
```
agenticta   latest   abc123def456   2 minutes ago   2.1GB
```

### Step 3: Tag for Artifactory

```bash
# Tag with version
VERSION=1.0.0
docker tag agenticta:latest nvcr.io/nvstaging/agenticta:$VERSION
docker tag agenticta:latest nvcr.io/nvstaging/agenticta:latest

# Verify tags
docker images | grep agenticta
```

### Step 4: Push to Artifactory

```bash
# Push specific version
docker push nvcr.io/nvstaging/agenticta:$VERSION

# Push latest
docker push nvcr.io/nvstaging/agenticta:latest
```

**Expected output:**
```
The push refers to repository [nvcr.io/nvstaging/agenticta]
5f70bf18a086: Pushed
1.0.0: digest: sha256:abc123... size: 2876
```

---

## Verify Deployment

### Check in Artifactory UI

1. Go to https://nvcr.io/
2. Navigate to `nvstaging/agenticta`
3. Verify tags: `latest`, `1.0.0`

### Test Pull

```bash
# Pull from Artifactory
docker pull nvcr.io/nvstaging/agenticta:latest

# Verify image content
docker run --rm nvcr.io/nvstaging/agenticta:latest ls -la /workspace
```

**Expected files:**
```
gradioUI.py
vault/
llm/
rag/
requirements.txt
(etc.)
```

---

## Running Production Image

### Option 1: Docker Run (Simple)

```bash
docker run -d \
  --name agenticta \
  -p 7860:7860 \
  -e VAULT_ADDR=https://prod.internal.vault.nvidia.com \
  -e VAULT_NAMESPACE=wwfo-self-ta \
  -e VAULT_TOKEN=$VAULT_TOKEN \
  -e VAULT_MOUNT_POINT=secret \
  nvcr.io/nvstaging/agenticta:latest
```

### Option 2: Docker Compose (Production)

Create `docker-compose.prod.yml`:

```yaml
version: '3.8'

services:
  agenticta:
    image: nvcr.io/nvstaging/agenticta:latest
    container_name: agenticta-prod
    ports:
      - "7860:7860"
    environment:
      - VAULT_ADDR=https://prod.internal.vault.nvidia.com
      - VAULT_NAMESPACE=wwfo-self-ta
      - VAULT_MOUNT_POINT=secret
      # VAULT_TOKEN injected via env_file or secrets
    env_file:
      - /etc/agenticta/.env.prod  # Secure location, not in repo!
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:7860/"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    deploy:
      resources:
        limits:
          memory: 4G
          cpus: '2'
```

Run:
```bash
docker-compose -f docker-compose.prod.yml up -d
```

### Option 3: Kubernetes (Best for Production)

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: agenticta
  namespace: wwfo-self-ta
spec:
  replicas: 2
  selector:
    matchLabels:
      app: agenticta
  template:
    metadata:
      labels:
        app: agenticta
    spec:
      containers:
      - name: agenticta
        image: nvcr.io/nvstaging/agenticta:1.0.0
        ports:
        - containerPort: 7860
        env:
        - name: VAULT_ADDR
          value: "https://prod.internal.vault.nvidia.com"
        - name: VAULT_NAMESPACE
          value: "wwfo-self-ta"
        - name: VAULT_TOKEN
          valueFrom:
            secretKeyRef:
              name: vault-token
              key: VAULT_TOKEN
        - name: VAULT_MOUNT_POINT
          value: "secret"
        resources:
          requests:
            memory: "2Gi"
            cpu: "1000m"
          limits:
            memory: "4Gi"
            cpu: "2000m"
        livenessProbe:
          httpGet:
            path: /
            port: 7860
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /
            port: 7860
          initialDelaySeconds: 10
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: agenticta
  namespace: wwfo-self-ta
spec:
  selector:
    app: agenticta
  ports:
  - protocol: TCP
    port: 80
    targetPort: 7860
  type: LoadBalancer
```

Deploy:
```bash
kubectl apply -f deployment.yaml
```

---

## CI/CD Integration

### GitLab CI/CD

```yaml
# .gitlab-ci.yml
variables:
  IMAGE_NAME: nvcr.io/nvstaging/agenticta
  DOCKER_DRIVER: overlay2

stages:
  - build
  - test
  - push
  - deploy

build:
  stage: build
  image: docker:latest
  services:
    - docker:dind
  script:
    - docker build -f Dockerfile.prod -t $IMAGE_NAME:$CI_COMMIT_SHA .
    - docker tag $IMAGE_NAME:$CI_COMMIT_SHA $IMAGE_NAME:latest
    - docker save $IMAGE_NAME:$CI_COMMIT_SHA -o image.tar
  artifacts:
    paths:
      - image.tar
    expire_in: 1 hour

test:
  stage: test
  image: docker:latest
  services:
    - docker:dind
  script:
    - docker load -i image.tar
    - docker run --rm $IMAGE_NAME:$CI_COMMIT_SHA python -m pytest tests/
  dependencies:
    - build

push:
  stage: push
  image: docker:latest
  services:
    - docker:dind
  script:
    - echo $DOCKER_REGISTRY_TOKEN | docker login -u '$oauthtoken' --password-stdin nvcr.io
    - docker load -i image.tar
    - docker push $IMAGE_NAME:$CI_COMMIT_SHA
    - docker push $IMAGE_NAME:latest
  dependencies:
    - build
  only:
    - main

deploy_staging:
  stage: deploy
  script:
    - kubectl set image deployment/agenticta agenticta=$IMAGE_NAME:$CI_COMMIT_SHA
    - kubectl rollout status deployment/agenticta
  environment:
    name: staging
  only:
    - main

deploy_production:
  stage: deploy
  script:
    - kubectl set image deployment/agenticta agenticta=$IMAGE_NAME:$CI_COMMIT_SHA
    - kubectl rollout status deployment/agenticta
  environment:
    name: production
  when: manual
  only:
    - main
```

---

## Security Checklist

Before pushing to Artifactory:

```bash
# 1. Check for secrets in image
docker run --rm nvcr.io/nvstaging/agenticta:latest env
# Should NOT see: VAULT_TOKEN, NVIDIA_API_KEY, etc.

# 2. Verify .dockerignore is working
docker build -f Dockerfile.prod -t test-build . 2>&1 | grep "Sending build context"
# Should be < 50MB (not including large PDFs, .git, etc.)

# 3. Check image size
docker images nvcr.io/nvstaging/agenticta:latest
# Should be ~2GB (reasonable for Python + ML libs)

# 4. Scan for vulnerabilities (optional)
docker scout cves nvcr.io/nvstaging/agenticta:latest

# 5. Test run without volumes
docker run --rm \
  -e VAULT_TOKEN=$VAULT_TOKEN \
  -e VAULT_ADDR=https://stg.internal.vault.nvidia.com \
  -e VAULT_NAMESPACE=wwfo-self-ta \
  nvcr.io/nvstaging/agenticta:latest \
  python -c "import vault; print('Vault imported successfully')"
```

---

## Troubleshooting

### Issue: "No such file or directory" when running image

**Cause:** Files not copied into image

**Solution:**
```bash
# Check what's in the image
docker run --rm nvcr.io/nvstaging/agenticta:latest ls -la /workspace

# Rebuild with Dockerfile.prod
docker build -f Dockerfile.prod -t agenticta:latest .
```

### Issue: "Cannot import module 'vault'"

**Cause:** Directory not copied or PYTHONPATH issue

**Solution:**
```dockerfile
# In Dockerfile.prod, ensure:
COPY vault/ /workspace/vault/
WORKDIR /workspace
```

### Issue: Image size too large (>5GB)

**Cause:** Including unnecessary files (PDFs, .git, volumes)

**Solution:**
```bash
# Check .dockerignore includes:
# - mnt/
# - volumes/
# - .git/
# - *.pdf
# - test_pdfs/
```

### Issue: Secrets visible in image

**Cause:** .env files copied into image

**Solution:**
```bash
# Ensure .dockerignore has:
.env
.env.*
env.vault-*

# Verify:
docker run --rm nvcr.io/nvstaging/agenticta:latest cat .env
# Should error: "No such file"
```

---

## Version Management

### Semantic Versioning

```bash
# Major version: Breaking changes
VERSION=2.0.0
docker tag agenticta:latest nvcr.io/nvstaging/agenticta:$VERSION

# Minor version: New features
VERSION=1.1.0
docker tag agenticta:latest nvcr.io/nvstaging/agenticta:$VERSION

# Patch version: Bug fixes
VERSION=1.0.1
docker tag agenticta:latest nvcr.io/nvstaging/agenticta:$VERSION
```

### Tagging Strategy

```bash
# Always maintain:
# 1. Specific version
docker push nvcr.io/nvstaging/agenticta:1.0.0

# 2. Latest (for testing)
docker push nvcr.io/nvstaging/agenticta:latest

# 3. Git commit SHA (traceability)
docker tag agenticta:latest nvcr.io/nvstaging/agenticta:$(git rev-parse --short HEAD)
docker push nvcr.io/nvstaging/agenticta:$(git rev-parse --short HEAD)

# 4. Environment-specific (optional)
docker tag agenticta:latest nvcr.io/nvstaging/agenticta:staging
docker tag agenticta:latest nvcr.io/nvstaging/agenticta:prod
```

---

## Quick Reference

### Build & Push Commands

```bash
# Complete workflow
docker build -f Dockerfile.prod -t agenticta:latest .
docker tag agenticta:latest nvcr.io/nvstaging/agenticta:1.0.0
docker tag agenticta:latest nvcr.io/nvstaging/agenticta:latest
docker push nvcr.io/nvstaging/agenticta:1.0.0
docker push nvcr.io/nvstaging/agenticta:latest
```

### Pull & Run Commands

```bash
# Pull and run
docker pull nvcr.io/nvstaging/agenticta:latest
docker run -d \
  -p 7860:7860 \
  -e VAULT_TOKEN=$VAULT_TOKEN \
  -e VAULT_ADDR=https://prod.internal.vault.nvidia.com \
  -e VAULT_NAMESPACE=wwfo-self-ta \
  nvcr.io/nvstaging/agenticta:latest
```

---

## Summary

| Aspect | Development | Production (Artifactory) |
|--------|-------------|-------------------------|
| **Code Location** | Volume mount | Baked into image |
| **Secrets** | .env file | Runtime injection |
| **Build Time** | Fast (no code copy) | Slower (full build) |
| **Image Size** | ~1.5GB | ~2.1GB |
| **Portability** | Low | High |
| **Security** | Lower | Higher |
| **Use Case** | Local dev | Staging/Production |

**Key Points:**
1. ✅ Use `Dockerfile.prod` for Artifactory builds
2. ✅ All Python code baked into image
3. ✅ Secrets injected at runtime (NOT in image)
4. ✅ Use `.dockerignore` to exclude sensitive files
5. ✅ Tag with version numbers for traceability
6. ✅ Test image before pushing to production

---

**Next Steps:**
1. Build production image: `docker build -f Dockerfile.prod -t agenticta:latest .`
2. Test locally: `docker run --rm agenticta:latest python -c "import vault; print('OK')"`
3. Tag for Artifactory: `docker tag agenticta:latest nvcr.io/nvstaging/agenticta:1.0.0`
4. Push: `docker push nvcr.io/nvstaging/agenticta:1.0.0`
5. Deploy: See "Running Production Image" section above

