import os
from typing import cast
from urllib.parse import urlparse

import dotenv
from langchain_mcp_adapters.client import (
    MultiServerMCPClient,
    SSEConnection,
    StdioConnection,
    StreamableHttpConnection,
    WebsocketConnection,
)

dotenv.load_dotenv(verbose=True)

URLS = os.getenv("AGENT_MCP_URLS")

if not URLS:
    raise ValueError("AGENT_MCP_URLS environment variable is not set.")

_connections = {}
for i, url in enumerate(URLS.split(",")):
    parsed_uri = urlparse(url.strip())
    result = "{uri.netloc}".format(uri=parsed_uri)
    name = f"{i + 1:0>2}_{result}"
    _connections[name] = StreamableHttpConnection(url=url, transport="streamable_http")

client = MultiServerMCPClient(
    connections=cast(
        dict[str, StdioConnection | SSEConnection | StreamableHttpConnection | WebsocketConnection], _connections
    )
)
