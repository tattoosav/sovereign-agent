"""
Ollama LLM client.

Simple wrapper around the Ollama API for chat completions.
"""

import logging
import time
from dataclasses import dataclass
from typing import Callable, TypeVar

import httpx

logger = logging.getLogger(__name__)

T = TypeVar("T")


def retry_with_backoff(
    func: Callable[..., T],
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
) -> Callable[..., T]:
    """
    Retry a function with exponential backoff.

    Args:
        func: Function to retry
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds

    Returns:
        Wrapped function that retries on failure
    """
    def wrapper(*args: object, **kwargs: object) -> T:
        last_exception = None

        for attempt in range(max_retries + 1):
            try:
                return func(*args, **kwargs)
            except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as e:
                last_exception = e

                if attempt == max_retries:
                    logger.error(f"Max retries ({max_retries}) reached for {func.__name__}")
                    raise

                # Calculate delay with exponential backoff
                delay = min(base_delay * (2 ** attempt), max_delay)
                logger.warning(
                    f"Attempt {attempt + 1}/{max_retries + 1} failed for {func.__name__}: {e}. "
                    f"Retrying in {delay:.1f}s..."
                )
                time.sleep(delay)

        # This should never be reached, but satisfy type checker
        if last_exception:
            raise last_exception
        raise RuntimeError("Unexpected retry loop exit")

    return wrapper


@dataclass
class LLMResponse:
    """Response from the LLM."""
    content: str
    tokens_used: int
    model: str


class OllamaClient:
    """Client for Ollama API."""

    def __init__(
        self,
        model: str = "qwen2.5-coder:32b",
        base_url: str = "http://localhost:11434",
        timeout: float = 600.0,  # 10 minutes for very complex tasks
        max_retries: int = 5,    # More retries for reliability
        retry_delay: float = 2.0,
        context_window: int = 32768,  # Large context window for complex tasks
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.context_window = context_window
        self._client = httpx.Client(timeout=timeout)

        logger.info(
            f"Initialized OllamaClient: model={model}, url={base_url}, "
            f"timeout={timeout}s, max_retries={max_retries}, context={context_window}"
        )
    
    def generate(
        self,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 16384,  # 16K tokens for full file generation
    ) -> LLMResponse:
        """
        Generate a completion.

        Args:
            prompt: The user prompt
            system: System prompt (optional)
            temperature: Sampling temperature (lower = more deterministic)
            max_tokens: Maximum tokens to generate

        Returns:
            LLMResponse with the generated content
        """
        logger.debug(f"Generating completion with {len(prompt)} char prompt")

        def _do_generate() -> LLMResponse:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                    "num_ctx": self.context_window,  # Use full context window
                }
            }

            if system:
                payload["system"] = system

            response = self._client.post(
                f"{self.base_url}/api/generate",
                json=payload,
            )
            response.raise_for_status()

            data = response.json()

            return LLMResponse(
                content=data.get("response", ""),
                tokens_used=data.get("eval_count", 0),
                model=self.model,
            )

        # Wrap with retry logic
        retrying_generate = retry_with_backoff(
            _do_generate,
            max_retries=self.max_retries,
            base_delay=self.retry_delay,
        )

        return retrying_generate()
    
    def _truncate_messages(self, messages: list[dict[str, str]], max_chars: int = 100000) -> list[dict[str, str]]:
        """
        Truncate messages to fit within context window.

        Preserves system message and recent messages, summarizes older ones.
        """
        total_chars = sum(len(m.get("content", "")) for m in messages)

        if total_chars <= max_chars:
            return messages

        logger.warning(f"Truncating messages: {total_chars} chars -> {max_chars} chars")

        # Always keep system message (first) and most recent messages
        if len(messages) <= 3:
            # Just truncate content if very few messages
            return [
                {**m, "content": m.get("content", "")[:max_chars // len(messages)]}
                for m in messages
            ]

        # Keep system message
        result = [messages[0]]

        # Create summary of middle messages
        middle_messages = messages[1:-4]  # All but first and last 4
        recent_messages = messages[-4:]   # Keep last 4 verbatim

        if middle_messages:
            summary_parts = []
            for msg in middle_messages[-6:]:  # Summarize last 6 of middle
                role = msg.get("role", "")
                content = msg.get("content", "")[:200]  # First 200 chars
                if role == "user":
                    summary_parts.append(f"User: {content}...")
                elif role == "assistant":
                    # Extract key info
                    if "<tool" in content:
                        summary_parts.append("Assistant: [executed tools]")
                    else:
                        summary_parts.append(f"Assistant: {content[:100]}...")

            if summary_parts:
                result.append({
                    "role": "system",
                    "content": f"[Earlier conversation summary]\n" + "\n".join(summary_parts)
                })

        # Add recent messages
        result.extend(recent_messages)

        # Final safety truncation
        for i, msg in enumerate(result):
            if len(msg.get("content", "")) > 30000:
                result[i] = {**msg, "content": msg["content"][:30000] + "\n[...truncated...]"}

        return result

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 16384,
    ) -> LLMResponse:
        """
        Chat completion (multi-turn).

        Args:
            messages: List of {"role": "user"|"assistant"|"system", "content": "..."}
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Returns:
            LLMResponse with the generated content
        """
        logger.debug(f"Chat completion with {len(messages)} messages")

        # Truncate messages if needed to fit context window
        # Estimate: ~4 chars per token, leave room for response
        max_input_chars = (self.context_window - max_tokens) * 4
        messages = self._truncate_messages(messages, max_chars=max_input_chars)

        def _do_chat() -> LLMResponse:
            payload = {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                    "num_ctx": self.context_window,  # Set context window
                }
            }

            response = self._client.post(
                f"{self.base_url}/api/chat",
                json=payload,
            )
            response.raise_for_status()

            data = response.json()

            return LLMResponse(
                content=data.get("message", {}).get("content", ""),
                tokens_used=data.get("eval_count", 0),
                model=self.model,
            )

        # Wrap with retry logic
        retrying_chat = retry_with_backoff(
            _do_chat,
            max_retries=self.max_retries,
            base_delay=self.retry_delay,
        )

        return retrying_chat()

    def chat_stream(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 16384,
    ):
        """
        Streaming chat completion.

        Args:
            messages: List of {"role": "user"|"assistant"|"system", "content": "..."}
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Yields:
            Chunks of generated text as they arrive
        """
        import json

        logger.debug(f"Streaming chat completion with {len(messages)} messages")

        # Truncate messages if needed
        max_input_chars = (self.context_window - max_tokens) * 4
        messages = self._truncate_messages(messages, max_chars=max_input_chars)

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
                "num_ctx": self.context_window,  # Set context window
            }
        }

        with self._client.stream(
            "POST",
            f"{self.base_url}/api/chat",
            json=payload,
            timeout=self.timeout,
        ) as response:
            response.raise_for_status()

            for line in response.iter_lines():
                if line:
                    try:
                        data = json.loads(line)
                        content = data.get("message", {}).get("content", "")
                        if content:
                            yield content

                        # Check if done
                        if data.get("done", False):
                            break
                    except json.JSONDecodeError:
                        continue
    
    def is_available(self) -> bool:
        """Check if Ollama server is available."""
        try:
            response = self._client.get(f"{self.base_url}/api/tags")
            return response.status_code == 200
        except Exception:
            return False
    
    def model_exists(self) -> bool:
        """Check if the configured model is available."""
        try:
            response = self._client.get(f"{self.base_url}/api/tags")
            if response.status_code != 200:
                return False
            models = response.json().get("models", [])
            model_names = [m.get("name", "") for m in models]
            return self.model in model_names or any(
                self.model.split(":")[0] in name for name in model_names
            )
        except Exception:
            return False
    
    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()
    
    def __enter__(self) -> "OllamaClient":
        return self
    
    def __exit__(self, *args: object) -> None:
        self.close()
