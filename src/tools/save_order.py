from datetime import datetime
from pathlib import Path

from langchain.tools import tool

ROOT = Path(__file__).parent.parent.resolve()


ORDERS_PATH = ROOT.parent / "downloads" / "sales_orders"
ORDERS_PATH.mkdir(parents=True, exist_ok=True)


@tool
def save_order(order: str) -> str:
    """
    Save an order into the database.
    """
    # Placeholder implementation
    ORDERS_PATH.joinpath(f"{datetime.now().isoformat()}.txt").write_text(order, encoding="utf-8")
    return f"Order '{order}' has been saved successfully."
