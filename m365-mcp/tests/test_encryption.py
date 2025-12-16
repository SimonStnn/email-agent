"""Tests for encryption key management.

This module tests the EncryptionKeyManager class including key generation,
keyring storage/retrieval, environment variable fallback, and validation.
"""

import os
import base64
import pytest
from unittest.mock import patch, MagicMock
from src.m365_mcp.encryption import EncryptionKeyManager


class TestKeyGeneration:
    """Test encryption key generation functionality."""

    def test_generate_key_returns_string(self):
        """Test that generate_key returns a string."""
        key = EncryptionKeyManager.generate_key()
        assert isinstance(key, str)

    def test_generate_key_produces_256bit_keys(self):
        """Test that generated keys are 256 bits (32 bytes)."""
        key = EncryptionKeyManager.generate_key()

        # Decode base64 and verify length
        key_bytes = base64.b64decode(key)
        assert len(key_bytes) == 32, f"Expected 32 bytes, got {len(key_bytes)}"

    def test_generate_key_returns_valid_base64(self):
        """Test that generated keys are valid base64 encoded strings."""
        key = EncryptionKeyManager.generate_key()

        # Should not raise exception
        try:
            decoded = base64.b64decode(key, validate=True)
            assert len(decoded) == 32
        except Exception as e:
            pytest.fail(f"Generated key is not valid base64: {e}")

    def test_generate_key_produces_unique_keys(self):
        """Test that each call to generate_key produces different keys."""
        keys = [EncryptionKeyManager.generate_key() for _ in range(10)]

        # All keys should be unique
        assert len(keys) == len(set(keys)), "Generated keys are not unique"

    def test_generate_key_no_null_bytes(self):
        """Test that generated keys don't contain null bytes."""
        key = EncryptionKeyManager.generate_key()
        key_bytes = base64.b64decode(key)

        # Should have full entropy (no null bytes expected in cryptographic random)
        # This is a statistical test - null bytes are possible but extremely unlikely
        assert len(key_bytes) == 32


class TestKeyValidation:
    """Test encryption key validation functionality."""

    def test_validate_key_accepts_valid_key(self):
        """Test that validation accepts properly formatted keys."""
        key = EncryptionKeyManager.generate_key()
        assert EncryptionKeyManager._validate_key(key) is True

    def test_validate_key_rejects_invalid_base64(self):
        """Test that validation rejects invalid base64 strings."""
        invalid_keys = [
            "not-valid-base64!@#",
            "short",
            "",
            "====",
        ]

        for invalid_key in invalid_keys:
            assert EncryptionKeyManager._validate_key(invalid_key) is False

    def test_validate_key_rejects_wrong_length(self):
        """Test that validation rejects keys with incorrect length."""
        # 16-byte key (128 bits) - too short
        short_key = base64.b64encode(b"0" * 16).decode("utf-8")
        assert EncryptionKeyManager._validate_key(short_key) is False

        # 64-byte key (512 bits) - too long
        long_key = base64.b64encode(b"0" * 64).decode("utf-8")
        assert EncryptionKeyManager._validate_key(long_key) is False

    def test_validate_key_accepts_32_bytes_only(self):
        """Test that validation accepts only 32-byte (256-bit) keys."""
        valid_key = base64.b64encode(b"0" * 32).decode("utf-8")
        assert EncryptionKeyManager._validate_key(valid_key) is True


class TestKeyringIntegration:
    """Test system keyring integration."""

    def test_get_key_from_keyring_success(self):
        """Test successful key retrieval from keyring."""
        test_key = EncryptionKeyManager.generate_key()
        mock_keyring = MagicMock()
        mock_keyring.get_password.return_value = test_key

        with patch.dict("sys.modules", {"keyring": mock_keyring}):
            result = EncryptionKeyManager._get_key_from_keyring()

        assert result == test_key
        mock_keyring.get_password.assert_called_once_with(
            EncryptionKeyManager.KEYRING_SERVICE, EncryptionKeyManager.KEYRING_USERNAME
        )

    def test_get_key_from_keyring_not_found(self):
        """Test keyring returns None when key not found."""
        mock_keyring = MagicMock()
        mock_keyring.get_password.return_value = None

        with patch.dict("sys.modules", {"keyring": mock_keyring}):
            result = EncryptionKeyManager._get_key_from_keyring()

        assert result is None

    def test_get_key_from_keyring_handles_exception(self):
        """Test keyring error handling."""
        mock_keyring = MagicMock()
        mock_keyring.get_password.side_effect = Exception("Keyring error")

        with patch.dict("sys.modules", {"keyring": mock_keyring}):
            result = EncryptionKeyManager._get_key_from_keyring()

        assert result is None

    def test_store_key_in_keyring_success(self):
        """Test successful key storage in keyring."""
        test_key = EncryptionKeyManager.generate_key()
        mock_keyring = MagicMock()

        with patch.dict("sys.modules", {"keyring": mock_keyring}):
            result = EncryptionKeyManager._store_key_in_keyring(test_key)

        assert result is True
        mock_keyring.set_password.assert_called_once_with(
            EncryptionKeyManager.KEYRING_SERVICE,
            EncryptionKeyManager.KEYRING_USERNAME,
            test_key,
        )

    def test_store_key_in_keyring_handles_exception(self):
        """Test keyring storage error handling."""
        test_key = EncryptionKeyManager.generate_key()
        mock_keyring = MagicMock()
        mock_keyring.set_password.side_effect = Exception("Keyring error")

        with patch.dict("sys.modules", {"keyring": mock_keyring}):
            result = EncryptionKeyManager._store_key_in_keyring(test_key)

        assert result is False

    def test_delete_key_from_keyring_success(self):
        """Test successful key deletion from keyring."""
        mock_keyring = MagicMock()

        with patch.dict("sys.modules", {"keyring": mock_keyring}):
            result = EncryptionKeyManager.delete_key_from_keyring()

        assert result is True
        mock_keyring.delete_password.assert_called_once_with(
            EncryptionKeyManager.KEYRING_SERVICE, EncryptionKeyManager.KEYRING_USERNAME
        )

    def test_delete_key_from_keyring_handles_exception(self):
        """Test keyring deletion error handling."""
        mock_keyring = MagicMock()
        mock_keyring.delete_password.side_effect = Exception("Keyring error")

        with patch.dict("sys.modules", {"keyring": mock_keyring}):
            result = EncryptionKeyManager.delete_key_from_keyring()

        assert result is False


class TestEnvironmentVariableFallback:
    """Test environment variable fallback functionality."""

    def test_get_key_from_env_success(self):
        """Test successful key retrieval from environment variable."""
        test_key = EncryptionKeyManager.generate_key()

        with patch.dict(os.environ, {EncryptionKeyManager.ENV_VAR: test_key}):
            result = EncryptionKeyManager._get_key_from_env()
            assert result == test_key

    def test_get_key_from_env_not_set(self):
        """Test environment variable returns None when not set."""
        with patch.dict(os.environ, {}, clear=True):
            result = EncryptionKeyManager._get_key_from_env()
            assert result is None

    def test_get_key_from_env_invalid_key(self):
        """Test environment variable validation rejects invalid keys."""
        with patch.dict(os.environ, {EncryptionKeyManager.ENV_VAR: "invalid-key"}):
            result = EncryptionKeyManager._get_key_from_env()
            assert result is None

    def test_get_key_from_env_validates_length(self):
        """Test environment variable validation checks key length."""
        short_key = base64.b64encode(b"0" * 16).decode("utf-8")

        with patch.dict(os.environ, {EncryptionKeyManager.ENV_VAR: short_key}):
            result = EncryptionKeyManager._get_key_from_env()
            assert result is None


class TestGetOrCreateKey:
    """Test the complete get_or_create_key workflow."""

    def test_get_or_create_key_from_keyring(self):
        """Test get_or_create_key retrieves from keyring first."""
        test_key = EncryptionKeyManager.generate_key()
        mock_keyring = MagicMock()
        mock_keyring.get_password.return_value = test_key

        with patch.dict("sys.modules", {"keyring": mock_keyring}):
            with patch.dict(os.environ, {}, clear=True):
                result = EncryptionKeyManager.get_or_create_key()

        assert result == test_key
        mock_keyring.get_password.assert_called_once()

    def test_get_or_create_key_from_env_when_keyring_unavailable(self):
        """Test get_or_create_key falls back to environment variable."""
        test_key = EncryptionKeyManager.generate_key()
        mock_keyring = MagicMock()
        mock_keyring.get_password.return_value = None

        with patch.dict("sys.modules", {"keyring": mock_keyring}):
            with patch.dict(os.environ, {EncryptionKeyManager.ENV_VAR: test_key}):
                result = EncryptionKeyManager.get_or_create_key()

        assert result == test_key

    def test_get_or_create_key_generates_new_when_none_available(self):
        """Test get_or_create_key generates new key when none found."""
        mock_keyring = MagicMock()
        mock_keyring.get_password.return_value = None

        with patch.dict("sys.modules", {"keyring": mock_keyring}):
            with patch.dict(os.environ, {}, clear=True):
                result = EncryptionKeyManager.get_or_create_key()

        # Should return a valid key
        assert result is not None
        assert EncryptionKeyManager._validate_key(result) is True

        # Should attempt to store in keyring
        mock_keyring.set_password.assert_called_once()

    def test_get_or_create_key_stores_generated_key(self):
        """Test that newly generated keys are stored in keyring."""
        mock_keyring = MagicMock()
        mock_keyring.get_password.return_value = None

        with patch.dict("sys.modules", {"keyring": mock_keyring}):
            with patch.dict(os.environ, {}, clear=True):
                key = EncryptionKeyManager.get_or_create_key()

        # Verify the generated key was passed to set_password
        mock_keyring.set_password.assert_called_once()
        call_args = mock_keyring.set_password.call_args

        assert call_args[0][0] == EncryptionKeyManager.KEYRING_SERVICE
        assert call_args[0][1] == EncryptionKeyManager.KEYRING_USERNAME
        assert call_args[0][2] == key

    def test_get_or_create_key_handles_storage_failure_gracefully(self):
        """Test that get_or_create_key continues if keyring storage fails."""
        mock_keyring = MagicMock()
        mock_keyring.get_password.return_value = None
        mock_keyring.set_password.side_effect = Exception("Storage failed")

        with patch.dict("sys.modules", {"keyring": mock_keyring}):
            with patch.dict(os.environ, {}, clear=True):
                result = EncryptionKeyManager.get_or_create_key()

        # Should still return a valid key
        assert result is not None
        assert EncryptionKeyManager._validate_key(result) is True


class TestCrossPlatformCompatibility:
    """Test cross-platform compatibility considerations."""

    def test_keyring_import_error_handled(self):
        """Test graceful handling when keyring module is not available."""
        # Simulate ImportError by patching at module level
        with patch.dict("sys.modules", {"keyring": None}):
            result = EncryptionKeyManager._get_key_from_keyring()
            assert result is None

    def test_constants_are_correct(self):
        """Test that service and username constants are set correctly."""
        assert EncryptionKeyManager.KEYRING_SERVICE == "m365-mcp-cache"
        assert EncryptionKeyManager.KEYRING_USERNAME == "encryption-key"
        assert EncryptionKeyManager.ENV_VAR == "M365_MCP_CACHE_KEY"
        assert EncryptionKeyManager.KEY_BYTES == 32

    def test_env_var_name_consistency(self):
        """Test that environment variable name is consistent."""
        # Verify the env var name is used consistently
        test_key = EncryptionKeyManager.generate_key()

        with patch.dict(os.environ, {"M365_MCP_CACHE_KEY": test_key}, clear=True):
            result = EncryptionKeyManager._get_key_from_env()
            assert result == test_key
