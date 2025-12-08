"""
Microsoft MCP Tools Registry

This module serves as the central registry for all Microsoft MCP tools.
It imports the FastMCP instance from mcp_instance and imports all tool modules
to ensure all tools are registered with the same instance.

The actual tool implementations are in the tools/ subdirectory, organized by category:
- tools/account.py - Account management (3 tools)
- tools/calendar.py - Calendar operations (6 tools)
- tools/contact.py - Contact management (5 tools)
- tools/email.py - Email operations (9 tools)
- tools/email_folders.py - Email folder navigation (3 tools)
- tools/email_rules.py - Email rule management (9 tools)
- tools/file.py - OneDrive file operations (5 tools)
- tools/folder.py - OneDrive folder navigation (3 tools)
- tools/search.py - Search operations (5 tools)

Total: 50 tools across 9 modules
"""

# Import the mcp instance
from .mcp_instance import mcp

# Import all tool modules - this triggers tool registration via @mcp.tool decorators
# The tools themselves are defined in the tools/ subdirectory

# Export the mcp instance for use by server.py
__all__ = ["mcp"]
