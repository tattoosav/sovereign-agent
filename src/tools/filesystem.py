"""
Filesystem tools for the agent.

Tools:
- read_file: Read contents of a file
- write_file: Write/create a file
- list_directory: List files in a directory
"""

from pathlib import Path
from typing import Any

from .base import BaseTool, ToolResult


class ReadFileTool(BaseTool):
    """Read the contents of a file."""
    
    def __init__(self, allowed_paths: list[Path] | None = None):
        self._allowed_paths = allowed_paths
    
    @property
    def name(self) -> str:
        return "read_file"
    
    @property
    def description(self) -> str:
        return "Read the contents of a file at the specified path."
    
    @property
    def parameters(self) -> dict[str, dict[str, Any]]:
        return {
            "path": {
                "type": "string",
                "description": "Absolute or relative path to the file",
                "required": True
            }
        }
    
    def _is_path_allowed(self, path: Path) -> bool:
        """Check if path is within allowed directories."""
        if self._allowed_paths is None:
            return True
        resolved = path.resolve()
        return any(
            resolved.is_relative_to(allowed.resolve()) 
            for allowed in self._allowed_paths
        )
    
    def execute(self, **kwargs: Any) -> ToolResult:
        path_str = kwargs.get("path")
        if not path_str:
            return ToolResult(
                success=False,
                output="",
                error="Missing required parameter: path"
            )
        
        path = Path(path_str)
        
        if not self._is_path_allowed(path):
            return ToolResult(
                success=False,
                output="",
                error=f"Access denied: {path} is outside allowed directories"
            )
        
        if not path.exists():
            return ToolResult(
                success=False,
                output="",
                error=f"File not found: {path}"
            )
        
        if not path.is_file():
            return ToolResult(
                success=False,
                output="",
                error=f"Not a file: {path}"
            )
        
        try:
            content = path.read_text(encoding="utf-8")
            return ToolResult(
                success=True,
                output=content
            )
        except UnicodeDecodeError:
            # Try other encodings
            for encoding in ["latin-1", "cp1252", "utf-16"]:
                try:
                    content = path.read_text(encoding=encoding)
                    return ToolResult(
                        success=True,
                        output=f"[Read with {encoding} encoding]\n{content}"
                    )
                except (UnicodeDecodeError, Exception):
                    continue

            # If all encodings fail, provide file info
            try:
                file_size = path.stat().st_size
                # Read first bytes to detect type
                with open(path, "rb") as f:
                    header = f.read(32)
                header_hex = header.hex()

                return ToolResult(
                    success=False,
                    output=f"File info: {file_size} bytes, header: {header_hex[:32]}...",
                    error=f"Cannot read {path}: binary file ({file_size} bytes). This appears to be a compiled/binary file, not source code."
                )
            except Exception:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Cannot read {path}: binary/non-text file"
                )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Error reading {path}: {e}"
            )


class WriteFileTool(BaseTool):
    """Write content to a file."""
    
    def __init__(self, allowed_paths: list[Path] | None = None):
        self._allowed_paths = allowed_paths
    
    @property
    def name(self) -> str:
        return "write_file"
    
    @property
    def description(self) -> str:
        return "Write content to a file. Creates the file if it doesn't exist, overwrites if it does."
    
    @property
    def parameters(self) -> dict[str, dict[str, Any]]:
        return {
            "path": {
                "type": "string",
                "description": "Absolute or relative path to the file",
                "required": True
            },
            "content": {
                "type": "string",
                "description": "Content to write to the file",
                "required": True
            }
        }
    
    def _is_path_allowed(self, path: Path) -> bool:
        if self._allowed_paths is None:
            return True
        resolved = path.resolve()
        return any(
            resolved.is_relative_to(allowed.resolve()) 
            for allowed in self._allowed_paths
        )
    
    def execute(self, **kwargs: Any) -> ToolResult:
        path_str = kwargs.get("path")
        content = kwargs.get("content")
        
        if not path_str:
            return ToolResult(success=False, output="", error="Missing required parameter: path")
        if content is None:
            return ToolResult(success=False, output="", error="Missing required parameter: content")
        
        path = Path(path_str)
        
        if not self._is_path_allowed(path):
            return ToolResult(
                success=False,
                output="",
                error=f"Access denied: {path} is outside allowed directories"
            )
        
        try:
            # Create parent directories if needed
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            return ToolResult(
                success=True,
                output=f"Successfully wrote {len(content)} bytes to {path}"
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Error writing to {path}: {e}"
            )


class ListDirectoryTool(BaseTool):
    """List contents of a directory."""
    
    def __init__(self, allowed_paths: list[Path] | None = None):
        self._allowed_paths = allowed_paths
    
    @property
    def name(self) -> str:
        return "list_directory"
    
    @property
    def description(self) -> str:
        return "List files and subdirectories in the specified directory."
    
    @property
    def parameters(self) -> dict[str, dict[str, Any]]:
        return {
            "path": {
                "type": "string",
                "description": "Path to the directory",
                "required": True
            },
            "recursive": {
                "type": "boolean",
                "description": "Whether to list recursively (default: false)",
                "required": False
            }
        }
    
    def _is_path_allowed(self, path: Path) -> bool:
        if self._allowed_paths is None:
            return True
        resolved = path.resolve()
        return any(
            resolved.is_relative_to(allowed.resolve()) 
            for allowed in self._allowed_paths
        )
    
    def execute(self, **kwargs: Any) -> ToolResult:
        path_str = kwargs.get("path")
        recursive = kwargs.get("recursive", False)
        
        if not path_str:
            return ToolResult(success=False, output="", error="Missing required parameter: path")
        
        path = Path(path_str)
        
        if not self._is_path_allowed(path):
            return ToolResult(
                success=False,
                output="",
                error=f"Access denied: {path} is outside allowed directories"
            )
        
        if not path.exists():
            return ToolResult(success=False, output="", error=f"Directory not found: {path}")
        
        if not path.is_dir():
            return ToolResult(success=False, output="", error=f"Not a directory: {path}")
        
        try:
            entries = []
            if recursive:
                for item in path.rglob("*"):
                    rel_path = item.relative_to(path)
                    prefix = "[DIR] " if item.is_dir() else "[FILE]"
                    entries.append(f"{prefix} {rel_path}")
            else:
                for item in sorted(path.iterdir()):
                    prefix = "[DIR] " if item.is_dir() else "[FILE]"
                    entries.append(f"{prefix} {item.name}")
            
            output = "\n".join(entries) if entries else "(empty directory)"
            return ToolResult(success=True, output=output)
        except Exception as e:
            return ToolResult(success=False, output="", error=f"Error listing {path}: {e}")
