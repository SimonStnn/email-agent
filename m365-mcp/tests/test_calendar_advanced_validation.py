"""Unit tests for Phase 3 advanced calendar features validation.

Tests cover:
- calendar_propose_new_time: Propose new meeting time
- calendar_get_free_busy: Get free/busy times for attendees
"""

import pytest
from src.m365_mcp.tools import calendar as calendar_tools
from src.m365_mcp.validators import ValidationError


class TestCalendarProposeNewTime:
    """Tests for calendar_propose_new_time validation."""

    def test_propose_time_rejects_invalid_start_datetime(self):
        """calendar_propose_new_time should reject invalid start datetime."""
        with pytest.raises(ValidationError) as exc_info:
            calendar_tools.calendar_propose_new_time.fn(
                account_id="test",
                event_id="event123",
                proposed_start="not-a-date",
                proposed_end="2024-01-15T11:00:00+00:00",
            )
        assert "ISO-8601 datetime" in str(exc_info.value)

    def test_propose_time_rejects_invalid_end_datetime(self):
        """calendar_propose_new_time should reject invalid end datetime."""
        with pytest.raises(ValidationError) as exc_info:
            calendar_tools.calendar_propose_new_time.fn(
                account_id="test",
                event_id="event123",
                proposed_start="2024-01-15T10:00:00+00:00",
                proposed_end="invalid-date",
            )
        assert "ISO-8601 datetime" in str(exc_info.value)

    def test_propose_time_rejects_end_before_start(self):
        """calendar_propose_new_time should reject end time before start time."""
        with pytest.raises(ValidationError) as exc_info:
            calendar_tools.calendar_propose_new_time.fn(
                account_id="test",
                event_id="event123",
                proposed_start="2024-01-15T11:00:00+00:00",
                proposed_end="2024-01-15T10:00:00+00:00",
            )
        assert "earlier" in str(exc_info.value).lower() or "start < end" in str(exc_info.value).lower()


class TestCalendarGetFreeBusy:
    """Tests for calendar_get_free_busy validation."""

    def test_get_free_busy_requires_attendees(self):
        """calendar_get_free_busy should require at least one attendee."""
        with pytest.raises((ValidationError, ValueError)) as exc_info:
            calendar_tools.calendar_get_free_busy.fn(
                account_id="test",
                attendees=[],
                start="2024-01-15T10:00:00+00:00",
                end="2024-01-15T11:00:00+00:00",
            )
        # Should fail due to empty attendees list

    def test_get_free_busy_rejects_invalid_email(self):
        """calendar_get_free_busy should reject invalid email addresses."""
        with pytest.raises(ValidationError) as exc_info:
            calendar_tools.calendar_get_free_busy.fn(
                account_id="test",
                attendees="not-an-email",
                start="2024-01-15T10:00:00+00:00",
                end="2024-01-15T11:00:00+00:00",
            )
        assert "email format" in str(exc_info.value).lower()

    def test_get_free_busy_rejects_invalid_start_datetime(self):
        """calendar_get_free_busy should reject invalid start datetime."""
        with pytest.raises(ValidationError) as exc_info:
            calendar_tools.calendar_get_free_busy.fn(
                account_id="test",
                attendees="user@example.com",
                start="not-a-date",
                end="2024-01-15T11:00:00+00:00",
            )
        assert "ISO-8601 datetime" in str(exc_info.value)

    def test_get_free_busy_rejects_invalid_end_datetime(self):
        """calendar_get_free_busy should reject invalid end datetime."""
        with pytest.raises(ValidationError) as exc_info:
            calendar_tools.calendar_get_free_busy.fn(
                account_id="test",
                attendees="user@example.com",
                start="2024-01-15T10:00:00+00:00",
                end="invalid-date",
            )
        assert "ISO-8601 datetime" in str(exc_info.value)

    def test_get_free_busy_rejects_end_before_start(self):
        """calendar_get_free_busy should reject end time before start time."""
        with pytest.raises(ValidationError) as exc_info:
            calendar_tools.calendar_get_free_busy.fn(
                account_id="test",
                attendees="user@example.com",
                start="2024-01-15T11:00:00+00:00",
                end="2024-01-15T10:00:00+00:00",
            )
        assert "earlier" in str(exc_info.value).lower() or "start < end" in str(exc_info.value).lower()

    def test_get_free_busy_rejects_invalid_time_interval_too_small(self):
        """calendar_get_free_busy should reject time_interval < 5."""
        with pytest.raises(ValidationError) as exc_info:
            calendar_tools.calendar_get_free_busy.fn(
                account_id="test",
                attendees="user@example.com",
                start="2024-01-15T10:00:00+00:00",
                end="2024-01-15T11:00:00+00:00",
                time_interval=3,
            )
        assert "must be between 5 and 1440 minutes" in str(exc_info.value)

    def test_get_free_busy_rejects_invalid_time_interval_too_large(self):
        """calendar_get_free_busy should reject time_interval > 1440."""
        with pytest.raises(ValidationError) as exc_info:
            calendar_tools.calendar_get_free_busy.fn(
                account_id="test",
                attendees="user@example.com",
                start="2024-01-15T10:00:00+00:00",
                end="2024-01-15T11:00:00+00:00",
                time_interval=2000,
            )
        assert "must be between 5 and 1440 minutes" in str(exc_info.value)

    def test_get_free_busy_accepts_multiple_attendees(self):
        """calendar_get_free_busy should accept multiple attendees."""
        # This test validates the function accepts the parameter format
        # Note: We can't actually run this without mocking as it makes API calls
        # Just verify that the validation logic handles multiple attendees correctly
        from src.m365_mcp.validators import normalize_recipients

        # Verify that multiple attendees can be normalized
        attendees = ["user1@example.com", "user2@example.com"]
        normalized = normalize_recipients(attendees, "attendees")
        assert len(normalized) == 2
        assert "user1@example.com" in normalized
        assert "user2@example.com" in normalized
