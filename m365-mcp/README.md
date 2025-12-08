# M365 MCP

Powerful MCP server for Microsoft Graph API - a complete AI assistant toolkit for Outlook, Calendar, OneDrive, and Contacts.

## Features

- **Email Management**: Read, send, reply, manage attachments, organize folders
- **Calendar Intelligence**: Create, update, check availability, respond to invitations
- **OneDrive Files**: Upload, download, browse with pagination
- **Contacts**: Search and list contacts from your address book
- **Multi-Account**: Support for multiple Microsoft accounts (personal, work, school)
- **Unified Search**: Search across emails, files, events, and people
- **⚡ High-Performance Caching**: AES-256 encrypted cache with 300x performance improvement
- **🔒 Security & Compliance**: GDPR and HIPAA compliant data encryption at rest

## Quick Start

**📚 See [QUICKSTART.md](QUICKSTART.md) for complete installation and setup guide.**

### TL;DR

```bash
# 1. Install
git clone https://github.com/robin-collins/m365-mcp.git
cd m365-mcp && uv sync

# 2. Configure (use .env.example template)
cp .env.example .env
# Edit .env with your M365_MCP_CLIENT_ID

# 3. Authenticate
uv run authenticate.py

# 4. Run
uv run m365-mcp
```

### Claude Desktop

```bash
# Add M365 MCP server (replace with your Azure app ID)
claude mcp add m365-mcp -e M365_MCP_CLIENT_ID=your-app-id-here -- uvx --from git+https://github.com/robin-collins/m365-mcp.git m365-mcp

# Start Claude Desktop
claude
```

### Usage Examples

```bash
# Email examples
> read my latest emails with full content
> reply to the email from John saying "I'll review this today"
> send an email with attachment to alice@example.com

# Calendar examples  
> show my calendar for next week
> check if I'm free tomorrow at 2pm
> create a meeting with Bob next Monday at 10am

# File examples
> list files in my OneDrive
> upload this report to OneDrive
> search for "project proposal" across all my files

# Multi-account
> list all my Microsoft accounts
> send email from my work account
```

## Available Tools

### Email Tools
- **`list_emails`** - List emails with optional body content
- **`get_email`** - Get specific email with attachments
- **`create_email_draft`** - Create email draft with attachments support
- **`send_email`** - Send email immediately with CC/BCC and attachments
- **`reply_to_email`** - Reply maintaining thread context
- **`reply_all_email`** - Reply to all recipients in thread
- **`update_email`** - Mark emails as read/unread
- **`move_email`** - Move emails between folders
- **`delete_email`** - Delete emails
- **`get_attachment`** - Get email attachment content
- **`search_emails`** - Search emails by query

### Calendar Tools
- **`list_events`** - List calendar events with details
- **`get_event`** - Get specific event details
- **`create_event`** - Create events with location and attendees
- **`update_event`** - Reschedule or modify events
- **`delete_event`** - Cancel events
- **`respond_event`** - Accept/decline/tentative response to invitations
- **`check_availability`** - Check free/busy times for scheduling
- **`search_events`** - Search calendar events

### Contact Tools
- **`list_contacts`** - List all contacts
- **`get_contact`** - Get specific contact details
- **`create_contact`** - Create new contact
- **`update_contact`** - Update contact information
- **`delete_contact`** - Delete contact
- **`search_contacts`** - Search contacts by query

### File Tools
- **`list_files`** - Browse OneDrive files and folders
- **`get_file`** - Download file content
- **`create_file`** - Upload files to OneDrive
- **`update_file`** - Update existing file content
- **`delete_file`** - Delete files or folders
- **`search_files`** - Search files in OneDrive

### Utility Tools
- **`unified_search`** - Search across emails, events, and files
- **`list_accounts`** - Show authenticated Microsoft accounts
- **`authenticate_account`** - Start authentication for a new Microsoft account
- **`complete_authentication`** - Complete the authentication process after entering device code

### Cache Management Tools
- **`cache_get_stats`** - View cache statistics (size, entries, hit rate)
- **`cache_invalidate`** - Manually invalidate cache entries by pattern
- **`cache_task_enqueue`** - Queue background cache warming tasks
- **`cache_task_status`** - Check status of queued cache tasks
- **`cache_task_list`** - List all cache tasks by account or status

## ⚡ High-Performance Caching

M365 MCP includes an intelligent caching system that dramatically improves performance by reducing redundant API calls to Microsoft Graph.

### Key Features

- **🔒 AES-256 Encryption**: All cached data encrypted at rest using SQLCipher
- **⚡ 300x Performance Boost**: Common operations like `folder_get_tree` go from 30s → <100ms
- **🧠 Intelligent TTL**: Three-state cache (Fresh/Stale/Expired) with automatic refresh
- **📦 Automatic Compression**: Large entries (≥50KB) automatically compressed (70-80% size reduction)
- **🔄 Cache Warming**: Background pre-population on startup for instant responses
- **🎯 Smart Invalidation**: Write operations automatically invalidate related caches
- **🌐 Multi-Account**: Complete isolation between different accounts
- **✅ Compliance Ready**: GDPR and HIPAA compliant data protection

### Performance Benchmarks

| Operation | Without Cache | With Cache | Speedup |
|-----------|---------------|------------|---------|
| `folder_get_tree` | 30s | <100ms | **300x** |
| `email_list` | 2-5s | <50ms | **40-100x** |
| `file_list` | 1-3s | <30ms | **30-100x** |
| Cache Hit Rate | N/A | >80% | **70%+ API call reduction** |

### Cache Configuration

The cache works automatically, but you can control its behavior:

```python
# Use cache (default - recommended)
folder_get_tree(account_id, path="/Documents")

# Force refresh (bypass cache, update with fresh data)
folder_get_tree(account_id, path="/Documents", force_refresh=True)

# Disable cache for this request only
email_list(account_id, folder="inbox", use_cache=False)
```

### Cache Security

- **Encryption**: AES-256 encryption via SQLCipher
- **Key Storage**: System keyring (macOS Keychain, Windows Credential Manager, Linux Secret Service)
- **Fallback**: Environment variable `M365_MCP_CACHE_KEY` for headless servers
- **Compliance**: GDPR Article 32 and HIPAA §164.312 compliant

### Cache Management

View cache statistics:
```python
stats = cache_get_stats()
# Returns: total_entries, size_bytes, hit_rate, oldest_entry, etc.
```

Manually invalidate cache:
```python
# Invalidate all email caches
cache_invalidate("email_*")

# Invalidate specific account's caches
cache_invalidate("email_*", account_id="account-123")
```

**📚 For complete cache documentation, see [CLAUDE.md](CLAUDE.md#cache-architecture)**

## Manual Setup

### 1. Azure App Registration

1. Go to [Azure Portal](https://portal.azure.com) → Microsoft Entra ID → App registrations
2. New registration → Name: `m365-mcp`
3. Supported account types: Personal + Work/School
4. Authentication → Allow public client flows: Yes
5. API permissions → Add these delegated permissions:
   - Mail.ReadWrite
   - Calendars.ReadWrite
   - Files.ReadWrite
   - Contacts.Read
   - People.Read
   - User.Read
6. Copy Application ID

### 2. Installation

```bash
git clone https://github.com/robin-collins/m365-mcp.git
cd m365-mcp
uv sync
```

### 3. Authentication

```bash
# Set your Azure app ID
export M365_MCP_CLIENT_ID="your-app-id-here"

# Run authentication script
uv run authenticate.py

# Follow the prompts to authenticate your Microsoft accounts
```

### 4. Claude Desktop Configuration

Add to your Claude Desktop configuration:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`  
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "microsoft": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/robin-collins/m365-mcp.git", "m365-mcp"],
      "env": {
        "M365_MCP_CLIENT_ID": "your-app-id-here"
      }
    }
  }
}
```

Or for local development:

```json
{
  "mcpServers": {
    "microsoft": {
      "command": "uv",
      "args": ["--directory", "/path/to/m365-mcp", "run", "m365-mcp"],
      "env": {
        "M365_MCP_CLIENT_ID": "your-app-id-here"
      }
    }
  }
}
```

## Transport Modes

M365 MCP supports two transport modes for different use cases:

### stdio (Default) - For Desktop Apps

**Use for:** Claude Desktop, local MCP clients

**Security:** Inherently secure through process isolation (no authentication required)

```bash
# Default mode - no configuration needed
export M365_MCP_CLIENT_ID="your-app-id"
uv run m365-mcp
```

### Streamable HTTP - For Web/API Access

**Use for:** Web applications, remote access, multi-client scenarios

**Security:** ⚠️ **Requires authentication** (bearer token or OAuth)

**Protocol:** Uses MCP Streamable HTTP (spec 2025-03-26+)

```bash
# Generate secure token
export MCP_AUTH_TOKEN=$(openssl rand -hex 32)

# Configure Streamable HTTP with bearer authentication
export M365_MCP_CLIENT_ID="your-app-id"
export MCP_TRANSPORT="http"
export MCP_AUTH_METHOD="bearer"
export MCP_HOST="127.0.0.1"
export MCP_PORT="8000"

# Start server
uv run m365-mcp
```

**Client connection:**
```python
from mcp.client.http import http_client

async with http_client(
    "http://localhost:8000/mcp",
    headers={"Authorization": f"Bearer {your_token}"}
) as (read, write):
    # Use the session...
```

**📚 See [SECURITY.md](SECURITY.md) for complete security guide and authentication options**

## Multi-Account Support

All tools require an `account_id` parameter as the first argument:

```python
# List accounts to get IDs
accounts = list_accounts()
account_id = accounts[0]["account_id"]

# Use account for operations
send_email(account_id, "user@example.com", "Subject", "Body")
list_emails(account_id, limit=10, include_body=True)
create_event(account_id, "Meeting", "2024-01-15T10:00:00Z", "2024-01-15T11:00:00Z")
```

## Development

```bash
# Run tests
uv run pytest tests/ -v

# Type checking
uv run pyright

# Format code
uvx ruff format .

# Lint
uvx ruff check --fix --unsafe-fixes .
```

## Example: AI Assistant Scenarios

### Smart Email Management
```python
# Get account ID first
accounts = list_accounts()
account_id = accounts[0]["account_id"]

# List latest emails with full content
emails = list_emails(account_id, limit=10, include_body=True)

# Reply maintaining thread
reply_to_email(account_id, email_id, "Thanks for your message. I'll review and get back to you.")

# Forward with attachments
email = get_email(email_id, account_id)
attachments = [get_attachment(email_id, att["id"], account_id) for att in email["attachments"]]
send_email(account_id, "boss@company.com", f"FW: {email['subject']}", email["body"]["content"], attachments=attachments)
```

### Intelligent Scheduling
```python
# Get account ID first
accounts = list_accounts()
account_id = accounts[0]["account_id"]

# Check availability before scheduling
availability = check_availability(account_id, "2024-01-15T10:00:00Z", "2024-01-15T18:00:00Z", ["colleague@company.com"])

# Create meeting with details
create_event(
    account_id,
    "Project Review",
    "2024-01-15T14:00:00Z", 
    "2024-01-15T15:00:00Z",
    location="Conference Room A",
    body="Quarterly review of project progress",
    attendees=["colleague@company.com", "manager@company.com"]
)
```

## Security Notes

- Tokens are cached locally in `~/.m365_mcp_token_cache.json`
- Cache data is encrypted at rest using AES-256 in `~/.m365_mcp_cache.db`
- Encryption keys stored securely in system keyring (or `M365_MCP_CACHE_KEY` env var)
- Use app-specific passwords if you have 2FA enabled
- Only request permissions your app actually needs
- Consider using a dedicated app registration for production

## Troubleshooting

- **Authentication fails**: Check your CLIENT_ID is correct
- **"Need admin approval"**: Use `M365_MCP_TENANT_ID=consumers` for personal accounts
- **Missing permissions**: Ensure all required API permissions are granted in Azure
- **Token errors**: Delete `~/.m365_mcp_token_cache.json` and re-authenticate
- **Cache issues**: Delete `~/.m365_mcp_cache.db` to reset cache (encryption key will regenerate)
- **Slow first requests**: Normal - cache warming runs in background, subsequent requests are fast

## License

MIT