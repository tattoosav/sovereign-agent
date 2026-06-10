"""
Central tool-registration factory for the air-gapped build.

This is the ONLY place that builds a populated ToolRegistry. The internet-capable
tools (web research, package-registry dependency checks) have been removed from the
codebase entirely, so there is no egress branch here: nothing network-capable is
importable or registrable. Every tool wired up below is local-only.
"""

import logging
from pathlib import Path

from .base import BaseTool, ToolRegistry
from .compound import register_compound_tools
from .crm_tool import CRMTool
from .dependencies import DependencyTool
from .docgen import DocGenTool
from .filesystem import ListDirectoryTool, ReadFileTool, WriteFileTool
from .editor import StrReplaceTool
from .git import GitTool
from .learning import LearningTool
from .python_exec import PythonExecTool
from .refactor import RefactorTool
from .review import CodeReviewTool
from .scaffolding import ScaffoldingTool
from .search import CodeSearchTool
from .shell import ShellTool
from .test_gen import TestGenTool
from .vision import ScreenshotTool, VisionTool
from .visual_studio import VisualStudioTool

logger = logging.getLogger(__name__)


def build_registry(
    working_dir: Path,
    *,
    shell_timeout: int = 300,
    shell_allowlist: bool = True,
    shell_allowed: list[str] | None = None,
    ollama_url: str = "http://127.0.0.1:11434",
    allowed_paths: list[Path] | None = None,
    extra_tools: list[BaseTool] | None = None,
) -> ToolRegistry:
    """Build the full local (air-gapped) tool registry.

    There is no network-capable tool registered here by design.
    """
    registry = ToolRegistry()
    paths = allowed_paths if allowed_paths is not None else [working_dir]

    _register_core(registry, paths)
    _register_shell(registry, working_dir, shell_timeout, shell_allowlist, shell_allowed)
    _register_specialized(registry, working_dir, ollama_url)

    # CRM (local SQLite under the workspace) — the primary purpose of this build.
    registry.register(CRMTool(db_path=working_dir / ".sovereign" / "crm.db"))

    # Compound tools build on top of the core tools registered above.
    base = {t.name: t for t in registry.all_tools()}
    register_compound_tools(registry, base)

    for tool in extra_tools or []:
        registry.register(tool)

    logger.info(f"Registered {len(registry.all_tools())} local tools (air-gapped)")
    return registry


def _register_core(registry: ToolRegistry, paths: list[Path]) -> None:
    """Register path-restricted core file/search/git tools."""
    registry.register(ReadFileTool(allowed_paths=paths))
    registry.register(WriteFileTool(allowed_paths=paths))
    registry.register(ListDirectoryTool(allowed_paths=paths))
    registry.register(StrReplaceTool(allowed_paths=paths))
    registry.register(CodeSearchTool(allowed_paths=paths))
    registry.register(GitTool(allowed_paths=paths))
    registry.register(CodeReviewTool(allowed_paths=paths))
    registry.register(TestGenTool(allowed_paths=paths))


def _register_shell(
    registry: ToolRegistry,
    working_dir: Path,
    timeout: int,
    allowlist: bool,
    allowed: list[str] | None,
) -> None:
    """Register shell + python execution, restricted to the working dir."""
    registry.register(ShellTool(
        timeout=timeout,
        allowed_commands=allowed if allowlist else None,
        cwd=working_dir,
    ))
    registry.register(PythonExecTool(timeout=timeout, working_dir=working_dir))


def _register_specialized(
    registry: ToolRegistry,
    working_dir: Path,
    ollama_url: str,
) -> None:
    """Register the local, all-in-one specialized tools (no network)."""
    registry.register(VisualStudioTool(working_dir=working_dir))
    registry.register(RefactorTool(working_dir=working_dir))
    registry.register(ScaffoldingTool())
    registry.register(DependencyTool())  # offline analyze-only
    registry.register(DocGenTool())
    registry.register(LearningTool())
    registry.register(VisionTool(ollama_url=ollama_url))
    registry.register(ScreenshotTool())
