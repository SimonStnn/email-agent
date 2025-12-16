"""Unit tests for Phase 3 calendar multiple calendars support tools validation.

Tests cover:
- calendar_list_calendars: List all calendars
- calendar_create_calendar: Create new calendar
- calendar_delete_calendar: Delete calendar (requires confirm)
"""

import pytest
from src.m365_mcp.tools import calendar as calendar_tools
from src.m365_mcp.validators import ValidationError


class TestCalendarCreateCalendar:
    """Tests for calendar_create_calendar validation."""

    def test_create_calendar_requires_string_name(self):
        """calendar_create_calendar should reject non-string names."""
        with pytest.raises(ValidationError) as exc_info:
            calendar_tools.calendar_create_calendar.fn(account_id="test", name=123)  # type: ignore
        assert "must be a string" in str(exc_info.value)

    def test_create_calendar_rejects_empty_name(self):
        """calendar_create_calendar should reject empty names."""
        with pytest.raises(ValidationError) as exc_info:
            calendar_tools.calendar_create_calendar.fn(account_id="test", name="")
        assert "cannot be empty" in str(exc_info.value)

    def test_create_calendar_rejects_whitespace_only_name(self):
        """calendar_create_calendar should reject whitespace-only names."""
        with pytest.raises(ValidationError) as exc_info:
            calendar_tools.calendar_create_calendar.fn(account_id="test", name="   ")
        assert "cannot be empty" in str(exc_info.value)


class TestCalendarDeleteCalendar:
    """Tests for calendar_delete_calendar validation."""

    def test_delete_calendar_requires_confirm_true(self):
        """calendar_delete_calendar should require confirm=True."""
        with pytest.raises(ValidationError) as exc_info:
            calendar_tools.calendar_delete_calendar.fn(
                account_id="test",
                calendar_id="cal123",
                confirm=False,
            )
        assert "confirm=True" in str(exc_info.value)

    def test_delete_calendar_requires_confirm_explicit(self):
        """calendar_delete_calendar should require explicit confirm parameter."""
        with pytest.raises(ValidationError) as exc_info:
            calendar_tools.calendar_delete_calendar.fn(
                account_id="test",
                calendar_id="cal123",
            )
        assert "confirm=True" in str(exc_info.value)
