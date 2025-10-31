import asyncio
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_mcp_adapters.tools import load_mcp_tools

# from langchain_core.tools import BaseTool
from langchain_ollama import ChatOllama

# from langchain_openai import AzureChatOpenAI
from pydantic import BaseModel

from const import CERM_MCP_SERVER_NAME

from .mcp_client import client as mcp_client

load_dotenv()

ROOT = Path(__file__).parent.parent.parent.resolve()
AGENT_PATH = ROOT / "config" / "agent"
AGENT_CONF = AGENT_PATH / "system_prompt.md"


class ResearchResponse(BaseModel):
    topic: str
    summary: str
    sources: list[str]
    tools_used: list[str]


model = ChatOllama(
    model="gpt-oss:20b",
    reasoning=None,
    temperature=0.7,
)
# model = AzureChatOpenAI(
#     azure_deployment="gpt-5-mini",
#     # reasoning=None,
#     # temperature=0.7,
# )
parser = PydanticOutputParser(pydantic_object=ResearchResponse)

system_prompt = (
    "You are an AI research assistant that helps users gather information on various topics using available tools."
)
# system_prompt = AGENT_CONF.read_text(encoding="utf-8").strip()

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


async def load_tools() -> list[Any]:
    async with mcp_client.session(CERM_MCP_SERVER_NAME) as session:
        tools = await load_mcp_tools(session)
    return tools


Agent = Any
agent: Agent = create_agent(model=model, system_prompt=system_prompt, tools=asyncio.run(load_tools()))
