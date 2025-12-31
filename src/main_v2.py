"""
Sovereign Agent v2 - Enhanced Entry Point

Run with: uv run python -m src.main_v2

Features over v1:
- Dynamic model routing (7B/14B/32B based on task complexity)
- RAG context retrieval (learns from past solutions)
- Task-specific prompting (implement, debug, refactor, etc.)
- Conversation summarization (handles long chats)
- Feedback loop (learns from errors and successes)
"""

import logging
import signal
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

from src.agent import AgentV2, AgentConfigV2
from src.core import load_config, setup_logging
from src.memory import KnowledgeBase, VectorStore
from src.tools import (
    CodeSearchTool,
    GitTool,
    ListDirectoryTool,
    ReadFileTool,
    ShellTool,
    StrReplaceTool,
    ToolRegistry,
    WriteFileTool,
)

logger = logging.getLogger(__name__)


def print_banner(console: Console) -> None:
    """Print the startup banner."""
    banner = """\
  ╔═══════════════════════════════════════════════════════════════╗
  ║              SOVEREIGN AGENT v2                               ║
  ║              Enhanced Intelligence Edition                    ║
  ╚═══════════════════════════════════════════════════════════════╝

  New in v2:
  • Dynamic model routing (7B/14B/32B)
  • RAG context retrieval
  • Task-specific prompting
  • Learning from past solutions
    """
    console.print(Panel(banner, style="cyan"))


# Global flag for graceful shutdown
shutdown_requested = False


def signal_handler(signum: int, frame: object) -> None:
    """Handle shutdown signals gracefully."""
    global shutdown_requested
    shutdown_requested = True
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    print("\n\nShutdown requested. Finishing current operation...")


def setup_signal_handlers() -> None:
    """Set up signal handlers for graceful shutdown."""
    signal.signal(signal.SIGINT, signal_handler)
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, signal_handler)


def setup_tools(working_dir: Path) -> ToolRegistry:
    """Set up the tool registry with all available tools."""
    registry = ToolRegistry()

    allowed_paths = [working_dir]
    registry.register(ReadFileTool(allowed_paths=allowed_paths))
    registry.register(WriteFileTool(allowed_paths=allowed_paths))
    registry.register(ListDirectoryTool(allowed_paths=allowed_paths))
    registry.register(StrReplaceTool(allowed_paths=allowed_paths))
    registry.register(CodeSearchTool(allowed_paths=allowed_paths))
    registry.register(GitTool(allowed_paths=allowed_paths))
    registry.register(ShellTool(
        timeout=30,
        blocked_commands=["rm -rf /", "rm -rf ~", "mkfs", "dd if="],
    ))

    logger.info(f"Registered {len(registry.all_tools())} tools")
    return registry


def main() -> None:
    """Main entry point for v2 agent."""
    # Load configuration
    config = load_config()

    # Setup logging
    log_file = Path(config.logging.log_file) if config.logging.log_file else None
    setup_logging(
        level=config.logging.level,
        log_file=log_file,
        console=config.logging.console,
        json_format=config.logging.json_format,
    )

    logger.info("Starting Sovereign Agent v2")

    # Setup signal handlers
    setup_signal_handlers()

    console = Console()
    print_banner(console)

    # Set working directory
    working_dir = Path(config.agent.working_dir) if config.agent.working_dir else Path.cwd()
    logger.info(f"Working directory: {working_dir}")
    console.print(f"[dim]Working directory: {working_dir}[/dim]")

    # Setup tools
    tools = setup_tools(working_dir)
    console.print(f"[dim]Loaded {len(tools.all_tools())} tools: {', '.join(t.name for t in tools.all_tools())}[/dim]")

    # Initialize memory systems
    console.print("[dim]Initializing memory systems...[/dim]")
    vector_store = VectorStore()
    knowledge_base = KnowledgeBase()

    kb_stats = knowledge_base.get_stats()
    console.print(f"[dim]Knowledge base: {kb_stats['total_entries']} entries[/dim]")

    # Create v2 agent config
    agent_config = AgentConfigV2(
        model=config.llm.model,
        ollama_url=config.llm.ollama_url,
        max_iterations=config.agent.max_iterations,
        temperature=config.llm.temperature,
        max_retries=config.llm.max_retries,
        retry_delay=config.llm.retry_delay,
        # v2 features enabled
        enable_routing=True,
        enable_rag=True,
        enable_planning=True,
        enable_learning=True,
    )

    # Create v2 agent
    agent = AgentV2(
        config=agent_config,
        tools=tools,
        vector_store=vector_store,
        knowledge_base=knowledge_base,
    )

    # Check Ollama
    if not agent.llm.is_available():
        console.print("[red]Error: Cannot connect to Ollama server.[/red]")
        console.print("[yellow]Make sure Ollama is running: ollama serve[/yellow]")
        sys.exit(1)

    if not agent.llm.model_exists():
        console.print(f"[red]Error: Model '{config.llm.model}' not found.[/red]")
        console.print(f"[yellow]Pull it with: ollama pull {config.llm.model}[/yellow]")
        sys.exit(1)

    console.print(f"[green]✓ Connected to Ollama[/green]")
    console.print(f"[green]✓ Dynamic routing enabled (7B/14B/32B)[/green]")
    console.print(f"[green]✓ RAG context retrieval enabled[/green]")
    console.print()
    console.print("[dim]Commands: 'exit' to quit, 'clear' to reset, 'metrics' for stats[/dim]")
    console.print()

    # Main loop
    try:
        while not shutdown_requested:
            try:
                user_input = console.input("[bold green]You:[/bold green] ").strip()
            except EOFError:
                logger.info("EOF received, exiting")
                break

            if shutdown_requested:
                break

            if not user_input:
                continue

            if user_input.lower() == "exit":
                console.print("[dim]Goodbye![/dim]")
                break

            if user_input.lower() == "clear":
                agent.reset()
                console.print("[dim]Conversation cleared.[/dim]")
                continue

            if user_input.lower() == "metrics":
                agent.display_comprehensive_metrics()
                continue

            # Run the v2 agent
            logger.debug(f"Processing: {user_input[:50]}...")
            result = agent.run_turn(user_input)

            # Display response
            agent.display_response(result.response)

            # Show turn info
            console.print(f"[dim]Model: {result.model_used} | Task: {result.task_type.value} | Iterations: {result.iterations}[/dim]")
            console.print()

    except KeyboardInterrupt:
        console.print("\n[dim]Interrupted. Goodbye![/dim]")

    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        console.print(f"[red]Fatal error: {e}[/red]")
        sys.exit(1)

    finally:
        logger.info("Cleaning up...")
        agent.close()
        logger.info("Sovereign Agent v2 stopped")


if __name__ == "__main__":
    main()
