#!/bin/bash
# Switch between Local and Production Vault
# Usage: ./switch_vault.sh [local|prod|staging]

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

MODE=${1:-}

if [ -z "$MODE" ]; then
    echo -e "${BLUE}Current Vault Configuration:${NC}"
    if [ -f "$PROJECT_ROOT/.env.vault-local" ]; then
        source "$PROJECT_ROOT/.env.vault-local"
        echo -e "  VAULT_ADDR: ${GREEN}${VAULT_ADDR}${NC}"
        echo -e "  VAULT_NAMESPACE: ${GREEN}${VAULT_NAMESPACE:-<none>}${NC}"
    else
        echo -e "  ${YELLOW}No active configuration${NC}"
    fi
    echo ""
    echo -e "${BLUE}Usage:${NC} $0 {local|staging|prod}"
    echo ""
    echo -e "${BLUE}Modes:${NC}"
    echo -e "  ${GREEN}local${NC}    - Use local Vault dev server (http://localhost:8200)"
    echo -e "  ${GREEN}staging${NC}  - Use NVIDIA staging Vault (stg.internal.vault.nvidia.com)"
    echo -e "  ${GREEN}prod${NC}     - Use NVIDIA production Vault (internal.vault.nvidia.com)"
    exit 0
fi

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║              Switching Vault Configuration                ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

case "$MODE" in
    local)
        echo -e "${BLUE}Switching to LOCAL Vault...${NC}"
        
        # Check if local Vault is running
        if ! docker ps | grep -q agenticta-vault-dev; then
            echo -e "${YELLOW}⚠ Local Vault not running. Starting it...${NC}"
            "$SCRIPT_DIR/start_local_vault.sh"
        fi
        
        cat > "$PROJECT_ROOT/.env.vault-local" << 'EOF'
# Local Vault Development Server Configuration
export VAULT_ADDR='http://localhost:8200'
export VAULT_TOKEN='dev-root-token-agenticta'
export VAULT_NAMESPACE=''

# For Python scripts (without export)
VAULT_ADDR=http://localhost:8200
VAULT_TOKEN=dev-root-token-agenticta
VAULT_NAMESPACE=
EOF
        
        echo -e "${GREEN}✓ Configured for LOCAL Vault${NC}"
        echo -e "  Address: ${GREEN}http://localhost:8200${NC}"
        echo -e "  UI: ${GREEN}http://localhost:8200/ui${NC}"
        ;;
        
    staging|stg)
        echo -e "${BLUE}Switching to STAGING Vault...${NC}"
        
        # Check if VAULT_TOKEN is set in .env
        if [ -f "$PROJECT_ROOT/.env" ]; then
            source "$PROJECT_ROOT/.env"
        fi
        
        if [ -z "$VAULT_TOKEN" ]; then
            echo -e "${RED}✗ VAULT_TOKEN not found in .env file${NC}"
            echo -e ""
            echo -e "${YELLOW}To get a STAGING Vault token, run these commands:${NC}"
            echo -e ""
            echo -e "  ${GREEN}export VAULT_ADDR=https://stg.internal.vault.nvidia.com${NC}"
            echo -e "  ${GREEN}export VAULT_NAMESPACE=wwfo-self-ta${NC}"
            echo -e "  ${GREEN}vault login -method=oidc -path=oidc-admins role=namespace-admin${NC}"
            echo -e ""
            echo -e "${YELLOW}This will open a browser for NVIDIA SSO authentication.${NC}"
            echo -e "${YELLOW}After login, copy the token and add it to .env:${NC}"
            echo -e "  VAULT_TOKEN=hvs.YOUR_TOKEN_HERE"
            echo -e ""
            echo -e "${BLUE}Alternative: Get token from UI:${NC} https://stg.internal.vault.nvidia.com/ui/"
            exit 1
        fi
        
        cat > "$PROJECT_ROOT/.env.vault-local" << EOF
# NVIDIA Staging Vault Configuration
export VAULT_ADDR='https://stg.internal.vault.nvidia.com'
export VAULT_TOKEN='${VAULT_TOKEN}'
export VAULT_NAMESPACE='wwfo-self-ta'

# For Python scripts (without export)
VAULT_ADDR=https://stg.internal.vault.nvidia.com
VAULT_TOKEN=${VAULT_TOKEN}
VAULT_NAMESPACE=wwfo-self-ta
EOF
        
        echo -e "${GREEN}✓ Configured for STAGING Vault${NC}"
        echo -e "  Address: ${GREEN}https://stg.internal.vault.nvidia.com${NC}"
        echo -e "  Namespace: ${GREEN}wwfo-self-ta${NC}"
        ;;
        
    prod|production)
        echo -e "${BLUE}Switching to PRODUCTION Vault...${NC}"
        
        # Check if VAULT_TOKEN is set in .env
        if [ -f "$PROJECT_ROOT/.env" ]; then
            source "$PROJECT_ROOT/.env"
        fi
        
        if [ -z "$VAULT_TOKEN" ]; then
            echo -e "${RED}✗ VAULT_TOKEN not found in .env file${NC}"
            echo -e ""
            echo -e "${YELLOW}To get a PRODUCTION Vault token, run these commands:${NC}"
            echo -e ""
            echo -e "  ${GREEN}export VAULT_ADDR=https://prod.internal.vault.nvidia.com${NC}"
            echo -e "  ${GREEN}export VAULT_NAMESPACE=wwfo-self-ta${NC}"
            echo -e "  ${GREEN}vault login -method=oidc -path=oidc-admins role=namespace-admin${NC}"
            echo -e ""
            echo -e "${YELLOW}This will open a browser for NVIDIA SSO authentication.${NC}"
            echo -e "${YELLOW}After login, copy the token and add it to .env:${NC}"
            echo -e "  VAULT_TOKEN=hvs.YOUR_TOKEN_HERE"
            echo -e ""
            echo -e "${BLUE}Alternative: Get token from UI:${NC} https://prod.internal.vault.nvidia.com/ui/"
            exit 1
        fi
        
        cat > "$PROJECT_ROOT/.env.vault-local" << EOF
# NVIDIA Production Vault Configuration
export VAULT_ADDR='https://internal.vault.nvidia.com'
export VAULT_TOKEN='${VAULT_TOKEN}'
export VAULT_NAMESPACE='wwfo-self-ta'

# For Python scripts (without export)
VAULT_ADDR=https://internal.vault.nvidia.com
VAULT_TOKEN=${VAULT_TOKEN}
VAULT_NAMESPACE=wwfo-self-ta
EOF
        
        echo -e "${GREEN}✓ Configured for PRODUCTION Vault${NC}"
        echo -e "  Address: ${GREEN}https://internal.vault.nvidia.com${NC}"
        echo -e "  Namespace: ${GREEN}wwfo-self-ta${NC}"
        echo -e ""
        echo -e "${RED}⚠ WARNING: You are using PRODUCTION Vault!${NC}"
        echo -e "${RED}  Be careful with operations that modify secrets.${NC}"
        ;;
        
    *)
        echo -e "${RED}✗ Invalid mode: $MODE${NC}"
        echo -e "${BLUE}Usage:${NC} $0 {local|staging|prod}"
        exit 1
        ;;
esac

echo ""
echo -e "${BLUE}Configuration saved to:${NC} .env.vault-local"
echo ""
echo -e "${BLUE}To activate in current shell:${NC}"
echo -e "  ${YELLOW}source .env.vault-local${NC}"
echo ""
echo -e "${BLUE}To verify:${NC}"
echo -e "  ${YELLOW}python scripts/vault/vault_health_check.py${NC}"
echo ""

# Optionally activate now
read -p "$(echo -e ${YELLOW}Activate configuration now? [Y/n]: ${NC})" -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]] || [[ -z $REPLY ]]; then
    source "$PROJECT_ROOT/.env.vault-local"
    echo -e "${GREEN}✓ Configuration activated${NC}"
    echo ""
    python "$SCRIPT_DIR/vault_health_check.py"
fi

