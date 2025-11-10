#!/bin/bash

# AgenticTA Environment Setup Script
# This script helps you set up the required environment variables

echo "╔═══════════════════════════════════════════════════════════╗"
echo "║        AgenticTA Environment Setup                        ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""

# Function to check if a variable is set
check_env() {
    local var_name=$1
    local var_value=${!var_name}
    
    if [ -z "$var_value" ]; then
        echo "❌ $var_name is NOT set"
        return 1
    else
        echo "✅ $var_name is set"
        return 0
    fi
}

# Check for NGC/NVIDIA API Key
echo "Checking required environment variables:"
echo ""

NGC_SET=false
NVIDIA_SET=false

if [ -n "$NGC_API_KEY" ]; then
    echo "✅ NGC_API_KEY is set"
    NGC_SET=true
fi

if [ -n "$NVIDIA_API_KEY" ]; then
    echo "✅ NVIDIA_API_KEY is set"
    NVIDIA_SET=true
fi

if [ "$NGC_SET" = false ] && [ "$NVIDIA_SET" = false ]; then
    echo "❌ Neither NGC_API_KEY nor NVIDIA_API_KEY is set"
    echo ""
    echo "You need to set one of these to access NVIDIA NGC containers."
    echo ""
    echo "To set NGC_API_KEY, add this to your ~/.bashrc or ~/.zshrc:"
    echo "  export NGC_API_KEY=\"nvapi-your-key-here\""
    echo ""
    echo "Or set NVIDIA_API_KEY:"
    echo "  export NVIDIA_API_KEY=\"nvapi-your-key-here\""
    echo ""
    echo "Get your API key from: https://org.ngc.nvidia.com/setup/api-key"
    echo ""
    exit 1
fi

echo ""

# Check optional variables
echo "Checking optional environment variables:"
echo ""

check_env "ASTRA_TOKEN" || echo "  (Optional - for Astra DB integration)"
check_env "HF_TOKEN" || echo "  (Optional - for HuggingFace models)"
check_env "DATADOG_EMBEDDING_API_TOKEN" || echo "  (Optional - for Datadog API access)"

echo ""
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║           Environment Setup Complete!                     ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""
echo "Next steps:"
echo "  1. make up        # Start all services"
echo "  2. make status    # Check service status"
echo "  3. make gradio    # Start Gradio UI"
echo ""

