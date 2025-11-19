from const import CERM_AZURE_SERVER_NAME, CERM_MCP_SERVER_NAME
from langchain_mcp_adapters.client import MultiServerMCPClient

client = MultiServerMCPClient(
    {
        CERM_MCP_SERVER_NAME: {
            "transport": "streamable_http",
            "url": "http://127.0.0.1:8000/mcp",
        },
        CERM_AZURE_SERVER_NAME: {
            "transport": "streamable_http",
            "url": "http://127.0.0.1:8400/mcp",
        },
    },
)
