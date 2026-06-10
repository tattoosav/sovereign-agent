"""
Configuration management system.

Supports:
- YAML configuration files
- Environment variable overrides
- Sensible defaults
- Validation
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml


@dataclass
class LLMConfig:
    """LLM configuration."""
    model: str = "qwen2.5-coder:14b"
    ollama_url: str = "http://localhost:11434"
    timeout: float = 600.0  # 10 minutes for large code generation
    temperature: float = 0.1
    max_tokens: int = 16384  # 16K tokens for full file generation
    max_retries: int = 5  # More retries for reliability
    retry_delay: float = 2.0


@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: str = "INFO"
    log_file: Optional[str] = None
    console: bool = True
    json_format: bool = False


@dataclass
class AgentConfig:
    """Agent configuration."""
    max_iterations: int = 15  # Reasonable limit to prevent timeouts
    working_dir: Optional[str] = None


# Default curated allowlist for shell commands in the air-gapped build.
# Deliberately excludes anything that can reach the network (curl, wget,
# Invoke-WebRequest, pip install, npm, ssh, scp, ...).
DEFAULT_SHELL_ALLOWED = [
    # Python / build / test
    "python", "python3", "py", "pytest", "mypy", "ruff", "pylint",
    "cmake", "msbuild", "dotnet", "make", "ninja",
    # Version control (local ops)
    "git",
    # Safe file inspection (cross-platform)
    "dir", "type", "ls", "cat", "echo", "findstr", "where", "whoami",
    "cd", "mkdir", "copy", "move", "ren",
]


@dataclass
class AirgapConfig:
    """
    Air-gap enforcement settings.

    This build is permanently offline: the internet-capable tools are removed
    from the codebase entirely, so there is no `enabled` toggle to re-enable
    them. These settings govern host binding, shell restriction, and the
    startup egress self-check.
    """
    allowed_hosts: list[str] = field(
        default_factory=lambda: ["127.0.0.1", "localhost"]
    )
    allowed_egress: list[str] = field(
        default_factory=lambda: ["http://127.0.0.1:11434", "http://localhost:11434"]
    )
    enforce_egress_check: bool = True
    shell_allowlist_mode: bool = True
    shell_allowed_commands: list[str] = field(
        default_factory=lambda: list(DEFAULT_SHELL_ALLOWED)
    )


@dataclass
class Config:
    """Main configuration object."""
    llm: LLMConfig = field(default_factory=LLMConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    airgap: AirgapConfig = field(default_factory=AirgapConfig)


def load_config(config_path: Optional[Path] = None) -> Config:
    """
    Load configuration from file with environment variable overrides.

    Args:
        config_path: Path to config.yaml file. If None, looks for config.yaml
                    in current directory, then ~/.config/sovereign-agent/config.yaml

    Returns:
        Loaded configuration object
    """
    # Start with defaults
    config_dict: dict[str, Any] = {}

    # Find config file
    if config_path is None:
        # Check current directory first
        if Path("config.yaml").exists():
            config_path = Path("config.yaml")
        # Then check home directory
        elif Path.home().joinpath(".config", "sovereign-agent", "config.yaml").exists():
            config_path = Path.home().joinpath(".config", "sovereign-agent", "config.yaml")

    # Load from file if it exists
    if config_path and config_path.exists():
        with open(config_path) as f:
            file_config = yaml.safe_load(f) or {}
            config_dict.update(file_config)

    # Environment variable overrides
    env_overrides = {
        "llm": {
            "model": os.getenv("SOVEREIGN_MODEL"),
            "ollama_url": os.getenv("SOVEREIGN_OLLAMA_URL"),
            "timeout": _parse_float(os.getenv("SOVEREIGN_TIMEOUT")),
            "temperature": _parse_float(os.getenv("SOVEREIGN_TEMPERATURE")),
            "max_tokens": _parse_int(os.getenv("SOVEREIGN_MAX_TOKENS")),
            "max_retries": _parse_int(os.getenv("SOVEREIGN_MAX_RETRIES")),
            "retry_delay": _parse_float(os.getenv("SOVEREIGN_RETRY_DELAY")),
        },
        "logging": {
            "level": os.getenv("SOVEREIGN_LOG_LEVEL"),
            "log_file": os.getenv("SOVEREIGN_LOG_FILE"),
            "console": _parse_bool(os.getenv("SOVEREIGN_LOG_CONSOLE")),
            "json_format": _parse_bool(os.getenv("SOVEREIGN_LOG_JSON")),
        },
        "agent": {
            "max_iterations": _parse_int(os.getenv("SOVEREIGN_MAX_ITERATIONS")),
            "working_dir": os.getenv("SOVEREIGN_WORKING_DIR"),
        },
        "airgap": {
            "enforce_egress_check": _parse_bool(os.getenv("SOVEREIGN_AIRGAP_ENFORCE")),
            "shell_allowlist_mode": _parse_bool(os.getenv("SOVEREIGN_SHELL_ALLOWLIST")),
        },
    }

    # Merge environment overrides (only if value is not None)
    for section, values in env_overrides.items():
        if section not in config_dict:
            config_dict[section] = {}
        for key, value in values.items():
            if value is not None:
                config_dict[section][key] = value

    # Build config object
    llm_config = LLMConfig(**config_dict.get("llm", {}))
    logging_config = LoggingConfig(**config_dict.get("logging", {}))
    agent_config = AgentConfig(**config_dict.get("agent", {}))
    airgap_config = AirgapConfig(**config_dict.get("airgap", {}))

    return Config(
        llm=llm_config,
        logging=logging_config,
        agent=agent_config,
        airgap=airgap_config,
    )


def _parse_int(value: Optional[str]) -> Optional[int]:
    """Parse string to int, return None if invalid."""
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _parse_float(value: Optional[str]) -> Optional[float]:
    """Parse string to float, return None if invalid."""
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _parse_bool(value: Optional[str]) -> Optional[bool]:
    """Parse string to bool, return None if invalid."""
    if value is None:
        return None
    return value.lower() in ("true", "1", "yes", "y")
