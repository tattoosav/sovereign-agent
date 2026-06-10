"""
Sovereign Agent - Autonomous Daemon Entry Point.

Runs the self-directed task loop. Drop tasks into <working-dir>/tasks/inbox/ and
results appear in <working-dir>/tasks/done/. Designed to run as a Windows service
(NSSM) that auto-starts at boot.

Run with: python -m src.autonomous --working-dir C:\\Sovereign\\workspace
"""

import argparse
import logging
import signal
import sys
from pathlib import Path

from src.agent.autonomous import AutonomousConfig, AutonomousRunner
from src.core import load_config, setup_logging
from src.core.egress_guard import EgressViolation

logger = logging.getLogger(__name__)


def main() -> None:
    """Parse args, build the runner, and run until stopped."""
    parser = argparse.ArgumentParser(description="Sovereign Agent Autonomous Daemon")
    parser.add_argument("--working-dir", default=None, help="Workspace + task queue root")
    parser.add_argument("--poll", type=float, default=5.0, help="Poll interval (seconds)")
    args = parser.parse_args()

    config = load_config()
    log_file = Path(config.logging.log_file) if config.logging.log_file else Path("logs/autonomous.log")
    setup_logging(level=config.logging.level, log_file=log_file, console=config.logging.console)

    working_dir = Path(args.working_dir or config.agent.working_dir or Path.cwd())
    logger.info(f"Starting autonomous daemon (working_dir={working_dir})")

    try:
        runner = AutonomousRunner(AutonomousConfig(
            working_dir=working_dir,
            poll_interval=args.poll,
        ))
    except EgressViolation as e:
        logger.critical(str(e))
        print(f"\nAIR-GAP VIOLATION: {e}")
        sys.exit(1)

    _install_signal_handlers(runner)

    try:
        runner.run_forever()
    except Exception as e:
        logger.exception(f"Fatal daemon error: {e}")
        sys.exit(1)


def _install_signal_handlers(runner: AutonomousRunner) -> None:
    """Wire SIGINT/SIGTERM/SIGBREAK to a graceful stop."""
    def handler(signum: int, frame: object) -> None:
        logger.info(f"Received signal {signum}; stopping after current task...")
        runner.stop()

    signal.signal(signal.SIGINT, handler)
    for name in ("SIGTERM", "SIGBREAK"):  # SIGBREAK is Windows-only
        sig = getattr(signal, name, None)
        if sig is not None:
            signal.signal(sig, handler)


if __name__ == "__main__":
    main()
