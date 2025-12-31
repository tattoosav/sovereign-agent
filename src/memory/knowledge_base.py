"""
Knowledge base for storing patterns, decisions, and learnings.

Stores project-specific knowledge, common patterns, and solutions.
"""

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class KnowledgeEntry:
    """A single knowledge entry."""
    id: str
    type: str  # "pattern", "decision", "solution", "note"
    title: str
    content: str
    tags: list[str]
    created_at: str
    updated_at: str
    metadata: dict[str, Any]


class KnowledgeBase:
    """
    Project-specific knowledge storage.

    Stores:
    - Architecture decisions
    - Code patterns
    - Common solutions
    - Project notes
    - Best practices
    """

    def __init__(self, storage_path: str = ".sovereign_knowledge"):
        """
        Initialize knowledge base.

        Args:
            storage_path: Directory to store knowledge files
        """
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.entries_file = self.storage_path / "entries.json"
        self._entries: dict[str, KnowledgeEntry] = {}
        self._load_entries()

    def _load_entries(self) -> None:
        """Load entries from disk."""
        if not self.entries_file.exists():
            return

        try:
            with open(self.entries_file, 'r') as f:
                data = json.load(f)
                for entry_dict in data:
                    entry = KnowledgeEntry(**entry_dict)
                    self._entries[entry.id] = entry
            logger.info(f"Loaded {len(self._entries)} knowledge entries")
        except Exception as e:
            logger.error(f"Error loading knowledge base: {e}")

    def _save_entries(self) -> None:
        """Save entries to disk."""
        try:
            data = [asdict(entry) for entry in self._entries.values()]
            with open(self.entries_file, 'w') as f:
                json.dump(data, f, indent=2)
            logger.debug(f"Saved {len(self._entries)} knowledge entries")
        except Exception as e:
            logger.error(f"Error saving knowledge base: {e}")

    def add_entry(
        self,
        entry_type: str,
        title: str,
        content: str,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None
    ) -> str:
        """
        Add a new knowledge entry.

        Args:
            entry_type: Type of entry (pattern, decision, solution, note)
            title: Entry title
            content: Entry content
            tags: Optional tags for categorization
            metadata: Optional additional metadata

        Returns:
            Entry ID
        """
        import hashlib

        # Generate ID
        timestamp = datetime.now().isoformat()
        entry_id = hashlib.md5(f"{timestamp}{title}".encode()).hexdigest()[:12]

        # Create entry
        entry = KnowledgeEntry(
            id=entry_id,
            type=entry_type,
            title=title,
            content=content,
            tags=tags or [],
            created_at=timestamp,
            updated_at=timestamp,
            metadata=metadata or {}
        )

        self._entries[entry_id] = entry
        self._save_entries()

        logger.info(f"Added knowledge entry: {title} ({entry_id})")
        return entry_id

    def get_entry(self, entry_id: str) -> KnowledgeEntry | None:
        """Get an entry by ID."""
        return self._entries.get(entry_id)

    def search_entries(
        self,
        query: str | None = None,
        entry_type: str | None = None,
        tags: list[str] | None = None
    ) -> list[KnowledgeEntry]:
        """
        Search knowledge entries.

        Args:
            query: Search query (searches title and content)
            entry_type: Filter by entry type
            tags: Filter by tags (entries must have ALL specified tags)

        Returns:
            List of matching entries
        """
        results = []

        for entry in self._entries.values():
            # Type filter
            if entry_type and entry.type != entry_type:
                continue

            # Tag filter
            if tags and not all(tag in entry.tags for tag in tags):
                continue

            # Query filter
            if query:
                query_lower = query.lower()
                if query_lower not in entry.title.lower() and \
                   query_lower not in entry.content.lower():
                    continue

            results.append(entry)

        # Sort by updated_at (most recent first)
        results.sort(key=lambda e: e.updated_at, reverse=True)
        return results

    def update_entry(
        self,
        entry_id: str,
        title: str | None = None,
        content: str | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None
    ) -> bool:
        """Update an existing entry."""
        entry = self._entries.get(entry_id)
        if not entry:
            return False

        if title:
            entry.title = title
        if content:
            entry.content = content
        if tags is not None:
            entry.tags = tags
        if metadata is not None:
            entry.metadata.update(metadata)

        entry.updated_at = datetime.now().isoformat()
        self._save_entries()

        logger.info(f"Updated knowledge entry: {entry_id}")
        return True

    def delete_entry(self, entry_id: str) -> bool:
        """Delete an entry."""
        if entry_id in self._entries:
            del self._entries[entry_id]
            self._save_entries()
            logger.info(f"Deleted knowledge entry: {entry_id}")
            return True
        return False

    def get_all_entries(self) -> list[KnowledgeEntry]:
        """Get all entries."""
        return list(self._entries.values())

    def get_stats(self) -> dict[str, Any]:
        """Get knowledge base statistics."""
        types = {}
        for entry in self._entries.values():
            types[entry.type] = types.get(entry.type, 0) + 1

        all_tags = set()
        for entry in self._entries.values():
            all_tags.update(entry.tags)

        return {
            "total_entries": len(self._entries),
            "types": types,
            "unique_tags": len(all_tags),
            "tags": sorted(all_tags)
        }

    def export_markdown(self, output_path: Path) -> None:
        """Export knowledge base to Markdown."""
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("# Knowledge Base\n\n")

            # Group by type
            by_type: dict[str, list[KnowledgeEntry]] = {}
            for entry in self._entries.values():
                if entry.type not in by_type:
                    by_type[entry.type] = []
                by_type[entry.type].append(entry)

            # Write entries
            for entry_type, entries in sorted(by_type.items()):
                f.write(f"## {entry_type.capitalize()}s\n\n")

                for entry in sorted(entries, key=lambda e: e.title):
                    f.write(f"### {entry.title}\n\n")
                    f.write(f"**Tags:** {', '.join(entry.tags)}\n\n")
                    f.write(f"{entry.content}\n\n")
                    f.write(f"*Created: {entry.created_at}*\n\n")
                    f.write("---\n\n")

        logger.info(f"Exported knowledge base to {output_path}")
