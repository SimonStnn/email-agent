import json
from pathlib import Path

# from langchain_core.language_models import BaseLanguageModel
# from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, RootModel

ROOT = Path(__file__).parent.parent.resolve()
CLASSIFICATIONS_PATH = ROOT.parent / "config" / "classification"
CLASSIFICATIONS_CONF = CLASSIFICATIONS_PATH / "classification.json"
CLASSIFICATIONS_PROMPT = CLASSIFICATIONS_PATH / "system_prompt.md"

if not CLASSIFICATIONS_CONF.exists() or not CLASSIFICATIONS_PROMPT.exists():
    raise FileNotFoundError(
        f"Classification configuration files not found in {CLASSIFICATIONS_PATH}. Please ensure that '{CLASSIFICATIONS_CONF.name}' and '{CLASSIFICATIONS_PROMPT.name}' exist."
    )


class Category(BaseModel):
    category: str
    description: str


class __Categories(RootModel[list[Category]]):
    pass


def get_categories() -> list[Category]:
    """Load classification categories from the configuration file."""
    data = json.loads(CLASSIFICATIONS_CONF.read_text(encoding="utf-8"))
    return __Categories.model_validate(
        data,
        strict=True,
    ).root


if __name__ == "__main__":
    from rich import print

    print(get_categories())
