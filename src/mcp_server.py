from mcp.server.fastmcp import FastMCP

from tools import Classification, Order, OrderConfirmation
from tools import classify_message as tool_classify_message
from tools import get_classifications as tool_get_classifications
from tools import save_order as tool_save_order
from tools import verify_order as tool_verify_order

mcp = FastMCP("cerm-mcp")


@mcp.tool()
def classify_message(message: str) -> str:
    """Classify the given message and return the classification result."""
    return tool_classify_message(message)


@mcp.tool()
def save_order(order_data: Order) -> OrderConfirmation:
    """Save the given order data and return a success message."""
    return tool_save_order(order_data)


@mcp.tool()
def verify_order(order_id: str) -> bool:
    """Verify the given order ID."""
    # Simulate order verification logic
    return tool_verify_order(order_id)


@mcp.tool()
def get_classifications() -> list[Classification]:
    """Get the list of all classifications."""
    return tool_get_classifications()


if __name__ == "__main__":
    mcp.run()
