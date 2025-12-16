import os

from mcp.server.fastmcp import FastMCP

# Allow configuring host/port via environment variables. Default to 0.0.0.0:8000
_host = os.environ.get("MCP_HOST", "0.0.0.0")
try:
    _port = int(os.environ.get("MCP_PORT", "8000"))
except ValueError:
    _port = 8000

mcp = FastMCP("CERM MCP Server", "0.1.0", host=_host, port=_port)
