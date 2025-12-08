# Project Structure

## Overview

M365 MCP Server follows a modular architecture with clear separation of concerns. The project is organized into logical layers that support easy maintenance, testing, and extension.

## Core Architecture

```
m365-mcp/
├── src/m365_mcp/          # Main package
│   ├── __init__.py            # Package initialization
│   ├── auth.py                # Authentication & token management
│   ├── graph.py               # Microsoft Graph API client
│   ├── server.py              # MCP server configuration & HTTP transport
│   ├── tools.py               # MCP tool definitions (51+ tools)
│   ├── cache.py               # Encrypted SQLite cache manager (AES-256)
│   ├── cache_config.py        # Cache configuration, TTL policies, key generation
│   ├── cache_warming.py       # Automatic background cache warming
│   ├── cache_migration.py     # Database migration utilities
│   ├── background_worker.py   # Async task queue for cache operations
│   └── encryption.py          # Encryption key management (keyring integration)
├── tests/                     # Test suite
│   ├── __init__.py
│   ├── test_integration.py    # Integration tests
│   ├── test_cache.py          # Cache operation tests (18 tests)
│   ├── test_encryption.py     # Encryption & key management tests (26 tests)
│   ├── test_cache_schema.py   # Database schema tests (8 tests)
│   ├── test_cache_warming.py  # Cache warming tests (20+ tests)
│   ├── test_background_worker.py # Background task tests (9 tests)
│   └── test_tool_caching.py   # Tool caching integration tests (7 tests)
├── .projects/steering/        # AI assistant guidance
│   ├── product.md             # Product overview
│   ├── tech.md                # Technology stack & commands
│   └── structure.md           # This file
├── docs/                      # Documentation
└── reports/                   # Generated reports & analysis
```

## Layer Responsibilities

### Authentication Layer (`auth.py`)
- **MSAL integration** - Microsoft Authentication Library setup
- **Token management** - Refresh token storage and renewal
- **Multi-account support** - Account discovery and isolation
- **Device flow authentication** - User-friendly auth process

### API Client Layer (`graph.py`)
- **HTTP client setup** - Configured httpx client with timeouts
- **Request/response handling** - Unified Graph API communication
- **Pagination support** - Efficient handling of large datasets
- **Rate limiting** - Intelligent backoff and retry logic
- **File upload** - Large file handling with chunked upload

### Tool Layer (`tools.py`)
- **MCP tool definitions** - FastMCP decorators for all operations
- **Business logic** - Email, calendar, file, and contact operations
- **Error handling** - Comprehensive error management
- **Type safety** - Full type annotations for all tools

### Server Layer (`server.py`)
- **Transport modes** - stdio (default) and HTTP support
- **Security configuration** - Authentication middleware for HTTP
- **Health checks** - Monitoring and diagnostics endpoints
- **Environment management** - Configuration loading and validation

### Cache Layer (`cache.py`, `cache_config.py`, `encryption.py`)
- **Encrypted storage** - AES-256 encryption via SQLCipher for data at rest
- **TTL management** - Three-state cache lifecycle (Fresh/Stale/Expired)
- **Compression** - Automatic gzip compression for entries ≥50KB
- **Invalidation** - Pattern-based cache invalidation on write operations
- **Connection pooling** - Pool of 5 connections for concurrent access
- **Key management** - Secure keyring integration with environment fallback
- **Size management** - Automatic cleanup at 80% of 2GB limit

### Background Processing (`background_worker.py`, `cache_warming.py`)
- **Async task queue** - Priority-based task scheduling and execution
- **Cache warming** - Non-blocking pre-population on server startup
- **Retry logic** - Automatic retry with exponential backoff for failed tasks
- **Status tracking** - Real-time task status and completion monitoring

## Key Design Patterns

### MCP Tool Pattern
All Microsoft 365 operations are exposed as stateless MCP tools with:
- **Consistent signatures** - account_id as first parameter
- **Comprehensive error handling** - Proper exception management
- **Type safety** - Full type annotations
- **Documentation** - Detailed docstrings with examples

### Graph API Client Pattern
Centralized API communication with:
- **Unified error handling** - Consistent HTTP error management
- **Automatic retries** - Exponential backoff for transient failures
- **Response parsing** - JSON response processing
- **Authentication** - Automatic token injection

### Multi-Account Pattern
Account isolation and management:
- **Account context** - Per-operation account specification
- **Token isolation** - Separate tokens per account
- **Resource scoping** - Account-specific API calls

## Development Organization

### Testing Structure
```
tests/
├── test_integration.py        # End-to-end integration tests
├── test_unit/                 # Unit tests (future)
└── test_fixtures/             # Test data and fixtures (future)
```

### Documentation Structure
```
*.md                           # Root documentation files
docs/                          # Detailed documentation (future)
reports/                       # Generated analysis and reports
```

### Build and Configuration
```
pyproject.toml                 # Project configuration
uv.lock                        # Dependency lock file
.env.example                   # Environment template
```

## File Organization Guidelines

### Adding New Tools
1. **Location** - Add to `src/m365_mcp/tools.py`
2. **Pattern** - Use `@mcp.tool` decorator
3. **Signature** - Include `account_id: str` as first parameter
4. **Documentation** - Comprehensive docstring with examples
5. **Error Handling** - Proper exception raising and handling

### Adding New Modules
1. **Location** - Create in `src/m365_mcp/`
2. **Integration** - Import in `__init__.py`
3. **Dependencies** - Minimize cross-module dependencies
4. **Testing** - Include corresponding test file

### Configuration Changes
1. **Environment variables** - Document in `.env.example`
2. **Server configuration** - Modify `server.py` transport logic
3. **Authentication** - Update `auth.py` scopes and flows

## Code Style Conventions

### Python Standards
- **Formatting** - Use `ruff format` for consistent formatting
- **Linting** - Use `ruff check` for code quality
- **Types** - Full type annotations required
- **Imports** - Group standard library, third-party, then local imports

### Documentation Standards
- **Docstrings** - Google style docstrings for all public functions
- **Comments** - Explain complex logic and business rules
- **Examples** - Include usage examples in tool docstrings

### Error Handling Standards
- **Specific exceptions** - Use appropriate exception types
- **Error messages** - Clear, actionable error messages
- **Logging** - Structured logging for debugging

## Extension Points

### Adding New Microsoft Services
1. **API Client** - Extend `graph.py` with new endpoints
2. **Tools** - Add tools in `tools.py` for new operations
3. **Authentication** - Update scopes in `auth.py` if needed
4. **Testing** - Add integration tests for new services

### Performance Enhancements
1. **Caching** - Add caching logic to `graph.py` or tool layer
2. **Batch Operations** - Implement batch API calls where beneficial
3. **Background Processing** - Use async patterns for long operations

### Transport Extensions
1. **New Transports** - Extend `server.py` transport modes
2. **Security** - Add authentication methods in `server.py`
3. **Monitoring** - Add metrics and health checks