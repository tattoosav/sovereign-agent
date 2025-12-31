"""Session management for web API."""

import logging
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from typing import Any

from src.agent import AgentV2, AgentConfigV2
from src.core import load_config
from src.memory import KnowledgeBase, VectorStore
from src.tools import (
    CodeSearchTool,
    GitTool,
    ListDirectoryTool,
    ReadFileTool,
    ShellTool,
    StrReplaceTool,
    ToolRegistry,
    WriteFileTool,
)

logger = logging.getLogger(__name__)


@dataclass
class Session:
    """Represents an active user session."""
    id: str
    agent: AgentV2
    created_at: float
    last_accessed: float
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


class SessionManager:
    """Manages user sessions and their agents."""

    def __init__(
        self,
        max_sessions: int = 10,
        session_timeout: float = 3600.0,  # 1 hour
    ):
        self._sessions: dict[str, Session] = {}
        self._lock = Lock()
        self.max_sessions = max_sessions
        self.session_timeout = session_timeout
        self._config = load_config()

    def _setup_tools(self, working_dir: Path) -> ToolRegistry:
        """Set up the tool registry with all available tools."""
        registry = ToolRegistry()
        allowed_paths = [working_dir]

        registry.register(ReadFileTool(allowed_paths=allowed_paths))
        registry.register(WriteFileTool(allowed_paths=allowed_paths))
        registry.register(ListDirectoryTool(allowed_paths=allowed_paths))
        registry.register(StrReplaceTool(allowed_paths=allowed_paths))
        registry.register(CodeSearchTool(allowed_paths=allowed_paths))
        registry.register(GitTool(allowed_paths=allowed_paths))
        registry.register(ShellTool(
            timeout=30,
            blocked_commands=["rm -rf /", "rm -rf ~", "mkfs", "dd if="],
        ))

        return registry

    def _create_agent(self) -> AgentV2:
        """Create a new v2 agent instance with full intelligence features."""
        working_dir = Path(self._config.agent.working_dir) if self._config.agent.working_dir else Path.cwd()
        tools = self._setup_tools(working_dir)

        # Initialize memory systems
        vector_store = VectorStore()
        knowledge_base = KnowledgeBase()

        agent_config = AgentConfigV2(
            model=self._config.llm.model,
            ollama_url=self._config.llm.ollama_url,
            max_iterations=self._config.agent.max_iterations,
            temperature=self._config.llm.temperature,
            max_retries=self._config.llm.max_retries,
            retry_delay=self._config.llm.retry_delay,
            # v2 features enabled
            enable_routing=True,
            enable_rag=True,
            enable_planning=True,
            enable_learning=True,
        )

        return AgentV2(
            config=agent_config,
            tools=tools,
            vector_store=vector_store,
            knowledge_base=knowledge_base,
        )

    def _cleanup_expired(self) -> None:
        """Remove expired sessions."""
        current_time = time.time()
        expired = [
            session_id
            for session_id, session in self._sessions.items()
            if current_time - session.last_accessed > self.session_timeout
        ]
        for session_id in expired:
            self._remove_session(session_id)
            logger.info(f"Removed expired session: {session_id}")

    def _remove_session(self, session_id: str) -> None:
        """Remove a session and cleanup its agent."""
        if session_id in self._sessions:
            session = self._sessions.pop(session_id)
            session.agent.close()

    def create_session(self) -> str:
        """Create a new session and return its ID."""
        with self._lock:
            # Cleanup expired sessions first
            self._cleanup_expired()

            # Check max sessions limit
            if len(self._sessions) >= self.max_sessions:
                # Remove oldest session
                oldest_id = min(
                    self._sessions.keys(),
                    key=lambda x: self._sessions[x].last_accessed
                )
                self._remove_session(oldest_id)
                logger.info(f"Removed oldest session to make room: {oldest_id}")

            # Create new session
            session_id = str(uuid.uuid4())
            agent = self._create_agent()

            self._sessions[session_id] = Session(
                id=session_id,
                agent=agent,
                created_at=time.time(),
                last_accessed=time.time(),
            )

            logger.info(f"Created new session: {session_id}")
            return session_id

    def get_session(self, session_id: str) -> Session | None:
        """Get a session by ID, updating its last accessed time."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session.last_accessed = time.time()
            return session

    def get_or_create_session(self, session_id: str | None) -> Session:
        """Get existing session or create a new one."""
        if session_id:
            session = self.get_session(session_id)
            if session:
                return session

        new_id = self.create_session()
        return self._sessions[new_id]

    def reset_session(self, session_id: str) -> bool:
        """Reset a session's conversation history."""
        session = self.get_session(session_id)
        if session:
            session.agent.reset()
            session.tool_calls.clear()
            logger.info(f"Reset session: {session_id}")
            return True
        return False

    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        with self._lock:
            if session_id in self._sessions:
                self._remove_session(session_id)
                logger.info(f"Deleted session: {session_id}")
                return True
            return False

    def get_active_count(self) -> int:
        """Get the number of active sessions."""
        with self._lock:
            self._cleanup_expired()
            return len(self._sessions)

    def check_ollama(self) -> bool:
        """Check if Ollama is available."""
        # Create a temporary agent to check
        try:
            agent = self._create_agent()
            available = agent.llm.is_available()
            agent.close()
            return available
        except Exception:
            return False

    def close_all(self) -> None:
        """Close all sessions."""
        with self._lock:
            for session_id in list(self._sessions.keys()):
                self._remove_session(session_id)
            logger.info("Closed all sessions")
