"""
Tests for code review functionality.
"""

import tempfile
from pathlib import Path

from src.agent.code_review import CodeReviewer, Severity, StaticAnalyzer
from src.tools import CodeReviewTool, ToolResult


def test_static_analyzer_init():
    """Test static analyzer initialization."""
    analyzer = StaticAnalyzer()
    # Should detect available tools
    assert isinstance(analyzer.available_tools, dict)
    # At minimum should check for mypy, ruff, pylint
    assert "mypy" in analyzer.available_tools
    assert "ruff" in analyzer.available_tools
    assert "pylint" in analyzer.available_tools


def test_analyze_nonexistent_file():
    """Test analyzing a file that doesn't exist."""
    analyzer = StaticAnalyzer()
    result = analyzer.analyze_file(Path("nonexistent.py"))

    assert not result.success
    assert "not found" in result.summary.lower()


def test_analyze_non_python_file():
    """Test analyzing a non-Python file."""
    analyzer = StaticAnalyzer()

    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        temp_path = Path(f.name)
        f.write(b"not python code")

    try:
        result = analyzer.analyze_file(temp_path)
        assert not result.success
        assert "not a python file" in result.summary.lower()
    finally:
        temp_path.unlink()


def test_analyze_valid_python():
    """Test analyzing valid Python code."""
    analyzer = StaticAnalyzer()

    with tempfile.NamedTemporaryFile(mode='w', suffix=".py", delete=False) as f:
        temp_path = Path(f.name)
        f.write("""
def hello(name: str) -> str:
    return f"Hello, {name}!"
""")

    try:
        result = analyzer.analyze_file(temp_path)
        assert result.success
        # Valid code might still have issues depending on tools available
    finally:
        temp_path.unlink()


def test_analyze_invalid_python():
    """Test analyzing Python code with issues."""
    analyzer = StaticAnalyzer()

    # Skip if no tools available
    if not any(analyzer.available_tools.values()):
        return

    with tempfile.NamedTemporaryFile(mode='w', suffix=".py", delete=False) as f:
        temp_path = Path(f.name)
        # Write code with obvious issues
        f.write("""
def bad_function():
    x = 1
    return x + "string"  # Type error
    y = 2  # Unreachable code
""")

    try:
        result = analyzer.analyze_file(temp_path)
        assert result.success  # Analysis succeeded
        # If mypy is available, should find the type error
        if analyzer.available_tools.get("mypy"):
            assert len(result.issues) > 0
    finally:
        temp_path.unlink()


def test_code_reviewer_review_file():
    """Test CodeReviewer file review."""
    reviewer = CodeReviewer()

    with tempfile.NamedTemporaryFile(mode='w', suffix=".py", delete=False) as f:
        temp_path = Path(f.name)
        f.write("print('hello')\n")

    try:
        result = reviewer.review_file(temp_path)
        assert result.success
    finally:
        temp_path.unlink()


def test_code_reviewer_format_issues():
    """Test issue formatting."""
    reviewer = CodeReviewer()

    with tempfile.NamedTemporaryFile(mode='w', suffix=".py", delete=False) as f:
        temp_path = Path(f.name)
        f.write("x = 1\n")

    try:
        result = reviewer.review_file(temp_path)
        formatted = reviewer.format_issues(result)
        assert isinstance(formatted, str)
        assert len(formatted) > 0
    finally:
        temp_path.unlink()


def test_code_review_tool_missing_path():
    """Test tool with missing path parameter."""
    tool = CodeReviewTool()
    result = tool.execute()

    assert not result.success
    assert "missing" in result.error.lower()


def test_code_review_tool_nonexistent_path():
    """Test tool with nonexistent path."""
    tool = CodeReviewTool()
    result = tool.execute(path="nonexistent_file.py")

    assert not result.success
    assert "not exist" in result.error.lower()


def test_code_review_tool_valid_file():
    """Test tool with valid Python file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix=".py", delete=False) as f:
        temp_path = Path(f.name)
        f.write("def test(): pass\n")

    try:
        tool = CodeReviewTool()
        result = tool.execute(path=str(temp_path))

        assert result.success
        assert isinstance(result.output, str)
    finally:
        temp_path.unlink()


def test_code_review_tool_directory():
    """Test tool with directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a Python file in the directory
        test_file = Path(tmpdir) / "test.py"
        test_file.write_text("x = 1\n")

        tool = CodeReviewTool()
        result = tool.execute(path=tmpdir, recursive="false")

        assert result.success
        assert "reviewed" in result.output.lower()


def test_code_review_tool_path_security():
    """Test that tool respects allowed paths."""
    with tempfile.NamedTemporaryFile(mode='w', suffix=".py", delete=False) as f:
        temp_path = Path(f.name)
        f.write("x = 1\n")

    try:
        # Create tool with restricted paths
        allowed = Path.cwd()
        tool = CodeReviewTool(allowed_paths=[allowed])

        # Try to review file outside allowed paths
        result = tool.execute(path=str(temp_path))

        # Should be blocked (unless temp is inside cwd)
        if not temp_path.is_relative_to(allowed):
            assert not result.success
            assert "not allowed" in result.error.lower()
    finally:
        temp_path.unlink()


def test_review_result_has_errors():
    """Test ReviewResult error detection."""
    from src.agent.code_review import ReviewResult, CodeIssue

    result = ReviewResult(success=True)
    assert not result.has_errors()

    result.issues.append(CodeIssue(
        file="test.py",
        line=1,
        column=1,
        severity=Severity.ERROR,
        code="E001",
        message="test",
        tool="test"
    ))
    assert result.has_errors()


def test_review_result_issue_counts():
    """Test ReviewResult issue counting."""
    from src.agent.code_review import ReviewResult, CodeIssue

    result = ReviewResult(success=True)
    result.issues.append(CodeIssue(
        file="test.py", line=1, column=1,
        severity=Severity.ERROR, code="E001", message="test", tool="test"
    ))
    result.issues.append(CodeIssue(
        file="test.py", line=2, column=1,
        severity=Severity.WARNING, code="W001", message="test", tool="test"
    ))
    result.issues.append(CodeIssue(
        file="test.py", line=3, column=1,
        severity=Severity.WARNING, code="W002", message="test", tool="test"
    ))

    counts = result.issue_count_by_severity()
    assert counts[Severity.ERROR] == 1
    assert counts[Severity.WARNING] == 2
    assert counts[Severity.INFO] == 0
