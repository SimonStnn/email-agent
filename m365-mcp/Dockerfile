FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    libsqlcipher-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

COPY pyproject.toml ./

RUN uv sync --no-install-project --no-dev

COPY . .

RUN uv sync --no-dev

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8400

CMD ["uv", "run", "m365-mcp"]
