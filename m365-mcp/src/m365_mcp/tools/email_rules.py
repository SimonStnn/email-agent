from typing import Any
from ..mcp_instance import mcp
from .. import graph
from ..validators import (
    ValidationError,
    format_validation_error,
    require_confirm,
    validate_choices,
    validate_email_format,
    validate_json_payload,
)

RULE_FLAG_STATUS_CHOICES = {"notFlagged", "flagged", "complete"}
RULE_IMPORTANCE_CHOICES = {"low", "normal", "high"}
RULE_SENSITIVITY_CHOICES = {"normal", "personal", "private", "confidential"}
RULE_MEETING_TYPES = {
    "meetingRequest",
    "meetingCancelled",
    "meetingAccepted",
    "meetingTentativelyAccepted",
    "meetingDeclined",
}

RULE_PREDICATE_STRING_LIST_KEYS = {
    "categories",
    "subjectContains",
    "bodyContains",
    "bodyOrSubjectContains",
    "senderContains",
    "recipientContains",
    "senderAddressContains",
    "recipientAddressContains",
    "headers",
    "headerContains",
    "searchTerms",
}
RULE_PREDICATE_RECIPIENT_KEYS = {
    "fromAddresses",
    "sentToAddresses",
}
RULE_PREDICATE_BOOL_KEYS = {
    "hasAttachments",
    "stopProcessingRules",
}
RULE_PREDICATE_CHOICE_MAP = {
    "importance": RULE_IMPORTANCE_CHOICES,
    "sensitivity": RULE_SENSITIVITY_CHOICES,
}
ALLOWED_RULE_PREDICATE_KEYS = tuple(
    RULE_PREDICATE_STRING_LIST_KEYS
    | RULE_PREDICATE_RECIPIENT_KEYS
    | RULE_PREDICATE_BOOL_KEYS
    | set(RULE_PREDICATE_CHOICE_MAP.keys())
    | {
        "withinSizeRange",
        "messageActionFlag",
        "meetingMessageType",
    }
)

RULE_ACTION_STRING_LIST_KEYS = {"assignCategories"}
RULE_ACTION_STRING_KEYS = {"copyToFolder", "moveToFolder"}
RULE_ACTION_RECIPIENT_KEYS = {
    "forwardTo",
    "forwardAsAttachmentTo",
    "redirectTo",
}
RULE_ACTION_BOOL_KEYS = {
    "markAsRead",
    "stopProcessingRules",
    "delete",
    "permanentDelete",
}
RULE_ACTION_CHOICE_MAP = {"markImportance": RULE_IMPORTANCE_CHOICES}
ALLOWED_RULE_ACTION_KEYS = tuple(
    RULE_ACTION_STRING_LIST_KEYS
    | RULE_ACTION_STRING_KEYS
    | RULE_ACTION_RECIPIENT_KEYS
    | RULE_ACTION_BOOL_KEYS
    | set(RULE_ACTION_CHOICE_MAP.keys())
)


def _validate_bool(value: Any, param_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(
            format_validation_error(
                param_name,
                value,
                "must be a boolean",
                "True or False",
            )
        )
    return value


def _validate_string_list(values: Any, param_name: str) -> list[str]:
    if not isinstance(values, list):
        raise ValidationError(
            format_validation_error(
                param_name,
                values,
                "must be a list of strings",
                "List of non-empty strings",
            )
        )
    normalised: list[str] = []
    for index, item in enumerate(values):
        if not isinstance(item, str):
            raise ValidationError(
                format_validation_error(
                    f"{param_name}[{index}]",
                    item,
                    "must be a string",
                    "Text value",
                )
            )
        trimmed = item.strip()
        if not trimmed:
            raise ValidationError(
                format_validation_error(
                    f"{param_name}[{index}]",
                    item,
                    "cannot be empty",
                    "Non-empty string",
                )
            )
        normalised.append(trimmed)
    return normalised


def _normalise_rule_recipients(
    recipients: Any,
    param_name: str,
) -> list[dict[str, dict[str, str]]]:
    if not isinstance(recipients, list):
        raise ValidationError(
            format_validation_error(
                param_name,
                recipients,
                "must be a list of recipient objects",
                "List of email addresses",
            )
        )
    result: list[dict[str, dict[str, str]]] = []
    for index, entry in enumerate(recipients):
        if isinstance(entry, str):
            email = validate_email_format(
                entry,
                f"{param_name}[{index}]",
            )
            result.append({"emailAddress": {"address": email}})
            continue
        if not isinstance(entry, dict):
            raise ValidationError(
                format_validation_error(
                    f"{param_name}[{index}]",
                    entry,
                    "must be a recipient dictionary",
                    "{'emailAddress': {'address': str}}",
                )
            )
        if "emailAddress" in entry and isinstance(entry["emailAddress"], dict):
            email_address = entry["emailAddress"].get("address")
            if not isinstance(email_address, str):
                raise ValidationError(
                    format_validation_error(
                        f"{param_name}[{index}].emailAddress.address",
                        email_address,
                        "must be a string",
                        "Email address",
                    )
                )
            email = validate_email_format(
                email_address,
                f"{param_name}[{index}].emailAddress.address",
            )
            result.append({"emailAddress": {"address": email}})
            continue
        if "address" in entry:
            email = validate_email_format(
                entry["address"],
                f"{param_name}[{index}].address",
            )
            result.append({"emailAddress": {"address": email}})
            continue
        raise ValidationError(
            format_validation_error(
                f"{param_name}[{index}]",
                entry,
                "must include an email address",
                "{'emailAddress': {'address': str}}",
            )
        )
    return result


def _validate_size_range(value: Any, param_name: str) -> dict[str, int]:
    payload = validate_json_payload(
        value,
        allowed_keys=("minimumSize", "maximumSize"),
        param_name=param_name,
    )
    validated: dict[str, int] = {}
    for key in ("minimumSize", "maximumSize"):
        if key in payload:
            amount = payload[key]
            if not isinstance(amount, int):
                raise ValidationError(
                    format_validation_error(
                        f"{param_name}.{key}",
                        amount,
                        "must be an integer number of bytes",
                        "Integer value ≥ 0",
                    )
                )
            if amount < 0:
                raise ValidationError(
                    format_validation_error(
                        f"{param_name}.{key}",
                        amount,
                        "cannot be negative",
                        "Value ≥ 0",
                    )
                )
            validated[key] = amount
    if (
        "minimumSize" in validated
        and "maximumSize" in validated
        and validated["minimumSize"] > validated["maximumSize"]
    ):
        raise ValidationError(
            format_validation_error(
                param_name,
                value,
                "minimumSize cannot exceed maximumSize",
                "minimumSize ≤ maximumSize",
            )
        )
    return validated


def _validate_rule_predicates(
    predicates: Any,
    param_name: str,
) -> dict[str, Any]:
    payload = validate_json_payload(
        predicates,
        allowed_keys=ALLOWED_RULE_PREDICATE_KEYS,
        param_name=param_name,
    )
    validated: dict[str, Any] = {}
    for key, value in payload.items():
        if key in RULE_PREDICATE_STRING_LIST_KEYS:
            validated[key] = _validate_string_list(value, f"{param_name}.{key}")
        elif key in RULE_PREDICATE_RECIPIENT_KEYS:
            validated[key] = _normalise_rule_recipients(value, f"{param_name}.{key}")
        elif key in RULE_PREDICATE_BOOL_KEYS:
            validated[key] = _validate_bool(value, f"{param_name}.{key}")
        elif key in RULE_PREDICATE_CHOICE_MAP:
            validated[key] = validate_choices(
                value,
                RULE_PREDICATE_CHOICE_MAP[key],
                f"{param_name}.{key}",
            )
        elif key == "withinSizeRange":
            validated[key] = _validate_size_range(value, f"{param_name}.{key}")
        elif key == "messageActionFlag":
            validated[key] = validate_choices(
                value,
                RULE_FLAG_STATUS_CHOICES,
                f"{param_name}.messageActionFlag",
            )
        elif key == "meetingMessageType":
            validated[key] = validate_choices(
                value,
                RULE_MEETING_TYPES,
                f"{param_name}.meetingMessageType",
            )
    return validated


def _validate_rule_actions(
    actions: Any,
    param_name: str,
) -> dict[str, Any]:
    payload = validate_json_payload(
        actions,
        allowed_keys=ALLOWED_RULE_ACTION_KEYS,
        param_name=param_name,
    )
    validated: dict[str, Any] = {}
    for key, value in payload.items():
        if key in RULE_ACTION_STRING_LIST_KEYS:
            validated[key] = _validate_string_list(value, f"{param_name}.{key}")
        elif key in RULE_ACTION_STRING_KEYS:
            if not isinstance(value, str):
                raise ValidationError(
                    format_validation_error(
                        f"{param_name}.{key}",
                        value,
                        "must be a string",
                        "Identifier or folder ID string",
                    )
                )
            trimmed = value.strip()
            if not trimmed:
                raise ValidationError(
                    format_validation_error(
                        f"{param_name}.{key}",
                        value,
                        "cannot be empty",
                        "Non-empty string",
                    )
                )
            validated[key] = trimmed
        elif key in RULE_ACTION_RECIPIENT_KEYS:
            validated[key] = _normalise_rule_recipients(value, f"{param_name}.{key}")
        elif key in RULE_ACTION_BOOL_KEYS:
            validated[key] = _validate_bool(value, f"{param_name}.{key}")
        elif key in RULE_ACTION_CHOICE_MAP:
            validated[key] = validate_choices(
                value,
                RULE_ACTION_CHOICE_MAP[key],
                f"{param_name}.{key}",
            )
    return validated


def _emailrules_list_impl(account_id: str) -> list[dict[str, Any]]:
    result = graph.request("GET", "/me/mailFolders/inbox/messageRules", account_id)
    if not result or "value" not in result:
        return []
    return list(result["value"])


def _emailrules_get_impl(rule_id: str, account_id: str) -> dict[str, Any]:
    result = graph.request(
        "GET", f"/me/mailFolders/inbox/messageRules/{rule_id}", account_id
    )
    if not result:
        raise ValueError(f"Message rule with ID {rule_id} not found")
    return result


# emailrules_list
@mcp.tool(
    name="emailrules_list",
    annotations={
        "title": "List Email Rules",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
    meta={"category": "emailrules", "safety_level": "safe"},
)
def emailrules_list(account_id: str) -> list[dict[str, Any]]:
    """📖 List all inbox message rules (read-only, safe for unsupervised use)

    Message rules automatically process incoming emails based on conditions.
    Rules are executed in sequence order (1, 2, 3...).

    Args:
        account_id: Microsoft account ID

    Returns:
        List of rules with: id, displayName, sequence, isEnabled, conditions, actions
    """
    return _emailrules_list_impl(account_id)


# emailrules_get
@mcp.tool(
    name="emailrules_get",
    annotations={
        "title": "Get Email Rule",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
    meta={"category": "emailrules", "safety_level": "safe"},
)
def emailrules_get(rule_id: str, account_id: str) -> dict[str, Any]:
    """📖 Get details of a specific message rule (read-only, safe for unsupervised use)

    Returns complete rule configuration including conditions, actions, and execution order.

    Args:
        rule_id: The message rule ID
        account_id: Microsoft account ID

    Returns:
        Rule details including conditions, actions, sequence, and enabled status
    """
    return _emailrules_get_impl(rule_id, account_id)


# emailrules_create
@mcp.tool(
    name="emailrules_create",
    annotations={
        "title": "Create Email Rule",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
    meta={"category": "emailrules", "safety_level": "moderate"},
)
def emailrules_create(
    account_id: str,
    display_name: str,
    conditions: dict[str, Any],
    actions: dict[str, Any],
    sequence: int = 1,
    is_enabled: bool = True,
    exceptions: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """✏️ Create a new inbox message rule to automatically process emails (requires user confirmation recommended)

    Rules are executed in priority order (sequence number).

    Conditions examples:
        {"fromAddresses": [{"address": "john@example.com"}]}
        {"subjectContains": ["urgent", "important"]}
        {"senderContains": ["@company.com"]}
        {"hasAttachments": true}

    Actions examples:
        {"moveToFolder": "folder_id"}
        {"markAsRead": true}
        {"forwardTo": [{"emailAddress": {"address": "manager@example.com"}}]}
        {"assignCategories": ["Red category"]}
        {"delete": true}

    Args:
        account_id: Microsoft account ID
        display_name: Name for the rule (e.g., "Move work emails to Projects")
        conditions: Conditions that trigger the rule
        actions: Actions to perform when conditions match
        sequence: Rule execution order (lower numbers execute first, default: 1)
        is_enabled: Whether the rule is active (default: True)
        exceptions: Optional conditions that prevent rule execution

    Returns:
        Created rule with its ID and full configuration
    """
    rule_data = {
        "displayName": display_name,
        "sequence": sequence,
        "isEnabled": is_enabled,
        "conditions": conditions,
        "actions": actions,
    }

    if exceptions:
        rule_data["exceptions"] = exceptions

    result = graph.request(
        "POST", "/me/mailFolders/inbox/messageRules", account_id, json=rule_data
    )
    if not result:
        raise ValueError("Failed to create message rule")
    return result


# emailrules_update
@mcp.tool(
    name="emailrules_update",
    annotations={
        "title": "Update Email Rule",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
    meta={"category": "emailrules", "safety_level": "moderate"},
)
def emailrules_update(
    rule_id: str,
    account_id: str,
    display_name: str | None = None,
    conditions: dict[str, Any] | None = None,
    actions: dict[str, Any] | None = None,
    sequence: int | None = None,
    is_enabled: bool | None = None,
    exceptions: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """✏️ Update an existing message rule (requires user confirmation recommended)

    Modifies rule properties, conditions, actions, or execution order.
    At least one field must be provided to update.

    Allowed parameters: display_name, conditions, actions, sequence,
    is_enabled, exceptions.

    Args:
        rule_id: The message rule ID to update
        account_id: Microsoft account ID
        display_name: New name for the rule (optional)
        conditions: New conditions (optional)
        actions: New actions (optional)
        sequence: New execution order (optional)
        is_enabled: Enable or disable the rule (optional)
        exceptions: New exception conditions (optional)

    Returns:
        Updated rule configuration
    """
    updates: dict[str, Any] = {}

    if display_name is not None:
        if not isinstance(display_name, str):
            raise ValidationError(
                format_validation_error(
                    "display_name",
                    display_name,
                    "must be a string",
                    "Rule display name",
                )
            )
        trimmed = display_name.strip()
        if not trimmed:
            raise ValidationError(
                format_validation_error(
                    "display_name",
                    display_name,
                    "cannot be empty",
                    "Non-empty rule name",
                )
            )
        updates["displayName"] = trimmed

    if conditions is not None:
        updates["conditions"] = _validate_rule_predicates(conditions, "conditions")

    if actions is not None:
        updates["actions"] = _validate_rule_actions(actions, "actions")

    if sequence is not None:
        if not isinstance(sequence, int):
            raise ValidationError(
                format_validation_error(
                    "sequence",
                    sequence,
                    "must be an integer",
                    "Integer value ≥ 1",
                )
            )
        if sequence < 1:
            raise ValidationError(
                format_validation_error(
                    "sequence",
                    sequence,
                    "must be at least 1",
                    "Integer value ≥ 1",
                )
            )
        updates["sequence"] = sequence

    if is_enabled is not None:
        updates["isEnabled"] = _validate_bool(is_enabled, "is_enabled")

    if exceptions is not None:
        updates["exceptions"] = _validate_rule_predicates(exceptions, "exceptions")

    if not updates:
        raise ValidationError(
            format_validation_error(
                "updates",
                {},
                "must include at least one update field",
                "Provide one or more allowed parameters",
            )
        )

    result = graph.request(
        "PATCH",
        f"/me/mailFolders/inbox/messageRules/{rule_id}",
        account_id,
        json=updates,
    )
    if not result:
        raise ValueError(f"Failed to update message rule {rule_id}")
    return result


# emailrules_delete
@mcp.tool(
    name="emailrules_delete",
    annotations={
        "title": "Delete Email Rule",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
        "openWorldHint": True,
    },
    meta={
        "category": "emailrules",
        "safety_level": "critical",
        "requires_confirmation": True,
    },
)
def emailrules_delete(
    rule_id: str, account_id: str, confirm: bool = False
) -> dict[str, str]:
    """🔴 Delete a message rule permanently (always require user confirmation)

    WARNING: This action permanently deletes the rule and cannot be undone.
    Emails will no longer be automatically processed by this rule.

    Args:
        rule_id: The message rule ID to delete
        account_id: Microsoft account ID
        confirm: Must be True to confirm deletion (prevents accidents)

    Returns:
        Status confirmation
    """
    require_confirm(confirm, "delete email rule")
    graph.request("DELETE", f"/me/mailFolders/inbox/messageRules/{rule_id}", account_id)
    return {"status": "deleted", "rule_id": rule_id}


# emailrules_move_top
@mcp.tool(
    name="emailrules_move_top",
    annotations={
        "title": "Move Email Rule to Top",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
    meta={"category": "emailrules", "safety_level": "moderate"},
)
def emailrules_move_top(rule_id: str, account_id: str) -> dict[str, Any]:
    """✏️ Move a message rule to the top of execution order (requires user confirmation recommended)

    Rules execute in sequence order. Moving to top means it runs before all other rules.
    Sets the rule's sequence number to 1.

    Args:
        rule_id: The message rule ID to move
        account_id: Microsoft account ID

    Returns:
        Updated rule with new sequence number
    """
    result = graph.request(
        "PATCH",
        f"/me/mailFolders/inbox/messageRules/{rule_id}",
        account_id,
        json={"sequence": 1},
    )
    if not result:
        raise ValueError(f"Failed to move rule {rule_id} to top")
    return result


# emailrules_move_bottom
@mcp.tool(
    name="emailrules_move_bottom",
    annotations={
        "title": "Move Email Rule to Bottom",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
    meta={"category": "emailrules", "safety_level": "moderate"},
)
def emailrules_move_bottom(rule_id: str, account_id: str) -> dict[str, Any]:
    """✏️ Move a message rule to the bottom of execution order (requires user confirmation recommended)

    Rules execute in sequence order. Moving to bottom means it runs after all other rules.

    Args:
        rule_id: The message rule ID to move
        account_id: Microsoft account ID

    Returns:
        Updated rule with new sequence number
    """
    # Get all rules to find the highest sequence number
    all_rules = _emailrules_list_impl(account_id)
    if not all_rules:
        raise ValueError("No rules found")

    max_sequence = max(rule.get("sequence", 1) for rule in all_rules)
    new_sequence = max_sequence + 1

    result = graph.request(
        "PATCH",
        f"/me/mailFolders/inbox/messageRules/{rule_id}",
        account_id,
        json={"sequence": new_sequence},
    )
    if not result:
        raise ValueError(f"Failed to move rule {rule_id} to bottom")
    return result


# emailrules_move_up
@mcp.tool(
    name="emailrules_move_up",
    annotations={
        "title": "Move Email Rule Up",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
    meta={"category": "emailrules", "safety_level": "moderate"},
)
def emailrules_move_up(rule_id: str, account_id: str) -> dict[str, Any]:
    """✏️ Move a message rule up one position in execution order (requires user confirmation recommended)

    Increases the rule's priority by moving it one position higher in the
    execution order. Rules at the top (sequence = 1) cannot be moved up.

    Args:
        rule_id: The message rule ID to move
        account_id: Microsoft account ID

    Returns:
        Updated rule with new sequence number
    """
    # Get current rule
    current_rule = _emailrules_get_impl(rule_id, account_id)
    current_sequence = current_rule.get("sequence", 1)

    if current_sequence <= 1:
        raise ValueError("Rule is already at the top (sequence = 1)")

    new_sequence = current_sequence - 1

    result = graph.request(
        "PATCH",
        f"/me/mailFolders/inbox/messageRules/{rule_id}",
        account_id,
        json={"sequence": new_sequence},
    )
    if not result:
        raise ValueError(f"Failed to move rule {rule_id} up")
    return result


# emailrules_move_down
@mcp.tool(
    name="emailrules_move_down",
    annotations={
        "title": "Move Email Rule Down",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
    meta={"category": "emailrules", "safety_level": "moderate"},
)
def emailrules_move_down(rule_id: str, account_id: str) -> dict[str, Any]:
    """✏️ Move a message rule down one position in execution order (requires user confirmation recommended)

    Decreases the rule's priority by moving it one position lower in the
    execution order. Rules at the bottom cannot be moved down further.

    Args:
        rule_id: The message rule ID to move
        account_id: Microsoft account ID

    Returns:
        Updated rule with new sequence number
    """
    # Get current rule
    current_rule = _emailrules_get_impl(rule_id, account_id)
    current_sequence = current_rule.get("sequence", 1)

    new_sequence = current_sequence + 1

    result = graph.request(
        "PATCH",
        f"/me/mailFolders/inbox/messageRules/{rule_id}",
        account_id,
        json={"sequence": new_sequence},
    )
    if not result:
        raise ValueError(f"Failed to move rule {rule_id} down")
    return result
