"""
Code Pattern Learning System.

Learns common patterns, idioms, and conventions from the codebase
to provide more contextual and project-specific suggestions.
"""

import ast
import hashlib
import json
import logging
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CodePattern:
    """A learned code pattern."""
    name: str
    category: str  # naming, structure, error_handling, imports, etc.
    language: str
    pattern: str  # The actual pattern or template
    occurrences: int = 1
    examples: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)
    confidence: float = 0.0  # 0-1 based on frequency and consistency
    last_seen: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "category": self.category,
            "language": self.language,
            "pattern": self.pattern,
            "occurrences": self.occurrences,
            "examples": self.examples[:5],  # Limit stored examples
            "files": self.files[:10],
            "confidence": self.confidence,
            "last_seen": self.last_seen,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CodePattern":
        return cls(**data)


@dataclass
class ProjectStyle:
    """Learned project coding style."""
    naming_conventions: dict[str, str] = field(default_factory=dict)
    import_style: str = ""  # absolute, relative, mixed
    docstring_style: str = ""  # google, numpy, sphinx, none
    type_hints: bool = False
    line_length: int = 88
    indentation: str = "spaces"
    indent_size: int = 4
    quotes: str = "double"  # single, double
    trailing_commas: bool = False
    common_imports: list[str] = field(default_factory=list)
    error_handling_style: str = ""
    test_framework: str = ""


class PatternLearner:
    """Learns patterns from codebase analysis."""

    def __init__(self, storage_path: Path | str = ".sovereign/patterns"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.patterns: dict[str, CodePattern] = {}
        self.project_style = ProjectStyle()
        self._load_patterns()

    def _load_patterns(self):
        """Load saved patterns from storage."""
        patterns_file = self.storage_path / "patterns.json"
        if patterns_file.exists():
            try:
                data = json.loads(patterns_file.read_text())
                for key, pattern_data in data.get("patterns", {}).items():
                    self.patterns[key] = CodePattern.from_dict(pattern_data)
                style_data = data.get("style", {})
                if style_data:
                    self.project_style = ProjectStyle(**style_data)
                logger.info(f"Loaded {len(self.patterns)} patterns")
            except Exception as e:
                logger.warning(f"Failed to load patterns: {e}")

    def _save_patterns(self):
        """Save patterns to storage."""
        patterns_file = self.storage_path / "patterns.json"
        try:
            data = {
                "patterns": {k: v.to_dict() for k, v in self.patterns.items()},
                "style": {
                    "naming_conventions": self.project_style.naming_conventions,
                    "import_style": self.project_style.import_style,
                    "docstring_style": self.project_style.docstring_style,
                    "type_hints": self.project_style.type_hints,
                    "line_length": self.project_style.line_length,
                    "indentation": self.project_style.indentation,
                    "indent_size": self.project_style.indent_size,
                    "quotes": self.project_style.quotes,
                    "trailing_commas": self.project_style.trailing_commas,
                    "common_imports": self.project_style.common_imports,
                    "error_handling_style": self.project_style.error_handling_style,
                    "test_framework": self.project_style.test_framework,
                },
                "updated": datetime.now().isoformat(),
            }
            patterns_file.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.error(f"Failed to save patterns: {e}")

    def learn_from_directory(self, directory: Path, recursive: bool = True) -> dict[str, int]:
        """Learn patterns from all files in a directory."""
        stats = {"files_analyzed": 0, "patterns_found": 0, "new_patterns": 0}

        pattern = "**/*" if recursive else "*"
        extensions = {".py", ".cpp", ".c", ".h", ".hpp", ".cs", ".lua", ".js"}

        for file_path in directory.glob(pattern):
            if file_path.is_file() and file_path.suffix in extensions:
                # Skip common non-source directories
                if any(part.startswith(".") or part in {"__pycache__", "node_modules", "venv"}
                       for part in file_path.parts):
                    continue

                try:
                    result = self.learn_from_file(file_path)
                    stats["files_analyzed"] += 1
                    stats["patterns_found"] += result.get("patterns_found", 0)
                    stats["new_patterns"] += result.get("new_patterns", 0)
                except Exception as e:
                    logger.warning(f"Failed to analyze {file_path}: {e}")

        # Update confidence scores
        self._update_confidence_scores()

        # Save learned patterns
        self._save_patterns()

        return stats

    def learn_from_file(self, file_path: Path) -> dict[str, int]:
        """Learn patterns from a single file."""
        stats = {"patterns_found": 0, "new_patterns": 0}

        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception:
            return stats

        language = self._detect_language(file_path)

        if language == "python":
            result = self._learn_python_patterns(content, str(file_path))
        elif language in ("cpp", "c"):
            result = self._learn_cpp_patterns(content, str(file_path))
        elif language == "csharp":
            result = self._learn_csharp_patterns(content, str(file_path))
        elif language == "lua":
            result = self._learn_lua_patterns(content, str(file_path))
        elif language == "javascript":
            result = self._learn_javascript_patterns(content, str(file_path))
        else:
            return stats

        stats["patterns_found"] = result.get("found", 0)
        stats["new_patterns"] = result.get("new", 0)

        return stats

    def _detect_language(self, file_path: Path) -> str:
        """Detect programming language from file extension."""
        ext = file_path.suffix.lower()
        if ext == ".py":
            return "python"
        elif ext in (".cpp", ".cc", ".cxx", ".hpp"):
            return "cpp"
        elif ext in (".c", ".h"):
            return "c"
        elif ext == ".cs":
            return "csharp"
        elif ext == ".lua":
            return "lua"
        elif ext == ".js":
            return "javascript"
        return "unknown"

    def _learn_python_patterns(self, content: str, file_path: str) -> dict[str, int]:
        """Learn patterns from Python code."""
        stats = {"found": 0, "new": 0}

        try:
            tree = ast.parse(content)
        except SyntaxError:
            return stats

        # Learn naming conventions
        self._learn_python_naming(tree, file_path)

        # Learn import patterns
        self._learn_python_imports(tree, file_path)

        # Learn docstring style
        self._learn_python_docstrings(tree, file_path)

        # Learn error handling patterns
        self._learn_python_error_handling(tree, file_path)

        # Learn decorator patterns
        self._learn_python_decorators(tree, file_path)

        # Learn class patterns
        self._learn_python_class_patterns(tree, file_path)

        # Learn style preferences
        self._learn_python_style(content)

        stats["found"] = sum(1 for p in self.patterns.values() if file_path in p.files)

        return stats

    def _learn_python_naming(self, tree: ast.AST, file_path: str):
        """Learn naming conventions from Python AST."""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Function naming
                name = node.name
                if name.startswith("_") and not name.startswith("__"):
                    self._add_pattern("private_prefix", "naming", "python",
                                      "Private methods/functions start with _",
                                      name, file_path)
                elif name.startswith("get_") or name.startswith("set_"):
                    self._add_pattern("getter_setter", "naming", "python",
                                      "Use get_/set_ prefix for accessors",
                                      name, file_path)
                elif name.startswith("is_") or name.startswith("has_"):
                    self._add_pattern("boolean_prefix", "naming", "python",
                                      "Boolean functions use is_/has_ prefix",
                                      name, file_path)

            elif isinstance(node, ast.ClassDef):
                # Class naming
                if node.name[0].isupper():
                    self._add_pattern("pascal_case_classes", "naming", "python",
                                      "Classes use PascalCase",
                                      node.name, file_path)

            elif isinstance(node, ast.Name) and node.id.isupper():
                # Constants
                self._add_pattern("upper_constants", "naming", "python",
                                  "Constants use UPPER_SNAKE_CASE",
                                  node.id, file_path)

    def _learn_python_imports(self, tree: ast.AST, file_path: str):
        """Learn import patterns."""
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module.startswith("."):
                    self._add_pattern("relative_imports", "imports", "python",
                                      "Uses relative imports",
                                      f"from {module} import ...", file_path)
                else:
                    self._add_pattern("absolute_imports", "imports", "python",
                                      "Uses absolute imports",
                                      f"from {module} import ...", file_path)

        # Track common imports
        for imp in imports:
            if imp not in self.project_style.common_imports:
                self.project_style.common_imports.append(imp)

    def _learn_python_docstrings(self, tree: ast.AST, file_path: str):
        """Learn docstring style."""
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.Module)):
                docstring = ast.get_docstring(node)
                if docstring:
                    if "Args:" in docstring or "Returns:" in docstring:
                        self._add_pattern("google_docstrings", "documentation", "python",
                                          "Uses Google-style docstrings",
                                          docstring[:100], file_path)
                        self.project_style.docstring_style = "google"
                    elif "Parameters" in docstring and "-------" in docstring:
                        self._add_pattern("numpy_docstrings", "documentation", "python",
                                          "Uses NumPy-style docstrings",
                                          docstring[:100], file_path)
                        self.project_style.docstring_style = "numpy"
                    elif ":param" in docstring or ":returns:" in docstring:
                        self._add_pattern("sphinx_docstrings", "documentation", "python",
                                          "Uses Sphinx-style docstrings",
                                          docstring[:100], file_path)
                        self.project_style.docstring_style = "sphinx"

    def _learn_python_error_handling(self, tree: ast.AST, file_path: str):
        """Learn error handling patterns."""
        for node in ast.walk(tree):
            if isinstance(node, ast.Try):
                # Check for specific exception handling
                for handler in node.handlers:
                    if handler.type:
                        exc_name = ""
                        if isinstance(handler.type, ast.Name):
                            exc_name = handler.type.id
                        elif isinstance(handler.type, ast.Attribute):
                            exc_name = handler.type.attr

                        if exc_name and exc_name != "Exception":
                            self._add_pattern("specific_exceptions", "error_handling", "python",
                                              f"Catches specific exceptions ({exc_name})",
                                              exc_name, file_path)

                # Check for finally block
                if node.finalbody:
                    self._add_pattern("uses_finally", "error_handling", "python",
                                      "Uses finally for cleanup",
                                      "try...finally", file_path)

            elif isinstance(node, ast.Raise):
                if node.exc and isinstance(node.exc, ast.Call):
                    if isinstance(node.exc.func, ast.Name):
                        exc_name = node.exc.func.id
                        self._add_pattern(f"raises_{exc_name}", "error_handling", "python",
                                          f"Raises {exc_name}",
                                          exc_name, file_path)

    def _learn_python_decorators(self, tree: ast.AST, file_path: str):
        """Learn decorator usage patterns."""
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                for decorator in node.decorator_list:
                    dec_name = ""
                    if isinstance(decorator, ast.Name):
                        dec_name = decorator.id
                    elif isinstance(decorator, ast.Attribute):
                        dec_name = decorator.attr
                    elif isinstance(decorator, ast.Call):
                        if isinstance(decorator.func, ast.Name):
                            dec_name = decorator.func.id
                        elif isinstance(decorator.func, ast.Attribute):
                            dec_name = decorator.func.attr

                    if dec_name:
                        self._add_pattern(f"decorator_{dec_name}", "decorators", "python",
                                          f"Uses @{dec_name} decorator",
                                          f"@{dec_name}", file_path)

    def _learn_python_class_patterns(self, tree: ast.AST, file_path: str):
        """Learn class patterns."""
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Check for dataclass
                for decorator in node.decorator_list:
                    if isinstance(decorator, ast.Name) and decorator.id == "dataclass":
                        self._add_pattern("uses_dataclass", "structure", "python",
                                          "Uses @dataclass for data classes",
                                          node.name, file_path)
                    elif isinstance(decorator, ast.Call):
                        if isinstance(decorator.func, ast.Name) and decorator.func.id == "dataclass":
                            self._add_pattern("uses_dataclass", "structure", "python",
                                              "Uses @dataclass for data classes",
                                              node.name, file_path)

                # Check inheritance
                if node.bases:
                    for base in node.bases:
                        if isinstance(base, ast.Name):
                            if base.id in ("ABC", "Protocol"):
                                self._add_pattern("abstract_base", "structure", "python",
                                                  "Uses abstract base classes",
                                                  node.name, file_path)
                            elif base.id == "Enum":
                                self._add_pattern("uses_enum", "structure", "python",
                                                  "Uses Enum for constants",
                                                  node.name, file_path)

    def _learn_python_style(self, content: str):
        """Learn style preferences from code."""
        lines = content.split("\n")

        # Check indentation
        for line in lines:
            if line.startswith("    ") and not line.startswith("\t"):
                self.project_style.indentation = "spaces"
                self.project_style.indent_size = 4
                break
            elif line.startswith("  ") and not line.startswith("    "):
                self.project_style.indentation = "spaces"
                self.project_style.indent_size = 2
                break
            elif line.startswith("\t"):
                self.project_style.indentation = "tabs"
                break

        # Check quotes
        single_quotes = content.count("'")
        double_quotes = content.count('"')
        self.project_style.quotes = "single" if single_quotes > double_quotes else "double"

        # Check for type hints
        if "def " in content and "->" in content:
            self.project_style.type_hints = True

        # Check line length
        max_line = max((len(line) for line in lines), default=0)
        if max_line <= 79:
            self.project_style.line_length = 79
        elif max_line <= 88:
            self.project_style.line_length = 88
        elif max_line <= 100:
            self.project_style.line_length = 100
        else:
            self.project_style.line_length = 120

        # Check trailing commas
        if re.search(r",\s*\n\s*[\)\]\}]", content):
            self.project_style.trailing_commas = True

        # Detect test framework
        if "import pytest" in content or "from pytest" in content:
            self.project_style.test_framework = "pytest"
        elif "import unittest" in content:
            self.project_style.test_framework = "unittest"

    def _learn_cpp_patterns(self, content: str, file_path: str) -> dict[str, int]:
        """Learn patterns from C++ code."""
        stats = {"found": 0, "new": 0}

        # Naming conventions
        if re.search(r"class\s+[A-Z][a-zA-Z]*", content):
            self._add_pattern("pascal_case_classes", "naming", "cpp",
                              "Classes use PascalCase", "", file_path)

        if re.search(r"m_\w+", content):
            self._add_pattern("m_prefix_members", "naming", "cpp",
                              "Member variables use m_ prefix", "", file_path)

        # Smart pointers
        if "unique_ptr" in content:
            self._add_pattern("uses_unique_ptr", "memory", "cpp",
                              "Uses std::unique_ptr for ownership", "", file_path)
        if "shared_ptr" in content:
            self._add_pattern("uses_shared_ptr", "memory", "cpp",
                              "Uses std::shared_ptr for shared ownership", "", file_path)

        # Modern C++ features
        if "auto " in content:
            self._add_pattern("uses_auto", "style", "cpp",
                              "Uses auto type deduction", "", file_path)
        if "constexpr" in content:
            self._add_pattern("uses_constexpr", "style", "cpp",
                              "Uses constexpr for compile-time constants", "", file_path)
        if "[[nodiscard]]" in content:
            self._add_pattern("uses_nodiscard", "style", "cpp",
                              "Uses [[nodiscard]] attribute", "", file_path)

        # Error handling
        if "try {" in content or "try{" in content:
            self._add_pattern("exception_handling", "error_handling", "cpp",
                              "Uses exception handling", "", file_path)

        return stats

    def _learn_csharp_patterns(self, content: str, file_path: str) -> dict[str, int]:
        """Learn patterns from C# code."""
        stats = {"found": 0, "new": 0}

        # Naming
        if re.search(r"private\s+\w+\s+_\w+", content):
            self._add_pattern("underscore_private", "naming", "csharp",
                              "Private fields use _ prefix", "", file_path)

        # Async patterns
        if "async Task" in content:
            self._add_pattern("async_await", "async", "csharp",
                              "Uses async/await pattern", "", file_path)

        # Nullable
        if "?" in content and "string?" in content:
            self._add_pattern("nullable_types", "types", "csharp",
                              "Uses nullable reference types", "", file_path)

        # Records
        if "record " in content:
            self._add_pattern("uses_records", "structure", "csharp",
                              "Uses record types for immutable data", "", file_path)

        # LINQ
        if ".Where(" in content or ".Select(" in content:
            self._add_pattern("uses_linq", "style", "csharp",
                              "Uses LINQ for queries", "", file_path)

        return stats

    def _learn_lua_patterns(self, content: str, file_path: str) -> dict[str, int]:
        """Learn patterns from Lua code (especially FiveM)."""
        stats = {"found": 0, "new": 0}

        # FiveM/CFX specific patterns
        if "Citizen.CreateThread" in content:
            self._add_pattern("citizen_threads", "fivem", "lua",
                              "Uses Citizen.CreateThread for loops", "", file_path)

        if "Citizen.Wait" in content:
            self._add_pattern("citizen_wait", "fivem", "lua",
                              "Uses Citizen.Wait for delays", "", file_path)

        if "RegisterNetEvent" in content:
            self._add_pattern("net_events", "fivem", "lua",
                              "Uses RegisterNetEvent for networking", "", file_path)

        if "TriggerServerEvent" in content or "TriggerClientEvent" in content:
            self._add_pattern("trigger_events", "fivem", "lua",
                              "Uses Trigger*Event for communication", "", file_path)

        if "AddEventHandler" in content:
            self._add_pattern("event_handlers", "fivem", "lua",
                              "Uses AddEventHandler for events", "", file_path)

        # ESP/Drawing patterns
        if "World3dToScreen2d" in content:
            self._add_pattern("world_to_screen", "esp", "lua",
                              "Uses World3dToScreen2d for ESP", "", file_path)

        if "DrawText" in content or "SetTextFont" in content:
            self._add_pattern("draw_text", "rendering", "lua",
                              "Uses native text drawing", "", file_path)

        if "DrawRect" in content:
            self._add_pattern("draw_rect", "rendering", "lua",
                              "Uses DrawRect for boxes/bars", "", file_path)

        if "GetPedBoneCoords" in content:
            self._add_pattern("bone_coords", "esp", "lua",
                              "Uses GetPedBoneCoords for skeleton ESP", "", file_path)

        if "GetActivePlayers" in content:
            self._add_pattern("player_iteration", "esp", "lua",
                              "Uses GetActivePlayers for player ESP", "", file_path)

        if "GetGamePool" in content:
            self._add_pattern("game_pool", "esp", "lua",
                              "Uses GetGamePool for entity lists", "", file_path)

        # NUI patterns
        if "SendNUIMessage" in content:
            self._add_pattern("nui_messages", "nui", "lua",
                              "Uses SendNUIMessage for UI", "", file_path)

        if "RegisterNUICallback" in content:
            self._add_pattern("nui_callbacks", "nui", "lua",
                              "Uses RegisterNUICallback for UI events", "", file_path)

        if "SetNuiFocus" in content:
            self._add_pattern("nui_focus", "nui", "lua",
                              "Uses SetNuiFocus for input control", "", file_path)

        # Common patterns
        if "local function" in content:
            self._add_pattern("local_functions", "structure", "lua",
                              "Uses local function declarations", "", file_path)

        if "exports[" in content or "exports." in content:
            self._add_pattern("exports", "fivem", "lua",
                              "Uses exports for cross-resource calls", "", file_path)

        # Error handling
        if "pcall" in content:
            self._add_pattern("pcall", "error_handling", "lua",
                              "Uses pcall for protected calls", "", file_path)

        return stats

    def _learn_javascript_patterns(self, content: str, file_path: str) -> dict[str, int]:
        """Learn patterns from JavaScript code (NUI/web)."""
        stats = {"found": 0, "new": 0}

        # FiveM NUI patterns
        if "window.addEventListener('message'" in content:
            self._add_pattern("nui_message_listener", "nui", "javascript",
                              "Listens for NUI messages from Lua", "", file_path)

        if "fetch('https://" in content and "nui-" in file_path.lower():
            self._add_pattern("nui_callbacks", "nui", "javascript",
                              "Uses fetch for NUI callbacks", "", file_path)

        # Modern JS patterns
        if "async " in content or "await " in content:
            self._add_pattern("async_await", "async", "javascript",
                              "Uses async/await pattern", "", file_path)

        if "=>" in content:
            self._add_pattern("arrow_functions", "style", "javascript",
                              "Uses arrow functions", "", file_path)

        if "const " in content:
            self._add_pattern("const_declarations", "style", "javascript",
                              "Uses const for constants", "", file_path)

        if "let " in content:
            self._add_pattern("let_declarations", "style", "javascript",
                              "Uses let for variables", "", file_path)

        # DOM patterns
        if "document.getElementById" in content or "document.querySelector" in content:
            self._add_pattern("dom_queries", "dom", "javascript",
                              "Uses DOM query methods", "", file_path)

        if "classList" in content:
            self._add_pattern("classlist", "dom", "javascript",
                              "Uses classList for styling", "", file_path)

        # Event handling
        if "addEventListener" in content:
            self._add_pattern("event_listeners", "events", "javascript",
                              "Uses addEventListener", "", file_path)

        return stats

    def _add_pattern(
        self,
        name: str,
        category: str,
        language: str,
        pattern: str,
        example: str,
        file_path: str
    ):
        """Add or update a pattern."""
        key = f"{language}:{category}:{name}"

        if key in self.patterns:
            p = self.patterns[key]
            p.occurrences += 1
            if example and example not in p.examples:
                p.examples.append(example)
            if file_path not in p.files:
                p.files.append(file_path)
            p.last_seen = datetime.now().isoformat()
        else:
            self.patterns[key] = CodePattern(
                name=name,
                category=category,
                language=language,
                pattern=pattern,
                occurrences=1,
                examples=[example] if example else [],
                files=[file_path],
                last_seen=datetime.now().isoformat(),
            )

    def _update_confidence_scores(self):
        """Update confidence scores based on frequency."""
        if not self.patterns:
            return

        # Group patterns by category
        by_category = defaultdict(list)
        for pattern in self.patterns.values():
            by_category[f"{pattern.language}:{pattern.category}"].append(pattern)

        # Calculate relative confidence within each category
        for patterns in by_category.values():
            max_occurrences = max(p.occurrences for p in patterns)
            for pattern in patterns:
                # Confidence based on relative frequency and file coverage
                freq_score = pattern.occurrences / max_occurrences
                coverage_score = min(len(pattern.files) / 10, 1.0)  # Cap at 10 files
                pattern.confidence = (freq_score * 0.7) + (coverage_score * 0.3)

    def get_patterns_for_language(self, language: str) -> list[CodePattern]:
        """Get all patterns for a specific language."""
        return [p for p in self.patterns.values() if p.language == language]

    def get_patterns_by_category(self, category: str) -> list[CodePattern]:
        """Get all patterns in a category."""
        return [p for p in self.patterns.values() if p.category == category]

    def get_high_confidence_patterns(self, threshold: float = 0.5) -> list[CodePattern]:
        """Get patterns with high confidence scores."""
        return sorted(
            [p for p in self.patterns.values() if p.confidence >= threshold],
            key=lambda p: p.confidence,
            reverse=True
        )

    def suggest_for_context(
        self,
        language: str,
        context: str,
        categories: list[str] | None = None
    ) -> list[CodePattern]:
        """Suggest patterns based on context."""
        relevant = self.get_patterns_for_language(language)

        if categories:
            relevant = [p for p in relevant if p.category in categories]

        # Sort by confidence
        return sorted(relevant, key=lambda p: p.confidence, reverse=True)[:10]

    def get_style_summary(self) -> str:
        """Get a summary of the learned project style."""
        style = self.project_style
        lines = [
            "Project Style Summary",
            "=" * 40,
            f"Indentation: {style.indent_size} {style.indentation}",
            f"Line length: {style.line_length}",
            f"Quotes: {style.quotes}",
            f"Type hints: {'Yes' if style.type_hints else 'No'}",
            f"Trailing commas: {'Yes' if style.trailing_commas else 'No'}",
            f"Docstring style: {style.docstring_style or 'Not detected'}",
            f"Test framework: {style.test_framework or 'Not detected'}",
        ]

        if style.naming_conventions:
            lines.append("\nNaming Conventions:")
            for key, value in style.naming_conventions.items():
                lines.append(f"  {key}: {value}")

        if style.common_imports:
            lines.append(f"\nCommon imports: {', '.join(style.common_imports[:10])}")

        return "\n".join(lines)

    def get_statistics(self) -> dict[str, Any]:
        """Get learning statistics."""
        by_language = defaultdict(int)
        by_category = defaultdict(int)

        for pattern in self.patterns.values():
            by_language[pattern.language] += 1
            by_category[pattern.category] += 1

        return {
            "total_patterns": len(self.patterns),
            "by_language": dict(by_language),
            "by_category": dict(by_category),
            "high_confidence_count": len(self.get_high_confidence_patterns()),
            "style": self.get_style_summary(),
        }
