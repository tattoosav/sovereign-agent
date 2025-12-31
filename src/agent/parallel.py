"""
Parallel Tool Execution System.

Allows the agent to execute multiple independent tools concurrently
for better performance on multi-tool operations.
"""

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Callable

from src.tools import BaseTool, ToolResult

logger = logging.getLogger(__name__)


@dataclass
class ParallelToolCall:
    """A tool call to be executed in parallel."""
    name: str
    params: dict[str, Any]
    tool: BaseTool


@dataclass
class ParallelResult:
    """Result of parallel tool execution."""
    name: str
    params: dict[str, Any]
    result: ToolResult
    duration: float


@dataclass
class ParallelExecutionResult:
    """Result of a batch of parallel tool executions."""
    results: list[ParallelResult]
    total_duration: float
    parallel_speedup: float  # Ratio of sequential time to parallel time


class ParallelExecutor:
    """
    Execute multiple tools in parallel using a thread pool.

    Analyzes tool calls for independence and groups them for
    concurrent execution when safe.
    """

    def __init__(
        self,
        max_workers: int = 4,
        timeout: float = 60.0,
    ):
        """
        Initialize parallel executor.

        Args:
            max_workers: Maximum concurrent tool executions
            timeout: Timeout for each tool execution in seconds
        """
        self.max_workers = max_workers
        self.timeout = timeout
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._stats = {
            "parallel_batches": 0,
            "total_parallel_calls": 0,
            "total_sequential_calls": 0,
            "time_saved": 0.0,
        }

        logger.info(f"Initialized ParallelExecutor with {max_workers} workers")

    def can_parallelize(self, calls: list[ParallelToolCall]) -> bool:
        """
        Determine if a set of tool calls can be safely parallelized.

        Tools are safe to parallelize when:
        - They don't write to the same files
        - They don't depend on each other's output
        - They are read-only operations

        Args:
            calls: List of tool calls to check

        Returns:
            True if calls can be parallelized safely
        """
        if len(calls) <= 1:
            return False

        # Read-only tools that are always safe to parallelize
        read_only_tools = {
            "read_file",
            "list_directory",
            "code_search",
            "search_and_read",
            "explore_directory",
            "git_status_diff",
        }

        # Check if all tools are read-only
        all_read_only = all(call.name in read_only_tools for call in calls)
        if all_read_only:
            return True

        # Check for file path conflicts in write operations
        write_tools = {"write_file", "str_replace", "edit_and_verify"}
        write_paths = set()

        for call in calls:
            if call.name in write_tools:
                path = call.params.get("path", "")
                if path in write_paths:
                    # Conflict: multiple writes to same file
                    logger.debug(f"Cannot parallelize: conflict on {path}")
                    return False
                write_paths.add(path)

        # If we have writes, check they don't conflict with reads
        for call in calls:
            if call.name == "read_file":
                path = call.params.get("path", "")
                if path in write_paths:
                    # Read after write - needs to be sequential
                    logger.debug(f"Cannot parallelize: read after write on {path}")
                    return False

        return True

    def group_for_parallel(
        self,
        calls: list[ParallelToolCall]
    ) -> list[list[ParallelToolCall]]:
        """
        Group tool calls into batches that can be executed in parallel.

        Args:
            calls: List of all tool calls

        Returns:
            List of batches, where each batch can be parallelized
        """
        if not calls:
            return []

        batches = []
        current_batch = []

        for call in calls:
            test_batch = current_batch + [call]
            if self.can_parallelize(test_batch):
                current_batch.append(call)
            else:
                # Current call conflicts - start new batch
                if current_batch:
                    batches.append(current_batch)
                current_batch = [call]

        # Don't forget the last batch
        if current_batch:
            batches.append(current_batch)

        logger.debug(f"Grouped {len(calls)} calls into {len(batches)} batches")
        return batches

    def _execute_single(self, call: ParallelToolCall) -> ParallelResult:
        """Execute a single tool call."""
        start_time = time.time()

        try:
            result = call.tool.execute(**call.params)
        except Exception as e:
            logger.error(f"Tool {call.name} failed: {e}")
            result = ToolResult(
                success=False,
                output="",
                error=str(e),
            )

        duration = time.time() - start_time

        return ParallelResult(
            name=call.name,
            params=call.params,
            result=result,
            duration=duration,
        )

    def execute_parallel(
        self,
        calls: list[ParallelToolCall]
    ) -> ParallelExecutionResult:
        """
        Execute a batch of tool calls in parallel.

        Args:
            calls: List of tool calls to execute

        Returns:
            ParallelExecutionResult with all results
        """
        if not calls:
            return ParallelExecutionResult(
                results=[],
                total_duration=0.0,
                parallel_speedup=1.0,
            )

        start_time = time.time()
        results = []

        if len(calls) == 1:
            # Single call, no parallelization needed
            result = self._execute_single(calls[0])
            results.append(result)
            self._stats["total_sequential_calls"] += 1
        else:
            # Submit all calls to thread pool
            futures = {}
            for call in calls:
                future = self._executor.submit(self._execute_single, call)
                futures[future] = call

            # Collect results as they complete
            for future in as_completed(futures, timeout=self.timeout):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    call = futures[future]
                    logger.error(f"Parallel execution failed for {call.name}: {e}")
                    results.append(ParallelResult(
                        name=call.name,
                        params=call.params,
                        result=ToolResult(success=False, output="", error=str(e)),
                        duration=0.0,
                    ))

            self._stats["parallel_batches"] += 1
            self._stats["total_parallel_calls"] += len(calls)

        total_duration = time.time() - start_time

        # Calculate theoretical sequential time
        sequential_time = sum(r.duration for r in results)
        parallel_speedup = sequential_time / total_duration if total_duration > 0 else 1.0

        # Track time saved
        time_saved = sequential_time - total_duration
        if time_saved > 0:
            self._stats["time_saved"] += time_saved

        logger.info(
            f"Parallel execution: {len(calls)} calls in {total_duration:.2f}s "
            f"(speedup: {parallel_speedup:.2f}x)"
        )

        return ParallelExecutionResult(
            results=results,
            total_duration=total_duration,
            parallel_speedup=parallel_speedup,
        )

    def execute_grouped(
        self,
        calls: list[ParallelToolCall]
    ) -> list[ParallelResult]:
        """
        Execute tool calls with automatic grouping for parallelization.

        Groups calls that can be safely parallelized and executes
        each group concurrently.

        Args:
            calls: List of all tool calls

        Returns:
            List of results in order
        """
        batches = self.group_for_parallel(calls)
        all_results = []

        for batch in batches:
            batch_result = self.execute_parallel(batch)
            all_results.extend(batch_result.results)

        return all_results

    def get_stats(self) -> dict[str, Any]:
        """Get execution statistics."""
        return {
            **self._stats,
            "max_workers": self.max_workers,
        }

    def reset_stats(self) -> None:
        """Reset statistics."""
        self._stats = {
            "parallel_batches": 0,
            "total_parallel_calls": 0,
            "total_sequential_calls": 0,
            "time_saved": 0.0,
        }

    def close(self) -> None:
        """Shut down the thread pool."""
        self._executor.shutdown(wait=True)


class AsyncParallelExecutor:
    """
    Async version of parallel executor for use with async frameworks.

    Uses asyncio for coordination with thread pool for actual execution.
    """

    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self._sync_executor = ParallelExecutor(max_workers=max_workers)

    async def execute_parallel(
        self,
        calls: list[ParallelToolCall]
    ) -> ParallelExecutionResult:
        """Execute tools in parallel asynchronously."""
        loop = asyncio.get_event_loop()

        # Run in thread pool to not block event loop
        result = await loop.run_in_executor(
            None,
            self._sync_executor.execute_parallel,
            calls,
        )

        return result

    async def execute_grouped(
        self,
        calls: list[ParallelToolCall]
    ) -> list[ParallelResult]:
        """Execute with automatic grouping asynchronously."""
        loop = asyncio.get_event_loop()

        result = await loop.run_in_executor(
            None,
            self._sync_executor.execute_grouped,
            calls,
        )

        return result

    def get_stats(self) -> dict[str, Any]:
        """Get execution statistics."""
        return self._sync_executor.get_stats()

    def close(self) -> None:
        """Clean up resources."""
        self._sync_executor.close()
