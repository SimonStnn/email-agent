# M365 MCP Cache User Guide

**Version**: 1.0
**Last Updated**: 2025-10-14

## Table of Contents

1. [Overview](#overview)
2. [Getting Started](#getting-started)
3. [Using Cache Parameters](#using-cache-parameters)
4. [Viewing Cache Statistics](#viewing-cache-statistics)
5. [Manual Cache Invalidation](#manual-cache-invalidation)
6. [Cache Warming](#cache-warming)
7. [Troubleshooting](#troubleshooting)
8. [Best Practices](#best-practices)

---

## Overview

The M365 MCP cache system dramatically improves performance by reducing redundant calls to Microsoft Graph API. The cache is:

- **Automatic**: Works out-of-the-box with no configuration required
- **Encrypted**: All data encrypted at rest with AES-256
- **Intelligent**: Three-state lifecycle (Fresh/Stale/Expired) ensures data freshness
- **Fast**: 300x performance improvement for common operations

### Performance Benefits

| Operation | Without Cache | With Cache | Improvement |
|-----------|---------------|------------|-------------|
| `folder_get_tree` | 30 seconds | <100ms | **300x faster** |
| `email_list` | 2-5 seconds | <50ms | **40-100x faster** |
| `file_list` | 1-3 seconds | <30ms | **30-100x faster** |

---

## Getting Started

### Automatic Caching

The cache works automatically for these operations:

- `folder_get_tree` - OneDrive folder navigation
- `email_list` - Email inbox/folder listings
- `file_list` - File and folder listings

**No configuration needed!** Just call these tools normally:

```python
# Cache is used automatically
result = folder_get_tree(account_id, path="/Documents")
```

### First Use

On first server startup:

1. Cache is empty (no cached data)
2. Cache warming begins in background (non-blocking)
3. First requests may be slower (cache miss)
4. Subsequent requests are fast (cache hit)

**Expected Timeline**:
- Server startup: Instant
- Cache warming: 30-60 seconds (background)
- First request: Normal API speed
- Second+ request: 40-300x faster

---

## Using Cache Parameters

### Default Behavior (Recommended)

Use cache automatically - fastest option:

```python
# Uses cache if available
folder_get_tree(account_id, path="/Documents")
email_list(account_id, folder="inbox", limit=10)
file_list(account_id, folder_id="root")
```

### Force Refresh

Bypass cache and fetch fresh data:

```python
# Forces API call, updates cache with fresh data
folder_get_tree(account_id, path="/Documents", force_refresh=True)
```

**When to use `force_refresh=True`**:
- After making changes (uploaded files, moved folders)
- When you need real-time data
- Troubleshooting cache issues

### Disable Cache

Disable cache for a single request:

```python
# Bypasses cache completely (no read, no write)
email_list(account_id, folder="inbox", use_cache=False)
```

**When to use `use_cache=False`**:
- Testing/debugging
- One-time operations
- When cache would be misleading

### Cache Parameter Summary

| Parameter | Default | Effect |
|-----------|---------|--------|
| (none) | Cache enabled | Use cache if fresh, refresh if stale/expired |
| `force_refresh=True` | Override | Bypass cache, fetch fresh, update cache |
| `use_cache=False` | Disable | No cache interaction at all |

---

## Viewing Cache Statistics

### Get Cache Stats

View comprehensive cache statistics:

```python
stats = cache_get_stats()
```

### Statistics Returned

```json
{
  "total_entries": 150,
  "total_size_bytes": 45000000,
  "total_size_mb": 42.9,
  "total_hits": 5432,
  "total_requests": 6000,
  "hit_rate": 0.905,
  "oldest_entry": "2025-10-14T10:30:00Z",
  "newest_entry": "2025-10-14T15:45:00Z"
}
```

### Understanding the Statistics

- **total_entries**: Number of cached items
- **total_size_mb**: Cache size in megabytes
- **hit_rate**: Percentage of requests served from cache (0.0-1.0)
- **total_hits**: Number of cache hits
- **total_requests**: Total cache lookups

**Good hit rate**: >0.80 (80%)
**Excellent hit rate**: >0.90 (90%)

---

## Manual Cache Invalidation

### Invalidate by Pattern

Manually clear cache entries:

```python
# Invalidate all email caches
cache_invalidate("email_*")

# Invalidate all folder caches
cache_invalidate("folder_*")

# Invalidate all file caches
cache_invalidate("file_*")
```

### Invalidate for Specific Account

Clear cache for one account only:

```python
# Clear email cache for specific account
cache_invalidate("email_*", account_id="account-123")
```

### Invalidate with Reason

Add audit trail for invalidation:

```python
# Invalidate with reason (logged)
cache_invalidate("folder_*", reason="User uploaded new files")
```

### Automatic Invalidation

The cache automatically invalidates on write operations:

- **File upload**: Invalidates `folder_get_tree` and `file_list`
- **Email send**: Invalidates `email_list` for sent folder
- **Email move**: Invalidates `email_list` for both folders
- **Folder create**: Invalidates `folder_get_tree`

**You rarely need manual invalidation!**

---

## Cache Warming

### What is Cache Warming?

Cache warming pre-populates the cache in the background on server startup:

1. Server starts (instant, non-blocking)
2. Warming begins in background
3. Common operations cached automatically
4. Your requests are fast from the start

### Monitor Cache Warming

Check warming status (not yet implemented in current release)

### Priority Order

Cache warming prioritizes:

1. **High**: `folder_get_tree` (slowest without cache)
2. **Medium**: `email_list` (inbox, sent)
3. **Low**: `file_list` (recent files)

---

## Troubleshooting

### Problem: Stale Data

**Symptoms**: Seeing old data, recent changes not reflected

**Solutions**:
```python
# Force refresh to get latest data
folder_get_tree(account_id, path="/Documents", force_refresh=True)

# Or invalidate and retry
cache_invalidate("folder_*", account_id=account_id)
folder_get_tree(account_id, path="/Documents")
```

### Problem: Cache Not Working

**Symptoms**: All requests are slow, no performance improvement

**Check**:
1. View cache stats: `cache_get_stats()`
2. Check hit rate (should be >0.80)
3. Verify encryption key: Check system keyring or `M365_MCP_CACHE_KEY` env var

**Solutions**:
```bash
# Reset cache database
rm ~/.m365_mcp_cache.db

# Restart server (cache will rebuild)
uv run m365-mcp
```

### Problem: Cache Too Large

**Symptoms**: Cache size approaching 2GB limit

**Automatic**: Cache cleanup triggers at 80% (1.6GB), reduces to 60% (1.2GB)

**Manual**:
```python
# View size
stats = cache_get_stats()
print(f"Cache size: {stats['total_size_mb']} MB")

# Clear specific caches
cache_invalidate("email_*")  # Typically largest
```

### Problem: Encryption Key Error

**Symptoms**: "Invalid encryption key" or "Cannot decrypt cache"

**Cause**: Encryption key changed or lost

**Solution**:
```bash
# Delete and recreate cache
rm ~/.m365_mcp_cache.db

# For headless servers, set key explicitly
export M365_MCP_CACHE_KEY="your-base64-key-here"
```

---

## Best Practices

### 1. Use Default Caching

✅ **DO**: Let cache work automatically
```python
folder_get_tree(account_id, path="/Documents")
```

❌ **DON'T**: Disable cache unnecessarily
```python
folder_get_tree(account_id, path="/Documents", use_cache=False)
```

### 2. Force Refresh After Writes

✅ **DO**: Refresh cache after modifications
```python
# Upload file
create_file(account_id, local_path="/tmp/file.pdf", parent="root")

# Force refresh to see new file
file_list(account_id, folder_id="root", force_refresh=True)
```

### 3. Monitor Cache Hit Rate

✅ **DO**: Check periodically
```python
stats = cache_get_stats()
if stats['hit_rate'] < 0.70:
    print("Warning: Low cache hit rate")
```

### 4. Multi-Account Isolation

✅ **DO**: Trust account isolation
```python
# These are completely isolated
email_list("account-1", folder="inbox")
email_list("account-2", folder="inbox")
```

### 5. Cache Size Management

✅ **DO**: Trust automatic cleanup

❌ **DON'T**: Manually manage unless necessary

### 6. Security Best Practices

✅ **DO**: Use system keyring (automatic)

✅ **DO**: For headless servers, use environment variable:
```bash
export M365_MCP_CACHE_KEY=$(openssl rand -base64 32)
```

❌ **DON'T**: Hardcode encryption keys in code

### 7. Performance Optimization

✅ **DO**: Let cache warm on startup
✅ **DO**: Batch operations when possible
✅ **DO**: Use cache for read-heavy workloads

❌ **DON'T**: Force refresh on every request
❌ **DON'T**: Disable cache for performance-critical operations

---

## Summary

- **Cache is automatic** - Works out-of-the-box
- **300x faster** - Massive performance improvements
- **Encrypted & secure** - AES-256, GDPR/HIPAA compliant
- **Intelligent** - Three-state TTL ensures freshness
- **Low maintenance** - Automatic cleanup and management

**For most users**: Just use the cache! It works automatically and requires no configuration.

**Questions or Issues?** See the security guide for encryption details or check the troubleshooting section above.

---

**Document Version**: 1.0
**Last Updated**: 2025-10-14
**Next Review**: After user feedback or major changes
