"""Cache configuration for M365 MCP Server.

This module defines cache behavior including:
- Database location and connection settings
- TTL (Time-To-Live) policies for different resource types
- Cache size limits and cleanup thresholds
- Cache warming operations
- Cache key generation utilities

The cache uses a three-state TTL model:
1. Fresh: Data is current and served immediately
2. Stale: Data is outdated but served while refreshing in background
3. Expired: Data is too old and must be refreshed before serving
"""

import os
import hashlib
import json
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional
from dataclasses import dataclass


# ============================================================================
# DATABASE CONFIGURATION
# ============================================================================

# Default cache database location (~/.m365_mcp_cache.db)
CACHE_DB_PATH = os.environ.get(
    "M365_MCP_CACHE_DB_PATH", str(Path.home() / ".m365_mcp_cache.db")
)

# SQLCipher encryption settings
SQLCIPHER_SETTINGS = {
    "kdf_iter": 256000,  # PBKDF2 iterations (higher = more secure, slower)
    "cipher_page_size": 4096,  # Page size in bytes
    "cipher_use_hmac": True,  # Use HMAC for authentication
}

# Connection pool settings
CONNECTION_POOL_SIZE = 5  # Maximum concurrent connections
CONNECTION_TIMEOUT = 30.0  # Connection timeout in seconds


# ============================================================================
# TTL POLICIES
# ============================================================================


@dataclass
class TTLPolicy:
    """Time-to-Live policy for a resource type.

    Attributes:
        fresh_seconds: How long data is considered fresh (served immediately)
        stale_seconds: How long data can be stale (served while refreshing)

    After stale_seconds, data is expired and must be refreshed before serving.
    """

    fresh_seconds: int
    stale_seconds: int

    @property
    def fresh_minutes(self) -> float:
        """Get fresh time in minutes."""
        return self.fresh_seconds / 60

    @property
    def stale_minutes(self) -> float:
        """Get stale time in minutes."""
        return self.stale_seconds / 60


# TTL policies for different resource types
# Format: resource_type -> TTLPolicy(fresh_seconds, stale_seconds)
TTL_POLICIES: Dict[str, TTLPolicy] = {
    # Folder Operations (relatively static)
    "folder_get_tree": TTLPolicy(
        fresh_seconds=30 * 60,  # 30 minutes fresh
        stale_seconds=2 * 60 * 60,  # 2 hours stale
    ),
    "folder_list": TTLPolicy(
        fresh_seconds=15 * 60,  # 15 minutes fresh
        stale_seconds=1 * 60 * 60,  # 1 hour stale
    ),
    # Email Operations (frequently changing)
    "email_list": TTLPolicy(
        fresh_seconds=2 * 60,  # 2 minutes fresh
        stale_seconds=10 * 60,  # 10 minutes stale
    ),
    "email_get": TTLPolicy(
        fresh_seconds=15 * 60,  # 15 minutes fresh
        stale_seconds=1 * 60 * 60,  # 1 hour stale
    ),
    # File Operations (moderately changing)
    "file_list": TTLPolicy(
        fresh_seconds=10 * 60,  # 10 minutes fresh
        stale_seconds=1 * 60 * 60,  # 1 hour stale
    ),
    "file_get": TTLPolicy(
        fresh_seconds=20 * 60,  # 20 minutes fresh
        stale_seconds=2 * 60 * 60,  # 2 hours stale
    ),
    # Contact Operations (relatively static)
    "contact_list": TTLPolicy(
        fresh_seconds=20 * 60,  # 20 minutes fresh
        stale_seconds=2 * 60 * 60,  # 2 hours stale
    ),
    "contact_get": TTLPolicy(
        fresh_seconds=30 * 60,  # 30 minutes fresh
        stale_seconds=4 * 60 * 60,  # 4 hours stale
    ),
    # Calendar Operations (time-sensitive)
    "calendar_list_events": TTLPolicy(
        fresh_seconds=5 * 60,  # 5 minutes fresh
        stale_seconds=30 * 60,  # 30 minutes stale
    ),
    "calendar_get_event": TTLPolicy(
        fresh_seconds=10 * 60,  # 10 minutes fresh
        stale_seconds=1 * 60 * 60,  # 1 hour stale
    ),
    # Search Operations (very time-sensitive)
    "search_emails": TTLPolicy(
        fresh_seconds=1 * 60,  # 1 minute fresh
        stale_seconds=5 * 60,  # 5 minutes stale
    ),
    "search_files": TTLPolicy(
        fresh_seconds=1 * 60,  # 1 minute fresh
        stale_seconds=5 * 60,  # 5 minutes stale
    ),
}


# ============================================================================
# CACHE LIMITS
# ============================================================================


@dataclass
class CacheLimits:
    """Cache size and behavior limits."""

    # Entry Size Limits
    max_entry_bytes: int = 10 * 1024 * 1024  # 10 MB per entry

    # Total Cache Size
    max_total_bytes: int = 2 * 1024 * 1024 * 1024  # 2 GB soft limit

    # Cleanup Thresholds
    cleanup_threshold: float = 0.8  # Trigger cleanup at 80% (1.6 GB)
    cleanup_target: float = 0.6  # Clean down to 60% (1.2 GB)

    # Account Limits
    max_entries_per_account: int = 10000  # Max entries per account

    # Compression
    compression_threshold: int = 50 * 1024  # Compress entries >= 50 KB
    compression_level: int = 6  # gzip compression level (1-9)


# Default cache limits instance
CACHE_LIMITS = CacheLimits()


# ============================================================================
# CACHE WARMING
# ============================================================================

# Enable cache warming on server startup
CACHE_WARMING_ENABLED = (
    os.environ.get("M365_MCP_CACHE_WARMING", "true").lower() == "true"
)

# Operations to warm cache with on startup
# Format: (operation_name, priority, throttle_sec, params)
CACHE_WARMING_OPERATIONS = [
    # Priority 1: Folder structure (most important, rarely changes)
    {
        "operation": "folder_get_tree",
        "priority": 1,
        "throttle_sec": 5,
        "params": {"folder_id": "root", "max_depth": 10},
    },
    # Priority 2: Email list (frequently accessed)
    {
        "operation": "email_list",
        "priority": 2,
        "throttle_sec": 3,
        "params": {"folder_id": "inbox", "limit": 50},
    },
    # Priority 3: Contact list (commonly used)
    {
        "operation": "contact_list",
        "priority": 3,
        "throttle_sec": 2,
        "params": {"limit": 100},
    },
]


# ============================================================================
# CACHE KEY GENERATION
# ============================================================================


def generate_cache_key(
    account_id: str, resource_type: str, parameters: Optional[Dict[str, Any]] = None
) -> str:
    """Generate deterministic cache key from operation parameters.

    Args:
        account_id: Microsoft account identifier
        resource_type: Type of resource (e.g., 'folder_get_tree', 'email_list')
        parameters: Optional operation parameters (must be JSON-serializable)

    Returns:
        Cache key in format: resource_type:account_id:param_hash

    Example:
        >>> generate_cache_key("acc-123", "folder_get_tree", {"folder_id": "root"})
        'folder_get_tree:acc-123:8f4b2c3d1a...'
    """
    # Start with resource type and account
    key_parts = [resource_type, account_id]

    # Add hash of parameters if provided
    if parameters:
        # Sort parameters for deterministic hashing
        param_json = json.dumps(parameters, sort_keys=True, separators=(",", ":"))
        param_hash = hashlib.sha256(param_json.encode()).hexdigest()[:16]
        key_parts.append(param_hash)

    return ":".join(key_parts)


def parse_cache_key(cache_key: str) -> Dict[str, str]:
    """Parse cache key back into components.

    Args:
        cache_key: Cache key to parse

    Returns:
        Dictionary with 'resource_type', 'account_id', and optionally 'param_hash'

    Example:
        >>> parse_cache_key("folder_get_tree:acc-123:8f4b2c3d")
        {'resource_type': 'folder_get_tree', 'account_id': 'acc-123', 'param_hash': '8f4b2c3d'}
    """
    parts = cache_key.split(":")

    result = {
        "resource_type": parts[0] if len(parts) > 0 else "",
        "account_id": parts[1] if len(parts) > 1 else "",
    }

    if len(parts) > 2:
        result["param_hash"] = parts[2]

    return result


def get_ttl_policy(resource_type: str) -> TTLPolicy:
    """Get TTL policy for a resource type.

    Args:
        resource_type: Type of resource (e.g., 'folder_get_tree')

    Returns:
        TTLPolicy for the resource type, or default policy if not found
    """
    # Return specific policy if defined
    if resource_type in TTL_POLICIES:
        return TTL_POLICIES[resource_type]

    # Default policy for unknown resource types (conservative)
    return TTLPolicy(
        fresh_seconds=5 * 60,  # 5 minutes fresh
        stale_seconds=15 * 60,  # 15 minutes stale
    )


# ============================================================================
# CACHE STATE ENUM
# ============================================================================


class CacheState(Enum):
    """Cache entry state based on TTL policies."""

    FRESH = "fresh"  # Data is current, serve immediately
    STALE = "stale"  # Data is outdated, serve but refresh in background
    EXPIRED = "expired"  # Data is too old, must refresh before serving
    MISSING = "missing"  # No cached data available
