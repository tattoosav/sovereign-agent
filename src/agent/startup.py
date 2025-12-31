"""
Startup and initialization routines for Sovereign Agent.

Handles:
- Codebase auto-indexing
- Model availability checks
- Memory system initialization
- Background tasks
- File watching for auto-reindexing
"""

import logging
import threading
import time
from pathlib import Path
from typing import Any, Callable

from src.memory.codebase_index import CodebaseIndexer
from src.memory.knowledge_base import KnowledgeBase
from src.memory.vector_store import VectorStore
from src.memory.file_watcher import IndexingFileWatcher

from .router import ModelRouter

logger = logging.getLogger(__name__)


class StartupManager:
    """
    Manages agent startup tasks and background operations.
    """

    def __init__(
        self,
        working_dir: Path,
        vector_store: VectorStore | None = None,
        knowledge_base: KnowledgeBase | None = None,
        ollama_url: str = "http://localhost:11434",
        enable_file_watcher: bool = True,
    ):
        self.working_dir = working_dir
        self.vector_store = vector_store or VectorStore()
        self.knowledge_base = knowledge_base or KnowledgeBase()
        self.ollama_url = ollama_url
        self.enable_file_watcher = enable_file_watcher

        self.indexer = CodebaseIndexer(self.vector_store)
        self.file_watcher: IndexingFileWatcher | None = None
        self._index_thread: threading.Thread | None = None
        self._indexing_complete = threading.Event()
        self._status: dict[str, Any] = {
            "indexing": False,
            "indexed_files": 0,
            "models_checked": False,
            "available_models": [],
            "file_watcher_running": False,
        }

    def initialize(self, blocking: bool = False) -> dict[str, Any]:
        """
        Run all initialization tasks.

        Args:
            blocking: If True, wait for all tasks to complete

        Returns:
            Status dict with initialization results
        """
        logger.info("Starting agent initialization...")

        # Check available models (always blocking, fast)
        self._check_models()

        # Start codebase indexing
        if blocking:
            self._index_codebase_sync()
        else:
            self._start_background_indexing()

        # Start file watcher for auto-reindexing
        if self.enable_file_watcher:
            self._start_file_watcher()

        return self.get_status()

    def _start_file_watcher(self) -> None:
        """Start the file watcher for auto-reindexing."""
        if self.file_watcher:
            return

        try:
            self.file_watcher = IndexingFileWatcher(
                watch_paths=[self.working_dir],
                indexer=self.indexer,
                poll_interval=5.0,
            )
            self.file_watcher.start()
            self._status["file_watcher_running"] = True
            logger.info(f"File watcher started for {self.working_dir}")
        except Exception as e:
            logger.error(f"Failed to start file watcher: {e}")
            self._status["file_watcher_running"] = False

    def stop_file_watcher(self) -> None:
        """Stop the file watcher."""
        if self.file_watcher:
            self.file_watcher.stop()
            self.file_watcher = None
            self._status["file_watcher_running"] = False
            logger.info("File watcher stopped")

    def _check_models(self) -> None:
        """Check available Ollama models."""
        ModelRouter.set_ollama_url(self.ollama_url)
        available = ModelRouter.get_available_models()
        self._status["models_checked"] = True
        self._status["available_models"] = list(available)
        logger.info(f"Available models: {available}")

    def _index_codebase_sync(self) -> None:
        """Index codebase synchronously."""
        self._status["indexing"] = True
        logger.info(f"Indexing codebase at {self.working_dir}...")

        try:
            # Check if already indexed
            stats = self.indexer.get_stats()
            if stats["total_documents"] > 0:
                logger.info(f"Codebase already indexed: {stats['total_documents']} documents")
                self._status["indexed_files"] = stats["total_documents"]
                self._status["indexing"] = False
                return

            # Index the codebase
            count = self.indexer.index_directory(self.working_dir)
            self._status["indexed_files"] = count
            logger.info(f"Indexed {count} files")

        except Exception as e:
            logger.error(f"Indexing error: {e}")

        finally:
            self._status["indexing"] = False
            self._indexing_complete.set()

    def _start_background_indexing(self) -> None:
        """Start background indexing thread."""
        if self._index_thread and self._index_thread.is_alive():
            return

        self._index_thread = threading.Thread(
            target=self._index_codebase_sync,
            daemon=True,
            name="codebase-indexer"
        )
        self._index_thread.start()
        logger.info("Started background codebase indexing")

    def wait_for_indexing(self, timeout: float | None = None) -> bool:
        """
        Wait for indexing to complete.

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            True if indexing completed, False if timeout
        """
        return self._indexing_complete.wait(timeout)

    def reindex(self, force: bool = False) -> int:
        """
        Reindex the codebase.

        Args:
            force: If True, clear existing index first

        Returns:
            Number of files indexed
        """
        if force:
            self.indexer.clear_index()

        return self.indexer.index_directory(self.working_dir)

    def get_status(self) -> dict[str, Any]:
        """Get current initialization status."""
        stats = self.indexer.get_stats()
        result = {
            **self._status,
            "index_stats": stats,
            "working_dir": str(self.working_dir),
            "knowledge_base_entries": self.knowledge_base.get_stats()["total_entries"],
        }

        # Add file watcher stats if running
        if self.file_watcher:
            result["file_watcher_stats"] = self.file_watcher.get_stats()

        return result

    def is_ready(self) -> bool:
        """Check if agent is ready to use."""
        return (
            self._status["models_checked"]
            and len(self._status["available_models"]) > 0
            and not self._status["indexing"]
        )


def quick_start(working_dir: Path, ollama_url: str = "http://localhost:11434") -> StartupManager:
    """
    Quick start helper for agent initialization.

    Args:
        working_dir: Working directory to index
        ollama_url: Ollama server URL

    Returns:
        Configured StartupManager
    """
    manager = StartupManager(
        working_dir=working_dir,
        ollama_url=ollama_url,
    )
    manager.initialize(blocking=False)
    return manager
