"""
Memory and knowledge management system.

Provides long-term memory, vector storage, and RAG capabilities.
"""

from src.memory.vector_store import VectorStore
from src.memory.codebase_index import CodebaseIndexer
from src.memory.knowledge_base import KnowledgeBase
from src.memory.file_watcher import FileWatcher, IndexingFileWatcher
from src.memory.conversation_store import ConversationStore, ConversationSession
from src.agent.pattern_learner import PatternLearner

__all__ = [
    "VectorStore",
    "CodebaseIndexer",
    "KnowledgeBase",
    "FileWatcher",
    "IndexingFileWatcher",
    "ConversationStore",
    "ConversationSession",
    "PatternLearner",
]
