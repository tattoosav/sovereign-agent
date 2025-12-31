"""
Compound Tools - Higher-level operations that chain multiple tools.

These tools combine common operations to reduce LLM round-trips
and make the agent more efficient.
"""

import logging
from pathlib import Path
from typing import Any

from .base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class SearchAndReadTool(BaseTool):
    """
    Search for code patterns and read matching files in one operation.

    Combines code_search + read_file to reduce round-trips.
    """

    def __init__(self, search_tool: BaseTool, read_tool: BaseTool):
        self._search_tool = search_tool
        self._read_tool = read_tool

    @property
    def name(self) -> str:
        return "search_and_read"

    @property
    def description(self) -> str:
        return """Search for a pattern and read matching files.
Combines search and read into one operation.
Returns search results with full file contents."""

    @property
    def parameters(self) -> dict[str, dict[str, Any]]:
        return {
            "pattern": {
                "type": "string",
                "description": "Regex pattern to search for",
                "required": True
            },
            "file_pattern": {
                "type": "string",
                "description": "Glob pattern for files (e.g., '*.py')",
                "required": False
            },
            "max_files": {
                "type": "integer",
                "description": "Maximum files to read (default: 3)",
                "required": False
            }
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        pattern = kwargs.get("pattern", "")
        file_pattern = kwargs.get("file_pattern", "*.py")
        max_files = int(kwargs.get("max_files", 3))

        if not pattern:
            return ToolResult(
                success=False,
                output="",
                error="Pattern is required"
            )

        # First, search for the pattern
        search_result = self._search_tool.execute(
            pattern=pattern,
            file_pattern=file_pattern
        )

        if not search_result.success:
            return search_result

        # Parse search results to get file paths
        lines = search_result.output.strip().split('\n')
        files_seen = set()
        files_to_read = []

        for line in lines:
            if ':' in line:
                file_path = line.split(':')[0]
                if file_path not in files_seen and len(files_to_read) < max_files:
                    files_seen.add(file_path)
                    files_to_read.append(file_path)

        if not files_to_read:
            return ToolResult(
                success=True,
                output=f"Search found matches but no readable files:\n{search_result.output}"
            )

        # Read each matching file
        output_parts = [f"Search results for '{pattern}':\n"]
        output_parts.append(search_result.output)
        output_parts.append("\n\n--- File Contents ---\n")

        for file_path in files_to_read:
            read_result = self._read_tool.execute(path=file_path)
            if read_result.success:
                output_parts.append(f"\n=== {file_path} ===\n")
                output_parts.append(read_result.output)
            else:
                output_parts.append(f"\n=== {file_path} (read failed) ===\n")

        return ToolResult(
            success=True,
            output='\n'.join(output_parts)
        )


class EditAndVerifyTool(BaseTool):
    """
    Edit a file and verify the change was applied correctly.

    Combines str_replace + read_file to ensure edits work.
    """

    def __init__(self, edit_tool: BaseTool, read_tool: BaseTool):
        self._edit_tool = edit_tool
        self._read_tool = read_tool

    @property
    def name(self) -> str:
        return "edit_and_verify"

    @property
    def description(self) -> str:
        return """Edit a file and verify the change was applied.
Performs str_replace and then reads the file to confirm.
Returns the diff and verification status."""

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
                "description": "String to replace (must match exactly)",
                "required": True
            },
            "new_str": {
                "type": "string",
                "description": "Replacement string",
                "required": True
            }
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        path = kwargs.get("path", "")
        old_str = kwargs.get("old_str", "")
        new_str = kwargs.get("new_str", "")

        if not all([path, old_str]):
            return ToolResult(
                success=False,
                output="",
                error="path and old_str are required"
            )

        # Perform the edit
        edit_result = self._edit_tool.execute(
            path=path,
            old_str=old_str,
            new_str=new_str
        )

        if not edit_result.success:
            return edit_result

        # Verify by reading the file
        read_result = self._read_tool.execute(path=path)

        if not read_result.success:
            return ToolResult(
                success=False,
                output=edit_result.output,
                error=f"Edit succeeded but verification read failed: {read_result.error}"
            )

        # Check if new_str is in the file
        if new_str in read_result.output:
            return ToolResult(
                success=True,
                output=f"{edit_result.output}\n\n✓ Verified: new content found in file"
            )
        else:
            return ToolResult(
                success=False,
                output=edit_result.output,
                error="Edit may have failed: new content not found in file"
            )


class ExploreDirectoryTool(BaseTool):
    """
    Explore a directory structure with summaries.

    Lists directory contents with file sizes and types.
    """

    def __init__(self, list_tool: BaseTool, read_tool: BaseTool):
        self._list_tool = list_tool
        self._read_tool = read_tool

    @property
    def name(self) -> str:
        return "explore_directory"

    @property
    def description(self) -> str:
        return """Explore a directory with detailed information.
Lists contents, file types, and optionally reads key files.
Great for understanding project structure."""

    @property
    def parameters(self) -> dict[str, dict[str, Any]]:
        return {
            "path": {
                "type": "string",
                "description": "Directory path to explore",
                "required": True
            },
            "depth": {
                "type": "integer",
                "description": "How deep to explore (default: 2)",
                "required": False
            },
            "read_readme": {
                "type": "boolean",
                "description": "Read README files if found (default: true)",
                "required": False
            }
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        path = kwargs.get("path", ".")
        depth = int(kwargs.get("depth", 2))
        read_readme = kwargs.get("read_readme", "true").lower() == "true"

        # List directory
        list_result = self._list_tool.execute(path=path)

        if not list_result.success:
            return list_result

        output_parts = [f"Directory: {path}\n"]
        output_parts.append(list_result.output)

        # Look for README files
        if read_readme:
            readme_names = ["README.md", "README.txt", "README", "readme.md"]
            for readme in readme_names:
                readme_path = Path(path) / readme
                read_result = self._read_tool.execute(path=str(readme_path))
                if read_result.success:
                    output_parts.append(f"\n\n=== {readme} ===\n")
                    # Truncate long READMEs
                    content = read_result.output
                    if len(content) > 2000:
                        content = content[:2000] + "\n... (truncated)"
                    output_parts.append(content)
                    break

        return ToolResult(
            success=True,
            output='\n'.join(output_parts)
        )


class GitStatusAndDiffTool(BaseTool):
    """
    Get git status and diff in one operation.

    Shows what changed and the actual changes.
    """

    def __init__(self, git_tool: BaseTool):
        self._git_tool = git_tool

    @property
    def name(self) -> str:
        return "git_status_diff"

    @property
    def description(self) -> str:
        return """Get git status and diff together.
Shows modified files and their changes in one call.
More efficient than separate status and diff commands."""

    @property
    def parameters(self) -> dict[str, dict[str, Any]]:
        return {
            "path": {
                "type": "string",
                "description": "Repository path (default: current directory)",
                "required": False
            }
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        path = kwargs.get("path", ".")

        # Get status
        status_result = self._git_tool.execute(operation="status", path=path)

        output_parts = ["=== Git Status ===\n"]
        if status_result.success:
            output_parts.append(status_result.output)
        else:
            return status_result

        # Get diff
        diff_result = self._git_tool.execute(operation="diff", path=path)

        output_parts.append("\n\n=== Git Diff ===\n")
        if diff_result.success:
            diff_output = diff_result.output
            if len(diff_output) > 5000:
                diff_output = diff_output[:5000] + "\n... (diff truncated)"
            output_parts.append(diff_output if diff_output else "(no changes)")
        else:
            output_parts.append(f"(diff failed: {diff_result.error})")

        return ToolResult(
            success=True,
            output='\n'.join(output_parts)
        )


def register_compound_tools(registry: Any, base_tools: dict[str, BaseTool]) -> None:
    """
    Register compound tools with the registry.

    Args:
        registry: ToolRegistry to register with
        base_tools: Dict mapping tool names to tool instances
    """
    # Search and Read
    if "code_search" in base_tools and "read_file" in base_tools:
        registry.register(SearchAndReadTool(
            search_tool=base_tools["code_search"],
            read_tool=base_tools["read_file"]
        ))
        logger.info("Registered compound tool: search_and_read")

    # Edit and Verify
    if "str_replace" in base_tools and "read_file" in base_tools:
        registry.register(EditAndVerifyTool(
            edit_tool=base_tools["str_replace"],
            read_tool=base_tools["read_file"]
        ))
        logger.info("Registered compound tool: edit_and_verify")

    # Explore Directory
    if "list_directory" in base_tools and "read_file" in base_tools:
        registry.register(ExploreDirectoryTool(
            list_tool=base_tools["list_directory"],
            read_tool=base_tools["read_file"]
        ))
        logger.info("Registered compound tool: explore_directory")

    # Git Status + Diff
    if "git" in base_tools:
        registry.register(GitStatusAndDiffTool(
            git_tool=base_tools["git"]
        ))
        logger.info("Registered compound tool: git_status_diff")
