"""
Base class for all agent tools.

Every tool must inherit from BaseTool and implement:
- name: str - unique identifier
- description: str - what the tool does (shown to LLM)
- parameters: dict - parameter definitions
- execute() - the actual implementation
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class ToolResult:
    """Result from executing a tool."""
    success: bool
    output: str
    error: str | None = None


class BaseTool(ABC):
    """Abstract base class for all tools."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique tool identifier."""
        ...
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Description shown to the LLM."""
        ...
    
    @property
    @abstractmethod
    def parameters(self) -> dict[str, dict[str, Any]]:
        """
        Parameter definitions.
        Format: {
            "param_name": {
                "type": "string",
                "description": "What this param does",
                "required": True
            }
        }
        """
        ...
    
    @abstractmethod
    def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the tool with given parameters."""
        ...
    
    def to_prompt_format(self) -> str:
        """Format tool info for inclusion in LLM prompt."""
        params_str = "\n".join(
            f"    - {name} ({info['type']}): {info['description']}"
            + (" [required]" if info.get('required') else " [optional]")
            for name, info in self.parameters.items()
        )
        return f"""<tool_definition>
  <name>{self.name}</name>
  <description>{self.description}</description>
  <parameters>
{params_str}
  </parameters>
</tool_definition>"""


class ToolRegistry:
    """Registry of available tools."""
    
    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}
    
    def register(self, tool: BaseTool) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool
    
    def get(self, name: str) -> BaseTool | None:
        """Get a tool by name."""
        return self._tools.get(name)
    
    def all_tools(self) -> list[BaseTool]:
        """Get all registered tools."""
        return list(self._tools.values())
    
    def get_prompt_block(self) -> str:
        """Get all tool definitions formatted for LLM prompt."""
        return "\n\n".join(tool.to_prompt_format() for tool in self._tools.values())
