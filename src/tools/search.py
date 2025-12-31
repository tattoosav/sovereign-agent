"""
Code search tools.

Provides grep-like functionality for searching code.
Uses ripgrep if available, falls back to Python implementation.
"""

import re
import subprocess
from pathlib import Path
from typing import Any

from .base import BaseTool, ToolResult


class CodeSearchTool(BaseTool):
    """
    Search for patterns in code files.

    Supports regex patterns and file type filtering.
    Uses ripgrep if available for performance, otherwise uses Python fallback.
    """

    def __init__(self, allowed_paths: list[Path] | None = None):
        self._allowed_paths = allowed_paths
        self._has_ripgrep = self._check_ripgrep()

    def _check_ripgrep(self) -> bool:
        """Check if ripgrep is available."""
        try:
            subprocess.run(
                ["rg", "--version"],
                capture_output=True,
                check=True,
                timeout=1
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            return False

    @property
    def name(self) -> str:
        return "code_search"

    @property
    def description(self) -> str:
        return (
            "Search for a pattern in code files. Supports regex patterns. "
            "Returns matching lines with file paths and line numbers."
        )

    @property
    def parameters(self) -> dict[str, dict[str, Any]]:
        return {
            "pattern": {
                "type": "string",
                "description": "Regex pattern to search for",
                "required": True
            },
            "path": {
                "type": "string",
                "description": "Directory to search in (default: current directory)",
                "required": False
            },
            "file_pattern": {
                "type": "string",
                "description": "Glob pattern for files to search (e.g., '*.py', '*.js')",
                "required": False
            },
            "case_sensitive": {
                "type": "boolean",
                "description": "Whether search is case sensitive (default: true)",
                "required": False
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results to return (default: 100)",
                "required": False
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

    def _search_with_ripgrep(
        self,
        pattern: str,
        search_path: Path,
        file_pattern: str | None,
        case_sensitive: bool,
        max_results: int
    ) -> str:
        """Search using ripgrep."""
        cmd = ["rg", "--line-number", "--with-filename"]

        if not case_sensitive:
            cmd.append("--ignore-case")

        if file_pattern:
            cmd.extend(["--glob", file_pattern])

        cmd.extend(["--max-count", str(max_results)])
        cmd.append(pattern)
        cmd.append(str(search_path))

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                return result.stdout
            elif result.returncode == 1:
                # No matches found
                return ""
            else:
                # Error occurred
                raise RuntimeError(f"ripgrep error: {result.stderr}")

        except subprocess.TimeoutExpired:
            raise RuntimeError("Search timed out after 30 seconds")

    def _search_python_fallback(
        self,
        pattern: str,
        search_path: Path,
        file_pattern: str | None,
        case_sensitive: bool,
        max_results: int
    ) -> str:
        """Fallback search using Python."""
        results = []
        flags = 0 if case_sensitive else re.IGNORECASE

        try:
            regex = re.compile(pattern, flags)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern: {e}")

        # Determine glob pattern
        glob_pat = file_pattern if file_pattern else "**/*"

        # Search files
        count = 0
        for file_path in search_path.rglob(glob_pat) if "**" in glob_pat else search_path.glob(glob_pat):
            if not file_path.is_file():
                continue

            # Skip binary files and common non-text files
            if file_path.suffix in {'.pyc', '.exe', '.dll', '.so', '.dylib', '.bin', '.dat'}:
                continue

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    for line_num, line in enumerate(f, 1):
                        if regex.search(line):
                            # Format: path:line_number:line_content
                            results.append(f"{file_path}:{line_num}:{line.rstrip()}")
                            count += 1
                            if count >= max_results:
                                break
            except (UnicodeDecodeError, PermissionError):
                # Skip binary files or files we can't read
                continue

            if count >= max_results:
                break

        return "\n".join(results)

    def execute(self, **kwargs: Any) -> ToolResult:
        pattern = kwargs.get("pattern")
        path_str = kwargs.get("path", ".")
        file_pattern = kwargs.get("file_pattern")
        case_sensitive = kwargs.get("case_sensitive", True)
        max_results = kwargs.get("max_results", 100)

        # Validate parameters
        if not pattern:
            return ToolResult(
                success=False,
                output="",
                error="Missing required parameter: pattern"
            )

        # Convert case_sensitive from string if needed
        if isinstance(case_sensitive, str):
            case_sensitive = case_sensitive.lower() in ("true", "1", "yes")

        # Convert max_results to int if needed
        try:
            max_results = int(max_results)
        except (ValueError, TypeError):
            max_results = 100

        search_path = Path(path_str)

        # Check permissions
        if not self._is_path_allowed(search_path):
            return ToolResult(
                success=False,
                output="",
                error=f"Access denied: {search_path} is outside allowed directories"
            )

        if not search_path.exists():
            return ToolResult(
                success=False,
                output="",
                error=f"Path not found: {search_path}"
            )

        if not search_path.is_dir():
            return ToolResult(
                success=False,
                output="",
                error=f"Not a directory: {search_path}"
            )

        # Perform search
        try:
            if self._has_ripgrep:
                output = self._search_with_ripgrep(
                    pattern, search_path, file_pattern, case_sensitive, max_results
                )
                method = "ripgrep"
            else:
                output = self._search_python_fallback(
                    pattern, search_path, file_pattern, case_sensitive, max_results
                )
                method = "Python fallback"

            if not output:
                return ToolResult(
                    success=True,
                    output=f"No matches found for pattern: {pattern}"
                )

            # Add header
            line_count = len(output.strip().split('\n'))
            header = f"Found {line_count} matches (using {method}):\n\n"

            return ToolResult(
                success=True,
                output=header + output
            )

        except ValueError as e:
            return ToolResult(
                success=False,
                output="",
                error=str(e)
            )
        except RuntimeError as e:
            return ToolResult(
                success=False,
                output="",
                error=str(e)
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Search error: {e}"
            )
