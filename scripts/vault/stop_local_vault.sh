#!/bin/bash
# Stop Local Vault Development Server

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"

echo -e "${BLUE}Stopping Local Vault Development Server...${NC}"

cd "$PROJECT_ROOT"

# Stop and remove container
docker compose -f docker-compose.vault-dev.yml down

echo -e "${GREEN}✓ Vault container stopped${NC}"
echo ""
echo -e "${YELLOW}Note: Vault data is preserved in Docker volume 'agenticta-vault-dev-data'${NC}"
echo -e "${YELLOW}To completely remove data: docker volume rm agenticta-vault-dev-data${NC}"
echo ""
echo -e "${BLUE}To restart Vault:${NC}"
echo -e "  ${YELLOW}./scripts/vault/start_local_vault.sh${NC}"

