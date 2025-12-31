"""
Sovereign Agent - Web Server Entry Point

Run with: uv run python -m src.web
"""

import logging
import sys
from pathlib import Path

import uvicorn

from src.api import create_app
from src.core import load_config, setup_logging

logger = logging.getLogger(__name__)


def main() -> None:
    """Main entry point for web server."""
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

    logger.info("Starting Sovereign Agent Web Server")

    # Create FastAPI app
    app = create_app()

    # Server configuration
    host = "127.0.0.1"
    port = 8000

    print(f"""
================================================================
          SOVEREIGN AGENT - WEB UI
          Your Local Coding Assistant
================================================================

Server starting at: http://{host}:{port}

Open your browser and navigate to the URL above.
Press Ctrl+C to stop the server.
    """)

    try:
        uvicorn.run(
            app,
            host=host,
            port=port,
            log_level="info",
        )
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
        print("\nServer stopped. Goodbye!")
    except Exception as e:
        logger.exception(f"Server error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
