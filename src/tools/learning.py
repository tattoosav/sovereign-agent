"""
Code Learning Tool.

Provides agent access to the pattern learning system.
"""

import logging
from pathlib import Path
from typing import Any

from .base import BaseTool, ToolResult
from src.agent.pattern_learner import PatternLearner

logger = logging.getLogger(__name__)


class LearningTool(BaseTool):
    """Tool for learning from and querying code patterns."""

    name = "learn"
    description = """Learn patterns from code and query learned knowledge.

Operations:
- analyze: Learn patterns from a file or directory
- patterns: Show learned patterns (filter by language/category)
- style: Show learned project style
- suggest: Get pattern suggestions for a context
- stats: Show learning statistics
- export: Export learned patterns to a file

This tool helps the agent understand project conventions and coding patterns.
"""
    parameters = {
        "operation": "Operation to perform",
        "path": "File or directory path (for analyze)",
        "language": "Filter by language (python, cpp, csharp)",
        "category": "Filter by category (naming, structure, error_handling, etc.)",
        "context": "Context for suggestions",
        "output": "Output file for export",
    }

    def __init__(self, storage_path: str = ".sovereign/patterns"):
        self.learner = PatternLearner(storage_path)

    def execute(
        self,
        operation: str,
        path: str = ".",
        language: str = "",
        category: str = "",
        context: str = "",
        output: str = "",
        **kwargs: Any
    ) -> ToolResult:
        """Execute learning operation."""
        try:
            if operation == "analyze":
                return self._analyze(Path(path))
            elif operation == "patterns":
                return self._get_patterns(language, category)
            elif operation == "style":
                return self._get_style()
            elif operation == "suggest":
                return self._suggest(language, context, category)
            elif operation == "stats":
                return self._get_stats()
            elif operation == "export":
                return self._export(output)
            else:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Unknown operation: {operation}"
                )
        except Exception as e:
            logger.exception(f"Learning tool error: {e}")
            return ToolResult(success=False, output="", error=str(e))

    def _analyze(self, path: Path) -> ToolResult:
        """Analyze files and learn patterns."""
        if not path.exists():
            return ToolResult(
                success=False,
                output="",
                error=f"Path not found: {path}"
            )

        if path.is_file():
            result = self.learner.learn_from_file(path)
            return ToolResult(
                success=True,
                output=f"Analyzed {path.name}\nPatterns found: {result.get('patterns_found', 0)}"
            )
        else:
            result = self.learner.learn_from_directory(path)
            lines = [
                "Learning Complete",
                "=" * 40,
                f"Files analyzed: {result['files_analyzed']}",
                f"Patterns found: {result['patterns_found']}",
                f"New patterns: {result['new_patterns']}",
                f"Total patterns stored: {len(self.learner.patterns)}",
            ]
            return ToolResult(success=True, output="\n".join(lines))

    def _get_patterns(self, language: str, category: str) -> ToolResult:
        """Get learned patterns with optional filtering."""
        patterns = list(self.learner.patterns.values())

        if language:
            patterns = [p for p in patterns if p.language == language]
        if category:
            patterns = [p for p in patterns if p.category == category]

        # Sort by confidence
        patterns = sorted(patterns, key=lambda p: p.confidence, reverse=True)

        if not patterns:
            return ToolResult(
                success=True,
                output="No patterns found matching criteria."
            )

        lines = ["Learned Patterns", "=" * 40]
        for p in patterns[:30]:  # Limit output
            conf = f"{p.confidence:.0%}"
            lines.append(f"\n[{p.language}] {p.name} ({conf} confidence)")
            lines.append(f"  Category: {p.category}")
            lines.append(f"  {p.pattern}")
            lines.append(f"  Seen {p.occurrences}x in {len(p.files)} files")
            if p.examples:
                lines.append(f"  Example: {p.examples[0][:50]}...")

        if len(patterns) > 30:
            lines.append(f"\n... and {len(patterns) - 30} more patterns")

        return ToolResult(success=True, output="\n".join(lines))

    def _get_style(self) -> ToolResult:
        """Get learned project style."""
        summary = self.learner.get_style_summary()
        return ToolResult(success=True, output=summary)

    def _suggest(self, language: str, context: str, category: str) -> ToolResult:
        """Get pattern suggestions for a context."""
        if not language:
            return ToolResult(
                success=False,
                output="",
                error="Language is required for suggestions"
            )

        categories = [category] if category else None
        patterns = self.learner.suggest_for_context(language, context, categories)

        if not patterns:
            return ToolResult(
                success=True,
                output=f"No pattern suggestions for {language}"
            )

        lines = [f"Pattern Suggestions for {language}", "=" * 40]
        for p in patterns:
            conf = f"{p.confidence:.0%}"
            lines.append(f"\n{p.name} ({conf})")
            lines.append(f"  {p.pattern}")
            if p.examples:
                lines.append(f"  Example: {p.examples[0][:60]}")

        return ToolResult(success=True, output="\n".join(lines))

    def _get_stats(self) -> ToolResult:
        """Get learning statistics."""
        stats = self.learner.get_statistics()

        lines = [
            "Learning Statistics",
            "=" * 40,
            f"Total patterns: {stats['total_patterns']}",
            f"High confidence patterns: {stats['high_confidence_count']}",
            "",
            "By Language:",
        ]
        for lang, count in stats["by_language"].items():
            lines.append(f"  {lang}: {count}")

        lines.append("\nBy Category:")
        for cat, count in stats["by_category"].items():
            lines.append(f"  {cat}: {count}")

        return ToolResult(success=True, output="\n".join(lines))

    def _export(self, output: str) -> ToolResult:
        """Export patterns to file."""
        if not output:
            output = "patterns_export.json"

        import json
        output_path = Path(output)

        data = {
            "patterns": [p.to_dict() for p in self.learner.patterns.values()],
            "style": {
                "naming_conventions": self.learner.project_style.naming_conventions,
                "import_style": self.learner.project_style.import_style,
                "docstring_style": self.learner.project_style.docstring_style,
                "type_hints": self.learner.project_style.type_hints,
                "line_length": self.learner.project_style.line_length,
                "quotes": self.learner.project_style.quotes,
            }
        }

        output_path.write_text(json.dumps(data, indent=2))
        return ToolResult(
            success=True,
            output=f"Exported {len(data['patterns'])} patterns to {output_path}"
        )
