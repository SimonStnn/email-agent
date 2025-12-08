"""
Tests for background worker task queue system.
"""

import asyncio
import pytest
import tempfile
from pathlib import Path

from src.m365_mcp.cache import CacheManager
from src.m365_mcp.background_worker import BackgroundWorker


@pytest.fixture
def temp_cache_db():
    """Create a temporary cache database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    yield db_path

    # Cleanup
    if db_path.exists():
        db_path.unlink()


@pytest.fixture
def cache_manager(temp_cache_db):
    """Create a CacheManager instance with temporary database."""
    return CacheManager(db_path=str(temp_cache_db), encryption_enabled=False)


@pytest.fixture
def mock_tool_executor():
    """Create a mock tool executor."""

    async def executor(operation: str, parameters: dict):
        # Simulate successful execution
        await asyncio.sleep(0.01)
        return {"success": True, "operation": operation}

    return executor


class TestTaskEnqueuing:
    """Test task enqueueing functionality."""

    def test_enqueue_task_basic(self, cache_manager):
        """Test basic task enqueueing."""
        task_id = cache_manager.enqueue_task(
            account_id="test-account",
            operation="folder_get_tree",
            parameters={"folder_id": "root"},
            priority=5,
        )

        assert task_id is not None
        assert len(task_id) == 36  # UUID format

        # Verify task was created
        task = cache_manager.get_task_status(task_id)
        assert task is not None
        assert task["account_id"] == "test-account"
        assert task["operation"] == "folder_get_tree"
        assert task["status"] == "queued"
        assert task["priority"] == 5
        assert task["retry_count"] == 0

    def test_enqueue_multiple_tasks(self, cache_manager):
        """Test enqueueing multiple tasks."""
        task_ids = []
        for i in range(5):
            task_id = cache_manager.enqueue_task(
                account_id=f"account-{i}",
                operation="email_list",
                parameters={"folder": "inbox"},
                priority=i + 1,
            )
            task_ids.append(task_id)

        assert len(task_ids) == 5
        assert len(set(task_ids)) == 5  # All unique

        # Verify all tasks exist
        tasks = cache_manager.list_tasks(limit=10)
        assert len(tasks) == 5


class TestTaskStatusTracking:
    """Test task status tracking."""

    def test_get_task_status(self, cache_manager):
        """Test getting task status."""
        task_id = cache_manager.enqueue_task(
            account_id="test-account",
            operation="folder_list",
            parameters={},
            priority=3,
        )

        status = cache_manager.get_task_status(task_id)
        assert status is not None
        assert status["task_id"] == task_id
        assert status["status"] == "queued"

    def test_list_tasks_no_filter(self, cache_manager):
        """Test listing all tasks."""
        for i in range(3):
            cache_manager.enqueue_task(
                account_id=f"account-{i}",
                operation="email_list",
                parameters={},
                priority=5,
            )

        tasks = cache_manager.list_tasks()
        assert len(tasks) == 3

    def test_list_tasks_by_account(self, cache_manager):
        """Test filtering tasks by account."""
        cache_manager.enqueue_task("account-1", "op1", {}, 5)
        cache_manager.enqueue_task("account-2", "op2", {}, 5)
        cache_manager.enqueue_task("account-1", "op3", {}, 5)

        tasks = cache_manager.list_tasks(account_id="account-1")
        assert len(tasks) == 2
        assert all(t["account_id"] == "account-1" for t in tasks)


class TestBackgroundWorker:
    """Test background worker execution."""

    @pytest.mark.asyncio
    async def test_worker_initialization(self, cache_manager, mock_tool_executor):
        """Test worker initialization."""
        worker = BackgroundWorker(cache_manager, mock_tool_executor)

        assert worker.cache_manager == cache_manager
        assert worker.tool_executor == mock_tool_executor
        assert worker.is_running is False
        assert worker.max_retries == 3

    @pytest.mark.asyncio
    async def test_worker_start_stop(self, cache_manager, mock_tool_executor):
        """Test starting and stopping worker."""
        worker = BackgroundWorker(cache_manager, mock_tool_executor)

        await worker.start()
        assert worker.is_running is True
        assert worker.worker_task is not None

        await worker.stop()
        assert worker.is_running is False

    @pytest.mark.asyncio
    async def test_process_single_task(self, cache_manager, mock_tool_executor):
        """Test processing a single task."""
        worker = BackgroundWorker(cache_manager, mock_tool_executor)

        task_id = cache_manager.enqueue_task(
            account_id="test-account",
            operation="folder_get_tree",
            parameters={"folder_id": "root"},
            priority=1,
        )

        # Process the task
        processed = await worker.process_next_task()
        assert processed is True

        # Check task status
        task = cache_manager.get_task_status(task_id)
        assert task["status"] == "completed"

    @pytest.mark.asyncio
    async def test_priority_ordering(self, cache_manager, mock_tool_executor):
        """Test tasks are processed in priority order."""
        worker = BackgroundWorker(cache_manager, mock_tool_executor)

        # Enqueue tasks with different priorities
        task_low = cache_manager.enqueue_task("acc", "op1", {}, priority=10)
        task_high = cache_manager.enqueue_task("acc", "op2", {}, priority=1)
        task_med = cache_manager.enqueue_task("acc", "op3", {}, priority=5)

        # Process first task (should be high priority)
        await worker.process_next_task()
        task = cache_manager.get_task_status(task_high)
        assert task["status"] == "completed"

        # Process second task (should be medium priority)
        await worker.process_next_task()
        task = cache_manager.get_task_status(task_med)
        assert task["status"] == "completed"

        # Process third task (should be low priority)
        await worker.process_next_task()
        task = cache_manager.get_task_status(task_low)
        assert task["status"] == "completed"


class TestRetryLogic:
    """Test retry logic for failed tasks."""

    @pytest.mark.asyncio
    async def test_task_retry_on_failure(self, cache_manager):
        """Test task is retried on failure."""
        call_count = 0

        async def failing_executor(operation, parameters):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Simulated failure")
            return {"success": True}

        worker = BackgroundWorker(cache_manager, failing_executor, max_retries=3)

        task_id = cache_manager.enqueue_task("acc", "op", {}, 5)

        # First attempt - should fail and retry
        await worker.process_next_task()
        task = cache_manager.get_task_status(task_id)
        assert task["status"] == "queued"
        assert task["retry_count"] == 1

        # Second attempt - should fail and retry
        await asyncio.sleep(1.5)  # Wait for backoff
        await worker.process_next_task()
        task = cache_manager.get_task_status(task_id)
        assert task["retry_count"] == 2

    @pytest.mark.asyncio
    async def test_task_fails_after_max_retries(self, cache_manager):
        """Test task marked failed after max retries."""

        async def always_failing_executor(operation, parameters):
            raise Exception("Always fails")

        worker = BackgroundWorker(cache_manager, always_failing_executor, max_retries=2)

        task_id = cache_manager.enqueue_task("acc", "op", {}, 5)

        # Process through all retries
        for _ in range(3):
            await worker.process_next_task()
            await asyncio.sleep(0.1)

        task = cache_manager.get_task_status(task_id)
        assert task["status"] == "failed"
        assert task["error"] is not None
