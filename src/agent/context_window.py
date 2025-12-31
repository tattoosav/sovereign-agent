"""
Smart Context Window Management.

Intelligently manages the context window to maximize relevant
information while staying within token limits.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any
from enum import Enum

logger = logging.getLogger(__name__)


class ContentPriority(Enum):
    """Priority levels for context content."""
    CRITICAL = 1    # Must include (system prompt, current task)
    HIGH = 2        # Important (recent messages, tool results)
    MEDIUM = 3      # Useful (retrieved context, summaries)
    LOW = 4         # Nice to have (old history, examples)


@dataclass
class ContextBlock:
    """A block of content for the context window."""
    content: str
    priority: ContentPriority
    category: str  # "system", "history", "tool_result", "rag", "summary"
    token_estimate: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.token_estimate == 0:
            # Rough estimate: 4 chars per token
            self.token_estimate = len(self.content) // 4


@dataclass
class ContextWindowConfig:
    """Configuration for context window management."""
    max_tokens: int = 8192          # Model's context limit
    reserve_for_response: int = 2048  # Reserve for model output
    min_history_messages: int = 4    # Always keep at least this many
    max_rag_tokens: int = 2000       # Max tokens for RAG context
    summarize_threshold: int = 6000  # Start summarizing at this point


class ContextWindowManager:
    """
    Manages the context window for optimal performance.

    Features:
    - Priority-based content selection
    - Automatic summarization of old content
    - Token budget tracking
    - Smart truncation
    """

    def __init__(self, config: ContextWindowConfig | None = None):
        self.config = config or ContextWindowConfig()
        self._blocks: list[ContextBlock] = []
        self._stats = {
            "total_builds": 0,
            "truncations": 0,
            "summarizations": 0,
        }

    def clear(self) -> None:
        """Clear all context blocks."""
        self._blocks.clear()

    def add_block(
        self,
        content: str,
        priority: ContentPriority,
        category: str,
        **metadata: Any
    ) -> None:
        """Add a content block."""
        block = ContextBlock(
            content=content,
            priority=priority,
            category=category,
            metadata=metadata,
        )
        self._blocks.append(block)

    def add_system_prompt(self, content: str) -> None:
        """Add system prompt (critical priority)."""
        self.add_block(content, ContentPriority.CRITICAL, "system")

    def add_user_message(self, content: str, is_current: bool = False) -> None:
        """Add a user message."""
        priority = ContentPriority.CRITICAL if is_current else ContentPriority.HIGH
        self.add_block(content, priority, "history", role="user")

    def add_assistant_message(self, content: str, is_recent: bool = True) -> None:
        """Add an assistant message."""
        priority = ContentPriority.HIGH if is_recent else ContentPriority.MEDIUM
        self.add_block(content, priority, "history", role="assistant")

    def add_tool_result(self, tool_name: str, result: str, is_recent: bool = True) -> None:
        """Add a tool result."""
        priority = ContentPriority.HIGH if is_recent else ContentPriority.LOW
        content = f"[Tool: {tool_name}]\n{result}"
        self.add_block(content, priority, "tool_result", tool=tool_name)

    def add_rag_context(self, content: str, source: str = "unknown") -> None:
        """Add RAG-retrieved context."""
        self.add_block(content, ContentPriority.MEDIUM, "rag", source=source)

    def add_summary(self, content: str) -> None:
        """Add a conversation summary."""
        self.add_block(content, ContentPriority.MEDIUM, "summary")

    def _estimate_total_tokens(self) -> int:
        """Estimate total tokens in all blocks."""
        return sum(block.token_estimate for block in self._blocks)

    def _get_available_tokens(self) -> int:
        """Get available tokens for context."""
        return self.config.max_tokens - self.config.reserve_for_response

    def build_context(self) -> list[dict[str, str]]:
        """
        Build the final context within token limits.

        Returns:
            List of messages in chat format
        """
        self._stats["total_builds"] += 1
        available_tokens = self._get_available_tokens()

        # Sort blocks by priority
        sorted_blocks = sorted(self._blocks, key=lambda b: b.priority.value)

        # Select blocks that fit
        selected_blocks: list[ContextBlock] = []
        used_tokens = 0

        for block in sorted_blocks:
            if used_tokens + block.token_estimate <= available_tokens:
                selected_blocks.append(block)
                used_tokens += block.token_estimate
            elif block.priority == ContentPriority.CRITICAL:
                # Must include critical content, truncate if needed
                remaining = available_tokens - used_tokens
                if remaining > 100:  # Worth including
                    truncated_content = self._truncate_content(block.content, remaining)
                    block.content = truncated_content
                    block.token_estimate = len(truncated_content) // 4
                    selected_blocks.append(block)
                    used_tokens += block.token_estimate
                    self._stats["truncations"] += 1

        # Build messages list
        messages = self._blocks_to_messages(selected_blocks)

        logger.debug(
            f"Built context: {len(selected_blocks)} blocks, "
            f"~{used_tokens} tokens (limit: {available_tokens})"
        )

        return messages

    def _blocks_to_messages(self, blocks: list[ContextBlock]) -> list[dict[str, str]]:
        """Convert blocks to chat message format."""
        messages: list[dict[str, str]] = []

        # Group by category for proper ordering
        system_blocks = [b for b in blocks if b.category == "system"]
        history_blocks = [b for b in blocks if b.category == "history"]
        tool_blocks = [b for b in blocks if b.category == "tool_result"]
        rag_blocks = [b for b in blocks if b.category == "rag"]
        summary_blocks = [b for b in blocks if b.category == "summary"]

        # System prompt first
        if system_blocks:
            system_content = "\n\n".join(b.content for b in system_blocks)

            # Add RAG context to system if present
            if rag_blocks:
                rag_content = "\n\n".join(b.content for b in rag_blocks)
                system_content += f"\n\n## Relevant Context\n{rag_content}"

            # Add summary if present
            if summary_blocks:
                summary_content = "\n\n".join(b.content for b in summary_blocks)
                system_content += f"\n\n## Conversation Summary\n{summary_content}"

            messages.append({"role": "system", "content": system_content})

        # History messages in order
        for block in history_blocks:
            role = block.metadata.get("role", "user")
            messages.append({"role": role, "content": block.content})

        # Recent tool results as assistant messages
        for block in tool_blocks:
            # Tool results are typically shown as part of assistant turn
            if messages and messages[-1]["role"] == "assistant":
                messages[-1]["content"] += f"\n\n{block.content}"
            else:
                messages.append({"role": "assistant", "content": block.content})

        return messages

    def _truncate_content(self, content: str, max_tokens: int) -> str:
        """Truncate content to fit within token limit."""
        max_chars = max_tokens * 4  # Rough estimate
        if len(content) <= max_chars:
            return content

        # Try to truncate at a sentence boundary
        truncated = content[:max_chars]
        last_period = truncated.rfind(".")
        last_newline = truncated.rfind("\n")

        cut_point = max(last_period, last_newline)
        if cut_point > max_chars * 0.5:  # Only use if we keep more than half
            truncated = content[:cut_point + 1]

        return truncated + "\n...[truncated]"

    def summarize_history(
        self,
        messages: list[dict[str, str]],
        keep_recent: int = 4
    ) -> tuple[str, list[dict[str, str]]]:
        """
        Summarize older history, keeping recent messages.

        Returns:
            Tuple of (summary, recent_messages)
        """
        if len(messages) <= keep_recent:
            return "", messages

        self._stats["summarizations"] += 1

        old_messages = messages[:-keep_recent]
        recent_messages = messages[-keep_recent:]

        # Create a simple summary
        summary_parts = []
        for msg in old_messages:
            role = msg["role"].capitalize()
            content = msg["content"]

            if role == "User":
                # Extract key intent
                preview = content[:150].replace("\n", " ")
                summary_parts.append(f"- User requested: {preview}...")
            elif role == "Assistant":
                # Note tools used or actions taken
                tools_used = re.findall(r'\[Tool: (\w+)\]', content)
                if tools_used:
                    summary_parts.append(f"- Assistant used tools: {', '.join(set(tools_used))}")
                else:
                    preview = content[:100].replace("\n", " ")
                    summary_parts.append(f"- Assistant responded: {preview}...")

        summary = "Previous conversation:\n" + "\n".join(summary_parts[-10:])
        return summary, recent_messages

    def get_stats(self) -> dict[str, Any]:
        """Get context window statistics."""
        return {
            **self._stats,
            "current_blocks": len(self._blocks),
            "estimated_tokens": self._estimate_total_tokens(),
            "available_tokens": self._get_available_tokens(),
            "config": {
                "max_tokens": self.config.max_tokens,
                "reserve_for_response": self.config.reserve_for_response,
            }
        }


class AdaptiveContextManager(ContextWindowManager):
    """
    Context manager that adapts to model and task requirements.

    Features:
    - Model-specific token limits
    - Task-type aware prioritization
    - Learning from past context usage
    """

    # Token limits for different model sizes
    MODEL_LIMITS = {
        "7b": 4096,
        "14b": 8192,
        "32b": 16384,
        "70b": 32768,
    }

    def __init__(
        self,
        model_size: str = "14b",
        task_type: str = "general"
    ):
        # Set config based on model
        max_tokens = self.MODEL_LIMITS.get(model_size, 8192)
        config = ContextWindowConfig(
            max_tokens=max_tokens,
            reserve_for_response=max_tokens // 4,
        )
        super().__init__(config)

        self.model_size = model_size
        self.task_type = task_type

    def adapt_for_task(self, task_type: str) -> None:
        """Adapt context strategy for task type."""
        self.task_type = task_type

        # Adjust RAG allocation based on task
        if task_type in ("implement", "refactor"):
            self.config.max_rag_tokens = 3000  # More code context needed
        elif task_type in ("explain", "document"):
            self.config.max_rag_tokens = 2000  # Balanced
        elif task_type == "debug":
            self.config.max_rag_tokens = 2500  # Error context important
        else:
            self.config.max_rag_tokens = 1500  # Less RAG, more history

    def adapt_for_model(self, model_size: str) -> None:
        """Adapt context limits for model size."""
        self.model_size = model_size
        max_tokens = self.MODEL_LIMITS.get(model_size, 8192)
        self.config.max_tokens = max_tokens
        self.config.reserve_for_response = max_tokens // 4
