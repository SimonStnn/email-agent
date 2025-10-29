import random

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("cerm-mcp")


@mcp.tool()
def dice_roll(sides: int, dices: int) -> str:
    """Roll a dice with given sides and number of dices."""
    results = [str(random.randint(1, sides)) for _ in range(dices)]
    return ", ".join(results)


if __name__ == "__main__":
    mcp.run()
