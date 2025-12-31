"""
Tests for the verification system.
"""

from pathlib import Path
import tempfile

from src.agent.verification import (
    ToolVerifier,
    VerificationStatus,
    VerificationResult,
    VerificationMetrics,
)
from src.tools import ToolResult


def test_verification_metrics():
    """Test verification metrics tracking."""
    metrics = VerificationMetrics()
    assert metrics.total_checks == 0
    assert metrics.success_rate() == 0.0

    # Record a passed result
    metrics.record(VerificationResult(VerificationStatus.PASSED, "test"))
    assert metrics.total_checks == 1
    assert metrics.passed == 1
    assert metrics.success_rate() == 1.0

    # Record a failed result
    metrics.record(VerificationResult(VerificationStatus.FAILED, "test"))
    assert metrics.total_checks == 2
    assert metrics.failed == 1
    assert metrics.success_rate() == 0.5


def test_verify_read_file_success():
    """Test verification of successful file read."""
    verifier = ToolVerifier()

    result = ToolResult(success=True, output="file contents")
    verification = verifier.verify("read_file", {"path": "test.txt"}, result)

    assert verification.status == VerificationStatus.PASSED
    assert "Successfully read" in verification.message


def test_verify_read_file_empty():
    """Test verification of empty file read."""
    verifier = ToolVerifier()

    result = ToolResult(success=True, output="")
    verification = verifier.verify("read_file", {"path": "test.txt"}, result)

    assert verification.status == VerificationStatus.FAILED
    assert "empty" in verification.message.lower()
    assert len(verification.suggestions) > 0


def test_verify_write_file():
    """Test verification of file write."""
    verifier = ToolVerifier()

    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        temp_path = f.name
        content = "test content"
        f.write(content)

    try:
        result = ToolResult(success=True, output=f"Wrote to {temp_path}")
        verification = verifier.verify(
            "write_file",
            {"path": temp_path, "content": content},
            result
        )

        assert verification.status == VerificationStatus.PASSED
        assert "Successfully wrote" in verification.message

    finally:
        Path(temp_path).unlink(missing_ok=True)


def test_verify_write_file_mismatch():
    """Test verification detects content mismatch."""
    verifier = ToolVerifier()

    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        temp_path = f.name
        f.write("wrong content")

    try:
        result = ToolResult(success=True, output=f"Wrote to {temp_path}")
        verification = verifier.verify(
            "write_file",
            {"path": temp_path, "content": "expected content"},
            result
        )

        assert verification.status == VerificationStatus.FAILED
        assert "mismatch" in verification.message.lower()

    finally:
        Path(temp_path).unlink(missing_ok=True)


def test_verify_str_replace():
    """Test verification of string replacement."""
    verifier = ToolVerifier()

    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        temp_path = f.name
        f.write("hello world")

    try:
        result = ToolResult(success=True, output="Replacement successful")
        verification = verifier.verify(
            "str_replace",
            {"path": temp_path, "old_str": "hello", "new_str": "world"},
            result
        )

        assert verification.status == VerificationStatus.PASSED

    finally:
        Path(temp_path).unlink(missing_ok=True)


def test_verify_code_search_no_results():
    """Test verification of code search with no results."""
    verifier = ToolVerifier()

    result = ToolResult(success=True, output="No matches found")
    verification = verifier.verify(
        "code_search",
        {"pattern": "nonexistent"},
        result
    )

    assert verification.status == VerificationStatus.PASSED
    assert len(verification.suggestions) > 0


def test_verify_code_search_with_results():
    """Test verification of code search with results."""
    verifier = ToolVerifier()

    result = ToolResult(success=True, output="file.py:10:match found")
    verification = verifier.verify(
        "code_search",
        {"pattern": "test"},
        result
    )

    assert verification.status == VerificationStatus.PASSED


def test_verify_skips_failed_tools():
    """Test that verification is skipped for failed tools."""
    verifier = ToolVerifier()

    result = ToolResult(success=False, output="", error="Tool failed")
    verification = verifier.verify(
        "read_file",
        {"path": "test.txt"},
        result
    )

    assert verification.status == VerificationStatus.SKIPPED


def test_verify_unknown_tool():
    """Test verification of unknown tool type."""
    verifier = ToolVerifier()

    result = ToolResult(success=True, output="result")
    verification = verifier.verify(
        "unknown_tool",
        {},
        result
    )

    assert verification.status == VerificationStatus.SKIPPED


def test_verifier_metrics():
    """Test that verifier tracks metrics correctly."""
    verifier = ToolVerifier()

    # Verify a few operations
    verifier.verify("read_file", {"path": "test.txt"}, ToolResult(True, "content"))
    verifier.verify("read_file", {"path": "test.txt"}, ToolResult(True, ""))
    verifier.verify("unknown_tool", {}, ToolResult(True, "result"))

    metrics = verifier.get_metrics()
    assert metrics["total_checks"] == 3
    assert metrics["passed"] == 1  # First read_file
    assert metrics["failed"] == 1  # Second read_file (empty)
    assert metrics["skipped"] == 1  # unknown_tool
    assert 0 <= metrics["success_rate"] <= 100
