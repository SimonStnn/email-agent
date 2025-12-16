"""Unit tests for account type detection module."""

import pytest
import jwt
from src.m365_mcp.account_type import (
    detect_account_type,
    _decode_token_unverified,
    _check_upn_domain,
)


class TestDetectAccountType:
    """Tests for the main detect_account_type function."""

    def test_detect_personal_account_jwt(self):
        """Test detection of personal account via JWT token issuer."""
        # Create a mock token with personal account issuer
        token = jwt.encode(
            {
                "iss": "https://login.microsoftonline.com/9188040d-6c67-4c5b-b112-36a304b66dad/v2.0",
                "sub": "test-user",
            },
            "secret",
            algorithm="HS256",
        )

        user_info = {"userPrincipalName": "user@outlook.com"}

        result = detect_account_type(token, user_info)

        assert result == "personal"

    def test_detect_work_school_account_jwt(self):
        """Test detection of work/school account via JWT token issuer."""
        # Create a mock token with tenant-specific issuer
        token = jwt.encode(
            {
                "iss": "https://login.microsoftonline.com/12345678-1234-1234-1234-123456789abc/v2.0",
                "sub": "test-user",
            },
            "secret",
            algorithm="HS256",
        )

        user_info = {"userPrincipalName": "user@contoso.com"}

        result = detect_account_type(token, user_info)

        assert result == "work_school"

    def test_detect_personal_account_domain_fallback(self):
        """Test fallback detection of personal account via domain."""
        # Use an invalid token that will fail JWT decoding
        invalid_token = "invalid.token.here"

        user_info = {"userPrincipalName": "user@outlook.com"}

        result = detect_account_type(invalid_token, user_info)

        assert result == "personal"

    def test_detect_work_school_account_domain_fallback(self):
        """Test fallback detection of work/school account via domain."""
        # Use an invalid token that will fail JWT decoding
        invalid_token = "invalid.token.here"

        user_info = {"userPrincipalName": "user@contoso.com"}

        result = detect_account_type(invalid_token, user_info)

        assert result == "work_school"

    def test_detect_account_type_failure(self):
        """Test that ValueError is raised when detection fails."""
        # Use an invalid token and no userPrincipalName
        invalid_token = "invalid.token.here"

        user_info = {}  # No userPrincipalName

        with pytest.raises(ValueError) as exc_info:
            detect_account_type(invalid_token, user_info)

        assert "Unable to determine account type" in str(exc_info.value)


class TestDecodeTokenUnverified:
    """Tests for JWT token decoding helper."""

    def test_decode_personal_account_token(self):
        """Test decoding token with personal account issuer."""
        token = jwt.encode(
            {
                "iss": "https://login.microsoftonline.com/9188040d-6c67-4c5b-b112-36a304b66dad/v2.0",
                "sub": "test-user",
            },
            "secret",
            algorithm="HS256",
        )

        result = _decode_token_unverified(token)

        assert result == "personal"

    def test_decode_work_school_account_token(self):
        """Test decoding token with tenant-specific issuer."""
        token = jwt.encode(
            {
                "iss": "https://login.microsoftonline.com/12345678-1234-1234-1234-123456789abc/v2.0",
                "sub": "test-user",
            },
            "secret",
            algorithm="HS256",
        )

        result = _decode_token_unverified(token)

        assert result == "work_school"

    def test_decode_invalid_token(self):
        """Test that invalid tokens raise exception."""
        invalid_token = "completely.invalid.token"

        with pytest.raises(jwt.DecodeError):
            _decode_token_unverified(invalid_token)

    def test_decode_token_unknown_issuer(self):
        """Test that unknown issuer returns None."""
        token = jwt.encode(
            {"iss": "https://unknown-issuer.com/v2.0", "sub": "test-user"},
            "secret",
            algorithm="HS256",
        )

        result = _decode_token_unverified(token)

        assert result is None


class TestCheckUpnDomain:
    """Tests for UPN domain checking helper."""

    def test_outlook_com_domain(self):
        """Test detection of outlook.com as personal."""
        result = _check_upn_domain("user@outlook.com")
        assert result == "personal"

    def test_hotmail_com_domain(self):
        """Test detection of hotmail.com as personal."""
        result = _check_upn_domain("user@hotmail.com")
        assert result == "personal"

    def test_live_com_domain(self):
        """Test detection of live.com as personal."""
        result = _check_upn_domain("user@live.com")
        assert result == "personal"

    def test_msn_com_domain(self):
        """Test detection of msn.com as personal."""
        result = _check_upn_domain("user@msn.com")
        assert result == "personal"

    def test_custom_domain_work_school(self):
        """Test detection of custom domain as work/school."""
        result = _check_upn_domain("user@contoso.com")
        assert result == "work_school"

    def test_subdomain_outlook(self):
        """Test handling of subdomains (e.g., mail.outlook.com)."""
        result = _check_upn_domain("user@mail.outlook.com")
        assert result == "personal"

    def test_case_insensitive(self):
        """Test that domain checking is case-insensitive."""
        result = _check_upn_domain("user@OUTLOOK.COM")
        assert result == "personal"

    def test_invalid_upn_no_at(self):
        """Test that UPN without @ returns None."""
        result = _check_upn_domain("invalidupn")
        assert result is None

    def test_empty_upn(self):
        """Test that empty UPN returns None."""
        result = _check_upn_domain("")
        assert result is None

    def test_none_upn(self):
        """Test that None UPN returns None."""
        result = _check_upn_domain(None)
        assert result is None
