"""Unit tests for file sharing tool validation (Phase 2)."""

import pytest
from src.m365_mcp.tools import file as file_tools
from src.m365_mcp.validators import ValidationError


def test_file_share_invalid_file_id():
    """Test file_share with invalid file_id."""
    with pytest.raises(ValidationError) as exc_info:
        file_tools.file_share.fn("", "test-account", "view", "anonymous")
    assert "file_id" in str(exc_info.value).lower()


def test_file_share_invalid_permission_type():
    """Test file_share with invalid permission_type."""
    with pytest.raises(ValidationError) as exc_info:
        file_tools.file_share.fn("VALID123", "test-account", "invalid", "anonymous")
    assert "permission_type" in str(exc_info.value).lower()


def test_file_share_invalid_scope():
    """Test file_share with invalid scope."""
    with pytest.raises(ValidationError) as exc_info:
        file_tools.file_share.fn("VALID123", "test-account", "view", "invalid")
    assert "scope" in str(exc_info.value).lower()


def test_file_download_url_invalid_file_id():
    """Test file_download_url with invalid file_id."""
    with pytest.raises(ValidationError) as exc_info:
        file_tools.file_download_url.fn("", "test-account")
    assert "file_id" in str(exc_info.value).lower()
