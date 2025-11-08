#!/bin/bash
# Setup NVIDIA Vault for AgenticTA
# This script sets up everything needed for a new namespace in NVIDIA Vault

set -e

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║        Setup NVIDIA Vault for AgenticTA                   ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if vault CLI is installed
if ! command -v vault &> /dev/null; then
    echo -e "${RED}✗ Vault CLI is not installed${NC}"
    echo -e "  Please install it first: brew install vault"
    exit 1
fi

# Check environment
if [ -z "$VAULT_ADDR" ] || [ -z "$VAULT_TOKEN" ] || [ -z "$VAULT_NAMESPACE" ]; then
    echo -e "${RED}✗ Vault environment not configured${NC}"
    echo -e ""
    echo -e "${YELLOW}Please set:${NC}"
    echo -e "  export VAULT_ADDR=https://stg.internal.vault.nvidia.com  # or prod"
    echo -e "  export VAULT_NAMESPACE=wwfo-self-ta"
    echo -e "  export VAULT_TOKEN=<your-token>"
    echo -e ""
    echo -e "${BLUE}Or run:${NC}"
    echo -e "  source .env.vault-local"
    exit 1
fi

echo -e "${GREEN}✓ Vault environment configured${NC}"
echo -e "  Address: ${VAULT_ADDR}"
echo -e "  Namespace: ${VAULT_NAMESPACE}"
echo ""

# Verify authentication
if ! vault token lookup > /dev/null 2>&1; then
    echo -e "${RED}✗ Not authenticated to Vault${NC}"
    echo -e "  Your token may be expired. Get a new one with:"
    echo -e "  ./scripts/vault/get_vault_token.sh staging"
    exit 1
fi

echo -e "${GREEN}✓ Authenticated to Vault${NC}"
echo ""

echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}Step 1: Enable KV Secrets Engine${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo ""

# Check if secret/ mount already exists
if vault secrets list | grep -q "^secret/"; then
    echo -e "${YELLOW}⚠  KV secrets engine already enabled at: secret/${NC}"
else
    echo -e "${BLUE}Enabling KV v2 secrets engine at: secret/${NC}"
    if vault secrets enable -version=2 -path=secret kv; then
        echo -e "${GREEN}✓ KV secrets engine enabled${NC}"
    else
        echo -e "${RED}✗ Failed to enable KV secrets engine${NC}"
        exit 1
    fi
fi
echo ""

echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}Step 2: Create Policy for Application Secrets${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo ""

POLICY_NAME="agenticta-secrets"
POLICY_FILE="/tmp/${POLICY_NAME}.hcl"

cat > "$POLICY_FILE" << 'EOF'
# Policy for AgenticTA application secrets
# Allows read/write to agenticta/* paths in the secret/ KV engine

# Allow full access to agenticta secrets
path "secret/data/agenticta/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}

# Allow listing agenticta paths
path "secret/metadata/agenticta/*" {
  capabilities = ["list", "read"]
}
EOF

echo -e "${BLUE}Creating policy: ${POLICY_NAME}${NC}"
if vault policy write "$POLICY_NAME" "$POLICY_FILE"; then
    echo -e "${GREEN}✓ Policy created${NC}"
    rm "$POLICY_FILE"
else
    echo -e "${RED}✗ Failed to create policy${NC}"
    rm "$POLICY_FILE"
    exit 1
fi
echo ""

echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}Step 3: Create Application Token${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo ""

echo -e "${YELLOW}Note: namespace-admin manages infrastructure but doesn't access data.${NC}"
echo -e "${YELLOW}We'll create a token with the agenticta-secrets policy for your app.${NC}"
echo ""

# Create a token with the agenticta-secrets policy
echo -e "${BLUE}Creating application token with agenticta-secrets policy...${NC}"
APP_TOKEN=$(vault token create \
    -policy=agenticta-secrets \
    -display-name="agenticta-app" \
    -ttl=720h \
    -format=json | jq -r '.auth.client_token')

if [ -n "$APP_TOKEN" ] && [ "$APP_TOKEN" != "null" ]; then
    echo -e "${GREEN}✓ Application token created${NC}"
    echo ""
    echo -e "${BLUE}Your AgenticTA Application Token:${NC}"
    echo -e "  ${APP_TOKEN}"
    echo ""
    
    # Offer to save to .env
    read -p "$(echo -e ${YELLOW}Save this token to .env? [Y/n]: ${NC})" -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]] || [[ -z $REPLY ]]; then
        if grep -q "^VAULT_TOKEN=" "$PROJECT_ROOT/.env" 2>/dev/null; then
            # Replace existing token
            sed -i.bak "s|^VAULT_TOKEN=.*|VAULT_TOKEN=${APP_TOKEN}|" "$PROJECT_ROOT/.env"
            echo -e "${GREEN}✓ Updated VAULT_TOKEN in .env${NC}"
        else
            # Add new token
            echo "" >> "$PROJECT_ROOT/.env"
            echo "# NVIDIA Vault Token (Application)" >> "$PROJECT_ROOT/.env"
            echo "VAULT_TOKEN=${APP_TOKEN}" >> "$PROJECT_ROOT/.env"
            echo -e "${GREEN}✓ Added VAULT_TOKEN to .env${NC}"
        fi
        
        # Update the environment
        export VAULT_TOKEN="$APP_TOKEN"
        
        # Create .env.vault-local
        echo -e "${BLUE}Updating .env.vault-local...${NC}"
        "$SCRIPT_DIR/switch_vault.sh" staging > /dev/null 2>&1 || true
        echo -e "${GREEN}✓ Run: source .env.vault-local${NC}"
    fi
else
    echo -e "${RED}✗ Failed to create application token${NC}"
    exit 1
fi
echo ""

echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}Step 4: Verification${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo ""

echo -e "${BLUE}Testing write access to secret/data/agenticta/test...${NC}"
if vault kv put secret/agenticta/test hello=world > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Write access confirmed${NC}"
    vault kv delete secret/agenticta/test > /dev/null 2>&1
else
    echo -e "${RED}✗ No write access yet${NC}"
    echo -e ""
    echo -e "${YELLOW}To fix this, you need to:${NC}"
    echo -e "  1. Contact your Vault administrator, OR"
    echo -e "  2. Re-authenticate with the new policy:"
    echo -e "     ${GREEN}./scripts/vault/get_vault_token.sh staging${NC}"
    echo -e ""
    exit 1
fi

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                 Setup Complete!                            ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}Next steps:${NC}"
echo -e "  1. Migrate your secrets:"
echo -e "     ${GREEN}python scripts/vault/migrate_secrets_to_vault.py${NC}"
echo -e ""
echo -e "  2. Verify secrets:"
echo -e "     ${GREEN}make vault-check${NC}"
echo -e ""
echo -e "  3. Test your application:"
echo -e "     ${GREEN}python scripts/vault/test_vault_integration.py${NC}"
echo -e ""


