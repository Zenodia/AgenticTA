#!/usr/bin/bash
# Environment setup for AgenticTA
# Source this file to set up your environment

if [ -z ${BASH_SOURCE[0]} ]; then
export TOP=$(dirname "$0")
else
export TOP=$(dirname "$(readlink -f "$BASH_SOURCE[0]")")
fi

# Path to RAG folder
RAG=$TOP/rag

# Useful aliases
alias v='source $TOP/.venv/bin/activate'
alias dps='docker ps --format "table {{.ID}}\t{{.Names}}\t{{.Status}}\t{{.Ports}}"'

# Load environment variables from .env if it exists
if [ -f "$TOP/.env" ]; then
    set -a
    source "$TOP/.env"
    set +a
fi
