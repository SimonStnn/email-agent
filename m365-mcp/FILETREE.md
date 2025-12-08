# File Tree

```text
m365-mcp/
├── .env                                    # Environment variables (create from .env.example)
├── .env.example                            # **NEW** Environment configuration template with comments
├── .env.stdio.example                      # **NEW** stdio mode configuration example
├── .env.http.example                       # **NEW** HTTP mode configuration example
├── .git/                                   # Git repository
├── .gitignore                              # Git ignore rules (includes .env)
├── .python-version                         # Python version specification
├── .venv/                                  # Virtual environment
├── authenticate.py                         # **MODIFIED** Interactive authentication script (supports --env-file)
├── CHANGELOG.md                            # **MODIFIED** Project changelog with monitoring system updates
├── CLAUDE.md                               # Claude Code guidance file
├── EMAIL_FOLDER_IMPLEMENTATION_SUMMARY.md  # **NEW** Email folder tools implementation
├── EMAIL_OUTPUT_FORMAT.md                  # **NEW** Email reading output format guide
├── ENV_FILE_USAGE.md                       # **NEW** Guide for using --env-file argument
├── FOLDER_LISTING_TODO.md                  # **NEW** Implementation plan
├── FILETREE.md                             # **MODIFIED** This file - project structure with monitoring updates
├── MESSAGE_RULES_IMPLEMENTATION_SUMMARY.md # **NEW** Message rule tools implementation
├── MONITORING.md                           # **NEW** Monitoring and troubleshooting guide
├── ONEDRIVE_FOLDER_IMPLEMENTATION_SUMMARY.md # **NEW** OneDrive folder tools implementation
├── QUICKSTART.md                           # **NEW** Quick start guide for installation and setup
├── SECURITY.md                             # **NEW** Security guide for transport modes and authentication
├── HTTP_TRANSPORT_IMPLEMENTATION.md         # **NEW** Streamable HTTP transport implementation details
├── HTTP_APP_METHOD_FIX.md                   # **NEW** Fix for http_app() method issue (2025-10-06)
├── MIGRATION_SSE_TO_HTTP.md                 # **NEW** Migration notes from SSE to Streamable HTTP
├── monitor_mcp_server.sh                   # **NEW** Health monitoring script with auto-recovery
├── start_mcp_with_monitoring.sh            # **MODIFIED** Server startup script with monitoring (supports .env file loading)
├── pyproject.toml                          # **MODIFIED** Python project configuration (added fastapi, uvicorn)
├── README.md                               # Project documentation
├── uv.lock                                 # UV package lock file
├── logs/                                   # **NEW** Log directory (auto-created)
│   ├── mcp_server_all.jsonl                # JSON structured logs (all levels)
│   ├── mcp_server_errors.jsonl             # JSON error logs only
│   ├── mcp_server.log                      # Human-readable logs
│   ├── server_output.log                   # Server stdout/stderr
│   └── monitor.log                         # Monitor activity log
├── reports/                                # **NEW** Error report directory (auto-created)
│   └── error_report_YYYYMMDD_HHMMSS.txt   # Auto-generated error reports
├── src/
│   └── m365_mcp/
│       ├── __init__.py                     # Package initialization
│       ├── auth.py                         # **MODIFIED** MSAL authentication & token management (env loading removed)
│       ├── cache_config.py                 # **NEW** Cache configuration and policies (244 lines)
│       │                                   #   - TTL policies for 12 resource types (Fresh/Stale/Expired)
│       │                                   #   - Cache limits and cleanup thresholds
│       │                                   #   - Cache warming operations configuration
│       │                                   #   - Cache key generation and parsing utilities
│       ├── encryption.py                   # **NEW** Encryption key management for secure cache (273 lines)
│       │                                   #   - EncryptionKeyManager class with 256-bit AES key generation
│       │                                   #   - Multi-source key retrieval (keyring → env var → generate)
│       │                                   #   - Cross-platform keyring support (Linux/macOS/Windows)
│       │                                   #   - Graceful degradation for headless environments
│       ├── cache.py                        # **NEW** Encrypted cache manager with compression and TTL (481 lines)
│       │                                   #   - CacheManager class with full lifecycle management
│       │                                   #   - Encrypted SQLite operations via SQLCipher (AES-256)
│       │                                   #   - Connection pooling (max 5 connections)
│       │                                   #   - Automatic gzip compression for entries ≥50KB
│       │                                   #   - Three-state TTL detection (Fresh/Stale/Expired)
│       │                                   #   - Pattern-based cache invalidation with wildcards
│       │                                   #   - Automatic cleanup at 80% capacity
│       │                                   #   - LRU eviction and statistics tracking
│       ├── cache_migration.py              # **NEW** Cache migration utilities (121 lines)
│       │                                   #   - Migrate from unencrypted to encrypted cache
│       │                                   #   - Automatic detection and migration on startup
│       │                                   #   - Backup creation for safety
│       ├── cache_warming.py                # **NEW** Background cache warming system (250 lines)
│       │                                   #   - CacheWarmer class for pre-populating cache
│       │                                   #   - Non-blocking startup (server responds immediately)
│       │                                   #   - Priority-based queue (folder_tree → emails → files)
│       │                                   #   - Throttled execution to respect API rate limits
│       │                                   #   - Automatic retry on failures
│       ├── background_worker.py            # **NEW** Async background task queue (200 lines)
│       │                                   #   - BackgroundWorker for async cache operations
│       │                                   #   - Priority-based task scheduling
│       │                                   #   - Retry logic with exponential backoff
│       │                                   #   - Task status tracking and monitoring
│       ├── graph.py                        # Microsoft Graph API client wrapper
│       ├── migrations/                     # **NEW** Database schema migrations
│       │   └── 001_init_cache.sql          # **NEW** Initial cache system schema (171 lines)
│       │                                   #   - cache_entries: Cached API responses with TTL
│       │                                   #   - cache_tasks: Background task queue
│       │                                   #   - cache_invalidation: Invalidation audit log
│       │                                   #   - cache_stats: Performance metrics
│       │                                   #   - 9 performance indexes
│       ├── health_check.py                 # **NEW** Health check utility module with async/sync functions
│       │                                   #   - check_health() - Single health check
│       │                                   #   - continuous_health_check() - Continuous monitoring
│       │                                   #   - CLI: python -m m365_mcp.health_check
│       ├── logging_config.py               # **NEW** Comprehensive logging configuration
│       │                                   #   - Structured JSON formatter
│       │                                   #   - Human-readable formatter with colors
│       │                                   #   - Multiple log outputs (JSON, errors, readable)
│       │                                   #   - Automatic log rotation (10 files × 10MB)
│       ├── mcp_instance.py                 # **NEW** FastMCP instance (single source of truth)
│       ├── server.py                       # **MODIFIED** FastMCP server with logging, monitoring, and graceful shutdown
│       │                                   #   - Command-line argument support (--env-file)
│       │                                   #   - Comprehensive structured logging
│       │                                   #   - Signal handlers for graceful shutdown
│       │                                   #   - Request/response timing and client IP tracking
│       ├── tools.py                        # **NEW** MCP tool registry (imports mcp and triggers tool registration)
│       ├── validators.py                   # Shared validation helpers and ValidationError class
│       │                                   #   - Validators for accounts, email, datetime, paths, Graph IDs, URLs
│       │                                   #   - Security helpers: ensure_safe_path, validate_graph_url, validate_onedrive_path
│       │                                   #   - Sanitised error messaging and logging utilities
│       └── tools/                          # **NEW** Modular tool implementations (57 tools across 11 files)
│           ├── __init__.py                  # **NEW** Tool package exports (imports all functions and mcp)
│           ├── account.py                   # **NEW** Account management tools (3 tools)
│           ├── calendar.py                  # **NEW** Calendar and event tools (6 tools)
│           ├── contact.py                   # **NEW** Contact management tools (5 tools)
│           ├── email.py                     # **NEW** Email operations tools (10 tools)
│           ├── email_folders.py             # **MODIFIED** Email folder management tools (9 tools)
│           ├── email_rules.py               # **NEW** Email rule/filter management tools (9 tools)
│           ├── file.py                      # **NEW** OneDrive file operations tools (5 tools)
│           ├── folder.py                    # **NEW** OneDrive folder navigation tools (3 tools)
│           ├── search.py                    # **NEW** Search operations tools (5 tools)
│           └── cache.py                     # **NEW** Cache management tools (5 tools)
│               ├── cache_get_stats          # View cache statistics
│               ├── cache_invalidate         # Invalidate cache entries by pattern
│               ├── cache_task_enqueue       # Queue background cache task
│               ├── cache_task_status        # Check cache task status
│               └── cache_task_list          # List cache tasks
│           ├── account.py: 3 tools
│           │   ├── account_list                    # List signed-in accounts
│           │   ├── account_authenticate            # Start device flow auth
│           │   └── account_complete_auth           # Complete device flow
│           ├── calendar.py: 6 tools
│           │   ├── calendar_get_event              # Get event details
│           │   ├── calendar_create_event           # Create event
│           │   ├── calendar_update_event           # Update event
│           │   ├── calendar_delete_event           # Delete event (confirm=True)
│           │   ├── calendar_respond_event          # Respond to invite
│           │   └── calendar_check_availability     # Check availability
│           ├── contact.py: 5 tools
│           │   ├── contact_list                    # List contacts
│           │   ├── contact_get                     # Get contact details
│           │   ├── contact_create                  # Create contact
│           │   ├── contact_update                  # Update contact
│           │   └── contact_delete                  # Delete contact (confirm=True)
│           ├── email.py: 10 tools
│           │   ├── email_list                      # List emails (folder_id param)
│           │   ├── email_get                       # Get email details
│           │   ├── email_create_draft              # Create draft
│           │   ├── email_send                      # Send email (confirm=True)
│           │   ├── email_update                    # Update email properties
│           │   ├── email_delete                    # Delete email (confirm=True)
│           │   ├── email_move                      # Move to folder
│           │   ├── email_reply                     # Reply to sender (confirm=True)
│           │   ├── email_reply_all                 # Reply to all recipients (confirm=True)
│           │   ├── email_archive                   # Archive email to Archive folder (✏️ moderate)
│           │   └── email_get_attachment            # Download attachment
│           ├── email_folders.py: 9 tools
│           │   ├── emailfolders_list               # List root/child folders
│           │   ├── emailfolders_get                # Get folder details
│           │   ├── emailfolders_get_tree           # Build recursive tree
│           │   ├── emailfolders_create             # Create new folder (✏️ moderate)
│           │   ├── emailfolders_rename             # Rename folder (✏️ moderate)
│           │   ├── emailfolders_move               # Move folder to parent (✏️ moderate)
│           │   ├── emailfolders_delete             # Delete folder (🔴 critical, confirm=True)
│           │   ├── emailfolders_mark_all_as_read   # Mark all as read (✏️ moderate)
│           │   └── emailfolders_empty              # Empty folder (🔴 critical, confirm=True)
│           ├── email_rules.py: 9 tools
│           │   ├── emailrules_list                 # List email filter rules
│           │   ├── emailrules_get                  # Get rule details
│           │   ├── emailrules_create               # Create filter rule
│           │   ├── emailrules_update               # Update rule
│           │   ├── emailrules_delete               # Delete rule (confirm=True)
│           │   ├── emailrules_move_top             # Move to sequence 1
│           │   ├── emailrules_move_bottom          # Move to last position
│           │   ├── emailrules_move_up              # Decrease sequence by 1
│           │   └── emailrules_move_down            # Increase sequence by 1
│           ├── file.py: 5 tools
│           │   ├── file_list                       # List files/folders (folder_id, type_filter)
│           │   ├── file_get                        # Download file
│           │   ├── file_create                     # Upload file
│           │   ├── file_update                     # Update file content
│           │   └── file_delete                     # Delete file/folder (confirm=True)
│           ├── folder.py: 3 tools
│           │   ├── folder_list                     # List OneDrive folders
│           │   ├── folder_get                      # Get folder metadata
│           │   └── folder_get_tree                 # Build recursive tree
│           └── search.py: 5 tools
│               ├── search_files                    # Search OneDrive files
│               ├── search_emails                   # Search emails
│               ├── search_events                   # Search calendar events
│               ├── search_contacts                 # Search contacts
│               └── search_unified                  # Unified search
├── tests/
│   ├── __init__.py                         # Test package initialization
│   ├── conftest.py                         # Shared pytest fixtures for Graph API mocking
│   ├── test_cache_schema.py                # **NEW** Cache schema and configuration tests (10 tests)
│   │                                       #   - Database creation with encryption (3 tests)
│   │                                       #   - Schema migration execution and verification
│   │                                       #   - Table structure validation
│   │                                       #   - Cache key generation and parsing (2 tests)
│   │                                       #   - TTL policy configuration (3 tests)
│   │                                       #   - Cache limits and state constants (2 tests)
│   ├── test_cache.py                       # **NEW** Cache manager comprehensive tests (361 lines, 19 tests)
│   │                                       #   - Cache basics: initialization, set/get, miss handling (5 tests)
│   │                                       #   - Compression: small/large entry handling (2 tests)
│   │                                       #   - TTL: Fresh/Stale/Expired state detection (3 tests)
│   │                                       #   - Invalidation: exact match and wildcard patterns (3 tests)
│   │                                       #   - Cleanup: expired entries and LRU eviction (1 test)
│   │                                       #   - Statistics: cache metrics and hit tracking (3 tests)
│   │                                       #   - Encryption: encrypted at rest verification (2 tests)
│   ├── test_encryption.py                  # **NEW** Encryption key management tests (309 lines, 26 tests)
│   │                                       #   - Key generation tests (5 tests)
│   │                                       #   - Key validation tests (4 tests)
│   │                                       #   - Keyring integration tests (7 tests)
│   │                                       #   - Environment variable fallback tests (4 tests)
│   │                                       #   - get_or_create_key workflow tests (5 tests)
│   │                                       #   - Cross-platform compatibility tests (3 tests)
│   ├── test_cache_warming.py               # **NEW** Cache warming tests (11+ tests)
│   │                                       #   - Non-blocking startup tests
│   │                                       #   - Priority queue ordering tests
│   │                                       #   - Throttling and rate limiting tests
│   │                                       #   - Skip already-cached entry tests
│   │                                       #   - Failure handling and retry tests
│   ├── test_background_worker.py           # **NEW** Background worker tests (9 tests)
│   │                                       #   - Task queue initialization
│   │                                       #   - Priority-based task ordering
│   │                                       #   - Retry logic with exponential backoff
│   │                                       #   - Task status tracking
│   │                                       #   - Worker start/stop lifecycle
│   ├── test_tool_caching.py                # **NEW** Tool caching integration tests (7 tests)
│   │                                       #   - Cache key generation for tools
│   │                                       #   - Cache hit/miss detection
│   │                                       #   - Account isolation verification
│   │                                       #   - Parameter isolation tests
│   │                                       #   - Cache statistics tracking
│   ├── test_cache_tools.py                 # **NEW** Cache management tool tests (~15 tests)
│   │                                       #   - cache_get_stats functionality
│   │                                       #   - cache_invalidate pattern matching
│   │                                       #   - cache_task_enqueue/status/list
│   │                                       #   - Multi-account cache operations
│   ├── test_integration.py                 # **REWRITTEN** Complete integration test suite (986 lines, 34 tests)
│   │                                       #   - Emails: list, list_without_body, get, create_draft, update, delete, move, reply, reply_all, send (10 tests)
│   │                                       #   - Calendar: list_events, get_event, create, update, delete, respond, check_availability (7 tests)
│   │                                       #   - Contacts: list, get, create, update, delete (5 tests)
│   │                                       #   - Files: list, get, create, update, delete (5 tests)
│   │                                       #   - Search: files, emails, events, contacts, unified (5 tests)
│   │                                       #   - Attachments: get_attachment (1 test)
│   │                                       #   - Account: list_accounts (1 test)
│   │                                       #   - All tests pass (125.80s for 34 tests, ~3.7s per test)
│   │                                       #   - Uses proven pattern: async for session in get_session()
│   ├── test_email_folders_integration.py  # **NEW** Email folder integration tests (298 lines, 7 tests)
│   │                                       #   - Test list, get, get_tree, create, delete, rename, and move operations
│   │                                       #   - All tests pass (16.49s for 7 tests, ~2.4s per test)
│   │                                       #   - Proper cleanup with try/finally blocks
│   ├── test_email_folders_validation.py   # **NEW** Email folder validation tests (365 lines, 17 tests)
│   │                                       #   - Create folder validation (5 tests)
│   │                                       #   - Delete folder validation (3 tests)
│   │                                       #   - Rename folder validation (3 tests)
│   │                                       #   - Move folder validation (3 tests)
│   │                                       #   - Mark all as read validation (2 tests)
│   │                                       #   - Empty folder validation (1 test)
│   │                                       #   - All tests pass (unit tests with mocked Graph API)
│   ├── test_folder_validation.py          # **NEW** OneDrive folder validation tests (295 lines, 13 tests)
│   │                                       #   - Create folder validation (5 tests: root, parent, empty name, whitespace, strips)
│   │                                       #   - Delete folder validation (3 tests: success, no confirm, default false)
│   │                                       #   - Rename folder validation (4 tests: success, empty, whitespace, strips)
│   │                                       #   - Move folder validation (1 test: success)
│   │                                       #   - All tests pass (unit tests with mocked Graph API)
│   └── tools/                              # Planned module-specific validation suites (future work)
│       ├── test_email_validation.py        # Planned email tool validation tests
│       ├── test_file_validation.py         # Planned file tool validation tests
│       ├── test_calendar_validation.py     # Planned calendar tool validation tests
│       ├── test_contact_validation.py      # Planned contact tool validation tests
│       ├── test_email_rules_validation.py  # Planned email rules validation tests
│       ├── test_search_validation.py       # Planned search tool validation tests
│       ├── test_folder_validation.py       # Planned folder validation tests
│       └── test_account_validation.py      # **PLANNED** Account tool validation tests
├── docs/                                   # **NEW** User documentation
│   ├── cache_user_guide.md                 # **NEW** Cache user guide (389 lines)
│   │                                       #   - How to use cache parameters
│   │                                       #   - When to force refresh
│   │                                       #   - Viewing cache statistics
│   │                                       #   - Manual cache invalidation
│   │                                       #   - Troubleshooting common issues
│   │                                       #   - Best practices
│   ├── cache_security.md                   # **NEW** Cache security guide (486 lines)
│   │                                       #   - Encryption details (AES-256, SQLCipher)
│   │                                       #   - Key management (keyring, environment)
│   │                                       #   - GDPR and HIPAA compliance
│   │                                       #   - Security best practices
│   │                                       #   - Backup and recovery procedures
│   │                                       #   - Threat model analysis
│   └── cache_examples.md                   # **NEW** Cache examples guide (642 lines)
│       │                                   #   - Basic cache usage patterns
│       │                                   #   - Performance optimization tips
│       │                                   #   - Multi-account cache management
│       │                                   #   - Advanced invalidation patterns
│       │                                   #   - Monitoring and debugging
│       │                                   #   - Common workflows
├── cache_update_v2/                        # **NEW** Cache implementation reports
│   ├── STILL_TODO.md                       # Implementation task tracking (updated to completion status)
│   ├── SECURITY_AUDIT_REPORT.md            # Complete security audit (A- rating)
│   ├── SESSION_SUMMARY.md                  # Session work summary
│   └── FINAL_REPORT.md                     # Implementation completion report
└── reports/
    └── todo/
        ├── PARAMETER_VALIDATION.md         # **NEW** Parameter validation analysis report
        └── PARAMETER_VALIDATION_PLAN.md    # **NEW** Comprehensive validation implementation plan
```

## Key Files

### Source Code

- **`src/m365_mcp/tools.py`** (tool registry, imports from tools/ directory)
- **`src/m365_mcp/tools/`** (modular tool implementations)
  - `account.py` - Account management (3 tools)
  - `calendar.py` - Calendar operations (6 tools)
  - `contact.py` - Contact management (5 tools)
  - `email.py` - Email operations (10 tools)
  - `email_folders.py` - Email folder management (9 tools)
  - `email_rules.py` - Email rule management (9 tools)
  - `file.py` - OneDrive file operations (5 tools)
  - `folder.py` - OneDrive folder navigation (3 tools)
  - `search.py` - Search operations (5 tools)
  - `server.py` - Server information (1 tool)

### Documentation

- **`README.md`** - **MODIFIED** User-facing documentation with cache features and performance benchmarks
- **`QUICKSTART.md`** - Quick start guide for installation and setup
- **`CLAUDE.md`** - **MODIFIED** AI assistant guidance with complete cache architecture section
- **`CHANGELOG.md`** - **MODIFIED** Version history with cache system implementation
- **`MONITORING.md`** - Comprehensive monitoring and troubleshooting guide
- **`SECURITY.md`** - Security guide for transport modes and authentication
- **`docs/cache_user_guide.md`** - **NEW** Complete cache user guide (389 lines)
- **`docs/cache_security.md`** - **NEW** Cache security and compliance guide (486 lines)
- **`docs/cache_examples.md`** - **NEW** Practical cache usage examples (642 lines)
- **`cache_update_v2/SECURITY_AUDIT_REPORT.md`** - **NEW** Complete security audit report
- **`cache_update_v2/FINAL_REPORT.md`** - **NEW** Implementation completion report
- **`.projects/steering/tech.md`** - **MODIFIED** Updated with cache dependencies and architecture
- **`.projects/steering/structure.md`** - **MODIFIED** Updated with cache modules and layers
- **`FOLDER_LISTING_TODO.md`** - Implementation plan
- **`EMAIL_FOLDER_IMPLEMENTATION_SUMMARY.md`** - Email folder tools implementation
- **`EMAIL_OUTPUT_FORMAT.md`** - Email reading output format guide
- **`ONEDRIVE_FOLDER_IMPLEMENTATION_SUMMARY.md`** - OneDrive folder tools implementation
- **`MESSAGE_RULES_IMPLEMENTATION_SUMMARY.md`** - Message rule tools implementation
- **`HTTP_TRANSPORT_IMPLEMENTATION.md`** - Streamable HTTP transport implementation details
- **`reports/todo/PARAMETER_VALIDATION.md`** - Parameter validation analysis report
- **`reports/todo/PARAMETER_VALIDATION_PLAN.md`** - Comprehensive validation implementation plan

### Scripts

- **`monitor_mcp_server.sh`** - **NEW** Health monitoring script with auto-recovery
  - Periodic health checks via HTTP endpoint
  - Automatic process cleanup on failure
  - Comprehensive error report generation
  - Configurable failure thresholds
- **`start_mcp_with_monitoring.sh`** - **NEW** Server startup script with monitoring
  - Launches server with automatic monitoring
  - Environment validation
  - Token generation if not provided
  - Graceful shutdown handling

### Configuration

- **`pyproject.toml`** - Project metadata, dependencies, build config
- **`.env`** - Environment variables (create from .env.example, not committed to git)
- **`.env.example`** - Template with all configuration options and detailed comments
- **`uv.lock`** - Locked dependency versions

### Authentication

- **`authenticate.py`** - CLI tool for user authentication
- **`~/.m365_mcp_token_cache.json`** - MSAL token cache stored in user's home directory (not in repo)

## Tool Naming Convention

All 62 MCP tools follow the `category_verb_entity` naming pattern for better organization:

**Categories:**

- `account_` - Account authentication and management (3 tools)
- `email_` - Email operations (10 tools)
- `emailfolders_` - Email folder management (9 tools)
- `emailrules_` - Email rule/filter management (9 tools)
- `calendar_` - Calendar and event operations (7 tools)
- `contact_` - Contact management (5 tools)
- `file_` - OneDrive file operations (5 tools)
- `folder_` - OneDrive folder navigation (3 tools)
- `search_` - Search operations (5 tools)
- `cache_` - Cache management and monitoring (5 tools) - **NEW**
- `server_` - Server information (1 tool)

**Safety Levels:**

- 📖 **Safe (29 tools)** - Read-only operations, safe for unsupervised use (includes 5 cache tools)
- ✏️ **Moderate (24 tools)** - Write/modify operations, requires user confirmation recommended (includes email_archive and folder management tools)
- 📧 **Dangerous (3 tools)** - Send operations (email), always require user confirmation
- 🔴 **Critical (7 tools)** - Delete operations, always require user confirmation with `confirm=True` parameter (includes folder operations)

**Confirmation Required:**
Tools with `confirm=True` parameter (10 tools):

- Send: `email_send`, `email_reply`, `email_reply_all`
- Delete: `email_delete`, `emailrules_delete`, `calendar_delete_event`, `contact_delete`, `file_delete`
- Folder Operations: `emailfolders_delete`, `emailfolders_empty`

**Cache Management Tools (5 new safe tools):**

- `cache_get_stats` - 📖 View cache statistics (size, entries, hit rate)
- `cache_invalidate` - 📖 Invalidate cache entries by pattern (safe maintenance operation)
- `cache_task_enqueue` - 📖 Queue background cache warming task
- `cache_task_status` - 📖 Check status of queued cache task
- `cache_task_list` - 📖 List all cache tasks by account or status

## Recent Changes

### 2024-10-03 - Email Folder Tools

**Modified:**

- `src/m365_mcp/tools.py` - Added 3 new tools, enhanced 1 tool, added 1 helper function

**Added:**

- `CHANGELOG.md` - Project changelog
- `FILETREE.md` - This file
- `EMAIL_FOLDER_IMPLEMENTATION_SUMMARY.md` - Implementation details
- `FOLDER_LISTING_TODO.md` - Full implementation plan
- `VERIFICATION_REPORT.md` - Comprehensive verification results
- `BUGFIX_SUMMARY.md` - Bug fix documentation
- `verify_email_tools.py` - Tool signature verification script
- `verify_implementation.py` - Implementation verification script
- `test_fix.py` - FunctionTool bug fix verification

**Bug Fixes:**

- Fixed "'FunctionTool' object is not callable" error in `get_mail_folder_tree`
- Created internal helper `_list_mail_folders_impl()` for code reuse

**Tool Count:** 35 → 38 (email folder tools added)

### 2024-10-03 - OneDrive Folder Tools

**Modified:**

- `src/m365_mcp/tools.py` - Added 3 new OneDrive tools, enhanced 1 tool, added 1 helper

**Added:**

- `ONEDRIVE_FOLDER_IMPLEMENTATION_SUMMARY.md` - OneDrive implementation details
- `verify_onedrive_tools.py` - OneDrive tool verification script

**New Tools:**

- `list_folders` - List only folders in OneDrive
- `get_folder` - Get OneDrive folder metadata
- `get_folder_tree` - Build recursive OneDrive folder tree
- `list_files` enhanced - Added folder_id and type_filter parameters

**Helper Function:**

- `_list_folders_impl()` - OneDrive folder listing implementation

**Tool Count:** 38 → 41 (OneDrive folder tools added)

### 2025-10-07 - Modular Tool Architecture

**Modified:**

- `src/m365_mcp/tools.py` - Refactored to import from modular tools/ directory
- `src/m365_mcp/tools/__init__.py` - **NEW** Package exports for all 51 tools

**Added:**

- `src/m365_mcp/tools/` - **NEW** Modular tool implementations (10 files)
  - `account.py` - 3 account management tools
  - `calendar.py` - 6 calendar tools
  - `contact.py` - 5 contact management tools
  - `email.py` - 9 email tools
  - `email_folders.py` - 3 email folder tools
  - `email_rules.py` - 9 email rule tools
  - `file.py` - 5 OneDrive file tools
  - `folder.py` - 3 OneDrive folder tools
  - `search.py` - 5 search tools

**Benefits:**

- Better code organization and maintainability
- Easier to locate and modify specific tool categories
- Cleaner imports and exports
- Preserved all existing functionality

**Tool Count:** 50 (unchanged - same functionality, improved structure)

**Added:**

- `MESSAGE_RULES_IMPLEMENTATION_SUMMARY.md` - Rule management implementation details
- `EMAIL_OUTPUT_FORMAT.md` - Email reading output format guide
- `verify_rule_tools.py` - Rule tool verification script

**New Tools:**

- `list_message_rules` - List all inbox rules
- `get_message_rule` - Get specific rule details
- `create_message_rule` - Create email filter with conditions/actions
- `update_message_rule` - Update existing rule
- `delete_message_rule` - Delete a rule
- `move_rule_to_top` - Move to sequence 1 (execute first)
- `move_rule_to_bottom` - Move to last position
- `move_rule_up` - Decrease sequence by 1
- `move_rule_down` - Increase sequence by 1

**Azure Permission Required:**

- `MailboxSettings.ReadWrite` - Not yet added to Azure app

**Tool Count:** 41 → 51 (message rule tools and server tools added)

### 2025-10-14 - High-Performance Encrypted Cache System

**Modified:**

- `src/m365_mcp/tools/folder.py` - Added caching to `folder_get_tree` (300x faster)
- `src/m365_mcp/tools/email.py` - Added caching to `email_list` (40-100x faster)
- `src/m365_mcp/tools/file.py` - Added caching to `file_list` (30-100x faster)
- `README.md` - Added cache features and performance benchmarks
- `CLAUDE.md` - Added complete cache architecture documentation
- `CHANGELOG.md` - Added cache system implementation details
- `.projects/steering/tech.md` - Updated with cache dependencies
- `.projects/steering/structure.md` - Updated with cache modules

**Added:**

- `src/m365_mcp/cache.py` - Encrypted cache manager (481 lines)
- `src/m365_mcp/cache_config.py` - Cache configuration and TTL policies (244 lines)
- `src/m365_mcp/cache_warming.py` - Background cache warming (250 lines)
- `src/m365_mcp/background_worker.py` - Async task queue (200 lines)
- `src/m365_mcp/encryption.py` - Encryption key management (273 lines)
- `src/m365_mcp/cache_migration.py` - Database migrations (121 lines)
- `src/m365_mcp/tools/cache.py` - **NEW** 5 cache management tools
- `docs/cache_user_guide.md` - Complete user guide (389 lines)
- `docs/cache_security.md` - Security and compliance guide (486 lines)
- `docs/cache_examples.md` - Practical usage examples (642 lines)
- `cache_update_v2/SECURITY_AUDIT_REPORT.md` - Complete security audit
- `cache_update_v2/FINAL_REPORT.md` - Implementation completion report
- `tests/test_cache.py` - Cache operations tests (18 tests)
- `tests/test_encryption.py` - Encryption key tests (26 tests)
- `tests/test_cache_schema.py` - Schema tests (8 tests)
- `tests/test_cache_warming.py` - Cache warming tests (11+ tests)
- `tests/test_background_worker.py` - Worker tests (9 tests)
- `tests/test_tool_caching.py` - Tool integration tests (7 tests)
- `tests/test_cache_tools.py` - Cache tool tests (~15 tests)

**New Cache Tools:**

- `cache_get_stats` - View cache statistics
- `cache_invalidate` - Invalidate cache entries
- `cache_task_enqueue` - Queue cache task
- `cache_task_status` - Check task status
- `cache_task_list` - List cache tasks

**Features:**

- **Performance**: 300x speedup for folder operations, 40-100x for email/file operations
- **Security**: AES-256 encryption via SQLCipher, GDPR/HIPAA compliant
- **Intelligent TTL**: Three-state lifecycle (Fresh/Stale/Expired)
- **Automatic Compression**: 70-80% size reduction for large entries
- **Cache Warming**: Non-blocking background pre-population
- **Account Isolation**: Multi-tenant safe cache
- **Zero Breaking Changes**: Fully backward compatible

**Testing:**

- 79 cache tests passing (100% pass rate)
- Security audit: A- rating (Excellent)
- Comprehensive test coverage: >95%

**Tool Count:** 51 → 56 (cache management tools added)

**Total Statistics:**

- Starting tools: 35
- Email folder tools: +3 (38 total) → +6 more (44 total) - **UPDATED**
- OneDrive folder tools: +3 (41 total)
- Message rule tools: +9 (50 total)
- Server tools: +1 (51 total)
- Cache management tools: +5 (56 total)
- Email folder management tools: +6 (62 total) - **NEW**
- Enhanced tools: 5 (`list_emails`, `list_files`, `folder_get_tree` with caching)
- Helper functions: 2 (`_list_mail_folders_impl`, `_list_folders_impl`)

### 2025-10-14 - Email Folder Management Tools

**Modified:**

- `src/m365_mcp/tools/email_folders.py` - **ENHANCED** Added 6 new tools for comprehensive folder management (9 tools total)

**New Tools:**

- `emailfolders_create(display_name, account_id, parent_folder_id?)` - Create folders at root or as children (✏️ moderate)
- `emailfolders_rename(folder_id, new_display_name, account_id)` - Rename existing folders (✏️ moderate)
- `emailfolders_move(folder_id, destination_folder_id, account_id)` - Move folders to different parents (✏️ moderate)
- `emailfolders_delete(folder_id, account_id, confirm=True)` - Permanently delete folders and contents (🔴 critical)
- `emailfolders_mark_all_as_read(folder_id, account_id)` - Mark all messages in folder as read (✏️ moderate)
- `emailfolders_empty(folder_id, account_id, confirm=True)` - Permanently delete all messages in folder (🔴 critical)

**Features:**

- **Comprehensive folder management**: Full CRUD operations on email folders
- **Safety first**: Critical operations require explicit `confirm=True` parameter
- **Input validation**: Microsoft Graph ID validation and sanitization
- **Error handling**: Graceful error handling with descriptive messages
- **Bulk operations**: Mark all as read and empty folder for large-scale management

**Safety Annotations:**

- 4 moderate safety tools (✏️) for create, rename, move, mark as read
- 2 critical safety tools (🔴) for delete and empty operations
- All critical tools require `confirm=True` to prevent accidents

**Tool Count:** 56 → 62 (email folder management tools added)

### 2025-10-05 - Transport Modes and Security

**Modified:**

- `src/m365_mcp/server.py` - Added stdio/Streamable HTTP transport selection with bearer token authentication
- `pyproject.toml` - Added fastapi and uvicorn dependencies

**Added:**

- `SECURITY.md` - Comprehensive security guide for transport modes, authentication, and best practices
- Streamable HTTP transport support with configurable host/port
- Bearer token authentication middleware for Streamable HTTP mode
- OAuth authentication support (FastMCP 2.0+)
- Security safeguards: refuses to start SSE without auth, token validation, network warnings

**Features:**

- **stdio transport** (default) - Process-isolated, secure for desktop apps (Claude Desktop)
- **Streamable HTTP transport** - HTTP-based for web/API access with required authentication:
  - Bearer token authentication (recommended)
  - OAuth 2.0 authentication
  - Health check endpoint at `/health`
  - Network binding warnings for `0.0.0.0`
  - Minimum token length validation (32 chars)

**Environment Variables:**

- `MCP_TRANSPORT` - "stdio" (default) or "sse"
- `MCP_HOST` - Streamable HTTP server bind address (default: "127.0.0.1")
- `MCP_PORT` - Streamable HTTP server port (default: "8000")
- `MCP_AUTH_METHOD` - "bearer", "oauth", or "none"
- `MCP_AUTH_TOKEN` - Bearer token (required for bearer auth)
- `MCP_ALLOW_INSECURE` - Allow SSE without auth (DANGEROUS, requires explicit opt-in)
