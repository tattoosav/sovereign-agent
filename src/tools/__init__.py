"""Tools package for the Sovereign Agent."""

from .base import BaseTool, ToolRegistry, ToolResult
from .editor import StrReplaceTool
from .filesystem import ListDirectoryTool, ReadFileTool, WriteFileTool
from .git import GitTool
from .review import CodeReviewTool
from .search import CodeSearchTool
from .shell import ShellTool
from .test_gen import TestGenTool
from .compound import (
    SearchAndReadTool,
    EditAndVerifyTool,
    ExploreDirectoryTool,
    GitStatusAndDiffTool,
    register_compound_tools,
)
from .visual_studio import VisualStudioTool
from .refactor import RefactorTool
from .scaffolding import ScaffoldingTool
from .dependencies import DependencyTool
from .docgen import DocGenTool
from .learning import LearningTool
from .web_research import WebResearchTool
from .vision import VisionTool, ScreenshotTool

__all__ = [
    # Base
    "BaseTool",
    "ToolRegistry",
    "ToolResult",
    # Core tools
    "ReadFileTool",
    "WriteFileTool",
    "ListDirectoryTool",
    "ShellTool",
    "StrReplaceTool",
    "CodeSearchTool",
    "GitTool",
    "CodeReviewTool",
    "TestGenTool",
    # Compound tools
    "SearchAndReadTool",
    "EditAndVerifyTool",
    "ExploreDirectoryTool",
    "GitStatusAndDiffTool",
    "register_compound_tools",
    # Specialized tools
    "VisualStudioTool",
    "RefactorTool",
    "ScaffoldingTool",
    "DependencyTool",
    "DocGenTool",
    "LearningTool",
    # Research & Vision
    "WebResearchTool",
    "VisionTool",
    "ScreenshotTool",
]
