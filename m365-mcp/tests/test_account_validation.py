from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

import pytest

from src.m365_mcp.tools import account as account_tools


def test_account_list_serialises_namedtuple(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure account_list exposes username/account_id/account_type triples."""

    accounts = [
        account_tools.auth.Account(
            username="ada@example.com", account_id="acc-1", account_type="work_school"
        ),
        account_tools.auth.Account(
            username="grace@example.com", account_id="acc-2", account_type="personal"
        ),
    ]
    monkeypatch.setattr(account_tools.auth, "list_accounts", lambda: accounts)

    result = account_tools.account_list.fn()

    assert result == [
        {
            "username": "ada@example.com",
            "account_id": "acc-1",
            "account_type": "work_school",
        },
        {
            "username": "grace@example.com",
            "account_id": "acc-2",
            "account_type": "personal",
        },
    ]


def test_account_authenticate_returns_flow_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify device flow details are surfaced when authentication begins."""

    flow: dict[str, Any] = {
        "user_code": "ABCD-1234",
        "verification_uri": "https://microsoft.com/devicelogin",
        "expires_in": 900,
    }

    class FakeApp:
        def initiate_device_flow(self, scopes: Iterable[str]) -> dict[str, Any]:
            self.scopes = list(scopes)  # type: ignore[attr-defined]
            return flow

    fake_app = FakeApp()
    monkeypatch.setattr(account_tools.auth, "get_app", lambda: fake_app)

    result = account_tools.account_authenticate.fn()

    assert result["status"] == "authentication_required"
    assert result["device_code"] == flow["user_code"]
    assert result["verification_url"] == flow["verification_uri"]
    assert result["_flow_cache"] == str(flow)


def test_account_authenticate_raises_when_flow_missing_user_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Guard against malformed device flow payloads."""

    class FakeApp:
        def initiate_device_flow(self, scopes: Iterable[str]) -> dict[str, Any]:
            return {"error_description": "User code unavailable"}

    monkeypatch.setattr(account_tools.auth, "get_app", lambda: FakeApp())

    with pytest.raises(Exception, match="Failed to get device code"):
        account_tools.account_authenticate.fn()


def test_account_complete_auth_rejects_invalid_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ensure flow cache must be a literal mapping."""

    monkeypatch.setattr(account_tools.auth, "get_app", lambda: None)

    with pytest.raises(ValueError, match="Invalid flow cache"):
        account_tools.account_complete_auth.fn("not-a-dict")


def test_account_complete_auth_returns_pending_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Map authorization_pending responses to a pending status."""

    flow_cache = {"device_code": "ABCD"}

    class FakeApp:
        token_cache = object()

        def acquire_token_by_device_flow(self, flow: dict[str, Any]) -> dict[str, str]:
            self.flow = flow  # type: ignore[attr-defined]
            return {
                "error": "authorization_pending",
                "error_description": "authorization_pending",
            }

        def get_accounts(self) -> list[dict[str, str]]:
            return []

    monkeypatch.setattr(account_tools.auth, "get_app", lambda: FakeApp())

    result = account_tools.account_complete_auth.fn(str(flow_cache))

    assert result["status"] == "pending"
    assert "Authentication is still pending" in result["message"]


def test_account_complete_auth_returns_success_and_writes_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Successful completion returns matched account details including account type."""

    flow_cache = {"device_code": "EFGH"}

    class FakeCacheBase:
        has_state_changed: bool = True

        def serialize(self) -> str:
            return "base-cache"

    monkeypatch.setattr(
        account_tools.auth.msal,
        "SerializableTokenCache",
        FakeCacheBase,
    )

    @dataclass
    class FakeCache(FakeCacheBase):
        def serialize(self) -> str:
            return "cache"

    class FakeApp:
        def __init__(self) -> None:
            self.token_cache = FakeCache()

        def acquire_token_by_device_flow(self, flow: dict[str, Any]) -> dict[str, Any]:
            return {
                "id_token_claims": {"preferred_username": "ada@example.com"},
                "access_token": "fake-access-token",
            }

        def get_accounts(self) -> list[dict[str, str]]:
            return [
                {"username": "ada@example.com", "home_account_id": "acc-1"},
                {"username": "grace@example.com", "home_account_id": "acc-2"},
            ]

    writes: list[str] = []

    def fake_write_cache(content: str) -> None:
        writes.append(content)

    def fake_get_account_type(account_id: str, username: str) -> str:
        return "work_school"

    monkeypatch.setattr(account_tools.auth, "get_app", lambda: FakeApp())
    monkeypatch.setattr(account_tools.auth, "_write_cache", fake_write_cache)
    monkeypatch.setattr(account_tools.auth, "_get_account_type", fake_get_account_type)

    result = account_tools.account_complete_auth.fn(str(flow_cache))

    assert result == {
        "status": "success",
        "username": "ada@example.com",
        "account_id": "acc-1",
        "account_type": "work_school",
        "message": "Successfully authenticated ada@example.com",
    }
    assert writes == ["cache"]
