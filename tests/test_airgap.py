"""Tests that the air-gap hardening holds: no egress tools, locked shell, local CORS."""

import importlib
from pathlib import Path

import pytest

from src.core.config import DEFAULT_SHELL_ALLOWED, load_config
from src.tools import build_registry
from src.tools.shell import ShellTool


def _registry(tmp_path: Path):
    return build_registry(tmp_path, shell_allowed=DEFAULT_SHELL_ALLOWED)


def test_web_research_module_deleted():
    """The internet research tool must be gone from the codebase entirely."""
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("src.tools.web_research")


def test_egress_tool_not_registered(tmp_path):
    reg = _registry(tmp_path)
    assert reg.get("web_research") is None
    # Core local tools are still present (all-in-one).
    for name in ["read_file", "write_file", "shell", "git", "code_search"]:
        assert reg.get(name) is not None


def test_dependencies_is_analyze_only(tmp_path):
    reg = _registry(tmp_path)
    dep = reg.get("dependencies")
    assert dep is not None
    for op in ["check_updates", "check_security", "add", "remove", "update"]:
        result = dep.execute(operation=op, path=str(tmp_path))
        assert not result.success
        assert "air-gapped" in (result.error or "").lower()


def test_shell_blocks_network_commands():
    sh = ShellTool(allowed_commands=DEFAULT_SHELL_ALLOWED)
    for cmd in ["curl http://x", "pip install requests", "Invoke-WebRequest x",
                "git push origin main", "wget http://x"]:
        allowed, _ = sh._is_command_allowed(cmd)
        assert not allowed, f"should block: {cmd}"


def test_shell_allows_local_commands():
    sh = ShellTool(allowed_commands=DEFAULT_SHELL_ALLOWED)
    for cmd in ["git status", "python script.py", "pytest -q"]:
        allowed, reason = sh._is_command_allowed(cmd)
        assert allowed, f"should allow: {cmd} ({reason})"


def test_shell_cwd_restricted(tmp_path):
    sh = ShellTool(cwd=tmp_path)
    assert sh._cwd == str(tmp_path)
    sh2 = ShellTool()
    assert sh2._cwd is None


def test_cors_origins_local_only():
    from src.api.server import _local_cors_origins
    origins = _local_cors_origins(["127.0.0.1", "localhost"], 8000)
    assert "*" not in origins
    assert "http://127.0.0.1:8000" in origins
    assert all(o.startswith("http://127.0.0.1") or o.startswith("http://localhost")
               for o in origins)


def test_validate_host_rejects_nonlocal():
    from src.web import _validate_host
    allowed = ["127.0.0.1", "localhost"]
    assert _validate_host("127.0.0.1", allowed)
    assert not _validate_host("0.0.0.0", allowed)
    assert not _validate_host("192.168.1.10", allowed)


def test_no_external_url_literals_in_tools():
    """No tool source may reference an external search/fetch endpoint."""
    banned = ["duckduckgo", "https://html.duckduckgo", "api.openai", "anthropic.com"]
    tools_dir = Path(__file__).parent.parent / "src" / "tools"
    for py in tools_dir.glob("*.py"):
        text = py.read_text(encoding="utf-8").lower()
        for needle in banned:
            assert needle not in text, f"{py.name} references {needle}"


def test_airgap_config_defaults():
    config = load_config()
    assert config.airgap.enforce_egress_check is True
    assert config.airgap.shell_allowlist_mode is True
    assert "127.0.0.1" in config.airgap.allowed_hosts
