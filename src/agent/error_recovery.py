"""
Error Recovery System (Phase 55)

Provides graceful degradation and alternative strategies when tools fail:
- Fallback strategies for common failures
- Context preservation across errors
- Alternative approach suggestions
- Error pattern recognition
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RecoveryStrategy(Enum):
    """Type of recovery strategy."""
    RETRY = "retry"
    FALLBACK = "fallback"
    ALTERNATIVE = "alternative"
    SKIP = "skip"
    ABORT = "abort"


@dataclass
class RecoveryAction:
    """A suggested recovery action."""
    strategy: RecoveryStrategy
    description: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class ErrorContext:
    """Context about an error."""
    tool_name: str
    error_message: str
    params: dict[str, Any]
    attempt_number: int = 1


class ErrorRecoveryManager:
    """Manages error recovery strategies."""

    def __init__(self) -> None:
        self.error_history: list[ErrorContext] = []
        self.recovery_patterns: dict[str, list[RecoveryAction]] = self._init_patterns()

    def _init_patterns(self) -> dict[str, list[RecoveryAction]]:
        """Initialize recovery patterns for common errors."""
        return {
            # File not found errors
            "file_not_found": [
                RecoveryAction(
                    RecoveryStrategy.ALTERNATIVE,
                    "Try listing the directory to see available files",
                    {"tool": "list_directory"}
                ),
                RecoveryAction(
                    RecoveryStrategy.ALTERNATIVE,
                    "Search for similar file names",
                    {"tool": "code_search"}
                ),
            ],

            # Path not allowed errors
            "path_not_allowed": [
                RecoveryAction(
                    RecoveryStrategy.ALTERNATIVE,
                    "Use a path within allowed directories",
                ),
                RecoveryAction(
                    RecoveryStrategy.SKIP,
                    "Skip this operation and continue with next step",
                ),
            ],

            # Permission denied
            "permission_denied": [
                RecoveryAction(
                    RecoveryStrategy.ALTERNATIVE,
                    "Try reading the file instead of writing",
                    {"tool": "read_file"}
                ),
                RecoveryAction(
                    RecoveryStrategy.SKIP,
                    "Skip this operation",
                ),
            ],

            # Git errors
            "git_error": [
                RecoveryAction(
                    RecoveryStrategy.ALTERNATIVE,
                    "Check git status first",
                    {"tool": "git", "operation": "status"}
                ),
                RecoveryAction(
                    RecoveryStrategy.SKIP,
                    "Continue without git operation",
                ),
            ],

            # Search no results
            "search_no_results": [
                RecoveryAction(
                    RecoveryStrategy.ALTERNATIVE,
                    "Try a broader search pattern",
                ),
                RecoveryAction(
                    RecoveryStrategy.ALTERNATIVE,
                    "List directory contents instead",
                    {"tool": "list_directory"}
                ),
            ],

            # Network/timeout errors
            "timeout": [
                RecoveryAction(
                    RecoveryStrategy.RETRY,
                    "Retry with longer timeout",
                    {"retry_delay": 2.0}
                ),
                RecoveryAction(
                    RecoveryStrategy.ALTERNATIVE,
                    "Try a simpler operation",
                ),
            ],

            # Empty file
            "empty_file": [
                RecoveryAction(
                    RecoveryStrategy.ALTERNATIVE,
                    "File might be empty - try creating content first",
                ),
                RecoveryAction(
                    RecoveryStrategy.SKIP,
                    "Skip this file and continue",
                ),
            ],

            # Type errors (for code review)
            "type_error": [
                RecoveryAction(
                    RecoveryStrategy.ALTERNATIVE,
                    "Add type annotations to fix type errors",
                ),
                RecoveryAction(
                    RecoveryStrategy.SKIP,
                    "Type errors are non-blocking, continue",
                ),
            ],
        }

    def _classify_error(self, error_context: ErrorContext) -> str:
        """Classify the error type."""
        error_msg = error_context.error_message.lower()

        # Check for specific error patterns
        if "not found" in error_msg or "does not exist" in error_msg:
            return "file_not_found"
        elif "not allowed" in error_msg:
            return "path_not_allowed"
        elif "permission" in error_msg or "denied" in error_msg:
            return "permission_denied"
        elif "git" in error_msg or error_context.tool_name == "git":
            return "git_error"
        elif "no matches" in error_msg or "no results" in error_msg:
            return "search_no_results"
        elif "timeout" in error_msg or "timed out" in error_msg:
            return "timeout"
        elif "empty" in error_msg:
            return "empty_file"
        elif "type" in error_msg:
            return "type_error"
        else:
            return "unknown"

    def record_error(self, error_context: ErrorContext) -> None:
        """Record an error for pattern analysis."""
        self.error_history.append(error_context)

    def suggest_recovery(self, error_context: ErrorContext) -> list[RecoveryAction]:
        """Suggest recovery actions for an error."""
        # Classify the error
        error_type = self._classify_error(error_context)

        # Get recovery actions for this error type
        actions = self.recovery_patterns.get(error_type, [])

        # If unknown error, provide generic recovery actions
        if not actions:
            actions = [
                RecoveryAction(
                    RecoveryStrategy.RETRY,
                    "Retry the operation once more",
                ),
                RecoveryAction(
                    RecoveryStrategy.ALTERNATIVE,
                    "Try a different approach",
                ),
                RecoveryAction(
                    RecoveryStrategy.SKIP,
                    "Skip and continue with next step",
                ),
            ]

        # Don't suggest retry if already retried multiple times
        if error_context.attempt_number >= 3:
            actions = [a for a in actions if a.strategy != RecoveryStrategy.RETRY]

        return actions

    def should_abort(self, error_context: ErrorContext) -> bool:
        """Determine if we should abort based on error severity."""
        # Check for critical errors
        critical_patterns = [
            "syntax error",
            "invalid syntax",
            "fatal",
            "critical",
        ]

        error_msg = error_context.error_message.lower()
        return any(pattern in error_msg for pattern in critical_patterns)

    def format_recovery_suggestions(self, actions: list[RecoveryAction]) -> str:
        """Format recovery suggestions for the LLM."""
        if not actions:
            return "No specific recovery suggestions available."

        lines = ["Recovery options:"]
        for i, action in enumerate(actions, 1):
            lines.append(f"{i}. [{action.strategy.value}] {action.description}")

        return "\n".join(lines)

    def get_error_stats(self) -> dict[str, Any]:
        """Get statistics about errors encountered."""
        if not self.error_history:
            return {"total_errors": 0}

        # Count errors by tool
        by_tool: dict[str, int] = {}
        for error in self.error_history:
            by_tool[error.tool_name] = by_tool.get(error.tool_name, 0) + 1

        # Count errors by type
        by_type: dict[str, int] = {}
        for error in self.error_history:
            error_type = self._classify_error(error)
            by_type[error_type] = by_type.get(error_type, 0) + 1

        return {
            "total_errors": len(self.error_history),
            "by_tool": by_tool,
            "by_type": by_type,
            "most_common_tool": max(by_tool.items(), key=lambda x: x[1])[0] if by_tool else None,
            "most_common_type": max(by_type.items(), key=lambda x: x[1])[0] if by_type else None,
        }
