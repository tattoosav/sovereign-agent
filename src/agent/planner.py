"""
Task planning and decomposition.

Breaks complex tasks into smaller, executable steps with dependencies.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

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


class TaskPlanner:
    """
    Decomposes complex requests into executable tasks.

    Uses heuristics to determine if a task needs decomposition.
    """

    @staticmethod
    def needs_decomposition(request: str) -> bool:
        """
        Determine if a request needs to be decomposed.

        Complex tasks typically involve:
        - Multiple files or operations
        - Sequential dependencies ("then", "after", "before")
        - Multiple verbs (implement, test, document, deploy)
        """
        request_lower = request.lower()

        # Keywords indicating complexity
        complexity_indicators = [
            " and then ", " after ", " before ",
            "first", "second", "third", "finally",
            "implement", "test", "deploy", "document",
            "multiple", "several", "various",
            "refactor", "migrate", "upgrade",
        ]

        # Count indicators
        indicator_count = sum(
            1 for indicator in complexity_indicators
            if indicator in request_lower
        )

        # Simple heuristic: 2+ indicators = complex task
        return indicator_count >= 2

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
