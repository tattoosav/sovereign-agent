"""
Enhanced System Prompts for Sovereign Agent v2.

Dynamic prompts based on task complexity, context, and agent state.
Includes specializations for C++, .NET, Visual Studio, and GUI development.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from src.agent.router import ModelSize
from src.agent.specializations import Specialization, get_specialization, detect_specialization


class TaskType(Enum):
    """Types of tasks for specialized prompting."""
    IMPLEMENT = "implement"       # Write new code
    DEBUG = "debug"               # Fix bugs
    REFACTOR = "refactor"         # Improve existing code
    EXPLAIN = "explain"           # Explain code
    REVIEW = "review"             # Code review
    TEST = "test"                 # Write tests
    DOCUMENT = "document"         # Write documentation
    EXPLORE = "explore"           # Explore codebase
    GENERAL = "general"           # General task


@dataclass
class PromptContext:
    """Context for building dynamic prompts."""
    task: str
    task_type: TaskType
    model_size: ModelSize
    tools_block: str
    retrieved_context: str = ""
    conversation_summary: str = ""
    error_history: str = ""
    performance_hint: str = ""
    specialization: Specialization = Specialization.GENERAL
    file_extensions: list[str] = field(default_factory=list)


# Base system prompt components
BASE_IDENTITY = """\
You are Sovereign Agent - an intelligent, autonomous coding assistant with full filesystem access.
You work locally on the user's machine with complete control over files, git, and shell commands.
"""

EFFICIENCY_RULES = """\
## Efficiency Rules
1. **NEVER read the same file twice** - Results are cached within iterations
2. **Read before editing** - ALWAYS use read_file before str_replace or write_file
3. **Use str_replace for edits** - More efficient than rewriting entire files
4. **List before reading** - Use list_directory to explore unknown directories
5. **Think before acting** - Plan your approach, don't trial-and-error
6. **Handle errors intelligently** - Read error recovery suggestions and follow them
"""

TOOL_FORMAT = """\
## Tool Usage Format

When you need to use a tool, output it in this exact format:
```
<tool name="tool_name">
<param name="param_name">value</param>
</tool>
```

You can use multiple tools in a single response. Execute all independent operations together.
"""

RESPONSE_FORMAT = """\
## Response Format

Structure your responses:
1. **Brief plan** (1-2 sentences of what you'll do)
2. **Tool calls** (execute your plan)
3. **Summary** (what happened, what's next)

Be concise. Avoid unnecessary explanations.
"""

# Task-specific prompts
TASK_PROMPTS = {
    TaskType.IMPLEMENT: """\
## Implementation Guidelines
- Write clean, well-structured code following existing patterns
- Add appropriate error handling
- Consider edge cases
- Use meaningful variable and function names
- Keep functions focused and small
""",

    TaskType.DEBUG: """\
## Debugging Guidelines
- First, understand the error completely before fixing
- Read relevant code to understand context
- Form a hypothesis about the root cause
- Make minimal, targeted fixes
- Verify the fix doesn't break other functionality
""",

    TaskType.REFACTOR: """\
## Refactoring Guidelines
- Preserve existing functionality - no behavior changes
- Make incremental improvements
- Use code_review to verify quality
- Consider backwards compatibility
- Run tests after changes if available
""",

    TaskType.EXPLAIN: """\
## Explanation Guidelines
- Be clear and concise
- Use examples when helpful
- Explain the "why" not just the "what"
- Reference specific code locations
- Adjust detail level to the question
""",

    TaskType.REVIEW: """\
## Code Review Guidelines
- Use the code_review tool for static analysis
- Check for common issues: bugs, security, performance
- Suggest specific, actionable improvements
- Prioritize critical issues first
- Be constructive, not just critical
""",

    TaskType.TEST: """\
## Testing Guidelines
- Use generate_tests to create test scaffolds
- Cover happy paths and edge cases
- Test error conditions
- Keep tests focused and independent
- Use descriptive test names
""",

    TaskType.DOCUMENT: """\
## Documentation Guidelines
- Be clear and concise
- Use proper formatting (markdown)
- Include code examples where helpful
- Document the "why" not just the "how"
- Keep documentation close to the code
""",

    TaskType.EXPLORE: """\
## Exploration Guidelines
- Use list_directory to understand structure
- Use code_search to find relevant patterns
- Read key files to understand architecture
- Map dependencies and relationships
- Summarize findings clearly
""",

    TaskType.GENERAL: """\
## General Guidelines
- Understand the request fully before acting
- Choose the most appropriate tools
- Verify your work produces correct results
- Be efficient and focused
"""
}

# Model-specific adjustments
MODEL_HINTS = {
    ModelSize.SMALL: """\
## Note: Operating in fast mode
- Focus on simple, direct solutions
- Minimize complex reasoning chains
- Prefer established patterns over novel approaches
""",

    ModelSize.MEDIUM: """\
## Note: Standard mode
- Balance thoroughness with efficiency
- Use appropriate level of detail
- Consider multiple approaches when relevant
""",

    ModelSize.LARGE: """\
## Note: Advanced reasoning mode
- Take time for complex analysis
- Consider architecture and design implications
- Explore edge cases thoroughly
- Think about long-term maintainability
"""
}


def detect_task_type(task: str) -> TaskType:
    """
    Detect the type of task from the description.

    Args:
        task: Task description

    Returns:
        TaskType enum
    """
    task_lower = task.lower()

    # Check for specific indicators
    if any(w in task_lower for w in ["implement", "create", "build", "add", "write new"]):
        return TaskType.IMPLEMENT

    if any(w in task_lower for w in ["debug", "fix", "bug", "error", "broken", "not working"]):
        return TaskType.DEBUG

    if any(w in task_lower for w in ["refactor", "improve", "clean up", "optimize", "restructure"]):
        return TaskType.REFACTOR

    if any(w in task_lower for w in ["explain", "what does", "how does", "why does", "understand"]):
        return TaskType.EXPLAIN

    if any(w in task_lower for w in ["review", "check", "audit", "analyze quality"]):
        return TaskType.REVIEW

    if any(w in task_lower for w in ["test", "write tests", "add tests", "coverage"]):
        return TaskType.TEST

    if any(w in task_lower for w in ["document", "readme", "docstring", "comments"]):
        return TaskType.DOCUMENT

    if any(w in task_lower for w in ["explore", "find", "search", "where is", "show me"]):
        return TaskType.EXPLORE

    return TaskType.GENERAL


def build_dynamic_prompt(context: PromptContext) -> str:
    """
    Build a dynamic system prompt based on context.

    Args:
        context: PromptContext with all relevant information

    Returns:
        Complete system prompt string
    """
    sections = []

    # Base identity
    sections.append(BASE_IDENTITY)

    # Model hint
    sections.append(MODEL_HINTS[context.model_size])

    # Language/Framework specialization
    if context.specialization != Specialization.GENERAL:
        spec_config = get_specialization(context.specialization)
        sections.append(spec_config.system_prompt_additions)
    elif context.file_extensions:
        # Auto-detect specialization from file extensions
        detected = detect_specialization(context.file_extensions)
        if detected != Specialization.GENERAL:
            spec_config = get_specialization(detected)
            sections.append(spec_config.system_prompt_additions)

    # Retrieved context (RAG)
    if context.retrieved_context:
        sections.append("## Relevant Context from Memory\n")
        sections.append(context.retrieved_context)
        sections.append("\nUse this context to inform your approach.\n")

    # Conversation summary
    if context.conversation_summary:
        sections.append("## Previous Conversation Summary\n")
        sections.append(context.conversation_summary)
        sections.append("\n")

    # Task-specific guidance
    sections.append(TASK_PROMPTS[context.task_type])

    # Tools
    sections.append("## Available Tools\n")
    sections.append(context.tools_block)

    # Tool format
    sections.append(TOOL_FORMAT)

    # Efficiency rules
    sections.append(EFFICIENCY_RULES)

    # Response format
    sections.append(RESPONSE_FORMAT)

    # Error history (if there were recent errors)
    if context.error_history:
        sections.append("## Recent Errors to Avoid\n")
        sections.append(context.error_history)
        sections.append("\nLearn from these errors and avoid repeating them.\n")

    # Performance hint
    if context.performance_hint:
        sections.append(f"\n## Performance Note\n{context.performance_hint}\n")

    # Closing
    sections.append("\nWork smart, work fast, work correct.")

    return "\n".join(sections)


# Keep backwards compatibility
def build_system_prompt(tools_block: str) -> str:
    """
    Build a basic system prompt (backwards compatible).

    For enhanced prompts, use build_dynamic_prompt with PromptContext.
    """
    context = PromptContext(
        task="",
        task_type=TaskType.GENERAL,
        model_size=ModelSize.MEDIUM,
        tools_block=tools_block
    )
    return build_dynamic_prompt(context)
