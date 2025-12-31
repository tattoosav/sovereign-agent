"""
Vector database integration using ChromaDB.

Provides semantic search and storage for code, documentation, and patterns.
"""

import hashlib
import logging
from pathlib import Path
from typing import Any

try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    chromadb = None  # type: ignore

logger = logging.getLogger(__name__)


class VectorStore:
    """
    Vector database for semantic search.

    Uses ChromaDB for local vector storage without external dependencies.
    """

    def __init__(self, persist_directory: str = ".sovereign_db"):
        """
        Initialize vector store.

        Args:
            persist_directory: Directory to persist the database
        """
        if not CHROMADB_AVAILABLE:
            logger.warning("ChromaDB not available. Install with: pip install chromadb")
            self._client = None
            return

        self.persist_dir = Path(persist_directory)
        self.persist_dir.mkdir(parents=True, exist_ok=True)

        # Initialize ChromaDB client
        self._client = chromadb.PersistentClient(
            path=str(self.persist_dir),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )

        logger.info(f"Vector store initialized at {self.persist_dir}")

    def is_available(self) -> bool:
        """Check if ChromaDB is available."""
        return CHROMADB_AVAILABLE and self._client is not None

    def get_or_create_collection(self, name: str) -> Any:
        """
        Get or create a collection.

        Args:
            name: Collection name

        Returns:
            ChromaDB collection object
        """
        if not self.is_available():
            raise RuntimeError("ChromaDB not available")

        return self._client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"}  # Use cosine similarity
        )

    def add_documents(
        self,
        collection_name: str,
        documents: list[str],
        metadatas: list[dict[str, Any]] | None = None,
        ids: list[str] | None = None
    ) -> None:
        """
        Add documents to a collection.

        Args:
            collection_name: Name of the collection
            documents: List of document texts
            metadatas: Optional metadata for each document
            ids: Optional IDs for each document (auto-generated if not provided)
        """
        if not self.is_available():
            logger.warning("ChromaDB not available, skipping add_documents")
            return

        collection = self.get_or_create_collection(collection_name)

        # Generate IDs if not provided
        if ids is None:
            ids = [
                hashlib.md5(doc.encode()).hexdigest()
                for doc in documents
            ]

        # Add documents
        collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )

        logger.info(f"Added {len(documents)} documents to collection '{collection_name}'")

    def search(
        self,
        collection_name: str,
        query: str,
        n_results: int = 5,
        where: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Search for similar documents.

        Args:
            collection_name: Name of the collection to search
            query: Search query
            n_results: Number of results to return
            where: Optional metadata filter

        Returns:
            Dict with 'documents', 'metadatas', 'distances', 'ids'
        """
        if not self.is_available():
            logger.warning("ChromaDB not available, returning empty results")
            return {
                "documents": [],
                "metadatas": [],
                "distances": [],
                "ids": []
            }

        try:
            collection = self.get_or_create_collection(collection_name)

            results = collection.query(
                query_texts=[query],
                n_results=n_results,
                where=where
            )

            # Flatten results (query returns nested lists)
            return {
                "documents": results["documents"][0] if results["documents"] else [],
                "metadatas": results["metadatas"][0] if results["metadatas"] else [],
                "distances": results["distances"][0] if results["distances"] else [],
                "ids": results["ids"][0] if results["ids"] else []
            }

        except Exception as e:
            logger.error(f"Search error: {e}")
            return {
                "documents": [],
                "metadatas": [],
                "distances": [],
                "ids": []
            }

    def delete_collection(self, collection_name: str) -> None:
        """Delete a collection."""
        if not self.is_available():
            return

        try:
            self._client.delete_collection(collection_name)
            logger.info(f"Deleted collection '{collection_name}'")
        except Exception as e:
            logger.error(f"Error deleting collection: {e}")

    def list_collections(self) -> list[str]:
        """List all collections."""
        if not self.is_available():
            return []

        try:
            collections = self._client.list_collections()
            return [c.name for c in collections]
        except Exception as e:
            logger.error(f"Error listing collections: {e}")
            return []

    def get_collection_count(self, collection_name: str) -> int:
        """Get number of documents in a collection."""
        if not self.is_available():
            return 0

        try:
            collection = self.get_or_create_collection(collection_name)
            return collection.count()
        except Exception as e:
            logger.error(f"Error getting collection count: {e}")
            return 0
