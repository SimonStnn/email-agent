import json
import logging
import os
import sys
import pathlib as pl
import msal
from typing import NamedTuple, Any

# Note: Environment variables should be loaded by the caller (server.py or authenticate.py)
# before importing this module

# Store token cache in user's home directory for proper permissions and portability
CACHE_FILE = pl.Path.home() / ".m365_mcp_token_cache.json"
METADATA_FILE = pl.Path.home() / ".m365_mcp_account_metadata.json"
SCOPES = [
    "Mail.ReadWrite",
    "Mail.Send",
    "User.Read"
]

logger = logging.getLogger(__name__)


class Account(NamedTuple):
    username: str
    account_id: str
    account_type: str  # "personal", "work_school", or "unknown"


def _select_account(
    accounts: list[dict[str, str]],
    result: dict[str, Any],
    fallback: dict[str, str] | None,
) -> dict[str, str] | None:
    """Select the account that matches the token result, if possible."""
    if fallback:
        return fallback

    preferred_username = None
    id_token_claims = result.get("id_token_claims")
    if isinstance(id_token_claims, dict):
        preferred_username = id_token_claims.get("preferred_username")

    if preferred_username:
        for account in accounts:
            if account.get("username", "").lower() == preferred_username.lower():
                return account

    return accounts[0] if accounts else None

def _read_cache() -> str | None:
    try:
        return CACHE_FILE.read_text()
    except FileNotFoundError:
        return None


def _write_cache(content: str) -> None:
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(content)


def _read_metadata() -> dict[str, dict]:
    """Read account metadata cache containing account types and other metadata.

    Returns:
        Dictionary mapping account_id to metadata dict with 'account_type' field.
    """
    try:
        content = METADATA_FILE.read_text()
        return json.loads(content)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _write_metadata(metadata: dict[str, dict]) -> None:
    """Write account metadata cache.

    Args:
        metadata: Dictionary mapping account_id to metadata dict.
    """
    METADATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    METADATA_FILE.write_text(json.dumps(metadata, indent=2))


def _get_account_type(account_id: str, username: str) -> str:
    """Get or detect account type for an account.

    Args:
        account_id: Account identifier.
        username: User's principal name (email).

    Returns:
        Account type: "personal", "work_school", or "unknown"
    """
    # Check metadata cache first
    metadata = _read_metadata()
    if account_id in metadata and "account_type" in metadata[account_id]:
        return metadata[account_id]["account_type"]

    # Detect account type using domain checking
    # Note: Microsoft Graph API access tokens are opaque and cannot be decoded
    # We rely on username (UPN) domain matching for detection
    try:
        from m365_mcp.account_type import _check_upn_domain

        account_type = _check_upn_domain(username)

        if not account_type:
            logger.warning(
                f"Could not determine account type from username: {username}"
            )
            return "unknown"

        # Store in metadata cache
        if account_id not in metadata:
            metadata[account_id] = {}
        metadata[account_id]["account_type"] = account_type
        _write_metadata(metadata)

        logger.info(
            f"Account type detected and cached for {account_id}: {account_type}"
        )
        return account_type

    except Exception as e:
        logger.warning(f"Failed to detect account type for {account_id}: {e}")
        return "unknown"


def get_app() -> msal.PublicClientApplication:
    client_id = os.getenv("M365_MCP_CLIENT_ID")
    if not client_id:
        raise ValueError("M365_MCP_CLIENT_ID environment variable is required")

    tenant_id = os.getenv("M365_MCP_TENANT_ID", "common")
    authority = f"https://login.microsoftonline.com/{tenant_id}"

    cache = msal.SerializableTokenCache()
    cache_content = _read_cache()
    if cache_content:
        cache.deserialize(cache_content)

    app = msal.PublicClientApplication(
        client_id, authority=authority, token_cache=cache
    )

    return app


def get_token(account_id: str | None = None) -> str:
    app = get_app()

    accounts = app.get_accounts()
    account = None

    if account_id:
        account = next(
            (a for a in accounts if a["home_account_id"] == account_id), None
        )
    elif accounts:
        account = accounts[0]

    result = app.acquire_token_silent(SCOPES, account=account)

    if result and "error" in result:
        logger.warning(
            "Silent token acquisition failed: %s - %s",
            result.get("error"),
            result.get("error_description", "no description"),
        )
        result = None

    if not result:
        flow = app.initiate_device_flow(scopes=SCOPES)
        if "user_code" not in flow:
            raise Exception(
                f"Failed to get device code: {flow.get('error_description', 'Unknown error')}"
            )
        verification_uri = flow.get(
            "verification_uri",
            flow.get("verification_url", "https://microsoft.com/devicelogin"),
        )
        print(
            f"\nTo authenticate:\n1. Visit {verification_uri}\n2. Enter code: {flow['user_code']}",
            file=sys.stderr,
        )
        result = app.acquire_token_by_device_flow(flow)
        accounts = app.get_accounts()
        account = _select_account(accounts, result, account)
    else:
        account = _select_account(accounts, result, account)

    if "error" in result:
        raise Exception(
            f"Auth failed: {result.get('error_description', result['error'])}"
        )

    cache = app.token_cache
    if isinstance(cache, msal.SerializableTokenCache) and cache.has_state_changed:
        _write_cache(cache.serialize())

    # Detect and cache account type for this account
    if account:
        _get_account_type(account["home_account_id"], account["username"])

    return result["access_token"]


def list_accounts() -> list[Account]:
    """List all authenticated Microsoft accounts with their types.

    Returns:
        List of Account objects with username, account_id, and account_type.
        Account type will be "unknown" if not yet detected.
    """
    app = get_app()
    metadata = _read_metadata()

    accounts = []
    for a in app.get_accounts():
        account_id = a["home_account_id"]
        # Get account type from metadata cache, default to "unknown"
        account_type = metadata.get(account_id, {}).get("account_type", "unknown")
        accounts.append(
            Account(
                username=a["username"],
                account_id=account_id,
                account_type=account_type,
            )
        )

    return accounts


def authenticate_new_account() -> Account | None:
    """Authenticate a new account interactively and detect its type.

    Returns:
        Account object with username, account_id, and detected account_type,
        or None if authentication failed.
    """
    app = get_app()

    flow = app.initiate_device_flow(scopes=SCOPES)
    if "user_code" not in flow:
        raise Exception(
            f"Failed to get device code: {flow.get('error_description', 'Unknown error')}"
        )

    print("\nTo authenticate:", file=sys.stderr)
    print(
        f"1. Visit: {flow.get('verification_uri', flow.get('verification_url', 'https://microsoft.com/devicelogin'))}",
        file=sys.stderr,
    )
    print(f"2. Enter code: {flow['user_code']}", file=sys.stderr)
    print("3. Sign in with your Microsoft account", file=sys.stderr)
    print("\nWaiting for authentication...", file=sys.stderr)

    result = app.acquire_token_by_device_flow(flow)

    if "error" in result:
        raise Exception(
            f"Auth failed: {result.get('error_description', result['error'])}"
        )

    cache = app.token_cache
    if isinstance(cache, msal.SerializableTokenCache) and cache.has_state_changed:
        _write_cache(cache.serialize())

    # Get the newly added account
    accounts = app.get_accounts()
    if accounts:
        # Find the account that matches the token we just got
        matched_account = None
        for account in accounts:
            if (
                account.get("username", "").lower()
                == result.get("id_token_claims", {})
                .get("preferred_username", "")
                .lower()
            ):
                matched_account = account
                break

        # If exact match not found, use the last account
        if not matched_account:
            matched_account = accounts[-1]

        # Detect and cache account type
        account_id = matched_account["home_account_id"]
        account_type = _get_account_type(account_id, matched_account["username"])

        return Account(
            username=matched_account["username"],
            account_id=account_id,
            account_type=account_type,
        )

    return None
