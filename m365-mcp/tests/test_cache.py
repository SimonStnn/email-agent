"""
Tests for encrypted cache manager.
"""

import pytest
import tempfile
from pathlib import Path
import time

from src.m365_mcp.cache import CacheManager, CacheState
from src.m365_mcp.cache_config import generate_cache_key


@pytest.fixture
def temp_cache_db():
    """Create temporary cache database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    yield str(db_path)

    # Cleanup
    if db_path.exists():
        db_path.unlink()


@pytest.fixture
def cache_manager(temp_cache_db):
    """Create cache manager instance for testing."""
    return CacheManager(db_path=temp_cache_db, encryption_enabled=True)


@pytest.fixture
def cache_manager_no_encryption(temp_cache_db):
    """Create cache manager without encryption for testing."""
    return CacheManager(db_path=temp_cache_db, encryption_enabled=False)


class TestCacheBasics:
    """Test basic cache operations."""

    def test_cache_initialization(self, cache_manager):
        """Test cache manager initializes correctly."""
        assert cache_manager is not None
        assert cache_manager.db_path.exists()
        assert cache_manager.encryption_enabled is True

    def test_cache_initialization_no_encryption(self, cache_manager_no_encryption):
        """Test cache manager initializes without encryption."""
        assert cache_manager_no_encryption is not None
        assert cache_manager_no_encryption.encryption_enabled is False

    def test_set_and_get_cached(self, cache_manager):
        """Test basic set and get operations."""
        account_id = "test-account-123"
        resource_type = "folder_get_tree"
        params = {"folder_id": "root"}
        data = {"folders": ["Inbox", "Sent", "Draft"]}

        # Set cache
        cache_manager.set_cached(account_id, resource_type, params, data)

        # Get cache
        result = cache_manager.get_cached(account_id, resource_type, params)

        assert result is not None
        cached_data, state = result
        assert cached_data == data
        assert state == CacheState.FRESH

    def test_cache_miss(self, cache_manager):
        """Test cache miss returns None."""
        result = cache_manager.get_cached(
            "nonexistent-account", "email_list", {"folder_id": "inbox"}
        )
        assert result is None

    def test_cache_key_generation(self):
        """Test cache key generation is consistent."""
        key1 = generate_cache_key("acc1", "email_list", {"folder": "inbox"})
        key2 = generate_cache_key("acc1", "email_list", {"folder": "inbox"})
        key3 = generate_cache_key("acc1", "email_list", {"folder": "sent"})

        assert key1 == key2
        assert key1 != key3


class TestCacheCompression:
    """Test compression functionality."""

    def test_small_entry_no_compression(self, cache_manager):
        """Test small entries are not compressed."""
        account_id = "test-account"
        resource_type = "email_get"
        params = {"email_id": "123"}
        data = {"subject": "Test", "body": "Small email"}

        cache_manager.set_cached(account_id, resource_type, params, data)

        # Check database directly
        cache_key = generate_cache_key(account_id, resource_type, params)
        with cache_manager._db() as conn:
            cursor = conn.execute(
                "SELECT is_compressed FROM cache_entries WHERE cache_key = ?",
                (cache_key,),
            )
            row = cursor.fetchone()
            assert row["is_compressed"] == 0

    def test_large_entry_compression(self, cache_manager):
        """Test large entries are compressed."""
        account_id = "test-account"
        resource_type = "email_list"
        params = {"folder_id": "inbox"}

        # Create large data (>50KB)
        data = {"emails": [{"id": str(i), "subject": "X" * 1000} for i in range(100)]}

        cache_manager.set_cached(account_id, resource_type, params, data)

        # Check database directly
        cache_key = generate_cache_key(account_id, resource_type, params)
        with cache_manager._db() as conn:
            cursor = conn.execute(
                "SELECT is_compressed FROM cache_entries WHERE cache_key = ?",
                (cache_key,),
            )
            row = cursor.fetchone()
            assert row["is_compressed"] == 1

        # Verify data is still retrievable
        result = cache_manager.get_cached(account_id, resource_type, params)
        assert result is not None
        cached_data, _ = result
        assert cached_data == data


class TestCacheTTL:
    """Test TTL and state detection."""

    def test_fresh_state(self, cache_manager):
        """Test fresh cache state."""
        account_id = "test-account"
        resource_type = "folder_get_tree"
        params = {"folder_id": "root"}
        data = {"folders": ["Inbox"]}

        cache_manager.set_cached(account_id, resource_type, params, data)

        # Immediately retrieve (should be FRESH)
        result = cache_manager.get_cached(account_id, resource_type, params)
        assert result is not None
        _, state = result
        assert state == CacheState.FRESH

    def test_stale_state(self, cache_manager, monkeypatch):
        """Test stale cache state."""
        account_id = "test-account"
        resource_type = "folder_get_tree"  # fresh=1800s, stale=7200s
        params = {"folder_id": "root"}
        data = {"folders": ["Inbox"]}

        # Set cache
        cache_manager.set_cached(account_id, resource_type, params, data)

        # Modify created_at to simulate age
        cache_key = generate_cache_key(account_id, resource_type, params)
        old_time = time.time() - 3600  # 1 hour ago (past fresh, within stale)

        with cache_manager._db() as conn:
            conn.execute(
                "UPDATE cache_entries SET created_at = ? WHERE cache_key = ?",
                (old_time, cache_key),
            )

        # Retrieve (should be STALE)
        result = cache_manager.get_cached(account_id, resource_type, params)
        assert result is not None
        _, state = result
        assert state == CacheState.STALE

    def test_expired_state(self, cache_manager):
        """Test expired cache returns None."""
        account_id = "test-account"
        resource_type = "folder_get_tree"  # stale=7200s
        params = {"folder_id": "root"}
        data = {"folders": ["Inbox"]}

        # Set cache
        cache_manager.set_cached(account_id, resource_type, params, data)

        # Modify created_at to simulate old age
        cache_key = generate_cache_key(account_id, resource_type, params)
        old_time = time.time() - 10000  # Way past stale threshold

        with cache_manager._db() as conn:
            conn.execute(
                "UPDATE cache_entries SET created_at = ? WHERE cache_key = ?",
                (old_time, cache_key),
            )

        # Retrieve (should be None - expired)
        result = cache_manager.get_cached(account_id, resource_type, params)
        assert result is None


class TestCacheInvalidation:
    """Test cache invalidation."""

    def test_invalidate_exact_match(self, cache_manager):
        """Test invalidation with exact pattern."""
        account_id = "test-account"

        # Set multiple cache entries
        for i in range(3):
            cache_manager.set_cached(
                account_id, "email_list", {"folder_id": f"folder-{i}"}, {"emails": []}
            )

        # Invalidate specific entry
        pattern = generate_cache_key(
            account_id, "email_list", {"folder_id": "folder-1"}
        )
        count = cache_manager.invalidate_pattern(pattern)

        assert count == 1

    def test_invalidate_wildcard(self, cache_manager):
        """Test invalidation with wildcard pattern."""
        account_id = "test-account"

        # Set entries for different resource types
        cache_manager.set_cached(
            account_id, "email_list", {"folder": "inbox"}, {"emails": []}
        )
        cache_manager.set_cached(
            account_id, "email_get", {"id": "123"}, {"subject": "Test"}
        )
        cache_manager.set_cached(account_id, "folder_list", {}, {"folders": []})

        # Invalidate all email_* entries
        count = cache_manager.invalidate_pattern("email_*")

        assert count >= 2  # Should invalidate email_list and email_get

    def test_invalidate_by_account(self, cache_manager):
        """Test invalidating all entries for an account."""
        # Set entries for different accounts
        cache_manager.set_cached("account-1", "email_list", {}, {"emails": []})
        cache_manager.set_cached("account-2", "email_list", {}, {"emails": []})
        cache_manager.set_cached("account-1", "folder_list", {}, {"folders": []})

        # Invalidate all for account-1
        count = cache_manager.invalidate_pattern("*account-1*")

        assert count == 2


class TestCacheCleanup:
    """Test cache cleanup functionality."""

    def test_cleanup_expired(self, cache_manager):
        """Test manual cleanup of expired entries."""
        account_id = "test-account"
        resource_type = "email_list"

        # Add entry
        cache_manager.set_cached(
            account_id, resource_type, {"folder": "inbox"}, {"emails": []}
        )

        # Make it expired
        cache_key = generate_cache_key(account_id, resource_type, {"folder": "inbox"})
        old_time = time.time() - 10000

        with cache_manager._db() as conn:
            conn.execute(
                "UPDATE cache_entries SET created_at = ?, expires_at = ? WHERE cache_key = ?",
                (old_time, old_time, cache_key),
            )

        # Cleanup
        count = cache_manager.cleanup_expired()

        assert count == 1

        # Verify entry is gone
        result = cache_manager.get_cached(
            account_id, resource_type, {"folder": "inbox"}
        )
        assert result is None


class TestCacheStats:
    """Test cache statistics."""

    def test_get_stats_empty(self, cache_manager):
        """Test stats for empty cache."""
        stats = cache_manager.get_stats()

        assert stats["entry_count"] == 0
        assert stats["total_bytes"] == 0
        assert stats["usage_percent"] >= 0

    def test_get_stats_with_entries(self, cache_manager):
        """Test stats with cache entries."""
        # Add entries
        cache_manager.set_cached("account-1", "email_list", {}, {"emails": []})
        cache_manager.set_cached("account-1", "folder_list", {}, {"folders": []})
        cache_manager.set_cached("account-2", "email_list", {}, {"emails": []})

        stats = cache_manager.get_stats()

        assert stats["entry_count"] == 3
        assert stats["total_bytes"] > 0
        assert len(stats["by_account"]) == 2
        assert "account-1" in stats["by_account"]
        assert "account-2" in stats["by_account"]

    def test_hit_count_tracking(self, cache_manager):
        """Test cache hit count is tracked."""
        account_id = "test-account"
        resource_type = "email_list"
        params = {"folder": "inbox"}

        cache_manager.set_cached(account_id, resource_type, params, {"emails": []})

        # Access multiple times
        for _ in range(5):
            cache_manager.get_cached(account_id, resource_type, params)

        # Check hit count in database
        cache_key = generate_cache_key(account_id, resource_type, params)
        with cache_manager._db() as conn:
            cursor = conn.execute(
                "SELECT hit_count FROM cache_entries WHERE cache_key = ?", (cache_key,)
            )
            row = cursor.fetchone()
            assert row["hit_count"] == 5


class TestCacheEncryption:
    """Test encryption functionality."""

    def test_encrypted_cache_creation(self, cache_manager):
        """Test encrypted cache is created."""
        assert cache_manager.encryption_enabled is True
        assert cache_manager.encryption_key is not None

    def test_data_encrypted_at_rest(self, cache_manager):
        """Test data is encrypted in database file."""
        account_id = "test-account"
        sensitive_data = {"password": "super-secret-123", "token": "abc123"}

        cache_manager.set_cached(account_id, "test_type", {}, sensitive_data)

        # Read raw database file
        with open(cache_manager.db_path, "rb") as f:
            raw_content = f.read()

        # Sensitive data should NOT appear in plaintext
        assert b"super-secret-123" not in raw_content
        assert b"abc123" not in raw_content
