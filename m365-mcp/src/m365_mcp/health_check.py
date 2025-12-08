"""
Health check utility for Microsoft MCP Server.

This module provides health check functionality that can be used
for monitoring, testing, and diagnostics.
"""

import asyncio
import sys
import time
from typing import Any, Optional
from dataclasses import dataclass
import httpx
import logging

logger = logging.getLogger(__name__)


@dataclass
class HealthCheckResult:
    """Result of a health check operation."""

    success: bool
    status_code: Optional[int]
    response_time_ms: float
    error: Optional[str] = None
    details: Optional[dict[str, Any]] = None


async def check_health_async(
    url: str,
    timeout: float = 5.0,
    auth_token: Optional[str] = None,
) -> HealthCheckResult:
    """
    Perform an async health check against the MCP server.

    Args:
        url: Health check endpoint URL
        timeout: Request timeout in seconds
        auth_token: Optional bearer token for authentication

    Returns:
        HealthCheckResult with success status and metrics
    """
    start_time = time.time()

    headers = {}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url, headers=headers)

            response_time_ms = (time.time() - start_time) * 1000

            if response.status_code == 200:
                try:
                    details = response.json()
                except Exception:
                    details = None

                return HealthCheckResult(
                    success=True,
                    status_code=response.status_code,
                    response_time_ms=response_time_ms,
                    details=details,
                )
            else:
                return HealthCheckResult(
                    success=False,
                    status_code=response.status_code,
                    response_time_ms=response_time_ms,
                    error=f"HTTP {response.status_code}: {response.text[:100]}",
                )

    except httpx.TimeoutException:
        response_time_ms = (time.time() - start_time) * 1000
        return HealthCheckResult(
            success=False,
            status_code=None,
            response_time_ms=response_time_ms,
            error=f"Request timeout after {timeout}s",
        )

    except httpx.ConnectError as e:
        response_time_ms = (time.time() - start_time) * 1000
        return HealthCheckResult(
            success=False,
            status_code=None,
            response_time_ms=response_time_ms,
            error=f"Connection error: {e}",
        )

    except Exception as e:
        response_time_ms = (time.time() - start_time) * 1000
        return HealthCheckResult(
            success=False,
            status_code=None,
            response_time_ms=response_time_ms,
            error=f"Unexpected error: {e}",
        )


def check_health(
    url: str,
    timeout: float = 5.0,
    auth_token: Optional[str] = None,
) -> HealthCheckResult:
    """
    Perform a synchronous health check against the MCP server.

    Args:
        url: Health check endpoint URL
        timeout: Request timeout in seconds
        auth_token: Optional bearer token for authentication

    Returns:
        HealthCheckResult with success status and metrics
    """
    return asyncio.run(check_health_async(url, timeout, auth_token))


async def continuous_health_check(
    url: str,
    interval: float = 10.0,
    timeout: float = 5.0,
    auth_token: Optional[str] = None,
    max_failures: int = 3,
) -> None:
    """
    Continuously monitor server health with configurable failure threshold.

    Args:
        url: Health check endpoint URL
        interval: Seconds between checks
        timeout: Request timeout in seconds
        auth_token: Optional bearer token for authentication
        max_failures: Maximum consecutive failures before exiting

    Raises:
        RuntimeError: When max consecutive failures is reached
    """
    consecutive_failures = 0
    check_count = 0

    logger.info(f"Starting continuous health monitoring: {url}")
    logger.info(f"Check interval: {interval}s, Timeout: {timeout}s")
    logger.info(f"Max consecutive failures: {max_failures}")

    while True:
        check_count += 1
        logger.info(f"Health check #{check_count}")

        result = await check_health_async(url, timeout, auth_token)

        if result.success:
            logger.info(
                f"✓ Health check passed - Response time: {result.response_time_ms:.2f}ms"
            )
            consecutive_failures = 0
        else:
            consecutive_failures += 1
            logger.error(
                f"✗ Health check failed ({consecutive_failures}/{max_failures}) - "
                f"Error: {result.error}"
            )

            if consecutive_failures >= max_failures:
                error_msg = (
                    f"Health check failed {consecutive_failures} times consecutively. "
                    f"Server appears to be down or unresponsive."
                )
                logger.critical(error_msg)
                raise RuntimeError(error_msg)

        await asyncio.sleep(interval)


def main() -> int:
    """
    Command-line interface for health checking.

    Usage:
        python -m microsoft_mcp.health_check http://localhost:8000/health
        python -m microsoft_mcp.health_check --continuous --interval 10 http://localhost:8000/health
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="MCP Server Health Check Utility",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "url",
        help="Health check endpoint URL (e.g., http://localhost:8000/health)",
    )

    parser.add_argument(
        "--continuous",
        action="store_true",
        help="Run continuous health monitoring",
    )

    parser.add_argument(
        "--interval",
        type=float,
        default=10.0,
        help="Seconds between checks (for continuous mode, default: 10)",
    )

    parser.add_argument(
        "--timeout",
        type=float,
        default=5.0,
        help="Request timeout in seconds (default: 5)",
    )

    parser.add_argument(
        "--auth-token",
        help="Bearer token for authentication",
    )

    parser.add_argument(
        "--max-failures",
        type=int,
        default=3,
        help="Max consecutive failures before exit (for continuous mode, default: 3)",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )

    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    try:
        if args.continuous:
            # Run continuous monitoring
            asyncio.run(
                continuous_health_check(
                    url=args.url,
                    interval=args.interval,
                    timeout=args.timeout,
                    auth_token=args.auth_token,
                    max_failures=args.max_failures,
                )
            )
            return 0
        else:
            # Single health check
            result = check_health(
                url=args.url,
                timeout=args.timeout,
                auth_token=args.auth_token,
            )

            if result.success:
                print("✓ Health check passed")
                print(f"  Status: {result.status_code}")
                print(f"  Response time: {result.response_time_ms:.2f}ms")
                if result.details:
                    print(f"  Details: {result.details}")
                return 0
            else:
                print("✗ Health check failed")
                if result.status_code:
                    print(f"  Status: {result.status_code}")
                print(f"  Response time: {result.response_time_ms:.2f}ms")
                print(f"  Error: {result.error}")
                return 1

    except KeyboardInterrupt:
        print("\nHealth check interrupted by user")
        return 130

    except Exception as e:
        logger.exception("Health check failed with unexpected error")
        print(f"✗ Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
