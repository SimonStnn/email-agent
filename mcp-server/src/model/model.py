import sys
from pathlib import Path

from dotenv import load_dotenv

# from langchain.tools import tool
from langchain_openai import AzureChatOpenAI

load_dotenv()

# Allow running this script directly: ensure the workspace root is on sys.path so
# `from src.config import settings` works whether the package is imported or the
# script is executed as `python test_scripts/pinecone_connection.py`.
ROOT = Path(__file__).parent.parent.resolve()
if ROOT not in sys.path:
    sys.path.insert(0, ROOT.as_posix())


model = AzureChatOpenAI(
    azure_deployment="gpt-5-mini",
    # reasoning=None,
    # temperature=0.7,
)
