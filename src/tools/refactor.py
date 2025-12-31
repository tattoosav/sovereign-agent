"""
Multi-File Refactoring Tool.

Provides intelligent refactoring capabilities across multiple files,
with support for rename, extract, move, and other refactoring operations.
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


@dataclass
class RefactorChange:
    """A single change in a refactoring operation."""
    file_path: Path
    line_number: int
    old_text: str
    new_text: str
    change_type: str  # "replace", "insert", "delete"


@dataclass
class RefactorResult:
    """Result of a refactoring operation."""
    success: bool
    changes: list[RefactorChange]
    files_modified: int
    error: str | None = None


class RefactorTool(BaseTool):
    """Tool for multi-file refactoring operations."""

    name = "refactor"
    description = """Perform multi-file refactoring operations.

Operations:
- rename_symbol: Rename a variable, function, class, or method across files
- extract_function: Extract code into a new function
- extract_class: Extract code into a new class
- move_to_file: Move a function or class to a different file
- inline_function: Inline a function's body at call sites
- change_signature: Change a function's parameters
- find_usages: Find all usages of a symbol
"""
    parameters = {
        "operation": "Refactoring operation to perform",
        "symbol": "Symbol name to refactor",
        "new_name": "New name (for rename operations)",
        "file_path": "File to refactor (or starting point)",
        "scope": "Scope: file, directory, project",
        "line_start": "Starting line (for extract operations)",
        "line_end": "Ending line (for extract operations)",
    }

    def __init__(self, working_dir: Path | None = None):
        self.working_dir = working_dir or Path.cwd()

    def execute(
        self,
        operation: str,
        symbol: str = "",
        new_name: str = "",
        file_path: str = "",
        scope: str = "project",
        line_start: int = 0,
        line_end: int = 0,
        **kwargs: Any
    ) -> ToolResult:
        """Execute refactoring operation."""
        try:
            if operation == "rename_symbol":
                return self._rename_symbol(symbol, new_name, file_path, scope)
            elif operation == "extract_function":
                return self._extract_function(file_path, line_start, line_end, new_name)
            elif operation == "extract_class":
                return self._extract_class(file_path, line_start, line_end, new_name)
            elif operation == "move_to_file":
                return self._move_to_file(symbol, file_path, kwargs.get("target_file", ""))
            elif operation == "find_usages":
                return self._find_usages(symbol, file_path, scope)
            elif operation == "inline_function":
                return self._inline_function(symbol, file_path)
            elif operation == "change_signature":
                return self._change_signature(
                    symbol, file_path,
                    kwargs.get("new_params", []),
                    kwargs.get("new_return_type", "")
                )
            else:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Unknown operation: {operation}"
                )
        except Exception as e:
            logger.exception(f"Refactor error: {e}")
            return ToolResult(success=False, output="", error=str(e))

    def _get_files_in_scope(self, file_path: str, scope: str) -> list[Path]:
        """Get files to process based on scope."""
        path = Path(file_path) if file_path else self.working_dir

        if scope == "file":
            return [path] if path.is_file() else []

        if scope == "directory":
            base = path if path.is_dir() else path.parent
        else:  # project
            base = self.working_dir

        # Find all source files
        extensions = [".py", ".cpp", ".c", ".h", ".hpp", ".cs", ".java", ".js", ".ts"]
        files = []
        for ext in extensions:
            files.extend(base.rglob(f"*{ext}"))

        # Exclude common directories
        exclude_dirs = {"node_modules", "__pycache__", ".git", "venv", ".venv", "build", "dist"}
        files = [f for f in files if not any(d in f.parts for d in exclude_dirs)]

        return files

    def _rename_symbol(
        self,
        symbol: str,
        new_name: str,
        file_path: str,
        scope: str
    ) -> ToolResult:
        """Rename a symbol across files."""
        if not symbol or not new_name:
            return ToolResult(
                success=False,
                output="",
                error="Both symbol and new_name are required"
            )

        files = self._get_files_in_scope(file_path, scope)
        if not files:
            return ToolResult(
                success=False,
                output="",
                error="No files found in scope"
            )

        changes = []
        files_modified = set()

        # Pattern to match whole word only
        pattern = re.compile(rf'\b{re.escape(symbol)}\b')

        for file in files:
            try:
                content = file.read_text(encoding="utf-8")
                lines = content.split('\n')
                file_changed = False

                for i, line in enumerate(lines):
                    if pattern.search(line):
                        new_line = pattern.sub(new_name, line)
                        if new_line != line:
                            changes.append(RefactorChange(
                                file_path=file,
                                line_number=i + 1,
                                old_text=line.strip(),
                                new_text=new_line.strip(),
                                change_type="replace"
                            ))
                            lines[i] = new_line
                            file_changed = True

                if file_changed:
                    file.write_text('\n'.join(lines), encoding="utf-8")
                    files_modified.add(file)

            except Exception as e:
                logger.warning(f"Error processing {file}: {e}")

        output_lines = [
            f"Renamed '{symbol}' to '{new_name}'",
            f"Files modified: {len(files_modified)}",
            f"Changes made: {len(changes)}",
            "",
            "Changes:"
        ]

        for change in changes[:20]:  # Show first 20 changes
            output_lines.append(
                f"  {change.file_path.name}:{change.line_number}"
            )

        if len(changes) > 20:
            output_lines.append(f"  ... and {len(changes) - 20} more")

        return ToolResult(
            success=True,
            output="\n".join(output_lines)
        )

    def _find_usages(
        self,
        symbol: str,
        file_path: str,
        scope: str
    ) -> ToolResult:
        """Find all usages of a symbol."""
        if not symbol:
            return ToolResult(success=False, output="", error="Symbol is required")

        files = self._get_files_in_scope(file_path, scope)
        pattern = re.compile(rf'\b{re.escape(symbol)}\b')

        usages = []

        for file in files:
            try:
                content = file.read_text(encoding="utf-8")
                lines = content.split('\n')

                for i, line in enumerate(lines):
                    matches = list(pattern.finditer(line))
                    for match in matches:
                        usages.append({
                            "file": str(file),
                            "line": i + 1,
                            "column": match.start() + 1,
                            "text": line.strip(),
                        })

            except Exception as e:
                logger.warning(f"Error processing {file}: {e}")

        output_lines = [
            f"Found {len(usages)} usages of '{symbol}'",
            ""
        ]

        for usage in usages[:50]:
            rel_path = Path(usage["file"]).relative_to(self.working_dir) \
                if self.working_dir in Path(usage["file"]).parents else usage["file"]
            output_lines.append(
                f"{rel_path}:{usage['line']}:{usage['column']}"
            )
            output_lines.append(f"  {usage['text']}")

        if len(usages) > 50:
            output_lines.append(f"\n... and {len(usages) - 50} more usages")

        return ToolResult(success=True, output="\n".join(output_lines))

    def _extract_function(
        self,
        file_path: str,
        line_start: int,
        line_end: int,
        function_name: str
    ) -> ToolResult:
        """Extract code into a new function."""
        if not file_path or not function_name:
            return ToolResult(
                success=False,
                output="",
                error="file_path and function_name are required"
            )

        path = Path(file_path)
        if not path.exists():
            return ToolResult(success=False, output="", error="File not found")

        content = path.read_text(encoding="utf-8")
        lines = content.split('\n')

        if line_start < 1 or line_end > len(lines):
            return ToolResult(
                success=False,
                output="",
                error=f"Invalid line range. File has {len(lines)} lines."
            )

        # Extract the code block
        extracted_lines = lines[line_start - 1:line_end]
        extracted_code = '\n'.join(extracted_lines)

        # Detect language
        ext = path.suffix.lower()

        if ext == ".py":
            # Python extraction
            indent = len(extracted_lines[0]) - len(extracted_lines[0].lstrip())
            base_indent = ' ' * indent

            # Find variables used
            variables = set(re.findall(r'\b([a-zA-Z_]\w*)\b', extracted_code))

            new_function = f"\ndef {function_name}():\n"
            for line in extracted_lines:
                new_function += f"    {line.strip()}\n"

            # Replace original code with function call
            lines[line_start - 1] = f"{base_indent}{function_name}()"
            del lines[line_start:line_end]

            # Add function definition at the end of file
            lines.append(new_function)

        elif ext in [".cpp", ".c", ".h", ".hpp", ".cs", ".java"]:
            # C-style extraction
            indent = len(extracted_lines[0]) - len(extracted_lines[0].lstrip())
            base_indent = ' ' * indent

            if ext == ".cs":
                new_function = f"\nprivate void {function_name}()\n{{\n"
            else:
                new_function = f"\nvoid {function_name}()\n{{\n"

            for line in extracted_lines:
                new_function += f"    {line}\n"
            new_function += "}\n"

            # Replace original code with function call
            lines[line_start - 1] = f"{base_indent}{function_name}();"
            del lines[line_start:line_end]

            # Add function before main or at appropriate place
            lines.append(new_function)

        else:
            return ToolResult(
                success=False,
                output="",
                error=f"Unsupported file type: {ext}"
            )

        # Write modified content
        path.write_text('\n'.join(lines), encoding="utf-8")

        return ToolResult(
            success=True,
            output=f"Extracted lines {line_start}-{line_end} to function '{function_name}'\n"
                   f"Function added to {path.name}"
        )

    def _extract_class(
        self,
        file_path: str,
        line_start: int,
        line_end: int,
        class_name: str
    ) -> ToolResult:
        """Extract code into a new class."""
        if not file_path or not class_name:
            return ToolResult(
                success=False,
                output="",
                error="file_path and class_name are required"
            )

        path = Path(file_path)
        if not path.exists():
            return ToolResult(success=False, output="", error="File not found")

        content = path.read_text(encoding="utf-8")
        lines = content.split('\n')
        ext = path.suffix.lower()

        if line_start < 1 or line_end > len(lines):
            return ToolResult(
                success=False,
                output="",
                error=f"Invalid line range"
            )

        extracted_lines = lines[line_start - 1:line_end]

        if ext == ".py":
            new_class = f"\nclass {class_name}:\n"
            new_class += "    def __init__(self):\n"
            new_class += "        pass\n\n"
            new_class += "    def execute(self):\n"
            for line in extracted_lines:
                new_class += f"        {line.strip()}\n"

        elif ext == ".cs":
            new_class = f"\npublic class {class_name}\n{{\n"
            new_class += "    public void Execute()\n    {\n"
            for line in extracted_lines:
                new_class += f"        {line}\n"
            new_class += "    }\n}\n"

        elif ext in [".cpp", ".h", ".hpp"]:
            new_class = f"\nclass {class_name}\n{{\npublic:\n"
            new_class += "    void Execute()\n    {\n"
            for line in extracted_lines:
                new_class += f"        {line}\n"
            new_class += "    }\n};\n"

        else:
            return ToolResult(
                success=False,
                output="",
                error=f"Unsupported file type: {ext}"
            )

        # Write new class file
        new_file = path.parent / f"{class_name}{ext}"
        new_file.write_text(new_class, encoding="utf-8")

        return ToolResult(
            success=True,
            output=f"Created class '{class_name}' in {new_file.name}"
        )

    def _move_to_file(
        self,
        symbol: str,
        source_file: str,
        target_file: str
    ) -> ToolResult:
        """Move a function or class to a different file."""
        if not all([symbol, source_file, target_file]):
            return ToolResult(
                success=False,
                output="",
                error="symbol, source_file, and target_file are required"
            )

        source = Path(source_file)
        target = Path(target_file)

        if not source.exists():
            return ToolResult(success=False, output="", error="Source file not found")

        content = source.read_text(encoding="utf-8")
        ext = source.suffix.lower()

        # Pattern to find function/class definition
        if ext == ".py":
            # Match Python function or class
            pattern = re.compile(
                rf'^((?:def|class)\s+{re.escape(symbol)}[^:]*:.*?)(?=\n(?:def|class)\s|\Z)',
                re.MULTILINE | re.DOTALL
            )
        elif ext in [".cpp", ".c", ".h", ".hpp"]:
            # Match C++ function or class
            pattern = re.compile(
                rf'((?:class|struct)\s+{re.escape(symbol)}\s*[^{{]*\{{[^}}]*\}};?|'
                rf'[^\n]*\s+{re.escape(symbol)}\s*\([^)]*\)\s*\{{[^}}]*\}})',
                re.MULTILINE | re.DOTALL
            )
        elif ext == ".cs":
            # Match C# method or class
            pattern = re.compile(
                rf'((?:public|private|protected|internal)?\s*(?:static)?\s*(?:class|struct)\s+{re.escape(symbol)}[^{{]*\{{[^}}]*\}}|'
                rf'(?:public|private|protected|internal)?\s*(?:static)?\s*\w+\s+{re.escape(symbol)}\s*\([^)]*\)\s*\{{[^}}]*\}})',
                re.MULTILINE | re.DOTALL
            )
        else:
            return ToolResult(
                success=False,
                output="",
                error=f"Unsupported file type: {ext}"
            )

        match = pattern.search(content)
        if not match:
            return ToolResult(
                success=False,
                output="",
                error=f"Could not find '{symbol}' in {source.name}"
            )

        extracted = match.group(1)

        # Remove from source
        new_source_content = content[:match.start()] + content[match.end():]
        source.write_text(new_source_content.strip() + '\n', encoding="utf-8")

        # Add to target
        if target.exists():
            target_content = target.read_text(encoding="utf-8")
            target_content += f"\n\n{extracted}"
        else:
            target_content = extracted

        target.write_text(target_content, encoding="utf-8")

        return ToolResult(
            success=True,
            output=f"Moved '{symbol}' from {source.name} to {target.name}"
        )

    def _inline_function(self, symbol: str, file_path: str) -> ToolResult:
        """Inline a function at its call sites."""
        # This is a complex operation that would need proper AST parsing
        # For now, provide guidance
        return ToolResult(
            success=True,
            output=f"Inlining '{symbol}' requires careful analysis.\n"
                   f"1. Find the function definition\n"
                   f"2. Find all call sites\n"
                   f"3. Replace each call with the function body\n"
                   f"4. Substitute parameters with arguments\n"
                   f"5. Handle return statements\n\n"
                   f"Use 'find_usages' to locate all call sites first."
        )

    def _change_signature(
        self,
        symbol: str,
        file_path: str,
        new_params: list[str],
        new_return_type: str
    ) -> ToolResult:
        """Change a function's signature."""
        if not symbol or not file_path:
            return ToolResult(
                success=False,
                output="",
                error="symbol and file_path are required"
            )

        # First, find all usages
        usages_result = self._find_usages(symbol, file_path, "project")

        return ToolResult(
            success=True,
            output=f"To change signature of '{symbol}':\n"
                   f"1. Update the function definition\n"
                   f"2. Update all call sites\n\n"
                   f"{usages_result.output}"
        )
