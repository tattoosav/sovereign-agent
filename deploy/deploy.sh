#!/bin/bash
# =============================================================================
# Sovereign Agent - Lambda Labs A100 Deployment Script
# =============================================================================
# This script sets up the complete environment on a Lambda Labs GPU instance
# Run this ONCE after SSH'ing into your instance
# =============================================================================

set -e  # Exit on error

echo "=============================================="
echo "  Sovereign Agent - A100 Deployment"
echo "=============================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# =============================================================================
# CONFIGURATION
# =============================================================================
AGENT_DIR="$HOME/sovereign-agent"
MODELS=("qwen2.5-coder:7b" "qwen2.5-coder:14b" "qwen2.5-coder:32b")
SOVEREIGN_DATA="$HOME/.sovereign"

# =============================================================================
# STEP 1: System Updates
# =============================================================================
log_info "Step 1/7: Updating system packages..."
sudo apt-get update -qq
sudo apt-get install -y -qq git curl wget tmux htop ncdu ripgrep

# =============================================================================
# STEP 2: Install Ollama
# =============================================================================
log_info "Step 2/7: Installing Ollama..."
if ! command -v ollama &> /dev/null; then
    curl -fsSL https://ollama.com/install.sh | sh
    log_info "Ollama installed successfully"
else
    log_info "Ollama already installed"
fi

# Start Ollama service
log_info "Starting Ollama service..."
sudo systemctl enable ollama 2>/dev/null || true
sudo systemctl start ollama 2>/dev/null || ollama serve &
sleep 3

# =============================================================================
# STEP 3: Pull Models (parallel for speed)
# =============================================================================
log_info "Step 3/7: Pulling Qwen 2.5 Coder models..."
echo "This may take 10-15 minutes on datacenter connection..."

for model in "${MODELS[@]}"; do
    log_info "Pulling $model..."
    ollama pull "$model" &
done
wait
log_info "All models downloaded"

# Verify models
log_info "Installed models:"
ollama list

# =============================================================================
# STEP 4: Install Python & UV
# =============================================================================
log_info "Step 4/7: Setting up Python environment..."

# Install uv if not present
if ! command -v uv &> /dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
fi

# =============================================================================
# STEP 5: Clone/Setup Agent
# =============================================================================
log_info "Step 5/7: Setting up Sovereign Agent..."

if [ -d "$AGENT_DIR" ]; then
    log_info "Agent directory exists, pulling latest..."
    cd "$AGENT_DIR"
    git pull 2>/dev/null || log_warn "Not a git repo, skipping pull"
else
    log_warn "Agent directory not found at $AGENT_DIR"
    log_warn "Please sync your agent files using sync.sh"
    mkdir -p "$AGENT_DIR"
fi

# =============================================================================
# STEP 6: Install Dependencies
# =============================================================================
log_info "Step 6/7: Installing Python dependencies..."

if [ -f "$AGENT_DIR/pyproject.toml" ]; then
    cd "$AGENT_DIR"
    uv sync
    log_info "Dependencies installed"
else
    log_warn "pyproject.toml not found, skipping dependency install"
fi

# =============================================================================
# STEP 7: Create Data Directories
# =============================================================================
log_info "Step 7/7: Creating data directories..."

mkdir -p "$SOVEREIGN_DATA/patterns"
mkdir -p "$SOVEREIGN_DATA/conversations"
mkdir -p "$SOVEREIGN_DATA/chromadb"
mkdir -p "$SOVEREIGN_DATA/knowledge"

# =============================================================================
# GPU Information
# =============================================================================
log_info "GPU Information:"
nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv

# =============================================================================
# Test Ollama
# =============================================================================
log_info "Testing Ollama connection..."
if ollama list &>/dev/null; then
    log_info "Ollama is running correctly"
else
    log_error "Ollama connection failed"
    exit 1
fi

# =============================================================================
# Summary
# =============================================================================
echo ""
echo "=============================================="
echo "  DEPLOYMENT COMPLETE!"
echo "=============================================="
echo ""
echo "Next steps:"
echo "  1. Sync your agent code:  ./sync.sh push"
echo "  2. Start the agent:       ./session.sh start"
echo "  3. Access Web UI:         http://$(hostname -I | awk '{print $1}'):8000"
echo ""
echo "Models available:"
ollama list
echo ""
echo "GPU Status:"
nvidia-smi --query-gpu=name,memory.used,memory.free --format=csv
echo ""
log_info "Ready for coding at 10x speed!"
