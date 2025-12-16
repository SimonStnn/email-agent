from __future__ import annotations

from typing import Any

import pytest

from src.m365_mcp.tools import calendar as calendar_tools
from src.m365_mcp.validators import ValidationError


def test_calendar_respond_event_rejects_invalid_response(
    mock_account_id: str,
) -> None:
    with pytest.raises(ValidationError) as exc:
        calendar_tools.calendar_respond_event.fn(
            account_id=mock_account_id,
            event_id="event-123",
            response="maybe",
        )

    assert "Invalid response" in str(exc.value)


def test_calendar_respond_event_accepts_alias_and_trims_message(
    monkeypatch: pytest.MonkeyPatch,
    mock_account_id: str,
) -> None:
    captured: dict[str, Any] = {}

    def fake_request(
        method: str,
        path: str,
        account_id: str | None = None,
        **kwargs: Any,
    ) -> dict[str, str]:
        captured["method"] = method
        captured["path"] = path
        captured["account_id"] = account_id
        captured["json"] = kwargs.get("json")
        return {"status": "sent"}

    monkeypatch.setattr(calendar_tools.graph, "request", fake_request)

    result = calendar_tools.calendar_respond_event.fn(
        account_id=mock_account_id,
        event_id="event-123",
        response="Tentative",
        message="  Looking forward  ",
    )

    assert result == {"status": "tentativelyAccept"}
    assert captured["path"].endswith("/tentativelyAccept")
    assert captured["json"]["comment"] == "Looking forward"


def test_calendar_create_event_rejects_invalid_attendees(
    mock_account_id: str,
) -> None:
    with pytest.raises(ValidationError) as exc:
        calendar_tools.calendar_create_event.fn(
            account_id=mock_account_id,
            subject="Team Sync",
            start="2024-05-01T10:00:00+00:00",
            end="2024-05-01T11:00:00+00:00",
            attendees="not-an-email",
        )

    assert "Invalid attendees" in str(exc.value)


def test_calendar_create_event_enforces_attendee_limit(
    mock_account_id: str,
) -> None:
    attendees = [
        f"user{i}@example.com" for i in range(calendar_tools.MAX_CALENDAR_ATTENDEES + 1)
    ]

    with pytest.raises(ValidationError) as exc:
        calendar_tools.calendar_create_event.fn(
            account_id=mock_account_id,
            subject="Large Meeting",
            start="2024-05-01T10:00:00+00:00",
            end="2024-05-01T11:00:00+00:00",
            attendees=attendees,
        )

    assert "Invalid attendees" in str(exc.value)


def test_calendar_create_event_validates_timezone(
    mock_account_id: str,
) -> None:
    with pytest.raises(ValidationError) as exc:
        calendar_tools.calendar_create_event.fn(
            account_id=mock_account_id,
            subject="Team Sync",
            start="2024-05-01T10:00:00+00:00",
            end="2024-05-01T11:00:00+00:00",
            timezone="Invalid/Zone",
        )

    assert "Invalid timezone" in str(exc.value)


def test_calendar_create_event_deduplicates_attendees(
    monkeypatch: pytest.MonkeyPatch,
    mock_account_id: str,
) -> None:
    captured: dict[str, Any] = {}

    def fake_request(
        method: str,
        path: str,
        account_id: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        captured["method"] = method
        captured["path"] = path
        captured["account_id"] = account_id
        captured["json"] = kwargs.get("json")
        return {"id": "event-123"}

    monkeypatch.setattr(calendar_tools.graph, "request", fake_request)

    result = calendar_tools.calendar_create_event.fn(
        account_id=mock_account_id,
        subject="Team Sync",
        start="2024-05-01T10:00:00+00:00",
        end="2024-05-01T11:00:00+00:00",
        attendees=[
            "owner@example.com",
            "OWNER@example.com",
            "guest@example.com",
        ],
        timezone="UTC",
    )

    assert result == {"id": "event-123"}
    attendee_payload = captured["json"]["attendees"]
    addresses = [entry["emailAddress"]["address"] for entry in attendee_payload]
    assert addresses == ["owner@example.com", "guest@example.com"]


def test_calendar_check_availability_validates_attendees(
    mock_account_id: str,
) -> None:
    with pytest.raises(ValidationError) as exc:
        calendar_tools.calendar_check_availability.fn(
            account_id=mock_account_id,
            start="2024-05-01T10:00:00+00:00",
            end="2024-05-01T11:00:00+00:00",
            attendees="bad-email",
        )

    assert "Invalid attendees" in str(exc.value)


def test_calendar_check_availability_rejects_invalid_datetime_window(
    mock_account_id: str,
) -> None:
    with pytest.raises(ValidationError):
        calendar_tools.calendar_check_availability.fn(
            account_id=mock_account_id,
            start="2024-05-01T11:00:00+00:00",
            end="2024-05-01T10:00:00+00:00",
        )


def test_calendar_check_availability_deduplicates_schedules(
    monkeypatch: pytest.MonkeyPatch,
    mock_account_id: str,
) -> None:
    captured: dict[str, Any] = {}

    def fake_request(
        method: str,
        path: str,
        account_id: str | None = None,
        **kwargs: Any,
    ) -> Any:
        if method == "GET" and path.startswith("/me"):
            return {"mail": "primary@example.com"}
        captured["method"] = method
        captured["path"] = path
        captured["account_id"] = account_id
        captured["json"] = kwargs.get("json")
        return {"value": []}

    monkeypatch.setattr(calendar_tools.graph, "request", fake_request)

    result = calendar_tools.calendar_check_availability.fn(
        account_id=mock_account_id,
        start="2024-05-01T10:00:00+00:00",
        end="2024-05-01T11:00:00+00:00",
        attendees=["PRIMARY@example.com", "guest@example.com"],
    )

    assert result == {"value": []}
    schedules = captured["json"]["schedules"]
    assert schedules == ["primary@example.com", "guest@example.com"]
    start_time = captured["json"]["startTime"]["dateTime"]
    end_time = captured["json"]["endTime"]["dateTime"]
    assert start_time.endswith("+00:00")
    assert end_time.endswith("+00:00")


def test_calendar_update_event_rejects_timezone_without_dates(
    mock_account_id: str,
) -> None:
    with pytest.raises(ValidationError):
        calendar_tools.calendar_update_event.fn(
            event_id="event-1",
            updates={"timezone": "UTC"},
            account_id=mock_account_id,
        )


def test_calendar_update_event_normalises_attendees(
    monkeypatch: pytest.MonkeyPatch,
    mock_account_id: str,
) -> None:
    captured: dict[str, Any] = {}

    def fake_request(
        method: str,
        path: str,
        account_id: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        captured["json"] = kwargs.get("json") or {}
        return {"status": "updated"}

    monkeypatch.setattr(calendar_tools.graph, "request", fake_request)

    result = calendar_tools.calendar_update_event.fn(
        event_id="event-1",
        updates={
            "start": "2024-06-01T10:00:00+00:00",
            "end": "2024-06-01T11:00:00+00:00",
            "timezone": "UTC",
            "attendees": ["One@example.com", "one@example.com", "two@example.com"],
        },
        account_id=mock_account_id,
    )

    assert result == {"status": "updated"}
    attendees = captured["json"]["attendees"]
    addresses = [entry["emailAddress"]["address"] for entry in attendees]
    assert addresses == ["one@example.com", "two@example.com"]


def test_calendar_update_event_rejects_invalid_start(
    mock_account_id: str,
) -> None:
    with pytest.raises(ValidationError):
        calendar_tools.calendar_update_event.fn(
            event_id="event-1",
            updates={
                "start": "2024-06-01T10:00:00",
                "end": "2024-06-01T11:00:00+00:00",
                "timezone": "UTC",
            },
            account_id=mock_account_id,
        )
