"""Unit tests for OneDrive folder management tool validation.

Tests validation, error handling, and API calls for folder management tools.
"""

from typing import Any
import pytest
from src.m365_mcp.tools import folder as folder_tools


@pytest.fixture
def mock_account_id() -> str:
    """Mock account ID for testing"""
    return "test-account-12345"


# folder_create tests
def test_folder_create_success_root_level(
    monkeypatch: pytest.MonkeyPatch,
    mock_account_id: str,
) -> None:
    """Test creating a folder at root level."""
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
            "id": "folder-123",
            "name": "Test Folder",
            "folder": {"childCount": 0},
        }

    monkeypatch.setattr(folder_tools.graph, "request", fake_request)

    result = folder_tools.folder_create.fn(
        name="Test Folder",
        account_id=mock_account_id,
        parent_folder_id=None,
    )

    assert result["id"] == "folder-123"
    assert captured["method"] == "POST"
    assert captured["path"] == "/me/drive/root/children"
    assert captured["json"]["name"] == "Test Folder"
    assert "folder" in captured["json"]


def test_folder_create_success_with_parent(
    monkeypatch: pytest.MonkeyPatch,
    mock_account_id: str,
) -> None:
    """Test creating a folder under a parent folder."""
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
            "id": "folder-456",
            "name": "Child Folder",
            "folder": {"childCount": 0},
        }

    monkeypatch.setattr(folder_tools.graph, "request", fake_request)

    result = folder_tools.folder_create.fn(
        name="Child Folder",
        account_id=mock_account_id,
        parent_folder_id="parent-folder-id",
    )

    assert result["id"] == "folder-456"
    assert captured["method"] == "POST"
    assert captured["path"] == "/me/drive/items/parent-folder-id/children"
    assert captured["json"]["name"] == "Child Folder"


def test_folder_create_empty_name(mock_account_id: str) -> None:
    """Test creating a folder with empty name raises ValueError."""
    with pytest.raises(ValueError, match="name cannot be empty"):
        folder_tools.folder_create.fn(
            name="",
            account_id=mock_account_id,
            parent_folder_id=None,
        )


def test_folder_create_whitespace_name(mock_account_id: str) -> None:
    """Test creating a folder with whitespace-only name raises ValueError."""
    with pytest.raises(ValueError, match="name cannot be empty"):
        folder_tools.folder_create.fn(
            name="   ",
            account_id=mock_account_id,
            parent_folder_id=None,
        )


def test_folder_create_strips_whitespace(
    monkeypatch: pytest.MonkeyPatch,
    mock_account_id: str,
) -> None:
    """Test that folder name is stripped of leading/trailing whitespace."""
    captured: dict[str, Any] = {}

    def fake_request(
        method: str,
        path: str,
        account_id: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        captured["json"] = kwargs.get("json", {})
        return {"id": "folder-123", "name": "Test Folder"}

    monkeypatch.setattr(folder_tools.graph, "request", fake_request)

    folder_tools.folder_create.fn(
        name="  Test Folder  ",
        account_id=mock_account_id,
        parent_folder_id=None,
    )

    assert captured["json"]["name"] == "Test Folder"


# folder_delete tests
def test_folder_delete_success(
    monkeypatch: pytest.MonkeyPatch,
    mock_account_id: str,
) -> None:
    """Test deleting a folder successfully."""
    captured: dict[str, Any] = {}

    def fake_request(
        method: str,
        path: str,
        account_id: str | None = None,
        **kwargs: Any,
    ) -> None:
        captured["method"] = method
        captured["path"] = path

    monkeypatch.setattr(folder_tools.graph, "request", fake_request)

    result = folder_tools.folder_delete.fn(
        folder_id="folder-to-delete",
        account_id=mock_account_id,
        confirm=True,
    )

    assert result["status"] == "deleted"
    assert result["folder_id"] == "folder-to-delete"
    assert captured["method"] == "DELETE"
    assert captured["path"] == "/me/drive/items/folder-to-delete"


def test_folder_delete_without_confirm(mock_account_id: str) -> None:
    """Test deleting folder without confirmation raises error."""
    with pytest.raises(Exception, match="delete OneDrive folder on resource requires confirm=True"):
        folder_tools.folder_delete.fn(
            folder_id="folder-id",
            account_id=mock_account_id,
            confirm=False,
        )


def test_folder_delete_confirm_default_false(mock_account_id: str) -> None:
    """Test that confirm defaults to False."""
    with pytest.raises(Exception, match="delete OneDrive folder on resource requires confirm=True"):
        folder_tools.folder_delete.fn(
            folder_id="folder-id",
            account_id=mock_account_id,
        )


# folder_rename tests
def test_folder_rename_success(
    monkeypatch: pytest.MonkeyPatch,
    mock_account_id: str,
) -> None:
    """Test renaming a folder successfully."""
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
            "id": "folder-123",
            "name": "New Folder Name",
        }

    monkeypatch.setattr(folder_tools.graph, "request", fake_request)

    result = folder_tools.folder_rename.fn(
        folder_id="folder-123",
        new_name="New Folder Name",
        account_id=mock_account_id,
    )

    assert result["name"] == "New Folder Name"
    assert captured["method"] == "PATCH"
    assert captured["path"] == "/me/drive/items/folder-123"
    assert captured["json"]["name"] == "New Folder Name"


def test_folder_rename_empty_name(mock_account_id: str) -> None:
    """Test renaming folder with empty name raises ValueError."""
    with pytest.raises(ValueError, match="new_name cannot be empty"):
        folder_tools.folder_rename.fn(
            folder_id="folder-123",
            new_name="",
            account_id=mock_account_id,
        )


def test_folder_rename_whitespace_name(mock_account_id: str) -> None:
    """Test renaming folder with whitespace-only name raises ValueError."""
    with pytest.raises(ValueError, match="new_name cannot be empty"):
        folder_tools.folder_rename.fn(
            folder_id="folder-123",
            new_name="   ",
            account_id=mock_account_id,
        )


def test_folder_rename_strips_whitespace(
    monkeypatch: pytest.MonkeyPatch,
    mock_account_id: str,
) -> None:
    """Test that new folder name is stripped of leading/trailing whitespace."""
    captured: dict[str, Any] = {}

    def fake_request(
        method: str,
        path: str,
        account_id: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        captured["json"] = kwargs.get("json", {})
        return {"id": "folder-123", "name": "Renamed"}

    monkeypatch.setattr(folder_tools.graph, "request", fake_request)

    folder_tools.folder_rename.fn(
        folder_id="folder-123",
        new_name="  Renamed  ",
        account_id=mock_account_id,
    )

    assert captured["json"]["name"] == "Renamed"


# folder_move tests
def test_folder_move_success(
    monkeypatch: pytest.MonkeyPatch,
    mock_account_id: str,
) -> None:
    """Test moving a folder successfully."""
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
            "id": "folder-123",
            "name": "Moved Folder",
            "parentReference": {"id": "new-parent-id"},
        }

    monkeypatch.setattr(folder_tools.graph, "request", fake_request)

    result = folder_tools.folder_move.fn(
        folder_id="folder-123",
        destination_folder_id="new-parent-id",
        account_id=mock_account_id,
    )

    assert result["id"] == "folder-123"
    assert result["parentReference"]["id"] == "new-parent-id"
    assert captured["method"] == "PATCH"
    assert captured["path"] == "/me/drive/items/folder-123"
    assert captured["json"]["parentReference"]["id"] == "new-parent-id"
