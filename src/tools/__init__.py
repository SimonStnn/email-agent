from langchain.tools import tool  # , ToolRuntime


@tool
def get_weather_for_location(city: str) -> str:
    """Get weather for a given city."""
    return f"It's always sunny in {city}!"
