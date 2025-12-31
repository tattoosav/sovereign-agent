"""
Code Intelligence System.

Provides intelligent code completion, suggestions, and analysis
based on context, patterns, and learned behaviors.
"""

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class SuggestionType(Enum):
    """Types of code suggestions."""
    COMPLETION = "completion"       # Complete current line/statement
    IMPORT = "import"               # Suggest imports
    METHOD = "method"               # Suggest method to call
    PATTERN = "pattern"             # Suggest design pattern
    REFACTOR = "refactor"           # Suggest refactoring
    FIX = "fix"                     # Suggest bug fix
    OPTIMIZATION = "optimization"   # Suggest optimization
    DOCUMENTATION = "documentation" # Suggest documentation


@dataclass
class CodeSuggestion:
    """A code suggestion."""
    type: SuggestionType
    content: str
    description: str
    confidence: float  # 0.0 to 1.0
    location: str = ""  # file:line
    context: str = ""   # surrounding code
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CodeContext:
    """Context for code intelligence."""
    file_path: str
    file_content: str
    cursor_line: int
    cursor_column: int
    language: str
    imports: list[str] = field(default_factory=list)
    classes: list[str] = field(default_factory=list)
    functions: list[str] = field(default_factory=list)
    variables: list[str] = field(default_factory=list)


class CodeIntelligence:
    """
    Intelligent code analysis and suggestion system.

    Features:
    - Context-aware completions
    - Import suggestions
    - Pattern recognition
    - Code smell detection
    - Optimization suggestions
    """

    # Common patterns by language
    PATTERNS = {
        "python": {
            "singleton": '''class {name}:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance''',

            "factory": '''class {name}Factory:
    @staticmethod
    def create(type_name: str) -> {name}:
        types = {{
            "default": Default{name},
        }}
        return types.get(type_name, Default{name})()''',

            "observer": '''from typing import Callable, List

class Observable:
    def __init__(self):
        self._observers: List[Callable] = []

    def subscribe(self, observer: Callable) -> None:
        self._observers.append(observer)

    def notify(self, *args, **kwargs) -> None:
        for observer in self._observers:
            observer(*args, **kwargs)''',

            "context_manager": '''class {name}:
    def __enter__(self):
        # Setup
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Cleanup
        return False''',

            "dataclass": '''from dataclasses import dataclass

@dataclass
class {name}:
    field1: str
    field2: int = 0''',
        },

        "cpp": {
            "singleton": '''class {name} {{
public:
    static {name}& instance() {{
        static {name} instance;
        return instance;
    }}
    {name}(const {name}&) = delete;
    {name}& operator=(const {name}&) = delete;
private:
    {name}() = default;
}};''',

            "raii": '''class {name} {{
public:
    explicit {name}(Resource* res) : resource_(res) {{}}
    ~{name}() {{ delete resource_; }}

    {name}(const {name}&) = delete;
    {name}& operator=(const {name}&) = delete;

    {name}({name}&& other) noexcept : resource_(other.resource_) {{
        other.resource_ = nullptr;
    }}
private:
    Resource* resource_;
}};''',

            "pimpl": '''// Header
class {name} {{
public:
    {name}();
    ~{name}();
    void doSomething();
private:
    struct Impl;
    std::unique_ptr<Impl> pImpl_;
}};

// Source
struct {name}::Impl {{
    // Implementation details
}};

{name}::{name}() : pImpl_(std::make_unique<Impl>()) {{}}
{name}::~{name}() = default;''',

            "smart_ptr": '''// Prefer these over raw pointers
auto unique = std::make_unique<{name}>();
auto shared = std::make_shared<{name}>();
std::weak_ptr<{name}> weak = shared;''',
        },

        "csharp": {
            "singleton": '''public sealed class {name}
{{
    private static readonly Lazy<{name}> _instance =
        new Lazy<{name}>(() => new {name}());

    public static {name} Instance => _instance.Value;

    private {name}() {{ }}
}}''',

            "repository": '''public interface I{name}Repository
{{
    Task<{name}?> GetByIdAsync(int id);
    Task<IEnumerable<{name}>> GetAllAsync();
    Task AddAsync({name} entity);
    Task UpdateAsync({name} entity);
    Task DeleteAsync(int id);
}}''',

            "dependency_injection": '''// Registration
services.AddScoped<I{name}Service, {name}Service>();
services.AddTransient<I{name}Factory, {name}Factory>();
services.AddSingleton<I{name}Cache, {name}Cache>();

// Usage
public class MyController
{{
    private readonly I{name}Service _service;

    public MyController(I{name}Service service)
    {{
        _service = service;
    }}
}}''',

            "async_pattern": '''public async Task<{name}> ProcessAsync(CancellationToken cancellationToken = default)
{{
    try
    {{
        var result = await _service.GetDataAsync(cancellationToken);
        return result;
    }}
    catch (OperationCanceledException)
    {{
        // Handle cancellation
        throw;
    }}
}}''',

            "options_pattern": '''public class {name}Options
{{
    public const string SectionName = "{name}";
    public string Setting1 {{ get; set; }} = "";
    public int Setting2 {{ get; set; }}
}}

// In Startup/Program
services.Configure<{name}Options>(config.GetSection({name}Options.SectionName));

// Usage
public class MyService
{{
    private readonly {name}Options _options;
    public MyService(IOptions<{name}Options> options)
    {{
        _options = options.Value;
    }}
}}''',
        },
    }

    # Common imports by language
    COMMON_IMPORTS = {
        "python": {
            "json": "import json",
            "path": "from pathlib import Path",
            "typing": "from typing import Any, Dict, List, Optional",
            "dataclass": "from dataclasses import dataclass, field",
            "async": "import asyncio",
            "logging": "import logging\nlogger = logging.getLogger(__name__)",
            "datetime": "from datetime import datetime, timedelta",
            "enum": "from enum import Enum, auto",
            "abc": "from abc import ABC, abstractmethod",
            "re": "import re",
        },
        "cpp": {
            "iostream": "#include <iostream>",
            "string": "#include <string>",
            "vector": "#include <vector>",
            "map": "#include <map>",
            "memory": "#include <memory>",
            "algorithm": "#include <algorithm>",
            "optional": "#include <optional>",
            "variant": "#include <variant>",
            "filesystem": "#include <filesystem>",
            "thread": "#include <thread>",
            "mutex": "#include <mutex>",
            "format": "#include <format>",  # C++20
        },
        "csharp": {
            "linq": "using System.Linq;",
            "collections": "using System.Collections.Generic;",
            "async": "using System.Threading.Tasks;",
            "json": "using System.Text.Json;",
            "http": "using System.Net.Http;",
            "di": "using Microsoft.Extensions.DependencyInjection;",
            "logging": "using Microsoft.Extensions.Logging;",
            "ef": "using Microsoft.EntityFrameworkCore;",
        },
    }

    # Code smells to detect
    CODE_SMELLS = {
        "python": [
            (r"except:\s*$", "Bare except clause - specify exception type"),
            (r"except Exception:", "Catching generic Exception - be more specific"),
            (r"global\s+\w+", "Global variable usage - consider alternatives"),
            (r"eval\(", "eval() usage - potential security risk"),
            (r"exec\(", "exec() usage - potential security risk"),
            (r"import \*", "Wildcard import - import specific names"),
            (r"^\s*print\(", "print() in code - use logging instead"),
            (r"time\.sleep\(", "Blocking sleep - consider async alternatives"),
        ],
        "cpp": [
            (r"\bnew\b(?!.*\bdelete\b)", "Raw new without delete - use smart pointers"),
            (r"malloc\(", "malloc usage - prefer new or containers"),
            (r"#define\s+\w+\s+\d+", "Macro constant - use constexpr"),
            (r"using namespace std;", "using namespace std - can cause conflicts"),
            (r"\bNULL\b", "NULL usage - use nullptr"),
            (r"const_cast", "const_cast usage - reconsider design"),
            (r"reinterpret_cast", "reinterpret_cast - ensure this is necessary"),
        ],
        "csharp": [
            (r"catch\s*\(Exception\s+\w+\)\s*\{[\s\S]*?throw;?\s*\}", "Empty catch block - handle or log exception"),
            (r"\.Result\b", ".Result on Task - use await instead"),
            (r"\.Wait\(\)", ".Wait() on Task - use await instead"),
            (r"new\s+Thread\(", "Manual Thread creation - use Task/async"),
            (r"lock\s*\(this\)", "lock(this) - use private object"),
            (r"public\s+\w+\s+\w+\s*;", "Public field - use property instead"),
        ],
    }

    def __init__(self):
        self._learned_patterns: dict[str, list[str]] = {}
        self._usage_stats: dict[str, int] = {}

    def detect_language(self, file_path: str) -> str:
        """Detect programming language from file extension."""
        ext = Path(file_path).suffix.lower()
        language_map = {
            ".py": "python",
            ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp",
            ".c": "cpp", ".h": "cpp", ".hpp": "cpp",
            ".cs": "csharp",
            ".js": "javascript", ".ts": "typescript",
            ".java": "java",
            ".go": "go",
            ".rs": "rust",
        }
        return language_map.get(ext, "unknown")

    def analyze_context(self, file_path: str, content: str, cursor_line: int) -> CodeContext:
        """Analyze code context at cursor position."""
        language = self.detect_language(file_path)
        lines = content.split('\n')

        # Extract imports
        imports = []
        if language == "python":
            imports = re.findall(r'^(?:from\s+\S+\s+)?import\s+.+$', content, re.MULTILINE)
        elif language == "cpp":
            imports = re.findall(r'^#include\s+[<"].+[>"]', content, re.MULTILINE)
        elif language == "csharp":
            imports = re.findall(r'^using\s+.+;', content, re.MULTILINE)

        # Extract classes
        classes = []
        if language == "python":
            classes = re.findall(r'^class\s+(\w+)', content, re.MULTILINE)
        elif language in ("cpp", "csharp"):
            classes = re.findall(r'\bclass\s+(\w+)', content)

        # Extract functions
        functions = []
        if language == "python":
            functions = re.findall(r'^(?:async\s+)?def\s+(\w+)', content, re.MULTILINE)
        elif language == "cpp":
            functions = re.findall(r'\b(\w+)\s*\([^)]*\)\s*(?:const)?\s*\{', content)
        elif language == "csharp":
            functions = re.findall(r'(?:public|private|protected|internal)?\s*(?:static\s+)?(?:async\s+)?\w+\s+(\w+)\s*\(', content)

        return CodeContext(
            file_path=file_path,
            file_content=content,
            cursor_line=cursor_line,
            cursor_column=0,
            language=language,
            imports=imports,
            classes=classes,
            functions=functions,
        )

    def get_completions(self, context: CodeContext) -> list[CodeSuggestion]:
        """Get code completions based on context."""
        suggestions = []
        lines = context.file_content.split('\n')

        if context.cursor_line <= 0 or context.cursor_line > len(lines):
            return suggestions

        current_line = lines[context.cursor_line - 1]

        # Check for import suggestions
        import_suggestions = self._get_import_suggestions(context, current_line)
        suggestions.extend(import_suggestions)

        # Check for pattern suggestions
        pattern_suggestions = self._get_pattern_suggestions(context, current_line)
        suggestions.extend(pattern_suggestions)

        # Check for method suggestions
        method_suggestions = self._get_method_suggestions(context, current_line)
        suggestions.extend(method_suggestions)

        return sorted(suggestions, key=lambda s: s.confidence, reverse=True)

    def _get_import_suggestions(self, context: CodeContext, current_line: str) -> list[CodeSuggestion]:
        """Suggest missing imports based on code usage."""
        suggestions = []
        lang_imports = self.COMMON_IMPORTS.get(context.language, {})

        # Check what might be missing
        content = context.file_content

        for keyword, import_stmt in lang_imports.items():
            # Check if keyword is used but not imported
            if keyword.lower() in content.lower():
                already_imported = any(keyword.lower() in imp.lower() for imp in context.imports)
                if not already_imported:
                    suggestions.append(CodeSuggestion(
                        type=SuggestionType.IMPORT,
                        content=import_stmt,
                        description=f"Add import for {keyword}",
                        confidence=0.7,
                        location=f"{context.file_path}:1",
                    ))

        return suggestions

    def _get_pattern_suggestions(self, context: CodeContext, current_line: str) -> list[CodeSuggestion]:
        """Suggest design patterns based on context."""
        suggestions = []
        lang_patterns = self.PATTERNS.get(context.language, {})

        # Check for pattern keywords in current line or nearby
        pattern_keywords = {
            "singleton": ["singleton", "instance", "only one"],
            "factory": ["factory", "create", "builder"],
            "observer": ["observer", "subscribe", "notify", "event"],
            "repository": ["repository", "crud", "database"],
        }

        line_lower = current_line.lower()
        for pattern_name, keywords in pattern_keywords.items():
            if any(kw in line_lower for kw in keywords):
                if pattern_name in lang_patterns:
                    suggestions.append(CodeSuggestion(
                        type=SuggestionType.PATTERN,
                        content=lang_patterns[pattern_name],
                        description=f"Implement {pattern_name} pattern",
                        confidence=0.6,
                        location=f"{context.file_path}:{context.cursor_line}",
                    ))

        return suggestions

    def _get_method_suggestions(self, context: CodeContext, current_line: str) -> list[CodeSuggestion]:
        """Suggest methods based on object type and context."""
        suggestions = []

        # This would ideally use type inference
        # For now, suggest based on common patterns
        if context.language == "python":
            if "list" in current_line.lower() or current_line.strip().endswith("["):
                suggestions.append(CodeSuggestion(
                    type=SuggestionType.METHOD,
                    content=".append(item)",
                    description="Add item to list",
                    confidence=0.5,
                ))
            if "dict" in current_line.lower() or current_line.strip().endswith("{"):
                suggestions.append(CodeSuggestion(
                    type=SuggestionType.METHOD,
                    content=".get(key, default)",
                    description="Get value with default",
                    confidence=0.5,
                ))

        return suggestions

    def detect_code_smells(self, file_path: str, content: str) -> list[CodeSuggestion]:
        """Detect potential code smells."""
        suggestions = []
        language = self.detect_language(file_path)
        smells = self.CODE_SMELLS.get(language, [])

        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            for pattern, message in smells:
                if re.search(pattern, line):
                    suggestions.append(CodeSuggestion(
                        type=SuggestionType.FIX,
                        content="",
                        description=message,
                        confidence=0.8,
                        location=f"{file_path}:{i}",
                        context=line.strip(),
                    ))

        return suggestions

    def suggest_optimizations(self, file_path: str, content: str) -> list[CodeSuggestion]:
        """Suggest performance optimizations."""
        suggestions = []
        language = self.detect_language(file_path)

        if language == "python":
            # List comprehension opportunities
            for_append = re.finditer(
                r'for\s+\w+\s+in\s+.+:\s*\n\s+\w+\.append\(',
                content
            )
            for match in for_append:
                suggestions.append(CodeSuggestion(
                    type=SuggestionType.OPTIMIZATION,
                    content="Consider using list comprehension",
                    description="List comprehension is often faster than for+append",
                    confidence=0.7,
                    context=match.group(0)[:50],
                ))

            # String concatenation in loop
            str_concat = re.finditer(r'for\s+.+:\s*\n\s+\w+\s*\+=\s*["\']', content)
            for match in str_concat:
                suggestions.append(CodeSuggestion(
                    type=SuggestionType.OPTIMIZATION,
                    content="Use ''.join() instead of += for strings in loop",
                    description="String += in loop creates many intermediate strings",
                    confidence=0.8,
                    context=match.group(0)[:50],
                ))

        elif language == "csharp":
            # StringBuilder for string concatenation
            str_concat = re.finditer(r'for\s*\(.+\)\s*\{[\s\S]*?\+=\s*"', content)
            for match in str_concat:
                suggestions.append(CodeSuggestion(
                    type=SuggestionType.OPTIMIZATION,
                    content="Use StringBuilder instead of += in loop",
                    description="String concatenation in loop is inefficient",
                    confidence=0.8,
                ))

        return suggestions

    def get_pattern(self, language: str, pattern_name: str, **kwargs: Any) -> str | None:
        """Get a code pattern template."""
        lang_patterns = self.PATTERNS.get(language, {})
        pattern = lang_patterns.get(pattern_name)
        if pattern and kwargs:
            return pattern.format(**kwargs)
        return pattern

    def learn_pattern(self, language: str, pattern: str) -> None:
        """Learn a new pattern from user code."""
        if language not in self._learned_patterns:
            self._learned_patterns[language] = []
        self._learned_patterns[language].append(pattern)
        logger.info(f"Learned new pattern for {language}")

    def get_stats(self) -> dict[str, Any]:
        """Get intelligence statistics."""
        return {
            "languages_supported": list(self.PATTERNS.keys()),
            "patterns_per_language": {lang: len(patterns) for lang, patterns in self.PATTERNS.items()},
            "learned_patterns": {lang: len(patterns) for lang, patterns in self._learned_patterns.items()},
            "usage_stats": self._usage_stats,
        }
