"""
File Watcher for Auto-Reindexing.

Monitors the codebase for file changes and automatically
triggers reindexing of modified files.
"""

import asyncio
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Any
from queue import Queue

logger = logging.getLogger(__name__)


@dataclass
class FileChange:
    """Represents a file change event."""
    path: Path
    change_type: str  # "created", "modified", "deleted"
    timestamp: float = field(default_factory=time.time)


class FileWatcher:
    """
    Watch directories for file changes.

    Uses polling-based approach for cross-platform compatibility.
    Supports debouncing to avoid multiple triggers for the same file.
    """

    # File extensions to watch
    DEFAULT_EXTENSIONS = {".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".java"}

    # Directories to ignore
    DEFAULT_IGNORE_DIRS = {
        ".git", "__pycache__", "node_modules", ".venv", "venv",
        ".mypy_cache", ".pytest_cache", "dist", "build", ".tox",
        ".eggs", "*.egg-info", ".cache"
    }

    def __init__(
        self,
        watch_paths: list[Path],
        on_change: Callable[[list[FileChange]], None],
        extensions: set[str] | None = None,
        ignore_dirs: set[str] | None = None,
        poll_interval: float = 2.0,
        debounce_seconds: float = 1.0,
    ):
        """
        Initialize file watcher.

        Args:
            watch_paths: Directories to watch
            on_change: Callback when files change
            extensions: File extensions to watch
            ignore_dirs: Directories to ignore
            poll_interval: Seconds between polls
            debounce_seconds: Seconds to wait before triggering
        """
        self.watch_paths = [Path(p) for p in watch_paths]
        self.on_change = on_change
        self.extensions = extensions or self.DEFAULT_EXTENSIONS
        self.ignore_dirs = ignore_dirs or self.DEFAULT_IGNORE_DIRS
        self.poll_interval = poll_interval
        self.debounce_seconds = debounce_seconds

        # State tracking
        self._file_states: dict[Path, float] = {}  # path -> mtime
        self._pending_changes: dict[Path, FileChange] = {}
        self._last_trigger: float = 0
        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

        # Statistics
        self._stats = {
            "total_changes": 0,
            "files_indexed": 0,
            "start_time": None,
        }

    def _should_watch(self, path: Path) -> bool:
        """Check if a path should be watched."""
        # Check extension
        if path.suffix.lower() not in self.extensions:
            return False

        # Check ignore patterns
        for part in path.parts:
            if part in self.ignore_dirs:
                return False
            # Check wildcard patterns
            for ignore in self.ignore_dirs:
                if "*" in ignore and part.endswith(ignore.replace("*", "")):
                    return False

        return True

    def _scan_directory(self, directory: Path) -> dict[Path, float]:
        """Scan directory and return file mtimes."""
        files = {}

        try:
            for root, dirs, filenames in os.walk(directory):
                root_path = Path(root)

                # Filter out ignored directories
                dirs[:] = [d for d in dirs if d not in self.ignore_dirs]

                for filename in filenames:
                    file_path = root_path / filename

                    if self._should_watch(file_path):
                        try:
                            mtime = file_path.stat().st_mtime
                            files[file_path] = mtime
                        except (OSError, IOError):
                            continue

        except Exception as e:
            logger.error(f"Error scanning {directory}: {e}")

        return files

    def _detect_changes(self) -> list[FileChange]:
        """Detect file changes since last scan."""
        changes = []

        # Scan all watch paths
        current_files = {}
        for watch_path in self.watch_paths:
            if watch_path.exists():
                current_files.update(self._scan_directory(watch_path))

        # Find changes
        with self._lock:
            # New or modified files
            for path, mtime in current_files.items():
                if path not in self._file_states:
                    changes.append(FileChange(path=path, change_type="created"))
                elif mtime > self._file_states[path]:
                    changes.append(FileChange(path=path, change_type="modified"))

            # Deleted files
            for path in list(self._file_states.keys()):
                if path not in current_files:
                    changes.append(FileChange(path=path, change_type="deleted"))

            # Update state
            self._file_states = current_files

        return changes

    def _watch_loop(self) -> None:
        """Main watch loop (runs in separate thread)."""
        logger.info(f"File watcher started for {len(self.watch_paths)} paths")

        # Initial scan
        for watch_path in self.watch_paths:
            if watch_path.exists():
                self._file_states.update(self._scan_directory(watch_path))

        logger.info(f"Initial scan found {len(self._file_states)} files to watch")

        while self._running:
            try:
                time.sleep(self.poll_interval)

                if not self._running:
                    break

                # Detect changes
                changes = self._detect_changes()

                if changes:
                    # Add to pending changes (debouncing)
                    with self._lock:
                        for change in changes:
                            self._pending_changes[change.path] = change

                    # Check if we should trigger
                    current_time = time.time()
                    if current_time - self._last_trigger >= self.debounce_seconds:
                        self._trigger_changes()

            except Exception as e:
                logger.error(f"Error in watch loop: {e}")

        logger.info("File watcher stopped")

    def _trigger_changes(self) -> None:
        """Trigger the on_change callback with pending changes."""
        with self._lock:
            if not self._pending_changes:
                return

            changes = list(self._pending_changes.values())
            self._pending_changes.clear()
            self._last_trigger = time.time()

        # Update stats
        self._stats["total_changes"] += len(changes)

        # Call the callback
        logger.info(f"Triggering callback for {len(changes)} file changes")
        try:
            self.on_change(changes)
        except Exception as e:
            logger.error(f"Error in change callback: {e}")

    def start(self) -> None:
        """Start watching for file changes."""
        if self._running:
            logger.warning("File watcher already running")
            return

        self._running = True
        self._stats["start_time"] = time.time()
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()

        logger.info("File watcher started")

    def stop(self) -> None:
        """Stop watching for file changes."""
        self._running = False

        if self._thread:
            self._thread.join(timeout=5.0)
            self._thread = None

        logger.info("File watcher stopped")

    def get_stats(self) -> dict[str, Any]:
        """Get watcher statistics."""
        with self._lock:
            return {
                **self._stats,
                "watched_files": len(self._file_states),
                "pending_changes": len(self._pending_changes),
                "is_running": self._running,
                "uptime": time.time() - self._stats["start_time"] if self._stats["start_time"] else 0,
            }

    def force_reindex(self, path: Path | None = None) -> None:
        """Force reindex of specific path or all paths."""
        if path:
            changes = [FileChange(path=path, change_type="modified")]
        else:
            changes = [FileChange(path=p, change_type="modified") for p in self._file_states.keys()]

        if changes:
            self.on_change(changes)


class IndexingFileWatcher:
    """
    File watcher that automatically reindexes changed files.

    Integrates FileWatcher with CodebaseIndexer for automatic
    vector store updates.
    """

    def __init__(
        self,
        watch_paths: list[Path],
        indexer: Any,  # CodebaseIndexer
        poll_interval: float = 5.0,
        batch_size: int = 10,
    ):
        """
        Initialize indexing file watcher.

        Args:
            watch_paths: Directories to watch
            indexer: CodebaseIndexer instance
            poll_interval: Seconds between polls
            batch_size: Max files to index per batch
        """
        self.indexer = indexer
        self.batch_size = batch_size
        self._pending_reindex: Queue[Path] = Queue()
        self._indexing_thread: threading.Thread | None = None
        self._running = False

        self.watcher = FileWatcher(
            watch_paths=watch_paths,
            on_change=self._on_file_change,
            poll_interval=poll_interval,
        )

        self._stats = {
            "files_reindexed": 0,
            "index_errors": 0,
        }

    def _on_file_change(self, changes: list[FileChange]) -> None:
        """Handle file changes."""
        for change in changes:
            if change.change_type in ("created", "modified"):
                self._pending_reindex.put(change.path)
                logger.debug(f"Queued for reindex: {change.path}")

        # Trigger indexing
        self._process_pending()

    def _process_pending(self) -> None:
        """Process pending reindex queue."""
        batch = []

        while not self._pending_reindex.empty() and len(batch) < self.batch_size:
            try:
                path = self._pending_reindex.get_nowait()
                if path.exists():
                    batch.append(path)
            except Exception:
                break

        if batch:
            self._index_batch(batch)

    def _index_batch(self, paths: list[Path]) -> None:
        """Index a batch of files."""
        logger.info(f"Reindexing {len(paths)} files...")

        for path in paths:
            try:
                self.indexer.index_file(path)
                self._stats["files_reindexed"] += 1
                logger.debug(f"Reindexed: {path}")
            except Exception as e:
                self._stats["index_errors"] += 1
                logger.error(f"Error reindexing {path}: {e}")

    def start(self) -> None:
        """Start the indexing file watcher."""
        self._running = True
        self.watcher.start()
        logger.info("Indexing file watcher started")

    def stop(self) -> None:
        """Stop the indexing file watcher."""
        self._running = False
        self.watcher.stop()
        logger.info("Indexing file watcher stopped")

    def get_stats(self) -> dict[str, Any]:
        """Get combined statistics."""
        watcher_stats = self.watcher.get_stats()
        return {
            **watcher_stats,
            **self._stats,
            "pending_reindex": self._pending_reindex.qsize(),
        }
