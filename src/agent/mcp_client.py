from langchain_mcp_adapters.client import MultiServerMCPClient

from const import CERM_MCP_SERVER_NAME

client = MultiServerMCPClient(
    {
        CERM_MCP_SERVER_NAME: {
            "transport": "streamable_http",
            "url": "http://127.0.0.1:8000/mcp",
        }
    }
)
