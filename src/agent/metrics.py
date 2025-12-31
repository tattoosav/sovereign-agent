"""
Comprehensive Metrics and Monitoring System

Tracks all agent performance metrics in one place:
- Tool execution stats
- Verification metrics
- Cache performance
- Error recovery stats
- LLM usage
- Iteration efficiency
"""

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolExecutionMetrics:
    """Metrics for tool execution."""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    total_execution_time: float = 0.0
    by_tool: dict[str, int] = field(default_factory=dict)

    def record_call(self, tool_name: str, success: bool, duration: float) -> None:
        """Record a tool call."""
        self.total_calls += 1
        if success:
            self.successful_calls += 1
        else:
            self.failed_calls += 1
        self.total_execution_time += duration

        # Track by tool
        if tool_name not in self.by_tool:
            self.by_tool[tool_name] = 0
        self.by_tool[tool_name] += 1

    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_calls == 0:
            return 0.0
        return self.successful_calls / self.total_calls

    def avg_execution_time(self) -> float:
        """Calculate average execution time."""
        if self.total_calls == 0:
            return 0.0
        return self.total_execution_time / self.total_calls


@dataclass
class IterationMetrics:
    """Metrics for agent iterations."""
    total_iterations: int = 0
    iterations_with_tools: int = 0
    iterations_without_tools: int = 0
    max_iterations_reached: int = 0
    early_completions: int = 0

    def record_iteration(self, had_tools: bool, completed_early: bool, hit_max: bool) -> None:
        """Record an iteration."""
        self.total_iterations += 1
        if had_tools:
            self.iterations_with_tools += 1
        else:
            self.iterations_without_tools += 1

        if completed_early:
            self.early_completions += 1
        if hit_max:
            self.max_iterations_reached += 1


@dataclass
class LLMMetrics:
    """Metrics for LLM usage."""
    total_calls: int = 0
    total_tokens_estimated: int = 0  # Rough estimate
    successful_calls: int = 0
    failed_calls: int = 0
    total_llm_time: float = 0.0

    def record_call(self, success: bool, duration: float, response_length: int = 0) -> None:
        """Record an LLM call."""
        self.total_calls += 1
        if success:
            self.successful_calls += 1
        else:
            self.failed_calls += 1
        self.total_llm_time += duration

        # Rough token estimate (4 chars ≈ 1 token)
        self.total_tokens_estimated += response_length // 4

    def avg_llm_time(self) -> float:
        """Calculate average LLM response time."""
        if self.total_calls == 0:
            return 0.0
        return self.total_llm_time / self.total_calls


class AgentMetricsCollector:
    """Centralized metrics collection for the agent."""

    def __init__(self) -> None:
        self.session_start = time.time()
        self.tool_metrics = ToolExecutionMetrics()
        self.iteration_metrics = IterationMetrics()
        self.llm_metrics = LLMMetrics()

    def get_session_duration(self) -> float:
        """Get session duration in seconds."""
        return time.time() - self.session_start

    def get_comprehensive_report(
        self,
        verification_metrics: dict[str, Any] | None = None,
        cache_stats: dict[str, Any] | None = None,
        error_stats: dict[str, Any] | None = None,
        parallel_stats: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Generate comprehensive metrics report."""
        report = {
            "session": {
                "duration_seconds": round(self.get_session_duration(), 2),
                "duration_formatted": self._format_duration(self.get_session_duration())
            },
            "tools": {
                "total_calls": self.tool_metrics.total_calls,
                "successful": self.tool_metrics.successful_calls,
                "failed": self.tool_metrics.failed_calls,
                "success_rate": round(self.tool_metrics.success_rate() * 100, 2),
                "avg_execution_time": round(self.tool_metrics.avg_execution_time(), 3),
                "by_tool": self.tool_metrics.by_tool,
                "most_used": self._get_most_used_tool()
            },
            "iterations": {
                "total": self.iteration_metrics.total_iterations,
                "with_tools": self.iteration_metrics.iterations_with_tools,
                "without_tools": self.iteration_metrics.iterations_without_tools,
                "early_completions": self.iteration_metrics.early_completions,
                "max_iterations_hit": self.iteration_metrics.max_iterations_reached
            },
            "llm": {
                "total_calls": self.llm_metrics.total_calls,
                "successful": self.llm_metrics.successful_calls,
                "failed": self.llm_metrics.failed_calls,
                "avg_response_time": round(self.llm_metrics.avg_llm_time(), 2),
                "estimated_tokens": self.llm_metrics.total_tokens_estimated
            }
        }

        # Add optional metrics
        if verification_metrics:
            report["verification"] = verification_metrics

        if cache_stats:
            report["cache"] = cache_stats

        if error_stats:
            report["errors"] = error_stats

        if parallel_stats:
            report["parallel"] = parallel_stats

        # Calculate efficiency score
        report["efficiency"] = self._calculate_efficiency_score(cache_stats, parallel_stats)

        return report

    def _get_most_used_tool(self) -> str | None:
        """Get the most frequently used tool."""
        if not self.tool_metrics.by_tool:
            return None
        return max(self.tool_metrics.by_tool.items(), key=lambda x: x[1])[0]

    def _format_duration(self, seconds: float) -> str:
        """Format duration as human-readable string."""
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f}m"
        else:
            hours = seconds / 3600
            return f"{hours:.1f}h"

    def _calculate_efficiency_score(
        self,
        cache_stats: dict[str, Any] | None,
        parallel_stats: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Calculate overall efficiency score."""
        score = 100.0

        # Deduct for failed operations
        if self.tool_metrics.total_calls > 0:
            failure_rate = self.tool_metrics.failed_calls / self.tool_metrics.total_calls
            score -= failure_rate * 20  # Max -20 points

        # Deduct for hitting max iterations
        if self.iteration_metrics.total_iterations > 0:
            max_hit_rate = self.iteration_metrics.max_iterations_reached / self.iteration_metrics.total_iterations
            score -= max_hit_rate * 30  # Max -30 points

        # Bonus for cache hits
        if cache_stats and cache_stats.get("total_operations", 0) > 0:
            cache_hit_rate = cache_stats.get("hit_rate", 0) / 100
            score += cache_hit_rate * 10  # Max +10 points

        # Bonus for early completions
        if self.iteration_metrics.total_iterations > 0:
            early_rate = self.iteration_metrics.early_completions / self.iteration_metrics.total_iterations
            score += early_rate * 10  # Max +10 points

        # Bonus for parallel execution time saved
        if parallel_stats and parallel_stats.get("time_saved", 0) > 0:
            score += min(parallel_stats["time_saved"] * 2, 10)  # Max +10 points

        return {
            "score": round(max(0, min(100, score)), 1),
            "grade": self._score_to_grade(score)
        }

    def _score_to_grade(self, score: float) -> str:
        """Convert score to letter grade."""
        if score >= 90:
            return "A"
        elif score >= 80:
            return "B"
        elif score >= 70:
            return "C"
        elif score >= 60:
            return "D"
        else:
            return "F"

    def format_report(self, report: dict[str, Any]) -> str:
        """Format metrics report for display."""
        lines = []

        lines.append("=" * 60)
        lines.append("AGENT PERFORMANCE REPORT")
        lines.append("=" * 60)

        # Session info
        lines.append(f"\nSession Duration: {report['session']['duration_formatted']}")

        # Tool metrics
        tools = report['tools']
        lines.append(f"\nTool Execution:")
        lines.append(f"  Total calls: {tools['total_calls']}")
        lines.append(f"  Success rate: {tools['success_rate']}%")
        lines.append(f"  Avg execution time: {tools['avg_execution_time']}s")
        if tools['most_used']:
            lines.append(f"  Most used tool: {tools['most_used']}")

        # Iteration metrics
        iters = report['iterations']
        lines.append(f"\nIterations:")
        lines.append(f"  Total: {iters['total']}")
        lines.append(f"  Early completions: {iters['early_completions']}")
        lines.append(f"  Max iterations hit: {iters['max_iterations_hit']}")

        # LLM metrics
        llm = report['llm']
        lines.append(f"\nLLM Usage:")
        lines.append(f"  Total calls: {llm['total_calls']}")
        lines.append(f"  Avg response time: {llm['avg_response_time']}s")
        lines.append(f"  Estimated tokens: ~{llm['estimated_tokens']}")

        # Cache metrics
        if 'cache' in report:
            cache = report['cache']
            lines.append(f"\nCache Performance:")
            lines.append(f"  Hit rate: {cache.get('hit_rate', 0)}%")
            lines.append(f"  Total operations: {cache.get('total_operations', 0)}")
            lines.append(f"  Cache hits: {cache.get('cache_hits', 0)}")

        # Verification metrics
        if 'verification' in report:
            verif = report['verification']
            lines.append(f"\nVerification:")
            lines.append(f"  Success rate: {verif.get('success_rate', 0)}%")
            lines.append(f"  Total checks: {verif.get('total_checks', 0)}")

        # Error metrics
        if 'errors' in report:
            errors = report['errors']
            lines.append(f"\nErrors:")
            lines.append(f"  Total: {errors.get('total_errors', 0)}")
            if errors.get('most_common_type'):
                lines.append(f"  Most common: {errors['most_common_type']}")

        # Parallel execution metrics
        if 'parallel' in report:
            parallel = report['parallel']
            lines.append(f"\nParallel Execution:")
            lines.append(f"  Parallel batches: {parallel.get('parallel_batches', 0)}")
            lines.append(f"  Parallel calls: {parallel.get('total_parallel_calls', 0)}")
            lines.append(f"  Sequential calls: {parallel.get('total_sequential_calls', 0)}")
            time_saved = parallel.get('time_saved', 0)
            if time_saved > 0:
                lines.append(f"  Time saved: {time_saved:.2f}s")

        # Efficiency score
        eff = report['efficiency']
        lines.append(f"\nEfficiency Score: {eff['score']}/100 (Grade: {eff['grade']})")

        lines.append("=" * 60)

        return "\n".join(lines)
