"""Tests for cache database schema and encryption.

This module tests:
- Database creation with SQLCipher encryption
- Schema migration execution
- Table and index creation
- Encryption key validation
"""

import os
import tempfile
from pathlib import Path
import pytest
import sqlcipher3.dbapi2 as sqlcipher

from src.m365_mcp.encryption import EncryptionKeyManager
from src.m365_mcp.cache_config import (
    generate_cache_key,
    parse_cache_key,
    get_ttl_policy,
    TTL_POLICIES,
    CACHE_LIMITS,
    CacheState,
)


class TestDatabaseCreation:
    """Test encrypted database creation and schema migration."""

    def test_database_creation_with_encryption(self):
        """Test that database can be created with SQLCipher encryption."""
        # Generate a test encryption key
        encryption_key = EncryptionKeyManager.generate_key()

        # Create temporary database
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name

        try:
            # Connect with encryption
            conn = sqlcipher.connect(db_path)  # type: ignore[attr-defined]
            conn.execute(f"PRAGMA key = '{encryption_key}'")
            conn.execute("PRAGMA cipher_page_size = 4096")

            # Create a simple test table
            conn.execute("CREATE TABLE test_table (id INTEGER PRIMARY KEY, value TEXT)")
            conn.execute("INSERT INTO test_table (id, value) VALUES (1, 'encrypted')")
            conn.commit()

            # Verify data was written
            cursor = conn.execute("SELECT value FROM test_table WHERE id = 1")
            result = cursor.fetchone()
            assert result[0] == "encrypted"

            conn.close()

            # Verify database is encrypted (cannot open without key)
            with pytest.raises(sqlcipher.DatabaseError):  # type: ignore[attr-defined]
                bad_conn = sqlcipher.connect(db_path)  # type: ignore[attr-defined]
                bad_conn.execute("SELECT * FROM test_table")
                bad_conn.close()

        finally:
            # Cleanup
            if os.path.exists(db_path):
                os.unlink(db_path)

    def test_schema_migration_execution(self):
        """Test that schema migration creates all required tables."""
        # Generate a test encryption key
        encryption_key = EncryptionKeyManager.generate_key()

        # Create temporary database
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name

        try:
            # Connect with encryption
            conn = sqlcipher.connect(db_path)  # type: ignore[attr-defined]
            conn.execute(f"PRAGMA key = '{encryption_key}'")
            conn.execute("PRAGMA cipher_page_size = 4096")

            # Read and execute migration script
            migration_path = (
                Path(__file__).parent.parent
                / "src"
                / "m365_mcp"
                / "migrations"
                / "001_init_cache.sql"
            )
            with open(migration_path, "r") as f:
                migration_sql = f.read()

            # Execute migration
            conn.executescript(migration_sql)
            conn.commit()

            # Verify all tables were created
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
            tables = [row[0] for row in cursor.fetchall()]

            expected_tables = [
                "cache_entries",
                "cache_invalidation",
                "cache_stats",
                "cache_tasks",
                "schema_version",
            ]

            for table in expected_tables:
                assert table in tables, f"Table {table} was not created"

            # Verify indexes were created
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' ORDER BY name"
            )
            indexes = [row[0] for row in cursor.fetchall()]

            expected_indexes = [
                "idx_cache_accessed",
                "idx_cache_account_fresh",
                "idx_cache_account_resource",
                "idx_cache_expires",
                "idx_invalidation_account_time",
                "idx_stats_period",
                "idx_tasks_account",
                "idx_tasks_created",
                "idx_tasks_status_priority",
            ]

            for index in expected_indexes:
                assert index in indexes, f"Index {index} was not created"

            # Verify schema_version entry
            cursor = conn.execute("SELECT version, description FROM schema_version")
            version_row = cursor.fetchone()
            assert version_row[0] == 1
            assert "Initial cache system" in version_row[1]

            # Verify initial stats entry was created
            cursor = conn.execute("SELECT COUNT(*) FROM cache_stats")
            stats_count = cursor.fetchone()[0]
            assert stats_count == 1, "Initial stats entry was not created"

            conn.close()

        finally:
            # Cleanup
            if os.path.exists(db_path):
                os.unlink(db_path)

    def test_table_structure_cache_entries(self):
        """Test cache_entries table has correct structure."""
        encryption_key = EncryptionKeyManager.generate_key()

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name

        try:
            conn = sqlcipher.connect(db_path)  # type: ignore[attr-defined]
            conn.execute(f"PRAGMA key = '{encryption_key}'")

            # Execute migration
            migration_path = (
                Path(__file__).parent.parent
                / "src"
                / "m365_mcp"
                / "migrations"
                / "001_init_cache.sql"
            )
            with open(migration_path, "r") as f:
                conn.executescript(f.read())

            # Get table info
            cursor = conn.execute("PRAGMA table_info(cache_entries)")
            columns = {row[1]: row[2] for row in cursor.fetchall()}  # name: type

            # Verify key columns exist
            expected_columns = [
                "cache_key",
                "account_id",
                "resource_type",
                "resource_id",
                "data_json",
                "is_compressed",
                "data_size_bytes",
                "created_at",
                "accessed_at",
                "fresh_until",
                "expires_at",
                "hit_count",
                "etag",
                "version",
            ]

            for col in expected_columns:
                assert col in columns, f"Column {col} missing from cache_entries"

            conn.close()

        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)


class TestCacheConfiguration:
    """Test cache configuration utilities."""

    def test_generate_cache_key(self):
        """Test cache key generation."""
        # Simple key without parameters
        key1 = generate_cache_key("acc-123", "folder_get_tree")
        assert key1 == "folder_get_tree:acc-123"

        # Key with parameters
        key2 = generate_cache_key(
            "acc-123", "folder_get_tree", {"folder_id": "root", "max_depth": 10}
        )
        assert key2.startswith("folder_get_tree:acc-123:")
        assert len(key2.split(":")) == 3

        # Same parameters should produce same key
        key3 = generate_cache_key(
            "acc-123", "folder_get_tree", {"folder_id": "root", "max_depth": 10}
        )
        assert key2 == key3

        # Different parameter order should produce same key (deterministic)
        key4 = generate_cache_key(
            "acc-123", "folder_get_tree", {"max_depth": 10, "folder_id": "root"}
        )
        assert key2 == key4

    def test_parse_cache_key(self):
        """Test cache key parsing."""
        # Simple key
        parsed = parse_cache_key("folder_get_tree:acc-123")
        assert parsed["resource_type"] == "folder_get_tree"
        assert parsed["account_id"] == "acc-123"
        assert "param_hash" not in parsed

        # Key with parameters
        parsed = parse_cache_key("folder_get_tree:acc-123:8f4b2c3d")
        assert parsed["resource_type"] == "folder_get_tree"
        assert parsed["account_id"] == "acc-123"
        assert parsed["param_hash"] == "8f4b2c3d"

    def test_ttl_policies_defined(self):
        """Test that all expected TTL policies are defined."""
        expected_resources = [
            "folder_get_tree",
            "folder_list",
            "email_list",
            "email_get",
            "file_list",
            "file_get",
            "contact_list",
            "contact_get",
            "calendar_list_events",
            "calendar_get_event",
            "search_emails",
            "search_files",
        ]

        for resource in expected_resources:
            assert resource in TTL_POLICIES, f"TTL policy for {resource} not defined"

    def test_get_ttl_policy(self):
        """Test TTL policy retrieval."""
        # Known resource type
        policy = get_ttl_policy("folder_get_tree")
        assert policy.fresh_seconds == 30 * 60
        assert policy.stale_seconds == 2 * 60 * 60

        # Unknown resource type (should return default)
        policy = get_ttl_policy("unknown_resource")
        assert policy.fresh_seconds == 5 * 60
        assert policy.stale_seconds == 15 * 60

    def test_ttl_policy_properties(self):
        """Test TTL policy helper properties."""
        policy = get_ttl_policy("folder_get_tree")

        assert policy.fresh_minutes == 30.0
        assert policy.stale_minutes == 120.0

    def test_cache_limits_values(self):
        """Test cache limits are set correctly."""
        assert CACHE_LIMITS.max_entry_bytes == 10 * 1024 * 1024  # 10 MB
        assert CACHE_LIMITS.max_total_bytes == 2 * 1024 * 1024 * 1024  # 2 GB
        assert CACHE_LIMITS.cleanup_threshold == 0.8
        assert CACHE_LIMITS.cleanup_target == 0.6
        assert CACHE_LIMITS.max_entries_per_account == 10000
        assert CACHE_LIMITS.compression_threshold == 50 * 1024  # 50 KB
        assert CACHE_LIMITS.compression_level == 6

    def test_cache_state_constants(self):
        """Test cache state constants are defined."""
        assert CacheState.FRESH.value == "fresh"
        assert CacheState.STALE.value == "stale"
        assert CacheState.EXPIRED.value == "expired"
        assert CacheState.MISSING.value == "missing"
