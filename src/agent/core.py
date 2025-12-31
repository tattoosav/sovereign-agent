"""
Sovereign Agent Core

The main agent loop that:
1. Takes user input
2. Sends to LLM with tool definitions
3. Parses LLM output for tool calls
4. Executes tools
5. Feeds results back to LLM
6. Repeats until task is complete
"""

import re
import time
from dataclasses import dataclass, field
from typing import Any

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from src.tools import ToolRegistry, ToolResult
from .error_recovery import ErrorContext, ErrorRecoveryManager
from .llm import OllamaClient
from .metrics import AgentMetricsCollector
from .operation_cache import OperationCache
from .prompts import build_system_prompt
from .verification import ToolVerifier, VerificationStatus


@dataclass
class Message:
    """A message in the conversation."""
    role: str  # "user", "assistant", "system"
    content: str


@dataclass
class ParsedToolCall:
    """A parsed tool call from LLM output."""
    name: str
    params: dict[str, str]
    raw: str  # Original XML for reference


@dataclass
class AgentConfig:
    """Configuration for the agent."""
    model: str = "qwen2.5-coder:32b"
    ollama_url: str = "http://localhost:11434"
    max_iterations: int = 10  # Prevent infinite loops
    temperature: float = 0.1
    max_retries: int = 3
    retry_delay: float = 1.0


class Agent:
    """The main agent that orchestrates everything."""
    
    def __init__(
        self,
        config: AgentConfig | None = None,
        tools: ToolRegistry | None = None,
    ):
        self.config = config or AgentConfig()
        self.tools = tools or ToolRegistry()
        self.console = Console()
        self.llm = OllamaClient(
            model=self.config.model,
            base_url=self.config.ollama_url,
            max_retries=self.config.max_retries,
            retry_delay=self.config.retry_delay,
        )
        self.history: list[Message] = []
        self.verifier = ToolVerifier()
        self.op_cache = OperationCache()
        self.error_recovery = ErrorRecoveryManager()
        self.metrics = AgentMetricsCollector()
    
    def _parse_tool_calls(self, text: str) -> list[ParsedToolCall]:
        """
        Parse tool calls from LLM output.
        
        Format:
        <tool name="tool_name">
        <param name="param_name">value</param>
        </tool>
        """
        tool_calls = []
        
        # Find all tool blocks
        tool_pattern = r'<tool\s+name="([^"]+)">(.*?)</tool>'
        for match in re.finditer(tool_pattern, text, re.DOTALL):
            tool_name = match.group(1)
            tool_body = match.group(2)
            
            # Parse parameters
            params = {}
            param_pattern = r'<param\s+name="([^"]+)">(.*?)</param>'
            for param_match in re.finditer(param_pattern, tool_body, re.DOTALL):
                param_name = param_match.group(1)
                param_value = param_match.group(2).strip()
                params[param_name] = param_value
            
            tool_calls.append(ParsedToolCall(
                name=tool_name,
                params=params,
                raw=match.group(0),
            ))
        
        return tool_calls
    
    def _execute_tool(self, call: ParsedToolCall) -> ToolResult:
        """Execute a single tool call."""
        tool = self.tools.get(call.name)

        if tool is None:
            return ToolResult(
                success=False,
                output="",
                error=f"Unknown tool: {call.name}"
            )

        # Check cache first
        cached_result = self.op_cache.get(call.name, call.params)
        if cached_result is not None:
            self.console.print(f"[dim]  (cached)[/dim]")
            # Still record the call for metrics
            self.metrics.tool_metrics.record_call(call.name, True, 0.0)
            return cached_result

        # Execute and cache result with timing
        start_time = time.time()
        result = tool.execute(**call.params)
        duration = time.time() - start_time

        # Record metrics
        self.metrics.tool_metrics.record_call(call.name, result.success, duration)

        # Only cache successful results
        if result.success:
            self.op_cache.set(call.name, call.params, result)

        return result
    
    def _format_tool_result(self, call: ParsedToolCall, result: ToolResult) -> str:
        """Format a tool result for feeding back to the LLM."""
        status = "success" if result.success else "error"
        content = result.output if result.success else (result.error or "Unknown error")
        
        return f"""<tool_result name="{call.name}" status="{status}">
{content}
</tool_result>"""
    
    def run_turn(self, user_input: str) -> str:
        """
        Run a single turn of the agent.
        
        This may involve multiple LLM calls if tools are used.
        """
        # Add user message to history
        self.history.append(Message(role="user", content=user_input))
        
        # Build system prompt with tools
        system_prompt = build_system_prompt(self.tools.get_prompt_block())
        
        iteration = 0
        accumulated_response = ""
        
        while iteration < self.config.max_iterations:
            iteration += 1

            # Reset iteration cache tracking
            self.op_cache.reset_iteration()

            # Build messages for LLM
            messages = [{"role": "system", "content": system_prompt}]
            for msg in self.history:
                messages.append({"role": msg.role, "content": msg.content})
            
            # Get LLM response with timing
            self.console.print(f"[dim]Thinking... (iteration {iteration})[/dim]")

            try:
                llm_start = time.time()
                response = self.llm.chat(
                    messages=messages,
                    temperature=self.config.temperature,
                )
                llm_duration = time.time() - llm_start

                # Record LLM metrics
                self.metrics.llm_metrics.record_call(
                    success=True,
                    duration=llm_duration,
                    response_length=len(response.content)
                )
            except Exception as e:
                self.metrics.llm_metrics.record_call(success=False, duration=0.0)
                error_msg = f"LLM error: {e}"
                self.console.print(f"[red]{error_msg}[/red]")
                return error_msg

            llm_output = response.content
            accumulated_response += llm_output
            
            # Parse for tool calls
            tool_calls = self._parse_tool_calls(llm_output)
            
            if not tool_calls:
                # No tool calls, we're done
                self.metrics.iteration_metrics.record_iteration(
                    had_tools=False,
                    completed_early=True,
                    hit_max=False
                )
                self.history.append(Message(role="assistant", content=accumulated_response))
                return accumulated_response
            
            # Execute tools and collect results
            tool_results_text = ""
            for call in tool_calls:
                self.console.print(f"[cyan]Executing tool: {call.name}[/cyan]")
                result = self._execute_tool(call)

                if result.success:
                    self.console.print(f"[green]OK {call.name} succeeded[/green]")
                else:
                    self.console.print(f"[red]FAIL {call.name} failed: {result.error}[/red]")

                    # Error recovery
                    error_ctx = ErrorContext(
                        tool_name=call.name,
                        error_message=result.error or "Unknown error",
                        params=call.params
                    )
                    self.error_recovery.record_error(error_ctx)

                    # Get recovery suggestions
                    recovery_actions = self.error_recovery.suggest_recovery(error_ctx)
                    recovery_text = self.error_recovery.format_recovery_suggestions(recovery_actions)

                    # Add recovery suggestions to result
                    if result.output:
                        result.output += f"\n\n[Error Recovery]\n{recovery_text}"
                    else:
                        result.output = f"[Error Recovery]\n{recovery_text}"

                # Verify the result
                verification = self.verifier.verify(call.name, call.params, result)

                if verification.status == VerificationStatus.FAILED:
                    self.console.print(f"[yellow]WARN Verification failed: {verification.message}[/yellow]")
                    # Add verification suggestions to the tool result
                    if verification.suggestions:
                        suggestions_text = "\n".join(f"- {s}" for s in verification.suggestions)
                        result.output += f"\n\n[Verification Suggestions]\n{suggestions_text}"
                elif verification.status == VerificationStatus.PASSED:
                    self.console.print(f"[dim]Verified: {verification.message}[/dim]")

                tool_results_text += self._format_tool_result(call, result) + "\n"
            
            # Record iteration with tools
            self.metrics.iteration_metrics.record_iteration(
                had_tools=True,
                completed_early=False,
                hit_max=False
            )

            # Add assistant response and tool results to history
            self.history.append(Message(role="assistant", content=llm_output))
            self.history.append(Message(role="user", content=f"Tool results:\n{tool_results_text}"))

            accumulated_response += f"\n\n[Tool results received, continuing...]\n\n"

        # Hit max iterations
        self.metrics.iteration_metrics.record_iteration(
            had_tools=False,
            completed_early=False,
            hit_max=True
        )
        warning = f"\n\n[Warning: Reached maximum iterations ({self.config.max_iterations})]"
        accumulated_response += warning
        self.history.append(Message(role="assistant", content=accumulated_response))

        return accumulated_response
    
    def display_response(self, response: str) -> None:
        """Display the agent's response nicely."""
        # Remove tool XML for display
        display_text = re.sub(r'<tool[^>]*>.*?</tool>', '[tool call]', response, flags=re.DOTALL)
        display_text = re.sub(r'<tool_result[^>]*>.*?</tool_result>', '', display_text, flags=re.DOTALL)
        
        self.console.print(Panel(
            Markdown(display_text.strip()),
            title="Agent",
            border_style="blue",
        ))
    
    def reset(self) -> None:
        """Clear conversation history."""
        self.history.clear()
    
    def get_verification_metrics(self) -> dict[str, Any]:
        """Get verification metrics."""
        return self.verifier.get_metrics()

    def display_verification_metrics(self) -> None:
        """Display verification statistics."""
        metrics = self.get_verification_metrics()
        if metrics["total_checks"] > 0:
            self.console.print("\n[bold cyan]Verification Metrics[/bold cyan]")
            self.console.print(f"  Total checks: {metrics['total_checks']}")
            self.console.print(f"  Passed: [green]{metrics['passed']}[/green]")
            self.console.print(f"  Failed: [red]{metrics['failed']}[/red]")
            self.console.print(f"  Skipped: [dim]{metrics['skipped']}[/dim]")
            self.console.print(f"  Success rate: [bold]{metrics['success_rate']}%[/bold]")

    def get_cache_stats(self) -> dict[str, Any]:
        """Get operation cache statistics."""
        return self.op_cache.get_stats()

    def display_cache_stats(self) -> None:
        """Display operation cache statistics."""
        stats = self.get_cache_stats()
        if stats["total_operations"] > 0:
            self.console.print("\n[bold cyan]Operation Cache Stats[/bold cyan]")
            self.console.print(f"  Total operations: {stats['total_operations']}")
            self.console.print(f"  Cache hits: [green]{stats['cache_hits']}[/green]")
            self.console.print(f"  Cache misses: [yellow]{stats['cache_misses']}[/yellow]")
            self.console.print(f"  Unique operations: {stats['unique_operations']}")
            self.console.print(f"  Hit rate: [bold]{stats['hit_rate']}%[/bold]")
            self.console.print(f"  Cache size: {stats['cache_size']}/{stats['max_size']}")

    def display_comprehensive_metrics(self) -> None:
        """Display comprehensive performance metrics."""
        report = self.metrics.get_comprehensive_report(
            verification_metrics=self.verifier.get_metrics(),
            cache_stats=self.op_cache.get_stats(),
            error_stats=self.error_recovery.get_error_stats()
        )

        # Use the metrics collector's built-in formatter
        formatted = self.metrics.format_report(report)
        self.console.print(formatted)

    def close(self) -> None:
        """Clean up resources."""
        self.llm.close()
