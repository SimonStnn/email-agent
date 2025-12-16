from __future__ import annotations

from collections.abc import Callable

import pytest

from src.m365_mcp.tools.calendar import calendar_delete_event
from src.m365_mcp.tools.contact import contact_delete
from src.m365_mcp.tools.email import email_delete, email_reply, email_send
from src.m365_mcp.tools.email_rules import emailrules_delete
from src.m365_mcp.tools.file import file_delete
from src.m365_mcp.validators import ValidationError


def _record(response: object, calls: list[str]) -> Callable[[], object]:
    """Return a callable that records when Graph is invoked."""

    def _wrapped() -> object:
        calls.append("called")
        return response

    return _wrapped


def test_email_delete_requires_confirmation(
    mock_graph_request,
    mock_account_id: str,
) -> None:
    email_id = "mock-email-id"

    with pytest.raises(ValidationError):
        email_delete.fn(email_id, mock_account_id, confirm=False)

    calls: list[str] = []
    mock_graph_request(
        "DELETE",
        f"/me/messages/{email_id}",
        _record(None, calls),
    )

    result = email_delete.fn(email_id, mock_account_id, confirm=True)
    assert result == {"status": "deleted"}
    assert calls, "Graph request should execute when confirm=True"


def test_file_delete_requires_confirmation(
    mock_graph_request,
    mock_account_id: str,
) -> None:
    file_id = "01ABCDEFZLMNO!123"

    with pytest.raises(ValidationError):
        file_delete.fn(file_id, mock_account_id, confirm=False)

    calls: list[str] = []
    mock_graph_request(
        "DELETE",
        f"/me/drive/items/{file_id}",
        _record(None, calls),
    )

    result = file_delete.fn(file_id, mock_account_id, confirm=True)
    assert result == {"status": "deleted"}
    assert calls, "Graph request should execute when confirm=True"


def test_contact_delete_requires_confirmation(
    mock_graph_request,
    mock_account_id: str,
) -> None:
    contact_id = "contact-123"

    with pytest.raises(ValidationError):
        contact_delete.fn(contact_id, mock_account_id, confirm=False)

    calls: list[str] = []
    mock_graph_request(
        "DELETE",
        f"/me/contacts/{contact_id}",
        _record(None, calls),
    )

    result = contact_delete.fn(contact_id, mock_account_id, confirm=True)
    assert result == {"status": "deleted"}
    assert calls, "Graph request should execute when confirm=True"


def test_calendar_delete_event_requires_confirmation(
    mock_graph_request,
    mock_account_id: str,
) -> None:
    event_id = "event-123"

    with pytest.raises(ValidationError):
        calendar_delete_event.fn(
            mock_account_id,
            event_id,
            send_cancellation=False,
            confirm=False,
        )

    calls: list[str] = []
    mock_graph_request(
        "DELETE",
        f"/me/events/{event_id}",
        _record(None, calls),
    )

    result = calendar_delete_event.fn(
        mock_account_id,
        event_id,
        send_cancellation=False,
        confirm=True,
    )
    assert result == {"status": "deleted"}
    assert calls, "Graph request should execute when confirm=True"


def test_emailrules_delete_requires_confirmation(
    mock_graph_request,
    mock_account_id: str,
) -> None:
    rule_id = "rule-123"

    with pytest.raises(ValidationError):
        emailrules_delete.fn(rule_id, mock_account_id, confirm=False)

    calls: list[str] = []
    mock_graph_request(
        "DELETE",
        f"/me/mailFolders/inbox/messageRules/{rule_id}",
        _record(None, calls),
    )

    result = emailrules_delete.fn(rule_id, mock_account_id, confirm=True)
    assert result == {"status": "deleted", "rule_id": rule_id}
    assert calls, "Graph request should execute when confirm=True"


def test_email_send_requires_confirmation(
    mock_graph_request,
    mock_account_id: str,
) -> None:
    with pytest.raises(ValidationError):
        email_send.fn(
            account_id=mock_account_id,
            to="recipient@example.com",
            subject="Test",
            body="Hello",
            confirm=False,
        )

    calls: list[str] = []
    mock_graph_request(
        "POST",
        "/me/sendMail",
        _record({"status": "sent"}, calls),
    )

    result = email_send.fn(
        account_id=mock_account_id,
        to="recipient@example.com",
        subject="Test",
        body="Hello",
        confirm=True,
    )
    assert result == {"status": "sent"}
    assert calls, "Graph request should execute when confirm=True"


def test_email_reply_requires_confirmation(
    mock_graph_request,
    mock_account_id: str,
) -> None:
    email_id = "mock-email-id"

    with pytest.raises(ValidationError):
        email_reply.fn(
            account_id=mock_account_id,
            email_id=email_id,
            body="Hello",
            confirm=False,
        )

    calls: list[str] = []
    mock_graph_request(
        "POST",
        f"/me/messages/{email_id}/reply",
        _record(None, calls),
    )

    result = email_reply.fn(
        account_id=mock_account_id,
        email_id=email_id,
        body="Hello",
        confirm=True,
    )
    assert result == {"status": "sent"}
    assert calls, "Graph request should execute when confirm=True"
