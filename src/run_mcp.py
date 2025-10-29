import sys

import mcpo

if __name__ == "__main__":
    sys.argv = ["mcpo", "--port", "8000", "--", "python", "src/mcp_server.py"]
    mcpo.main()
