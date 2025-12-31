#!/bin/bash
# =============================================================================
# Sovereign Agent - Session Management Script
# =============================================================================
# Easy start/stop/monitor for Lambda Labs sessions
# =============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step() { echo -e "${CYAN}[STEP]${NC} $1"; }

# =============================================================================
# CONFIGURATION
# =============================================================================
SCRIPT_DIR="$(dirname $(realpath $0))"
LAMBDA_IP="${LAMBDA_IP:-}"
LAMBDA_USER="${LAMBDA_USER:-ubuntu}"
LAMBDA_KEY="${LAMBDA_KEY:-$HOME/.ssh/lambda_key}"
REMOTE_AGENT_DIR="~/sovereign-agent"
WEB_PORT=8000

# Load .env if exists
if [ -f "$SCRIPT_DIR/.env" ]; then
    source "$SCRIPT_DIR/.env"
fi

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================
check_config() {
    if [ -z "$LAMBDA_IP" ]; then
        log_error "LAMBDA_IP not set!"
        echo ""
        echo "Usage:"
        echo "  export LAMBDA_IP=your-instance-ip"
        echo "  $0 start"
        exit 1
    fi
}

ssh_cmd() {
    ssh -i "$LAMBDA_KEY" -o StrictHostKeyChecking=no -o ConnectTimeout=10 "$LAMBDA_USER@$LAMBDA_IP" "$@"
}

# =============================================================================
# COMMANDS
# =============================================================================
start_session() {
    check_config

    echo ""
    echo -e "${BOLD}=============================================="
    echo "  Starting Sovereign Agent Session"
    echo "==============================================${NC}"
    echo ""

    # Step 1: Check connection
    log_step "1/6 Checking VPS connection..."
    if ! ssh_cmd "echo 'Connected'" &>/dev/null; then
        log_error "Cannot connect to VPS at $LAMBDA_IP"
        exit 1
    fi
    log_info "Connected to $LAMBDA_IP"

    # Step 2: Sync code
    log_step "2/6 Syncing agent code..."
    "$SCRIPT_DIR/sync.sh" push-code

    # Step 3: Sync patterns
    log_step "3/6 Syncing learned patterns..."
    "$SCRIPT_DIR/sync.sh" push-patterns

    # Step 4: Ensure Ollama is running
    log_step "4/6 Starting Ollama..."
    ssh_cmd "pgrep ollama || (ollama serve &>/dev/null &)"
    sleep 2

    # Step 5: Install dependencies if needed
    log_step "5/6 Checking dependencies..."
    ssh_cmd "cd $REMOTE_AGENT_DIR && uv sync 2>/dev/null || pip install -r requirements.txt 2>/dev/null || true"

    # Step 6: Start agent
    log_step "6/6 Starting Sovereign Agent..."
    ssh_cmd "cd $REMOTE_AGENT_DIR && \
        pkill -f 'python.*src.web' 2>/dev/null || true && \
        sleep 1 && \
        nohup uv run python -m src.web --host 0.0.0.0 --port $WEB_PORT > agent.log 2>&1 &"

    sleep 3

    # Verify
    if ssh_cmd "pgrep -f 'python.*src.web'" &>/dev/null; then
        log_info "Agent started successfully!"
    else
        log_error "Agent failed to start. Check logs with: $0 logs"
        exit 1
    fi

    echo ""
    echo -e "${BOLD}=============================================="
    echo "  SESSION READY!"
    echo "==============================================${NC}"
    echo ""
    echo -e "  Web UI:    ${GREEN}http://$LAMBDA_IP:$WEB_PORT${NC}"
    echo -e "  SSH:       ${CYAN}ssh -i $LAMBDA_KEY $LAMBDA_USER@$LAMBDA_IP${NC}"
    echo ""
    echo "  Commands:"
    echo "    $0 status   - Check session status"
    echo "    $0 logs     - View agent logs"
    echo "    $0 stop     - Stop and sync back"
    echo ""

    # GPU info
    log_info "GPU Status:"
    ssh_cmd "nvidia-smi --query-gpu=name,memory.used,memory.free --format=csv"
    echo ""
}

stop_session() {
    check_config

    echo ""
    echo -e "${BOLD}=============================================="
    echo "  Stopping Sovereign Agent Session"
    echo "==============================================${NC}"
    echo ""

    # Step 1: Stop agent
    log_step "1/4 Stopping agent..."
    ssh_cmd "pkill -f 'python.*src.web' 2>/dev/null || true"
    log_info "Agent stopped"

    # Step 2: Pull code changes
    log_step "2/4 Pulling code changes..."
    "$SCRIPT_DIR/sync.sh" pull-code

    # Step 3: Pull learned patterns
    log_step "3/4 Pulling learned patterns..."
    "$SCRIPT_DIR/sync.sh" pull-patterns

    # Step 4: Summary
    log_step "4/4 Session summary..."

    echo ""
    echo -e "${BOLD}=============================================="
    echo "  SESSION ENDED"
    echo "==============================================${NC}"
    echo ""
    echo "  All code and patterns synced to local machine."
    echo "  You can now terminate the Lambda instance."
    echo ""
    echo -e "  ${YELLOW}Don't forget to stop your Lambda instance to stop billing!${NC}"
    echo ""
}

show_status() {
    check_config

    echo ""
    echo -e "${BOLD}Session Status${NC}"
    echo "=============="
    echo ""

    # Connection
    echo -n "Connection: "
    if ssh_cmd "echo ok" &>/dev/null; then
        echo -e "${GREEN}Connected${NC}"
    else
        echo -e "${RED}Disconnected${NC}"
        exit 1
    fi

    # Agent
    echo -n "Agent:      "
    if ssh_cmd "pgrep -f 'python.*src.web'" &>/dev/null; then
        echo -e "${GREEN}Running${NC}"
        echo -e "            http://$LAMBDA_IP:$WEB_PORT"
    else
        echo -e "${YELLOW}Not running${NC}"
    fi

    # Ollama
    echo -n "Ollama:     "
    if ssh_cmd "pgrep ollama" &>/dev/null; then
        echo -e "${GREEN}Running${NC}"
    else
        echo -e "${YELLOW}Not running${NC}"
    fi

    echo ""
    echo -e "${BOLD}GPU Status${NC}"
    echo "=========="
    ssh_cmd "nvidia-smi --query-gpu=name,memory.used,memory.free,temperature.gpu,utilization.gpu --format=csv"

    echo ""
    echo -e "${BOLD}Models${NC}"
    echo "======"
    ssh_cmd "ollama list 2>/dev/null || echo 'Ollama not available'"

    echo ""
    echo -e "${BOLD}Disk Space${NC}"
    echo "=========="
    ssh_cmd "df -h ~ | tail -1"
    echo ""
}

show_logs() {
    check_config
    log_info "Streaming agent logs (Ctrl+C to exit)..."
    ssh_cmd "tail -f $REMOTE_AGENT_DIR/agent.log"
}

run_shell() {
    check_config
    log_info "Opening SSH session..."
    ssh -i "$LAMBDA_KEY" -o StrictHostKeyChecking=no "$LAMBDA_USER@$LAMBDA_IP"
}

learn_codebase() {
    check_config

    local project_path="${2:-.}"

    log_info "Running codebase learning on VPS..."
    ssh_cmd "cd $REMOTE_AGENT_DIR && uv run python -c \"
from src.tools.learning import LearningTool
from src.memory import CodebaseIndexer, VectorStore

print('Initializing learning...')
learner = LearningTool()

print('Analyzing codebase...')
result = learner.execute('analyze', path='$project_path')
print(result.output)

print('\\nLearning complete!')
\""
}

index_codebase() {
    check_config

    local project_path="${2:-.}"

    log_info "Indexing codebase for RAG on VPS..."
    ssh_cmd "cd $REMOTE_AGENT_DIR && uv run python -c \"
from src.memory import CodebaseIndexer, VectorStore

print('Initializing vector store...')
store = VectorStore()
indexer = CodebaseIndexer(store)

print('Indexing codebase at: $project_path')
stats = indexer.index_directory('$project_path')
print(f'Indexed {stats.get(\"files_indexed\", 0)} files')
print('\\nIndexing complete!')
\""
}

# =============================================================================
# USAGE
# =============================================================================
usage() {
    echo ""
    echo -e "${BOLD}Sovereign Agent Session Manager${NC}"
    echo "================================"
    echo ""
    echo "Usage: $0 <command>"
    echo ""
    echo "Session Commands:"
    echo "  start       Start agent session (sync + start)"
    echo "  stop        Stop session (stop + sync back)"
    echo "  status      Show session status"
    echo "  logs        Stream agent logs"
    echo "  shell       SSH into VPS"
    echo ""
    echo "Learning Commands:"
    echo "  learn [path]   Learn patterns from codebase"
    echo "  index [path]   Index codebase for RAG"
    echo ""
    echo "Configuration (set via environment or .env file):"
    echo "  LAMBDA_IP     VPS IP address (required)"
    echo "  LAMBDA_USER   SSH user (default: ubuntu)"
    echo "  LAMBDA_KEY    SSH private key path"
    echo ""
    echo "Example:"
    echo "  export LAMBDA_IP=123.45.67.89"
    echo "  $0 start"
    echo ""
}

# =============================================================================
# MAIN
# =============================================================================
case "${1:-}" in
    start)
        start_session
        ;;
    stop)
        stop_session
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs
        ;;
    shell|ssh)
        run_shell
        ;;
    learn)
        learn_codebase "$@"
        ;;
    index)
        index_codebase "$@"
        ;;
    *)
        usage
        exit 1
        ;;
esac
