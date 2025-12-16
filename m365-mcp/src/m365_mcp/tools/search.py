import datetime as dt
from datetime import datetime, timezone
from typing import Any, Sequence
from ..mcp_instance import mcp
from .. import graph, auth, search_router
from .cache_tools import get_cache_manager
from ..validators import (
    ValidationError,
    format_validation_error,
    validate_choices,
    validate_folder_choice,
    validate_limit,
)

# Common constants (using from email.py as they are consistent across files)
from .email import EMAIL_FOLDER_NAMES, FOLDERS

MAX_SEARCH_QUERY_LENGTH = 512
ALLOWED_SEARCH_ENTITY_TYPES: Sequence[str] = ("message", "event", "driveItem")


def _get_account_type(account_id: str) -> str:
    """Get account type for the given account_id.

    If account type is "unknown", triggers detection by getting a fresh token.

    Args:
        account_id: Microsoft account identifier.

    Returns:
        Account type: "personal", "work_school", or "unknown"
    """
    accounts = auth.list_accounts()
    for account in accounts:
        if account.account_id == account_id:
            account_type = account.account_type
            # If unknown, trigger detection by getting token
            if account_type == "unknown":
                try:
                    # Getting token triggers account type detection
                    auth.get_token(account_id)
                    # Re-fetch accounts to get updated type
                    accounts = auth.list_accounts()
                    for account in accounts:
                        if account.account_id == account_id:
                            return account.account_type
                except Exception:
                    # If detection fails, return unknown
                    pass
            return account_type
    return "unknown"


def _validate_search_query(query: str, param_name: str = "query") -> str:
    """Ensure search queries are non-empty and within length bounds."""
    if not isinstance(query, str):
        reason = "must be a string"
        raise ValidationError(
            format_validation_error(
                param_name,
                query,
                reason,
                f"1-{MAX_SEARCH_QUERY_LENGTH} characters",
            )
        )
    trimmed = query.strip()
    if not trimmed:
        reason = "cannot be empty"
        raise ValidationError(
            format_validation_error(
                param_name,
                query,
                reason,
                f"1-{MAX_SEARCH_QUERY_LENGTH} characters",
            )
        )
    if len(trimmed) > MAX_SEARCH_QUERY_LENGTH:
        reason = f"must be <= {MAX_SEARCH_QUERY_LENGTH} characters"
        raise ValidationError(
            format_validation_error(
                param_name,
                trimmed,
                reason,
                f"1-{MAX_SEARCH_QUERY_LENGTH} characters",
            )
        )
    return trimmed


def _validate_entity_types(
    entity_types: list[str] | tuple[str, ...] | str | None,
) -> list[str]:
    """Validate unified search entity type selections."""
    if entity_types is None:
        return list(ALLOWED_SEARCH_ENTITY_TYPES)
    if isinstance(entity_types, str):
        candidate_iterable: Sequence[str] = [entity_types]
    else:
        candidate_iterable = entity_types
        if not isinstance(candidate_iterable, (list, tuple)):
            raise ValidationError(
                format_validation_error(
                    "entity_types",
                    entity_types,
                    "must be a list of entity types",
                    f"Subset of {sorted(ALLOWED_SEARCH_ENTITY_TYPES)}",
                )
            )
    validated: list[str] = []
    for index, value in enumerate(candidate_iterable):
        validated.append(
            validate_choices(
                value,
                ALLOWED_SEARCH_ENTITY_TYPES,
                f"entity_types[{index}]",
            )
        )
    return validated


# search_files
@mcp.tool(
    name="search_files",
    annotations={
        "title": "Search Files",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
    meta={"category": "search", "safety_level": "safe"},
)
def search_files(
    query: str,
    account_id: str,
    limit: int = 50,
    use_cache: bool = True,
    force_refresh: bool = False,
) -> list[dict[str, Any]]:
    """📖 Search for files in OneDrive (read-only, safe for unsupervised use)

    Searches file names and content across all accessible OneDrive folders.
    Automatically routes to the appropriate API based on account type:
    - Personal accounts: Uses OneDrive-specific search
    - Work/school accounts: Uses unified search API

    Args:
        query: Search query string (1-512 characters)
        account_id: Microsoft account ID
        limit: Maximum results to return (1-500, default: 50)
        use_cache: Whether to use cache (default: True)
        force_refresh: Bypass cache and fetch fresh data (default: False)

    Returns:
        List of matching files with metadata
    """
    limit = validate_limit(limit, 1, 500, "limit")
    search_query = _validate_search_query(query)

    # Build cache parameters
    cache_params = {
        "query": search_query,
        "limit": limit,
    }

    # Check cache if enabled
    if use_cache and not force_refresh:
        try:
            cache_manager = get_cache_manager()
            cached_result = cache_manager.get_cached(
                account_id, "search_files", cache_params
            )
            if cached_result:
                data, state = cached_result
                # Add cache status to each file
                for file in data:
                    file["_cache_status"] = state.value
                return data
        except Exception:
            # If cache fails, continue to API call
            pass

    # Get account type and route to appropriate search API
    account_type = _get_account_type(account_id)
    items = search_router.search_files(account_id, account_type, search_query, limit)

    results = [
        {
            "id": item["id"],
            "name": item["name"],
            "type": "folder" if "folder" in item else "file",
            "size": item.get("size", 0),
            "modified": item.get("lastModifiedDateTime"),
            "download_url": item.get("@microsoft.graph.downloadUrl"),
        }
        for item in items
    ]

    # Add cache metadata to each file
    cached_at = datetime.now(timezone.utc).isoformat()
    for file in results:
        file["_cache_status"] = "fresh"
        file["_cached_at"] = cached_at

    # Store in cache
    if use_cache:
        try:
            cache_manager = get_cache_manager()
            cache_manager.set_cached(account_id, "search_files", cache_params, results)
        except Exception:
            # If cache storage fails, still return the result
            pass

    return results


# search_emails
@mcp.tool(
    name="search_emails",
    annotations={
        "title": "Search Emails",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
    meta={"category": "search", "safety_level": "safe"},
)
def search_emails(
    query: str,
    account_id: str,
    limit: int = 50,
    folder: str | None = None,
    use_cache: bool = True,
    force_refresh: bool = False,
) -> list[dict[str, Any]]:
    """📖 Search emails across mailbox (read-only, safe for unsupervised use)

    Searches email subject, body, and sender across all or specific folders.
    Automatically routes to the appropriate API based on account type:
    - Personal accounts: Uses OData $search parameter
    - Work/school accounts: Uses unified search API

    Args:
        query: Search query string (1-512 characters)
        account_id: Microsoft account ID
        limit: Maximum results to return (1-500, default: 50)
        folder: Optional folder to search within (e.g., "inbox", "sent")
        use_cache: Whether to use cache (default: True)
        force_refresh: Bypass cache and fetch fresh data (default: False)

    Returns:
        List of matching emails with metadata
    """
    limit = validate_limit(limit, 1, 500, "limit")
    search_query = _validate_search_query(query)

    # Build cache parameters
    cache_params = {
        "query": search_query,
        "limit": limit,
        "folder": folder,
    }

    # Check cache if enabled
    if use_cache and not force_refresh:
        try:
            cache_manager = get_cache_manager()
            cached_result = cache_manager.get_cached(
                account_id, "search_emails", cache_params
            )
            if cached_result:
                data, state = cached_result
                # Add cache status to each email
                for email in data:
                    email["_cache_status"] = state.value
                return data
        except Exception:
            # If cache fails, continue to API call
            pass

    # Fetch from API
    if folder:
        # For folder-specific search, use the traditional endpoint
        folder_key = validate_folder_choice(folder, EMAIL_FOLDER_NAMES, "folder")
        folder_path = FOLDERS[folder_key.casefold()]
        endpoint = f"/me/mailFolders/{folder_path}/messages"

        params = {
            "$search": f'"{search_query}"',
            "$top": limit,
            "$select": "id,subject,from,toRecipients,receivedDateTime,hasAttachments,body,conversationId,isRead",
        }

        results = list(
            graph.request_paginated(endpoint, account_id, params=params, limit=limit)
        )
    else:
        # Get account type and route to appropriate search API
        account_type = _get_account_type(account_id)
        results = search_router.search_emails(
            account_id, account_type, search_query, limit
        )

    # Add cache metadata to each email
    cached_at = datetime.now(timezone.utc).isoformat()
    for email in results:
        email["_cache_status"] = "fresh"
        email["_cached_at"] = cached_at

    # Store in cache
    if use_cache:
        try:
            cache_manager = get_cache_manager()
            cache_manager.set_cached(account_id, "search_emails", cache_params, results)
        except Exception:
            # If cache storage fails, still return the result
            pass

    return results


# search_events
@mcp.tool(
    name="search_events",
    annotations={
        "title": "Search Events",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
    meta={"category": "search", "safety_level": "safe"},
)
def search_events(
    query: str,
    account_id: str,
    days_ahead: int = 365,
    days_back: int = 365,
    limit: int = 50,
    use_cache: bool = True,
    force_refresh: bool = False,
) -> list[dict[str, Any]]:
    """📖 Search calendar events (read-only, safe for unsupervised use)

    Searches event titles, locations, and descriptions within date range.
    Automatically routes to the appropriate API based on account type:
    - Personal accounts: Uses OData $search parameter
    - Work/school accounts: Uses unified search API

    Args:
        query: Search query string (1-512 characters)
        account_id: Microsoft account ID
        days_ahead: Days to look forward (0-730, default: 365)
        days_back: Days to look back (0-730, default: 365)
        limit: Maximum results to return (1-500, default: 50)
        use_cache: Whether to use cache (default: True)
        force_refresh: Bypass cache and fetch fresh data (default: False)

    Returns:
        List of matching events
    """
    days_ahead = validate_limit(days_ahead, 0, 730, "days_ahead")
    days_back = validate_limit(days_back, 0, 730, "days_back")
    limit = validate_limit(limit, 1, 500, "limit")
    search_query = _validate_search_query(query)

    # Build cache parameters
    cache_params = {
        "query": search_query,
        "days_ahead": days_ahead,
        "days_back": days_back,
        "limit": limit,
    }

    # Check cache if enabled
    if use_cache and not force_refresh:
        try:
            cache_manager = get_cache_manager()
            cached_result = cache_manager.get_cached(
                account_id, "search_events", cache_params
            )
            if cached_result:
                data, state = cached_result
                # Add cache status to each event
                for event in data:
                    event["_cache_status"] = state.value
                return data
        except Exception:
            # If cache fails, continue to API call
            pass

    # Get account type and route to appropriate search API
    account_type = _get_account_type(account_id)
    events = search_router.search_events(account_id, account_type, search_query, limit)

    # Filter by date range if needed
    if days_ahead != 365 or days_back != 365:
        now = dt.datetime.now(dt.timezone.utc)
        start = now - dt.timedelta(days=days_back)
        end = now + dt.timedelta(days=days_ahead)

        filtered_events = []
        for event in events:
            start_info = event.get("start", {})
            end_info = event.get("end", {})
            if not isinstance(start_info, dict) or not isinstance(end_info, dict):
                continue
            start_raw = start_info.get("dateTime")
            end_raw = end_info.get("dateTime")
            if not isinstance(start_raw, str) or not isinstance(end_raw, str):
                continue
            try:
                event_start = dt.datetime.fromisoformat(
                    start_raw.replace("Z", "+00:00")
                )
                event_end = dt.datetime.fromisoformat(end_raw.replace("Z", "+00:00"))
            except ValueError:
                continue

            if event_start <= end and event_end >= start:
                filtered_events.append(event)

        events = filtered_events

    # Add cache metadata to each event
    cached_at = datetime.now(timezone.utc).isoformat()
    for event in events:
        event["_cache_status"] = "fresh"
        event["_cached_at"] = cached_at

    # Store in cache
    if use_cache:
        try:
            cache_manager = get_cache_manager()
            cache_manager.set_cached(account_id, "search_events", cache_params, events)
        except Exception:
            # If cache storage fails, still return the result
            pass

    return events


# search_contacts
@mcp.tool(
    name="search_contacts",
    annotations={
        "title": "Search Contacts",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
    meta={"category": "search", "safety_level": "safe"},
)
def search_contacts(
    query: str,
    account_id: str,
    limit: int = 50,
    use_cache: bool = True,
    force_refresh: bool = False,
) -> list[dict[str, Any]]:
    """📖 Search contacts (read-only, safe for unsupervised use)

    Searches contact names, email addresses, and phone numbers.
    Uses $filter with prefix matching (startswith) for all account types
    due to Graph API limitations.

    Note: Contact search is limited to prefix matching and may not find
    matches in the middle of names.

    Args:
        query: Search query string (1-512 characters, used as prefix)
        account_id: Microsoft account ID
        limit: Maximum results to return (1-500, default: 50)
        use_cache: Whether to use cache (default: True)
        force_refresh: Bypass cache and fetch fresh data (default: False)

    Returns:
        List of matching contacts
    """
    limit = validate_limit(limit, 1, 500, "limit")
    search_query = _validate_search_query(query)

    # Build cache parameters
    cache_params = {
        "query": search_query,
        "limit": limit,
    }

    # Check cache if enabled
    if use_cache and not force_refresh:
        try:
            cache_manager = get_cache_manager()
            cached_result = cache_manager.get_cached(
                account_id, "search_contacts", cache_params
            )
            if cached_result:
                data, state = cached_result
                # Add cache status to each contact
                for contact in data:
                    contact["_cache_status"] = state.value
                return data
        except Exception:
            # If cache fails, continue to API call
            pass

    # Get account type and route to appropriate search API
    account_type = _get_account_type(account_id)
    contacts = search_router.search_contacts(
        account_id, account_type, search_query, limit
    )

    # Add cache metadata to each contact
    cached_at = datetime.now(timezone.utc).isoformat()
    for contact in contacts:
        contact["_cache_status"] = "fresh"
        contact["_cached_at"] = cached_at

    # Store in cache
    if use_cache:
        try:
            cache_manager = get_cache_manager()
            cache_manager.set_cached(
                account_id, "search_contacts", cache_params, contacts
            )
        except Exception:
            # If cache storage fails, still return the result
            pass

    return contacts


# search_unified
@mcp.tool(
    name="search_unified",
    annotations={
        "title": "Unified Search",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
    meta={"category": "search", "safety_level": "safe"},
)
def search_unified(
    query: str,
    account_id: str,
    entity_types: list[str] | None = None,
    limit: int = 50,
    use_cache: bool = True,
    force_refresh: bool = False,
) -> dict[str, list[dict[str, Any]]]:
    """📖 Search across multiple Microsoft 365 resources (read-only, safe for unsupervised use)

    Searches emails, events, and files simultaneously.
    Automatically routes to the appropriate API based on account type:
    - Personal accounts: Performs sequential searches for each entity type
    - Work/school accounts: Uses unified search API for parallel search

    Args:
        query: Search query string (1-512 characters)
        account_id: Microsoft account ID
        entity_types: Types to search: 'message', 'event', 'driveItem' (default: all)
        limit: Maximum results per type (1-500, default: 50)
        use_cache: Whether to use cache (default: True)
        force_refresh: Bypass cache and fetch fresh data (default: False)

    Returns:
        Dictionary with results grouped by entity type
    """
    validated_entity_types = _validate_entity_types(entity_types)
    limit = validate_limit(limit, 1, 500, "limit")
    search_query = _validate_search_query(query)

    # Build cache parameters
    cache_params = {
        "query": search_query,
        "entity_types": sorted(validated_entity_types),
        "limit": limit,
    }

    # Check cache if enabled
    if use_cache and not force_refresh:
        try:
            cache_manager = get_cache_manager()
            cached_result = cache_manager.get_cached(
                account_id, "search_unified", cache_params
            )
            if cached_result:
                data, state = cached_result
                # Add cache status to items in each category
                for category, items in data.items():
                    for item in items:
                        item["_cache_status"] = state.value
                return data
        except Exception:
            # If cache fails, continue to API call
            pass

    # Get account type and route to appropriate search API
    account_type = _get_account_type(account_id)
    filtered_results = search_router.unified_search(
        account_id, account_type, search_query, validated_entity_types, limit
    )

    # Add cache metadata to each item
    cached_at = datetime.now(timezone.utc).isoformat()
    for category, items in filtered_results.items():
        for item in items:
            item["_cache_status"] = "fresh"
            item["_cached_at"] = cached_at

    # Store in cache
    if use_cache:
        try:
            cache_manager = get_cache_manager()
            cache_manager.set_cached(
                account_id, "search_unified", cache_params, filtered_results
            )
        except Exception:
            # If cache storage fails, still return the result
            pass

    return filtered_results
