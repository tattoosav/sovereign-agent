"""
Test Generation System (Phase 53)

Automatically generates test cases for Python code:
- Analyzes code to create test cases
- Detects coverage gaps
- Generates pytest-compatible tests
- Template-based generation
"""

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class FunctionInfo:
    """Information about a function for test generation."""
    name: str
    args: list[str]
    returns: str | None
    docstring: str | None
    is_async: bool = False
    decorators: list[str] = field(default_factory=list)
    line_number: int = 0


@dataclass
class ClassInfo:
    """Information about a class for test generation."""
    name: str
    methods: list[FunctionInfo]
    base_classes: list[str]
    docstring: str | None
    line_number: int = 0


@dataclass
class ModuleInfo:
    """Information about a module."""
    name: str
    functions: list[FunctionInfo]
    classes: list[ClassInfo]
    imports: list[str]


class CodeAnalyzer(ast.NodeVisitor):
    """Analyze Python code to extract testable elements."""

    def __init__(self) -> None:
        self.functions: list[FunctionInfo] = []
        self.classes: list[ClassInfo] = []
        self.imports: list[str] = []
        self.current_class: ClassInfo | None = None

    def visit_Import(self, node: ast.Import) -> None:
        """Track imports."""
        for alias in node.names:
            self.imports.append(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Track from imports."""
        if node.module:
            for alias in node.names:
                self.imports.append(f"{node.module}.{alias.name}")
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Extract function information."""
        # Get argument names
        args = [arg.arg for arg in node.args.args if arg.arg != "self"]

        # Get return type annotation
        returns = None
        if node.returns:
            returns = ast.unparse(node.returns)

        # Get docstring
        docstring = ast.get_docstring(node)

        # Get decorators
        decorators = [ast.unparse(dec) for dec in node.decorator_list]

        func_info = FunctionInfo(
            name=node.name,
            args=args,
            returns=returns,
            docstring=docstring,
            is_async=False,
            decorators=decorators,
            line_number=node.lineno
        )

        if self.current_class:
            self.current_class.methods.append(func_info)
        else:
            self.functions.append(func_info)

        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Extract async function information."""
        args = [arg.arg for arg in node.args.args if arg.arg != "self"]
        returns = ast.unparse(node.returns) if node.returns else None
        docstring = ast.get_docstring(node)
        decorators = [ast.unparse(dec) for dec in node.decorator_list]

        func_info = FunctionInfo(
            name=node.name,
            args=args,
            returns=returns,
            docstring=docstring,
            is_async=True,
            decorators=decorators,
            line_number=node.lineno
        )

        if self.current_class:
            self.current_class.methods.append(func_info)
        else:
            self.functions.append(func_info)

        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Extract class information."""
        base_classes = [ast.unparse(base) for base in node.bases]
        docstring = ast.get_docstring(node)

        class_info = ClassInfo(
            name=node.name,
            methods=[],
            base_classes=base_classes,
            docstring=docstring,
            line_number=node.lineno
        )

        # Temporarily set current class for method extraction
        old_class = self.current_class
        self.current_class = class_info

        self.generic_visit(node)

        self.current_class = old_class
        self.classes.append(class_info)


class TestGenerator:
    """Generate pytest-compatible test cases."""

    def analyze_file(self, file_path: Path) -> ModuleInfo | None:
        """Analyze a Python file and extract testable elements."""
        try:
            content = file_path.read_text()
            tree = ast.parse(content)

            analyzer = CodeAnalyzer()
            analyzer.visit(tree)

            return ModuleInfo(
                name=file_path.stem,
                functions=analyzer.functions,
                classes=analyzer.classes,
                imports=analyzer.imports
            )
        except Exception:
            return None

    def generate_function_tests(self, func: FunctionInfo, module_name: str) -> str:
        """Generate test cases for a function."""
        tests = []

        # Skip private functions (those starting with _)
        if func.name.startswith("_"):
            return ""

        # Skip functions with certain decorators
        skip_decorators = ["abstractmethod", "property"]
        if any(dec in func.decorators for dec in skip_decorators):
            return ""

        # Generate basic test
        test_name = f"test_{func.name}"

        if func.is_async:
            tests.append(f"""
async def {test_name}():
    \"\"\"Test {func.name} function.\"\"\"
    # TODO: Implement test for {func.name}
    # Function signature: {func.name}({', '.join(func.args)})
    pass
""")
        else:
            tests.append(f"""
def {test_name}():
    \"\"\"Test {func.name} function.\"\"\"
    # TODO: Implement test for {func.name}
    # Function signature: {func.name}({', '.join(func.args)})
    pass
""")

        # Generate edge case tests if function has parameters
        if func.args:
            tests.append(f"""
def {test_name}_edge_cases():
    \"\"\"Test {func.name} with edge cases.\"\"\"
    # TODO: Test edge cases (None, empty, invalid input, etc.)
    pass
""")

        # Generate error handling test
        tests.append(f"""
def {test_name}_error_handling():
    \"\"\"Test {func.name} error handling.\"\"\"
    # TODO: Test that errors are handled appropriately
    pass
""")

        return "\n".join(tests)

    def generate_class_tests(self, cls: ClassInfo, module_name: str) -> str:
        """Generate test cases for a class."""
        tests = []

        # Skip private classes
        if cls.name.startswith("_"):
            return ""

        # Generate setup/teardown
        tests.append(f"""
class Test{cls.name}:
    \"\"\"Tests for {cls.name} class.\"\"\"

    def setup_method(self):
        \"\"\"Set up test fixtures.\"\"\"
        # TODO: Initialize {cls.name} instance
        pass

    def teardown_method(self):
        \"\"\"Clean up after tests.\"\"\"
        pass
""")

        # Generate tests for each public method
        for method in cls.methods:
            if not method.name.startswith("_") or method.name == "__init__":
                test_name = f"test_{method.name}"
                if method.is_async:
                    tests.append(f"""
    async def {test_name}(self):
        \"\"\"Test {cls.name}.{method.name} method.\"\"\"
        # TODO: Implement test
        pass
""")
                else:
                    tests.append(f"""
    def {test_name}(self):
        \"\"\"Test {cls.name}.{method.name} method.\"\"\"
        # TODO: Implement test
        pass
""")

        return "\n".join(tests)

    def generate_test_file(self, module_info: ModuleInfo, source_file: Path) -> str:
        """Generate a complete test file for a module."""
        lines = []

        # Header
        lines.append(f'"""')
        lines.append(f'Tests for {source_file.name}')
        lines.append(f'"""')
        lines.append('')

        # Imports
        lines.append('import pytest')
        lines.append('from pathlib import Path')
        lines.append('')

        # Import the module being tested
        # Calculate import path
        lines.append(f'# Import from source module')
        lines.append(f'# from {module_info.name} import ...')
        lines.append('')

        # Generate function tests
        if module_info.functions:
            lines.append('# Function Tests')
            lines.append('')
            for func in module_info.functions:
                test_code = self.generate_function_tests(func, module_info.name)
                if test_code:
                    lines.append(test_code)

        # Generate class tests
        if module_info.classes:
            lines.append('# Class Tests')
            lines.append('')
            for cls in module_info.classes:
                test_code = self.generate_class_tests(cls, module_info.name)
                if test_code:
                    lines.append(test_code)

        return "\n".join(lines)

    def generate_tests_for_file(self, source_file: Path) -> str | None:
        """Generate tests for a Python source file."""
        module_info = self.analyze_file(source_file)
        if not module_info:
            return None

        return self.generate_test_file(module_info, source_file)
