"""Unit tests for email forward tool validation.

Tests validation, error handling, and API calls for email_forward.
"""

from typing import Any
from unittest.mock import MagicMock
import pytest
from src.m365_mcp.tools import email as email_tools


@pytest.fixture
def mock_account_id() -> str:
    """Mock account ID for testing"""
    return "test-account-12345"


@pytest.fixture(autouse=True)
def mock_validators(monkeypatch: pytest.MonkeyPatch) -> None:
    """Auto-mock normalize_recipients for all tests."""
    # Mock normalize_recipients to return emails as-is (in a list)
    def fake_normalize(recipients: str | list[str] | None, param_name: str) -> list[str]:
        if recipients is None:
            return []
        if isinstance(recipients, str):
            return [recipients]
        return list(recipients)

    monkeypatch.setattr(
        "src.m365_mcp.tools.email.normalize_recipients", fake_normalize
    )


# email_forward tests
def test_email_forward_success(
    monkeypatch: pytest.MonkeyPatch,
    mock_account_id: str,
) -> None:
    """Test forwarding an email successfully."""
    captured: dict[str, Any] = {}

    def fake_request(
        method: str,
        path: str,
        account_id: str | None = None,
        **kwargs: Any,
    ) -> None:
        captured["method"] = method
        captured["path"] = path
        captured["json"] = kwargs.get("json", {})

    monkeypatch.setattr(email_tools.graph, "request", fake_request)

    result = email_tools.email_forward.fn(
        account_id=mock_account_id,
        email_id="email-123",
        to="recipient@example.com",
        cc=None,
        body=None,
        confirm=True,
    )

    assert result["status"] == "sent"
    assert captured["method"] == "POST"
    assert captured["path"] == "/me/messages/email-123/forward"
    assert len(captured["json"]["toRecipients"]) == 1
    assert captured["json"]["toRecipients"][0]["emailAddress"]["address"] == "recipient@example.com"
    assert "ccRecipients" not in captured["json"]
    assert "comment" not in captured["json"]


def test_email_forward_with_cc(
    monkeypatch: pytest.MonkeyPatch,
    mock_account_id: str,
) -> None:
    """Test forwarding email with CC recipients."""
    captured: dict[str, Any] = {}

    def fake_request(
        method: str,
        path: str,
        account_id: str | None = None,
        **kwargs: Any,
    ) -> None:
        captured["json"] = kwargs.get("json", {})

    monkeypatch.setattr(email_tools.graph, "request", fake_request)

    email_tools.email_forward.fn(
        account_id=mock_account_id,
        email_id="email-123",
        to="recipient@example.com",
        cc="cc@example.com",
        body=None,
        confirm=True,
    )

    assert len(captured["json"]["ccRecipients"]) == 1
    assert captured["json"]["ccRecipients"][0]["emailAddress"]["address"] == "cc@example.com"


def test_email_forward_with_body(
    monkeypatch: pytest.MonkeyPatch,
    mock_account_id: str,
) -> None:
    """Test forwarding email with comment body."""
    captured: dict[str, Any] = {}

    def fake_request(
        method: str,
        path: str,
        account_id: str | None = None,
        **kwargs: Any,
    ) -> None:
        captured["json"] = kwargs.get("json", {})

    monkeypatch.setattr(email_tools.graph, "request", fake_request)

    email_tools.email_forward.fn(
        account_id=mock_account_id,
        email_id="email-123",
        to="recipient@example.com",
        cc=None,
        body="FYI - please review",
        confirm=True,
    )

    assert captured["json"]["comment"] == "FYI - please review"


def test_email_forward_strips_body_whitespace(
    monkeypatch: pytest.MonkeyPatch,
    mock_account_id: str,
) -> None:
    """Test that forward body comment is stripped of whitespace."""
    captured: dict[str, Any] = {}

    def fake_request(
        method: str,
        path: str,
        account_id: str | None = None,
        **kwargs: Any,
    ) -> None:
        captured["json"] = kwargs.get("json", {})

    monkeypatch.setattr(email_tools.graph, "request", fake_request)

    email_tools.email_forward.fn(
        account_id=mock_account_id,
        email_id="email-123",
        to="recipient@example.com",
        cc=None,
        body="  Trimmed comment  ",
        confirm=True,
    )

    assert captured["json"]["comment"] == "Trimmed comment"


def test_email_forward_empty_body_not_included(
    monkeypatch: pytest.MonkeyPatch,
    mock_account_id: str,
) -> None:
    """Test that empty body comment is not included in payload."""
    captured: dict[str, Any] = {}

    def fake_request(
        method: str,
        path: str,
        account_id: str | None = None,
        **kwargs: Any,
    ) -> None:
        captured["json"] = kwargs.get("json", {})

    monkeypatch.setattr(email_tools.graph, "request", fake_request)

    email_tools.email_forward.fn(
        account_id=mock_account_id,
        email_id="email-123",
        to="recipient@example.com",
        cc=None,
        body="   ",  # Whitespace-only
        confirm=True,
    )

    assert "comment" not in captured["json"]


def test_email_forward_without_confirm(mock_account_id: str) -> None:
    """Test forwarding email without confirmation raises error."""
    with pytest.raises(Exception, match="forward email on resource requires confirm=True"):
        email_tools.email_forward.fn(
            account_id=mock_account_id,
            email_id="email-123",
            to="recipient@example.com",
            cc=None,
            body=None,
            confirm=False,
        )


def test_email_forward_multiple_recipients(
    monkeypatch: pytest.MonkeyPatch,
    mock_account_id: str,
) -> None:
    """Test forwarding email to multiple recipients."""
    captured: dict[str, Any] = {}

    def fake_request(
        method: str,
        path: str,
        account_id: str | None = None,
        **kwargs: Any,
    ) -> None:
        captured["json"] = kwargs.get("json", {})

    monkeypatch.setattr(email_tools.graph, "request", fake_request)

    email_tools.email_forward.fn(
        account_id=mock_account_id,
        email_id="email-123",
        to=["user1@example.com", "user2@example.com"],
        cc=["cc1@example.com", "cc2@example.com"],
        body="Please review",
        confirm=True,
    )

    assert len(captured["json"]["toRecipients"]) == 2
    assert len(captured["json"]["ccRecipients"]) == 2
    assert captured["json"]["comment"] == "Please review"
