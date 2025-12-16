# M365 MCP Cache Examples

**Version**: 1.0
**Last Updated**: 2025-10-14

## Table of Contents

1. [Basic Cache Usage](#basic-cache-usage)
2. [Performance Optimization Patterns](#performance-optimization-patterns)
3. [Multi-Account Cache Management](#multi-account-cache-management)
4. [Advanced Invalidation Patterns](#advanced-invalidation-patterns)
5. [Monitoring and Debugging](#monitoring-and-debugging)
6. [Common Workflows](#common-workflows)

---

## Basic Cache Usage

### Example 1: Default Caching (Recommended)

```python
# Automatic caching - fastest and simplest
def browse_documents(account_id):
    # First call: Cache miss, fetches from API (30s)
    folders = folder_get_tree(account_id, path="/Documents")

    # Second call: Cache hit, returns instantly (<100ms)
    folders_again = folder_get_tree(account_id, path="/Documents")

    return folders
```

**Result**: 300x performance improvement on repeated calls

### Example 2: Force Refresh After Write

```python
# Upload a file, then refresh cache to see it
def upload_and_verify(account_id, file_path):
    # Upload file
    result = create_file(
        account_id=account_id,
        local_file_path=file_path,
        parent_folder_id="root"
    )

    # Force refresh to see new file immediately
    files = file_list(
        account_id,
        folder_id="root",
        force_refresh=True  # Bypasses stale cache
    )

    # Verify file appears in list
    uploaded_file = next(
        (f for f in files if f['name'] == result['name']),
        None
    )

    return uploaded_file is not None
```

### Example 3: Disable Cache for One-Time Operations

```python
# One-time lookup that shouldn't pollute cache
def quick_check(account_id, email_id):
    # Get email without caching
    email = get_email(
        account_id,
        email_id,
        use_cache=False  # No cache read or write
    )

    return email['isRead']
```

---

## Performance Optimization Patterns

### Pattern 1: Batch Operations with Cache

```python
# Efficiently process multiple accounts
def get_all_inboxes(accounts):
    results = {}

    for account in accounts:
        account_id = account['account_id']

        # First call per account: Cache miss
        # Subsequent calls: Cache hit (<50ms)
        emails = email_list(
            account_id,
            folder="inbox",
            limit=50,
            include_body=False  # Faster, less to cache
        )

        results[account_id] = emails

    return results
```

**Performance**:
- First run: ~2-5s per account
- Subsequent runs: ~50ms per account (40-100x faster)

### Pattern 2: Lazy Loading with Cache

```python
# Load data on-demand, cache for future use
class EmailBrowser:
    def __init__(self, account_id):
        self.account_id = account_id
        self._folder_cache = None

    def get_folders(self):
        if self._folder_cache is None:
            # First call: Populates both memory and disk cache
            self._folder_cache = folder_get_tree(
                self.account_id,
                path="/"
            )
        return self._folder_cache

    def refresh_folders(self):
        # Force refresh when needed
        self._folder_cache = folder_get_tree(
            self.account_id,
            path="/",
            force_refresh=True
        )
        return self._folder_cache
```

### Pattern 3: Progressive Enhancement

```python
# Show cached data first, refresh in background
import asyncio

async def show_emails_progressive(account_id):
    # Step 1: Show cached data immediately (fast)
    emails = email_list(account_id, folder="inbox", limit=10)
    display_emails(emails)  # User sees data instantly

    # Step 2: Check if data is stale
    stats = cache_get_stats()

    # Step 3: Refresh in background if needed
    if should_refresh(stats):
        # Non-blocking refresh
        asyncio.create_task(
            refresh_emails_background(account_id)
        )

    return emails

async def refresh_emails_background(account_id):
    # Fetch fresh data in background
    await asyncio.sleep(0.1)  # Let UI render first

    fresh_emails = email_list(
        account_id,
        folder="inbox",
        limit=10,
        force_refresh=True
    )

    # Update UI with fresh data
    update_display(fresh_emails)
```

---

## Multi-Account Cache Management

### Pattern 1: Account Isolation

```python
# Cache automatically isolates accounts
def compare_accounts(account1_id, account2_id):
    # These are completely isolated in cache
    inbox1 = email_list(account1_id, folder="inbox")
    inbox2 = email_list(account2_id, folder="inbox")

    return {
        'account1_count': len(inbox1),
        'account2_count': len(inbox2)
    }
```

**Cache Isolation**: Changes to account1 never affect account2 cache

### Pattern 2: Selective Account Refresh

```python
# Refresh cache for specific account only
def refresh_account_cache(account_id, reason="User requested"):
    # Invalidate all cache for this account
    cache_invalidate("email_*", account_id=account_id, reason=reason)
    cache_invalidate("folder_*", account_id=account_id, reason=reason)
    cache_invalidate("file_*", account_id=account_id, reason=reason)

    # Optionally warm cache immediately
    folder_get_tree(account_id, path="/", force_refresh=True)
    email_list(account_id, folder="inbox", force_refresh=True)
```

### Pattern 3: Multi-Account Statistics

```python
# Monitor cache effectiveness across accounts
def analyze_cache_by_account(accounts):
    stats = cache_get_stats()

    analysis = {
        'total_hit_rate': stats['hit_rate'],
        'total_size_mb': stats['total_size_mb'],
        'accounts': {}
    }

    for account in accounts:
        account_id = account['account_id']

        # Get account-specific stats (conceptual - not yet implemented)
        analysis['accounts'][account_id] = {
            'username': account['username'],
            'cached_operations': 'multiple'  # folder_tree, emails, files
        }

    return analysis
```

---

## Advanced Invalidation Patterns

### Pattern 1: Smart Invalidation on Write

```python
# Automatically invalidate related caches after operations
def upload_file_smart(account_id, file_path, parent_folder):
    # Upload file
    result = create_file(
        account_id=account_id,
        local_file_path=file_path,
        parent_folder_id=parent_folder
    )

    # Smart invalidation: Clear related caches
    cache_invalidate("file_list:*", account_id=account_id)
    cache_invalidate("folder_get_tree:*", account_id=account_id)

    # Return fresh data
    return file_list(
        account_id,
        folder_id=parent_folder,
        force_refresh=True
    )
```

### Pattern 2: Targeted Pattern Invalidation

```python
# Invalidate specific patterns based on operation
def manage_email_folders(account_id, operation):
    if operation == "create_folder":
        # Only invalidate folder-related caches
        cache_invalidate("folder_*", account_id=account_id)

    elif operation == "move_emails":
        # Invalidate both source and destination email lists
        cache_invalidate("email_list:*", account_id=account_id)

    elif operation == "delete_folder":
        # Invalidate everything (folder structure changed)
        cache_invalidate("folder_*", account_id=account_id)
        cache_invalidate("email_*", account_id=account_id)
```

### Pattern 3: Bulk Invalidation with Audit

```python
# Invalidate multiple patterns with audit trail
def reset_account_cache_audited(account_id, admin_user):
    patterns = ["email_*", "folder_*", "file_*"]

    for pattern in patterns:
        cache_invalidate(
            pattern,
            account_id=account_id,
            reason=f"Admin reset by {admin_user}"
        )

    # Log for compliance
    log_audit_event(
        action="cache_reset",
        account_id=account_id,
        admin=admin_user,
        timestamp=datetime.now()
    )
```

---

## Monitoring and Debugging

### Example 1: Cache Health Check

```python
# Monitor cache health and performance
def check_cache_health():
    stats = cache_get_stats()

    health = {
        'status': 'healthy',
        'issues': []
    }

    # Check hit rate
    if stats['hit_rate'] < 0.70:
        health['status'] = 'warning'
        health['issues'].append(
            f"Low hit rate: {stats['hit_rate']:.1%} (expected >70%)"
        )

    # Check size
    size_percent = (stats['total_size_mb'] / 2048) * 100  # 2GB limit
    if size_percent > 80:
        health['status'] = 'warning'
        health['issues'].append(
            f"Cache near limit: {size_percent:.1f}% (cleanup at 80%)"
        )

    # Check age
    from datetime import datetime, timedelta
    oldest = datetime.fromisoformat(stats['oldest_entry'].replace('Z', '+00:00'))
    age_hours = (datetime.now().astimezone() - oldest).total_seconds() / 3600

    if age_hours < 1:
        health['issues'].append(
            "Cache recently cleared (less than 1 hour old)"
        )

    return health
```

### Example 2: Performance Benchmarking

```python
import time

# Benchmark cache performance improvement
def benchmark_cache_performance(account_id):
    # Clear cache to start fresh
    cache_invalidate("folder_*", account_id=account_id)

    # Measure first call (cache miss)
    start = time.time()
    result1 = folder_get_tree(account_id, path="/Documents")
    cold_time = time.time() - start

    # Measure second call (cache hit)
    start = time.time()
    result2 = folder_get_tree(account_id, path="/Documents")
    hot_time = time.time() - start

    speedup = cold_time / hot_time if hot_time > 0 else 0

    return {
        'cold_ms': cold_time * 1000,
        'hot_ms': hot_time * 1000,
        'speedup': f"{speedup:.0f}x",
        'cache_working': speedup > 10  # Should be 100x+
    }
```

### Example 3: Debug Cache Behavior

```python
# Debug why cache isn't working as expected
def debug_cache_issue(account_id, operation, params):
    print(f"Debugging cache for {operation}")

    # 1. Check cache stats
    stats = cache_get_stats()
    print(f"Cache stats: {stats['total_entries']} entries, "
          f"{stats['hit_rate']:.1%} hit rate")

    # 2. Try operation with cache
    start = time.time()
    result1 = globals()[operation](account_id, **params)
    time1 = time.time() - start
    print(f"First call: {time1*1000:.0f}ms")

    # 3. Try again (should be cached)
    start = time.time()
    result2 = globals()[operation](account_id, **params)
    time2 = time.time() - start
    print(f"Second call: {time2*1000:.0f}ms")

    # 4. Check if cached
    if time2 < time1 * 0.1:  # 10x+ faster
        print("✅ Cache is working!")
    else:
        print("❌ Cache not working as expected")
        print("Possible issues:")
        print("- Cache disabled (use_cache=False)?")
        print("- Different parameters?")
        print("- Cache recently invalidated?")

    return {
        'cached': time2 < time1 * 0.1,
        'speedup': time1 / time2 if time2 > 0 else 0
    }
```

---

## Common Workflows

### Workflow 1: Daily Email Processing

```python
# Efficient daily email workflow with caching
def process_daily_emails(account_id):
    # Step 1: Get inbox (cached after first run)
    inbox = email_list(
        account_id,
        folder="inbox",
        limit=50,
        include_body=False  # Faster
    )

    # Step 2: Process unread emails
    unread = [e for e in inbox if not e.get('isRead', False)]

    for email in unread:
        # Process each email
        process_email(account_id, email['id'])

    # Step 3: Refresh cache after processing
    email_list(
        account_id,
        folder="inbox",
        limit=50,
        force_refresh=True
    )

    return len(unread)
```

### Workflow 2: Document Management

```python
# Manage documents with intelligent caching
def organize_documents(account_id):
    # Step 1: Get folder structure (cached, very fast)
    folders = folder_get_tree(account_id, path="/Documents")

    # Step 2: Find target folders
    work_folder = find_folder(folders, "Work")
    personal_folder = find_folder(folders, "Personal")

    # Step 3: Upload files (invalidates cache)
    upload_file(account_id, "report.pdf", work_folder['id'])

    # Step 4: Verify with forced refresh
    work_files = file_list(
        account_id,
        folder_id=work_folder['id'],
        force_refresh=True
    )

    return work_files
```

### Workflow 3: Multi-Account Sync

```python
# Sync across multiple accounts efficiently
def sync_accounts(accounts):
    results = []

    for account in accounts:
        account_id = account['account_id']

        # Get latest emails (cached if recent)
        emails = email_list(account_id, folder="inbox", limit=10)

        # Get folder structure (cached)
        folders = folder_get_tree(account_id, path="/")

        # Analyze
        result = {
            'account': account['username'],
            'unread_count': sum(1 for e in emails if not e.get('isRead')),
            'folder_count': count_folders(folders),
            'cached': True  # Data from cache
        }

        results.append(result)

    return results
```

**Performance**: Processes 10 accounts in ~500ms (vs. 20-50s without cache)

### Workflow 4: Cache Warming on Startup

```python
# Warm cache on application startup
import asyncio

async def warm_cache_on_startup(accounts):
    """Pre-populate cache for all accounts on startup."""

    print("Starting cache warming...")

    tasks = []
    for account in accounts:
        account_id = account['account_id']

        # Queue high-priority operations
        tasks.append(warm_account_cache(account_id))

    # Run concurrently but throttled
    for i in range(0, len(tasks), 3):  # 3 at a time
        batch = tasks[i:i+3]
        await asyncio.gather(*batch)
        await asyncio.sleep(0.5)  # Throttle

    print(f"Cache warming complete for {len(accounts)} accounts")

async def warm_account_cache(account_id):
    """Warm cache for single account."""

    # Priority 1: Folder structure (slowest without cache)
    folder_get_tree(account_id, path="/", force_refresh=True)

    # Priority 2: Inbox
    email_list(account_id, folder="inbox", limit=50, force_refresh=True)

    # Priority 3: Recent files
    file_list(account_id, folder_id="root", force_refresh=True)
```

### Workflow 5: Scheduled Cache Maintenance

```python
# Periodic cache maintenance
def daily_cache_maintenance():
    """Run daily cache maintenance tasks."""

    stats = cache_get_stats()

    # 1. Check health
    health = check_cache_health()
    if health['status'] != 'healthy':
        log_warning(f"Cache health issues: {health['issues']}")

    # 2. Clear old entries (automatic, but can force)
    if stats['total_size_mb'] > 1500:  # 1.5GB
        # Trigger cleanup by invalidating old patterns
        cache_invalidate("email_list:*", reason="Daily maintenance")

    # 3. Log statistics
    log_info(f"Cache stats: {stats['total_entries']} entries, "
             f"{stats['hit_rate']:.1%} hit rate, "
             f"{stats['total_size_mb']:.0f}MB")

    return stats
```

---

## Best Practices Summary

### ✅ DO

1. **Let cache work automatically** - Default behavior is optimal
2. **Force refresh after writes** - Ensures data consistency
3. **Monitor hit rate** - Should be >80%
4. **Use cache for read-heavy operations** - Maximum benefit
5. **Trust account isolation** - Cache handles multi-tenant safely

### ❌ DON'T

1. **Disable cache unnecessarily** - Loses performance benefits
2. **Force refresh on every call** - Defeats purpose of cache
3. **Manually manage cache size** - Automatic cleanup handles it
4. **Invalidate too aggressively** - Reduces hit rate
5. **Hardcode encryption keys** - Use system keyring

---

## Performance Tips

1. **Batch operations**: Process multiple items in one loop
2. **Lazy load**: Only fetch data when needed
3. **Progressive enhancement**: Show cached data first, refresh background
4. **Cache warming**: Pre-populate on startup for instant responses
5. **Monitor metrics**: Track hit rate and adjust patterns

---

## Troubleshooting Examples

### Problem: Seeing Stale Data

```python
# Force refresh to see latest changes
result = folder_get_tree(account_id, path="/", force_refresh=True)
```

### Problem: Low Hit Rate

```python
# Check if parameters are changing
stats = cache_get_stats()
if stats['hit_rate'] < 0.70:
    # Review code for parameter variations
    # Consider normalizing parameters
    pass
```

### Problem: Cache Too Large

```python
# Selective invalidation to reduce size
cache_invalidate("email_*")  # Emails usually largest
```

---

**Document Version**: 1.0
**Last Updated**: 2025-10-14
**See Also**: `cache_user_guide.md`, `cache_security.md`
