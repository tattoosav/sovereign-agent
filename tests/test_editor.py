"""
Tests for editor tools.

Run with: uv run pytest tests/test_editor.py
"""

from pathlib import Path

import pytest

from src.tools import StrReplaceTool


class TestStrReplaceTool:
    """Tests for StrReplaceTool."""

    def test_simple_replacement(self, tmp_path: Path) -> None:
        """Should replace a unique string successfully."""
        # Setup
        test_file = tmp_path / "code.py"
        original = """def hello():
    print("Hello")
    return True"""
        test_file.write_text(original)

        tool = StrReplaceTool(allowed_paths=[tmp_path])

        # Execute
        result = tool.execute(
            path=str(test_file),
            old_str='print("Hello")',
            new_str='print("Hello, World!")'
        )

        # Verify
        assert result.success is True
        assert "Successfully edited" in result.output
        assert "Diff:" in result.output

        # Check file was actually modified
        new_content = test_file.read_text()
        assert 'print("Hello, World!")' in new_content
        assert 'print("Hello")' not in new_content

    def test_multiline_replacement(self, tmp_path: Path) -> None:
        """Should replace multiline strings."""
        test_file = tmp_path / "test.py"
        original = """def old_function():
    x = 1
    y = 2
    return x + y

def other():
    pass"""
        test_file.write_text(original)

        tool = StrReplaceTool(allowed_paths=[tmp_path])

        old_str = """def old_function():
    x = 1
    y = 2
    return x + y"""

        new_str = """def new_function(x, y):
    return x + y"""

        result = tool.execute(
            path=str(test_file),
            old_str=old_str,
            new_str=new_str
        )

        assert result.success is True
        new_content = test_file.read_text()
        assert "new_function(x, y)" in new_content
        assert "old_function" not in new_content

    def test_string_not_found(self, tmp_path: Path) -> None:
        """Should fail if old_str not found in file."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, World!")

        tool = StrReplaceTool(allowed_paths=[tmp_path])

        result = tool.execute(
            path=str(test_file),
            old_str="This string does not exist",
            new_str="Replacement"
        )

        assert result.success is False
        assert "not found" in result.error.lower()

    def test_string_appears_multiple_times(self, tmp_path: Path) -> None:
        """Should fail if old_str appears more than once for safety."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("foo bar foo baz foo")

        tool = StrReplaceTool(allowed_paths=[tmp_path])

        result = tool.execute(
            path=str(test_file),
            old_str="foo",
            new_str="replacement"
        )

        assert result.success is False
        assert "3 times" in result.error
        assert "exactly once" in result.error.lower()

    def test_file_not_found(self, tmp_path: Path) -> None:
        """Should fail if file doesn't exist."""
        tool = StrReplaceTool(allowed_paths=[tmp_path])

        result = tool.execute(
            path=str(tmp_path / "nonexistent.txt"),
            old_str="foo",
            new_str="bar"
        )

        assert result.success is False
        assert "not found" in result.error.lower()

    def test_access_denied_outside_allowed_paths(self, tmp_path: Path) -> None:
        """Should deny access to files outside allowed paths."""
        tool = StrReplaceTool(allowed_paths=[tmp_path])

        result = tool.execute(
            path="/etc/passwd",
            old_str="root",
            new_str="hacker"
        )

        assert result.success is False
        assert "denied" in result.error.lower()

    def test_missing_parameters(self, tmp_path: Path) -> None:
        """Should fail gracefully with missing parameters."""
        tool = StrReplaceTool(allowed_paths=[tmp_path])

        # Missing path
        result = tool.execute(old_str="foo", new_str="bar")
        assert result.success is False
        assert "missing" in result.error.lower()
        assert "path" in result.error.lower()

        # Missing old_str
        result = tool.execute(path="test.txt", new_str="bar")
        assert result.success is False
        assert "missing" in result.error.lower()
        assert "old_str" in result.error.lower()

        # Missing new_str
        result = tool.execute(path="test.txt", old_str="foo")
        assert result.success is False
        assert "missing" in result.error.lower()
        assert "new_str" in result.error.lower()

    def test_empty_string_replacement(self, tmp_path: Path) -> None:
        """Should handle empty string replacements (deletion)."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello REMOVE_THIS World")

        tool = StrReplaceTool(allowed_paths=[tmp_path])

        result = tool.execute(
            path=str(test_file),
            old_str=" REMOVE_THIS",
            new_str=""
        )

        assert result.success is True
        assert test_file.read_text() == "Hello World"

    def test_diff_output_present(self, tmp_path: Path) -> None:
        """Should include diff in output."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("line1\nline2\nline3")

        tool = StrReplaceTool(allowed_paths=[tmp_path])

        result = tool.execute(
            path=str(test_file),
            old_str="line2",
            new_str="LINE_TWO"
        )

        assert result.success is True
        assert "---" in result.output  # Diff header
        assert "+++" in result.output  # Diff header
        assert "-line2" in result.output or "- line2" in result.output
        assert "+LINE_TWO" in result.output or "+ LINE_TWO" in result.output

    def test_preserves_newlines(self, tmp_path: Path) -> None:
        """Should preserve newline characters correctly."""
        test_file = tmp_path / "test.txt"
        original = "line1\nline2\nline3\n"
        test_file.write_text(original)

        tool = StrReplaceTool(allowed_paths=[tmp_path])

        result = tool.execute(
            path=str(test_file),
            old_str="line2",
            new_str="modified_line2"
        )

        assert result.success is True
        new_content = test_file.read_text()
        assert new_content == "line1\nmodified_line2\nline3\n"

    def test_unicode_content(self, tmp_path: Path) -> None:
        """Should handle unicode content correctly."""
        test_file = tmp_path / "unicode.txt"
        test_file.write_text("Hello 世界 こんにちは", encoding="utf-8")

        tool = StrReplaceTool(allowed_paths=[tmp_path])

        result = tool.execute(
            path=str(test_file),
            old_str="世界",
            new_str="World"
        )

        assert result.success is True
        assert "Hello World こんにちは" == test_file.read_text(encoding="utf-8")

    def test_exact_match_required(self, tmp_path: Path) -> None:
        """Should require exact match including whitespace."""
        test_file = tmp_path / "test.py"
        test_file.write_text("def foo():\n    pass")

        tool = StrReplaceTool(allowed_paths=[tmp_path])

        # Wrong indentation - should not match
        result = tool.execute(
            path=str(test_file),
            old_str="def foo():\npass",  # Missing indentation
            new_str="def bar():\n    pass"
        )

        assert result.success is False
        assert "not found" in result.error.lower()
