"""
Automated Documentation Generator.

Generates comprehensive documentation from code analysis.
Supports Python, C++, C#, and other languages.
"""

import ast
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


@dataclass
class DocItem:
    """A documentation item."""
    name: str
    kind: str  # module, class, function, method, property, variable
    signature: str = ""
    docstring: str = ""
    file_path: str = ""
    line_number: int = 0
    parameters: list[dict[str, str]] = field(default_factory=list)
    returns: str = ""
    raises: list[str] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)
    children: list["DocItem"] = field(default_factory=list)


@dataclass
class ModuleDoc:
    """Documentation for a module/file."""
    name: str
    path: str
    description: str = ""
    classes: list[DocItem] = field(default_factory=list)
    functions: list[DocItem] = field(default_factory=list)
    constants: list[DocItem] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)


class DocGenerator:
    """Generates documentation from source code."""

    def __init__(self):
        self.modules: list[ModuleDoc] = []

    def analyze_python_file(self, file_path: Path) -> ModuleDoc | None:
        """Analyze a Python file and extract documentation."""
        try:
            content = file_path.read_text(encoding="utf-8")
            tree = ast.parse(content)

            module_doc = ModuleDoc(
                name=file_path.stem,
                path=str(file_path),
                description=ast.get_docstring(tree) or "",
            )

            # Extract imports
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        module_doc.imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    module_name = node.module or ""
                    for alias in node.names:
                        module_doc.imports.append(f"{module_name}.{alias.name}")

            # Process top-level nodes
            for node in tree.body:
                if isinstance(node, ast.ClassDef):
                    class_doc = self._analyze_class(node, content)
                    module_doc.classes.append(class_doc)
                elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                    func_doc = self._analyze_function(node, content)
                    module_doc.functions.append(func_doc)
                elif isinstance(node, ast.Assign):
                    # Top-level constants
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id.isupper():
                            module_doc.constants.append(DocItem(
                                name=target.id,
                                kind="constant",
                                line_number=node.lineno,
                            ))

            return module_doc

        except SyntaxError as e:
            logger.warning(f"Syntax error in {file_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error analyzing {file_path}: {e}")
            return None

    def _analyze_class(self, node: ast.ClassDef, source: str) -> DocItem:
        """Analyze a class definition."""
        bases = [
            ast.unparse(base) if hasattr(ast, "unparse") else ""
            for base in node.bases
        ]
        signature = f"class {node.name}({', '.join(bases)})" if bases else f"class {node.name}"

        class_doc = DocItem(
            name=node.name,
            kind="class",
            signature=signature,
            docstring=ast.get_docstring(node) or "",
            line_number=node.lineno,
        )

        # Analyze methods
        for item in node.body:
            if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef):
                method_doc = self._analyze_function(item, source)
                method_doc.kind = "method"
                class_doc.children.append(method_doc)
            elif isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                # Class attribute with annotation
                attr_doc = DocItem(
                    name=item.target.id,
                    kind="property",
                    signature=f"{item.target.id}: {ast.unparse(item.annotation) if hasattr(ast, 'unparse') else ''}",
                    line_number=item.lineno,
                )
                class_doc.children.append(attr_doc)

        return class_doc

    def _analyze_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef, source: str) -> DocItem:
        """Analyze a function definition."""
        # Build signature
        args = []
        for arg in node.args.args:
            arg_str = arg.arg
            if arg.annotation:
                try:
                    arg_str += f": {ast.unparse(arg.annotation)}"
                except Exception:
                    pass
            args.append(arg_str)

        # Add *args and **kwargs
        if node.args.vararg:
            args.append(f"*{node.args.vararg.arg}")
        if node.args.kwarg:
            args.append(f"**{node.args.kwarg.arg}")

        return_type = ""
        if node.returns:
            try:
                return_type = ast.unparse(node.returns)
            except Exception:
                pass

        prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
        signature = f"{prefix} {node.name}({', '.join(args)})"
        if return_type:
            signature += f" -> {return_type}"

        # Parse docstring
        docstring = ast.get_docstring(node) or ""
        parameters, returns, raises, examples = self._parse_docstring(docstring)

        return DocItem(
            name=node.name,
            kind="function",
            signature=signature,
            docstring=docstring,
            line_number=node.lineno,
            parameters=parameters,
            returns=returns,
            raises=raises,
            examples=examples,
        )

    def _parse_docstring(self, docstring: str) -> tuple[list, str, list, list]:
        """Parse docstring to extract structured information."""
        parameters = []
        returns = ""
        raises = []
        examples = []

        if not docstring:
            return parameters, returns, raises, examples

        # Parse Google-style docstring
        current_section = None
        current_content = []

        lines = docstring.split("\n")
        for line in lines:
            stripped = line.strip()

            # Check for section headers
            if stripped in ("Args:", "Arguments:", "Parameters:"):
                current_section = "args"
                continue
            elif stripped in ("Returns:", "Return:"):
                current_section = "returns"
                continue
            elif stripped in ("Raises:", "Exceptions:"):
                current_section = "raises"
                continue
            elif stripped in ("Examples:", "Example:"):
                current_section = "examples"
                continue

            # Process content based on section
            if current_section == "args" and stripped:
                # Parse parameter: "name (type): description"
                match = re.match(r"(\w+)\s*(?:\(([^)]+)\))?\s*:\s*(.*)", stripped)
                if match:
                    parameters.append({
                        "name": match.group(1),
                        "type": match.group(2) or "",
                        "description": match.group(3),
                    })
            elif current_section == "returns" and stripped:
                returns += stripped + " "
            elif current_section == "raises" and stripped:
                raises.append(stripped)
            elif current_section == "examples" and line:
                examples.append(line)

        return parameters, returns.strip(), raises, examples

    def analyze_cpp_file(self, file_path: Path) -> ModuleDoc | None:
        """Analyze a C++ file and extract documentation."""
        try:
            content = file_path.read_text(encoding="utf-8")
            module_doc = ModuleDoc(
                name=file_path.stem,
                path=str(file_path),
            )

            # Extract classes
            class_pattern = r"(?:/\*\*(.*?)\*/\s*)?(class|struct)\s+(\w+)(?:\s*:\s*([^{]+))?\s*\{"
            for match in re.finditer(class_pattern, content, re.DOTALL):
                docstring = match.group(1) or ""
                kind = match.group(2)
                name = match.group(3)
                bases = match.group(4) or ""

                class_doc = DocItem(
                    name=name,
                    kind=kind,
                    signature=f"{kind} {name}" + (f" : {bases.strip()}" if bases else ""),
                    docstring=self._clean_cpp_docstring(docstring),
                    line_number=content[:match.start()].count("\n") + 1,
                )
                module_doc.classes.append(class_doc)

            # Extract functions
            func_pattern = r"(?:/\*\*(.*?)\*/\s*)?(?:(?:virtual|static|inline|constexpr|explicit)\s+)*(\w+(?:<[^>]+>)?(?:\s*\*)?)\s+(\w+)\s*\(([^)]*)\)"
            for match in re.finditer(func_pattern, content, re.DOTALL):
                docstring = match.group(1) or ""
                return_type = match.group(2)
                name = match.group(3)
                params = match.group(4)

                # Skip common false positives
                if name in ("if", "while", "for", "switch", "catch", "sizeof", "return"):
                    continue

                func_doc = DocItem(
                    name=name,
                    kind="function",
                    signature=f"{return_type} {name}({params})",
                    docstring=self._clean_cpp_docstring(docstring),
                    returns=return_type,
                    line_number=content[:match.start()].count("\n") + 1,
                )
                module_doc.functions.append(func_doc)

            return module_doc

        except Exception as e:
            logger.error(f"Error analyzing C++ file {file_path}: {e}")
            return None

    def _clean_cpp_docstring(self, docstring: str) -> str:
        """Clean up C++ docstring (remove * from each line)."""
        lines = []
        for line in docstring.split("\n"):
            line = line.strip()
            if line.startswith("*"):
                line = line[1:].strip()
            if line:
                lines.append(line)
        return "\n".join(lines)

    def analyze_csharp_file(self, file_path: Path) -> ModuleDoc | None:
        """Analyze a C# file and extract documentation."""
        try:
            content = file_path.read_text(encoding="utf-8")
            module_doc = ModuleDoc(
                name=file_path.stem,
                path=str(file_path),
            )

            # Extract namespace
            ns_match = re.search(r"namespace\s+([\w.]+)", content)
            if ns_match:
                module_doc.description = f"Namespace: {ns_match.group(1)}"

            # Extract classes
            class_pattern = r"(?:///\s*<summary>\s*(.*?)</summary>\s*)?(?:public|private|protected|internal)?\s*(?:partial|abstract|sealed|static)?\s*class\s+(\w+)(?:<[^>]+>)?(?:\s*:\s*([^{]+))?\s*\{"
            for match in re.finditer(class_pattern, content, re.DOTALL):
                summary = match.group(1) or ""
                name = match.group(2)
                bases = match.group(3) or ""

                class_doc = DocItem(
                    name=name,
                    kind="class",
                    signature=f"class {name}" + (f" : {bases.strip()}" if bases else ""),
                    docstring=self._clean_xml_doc(summary),
                    line_number=content[:match.start()].count("\n") + 1,
                )
                module_doc.classes.append(class_doc)

            # Extract methods
            method_pattern = r"(?:///\s*<summary>\s*(.*?)</summary>\s*)?(?:public|private|protected|internal)\s+(?:static|virtual|override|async)?\s*(\w+(?:<[^>]+>)?(?:\[\])?)\s+(\w+)\s*\(([^)]*)\)"
            for match in re.finditer(method_pattern, content, re.DOTALL):
                summary = match.group(1) or ""
                return_type = match.group(2)
                name = match.group(3)
                params = match.group(4)

                func_doc = DocItem(
                    name=name,
                    kind="method",
                    signature=f"{return_type} {name}({params})",
                    docstring=self._clean_xml_doc(summary),
                    returns=return_type,
                    line_number=content[:match.start()].count("\n") + 1,
                )
                module_doc.functions.append(func_doc)

            return module_doc

        except Exception as e:
            logger.error(f"Error analyzing C# file {file_path}: {e}")
            return None

    def _clean_xml_doc(self, xml_doc: str) -> str:
        """Clean up XML documentation comments."""
        # Remove XML tags
        clean = re.sub(r"<[^>]+>", "", xml_doc)
        # Clean up whitespace
        clean = re.sub(r"\s+", " ", clean).strip()
        return clean

    def generate_markdown(self, modules: list[ModuleDoc]) -> str:
        """Generate markdown documentation."""
        lines = []

        for module in modules:
            lines.append(f"# {module.name}")
            lines.append("")

            if module.description:
                lines.append(module.description)
                lines.append("")

            lines.append(f"**File:** `{module.path}`")
            lines.append("")

            # Table of Contents
            if module.classes or module.functions:
                lines.append("## Contents")
                lines.append("")
                for cls in module.classes:
                    lines.append(f"- [{cls.name}](#{cls.name.lower()})")
                for func in module.functions:
                    lines.append(f"- [{func.name}](#{func.name.lower()})")
                lines.append("")

            # Classes
            for cls in module.classes:
                lines.append(f"## {cls.name}")
                lines.append("")
                lines.append(f"```python")
                lines.append(cls.signature)
                lines.append("```")
                lines.append("")

                if cls.docstring:
                    lines.append(cls.docstring.split("\n")[0])
                    lines.append("")

                # Methods
                if cls.children:
                    lines.append("### Methods")
                    lines.append("")
                    for method in cls.children:
                        if method.kind == "method" and not method.name.startswith("_"):
                            lines.append(f"#### `{method.name}`")
                            lines.append("")
                            lines.append(f"```python")
                            lines.append(method.signature)
                            lines.append("```")
                            lines.append("")
                            if method.docstring:
                                # Just the first line/paragraph
                                first_line = method.docstring.split("\n\n")[0]
                                lines.append(first_line)
                                lines.append("")

            # Functions
            if module.functions:
                lines.append("## Functions")
                lines.append("")
                for func in module.functions:
                    if not func.name.startswith("_"):
                        lines.append(f"### `{func.name}`")
                        lines.append("")
                        lines.append(f"```python")
                        lines.append(func.signature)
                        lines.append("```")
                        lines.append("")
                        if func.docstring:
                            first_line = func.docstring.split("\n\n")[0]
                            lines.append(first_line)
                            lines.append("")

            # Constants
            if module.constants:
                lines.append("## Constants")
                lines.append("")
                for const in module.constants:
                    lines.append(f"- `{const.name}`")
                lines.append("")

            lines.append("---")
            lines.append("")

        return "\n".join(lines)

    def generate_html(self, modules: list[ModuleDoc]) -> str:
        """Generate HTML documentation."""
        html_parts = [
            "<!DOCTYPE html>",
            "<html lang='en'>",
            "<head>",
            "<meta charset='UTF-8'>",
            "<meta name='viewport' content='width=device-width, initial-scale=1.0'>",
            "<title>API Documentation</title>",
            "<style>",
            "body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; ",
            "       max-width: 900px; margin: 0 auto; padding: 20px; line-height: 1.6; }",
            "h1, h2, h3 { color: #333; }",
            "pre { background: #f4f4f4; padding: 15px; border-radius: 5px; overflow-x: auto; }",
            "code { background: #f4f4f4; padding: 2px 6px; border-radius: 3px; }",
            ".module { border-left: 4px solid #007acc; padding-left: 15px; margin: 20px 0; }",
            ".class { border-left: 3px solid #28a745; padding-left: 10px; margin: 15px 0; }",
            ".function { border-left: 2px solid #6c757d; padding-left: 10px; margin: 10px 0; }",
            ".docstring { color: #555; font-style: italic; }",
            "</style>",
            "</head>",
            "<body>",
            "<h1>API Documentation</h1>",
        ]

        for module in modules:
            html_parts.append(f"<div class='module'>")
            html_parts.append(f"<h2>{module.name}</h2>")
            html_parts.append(f"<p><code>{module.path}</code></p>")

            if module.description:
                html_parts.append(f"<p class='docstring'>{module.description}</p>")

            for cls in module.classes:
                html_parts.append(f"<div class='class'>")
                html_parts.append(f"<h3>{cls.name}</h3>")
                html_parts.append(f"<pre>{cls.signature}</pre>")
                if cls.docstring:
                    html_parts.append(f"<p class='docstring'>{cls.docstring.split(chr(10))[0]}</p>")

                for method in cls.children:
                    if method.kind == "method" and not method.name.startswith("_"):
                        html_parts.append(f"<div class='function'>")
                        html_parts.append(f"<h4>{method.name}</h4>")
                        html_parts.append(f"<pre>{method.signature}</pre>")
                        if method.docstring:
                            html_parts.append(f"<p class='docstring'>{method.docstring.split(chr(10))[0]}</p>")
                        html_parts.append("</div>")

                html_parts.append("</div>")

            for func in module.functions:
                if not func.name.startswith("_"):
                    html_parts.append(f"<div class='function'>")
                    html_parts.append(f"<h3>{func.name}</h3>")
                    html_parts.append(f"<pre>{func.signature}</pre>")
                    if func.docstring:
                        html_parts.append(f"<p class='docstring'>{func.docstring.split(chr(10))[0]}</p>")
                    html_parts.append("</div>")

            html_parts.append("</div>")

        html_parts.extend(["</body>", "</html>"])
        return "\n".join(html_parts)


class DocGenTool(BaseTool):
    """Tool for generating documentation."""

    name = "docgen"
    description = """Generate documentation from source code.

Operations:
- analyze: Analyze files and extract documentation info
- generate: Generate markdown or HTML documentation
- api: Generate API reference for a module/package
- readme: Generate README template

Supports: Python, C++, C#
"""
    parameters = {
        "operation": "Operation to perform",
        "path": "File or directory path",
        "output": "Output file path (optional)",
        "format": "Output format: markdown, html (default: markdown)",
        "recursive": "Scan directories recursively (default: true)",
    }

    def __init__(self):
        self.generator = DocGenerator()

    def execute(
        self,
        operation: str,
        path: str = ".",
        output: str = "",
        format: str = "markdown",
        recursive: bool = True,
        **kwargs: Any
    ) -> ToolResult:
        """Execute documentation operation."""
        try:
            target = Path(path)

            if operation == "analyze":
                return self._analyze(target, recursive)
            elif operation == "generate":
                return self._generate(target, output, format, recursive)
            elif operation == "api":
                return self._generate_api(target, output, format, recursive)
            elif operation == "readme":
                return self._generate_readme(target, output)
            else:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Unknown operation: {operation}"
                )
        except Exception as e:
            logger.exception(f"DocGen error: {e}")
            return ToolResult(success=False, output="", error=str(e))

    def _get_files(self, path: Path, recursive: bool) -> list[Path]:
        """Get all source files from path."""
        if path.is_file():
            return [path]

        extensions = {".py", ".cpp", ".c", ".h", ".hpp", ".cs"}
        if recursive:
            files = [f for f in path.rglob("*") if f.suffix in extensions]
        else:
            files = [f for f in path.glob("*") if f.suffix in extensions]

        # Exclude common non-source directories
        exclude = {"__pycache__", ".git", "node_modules", "venv", ".venv", "build", "dist"}
        return [f for f in files if not any(e in f.parts for e in exclude)]

    def _analyze_file(self, file_path: Path) -> ModuleDoc | None:
        """Analyze a single file based on extension."""
        if file_path.suffix == ".py":
            return self.generator.analyze_python_file(file_path)
        elif file_path.suffix in (".cpp", ".c", ".h", ".hpp"):
            return self.generator.analyze_cpp_file(file_path)
        elif file_path.suffix == ".cs":
            return self.generator.analyze_csharp_file(file_path)
        return None

    def _analyze(self, path: Path, recursive: bool) -> ToolResult:
        """Analyze files and return summary."""
        files = self._get_files(path, recursive)
        if not files:
            return ToolResult(
                success=False,
                output="",
                error=f"No source files found in {path}"
            )

        modules = []
        for file_path in files:
            module_doc = self._analyze_file(file_path)
            if module_doc:
                modules.append(module_doc)

        # Build summary
        total_classes = sum(len(m.classes) for m in modules)
        total_functions = sum(len(m.functions) for m in modules)

        lines = [
            "Documentation Analysis",
            "=" * 40,
            f"Files analyzed: {len(files)}",
            f"Modules documented: {len(modules)}",
            f"Classes: {total_classes}",
            f"Functions: {total_functions}",
            "",
            "Modules:",
        ]

        for mod in modules[:20]:  # Limit output
            lines.append(f"  {mod.name}")
            lines.append(f"    Classes: {len(mod.classes)}, Functions: {len(mod.functions)}")

        if len(modules) > 20:
            lines.append(f"  ... and {len(modules) - 20} more")

        return ToolResult(success=True, output="\n".join(lines))

    def _generate(
        self,
        path: Path,
        output: str,
        format: str,
        recursive: bool
    ) -> ToolResult:
        """Generate documentation."""
        files = self._get_files(path, recursive)
        if not files:
            return ToolResult(
                success=False,
                output="",
                error=f"No source files found in {path}"
            )

        modules = []
        for file_path in files:
            module_doc = self._analyze_file(file_path)
            if module_doc:
                modules.append(module_doc)

        if not modules:
            return ToolResult(
                success=False,
                output="",
                error="No documentation extracted"
            )

        # Generate output
        if format == "html":
            content = self.generator.generate_html(modules)
            extension = ".html"
        else:
            content = self.generator.generate_markdown(modules)
            extension = ".md"

        # Write to file or return
        if output:
            output_path = Path(output)
            if not output_path.suffix:
                output_path = output_path.with_suffix(extension)
            output_path.write_text(content, encoding="utf-8")
            return ToolResult(
                success=True,
                output=f"Documentation generated: {output_path}\n({len(modules)} modules documented)"
            )
        else:
            return ToolResult(success=True, output=content)

    def _generate_api(
        self,
        path: Path,
        output: str,
        format: str,
        recursive: bool
    ) -> ToolResult:
        """Generate API reference documentation."""
        # Same as generate but with API-specific formatting
        return self._generate(path, output, format, recursive)

    def _generate_readme(self, path: Path, output: str) -> ToolResult:
        """Generate README template."""
        project_name = path.name if path.is_dir() else path.parent.name

        # Try to detect project type
        project_type = "Project"
        if (path / "pyproject.toml").exists() or (path / "setup.py").exists():
            project_type = "Python"
        elif (path / "package.json").exists():
            project_type = "Node.js"
        elif list(path.glob("*.csproj")) or list(path.glob("*.sln")):
            project_type = ".NET"
        elif (path / "CMakeLists.txt").exists():
            project_type = "C++"

        readme = f"""# {project_name}

{project_type} project.

## Description

Add project description here.

## Installation

```bash
# Add installation instructions
```

## Usage

```python
# Add usage examples
```

## Features

- Feature 1
- Feature 2
- Feature 3

## Development

### Prerequisites

- Requirement 1
- Requirement 2

### Setup

```bash
# Setup instructions
```

### Testing

```bash
# Test commands
```

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

Add license information here.

## Acknowledgments

- Acknowledgment 1
- Acknowledgment 2
"""

        if output:
            output_path = Path(output)
            output_path.write_text(readme, encoding="utf-8")
            return ToolResult(
                success=True,
                output=f"README generated: {output_path}"
            )

        return ToolResult(success=True, output=readme)
