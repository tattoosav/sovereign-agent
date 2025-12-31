"""
Task planning and decomposition.

Breaks complex tasks into smaller, executable steps with dependencies.
Supports both heuristic and LLM-based decomposition for complex projects.
"""

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Status of a task."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


@dataclass
class Task:
    """A single task in a plan."""
    id: str
    description: str
    status: TaskStatus = TaskStatus.PENDING
    dependencies: list[str] = field(default_factory=list)
    result: Any | None = None
    error: str | None = None

    def can_start(self, completed_tasks: set[str]) -> bool:
        """Check if all dependencies are completed."""
        return all(dep_id in completed_tasks for dep_id in self.dependencies)


@dataclass
class TaskPlan:
    """A plan consisting of multiple tasks."""
    name: str
    tasks: list[Task]

    def get_next_tasks(self) -> list[Task]:
        """Get all tasks that can be started now."""
        completed = {
            task.id for task in self.tasks
            if task.status == TaskStatus.COMPLETED
        }

        return [
            task for task in self.tasks
            if task.status == TaskStatus.PENDING and task.can_start(completed)
        ]

    def get_task(self, task_id: str) -> Task | None:
        """Get a task by ID."""
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None

    def mark_completed(self, task_id: str, result: Any = None) -> None:
        """Mark a task as completed."""
        task = self.get_task(task_id)
        if task:
            task.status = TaskStatus.COMPLETED
            task.result = result
            logger.info(f"Task completed: {task_id}")

    def mark_failed(self, task_id: str, error: str) -> None:
        """Mark a task as failed."""
        task = self.get_task(task_id)
        if task:
            task.status = TaskStatus.FAILED
            task.error = error
            logger.error(f"Task failed: {task_id} - {error}")

    def mark_in_progress(self, task_id: str) -> None:
        """Mark a task as in progress."""
        task = self.get_task(task_id)
        if task:
            task.status = TaskStatus.IN_PROGRESS
            logger.info(f"Task started: {task_id}")

    def is_complete(self) -> bool:
        """Check if all tasks are completed."""
        return all(
            task.status == TaskStatus.COMPLETED
            for task in self.tasks
        )

    def has_failures(self) -> bool:
        """Check if any tasks failed."""
        return any(
            task.status == TaskStatus.FAILED
            for task in self.tasks
        )

    def get_progress(self) -> tuple[int, int]:
        """Get (completed, total) task counts."""
        completed = sum(
            1 for task in self.tasks
            if task.status == TaskStatus.COMPLETED
        )
        return (completed, len(self.tasks))


class TaskComplexity(Enum):
    """Complexity level of a task."""
    SIMPLE = "simple"           # Single file, single operation
    MODERATE = "moderate"       # Multiple files, related operations
    COMPLEX = "complex"         # Multi-component, needs planning
    PROJECT = "project"         # Full project creation/transformation


class TaskPlanner:
    """
    Decomposes complex requests into executable tasks.

    Uses heuristics and optional LLM-based decomposition for complex projects.
    """

    # Project-level keywords that require structured planning
    PROJECT_KEYWORDS = [
        "create a project", "build a", "develop a", "implement a full",
        "turn it into", "transform into", "convert to",
        "loader", "injector", "bypass", "overlay system",
        "complete application", "full system", "entire project",
    ]

    # Multi-phase keywords
    PHASE_KEYWORDS = [
        "first", "then", "after that", "finally", "also",
        "multiple features", "several components",
        "phase 1", "phase 2", "step 1", "step 2",
    ]

    @staticmethod
    def analyze_complexity(request: str) -> TaskComplexity:
        """
        Analyze the complexity of a request.

        Returns:
            TaskComplexity enum indicating the level of planning needed.
        """
        request_lower = request.lower()

        # Check for project-level tasks
        for keyword in TaskPlanner.PROJECT_KEYWORDS:
            if keyword in request_lower:
                logger.info(f"Project-level task detected: '{keyword}'")
                return TaskComplexity.PROJECT

        # Count complexity indicators
        complexity_indicators = [
            " and then ", " after ", " before ",
            "implement", "test", "deploy", "document",
            "multiple", "several", "various",
            "refactor", "migrate", "upgrade",
            "enhance", "improve", "optimize",
            "add features", "new functionality",
        ]

        indicator_count = sum(
            1 for indicator in complexity_indicators
            if indicator in request_lower
        )

        # Check for multi-phase indicators
        phase_count = sum(
            1 for keyword in TaskPlanner.PHASE_KEYWORDS
            if keyword in request_lower
        )

        if phase_count >= 2 or indicator_count >= 4:
            return TaskComplexity.COMPLEX
        elif indicator_count >= 2:
            return TaskComplexity.MODERATE
        return TaskComplexity.SIMPLE

    @staticmethod
    def needs_decomposition(request: str) -> bool:
        """
        Determine if a request needs to be decomposed.

        Complex tasks typically involve:
        - Multiple files or operations
        - Sequential dependencies ("then", "after", "before")
        - Multiple verbs (implement, test, document, deploy)
        """
        complexity = TaskPlanner.analyze_complexity(request)
        return complexity in [TaskComplexity.COMPLEX, TaskComplexity.PROJECT]

    @staticmethod
    def create_simple_plan(description: str) -> TaskPlan:
        """Create a simple plan with a single task."""
        return TaskPlan(
            name="Simple Task",
            tasks=[
                Task(
                    id="task_1",
                    description=description,
                    status=TaskStatus.PENDING
                )
            ]
        )

    @staticmethod
    def decompose_task(request: str) -> TaskPlan:
        """
        Decompose a complex request into subtasks.

        This is a simple heuristic-based decomposition.
        In the future, this could use the LLM to create better plans.
        """
        request_lower = request.lower()
        tasks = []
        task_counter = 1

        # Common patterns for task decomposition

        # Pattern: "implement X and test it"
        if "implement" in request_lower and "test" in request_lower:
            tasks.append(Task(
                id=f"task_{task_counter}",
                description=f"Implement: {request}",
                dependencies=[]
            ))
            task_counter += 1

            tasks.append(Task(
                id=f"task_{task_counter}",
                description=f"Test: {request}",
                dependencies=[f"task_{task_counter-1}"]
            ))
            task_counter += 1

        # Pattern: "refactor X and update tests"
        elif "refactor" in request_lower:
            tasks.append(Task(
                id=f"task_{task_counter}",
                description=f"Analyze code to refactor",
                dependencies=[]
            ))
            task_counter += 1

            tasks.append(Task(
                id=f"task_{task_counter}",
                description=f"Perform refactoring",
                dependencies=[f"task_{task_counter-1}"]
            ))
            task_counter += 1

            if "test" in request_lower:
                tasks.append(Task(
                    id=f"task_{task_counter}",
                    description="Update tests",
                    dependencies=[f"task_{task_counter-1}"]
                ))
                task_counter += 1

        # Pattern: Files mentioned with different operations
        elif " and " in request_lower:
            # Split by "and" as a simple heuristic
            parts = request.split(" and ")
            for i, part in enumerate(parts):
                deps = [f"task_{i}"] if i > 0 else []
                tasks.append(Task(
                    id=f"task_{i+1}",
                    description=part.strip(),
                    dependencies=deps
                ))
            task_counter = len(parts) + 1

        # Default: create a simple plan
        if not tasks:
            return TaskPlanner.create_simple_plan(request)

        return TaskPlan(
            name=request[:50] + "..." if len(request) > 50 else request,
            tasks=tasks
        )

    @staticmethod
    def create_project_plan(
        request: str,
        project_type: str = "general",
        llm_client: Any = None,
    ) -> TaskPlan:
        """
        Create a comprehensive project plan for complex tasks.

        For project-level tasks like "turn this into a loader with overlay",
        creates a multi-phase plan with proper dependencies.

        Args:
            request: The user's request
            project_type: Type of project (game_mod, overlay, loader, etc.)
            llm_client: Optional LLM client for intelligent decomposition

        Returns:
            TaskPlan with phased execution plan
        """
        request_lower = request.lower()
        tasks = []
        task_id = 1

        # Determine project components from request
        has_loader = any(k in request_lower for k in ["loader", "injector", "bypass"])
        has_overlay = any(k in request_lower for k in ["overlay", "menu", "gui", "ui"])
        has_cleaning = any(k in request_lower for k in ["clean", "trace", "string", "anti-detection"])
        has_injection = any(k in request_lower for k in ["inject", "dll", "hook"])
        has_config = any(k in request_lower for k in ["config", "settings", "options"])

        # Phase 1: Analysis and Planning
        tasks.append(Task(
            id=f"task_{task_id}",
            description="Phase 1: Analyze existing codebase structure and identify components",
            status=TaskStatus.PENDING,
            dependencies=[]
        ))
        task_id += 1

        tasks.append(Task(
            id=f"task_{task_id}",
            description="Phase 1: Create project structure and directory layout",
            status=TaskStatus.PENDING,
            dependencies=[f"task_{task_id - 1}"]
        ))
        task_id += 1

        # Phase 2: Core Infrastructure
        if has_loader:
            tasks.append(Task(
                id=f"task_{task_id}",
                description="Phase 2: Implement loader/executor core with process handling",
                status=TaskStatus.PENDING,
                dependencies=[f"task_{task_id - 1}"]
            ))
            task_id += 1

        if has_injection:
            tasks.append(Task(
                id=f"task_{task_id}",
                description="Phase 2: Implement injection mechanism (DLL injection, memory writing)",
                status=TaskStatus.PENDING,
                dependencies=[f"task_{task_id - 1}"]
            ))
            task_id += 1

        # Phase 3: Features
        if has_overlay:
            tasks.append(Task(
                id=f"task_{task_id}",
                description="Phase 3: Create overlay window and rendering system",
                status=TaskStatus.PENDING,
                dependencies=[f"task_{task_id - 1}"]
            ))
            task_id += 1

            tasks.append(Task(
                id=f"task_{task_id}",
                description="Phase 3: Implement in-game menu and configuration UI",
                status=TaskStatus.PENDING,
                dependencies=[f"task_{task_id - 1}"]
            ))
            task_id += 1

        if has_config:
            tasks.append(Task(
                id=f"task_{task_id}",
                description="Phase 3: Implement configuration system (save/load settings)",
                status=TaskStatus.PENDING,
                dependencies=[f"task_{task_id - 1}"]
            ))
            task_id += 1

        # Phase 4: Security/Cleaning
        if has_cleaning:
            tasks.append(Task(
                id=f"task_{task_id}",
                description="Phase 4: Implement trace cleaning (memory, registry, logs)",
                status=TaskStatus.PENDING,
                dependencies=[f"task_{task_id - 1}"]
            ))
            task_id += 1

            tasks.append(Task(
                id=f"task_{task_id}",
                description="Phase 4: Add string obfuscation and anti-detection measures",
                status=TaskStatus.PENDING,
                dependencies=[f"task_{task_id - 1}"]
            ))
            task_id += 1

        # Phase 5: Integration and Testing
        tasks.append(Task(
            id=f"task_{task_id}",
            description="Phase 5: Integrate all components and test end-to-end",
            status=TaskStatus.PENDING,
            dependencies=[f"task_{task_id - 1}"]
        ))
        task_id += 1

        tasks.append(Task(
            id=f"task_{task_id}",
            description="Phase 5: Create build system and documentation",
            status=TaskStatus.PENDING,
            dependencies=[f"task_{task_id - 1}"]
        ))

        return TaskPlan(
            name=f"Project: {request[:40]}...",
            tasks=tasks
        )

    @staticmethod
    def get_current_phase_prompt(plan: TaskPlan) -> str:
        """
        Get a focused prompt for the current phase of execution.

        This helps the LLM focus on one phase at a time instead of
        being overwhelmed by the entire project scope.

        Returns:
            A prompt describing just the current phase to work on.
        """
        next_tasks = plan.get_next_tasks()

        if not next_tasks:
            completed, total = plan.get_progress()
            if completed == total:
                return "All phases complete! Summarize the work done."
            return "Waiting for blocked tasks to unblock."

        # Get current phase from task description
        current_task = next_tasks[0]
        phase_match = re.search(r'Phase (\d+):', current_task.description)
        phase_num = phase_match.group(1) if phase_match else "Current"

        # Get all tasks in this phase
        phase_tasks = [
            t for t in next_tasks
            if f"Phase {phase_num}:" in t.description
        ]

        prompt_parts = [
            f"## Current Phase: {phase_num}",
            f"Tasks to complete ({len(phase_tasks)}):",
        ]

        for task in phase_tasks:
            desc = task.description.replace(f"Phase {phase_num}: ", "")
            prompt_parts.append(f"- {desc}")

        prompt_parts.extend([
            "",
            "Focus ONLY on these tasks. Complete them before moving to the next phase.",
            "Use tools to implement each task, then report completion.",
        ])

        return "\n".join(prompt_parts)

    @staticmethod
    def format_plan_summary(plan: TaskPlan) -> str:
        """
        Format a plan summary for display or inclusion in prompts.
        """
        completed, total = plan.get_progress()
        lines = [
            f"## Project Plan: {plan.name}",
            f"Progress: {completed}/{total} tasks complete",
            "",
            "### Tasks:",
        ]

        for task in plan.tasks:
            status_icon = {
                TaskStatus.PENDING: "⏳",
                TaskStatus.IN_PROGRESS: "🔄",
                TaskStatus.COMPLETED: "✅",
                TaskStatus.FAILED: "❌",
                TaskStatus.BLOCKED: "🚫",
            }.get(task.status, "?")

            lines.append(f"{status_icon} {task.description}")

        return "\n".join(lines)
