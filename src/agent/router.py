"""
Multi-model routing system.

Routes tasks to appropriate models based on complexity.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum

import httpx

logger = logging.getLogger(__name__)


class ModelSize(Enum):
    """Model size categories."""
    SMALL = "small"    # 7B - fast, simple tasks
    MEDIUM = "medium"  # 14B - balanced
    LARGE = "large"    # 32B+ - complex tasks


@dataclass
class ModelConfig:
    """Configuration for a specific model."""
    size: ModelSize
    name: str
    max_tokens: int
    use_cases: list[str]


class ModelRouter:
    """
    Routes tasks to appropriate models based on complexity.

    Uses heuristics to analyze task complexity and select the best model.
    Checks model availability and falls back gracefully.
    """

    # Default model registry (can be overridden by available models)
    # All models use 32K context for complex code generation
    MODELS = {
        ModelSize.SMALL: ModelConfig(
            size=ModelSize.SMALL,
            name="qwen2.5-coder:7b",
            max_tokens=8192,  # 8K for small model
            use_cases=[
                "explain code",
                "format code",
                "simple edits",
                "documentation",
                "code review comments"
            ]
        ),
        ModelSize.MEDIUM: ModelConfig(
            size=ModelSize.MEDIUM,
            name="qwen2.5-coder:14b",
            max_tokens=16384,  # 16K for full file generation
            use_cases=[
                "implement features",
                "debug issues",
                "refactor code",
                "write tests",
                "most coding tasks"
            ]
        ),
        ModelSize.LARGE: ModelConfig(
            size=ModelSize.LARGE,
            name="qwen2.5-coder:32b",
            max_tokens=16384,  # 16K for complex multi-file tasks
            use_cases=[
                "architecture design",
                "multi-file refactoring",
                "complex debugging",
                "system design",
                "advanced algorithms"
            ]
        )
    }

    # Cache of available models (populated on first check)
    _available_models: set[str] | None = None
    _ollama_url: str = "http://localhost:11434"

    @classmethod
    def set_ollama_url(cls, url: str) -> None:
        """Set the Ollama URL for model availability checks."""
        cls._ollama_url = url
        cls._available_models = None  # Reset cache

    @classmethod
    def get_available_models(cls) -> set[str]:
        """Get list of available models from Ollama."""
        if cls._available_models is not None:
            return cls._available_models

        try:
            response = httpx.get(f"{cls._ollama_url}/api/tags", timeout=5.0)
            if response.status_code == 200:
                data = response.json()
                cls._available_models = {
                    model["name"] for model in data.get("models", [])
                }
                logger.info(f"Available models: {cls._available_models}")
            else:
                cls._available_models = set()
        except Exception as e:
            logger.warning(f"Could not fetch available models: {e}")
            cls._available_models = set()

        return cls._available_models

    @classmethod
    def is_model_available(cls, model_name: str) -> bool:
        """Check if a model is available."""
        available = cls.get_available_models()
        return model_name in available

    @classmethod
    def get_best_available_model(cls, preferred_size: ModelSize) -> str:
        """
        Get the best available model for the preferred size.

        Falls back to smaller models if larger ones aren't available.
        """
        # Order of preference: preferred -> medium -> small -> large
        size_priority = {
            ModelSize.LARGE: [ModelSize.LARGE, ModelSize.MEDIUM, ModelSize.SMALL],
            ModelSize.MEDIUM: [ModelSize.MEDIUM, ModelSize.SMALL, ModelSize.LARGE],
            ModelSize.SMALL: [ModelSize.SMALL, ModelSize.MEDIUM, ModelSize.LARGE],
        }

        for size in size_priority[preferred_size]:
            model_name = cls.MODELS[size].name
            if cls.is_model_available(model_name):
                if size != preferred_size:
                    logger.info(f"Falling back from {preferred_size.value} to {size.value} (model availability)")
                return model_name

        # If no configured models available, return the medium as default
        # (let it fail later with a clear error)
        logger.warning("No configured models available, using default")
        return cls.MODELS[ModelSize.MEDIUM].name

    @staticmethod
    def analyze_complexity(task: str, context_size: int = 0) -> ModelSize:
        """
        Analyze task complexity and return appropriate model size.

        Args:
            task: The task description
            context_size: Size of context (number of files, lines, etc.)

        Returns:
            ModelSize enum indicating which model to use
        """
        task_lower = task.lower()

        # High complexity indicators
        high_complexity = [
            "architecture", "design system", "multi-file",
            "refactor entire", "migrate", "redesign",
            "complex algorithm", "optimize performance",
            "debug complex", "analyze entire"
        ]

        # Low complexity indicators
        low_complexity = [
            "explain", "format", "add comment", "fix typo",
            "rename variable", "simple edit", "documentation",
            "what does", "how does"
        ]

        # Check for high complexity
        if any(indicator in task_lower for indicator in high_complexity):
            logger.info(f"Routing to LARGE model: high complexity task")
            return ModelSize.LARGE

        # Check for low complexity
        if any(indicator in task_lower for indicator in low_complexity):
            logger.info(f"Routing to SMALL model: low complexity task")
            return ModelSize.SMALL

        # Context size matters
        if context_size > 1000:  # Large codebase
            logger.info(f"Routing to LARGE model: large context ({context_size})")
            return ModelSize.LARGE

        # Word count heuristic
        word_count = len(task.split())
        if word_count > 100:  # Detailed/complex description
            logger.info(f"Routing to LARGE model: detailed request ({word_count} words)")
            return ModelSize.LARGE

        # File count heuristic from task description
        file_mentions = task_lower.count(".py") + task_lower.count(".js") + \
                       task_lower.count(".ts") + task_lower.count(".java")

        if file_mentions > 5:
            logger.info(f"Routing to LARGE model: multiple files ({file_mentions})")
            return ModelSize.LARGE
        elif file_mentions > 2:
            logger.info(f"Routing to MEDIUM model: several files ({file_mentions})")
            return ModelSize.MEDIUM

        # Tool usage complexity
        tool_indicators = task_lower.count("read") + task_lower.count("write") + \
                         task_lower.count("search") + task_lower.count("execute")

        if tool_indicators > 3:
            logger.info(f"Routing to MEDIUM model: multiple tools needed")
            return ModelSize.MEDIUM

        # Default to medium model (best balance)
        logger.info(f"Routing to MEDIUM model: default choice")
        return ModelSize.MEDIUM

    @classmethod
    def get_model_for_task(cls, task: str, context_size: int = 0) -> str:
        """
        Get the model name for a given task.

        Checks model availability and falls back if needed.

        Args:
            task: The task description
            context_size: Size of context

        Returns:
            Model name string (e.g., "qwen2.5-coder:14b")
        """
        preferred_size = cls.analyze_complexity(task, context_size)
        model_name = cls.get_best_available_model(preferred_size)
        logger.info(f"Selected model: {model_name} for task: {task[:50]}...")
        return model_name

    @classmethod
    def get_model_config(cls, size: ModelSize) -> ModelConfig:
        """Get configuration for a specific model size."""
        return cls.MODELS[size]
