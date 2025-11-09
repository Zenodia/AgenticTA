#!/bin/bash
# Start Local Vault Development Server
# This script starts a local Vault instance and configures it with your secrets

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     Starting Local Vault Development Server               ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}✗ Docker is not running. Please start Docker first.${NC}"
    exit 1
fi

# Check if .env file exists
if [ ! -f "$PROJECT_ROOT/.env" ]; then
    echo -e "${YELLOW}⚠ .env file not found. Creating from template...${NC}"
    if [ -f "$SCRIPT_DIR/env.template" ]; then
        cp "$SCRIPT_DIR/env.template" "$PROJECT_ROOT/.env"
        echo -e "${GREEN}✓ Created .env from template${NC}"
        echo -e "${YELLOW}  Please edit .env and add your secrets before running migration${NC}"
    else
        echo -e "${RED}✗ env.template not found${NC}"
        exit 1
    fi
fi

# Start Vault container
echo -e "${BLUE}Starting Vault container...${NC}"
cd "$PROJECT_ROOT"
docker compose -f docker-compose.vault-dev.yml up -d

# Wait for Vault to be ready
echo -e "${BLUE}Waiting for Vault to be ready...${NC}"
for i in {1..30}; do
    if docker exec -e VAULT_ADDR='http://127.0.0.1:8200' agenticta-vault-dev vault status > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Vault is ready${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${RED}✗ Vault failed to start after 30 seconds${NC}"
        docker compose -f docker-compose.vault-dev.yml logs vault-dev
        exit 1
    fi
    echo -n "."
    sleep 1
done
echo ""

# Set environment variables for this session
export VAULT_ADDR='http://localhost:8200'
export VAULT_TOKEN='dev-root-token-agenticta'
export VAULT_NAMESPACE=''

# Create .env.vault-local for persistence
echo -e "${BLUE}Creating .env.vault-local...${NC}"
cat > "$PROJECT_ROOT/.env.vault-local" << EOF
# Local Vault Development Server Configuration
# Source this file to use local Vault: source .env.vault-local

export VAULT_ADDR='http://localhost:8200'
export VAULT_TOKEN='dev-root-token-agenticta'
export VAULT_NAMESPACE=''

# For Python scripts (without export)
VAULT_ADDR=http://localhost:8200
VAULT_TOKEN=dev-root-token-agenticta
VAULT_NAMESPACE=
EOF

echo -e "${GREEN}✓ Created .env.vault-local${NC}"

# Enable KV v2 secrets engine
echo -e "${BLUE}Setting up KV v2 secrets engine...${NC}"
docker exec agenticta-vault-dev vault secrets enable -version=2 -path=secret kv 2>/dev/null || true
echo -e "${GREEN}✓ KV v2 secrets engine ready${NC}"
echo ""

# Wait for Vault to be accessible from host (not just inside container)
echo -e "${BLUE}Waiting for Vault to be accessible on localhost:8200...${NC}"
for i in {1..30}; do
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:8200/v1/sys/health | grep -q "20[03]"; then
        echo -e "${GREEN}✓ Vault is accessible from host${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${RED}✗ Vault failed to become accessible after 30 seconds${NC}"
        echo -e "${YELLOW}  Check port mapping: docker ps | grep vault${NC}"
        exit 1
    fi
    echo -n "."
    sleep 1
done
echo ""

# Auto-migrate secrets from .env if it exists
MIGRATION_SUCCESS=false
if [ -f "$PROJECT_ROOT/.env" ]; then
    echo -e "${BLUE}Migrating secrets from .env to Vault...${NC}"
    
    # Check if agenticta container is running
    if docker ps --filter "name=agenticta" --format "{{.Names}}" | grep -q "agenticta" 2>/dev/null; then
        echo -e "${BLUE}Running migration from agenticta container...${NC}"
        
        # Run migration inside agenticta container
        if docker compose -f "$PROJECT_ROOT/docker-compose.yml" exec -T \
            -e VAULT_ADDR=http://vault-dev:8200 \
            -e VAULT_TOKEN=dev-root-token-agenticta \
            -e VAULT_NAMESPACE='' \
            agenticta python scripts/vault/migrate_secrets_to_vault.py 2>&1 | tee /tmp/vault_migration.log | grep -q "Successfully migrated all secrets"; then
            echo -e "${GREEN}✓ Secrets migrated successfully${NC}"
            MIGRATION_SUCCESS=true
        else
            echo -e "${YELLOW}⚠ Migration failed or incomplete${NC}"
            echo -e "   ${YELLOW}Check logs: cat /tmp/vault_migration.log${NC}"
            echo -e "   ${YELLOW}Run manually: docker compose exec agenticta python scripts/vault/migrate_secrets_to_vault.py${NC}"
        fi
    else
        echo -e "${YELLOW}⚠ AgenticTA container not running - skipping auto-migration${NC}"
        echo -e "   ${YELLOW}Start container with: make up${NC}"
        echo -e "   ${YELLOW}Then run: docker compose exec agenticta python scripts/vault/migrate_secrets_to_vault.py${NC}"
        MIGRATION_SUCCESS=true  # Not a failure, just skip
    fi
else
    echo -e "${YELLOW}⚠ .env file not found, skipping migration${NC}"
    MIGRATION_SUCCESS=true  # Not an error if no .env
fi

# Display info
echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║          Local Vault Server Started Successfully!          ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}Vault Configuration:${NC}"
echo -e "  Address:   ${GREEN}http://localhost:8200${NC}"
echo -e "  Token:     ${GREEN}dev-root-token-agenticta${NC}"
echo -e "  UI:        ${GREEN}http://localhost:8200/ui${NC}"
echo -e "  Namespace: ${GREEN}(none - not used in dev mode)${NC}"
echo ""

# Run basic health check
echo -e "${BLUE}Running basic health check...${NC}"
export VAULT_ADDR='http://localhost:8200'
export VAULT_TOKEN='dev-root-token-agenticta'
export VAULT_NAMESPACE=''

HEALTH_SUCCESS=false

# Quick connectivity test
if docker exec -e VAULT_ADDR='http://127.0.0.1:8200' agenticta-vault-dev vault status > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Vault is responding${NC}"
    
    # Quick secret read test
    if docker exec -e VAULT_ADDR='http://127.0.0.1:8200' -e VAULT_TOKEN="dev-root-token-agenticta" agenticta-vault-dev \
        vault kv get secret/agenticta/api-keys > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Secrets are accessible${NC}"
        HEALTH_SUCCESS=true
    else
        echo -e "${RED}✗ Cannot read secrets from Vault${NC}"
        echo -e "   ${YELLOW}Run: make vault-check${NC}"
        HEALTH_SUCCESS=false
    fi
else
    echo -e "${RED}✗ Vault is not responding${NC}"
    echo -e "   ${YELLOW}Check container: docker ps | grep vault${NC}"
    HEALTH_SUCCESS=false
fi

# Overall status
echo ""
if [ "$MIGRATION_SUCCESS" = true ] && [ "$HEALTH_SUCCESS" = true ]; then
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                  ✅ All Checks Passed!                     ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${YELLOW}⚠️  IMPORTANT: To use Vault, run this in your terminal:${NC}"
    echo -e "${GREEN}    source .env.vault-local${NC}"
    echo ""
else
    echo -e "${YELLOW}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${YELLOW}║              ⚠️  Setup Complete with Warnings              ║${NC}"
    echo -e "${YELLOW}╚════════════════════════════════════════════════════════════╝${NC}"
    echo -e "${YELLOW}Run for full diagnostics: make vault-check${NC}"
    echo ""
    echo -e "${YELLOW}⚠️  To use Vault (if available), run:${NC}"
    echo -e "    ${YELLOW}source .env.vault-local${NC}"
    echo ""
fi

# Optionally run full health check (only if interactive)
if [ -t 0 ] && [ "$HEALTH_SUCCESS" = true ]; then
    read -p "$(echo -e ${YELLOW}Run full health check? [y/N]: ${NC})" -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo ""
        if docker ps --filter "name=agenticta" --format "{{.Names}}" | grep -q "agenticta" 2>/dev/null; then
            docker compose exec -e VAULT_ADDR=http://vault-dev:8200 -e VAULT_TOKEN=dev-root-token-agenticta agenticta python "$SCRIPT_DIR/vault_health_check.py"
        else
            echo -e "${YELLOW}⚠ AgenticTA container not running - start with 'make up' to run health check${NC}"
        fi
    fi
fi

echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                  ✅ Next Steps!                            ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${BLUE}1. Check secrets:${NC}"
echo -e "     ${YELLOW}make vault-check${NC}"
echo ""
echo -e "  ${BLUE}2. If secrets missing, migrate from .env:${NC}"
echo -e "     ${YELLOW}docker compose exec agenticta python scripts/vault/migrate_secrets_to_vault.py${NC}"
echo ""
echo -e "  ${BLUE}3. Stop Vault when done:${NC}"
echo -e "     ${YELLOW}make vault-dev-stop${NC}"
echo ""
