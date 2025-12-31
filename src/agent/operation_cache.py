"""
Operation Cache (Phase 54)

Prevents redundant operations in the agent loop:
- Caches read operations
- Deduplicates identical tool calls
- Tracks operation history
- Provides efficiency metrics
"""

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CachedOperation:
    """A cached operation result."""
    tool_name: str
    params_hash: str
    result: Any
    timestamp: float
    hit_count: int = 0


@dataclass
class OperationStats:
    """Statistics about operation caching."""
    total_operations: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    unique_operations: int = 0

    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        if self.total_operations == 0:
            return 0.0
        return self.cache_hits / self.total_operations


class OperationCache:
    """Cache for agent operations to prevent redundancy."""

    def __init__(self, ttl: float = 300.0, max_size: int = 1000):
        """
        Initialize operation cache.

        Args:
            ttl: Time to live for cache entries (seconds)
            max_size: Maximum number of cached entries
        """
        self.ttl = ttl
        self.max_size = max_size
        self.cache: dict[str, CachedOperation] = {}
        self.stats = OperationStats()

        # Track tool calls in current iteration
        self.iteration_history: list[str] = []

    def _make_key(self, tool_name: str, params: dict[str, Any]) -> str:
        """Create cache key from tool name and parameters."""
        # Sort params for consistent hashing
        param_str = str(sorted(params.items()))
        param_hash = hashlib.md5(param_str.encode()).hexdigest()
        return f"{tool_name}:{param_hash}"

    def _is_expired(self, operation: CachedOperation) -> bool:
        """Check if cached operation has expired."""
        return (time.time() - operation.timestamp) > self.ttl

    def _evict_old_entries(self) -> None:
        """Remove expired entries."""
        now = time.time()
        expired_keys = [
            key for key, op in self.cache.items()
            if (now - op.timestamp) > self.ttl
        ]
        for key in expired_keys:
            del self.cache[key]

    def should_cache(self, tool_name: str) -> bool:
        """Determine if a tool's results should be cached."""
        # Read operations are safe to cache
        cacheable_tools = {
            "read_file",
            "list_directory",
            "code_search",
            "git",  # Read-only git commands
        }
        return tool_name in cacheable_tools

    def get(self, tool_name: str, params: dict[str, Any]) -> Any | None:
        """Get cached result for an operation."""
        self.stats.total_operations += 1

        # Check if tool should be cached
        if not self.should_cache(tool_name):
            self.stats.cache_misses += 1
            return None

        key = self._make_key(tool_name, params)

        # Check iteration history for same-iteration duplicates
        if key in self.iteration_history:
            # Same operation in same iteration - warning sign
            pass

        # Check cache
        if key in self.cache:
            operation = self.cache[key]

            # Check if expired
            if self._is_expired(operation):
                del self.cache[key]
                self.stats.cache_misses += 1
                return None

            # Cache hit!
            operation.hit_count += 1
            self.stats.cache_hits += 1
            self.iteration_history.append(key)
            return operation.result

        self.stats.cache_misses += 1
        return None

    def set(self, tool_name: str, params: dict[str, Any], result: Any) -> None:
        """Cache an operation result."""
        if not self.should_cache(tool_name):
            return

        # Evict old entries if cache is full
        if len(self.cache) >= self.max_size:
            self._evict_old_entries()

            # If still full, remove least recently used
            if len(self.cache) >= self.max_size:
                # Find entry with oldest timestamp
                oldest_key = min(self.cache.keys(), key=lambda k: self.cache[k].timestamp)
                del self.cache[oldest_key]

        key = self._make_key(tool_name, params)
        params_hash = hashlib.md5(str(sorted(params.items())).encode()).hexdigest()

        self.cache[key] = CachedOperation(
            tool_name=tool_name,
            params_hash=params_hash,
            result=result,
            timestamp=time.time(),
            hit_count=0
        )

        if key not in self.iteration_history:
            self.stats.unique_operations += 1

        self.iteration_history.append(key)

    def reset_iteration(self) -> None:
        """Reset iteration history (call at start of each iteration)."""
        self.iteration_history.clear()

    def clear(self) -> None:
        """Clear all cached operations."""
        self.cache.clear()
        self.iteration_history.clear()
        self.stats = OperationStats()

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        return {
            "total_operations": self.stats.total_operations,
            "cache_hits": self.stats.cache_hits,
            "cache_misses": self.stats.cache_misses,
            "unique_operations": self.stats.unique_operations,
            "hit_rate": round(self.stats.hit_rate() * 100, 2),
            "cache_size": len(self.cache),
            "max_size": self.max_size
        }

    def detect_redundancy(self) -> list[str]:
        """Detect redundant operations in current iteration."""
        seen = set()
        duplicates = []

        for key in self.iteration_history:
            if key in seen:
                duplicates.append(key)
            seen.add(key)

        return duplicates
