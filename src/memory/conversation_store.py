"""
Conversation Persistence System.

Saves and loads conversation history, allowing sessions to be
resumed across restarts. Includes summarization for long histories.
"""

import json
import logging
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any
import hashlib

logger = logging.getLogger(__name__)


@dataclass
class ConversationMessage:
    """A single message in a conversation."""
    role: str  # "user", "assistant", "system"
    content: str
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConversationMessage":
        return cls(**data)


@dataclass
class ConversationSession:
    """A complete conversation session."""
    session_id: str
    messages: list[ConversationMessage] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    summary: str = ""  # Summary of older messages
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_message(self, role: str, content: str, **metadata: Any) -> None:
        """Add a message to the conversation."""
        self.messages.append(ConversationMessage(
            role=role,
            content=content,
            metadata=metadata,
        ))
        self.updated_at = time.time()

    def get_recent_messages(self, count: int = 10) -> list[ConversationMessage]:
        """Get the most recent messages."""
        return self.messages[-count:]

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "messages": [m.to_dict() for m in self.messages],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "summary": self.summary,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConversationSession":
        messages = [ConversationMessage.from_dict(m) for m in data.get("messages", [])]
        return cls(
            session_id=data["session_id"],
            messages=messages,
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            summary=data.get("summary", ""),
            metadata=data.get("metadata", {}),
        )


class ConversationStore:
    """
    Persistent storage for conversation sessions.

    Features:
    - Save/load sessions to disk
    - Automatic summarization of old messages
    - Session search and listing
    - Cleanup of old sessions
    """

    def __init__(
        self,
        storage_dir: Path | str = ".sovereign/conversations",
        max_messages_before_summary: int = 20,
        auto_save: bool = True,
    ):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.max_messages_before_summary = max_messages_before_summary
        self.auto_save = auto_save

        # In-memory cache
        self._sessions: dict[str, ConversationSession] = {}
        self._stats = {
            "sessions_loaded": 0,
            "sessions_saved": 0,
            "messages_stored": 0,
        }

        logger.info(f"ConversationStore initialized at {self.storage_dir}")

    def _get_session_path(self, session_id: str) -> Path:
        """Get the file path for a session."""
        # Use hash prefix for directory sharding
        hash_prefix = hashlib.md5(session_id.encode()).hexdigest()[:2]
        session_dir = self.storage_dir / hash_prefix
        session_dir.mkdir(exist_ok=True)
        return session_dir / f"{session_id}.json"

    def create_session(self, session_id: str | None = None) -> ConversationSession:
        """Create a new conversation session."""
        if session_id is None:
            session_id = f"session_{int(time.time() * 1000)}"

        session = ConversationSession(session_id=session_id)
        self._sessions[session_id] = session

        if self.auto_save:
            self.save_session(session_id)

        logger.info(f"Created new session: {session_id}")
        return session

    def get_session(self, session_id: str) -> ConversationSession | None:
        """Get a session by ID, loading from disk if needed."""
        # Check cache first
        if session_id in self._sessions:
            return self._sessions[session_id]

        # Try to load from disk
        session_path = self._get_session_path(session_id)
        if session_path.exists():
            return self.load_session(session_id)

        return None

    def save_session(self, session_id: str) -> bool:
        """Save a session to disk."""
        session = self._sessions.get(session_id)
        if not session:
            return False

        session_path = self._get_session_path(session_id)
        try:
            with open(session_path, "w", encoding="utf-8") as f:
                json.dump(session.to_dict(), f, indent=2, ensure_ascii=False)

            self._stats["sessions_saved"] += 1
            self._stats["messages_stored"] = sum(
                len(s.messages) for s in self._sessions.values()
            )
            logger.debug(f"Saved session: {session_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to save session {session_id}: {e}")
            return False

    def load_session(self, session_id: str) -> ConversationSession | None:
        """Load a session from disk."""
        session_path = self._get_session_path(session_id)
        if not session_path.exists():
            return None

        try:
            with open(session_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            session = ConversationSession.from_dict(data)
            self._sessions[session_id] = session
            self._stats["sessions_loaded"] += 1
            logger.debug(f"Loaded session: {session_id}")
            return session

        except Exception as e:
            logger.error(f"Failed to load session {session_id}: {e}")
            return None

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        **metadata: Any
    ) -> bool:
        """Add a message to a session."""
        session = self.get_session(session_id)
        if not session:
            session = self.create_session(session_id)

        session.add_message(role, content, **metadata)

        # Check if we need to summarize
        if len(session.messages) > self.max_messages_before_summary:
            self._summarize_old_messages(session)

        if self.auto_save:
            self.save_session(session_id)

        return True

    def _summarize_old_messages(self, session: ConversationSession) -> None:
        """Summarize older messages to reduce context size."""
        if len(session.messages) <= self.max_messages_before_summary:
            return

        # Keep the most recent messages
        keep_count = self.max_messages_before_summary // 2
        old_messages = session.messages[:-keep_count]
        session.messages = session.messages[-keep_count:]

        # Create a simple summary of old messages
        old_summary_parts = []
        for msg in old_messages:
            if msg.role == "user":
                # Truncate long messages
                content = msg.content[:200] + "..." if len(msg.content) > 200 else msg.content
                old_summary_parts.append(f"User asked: {content}")
            elif msg.role == "assistant":
                # Just note that assistant responded
                old_summary_parts.append("Assistant responded with solution/explanation")

        # Combine with existing summary
        new_summary = "\n".join(old_summary_parts[-10:])  # Keep last 10 summary items
        if session.summary:
            session.summary = f"{session.summary}\n---\n{new_summary}"
        else:
            session.summary = new_summary

        logger.info(f"Summarized {len(old_messages)} old messages in session {session.session_id}")

    def list_sessions(self, limit: int = 50) -> list[dict[str, Any]]:
        """List all available sessions."""
        sessions = []

        # Scan storage directory
        for hash_dir in self.storage_dir.iterdir():
            if not hash_dir.is_dir():
                continue
            for session_file in hash_dir.glob("*.json"):
                try:
                    with open(session_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    sessions.append({
                        "session_id": data["session_id"],
                        "created_at": data.get("created_at", 0),
                        "updated_at": data.get("updated_at", 0),
                        "message_count": len(data.get("messages", [])),
                    })
                except Exception:
                    continue

        # Sort by updated_at descending
        sessions.sort(key=lambda x: x["updated_at"], reverse=True)
        return sessions[:limit]

    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        # Remove from cache
        self._sessions.pop(session_id, None)

        # Remove from disk
        session_path = self._get_session_path(session_id)
        try:
            if session_path.exists():
                session_path.unlink()
            logger.info(f"Deleted session: {session_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete session {session_id}: {e}")
            return False

    def cleanup_old_sessions(self, max_age_days: int = 30) -> int:
        """Delete sessions older than max_age_days."""
        cutoff = time.time() - (max_age_days * 24 * 60 * 60)
        deleted = 0

        for session_info in self.list_sessions(limit=1000):
            if session_info["updated_at"] < cutoff:
                if self.delete_session(session_info["session_id"]):
                    deleted += 1

        logger.info(f"Cleaned up {deleted} old sessions")
        return deleted

    def search_sessions(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Search sessions by content."""
        results = []
        query_lower = query.lower()

        for session_info in self.list_sessions(limit=100):
            session = self.load_session(session_info["session_id"])
            if not session:
                continue

            # Search in messages
            for msg in session.messages:
                if query_lower in msg.content.lower():
                    results.append({
                        **session_info,
                        "match_preview": msg.content[:100],
                    })
                    break

            if len(results) >= limit:
                break

        return results

    def get_stats(self) -> dict[str, Any]:
        """Get storage statistics."""
        return {
            **self._stats,
            "cached_sessions": len(self._sessions),
            "storage_dir": str(self.storage_dir),
        }

    def export_session(self, session_id: str, format: str = "json") -> str | None:
        """Export a session to a string."""
        session = self.get_session(session_id)
        if not session:
            return None

        if format == "json":
            return json.dumps(session.to_dict(), indent=2)
        elif format == "markdown":
            lines = [f"# Conversation: {session_id}\n"]
            lines.append(f"Created: {time.ctime(session.created_at)}\n")
            if session.summary:
                lines.append(f"## Summary\n{session.summary}\n")
            lines.append("## Messages\n")
            for msg in session.messages:
                role = msg.role.capitalize()
                lines.append(f"### {role}\n{msg.content}\n")
            return "\n".join(lines)

        return None
