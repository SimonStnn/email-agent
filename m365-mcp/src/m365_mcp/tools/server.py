from ..mcp_instance import mcp
from importlib.metadata import version, PackageNotFoundError


# server_get_version
@mcp.tool(
    name="server_get_version",
    annotations={
        "title": "Get Server Version",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
    meta={"category": "server", "safety_level": "safe"},
)
def server_get_version() -> dict[str, str]:
    """📖 Get the version of the m365-mcp server (read-only, safe for unsupervised use)

    Returns the current version of the m365-mcp server that is running.
    Useful for diagnostics, troubleshooting, and ensuring compatibility.

    Returns:
        Dictionary containing:
        - version: The semantic version string (e.g., "0.1.3")
        - package: The package name ("m365-mcp")

    Example:
        >>> server_get_version()
        {"version": "0.1.3", "package": "m365-mcp"}
    """
    try:
        pkg_version = version("m365-mcp")
    except PackageNotFoundError:
        # Fallback for development environments where package isn't installed
        pkg_version = "dev"

    return {
        "package": "m365-mcp",
        "version": pkg_version,
    }
