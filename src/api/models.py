"""Pydantic models for API request/response schemas."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ChatRequest:
    """Request body for chat endpoint."""
    message: str
    session_id: str | None = None


@dataclass
class ToolCall:
    """Represents a tool call made during response generation."""
    name: str
    params: dict[str, Any]
    result: str
    success: bool


@dataclass
class ChatResponse:
    """Response body for chat endpoint."""
    response: str
    session_id: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    status: str = "success"
    error: str | None = None


@dataclass
class SessionResponse:
    """Response for session operations."""
    session_id: str
    message: str


@dataclass
class HistoryMessage:
    """A message in conversation history."""
    role: str
    content: str


@dataclass
class HistoryResponse:
    """Response for history endpoint."""
    session_id: str
    messages: list[HistoryMessage]


@dataclass
class ToolInfo:
    """Information about an available tool."""
    name: str
    description: str
    parameters: dict[str, Any]


@dataclass
class ToolsResponse:
    """Response for tools endpoint."""
    tools: list[ToolInfo]


@dataclass
class MetricsResponse:
    """Response for metrics endpoint."""
    session_id: str
    metrics: dict[str, Any]


@dataclass
class HealthResponse:
    """Response for health check endpoint."""
    status: str
    ollama_connected: bool
    active_sessions: int
