"""Account type detection for Microsoft 365 accounts.

This module provides functionality to detect whether a Microsoft account is
a personal account (outlook.com, hotmail.com, live.com) or a work/school
account (organizational/tenant-based).

Account type detection is used to route API requests to the appropriate
Microsoft Graph API endpoints, as personal accounts have different API
capabilities and limitations compared to work/school accounts.
"""

import logging
from typing import Any

import jwt

logger = logging.getLogger(__name__)

# Personal Microsoft account domains
PERSONAL_DOMAINS = {
    "outlook.com",
    "hotmail.com",
    "live.com",
    "msn.com",
}


def detect_account_type(access_token: str, user_info: dict[str, Any]) -> str:
    """Detect whether a Microsoft account is personal or work/school.

    This function uses a two-tier detection strategy:
    1. Primary: Decode the JWT access token and check the issuer (iss) claim
    2. Fallback: Check the userPrincipalName domain against known personal
       account domains

    Args:
        access_token: The Microsoft Graph API access token (JWT format).
        user_info: User information dictionary containing at minimum
            userPrincipalName field.

    Returns:
        Account type string: "personal" or "work_school"

    Raises:
        ValueError: If account type cannot be determined from either token
            or user info.

    Example:
        >>> user_info = {"userPrincipalName": "user@outlook.com"}
        >>> account_type = detect_account_type(token, user_info)
        >>> print(account_type)
        "personal"
    """
    # Try JWT token decoding first (most reliable method)
    try:
        account_type = _decode_token_unverified(access_token)
        if account_type:
            logger.info(f"Account type detected via JWT: {account_type}")
            return account_type
    except Exception as e:
        logger.warning(f"JWT token decoding failed, falling back to domain check: {e}")

    # Fallback to domain pattern matching
    upn = user_info.get("userPrincipalName")
    if upn:
        account_type = _check_upn_domain(upn)
        if account_type:
            logger.info(f"Account type detected via domain: {account_type}")
            return account_type

    # Detection failed
    logger.error("Failed to detect account type from both token and user info")
    raise ValueError(
        "Unable to determine account type. Token decoding and domain "
        "matching both failed. Please ensure the account is properly "
        "authenticated."
    )


def _decode_token_unverified(token: str) -> str | None:
    """Decode JWT token without verification to extract issuer claim.

    SECURITY NOTE: Decoding without signature verification is safe in this
    context because:
    1. The token has already been validated by MSAL during authentication
    2. We only use the token for read-only account type detection
    3. The token is never passed to external APIs
    4. We're only extracting metadata (issuer), not trusting any permissions

    Args:
        token: JWT access token string.

    Returns:
        Account type ("personal" or "work_school") if detected, None if
        detection failed.

    Raises:
        Exception: If JWT decoding fails due to malformed token.
    """
    try:
        # Decode without verification (see security note above)
        payload = jwt.decode(
            token,
            options={
                "verify_signature": False,
                "verify_aud": False,
                "verify_exp": False,
            },
        )

        # Check issuer claim
        issuer = payload.get("iss", "")

        # Personal accounts use consumers tenant
        # Example: https://login.microsoftonline.com/9188040d-6c67-4c5b-b112-36a304b66dad/v2.0
        if "9188040d-6c67-4c5b-b112-36a304b66dad" in issuer:
            return "personal"

        # Work/school accounts use tenant-specific issuer
        # Example: https://login.microsoftonline.com/{tenant-id}/v2.0
        if "login.microsoftonline.com" in issuer:
            return "work_school"

        logger.debug(f"Unknown issuer format: {issuer}")
        return None

    except jwt.DecodeError as e:
        logger.debug(f"JWT decode error: {e}")
        raise


def _check_upn_domain(upn: str | None) -> str | None:
    """Check userPrincipalName domain to detect personal accounts.

    Args:
        upn: User Principal Name (email-like identifier), or None.

    Returns:
        "personal" if UPN matches personal account domain, "work_school"
        for other domains, or None if domain cannot be extracted or upn is None.

    Example:
        >>> _check_upn_domain("user@outlook.com")
        "personal"
        >>> _check_upn_domain("user@contoso.com")
        "work_school"
    """
    if not upn or "@" not in upn:
        return None

    # Extract domain (handle case-insensitivity)
    domain = upn.split("@")[-1].lower()

    # Remove any subdomains (e.g., user@mail.outlook.com -> outlook.com)
    domain_parts = domain.split(".")
    if len(domain_parts) >= 2:
        # Get the last two parts (e.g., outlook.com)
        domain = ".".join(domain_parts[-2:])

    # Check against known personal account domains
    if domain in PERSONAL_DOMAINS:
        return "personal"

    # All other domains are assumed to be work/school
    return "work_school"
