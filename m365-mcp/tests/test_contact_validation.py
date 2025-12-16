from __future__ import annotations

from typing import Any

import pytest

from src.m365_mcp.tools import contact as contact_tools
from src.m365_mcp.validators import ValidationError


def test_contact_list_rejects_invalid_limit(mock_account_id: str) -> None:
    with pytest.raises(ValidationError):
        contact_tools.contact_list.fn(account_id=mock_account_id, limit=0)


def test_contact_update_normalises_payload(
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

    monkeypatch.setattr(contact_tools.graph, "request", fake_request)

    result = contact_tools.contact_update.fn(
        contact_id="contact-1",
        updates={
            "givenName": "  Jane ",
            "emailAddresses": [
                {"address": "USER@example.com", "name": " User "},
                "other@example.com",
            ],
            "businessPhones": [" 123-555-0100 "],
            "mobilePhone": " 555-0000 ",
        },
        account_id=mock_account_id,
    )

    assert result == {"status": "updated"}
    payload = captured["json"]
    assert payload["givenName"] == "Jane"
    email_addresses = payload["emailAddresses"]
    assert email_addresses[0] == {"address": "user@example.com", "name": "User"}
    assert email_addresses[1] == {"address": "other@example.com"}
    assert payload["businessPhones"] == ["123-555-0100"]
    assert payload["mobilePhone"] == "555-0000"


def test_contact_update_rejects_invalid_email(mock_account_id: str) -> None:
    with pytest.raises(ValidationError):
        contact_tools.contact_update.fn(
            contact_id="contact-1",
            updates={"emailAddresses": [{"address": "not-an-email"}]},
            account_id=mock_account_id,
        )


def test_contact_update_rejects_invalid_phone(mock_account_id: str) -> None:
    with pytest.raises(ValidationError):
        contact_tools.contact_update.fn(
            contact_id="contact-1",
            updates={"businessPhones": [""]},
            account_id=mock_account_id,
        )


def test_contact_update_rejects_empty_mobile_phone(mock_account_id: str) -> None:
    with pytest.raises(ValidationError):
        contact_tools.contact_update.fn(
            contact_id="contact-1",
            updates={"mobilePhone": "   "},
            account_id=mock_account_id,
        )
