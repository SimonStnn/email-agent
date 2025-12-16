"""
Encrypted SQLite cache manager for M365 MCP Server.

This module provides a comprehensive caching system with encryption, compression,
TTL management, and automatic cleanup for Microsoft 365 data.
"""

import json
import gzip
import logging
import time
from pathlib import Path
from contextlib import contextmanager
from typing import Any, Optional

try:
    import sqlcipher3 as sqlite3
except ImportError:
    import sqlite3

from .encryption import EncryptionKeyManager
from .cache_config import (
    CACHE_DB_PATH,
    TTL_POLICIES,
    CACHE_LIMITS,
    CacheState,
    generate_cache_key,
)

logger = logging.getLogger(__name__)


class CacheManager:
    """
    Encrypted cache manager with compression and TTL support.

    Features:
    - AES-256 encryption via SQLCipher
    - Automatic compression for entries ≥50KB
    - Three-state TTL (Fresh/Stale/Expired)
    - Connection pooling
    - Automatic cleanup at 80% capacity
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        encryption_enabled: bool = True,
        max_connections: int = 5,
    ):
        """
        Initialize cache manager.

        Args:
            db_path: Path to SQLite database file. Defaults to CACHE_DB_PATH.
            encryption_enabled: Whether to enable SQLCipher encryption.
            max_connections: Maximum number of pooled connections.
        """
        self.db_path = Path(db_path) if db_path else Path(CACHE_DB_PATH)
        self.encryption_enabled = encryption_enabled
        self.max_connections = max_connections
        self._connection_pool = []

        # Get encryption key if enabled
        self.encryption_key = None
        if self.encryption_enabled:
            key_manager = EncryptionKeyManager()
            self.encryption_key = key_manager.get_or_create_key()
            logger.info("Cache encryption enabled")
        else:
            logger.warning("Cache encryption DISABLED - data stored in plaintext")

        # Initialize database
        self._init_database()
        logger.info(f"Cache manager initialized at {self.db_path}")

    def _create_connection(self) -> sqlite3.Connection:  # type: ignore[name-defined]
        """
        Create a new database connection with encryption.

        Returns:
            SQLite connection with encryption configured.
        """
        conn = sqlite3.connect(str(self.db_path))  # type: ignore[attr-defined]

        if self.encryption_enabled and self.encryption_key:
            # Set encryption key for SQLCipher
            conn.execute(f"PRAGMA key = '{self.encryption_key}'")
            conn.execute("PRAGMA cipher_compatibility = 4")

        # Performance optimizations
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA cache_size = -64000")  # 64MB cache
        conn.execute("PRAGMA temp_store = MEMORY")

        conn.row_factory = sqlite3.Row  # type: ignore[attr-defined]
        return conn

    @contextmanager
    def _db(self):
        """
        Context manager for database connections with pooling.

        Yields:
            Database connection from pool or newly created.
        """
        # Get connection from pool or create new
        if self._connection_pool:
            conn = self._connection_pool.pop()
        else:
            conn = self._create_connection()

        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            # Return to pool if under limit
            if len(self._connection_pool) < self.max_connections:
                self._connection_pool.append(conn)
            else:
                conn.close()

    def _init_database(self) -> None:
        """
        Initialize database schema using migration script.
        """
        # Ensure parent directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Read and execute migration script
        migration_path = Path(__file__).parent / "migrations" / "001_init_cache.sql"

        if not migration_path.exists():
            raise FileNotFoundError(f"Migration script not found: {migration_path}")

        with open(migration_path) as f:
            migration_sql = f.read()

        with self._db() as conn:
            conn.executescript(migration_sql)

        logger.info("Database schema initialized")

    def get_cached(
        self, account_id: str, resource_type: str, params: dict[str, Any]
    ) -> Optional[tuple[Any, CacheState]]:
        """
        Retrieve cached data with state detection.

        Args:
            account_id: Microsoft account identifier.
            resource_type: Type of resource (e.g., 'email_list', 'folder_tree').
            params: Parameters used to generate cache key.

        Returns:
            Tuple of (data, state) if found, None if not found or expired.
            State is FRESH, STALE, or None for expired.
        """
        cache_key = generate_cache_key(account_id, resource_type, params)

        # Get TTL policy for this resource type
        from .cache_config import TTLPolicy

        ttl_policy = TTL_POLICIES.get(resource_type)
        if not ttl_policy:
            logger.warning(f"No TTL policy for {resource_type}, using default")
            ttl_policy = TTLPolicy(fresh_seconds=300, stale_seconds=1800)

        with self._db() as conn:
            cursor = conn.execute(
                """
                SELECT data_json, is_compressed, created_at, accessed_at, hit_count
                FROM cache_entries
                WHERE cache_key = ?
                """,
                (cache_key,),
            )
            row = cursor.fetchone()

            if not row:
                return None

            # Decompress if needed
            data_bytes = row["data_json"]
            if row["is_compressed"]:
                data_bytes = gzip.decompress(data_bytes)

            # Parse JSON
            try:
                data = json.loads(data_bytes.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                logger.error(f"Failed to parse cached data: {e}")
                return None

            # Determine cache state
            age_seconds = time.time() - row["created_at"]

            if age_seconds <= ttl_policy.fresh_seconds:
                state = CacheState.FRESH
            elif age_seconds <= ttl_policy.stale_seconds:
                state = CacheState.STALE
            else:
                # Expired, delete and return None
                conn.execute(
                    "DELETE FROM cache_entries WHERE cache_key = ?", (cache_key,)
                )
                return None

            # Update access tracking
            conn.execute(
                """
                UPDATE cache_entries
                SET accessed_at = ?, hit_count = hit_count + 1
                WHERE cache_key = ?
                """,
                (time.time(), cache_key),
            )

            return (data, state)

    def set_cached(
        self, account_id: str, resource_type: str, params: dict[str, Any], data: Any
    ) -> None:
        """
        Store data in cache with compression and encryption.

        Args:
            account_id: Microsoft account identifier.
            resource_type: Type of resource being cached.
            params: Parameters used to generate cache key.
            data: Data to cache (will be JSON serialized).

        Raises:
            ValueError: If data exceeds size limit.
        """
        cache_key = generate_cache_key(account_id, resource_type, params)

        # Serialize to JSON
        data_json = json.dumps(data)
        data_bytes = data_json.encode("utf-8")

        # Compress if >= 50KB
        compressed = False
        if len(data_bytes) >= CACHE_LIMITS.compression_threshold:
            data_bytes = gzip.compress(data_bytes, compresslevel=6)
            compressed = True

        # Check size limit (10MB)
        if len(data_bytes) > CACHE_LIMITS.max_entry_bytes:
            raise ValueError(
                f"Cache entry too large: {len(data_bytes)} bytes "
                f"(max: {CACHE_LIMITS.max_entry_bytes})"
            )

        now = time.time()

        # Calculate fresh_until and expires_at based on TTL policy
        from .cache_config import TTLPolicy

        ttl_policy = TTL_POLICIES.get(resource_type)
        if not ttl_policy:
            ttl_policy = TTLPolicy(fresh_seconds=300, stale_seconds=1800)

        fresh_until = now + ttl_policy.fresh_seconds
        expires_at = now + ttl_policy.stale_seconds

        with self._db() as conn:
            # Insert or replace cache entry
            conn.execute(
                """
                INSERT OR REPLACE INTO cache_entries
                (cache_key, account_id, resource_type, data_json, is_compressed,
                 data_size_bytes, created_at, accessed_at, fresh_until, expires_at, hit_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                """,
                (
                    cache_key,
                    account_id,
                    resource_type,
                    data_bytes,
                    compressed,
                    len(data_bytes),
                    now,
                    now,
                    fresh_until,
                    expires_at,
                ),
            )

        # Check if cleanup needed
        self._check_cleanup()

    def _check_cleanup(self) -> None:
        """
        Check if cleanup is needed and trigger if at threshold.
        """
        with self._db() as conn:
            cursor = conn.execute(
                "SELECT SUM(data_size_bytes) as total FROM cache_entries"
            )
            row = cursor.fetchone()
            total_bytes = row["total"] if row and row["total"] else 0

            # Trigger cleanup at 80% threshold
            threshold = CACHE_LIMITS.max_total_bytes * CACHE_LIMITS.cleanup_threshold

            if total_bytes >= threshold:
                logger.info(f"Cache size {total_bytes} bytes, triggering cleanup")
                self._cleanup_to_target()

    def invalidate_pattern(
        self, pattern: str, account_id: Optional[str] = None, reason: str = "manual"
    ) -> int:
        """
        Invalidate cache entries matching pattern.

        Args:
            pattern: Cache key pattern with wildcards (*).
            account_id: Optional account ID to limit invalidation scope.
            reason: Reason for invalidation.

        Returns:
            Number of entries invalidated.
        """
        # Convert wildcard pattern to SQL LIKE pattern
        sql_pattern = pattern.replace("*", "%")

        with self._db() as conn:
            # Build query with optional account filter
            if account_id:
                where_clause = "cache_key LIKE ? AND account_id = ?"
                params = (sql_pattern, account_id)
                log_account = account_id
            else:
                where_clause = "cache_key LIKE ?"
                params = (sql_pattern,)
                log_account = "system"

            # Count matching entries first
            cursor = conn.execute(
                f"SELECT COUNT(*) as count FROM cache_entries WHERE {where_clause}",
                params,
            )
            count = cursor.fetchone()["count"]

            # Log invalidation
            conn.execute(
                """
                INSERT INTO cache_invalidation
                (account_id, pattern, reason, invalidated_at, entries_invalidated)
                VALUES (?, ?, ?, ?, ?)
                """,
                (log_account, pattern, reason, time.time(), count),
            )

            # Delete matching entries
            conn.execute(f"DELETE FROM cache_entries WHERE {where_clause}", params)

            if count > 0:
                logger.info(f"Invalidated {count} entries matching '{pattern}'")

            return count

    def _cleanup_to_target(self) -> None:
        """
        Clean up cache to target size (60% of max).
        """
        target_bytes = CACHE_LIMITS.max_total_bytes * CACHE_LIMITS.cleanup_target

        with self._db() as conn:
            # First delete expired entries
            now = time.time()
            conn.execute(
                """
                DELETE FROM cache_entries
                WHERE expires_at < ?
                """,
                (now,),
            )

            # Check remaining size
            cursor = conn.execute(
                "SELECT SUM(data_size_bytes) as total FROM cache_entries"
            )
            row = cursor.fetchone()
            current_bytes = row["total"] if row and row["total"] else 0

            # If still over target, delete LRU entries
            if current_bytes > target_bytes:
                bytes_to_free = current_bytes - target_bytes

                # Delete oldest accessed entries until target reached
                conn.execute(
                    """
                    DELETE FROM cache_entries
                    WHERE cache_key IN (
                        SELECT cache_key FROM cache_entries
                        ORDER BY accessed_at ASC
                        LIMIT (
                            SELECT COUNT(*) FROM cache_entries
                            WHERE (
                                SELECT SUM(data_size_bytes) FROM cache_entries e2
                                WHERE e2.accessed_at <= cache_entries.accessed_at
                            ) <= ?
                        )
                    )
                    """,
                    (bytes_to_free,),
                )

            logger.info(f"Cleanup complete, target size: {target_bytes} bytes")

    def cleanup_expired(self) -> int:
        """
        Manually clean up expired entries.

        Returns:
            Number of entries deleted.
        """
        now = time.time()
        count = 0

        with self._db() as conn:
            # Use expires_at from the table (already calculated)
            cursor = conn.execute(
                """
                DELETE FROM cache_entries
                WHERE expires_at < ?
                """,
                (now,),
            )
            count = cursor.rowcount

        if count > 0:
            logger.info(f"Cleaned up {count} expired entries")

        return count

    def get_stats(self) -> dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache metrics.
        """
        with self._db() as conn:
            # Overall stats
            cursor = conn.execute(
                """
                SELECT
                    COUNT(*) as entry_count,
                    SUM(data_size_bytes) as total_bytes,
                    AVG(data_size_bytes) as avg_bytes,
                    SUM(hit_count) as total_hits
                FROM cache_entries
                """
            )
            overall = cursor.fetchone()

            # Per-account stats
            cursor = conn.execute(
                """
                SELECT
                    account_id,
                    COUNT(*) as entry_count,
                    SUM(data_size_bytes) as total_bytes
                FROM cache_entries
                GROUP BY account_id
                """
            )
            by_account = {row["account_id"]: dict(row) for row in cursor}

            # Per-resource-type stats
            cursor = conn.execute(
                """
                SELECT
                    resource_type,
                    COUNT(*) as entry_count,
                    SUM(data_size_bytes) as total_bytes,
                    AVG(hit_count) as avg_hits
                FROM cache_entries
                GROUP BY resource_type
                """
            )
            by_resource = {row["resource_type"]: dict(row) for row in cursor}

            return {
                "entry_count": overall["entry_count"],
                "total_bytes": overall["total_bytes"] or 0,
                "avg_bytes": overall["avg_bytes"] or 0,
                "total_hits": overall["total_hits"] or 0,
                "max_bytes": CACHE_LIMITS.max_total_bytes,
                "usage_percent": (overall["total_bytes"] or 0)
                / CACHE_LIMITS.max_total_bytes
                * 100,
                "by_account": by_account,
                "by_resource": by_resource,
            }

    def enqueue_task(
        self,
        account_id: str,
        operation: str,
        parameters: dict[str, Any],
        priority: int = 5,
    ) -> str:
        """
        Enqueue a background task.

        Args:
            account_id: Microsoft account identifier
            operation: Operation name (e.g., "folder_get_tree")
            parameters: Operation parameters
            priority: Task priority (1=highest, 10=lowest)

        Returns:
            str: Generated task_id
        """
        import uuid

        task_id = str(uuid.uuid4())

        with self._db() as conn:
            conn.execute(
                """
                INSERT INTO cache_tasks (
                    task_id, account_id, operation, parameters_json,
                    priority, status, retry_count, created_at
                )
                VALUES (?, ?, ?, ?, ?, 'queued', 0, ?)
                """,
                (
                    task_id,
                    account_id,
                    operation,
                    json.dumps(parameters),
                    priority,
                    time.time(),
                ),
            )

        logger.info(
            f"Task enqueued: {task_id}",
            extra={
                "task_id": task_id,
                "account_id": account_id,
                "operation": operation,
                "priority": priority,
            },
        )

        return task_id

    def get_task_status(self, task_id: str) -> Optional[dict[str, Any]]:
        """
        Get status of a specific task.

        Args:
            task_id: Unique task identifier

        Returns:
            Optional[dict[str, Any]]: Task details if found, None otherwise
        """
        with self._db() as conn:
            cursor = conn.execute(
                """
                SELECT
                    task_id, account_id, operation, parameters_json,
                    priority, status, retry_count,
                    created_at, started_at, completed_at,
                    result_json, last_error
                FROM cache_tasks
                WHERE task_id = ?
                """,
                (task_id,),
            )

            row = cursor.fetchone()

            if row:
                return {
                    "task_id": row["task_id"],
                    "account_id": row["account_id"],
                    "operation": row["operation"],
                    "parameters": json.loads(row["parameters_json"])
                    if row["parameters_json"]
                    else {},
                    "priority": row["priority"],
                    "status": row["status"],
                    "retry_count": row["retry_count"],
                    "created_at": row["created_at"],
                    "started_at": row["started_at"],
                    "completed_at": row["completed_at"],
                    "result": row["result_json"],
                    "error": row["last_error"],
                }

            return None

    def list_tasks(
        self,
        account_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        List tasks with optional filtering.

        Args:
            account_id: Filter by account (optional)
            status: Filter by status (optional)
            limit: Maximum number of tasks to return

        Returns:
            list[dict[str, Any]]: List of task details
        """
        query = """
            SELECT
                task_id, account_id, operation, parameters_json,
                priority, status, retry_count,
                created_at, started_at, completed_at,
                result_json, last_error
            FROM cache_tasks
            WHERE 1=1
        """
        params = []

        if account_id:
            query += " AND account_id = ?"
            params.append(account_id)

        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with self._db() as conn:
            cursor = conn.execute(query, params)

            return [
                {
                    "task_id": row["task_id"],
                    "account_id": row["account_id"],
                    "operation": row["operation"],
                    "parameters": json.loads(row["parameters_json"])
                    if row["parameters_json"]
                    else {},
                    "priority": row["priority"],
                    "status": row["status"],
                    "retry_count": row["retry_count"],
                    "created_at": row["created_at"],
                    "started_at": row["started_at"],
                    "completed_at": row["completed_at"],
                    "result": row["result_json"],
                    "error": row["last_error"],
                }
                for row in cursor
            ]
