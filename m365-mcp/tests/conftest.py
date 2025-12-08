from __future__ import annotations

import os
import subprocess
import time
from collections import deque
from pathlib import Path
from typing import Any, Callable

import pytest
from dotenv import load_dotenv

from src.m365_mcp import graph

# Load environment variables from .env file for all tests
test_env_file = os.getenv("TEST_ENV_FILE", ".env")
if Path(test_env_file).exists():
    load_dotenv(dotenv_path=test_env_file)
else:
    load_dotenv()


@pytest.fixture
def mock_graph_request(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[str, str, Any], None]:
    """Patch graph.request and allow registering responses."""

    responses: dict[tuple[str, str], Any] = {}

    def register(method: str, path: str, response: Any) -> None:
        responses[(method, path)] = response

    def fake_request(
        method: str,
        path: str,
        account_id: str | None = None,
        **kwargs: Any,
    ) -> Any:
        key = (method, path)
        if key not in responses:
            raise AssertionError(f"Unexpected Graph request: {method} {path}")
        value = responses[key]
        return value() if callable(value) else value

    monkeypatch.setattr(graph, "request", fake_request)
    return register


@pytest.fixture
def mock_graph_paginated(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[str, list[dict[str, Any]]], None]:
    """Patch graph.request_paginated with configurable payloads."""

    payloads: dict[str, deque[list[dict[str, Any]]]] = {}

    def register(path: str, pages: list[dict[str, Any]]) -> None:
        payloads.setdefault(path, deque()).append(pages)

    def fake_paginated(
        path: str,
        account_id: str | None = None,
        params: dict[str, Any] | None = None,
        limit: int | None = None,
    ):
        queue = payloads.get(path)
        if not queue:
            return iter(())
        page = queue.popleft()
        return iter(page)

    monkeypatch.setattr(graph, "request_paginated", fake_paginated)
    return register


@pytest.fixture
def mock_account_id() -> str:
    """Provide a reusable fake account identifier."""

    return "test-account"


@pytest.fixture
def mock_email_data() -> Callable[..., dict[str, Any]]:
    """Factory for building fake email payloads."""

    def _builder(**overrides: Any) -> dict[str, Any]:
        payload = {
            "id": "mock-email-id",
            "subject": "Test Subject",
            "body": {"contentType": "Text", "content": "Hello"},
            "hasAttachments": False,
        }
        payload.update(overrides)
        return payload

    return _builder


@pytest.fixture
def mock_file_metadata() -> Callable[..., dict[str, Any]]:
    """Factory for building fake OneDrive file metadata payloads."""

    def _builder(**overrides: Any) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": "01ABCDEFZLMNO!123",
            "name": "example.txt",
            "size": 2048,
            "file": {"mimeType": "text/plain"},
            "@microsoft.graph.downloadUrl": (
                "https://graph.microsoft.com/v1.0/me/drive/items/01ABCDEFZLMNO!123/content"
            ),
        }
        payload.update(overrides)
        return payload

    return _builder


@pytest.fixture
def mock_calendar_event() -> Callable[..., dict[str, Any]]:
    """Factory for creating calendar event payloads."""

    def _builder(**overrides: Any) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": "event-123",
            "subject": "Team Sync",
            "start": {"dateTime": "2024-05-01T10:00:00+00:00", "timeZone": "UTC"},
            "end": {"dateTime": "2024-05-01T11:00:00+00:00", "timeZone": "UTC"},
            "attendees": [
                {
                    "emailAddress": {"address": "owner@example.com", "name": "Owner"},
                    "type": "required",
                }
            ],
        }
        payload.update(overrides)
        return payload

    return _builder


@pytest.fixture
def mock_contact_data() -> Callable[..., dict[str, Any]]:
    """Factory for creating contact payloads."""

    def _builder(**overrides: Any) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": "contact-123",
            "displayName": "Ada Lovelace",
            "givenName": "Ada",
            "surname": "Lovelace",
            "emailAddresses": [
                {"address": "ada.lovelace@example.com", "name": "Ada Lovelace"}
            ],
        }
        payload.update(overrides)
        return payload

    return _builder


@pytest.fixture
def temp_safe_dir(tmp_path: Path) -> Path:
    """Provide an isolated directory for filesystem interactions."""

    target = tmp_path / "safe"
    target.mkdir()
    return target


@pytest.fixture(autouse=True, scope="session")
def ensure_port_8000_free():
    """Kill any process on port 8000 before and after test session.

    This prevents orphaned HTTP server processes from blocking the port
    and causing test failures. Runs automatically for every test session.
    """

    def cleanup():
        """Find and kill all processes using port 8000 using netstat approach."""
        try:
            # Use the proven netstat approach to kill processes on port 8000
            # Loop while port 8000 is in use (max 3 iterations to avoid infinite loop)
            max_attempts = 3
            attempt = 0

            while attempt < max_attempts:
                # Check if port 8000 is in use
                check_result = subprocess.run(
                    ["sudo", "netstat", "-tunlp"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                )

                if "8000" not in check_result.stdout:
                    # Port is free
                    break

                # Extract PID and kill it
                # Parse: "tcp 0 0 :::8000 :::* LISTEN 12345/python"
                # Extract: "12345/python" then remove last 8 chars to get PID
                for line in check_result.stdout.split("\n"):
                    if "8000" in line:
                        # Use awk to get column 7, sed to remove last 8 chars
                        pid_result = subprocess.run(
                            [
                                "bash",
                                "-c",
                                f"echo '{line}' | awk '{{print $7}}' | sed 's/.{{8}}$//'",
                            ],
                            capture_output=True,
                            text=True,
                            timeout=2,
                            check=False,
                        )
                        pid = pid_result.stdout.strip()

                        if pid:
                            # Kill the process
                            subprocess.run(
                                ["sudo", "kill", "-9", pid],
                                stderr=subprocess.DEVNULL,
                                timeout=2,
                                check=False,
                            )

                # Wait before next iteration
                time.sleep(1)
                attempt += 1

        except subprocess.TimeoutExpired:
            print("Warning: Port 8000 cleanup timed out")
        except Exception as e:
            # Don't fail tests if cleanup fails, just warn
            print(f"Warning: Port 8000 cleanup encountered error: {e}")

    # Clean before test session starts
    cleanup()

    yield

    # Clean after test session ends
    cleanup()
