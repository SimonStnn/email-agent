from mcp_server import mcp
from tools import *  # noqa: F401 F403 # import all registered tools

if __name__ == "__main__":
    mcp.run(transport="streamable-http")
