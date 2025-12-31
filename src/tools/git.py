"""
Git integration tools.

Provides Git operations: status, diff, log, commit, branch management.
"""

import subprocess
from pathlib import Path
from typing import Any

from .base import BaseTool, ToolResult


class GitTool(BaseTool):
    """
    Execute Git commands.

    Supports common operations: status, diff, log, commit, branch, etc.
    """

    def __init__(self, allowed_paths: list[Path] | None = None):
        self._allowed_paths = allowed_paths

    @property
    def name(self) -> str:
        return "git"

    @property
    def description(self) -> str:
        return (
            "Execute Git commands. Supported operations: status, diff, log, "
            "commit, add, branch, checkout. Use 'operation' parameter to specify the command."
        )

    @property
    def parameters(self) -> dict[str, dict[str, Any]]:
        return {
            "operation": {
                "type": "string",
                "description": "Git operation: status, diff, log, add, commit, branch, checkout",
                "required": True
            },
            "path": {
                "type": "string",
                "description": "Repository path (default: current directory)",
                "required": False
            },
            "args": {
                "type": "string",
                "description": "Additional arguments for the git command",
                "required": False
            },
            "message": {
                "type": "string",
                "description": "Commit message (for commit operation)",
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

    def _run_git_command(self, repo_path: Path, git_args: list[str]) -> tuple[bool, str, str]:
        """
        Run a git command and return (success, stdout, stderr).
        """
        try:
            result = subprocess.run(
                ["git", "-C", str(repo_path)] + git_args,
                capture_output=True,
                text=True,
                timeout=30
            )
            return (result.returncode == 0, result.stdout, result.stderr)
        except subprocess.TimeoutExpired:
            return (False, "", "Git command timed out after 30 seconds")
        except FileNotFoundError:
            return (False, "", "Git is not installed or not in PATH")
        except Exception as e:
            return (False, "", f"Error running git command: {e}")

    def execute(self, **kwargs: Any) -> ToolResult:
        operation = kwargs.get("operation", "").lower()
        path_str = kwargs.get("path", ".")
        args_str = kwargs.get("args", "")
        message = kwargs.get("message")

        if not operation:
            return ToolResult(
                success=False,
                output="",
                error="Missing required parameter: operation"
            )

        repo_path = Path(path_str)

        # Check permissions
        if not self._is_path_allowed(repo_path):
            return ToolResult(
                success=False,
                output="",
                error=f"Access denied: {repo_path} is outside allowed directories"
            )

        if not repo_path.exists():
            return ToolResult(
                success=False,
                output="",
                error=f"Path not found: {repo_path}"
            )

        # Build git command based on operation
        git_args: list[str] = []

        if operation == "status":
            git_args = ["status"]
            if args_str:
                git_args.extend(args_str.split())

        elif operation == "diff":
            git_args = ["diff"]
            if args_str:
                git_args.extend(args_str.split())

        elif operation == "log":
            git_args = ["log"]
            if not args_str:
                # Default: show last 10 commits with oneline format
                git_args.extend(["--oneline", "-n", "10"])
            else:
                git_args.extend(args_str.split())

        elif operation == "add":
            if not args_str:
                return ToolResult(
                    success=False,
                    output="",
                    error="'add' operation requires 'args' parameter (files to add)"
                )
            git_args = ["add"] + args_str.split()

        elif operation == "commit":
            if not message:
                return ToolResult(
                    success=False,
                    output="",
                    error="'commit' operation requires 'message' parameter"
                )
            git_args = ["commit", "-m", message]
            if args_str:
                git_args.extend(args_str.split())

        elif operation == "branch":
            git_args = ["branch"]
            if args_str:
                git_args.extend(args_str.split())

        elif operation == "checkout":
            if not args_str:
                return ToolResult(
                    success=False,
                    output="",
                    error="'checkout' operation requires 'args' parameter (branch name)"
                )
            git_args = ["checkout"] + args_str.split()

        elif operation == "pull":
            git_args = ["pull"]
            if args_str:
                git_args.extend(args_str.split())

        elif operation == "push":
            git_args = ["push"]
            if args_str:
                git_args.extend(args_str.split())

        else:
            return ToolResult(
                success=False,
                output="",
                error=f"Unsupported operation: {operation}. Supported: status, diff, log, add, commit, branch, checkout, pull, push"
            )

        # Execute git command
        success, stdout, stderr = self._run_git_command(repo_path, git_args)

        if success:
            output = stdout if stdout else "(no output)"
            return ToolResult(
                success=True,
                output=f"Git {operation} completed:\n\n{output}"
            )
        else:
            error_msg = stderr if stderr else stdout
            return ToolResult(
                success=False,
                output="",
                error=f"Git {operation} failed: {error_msg}"
            )
