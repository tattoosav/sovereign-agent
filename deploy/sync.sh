#!/bin/bash
# =============================================================================
# Sovereign Agent - Sync Script
# =============================================================================
# Syncs agent code and learned patterns between local machine and VPS
# =============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step() { echo -e "${CYAN}[STEP]${NC} $1"; }

# =============================================================================
# CONFIGURATION - EDIT THESE
# =============================================================================
# Set these environment variables or edit directly:
LAMBDA_IP="${LAMBDA_IP:-}"
LAMBDA_USER="${LAMBDA_USER:-ubuntu}"
LAMBDA_KEY="${LAMBDA_KEY:-$HOME/.ssh/lambda_key}"

# Local paths (Windows paths converted for Git Bash/WSL)
LOCAL_AGENT_DIR="${LOCAL_AGENT_DIR:-$(dirname $(dirname $(realpath $0)))}"
LOCAL_SOVEREIGN_DATA="${LOCAL_SOVEREIGN_DATA:-$LOCAL_AGENT_DIR/.sovereign}"

# Remote paths
REMOTE_AGENT_DIR="~/sovereign-agent"
REMOTE_SOVEREIGN_DATA="~/.sovereign"

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================
check_config() {
    if [ -z "$LAMBDA_IP" ]; then
        log_error "LAMBDA_IP not set!"
        echo ""
        echo "Set it with:"
        echo "  export LAMBDA_IP=your-instance-ip"
        echo ""
        echo "Or create deploy/.env file with:"
        echo "  LAMBDA_IP=your-instance-ip"
        exit 1
    fi

    if [ ! -f "$LAMBDA_KEY" ]; then
        log_error "SSH key not found: $LAMBDA_KEY"
        echo "Set LAMBDA_KEY to your SSH private key path"
        exit 1
    fi
}

ssh_cmd() {
    ssh -i "$LAMBDA_KEY" -o StrictHostKeyChecking=no "$LAMBDA_USER@$LAMBDA_IP" "$@"
}

rsync_to_remote() {
    rsync -avz --progress \
        -e "ssh -i $LAMBDA_KEY -o StrictHostKeyChecking=no" \
        "$@"
}

rsync_from_remote() {
    rsync -avz --progress \
        -e "ssh -i $LAMBDA_KEY -o StrictHostKeyChecking=no" \
        "$@"
}

# Load .env if exists
if [ -f "$(dirname $0)/.env" ]; then
    source "$(dirname $0)/.env"
fi

# =============================================================================
# COMMANDS
# =============================================================================
push_code() {
    log_step "Pushing agent code to VPS..."

    check_config

    # Create remote directory
    ssh_cmd "mkdir -p $REMOTE_AGENT_DIR"

    # Sync code (exclude unnecessary files)
    rsync_to_remote \
        --exclude='.git' \
        --exclude='__pycache__' \
        --exclude='.venv' \
        --exclude='*.pyc' \
        --exclude='.mypy_cache' \
        --exclude='.pytest_cache' \
        --exclude='.ruff_cache' \
        --exclude='chromadb_data' \
        --exclude='.sovereign/chromadb' \
        "$LOCAL_AGENT_DIR/" "$LAMBDA_USER@$LAMBDA_IP:$REMOTE_AGENT_DIR/"

    log_info "Code pushed successfully!"
}

push_patterns() {
    log_step "Pushing learned patterns to VPS..."

    check_config

    # Create remote data directory
    ssh_cmd "mkdir -p $REMOTE_SOVEREIGN_DATA"

    # Sync .sovereign folder (patterns, conversations, knowledge)
    if [ -d "$LOCAL_SOVEREIGN_DATA" ]; then
        rsync_to_remote \
            --exclude='chromadb' \
            "$LOCAL_SOVEREIGN_DATA/" "$LAMBDA_USER@$LAMBDA_IP:$REMOTE_SOVEREIGN_DATA/"
        log_info "Patterns pushed successfully!"
    else
        log_warn "No local .sovereign folder found, skipping patterns"
    fi
}

pull_patterns() {
    log_step "Pulling learned patterns from VPS..."

    check_config

    # Create local data directory
    mkdir -p "$LOCAL_SOVEREIGN_DATA"

    # Sync patterns back
    rsync_from_remote \
        --exclude='chromadb' \
        "$LAMBDA_USER@$LAMBDA_IP:$REMOTE_SOVEREIGN_DATA/" "$LOCAL_SOVEREIGN_DATA/"

    log_info "Patterns pulled successfully!"
}

pull_code() {
    log_step "Pulling code changes from VPS..."

    check_config

    # Sync code back (only changed files)
    rsync_from_remote \
        --exclude='.git' \
        --exclude='__pycache__' \
        --exclude='.venv' \
        --exclude='*.pyc' \
        --exclude='.mypy_cache' \
        --exclude='.pytest_cache' \
        --exclude='chromadb_data' \
        --exclude='.sovereign' \
        "$LAMBDA_USER@$LAMBDA_IP:$REMOTE_AGENT_DIR/" "$LOCAL_AGENT_DIR/"

    log_info "Code pulled successfully!"
}

push_all() {
    log_step "Full push: code + patterns..."
    push_code
    push_patterns
    log_info "Full push complete!"
}

pull_all() {
    log_step "Full pull: code + patterns..."
    pull_code
    pull_patterns
    log_info "Full pull complete!"
}

status() {
    log_step "Checking VPS status..."

    check_config

    echo ""
    log_info "Connection test:"
    ssh_cmd "echo 'Connected to \$(hostname)'"

    echo ""
    log_info "GPU Status:"
    ssh_cmd "nvidia-smi --query-gpu=name,memory.used,memory.free,temperature.gpu --format=csv"

    echo ""
    log_info "Ollama Models:"
    ssh_cmd "ollama list 2>/dev/null || echo 'Ollama not running'"

    echo ""
    log_info "Disk Usage:"
    ssh_cmd "df -h ~ | tail -1"

    echo ""
    log_info "Agent Status:"
    ssh_cmd "ps aux | grep -E 'python.*src\.(web|main)' | grep -v grep || echo 'Agent not running'"
}

# =============================================================================
# USAGE
# =============================================================================
usage() {
    echo ""
    echo "Sovereign Agent Sync Script"
    echo "==========================="
    echo ""
    echo "Usage: $0 <command>"
    echo ""
    echo "Commands:"
    echo "  push-code     Push agent code to VPS"
    echo "  push-patterns Push learned patterns to VPS"
    echo "  push          Push everything (code + patterns)"
    echo ""
    echo "  pull-code     Pull code changes from VPS"
    echo "  pull-patterns Pull learned patterns from VPS"
    echo "  pull          Pull everything (code + patterns)"
    echo ""
    echo "  status        Check VPS status"
    echo ""
    echo "Configuration:"
    echo "  LAMBDA_IP     VPS IP address (required)"
    echo "  LAMBDA_USER   SSH user (default: ubuntu)"
    echo "  LAMBDA_KEY    SSH private key path"
    echo ""
    echo "Example:"
    echo "  export LAMBDA_IP=123.45.67.89"
    echo "  $0 push"
    echo ""
}

# =============================================================================
# MAIN
# =============================================================================
case "${1:-}" in
    push-code)
        push_code
        ;;
    push-patterns)
        push_patterns
        ;;
    push)
        push_all
        ;;
    pull-code)
        pull_code
        ;;
    pull-patterns)
        pull_patterns
        ;;
    pull)
        pull_all
        ;;
    status)
        status
        ;;
    *)
        usage
        exit 1
        ;;
esac
