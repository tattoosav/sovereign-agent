"""
Tests for filesystem tools.

Run with: uv run pytest tests/
"""

import tempfile
from pathlib import Path

import pytest

from src.tools import ReadFileTool, WriteFileTool, ListDirectoryTool


class TestReadFileTool:
    """Tests for ReadFileTool."""
    
    def test_read_existing_file(self, tmp_path: Path) -> None:
        """Should read contents of existing file."""
        # Setup
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, World!")
        
        tool = ReadFileTool(allowed_paths=[tmp_path])
        
        # Execute
        result = tool.execute(path=str(test_file))
        
        # Verify
        assert result.success is True
        assert result.output == "Hello, World!"
        assert result.error is None
    
    def test_read_nonexistent_file(self, tmp_path: Path) -> None:
        """Should fail for nonexistent file."""
        tool = ReadFileTool(allowed_paths=[tmp_path])
        
        result = tool.execute(path=str(tmp_path / "does_not_exist.txt"))
        
        assert result.success is False
        assert "not found" in result.error.lower()
    
    def test_read_outside_allowed_path(self, tmp_path: Path) -> None:
        """Should deny access outside allowed paths."""
        tool = ReadFileTool(allowed_paths=[tmp_path])
        
        result = tool.execute(path="/etc/passwd")
        
        assert result.success is False
        assert "denied" in result.error.lower()
    
    def test_read_missing_path_param(self) -> None:
        """Should fail if path parameter missing."""
        tool = ReadFileTool()
        
        result = tool.execute()
        
        assert result.success is False
        assert "missing" in result.error.lower()


class TestWriteFileTool:
    """Tests for WriteFileTool."""
    
    def test_write_new_file(self, tmp_path: Path) -> None:
        """Should create new file with content."""
        tool = WriteFileTool(allowed_paths=[tmp_path])
        test_file = tmp_path / "new.txt"
        
        result = tool.execute(path=str(test_file), content="New content")
        
        assert result.success is True
        assert test_file.exists()
        assert test_file.read_text() == "New content"
    
    def test_overwrite_existing_file(self, tmp_path: Path) -> None:
        """Should overwrite existing file."""
        test_file = tmp_path / "existing.txt"
        test_file.write_text("Old content")
        
        tool = WriteFileTool(allowed_paths=[tmp_path])
        result = tool.execute(path=str(test_file), content="New content")
        
        assert result.success is True
        assert test_file.read_text() == "New content"
    
    def test_write_creates_parent_dirs(self, tmp_path: Path) -> None:
        """Should create parent directories if needed."""
        tool = WriteFileTool(allowed_paths=[tmp_path])
        test_file = tmp_path / "subdir" / "nested" / "file.txt"
        
        result = tool.execute(path=str(test_file), content="Nested content")
        
        assert result.success is True
        assert test_file.exists()
    
    def test_write_outside_allowed_path(self, tmp_path: Path) -> None:
        """Should deny writes outside allowed paths."""
        tool = WriteFileTool(allowed_paths=[tmp_path])
        
        result = tool.execute(path="/tmp/unauthorized.txt", content="Bad")
        
        assert result.success is False
        assert "denied" in result.error.lower()


class TestListDirectoryTool:
    """Tests for ListDirectoryTool."""
    
    def test_list_directory(self, tmp_path: Path) -> None:
        """Should list directory contents."""
        # Setup
        (tmp_path / "file1.txt").write_text("a")
        (tmp_path / "file2.py").write_text("b")
        (tmp_path / "subdir").mkdir()
        
        tool = ListDirectoryTool(allowed_paths=[tmp_path])
        result = tool.execute(path=str(tmp_path))
        
        assert result.success is True
        assert "file1.txt" in result.output
        assert "file2.py" in result.output
        assert "subdir" in result.output
    
    def test_list_empty_directory(self, tmp_path: Path) -> None:
        """Should handle empty directory."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        
        tool = ListDirectoryTool(allowed_paths=[tmp_path])
        result = tool.execute(path=str(empty_dir))
        
        assert result.success is True
        assert "empty" in result.output.lower()
    
    def test_list_nonexistent_directory(self, tmp_path: Path) -> None:
        """Should fail for nonexistent directory."""
        tool = ListDirectoryTool(allowed_paths=[tmp_path])
        
        result = tool.execute(path=str(tmp_path / "nope"))
        
        assert result.success is False
        assert "not found" in result.error.lower()
