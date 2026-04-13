"""
Enhanced System Prompts for Sovereign Agent v2.

Dynamic prompts based on task complexity, context, and agent state.
"""

from dataclasses import dataclass, field
from enum import Enum

from src.agent.router import ModelSize
from src.agent.specializations import Specialization, get_specialization, detect_specialization


class TaskType(Enum):
    """Types of tasks for specialized prompting."""
    IMPLEMENT = "implement"
    DEBUG = "debug"
    REFACTOR = "refactor"
    EXPLAIN = "explain"
    REVIEW = "review"
    TEST = "test"
    DOCUMENT = "document"
    EXPLORE = "explore"
    BUILD = "build"
    GENERAL = "general"


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


BASE_IDENTITY = """\
You are Sovereign Agent - an autonomous coding AI with full filesystem access.

## Core Principles
1. **Write complete code** - Every function has a working implementation. No stubs, no TODOs.
2. **Execute, don't explain** - When asked to implement, use write_file immediately.
3. **Read before editing** - Always read existing code before modifying it.
4. **Be efficient** - Don't read the same file twice. Plan before acting.
5. **Verify your work** - Check that files were saved correctly.

## Workflow
1. Read 1-3 files to understand context
2. Write complete implementations
3. Save with write_file immediately
4. Verify and move to next file
"""

EFFICIENCY_RULES = """\
## Efficiency
- Results are cached within iterations - don't re-read files
- Use str_replace for edits, write_file for new files
- List directories before reading unknown paths
- Handle errors by trying a different approach, not retrying the same one
"""

ANTI_LOOP_RULES = """\
## Avoid Loops
- Track what you've discovered - don't repeat searches
- After 2-3 tool calls, summarize findings before continuing
- If a search returns nothing, try a broader pattern or move on
- When you have enough context, stop exploring and respond
"""

TOOL_FORMAT = """\
## Tool Format

Use tools in this exact XML format:
```
<tool name="tool_name">
<param name="param_name">value</param>
</tool>
```

For str_replace, ALL THREE parameters are required: path, old_str, new_str.
You can use multiple tools in a single response.
"""

RESPONSE_FORMAT = """\
## Response Format
1. Brief plan (1-2 sentences)
2. Tool calls (execute your plan)
3. Summary (what happened, what's next)
"""

TASK_PROMPTS = {
    TaskType.IMPLEMENT: """\
## Implementation Mode
- Write COMPLETE files, not snippets
- Include all headers/imports
- No placeholders - every function has a real body
- Save every file with write_file
- Use your full output capacity for complete code
""",

    TaskType.DEBUG: """\
## Debugging Mode
- Understand the error before fixing
- Read relevant code for context
- Make minimal, targeted fixes
- Verify the fix doesn't break other functionality
""",

    TaskType.REFACTOR: """\
## Refactoring Mode
- Preserve existing functionality
- Make incremental improvements
- Use code_review to verify quality
- Run tests after changes if available
""",

    TaskType.EXPLAIN: """\
## Explanation Mode
- Be clear and concise
- Use examples when helpful
- Explain the "why" not just the "what"
- Reference specific code locations
""",

    TaskType.REVIEW: """\
## Review Mode
- Use code_review for static analysis
- Check for bugs, security issues, performance
- Suggest specific, actionable improvements
- Prioritize critical issues first
""",

    TaskType.TEST: """\
## Testing Mode
- Use generate_tests for scaffolds
- Cover happy paths and edge cases
- Test error conditions
- Keep tests focused and independent
""",

    TaskType.DOCUMENT: """\
## Documentation Mode
- Be clear and concise with proper formatting
- Include code examples where helpful
- Document the "why" not just the "how"
""",

    TaskType.EXPLORE: """\
## Exploration Mode
1. List root directory for project structure
2. Read entry points and config files
3. Identify tech stack and architecture
4. Stop when you can explain what it does and how to improve it

Report: project type, purpose, tech stack, architecture, key features, improvements.
""",

    TaskType.BUILD: """\
## Build Mode
- Read build files (vcxproj, CMakeLists.txt, Makefile) first
- Check configuration and platform settings
- Verify source files and library dependencies
- Analyze build errors systematically
- Fix issues one by one, verify each fix
""",

    TaskType.GENERAL: """\
## General Mode
- Understand the request fully before acting
- Choose the most appropriate tools
- Verify results are correct
"""
}

MODEL_HINTS = {
    ModelSize.SMALL: "Focus on simple, direct solutions. Prefer established patterns.",
    ModelSize.MEDIUM: "Balance thoroughness with efficiency.",
    ModelSize.LARGE: "Take time for complex analysis. Consider architecture and edge cases.",
}


def detect_task_type(task: str) -> TaskType:
    """Detect the type of task from the description."""
    task_lower = task.lower()

    if any(w in task_lower for w in ["compile", "msbuild", "cmake", "build error", "linker error",
                                      "lnk2019", "vcxproj", "build the project", "fix build",
                                      "compilation", "build system"]):
        return TaskType.BUILD

    if any(w in task_lower for w in ["implement", "create", "add", "write new"]):
        return TaskType.IMPLEMENT

    if "build" in task_lower and not any(w in task_lower for w in ["error", "fix", "fail"]):
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


def build_dynamic_prompt(context: PromptContext, compact: bool = False) -> str:
    """Build a dynamic system prompt based on context."""
    sections = []

    sections.append(BASE_IDENTITY)

    if not compact:
        sections.append(f"## Model Note\n{MODEL_HINTS[context.model_size]}")

        if context.specialization != Specialization.GENERAL:
            spec_config = get_specialization(context.specialization)
            sections.append(spec_config.system_prompt_additions)
        elif context.file_extensions:
            detected = detect_specialization(context.file_extensions)
            if detected != Specialization.GENERAL:
                spec_config = get_specialization(detected)
                sections.append(spec_config.system_prompt_additions)

    if context.retrieved_context:
        rag_content = context.retrieved_context
        if len(rag_content) > 4000:
            rag_content = rag_content[:4000] + "\n[...truncated...]"
        sections.append(f"## Relevant Context\n{rag_content}")

    if context.conversation_summary:
        summary = context.conversation_summary
        if len(summary) > 2000:
            summary = summary[:2000] + "\n[...truncated...]"
        sections.append(f"## Previous Summary\n{summary}")

    sections.append(TASK_PROMPTS[context.task_type])

    sections.append("## Available Tools\n")
    sections.append(context.tools_block)

    sections.append(TOOL_FORMAT)

    if compact:
        sections.append(EFFICIENCY_RULES)
    else:
        sections.append(EFFICIENCY_RULES)
        sections.append(ANTI_LOOP_RULES)
        sections.append(RESPONSE_FORMAT)

    if context.error_history:
        errors = context.error_history
        if len(errors) > 500:
            errors = errors[-500:]
        sections.append(f"## Recent Errors\n{errors}")

    if context.performance_hint:
        sections.append(f"\n{context.performance_hint}\n")

    return "\n\n".join(sections)


def build_system_prompt(tools_block: str) -> str:
    """Build a basic system prompt (backwards compatible)."""
    context = PromptContext(
        task="",
        task_type=TaskType.GENERAL,
        model_size=ModelSize.MEDIUM,
        tools_block=tools_block
    )
    return build_dynamic_prompt(context)
