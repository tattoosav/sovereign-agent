"""
Test Generation Tool

Allows the agent to automatically generate test scaffolds for Python code.
"""

from pathlib import Path
from typing import Any

from src.agent.test_generator import TestGenerator
from .base import BaseTool, ToolResult


class TestGenTool(BaseTool):
    """Generate pytest-compatible test scaffolds for Python code."""

    def __init__(self, allowed_paths: list[Path] | None = None):
        self.allowed_paths = allowed_paths or []
        self.generator = TestGenerator()

    @property
    def name(self) -> str:
        return "generate_tests"

    @property
    def description(self) -> str:
        return """Generate pytest-compatible test scaffolds for Python code.

Analyzes Python source files and creates test templates with:
- Test functions for each public function
- Test classes for each class
- Edge case test placeholders
- Error handling test placeholders

Parameters:
- source_file: Path to Python source file to generate tests for
- output_file: Path where test file should be written (optional)

Returns test code as string if no output_file specified,
otherwise writes to file and returns confirmation.

Example:
<tool name="generate_tests">
<param name="source_file">src/agent/core.py</param>
<param name="output_file">tests/test_core.py</param>
</tool>"""

    @property
    def parameters(self) -> dict[str, dict[str, Any]]:
        return {
            "source_file": {
                "type": "string",
                "description": "Path to Python source file",
                "required": True
            },
            "output_file": {
                "type": "string",
                "description": "Path to write generated tests (optional)",
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
        """Execute test generation."""
        source_file_str = kwargs.get("source_file")
        if not source_file_str:
            return ToolResult(
                success=False,
                output="",
                error="Missing required parameter: source_file"
            )

        source_file = Path(source_file_str).resolve()

        # Security check
        if not self._check_path_allowed(source_file):
            return ToolResult(
                success=False,
                output="",
                error=f"Path not allowed: {source_file}"
            )

        if not source_file.exists():
            return ToolResult(
                success=False,
                output="",
                error=f"Source file does not exist: {source_file}"
            )

        if source_file.suffix != ".py":
            return ToolResult(
                success=False,
                output="",
                error=f"Source file must be a Python file (.py): {source_file}"
            )

        # Generate tests
        test_code = self.generator.generate_tests_for_file(source_file)

        if not test_code:
            return ToolResult(
                success=False,
                output="",
                error=f"Failed to analyze {source_file} - may contain syntax errors"
            )

        # Write to file if output_file specified
        output_file_str = kwargs.get("output_file")
        if output_file_str:
            output_file = Path(output_file_str).resolve()

            # Security check for output path
            if not self._check_path_allowed(output_file):
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Output path not allowed: {output_file}"
                )

            # Create parent directory if needed
            output_file.parent.mkdir(parents=True, exist_ok=True)

            try:
                output_file.write_text(test_code)
                return ToolResult(
                    success=True,
                    output=f"Generated tests written to {output_file}\n\n{test_code[:500]}..."
                )
            except Exception as e:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Failed to write test file: {e}"
                )
        else:
            # Return test code
            return ToolResult(
                success=True,
                output=test_code
            )
