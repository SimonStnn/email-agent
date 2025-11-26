import asyncio
from pathlib import Path
from typing import Any

from const import CERM_AZURE_SERVER_NAME, CERM_MCP_SERVER_NAME
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import BaseTool
from langchain_mcp_adapters.tools import load_mcp_tools
from langchain_openai import AzureChatOpenAI
from pydantic import BaseModel

from .mcp_client import client as mcp_client

# from langchain_ollama import ChatOllama


load_dotenv()

ROOT = Path(__file__).parent.parent.parent.resolve()
AGENT_PATH = ROOT / "config" / "agent"
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

system_prompt = (
    "You are an AI research assistant that helps users gather information on various topics using available tools."
)
# system_prompt = AGENT_CONF.read_text(encoding="utf-8").strip()

prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            (f"{system_prompt}\n\n{{format_instructions}}"),
        ),
        ("placeholder", "{chat_history}"),
        ("human", "{query}"),
        ("placeholder", "{agent_scratchpad}"),
    ]
).partial(format_instructions=parser.get_format_instructions())


async def load_tools() -> list[BaseTool]:
    tools: list[BaseTool] = []
    async with mcp_client.session(CERM_MCP_SERVER_NAME) as session:
        tools.extend(await load_mcp_tools(session))
    async with mcp_client.session(CERM_AZURE_SERVER_NAME) as session:
        tools.extend(await load_mcp_tools(session))
    return tools


_mcp_session = None
_mcp_session_ctx = None
_mcp_session_task = None
_mcp_session_stop = None
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
    # Create a dedicated background task which owns the session context.
    # This ensures the `__aenter__` and `__aexit__` calls run in the same
    # asyncio Task (avoid anyio cancel scope mismatches).
    global _mcp_session_task, _mcp_session_stop, _mcp_session, _mcp_session_ctx

    if _mcp_session_task is not None:
        # Already initialized
        return

    _mcp_session_stop = asyncio.Event()

    async def session_runner():
        global _mcp_session, _mcp_session_ctx, tools
        session_ctx_local = mcp_client.session(CERM_MCP_SERVER_NAME)
        session_ctx_m365 = mcp_client.session(CERM_AZURE_SERVER_NAME)
        _mcp_session_ctx = session_ctx_local
        try:
            _mcp_session = await session_ctx_local.__aenter__()
            _mcp_m365_session = await session_ctx_m365.__aenter__()
            # load tools while session is active
            tools_local = await load_mcp_tools(_mcp_session)
            tools_local += await load_mcp_tools(_mcp_m365_session)
            # store the tools for use by the agent
            tools = tools_local
            # Wait until shutdown is signaled
            if _mcp_session_stop is not None:
                await _mcp_session_stop.wait()
        finally:
            # ensure __aexit__ is called in the same task
            await session_ctx_local.__aexit__(None, None, None)

    _mcp_session_task = asyncio.create_task(session_runner())

    # Give the runner a moment to enter and populate the session to avoid
    # racing when init_agent is awaited followed by immediate use.
    while _mcp_session is None:
        await asyncio.sleep(0.01)
    # Wait for the session runner to load tools
    while not tools:
        await asyncio.sleep(0.01)

    agent = create_agent(
        model=model,
        # system_prompt=system_prompt,
        tools=tools,
    )


async def shutdown_agent() -> None:
    """Shutdown the MCP session and clear agent state."""
    global _mcp_session, agent, tools
    global _mcp_session_ctx
    global _mcp_session_task, _mcp_session_stop, _mcp_session_ctx, _mcp_session

    if _mcp_session_task is None:
        return

    # Signal the session runner to stop and wait for it to finish.
    if _mcp_session_stop is not None:
        _mcp_session_stop.set()

    # Await the background task finishing; it will call __aexit__ itself
    await _mcp_session_task
    _mcp_session_task = None
    _mcp_session_stop = None
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

    # type: ignore[arg-type]
    result = await agent.ainvoke({"messages": messages})
    return result, messages
