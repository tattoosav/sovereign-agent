"""
Shell command execution tool.

WARNING: This tool can execute arbitrary commands on the system.
Use allowed_commands and blocked_commands to restrict what can be run.
"""

import shlex
import subprocess
from pathlib import Path
from typing import Any

from .base import BaseTool, ToolResult


# Network-capable commands blocked unconditionally in the air-gapped build.
# Defense-in-depth: even if the allowlist were widened, these can never run.
NETWORK_BLOCKED = [
    "curl", "wget", "Invoke-WebRequest", "Invoke-RestMethod", "iwr", "irm",
    "bitsadmin", "certutil", "ncat", "telnet", "Start-BitsTransfer",
    "ssh ", "scp ", "sftp", "pip install", "pip download", "pip3 install",
    "npm install", "npm i ", "yarn add", "nuget", "dotnet restore",
    "dotnet add", "git clone", "git pull", "git fetch", "git push",
]


class ShellTool(BaseTool):
    """Execute shell commands."""

    def __init__(
        self,
        timeout: int = 30,
        allowed_commands: list[str] | None = None,
        blocked_commands: list[str] | None = None,
        cwd: str | Path | None = None,
    ):
        self._timeout = timeout
        self._allowed_commands = allowed_commands  # If set, ONLY these commands work
        self._cwd = str(cwd) if cwd is not None else None
        base_blocked = blocked_commands or [
            "rm -rf /",
            "rm -rf ~",
            "mkfs",
            "dd if=",
            ":(){:|:&};:",  # Fork bomb
        ]
        # Always include the network blocklist (air-gap defense-in-depth).
        self._blocked_commands = base_blocked + NETWORK_BLOCKED
    
    @property
    def name(self) -> str:
        return "shell"
    
    @property
    def description(self) -> str:
        return "Execute a shell command and return its output."
    
    @property
    def parameters(self) -> dict[str, dict[str, Any]]:
        return {
            "command": {
                "type": "string",
                "description": "The shell command to execute",
                "required": True
            }
        }
    
    def _is_command_allowed(self, command: str) -> tuple[bool, str]:
        """Check if command is allowed to run."""
        # Check blocked patterns
        for blocked in self._blocked_commands:
            if blocked in command:
                return False, f"Command contains blocked pattern: {blocked}"
        
        # If allowlist is set, check against it
        if self._allowed_commands is not None:
            try:
                parts = shlex.split(command)
                base_cmd = parts[0] if parts else ""
            except ValueError:
                base_cmd = command.split()[0] if command.split() else ""
            
            if base_cmd not in self._allowed_commands:
                return False, f"Command '{base_cmd}' is not in the allowed list"
        
        return True, ""
    
    def execute(self, **kwargs: Any) -> ToolResult:
        command = kwargs.get("command")
        
        if not command:
            return ToolResult(
                success=False,
                output="",
                error="Missing required parameter: command"
            )
        
        # Safety check
        allowed, reason = self._is_command_allowed(command)
        if not allowed:
            return ToolResult(
                success=False,
                output="",
                error=f"Command blocked: {reason}"
            )
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=self._timeout,
                cwd=self._cwd,  # Restrict to working dir when set
            )
            
            output = result.stdout
            if result.stderr:
                output += f"\n[stderr]: {result.stderr}"
            
            return ToolResult(
                success=result.returncode == 0,
                output=output.strip() or "(no output)",
                error=None if result.returncode == 0 else f"Exit code: {result.returncode}"
            )
        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                output="",
                error=f"Command timed out after {self._timeout} seconds"
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Error executing command: {e}"
            )
