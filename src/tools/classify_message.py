import json
import logging
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

from langchain.tools import tool
from langchain_core.language_models import BaseLanguageModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, RootModel

# Allow running this script directly: ensure the workspace root is on sys.path so
# `from src.config import settings` works whether the package is imported or the
# script is executed as `python test_scripts/pinecone_connection.py`.
ROOT = Path(__file__).parent.parent.resolve()
if ROOT not in sys.path:
    sys.path.insert(0, ROOT.as_posix())


CLASSIFICATIONS_PATH = ROOT.parent / "config" / "classification"
CLASSIFICATIONS_CONF = CLASSIFICATIONS_PATH / "classification.json"
CLASSIFICATIONS_PROMPT = CLASSIFICATIONS_PATH / "system_prompt.md"

if not CLASSIFICATIONS_CONF.exists() or not CLASSIFICATIONS_PROMPT.exists():
    raise FileNotFoundError(
        f"Classification configuration files not found in {CLASSIFICATIONS_PATH}. Please ensure that '{CLASSIFICATIONS_CONF.name}' and '{CLASSIFICATIONS_PROMPT.name}' exist."
    )


class Classification(BaseModel):
    category: str
    description: str


class __Classifications(RootModel[list[Classification]]):
    pass


logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_classifications() -> list[Classification]:
    data = json.loads(CLASSIFICATIONS_CONF.read_text(encoding="utf-8"))
    return __Classifications.model_validate(data).root


@lru_cache(maxsize=1)
def _get_model() -> BaseLanguageModel:
    try:
        from agent import model  # local import to avoid circular dependency
    except ImportError as exc:  # pragma: no cover - defensive logging
        raise RuntimeError("Classification model is unavailable; ensure agent.model is initialized") from exc
    return model


@lru_cache(maxsize=1)
def _system_prompt() -> str:
    return CLASSIFICATIONS_PROMPT.read_text(encoding="utf-8").strip()


def _extract_response_text(raw: Any) -> str:
    if raw is None:
        return ""

    if hasattr(raw, "content"):
        raw = raw.content

    if isinstance(raw, str):
        return raw.strip()

    if isinstance(raw, list):
        parts: list[str] = []
        for item in raw:
            parts.append(_extract_response_text(item))
        return " ".join(parts).strip()

    return str(raw).strip()


def _normalize(text: str) -> str:
    return text.strip().lower()


def _pick_category(response_text: str, categories: list[str]) -> str:
    if not response_text:
        return "Other"

    normalized_map = {_normalize(category): category for category in categories}

    # Try JSON parsing first
    try:
        parsed = json.loads(response_text)
    except json.JSONDecodeError:
        parsed = None

    if isinstance(parsed, dict):
        for key in ("category", "label", "result"):
            value = parsed.get(key)
            if isinstance(value, str) and _normalize(value) in normalized_map:
                return normalized_map[_normalize(value)]
    elif isinstance(parsed, list):
        for item in parsed:
            if isinstance(item, str) and _normalize(item) in normalized_map:
                return normalized_map[_normalize(item)]
            if isinstance(item, dict):
                value = item.get("category") or item.get("label") or item.get("result")
                if isinstance(value, str) and _normalize(value) in normalized_map:
                    return normalized_map[_normalize(value)]

    # Check first non-empty line
    for line in response_text.splitlines():
        candidate = _normalize(line.strip("`\"' "))
        if candidate in normalized_map:
            return normalized_map[candidate]

    lowered = response_text.lower()
    for category in categories:
        if category.lower() in lowered:
            return category

    return "Other"


@tool
def classify_message(message: str) -> str:
    """
    Classify a message into one of the predefined categories.
    """
    classifications = get_classifications()
    categories = [c.category for c in classifications]

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
        SystemMessage(content=f"{_system_prompt()}\n\n{guide}."),
        HumanMessage(content=f"Email to classify:\n{message}"),
    ]

    try:
        response = _get_model().invoke(prompt_messages)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception("Failed to classify message via model: %s", exc)
        return "Other"

    response_text = _extract_response_text(response)
    category = _pick_category(response_text, categories)

    if category == "Other" and response_text:
        logger.info("Model returned '%s', falling back to 'Other'", response_text)

    return category


if __name__ == "__main__":
    from rich import print

    print(get_classifications())
