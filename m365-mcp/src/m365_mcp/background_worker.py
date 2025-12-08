"""
Background worker for executing cache warming and maintenance tasks.

This module provides an asynchronous background worker that processes tasks
from the cache_tasks queue with priority ordering, retry logic, and proper
error handling.
"""

import asyncio
import logging
import time
import traceback
from typing import Any, Optional

from .cache import CacheManager

logger = logging.getLogger(__name__)


class BackgroundWorker:
    """
    Asynchronous background worker for cache tasks.

    Processes tasks from the cache_tasks table with priority ordering,
    exponential backoff for retries, and graceful error handling.

    Attributes:
        cache_manager: CacheManager instance for task queue operations
        tool_executor: Callable for executing tool operations
        is_running: Whether the worker is currently running
        worker_task: The asyncio task running the worker loop
        max_retries: Maximum number of retries for failed tasks (default: 3)
        initial_backoff: Initial backoff delay in seconds (default: 1)
    """

    def __init__(
        self,
        cache_manager: CacheManager,
        tool_executor: Any,
        max_retries: int = 3,
        initial_backoff: float = 1.0,
    ):
        """
        Initialize the background worker.

        Args:
            cache_manager: CacheManager instance for accessing task queue
            tool_executor: Callable that can execute tool operations
            max_retries: Maximum retry attempts for failed tasks
            initial_backoff: Initial backoff delay in seconds for retries
        """
        self.cache_manager = cache_manager
        self.tool_executor = tool_executor
        self.is_running = False
        self.worker_task: Optional[asyncio.Task] = None
        self.max_retries = max_retries
        self.initial_backoff = initial_backoff

        logger.info(
            "BackgroundWorker initialized",
            extra={"max_retries": max_retries, "initial_backoff": initial_backoff},
        )

    async def start(self) -> None:
        """
        Start the background worker loop.

        Creates an asyncio task that runs the worker loop in the background.
        This method returns immediately, allowing the worker to run
        concurrently with other operations.

        Raises:
            RuntimeError: If the worker is already running
        """
        if self.is_running:
            raise RuntimeError("Background worker is already running")

        self.is_running = True
        self.worker_task = asyncio.create_task(self._worker_loop())

        logger.info("Background worker started")

    async def stop(self) -> None:
        """
        Stop the background worker gracefully.

        Signals the worker to stop and waits for the current task to complete.
        Cancels the worker task if it doesn't complete within a reasonable time.
        """
        if not self.is_running:
            logger.warning("Background worker is not running")
            return

        self.is_running = False

        if self.worker_task:
            try:
                # Wait up to 30 seconds for graceful shutdown
                await asyncio.wait_for(self.worker_task, timeout=30.0)
            except asyncio.TimeoutError:
                logger.warning("Background worker did not stop gracefully, cancelling")
                self.worker_task.cancel()
                try:
                    await self.worker_task
                except asyncio.CancelledError:
                    pass

        logger.info("Background worker stopped")

    async def _worker_loop(self) -> None:
        """
        Main worker loop that processes tasks from the queue.

        Continuously fetches and processes the next highest priority task
        until the worker is stopped. Implements a short sleep between
        iterations to prevent tight looping.
        """
        logger.info("Worker loop started")

        while self.is_running:
            try:
                # Process the next task
                processed = await self.process_next_task()

                if not processed:
                    # No tasks available, sleep briefly before checking again
                    await asyncio.sleep(1.0)
                else:
                    # Small delay between tasks to prevent overwhelming the system
                    await asyncio.sleep(0.1)

            except Exception as e:
                logger.error(
                    f"Unexpected error in worker loop: {e}",
                    extra={"error": str(e), "traceback": traceback.format_exc()},
                )
                # Sleep longer on errors to avoid error loops
                await asyncio.sleep(5.0)

        logger.info("Worker loop stopped")

    async def process_next_task(self) -> bool:
        """
        Process the next task from the queue.

        Fetches the highest priority queued task, executes it, and updates
        its status based on the result. Handles task failures with retry logic.

        Returns:
            bool: True if a task was processed, False if no tasks available
        """
        # Get the next task
        task = self._get_next_task()

        if not task:
            return False

        task_id = task["task_id"]
        operation = task["operation"]
        params = task.get("parameters", {})

        logger.info(
            f"Processing task {task_id}",
            extra={
                "task_id": task_id,
                "operation": operation,
                "priority": task.get("priority", 5),
            },
        )

        # Mark task as running
        self._update_task_status(
            task_id=task_id, status="running", started_at=time.time()
        )

        try:
            # Execute the operation
            result = await self._execute_operation(operation, params)

            # Mark task as completed
            import json

            self._update_task_status(
                task_id=task_id,
                status="completed",
                completed_at=time.time(),
                result_json=json.dumps(result),
            )

            logger.info(
                f"Task {task_id} completed successfully",
                extra={"task_id": task_id, "operation": operation},
            )

            return True

        except Exception as e:
            # Handle task failure
            await self._handle_task_failure(task, e)
            return True

    def _get_next_task(self) -> Optional[dict[str, Any]]:
        """
        Get the next highest priority queued task.

        Queries the cache_tasks table for tasks with status='queued',
        ordered by priority (1=highest) and created_at (oldest first).

        Returns:
            Optional[dict[str, Any]]: Task details if available, None otherwise
        """
        try:
            with self.cache_manager._db() as conn:
                cursor = conn.execute("""
                    SELECT task_id, account_id, operation, parameters_json,
                           priority, status, retry_count, created_at
                    FROM cache_tasks
                    WHERE status = 'queued'
                    ORDER BY priority ASC, created_at ASC
                    LIMIT 1
                """)

                row = cursor.fetchone()

                if row:
                    import json

                    return {
                        "task_id": row[0],
                        "account_id": row[1],
                        "operation": row[2],
                        "parameters": json.loads(row[3]) if row[3] else {},
                        "priority": row[4],
                        "status": row[5],
                        "retry_count": row[6],
                        "created_at": row[7],
                    }

                return None

        except Exception as e:
            logger.error(f"Error getting next task: {e}")
            return None

    def _update_task_status(self, task_id: str, status: str, **kwargs) -> None:
        """
        Update task status and related fields.

        Args:
            task_id: Unique task identifier
            status: New status (queued, running, completed, failed)
            **kwargs: Additional fields to update (started_at, completed_at, etc.)
        """
        try:
            # Build SET clause dynamically
            set_fields = ["status = ?"]
            values = [status]

            for field, value in kwargs.items():
                set_fields.append(f"{field} = ?")
                values.append(value)

            values.append(task_id)  # For WHERE clause

            with self.cache_manager._db() as conn:
                conn.execute(
                    f"""
                    UPDATE cache_tasks
                    SET {", ".join(set_fields)}
                    WHERE task_id = ?
                    """,
                    values,
                )
                conn.commit()

        except Exception as e:
            logger.error(
                f"Error updating task status: {e}",
                extra={"task_id": task_id, "status": status},
            )

    async def _handle_task_failure(
        self, task: dict[str, Any], error: Exception
    ) -> None:
        """
        Handle task failure with retry logic.

        Implements exponential backoff for retries. If max retries exceeded,
        marks the task as failed permanently.

        Args:
            task: Task details dictionary
            error: Exception that caused the failure
        """
        task_id = task["task_id"]
        retry_count = task.get("retry_count", 0)

        error_message = f"{type(error).__name__}: {str(error)}"

        if retry_count < self.max_retries:
            # Calculate exponential backoff delay
            backoff_delay = self.initial_backoff * (2**retry_count)

            logger.warning(
                f"Task {task_id} failed, will retry in {backoff_delay}s",
                extra={
                    "task_id": task_id,
                    "retry_count": retry_count + 1,
                    "max_retries": self.max_retries,
                    "error": error_message,
                },
            )

            # Update task for retry
            self._update_task_status(
                task_id=task_id,
                status="queued",
                retry_count=retry_count + 1,
                last_error=error_message,
            )

            # Sleep for backoff period
            await asyncio.sleep(backoff_delay)

        else:
            # Max retries exceeded, mark as failed
            logger.error(
                f"Task {task_id} failed permanently after {retry_count} retries",
                extra={
                    "task_id": task_id,
                    "operation": task.get("operation"),
                    "error": error_message,
                    "traceback": traceback.format_exc(),
                },
            )

            self._update_task_status(
                task_id=task_id,
                status="failed",
                completed_at=time.time(),
                last_error=error_message,
            )

    async def _execute_operation(
        self, operation: str, parameters: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Execute a tool operation.

        Args:
            operation: Tool operation name (e.g., "folder_get_tree")
            parameters: Parameters to pass to the tool

        Returns:
            dict[str, Any]: Operation result

        Raises:
            ValueError: If operation is not supported
            Exception: If operation execution fails
        """
        if not self.tool_executor:
            raise RuntimeError("No tool executor configured")

        # Execute the tool operation
        result = await self.tool_executor(operation, parameters)

        return {"success": True, "operation": operation, "result": result}
