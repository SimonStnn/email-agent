import logging
from typing import Any, cast

from langchain_core.messages import HumanMessage, SystemMessage
from mcp_server import mcp
from model import model
from pydantic import BaseModel, Field
from utils import get_categories, get_system_prompt

logger = logging.getLogger(__name__)


def classify_message(message: str) -> str:
    """
    Classify a message into one of the predefined categories.
    """
    classifications = get_categories()
    categories = [c.category for c in classifications]

    class __Category(BaseModel):
        """A movie with details."""

        reason: str = Field(description="Reason for the classification")
        category: str = Field(
            description="The category assigned",
            json_schema_extra={"enum": cast(list[Any], categories)},
        )

    message = (message or "").strip()
    if not message:
        return "Other"

    guide = "\n".join(
        [
            "Valid categories:",
            "",
            *[f"- **{item.category}**: {item.description}" for item in classifications],
        ]
    )
    prompt_messages = [
        SystemMessage(content=f"{get_system_prompt()}\n\n{guide}."),
        HumanMessage(content=f"Email to classify:\n{message}"),
    ]
    model_with_structure = model.with_structured_output(__Category)
    response = __Category.model_validate(model_with_structure.invoke(prompt_messages))

    return response.category


mcp.tool()(get_categories)


# Expose classification as an MCP tool
mcp.tool()(classify_message)
