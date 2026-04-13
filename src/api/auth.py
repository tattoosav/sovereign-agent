"""
Authentication, API key management, and rate limiting.

Provides:
- API key CRUD (create, validate, revoke)
- Per-key rate limiting (requests per minute)
- Usage tracking (total requests, tokens)
- SQLite persistence
"""

import hashlib
import logging
import secrets
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Default limits
DEFAULT_RATE_LIMIT = 30       # requests per minute
DEFAULT_DAILY_LIMIT = 1000    # requests per day
DEFAULT_DB_PATH = Path("data/auth.db")


@dataclass
class APIKey:
    """An API key record."""
    key_hash: str
    name: str
    created_at: float
    rate_limit: int          # requests per minute
    daily_limit: int         # requests per day
    is_active: bool
    total_requests: int
    total_tokens: int


@dataclass
class RateLimitResult:
    """Result of a rate limit check."""
    allowed: bool
    remaining: int           # requests remaining in window
    reset_at: float          # unix timestamp when window resets
    reason: str = ""


class AuthManager:
    """Manages API keys, rate limits, and usage tracking."""

    def __init__(self, db_path: Path = DEFAULT_DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        # In-memory rate limit tracking: key_hash -> list of request timestamps
        self._request_log: dict[str, list[float]] = {}
        self._daily_counts: dict[str, tuple[str, int]] = {}  # key_hash -> (date_str, count)

    def _init_db(self) -> None:
        """Create tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS api_keys (
                    key_hash TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    rate_limit INTEGER NOT NULL DEFAULT 30,
                    daily_limit INTEGER NOT NULL DEFAULT 1000,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    total_requests INTEGER NOT NULL DEFAULT 0,
                    total_tokens INTEGER NOT NULL DEFAULT 0
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS usage_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key_hash TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    endpoint TEXT NOT NULL,
                    tokens_used INTEGER NOT NULL DEFAULT 0,
                    duration_ms INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY (key_hash) REFERENCES api_keys(key_hash)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_usage_timestamp
                ON usage_log(key_hash, timestamp)
            """)
            conn.commit()

    def create_key(self, name: str, rate_limit: int = DEFAULT_RATE_LIMIT,
                   daily_limit: int = DEFAULT_DAILY_LIMIT) -> str:
        """
        Create a new API key.

        Returns:
            The raw API key string (only shown once — store it safely).
        """
        raw_key = f"sk-{secrets.token_hex(24)}"
        key_hash = self._hash_key(raw_key)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO api_keys (key_hash, name, created_at, rate_limit, daily_limit) "
                "VALUES (?, ?, ?, ?, ?)",
                (key_hash, name, time.time(), rate_limit, daily_limit)
            )
            conn.commit()

        logger.info(f"Created API key '{name}' (hash: {key_hash[:12]}...)")
        return raw_key

    def validate_key(self, raw_key: str) -> Optional[APIKey]:
        """
        Validate an API key and return its record, or None if invalid.
        """
        key_hash = self._hash_key(raw_key)

        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT key_hash, name, created_at, rate_limit, daily_limit, "
                "is_active, total_requests, total_tokens "
                "FROM api_keys WHERE key_hash = ?",
                (key_hash,)
            ).fetchone()

        if not row:
            return None

        key = APIKey(
            key_hash=row[0], name=row[1], created_at=row[2],
            rate_limit=row[3], daily_limit=row[4],
            is_active=bool(row[5]), total_requests=row[6], total_tokens=row[7]
        )

        if not key.is_active:
            return None

        return key

    def check_rate_limit(self, key: APIKey) -> RateLimitResult:
        """
        Check if a request is allowed under the key's rate limit.
        """
        now = time.time()
        window_start = now - 60  # 1-minute sliding window

        # Clean old entries
        log = self._request_log.get(key.key_hash, [])
        log = [t for t in log if t > window_start]
        self._request_log[key.key_hash] = log

        # Check per-minute limit
        if len(log) >= key.rate_limit:
            return RateLimitResult(
                allowed=False,
                remaining=0,
                reset_at=log[0] + 60,
                reason=f"Rate limit exceeded ({key.rate_limit}/min)"
            )

        # Check daily limit
        today = time.strftime("%Y-%m-%d")
        daily_key = self._daily_counts.get(key.key_hash, ("", 0))
        if daily_key[0] == today:
            daily_count = daily_key[1]
        else:
            daily_count = 0

        if daily_count >= key.daily_limit:
            return RateLimitResult(
                allowed=False,
                remaining=0,
                reset_at=now + 3600,  # approximate
                reason=f"Daily limit exceeded ({key.daily_limit}/day)"
            )

        return RateLimitResult(
            allowed=True,
            remaining=key.rate_limit - len(log) - 1,
            reset_at=now + 60,
        )

    def record_usage(self, key: APIKey, endpoint: str,
                     tokens_used: int = 0, duration_ms: int = 0) -> None:
        """Record a request for rate limiting and usage tracking."""
        now = time.time()

        # Update in-memory rate limit log
        if key.key_hash not in self._request_log:
            self._request_log[key.key_hash] = []
        self._request_log[key.key_hash].append(now)

        # Update daily count
        today = time.strftime("%Y-%m-%d")
        daily_key = self._daily_counts.get(key.key_hash, ("", 0))
        if daily_key[0] == today:
            self._daily_counts[key.key_hash] = (today, daily_key[1] + 1)
        else:
            self._daily_counts[key.key_hash] = (today, 1)

        # Persist to DB
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO usage_log (key_hash, timestamp, endpoint, tokens_used, duration_ms) "
                "VALUES (?, ?, ?, ?, ?)",
                (key.key_hash, now, endpoint, tokens_used, duration_ms)
            )
            conn.execute(
                "UPDATE api_keys SET total_requests = total_requests + 1, "
                "total_tokens = total_tokens + ? WHERE key_hash = ?",
                (tokens_used, key.key_hash)
            )
            conn.commit()

    def revoke_key(self, raw_key: str) -> bool:
        """Revoke an API key. Returns True if found and revoked."""
        key_hash = self._hash_key(raw_key)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "UPDATE api_keys SET is_active = 0 WHERE key_hash = ?",
                (key_hash,)
            )
            conn.commit()
            return cursor.rowcount > 0

    def list_keys(self) -> list[APIKey]:
        """List all API keys (active and revoked)."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT key_hash, name, created_at, rate_limit, daily_limit, "
                "is_active, total_requests, total_tokens FROM api_keys "
                "ORDER BY created_at DESC"
            ).fetchall()

        return [
            APIKey(
                key_hash=r[0], name=r[1], created_at=r[2],
                rate_limit=r[3], daily_limit=r[4],
                is_active=bool(r[5]), total_requests=r[6], total_tokens=r[7]
            )
            for r in rows
        ]

    def get_usage_stats(self, key_hash: str, hours: int = 24) -> dict:
        """Get usage stats for a key over the last N hours."""
        since = time.time() - (hours * 3600)
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT COUNT(*), COALESCE(SUM(tokens_used), 0), "
                "COALESCE(AVG(duration_ms), 0) "
                "FROM usage_log WHERE key_hash = ? AND timestamp > ?",
                (key_hash, since)
            ).fetchone()

        return {
            "requests": row[0],
            "tokens": row[1],
            "avg_duration_ms": round(row[2]),
            "period_hours": hours,
        }

    @staticmethod
    def _hash_key(raw_key: str) -> str:
        """Hash an API key for storage. Never store raw keys."""
        return hashlib.sha256(raw_key.encode()).hexdigest()
