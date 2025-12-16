"""Unit tests for user email fallback functionality."""

import pytest
from unittest.mock import patch
from src.m365_mcp.tools.calendar import _get_user_email_with_fallback


class TestGetUserEmailWithFallback:
    """Tests for the email fallback helper function."""

    @patch("src.m365_mcp.tools.calendar.graph")
    def test_mail_field_present(self, mock_graph):
        """Test that mail field is used when present."""
        mock_graph.request.return_value = {
            "mail": "user@example.com",
            "userPrincipalName": "user@contoso.com",
            "otherMails": ["other@example.com"],
        }

        result = _get_user_email_with_fallback("test-account-id")

        assert result == "user@example.com"
        mock_graph.request.assert_called_once_with(
            "GET", "/me?$select=mail,userPrincipalName,otherMails", "test-account-id"
        )

    @patch("src.m365_mcp.tools.calendar.graph")
    def test_fallback_to_upn(self, mock_graph):
        """Test fallback to userPrincipalName when mail is None."""
        mock_graph.request.return_value = {
            "mail": None,
            "userPrincipalName": "user@contoso.com",
            "otherMails": ["other@example.com"],
        }

        result = _get_user_email_with_fallback("test-account-id")

        assert result == "user@contoso.com"

    @patch("src.m365_mcp.tools.calendar.graph")
    def test_fallback_to_upn_mail_empty_string(self, mock_graph):
        """Test fallback to userPrincipalName when mail is empty string."""
        mock_graph.request.return_value = {
            "mail": "",
            "userPrincipalName": "user@contoso.com",
            "otherMails": [],
        }

        result = _get_user_email_with_fallback("test-account-id")

        assert result == "user@contoso.com"

    @patch("src.m365_mcp.tools.calendar.graph")
    def test_fallback_to_upn_mail_whitespace(self, mock_graph):
        """Test fallback to userPrincipalName when mail is whitespace."""
        mock_graph.request.return_value = {
            "mail": "   ",
            "userPrincipalName": "user@contoso.com",
            "otherMails": [],
        }

        result = _get_user_email_with_fallback("test-account-id")

        assert result == "user@contoso.com"

    @patch("src.m365_mcp.tools.calendar.graph")
    def test_fallback_to_other_mails(self, mock_graph):
        """Test fallback to first item in otherMails array."""
        mock_graph.request.return_value = {
            "mail": None,
            "userPrincipalName": None,
            "otherMails": ["first@example.com", "second@example.com"],
        }

        result = _get_user_email_with_fallback("test-account-id")

        assert result == "first@example.com"

    @patch("src.m365_mcp.tools.calendar.graph")
    def test_fallback_to_other_mails_upn_empty(self, mock_graph):
        """Test fallback to otherMails when UPN is empty string."""
        mock_graph.request.return_value = {
            "mail": None,
            "userPrincipalName": "",
            "otherMails": ["other@example.com"],
        }

        result = _get_user_email_with_fallback("test-account-id")

        assert result == "other@example.com"

    @patch("src.m365_mcp.tools.calendar.graph")
    def test_no_email_found_raises_error(self, mock_graph):
        """Test that ValueError is raised when no email is found."""
        mock_graph.request.return_value = {
            "mail": None,
            "userPrincipalName": None,
            "otherMails": [],
        }

        with pytest.raises(ValueError) as exc_info:
            _get_user_email_with_fallback("test-account-id")

        assert "Unable to determine user email address" in str(exc_info.value)

    @patch("src.m365_mcp.tools.calendar.graph")
    def test_no_email_fields_raises_error(self, mock_graph):
        """Test that ValueError is raised when no email fields present."""
        # Empty dict evaluates to False, caught by initial check
        mock_graph.request.return_value = {}

        with pytest.raises(ValueError) as exc_info:
            _get_user_email_with_fallback("test-account-id")

        # Empty dict triggers the first check (not user_info)
        assert "Failed to retrieve user profile information" in str(exc_info.value)

    @patch("src.m365_mcp.tools.calendar.graph")
    def test_other_mails_empty_array_raises_error(self, mock_graph):
        """Test that ValueError is raised when otherMails is empty."""
        mock_graph.request.return_value = {
            "mail": None,
            "userPrincipalName": None,
            "otherMails": [],
        }

        with pytest.raises(ValueError) as exc_info:
            _get_user_email_with_fallback("test-account-id")

        assert "Unable to determine user email address" in str(exc_info.value)

    @patch("src.m365_mcp.tools.calendar.graph")
    def test_other_mails_none_raises_error(self, mock_graph):
        """Test that ValueError is raised when otherMails is None."""
        mock_graph.request.return_value = {
            "mail": None,
            "userPrincipalName": None,
            "otherMails": None,
        }

        with pytest.raises(ValueError) as exc_info:
            _get_user_email_with_fallback("test-account-id")

        assert "Unable to determine user email address" in str(exc_info.value)

    @patch("src.m365_mcp.tools.calendar.graph")
    def test_failed_to_retrieve_user_info(self, mock_graph):
        """Test that ValueError is raised when user info retrieval fails."""
        mock_graph.request.return_value = None

        with pytest.raises(ValueError) as exc_info:
            _get_user_email_with_fallback("test-account-id")

        assert "Failed to retrieve user profile information" in str(exc_info.value)

    @patch("src.m365_mcp.tools.calendar.graph")
    def test_mail_with_leading_trailing_whitespace(self, mock_graph):
        """Test that email is trimmed when it has whitespace."""
        mock_graph.request.return_value = {
            "mail": "  user@example.com  ",
            "userPrincipalName": "user@contoso.com",
        }

        result = _get_user_email_with_fallback("test-account-id")

        assert result == "user@example.com"

    @patch("src.m365_mcp.tools.calendar.graph")
    def test_upn_with_leading_trailing_whitespace(self, mock_graph):
        """Test that UPN is trimmed when it has whitespace."""
        mock_graph.request.return_value = {
            "mail": None,
            "userPrincipalName": "  user@contoso.com  ",
        }

        result = _get_user_email_with_fallback("test-account-id")

        assert result == "user@contoso.com"

    @patch("src.m365_mcp.tools.calendar.graph")
    def test_other_mails_with_whitespace(self, mock_graph):
        """Test that otherMails item is trimmed when it has whitespace."""
        mock_graph.request.return_value = {
            "mail": None,
            "userPrincipalName": None,
            "otherMails": ["  other@example.com  "],
        }

        result = _get_user_email_with_fallback("test-account-id")

        assert result == "other@example.com"

    @patch("src.m365_mcp.tools.calendar.graph")
    def test_other_mails_first_item_empty(self, mock_graph):
        """Test fallback skips empty first item in otherMails."""
        mock_graph.request.return_value = {
            "mail": None,
            "userPrincipalName": None,
            "otherMails": [""],
        }

        with pytest.raises(ValueError) as exc_info:
            _get_user_email_with_fallback("test-account-id")

        assert "Unable to determine user email address" in str(exc_info.value)

    @patch("src.m365_mcp.tools.calendar.graph")
    def test_other_mails_not_list(self, mock_graph):
        """Test handling when otherMails is not a list."""
        mock_graph.request.return_value = {
            "mail": None,
            "userPrincipalName": None,
            "otherMails": "not-a-list",
        }

        with pytest.raises(ValueError) as exc_info:
            _get_user_email_with_fallback("test-account-id")

        assert "Unable to determine user email address" in str(exc_info.value)

    @patch("src.m365_mcp.tools.calendar.graph")
    def test_mail_not_string(self, mock_graph):
        """Test fallback when mail is not a string."""
        mock_graph.request.return_value = {
            "mail": 123,  # Not a string
            "userPrincipalName": "user@contoso.com",
        }

        result = _get_user_email_with_fallback("test-account-id")

        assert result == "user@contoso.com"
