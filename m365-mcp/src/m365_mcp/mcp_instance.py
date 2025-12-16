"""
Microsoft MCP Instance

This module contains the single FastMCP instance that all tools register with.
It's separated into its own module to avoid circular import issues.
"""

from fastmcp import FastMCP

# Create the single FastMCP instance that all tools will register with
mcp = FastMCP("microsoft-mcp")

__all__ = ["mcp"]
