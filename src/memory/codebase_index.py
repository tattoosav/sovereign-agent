"""
Codebase indexing for semantic search.

Indexes code files for fast semantic search and retrieval.
"""

import logging
from pathlib import Path
from typing import Any

from src.memory.vector_store import VectorStore

logger = logging.getLogger(__name__)


class CodebaseIndexer:
    """
    Index and search codebase using vector embeddings.

    Provides semantic search over code files, functions, and classes.
    """

    def __init__(self, vector_store: VectorStore | None = None):
        """
        Initialize codebase indexer.

        Args:
            vector_store: Vector store instance (creates new if None)
        """
        self.vector_store = vector_store or VectorStore()
        self.collection_name = "codebase"

    def index_file(self, file_path: Path, project_root: Path | None = None) -> None:
        """
        Index a single code file.

        Args:
            file_path: Path to the file to index
            project_root: Root of the project (for relative paths)
        """
        if not file_path.exists() or not file_path.is_file():
            logger.warning(f"File not found: {file_path}")
            return

        # Skip binary and non-code files
        skip_extensions = {
            '.pyc', '.exe', '.dll', '.so', '.dylib', '.bin', '.dat',
            '.jpg', '.png', '.gif', '.pdf', '.zip', '.tar', '.gz'
        }

        if file_path.suffix in skip_extensions:
            return

        # Read file content
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except (UnicodeDecodeError, PermissionError) as e:
            logger.debug(f"Skipping {file_path}: {e}")
            return

        # Get relative path
        if project_root:
            try:
                rel_path = file_path.relative_to(project_root)
            except ValueError:
                rel_path = file_path
        else:
            rel_path = file_path

        # Create document ID and metadata
        doc_id = str(rel_path).replace("\\", "/")
        metadata = {
            "path": str(rel_path),
            "filename": file_path.name,
            "extension": file_path.suffix,
            "size": len(content)
        }

        # Index the file
        self.vector_store.add_documents(
            collection_name=self.collection_name,
            documents=[content],
            metadatas=[metadata],
            ids=[doc_id]
        )

        logger.debug(f"Indexed: {rel_path}")

    def index_directory(
        self,
        directory: Path,
        recursive: bool = True,
        file_patterns: list[str] | None = None
    ) -> int:
        """
        Index all files in a directory.

        Args:
            directory: Directory to index
            recursive: Whether to recurse into subdirectories
            file_patterns: List of glob patterns to match (e.g., ['*.py', '*.js'])

        Returns:
            Number of files indexed
        """
        if not directory.exists() or not directory.is_dir():
            logger.error(f"Directory not found: {directory}")
            return 0

        # Default patterns for code files
        if file_patterns is None:
            file_patterns = [
                '*.py', '*.js', '*.ts', '*.tsx', '*.jsx',
                '*.java', '*.cpp', '*.c', '*.h', '*.hpp',
                '*.rs', '*.go', '*.rb', '*.php', '*.swift',
                '*.kt', '*.scala', '*.sh', '*.bash',
                '*.md', '*.txt', '*.yaml', '*.yml', '*.json'
            ]

        indexed_count = 0

        for pattern in file_patterns:
            if recursive:
                files = directory.rglob(pattern)
            else:
                files = directory.glob(pattern)

            for file_path in files:
                # Skip hidden directories and common exclude patterns
                if any(part.startswith('.') for part in file_path.parts):
                    continue

                if any(exclude in str(file_path) for exclude in ['node_modules', '__pycache__', 'venv', '.git']):
                    continue

                self.index_file(file_path, project_root=directory)
                indexed_count += 1

        logger.info(f"Indexed {indexed_count} files from {directory}")
        return indexed_count

    def search(
        self,
        query: str,
        n_results: int = 5,
        file_type: str | None = None
    ) -> list[dict[str, Any]]:
        """
        Search the codebase for relevant files.

        Args:
            query: Search query (natural language or code)
            n_results: Number of results to return
            file_type: Optional file extension filter (e.g., '.py')

        Returns:
            List of dicts with 'path', 'content', 'similarity'
        """
        # Build metadata filter
        where = None
        if file_type:
            where = {"extension": file_type}

        # Search vector store
        results = self.vector_store.search(
            collection_name=self.collection_name,
            query=query,
            n_results=n_results,
            where=where
        )

        # Format results
        formatted_results = []
        for i, doc in enumerate(results["documents"]):
            formatted_results.append({
                "path": results["metadatas"][i].get("path", "unknown"),
                "content": doc,
                "similarity": 1.0 - results["distances"][i],  # Convert distance to similarity
                "metadata": results["metadatas"][i]
            })

        return formatted_results

    def get_stats(self) -> dict[str, Any]:
        """Get indexing statistics."""
        count = self.vector_store.get_collection_count(self.collection_name)
        return {
            "total_documents": count,
            "collection_name": self.collection_name,
            "available": self.vector_store.is_available()
        }

    def clear_index(self) -> None:
        """Clear all indexed documents."""
        self.vector_store.delete_collection(self.collection_name)
        logger.info("Cleared codebase index")
