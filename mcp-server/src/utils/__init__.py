import json
from pathlib import Path

from pydantic import BaseModel, RootModel

CONFIG_DIR = Path(__file__).parent.parent.parent / "config"
CONFIG_CLASSIFICATIONS = CONFIG_DIR / "classification" / "classification.json"
CONFIG_SYSTEM_PROMPT = CONFIG_DIR / "model" / "system_prompt.md"

for path in [CONFIG_CLASSIFICATIONS, CONFIG_SYSTEM_PROMPT]:
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")


class Category(BaseModel):
    category: str
    description: str


class __Categories(RootModel[list[Category]]):
    pass


def get_categories() -> list[Category]:
    """Load classification categories from the configuration file."""
    data = json.loads(CONFIG_CLASSIFICATIONS.read_text(encoding="utf-8"))
    return __Categories.model_validate(
        data,
        strict=True,
    ).root


def get_system_prompt() -> str:
    return CONFIG_SYSTEM_PROMPT.read_text(encoding="utf-8")
