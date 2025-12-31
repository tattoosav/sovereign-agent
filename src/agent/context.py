"""
Context Manager for Sovereign Agent.

Manages context retrieval, conversation summarization, and RAG integration.
This is the intelligence layer that makes the agent smarter.
"""

import logging
from dataclasses import dataclass, field
from typing import Any

from src.memory.knowledge_base import KnowledgeBase
from src.memory.vector_store import VectorStore

logger = logging.getLogger(__name__)


@dataclass
class RetrievedContext:
    """Context retrieved from memory systems."""
    relevant_code: list[dict[str, Any]] = field(default_factory=list)
    past_solutions: list[dict[str, Any]] = field(default_factory=list)
    patterns: list[dict[str, Any]] = field(default_factory=list)

    def is_empty(self) -> bool:
        """Check if no context was retrieved."""
        return not (self.relevant_code or self.past_solutions or self.patterns)

    def to_prompt_section(self) -> str:
        """Format retrieved context for inclusion in prompt."""
        if self.is_empty():
            return ""

        sections = []

        if self.relevant_code:
            sections.append("## Relevant Code from Codebase\n")
            for item in self.relevant_code[:3]:  # Limit to top 3
                sections.append(f"**{item.get('file', 'Unknown')}:**\n```\n{item.get('content', '')[:500]}...\n```\n")

        if self.past_solutions:
            sections.append("## Similar Past Solutions\n")
            for item in self.past_solutions[:2]:  # Limit to top 2
                sections.append(f"**{item.get('title', 'Solution')}:**\n{item.get('content', '')[:300]}...\n")

        if self.patterns:
            sections.append("## Relevant Patterns\n")
            for item in self.patterns[:2]:
                sections.append(f"- **{item.get('title', 'Pattern')}:** {item.get('content', '')[:200]}\n")

        return "\n".join(sections)


class ContextManager:
    """
    Manages context retrieval and conversation intelligence.

    Responsibilities:
    - Query vector store for relevant code
    - Search knowledge base for past solutions
    - Summarize long conversations
    - Build enriched prompts with retrieved context
    """

    def __init__(
        self,
        vector_store: VectorStore | None = None,
        knowledge_base: KnowledgeBase | None = None,
        max_history_tokens: int = 4000,
    ):
        self.vector_store = vector_store or VectorStore()
        self.knowledge_base = knowledge_base or KnowledgeBase()
        self.max_history_tokens = max_history_tokens
        self._conversation_summary: str = ""

    def retrieve_context(self, query: str) -> RetrievedContext:
        """
        Retrieve relevant context for a query.

        Args:
            query: The user's request or task description

        Returns:
            RetrievedContext with relevant code, solutions, and patterns
        """
        context = RetrievedContext()

        # Search codebase for relevant code
        if self.vector_store.is_available():
            try:
                code_results = self.vector_store.search(
                    collection_name="codebase",
                    query=query,
                    n_results=5
                )

                for i, doc in enumerate(code_results.get("documents", [])):
                    metadata = code_results.get("metadatas", [{}])[i] if code_results.get("metadatas") else {}
                    context.relevant_code.append({
                        "file": metadata.get("file_path", "unknown"),
                        "content": doc,
                        "distance": code_results.get("distances", [])[i] if code_results.get("distances") else 1.0
                    })

                logger.debug(f"Retrieved {len(context.relevant_code)} relevant code snippets")

            except Exception as e:
                logger.warning(f"Error retrieving code context: {e}")

        # Search knowledge base for past solutions
        try:
            solutions = self.knowledge_base.search_entries(
                query=query,
                entry_type="solution"
            )

            for sol in solutions[:3]:
                context.past_solutions.append({
                    "title": sol.title,
                    "content": sol.content,
                    "tags": sol.tags
                })

            # Also get relevant patterns
            patterns = self.knowledge_base.search_entries(
                query=query,
                entry_type="pattern"
            )

            for pat in patterns[:2]:
                context.patterns.append({
                    "title": pat.title,
                    "content": pat.content,
                    "tags": pat.tags
                })

            logger.debug(f"Retrieved {len(context.past_solutions)} solutions, {len(context.patterns)} patterns")

        except Exception as e:
            logger.warning(f"Error retrieving knowledge base context: {e}")

        return context

    def summarize_conversation(self, messages: list[dict[str, str]], llm_client: Any = None) -> str:
        """
        Summarize a long conversation to reduce token usage.

        Args:
            messages: List of conversation messages
            llm_client: Optional LLM client for generating summary

        Returns:
            Summarized conversation as a string
        """
        if len(messages) <= 4:
            # Short conversation, no need to summarize
            return ""

        # Simple heuristic summarization (can be enhanced with LLM)
        summary_parts = []

        # Keep track of key actions
        tool_calls = []
        key_points = []

        for msg in messages:
            content = msg.get("content", "")
            role = msg.get("role", "")

            if role == "user":
                # Extract key user requests (first sentence or line)
                first_line = content.split('\n')[0][:100]
                if first_line:
                    key_points.append(f"User asked: {first_line}")

            elif role == "assistant":
                # Extract tool usage
                if "<tool" in content:
                    import re
                    tools = re.findall(r'<tool name="([^"]+)">', content)
                    tool_calls.extend(tools)

        if key_points:
            summary_parts.append("Previous requests: " + "; ".join(key_points[-3:]))

        if tool_calls:
            unique_tools = list(set(tool_calls))
            summary_parts.append(f"Tools used: {', '.join(unique_tools)}")

        summary = "\n".join(summary_parts)
        self._conversation_summary = summary

        logger.debug(f"Generated conversation summary: {len(summary)} chars")
        return summary

    def get_optimized_history(
        self,
        messages: list[dict[str, str]],
        max_messages: int = 10
    ) -> list[dict[str, str]]:
        """
        Get optimized conversation history for prompt.

        Keeps recent messages and summarizes older ones.

        Args:
            messages: Full conversation history
            max_messages: Maximum messages to include verbatim

        Returns:
            Optimized message list
        """
        if len(messages) <= max_messages:
            return messages

        # Summarize older messages
        older_messages = messages[:-max_messages]
        recent_messages = messages[-max_messages:]

        summary = self.summarize_conversation(older_messages)

        optimized = []
        if summary:
            optimized.append({
                "role": "system",
                "content": f"[Conversation Summary]\n{summary}"
            })

        optimized.extend(recent_messages)

        logger.info(f"Optimized history: {len(messages)} -> {len(optimized)} messages")
        return optimized

    def learn_from_success(
        self,
        task: str,
        solution: str,
        tools_used: list[str],
        tags: list[str] | None = None
    ) -> None:
        """
        Store successful solutions for future reference.

        Args:
            task: The original task description
            solution: The successful solution
            tools_used: List of tools that were used
            tags: Optional tags for categorization
        """
        try:
            entry_tags = tags or []
            entry_tags.extend(tools_used)
            entry_tags = list(set(entry_tags))  # Deduplicate

            self.knowledge_base.add_entry(
                entry_type="solution",
                title=task[:100],
                content=solution,
                tags=entry_tags,
                metadata={"tools_used": tools_used}
            )

            logger.info(f"Stored successful solution: {task[:50]}...")

        except Exception as e:
            logger.warning(f"Error storing solution: {e}")

    def learn_pattern(
        self,
        pattern_name: str,
        description: str,
        example: str,
        tags: list[str] | None = None
    ) -> None:
        """
        Store a code pattern for future reference.

        Args:
            pattern_name: Name of the pattern
            description: Description of what the pattern does
            example: Example code or usage
            tags: Optional tags for categorization
        """
        try:
            content = f"{description}\n\nExample:\n```\n{example}\n```"

            self.knowledge_base.add_entry(
                entry_type="pattern",
                title=pattern_name,
                content=content,
                tags=tags or []
            )

            logger.info(f"Stored pattern: {pattern_name}")

        except Exception as e:
            logger.warning(f"Error storing pattern: {e}")
