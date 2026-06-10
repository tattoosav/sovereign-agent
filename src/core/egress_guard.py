"""
Startup egress self-check for the air-gapped build.

Confirms the ONLY connection we want (local Ollama) is reachable, and that a known
external host is NOT reachable. Offline-safe: every probe is short and wrapped, so it
never blocks. When enforcement is on, a detected egress path aborts startup.

Run standalone for an operator report:
    python -m src.core.egress_guard
"""

import logging
import socket
import time
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

# Hosts probed to confirm the box cannot reach the public internet.
# These are well-known anycast addresses; a refused/timed-out connect is GOOD.
_EXTERNAL_PROBES = [("1.1.1.1", 443), ("8.8.8.8", 443)]
_PROBE_TIMEOUT = 1.5


class EgressViolation(Exception):
    """Raised when outbound internet access is detected in enforce mode."""


@dataclass
class EgressReport:
    """Result of an egress self-check."""
    ollama_ok: bool
    external_blocked: bool
    allowed_url: str
    checked_at: float

    def summary(self) -> str:
        ok = "OK" if self.ollama_ok else "UNREACHABLE"
        blocked = "BLOCKED" if self.external_blocked else "REACHABLE (!)"
        return (
            f"Egress check: Ollama={ok} ({self.allowed_url}) | "
            f"external internet={blocked}"
        )


def _ollama_reachable(url: str) -> bool:
    """Return True if local Ollama answers at the allowed URL."""
    try:
        resp = httpx.get(f"{url.rstrip('/')}/api/tags", timeout=3.0)
        return resp.status_code == 200
    except Exception as e:
        logger.warning(f"Ollama not reachable at {url}: {e}")
        return False


def _external_reachable() -> bool:
    """Return True if any external host accepts a TCP connection (= egress!)."""
    for host, port in _EXTERNAL_PROBES:
        try:
            with socket.create_connection((host, port), timeout=_PROBE_TIMEOUT):
                logger.critical(f"EGRESS DETECTED: connected to {host}:{port}")
                return True
        except OSError:
            continue  # Refused/timeout = air-gapped, as expected.
    return False


def assert_airgap(config: object) -> EgressReport:
    """Verify air-gap posture; raise EgressViolation if egress is found in enforce mode."""
    airgap = getattr(config, "airgap", None)
    allowed = getattr(airgap, "allowed_egress", ["http://127.0.0.1:11434"])
    enforce = getattr(airgap, "enforce_egress_check", True)
    url = allowed[0] if allowed else "http://127.0.0.1:11434"

    report = EgressReport(
        ollama_ok=_ollama_reachable(url),
        external_blocked=not _external_reachable(),
        allowed_url=url,
        checked_at=time.time(),
    )
    logger.info(report.summary())

    if not report.external_blocked and enforce:
        raise EgressViolation(
            "Outbound internet access detected. This build must run air-gapped. "
            "Disconnect the network or set SOVEREIGN_AIRGAP_ENFORCE=false to override."
        )
    return report


def main() -> None:
    """Operator entry point: print the egress report."""
    from src.core.config import load_config

    logging.basicConfig(level=logging.INFO)
    try:
        report = assert_airgap(load_config())
        print(report.summary())
    except EgressViolation as e:
        print(f"FAIL: {e}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
