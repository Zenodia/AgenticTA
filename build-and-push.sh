#!/bin/bash
# Build and push AgenticTA to NVIDIA Artifactory
# Usage: ./build-and-push.sh [VERSION]

set -e  # Exit on error

# Configuration
IMAGE_NAME="agenticta"
REGISTRY="artifactory.nvidia.com/it-continum"
VERSION="${1:-latest}"

echo "=========================================="
echo "Building AgenticTA for Artifactory"
echo "=========================================="
echo "Image: $REGISTRY/$IMAGE_NAME:$VERSION"
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Error: Docker is not running"
    exit 1
fi

# Check if .dockerignore exists
if [ ! -f ".dockerignore" ]; then
    echo "⚠️  Warning: .dockerignore not found"
    echo "   This may include sensitive files in the image!"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Step 1: Build image
echo "📦 Step 1/4: Building Docker image..."
docker build -f Dockerfile.prod -t $IMAGE_NAME:$VERSION .

if [ $? -ne 0 ]; then
    echo "❌ Build failed!"
    exit 1
fi

echo "✅ Build successful"
echo ""

# Step 2: Tag for Artifactory
echo "🏷️  Step 2/4: Tagging image..."
docker tag $IMAGE_NAME:$VERSION $REGISTRY/$IMAGE_NAME:$VERSION

if [ "$VERSION" != "latest" ]; then
    docker tag $IMAGE_NAME:$VERSION $REGISTRY/$IMAGE_NAME:latest
    echo "   Tagged: $REGISTRY/$IMAGE_NAME:$VERSION"
    echo "   Tagged: $REGISTRY/$IMAGE_NAME:latest"
else
    echo "   Tagged: $REGISTRY/$IMAGE_NAME:latest"
fi
echo ""

# Step 3: Security check
echo "🔒 Step 3/4: Running security checks..."
echo "   Checking image size..."
SIZE=$(docker images $IMAGE_NAME:$VERSION --format "{{.Size}}")
echo "   Image size: $SIZE"

echo "   Checking for secrets in environment..."
# Temporarily allow grep to return non-zero (when no secrets found, that's good!)
set +e
SECRETS=$(docker run --rm $IMAGE_NAME:$VERSION env | grep -iE "(token|password|secret|key)" | grep -v "VAULT_ADDR" | grep -v "VAULT_MOUNT_POINT" | grep -v "GPG_KEY")
set -e
SECRETS_FOUND=$(echo "$SECRETS" | grep -v '^$' | wc -l)
if [ "$SECRETS_FOUND" -gt 0 ]; then
    echo "   ⚠️  WARNING: Found $SECRETS_FOUND potential secrets in environment!"
    echo ""
    echo "   Secrets found:"
    echo "$SECRETS" | sed 's/^/     /'
    echo ""
    read -p "   Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    echo "   ✅ No hardcoded secrets detected"
fi
echo ""

# Step 4: Push to Artifactory
echo "📤 Step 4/4: Pushing to Artifactory..."
echo "   Checking Docker login..."

# Check if credentials exist in docker config
if [ -f ~/.docker/config.json ]; then
    if grep -q "artifactory.nvidia.com" ~/.docker/config.json 2>/dev/null; then
        echo "   ✅ Logged in to artifactory.nvidia.com"
    else
        echo "   ⚠️  Not logged in to artifactory.nvidia.com"
        echo "   Please run: docker login artifactory.nvidia.com"
        echo "   Username: <your-nvidia-username>"
        echo "   Password: <your-artifactory-token>"
        exit 1
    fi
else
    echo "   ⚠️  Docker config not found. Please login first."
    echo "   Run: docker login artifactory.nvidia.com"
    exit 1
fi

echo "   Pushing $REGISTRY/$IMAGE_NAME:$VERSION..."
docker push $REGISTRY/$IMAGE_NAME:$VERSION

if [ "$VERSION" != "latest" ]; then
    echo "   Pushing $REGISTRY/$IMAGE_NAME:latest..."
    docker push $REGISTRY/$IMAGE_NAME:latest
fi

echo ""
echo "=========================================="
echo "✅ SUCCESS!"
echo "=========================================="
echo ""
echo "Image pushed to:"
echo "  • $REGISTRY/$IMAGE_NAME:$VERSION"
if [ "$VERSION" != "latest" ]; then
    echo "  • $REGISTRY/$IMAGE_NAME:latest"
fi
echo ""
echo "To deploy:"
echo "  # Set your Vault address (staging or production):"
echo "  export VAULT_ADDR=https://stg.internal.vault.nvidia.com   # Staging"
echo "  # export VAULT_ADDR=https://prod.internal.vault.nvidia.com  # Production"
echo ""
echo "  docker pull $REGISTRY/$IMAGE_NAME:$VERSION"
echo "  docker run -d -p 7860:7860 \\"
echo "    -e VAULT_TOKEN=\\\$VAULT_TOKEN \\"
echo "    -e VAULT_ADDR=\\\$VAULT_ADDR \\"
echo "    -e VAULT_NAMESPACE=wwfo-self-ta \\"
echo "    -e VAULT_MOUNT_POINT=secret \\"
echo "    $REGISTRY/$IMAGE_NAME:$VERSION"
echo ""

