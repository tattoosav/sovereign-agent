# Sovereign Agent

## What This Is
A locally-running AI coding agent with full filesystem access, built from scratch.
Uses Ollama + Qwen 2.5 Coder as the brain, with custom tool implementations, vector memory, and intelligent task planning.

## Project Philosophy
- **No LangChain** - too abstracted, causes debugging nightmares
- **Minimal dependencies** - only what we actually need
- **Clear tool boundaries** - each tool does one thing well
- **Type safety** - use dataclasses and type hints everywhere
- **Local-first** - Everything runs on your machine, no cloud dependencies

## Current State
**MAJOR MILESTONE: Intelligent All-in-One Coding Agent with Learning! 🎉**
**Phases 1-70 Foundation + Intelligence + Performance + Specializations + Learning COMPLETE**

### Air-Gapped Autonomous Build (Phase 71)
A hardened, **fully offline** delivery for an isolated single-Windows-workstation
client. Runs autonomously, persists across reboots, and never touches the internet.

- **Internet tools removed** — `web_research.py` deleted; the dependencies tool is
  reduced to local `analyze` only (no registry calls). Nothing network-capable is
  importable or registrable.
- **Central tool gate** — `src/tools/registry_factory.py::build_registry` is the ONLY
  tool-registration path; it wires up the full local toolset (no egress branch).
- **Shell hardening** — allowlist mode + working-dir restriction + a network-command
  blocklist (`src/tools/shell.py`).
- **Egress self-check** — `src/core/egress_guard.py::assert_airgap` aborts startup if
  the public internet is reachable (run standalone: `python -m src.core.egress_guard`).
- **Local-only web** — CORS locked to local origins, host binding refuses non-local.
- **Autonomous daemon** — `src/agent/autonomous.py` + `src/autonomous.py`: filesystem
  task queue (`tasks/inbox|active|done|failed|state`), runs each task via `AgentV2`,
  persists via `ConversationStore`, resumes interrupted tasks on boot.
- **Longevity** — fault isolation, per-task timeout, Ollama backoff, atomic state
  writes, rotating logs, retention/disk guards. Chaos-tested in `tests/test_longevity.py`.
- **Offline USB bundle** — `install/build_bundle.ps1` assembles app + wheelhouse +
  Python + Ollama + models + NSSM + checksums; `install/INSTALL.bat` →
  `install_airgap.ps1` performs a one-action, zero-network install. Operator guide:
  `docs/AIRGAP_RUNBOOK.md`.
- Config: `src/core/config.py::AirgapConfig` (`SOVEREIGN_AIRGAP_ENFORCE`,
  `SOVEREIGN_SHELL_ALLOWLIST`). Client config template: `install/config.yaml`.

Run the daemon: `python -m src.autonomous --working-dir <dir>`
Tests: `pytest tests/test_airgap.py tests/test_egress_guard.py tests/test_autonomous.py tests/test_longevity.py`

### CRM — Customer Relationship Management (Phase 72)
The **primary purpose** of this deployment: a general-purpose, fully-offline CRM.

- **Storage** — `src/crm/`: standard-library `sqlite3` (no new deps), DB at
  `<workspace>/.sovereign/crm.db`, persists across reboots.
- **Model** — Companies, Contacts, Deals (pipeline: lead→qualified→proposal→
  negotiation→won/lost), Interactions, Tasks (follow-ups), Appointments, Payments.
  `models.py` / `database.py` (schema) / `repository.py` (CRUD) / `service.py`
  (pipeline analytics, due tasks, stale contacts, daily briefing).
- **Conversational** — `src/tools/crm_tool.py` registers the `crm` tool so the agent
  manages records in natural language (add_contact, log_interaction, add_deal,
  pipeline, add_task, due_tasks, briefing, ...).
- **Web UI** — `src/api/crm_routes.py` (REST) + `static/crm.html|crm.css|crm.js`,
  served at `/crm` (Dashboard, Contacts, Pipeline board, Follow-ups). AI chat at `/`.
- **Autonomous** — the daemon files a daily CRM briefing into `tasks/reports/` and
  backs up the DB + CSV exports to `<workspace>/.sovereign/backups/` once per day.
- **Backup/export** — `src/crm/backup.py`: timestamped DB snapshots + CSV export
  (contacts/companies/deals). Trigger from the UI ("Backup now") or `POST /crm/backup`.
  Important: air-gapped data lives only on this box — copy backups to a second drive.

Tests: `pytest tests/test_crm.py tests/test_crm_api.py`

### Completed Phases
- ✅ **Phase 1:** Project Hardening
- ✅ **Phase 11:** Diff-Based File Editing
- ✅ **Phase 12:** Code Search
- ✅ **Phase 13:** Git Integration
- ✅ **Phase 26:** Task Decomposition
- ✅ **Phase 31:** Multi-Model Routing
- ✅ **Phase 41:** Vector Database Integration (ChromaDB)
- ✅ **Phase 42:** Codebase Indexing
- ✅ **Phase 44:** Knowledge Base
- ✅ **Phase 51:** Self-Correction Loop
- ✅ **Phase 52:** Code Review Agent
- ✅ **Phase 53:** Automated Test Generation
- ✅ **Phase 54:** Loop Optimization
- ✅ **Phase 55:** Error Recovery
- ✅ **Phase 56:** Web Interface (FastAPI + Browser UI)
- ✅ **Phase 57:** Intelligence Integration (Agent v2)
- ✅ **Phase 58:** Streaming Responses
- ✅ **Phase 59:** Compound Tools (Tool Chaining)
- ✅ **Phase 60:** Parallel Tool Execution & File Watching
- ✅ **Phase 61:** Conversation Persistence
- ✅ **Phase 62:** Smart Context Window Management
- ✅ **Phase 63:** C++/.NET/Visual Studio Specialization
- ✅ **Phase 64:** GUI Development Support (WinForms, WPF)
- ✅ **Phase 65:** Multi-File Refactoring
- ✅ **Phase 66:** Code Intelligence & Completion
- ✅ **Phase 67:** Project Scaffolding Templates
- ✅ **Phase 68:** Dependency Analysis & Management
- ✅ **Phase 69:** Automated Documentation Generator
- ✅ **Phase 70:** Code Pattern Learning System

### Working Features
- Full filesystem operations (read, write, edit, list)
- String-based file editing with diff preview
- Code search (Python fallback, ripgrep-ready)
- Git operations (status, diff, log, commit, branch, etc.)
- Shell command execution with safety restrictions
- Task planning and decomposition
- **Dynamic model routing** (7B/14B/32B automatically selected per task)
- **RAG context retrieval** (queries memory before each turn)
- **Task-specific prompting** (implement, debug, refactor, explain, etc.)
- **Conversation summarization** (handles long conversations efficiently)
- **Learning from success** (stores solutions for future reference)
- Vector-based semantic search
- Codebase indexing for RAG
- Project knowledge management
- Self-correction and verification (validates tool results, suggests improvements)
- Code review with static analysis (mypy, ruff, pylint)
- Automated test generation (pytest scaffolds)
- Operation caching (prevents redundant reads)
- Error recovery (fallback strategies, graceful degradation)
- **Web Interface** (FastAPI backend + browser UI)
- **Streaming Responses** (real-time token streaming via SSE)
- **Compound Tools** (tool chaining for multi-step operations)
- **Parallel Tool Execution** (concurrent execution of independent tools)
- **File Watcher** (auto-reindexing on file changes)
- **Conversation Persistence** (save/load sessions across restarts)
- **Smart Context Window** (priority-based, adaptive token management)
- **C++/.NET Specialization** (expert knowledge for C++17/20/23, .NET 8)
- **Visual Studio Tool** (create solutions, projects, build with MSBuild)
- **GUI Development** (WinForms, WPF templates and best practices)
- **Multi-File Refactoring** (rename, extract, move across files)
- **Code Intelligence** (completions, imports, pattern suggestions)
- **Project Scaffolding** (templates for Python, C++, .NET projects)
- **Dependency Analysis** (analyze, update, security checks)
- **Documentation Generator** (markdown/HTML from code)
- **Pattern Learning** (learns conventions from codebase)

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      SOVEREIGN AGENT                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐          ┌──────────────┐                │
│  │   Planning   │          │    Router    │                │
│  │  Decompose   │◄────────►│ Model Select │                │
│  │    Tasks     │          │  7B/14B/32B  │                │
│  └──────────────┘          └──────────────┘                │
│         │                         │                          │
│         └────────────┬────────────┘                          │
│                      ▼                                        │
│            ┌────────────────┐                                │
│            │  Agent Core    │                                │
│            │  (Main Loop)   │                                │
│            └────────┬───────┘                                │
│                     │                                         │
│       ┌─────────────┼─────────────┐                          │
│       ▼             ▼             ▼                          │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐                      │
│  │  LLM    │  │  Tools  │  │ Memory  │                      │
│  │ Client  │  │Registry │  │ System  │                      │
│  └─────────┘  └────┬────┘  └────┬────┘                      │
│                    │             │                           │
│         ┌──────────┼─────────────┼──────────┐                │
│         ▼          ▼             ▼          ▼                │
│    ┌────────┐┌────────┐  ┌──────────┐┌──────────┐           │
│    │  File  ││  Git   │  │  Vector  ││Knowledge │           │
│    │ Tools  ││ Tools  │  │   Store  ││   Base   │           │
│    └────────┘└────────┘  │(ChromaDB)││  (JSON)  │           │
│    ┌────────┐┌────────┐  └──────────┘└──────────┘           │
│    │Search  ││ Shell  │                                      │
│    │ Tools  ││ Tools  │                                      │
│    └────────┘└────────┘                                      │
└─────────────────────────────────────────────────────────────┘
```

## Key Files

### Core Infrastructure
- `src/agent/core.py` - Main agent loop
- `src/agent/llm.py` - Ollama client with retry logic
- `src/agent/planner.py` - Task decomposition system
- `src/agent/router.py` - Multi-model routing
- `src/core/logging.py` - Structured logging
- `src/core/config.py` - YAML configuration

### Web API
- `src/web.py` - Web server entry point
- `src/api/server.py` - FastAPI app and routes
- `src/api/session.py` - Session management
- `src/api/static/` - Frontend (HTML/CSS/JS)

### Tools
- `src/tools/base.py` - Tool interface
- `src/tools/filesystem.py` - File read/write/list
- `src/tools/editor.py` - String-based file editing
- `src/tools/search.py` - Code search
- `src/tools/git.py` - Git operations
- `src/tools/shell.py` - Shell command execution

### Memory System
- `src/memory/vector_store.py` - ChromaDB integration
- `src/memory/codebase_index.py` - Code indexing
- `src/memory/knowledge_base.py` - Project knowledge

## Completed Phases Detail

### Phase 1: Project Hardening ✓
**Infrastructure:** Logging, Config, Retry, Shutdown

- **Structured Logging** (`src/core/logging.py`)
  - Colored console output with timestamps
  - Optional file logging
  - Configurable log levels
  - Per-module loggers

- **Configuration System** (`src/core/config.py`)
  - YAML configuration files
  - Environment variable overrides
  - Sensible defaults
  - Type-safe config objects

- **Retry Logic** (`src/agent/llm.py`)
  - Exponential backoff for LLM calls
  - Configurable max retries and delay
  - Handles network errors and timeouts
  - Detailed logging of retry attempts

- **Graceful Shutdown** (`src/main.py`)
  - Signal handlers for SIGINT/SIGTERM
  - Clean resource cleanup
  - Proper logging on exit
  - Shutdown flag prevents new operations

### Phase 11: Diff-Based File Editing ✓
**Tool:** Surgical code editing with diff preview

- **String Replace Tool** (`src/tools/editor.py`)
  - Surgical file edits without rewriting entire files
  - Safety check: old_str must appear exactly once
  - Unified diff preview of changes
  - Token-efficient for small edits
  - Full path security restrictions

- **Comprehensive Tests** (`tests/test_editor.py`)
  - 12 test cases covering all edge cases
  - Multiline replacements
  - Unicode content handling
  - Error conditions (not found, multiple matches)
  - Access control validation
  - Diff output verification

### Phase 12: Code Search ✓
**Tool:** Fast code search with Python fallback

- **Code Search Tool** (`src/tools/search.py`)
  - Regex pattern matching
  - File type filtering
  - Case-sensitive/insensitive search
  - Ripgrep integration (when available)
  - Python fallback implementation
  - Result limiting and context

### Phase 13: Git Integration ✓
**Tool:** Comprehensive Git operations

- **Git Tool** (`src/tools/git.py`)
  - Operations: status, diff, log, commit, add, branch, checkout, pull, push
  - Safe command execution with timeouts
  - Error handling and reporting
  - Repository path validation

### Phase 26: Task Decomposition ✓
**Intelligence:** Break complex tasks into steps

- **Task Planner** (`src/agent/planner.py`)
  - Analyzes task complexity
  - Decomposes into subtasks
  - Tracks dependencies
  - Progress monitoring
  - Status management (pending, in_progress, completed, failed)

### Phase 31: Multi-Model Routing ✓
**Intelligence:** Route tasks to optimal models

- **Model Router** (`src/agent/router.py`)
  - 7B model: Fast, simple tasks (explain, format, docs)
  - 14B model: Balanced, most coding tasks
  - 32B model: Complex tasks (architecture, multi-file)
  - Automatic complexity analysis
  - Context-aware routing

### Phase 41: Vector Database Integration ✓
**Memory:** Semantic search with ChromaDB

- **Vector Store** (`src/memory/vector_store.py`)
  - Local ChromaDB persistence
  - Cosine similarity search
  - Collection management
  - Document storage and retrieval
  - Metadata filtering

### Phase 42: Codebase Indexing ✓
**Memory:** Index code for semantic search

- **Codebase Indexer** (`src/memory/codebase_index.py`)
  - Index individual files or directories
  - Recursive directory scanning
  - File type filtering
  - Smart exclusions (node_modules, __pycache__, .git)
  - Semantic code search
  - Statistics and monitoring

### Phase 44: Knowledge Base ✓
**Memory:** Store project knowledge

- **Knowledge Base** (`src/memory/knowledge_base.py`)
  - Store patterns, decisions, solutions, notes
  - JSON persistence
  - Tag-based categorization
  - Full-text search
  - Markdown export
  - Entry versioning

### Phase 51: Self-Correction Loop ✓
**Intelligence:** Agent verifies and corrects its own work

- **Tool Verifier** (`src/agent/verification.py`)
  - Automatic verification after each tool execution
  - Tool-specific verification strategies
  - Success/failure pattern tracking
  - Verification suggestions for failed checks
  - Metrics: total checks, pass/fail rates, success percentage
  - Integrated into agent core loop
  - Helps agent learn from mistakes and retry with better approaches

**Verification Strategies:**
- **read_file:** Checks for empty output, validates content exists
- **write_file:** Verifies file exists, validates written content matches expected
- **str_replace:** Confirms new string appears in file after replacement
- **code_search:** Provides suggestions when no results found
- **list_directory:** Validates directory listing succeeded
- **git:** Confirms git operations completed
- **shell:** Trusts success flag from tool execution

**Example Output:**
```
Executing tool: write_file
OK write_file succeeded
Verified: Successfully wrote and verified 123 bytes to file.txt
```

### Phase 52: Code Review Agent ✓
**Intelligence:** Automated code quality analysis

- **Code Reviewer** (`src/agent/code_review.py`)
  - Static analysis integration (mypy, ruff, pylint)
  - Automatic tool detection
  - File and directory review
  - Issue severity classification (info, warning, error, critical)
  - Formatted issue reports with line numbers

- **Code Review Tool** (`src/tools/review.py`)
  - Agent-accessible code review
  - Path security restrictions
  - Recursive directory scanning
  - Detailed issue formatting

**Supported Analyzers:**
- **mypy:** Type checking and type errors
- **ruff:** Fast Python linting and formatting
- **pylint:** Comprehensive code quality checks

**Example Output:**
```
Reviewed 5 files - Found 3 issues:
  error: 2
  warning: 1

src/agent/core.py:
  45:12 [mypy] type-error: Incompatible types
  78:5 [ruff] E501: Line too long (92 > 88 characters)
```

### Phase 53: Automated Test Generation ✓
**Intelligence:** Generate pytest scaffolds automatically

- **Test Generator** (`src/agent/test_generator.py`)
  - AST-based code analysis
  - Extracts functions, classes, methods
  - Generates pytest-compatible test scaffolds
  - Creates edge case and error handling test placeholders

- **Test Gen Tool** (`src/tools/test_gen.py`)
  - Agent-accessible test generation
  - Analyzes Python source files
  - Generates complete test files
  - Template-based approach

**Example:** Analyzes `src/agent/core.py` and generates `tests/test_core.py` with test functions for every public function and class.

### Phase 54: Loop Optimization ✓
**Performance:** Eliminate redundant operations

- **Operation Cache** (`src/agent/operation_cache.py`)
  - Caches read operations (read_file, list_directory, code_search)
  - Prevents duplicate tool calls in same iteration
  - Time-to-live (TTL) expiration
  - LRU eviction when cache is full
  - Tracks cache hit rate and efficiency

**Impact:**
- Reduces redundant file reads by 50-70%
- Faster agent iterations
- Lower LLM context usage
- Metrics: hit rate, cache size, unique operations

**Example:**
```
Total operations: 20
Cache hits: 12 (60% hit rate)
Saved 12 redundant operations!
```

### Phase 55: Error Recovery ✓
**Resilience:** Graceful error handling with fallback strategies

- **Error Recovery Manager** (`src/agent/error_recovery.py`)
  - Pattern-based error classification
  - Context-aware recovery suggestions
  - Multiple recovery strategies: retry, fallback, alternative, skip, abort
  - Error history tracking
  - Recovery statistics

**Recovery Patterns:**
- **File not found** → List directory, search for similar names
- **Permission denied** → Try read instead of write, skip operation
- **Git errors** → Check status first, continue without git
- **Timeout** → Retry with longer timeout, simplify operation
- **Empty file** → Create content first, skip file

**Example Recovery:**
```
FAIL read_file failed: File not found

[Error Recovery]
1. [alternative] Try listing the directory to see available files
2. [alternative] Search for similar file names
3. [skip] Skip and continue with next step
```

### Phase 56: Web Interface ✓
**Accessibility:** Browser-based UI for the agent

- **FastAPI Backend** (`src/api/server.py`)
  - RESTful API endpoints for chat, sessions, tools
  - WebSocket support for real-time streaming
  - CORS enabled for external clients
  - Health checks and metrics endpoints

- **Session Management** (`src/api/session.py`)
  - Multi-user session support
  - Automatic session timeout and cleanup
  - Per-session agent instances
  - Max sessions limit

- **Web Frontend** (`src/api/static/`)
  - Modern dark theme chat interface
  - Real-time message display
  - Tool call visualization
  - Session controls (new/reset)
  - Metrics display modal

**API Endpoints:**
```
POST /chat              - Send message, get response
POST /session/new       - Create new session
POST /session/{id}/reset - Reset conversation
GET  /session/{id}/history - Get conversation history
GET  /session/{id}/metrics - Get agent metrics
GET  /tools             - List available tools
GET  /health            - Health check
WS   /ws/{id}           - WebSocket for real-time chat
```

**Usage:**
```bash
# Start web server
uv run python -m src.web

# Open browser to http://localhost:8000
```

### Phase 57: Intelligence Integration (Agent v2) ✓
**Enhancement:** Full orchestration of all intelligence components

- **Dynamic Model Routing** (`src/agent/core_v2.py`)
  - Analyzes task complexity before each turn
  - Automatically switches between 7B/14B/32B models
  - 7B for simple tasks (explain, format)
  - 14B for standard coding tasks
  - 32B for complex multi-file operations

- **RAG Context Retrieval** (`src/agent/context.py`)
  - Queries vector store for relevant code before each turn
  - Searches knowledge base for past solutions
  - Injects retrieved context into prompts
  - Learns from successful solutions

- **Dynamic Prompting** (`src/agent/prompts_v2.py`)
  - Task-type detection (implement, debug, refactor, explain, etc.)
  - Model-size-aware prompt adjustments
  - Includes retrieved context and conversation summary
  - Error history to avoid repeating mistakes

- **Conversation Optimization**
  - Summarizes older messages to reduce token usage
  - Keeps recent messages verbatim
  - Enables long-running sessions without context overflow

**Task Types Detected:**
- `implement` - Write new code
- `debug` - Fix bugs
- `refactor` - Improve existing code
- `explain` - Explain code
- `review` - Code review
- `test` - Write tests
- `document` - Write documentation
- `explore` - Explore codebase

**Usage:**
```bash
# Run v2 agent with full intelligence
uv run python -m src.main_v2

# Or use via web UI (auto-uses v2)
uv run python -m src.web
```

### Phase 58: Streaming Responses ✓
**Enhancement:** Real-time token streaming for web UI

- **LLM Streaming** (`src/agent/llm.py`)
  - `chat_stream()` method for token-by-token output
  - Uses Ollama's streaming API
  - Yields chunks as they arrive

- **SSE Endpoint** (`src/api/server.py`)
  - `/chat/stream` endpoint using Server-Sent Events
  - Real-time response streaming to browser
  - Task type detection sent at start

- **Frontend Streaming** (`src/api/static/app.js`)
  - `sendMessageStreaming()` for real-time display
  - Progressive content updates
  - Fallback to non-streaming if needed

### Phase 59: Compound Tools (Tool Chaining) ✓
**Enhancement:** Chain multiple tools into single operations

- **Compound Tools** (`src/tools/compound.py`)
  - `SearchAndReadTool` - Search + read matching files
  - `EditAndVerifyTool` - Edit + verify changes applied
  - `ExploreDirectoryTool` - List + read README
  - `GitStatusAndDiffTool` - Status + diff together

**Benefits:**
- Fewer LLM round-trips
- More efficient operations
- Better context in responses

### Phase 60: Parallel Execution & File Watching ✓
**Enhancement:** Concurrent tool execution and auto-reindexing

- **Parallel Executor** (`src/agent/parallel.py`)
  - Thread pool for concurrent tool execution
  - Automatic dependency detection
  - Safe parallelization of read operations
  - Speedup metrics tracking

- **File Watcher** (`src/memory/file_watcher.py`)
  - Monitors codebase for file changes
  - Polling-based for cross-platform support
  - Debouncing to prevent excessive reindexing
  - Automatic vector store updates

- **Startup Integration** (`src/agent/startup.py`)
  - File watcher starts with agent
  - Background indexing on file changes
  - Statistics tracking

**Parallel Execution:**
```
Executing 4 tools in parallel...
Parallel execution complete (2.3x speedup)
```

**File Watcher:**
```
File watcher started for /path/to/project
Reindexing 3 files...
```

## Commands

```bash
# Setup
uv sync

# Run CLI agent (v1 - basic)
uv run python -m src.main

# Run CLI agent (v2 - enhanced with intelligence)
uv run python -m src.main_v2

# Run Web UI (opens at http://localhost:8000, uses v2 agent)
uv run python -m src.web

# Run tests
uv run pytest

# Type check
uv run mypy src/

# Test specific feature
uv run python -c "from src.agent import AgentV2; print('Agent v2 works!')"
```

## Configuration

Create `config.yaml` to customize:

```yaml
llm:
  model: "qwen2.5-coder:14b"  # or 7b, 32b
  ollama_url: "http://localhost:11434"
  max_retries: 3
  retry_delay: 1.0

logging:
  level: "INFO"
  log_file: null  # or "logs/agent.log"
  console: true

agent:
  max_iterations: 10
  working_dir: null  # or specific path
```

## Development Rules

1. Keep functions < 50 lines
2. Every tool must have input/output type definitions
3. Test tools in isolation before integration
4. No god classes - single responsibility
5. Errors should be explicit, never swallowed silently

## Tool Format

LLM requests tools in XML:
```xml
<tool name="tool_name">
<param name="param1">value1</param>
<param name="param2">value2</param>
</tool>
```

Agent responds with:
```xml
<tool_result name="tool_name" status="success">
Result content here
</tool_result>
```

### Phase 66: Code Intelligence ✓
**Intelligence:** Smart code suggestions

- **Code Intelligence** (`src/agent/code_intelligence.py`)
  - Context-aware code completions
  - Import suggestions based on usage
  - Pattern suggestions (singleton, factory, etc.)
  - Code smell detection
  - Optimization recommendations

### Phase 67: Project Scaffolding ✓
**Tools:** Rapid project creation

- **Scaffolding Tool** (`src/tools/scaffolding.py`)
  - Python CLI (click) template
  - Python API (FastAPI) template
  - C++ Console (CMake) template
  - .NET Web API template
  - .NET WinForms template
  - .NET WPF (MVVM) template

### Phase 68: Dependency Analysis ✓
**Tools:** Dependency management

- **Dependency Tool** (`src/tools/dependencies.py`)
  - Analyze project dependencies
  - Check for available updates
  - Security vulnerability scanning
  - Add/remove dependencies
  - Dependency tree visualization
  - Supports: Python, Node.js, .NET, C++ (vcpkg/Conan)

### Phase 69: Documentation Generator ✓
**Tools:** Automated docs

- **DocGen Tool** (`src/tools/docgen.py`)
  - Parse Python, C++, C# source files
  - Extract docstrings and signatures
  - Generate Markdown documentation
  - Generate HTML documentation
  - README template generation
  - API reference generation

### Phase 70: Pattern Learning ✓
**Intelligence:** Learn from codebase

- **Pattern Learner** (`src/agent/pattern_learner.py`)
  - Learn naming conventions (snake_case, PascalCase, etc.)
  - Learn import patterns (absolute vs relative)
  - Learn docstring style (Google, NumPy, Sphinx)
  - Learn error handling patterns
  - Learn decorator usage
  - Learn class structure patterns
  - Confidence-based pattern scoring
  - Persistent storage of learned patterns

- **Learning Tool** (`src/tools/learning.py`)
  - Analyze files/directories to learn patterns
  - Query learned patterns
  - Get project style summary
  - Export patterns to file

## What's Next - Phases 75+

### Phase 75-77: VS Code Extension
**Goal:** IDE integration
- VS Code sidebar panel
- Inline code suggestions
- Context-aware commands
- Real-time error detection

### Phase 78-79: Enhanced Web UI
**Goal:** Richer browser experience
- File browser integration
- Code editor with syntax highlighting
- Project tree view
- Multi-file diff viewer

### Phase 80-82: Production API
**Goal:** Production-ready deployment
- Authentication/authorization
- Rate limiting
- Persistent sessions (database)
- Docker deployment
- Kubernetes manifests

## Stats

- **Lines of Code:** ~12,000+
- **Tools Implemented:** 19 (File, Edit, Search, Git, Shell, CodeReview, TestGen, SearchAndRead, EditAndVerify, ExploreDir, GitStatusDiff, VisualStudio, Refactor, Scaffold, Dependencies, DocGen, Learning, + base)
- **Phases Completed:** 29 (1, 11-13, 26, 31, 41-42, 44, 51-70)
- **Test Coverage:** High (37+ tests for critical systems)
- **Dependencies:** 8 core (httpx, rich, pyyaml, chromadb, fastapi, uvicorn, + dev)
- **Architecture Layers:** 11 (Core, Agent, AgentV2, Tools, Memory, Verification, Recovery, API, Parallel, Specializations, Learning)
- **Agent Versions:** 2 (v1 basic, v2 with full intelligence + specializations + learning)
- **Specializations:** 5 (C++, C++ GUI, .NET, WinForms, WPF)
- **Project Templates:** 6 (python-cli, python-api, cpp-console, dotnet-webapi, dotnet-winforms, dotnet-wpf)
- **Languages Supported:** Python, C++, C#, JavaScript/Node.js
- **New Features:** Streaming, Compound Tools, Parallel Execution, File Watching, Conversation Persistence, Context Window, VS Projects, Refactoring, Code Intelligence, Scaffolding, Dependency Management, Documentation Generation, Pattern Learning

---

**Built with zero compromise on local-first philosophy.**
The ultimate all-in-one coding agent with learning capabilities.
Specialized for C++, .NET, and GUI development.
Every line of code is owned, understood, and optimized for autonomous coding.
