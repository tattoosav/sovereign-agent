"""
Self-Correction and Verification System

This module provides verification strategies for agent operations.
After executing tools, we verify the results and retry with adjustments if needed.
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from src.tools import ToolResult


class VerificationStatus(Enum):
    """Status of verification check."""
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class VerificationResult:
    """Result of verification check."""
    status: VerificationStatus
    message: str
    suggestions: list[str] = field(default_factory=list)


@dataclass
class VerificationMetrics:
    """Track verification statistics."""
    total_checks: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0

    def record(self, result: VerificationResult) -> None:
        """Record a verification result."""
        self.total_checks += 1
        if result.status == VerificationStatus.PASSED:
            self.passed += 1
        elif result.status == VerificationStatus.FAILED:
            self.failed += 1
        else:
            self.skipped += 1

    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_checks == 0:
            return 0.0
        return self.passed / self.total_checks


class ToolVerifier:
    """Verify tool execution results."""

    def __init__(self) -> None:
        self.metrics = VerificationMetrics()

    def verify(self, tool_name: str, params: dict[str, Any], result: ToolResult) -> VerificationResult:
        """
        Verify a tool execution result.

        Returns suggestions for retrying if verification fails.
        """
        if not result.success:
            # Tool already failed, skip verification
            verification = VerificationResult(
                status=VerificationStatus.SKIPPED,
                message=f"Tool {tool_name} failed, skipping verification"
            )
            self.metrics.record(verification)
            return verification

        # Route to specific verification logic
        if tool_name == "read_file":
            verification = self._verify_read_file(params, result)
        elif tool_name == "write_file":
            verification = self._verify_write_file(params, result)
        elif tool_name == "str_replace":
            verification = self._verify_str_replace(params, result)
        elif tool_name == "list_directory":
            verification = self._verify_list_directory(params, result)
        elif tool_name == "code_search":
            verification = self._verify_code_search(params, result)
        elif tool_name == "git":
            verification = self._verify_git(params, result)
        elif tool_name == "shell":
            verification = self._verify_shell(params, result)
        else:
            # Unknown tool, skip verification
            verification = VerificationResult(
                status=VerificationStatus.SKIPPED,
                message=f"No verification strategy for {tool_name}"
            )

        self.metrics.record(verification)
        return verification

    def _verify_read_file(self, params: dict[str, Any], result: ToolResult) -> VerificationResult:
        """Verify file read operation."""
        path = params.get("path", "")

        # Check if file actually has content
        if not result.output or len(result.output.strip()) == 0:
            return VerificationResult(
                status=VerificationStatus.FAILED,
                message=f"File {path} appears to be empty",
                suggestions=[
                    "Check if the file path is correct",
                    "Verify the file has content",
                    "Try listing the directory to see what files exist"
                ]
            )

        return VerificationResult(
            status=VerificationStatus.PASSED,
            message=f"Successfully read {len(result.output)} bytes from {path}"
        )

    def _verify_write_file(self, params: dict[str, Any], result: ToolResult) -> VerificationResult:
        """Verify file write operation."""
        path = params.get("path", "")
        content = params.get("content", "")

        # Check if we can read back what we wrote
        try:
            file_path = Path(path)
            if not file_path.exists():
                return VerificationResult(
                    status=VerificationStatus.FAILED,
                    message=f"File {path} does not exist after write",
                    suggestions=[
                        "Check if the directory exists",
                        "Verify write permissions",
                        "Try creating the directory first"
                    ]
                )

            written_content = file_path.read_text()
            if written_content != content:
                return VerificationResult(
                    status=VerificationStatus.FAILED,
                    message=f"File {path} content mismatch after write",
                    suggestions=[
                        "File may have been modified by another process",
                        "Check for encoding issues",
                        "Retry the write operation"
                    ]
                )

            return VerificationResult(
                status=VerificationStatus.PASSED,
                message=f"Successfully wrote and verified {len(content)} bytes to {path}"
            )

        except Exception as e:
            return VerificationResult(
                status=VerificationStatus.FAILED,
                message=f"Failed to verify write: {e}",
                suggestions=["Retry the write operation"]
            )

    def _verify_str_replace(self, params: dict[str, Any], result: ToolResult) -> VerificationResult:
        """Verify string replacement operation."""
        path = params.get("path", "")
        new_str = params.get("new_str", "")

        # Check if the new string is now in the file
        try:
            file_path = Path(path)
            if not file_path.exists():
                return VerificationResult(
                    status=VerificationStatus.FAILED,
                    message=f"File {path} does not exist after replacement",
                    suggestions=["File may have been deleted", "Check file path"]
                )

            content = file_path.read_text()
            if new_str not in content:
                return VerificationResult(
                    status=VerificationStatus.FAILED,
                    message=f"New string not found in {path} after replacement",
                    suggestions=[
                        "The replacement may have failed",
                        "Verify old_str was correct",
                        "Try using write_file instead"
                    ]
                )

            return VerificationResult(
                status=VerificationStatus.PASSED,
                message=f"Successfully replaced string in {path}"
            )

        except Exception as e:
            return VerificationResult(
                status=VerificationStatus.FAILED,
                message=f"Failed to verify replacement: {e}",
                suggestions=["Retry the operation"]
            )

    def _verify_list_directory(self, params: dict[str, Any], result: ToolResult) -> VerificationResult:
        """Verify directory listing operation."""
        # If we got output, assume it worked
        if result.output:
            return VerificationResult(
                status=VerificationStatus.PASSED,
                message="Successfully listed directory"
            )

        # Empty output might be valid (empty directory) or an error
        return VerificationResult(
            status=VerificationStatus.PASSED,
            message="Directory appears to be empty (or listing failed silently)"
        )

    def _verify_code_search(self, params: dict[str, Any], result: ToolResult) -> VerificationResult:
        """Verify code search operation."""
        pattern = params.get("pattern", "")

        # If no results, might be legitimate or pattern issue
        if not result.output or "No matches found" in result.output:
            return VerificationResult(
                status=VerificationStatus.PASSED,
                message=f"No matches found for pattern: {pattern}",
                suggestions=[
                    "Try a simpler or broader pattern",
                    "Check if pattern syntax is correct",
                    "Search in a different directory"
                ]
            )

        return VerificationResult(
            status=VerificationStatus.PASSED,
            message=f"Found matches for pattern: {pattern}"
        )

    def _verify_git(self, params: dict[str, Any], result: ToolResult) -> VerificationResult:
        """Verify git operation."""
        operation = params.get("operation", "")

        # Most git operations are self-verifying through their output
        return VerificationResult(
            status=VerificationStatus.PASSED,
            message=f"Git operation '{operation}' completed"
        )

    def _verify_shell(self, params: dict[str, Any], result: ToolResult) -> VerificationResult:
        """Verify shell command execution."""
        # Shell commands are hard to verify generically
        # We trust the success flag from the tool
        return VerificationResult(
            status=VerificationStatus.PASSED,
            message="Shell command executed"
        )

    def get_metrics(self) -> dict[str, Any]:
        """Get verification metrics as dict."""
        return {
            "total_checks": self.metrics.total_checks,
            "passed": self.metrics.passed,
            "failed": self.metrics.failed,
            "skipped": self.metrics.skipped,
            "success_rate": round(self.metrics.success_rate() * 100, 2)
        }
