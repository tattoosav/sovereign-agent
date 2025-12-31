"""
Sovereign Agent Core v2 - Enhanced with Intelligence Integration.

This version integrates:
- Dynamic model routing
- RAG context retrieval
- Dynamic prompting
- Task decomposition
- Conversation optimization
- Feedback loops
"""

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from src.memory.knowledge_base import KnowledgeBase
from src.memory.vector_store import VectorStore
from src.tools import ToolRegistry, ToolResult

from .context import ContextManager, RetrievedContext
from .error_recovery import ErrorContext, ErrorRecoveryManager
from .llm import OllamaClient
from .metrics import AgentMetricsCollector
from .operation_cache import OperationCache
from .planner import TaskPlanner, TaskStatus
from .prompts_v2 import (
    PromptContext,
    TaskType,
    build_dynamic_prompt,
    detect_task_type,
)
from .router import ModelRouter, ModelSize
from .verification import ToolVerifier, VerificationStatus
from .parallel import ParallelExecutor, ParallelToolCall

logger = logging.getLogger(__name__)


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
    raw: str


@dataclass
class AgentConfig:
    """Configuration for the agent."""
    model: str = "qwen2.5-coder:14b"  # Default, but router may override
    ollama_url: str = "http://localhost:11434"
    max_iterations: int = 25  # Increased for complex multi-file tasks
    temperature: float = 0.1
    max_retries: int = 3
    retry_delay: float = 1.0
    # v2 features
    enable_routing: bool = True      # Dynamic model selection
    enable_rag: bool = True          # Context retrieval
    enable_planning: bool = True     # Task decomposition
    enable_learning: bool = True     # Store successful solutions
    max_history_messages: int = 20   # Before summarization kicks in (increased for better context)
    enable_parallel: bool = True     # Parallel tool execution
    parallel_workers: int = 4        # Max concurrent tool executions


@dataclass
class TurnResult:
    """Result of a single agent turn."""
    response: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    model_used: str = ""
    task_type: TaskType = TaskType.GENERAL
    tokens_used: int = 0
    iterations: int = 0


class AgentV2:
    """
    Enhanced Agent with full intelligence integration.

    New features over v1:
    - Dynamic model routing based on task complexity
    - RAG context retrieval before each turn
    - Task-specific prompting
    - Task decomposition for complex requests
    - Conversation summarization
    - Learning from successful solutions
    """

    def __init__(
        self,
        config: AgentConfig | None = None,
        tools: ToolRegistry | None = None,
        vector_store: VectorStore | None = None,
        knowledge_base: KnowledgeBase | None = None,
    ):
        self.config = config or AgentConfig()
        self.tools = tools or ToolRegistry()
        self.console = Console()

        # Core LLM client (model may be switched per-turn)
        self.llm = OllamaClient(
            model=self.config.model,
            base_url=self.config.ollama_url,
            max_retries=self.config.max_retries,
            retry_delay=self.config.retry_delay,
        )

        # Conversation state
        self.history: list[Message] = []

        # Intelligence components
        self.context_manager = ContextManager(
            vector_store=vector_store,
            knowledge_base=knowledge_base,
        )
        self.planner = TaskPlanner()
        self.verifier = ToolVerifier()
        self.op_cache = OperationCache()
        self.error_recovery = ErrorRecoveryManager()
        self.metrics = AgentMetricsCollector()

        # Parallel execution
        self.parallel_executor = ParallelExecutor(
            max_workers=self.config.parallel_workers
        ) if self.config.enable_parallel else None

        # Track current task info
        self._current_model: str = self.config.model
        self._current_task_type: TaskType = TaskType.GENERAL
        self._turn_tool_calls: list[dict[str, Any]] = []
        self._error_history: list[str] = []
        self._recent_tool_calls: list[str] = []  # For loop detection
        self._empty_search_count: int = 0  # Track unproductive searches
        self._files_discovered: set[str] = set()  # Track what we've found

    def _select_model(self, task: str) -> str:
        """
        Select the appropriate model for the task.

        Uses the router if enabled, otherwise uses default model.
        """
        if not self.config.enable_routing:
            return self.config.model

        # Calculate context size from history
        context_size = sum(len(msg.content) for msg in self.history)

        # Get model from router
        model = ModelRouter.get_model_for_task(task, context_size)

        if model != self._current_model:
            logger.info(f"Switching model: {self._current_model} -> {model}")
            self._current_model = model
            # Update LLM client
            self.llm = OllamaClient(
                model=model,
                base_url=self.config.ollama_url,
                max_retries=self.config.max_retries,
                retry_delay=self.config.retry_delay,
            )

        return model

    def _get_model_size(self) -> ModelSize:
        """Get the current model size enum."""
        if "7b" in self._current_model.lower():
            return ModelSize.SMALL
        elif "32b" in self._current_model.lower():
            return ModelSize.LARGE
        return ModelSize.MEDIUM

    def _retrieve_context(self, task: str) -> RetrievedContext:
        """Retrieve relevant context for the task."""
        if not self.config.enable_rag:
            return RetrievedContext()

        return self.context_manager.retrieve_context(task)

    def _build_prompt(self, task: str, retrieved_context: RetrievedContext) -> str:
        """Build the dynamic system prompt."""
        # Get conversation summary if history is long
        conversation_summary = ""
        if len(self.history) > self.config.max_history_messages:
            messages = [{"role": m.role, "content": m.content} for m in self.history]
            conversation_summary = self.context_manager.summarize_conversation(messages)

        # Build error history string
        error_history = ""
        if self._error_history:
            error_history = "\n".join(self._error_history[-3:])  # Last 3 errors

        # Performance hint based on metrics
        performance_hint = ""
        if self.metrics.iteration_metrics.max_iterations_reached > 2:
            performance_hint = "Warning: You've hit max iterations multiple times. Be more decisive."

        context = PromptContext(
            task=task,
            task_type=self._current_task_type,
            model_size=self._get_model_size(),
            tools_block=self.tools.get_prompt_block(),
            retrieved_context=retrieved_context.to_prompt_section(),
            conversation_summary=conversation_summary,
            error_history=error_history,
            performance_hint=performance_hint,
        )

        return build_dynamic_prompt(context)

    def _parse_tool_calls(self, text: str) -> list[ParsedToolCall]:
        """Parse tool calls from LLM output."""
        tool_calls = []

        tool_pattern = r'<tool\s+name="([^"]+)">(.*?)</tool>'
        for match in re.finditer(tool_pattern, text, re.DOTALL):
            tool_name = match.group(1)
            tool_body = match.group(2)

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

    def _infer_path_from_context(self) -> str | None:
        """Try to infer a project path from recent conversation context."""
        # Look for paths mentioned in recent messages
        for msg in reversed(self.history[-10:]):  # Check more messages
            content = msg.content
            # Look for /tmp/sovereign_ paths (uploaded projects) - tempfile adds random suffix
            # Format: /tmp/sovereign_abc12345_xyz789 or similar
            match = re.search(r'/tmp/sovereign_[a-zA-Z0-9_]+', content)
            if match:
                logger.info(f"Found sovereign path in context: {match.group(0)}")
                return match.group(0)
            # Look for any /tmp path that might be a project directory
            match = re.search(r'/tmp/[a-zA-Z0-9_-]+', content)
            if match:
                logger.info(f"Found tmp path in context: {match.group(0)}")
                return match.group(0)
            # Look for explicit path mentions
            match = re.search(r'(?:files are at|project at|uploaded to|path is)[:\s]+([/\w_-]+)', content, re.IGNORECASE)
            if match:
                logger.info(f"Found explicit path mention: {match.group(1)}")
                return match.group(1)
        logger.warning("Could not infer path from context")
        return None

    def _validate_tool_call(self, call: ParsedToolCall) -> tuple[bool, str]:
        """
        Validate a tool call before execution.

        Returns:
            (is_valid, error_message) tuple
        """
        tool = self.tools.get(call.name)
        if tool is None:
            return False, f"Unknown tool: {call.name}"

        # Check required parameters
        missing_params = []
        for param_name, param_info in tool.parameters.items():
            if param_info.get("required", False):
                if param_name not in call.params or not call.params[param_name]:
                    missing_params.append(param_name)

        if missing_params:
            param_list = ", ".join(missing_params)
            # Provide specific guidance for common tools
            guidance = ""
            if call.name == "str_replace":
                guidance = "\n\nFor str_replace, you MUST provide:\n- path: file to edit\n- old_str: exact text to find (copy from read_file output)\n- new_str: replacement text"
            elif call.name == "write_file":
                guidance = "\n\nFor write_file, you MUST provide:\n- path: file to create/overwrite\n- content: complete file contents"

            return False, f"Missing required parameters: {param_list}{guidance}"

        return True, ""

    def _execute_tool(self, call: ParsedToolCall) -> ToolResult:
        """Execute a single tool call with caching."""
        tool = self.tools.get(call.name)

        if tool is None:
            return ToolResult(
                success=False,
                output="",
                error=f"Unknown tool: {call.name}"
            )

        # Validate tool call before execution
        is_valid, validation_error = self._validate_tool_call(call)
        if not is_valid:
            logger.warning(f"Invalid tool call {call.name}: {validation_error}")
            return ToolResult(
                success=False,
                output="",
                error=validation_error
            )

        # Auto-fill missing path parameter for filesystem tools
        if call.name in ["list_directory", "read_file", "code_search"] and "path" not in call.params:
            inferred_path = self._infer_path_from_context()
            if inferred_path:
                call.params["path"] = inferred_path
                logger.info(f"Auto-filled missing path parameter: {inferred_path}")

        # Check cache
        cached_result = self.op_cache.get(call.name, call.params)
        if cached_result is not None:
            self.console.print(f"[dim]  (cached)[/dim]")
            self.metrics.tool_metrics.record_call(call.name, True, 0.0)
            return cached_result

        # Execute
        start_time = time.time()
        result = tool.execute(**call.params)
        duration = time.time() - start_time

        # Record metrics
        self.metrics.tool_metrics.record_call(call.name, result.success, duration)

        # Cache successful results
        if result.success:
            self.op_cache.set(call.name, call.params, result)

        # Track tool call
        self._turn_tool_calls.append({
            "name": call.name,
            "params": call.params,
            "success": result.success,
            "duration": duration,
        })

        return result

    def _format_tool_result(self, call: ParsedToolCall, result: ToolResult) -> str:
        """Format a tool result for the LLM."""
        status = "success" if result.success else "error"
        content = result.output if result.success else (result.error or "Unknown error")

        return f"""<tool_result name="{call.name}" status="{status}">
{content}
</tool_result>"""

    def _execute_tools_parallel(
        self,
        calls: list[ParsedToolCall]
    ) -> list[tuple[ParsedToolCall, ToolResult]]:
        """
        Execute multiple tool calls in parallel when possible.

        Returns list of (call, result) tuples in original order.
        """
        if not calls:
            return []

        # If parallel execution disabled or only one call, use sequential
        if not self.parallel_executor or len(calls) == 1:
            return [(call, self._execute_tool(call)) for call in calls]

        # Convert to ParallelToolCall format
        parallel_calls = []
        for call in calls:
            tool = self.tools.get(call.name)
            if tool:
                parallel_calls.append(ParallelToolCall(
                    name=call.name,
                    params=call.params,
                    tool=tool,
                ))

        # Check if parallelization is possible
        if not self.parallel_executor.can_parallelize(parallel_calls):
            self.console.print("[dim]  (sequential execution - dependencies detected)[/dim]")
            return [(call, self._execute_tool(call)) for call in calls]

        # Execute in parallel
        self.console.print(f"[cyan]Executing {len(calls)} tools in parallel...[/cyan]")
        execution_result = self.parallel_executor.execute_parallel(parallel_calls)

        # Map results back to original calls
        results = []
        for i, call in enumerate(calls):
            if i < len(execution_result.results):
                parallel_result = execution_result.results[i]
                result = parallel_result.result

                # Record metrics
                self.metrics.tool_metrics.record_call(
                    call.name,
                    result.success,
                    parallel_result.duration
                )

                # Cache successful results
                if result.success:
                    self.op_cache.set(call.name, call.params, result)

                # Track tool call
                self._turn_tool_calls.append({
                    "name": call.name,
                    "params": call.params,
                    "success": result.success,
                    "duration": parallel_result.duration,
                })

                results.append((call, result))
            else:
                # Fallback to sequential if something went wrong
                results.append((call, self._execute_tool(call)))

        self.console.print(
            f"[green]Parallel execution complete "
            f"({execution_result.parallel_speedup:.1f}x speedup)[/green]"
        )

        return results

    def run_turn(self, user_input: str) -> TurnResult:
        """
        Run a single turn of the enhanced agent.

        This orchestrates:
        1. Model selection
        2. Context retrieval
        3. Dynamic prompting
        4. Tool execution loop
        5. Learning from success

        Returns:
            TurnResult with response and metadata
        """
        self._turn_tool_calls = []
        self._recent_tool_calls = []  # Reset loop detection
        self._empty_search_count = 0  # Reset unproductive search counter
        self._files_discovered = set()  # Reset discovered files
        total_tokens = 0

        # Detect task type
        self._current_task_type = detect_task_type(user_input)
        self.console.print(f"[dim]Task type: {self._current_task_type.value}[/dim]")

        # Select model based on task complexity
        model_used = self._select_model(user_input)
        self.console.print(f"[dim]Using model: {model_used}[/dim]")

        # Retrieve relevant context
        retrieved_context = self._retrieve_context(user_input)
        if not retrieved_context.is_empty():
            self.console.print(f"[dim]Retrieved context: {len(retrieved_context.relevant_code)} code, {len(retrieved_context.past_solutions)} solutions[/dim]")

        # Add user message to history
        self.history.append(Message(role="user", content=user_input))

        # Build dynamic prompt
        system_prompt = self._build_prompt(user_input, retrieved_context)

        iteration = 0
        accumulated_response = ""

        while iteration < self.config.max_iterations:
            iteration += 1
            self.op_cache.reset_iteration()

            # Build messages (with history optimization)
            messages = [{"role": "system", "content": system_prompt}]

            # Optimize history if too long
            history_messages = [{"role": m.role, "content": m.content} for m in self.history]
            if len(history_messages) > self.config.max_history_messages:
                history_messages = self.context_manager.get_optimized_history(
                    history_messages,
                    max_messages=self.config.max_history_messages
                )

            messages.extend(history_messages)

            # Get LLM response
            self.console.print(f"[dim]Thinking... (iteration {iteration})[/dim]")

            try:
                llm_start = time.time()
                response = self.llm.chat(
                    messages=messages,
                    temperature=self.config.temperature,
                )
                llm_duration = time.time() - llm_start

                total_tokens += response.tokens_used
                self.metrics.llm_metrics.record_call(
                    success=True,
                    duration=llm_duration,
                    response_length=len(response.content)
                )

            except Exception as e:
                self.metrics.llm_metrics.record_call(success=False, duration=0.0)
                error_msg = f"LLM error: {e}"
                self.console.print(f"[red]{error_msg}[/red]")
                self._error_history.append(f"LLM failed: {e}")
                return TurnResult(
                    response=error_msg,
                    model_used=model_used,
                    task_type=self._current_task_type,
                    iterations=iteration,
                )

            llm_output = response.content
            accumulated_response += llm_output

            # Debug: Log raw LLM output to see what tools it's generating
            logger.debug(f"Raw LLM output: {llm_output[:500]}...")

            # Parse tool calls
            tool_calls = self._parse_tool_calls(llm_output)

            # Debug: Log parsed tool calls
            for tc in tool_calls:
                logger.info(f"Parsed tool call: {tc.name} with params: {tc.params}")

            # Loop detection - check if we're repeating the same tool calls
            if tool_calls:
                current_call_sig = "|".join(f"{tc.name}:{sorted(tc.params.items())}" for tc in tool_calls)
                self._recent_tool_calls.append(current_call_sig)

                # Check for loops (same call 3+ times in last 5 iterations)
                if len(self._recent_tool_calls) >= 3:
                    recent = self._recent_tool_calls[-5:]
                    if recent.count(current_call_sig) >= 3:
                        logger.warning(f"Loop detected: {tool_calls[0].name} called repeatedly")
                        self.console.print(f"[yellow]Loop detected - breaking out of repeated {tool_calls[0].name} calls[/yellow]")

                        # Force completion with what we have
                        self.history.append(Message(role="assistant", content=accumulated_response))
                        return TurnResult(
                            response=accumulated_response + "\n\n[Warning: Detected repetitive behavior, stopping early]",
                            tool_calls=self._turn_tool_calls,
                            model_used=model_used,
                            task_type=self._current_task_type,
                            tokens_used=total_tokens,
                            iterations=iteration,
                        )

            # Check for unproductive exploration (many empty searches)
            if self._empty_search_count >= 4:
                logger.warning(f"Unproductive exploration: {self._empty_search_count} empty searches")
                self.console.print(f"[yellow]Many searches found nothing - synthesizing from available data[/yellow]")

                # Inject guidance to synthesize
                synthesis_prompt = f"""
You've searched extensively but many patterns weren't found.
Files discovered so far: {', '.join(list(self._files_discovered)[:20]) if self._files_discovered else 'See directory listings above'}

STOP SEARCHING. Instead:
1. Summarize what you DID find from the directory listings and any files you read
2. Describe the project based on available evidence
3. If you couldn't find specific patterns, say so and explain what the project likely is based on the file structure
"""
                accumulated_response += f"\n\n{synthesis_prompt}"
                self._empty_search_count = 0  # Reset to give it one more chance

            # Force synthesis after too many iterations
            if iteration >= 10 and self._current_task_type == TaskType.EXPLORE:
                logger.info(f"Forcing synthesis at iteration {iteration}")
                self.console.print(f"[yellow]Iteration {iteration} - time to synthesize findings[/yellow]")
                accumulated_response += "\n\n**Time to synthesize:** You've explored enough. Provide your analysis now based on what you found."

            if not tool_calls:
                # No tools, task complete
                self.metrics.iteration_metrics.record_iteration(
                    had_tools=False,
                    completed_early=True,
                    hit_max=False
                )
                self.history.append(Message(role="assistant", content=accumulated_response))

                # Learn from success if enabled
                if self.config.enable_learning and len(self._turn_tool_calls) > 0:
                    tools_used = list(set(tc["name"] for tc in self._turn_tool_calls))
                    self.context_manager.learn_from_success(
                        task=user_input,
                        solution=accumulated_response[:500],
                        tools_used=tools_used,
                    )

                return TurnResult(
                    response=accumulated_response,
                    tool_calls=self._turn_tool_calls,
                    model_used=model_used,
                    task_type=self._current_task_type,
                    tokens_used=total_tokens,
                    iterations=iteration,
                )

            # Execute tools (with parallel execution when possible)
            tool_results_text = ""

            # Try parallel execution for multiple tools
            if len(tool_calls) > 1 and self.parallel_executor:
                executed_tools = self._execute_tools_parallel(tool_calls)
            else:
                # Single tool or parallel disabled - execute sequentially
                executed_tools = []
                for call in tool_calls:
                    self.console.print(f"[cyan]Executing tool: {call.name}[/cyan]")
                    result = self._execute_tool(call)
                    executed_tools.append((call, result))

            # Process results (verification, error recovery)
            for call, result in executed_tools:
                if result.success:
                    self.console.print(f"[green]OK {call.name} succeeded[/green]")

                    # Track productive vs unproductive results
                    if call.name == "code_search":
                        if "No matches found" in result.output or not result.output.strip():
                            self._empty_search_count += 1
                            logger.info(f"Empty search #{self._empty_search_count}")
                    elif call.name == "list_directory":
                        # Extract files from directory listing for context
                        for line in result.output.split('\n'):
                            if line.strip():
                                self._files_discovered.add(line.strip())
                    elif call.name == "read_file":
                        # Successful file read - good progress
                        self._empty_search_count = max(0, self._empty_search_count - 1)
                else:
                    self.console.print(f"[red]FAIL {call.name} failed: {result.error}[/red]")
                    self._error_history.append(f"{call.name} failed: {result.error}")

                    # Error recovery
                    error_ctx = ErrorContext(
                        tool_name=call.name,
                        error_message=result.error or "Unknown error",
                        params=call.params
                    )
                    self.error_recovery.record_error(error_ctx)
                    recovery_actions = self.error_recovery.suggest_recovery(error_ctx)
                    recovery_text = self.error_recovery.format_recovery_suggestions(recovery_actions)

                    if result.output:
                        result.output += f"\n\n[Error Recovery]\n{recovery_text}"
                    else:
                        result.output = f"[Error Recovery]\n{recovery_text}"

                # Verify result
                verification = self.verifier.verify(call.name, call.params, result)

                if verification.status == VerificationStatus.FAILED:
                    self.console.print(f"[yellow]WARN Verification failed: {verification.message}[/yellow]")
                    if verification.suggestions:
                        suggestions_text = "\n".join(f"- {s}" for s in verification.suggestions)
                        result.output += f"\n\n[Verification Suggestions]\n{suggestions_text}"
                elif verification.status == VerificationStatus.PASSED:
                    self.console.print(f"[dim]Verified: {verification.message}[/dim]")

                tool_results_text += self._format_tool_result(call, result) + "\n"

            # Record iteration
            self.metrics.iteration_metrics.record_iteration(
                had_tools=True,
                completed_early=False,
                hit_max=False
            )

            # Add to history
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

        return TurnResult(
            response=accumulated_response,
            tool_calls=self._turn_tool_calls,
            model_used=model_used,
            task_type=self._current_task_type,
            tokens_used=total_tokens,
            iterations=iteration,
        )

    def display_response(self, response: str) -> None:
        """Display the agent's response nicely."""
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
        self._error_history.clear()
        self._turn_tool_calls.clear()

    def get_verification_metrics(self) -> dict[str, Any]:
        """Get verification metrics."""
        return self.verifier.get_metrics()

    def get_cache_stats(self) -> dict[str, Any]:
        """Get operation cache statistics."""
        return self.op_cache.get_stats()

    def display_comprehensive_metrics(self) -> None:
        """Display comprehensive performance metrics."""
        parallel_stats = self.parallel_executor.get_stats() if self.parallel_executor else {}
        report = self.metrics.get_comprehensive_report(
            verification_metrics=self.verifier.get_metrics(),
            cache_stats=self.op_cache.get_stats(),
            error_stats=self.error_recovery.get_error_stats(),
            parallel_stats=parallel_stats,
        )
        formatted = self.metrics.format_report(report)
        self.console.print(formatted)

    def get_parallel_stats(self) -> dict[str, Any]:
        """Get parallel execution statistics."""
        if self.parallel_executor:
            return self.parallel_executor.get_stats()
        return {}

    def close(self) -> None:
        """Clean up resources."""
        self.llm.close()
        if self.parallel_executor:
            self.parallel_executor.close()
