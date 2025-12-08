from typing import Any
from datetime import datetime, timezone
from ..mcp_instance import mcp
from .. import graph
from .cache_tools import get_cache_manager
from ..validators import (
    ValidationError,
    format_validation_error,
    require_confirm,
    validate_email_format,
    validate_json_payload,
    validate_limit,
)

ALLOWED_CONTACT_UPDATE_KEYS = (
    "givenName",
    "surname",
    "displayName",
    "emailAddresses",
    "businessPhones",
    "homePhones",
    "mobilePhone",
    "jobTitle",
    "companyName",
    "department",
)


def _normalise_phone_list(phones: Any, param_name: str) -> list[str]:
    """Validate and normalise phone number lists."""
    if not isinstance(phones, list):
        raise ValidationError(
            format_validation_error(
                param_name,
                phones,
                "must be a list of phone numbers",
                "List of non-empty strings",
            )
        )
    normalised: list[str] = []
    for index, phone in enumerate(phones):
        if not isinstance(phone, str):
            raise ValidationError(
                format_validation_error(
                    f"{param_name}[{index}]",
                    phone,
                    "must be a string",
                    "Phone number string",
                )
            )
        trimmed = phone.strip()
        if not trimmed:
            raise ValidationError(
                format_validation_error(
                    f"{param_name}[{index}]",
                    phone,
                    "cannot be empty",
                    "Non-empty phone number",
                )
            )
        normalised.append(trimmed)
    return normalised


def _normalise_email_addresses(addresses: Any) -> list[dict[str, str]]:
    """Validate and normalise contact email addresses."""
    if not isinstance(addresses, list):
        raise ValidationError(
            format_validation_error(
                "updates.emailAddresses",
                addresses,
                "must be a list of email objects",
                "List of {'address': str, 'name': str?}",
            )
        )
    result: list[dict[str, str]] = []
    for index, entry in enumerate(addresses):
        if isinstance(entry, str):
            result.append(
                {
                    "address": validate_email_format(
                        entry,
                        f"updates.emailAddresses[{index}]",
                    ),
                }
            )
            continue
        entry_payload = validate_json_payload(
            entry,
            required_keys=("address",),
            allowed_keys=("address", "name"),
            param_name=f"updates.emailAddresses[{index}]",
        )
        address = validate_email_format(
            entry_payload["address"],
            f"updates.emailAddresses[{index}].address",
        )
        normalised_entry: dict[str, str] = {"address": address}
        if "name" in entry_payload:
            name_value = entry_payload["name"]
            if not isinstance(name_value, str):
                raise ValidationError(
                    format_validation_error(
                        f"updates.emailAddresses[{index}].name",
                        name_value,
                        "must be a string",
                        "Display name string",
                    )
                )
            normalised_entry["name"] = name_value.strip()
        result.append(normalised_entry)
    return result


# contact_list
@mcp.tool(
    name="contact_list",
    annotations={
        "title": "List Contacts",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
    meta={"category": "contact", "safety_level": "safe"},
)
def contact_list(
    account_id: str,
    limit: int = 50,
    use_cache: bool = True,
    force_refresh: bool = False,
) -> list[dict[str, Any]]:
    """📖 List contacts (read-only, safe for unsupervised use)

    Returns contacts with names, email addresses, and phone numbers.

    Caching: Results are cached for 20 minutes (fresh) / 2 hours (stale).
    Use force_refresh=True to bypass cache and fetch fresh data.

    Args:
        account_id: Microsoft account ID
        limit: Maximum contacts to return (1-500, default: 50)
        use_cache: Whether to use cached data if available (default: True)
        force_refresh: Force refresh from API, bypassing cache (default: False)

    Returns:
        List of contact objects with metadata.
        Each contact includes _cache_status and _cached_at fields.
    """
    limit = validate_limit(limit, 1, 500, "limit")

    # Build cache parameters
    cache_params = {
        "limit": limit,
    }

    # Try to get from cache if enabled and not forcing refresh
    if use_cache and not force_refresh:
        try:
            cache_manager = get_cache_manager()
            cached_result = cache_manager.get_cached(
                account_id, "contact_list", cache_params
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

    # Fetch from API
    params = {"$top": limit}
    contacts = list(
        graph.request_paginated("/me/contacts", account_id, params=params, limit=limit)
    )

    # Add cache metadata to each contact
    cached_at = datetime.now(timezone.utc).isoformat()
    for contact in contacts:
        contact["_cache_status"] = "fresh"
        contact["_cached_at"] = cached_at

    # Store in cache if enabled
    if use_cache:
        try:
            cache_manager = get_cache_manager()
            cache_manager.set_cached(account_id, "contact_list", cache_params, contacts)
        except Exception:
            # If cache storage fails, still return the result
            pass

    return contacts


# contact_get
@mcp.tool(
    name="contact_get",
    annotations={
        "title": "Get Contact",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
    meta={"category": "contact", "safety_level": "safe"},
)
def contact_get(
    contact_id: str,
    account_id: str,
    use_cache: bool = True,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """📖 Get contact details (read-only, safe for unsupervised use)

    Returns complete contact information including all fields.

    Caching: Results are cached for 30 minutes (fresh) / 4 hours (stale).
    Use force_refresh=True to bypass cache and fetch fresh data.

    Args:
        contact_id: The contact ID
        account_id: Microsoft account ID
        use_cache: Whether to use cached data if available (default: True)
        force_refresh: Force refresh from API, bypassing cache (default: False)

    Returns:
        Contact details with:
        - _cache_status: Cache state (fresh/stale/miss)
        - _cached_at: When data was cached (ISO format)
    """
    # Generate cache key from parameters
    cache_params = {
        "contact_id": contact_id,
    }

    # Try to get from cache if enabled and not forcing refresh
    if use_cache and not force_refresh:
        try:
            cache_manager = get_cache_manager()
            cached_result = cache_manager.get_cached(
                account_id, "contact_get", cache_params
            )

            if cached_result:
                data, state = cached_result
                # Add cache metadata
                data["_cache_status"] = state.value
                return data
        except Exception:
            # If cache fails, continue to API call
            pass

    # Fetch from API
    result = graph.request("GET", f"/me/contacts/{contact_id}", account_id)
    if not result:
        raise ValueError(f"Contact with ID {contact_id} not found")

    # Add cache metadata
    result["_cache_status"] = "miss"  # Fresh from API
    result["_cached_at"] = datetime.now(timezone.utc).isoformat()

    # Store in cache if enabled
    if use_cache:
        try:
            cache_manager = get_cache_manager()
            cache_manager.set_cached(account_id, "contact_get", cache_params, result)
        except Exception:
            # If cache storage fails, still return the result
            pass

    return result


# contact_create
@mcp.tool(
    name="contact_create",
    annotations={
        "title": "Create Contact",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
    meta={"category": "contact", "safety_level": "moderate"},
)
def contact_create(
    account_id: str,
    given_name: str,
    surname: str | None = None,
    email_addresses: str | list[str] | None = None,
    phone_numbers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """✏️ Create a new contact (requires user confirmation recommended)

    Creates a contact with name, email addresses, and phone numbers.

    Args:
        account_id: Microsoft account ID
        given_name: First name (required)
        surname: Last name (optional)
        email_addresses: Email address(es) (optional)
        phone_numbers: Phone numbers dict with keys: business, home, mobile (optional)

    Returns:
        Created contact object with ID
    """
    contact: dict[str, Any] = {"givenName": given_name}

    if surname:
        contact["surname"] = surname

    if email_addresses:
        email_list = (
            [email_addresses] if isinstance(email_addresses, str) else email_addresses
        )
        contact["emailAddresses"] = [
            {"address": email, "name": f"{given_name} {surname or ''}".strip()}
            for email in email_list
        ]

    if phone_numbers:
        if "business" in phone_numbers:
            contact["businessPhones"] = [phone_numbers["business"]]
        if "home" in phone_numbers:
            contact["homePhones"] = [phone_numbers["home"]]
        if "mobile" in phone_numbers:
            contact["mobilePhone"] = phone_numbers["mobile"]

    result = graph.request("POST", "/me/contacts", account_id, json=contact)
    if not result:
        raise ValueError("Failed to create contact")

    # Note: Cache invalidation happens automatically via TTL (20min for contact_list)

    return result


# contact_update
@mcp.tool(
    name="contact_update",
    annotations={
        "title": "Update Contact",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
    meta={"category": "contact", "safety_level": "moderate"},
)
def contact_update(
    contact_id: str, updates: dict[str, Any], account_id: str
) -> dict[str, Any]:
    """✏️ Update contact information (requires user confirmation recommended)

    Modifies contact fields like name, email, or phone numbers.

    Allowed update keys: givenName, surname, displayName, emailAddresses,
    businessPhones, homePhones, mobilePhone, jobTitle, companyName, department.

    Args:
        contact_id: The contact ID to update
        updates: Dictionary with fields to update
        account_id: Microsoft account ID

    Returns:
        Updated contact object
    """
    payload = validate_json_payload(
        updates,
        allowed_keys=ALLOWED_CONTACT_UPDATE_KEYS,
        param_name="updates",
    )
    if not payload:
        raise ValidationError(
            format_validation_error(
                "updates",
                payload,
                "must include at least one field",
                f"Subset of {sorted(ALLOWED_CONTACT_UPDATE_KEYS)}",
            )
        )

    graph_updates: dict[str, Any] = {}

    for field in (
        "givenName",
        "surname",
        "displayName",
        "jobTitle",
        "companyName",
        "department",
    ):
        if field in payload:
            value = payload[field]
            if not isinstance(value, str):
                raise ValidationError(
                    format_validation_error(
                        f"updates.{field}",
                        value,
                        "must be a string",
                        "Text value",
                    )
                )
            graph_updates[field] = value.strip()

    if "emailAddresses" in payload:
        graph_updates["emailAddresses"] = _normalise_email_addresses(
            payload["emailAddresses"]
        )

    if "businessPhones" in payload:
        graph_updates["businessPhones"] = _normalise_phone_list(
            payload["businessPhones"],
            "updates.businessPhones",
        )

    if "homePhones" in payload:
        graph_updates["homePhones"] = _normalise_phone_list(
            payload["homePhones"],
            "updates.homePhones",
        )

    if "mobilePhone" in payload:
        mobile_phone = payload["mobilePhone"]
        if mobile_phone is None:
            graph_updates["mobilePhone"] = None
        elif not isinstance(mobile_phone, str):
            raise ValidationError(
                format_validation_error(
                    "updates.mobilePhone",
                    mobile_phone,
                    "must be a string",
                    "Phone number string",
                )
            )
        else:
            trimmed = mobile_phone.strip()
            if not trimmed:
                raise ValidationError(
                    format_validation_error(
                        "updates.mobilePhone",
                        mobile_phone,
                        "cannot be empty",
                        "Non-empty phone number",
                    )
                )
            graph_updates["mobilePhone"] = trimmed

    result = graph.request(
        "PATCH", f"/me/contacts/{contact_id}", account_id, json=graph_updates
    )

    # Note: Cache invalidation happens automatically via TTL (20min for contact_list)

    return result or {"status": "updated"}


# contact_delete
@mcp.tool(
    name="contact_delete",
    annotations={
        "title": "Delete Contact",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
        "openWorldHint": True,
    },
    meta={
        "category": "contact",
        "safety_level": "critical",
        "requires_confirmation": True,
    },
)
def contact_delete(
    contact_id: str, account_id: str, confirm: bool = False
) -> dict[str, str]:
    """🔴 Delete a contact permanently (always require user confirmation)

    WARNING: This action permanently deletes the contact and cannot be undone.

    Args:
        contact_id: The contact to delete
        account_id: Microsoft account ID
        confirm: Must be True to confirm deletion (prevents accidents)

    Returns:
        Status confirmation
    """
    require_confirm(confirm, "delete contact")
    graph.request("DELETE", f"/me/contacts/{contact_id}", account_id)

    # Note: Cache invalidation happens automatically via TTL (20min for contact_list)

    return {"status": "deleted"}


# contact_create_list
@mcp.tool(
    name="contact_create_list",
    annotations={
        "title": "Create Contact List",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
    meta={"category": "contact", "safety_level": "moderate"},
)
def contact_create_list(
    account_id: str,
    list_name: str,
) -> dict[str, Any]:
    """✏️ Create a new contact list (requires user confirmation recommended)

    Creates a contact folder (list) for organizing contacts into groups.
    Useful for creating distribution lists, project teams, or other groupings.

    Args:
        account_id: Microsoft account ID
        list_name: Name for the contact list/folder

    Returns:
        Created contact folder object with ID

    Raises:
        ValidationError: If list name is empty or invalid.
    """
    # Validate list name
    if not isinstance(list_name, str):
        raise ValidationError(
            format_validation_error(
                "list_name",
                list_name,
                "must be a string",
                "Non-empty list name",
            )
        )

    name_stripped = list_name.strip()
    if not name_stripped:
        raise ValidationError(
            format_validation_error(
                "list_name",
                list_name,
                "cannot be empty",
                "Non-empty list name",
            )
        )

    # Create contact folder payload
    payload = {"displayName": name_stripped}

    # Create contact folder
    result = graph.request("POST", "/me/contactFolders", account_id, json=payload)
    if not result:
        raise ValueError("Failed to create contact list")

    return result


# contact_add_to_list
@mcp.tool(
    name="contact_add_to_list",
    annotations={
        "title": "Add Contact to List",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
    meta={"category": "contact", "safety_level": "moderate"},
)
def contact_add_to_list(
    account_id: str,
    contact_id: str,
    list_id: str,
) -> dict[str, Any]:
    """✏️ Add a contact to a contact list (requires user confirmation recommended)

    Adds an existing contact to a contact folder (list). The contact is copied
    to the list, so it will exist in both the original location and the list.

    Args:
        account_id: Microsoft account ID
        contact_id: The contact ID to add
        list_id: The contact list/folder ID

    Returns:
        Copy of the contact in the new list

    Raises:
        ValueError: If contact or list is not found.
    """
    # First, get the contact details
    contact = graph.request("GET", f"/me/contacts/{contact_id}", account_id)
    if not contact:
        raise ValueError(f"Contact with ID {contact_id} not found")

    # Create a copy of the contact in the target folder
    # Remove system fields that shouldn't be copied
    contact_copy = {
        k: v
        for k, v in contact.items()
        if k not in ("id", "@odata.context", "@odata.etag", "createdDateTime", "lastModifiedDateTime")
    }

    # Add the contact to the folder
    result = graph.request(
        "POST",
        f"/me/contactFolders/{list_id}/contacts",
        account_id,
        json=contact_copy,
    )
    if not result:
        raise ValueError(f"Failed to add contact to list {list_id}")

    return result


# contact_export
@mcp.tool(
    name="contact_export",
    annotations={
        "title": "Export Contact",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
    meta={"category": "contact", "safety_level": "safe"},
)
def contact_export(
    account_id: str,
    contact_id: str,
    format: str = "vcard",
) -> dict[str, Any]:
    """📖 Export a contact in vCard format (read-only, safe for unsupervised use)

    Exports contact information in vCard format for portability and sharing.
    vCard is a standard format supported by most contact management applications.

    Args:
        account_id: Microsoft account ID
        contact_id: The contact ID to export
        format: Export format (currently only "vcard" is supported)

    Returns:
        Dictionary containing the vCard data and metadata

    Raises:
        ValidationError: If format is not supported.
        ValueError: If contact is not found.
    """
    # Validate format
    if format.lower() != "vcard":
        raise ValidationError(
            format_validation_error(
                "format",
                format,
                "only 'vcard' format is currently supported",
                "vcard",
            )
        )

    # Get contact details
    contact = graph.request("GET", f"/me/contacts/{contact_id}", account_id)
    if not contact:
        raise ValueError(f"Contact with ID {contact_id} not found")

    # Build vCard format (version 3.0)
    vcard_lines = ["BEGIN:VCARD", "VERSION:3.0"]

    # Add name fields
    given_name = contact.get("givenName", "")
    surname = contact.get("surname", "")
    display_name = contact.get("displayName", f"{given_name} {surname}".strip())

    if display_name:
        vcard_lines.append(f"FN:{display_name}")

    if given_name or surname:
        # Format: surname;given_name;middle;prefix;suffix
        vcard_lines.append(f"N:{surname};{given_name};;;")

    # Add email addresses
    email_addresses = contact.get("emailAddresses", [])
    for idx, email_obj in enumerate(email_addresses):
        if isinstance(email_obj, dict) and "address" in email_obj:
            email_type = "INTERNET" if idx == 0 else f"INTERNET,type=OTHER{idx}"
            vcard_lines.append(f"EMAIL;type={email_type}:{email_obj['address']}")

    # Add phone numbers
    business_phones = contact.get("businessPhones", [])
    for phone in business_phones:
        vcard_lines.append(f"TEL;type=WORK,VOICE:{phone}")

    home_phones = contact.get("homePhones", [])
    for phone in home_phones:
        vcard_lines.append(f"TEL;type=HOME,VOICE:{phone}")

    mobile_phone = contact.get("mobilePhone")
    if mobile_phone:
        vcard_lines.append(f"TEL;type=CELL:{mobile_phone}")

    # Add organization information
    company_name = contact.get("companyName")
    department = contact.get("department")
    if company_name or department:
        org_value = f"{company_name or ''};{department or ''}"
        vcard_lines.append(f"ORG:{org_value}")

    job_title = contact.get("jobTitle")
    if job_title:
        vcard_lines.append(f"TITLE:{job_title}")

    # Add business address if available
    business_address = contact.get("businessAddress")
    if business_address and isinstance(business_address, dict):
        street = business_address.get("street", "")
        city = business_address.get("city", "")
        state = business_address.get("state", "")
        postal_code = business_address.get("postalCode", "")
        country = business_address.get("countryOrRegion", "")
        # Format: POBox;Extended;Street;City;State;PostalCode;Country
        vcard_lines.append(f"ADR;type=WORK:;;{street};{city};{state};{postal_code};{country}")

    # Add home address if available
    home_address = contact.get("homeAddress")
    if home_address and isinstance(home_address, dict):
        street = home_address.get("street", "")
        city = home_address.get("city", "")
        state = home_address.get("state", "")
        postal_code = home_address.get("postalCode", "")
        country = home_address.get("countryOrRegion", "")
        vcard_lines.append(f"ADR;type=HOME:;;{street};{city};{state};{postal_code};{country}")

    vcard_lines.append("END:VCARD")

    # Join lines with CRLF as per vCard spec
    vcard_content = "\r\n".join(vcard_lines)

    return {
        "contact_id": contact_id,
        "display_name": display_name,
        "format": "vcard",
        "vcard": vcard_content,
        "size_bytes": len(vcard_content.encode("utf-8")),
    }
