"""Unit tests for calendar_forward_event validation (Phase 2)."""

import pytest
from src.m365_mcp.tools import calendar as calendar_tools
from src.m365_mcp.validators import ValidationError


def test_calendar_forward_event_missing_confirm():
    """Test calendar_forward_event without confirmation."""
    with pytest.raises(ValidationError) as exc_info:
        calendar_tools.calendar_forward_event.fn(
            "test-account", "EVENT123", "user@example.com", confirm=False
        )
    assert "confirm" in str(exc_info.value).lower()


def test_calendar_forward_event_invalid_recipient():
    """Test calendar_forward_event with invalid recipient."""
    with pytest.raises(ValidationError) as exc_info:
        calendar_tools.calendar_forward_event.fn(
            "test-account", "EVENT123", "invalid-email", confirm=True
        )
    assert "email" in str(exc_info.value).lower() or "recipient" in str(exc_info.value).lower()


def test_calendar_forward_event_too_many_recipients():
    """Test calendar_forward_event with too many recipients."""
    # Create 501 recipients to exceed limit
    recipients = [f"user{i}@example.com" for i in range(501)]

    with pytest.raises(ValidationError) as exc_info:
        calendar_tools.calendar_forward_event.fn(
            "test-account", "EVENT123", recipients, confirm=True
        )
    assert "500" in str(exc_info.value) or "recipient" in str(exc_info.value).lower()
