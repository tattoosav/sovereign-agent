"""Agent package for Sovereign Agent."""

from .core import Agent, AgentConfig
from .core_v2 import AgentV2, AgentConfig as AgentConfigV2, TurnResult
from .llm import OllamaClient
from .router import ModelRouter, ModelSize
from .context import ContextManager
from .prompts_v2 import TaskType, detect_task_type
from .parallel import ParallelExecutor, AsyncParallelExecutor, ParallelToolCall

__all__ = [
    # v1 (backwards compatible)
    "Agent",
    "AgentConfig",
    "OllamaClient",
    # v2 (enhanced)
    "AgentV2",
    "AgentConfigV2",
    "TurnResult",
    "ModelRouter",
    "ModelSize",
    "ContextManager",
    "TaskType",
    "detect_task_type",
    # Parallel execution
    "ParallelExecutor",
    "AsyncParallelExecutor",
    "ParallelToolCall",
]
