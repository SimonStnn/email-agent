"""Tests for cache warming functionality.

This module tests the CacheWarmer class and cache warming operations.
"""

import asyncio
import pytest
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.m365_mcp.cache import CacheManager
from src.m365_mcp.cache_warming import CacheWarmer
from src.m365_mcp.cache_config import CacheState


@pytest.fixture
def temp_db():
    """Create temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    yield db_path

    # Cleanup
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def cache_manager(temp_db):
    """Create CacheManager instance for testing."""
    return CacheManager(db_path=temp_db, encryption_enabled=False)


@pytest.fixture
def mock_accounts():
    """Create mock account list."""
    return [
        {"account_id": "account-1", "username": "user1@example.com"},
        {"account_id": "account-2", "username": "user2@example.com"},
    ]


@pytest.fixture
def mock_tool_executor():
    """Create mock tool executor function."""
    call_log = []

    def executor(
        account_id: str, operation: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Mock tool executor that logs calls and returns test data."""
        call_log.append(
            {
                "account_id": account_id,
                "operation": operation,
                "params": params,
            }
        )

        # Return operation-specific test data
        if operation == "folder_get_tree":
            return {
                "folder_id": params.get("folder_id", "root"),
                "children": [
                    {"id": "folder-1", "name": "Documents"},
                    {"id": "folder-2", "name": "Pictures"},
                ],
            }
        elif operation == "email_list":
            return {
                "emails": [
                    {"id": "email-1", "subject": "Test 1"},
                    {"id": "email-2", "subject": "Test 2"},
                ]
            }
        elif operation == "contact_list":
            return {
                "contacts": [
                    {"id": "contact-1", "name": "Alice"},
                    {"id": "contact-2", "name": "Bob"},
                ]
            }
        else:
            return {"result": "success"}

    # Attach call log to function for inspection
    executor.call_log = call_log

    return executor


class TestCacheWarmerInit:
    """Tests for CacheWarmer initialization."""

    def test_init_with_valid_parameters(
        self, cache_manager, mock_accounts, mock_tool_executor
    ):
        """Test initialization with valid parameters."""
        warmer = CacheWarmer(cache_manager, mock_tool_executor, mock_accounts)

        assert warmer.cache_manager is cache_manager
        assert warmer.tool_executor is mock_tool_executor
        assert warmer.accounts == mock_accounts
        assert warmer.is_warming is False
        assert warmer.warming_started_at is None
        assert warmer.warming_completed_at is None
        assert warmer.operations_completed == 0
        assert warmer.operations_total == 0

    def test_init_with_empty_accounts(self, cache_manager, mock_tool_executor):
        """Test initialization with empty account list."""
        warmer = CacheWarmer(cache_manager, mock_tool_executor, [])

        assert warmer.accounts == []
        assert warmer.is_warming is False


class TestBuildWarmingQueue:
    """Tests for warming queue building."""

    def test_build_queue_with_single_account(
        self, cache_manager, mock_accounts, mock_tool_executor
    ):
        """Test queue building with single account."""
        single_account = [mock_accounts[0]]
        warmer = CacheWarmer(cache_manager, mock_tool_executor, single_account)

        queue = warmer._build_warming_queue()

        # Should have 3 operations per account (from CACHE_WARMING_OPERATIONS)
        assert len(queue) == 3

        # Check first operation
        assert queue[0]["account_id"] == "account-1"
        assert queue[0]["operation"] == "folder_get_tree"
        assert queue[0]["priority"] == 1
        assert queue[0]["throttle_sec"] == 5

    def test_build_queue_with_multiple_accounts(
        self, cache_manager, mock_accounts, mock_tool_executor
    ):
        """Test queue building with multiple accounts."""
        warmer = CacheWarmer(cache_manager, mock_tool_executor, mock_accounts)

        queue = warmer._build_warming_queue()

        # Should have 3 operations × 2 accounts = 6 total
        assert len(queue) == 6

        # Verify both accounts are represented
        account_ids = {item["account_id"] for item in queue}
        assert account_ids == {"account-1", "account-2"}

    def test_queue_sorted_by_priority(
        self, cache_manager, mock_accounts, mock_tool_executor
    ):
        """Test that queue is sorted by priority."""
        warmer = CacheWarmer(cache_manager, mock_tool_executor, mock_accounts)

        queue = warmer._build_warming_queue()

        # Verify priorities are in ascending order (lower = higher priority)
        priorities = [item["priority"] for item in queue]
        assert priorities == sorted(priorities)

    def test_build_queue_with_empty_accounts(self, cache_manager, mock_tool_executor):
        """Test queue building with no accounts."""
        warmer = CacheWarmer(cache_manager, mock_tool_executor, [])

        queue = warmer._build_warming_queue()

        assert len(queue) == 0


@pytest.mark.asyncio
class TestWarmingLoop:
    """Tests for warming loop execution."""

    async def test_warming_loop_executes_all_operations(
        self, cache_manager, mock_accounts, mock_tool_executor
    ):
        """Test that warming loop executes all operations."""
        # Use single account for simpler verification
        single_account = [mock_accounts[0]]
        warmer = CacheWarmer(cache_manager, mock_tool_executor, single_account)

        queue = warmer._build_warming_queue()
        await warmer._warming_loop(queue)

        # Should have executed 3 operations
        assert len(mock_tool_executor.call_log) == 3

        # Verify all operations were called
        operations = [call["operation"] for call in mock_tool_executor.call_log]
        assert "folder_get_tree" in operations
        assert "email_list" in operations
        assert "contact_list" in operations

    async def test_warming_loop_caches_results(
        self, cache_manager, mock_accounts, mock_tool_executor
    ):
        """Test that warming loop stores results in cache."""
        single_account = [mock_accounts[0]]
        warmer = CacheWarmer(cache_manager, mock_tool_executor, single_account)

        queue = warmer._build_warming_queue()
        await warmer._warming_loop(queue)

        # Check that results are cached
        cached = cache_manager.get_cached(
            "account-1", "folder_get_tree", {"folder_id": "root", "max_depth": 10}
        )

        assert cached is not None
        data, state = cached
        assert "folder_id" in data
        assert state in [CacheState.FRESH, CacheState.STALE]

    async def test_warming_loop_skips_fresh_cache(
        self, cache_manager, mock_accounts, mock_tool_executor
    ):
        """Test that warming loop skips operations with fresh cache."""
        single_account = [mock_accounts[0]]
        warmer = CacheWarmer(cache_manager, mock_tool_executor, single_account)

        # Pre-populate cache with fresh data
        cache_manager.set_cached(
            "account-1",
            "folder_get_tree",
            {"folder_id": "root", "max_depth": 10},
            {"pre_cached": True},
        )

        queue = warmer._build_warming_queue()
        await warmer._warming_loop(queue)

        # Should have skipped folder_get_tree (already cached)
        assert warmer.operations_skipped >= 1

        # Check that the cached data wasn't overwritten
        cached = cache_manager.get_cached(
            "account-1", "folder_get_tree", {"folder_id": "root", "max_depth": 10}
        )
        assert cached is not None
        data, state = cached
        assert data["pre_cached"] is True

    async def test_warming_loop_handles_failures_gracefully(
        self, cache_manager, mock_accounts
    ):
        """Test that warming loop handles operation failures."""

        def failing_executor(account_id: str, operation: str, params: dict[str, Any]):
            """Executor that always fails."""
            raise Exception("Simulated failure")

        single_account = [mock_accounts[0]]
        warmer = CacheWarmer(cache_manager, failing_executor, single_account)

        queue = warmer._build_warming_queue()

        # Should not raise exception
        await warmer._warming_loop(queue)

        # Should have recorded failures
        assert warmer.operations_failed == len(queue)
        assert warmer.operations_completed == len(queue)

    async def test_warming_loop_sets_completion_time(
        self, cache_manager, mock_accounts, mock_tool_executor
    ):
        """Test that warming loop sets completion time."""
        single_account = [mock_accounts[0]]
        warmer = CacheWarmer(cache_manager, mock_tool_executor, single_account)

        queue = warmer._build_warming_queue()
        await warmer._warming_loop(queue)

        assert warmer.warming_completed_at is not None
        assert isinstance(warmer.warming_completed_at, datetime)


@pytest.mark.asyncio
class TestStartWarming:
    """Tests for start_warming method."""

    async def test_start_warming_with_accounts(
        self, cache_manager, mock_accounts, mock_tool_executor
    ):
        """Test starting warming process with accounts."""
        warmer = CacheWarmer(cache_manager, mock_tool_executor, mock_accounts)

        await warmer.start_warming()

        # Give async task time to start
        await asyncio.sleep(0.1)

        # Should have set started time and total operations
        assert warmer.warming_started_at is not None
        assert warmer.operations_total > 0

    async def test_start_warming_with_no_accounts(
        self, cache_manager, mock_tool_executor
    ):
        """Test starting warming with no accounts."""
        warmer = CacheWarmer(cache_manager, mock_tool_executor, [])

        await warmer.start_warming()

        # Should not start warming
        assert warmer.warming_started_at is None
        assert warmer.operations_total == 0

    async def test_start_warming_prevents_double_start(
        self, cache_manager, mock_accounts, mock_tool_executor
    ):
        """Test that start_warming prevents double starts."""
        warmer = CacheWarmer(cache_manager, mock_tool_executor, mock_accounts)

        # Manually set is_warming flag
        warmer.is_warming = True

        await warmer.start_warming()

        # Should not have updated started time
        assert warmer.warming_started_at is None


class TestWarmingStatus:
    """Tests for get_warming_status method."""

    def test_status_before_warming(
        self, cache_manager, mock_accounts, mock_tool_executor
    ):
        """Test status before warming starts."""
        warmer = CacheWarmer(cache_manager, mock_tool_executor, mock_accounts)

        status = warmer.get_warming_status()

        assert status["is_warming"] is False
        assert status["operations_total"] == 0
        assert status["operations_completed"] == 0
        assert status["progress_percent"] == 0.0
        assert "started_at" not in status

    @pytest.mark.asyncio
    async def test_status_during_warming(
        self, cache_manager, mock_accounts, mock_tool_executor
    ):
        """Test status during warming process."""
        warmer = CacheWarmer(cache_manager, mock_tool_executor, mock_accounts)

        await warmer.start_warming()
        await asyncio.sleep(0.1)  # Give task time to start

        status = warmer.get_warming_status()

        # Should show warming in progress
        assert status["operations_total"] > 0
        assert "started_at" in status

    @pytest.mark.asyncio
    async def test_status_after_warming_complete(
        self, cache_manager, mock_accounts, mock_tool_executor
    ):
        """Test status after warming completes."""
        single_account = [mock_accounts[0]]
        warmer = CacheWarmer(cache_manager, mock_tool_executor, single_account)

        # Execute warming synchronously for this test
        queue = warmer._build_warming_queue()
        warmer.warming_started_at = datetime.now(timezone.utc)
        warmer.operations_total = len(queue)
        await warmer._warming_loop(queue)

        status = warmer.get_warming_status()

        assert status["is_warming"] is False
        assert status["operations_completed"] == status["operations_total"]
        assert status["progress_percent"] == 100.0
        assert "completed_at" in status
        assert "duration_seconds" in status
        assert status["duration_seconds"] >= 0
