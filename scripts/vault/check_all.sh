#!/bin/bash
# Comprehensive Vault Health Check
# Verifies all aspects of Vault integration

# Don't exit on errors - we want to run all checks
set +e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║           Comprehensive Vault Health Check                ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Track results
PASSED=0
FAILED=0
WARNINGS=0

# Helper functions
pass() {
    echo -e "${GREEN}✓${NC} $1"
    ((PASSED++))
}

fail() {
    echo -e "${RED}✗${NC} $1"
    ((FAILED++))
}

warn() {
    echo -e "${YELLOW}⚠${NC} $1"
    ((WARNINGS++))
}

section() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

# Check 1: Environment Variables
section "1. Environment Variables"

if [ -n "$VAULT_ADDR" ]; then
    pass "VAULT_ADDR is set: $VAULT_ADDR"
else
    fail "VAULT_ADDR is not set"
fi

if [ -n "$VAULT_TOKEN" ]; then
    pass "VAULT_TOKEN is set (${#VAULT_TOKEN} chars)"
else
    fail "VAULT_TOKEN is not set"
fi

if [ -n "$VAULT_NAMESPACE" ]; then
    pass "VAULT_NAMESPACE is set: $VAULT_NAMESPACE"
else
    warn "VAULT_NAMESPACE is not set (OK for local)"
fi

MOUNT_POINT="${VAULT_MOUNT_POINT:-secret}"
pass "VAULT_MOUNT_POINT: $MOUNT_POINT (default if not set)"

# Check 2: Vault CLI
section "2. Vault CLI"

if command -v vault &> /dev/null; then
    VAULT_VERSION=$(vault version | head -1)
    pass "Vault CLI installed: $VAULT_VERSION"
else
    fail "Vault CLI not found"
    echo "   Install with: brew install vault"
fi

# Check 3: Vault Connection
section "3. Vault Connection"

if vault status > /dev/null 2>&1; then
    pass "Vault is accessible"
    vault status | grep -E "Sealed|Initialized" | while read line; do
        echo "   $line"
    done
else
    fail "Cannot connect to Vault"
fi

# Check 4: Token Status
section "4. Token Status"

if vault token lookup > /dev/null 2>&1; then
    pass "Token is valid"
    
    # Get token details
    DISPLAY_NAME=$(vault token lookup -format=json 2>/dev/null | jq -r '.data.display_name // "N/A"')
    TTL=$(vault token lookup -format=json 2>/dev/null | jq -r '.data.ttl // 0')
    POLICIES=$(vault token lookup -format=json 2>/dev/null | jq -r '.data.policies | join(", ")')
    
    echo "   Display Name: $DISPLAY_NAME"
    echo "   TTL: $TTL seconds ($(($TTL / 3600)) hours)"
    echo "   Policies: $POLICIES"
    
    if [[ "$POLICIES" == *"agenticta-secrets"* ]]; then
        pass "Application policy attached (agenticta-secrets)"
    elif [[ "$POLICIES" == *"namespace-admin"* ]]; then
        warn "Using namespace-admin token (can't access secrets)"
        echo "   Run: ./scripts/vault/setup_nvidia_vault.sh"
    else
        warn "Unknown policies: $POLICIES"
    fi
    
    if [ $TTL -lt 86400 ]; then
        warn "Token expires in less than 24 hours"
    fi
else
    fail "Token is invalid or expired"
fi

# Check 5: Secrets Engine
section "5. Secrets Engine"

if vault secrets list | grep -q "^${MOUNT_POINT}/"; then
    pass "KV secrets engine enabled at: ${MOUNT_POINT}/"
    
    # Check if it's KV v2
    TYPE=$(vault secrets list -format=json | jq -r ".\"${MOUNT_POINT}/\".type // \"unknown\"")
    VERSION=$(vault secrets list -format=json | jq -r ".\"${MOUNT_POINT}/\".options.version // \"1\"")
    
    echo "   Type: $TYPE"
    echo "   Version: $VERSION"
    
    if [ "$VERSION" == "2" ]; then
        pass "Using KV v2 (versioned secrets)"
    else
        warn "Not using KV v2 (version: $VERSION)"
    fi
else
    fail "KV secrets engine not found at: ${MOUNT_POINT}/"
fi

# Check 6: Secret Paths
section "6. Secret Paths"

if vault kv list ${MOUNT_POINT}/agenticta > /dev/null 2>&1; then
    pass "agenticta/ path exists"
    
    PATHS=$(vault kv list -format=json ${MOUNT_POINT}/agenticta 2>/dev/null | jq -r '.[]' | wc -l)
    echo "   Found $PATHS secret paths"
else
    fail "agenticta/ path not found"
fi

# Check 7: Required Secrets
section "7. Required Secrets"

check_secret() {
    local path=$1
    local key=$2
    
    if vault kv get -field=$key ${MOUNT_POINT}/${path} > /dev/null 2>&1; then
        VALUE=$(vault kv get -field=$key ${MOUNT_POINT}/${path} 2>/dev/null)
        pass "$path: $key (${#VALUE} chars)"
    else
        fail "$path: $key MISSING"
    fi
}

check_secret "agenticta/api-keys" "nvidia_api_key"
check_secret "agenticta/api-keys" "hf_token"
check_secret "agenticta/auth-tokens" "astra_token"
check_secret "agenticta/observability" "datadog_embedding_api_token"

# Check 8: Python Environment
section "8. Python Environment"

cd "$PROJECT_ROOT"

if [ -f ".venv/bin/python" ]; then
    pass "Virtual environment found"
else
    warn "Virtual environment not found at .venv/"
fi

if python -c "import hvac" 2>/dev/null; then
    HVAC_VERSION=$(python -c "import hvac; print(hvac.__version__)" 2>/dev/null)
    pass "hvac library installed: $HVAC_VERSION"
else
    fail "hvac library not installed"
    echo "   Install with: pip install hvac"
fi

if python -c "from dotenv import load_dotenv" 2>/dev/null; then
    pass "python-dotenv library installed"
else
    fail "python-dotenv library not installed"
fi

# Check 9: Vault Python Module
section "9. Vault Python Module"

if python -c "from vault import get_secrets_config" 2>/dev/null; then
    pass "Vault module can be imported"
    
    # Test instantiation
    if python -c "from vault import get_secrets_config; get_secrets_config()" 2>/dev/null; then
        pass "Vault client can be instantiated"
    else
        fail "Vault client instantiation failed"
    fi
else
    fail "Cannot import vault module"
fi

# Check 10: Secret Retrieval
section "10. Secret Retrieval via Python"

TEST_SCRIPT=$(cat << 'EOF'
import sys
from vault import get_secrets_config

try:
    secrets = get_secrets_config()
    
    # Test each secret
    secrets_to_test = [
        'NVIDIA_API_KEY',
        'HF_TOKEN',
        'ASTRA_TOKEN',
        'DATADOG_EMBEDDING_API_TOKEN'
    ]
    
    for secret_name in secrets_to_test:
        value = secrets.get(secret_name)
        if value:
            print(f"✓ {secret_name}: {len(value)} chars")
        else:
            print(f"✗ {secret_name}: MISSING")
            sys.exit(1)
    
    print("✓ All secrets retrieved successfully")
    sys.exit(0)
except Exception as e:
    print(f"✗ Error: {e}")
    sys.exit(1)
EOF
)

if echo "$TEST_SCRIPT" | python 2>/dev/null; then
    pass "All secrets retrievable via Python"
else
    fail "Secret retrieval failed"
fi

# Check 11: Configuration Files
section "11. Configuration Files"

if [ -f "$PROJECT_ROOT/.env" ]; then
    pass ".env file exists"
    
    if grep -q "VAULT_TOKEN" "$PROJECT_ROOT/.env"; then
        pass "VAULT_TOKEN in .env"
    else
        warn "VAULT_TOKEN not in .env"
    fi
else
    warn ".env file not found"
fi

if [ -f "$PROJECT_ROOT/.env.vault-local" ]; then
    pass ".env.vault-local exists"
else
    warn ".env.vault-local not found"
fi

if [ -f "$PROJECT_ROOT/docker-compose.vault-dev.yml" ]; then
    pass "docker-compose.vault-dev.yml exists"
else
    warn "docker-compose.vault-dev.yml not found"
fi

# Check 12: Scripts
section "12. Vault Scripts"

SCRIPTS=(
    "setup_nvidia_vault.sh"
    "get_vault_token.sh"
    "start_local_vault.sh"
    "stop_local_vault.sh"
    "switch_vault.sh"
    "migrate_secrets_to_vault.py"
    "list_secrets.py"
    "vault_health_check.py"
)

for script in "${SCRIPTS[@]}"; do
    if [ -f "$SCRIPT_DIR/$script" ]; then
        if [ -x "$SCRIPT_DIR/$script" ] || [[ "$script" == *.py ]]; then
            pass "$script"
        else
            warn "$script (not executable)"
        fi
    else
        fail "$script (missing)"
    fi
done

# Check 13: Local Vault (optional)
section "13. Local Vault Server (Optional)"

if docker ps 2>/dev/null | grep -q agenticta-vault-dev; then
    pass "Local Vault container is running"
else
    warn "Local Vault container not running"
    echo "   Start with: make vault-dev-start"
fi

# Summary
section "Summary"

echo ""
echo -e "${GREEN}Passed:${NC}   $PASSED"
echo -e "${YELLOW}Warnings:${NC} $WARNINGS"
echo -e "${RED}Failed:${NC}   $FAILED"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║              ✅ All Critical Checks Passed!                ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
    
    if [ $WARNINGS -gt 0 ]; then
        echo ""
        echo -e "${YELLOW}Note: $WARNINGS warning(s) can be safely ignored for basic operation.${NC}"
    fi
    
    exit 0
else
    echo -e "${RED}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║              ❌ Some Checks Failed                         ║${NC}"
    echo -e "${RED}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${YELLOW}Troubleshooting:${NC}"
    echo "  1. Ensure .env.vault-local is sourced: source .env.vault-local"
    echo "  2. Check token validity: vault token lookup"
    echo "  3. Verify secrets exist: make vault-check"
    echo "  4. See docs: cat VAULT_README.md"
    echo ""
    exit 1
fi

