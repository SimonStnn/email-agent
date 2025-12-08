"""Shared parameter validation helpers for Microsoft MCP tools."""

from __future__ import annotations

import logging
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Collection, Iterable, Sequence
from urllib.parse import urljoin, urlparse

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

LOGGER = logging.getLogger("microsoft_mcp.validators")

EMAIL_PATTERN = re.compile(
    r"^(?P<local>[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+)"
    r"@(?P<domain>[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*)$"
)

GRAPH_ALLOWED_HOSTS = {
    "graph.microsoft.com",
    "graph.microsoft.us",
    "graph.microsoft.de",
    "microsoftgraph.chinacloudapi.cn",
}

GRAPH_ALLOWED_SUFFIXES = (
    ".sharepoint.com",
    ".sharepoint-df.com",
    ".sharepoint-us.com",
    ".onmicrosoft.com",
    ".1drv.com",
    ".onedrive.live.com",
    ".storage.live.com",
    ".microsoftpersonalcontent.com",
)

WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}

DEFAULT_ALLOWED_ROOTS: tuple[Path, ...] = (
    Path.cwd().resolve(),
    Path(tempfile.gettempdir()).resolve(),
)


class ValidationError(ValueError):
    """Raised when parameter validation fails."""


def _mask_value(value: Any) -> str:
    """Return a sanitised representation of a potentially sensitive value."""
    if value is None:
        return "None"

    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return ""

        email_match = EMAIL_PATTERN.match(stripped)
        if email_match:
            local = email_match.group("local")
            domain = email_match.group("domain")
            if len(local) <= 1:
                masked_local = "*"
            elif len(local) == 2:
                masked_local = local[0] + "*"
            else:
                masked_local = local[0] + "***" + local[-1]
            return f"{masked_local}@{domain}"

        if len(stripped) > 64:
            return f"{stripped[:32]}…{stripped[-8:]}"

        return stripped

    return str(value)


def format_validation_error(
    param: str,
    value: Any,
    reason: str,
    expected: str,
) -> str:
    """Format the canonical validation error message."""
    masked = _mask_value(value)
    return f"Invalid {param} '{masked}': {reason}. Expected: {expected}"


def _log_failure(param: str, reason: str, value: Any) -> None:
    """Log validation failure without exposing sensitive data."""
    LOGGER.warning(
        "Validation failed",
        extra={
            "param": param,
            "reason": reason,
            "value": _mask_value(value),
        },
    )


def validate_account_id(account_id: str, param_name: str = "account_id") -> str:
    """Ensure account identifiers are present and well formed."""
    if not isinstance(account_id, str):
        reason = "must be a string"
        _log_failure(param_name, reason, account_id)
        raise ValidationError(
            format_validation_error(param_name, account_id, reason, "non-empty string")
        )

    trimmed = account_id.strip()
    if not trimmed:
        reason = "cannot be empty"
        _log_failure(param_name, reason, account_id)
        raise ValidationError(
            format_validation_error(param_name, account_id, reason, "non-empty string")
        )

    return trimmed


def validate_confirmation_flag(
    confirm: bool | None,
    operation: str,
    resource_type: str,
    param_name: str = "confirm",
) -> bool:
    """Ensure destructive operations require explicit confirmation."""
    if confirm is not True:
        reason = f"{operation} on {resource_type} requires confirm=True to proceed"
        _log_failure(param_name, reason, confirm)
        raise ValidationError(
            format_validation_error(
                param_name,
                confirm,
                reason,
                "Explicit user confirmation",
            )
        )
    return True


def require_confirm(confirm: bool, action: str, param_name: str = "confirm") -> None:
    """Backward compatible confirmation guard."""
    validate_confirmation_flag(confirm, action, "resource", param_name)


def validate_positive_int(value: Any, name: str) -> int:
    """Return a positive integer or raise ValidationError."""
    if not isinstance(value, int):
        reason = "must be an integer"
        _log_failure(name, reason, value)
        raise ValidationError(
            format_validation_error(name, value, reason, "Positive integer")
        )
    if value <= 0:
        reason = "must be greater than zero"
        _log_failure(name, reason, value)
        raise ValidationError(
            format_validation_error(name, value, reason, "Positive integer (> 0)")
        )
    return value


def validate_limit(
    limit: Any,
    minimum: int,
    maximum: int,
    param_name: str = "limit",
) -> int:
    """Validate pagination or item limits."""
    if not isinstance(limit, int):
        reason = "must be an integer"
        _log_failure(param_name, reason, limit)
        raise ValidationError(
            format_validation_error(param_name, limit, reason, f"{minimum}-{maximum}")
        )
    if limit < minimum or limit > maximum:
        reason = f"must be between {minimum} and {maximum}"
        _log_failure(param_name, reason, limit)
        raise ValidationError(
            format_validation_error(param_name, limit, reason, f"{minimum}-{maximum}")
        )
    return limit


def validate_email_format(email: str, param_name: str = "email") -> str:
    """Validate email address format and normalise casing."""
    if not isinstance(email, str):
        reason = "must be a string"
        _log_failure(param_name, reason, email)
        raise ValidationError(
            format_validation_error(param_name, email, reason, "Valid email address")
        )
    trimmed = email.strip()
    match = EMAIL_PATTERN.match(trimmed)
    if not match:
        reason = "does not match email format"
        _log_failure(param_name, reason, email)
        raise ValidationError(
            format_validation_error(
                param_name, email, reason, "name@example.com pattern"
            )
        )
    return trimmed.lower()


def normalize_recipients(
    recipients: str | Sequence[str] | None,
    param_name: str = "recipients",
) -> list[str]:
    """Normalise recipient inputs to a list of validated email addresses."""
    if recipients is None:
        return []
    values: Iterable[str]
    if isinstance(recipients, str):
        values = [part.strip() for part in recipients.split(",")]
    else:
        values = recipients

    normalised: list[str] = []
    for raw in values:
        if not raw:
            continue
        normalised.append(validate_email_format(raw, param_name))

    if not normalised:
        reason = "must include at least one valid email"
        _log_failure(param_name, reason, recipients)
        raise ValidationError(
            format_validation_error(
                param_name,
                recipients,
                reason,
                "Non-empty recipient list",
            )
        )
    return normalised


def validate_choices(
    value: str,
    allowed: Collection[str],
    param_name: str = "value",
) -> str:
    """Validate that a string value is within an allowed set (case-insensitive)."""
    if not isinstance(value, str):
        reason = "must be a string"
        _log_failure(param_name, reason, value)
        raise ValidationError(
            format_validation_error(
                param_name, value, reason, f"One of {sorted(allowed)}"
            )
        )

    trimmed = value.strip()
    if not trimmed:
        reason = "cannot be empty"
        _log_failure(param_name, reason, value)
        raise ValidationError(
            format_validation_error(
                param_name, value, reason, f"One of {sorted(allowed)}"
            )
        )

    allowed_map = {item.casefold(): item for item in allowed}
    matched = allowed_map.get(trimmed.casefold())
    if matched is None:
        reason = "not in allowed set"
        _log_failure(param_name, reason, value)
        raise ValidationError(
            format_validation_error(
                param_name, value, reason, f"One of {sorted(allowed)}"
            )
        )
    return matched


def validate_iso_datetime(
    value: str,
    param_name: str,
    allow_date_only: bool = False,
) -> datetime:
    """Parse ISO-8601 datetimes ensuring timezone awareness."""
    if not isinstance(value, str):
        reason = "must be a string"
        _log_failure(param_name, reason, value)
        raise ValidationError(
            format_validation_error(param_name, value, reason, "ISO-8601 string")
        )

    trimmed = value.strip()
    if not trimmed:
        reason = "cannot be empty"
        _log_failure(param_name, reason, value)
        raise ValidationError(
            format_validation_error(param_name, value, reason, "ISO-8601 string")
        )

    try:
        parsed = datetime.fromisoformat(trimmed.replace("Z", "+00:00"))
    except ValueError as exc:
        reason = f"invalid ISO-8601 datetime ({exc})"
        _log_failure(param_name, reason, value)
        raise ValidationError(
            format_validation_error(param_name, value, reason, "YYYY-MM-DDTHH:MM:SS+TZ")
        ) from exc

    if parsed.tzinfo is None:
        if allow_date_only and len(trimmed) == 10:
            return parsed
        reason = "timezone information required"
        _log_failure(param_name, reason, value)
        raise ValidationError(
            format_validation_error(
                param_name, value, reason, "Timezone-aware datetime"
            )
        )

    return parsed


def validate_timezone(tz: str, param_name: str = "timezone") -> str:
    """Ensure timezone names resolve via zoneinfo."""
    if not isinstance(tz, str):
        reason = "must be a string"
        _log_failure(param_name, reason, tz)
        raise ValidationError(
            format_validation_error(param_name, tz, reason, "Valid IANA timezone name")
        )
    trimmed = tz.strip()
    if not trimmed:
        reason = "cannot be empty"
        _log_failure(param_name, reason, tz)
        raise ValidationError(
            format_validation_error(param_name, tz, reason, "Valid IANA timezone name")
        )
    try:
        ZoneInfo(trimmed)
    except ZoneInfoNotFoundError as exc:
        reason = "unknown timezone"
        _log_failure(param_name, reason, tz)
        raise ValidationError(
            format_validation_error(param_name, tz, reason, "Valid IANA timezone name")
        ) from exc
    return trimmed


def validate_datetime_window(
    start: str,
    end: str,
    *,
    allow_equal: bool = False,
) -> tuple[datetime, datetime]:
    """Validate a datetime range."""
    start_dt = validate_iso_datetime(start, "start")
    end_dt = validate_iso_datetime(end, "end")

    if allow_equal and start_dt == end_dt:
        return start_dt, end_dt

    if start_dt >= end_dt:
        reason = "start must be earlier than end"
        _log_failure("datetime_window", reason, f"{start_dt}->{end_dt}")
        raise ValidationError(
            format_validation_error(
                "datetime_window",
                f"{_mask_value(start)}→{_mask_value(end)}",
                reason,
                "start < end",
            )
        )
    return start_dt, end_dt


def validate_datetime_ordering(
    first: datetime,
    second: datetime,
    param_name: str = "datetime_order",
) -> None:
    """Ensure the first datetime is not after the second."""
    if first > second:
        reason = "first datetime must not be after second"
        _log_failure(param_name, reason, f"{first}->{second}")
        raise ValidationError(
            format_validation_error(
                param_name,
                f"{first.isoformat()}→{second.isoformat()}",
                reason,
                "First <= Second",
            )
        )


def validate_folder_choice(
    value: str,
    allowed: Sequence[str],
    param_name: str = "folder",
) -> str:
    """Validate folder selections against allowed list."""
    if not isinstance(value, str):
        reason = "must be a string"
        _log_failure(param_name, reason, value)
        raise ValidationError(
            format_validation_error(param_name, value, reason, f"One of {allowed}")
        )
    normalised = value.strip()
    allowed_lower = {item.lower(): item for item in allowed}
    if normalised.lower() not in allowed_lower:
        reason = "not in allowed set"
        _log_failure(param_name, reason, value)
        raise ValidationError(
            format_validation_error(
                param_name, value, reason, f"One of {sorted(allowed)}"
            )
        )
    return allowed_lower[normalised.lower()]


def validate_json_payload(
    payload: Any,
    *,
    required_keys: Sequence[str] | None = None,
    allowed_keys: Sequence[str] | None = None,
    param_name: str = "payload",
) -> dict[str, Any]:
    """Ensure payloads are JSON-like dictionaries with required/allowed keys."""
    if not isinstance(payload, dict):
        reason = "must be a JSON object"
        _log_failure(param_name, reason, payload)
        raise ValidationError(
            format_validation_error(param_name, payload, reason, "Dictionary value")
        )

    if required_keys:
        missing = [key for key in required_keys if key not in payload]
        if missing:
            reason = f"missing keys {missing}"
            _log_failure(param_name, reason, payload)
            raise ValidationError(
                format_validation_error(
                    param_name,
                    payload,
                    reason,
                    f"Include keys {sorted(required_keys)}",
                )
            )

    if allowed_keys is not None:
        allowed_set = set(allowed_keys)
        unknown = sorted(key for key in payload if key not in allowed_set)
        if unknown:
            reason = f"contains unsupported keys {unknown}"
            _log_failure(param_name, reason, payload)
            raise ValidationError(
                format_validation_error(
                    param_name,
                    payload,
                    reason,
                    f"Only keys {sorted(allowed_set)}",
                )
            )

    return payload


def validate_request_size(
    size_bytes: int,
    limit_bytes: int,
    param_name: str = "request_size",
) -> int:
    """Ensure request payloads stay within configured limits."""
    if not isinstance(size_bytes, int):
        reason = "must be integer number of bytes"
        _log_failure(param_name, reason, size_bytes)
        raise ValidationError(
            format_validation_error(
                param_name, size_bytes, reason, "Integer bytes value"
            )
        )
    if size_bytes < 0:
        reason = "cannot be negative"
        _log_failure(param_name, reason, size_bytes)
        raise ValidationError(
            format_validation_error(
                param_name, size_bytes, reason, "0 or positive integer"
            )
        )
    if size_bytes > limit_bytes:
        reason = f"exceeds limit of {limit_bytes} bytes"
        _log_failure(param_name, reason, size_bytes)
        raise ValidationError(
            format_validation_error(
                param_name,
                size_bytes,
                reason,
                f"<= {limit_bytes} bytes",
            )
        )
    return size_bytes


def validate_microsoft_graph_id(
    identifier: str,
    param_name: str = "identifier",
) -> str:
    """Validate Microsoft Graph resource identifiers.

    Microsoft Graph IDs are typically base64-encoded strings that may contain
    alphanumeric characters, plus signs, slashes, equals signs, hyphens,
    underscores, and other URL-safe characters.
    """
    if not isinstance(identifier, str):
        reason = "must be a string"
        _log_failure(param_name, reason, identifier)
        raise ValidationError(
            format_validation_error(
                param_name,
                identifier,
                reason,
                "Graph resource identifier string",
            )
        )
    trimmed = identifier.strip()
    if not trimmed:
        reason = "cannot be empty"
        _log_failure(param_name, reason, identifier)
        raise ValidationError(
            format_validation_error(param_name, identifier, reason, "Non-empty string")
        )
    # Allow base64 characters (A-Z, a-z, 0-9, +, /, =) and URL-safe variants (-, _)
    # Also allow common Graph ID characters like ! and .
    if not re.fullmatch(r"[A-Za-z0-9\-._!+=/$]{1,512}", trimmed):
        reason = "contains unsupported characters"
        _log_failure(param_name, reason, identifier)
        raise ValidationError(
            format_validation_error(
                param_name,
                identifier,
                reason,
                "Alphanumeric with - . _ ! + = / $",
            )
        )
    return trimmed


def validate_onedrive_path(
    onedrive_path: str,
    param_name: str = "onedrive_path",
) -> str:
    """Validate OneDrive path format."""
    if not isinstance(onedrive_path, str):
        reason = "must be a string"
        _log_failure(param_name, reason, onedrive_path)
        raise ValidationError(
            format_validation_error(
                param_name,
                onedrive_path,
                reason,
                "Path beginning with '/'",
            )
        )
    trimmed = onedrive_path.strip()
    if not trimmed.startswith("/"):
        reason = "must start with '/'"
        _log_failure(param_name, reason, onedrive_path)
        raise ValidationError(
            format_validation_error(
                param_name,
                onedrive_path,
                reason,
                "Absolute OneDrive path like '/Documents/file.txt'",
            )
        )
    parts = [part for part in trimmed.split("/") if part]
    invalid_chars = re.compile(r'[<>:"|?*]')
    for part in parts:
        if part == "..":
            reason = "parent directory segments are not allowed"
            _log_failure(param_name, reason, onedrive_path)
            raise ValidationError(
                format_validation_error(
                    param_name,
                    onedrive_path,
                    reason,
                    "Path without '..' segments",
                )
            )
        if invalid_chars.search(part):
            reason = "contains reserved characters"
            _log_failure(param_name, reason, onedrive_path)
            raise ValidationError(
                format_validation_error(
                    param_name,
                    onedrive_path,
                    reason,
                    'Path without < > : " | ? * characters',
                )
            )
        if os.name == "nt":
            upper = part.split(".")[0].upper()
            if upper in WINDOWS_RESERVED_NAMES:
                reason = "contains Windows reserved filename"
                _log_failure(param_name, reason, onedrive_path)
                raise ValidationError(
                    format_validation_error(
                        param_name,
                        onedrive_path,
                        reason,
                        "Path without reserved Windows names",
                    )
                )
    normalised = "/" + "/".join(parts)
    return normalised or "/"


def _resolve_allowed_roots(
    allowed_roots: Sequence[str | Path] | None,
) -> list[Path]:
    """Resolve allowed root directories."""
    roots: list[Path] = []
    if allowed_roots:
        for entry in allowed_roots:
            roots.append(Path(entry).expanduser().resolve())
    else:
        roots.extend(DEFAULT_ALLOWED_ROOTS)

    env_roots = os.getenv("MCP_FILE_ALLOWED_ROOTS")
    if env_roots:
        for part in env_roots.split(os.pathsep):
            if part:
                roots.append(Path(part).expanduser().resolve())
    return roots


def _is_subpath(candidate: Path, parent: Path) -> bool:
    """Return True if candidate resides within parent."""
    try:
        candidate.relative_to(parent)
        return True
    except ValueError:
        return False


def ensure_safe_path(
    path: str | Path,
    *,
    allow_overwrite: bool = False,
    must_exist: bool = False,
    allowed_roots: Sequence[str | Path] | None = None,
    param_name: str = "path",
) -> Path:
    """Validate local filesystem paths for safe read/write operations."""
    candidate = Path(path).expanduser()
    candidate_str = str(candidate)

    if os.name == "nt":
        if candidate_str.startswith("\\\\"):
            reason = "UNC paths are not allowed"
            _log_failure(param_name, reason, candidate_str)
            raise ValidationError(
                format_validation_error(
                    param_name,
                    candidate_str,
                    reason,
                    "Absolute path on local drive",
                )
            )

    resolved = candidate.resolve(strict=False)

    if ".." in candidate.parts:
        reason = "parent directory segments are not allowed"
        _log_failure(param_name, reason, candidate_str)
        raise ValidationError(
            format_validation_error(
                param_name,
                candidate_str,
                reason,
                "Path without '..' segments",
            )
        )

    roots = _resolve_allowed_roots(allowed_roots)
    if not any(_is_subpath(resolved, root) for root in roots):
        reason = "path escapes allowed directories"
        _log_failure(param_name, reason, candidate_str)
        raise ValidationError(
            format_validation_error(
                param_name,
                candidate_str,
                reason,
                f"Location inside {', '.join(str(r) for r in roots)}",
            )
        )

    if os.name == "nt":
        for part in resolved.parts:
            if part == resolved.drive:
                continue
            if ":" in part:
                reason = "alternate data streams are not allowed"
                _log_failure(param_name, reason, candidate_str)
                raise ValidationError(
                    format_validation_error(
                        param_name,
                        candidate_str,
                        reason,
                        "Filenames without ':' segments",
                    )
                )
            upper = part.split(".")[0].upper()
            if upper in WINDOWS_RESERVED_NAMES:
                reason = "contains Windows reserved filename"
                _log_failure(param_name, reason, candidate_str)
                raise ValidationError(
                    format_validation_error(
                        param_name,
                        candidate_str,
                        reason,
                        "No reserved Windows filenames",
                    )
                )

    if resolved.exists():
        if resolved.is_dir():
            reason = "expected file path but found directory"
            _log_failure(param_name, reason, candidate_str)
            raise ValidationError(
                format_validation_error(
                    param_name,
                    candidate_str,
                    reason,
                    "Existing file or new file path",
                )
            )
        if not allow_overwrite:
            reason = "would overwrite existing file"
            _log_failure(param_name, reason, candidate_str)
            raise ValidationError(
                format_validation_error(
                    param_name,
                    candidate_str,
                    reason,
                    "Unique file path",
                )
            )
    elif must_exist:
        reason = "path does not exist"
        _log_failure(param_name, reason, candidate_str)
        raise ValidationError(
            format_validation_error(
                param_name,
                candidate_str,
                reason,
                "Existing file path",
            )
        )

    parent = resolved.parent
    if not parent.exists():
        try:
            parent_relative = parent.relative_to(parent.anchor)
            if any(part == ".." for part in parent_relative.parts):
                reason = "parent directory traversal detected"
                _log_failure(param_name, reason, candidate_str)
                raise ValidationError(
                    format_validation_error(
                        param_name,
                        candidate_str,
                        reason,
                        "Valid parent directory",
                    )
                )
        except ValueError:
            pass

    if resolved.is_symlink():
        reason = "symlinks are not allowed"
        _log_failure(param_name, reason, candidate_str)
        raise ValidationError(
            format_validation_error(
                param_name,
                candidate_str,
                reason,
                "Regular file path",
            )
        )

    return resolved


def validate_graph_url(
    url: str,
    param_name: str = "url",
    *,
    allow_redirect: bool = False,
) -> str:
    """Validate download URLs returned by Microsoft Graph."""
    if not isinstance(url, str):
        reason = "must be a string"
        _log_failure(param_name, reason, url)
        raise ValidationError(
            format_validation_error(param_name, url, reason, "HTTPS URL")
        )

    trimmed = url.strip()
    if not trimmed:
        reason = "cannot be empty"
        _log_failure(param_name, reason, url)
        raise ValidationError(
            format_validation_error(param_name, url, reason, "HTTPS URL")
        )

    parsed = urlparse(trimmed)
    if parsed.scheme.lower() != "https":
        reason = "must use HTTPS"
        _log_failure(param_name, reason, url)
        raise ValidationError(
            format_validation_error(param_name, url, reason, "HTTPS URL")
        )

    host = parsed.hostname or ""
    host_lower = host.lower()
    allowed = host_lower in GRAPH_ALLOWED_HOSTS or any(
        host_lower.endswith(suffix) for suffix in GRAPH_ALLOWED_SUFFIXES
    )
    if not allowed:
        reason = "host is not an approved Microsoft domain"
        _log_failure(param_name, reason, host_lower)
        raise ValidationError(
            format_validation_error(
                param_name,
                url,
                reason,
                f"Host within {sorted(GRAPH_ALLOWED_HOSTS)} or "
                f"{GRAPH_ALLOWED_SUFFIXES}",
            )
        )

    if parsed.username or parsed.password:
        reason = "embedded credentials are not allowed"
        _log_failure(param_name, reason, url)
        raise ValidationError(
            format_validation_error(
                param_name,
                url,
                reason,
                "URL without credentials",
            )
        )

    if allow_redirect and parsed.path:
        trimmed = urljoin(trimmed, parsed.path)

    return trimmed


def validate_attachments(
    attachments: Sequence[str | Path] | str | None,
    *,
    max_inline_size_bytes: int = 3_145_728,
    max_attachments: int = 10,
    param_name: str = "attachments",
) -> list[Path]:
    """Validate attachment inputs for email tools."""
    if attachments is None:
        return []

    if isinstance(attachments, (str, Path)):
        values = [attachments]
    else:
        values = list(attachments)

    if not values:
        reason = "attachment list cannot be empty"
        _log_failure(param_name, reason, attachments)
        raise ValidationError(
            format_validation_error(
                param_name,
                attachments,
                reason,
                "Provide at least one attachment or None",
            )
        )

    if len(values) > max_attachments:
        reason = f"exceeds limit of {max_attachments} attachments"
        _log_failure(param_name, reason, len(values))
        raise ValidationError(
            format_validation_error(
                param_name,
                len(values),
                reason,
                f"<= {max_attachments} attachments",
            )
        )

    validated: list[Path] = []
    for item in values:
        path = ensure_safe_path(
            Path(item),
            allow_overwrite=True,
            must_exist=True,
            param_name=param_name,
        )
        size = path.stat().st_size
        validate_request_size(size, max_inline_size_bytes, f"{param_name}_size")
        validated.append(path)
    return validated
