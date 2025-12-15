FROM python:3.12-slim

# 1. Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# 2. Install System Dependencies (Required for sqlcipher3)
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    libsqlcipher-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# 3. Install dependencies ONLY (Layer 1)
# We copy pyproject.toml and uv.lock.
# We DO NOT copy README.md yet.
COPY pyproject.toml ./

# CRITICAL FIX: --no-install-project
# This tells uv: "Don't read pyproject.toml metadata or look for README yet, just give me the libraries."
RUN uv sync --frozen --no-install-project --no-dev

# 4. Install the project (Layer 2)
# Now we copy everything, including README.md and src/
COPY . .

# Now we run sync again to install the actual project 'm365-mcp'
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8400

CMD ["uv", "run", "m365-mcp"]
