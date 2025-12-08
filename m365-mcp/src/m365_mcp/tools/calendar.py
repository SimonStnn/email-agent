from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from .. import graph
from ..mcp_instance import mcp
from .cache_tools import get_cache_manager
from ..validators import (
    ValidationError,
    format_validation_error,
    normalize_recipients,
    require_confirm,
    validate_choices,
    validate_datetime_window,
    validate_iso_datetime,
    validate_json_payload,
    validate_limit,
    validate_timezone,
)

MAX_CALENDAR_ATTENDEES = 500
CALENDAR_RESPONSE_ALIASES = {
    "accept": "accept",
    "decline": "decline",
    "tentativelyAccept": "tentativelyAccept",
    "tentative": "tentativelyAccept",
}
ALLOWED_CALENDAR_UPDATE_KEYS = (
    "subject",
    "start",
    "end",
    "timezone",
    "location",
    "body",
    "attendees",
)


def _get_user_email_with_fallback(account_id: str) -> str:
    """Get user email with fallback chain for profiles missing mail field.

    Implements a fallback strategy:
    1. Try mail field (primary email)
    2. Fallback to userPrincipalName (usually email-like)
    3. Fallback to first item in otherMails array
    4. Raise ValueError if no email found

    Args:
        account_id: Microsoft account identifier.

    Returns:
        User email address.

    Raises:
        ValueError: If no email address can be determined from user profile.
    """
    # Request user info with all possible email fields
    user_info = graph.request(
        "GET",
        "/me?$select=mail,userPrincipalName,otherMails",
        account_id,
    )

    if not user_info:
        raise ValueError("Failed to retrieve user profile information")

    # Try mail field first (primary email)
    mail = user_info.get("mail")
    if mail and isinstance(mail, str) and mail.strip():
        return mail.strip()

    # Fallback to userPrincipalName (usually email format)
    upn = user_info.get("userPrincipalName")
    if upn and isinstance(upn, str) and upn.strip():
        return upn.strip()

    # Fallback to first item in otherMails array
    other_mails = user_info.get("otherMails")
    if other_mails and isinstance(other_mails, list) and len(other_mails) > 0:
        first_other = other_mails[0]
        if first_other and isinstance(first_other, str) and first_other.strip():
            return first_other.strip()

    # No email found in any field
    raise ValueError(
        "Unable to determine user email address. "
        "The user profile is missing mail, userPrincipalName, "
        "and otherMails fields."
    )


# calendar_list_events
@mcp.tool(
    name="calendar_list_events",
    annotations={
        "title": "List Calendar Events",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
    meta={"category": "calendar", "safety_level": "safe"},
)
def calendar_list_events(
    account_id: str,
    days_ahead: int = 7,
    include_details: bool = False,
    limit: int = 50,
    use_cache: bool = True,
    force_refresh: bool = False,
) -> list[dict[str, Any]]:
    """📖 List upcoming calendar events (read-only, safe for unsupervised use)

    Returns calendar events from now until the specified number of days ahead.

    Caching: Results are cached for 5 minutes (fresh) / 30 minutes (stale).
    Use force_refresh=True to bypass cache and fetch fresh data.

    Args:
        account_id: Microsoft account ID
        days_ahead: Number of days ahead to look for events (1-365, default: 7)
        include_details: Include full event details like attendees and body (default: False)
        limit: Maximum events to return (1-200, default: 50)
        use_cache: Whether to use cached data if available (default: True)
        force_refresh: Force refresh from API, bypassing cache (default: False)

    Returns:
        List of calendar events with metadata.
        Each event includes _cache_status and _cached_at fields.
    """
    # Validate parameters
    if not isinstance(days_ahead, int) or days_ahead < 1 or days_ahead > 365:
        reason = "must be between 1 and 365"
        raise ValidationError(
            format_validation_error("days_ahead", days_ahead, reason, "1-365")
        )

    limit = validate_limit(limit, 1, 200, "limit")

    # Calculate time window
    now = datetime.now(timezone.utc)
    end_time = now + timedelta(days=days_ahead)

    # Build cache parameters
    cache_params = {
        "days_ahead": days_ahead,
        "include_details": include_details,
        "limit": limit,
    }

    # Check cache if enabled
    if use_cache and not force_refresh:
        try:
            cache_manager = get_cache_manager()
            cached_result = cache_manager.get_cached(
                account_id, "calendar_list_events", cache_params
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

    # Build select fields based on include_details
    if include_details:
        select_fields = "id,subject,start,end,location,body,attendees,organizer,isAllDay,isCancelled,recurrence,onlineMeeting"
    else:
        select_fields = "id,subject,start,end,location,organizer,isAllDay,isCancelled"

    # Query parameters
    params = {
        "$filter": f"start/dateTime ge '{now.isoformat()}' and start/dateTime le '{end_time.isoformat()}'",
        "$select": select_fields,
        "$orderby": "start/dateTime",
        "$top": limit,
    }

    # Fetch from API
    events = list(
        graph.request_paginated(
            "/me/calendar/events",
            account_id,
            params=params,
            limit=limit,
        )
    )

    # Add cache metadata to each event
    cached_at = datetime.now(timezone.utc).isoformat()
    for event in events:
        event["_cache_status"] = "fresh"
        event["_cached_at"] = cached_at

    # Store in cache
    if use_cache:
        try:
            cache_manager = get_cache_manager()
            cache_manager.set_cached(
                account_id, "calendar_list_events", cache_params, events
            )
        except Exception:
            # If cache storage fails, still return the result
            pass

    return events


# calendar_get_event
@mcp.tool(
    name="calendar_get_event",
    annotations={
        "title": "Get Calendar Event",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
    meta={"category": "calendar", "safety_level": "safe"},
)
def calendar_get_event(
    event_id: str,
    account_id: str,
    use_cache: bool = True,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """📖 Get full event details (read-only, safe for unsupervised use)

    Returns complete event information including recurrence patterns and online meeting details.

    Args:
        event_id: The event ID
        account_id: Microsoft account ID
        use_cache: Whether to use cache (default: True)
        force_refresh: Bypass cache and fetch fresh data (default: False)

    Returns:
        Complete event object with all metadata
    """
    # Build cache parameters
    cache_params = {"event_id": event_id}

    # Check cache if enabled
    if use_cache and not force_refresh:
        try:
            cache_manager = get_cache_manager()
            cached_result = cache_manager.get_cached(
                account_id, "calendar_get_event", cache_params
            )

            if cached_result:
                data, state = cached_result
                data["_cache_status"] = state.value
                return data
        except Exception:
            # If cache fails, continue to API call
            pass

    # Fetch from API
    result = graph.request("GET", f"/me/events/{event_id}", account_id)
    if not result:
        raise ValueError(f"Event with ID {event_id} not found")

    # Add cache metadata
    result["_cache_status"] = "fresh"
    result["_cached_at"] = datetime.now(timezone.utc).isoformat()

    # Store in cache
    if use_cache:
        try:
            cache_manager = get_cache_manager()
            cache_manager.set_cached(
                account_id, "calendar_get_event", cache_params, result
            )
        except Exception:
            # If cache storage fails, still return the result
            pass

    return result


# calendar_create_event
@mcp.tool(
    name="calendar_create_event",
    annotations={
        "title": "Create Calendar Event",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
    meta={"category": "calendar", "safety_level": "moderate"},
)
def calendar_create_event(
    account_id: str,
    subject: str,
    start: str,
    end: str,
    location: str | None = None,
    body: str | None = None,
    attendees: str | list[str] | None = None,
    timezone: str = "UTC",
) -> dict[str, Any]:
    """✏️ Create a calendar event (requires user confirmation recommended)

    Creates a new calendar event with optional attendees and location.
    Attendees will receive meeting invitations. Addresses are validated,
    deduplicated, and limited to 500 unique recipients.

    Args:
        account_id: Microsoft account ID
        subject: Event title
        start: Start time in ISO format (e.g., "2024-01-15T10:00:00")
        end: End time in ISO format
        location: Location name (optional)
        body: Event description (optional)
        attendees: Email address(es) of attendees (optional)
        timezone: Timezone for the event (default: "UTC")

    Returns:
        Created event object with ID

    Raises:
        ValidationError: If datetime values, timezone, or attendee
            addresses are invalid.
    """
    start_dt, end_dt = validate_datetime_window(start, end)
    timezone_normalized = validate_timezone(timezone)
    tzinfo = ZoneInfo(timezone_normalized)
    start_local = start_dt.astimezone(tzinfo)
    end_local = end_dt.astimezone(tzinfo)

    attendees_deduped: list[str] = []
    if attendees:
        attendee_candidates = normalize_recipients(attendees, "attendees")
        seen: set[str] = set()
        for address in attendee_candidates:
            key = address.casefold()
            if key in seen:
                continue
            seen.add(key)
            attendees_deduped.append(address)
        if len(attendees_deduped) > MAX_CALENDAR_ATTENDEES:
            reason = (
                f"must not exceed {MAX_CALENDAR_ATTENDEES} unique attendees per event"
            )
            raise ValidationError(
                format_validation_error(
                    "attendees",
                    len(attendees_deduped),
                    reason,
                    f"≤ {MAX_CALENDAR_ATTENDEES}",
                )
            )

    event = {
        "subject": subject,
        "start": {
            "dateTime": start_local.isoformat(),
            "timeZone": timezone_normalized,
        },
        "end": {
            "dateTime": end_local.isoformat(),
            "timeZone": timezone_normalized,
        },
    }

    if location:
        event["location"] = {"displayName": location}

    if body:
        event["body"] = {"contentType": "Text", "content": body}

    if attendees_deduped:
        event["attendees"] = [
            {"emailAddress": {"address": address}, "type": "required"}
            for address in attendees_deduped
        ]

    result = graph.request("POST", "/me/events", account_id, json=event)
    if not result:
        raise ValueError("Failed to create event")

    # Note: Cache invalidation for calendar events happens automatically via TTL
    # No manual invalidation needed as calendar list caches are short-lived (5min)

    return result


# calendar_update_event
@mcp.tool(
    name="calendar_update_event",
    annotations={
        "title": "Update Calendar Event",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
    meta={"category": "calendar", "safety_level": "moderate"},
)
def calendar_update_event(
    event_id: str, updates: dict[str, Any], account_id: str
) -> dict[str, Any]:
    """✏️ Update event properties (requires user confirmation recommended)

    Modifies event details like time, location, or attendees.
    Attendees will receive update notifications.

    Allowed update keys: subject, start, end, timezone, location, body, attendees.

    Args:
        event_id: The event ID to update
        updates: Dictionary with fields to update (subject, start, end, location, body)
        account_id: Microsoft account ID

    Returns:
        Updated event object
    """
    payload = validate_json_payload(
        updates,
        allowed_keys=ALLOWED_CALENDAR_UPDATE_KEYS,
        param_name="updates",
    )
    if not payload:
        raise ValidationError(
            format_validation_error(
                "updates",
                payload,
                "must include at least one field",
                f"Subset of {sorted(ALLOWED_CALENDAR_UPDATE_KEYS)}",
            )
        )

    timezone_override: str | None = None
    if "timezone" in payload:
        timezone_override = validate_timezone(payload["timezone"], "updates.timezone")
        if "start" not in payload and "end" not in payload:
            raise ValidationError(
                format_validation_error(
                    "updates.timezone",
                    payload["timezone"],
                    "can only be provided when updating start or end",
                    "Include start/end alongside timezone",
                )
            )

    start_value: str | None = None
    end_value: str | None = None

    if "start" in payload:
        start_raw = payload["start"]
        if not isinstance(start_raw, str):
            raise ValidationError(
                format_validation_error(
                    "updates.start",
                    start_raw,
                    "must be an ISO-8601 datetime string",
                    "YYYY-MM-DDTHH:MM:SS+TZ",
                )
            )
        validate_iso_datetime(start_raw, "updates.start")
        start_value = start_raw

    if "end" in payload:
        end_raw = payload["end"]
        if not isinstance(end_raw, str):
            raise ValidationError(
                format_validation_error(
                    "updates.end",
                    end_raw,
                    "must be an ISO-8601 datetime string",
                    "YYYY-MM-DDTHH:MM:SS+TZ",
                )
            )
        validate_iso_datetime(end_raw, "updates.end")
        end_value = end_raw

    if start_value and end_value:
        validate_datetime_window(start_value, end_value)

    formatted_updates: dict[str, Any] = {}

    if "subject" in payload:
        subject_value = payload["subject"]
        if not isinstance(subject_value, str):
            raise ValidationError(
                format_validation_error(
                    "updates.subject",
                    subject_value,
                    "must be a string",
                    "Subject string",
                )
            )
        formatted_updates["subject"] = subject_value

    timezone_for_dates = timezone_override or "UTC"

    if start_value is not None:
        formatted_updates["start"] = {
            "dateTime": start_value,
            "timeZone": timezone_for_dates,
        }

    if end_value is not None:
        formatted_updates["end"] = {
            "dateTime": end_value,
            "timeZone": timezone_for_dates,
        }

    if "location" in payload:
        location_value = payload["location"]
        if not isinstance(location_value, str):
            raise ValidationError(
                format_validation_error(
                    "updates.location",
                    location_value,
                    "must be a string",
                    "Location name string",
                )
            )
        formatted_updates["location"] = {"displayName": location_value.strip()}

    if "body" in payload:
        body_value = payload["body"]
        if not isinstance(body_value, str):
            raise ValidationError(
                format_validation_error(
                    "updates.body",
                    body_value,
                    "must be a string",
                    "Event description string",
                )
            )
        formatted_updates["body"] = {"contentType": "Text", "content": body_value}

    if "attendees" in payload:
        attendees_value = payload["attendees"]
        if isinstance(attendees_value, list) and not attendees_value:
            formatted_updates["attendees"] = []
        else:
            attendee_candidates = normalize_recipients(
                attendees_value,
                "updates.attendees",
            )
            deduped: list[str] = []
            seen: set[str] = set()
            for address in attendee_candidates:
                key = address.casefold()
                if key in seen:
                    continue
                seen.add(key)
                deduped.append(address)
            if len(deduped) > MAX_CALENDAR_ATTENDEES:
                raise ValidationError(
                    format_validation_error(
                        "updates.attendees",
                        len(deduped),
                        f"must not exceed {MAX_CALENDAR_ATTENDEES} attendees",
                        f"≤ {MAX_CALENDAR_ATTENDEES}",
                    )
                )
            formatted_updates["attendees"] = [
                {"emailAddress": {"address": address}, "type": "required"}
                for address in deduped
            ]

    result = graph.request(
        "PATCH", f"/me/events/{event_id}", account_id, json=formatted_updates
    )

    # Note: Cache invalidation happens automatically via TTL (5min for calendar_list_events)

    return result or {"status": "updated"}


# calendar_delete_event
@mcp.tool(
    name="calendar_delete_event",
    annotations={
        "title": "Delete Calendar Event",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
        "openWorldHint": True,
    },
    meta={
        "category": "calendar",
        "safety_level": "critical",
        "requires_confirmation": True,
    },
)
def calendar_delete_event(
    account_id: str,
    event_id: str,
    send_cancellation: bool = True,
    confirm: bool = False,
) -> dict[str, str]:
    """🔴 Delete a calendar event (always require user confirmation)

    WARNING: This action permanently deletes the event and cannot be undone.
    If this is a meeting, attendees will receive cancellation notices.

    Args:
        account_id: Microsoft account ID
        event_id: The event to delete
        send_cancellation: Whether to notify attendees (default: True)
        confirm: Must be True to confirm deletion (prevents accidents)

    Returns:
        Status confirmation
    """
    require_confirm(confirm, "delete calendar event")
    if send_cancellation:
        graph.request("POST", f"/me/events/{event_id}/cancel", account_id, json={})
    else:
        graph.request("DELETE", f"/me/events/{event_id}", account_id)

    # Note: Cache invalidation happens automatically via TTL (5min for calendar_list_events)

    return {"status": "deleted"}


# calendar_respond_event
@mcp.tool(
    name="calendar_respond_event",
    annotations={
        "title": "Respond to Calendar Event",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
    meta={"category": "calendar", "safety_level": "moderate"},
)
def calendar_respond_event(
    account_id: str,
    event_id: str,
    response: str = "accept",
    message: str | None = None,
) -> dict[str, str]:
    """⚠️ Respond to a calendar event invitation (requires user confirmation recommended)

    IMPORTANT: This sends a response to the event organizer.

    Valid responses:
        - "accept" - Accept the invitation
        - "decline" - Decline the invitation
        - "tentativelyAccept" - Mark as tentative
      (Input is case-insensitive; "tentative" is accepted as an alias.)

    Args:
        account_id: Microsoft account ID
        event_id: The event ID to respond to
        response: Response type (default: "accept")
        message: Optional message to the organizer

    Returns:
        Status confirmation

    Raises:
        ValidationError: If the response value or message payload is invalid.
    """
    canonical_key = validate_choices(
        response,
        CALENDAR_RESPONSE_ALIASES.keys(),
        "response",
    )
    resolved_response = CALENDAR_RESPONSE_ALIASES[canonical_key]

    payload: dict[str, Any] = {"sendResponse": True}

    if message is not None:
        if not isinstance(message, str):
            reason = "must be a string"
            raise ValidationError(
                format_validation_error(
                    "message",
                    message,
                    reason,
                    "Non-empty response message or omit parameter",
                )
            )
        message_trimmed = message.strip()
        if not message_trimmed:
            reason = "cannot be empty when provided"
            raise ValidationError(
                format_validation_error(
                    "message",
                    message,
                    reason,
                    "Non-empty response message or omit parameter",
                )
            )
        payload["comment"] = message_trimmed

    graph.request(
        "POST",
        f"/me/events/{event_id}/{resolved_response}",
        account_id,
        json=payload,
    )
    return {"status": resolved_response}


# calendar_check_availability
@mcp.tool(
    name="calendar_check_availability",
    annotations={
        "title": "Check Calendar Availability",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
    meta={"category": "calendar", "safety_level": "safe"},
)
def calendar_check_availability(
    account_id: str,
    start: str,
    end: str,
    attendees: str | list[str] | None = None,
) -> dict[str, Any]:
    """📖 Check calendar availability for scheduling (read-only, safe for unsupervised use)

    Returns free/busy information for the user and optional attendees.
    Useful for finding meeting times.

    Args:
        account_id: Microsoft account ID
        start: Start time in ISO format
        end: End time in ISO format
        attendees: Optional email address(es) to check availability

    Returns:
        Schedule information with free/busy slots

    Raises:
        ValidationError: If start/end datetimes or attendee addresses
            are invalid.
        ValueError: If the current account email address is unavailable.
    """
    start_dt, end_dt = validate_datetime_window(start, end)

    attendee_addresses: list[str] = []
    if attendees:
        attendee_candidates = normalize_recipients(attendees, "attendees")
        seen_attendees: set[str] = set()
        for address in attendee_candidates:
            key = address.casefold()
            if key in seen_attendees:
                continue
            seen_attendees.add(key)
            attendee_addresses.append(address)
        if len(attendee_addresses) > MAX_CALENDAR_ATTENDEES:
            reason = (
                f"must not exceed {MAX_CALENDAR_ATTENDEES} unique attendees per request"
            )
            raise ValidationError(
                format_validation_error(
                    "attendees",
                    len(attendee_addresses),
                    reason,
                    f"≤ {MAX_CALENDAR_ATTENDEES}",
                )
            )

    # Get user email with fallback chain
    user_email = _get_user_email_with_fallback(account_id)
    schedules = [user_email]
    current_keys = {user_email.casefold()}
    for address in attendee_addresses:
        key = address.casefold()
        if key in current_keys:
            continue
        current_keys.add(key)
        schedules.append(address)

    payload = {
        "schedules": schedules,
        "startTime": {
            "dateTime": start_dt.astimezone(timezone.utc).isoformat(),
            "timeZone": "UTC",
        },
        "endTime": {
            "dateTime": end_dt.astimezone(timezone.utc).isoformat(),
            "timeZone": "UTC",
        },
        "availabilityViewInterval": 30,
    }

    result = graph.request("POST", "/me/calendar/getSchedule", account_id, json=payload)
    if not result:
        raise ValueError("Failed to check availability")
    return result


# calendar_forward_event
@mcp.tool(
    name="calendar_forward_event",
    annotations={
        "title": "Forward Calendar Event",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
    meta={
        "category": "calendar",
        "safety_level": "dangerous",
        "requires_confirmation": True,
    },
)
def calendar_forward_event(
    account_id: str,
    event_id: str,
    to: str | list[str],
    cc: str | list[str] | None = None,
    message: str | None = None,
    confirm: bool = False,
) -> dict[str, str]:
    """📧 Forward a calendar event to recipients (always require user confirmation)

    WARNING: Meeting invitation will be sent immediately to specified recipients.
    This action cannot be undone.

    Addresses are validated, deduplicated across To/CC, and limited to
    500 unique recipients in total.

    Args:
        account_id: Microsoft account ID
        event_id: The event ID to forward
        to: Recipient email address(es)
        cc: CC recipient email address(es) (optional)
        message: Optional comment/message to include with forward (plain text)
        confirm: Must be True to confirm sending (prevents accidents)

    Returns:
        Status confirmation

    Raises:
        ValidationError: If recipients are invalid, exceed limits,
            or confirm is False.
    """
    to_normalized = normalize_recipients(to, "to")
    cc_normalized = normalize_recipients(cc, "cc") if cc else []

    seen: set[str] = set()
    to_unique: list[str] = []
    cc_unique: list[str] = []

    for address in to_normalized:
        key = address.casefold()
        if key in seen:
            continue
        seen.add(key)
        to_unique.append(address)

    for address in cc_normalized:
        key = address.casefold()
        if key in seen:
            continue
        seen.add(key)
        cc_unique.append(address)

    total_unique = len(to_unique) + len(cc_unique)
    if total_unique > MAX_CALENDAR_ATTENDEES:
        reason = f"must not exceed {MAX_CALENDAR_ATTENDEES} unique recipients"
        raise ValidationError(
            format_validation_error(
                "recipients",
                total_unique,
                reason,
                f"≤ {MAX_CALENDAR_ATTENDEES}",
            )
        )

    require_confirm(confirm, "forward calendar event")

    payload: dict[str, Any] = {
        "toRecipients": [{"emailAddress": {"address": addr}} for addr in to_unique],
    }

    if cc_unique:
        payload["ccRecipients"] = [
            {"emailAddress": {"address": addr}} for addr in cc_unique
        ]

    if message:
        message_stripped = message.strip()
        if message_stripped:
            payload["comment"] = message_stripped

    endpoint = f"/me/events/{event_id}/forward"
    graph.request("POST", endpoint, account_id, json=payload)

    return {"status": "forwarded"}


# calendar_list_calendars
@mcp.tool(
    name="calendar_list_calendars",
    annotations={
        "title": "List Calendars",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
    meta={"category": "calendar", "safety_level": "safe"},
)
def calendar_list_calendars(
    account_id: str,
    use_cache: bool = True,
    force_refresh: bool = False,
) -> list[dict[str, Any]]:
    """📖 List all available calendars (read-only, safe for unsupervised use)

    Returns all calendars accessible by the user, including primary calendar
    and any additional calendars (shared, group, etc.).

    Caching: Results are cached for 15 minutes (fresh) / 1 hour (stale).
    Use force_refresh=True to bypass cache and fetch fresh data.

    Args:
        account_id: Microsoft account ID
        use_cache: Whether to use cached data if available (default: True)
        force_refresh: Force refresh from API, bypassing cache (default: False)

    Returns:
        List of calendar objects with metadata.
        Each calendar includes _cache_status and _cached_at fields.
    """
    # Build cache parameters
    cache_params = {}

    # Check cache if enabled
    if use_cache and not force_refresh:
        try:
            cache_manager = get_cache_manager()
            cached_result = cache_manager.get_cached(
                account_id, "calendar_list_calendars", cache_params
            )

            if cached_result:
                data, state = cached_result
                # Add cache status to each calendar
                for calendar in data:
                    calendar["_cache_status"] = state.value
                return data
        except Exception:
            # If cache fails, continue to API call
            pass

    # Fetch from API
    calendars = list(
        graph.request_paginated(
            "/me/calendars",
            account_id,
            params={"$select": "id,name,color,canEdit,canShare,canViewPrivateItems,owner,isDefaultCalendar"},
        )
    )

    # Add cache metadata to each calendar
    cached_at = datetime.now(timezone.utc).isoformat()
    for calendar in calendars:
        calendar["_cache_status"] = "fresh"
        calendar["_cached_at"] = cached_at

    # Store in cache
    if use_cache:
        try:
            cache_manager = get_cache_manager()
            cache_manager.set_cached(
                account_id, "calendar_list_calendars", cache_params, calendars
            )
        except Exception:
            # If cache storage fails, still return the result
            pass

    return calendars


# calendar_create_calendar
@mcp.tool(
    name="calendar_create_calendar",
    annotations={
        "title": "Create Calendar",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
    meta={"category": "calendar", "safety_level": "moderate"},
)
def calendar_create_calendar(
    account_id: str,
    name: str,
) -> dict[str, Any]:
    """✏️ Create a new calendar (requires user confirmation recommended)

    Creates a new calendar in the user's mailbox. Useful for organizing
    events into separate calendars (work, personal, project-specific, etc.).

    Args:
        account_id: Microsoft account ID
        name: Name for the new calendar

    Returns:
        Created calendar object with ID and metadata

    Raises:
        ValidationError: If calendar name is empty or invalid.
    """
    # Validate calendar name
    if not isinstance(name, str):
        raise ValidationError(
            format_validation_error(
                "name",
                name,
                "must be a string",
                "Non-empty calendar name",
            )
        )

    name_stripped = name.strip()
    if not name_stripped:
        raise ValidationError(
            format_validation_error(
                "name",
                name,
                "cannot be empty",
                "Non-empty calendar name",
            )
        )

    # Create calendar payload
    payload = {"name": name_stripped}

    # Create calendar
    result = graph.request("POST", "/me/calendars", account_id, json=payload)
    if not result:
        raise ValueError("Failed to create calendar")

    # Invalidate calendar list cache
    try:
        cache_manager = get_cache_manager()
        cache_manager.invalidate_pattern(
            f"calendar_list_calendars:{account_id}:*",
            reason="calendar_created",
        )
    except Exception:
        # If cache invalidation fails, continue
        pass

    return result


# calendar_delete_calendar
@mcp.tool(
    name="calendar_delete_calendar",
    annotations={
        "title": "Delete Calendar",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
        "openWorldHint": True,
    },
    meta={
        "category": "calendar",
        "safety_level": "critical",
        "requires_confirmation": True,
    },
)
def calendar_delete_calendar(
    account_id: str,
    calendar_id: str,
    confirm: bool = False,
) -> dict[str, str]:
    """🔴 Delete a calendar permanently (always require user confirmation)

    WARNING: This action permanently deletes the calendar and ALL events
    contained within it. This action cannot be undone.

    Note: The default calendar cannot be deleted.

    Args:
        account_id: Microsoft account ID
        calendar_id: The calendar ID to delete
        confirm: Must be True to confirm deletion (prevents accidents)

    Returns:
        Status confirmation

    Raises:
        ValidationError: If confirm is False.
        ValueError: If attempting to delete the default calendar.
    """
    require_confirm(confirm, "delete calendar")

    # Check if this is the default calendar (cannot be deleted)
    calendar_info = graph.request(
        "GET",
        f"/me/calendars/{calendar_id}?$select=isDefaultCalendar",
        account_id,
    )

    if calendar_info and calendar_info.get("isDefaultCalendar"):
        raise ValueError("Cannot delete the default calendar")

    # Delete calendar
    graph.request("DELETE", f"/me/calendars/{calendar_id}", account_id)

    # Invalidate calendar list cache
    try:
        cache_manager = get_cache_manager()
        cache_manager.invalidate_pattern(
            f"calendar_list_calendars:{account_id}:*",
            reason="calendar_deleted",
        )
    except Exception:
        # If cache invalidation fails, continue
        pass

    return {"status": "deleted"}


# calendar_propose_new_time
@mcp.tool(
    name="calendar_propose_new_time",
    annotations={
        "title": "Propose New Meeting Time",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
    meta={"category": "calendar", "safety_level": "moderate"},
)
def calendar_propose_new_time(
    account_id: str,
    event_id: str,
    proposed_start: str,
    proposed_end: str,
    message: str | None = None,
) -> dict[str, str]:
    """✏️ Propose a new time for a meeting (requires user confirmation recommended)

    Proposes a new meeting time to the organizer. This is useful when you've
    been invited to a meeting but the time doesn't work for you.

    Note: This only works for meetings where you are an attendee, not the organizer.

    Args:
        account_id: Microsoft account ID
        event_id: The event ID to propose new time for
        proposed_start: Proposed start time in ISO format (e.g., "2024-01-15T10:00:00")
        proposed_end: Proposed end time in ISO format
        message: Optional message explaining the proposed change

    Returns:
        Status confirmation

    Raises:
        ValidationError: If datetime values are invalid.
    """
    # Validate datetime window
    start_dt, end_dt = validate_datetime_window(proposed_start, proposed_end)

    # Build payload
    payload: dict[str, Any] = {
        "proposedNewTime": {
            "start": {
                "dateTime": start_dt.astimezone(timezone.utc).isoformat(),
                "timeZone": "UTC",
            },
            "end": {
                "dateTime": end_dt.astimezone(timezone.utc).isoformat(),
                "timeZone": "UTC",
            },
        },
        "sendResponse": True,
    }

    if message:
        message_stripped = message.strip()
        if message_stripped:
            payload["comment"] = message_stripped

    # Send tentative response with proposed new time
    graph.request(
        "POST",
        f"/me/events/{event_id}/tentativelyAccept",
        account_id,
        json=payload,
    )

    return {"status": "proposed_new_time"}


# calendar_get_free_busy
@mcp.tool(
    name="calendar_get_free_busy",
    annotations={
        "title": "Get Free/Busy Times",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
    meta={"category": "calendar", "safety_level": "safe"},
)
def calendar_get_free_busy(
    account_id: str,
    attendees: str | list[str],
    start: str,
    end: str,
    time_interval: int = 30,
) -> dict[str, Any]:
    """📖 Get simplified free/busy times for attendees (read-only, safe for unsupervised use)

    Returns a simplified view of free/busy information for specified attendees.
    This is similar to calendar_check_availability but focuses on availability
    view strings rather than detailed schedule information.

    Args:
        account_id: Microsoft account ID
        attendees: Email address(es) to check availability for
        start: Start time in ISO format
        end: End time in ISO format
        time_interval: Interval in minutes for availability view (default: 30)

    Returns:
        Free/busy information with availability view strings

    Raises:
        ValidationError: If start/end datetimes or attendee addresses are invalid.
    """
    # Validate datetime window
    start_dt, end_dt = validate_datetime_window(start, end)

    # Validate and normalize attendees
    attendee_candidates = normalize_recipients(attendees, "attendees")
    attendee_addresses: list[str] = []
    seen: set[str] = set()
    for address in attendee_candidates:
        key = address.casefold()
        if key in seen:
            continue
        seen.add(key)
        attendee_addresses.append(address)

    if len(attendee_addresses) > MAX_CALENDAR_ATTENDEES:
        reason = f"must not exceed {MAX_CALENDAR_ATTENDEES} unique attendees"
        raise ValidationError(
            format_validation_error(
                "attendees",
                len(attendee_addresses),
                reason,
                f"≤ {MAX_CALENDAR_ATTENDEES}",
            )
        )

    # Validate time interval
    if not isinstance(time_interval, int) or time_interval < 5 or time_interval > 1440:
        raise ValidationError(
            format_validation_error(
                "time_interval",
                time_interval,
                "must be between 5 and 1440 minutes",
                "5-1440",
            )
        )

    # Build payload
    payload = {
        "schedules": attendee_addresses,
        "startTime": {
            "dateTime": start_dt.astimezone(timezone.utc).isoformat(),
            "timeZone": "UTC",
        },
        "endTime": {
            "dateTime": end_dt.astimezone(timezone.utc).isoformat(),
            "timeZone": "UTC",
        },
        "availabilityViewInterval": time_interval,
    }

    # Make API request
    result = graph.request("POST", "/me/calendar/getSchedule", account_id, json=payload)
    if not result:
        raise ValueError("Failed to get free/busy information")

    return result
