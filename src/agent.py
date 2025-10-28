from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate

# from langchain_ollama import ChatOllama
from langchain_openai import AzureChatOpenAI
from pydantic import BaseModel

from tools import classify_message, save_order

load_dotenv()

ROOT = Path(__file__).parent.resolve()
AGENT_PATH = ROOT.parent / "config" / "agent"
AGENT_CONF = AGENT_PATH / "system_prompt.md"


class ResearchResponse(BaseModel):
    topic: str
    summary: str
    sources: list[str]
    tools_used: list[str]


# model = ChatOllama(
#     model="gpt-oss:20b",
#     reasoning=None,
#     temperature=0.7,
# )
model = AzureChatOpenAI(
    azure_deployment="gpt-5-mini",
    # reasoning=None,
    # temperature=0.7,
)
parser = PydanticOutputParser(pydantic_object=ResearchResponse)

system_prompt = AGENT_CONF.read_text(encoding="utf-8").strip()

prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            (f"{system_prompt}" "\n\n{format_instructions}"),
        ),
        ("placeholder", "{chat_history}"),
        ("human", "{query}"),
        ("placeholder", "{agent_scratchpad}"),
    ]
).partial(format_instructions=parser.get_format_instructions())

tools = [classify_message, save_order]

Agent = Any
agent: Agent = create_agent(model=model, tools=tools, system_prompt=system_prompt)
