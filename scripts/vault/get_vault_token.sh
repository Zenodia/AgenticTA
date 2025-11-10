#!/bin/bash
# Get Vault Token from NVIDIA Vault using OIDC Authentication
# This script helps you authenticate and get a Vault token

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

ENV=${1:-staging}

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║        Get NVIDIA Vault Token via OIDC                    ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if vault CLI is installed
if ! command -v vault &> /dev/null; then
    echo -e "${RED}✗ Vault CLI is not installed${NC}"
    echo -e ""
    echo -e "${YELLOW}To install Vault CLI:${NC}"
    echo -e ""
    echo -e "  ${GREEN}# macOS${NC}"
    echo -e "  brew install vault"
    echo -e ""
    echo -e "  ${GREEN}# Linux${NC}"
    echo -e "  wget https://releases.hashicorp.com/vault/1.15.0/vault_1.15.0_linux_amd64.zip"
    echo -e "  unzip vault_1.15.0_linux_amd64.zip"
    echo -e "  sudo mv vault /usr/local/bin/"
    echo -e ""
    exit 1
fi

# Function to get vault token for an environment
get_vault_token() {
    local env_name=$1
    local vault_addr=$2
    local env_display=$3
    
    echo -e "${BLUE}Environment: ${GREEN}${env_display}${NC}"
    echo -e ""
    
    # Production confirmation
    if [ "$env_name" = "prod" ]; then
        echo -e "${YELLOW}⚠️  WARNING: You are about to access PRODUCTION Vault${NC}"
        echo -e "${YELLOW}   This should only be used for production deployments.${NC}"
        echo -e ""
        read -p "$(echo -e ${YELLOW}Are you sure you want to continue? [y/N]: ${NC})" -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo -e "${YELLOW}Cancelled.${NC}"
            exit 0
        fi
        echo -e ""
    fi
    
    echo -e "${YELLOW}Running OIDC authentication...${NC}"
    echo -e ""
    
    export VAULT_ADDR="${vault_addr}"
    export VAULT_NAMESPACE=wwfo-self-ta
    # Unset any existing token to avoid conflicts
    unset VAULT_TOKEN
    
    echo -e "${GREEN}export VAULT_ADDR=${vault_addr}${NC}"
    echo -e "${GREEN}export VAULT_NAMESPACE=wwfo-self-ta${NC}"
    echo -e "${GREEN}vault login -method=oidc -path=oidc-admins role=namespace-admin${NC}"
    echo -e ""
    echo -e "${YELLOW}This will open a browser for NVIDIA SSO authentication...${NC}"
    echo -e ""
    
    # Run vault login
    vault login -method=oidc -path=oidc-admins role=namespace-admin
    
    # Get the token from where vault CLI stores it
    TOKEN=$(cat ~/.vault-token 2>/dev/null)
    
    if [ -n "$TOKEN" ]; then
        echo -e ""
        echo -e "${GREEN}✓ Successfully authenticated!${NC}"
        echo -e ""
        echo -e "${BLUE}Your Vault Token:${NC}"
        echo -e "  ${GREEN}${TOKEN}${NC}"
        echo -e ""
        echo -e "${BLUE}Add this to your .env file:${NC}"
        echo -e "  ${YELLOW}VAULT_TOKEN=${TOKEN}${NC}"
        echo -e ""
        
        # Offer to add to .env
        read -p "$(echo -e ${YELLOW}Add token to .env file now? [Y/n]: ${NC})" -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]] || [[ -z $REPLY ]]; then
            if grep -q "^VAULT_TOKEN=" "$PROJECT_ROOT/.env" 2>/dev/null; then
                # Replace existing token
                sed -i.bak "s|^VAULT_TOKEN=.*|VAULT_TOKEN=${TOKEN}|" "$PROJECT_ROOT/.env"
                echo -e "${GREEN}✓ Updated VAULT_TOKEN in .env${NC}"
            else
                # Add new token
                echo "" >> "$PROJECT_ROOT/.env"
                echo "# NVIDIA Vault Token (${env_display})" >> "$PROJECT_ROOT/.env"
                echo "VAULT_TOKEN=${TOKEN}" >> "$PROJECT_ROOT/.env"
                echo -e "${GREEN}✓ Added VAULT_TOKEN to .env${NC}"
            fi
        fi
    else
        echo -e "${RED}✗ Failed to get token${NC}"
        exit 1
    fi
}

case "$ENV" in
    staging|stg)
        get_vault_token "staging" "https://stg.internal.vault.nvidia.com" "STAGING"
        ;;
        
    prod|production)
        get_vault_token "prod" "https://prod.internal.vault.nvidia.com" "PRODUCTION"
        ;;
        
    *)
        echo -e "${RED}✗ Invalid environment: $ENV${NC}"
        echo -e ""
        echo -e "${BLUE}Usage:${NC} $0 {staging|prod}"
        echo -e ""
        echo -e "${BLUE}Examples:${NC}"
        echo -e "  $0 staging    # Get staging token"
        echo -e "  $0 prod       # Get production token"
        exit 1
        ;;
esac

echo -e ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║              Token Saved Successfully!                    ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo -e ""
echo -e "${BLUE}✓ Token saved to:${NC} .env"
echo -e ""

# Automatically create .env.vault-local
echo -e "${BLUE}Creating .env.vault-local...${NC}"
"$SCRIPT_DIR/switch_vault.sh" "$ENV" > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Created .env.vault-local${NC}"
    echo -e ""
    echo -e "${YELLOW}⚠️  IMPORTANT: Run this command to activate:${NC}"
    echo -e "  ${GREEN}source .env.vault-local${NC}"
    echo -e ""
    echo -e "${BLUE}Then test it:${NC}"
    echo -e "  ${YELLOW}python scripts/vault/vault_health_check.py${NC}"
else
    echo -e "${YELLOW}⚠ Could not automatically create .env.vault-local${NC}"
    echo -e ""
    echo -e "${YELLOW}⚠️  IMPORTANT: Run these commands manually:${NC}"
    echo -e ""
    echo -e "  1. ${GREEN}./scripts/vault/switch_vault.sh $ENV${NC}"
    echo -e "  2. ${GREEN}source .env.vault-local${NC}"
    echo -e "  3. ${GREEN}python scripts/vault/vault_health_check.py${NC}"
fi
echo -e ""

