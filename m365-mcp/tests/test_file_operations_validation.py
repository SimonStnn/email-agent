"""Unit tests for OneDrive file operations tool validation.

Tests validation, error handling, and API calls for file copy, move, and rename tools.
"""

from typing import Any
from unittest.mock import MagicMock
import pytest
from src.m365_mcp.tools import file as file_tools


@pytest.fixture
def mock_account_id() -> str:
    """Mock account ID for testing"""
    return "test-account-12345"


@pytest.fixture(autouse=True)
def mock_cache_manager(monkeypatch: pytest.MonkeyPatch) -> None:
    """Auto-mock cache manager for all tests."""
    mock_cache = MagicMock()
    monkeypatch.setattr(
        "src.m365_mcp.tools.file.get_cache_manager", lambda: mock_cache
    )


@pytest.fixture(autouse=True)
def mock_validators(monkeypatch: pytest.MonkeyPatch, mock_account_id: str) -> None:
    """Auto-mock validators for all tests."""
    # Mock validate_account_id to return the account ID as-is
    monkeypatch.setattr(
        "src.m365_mcp.tools.file.validate_account_id", lambda x: x
    )
    # Mock validate_microsoft_graph_id to return the ID as-is
    monkeypatch.setattr(
        "src.m365_mcp.tools.file.validate_microsoft_graph_id", lambda x, y: x
    )


# file_copy tests
def test_file_copy_success(
    monkeypatch: pytest.MonkeyPatch,
    mock_account_id: str,
) -> None:
    """Test copying a file successfully."""
    captured: dict[str, Any] = {}

    def fake_request(
        method: str,
        path: str,
        account_id: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        captured["method"] = method
        captured["path"] = path
        captured["json"] = kwargs.get("json", {})
        return {
            "status": "copy initiated",
            "location": "https://api.onedrive.com/monitor/copy-status",
        }

    monkeypatch.setattr(file_tools.graph, "request", fake_request)

    result = file_tools.file_copy.fn(
        file_id="file-123",
        destination_folder_id="dest-folder-456",
        account_id=mock_account_id,
        new_name=None,
    )

    assert "status" in result or "location" in result
    assert captured["method"] == "POST"
    assert captured["path"] == "/me/drive/items/file-123/copy"
    assert captured["json"]["parentReference"]["id"] == "dest-folder-456"
    assert "name" not in captured["json"]


def test_file_copy_with_new_name(
    monkeypatch: pytest.MonkeyPatch,
    mock_account_id: str,
) -> None:
    """Test copying file with new name."""
    captured: dict[str, Any] = {}

    def fake_request(
        method: str,
        path: str,
        account_id: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        captured["json"] = kwargs.get("json", {})
        return {"status": "copy initiated"}

    monkeypatch.setattr(file_tools.graph, "request", fake_request)

    file_tools.file_copy.fn(
        file_id="file-123",
        destination_folder_id="dest-folder-456",
        account_id=mock_account_id,
        new_name="New File Name.txt",
    )

    assert captured["json"]["name"] == "New File Name.txt"


def test_file_copy_empty_new_name(mock_account_id: str) -> None:
    """Test copying file with empty new_name raises ValueError."""
    with pytest.raises(ValueError, match="new_name cannot be empty"):
        file_tools.file_copy.fn(
            file_id="file-123",
            destination_folder_id="dest-folder-456",
            account_id=mock_account_id,
            new_name="",
        )


def test_file_copy_whitespace_new_name(mock_account_id: str) -> None:
    """Test copying file with whitespace-only new_name raises ValueError."""
    with pytest.raises(ValueError, match="new_name cannot be empty"):
        file_tools.file_copy.fn(
            file_id="file-123",
            destination_folder_id="dest-folder-456",
            account_id=mock_account_id,
            new_name="   ",
        )


def test_file_copy_strips_new_name_whitespace(
    monkeypatch: pytest.MonkeyPatch,
    mock_account_id: str,
) -> None:
    """Test that new_name is stripped of leading/trailing whitespace."""
    captured: dict[str, Any] = {}

    def fake_request(
        method: str,
        path: str,
        account_id: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        captured["json"] = kwargs.get("json", {})
        return {"status": "copy initiated"}

    monkeypatch.setattr(file_tools.graph, "request", fake_request)

    file_tools.file_copy.fn(
        file_id="file-123",
        destination_folder_id="dest-folder-456",
        account_id=mock_account_id,
        new_name="  Trimmed Name.txt  ",
    )

    assert captured["json"]["name"] == "Trimmed Name.txt"


# file_move tests
def test_file_move_success(
    monkeypatch: pytest.MonkeyPatch,
    mock_account_id: str,
) -> None:
    """Test moving a file successfully."""
    captured: dict[str, Any] = {}

    def fake_request(
        method: str,
        path: str,
        account_id: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        captured["method"] = method
        captured["path"] = path
        captured["json"] = kwargs.get("json", {})
        return {
            "id": "file-123",
            "name": "document.txt",
            "parentReference": {"id": "new-parent-folder"},
        }

    monkeypatch.setattr(file_tools.graph, "request", fake_request)

    result = file_tools.file_move.fn(
        file_id="file-123",
        destination_folder_id="new-parent-folder",
        account_id=mock_account_id,
    )

    assert result["id"] == "file-123"
    assert result["parentReference"]["id"] == "new-parent-folder"
    assert captured["method"] == "PATCH"
    assert captured["path"] == "/me/drive/items/file-123"
    assert captured["json"]["parentReference"]["id"] == "new-parent-folder"


# file_rename tests
def test_file_rename_success(
    monkeypatch: pytest.MonkeyPatch,
    mock_account_id: str,
) -> None:
    """Test renaming a file successfully."""
    captured: dict[str, Any] = {}

    def fake_request(
        method: str,
        path: str,
        account_id: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        captured["method"] = method
        captured["path"] = path
        captured["json"] = kwargs.get("json", {})
        return {
            "id": "file-123",
            "name": "New File Name.txt",
        }

    monkeypatch.setattr(file_tools.graph, "request", fake_request)

    result = file_tools.file_rename.fn(
        file_id="file-123",
        new_name="New File Name.txt",
        account_id=mock_account_id,
    )

    assert result["name"] == "New File Name.txt"
    assert captured["method"] == "PATCH"
    assert captured["path"] == "/me/drive/items/file-123"
    assert captured["json"]["name"] == "New File Name.txt"


def test_file_rename_empty_name(mock_account_id: str) -> None:
    """Test renaming file with empty name raises ValueError."""
    with pytest.raises(ValueError, match="new_name cannot be empty"):
        file_tools.file_rename.fn(
            file_id="file-123",
            new_name="",
            account_id=mock_account_id,
        )


def test_file_rename_whitespace_name(mock_account_id: str) -> None:
    """Test renaming file with whitespace-only name raises ValueError."""
    with pytest.raises(ValueError, match="new_name cannot be empty"):
        file_tools.file_rename.fn(
            file_id="file-123",
            new_name="   ",
            account_id=mock_account_id,
        )


def test_file_rename_strips_whitespace(
    monkeypatch: pytest.MonkeyPatch,
    mock_account_id: str,
) -> None:
    """Test that new file name is stripped of leading/trailing whitespace."""
    captured: dict[str, Any] = {}

    def fake_request(
        method: str,
        path: str,
        account_id: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        captured["json"] = kwargs.get("json", {})
        return {"id": "file-123", "name": "Renamed.txt"}

    monkeypatch.setattr(file_tools.graph, "request", fake_request)

    file_tools.file_rename.fn(
        file_id="file-123",
        new_name="  Renamed.txt  ",
        account_id=mock_account_id,
    )

    assert captured["json"]["name"] == "Renamed.txt"
