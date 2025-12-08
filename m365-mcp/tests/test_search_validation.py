from __future__ import annotations

import datetime as dt
from typing import Any, Callable, Dict

import pytest

from src.m365_mcp.tools import search as search_tools
from src.m365_mcp.validators import ValidationError


@pytest.mark.parametrize(
    ("callable_fn", "kwargs"),
    [
        (
            search_tools.search_files.fn,
            {"query": "report", "account_id": "acc", "limit": 0},
        ),
        (
            search_tools.search_emails.fn,
            {"query": "report", "account_id": "acc", "limit": 0},
        ),
        (
            search_tools.search_contacts.fn,
            {"query": "user", "account_id": "acc", "limit": 0},
        ),
        (
            search_tools.search_unified.fn,
            {"query": "report", "account_id": "acc", "limit": 0},
        ),
    ],
)
def test_search_limits_reject_invalid_input(
    callable_fn: Callable[..., Any],
    kwargs: Dict[str, Any],
) -> None:
    with pytest.raises(ValidationError):
        callable_fn(**kwargs)


@pytest.mark.parametrize(
    ("callable_fn", "kwargs"),
    [
        (search_tools.search_files.fn, {"account_id": "acc"}),
        (search_tools.search_emails.fn, {"account_id": "acc"}),
        (search_tools.search_events.fn, {"account_id": "acc"}),
        (search_tools.search_contacts.fn, {"account_id": "acc"}),
        (search_tools.search_unified.fn, {"account_id": "acc"}),
    ],
)
@pytest.mark.parametrize("bad_query", ["", "   "])
def test_search_query_rejects_empty(
    callable_fn: Callable[..., Any],
    kwargs: Dict[str, Any],
    bad_query: str,
) -> None:
    with pytest.raises(ValidationError):
        callable_fn(query=bad_query, **kwargs)


@pytest.mark.parametrize(
    "callable_fn",
    [
        search_tools.search_files.fn,
        search_tools.search_emails.fn,
        search_tools.search_events.fn,
        search_tools.search_contacts.fn,
        search_tools.search_unified.fn,
    ],
)
def test_search_query_rejects_excess_length(callable_fn: Callable[..., Any]) -> None:
    overlong_query = "x" * 600
    with pytest.raises(ValidationError):
        callable_fn(query=overlong_query, account_id="acc")


def test_search_events_rejects_invalid_days(mock_account_id: str) -> None:
    with pytest.raises(ValidationError):
        search_tools.search_events.fn(
            query="meeting",
            account_id=mock_account_id,
            days_back=-1,
        )


def test_search_events_filters_by_range(
    monkeypatch: pytest.MonkeyPatch,
    mock_account_id: str,
) -> None:
    now = dt.datetime.now(dt.timezone.utc)
    inside_start = (now - dt.timedelta(hours=1)).isoformat()
    inside_end = (now + dt.timedelta(hours=1)).isoformat()
    outside_start = (now - dt.timedelta(days=10)).isoformat()
    outside_end = (now - dt.timedelta(days=9, hours=20)).isoformat()

    def fake_search_events(
        account_id: str,
        account_type: str,
        query: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        assert limit == 50
        return [
            {"start": {"dateTime": inside_start}, "end": {"dateTime": inside_end}},
            {"start": {"dateTime": outside_start}, "end": {"dateTime": outside_end}},
            {"start": {}, "end": {}},
        ]

    # Import search_router to mock it
    from src.m365_mcp import search_router

    monkeypatch.setattr(search_router, "search_events", fake_search_events)

    results = search_tools.search_events.fn(
        query="meeting",
        account_id=mock_account_id,
        days_back=1,
        days_ahead=1,
        limit=50,
        use_cache=False,  # Disable caching for test
    )

    assert len(results) == 1
    assert results[0]["start"]["dateTime"] == inside_start


def test_search_emails_rejects_invalid_folder(mock_account_id: str) -> None:
    with pytest.raises(ValidationError):
        search_tools.search_emails.fn(
            query="reports",
            account_id=mock_account_id,
            folder="spam",
        )


def test_search_unified_rejects_invalid_entity_type() -> None:
    with pytest.raises(ValidationError):
        search_tools.search_unified.fn(
            query="report",
            account_id="acc",
            entity_types=["message", "calendar"],
        )


def test_search_files_trims_query(
    monkeypatch: pytest.MonkeyPatch,
    mock_account_id: str,
) -> None:
    captured: dict[str, Any] = {}

    def fake_search_files(
        account_id: str,
        account_type: str,
        query: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        captured["query"] = query
        captured["account_id"] = account_id
        captured["account_type"] = account_type
        captured["limit"] = limit
        return []

    # Import search_router to mock it
    from src.m365_mcp import search_router

    monkeypatch.setattr(search_router, "search_files", fake_search_files)

    search_tools.search_files.fn(
        query="  quarterly report ",
        account_id=mock_account_id,
        limit=25,
        use_cache=False,  # Disable caching for test
    )

    assert captured["query"] == "quarterly report"
    assert captured["account_id"] == mock_account_id
    assert captured["limit"] == 25
