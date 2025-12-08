"""Cache warming implementation for M365 MCP Server.

This module provides background cache warming functionality to pre-populate
the cache with frequently accessed data on server startup.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Callable

from .cache import CacheManager
from .cache_config import CACHE_WARMING_OPERATIONS, CacheState

logger = logging.getLogger(__name__)


class CacheWarmer:
    """Manages background cache warming operations.

    The CacheWarmer pre-populates the cache with frequently accessed data
    to improve initial response times. It runs asynchronously without blocking
    server startup.
    """

    def __init__(
        self,
        cache_manager: CacheManager,
        tool_executor: Callable[[str, str, dict[str, Any]], Any],
        accounts: list[dict[str, str]],
    ):
        """Initialize the cache warmer.

        Args:
            cache_manager: CacheManager instance for checking cache status
            tool_executor: Callable that executes tool operations
                          Signature: (account_id, operation, params) -> result
            accounts: List of account dictionaries with account_id and username
        """
        self.cache_manager = cache_manager
        self.tool_executor = tool_executor
        self.accounts = accounts

        self.is_warming = False
        self.warming_started_at: datetime | None = None
        self.warming_completed_at: datetime | None = None
        self.operations_completed = 0
        self.operations_total = 0
        self.operations_skipped = 0
        self.operations_failed = 0

    async def start_warming(self) -> None:
        """Start the cache warming process.

        This method builds the warming queue and starts the warming loop
        asynchronously without blocking.
        """
        if self.is_warming:
            logger.warning("Cache warming already in progress")
            return

        if not self.accounts:
            logger.info("No accounts configured, skipping cache warming")
            return

        logger.info(f"Starting cache warming for {len(self.accounts)} account(s)")
        self.warming_started_at = datetime.now(timezone.utc)

        # Build warming queue
        warming_queue = self._build_warming_queue()
        self.operations_total = len(warming_queue)

        # Start warming loop asynchronously
        asyncio.create_task(self._warming_loop(warming_queue))

    def _build_warming_queue(self) -> list[dict[str, Any]]:
        """Build the queue of warming operations.

        Returns:
            List of warming operation dictionaries sorted by priority.
            Each dict contains: account_id, operation, params, priority, throttle_sec
        """
        queue = []

        for account in self.accounts:
            account_id = account.get("account_id")
            if not account_id:
                continue

            for operation_config in CACHE_WARMING_OPERATIONS:
                queue_item = {
                    "account_id": account_id,
                    "operation": operation_config["operation"],
                    "params": operation_config.get("params", {}),
                    "priority": operation_config.get("priority", 5),
                    "throttle_sec": operation_config.get("throttle_sec", 0.5),
                }
                queue.append(queue_item)

        # Sort by priority (lower number = higher priority)
        queue.sort(key=lambda x: x["priority"])

        return queue

    async def _warming_loop(self, queue: list[dict[str, Any]]) -> None:
        """Execute warming operations from the queue.

        Args:
            queue: List of warming operations to execute
        """
        self.is_warming = True

        # Initialize started_at if not already set
        if not self.warming_started_at:
            self.warming_started_at = datetime.now(timezone.utc)

        try:
            for item in queue:
                account_id = item["account_id"]
                operation = item["operation"]
                params = item["params"]
                throttle_sec = item["throttle_sec"]

                try:
                    # Check if already cached (skip if fresh)
                    cached_result = self.cache_manager.get_cached(
                        account_id, operation, params
                    )

                    if cached_result:
                        data, state = cached_result
                        if state == CacheState.FRESH:
                            logger.debug(
                                f"Skipping {operation} for account {account_id[:8]}... "
                                "(already cached)"
                            )
                            self.operations_skipped += 1
                            self.operations_completed += 1
                            continue

                    # Execute operation
                    logger.debug(
                        f"Warming cache: {operation} for account {account_id[:8]}..."
                    )
                    result = await self._execute_warming_operation(
                        account_id, operation, params
                    )

                    if result:
                        # Store in cache
                        self.cache_manager.set_cached(
                            account_id, operation, params, result
                        )
                        logger.debug(
                            f"Cached {operation} for account {account_id[:8]}..."
                        )

                    self.operations_completed += 1

                except Exception as e:
                    logger.warning(
                        f"Failed to warm cache for {operation} "
                        f"(account {account_id[:8]}...): {e}"
                    )
                    self.operations_failed += 1
                    self.operations_completed += 1

                # Throttle to avoid overwhelming the API
                if throttle_sec > 0:
                    await asyncio.sleep(throttle_sec)

            self.warming_completed_at = datetime.now(timezone.utc)
            duration = (
                self.warming_completed_at - self.warming_started_at
            ).total_seconds()

            logger.info(
                f"Cache warming completed in {duration:.1f}s: "
                f"{self.operations_completed - self.operations_failed - self.operations_skipped} "
                f"warmed, {self.operations_skipped} skipped, "
                f"{self.operations_failed} failed"
            )

        finally:
            self.is_warming = False

    async def _execute_warming_operation(
        self, account_id: str, operation: str, params: dict[str, Any]
    ) -> Any:
        """Execute a warming operation.

        Args:
            account_id: Account identifier
            operation: Operation name (e.g., "folder_get_tree")
            params: Operation parameters

        Returns:
            Operation result

        Raises:
            Exception: If operation execution fails
        """
        # Call tool executor (async or sync)
        result = self.tool_executor(account_id, operation, params)

        # If result is a coroutine, await it
        if asyncio.iscoroutine(result):
            result = await result

        return result

    def get_warming_status(self) -> dict[str, Any]:
        """Get the current warming status.

        Returns:
            Dictionary with warming status information
        """
        status = {
            "is_warming": self.is_warming,
            "operations_total": self.operations_total,
            "operations_completed": self.operations_completed,
            "operations_skipped": self.operations_skipped,
            "operations_failed": self.operations_failed,
        }

        if self.warming_started_at:
            status["started_at"] = self.warming_started_at.isoformat()

        if self.warming_completed_at:
            status["completed_at"] = self.warming_completed_at.isoformat()
            if self.warming_started_at:
                duration = (
                    self.warming_completed_at - self.warming_started_at
                ).total_seconds()
                status["duration_seconds"] = round(duration, 2)
        elif self.is_warming:
            # Calculate current duration if still warming
            if self.warming_started_at:
                duration = (
                    datetime.now(timezone.utc) - self.warming_started_at
                ).total_seconds()
                status["duration_seconds"] = round(duration, 2)

        # Calculate progress percentage
        if self.operations_total > 0:
            progress = (self.operations_completed / self.operations_total) * 100
            status["progress_percent"] = round(progress, 1)
        else:
            status["progress_percent"] = 0.0

        return status
