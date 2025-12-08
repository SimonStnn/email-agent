# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

M365 MCP is a Model Context Protocol (MCP) server that provides AI assistants with access to Microsoft Graph API. It enables management of Outlook emails, Calendar events, OneDrive files, and Contacts with support for multiple Microsoft accounts (personal, work, school).

## Architecture

### Core Modules

- **`src/m365_mcp/server.py`**: Entry point that initializes the FastMCP server
- **`src/m365_mcp/auth.py`**: Handles MSAL authentication using device flow, token caching to `~/.m365_mcp_token_cache.json`, and multi-account management
- **`src/m365_mcp/graph.py`**: HTTP client wrapper for Microsoft Graph API with retry logic, pagination, chunked uploads (15×320 KiB chunks), and rate limiting handling
- **`src/m365_mcp/tools.py`**: Defines 51 MCP tools using FastMCP decorators (`@mcp.tool`)
- **`authenticate.py`**: Standalone script for interactive account authentication

### Cache System

- **`src/m365_mcp/cache.py`**: Encrypted SQLite cache manager with AES-256 encryption via SQLCipher
- **`src/m365_mcp/cache_config.py`**: Cache configuration, TTL policies, and cache key generation
- **`src/m365_mcp/cache_warming.py`**: Automatic cache warming on server startup for faster first requests
- **`src/m365_mcp/background_worker.py`**: Async background worker for cache warming and maintenance tasks
- **`src/m365_mcp/encryption.py`**: Encryption key management with keyring integration and environment fallback
- **`src/m365_mcp/cache_migration.py`**: Database migration utilities for cache schema updates

### Key Design Patterns

- **Multi-Account Architecture**: All tool functions require `account_id` as first parameter. Use `list_accounts()` to get available account IDs.
- **Token Management**: Uses MSAL `PublicClientApplication` with device flow authentication. Tokens are automatically refreshed and cached.
- **Pagination**: `graph.request_paginated()` follows `@odata.nextLink` for large result sets
- **Large File Handling**: Files >4.8MB use resumable upload sessions via `graph.upload_large_file()` and `graph.upload_large_mail_attachment()`
- **Error Handling**: Graph requests implement exponential backoff for 5xx errors and respect 429 rate limit headers
- **Encrypted Caching**: AES-256 encrypted SQLite cache with automatic compression, TTL management, and cache warming for 300x performance improvement on repeated operations

### Cache Architecture

The M365 MCP server includes a comprehensive caching system that dramatically improves performance by reducing redundant API calls to Microsoft Graph.

#### Key Features

1. **AES-256 Encryption**: All cached data is encrypted at rest using SQLCipher
   - Encryption keys stored securely in system keyring (macOS Keychain, Windows Credential Manager, Linux Secret Service)
   - Environment variable fallback for headless servers (`M365_MCP_CACHE_KEY`)
   - GDPR and HIPAA compliant data protection

2. **Intelligent TTL Management**: Three-state cache lifecycle
   - **Fresh** (0-5 min for folder tree, 0-5 min for emails): Return immediately, no API call
   - **Stale** (5-30 min): Return cached data immediately, refresh in background
   - **Expired** (>30 min): Fetch fresh data from API, update cache

3. **Automatic Compression**: Entries ≥50KB are automatically gzip-compressed (typically 70-80% size reduction)

4. **Smart Invalidation**: Write operations automatically invalidate related cache entries
   - Pattern-based invalidation (e.g., `email_*` invalidates all email caches)
   - Account-isolated invalidation (changes to account A don't affect account B)

5. **Cache Warming**: Automatic background cache population on server startup
   - Non-blocking startup (server responds immediately)
   - Prioritized queue (folder trees → email lists → file lists)
   - Throttled execution to respect API rate limits

6. **Connection Pooling**: Pool of 5 SQLite connections for concurrent access

7. **Automatic Cleanup**: Maintains cache size under 2GB limit
   - Triggers cleanup at 80% threshold (1.6GB)
   - Reduces to 60% target (1.2GB) by removing oldest entries
   - Expires stale entries automatically

#### Cache Tools

Five new MCP tools for cache management:

1. **`cache_get_stats()`**: View cache statistics (size, entries, hit rate)
2. **`cache_invalidate(pattern, account_id?, reason?)`**: Manually invalidate cache entries
3. **`cache_task_enqueue(task_type, params, priority?)`**: Queue background cache task
4. **`cache_task_status(task_id)`**: Check status of background task
5. **`cache_task_list(account_id?, status?)`**: List all queued/running tasks

#### Performance Impact

- **folder_get_tree**: 30s → <100ms (300x faster)
- **email_list**: 2-5s → <50ms (40-100x faster)
- **file_list**: 1-3s → <30ms (30-100x faster)
- **Cache hit rate**: >80% on typical workloads
- **API call reduction**: >70% fewer Graph API calls

#### Using Cache Parameters

Most tools support optional caching parameters:

```python
# Use cache by default (recommended)
folder_get_tree(account_id, path="/Documents")

# Force refresh and update cache
folder_get_tree(account_id, path="/Documents", force_refresh=True)

# Disable cache for this request only
email_list(account_id, folder="inbox", use_cache=False)
```

### Steering and Guidance Documents

Read and reference the below documentation and ensure compliance for all code edits.

- @.projects/steering/product.md
- @.projects/steering/tech.md
- @.projects/steering/structure.md
- @.projects/steering/python.md
- @.projects/steering/mcp-server.md
- @.projects/steering/tool-names.md

## Development Commands

```bash
# Install dependencies
uv sync

# Run authentication (interactive)
uv run authenticate.py

# Run MCP server (requires M365_MCP_CLIENT_ID env var)
uv run m365-mcp

# Run tests (requires authenticated account)
uv run pytest tests/ -v

# Type checking
uv run pyright

# Format code
uvx ruff format .

# Lint and auto-fix
uvx ruff check --fix --unsafe-fixes .
```

## Environment Variables

- **`M365_MCP_CLIENT_ID`** (required): Azure app registration client ID
- **`M365_MCP_TENANT_ID`** (optional): Defaults to "common". Use "consumers" for personal accounts only

## Azure App Requirements

Required delegated permissions:
- Mail.ReadWrite
- Calendars.ReadWrite
- Files.ReadWrite
- Contacts.Read
- People.Read
- User.Read

App must allow public client flows (device code authentication).

## Testing

Tests in `tests/test_integration.py` run against live Microsoft Graph API and require:
1. Valid `M365_MCP_CLIENT_ID` in environment
2. At least one authenticated account (run `authenticate.py` first)
3. Test account with email, calendar, and OneDrive access

## Common Patterns

### Working with Account IDs
```python
# All tools require account_id as first parameter
accounts = list_accounts()
account_id = accounts[0]["account_id"]

# Use in tool calls
send_email(account_id, to="user@example.com", subject="Test", body="Hello")
```

### Email with Attachments
```python
# Attachments are base64-encoded strings
attachments = [{
    "name": "file.pdf",
    "content_bytes": base64_string,
    "content_type": "application/pdf"
}]
send_email(account_id, to="...", subject="...", body="...", attachments=attachments)
```

### File Uploads
```python
# Files auto-switch to chunked upload for files >4.8MB
create_file(
    account_id=account_id,
    local_file_path="/path/to/file.pdf",
    parent_folder_id="root"  # Use "root" for OneDrive root
)
```

## Important Notes

- FastMCP handles tool registration via decorators; tools are auto-discovered from `tools.py`
- Graph API requests automatically add `ConsistencyLevel: eventual` header for search queries
- Email body content returns as plain text (via `outlook.body-content-type="text"` preference header)
- Folder names in `FOLDERS` dict map user-friendly names to Graph API folder IDs (e.g., "deleted" → "deleteditems")
