"""Integration tests for tool caching functionality.

Tests cache behavior for the cache manager used by folder_get_tree, email_list, and file_list tools.
"""

import pytest
from src.m365_mcp.cache import CacheManager
from src.m365_mcp.cache_config import CacheState, generate_cache_key


@pytest.fixture
def cache_manager(tmp_path):
    """Create a temporary cache manager for testing."""
    db_path = tmp_path / "test_cache.db"
    cache_mgr = CacheManager(db_path=str(db_path))
    return cache_mgr


@pytest.fixture
def test_account_id():
    """Return a test account ID."""
    return "test-account-123"


class TestCacheKeyGeneration:
    """Test cache key generation for different operations."""

    def test_folder_get_tree_key_generation(self, test_account_id):
        """Test cache key generation for folder_get_tree."""
        params1 = {"path": "/", "folder_id": None, "max_depth": 10}
        params2 = {"path": "/Documents", "folder_id": None, "max_depth": 10}

        key1 = generate_cache_key(test_account_id, "folder_get_tree", params1)
        key2 = generate_cache_key(test_account_id, "folder_get_tree", params2)

        # Keys should be different for different parameters
        assert key1 != key2
        assert key1.startswith("folder_get_tree:")
        assert test_account_id in key1

    def test_email_list_key_generation(self, test_account_id):
        """Test cache key generation for email_list."""
        params1 = {
            "folder": "inbox",
            "folder_id": None,
            "folder_path": "inbox",
            "limit": 10,
            "include_body": True,
        }
        params2 = {
            "folder": "sent",
            "folder_id": None,
            "folder_path": "sent",
            "limit": 10,
            "include_body": True,
        }

        key1 = generate_cache_key(test_account_id, "email_list", params1)
        key2 = generate_cache_key(test_account_id, "email_list", params2)

        # Keys should be different for different folders
        assert key1 != key2
        assert key1.startswith("email_list:")

    def test_file_list_key_generation(self, test_account_id):
        """Test cache key generation for file_list."""
        params1 = {"path": "/", "folder_id": None, "limit": 50, "type_filter": "all"}
        params2 = {"path": "/", "folder_id": None, "limit": 100, "type_filter": "all"}

        key1 = generate_cache_key(test_account_id, "file_list", params1)
        key2 = generate_cache_key(test_account_id, "file_list", params2)

        # Keys should be different for different limits
        assert key1 != key2
        assert key1.startswith("file_list:")


class TestCacheOperations:
    """Test basic cache operations."""

    def test_cache_miss_on_first_get(self, cache_manager, test_account_id):
        """Test that getting non-existent cache returns None."""
        params = {"path": "/", "max_depth": 10}
        result = cache_manager.get_cached(test_account_id, "folder_get_tree", params)

        assert result is None

    def test_cache_hit_after_set(self, cache_manager, test_account_id):
        """Test that cached data can be retrieved."""
        params = {"path": "/", "max_depth": 10}
        data = {"folders": [], "root_path": "/"}

        # Store in cache
        cache_manager.set_cached(test_account_id, "folder_get_tree", params, data)

        # Retrieve from cache
        result = cache_manager.get_cached(test_account_id, "folder_get_tree", params)

        assert result is not None
        cached_data, state = result
        assert cached_data == data
        assert state == CacheState.FRESH

    def test_cache_isolation_by_params(self, cache_manager, test_account_id):
        """Test that different parameters have separate cache entries."""
        params1 = {"path": "/", "max_depth": 10}
        params2 = {"path": "/Documents", "max_depth": 10}

        data1 = {"folders": [], "root_path": "/"}
        data2 = {"folders": [{"name": "folder1"}], "root_path": "/Documents"}

        # Store different data for different parameters
        cache_manager.set_cached(test_account_id, "folder_get_tree", params1, data1)
        cache_manager.set_cached(test_account_id, "folder_get_tree", params2, data2)

        # Retrieve and verify each has correct data
        result1 = cache_manager.get_cached(test_account_id, "folder_get_tree", params1)
        result2 = cache_manager.get_cached(test_account_id, "folder_get_tree", params2)

        assert result1 is not None
        assert result2 is not None
        assert result1[0] == data1
        assert result2[0] == data2

    def test_cache_isolation_by_account(self, cache_manager):
        """Test that different accounts have separate cache entries."""
        account1 = "account-1"
        account2 = "account-2"
        params = {"path": "/", "max_depth": 10}

        data1 = {"folders": [], "account": "account-1"}
        data2 = {"folders": [], "account": "account-2"}

        # Store different data for different accounts
        cache_manager.set_cached(account1, "folder_get_tree", params, data1)
        cache_manager.set_cached(account2, "folder_get_tree", params, data2)

        # Retrieve and verify each account has correct data
        result1 = cache_manager.get_cached(account1, "folder_get_tree", params)
        result2 = cache_manager.get_cached(account2, "folder_get_tree", params)

        assert result1 is not None
        assert result2 is not None
        assert result1[0] == data1
        assert result2[0] == data2


class TestCacheStateDetection:
    """Test cache state (fresh/stale/expired) detection."""

    def test_fresh_state_within_fresh_window(self, cache_manager, test_account_id):
        """Test that recently cached data is marked as FRESH."""
        params = {"folder": "inbox", "limit": 10}
        data = [{"id": "email-1", "subject": "Test"}]

        # Store in cache
        cache_manager.set_cached(test_account_id, "email_list", params, data)

        # Immediately retrieve (should be fresh)
        result = cache_manager.get_cached(test_account_id, "email_list", params)

        assert result is not None
        cached_data, state = result
        assert state == CacheState.FRESH
        assert cached_data == data

    def test_invalidate_pattern(self, cache_manager, test_account_id):
        """Test cache invalidation with patterns."""
        # Store multiple cache entries
        params1 = {"folder": "inbox", "limit": 10}
        params2 = {"folder": "sent", "limit": 10}

        cache_manager.set_cached(test_account_id, "email_list", params1, [{"id": "1"}])
        cache_manager.set_cached(test_account_id, "email_list", params2, [{"id": "2"}])

        # Invalidate all email_list entries for this account
        cache_manager.invalidate_pattern(f"email_list:{test_account_id}*")

        # Verify both were invalidated
        result1 = cache_manager.get_cached(test_account_id, "email_list", params1)
        result2 = cache_manager.get_cached(test_account_id, "email_list", params2)

        assert result1 is None
        assert result2 is None


class TestCacheStats:
    """Test cache statistics tracking."""

    def test_hit_count_tracking(self, cache_manager, test_account_id):
        """Test that cache hit counts are tracked."""
        params = {"path": "/", "max_depth": 10}
        data = {"folders": []}

        # Store in cache
        cache_manager.set_cached(test_account_id, "folder_get_tree", params, data)

        # Access multiple times
        cache_manager.get_cached(test_account_id, "folder_get_tree", params)
        cache_manager.get_cached(test_account_id, "folder_get_tree", params)
        cache_manager.get_cached(test_account_id, "folder_get_tree", params)

        # Get stats
        stats = cache_manager.get_stats()

        # Verify hit count increased and entry exists
        assert stats["entry_count"] > 0
        assert stats["total_hits"] >= 3

    def test_cache_stats_structure(self, cache_manager, test_account_id):
        """Test that cache stats return proper structure."""
        params = {"path": "/", "max_depth": 10}
        data = {"folders": []}

        # Store in cache
        cache_manager.set_cached(test_account_id, "folder_get_tree", params, data)

        # Get stats
        stats = cache_manager.get_stats()

        # Verify expected fields exist
        assert "entry_count" in stats
        assert "total_bytes" in stats
        assert "avg_bytes" in stats
        assert "total_hits" in stats
        assert "max_bytes" in stats
        assert "usage_percent" in stats
        assert "by_account" in stats
        assert "by_resource" in stats

        # Verify entry was counted
        assert stats["entry_count"] == 1
        assert test_account_id in stats["by_account"]
