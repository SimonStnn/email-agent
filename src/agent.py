from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate

# from langchain_ollama import ChatOllama
from langchain_openai import AzureChatOpenAI
from pydantic import BaseModel

from tools import get_weather_for_location

load_dotenv()


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


prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
                You are a research assistant that will help generate a research paper.
                Answer the user query and use neccessary tools.
                Wrap the output in this format and provide no other text\n{format_instructions}
                """,
        ),
        ("placeholder", "{chat_history}"),
        ("human", "{query}"),
        ("placeholder", "{agent_scratchpad}"),
    ]
).partial(format_instructions=parser.get_format_instructions())

tools = [get_weather_for_location]

agent = create_agent(model=model, tools=tools)
