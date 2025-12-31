"""
Sovereign Agent - Main Entry Point

Run with: uv run python -m src.main
"""

import logging
import signal
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

from src.agent import Agent, AgentConfig
from src.core import load_config, setup_logging
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
  ║              SOVEREIGN AGENT                                   ║
  ║              Your Local Coding Assistant                       ║
  ╚═══════════════════════════════════════════════════════════════╝
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

    # Filesystem tools - restricted to working directory
    allowed_paths = [working_dir]
    registry.register(ReadFileTool(allowed_paths=allowed_paths))
    registry.register(WriteFileTool(allowed_paths=allowed_paths))
    registry.register(ListDirectoryTool(allowed_paths=allowed_paths))
    registry.register(StrReplaceTool(allowed_paths=allowed_paths))
    registry.register(CodeSearchTool(allowed_paths=allowed_paths))
    registry.register(GitTool(allowed_paths=allowed_paths))

    # Shell tool - with safety restrictions
    registry.register(ShellTool(
        timeout=30,
        blocked_commands=["rm -rf /", "rm -rf ~", "mkfs", "dd if="],
    ))

    logger.info(f"Registered {len(registry.all_tools())} tools")
    return registry


def main() -> None:
    """Main entry point."""
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

    logger.info("Starting Sovereign Agent")
    logger.info(f"Configuration: model={config.llm.model}, max_iterations={config.agent.max_iterations}")

    # Setup signal handlers for graceful shutdown
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

    # Create agent config from loaded config
    agent_config = AgentConfig(
        model=config.llm.model,
        ollama_url=config.llm.ollama_url,
        max_iterations=config.agent.max_iterations,
        temperature=config.llm.temperature,
        max_retries=config.llm.max_retries,
        retry_delay=config.llm.retry_delay,
    )

    # Create agent
    agent = Agent(config=agent_config, tools=tools)
    
    # Check if Ollama is available
    if not agent.llm.is_available():
        console.print("[red]Error: Cannot connect to Ollama server.[/red]")
        console.print("[yellow]Make sure Ollama is running: ollama serve[/yellow]")
        sys.exit(1)
    
    if not agent.llm.model_exists():
        console.print(f"[red]Error: Model '{config.model}' not found.[/red]")
        console.print(f"[yellow]Pull it with: ollama pull {config.model}[/yellow]")
        sys.exit(1)
    
    console.print(f"[green]✓ Connected to Ollama with model: {config.model}[/green]")
    console.print()
    console.print("[dim]Commands: 'exit' to quit, 'clear' to reset conversation[/dim]")
    console.print()
    
    # Main loop
    try:
        while not shutdown_requested:
            # Get user input
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
                logger.info("User requested exit")
                console.print("[dim]Goodbye![/dim]")
                break

            if user_input.lower() == "clear":
                agent.reset()
                logger.info("Conversation cleared")
                console.print("[dim]Conversation cleared.[/dim]")
                continue

            # Run the agent
            logger.debug(f"Processing user input: {user_input[:50]}...")
            response = agent.run_turn(user_input)
            agent.display_response(response)
            console.print()

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
        console.print("\n[dim]Interrupted. Goodbye![/dim]")

    except Exception as e:
        logger.exception(f"Unexpected error in main loop: {e}")
        console.print(f"[red]Fatal error: {e}[/red]")
        sys.exit(1)

    finally:
        logger.info("Cleaning up and shutting down")
        agent.close()
        logger.info("Sovereign Agent stopped")


if __name__ == "__main__":
    main()
