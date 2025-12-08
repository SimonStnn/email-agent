"""Unit tests for email folder management tools."""

from __future__ import annotations

from typing import Any

import pytest

from src.m365_mcp.tools import email_folders as folder_tools
from src.m365_mcp.validators import ValidationError


# Test emailfolders_create


def test_emailfolders_create_success_root_level(
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
            "displayName": "Test Folder",
            "childFolderCount": 0,
        }

    monkeypatch.setattr(folder_tools.graph, "request", fake_request)

    result = folder_tools.emailfolders_create.fn(
        display_name="Test Folder",
        account_id=mock_account_id,
        parent_folder_id=None,
    )

    assert result["id"] == "folder-123"
    assert result["displayName"] == "Test Folder"
    assert captured["method"] == "POST"
    assert captured["path"] == "/me/mailFolders"
    assert captured["json"]["displayName"] == "Test Folder"


def test_emailfolders_create_success_with_parent(
    monkeypatch: pytest.MonkeyPatch,
    mock_account_id: str,
) -> None:
    """Test creating a child folder."""
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
            "displayName": "Child Folder",
            "parentFolderId": "parent-123",
        }

    monkeypatch.setattr(folder_tools.graph, "request", fake_request)

    result = folder_tools.emailfolders_create.fn(
        display_name="Child Folder",
        account_id=mock_account_id,
        parent_folder_id="parent-123",
    )

    assert result["id"] == "folder-456"
    assert captured["path"] == "/me/mailFolders/parent-123/childFolders"


def test_emailfolders_create_strips_whitespace(
    monkeypatch: pytest.MonkeyPatch,
    mock_account_id: str,
) -> None:
    """Test that display name is stripped of whitespace."""
    captured: dict[str, Any] = {}

    def fake_request(
        method: str,
        path: str,
        account_id: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        captured["json"] = kwargs.get("json", {})
        return {"id": "folder-123", "displayName": "Trimmed"}

    monkeypatch.setattr(folder_tools.graph, "request", fake_request)

    folder_tools.emailfolders_create.fn(
        display_name="  Trimmed  ",
        account_id=mock_account_id,
    )

    assert captured["json"]["displayName"] == "Trimmed"


def test_emailfolders_create_rejects_empty_name(mock_account_id: str) -> None:
    """Test that empty display name is rejected."""
    with pytest.raises(ValueError, match="cannot be empty"):
        folder_tools.emailfolders_create.fn(
            display_name="",
            account_id=mock_account_id,
        )


def test_emailfolders_create_rejects_whitespace_only_name(
    mock_account_id: str,
) -> None:
    """Test that whitespace-only display name is rejected."""
    with pytest.raises(ValueError, match="cannot be empty"):
        folder_tools.emailfolders_create.fn(
            display_name="   ",
            account_id=mock_account_id,
        )


# Test emailfolders_rename


def test_emailfolders_rename_success(
    monkeypatch: pytest.MonkeyPatch,
    mock_account_id: str,
) -> None:
    """Test renaming a folder."""
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
            "displayName": "New Name",
        }

    monkeypatch.setattr(folder_tools.graph, "request", fake_request)

    result = folder_tools.emailfolders_rename.fn(
        folder_id="folder-123",
        new_display_name="New Name",
        account_id=mock_account_id,
    )

    assert result["displayName"] == "New Name"
    assert captured["method"] == "PATCH"
    assert captured["path"] == "/me/mailFolders/folder-123"
    assert captured["json"]["displayName"] == "New Name"


def test_emailfolders_rename_strips_whitespace(
    monkeypatch: pytest.MonkeyPatch,
    mock_account_id: str,
) -> None:
    """Test that new display name is stripped."""
    captured: dict[str, Any] = {}

    def fake_request(
        method: str,
        path: str,
        account_id: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        captured["json"] = kwargs.get("json", {})
        return {"id": "folder-123", "displayName": "Trimmed"}

    monkeypatch.setattr(folder_tools.graph, "request", fake_request)

    folder_tools.emailfolders_rename.fn(
        folder_id="folder-123",
        new_display_name="  Trimmed  ",
        account_id=mock_account_id,
    )

    assert captured["json"]["displayName"] == "Trimmed"


def test_emailfolders_rename_rejects_empty_name(mock_account_id: str) -> None:
    """Test that empty new display name is rejected."""
    with pytest.raises(ValueError, match="cannot be empty"):
        folder_tools.emailfolders_rename.fn(
            folder_id="folder-123",
            new_display_name="",
            account_id=mock_account_id,
        )


def test_emailfolders_rename_rejects_whitespace_only_name(
    mock_account_id: str,
) -> None:
    """Test that whitespace-only new display name is rejected."""
    with pytest.raises(ValueError, match="cannot be empty"):
        folder_tools.emailfolders_rename.fn(
            folder_id="folder-123",
            new_display_name="   ",
            account_id=mock_account_id,
        )


# Test emailfolders_move


def test_emailfolders_move_success(
    monkeypatch: pytest.MonkeyPatch,
    mock_account_id: str,
) -> None:
    """Test moving a folder to a different parent."""
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
            "parentFolderId": "parent-456",
        }

    monkeypatch.setattr(folder_tools.graph, "request", fake_request)

    result = folder_tools.emailfolders_move.fn(
        folder_id="folder-123",
        destination_folder_id="parent-456",
        account_id=mock_account_id,
    )

    assert result["parentFolderId"] == "parent-456"
    assert captured["method"] == "PATCH"
    assert captured["path"] == "/me/mailFolders/folder-123"
    assert captured["json"]["parentFolderId"] == "parent-456"


# Test emailfolders_delete


def test_emailfolders_delete_success(
    monkeypatch: pytest.MonkeyPatch,
    mock_account_id: str,
) -> None:
    """Test deleting a folder."""
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

    result = folder_tools.emailfolders_delete.fn(
        folder_id="folder-123",
        account_id=mock_account_id,
        confirm=True,
    )

    assert result["status"] == "deleted"
    assert result["folder_id"] == "folder-123"
    assert captured["method"] == "DELETE"
    assert captured["path"] == "/me/mailFolders/folder-123"


def test_emailfolders_delete_requires_confirmation(mock_account_id: str) -> None:
    """Test that deletion requires explicit confirmation."""
    with pytest.raises(ValidationError, match="confirm=True"):
        folder_tools.emailfolders_delete.fn(
            folder_id="folder-123",
            account_id=mock_account_id,
            confirm=False,
        )


# Test emailfolders_mark_all_as_read


def test_emailfolders_mark_all_as_read_success(
    monkeypatch: pytest.MonkeyPatch,
    mock_account_id: str,
) -> None:
    """Test marking all messages in folder as read."""
    captured_requests: list[dict[str, Any]] = []

    def fake_paginated(
        path: str,
        account_id: str | None = None,
        params: dict[str, Any] | None = None,
        limit: int | None = None,
    ):
        # Return 2 unread messages
        return iter(
            [
                {"id": "msg-1", "isRead": False},
                {"id": "msg-2", "isRead": False},
            ]
        )

    def fake_request(
        method: str,
        path: str,
        account_id: str | None = None,
        **kwargs: Any,
    ) -> None:
        captured_requests.append(
            {
                "method": method,
                "path": path,
                "json": kwargs.get("json", {}),
            }
        )

    monkeypatch.setattr(folder_tools.graph, "request_paginated", fake_paginated)
    monkeypatch.setattr(folder_tools.graph, "request", fake_request)

    result = folder_tools.emailfolders_mark_all_as_read.fn(
        folder_id="folder-123",
        account_id=mock_account_id,
    )

    assert result["status"] == "completed"
    assert result["folder_id"] == "folder-123"
    assert result["messages_marked_read"] == 2
    assert len(captured_requests) == 2
    assert all(req["method"] == "PATCH" for req in captured_requests)
    assert all(req["json"]["isRead"] is True for req in captured_requests)


def test_emailfolders_mark_all_as_read_empty_folder(
    monkeypatch: pytest.MonkeyPatch,
    mock_account_id: str,
) -> None:
    """Test marking all as read in empty folder."""

    def fake_paginated(
        path: str,
        account_id: str | None = None,
        params: dict[str, Any] | None = None,
        limit: int | None = None,
    ):
        return iter([])

    monkeypatch.setattr(folder_tools.graph, "request_paginated", fake_paginated)

    result = folder_tools.emailfolders_mark_all_as_read.fn(
        folder_id="folder-123",
        account_id=mock_account_id,
    )

    assert result["messages_marked_read"] == 0


# Test emailfolders_empty


def test_emailfolders_empty_success(
    monkeypatch: pytest.MonkeyPatch,
    mock_account_id: str,
) -> None:
    """Test emptying a folder (deleting all messages)."""
    captured_deletes: list[str] = []

    def fake_paginated(
        path: str,
        account_id: str | None = None,
        params: dict[str, Any] | None = None,
        limit: int | None = None,
    ):
        # Return 3 messages
        return iter(
            [
                {"id": "msg-1"},
                {"id": "msg-2"},
                {"id": "msg-3"},
            ]
        )

    def fake_request(
        method: str,
        path: str,
        account_id: str | None = None,
        **kwargs: Any,
    ) -> None:
        if method == "DELETE":
            captured_deletes.append(path)

    monkeypatch.setattr(folder_tools.graph, "request_paginated", fake_paginated)
    monkeypatch.setattr(folder_tools.graph, "request", fake_request)

    result = folder_tools.emailfolders_empty.fn(
        folder_id="folder-123",
        account_id=mock_account_id,
        confirm=True,
    )

    assert result["status"] == "completed"
    assert result["folder_id"] == "folder-123"
    assert result["messages_deleted"] == 3
    assert len(captured_deletes) == 3
    assert "/me/messages/msg-1" in captured_deletes
    assert "/me/messages/msg-2" in captured_deletes
    assert "/me/messages/msg-3" in captured_deletes


def test_emailfolders_empty_requires_confirmation(mock_account_id: str) -> None:
    """Test that emptying folder requires explicit confirmation."""
    with pytest.raises(ValidationError, match="confirm=True"):
        folder_tools.emailfolders_empty.fn(
            folder_id="folder-123",
            account_id=mock_account_id,
            confirm=False,
        )


def test_emailfolders_empty_handles_empty_folder(
    monkeypatch: pytest.MonkeyPatch,
    mock_account_id: str,
) -> None:
    """Test emptying an already empty folder."""

    def fake_paginated(
        path: str,
        account_id: str | None = None,
        params: dict[str, Any] | None = None,
        limit: int | None = None,
    ):
        return iter([])

    monkeypatch.setattr(folder_tools.graph, "request_paginated", fake_paginated)

    result = folder_tools.emailfolders_empty.fn(
        folder_id="folder-123",
        account_id=mock_account_id,
        confirm=True,
    )

    assert result["messages_deleted"] == 0
