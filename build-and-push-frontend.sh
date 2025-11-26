#!/bin/bash
# Build and push frontend Docker image to Artifactory
# Usage: ./build-and-push-frontend.sh [VERSION]
#   VERSION: Version tag to build and push (default: latest)
#
# Example:
#   ./build-and-push-frontend.sh 0.0.17
#   ./build-and-push-frontend.sh latest

set -e  # Exit on error

# Configuration
LOCAL_IMAGE_NAME="agenticta-frontend"
REGISTRY="artifactory.nvidia.com/it-continum"
REPOSITORY="agenticta"
IMAGE_NAME="frontend"
DOCKERFILE="Dockerfile.prod"
VERSION="${1:-latest}"

# Full image paths
# Format: artifactory.nvidia.com/it-continum/agenticta/frontend:VERSION
FULL_IMAGE_TAG="$REGISTRY/$REPOSITORY/$IMAGE_NAME"
LOCAL_TAG="$LOCAL_IMAGE_NAME"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "=========================================="
echo "Build and Push AgenticTA Frontend"
echo "=========================================="
echo "Version: $VERSION"
echo "Local image: $LOCAL_TAG:$VERSION"
echo "Registry: $REGISTRY"
echo "Repository: $REPOSITORY"
echo "Image name: $IMAGE_NAME"
echo "Full tag: $FULL_IMAGE_TAG:$VERSION"
echo ""

# ==========================================
# Step 1: Pre-flight checks
# ==========================================
echo -e "${GREEN}🔍 Step 1/6: Pre-flight checks...${NC}"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}❌ Error: Docker is not running${NC}"
    exit 1
fi
echo "   ✅ Docker is running"

# Check if Dockerfile exists
if [ ! -f "$DOCKERFILE" ]; then
    echo -e "${RED}❌ Error: Dockerfile not found: $DOCKERFILE${NC}"
    exit 1
fi
echo "   ✅ Dockerfile found: $DOCKERFILE"

# Check if frontendUI directory exists
if [ ! -d "frontendUI" ]; then
    echo -e "${RED}❌ Error: frontendUI directory not found${NC}"
    echo "   Make sure you're running this script from the AgenticTA root directory"
    exit 1
fi
echo "   ✅ frontendUI directory found"

# Check if .dockerignore exists
if [ ! -f ".dockerignore" ]; then
    echo -e "${YELLOW}⚠️  Warning: .dockerignore not found${NC}"
    echo "   This may include sensitive files in the image!"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    echo "   ✅ .dockerignore found"
fi
echo ""

# ==========================================
# Step 2: Build Docker image
# ==========================================
echo -e "${GREEN}📦 Step 2/6: Building Docker image...${NC}"
echo "   Command: docker build -f $DOCKERFILE -t $LOCAL_TAG:$VERSION ."
echo ""

docker build -f "$DOCKERFILE" -t "$LOCAL_TAG:$VERSION" .

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Build failed!${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}✅ Build successful${NC}"

# Display image info
SIZE=$(docker images "$LOCAL_TAG:$VERSION" --format "{{.Size}}")
IMAGE_ID=$(docker images "$LOCAL_TAG:$VERSION" --format "{{.ID}}")
CREATED=$(docker images "$LOCAL_TAG:$VERSION" --format "{{.CreatedAt}}")

echo "   Image ID: $IMAGE_ID"
echo "   Size: $SIZE"
echo "   Created: $CREATED"
echo ""

# ==========================================
# Step 3: Check Docker authentication
# ==========================================
echo -e "${GREEN}🔐 Step 3/6: Checking Docker authentication...${NC}"

if [ -f ~/.docker/config.json ]; then
    if grep -q "$REGISTRY" ~/.docker/config.json 2>/dev/null; then
        echo -e "   ${GREEN}✅ Logged in to $REGISTRY${NC}"
    else
        echo -e "${YELLOW}⚠️  Not logged in to $REGISTRY${NC}"
        echo "   Please run: docker login $REGISTRY"
        echo "   Username: <your-nvidia-username>"
        echo "   Password: <your-artifactory-token>"
        echo ""
        read -p "Continue anyway? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
else
    echo -e "${YELLOW}⚠️  Docker config not found.${NC}"
    echo "   Please login first: docker login $REGISTRY"
    exit 1
fi
echo ""

# ==========================================
# Step 4: Tag image for Artifactory
# ==========================================
echo -e "${GREEN}🏷️  Step 4/6: Tagging image for Artifactory...${NC}"
echo "   Tagging: $LOCAL_TAG:$VERSION -> $FULL_IMAGE_TAG:$VERSION"

docker tag "$LOCAL_TAG:$VERSION" "$FULL_IMAGE_TAG:$VERSION"

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Tagging failed!${NC}"
    exit 1
fi

# Also tag as latest if version is not "latest"
if [ "$VERSION" != "latest" ]; then
    echo "   Tagging: $LOCAL_TAG:$VERSION -> $FULL_IMAGE_TAG:latest"
    docker tag "$LOCAL_TAG:$VERSION" "$FULL_IMAGE_TAG:latest"
fi

echo -e "   ${GREEN}✅ Tagging successful${NC}"
echo ""

# ==========================================
# Step 5: Security checks
# ==========================================
echo -e "${GREEN}🔒 Step 5/6: Running security checks...${NC}"
echo "   Checking image size..."
SIZE=$(docker images "$LOCAL_TAG:$VERSION" --format "{{.Size}}")
echo "   Image size: $SIZE"

# Check for potential secrets in environment (non-blocking)
echo "   Checking for hardcoded secrets..."
set +e
SECRETS=$(docker run --rm "$LOCAL_TAG:$VERSION" env 2>/dev/null | grep -iE "(token|password|secret|key)" | grep -v "VAULT_ADDR" | grep -v "VAULT_MOUNT_POINT" | grep -v "GPG_KEY" | grep -v "PATH" || true)
set -e
SECRETS_FOUND=$(echo "$SECRETS" | grep -v '^$' | wc -l)
if [ "$SECRETS_FOUND" -gt 0 ]; then
    echo -e "   ${YELLOW}⚠️  WARNING: Found $SECRETS_FOUND potential secrets in environment!${NC}"
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
    echo -e "   ${GREEN}✅ No hardcoded secrets detected${NC}"
fi
echo ""

# ==========================================
# Step 6: Push to Artifactory
# ==========================================
echo -e "${GREEN}📤 Step 6/6: Pushing to Artifactory...${NC}"
echo "   Pushing: $FULL_IMAGE_TAG:$VERSION"

docker push "$FULL_IMAGE_TAG:$VERSION"

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Push failed!${NC}"
    exit 1
fi

if [ "$VERSION" != "latest" ]; then
    echo "   Pushing: $FULL_IMAGE_TAG:latest"
    docker push "$FULL_IMAGE_TAG:latest"
fi

echo ""
echo "=========================================="
echo -e "${GREEN}✅ SUCCESS!${NC}"
echo "=========================================="
echo ""
echo "Image pushed to:"
echo -e "   ${BLUE}• $FULL_IMAGE_TAG:$VERSION${NC}"
if [ "$VERSION" != "latest" ]; then
    echo -e "   ${BLUE}• $FULL_IMAGE_TAG:latest${NC}"
fi
echo ""
echo "To update deployment:"
echo "   Update values.yaml in agenticta-deploy:"
echo "     image:"
echo "       repository: $REGISTRY/$REPOSITORY"
echo "       name: $IMAGE_NAME"
echo "       tag: $VERSION"
echo ""
echo "To verify:"
echo "   docker pull $FULL_IMAGE_TAG:$VERSION"
echo ""
