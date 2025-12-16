# Python Implementation Standards for M365 MCP Server

## Code Quality Mandates

### PEP 8 Compliance
- **Indentation**: 4 spaces (no tabs)
- **Line length**: Maximum 79 characters for code, 72 for docstrings
- **Blank lines**: 2 blank lines between top-level function/class definitions
- **Encoding**: UTF-8 for all source files

### Naming Conventions
- **Classes/Exceptions**: CapWords (PascalCase)
- **Functions/Methods/Variables**: snake_case
- **Constants**: MACRO_CASE
- **Private members**: Single leading underscore (_internal_method)

### Project Structure
- **Layout**: Use src/ layout (src/m365_mcp/)
- **Configuration**: pyproject.toml as single source of truth
- **Dependencies**: Pinned exact versions (package==X.Y.Z)
- **Imports**: Group standard library, third-party, then local imports

## Documentation Standards (PEP 257)

### Docstring Requirements
- **Coverage**: Every public module, function, method, and class
- **Style**: Google-style docstrings exclusively
- **Structure**: Include Args:, Returns:, and Raises: sections
- **Summary line**: Imperative command ending in period ("Calculate the total.")

### Example Structure
```python
def categorize_email(email_id: str, account_id: str) -> dict[str, Any]:
    """Categorize email using AI-powered content analysis.

    Args:
        email_id: The unique identifier for the email message.
        account_id: The Microsoft account identifier.

    Returns:
        Dictionary containing categorization results and confidence scores.

    Raises:
        ValueError: If email_id is not found or invalid.
        ConnectionError: If Microsoft Graph API is unreachable.
    """
```

## Error Handling Excellence

### Exception Practices
- **Specificity**: Only catch anticipated exceptions (ValueError, TypeError, etc.)
- **Custom hierarchy**: Define project-specific exceptions inheriting from base class
- **Exception chaining**: Use `raise NewError from OriginalError` to preserve context
- **Logging**: Structured JSON format using Python logging module (never print())

### Custom Exception Example
```python
class MicrosoftMCPServerError(Exception):
    """Base exception for M365 MCP Server errors."""
    pass

class AuthenticationError(MicrosoftMCPServerError):
    """Raised when Microsoft authentication fails."""
    pass

class GraphAPIError(MicrosoftMCPServerError):
    """Raised when Microsoft Graph API calls fail."""
    pass
```

## Type Hinting Requirements

### Comprehensive Type Annotations
- **Function signatures**: All parameters and return types
- **Class attributes**: Instance variables and properties
- **Complex types**: Use Union, Optional, List, Dict from typing module
- **Generic types**: Specify type parameters (dict[str, Any])

### Example Type Annotations
```python
from typing import Any, Optional, Union
from collections.abc import Iterator

def list_emails(
    account_id: str,
    folder_id: Optional[str] = None,
    limit: int = 10,
    include_body: bool = True
) -> list[dict[str, Any]]:
    """List emails with full type annotations."""
    pass

class EmailProcessor:
    def __init__(self, cache_size: int = 1000) -> None:
        self.cache_size: int = cache_size
        self.emails: dict[str, dict[str, Any]] = {}
```

## Development Workflow

### Test-Driven Development (TDD) Mandate
1. **RED Stage**: Write comprehensive unit tests first, confirm they fail
2. **GREEN Stage**: Write minimal code to pass tests
3. **Refactor Stage**: Improve structure while maintaining test compliance

### Code Quality Tools
- **Formatting**: Black for uncompromising code formatting
- **Import sorting**: isort for PEP 8 compliant imports
- **Linting**: Ruff for style violations and error detection
- **Type checking**: mypy for static type analysis

### Pre-commit Hooks
All code must pass automated quality checks before commit:
```bash
# Format code
black src/ tests/
isort src/ tests/

# Lint and check types
ruff check src/ tests/
mypy src/
```

## Async and Concurrency Patterns

### Async Function Standards
- **Event loop**: Use asyncio for all I/O operations
- **Awaitable returns**: Functions doing I/O must be async
- **Background tasks**: Use asyncio.create_task() for concurrent operations
- **Cancellation**: Handle asyncio.CancelledError appropriately

### Example Async Patterns
```python
import asyncio
from typing import AsyncIterator

async def process_emails_batch(
    email_ids: list[str],
    account_id: str
) -> AsyncIterator[dict[str, Any]]:
    """Process emails concurrently with proper async patterns."""

    async def process_single_email(email_id: str) -> dict[str, Any]:
        # Simulate async email processing
        await asyncio.sleep(0.1)
        return {"email_id": email_id, "status": "processed"}

    # Process emails concurrently
    tasks = [
        asyncio.create_task(process_single_email(email_id))
        for email_id in email_ids
    ]

    for task in asyncio.as_completed(tasks):
        try:
            result = await task
            yield result
        except Exception as e:
            logger.error(f"Email processing failed: {e}")
```

## Logging Standards

### Structured Logging
- **Module**: Use Python logging, never print()
- **Format**: JSON structured format for observability
- **Levels**: DEBUG, INFO, WARNING, ERROR, CRITICAL
- **Context**: Include relevant identifiers (account_id, email_id, etc.)

### Logging Configuration
```python
import logging
import json
from datetime import datetime

class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        from datetime import datetime, timezone
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "account_id": getattr(record, "account_id", None),
            "operation": getattr(record, "operation", None)
        }
        return json.dumps(log_entry)

# Configure structured logging
logger = logging.getLogger("m365_mcp")
handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
logger.addHandler(handler)
logger.setLevel(logging.INFO)
```

## Graceful Shutdown Requirements

### Signal Handling
- **Signals**: Handle SIGTERM and SIGINT for graceful shutdown
- **Cleanup**: Close database connections, stop background tasks
- **Timeout**: Implement shutdown timeout to force termination

### Shutdown Implementation
```python
import signal
import asyncio
from contextlib import asynccontextmanager

class GracefulShutdown:
    def __init__(self):
        self.shutdown_event = asyncio.Event()

    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, initiating graceful shutdown")
        self.shutdown_event.set()

    async def wait_for_shutdown(self):
        """Wait for shutdown signal."""
        await self.shutdown_event.wait()

@asynccontextmanager
async def lifespan(app):
    shutdown_manager = GracefulShutdown()
    shutdown_manager.setup_signal_handlers()

    try:
        yield
    finally:
        logger.info("Performing graceful shutdown")
        # Cleanup operations
        await cleanup_resources()
```

## Security Considerations

### Input Validation
- **Type checking**: Validate input types and ranges
- **Sanitization**: Clean and validate all user inputs
- **Bounds checking**: Ensure parameters are within acceptable limits

### Authentication Handling
- **Token security**: Never log or expose authentication tokens
- **Scope validation**: Verify OAuth scopes match required permissions
- **Error handling**: Don't leak sensitive information in error messages

## Performance Guidelines

### Memory Management
- **Large datasets**: Use iterators and generators for large data processing
- **Caching**: Implement appropriate TTL-based caching strategies
- **Resource cleanup**: Properly close files, connections, and other resources

### API Optimization
- **Batch operations**: Use Microsoft Graph batch endpoints where beneficial
- **Pagination**: Handle large result sets efficiently
- **Rate limiting**: Implement intelligent backoff for API quotas