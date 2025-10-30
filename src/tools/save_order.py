from datetime import datetime
from pathlib import Path

# from langchain.tools import tool
from pydantic import BaseModel

ROOT = Path(__file__).parent.parent.resolve()


ORDERS_PATH = ROOT.parent / "downloads" / "sales_orders"
ORDERS_PATH.mkdir(parents=True, exist_ok=True)

OrderID = str


class Item(BaseModel):
    name: str
    quantity: int


class Order(BaseModel):
    item: list[Item]
    customer_name: str
    address: str
    email: str


class OrderConfirmation(BaseModel):
    order_path: str
    order_id: OrderID
    success: bool


def save_order(order: Order) -> OrderConfirmation:
    """
    Save an order into the database.
    """
    # Placeholder implementation: write to a timestamped .json file under downloads/sales_orders
    safe_name = datetime.now().isoformat().replace(":", "-")
    path = ORDERS_PATH.joinpath(f"{safe_name}.json")
    path.write_text(order.model_dump_json(), encoding="utf-8")

    return OrderConfirmation(
        order_path=path.as_posix(),
        order_id=safe_name,
        success=path.exists(),
    )


def verify_order(order_id: OrderID) -> bool:
    """
    Verify if an order with the given ID exists.
    """
    # Placeholder implementation: check if any file contains the order_id
    for order_file in ORDERS_PATH.glob("*.json"):
        content = order_file.read_text(encoding="utf-8")
        if order_id in content:
            return True
    return False
