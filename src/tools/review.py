"""
Code Review Tool

Allows the agent to review code quality using static analysis.
"""

from pathlib import Path
from typing import Any

from src.agent.code_review import CodeReviewer
from .base import BaseTool, ToolResult


class CodeReviewTool(BaseTool):
    """Review Python code for quality issues."""

    def __init__(self, allowed_paths: list[Path] | None = None):
        self.allowed_paths = allowed_paths or []
        self.reviewer = CodeReviewer()

    @property
    def name(self) -> str:
        return "code_review"

    @property
    def description(self) -> str:
        return """Review Python code for quality, type errors, and best practices.

Parameters:
- path: File or directory to review
- recursive: If path is directory, review recursively (default: true)

Returns formatted report of issues found.

Tools used (if available):
- mypy: Type checking
- ruff: Linting and style
- pylint: Code quality

Example:
<tool name="code_review">
<param name="path">src/agent/core.py</param>
</tool>"""

    @property
    def parameters(self) -> dict[str, dict[str, Any]]:
        return {
            "path": {
                "type": "string",
                "description": "File or directory path to review",
                "required": True
            },
            "recursive": {
                "type": "string",
                "description": "Review directory recursively (true/false, default: true)",
                "required": False
            }
        }

    def _check_path_allowed(self, path: Path) -> bool:
        """Check if path is within allowed directories."""
        if not self.allowed_paths:
            return True

        path = path.resolve()
        return any(
            path == allowed or path.is_relative_to(allowed)
            for allowed in self.allowed_paths
        )

    def execute(self, **kwargs: Any) -> ToolResult:
        """Execute code review."""
        path_str = kwargs.get("path")
        if not path_str:
            return ToolResult(
                success=False,
                output="",
                error="Missing required parameter: path"
            )

        path = Path(path_str).resolve()

        # Security check
        if not self._check_path_allowed(path):
            return ToolResult(
                success=False,
                output="",
                error=f"Path not allowed: {path}"
            )

        if not path.exists():
            return ToolResult(
                success=False,
                output="",
                error=f"Path does not exist: {path}"
            )

        # Review file or directory
        if path.is_file():
            result = self.reviewer.review_file(path)
            output = self.reviewer.format_issues(result)

            return ToolResult(
                success=result.success,
                output=output,
                error=None if result.success else result.summary
            )

        elif path.is_dir():
            recursive = kwargs.get("recursive", "true").lower() == "true"
            results = self.reviewer.review_directory(path, recursive=recursive)

            # Combine all results
            all_output = []
            total_issues = 0

            for file_path, result in results.items():
                if result.issues:
                    total_issues += len(result.issues)
                    all_output.append(self.reviewer.format_issues(result))

            if total_issues == 0:
                output = f"Reviewed {len(results)} files - No issues found!"
            else:
                output = f"Reviewed {len(results)} files - Found {total_issues} issues:\n\n"
                output += "\n\n".join(all_output)

            return ToolResult(
                success=True,
                output=output
            )

        else:
            return ToolResult(
                success=False,
                output="",
                error=f"Path is neither file nor directory: {path}"
            )
