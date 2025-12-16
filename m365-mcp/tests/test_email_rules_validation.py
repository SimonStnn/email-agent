from __future__ import annotations

from typing import Any

import pytest

from src.m365_mcp.tools import email_rules as email_rules_tools
from src.m365_mcp.validators import ValidationError


def test_emailrules_update_rejects_sequence_below_one(
    mock_account_id: str,
) -> None:
    with pytest.raises(ValidationError):
        email_rules_tools.emailrules_update.fn(
            rule_id="rule-1",
            account_id=mock_account_id,
            sequence=0,
        )


def test_emailrules_update_requires_updates(mock_account_id: str) -> None:
    with pytest.raises(ValidationError):
        email_rules_tools.emailrules_update.fn(
            rule_id="rule-1",
            account_id=mock_account_id,
        )


def test_emailrules_update_normalises_payload(
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
        return {"id": "rule-1"}

    monkeypatch.setattr(email_rules_tools.graph, "request", fake_request)

    result = email_rules_tools.emailrules_update.fn(
        rule_id="rule-1",
        account_id=mock_account_id,
        display_name="  Important Projects ",
        conditions={
            "categories": ["  Projects  "],
            "fromAddresses": ["LEAD@example.com"],
            "hasAttachments": True,
        },
        actions={
            "assignCategories": ["  Projects  "],
            "markAsRead": False,
            "forwardTo": ["manager@example.com"],
        },
    )

    assert result == {"id": "rule-1"}
    payload = captured["json"]
    assert payload["displayName"] == "Important Projects"
    assert payload["conditions"]["categories"] == ["Projects"]
    assert payload["conditions"]["fromAddresses"] == [
        {"emailAddress": {"address": "lead@example.com"}}
    ]
    assert payload["actions"]["assignCategories"] == ["Projects"]
    assert payload["actions"]["forwardTo"] == [
        {"emailAddress": {"address": "manager@example.com"}}
    ]


def test_emailrules_update_rejects_invalid_actions(mock_account_id: str) -> None:
    with pytest.raises(ValidationError):
        email_rules_tools.emailrules_update.fn(
            rule_id="rule-1",
            account_id=mock_account_id,
            actions={"assignCategories": "not-a-list"},
        )
