"""
Cache migration utilities for M365 MCP Server.

Handles migration from unencrypted to encrypted cache databases.
"""

import logging
import shutil
from pathlib import Path
from typing import Optional

try:
    import sqlcipher3 as sqlite3
except ImportError:
    import sqlite3

from .encryption import EncryptionKeyManager
from .cache_config import CACHE_DB_PATH

logger = logging.getLogger(__name__)


def migrate_to_encrypted_cache(
    old_db_path: Optional[Path] = None,
    new_db_path: Optional[Path] = None,
    backup: bool = True,
) -> bool:
    """
    Migrate from unencrypted cache to encrypted cache.

    Args:
        old_db_path: Path to old unencrypted database.
        new_db_path: Path to new encrypted database.
        backup: Whether to create backup of old database.

    Returns:
        True if migration successful, False otherwise.
    """
    old_db: Path = old_db_path or Path(CACHE_DB_PATH)
    new_db: Path = new_db_path or Path(CACHE_DB_PATH).with_suffix(".encrypted.db")

    if not old_db.exists():
        logger.info("No existing cache database to migrate")
        return False

    # Create backup if requested
    if backup:
        backup_path = old_db.with_suffix(".backup.db")
        shutil.copy2(old_db, backup_path)
        logger.info(f"Created backup at {backup_path}")

    # Get encryption key
    key_manager = EncryptionKeyManager()
    encryption_key = key_manager.get_or_create_key()

    try:
        # Connect to old unencrypted database
        old_conn = sqlite3.connect(str(old_db))  # type: ignore[attr-defined]

        # Create new encrypted database
        new_conn = sqlite3.connect(str(new_db))  # type: ignore[attr-defined]
        new_conn.execute(f"PRAGMA key = '{encryption_key}'")
        new_conn.execute("PRAGMA cipher_compatibility = 4")

        # Copy schema
        old_cursor = old_conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table'"
        )
        for row in old_cursor:
            if row[0]:
                new_conn.execute(row[0])

        # Copy data from each table
        tables = ["cache_entries", "cache_tasks", "cache_invalidation", "cache_stats"]

        for table in tables:
            # Get column names
            cursor = old_conn.execute(f"PRAGMA table_info({table})")
            columns = [col[1] for col in cursor.fetchall()]

            if not columns:
                continue

            # Copy data
            column_list = ", ".join(columns)
            placeholders = ", ".join(["?"] * len(columns))

            old_cursor = old_conn.execute(f"SELECT {column_list} FROM {table}")
            rows = old_cursor.fetchall()

            if rows:
                new_conn.executemany(
                    f"INSERT INTO {table} ({column_list}) VALUES ({placeholders})", rows
                )

        new_conn.commit()
        old_conn.close()
        new_conn.close()

        logger.info(f"Successfully migrated cache to encrypted database at {new_db}")
        return True

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return False


def detect_and_migrate() -> bool:
    """
    Detect if migration is needed and perform it automatically.

    Returns:
        True if migration was performed, False otherwise.
    """
    cache_db_path = Path(CACHE_DB_PATH)
    if not cache_db_path.exists():
        return False

    # Try to open with encryption
    try:
        key_manager = EncryptionKeyManager()
        encryption_key = key_manager.get_or_create_key()

        conn = sqlite3.connect(str(cache_db_path))  # type: ignore[attr-defined]
        conn.execute(f"PRAGMA key = '{encryption_key}'")
        conn.execute("SELECT COUNT(*) FROM sqlite_master")
        conn.close()

        # Database is already encrypted
        return False

    except Exception:
        # Database is unencrypted, migrate it
        logger.info("Detected unencrypted cache database, migrating...")

        # Create temporary encrypted database
        temp_path = cache_db_path.with_suffix(".migrating.db")

        if migrate_to_encrypted_cache(cache_db_path, temp_path):
            # Replace old database with new
            old_backup = cache_db_path.with_suffix(".old.db")
            cache_db_path.rename(old_backup)
            temp_path.rename(cache_db_path)

            logger.info("Migration complete, old database backed up")
            return True
        else:
            logger.error("Migration failed")
            return False
