"""Unit tests for email quick actions validation (Phase 2)."""

import pytest
from src.m365_mcp.tools import email as email_tools
from src.m365_mcp.validators import ValidationError


def test_email_mark_read_invalid_email_id():
    """Test email_mark_read with invalid email_id."""
    with pytest.raises(ValidationError) as exc_info:
        email_tools.email_mark_read.fn("", "test-account", True)
    assert "email_id" in str(exc_info.value).lower()


def test_email_mark_read_invalid_is_read_type():
    """Test email_mark_read with non-boolean is_read."""
    with pytest.raises(ValidationError) as exc_info:
        email_tools.email_mark_read.fn("VALID123", "test-account", "yes")
    assert "is_read" in str(exc_info.value).lower()


def test_email_flag_invalid_email_id():
    """Test email_flag with invalid email_id."""
    with pytest.raises(ValidationError) as exc_info:
        email_tools.email_flag.fn("", "test-account", "flagged")
    assert "email_id" in str(exc_info.value).lower()


def test_email_flag_invalid_flag_status():
    """Test email_flag with invalid flag_status."""
    with pytest.raises(ValidationError) as exc_info:
        email_tools.email_flag.fn("VALID123", "test-account", "invalid")
    assert "flag_status" in str(exc_info.value).lower()


def test_email_add_category_invalid_email_id():
    """Test email_add_category with invalid email_id."""
    with pytest.raises(ValidationError) as exc_info:
        email_tools.email_add_category.fn("", "test-account", "Important")
    assert "email_id" in str(exc_info.value).lower()


def test_email_add_category_empty_category():
    """Test email_add_category with empty category."""
    with pytest.raises(ValidationError) as exc_info:
        email_tools.email_add_category.fn("VALID123", "test-account", "")
    assert "categor" in str(exc_info.value).lower()


def test_email_add_category_empty_list():
    """Test email_add_category with empty list."""
    with pytest.raises(ValidationError) as exc_info:
        email_tools.email_add_category.fn("VALID123", "test-account", [])
    assert "categor" in str(exc_info.value).lower()


def test_email_archive_invalid_email_id():
    """Test email_archive with invalid email_id."""
    with pytest.raises(ValidationError) as exc_info:
        email_tools.email_archive.fn("", "test-account")
    assert "email_id" in str(exc_info.value).lower()


def test_email_archive_invalid_account_id():
    """Test email_archive with invalid account_id."""
    with pytest.raises(ValidationError) as exc_info:
        email_tools.email_archive.fn("VALID123", "")
    assert "account_id" in str(exc_info.value).lower()
