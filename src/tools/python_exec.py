"""
Python code execution tool.

Allows the agent to execute Python code directly for autonomous operation.
"""

import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .base import BaseTool, ToolResult


class PythonExecTool(BaseTool):
    """Execute Python code directly."""

    def __init__(self, timeout: int = 120, working_dir: Path | None = None):
        self._timeout = timeout
        self._working_dir = working_dir

    @property
    def name(self) -> str:
        return "python_exec"

    @property
    def description(self) -> str:
        return """Execute Python code and return the output.
Use this to:
- Run analysis scripts
- Process data
- Test code snippets
- Perform calculations
- Interact with APIs"""

    @property
    def parameters(self) -> dict[str, dict[str, Any]]:
        return {
            "code": {
                "type": "string",
                "description": "Python code to execute",
                "required": True
            }
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        code = kwargs.get("code")

        if not code:
            return ToolResult(
                success=False,
                output="",
                error="Missing required parameter: code"
            )

        try:
            # Write code to temp file
            with tempfile.NamedTemporaryFile(
                mode='w',
                suffix='.py',
                delete=False
            ) as f:
                f.write(code)
                temp_path = f.name

            # Execute the code
            result = subprocess.run(
                ["python", temp_path],
                capture_output=True,
                text=True,
                timeout=self._timeout,
                cwd=str(self._working_dir) if self._working_dir else None,
            )

            # Clean up
            Path(temp_path).unlink(missing_ok=True)

            output = result.stdout
            if result.stderr:
                output += f"\n[stderr]: {result.stderr}"

            return ToolResult(
                success=result.returncode == 0,
                output=output.strip() or "(no output)",
                error=None if result.returncode == 0 else f"Exit code: {result.returncode}"
            )

        except subprocess.TimeoutExpired:
            Path(temp_path).unlink(missing_ok=True)
            return ToolResult(
                success=False,
                output="",
                error=f"Code execution timed out after {self._timeout} seconds"
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Error executing code: {e}"
            )
