"""Encryption key management for M365 MCP cache system.

This module provides secure encryption key management with system keyring
integration and environment variable fallback for headless deployments.

All cached data is encrypted at rest using AES-256-CBC via SQLCipher.
"""

import os
import secrets
import base64
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class EncryptionKeyManager:
    """Manage encryption keys with system keyring integration.

    This class handles automatic encryption key generation, storage, and
    retrieval using a priority-based approach:

    1. System keyring (Linux/macOS/Windows)
    2. Environment variable (M365_MCP_CACHE_KEY)
    3. Generate new key and store in keyring

    The encryption keys are 256-bit (32 bytes) cryptographically secure
    random values, base64-encoded for storage and transport.

    Security Guarantees:
    - Keys are never logged or exposed in error messages
    - Keys are stored securely in OS-native keyrings when available
    - Keys are generated using cryptographically secure random sources
    - Fallback to environment variables for headless server deployments

    Example:
        >>> manager = EncryptionKeyManager()
        >>> key = manager.get_or_create_key()
        >>> # key is a base64-encoded 256-bit encryption key
    """

    KEYRING_SERVICE = "m365-mcp-cache"
    KEYRING_USERNAME = "encryption-key"
    ENV_VAR = "M365_MCP_CACHE_KEY"
    KEY_BYTES = 32  # 256 bits

    @staticmethod
    def generate_key() -> str:
        """Generate cryptographically secure 256-bit encryption key.

        Uses Python's secrets module which provides cryptographically strong
        random values suitable for managing data such as encryption keys.

        Returns:
            Base64-encoded 256-bit encryption key suitable for use with
            SQLCipher and AES-256 encryption.

        Example:
            >>> key = EncryptionKeyManager.generate_key()
            >>> len(base64.b64decode(key))
            32
        """
        key_bytes = secrets.token_bytes(EncryptionKeyManager.KEY_BYTES)
        key_b64 = base64.b64encode(key_bytes).decode("utf-8")

        logger.debug("Generated new 256-bit encryption key")
        return key_b64

    @staticmethod
    def get_or_create_key() -> str:
        """Get encryption key with automatic fallback and generation.

        Implements a priority-based key retrieval strategy:

        1. **System Keyring**: Attempts to retrieve key from OS-native keyring
           - Linux: Secret Service API (GNOME Keyring, KWallet)
           - macOS: Keychain Services
           - Windows: Credential Manager (DPAPI)

        2. **Environment Variable**: Falls back to M365_MCP_CACHE_KEY if set

        3. **Generate New**: Creates new 256-bit key and attempts to store
           in system keyring for persistence

        Returns:
            Base64-encoded 256-bit encryption key.

        Raises:
            ValueError: If key generation or retrieval fails catastrophically.

        Security Notes:
            - Key sources are logged (for debugging) but keys are never logged
            - Failed keyring operations are logged as warnings, not errors
            - Environment variable fallback allows headless deployments

        Example:
            >>> key = EncryptionKeyManager.get_or_create_key()
            >>> # Key retrieved from keyring or generated new
        """
        # Priority 1: Try system keyring
        key = EncryptionKeyManager._get_key_from_keyring()
        if key:
            logger.info("Encryption key loaded from system keyring")
            return key

        # Priority 2: Try environment variable
        key = EncryptionKeyManager._get_key_from_env()
        if key:
            logger.info("Encryption key loaded from environment variable")
            return key

        # Priority 3: Generate new key
        logger.info("No existing encryption key found, generating new key")
        key = EncryptionKeyManager.generate_key()

        # Try to persist new key in keyring for future use
        if EncryptionKeyManager._store_key_in_keyring(key):
            logger.info("New encryption key generated and stored in system keyring")
        else:
            logger.warning(
                f"New encryption key generated but could not be stored in keyring. "
                f"To persist the key across sessions, set the {EncryptionKeyManager.ENV_VAR} "
                f"environment variable."
            )

        return key

    @staticmethod
    def _get_key_from_keyring() -> Optional[str]:
        """Attempt to retrieve encryption key from system keyring.

        Returns:
            Base64-encoded encryption key if found, None otherwise.
        """
        try:
            import keyring

            key = keyring.get_password(
                EncryptionKeyManager.KEYRING_SERVICE,
                EncryptionKeyManager.KEYRING_USERNAME,
            )

            if key:
                # Validate key format
                if EncryptionKeyManager._validate_key(key):
                    return key
                else:
                    logger.warning("Invalid key format found in keyring, ignoring")
                    return None

            return None

        except ImportError:
            logger.debug("keyring module not available")
            return None
        except Exception as e:
            logger.warning(f"System keyring unavailable: {e}")
            return None

    @staticmethod
    def _get_key_from_env() -> Optional[str]:
        """Attempt to retrieve encryption key from environment variable.

        Returns:
            Base64-encoded encryption key if found, None otherwise.
        """
        key = os.getenv(EncryptionKeyManager.ENV_VAR)

        if key:
            # Validate key format
            if EncryptionKeyManager._validate_key(key):
                return key
            else:
                logger.warning(
                    f"Invalid key format in {EncryptionKeyManager.ENV_VAR} "
                    f"environment variable"
                )
                return None

        return None

    @staticmethod
    def _store_key_in_keyring(key: str) -> bool:
        """Attempt to store encryption key in system keyring.

        Args:
            key: Base64-encoded encryption key to store.

        Returns:
            True if key was successfully stored, False otherwise.
        """
        try:
            import keyring

            keyring.set_password(
                EncryptionKeyManager.KEYRING_SERVICE,
                EncryptionKeyManager.KEYRING_USERNAME,
                key,
            )

            logger.debug("Encryption key stored in system keyring")
            return True

        except ImportError:
            logger.debug("keyring module not available for storage")
            return False
        except Exception as e:
            logger.warning(f"Could not store key in keyring: {e}")
            return False

    @staticmethod
    def _validate_key(key: str) -> bool:
        """Validate encryption key format and length.

        Args:
            key: Base64-encoded key to validate.

        Returns:
            True if key is valid format and correct length, False otherwise.
        """
        try:
            # Attempt to decode base64
            key_bytes = base64.b64decode(key, validate=True)

            # Verify key length (256 bits = 32 bytes)
            if len(key_bytes) != EncryptionKeyManager.KEY_BYTES:
                logger.warning(
                    f"Invalid key length: {len(key_bytes)} bytes "
                    f"(expected {EncryptionKeyManager.KEY_BYTES})"
                )
                return False

            return True

        except Exception as e:
            logger.warning(f"Key validation failed: {e}")
            return False

    @staticmethod
    def delete_key_from_keyring() -> bool:
        """Delete encryption key from system keyring.

        This is primarily used for testing and administrative purposes.
        Use with caution as this will make the existing cache database
        inaccessible.

        Returns:
            True if key was deleted or didn't exist, False on error.

        Warning:
            Deleting the encryption key will make the existing encrypted
            cache database unreadable. The database will need to be deleted
            and recreated.
        """
        try:
            import keyring

            keyring.delete_password(
                EncryptionKeyManager.KEYRING_SERVICE,
                EncryptionKeyManager.KEYRING_USERNAME,
            )

            logger.info("Encryption key deleted from system keyring")
            return True

        except ImportError:
            logger.debug("keyring module not available")
            return True  # No key to delete
        except Exception as e:
            logger.warning(f"Could not delete key from keyring: {e}")
            return False
