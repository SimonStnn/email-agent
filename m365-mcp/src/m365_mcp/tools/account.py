from ..mcp_instance import mcp
from .. import auth


# account_list
@mcp.tool(
    name="account_list",
    annotations={
        "title": "List Accounts",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
    meta={"category": "account", "safety_level": "safe"},
)
def account_list() -> list[dict[str, str]]:
    """📖 List all signed-in Microsoft accounts (read-only, safe for unsupervised use)

    Returns a list of authenticated Microsoft accounts with their usernames, account IDs,
    and account types (personal or work/school).

    Returns:
        List of account dictionaries with:
        - username: Account email/username
        - account_id: Unique account identifier
        - account_type: "personal", "work_school", or "unknown"

    Example:
        [
            {
                "username": "user@outlook.com",
                "account_id": "abc123...",
                "account_type": "personal"
            },
            {
                "username": "user@contoso.com",
                "account_id": "def456...",
                "account_type": "work_school"
            }
        ]
    """
    return [
        {
            "username": acc.username,
            "account_id": acc.account_id,
            "account_type": acc.account_type,
        }
        for acc in auth.list_accounts()
    ]


# account_authenticate
@mcp.tool(
    name="account_authenticate",
    annotations={
        "title": "Authenticate Account",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
    meta={"category": "account", "safety_level": "moderate"},
)
def account_authenticate() -> dict[str, str]:
    """✏️ Authenticate a new Microsoft account using device flow (requires user confirmation recommended)

    Initiates device flow authentication for adding a new Microsoft account.
    Returns authentication instructions with a device code and verification URL.

    The user must:
    1. Visit the verification URL
    2. Enter the device code
    3. Sign in with their Microsoft account
    4. Use account_complete_auth to finish the process
    """
    app = auth.get_app()
    flow = app.initiate_device_flow(scopes=auth.SCOPES)

    if "user_code" not in flow:
        error_msg = flow.get("error_description", "Unknown error")
        raise Exception(f"Failed to get device code: {error_msg}")

    verification_url = flow.get(
        "verification_uri",
        flow.get("verification_url", "https://microsoft.com/devicelogin"),
    )

    return {
        "status": "authentication_required",
        "instructions": "To authenticate a new Microsoft account:",
        "step1": f"Visit: {verification_url}",
        "step2": f"Enter code: {flow['user_code']}",
        "step3": "Sign in with the Microsoft account you want to add",
        "step4": "After authenticating, use the 'complete_authentication' tool to finish the process",
        "device_code": flow["user_code"],
        "verification_url": verification_url,
        "expires_in": flow.get("expires_in", 900),
        "_flow_cache": str(flow),
    }


# account_complete_auth
@mcp.tool(
    name="account_complete_auth",
    annotations={
        "title": "Complete Authentication",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
    meta={"category": "account", "safety_level": "moderate"},
)
def account_complete_auth(flow_cache: str) -> dict[str, str]:
    """✏️ Complete device flow authentication (requires user confirmation recommended)

    Completes the authentication process after the user has entered the device code
    at the verification URL.

    Args:
        flow_cache: The flow data returned from account_authenticate (the _flow_cache field)

    Returns:
        Account information if authentication was successful, or pending status if
        the user hasn't completed authentication yet.
    """
    import ast

    try:
        flow = ast.literal_eval(flow_cache)
    except (ValueError, SyntaxError):
        raise ValueError("Invalid flow cache data")

    app = auth.get_app()
    result = app.acquire_token_by_device_flow(flow)

    if "error" in result:
        error_msg = result.get("error_description", result["error"])
        if "authorization_pending" in error_msg:
            return {
                "status": "pending",
                "message": "Authentication is still pending. The user needs to complete the authentication process.",
                "instructions": "Please ensure you've visited the URL and entered the code, then try again.",
            }
        raise Exception(f"Authentication failed: {error_msg}")

    # Save the token cache
    cache = app.token_cache
    if isinstance(cache, auth.msal.SerializableTokenCache) and cache.has_state_changed:
        auth._write_cache(cache.serialize())

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
        account_type = auth._get_account_type(account_id, matched_account["username"])

        return {
            "status": "success",
            "username": matched_account["username"],
            "account_id": account_id,
            "account_type": account_type,
            "message": f"Successfully authenticated {matched_account['username']}",
        }

    return {
        "status": "error",
        "message": "Authentication succeeded but no account was found",
    }
