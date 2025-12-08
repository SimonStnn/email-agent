# MCP Server Implementation Standards for M365 MCP Server

## MCP Protocol Compliance

### Core Primitives Definition
- **Tools**: Executable functions exposed as MCP tools (e.g., list_emails, send_email)
- **Resources**: Data sources providing contextual information (e.g., folder trees, email metadata)
- **Prompts**: Reusable templates for structuring AI interactions (future enhancement)

### Transport Layer Requirements
- **stdio Mode**: Primary transport for desktop applications - NEVER write to stdout
- **HTTP Mode**: Streamable HTTP for web applications with authentication middleware
- **Logging**: All internal logging must use stderr or structured log files

## Tool Design Mandates

### Single Responsibility Principle (SRP) for Tools
Each MCP tool must have exactly one responsibility:
```python
# ✅ GOOD: Single responsibility
@mcp.tool
def list_emails(account_id: str, folder_id: str) -> list[dict[str, Any]]:
    """List emails in a specific folder."""

@mcp.tool
def send_email(account_id: str, to: str, subject: str, body: str) -> dict[str, str]:
    """Send a single email."""

# ❌ BAD: Multiple responsibilities
@mcp.tool
def manage_emails(account_id: str, action: str, **kwargs) -> Any:
    """Handle multiple email operations."""  # Violates SRP
```

### Tool Signature Standards
- **Account isolation**: `account_id: str` as first parameter for all tools
- **Type safety**: Complete type annotations for all parameters and returns
- **Error handling**: Proper exception raising with descriptive messages
- **Documentation**: Google-style docstrings with Args, Returns, Raises sections

### Tool Implementation Pattern
```python
@mcp.tool
def get_email_patterns(
    account_id: str,
    analysis_period_days: int = 30,
    include_confidence_scores: bool = True,
) -> dict[str, Any]:
    """Analyze email patterns for intelligent organization.

    Args:
        account_id: The Microsoft account identifier.
        analysis_period_days: Number of days of email history to analyze.
        include_confidence_scores: Whether to include confidence scores in results.

    Returns:
        Dictionary containing pattern analysis results with sender clusters,
        keyword frequencies, and temporal patterns.

    Raises:
        ValueError: If account_id is invalid or analysis period is too large.
        ConnectionError: If Microsoft Graph API is unavailable.
    """
    # Validate inputs
    if analysis_period_days > 365:
        raise ValueError("Analysis period cannot exceed 365 days")

    try:
        # Implementation logic here
        patterns = analyze_email_patterns(account_id, analysis_period_days)

        if not include_confidence_scores:
            # Remove confidence scores from results
            patterns = remove_confidence_scores(patterns)

        return patterns

    except GraphAPIError as e:
        logger.error(f"Graph API error for account {account_id}: {e}")
        raise ConnectionError(f"Failed to analyze email patterns: {e}") from e
```

## Security Mandates

### OAuth 2.1 Compliance
- **Token validation**: Verify tokens are intended for this server (RFC 8707)
- **Scope enforcement**: Locally validate OAuth scopes match tool requirements
- **Token isolation**: Never pass client tokens to upstream APIs

### Authentication Middleware (HTTP Mode)
```python
class MCPAuthenticationMiddleware:
    def __init__(self, required_scopes: list[str]):
        self.required_scopes = set(required_scopes)

    async def __call__(self, request: Request, call_next):
        # Extract and validate bearer token
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing or invalid Authorization header"},
                headers={"WWW-Authenticate": "Bearer"}
            )

        token = auth_header[7:]  # Remove "Bearer " prefix

        # Validate token and extract scopes
        try:
            token_scopes = validate_access_token(token)
            if not self.required_scopes.issubset(token_scopes):
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Insufficient permissions"}
                )
        except TokenError as e:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid authentication token"}
            )

        return await call_next(request)
```

### Least Privilege Tool Design
Tools must be designed with minimal required permissions:
```python
# ✅ GOOD: Minimal scope
@mcp.tool
def list_inbox_emails(account_id: str, limit: int = 10) -> list[dict[str, Any]]:
    """List emails from inbox only."""
    # Requires only Mail.Read scope

# ❌ BAD: Over-privileged
@mcp.tool
def manage_all_emails(account_id: str, folder_id: str, action: str) -> Any:
    """Manage emails across all folders."""
    # Would require Mail.ReadWrite scope even for read operations
```

## Server Architecture Standards

### Multi-Account Support Pattern
```python
class MultiAccountManager:
    def __init__(self):
        self.account_sessions: dict[str, dict[str, Any]] = {}

    def get_account_context(self, account_id: str) -> dict[str, Any]:
        """Get account-specific context and validate access."""
        if account_id not in self.account_sessions:
            # Validate account exists and is authenticated
            account_context = validate_and_load_account(account_id)
            self.account_sessions[account_id] = account_context

        return self.account_sessions[account_id]

    def cleanup_account_session(self, account_id: str):
        """Clean up account session and associated resources."""
        if account_id in self.account_sessions:
            # Close connections, clear caches, etc.
            del self.account_sessions[account_id]
```

### Session Management
- **Session binding**: Bind session IDs to user information (user_id:session_id)
- **Session isolation**: Complete isolation between different accounts
- **Resource cleanup**: Proper cleanup of account-specific resources

## Error Handling and Resilience

### MCP-Specific Error Responses
```python
class MCPError(Exception):
    """Base class for MCP server errors."""

    def __init__(self, message: str, error_code: str, details: dict[str, Any] = None):
        super().__init__(message)
        self.error_code = error_code
        self.details = details or {}

class ToolExecutionError(MCPError):
    """Raised when tool execution fails."""
    pass

class AuthenticationError(MCPError):
    """Raised when authentication fails."""
    pass

@mcp.tool
def safe_email_operation(account_id: str, email_id: str) -> dict[str, Any]:
    """Safely perform email operation with comprehensive error handling."""
    try:
        # Validate account access
        account_context = get_account_context(account_id)

        # Perform operation with proper error handling
        result = perform_email_operation(email_id, account_context)

        return result

    except AuthenticationError as e:
        # Return proper MCP error response
        raise MCPError(
            "Authentication failed",
            "AUTHENTICATION_ERROR",
            {"account_id": account_id}
        ) from e

    except GraphAPIError as e:
        raise MCPError(
            "Microsoft Graph API error",
            "GRAPH_API_ERROR",
            {"operation": "email_operation", "email_id": email_id}
        ) from e

    except Exception as e:
        # Unexpected errors should be logged and handled gracefully
        logger.error(f"Unexpected error in email operation: {e}", exc_info=True)
        raise MCPError(
            "Internal server error",
            "INTERNAL_ERROR"
        ) from e
```

### Graceful Degradation
- **Partial failures**: Handle partial failures in batch operations
- **Fallback strategies**: Implement fallbacks for non-critical operations
- **Resource cleanup**: Ensure proper cleanup on errors

## Performance and Scalability

### Caching Strategy for MCP Tools
```python
class MCPToolCache:
    def __init__(self):
        # Hot cache for frequently accessed data (5 min TTL)
        self.hot_cache: TTLCache[str, Any] = TTLCache(maxsize=1000, ttl=300)

        # Warm cache for recent data (1 hour TTL)
        self.warm_cache: TTLCache[str, Any] = TTLCache(maxsize=10000, ttl=3600)

        # Cold cache for metadata (24 hour TTL)
        self.cold_cache: TTLCache[str, Any] = TTLCache(maxsize=50000, ttl=86400)

    def get_cached_result(self, cache_key: str, loader_func) -> Any:
        """Get result with multi-level cache fallback."""
        # Try hot cache first
        if cache_key in self.hot_cache:
            return self.hot_cache[cache_key]

        # Try warm cache
        if cache_key in self.warm_cache:
            value = self.warm_cache[cache_key]
            self.hot_cache[cache_key] = value  # Promote to hot
            return value

        # Try cold cache for metadata
        if cache_key in self.cold_cache:
            return self.cold_cache[cache_key]

        # Load fresh data and cache
        value = loader_func()
        self.hot_cache[cache_key] = value
        self.warm_cache[cache_key] = value
        self.cold_cache[cache_key] = value

        return value
```

### Rate Limiting and Backoff
```python
class RateLimitManager:
    def __init__(self):
        self.request_counts: dict[str, int] = {}
        self.backoff_until: dict[str, float] = {}

    async def check_rate_limit(self, account_id: str) -> None:
        """Check and enforce rate limits for Microsoft Graph API."""
        now = time.time()

        # Reset counters if backoff period has passed
        if account_id in self.backoff_until and now > self.backoff_until[account_id]:
            self.request_counts[account_id] = 0
            del self.backoff_until[account_id]

        # Check current rate limit
        current_count = self.request_counts.get(account_id, 0)
        if current_count >= 1000:  # Microsoft Graph limit
            # Implement exponential backoff
            backoff_seconds = min(2 ** (current_count // 1000), 300)  # Max 5 min
            self.backoff_until[account_id] = now + backoff_seconds
            raise RateLimitError(f"Rate limit exceeded. Backoff for {backoff_seconds}s")

        self.request_counts[account_id] = current_count + 1
```

## Testing Standards for MCP Tools

### Test-Driven Development (TDD) Process
1. **RED Stage**: Write failing unit tests for tool behavior
2. **GREEN Stage**: Implement minimal tool functionality to pass tests
3. **Refactor Stage**: Improve code structure while maintaining test compliance

### MCP Tool Testing Pattern
```python
import pytest
from unittest.mock import Mock, patch

class TestEmailCategorization:
    def test_categorize_single_email_success(self):
        """Test successful email categorization."""
        # Arrange
        account_id = "test-account-123"
        email_id = "email-456"

        expected_result = {
            "email_id": email_id,
            "categories": ["Work", "Important"],
            "confidence": 0.85
        }

        with patch('m365_mcp.graph.request') as mock_request:
            mock_request.return_value = expected_result

            # Act
            result = categorize_email(account_id, email_id)

            # Assert
            assert result == expected_result
            mock_request.assert_called_once()

    def test_categorize_email_invalid_account(self):
        """Test error handling for invalid account."""
        # Arrange
        invalid_account_id = "invalid-account"

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid account"):
            categorize_email(invalid_account_id, "email-123")
```

## Deployment and Configuration

### Environment-Based Configuration
```python
class MCPConfiguration:
    def __init__(self):
        self.client_id = os.getenv("M365_MCP_CLIENT_ID")
        self.transport = os.getenv("MCP_TRANSPORT", "stdio")
        self.auth_method = os.getenv("MCP_AUTH_METHOD", "none")
        self.host = os.getenv("MCP_HOST", "127.0.0.1")
        self.port = int(os.getenv("MCP_PORT", "8000"))

    def validate_configuration(self) -> None:
        """Validate all required configuration is present."""
        if not self.client_id:
            raise ConfigurationError(
                "M365_MCP_CLIENT_ID environment variable is required"
            )

        if self.transport not in ["stdio", "http"]:
            raise ConfigurationError(
                f"Invalid MCP_TRANSPORT: {self.transport}. Must be 'stdio' or 'http'"
            )
```

### Health Check Endpoints
```python
@mcp.tool
def health_check() -> dict[str, str]:
    """Provide server health and status information."""
    return {
        "status": "healthy",
        "transport": get_current_transport(),
        "version": get_server_version(),
        "accounts_configured": len(get_configured_accounts())
    }
```

## Monitoring and Observability

### Structured Logging for MCP Operations
```python
import logging
import json
from datetime import datetime

class MCPStructuredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        from datetime import datetime, timezone
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "mcp_tool": getattr(record, "mcp_tool", None),
            "account_id": getattr(record, "account_id", None),
            "operation_id": getattr(record, "operation_id", None),
            "duration_ms": getattr(record, "duration_ms", None)
        }

        # Remove None values for cleaner logs
        return json.dumps({k: v for k, v in log_entry.items() if v is not None})

# Configure MCP-specific logging
mcp_logger = logging.getLogger("mcp.server")
handler = logging.StreamHandler(sys.stderr)  # Use stderr for stdio transport
handler.setFormatter(MCPStructuredFormatter())
mcp_logger.addHandler(handler)
mcp_logger.setLevel(logging.INFO)
```

### Performance Monitoring
```python
import time
from functools import wraps
from contextlib import contextmanager

def monitor_tool_performance(tool_name: str):
    """Decorator to monitor MCP tool performance."""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()

            try:
                result = await func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000

                # Log performance metrics
                mcp_logger.info(
                    f"Tool {tool_name} completed successfully",
                    extra={
                        "mcp_tool": tool_name,
                        "duration_ms": duration_ms,
                        "success": True
                    }
                )

                return result

            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                mcp_logger.error(
                    f"Tool {tool_name} failed",
                    extra={
                        "mcp_tool": tool_name,
                        "duration_ms": duration_ms,
                        "error": str(e),
                        "success": False
                    }
                )
                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()

            try:
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000

                mcp_logger.info(
                    f"Tool {tool_name} completed successfully",
                    extra={
                        "mcp_tool": tool_name,
                        "duration_ms": duration_ms,
                        "success": True
                    }
                )

                return result

            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                mcp_logger.error(
                    f"Tool {tool_name} failed",
                    extra={
                        "mcp_tool": tool_name,
                        "duration_ms": duration_ms,
                        "error": str(e),
                        "success": False
                    }
                )
                raise

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

    return decorator

# Apply performance monitoring to all MCP tools
@mcp.tool
@monitor_tool_performance("categorize_emails")
def categorize_emails(account_id: str, email_ids: list[str]) -> dict[str, Any]:
    """Categorize emails with performance monitoring."""
    # Implementation here
    pass
```

## Validation Checklist for MCP Tools

### Pre-Implementation Validation
- [ ] Tool follows Single Responsibility Principle
- [ ] Tool has minimal required OAuth scope
- [ ] Tool includes comprehensive error handling
- [ ] Tool has complete type annotations
- [ ] Tool has Google-style docstring with Args/Returns/Raises

### Security Validation
- [ ] Tool validates all input parameters
- [ ] Tool enforces least privilege access
- [ ] Tool handles authentication errors properly
- [ ] Tool doesn't expose sensitive data in responses

### Performance Validation
- [ ] Tool implements appropriate caching strategy
- [ ] Tool handles large datasets efficiently
- [ ] Tool respects API rate limits
- [ ] Tool includes performance monitoring

### Testing Validation
- [ ] Tool has comprehensive unit tests
- [ ] Tool tests cover success and failure scenarios
- [ ] Tool tests validate error handling
- [ ] Tool tests confirm type safety