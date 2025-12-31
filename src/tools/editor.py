"""
Code editing tool using string replacement.

This tool allows surgical edits to files without rewriting the entire file.
It's more token-efficient and precise than write_file for small changes.
"""

import difflib
from pathlib import Path
from typing import Any

from .base import BaseTool, ToolResult


class StrReplaceTool(BaseTool):
    """
    Replace an exact string in a file with new content.

    The old_str must appear exactly once in the file for safety.
    Returns a unified diff showing the changes made.
    """

    def __init__(self, allowed_paths: list[Path] | None = None):
        self._allowed_paths = allowed_paths

    @property
    def name(self) -> str:
        return "str_replace"

    @property
    def description(self) -> str:
        return (
            "Replace an exact string in a file. The old_str must appear exactly "
            "once in the file. Returns a diff preview of the changes."
        )

    @property
    def parameters(self) -> dict[str, dict[str, Any]]:
        return {
            "path": {
                "type": "string",
                "description": "Path to the file to edit",
                "required": True
            },
            "old_str": {
                "type": "string",
                "description": "Exact string to find (must be unique in file)",
                "required": True
            },
            "new_str": {
                "type": "string",
                "description": "String to replace with",
                "required": True
            }
        }

    def _is_path_allowed(self, path: Path) -> bool:
        """Check if path is within allowed directories."""
        if self._allowed_paths is None:
            return True
        resolved = path.resolve()
        return any(
            resolved.is_relative_to(allowed.resolve())
            for allowed in self._allowed_paths
        )

    def _generate_diff(self, old_content: str, new_content: str, filepath: str) -> str:
        """Generate a unified diff for display."""
        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)

        diff = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"{filepath} (before)",
            tofile=f"{filepath} (after)",
            lineterm=""
        )

        return "".join(diff)

    def execute(self, **kwargs: Any) -> ToolResult:
        path_str = kwargs.get("path")
        old_str = kwargs.get("old_str")
        new_str = kwargs.get("new_str")

        # Validate parameters
        if not path_str:
            return ToolResult(
                success=False,
                output="",
                error="Missing required parameter: path"
            )
        if old_str is None:
            return ToolResult(
                success=False,
                output="",
                error="Missing required parameter: old_str"
            )
        if new_str is None:
            return ToolResult(
                success=False,
                output="",
                error="Missing required parameter: new_str"
            )

        path = Path(path_str)

        # Check permissions
        if not self._is_path_allowed(path):
            return ToolResult(
                success=False,
                output="",
                error=f"Access denied: {path} is outside allowed directories"
            )

        # Check file exists
        if not path.exists():
            return ToolResult(
                success=False,
                output="",
                error=f"File not found: {path}"
            )

        if not path.is_file():
            return ToolResult(
                success=False,
                output="",
                error=f"Not a file: {path}"
            )

        # Read file
        try:
            original_content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return ToolResult(
                success=False,
                output="",
                error=f"Cannot read {path}: not a text file"
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Error reading {path}: {e}"
            )

        # Check old_str appears exactly once
        occurrences = original_content.count(old_str)

        if occurrences == 0:
            return ToolResult(
                success=False,
                output="",
                error=f"String not found in {path}:\n{old_str[:100]}..."
            )

        if occurrences > 1:
            return ToolResult(
                success=False,
                output="",
                error=f"String appears {occurrences} times in {path}. Must appear exactly once for safety."
            )

        # Perform replacement
        new_content = original_content.replace(old_str, new_str, 1)

        # Generate diff
        diff = self._generate_diff(original_content, new_content, str(path))

        # Write back to file
        try:
            path.write_text(new_content, encoding="utf-8")
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Error writing to {path}: {e}"
            )

        # Success! Return diff preview
        result_message = f"Successfully edited {path}\n\nDiff:\n{diff}"

        return ToolResult(
            success=True,
            output=result_message
        )
