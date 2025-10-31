from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import BaseTool
from langchain_mcp_adapters.tools import load_mcp_tools
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


async def load_tools() -> list[BaseTool]:
    async with mcp_client.session(CERM_MCP_SERVER_NAME) as session:
        tools = await load_mcp_tools(session)
    return tools


_mcp_session = None
_mcp_session_ctx = None
tools: list[BaseTool] = []
Agent = Any
agent: Agent | None = None


async def init_agent() -> None:
    """Initialize the MCP session, load tools, and create the agent.

    This must be called from application startup code (not at module import)
    so that the MCP session's lifecycle is managed by the application.
    """
    global _mcp_session, tools, agent

    # Enter and keep the session active until shutdown_agent() is called.
    session_ctx = mcp_client.session(CERM_MCP_SERVER_NAME)
    # Keep both the context manager (ctx) and the entered session object so we
    # can call the correct __aexit__ on the context manager during shutdown.
    global _mcp_session_ctx
    _mcp_session_ctx = session_ctx
    _mcp_session = await _mcp_session_ctx.__aenter__()
    tools = await load_mcp_tools(_mcp_session)

    agent = create_agent(
        model=model,
        # system_prompt=system_prompt,
        tools=tools,
    )


async def shutdown_agent() -> None:
    """Shutdown the MCP session and clear agent state."""
    global _mcp_session, agent, tools
    global _mcp_session_ctx
    if _mcp_session_ctx is not None:
        # exit the session context we entered in `init_agent`
        await _mcp_session_ctx.__aexit__(None, None, None)
        _mcp_session_ctx = None
        _mcp_session = None
    agent = None
    tools = []


async def invoke_agent(messages: list[Any]) -> tuple[Any, list[Any]]:
    """Invoke the agent with the given messages and process the response.

    The agent must be initialized via `init_agent()` before calling this.
    """
    if agent is None:
        raise RuntimeError("Agent not initialized. Call init_agent() first.")

    result = await agent.ainvoke({"messages": messages})  # type: ignore[arg-type]
    return result, messages
