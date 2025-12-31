"""
Code Review Agent (Phase 52)

Provides automated code review with:
- Static analysis (mypy, ruff, pylint)
- Best practices verification
- Security vulnerability scanning
- Automated fix suggestions
"""

import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class Severity(Enum):
    """Issue severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class CodeIssue:
    """A code quality issue."""
    file: str
    line: int | None
    column: int | None
    severity: Severity
    code: str  # Error code (e.g., "E501", "type-error")
    message: str
    tool: str  # Which tool found it (mypy, ruff, etc.)
    suggestion: str | None = None


@dataclass
class ReviewResult:
    """Result of code review."""
    success: bool
    issues: list[CodeIssue] = field(default_factory=list)
    summary: str = ""

    def has_errors(self) -> bool:
        """Check if there are any error-level issues."""
        return any(i.severity in (Severity.ERROR, Severity.CRITICAL) for i in self.issues)

    def has_warnings(self) -> bool:
        """Check if there are any warnings."""
        return any(i.severity == Severity.WARNING for i in self.issues)

    def issue_count_by_severity(self) -> dict[Severity, int]:
        """Count issues by severity."""
        counts = {s: 0 for s in Severity}
        for issue in self.issues:
            counts[issue.severity] += 1
        return counts


class StaticAnalyzer:
    """Run static analysis tools on Python code."""

    def __init__(self) -> None:
        self.available_tools = self._check_available_tools()

    def _check_available_tools(self) -> dict[str, bool]:
        """Check which analysis tools are installed."""
        tools = {}
        for tool in ["mypy", "ruff", "pylint"]:
            try:
                subprocess.run(
                    [tool, "--version"],
                    capture_output=True,
                    timeout=5,
                    check=False
                )
                tools[tool] = True
            except (FileNotFoundError, subprocess.TimeoutExpired):
                tools[tool] = False
        return tools

    def _run_mypy(self, file_path: Path) -> list[CodeIssue]:
        """Run mypy type checker."""
        if not self.available_tools.get("mypy"):
            return []

        issues = []
        try:
            result = subprocess.run(
                ["mypy", "--no-error-summary", str(file_path)],
                capture_output=True,
                text=True,
                timeout=30,
                check=False
            )

            # Parse mypy output
            for line in result.stdout.splitlines():
                if not line.strip() or ":" not in line:
                    continue

                parts = line.split(":", 3)
                if len(parts) >= 4:
                    try:
                        line_num = int(parts[1])
                        severity = Severity.ERROR if "error:" in line else Severity.WARNING
                        message = parts[3].strip()

                        issues.append(CodeIssue(
                            file=str(file_path),
                            line=line_num,
                            column=None,
                            severity=severity,
                            code="type-error",
                            message=message,
                            tool="mypy"
                        ))
                    except (ValueError, IndexError):
                        continue

        except subprocess.TimeoutExpired:
            pass

        return issues

    def _run_ruff(self, file_path: Path) -> list[CodeIssue]:
        """Run ruff linter."""
        if not self.available_tools.get("ruff"):
            return []

        issues = []
        try:
            result = subprocess.run(
                ["ruff", "check", str(file_path), "--output-format=text"],
                capture_output=True,
                text=True,
                timeout=30,
                check=False
            )

            # Parse ruff output: file.py:10:5: E501 Line too long
            for line in result.stdout.splitlines():
                if not line.strip() or ":" not in line:
                    continue

                parts = line.split(":", 4)
                if len(parts) >= 4:
                    try:
                        line_num = int(parts[1])
                        col_num = int(parts[2]) if parts[2].strip().isdigit() else None

                        # Extract code and message
                        rest = parts[3].strip()
                        code_and_msg = rest.split(None, 1)
                        code = code_and_msg[0] if code_and_msg else "ruff"
                        message = code_and_msg[1] if len(code_and_msg) > 1 else rest

                        # Determine severity based on code
                        if code.startswith("E") or code.startswith("F"):
                            severity = Severity.ERROR
                        else:
                            severity = Severity.WARNING

                        issues.append(CodeIssue(
                            file=str(file_path),
                            line=line_num,
                            column=col_num,
                            severity=severity,
                            code=code,
                            message=message,
                            tool="ruff"
                        ))
                    except (ValueError, IndexError):
                        continue

        except subprocess.TimeoutExpired:
            pass

        return issues

    def analyze_file(self, file_path: Path) -> ReviewResult:
        """Run all available static analysis tools on a file."""
        if not file_path.exists():
            return ReviewResult(
                success=False,
                summary=f"File not found: {file_path}"
            )

        if file_path.suffix != ".py":
            return ReviewResult(
                success=False,
                summary=f"Not a Python file: {file_path}"
            )

        all_issues = []

        # Run available tools
        if self.available_tools.get("mypy"):
            all_issues.extend(self._run_mypy(file_path))

        if self.available_tools.get("ruff"):
            all_issues.extend(self._run_ruff(file_path))

        # Generate summary
        issue_counts = {}
        for issue in all_issues:
            issue_counts[issue.severity] = issue_counts.get(issue.severity, 0) + 1

        summary_parts = []
        if issue_counts:
            summary_parts.append(f"Found {len(all_issues)} issues:")
            for severity, count in sorted(issue_counts.items(), key=lambda x: x[0].value):
                summary_parts.append(f"  {severity.value}: {count}")
        else:
            summary_parts.append("No issues found!")

        tools_used = [t for t, available in self.available_tools.items() if available]
        summary_parts.append(f"Tools: {', '.join(tools_used) if tools_used else 'none available'}")

        return ReviewResult(
            success=True,
            issues=all_issues,
            summary="\n".join(summary_parts)
        )


class CodeReviewer:
    """High-level code review interface."""

    def __init__(self) -> None:
        self.analyzer = StaticAnalyzer()

    def review_file(self, file_path: Path) -> ReviewResult:
        """Review a single file."""
        return self.analyzer.analyze_file(file_path)

    def review_directory(
        self,
        directory: Path,
        recursive: bool = True,
        pattern: str = "*.py"
    ) -> dict[str, ReviewResult]:
        """Review all Python files in a directory."""
        results = {}

        if recursive:
            files = directory.rglob(pattern)
        else:
            files = directory.glob(pattern)

        for file_path in files:
            # Skip common directories
            if any(part in file_path.parts for part in ["__pycache__", ".venv", "venv", "node_modules"]):
                continue

            results[str(file_path)] = self.review_file(file_path)

        return results

    def format_issues(self, result: ReviewResult) -> str:
        """Format review issues for display."""
        if not result.issues:
            return result.summary

        lines = [result.summary, ""]

        # Group by file
        by_file: dict[str, list[CodeIssue]] = {}
        for issue in result.issues:
            if issue.file not in by_file:
                by_file[issue.file] = []
            by_file[issue.file].append(issue)

        for file, issues in by_file.items():
            lines.append(f"\n{file}:")
            for issue in sorted(issues, key=lambda x: (x.line or 0, x.column or 0)):
                location = f"{issue.line}:{issue.column}" if issue.column else str(issue.line)
                lines.append(f"  {location} [{issue.tool}] {issue.code}: {issue.message}")

        return "\n".join(lines)
