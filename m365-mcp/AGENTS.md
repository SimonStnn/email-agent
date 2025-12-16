# Repository Guidelines

## Steering Documents: (ADHERE TO THESE STRICTLY)
- .projects/steering/mcp-server.md
- .projects/steering/product.md
- .projects/steering/python.md
- .projects/steering/structure.md
- .projects/steering/tech.md
- .projects/steering/tool-names.md
- 
## Project Structure & Module Organization
- Primary package lives in `src/microsoft_mcp/` with `server.py` as the CLI entrypoint and `auth.py`, `graph.py`, and `tools.py` providing authentication, Graph client, and tool registry layers.
- Integration and regression tests reside in `tests/` and the root-level `test_fix.py`; keep new suites parallel to the feature folders they exercise.
- CLI utilities and verification helpers (`authenticate.py`, `verify_*.py`, `verify_rule_tools.py`) sit at the repository root for direct invocation.
- Documentation and operational references are in `README.md`, `QUICKSTART.md`, `SECURITY.md`, and `FILETREE.md`; update the matching file when changing behavior or setup expectations.

## Build, Test, and Development Commands
- `uv sync` installs all runtime and dev dependencies defined in `pyproject.toml` / `uv.lock`.
- `uv run microsoft-mcp` launches the MCP server and respects transport env vars such as `MCP_TRANSPORT=http`.
- `uv run authenticate.py` walks through the device-code flow to seed the local token cache.
- `uv run pytest tests/ -v` executes the integration suite; add `-k name` for targeted runs.
- `uv run pyright` performs type checking, while `uvx ruff format .` and `uvx ruff check --fix --unsafe-fixes .` enforce formatting and lint rules.

## Coding Style & Naming Conventions
- Target Python 3.12+ with full type hints on public functions; mirror the explicit return annotations used in `server.py`.
- Use four-space indentation, wrap domain logic by tool family, and favor short helper functions over deeply nested conditionals.
- Follow `snake_case` for functions, variables, and module-level constants; reserve `PascalCase` for any classes introduced later.
- Prefer async-aware patterns when extending tool handlers and include concise docstrings to describe side effects or external calls.
- Run Ruff prior to commits to maintain import ordering and statement formatting consistency.

## Testing Guidelines
- Pytest is the canonical framework; place new files under `tests/` as `test_<feature>.py` and ensure function names describe expected outcomes (e.g., `test_list_emails_returns_paged_results`).
- Cover both stdio and HTTP transports where applicable, and exercise multi-account flows that depend on `account_id`.
- Use the existing verification scripts (`verify_implementation.py`, `verify_email_tools.py`, etc.) for additional regression checks when modifying related subsystems.
- Include fixtures or recorded responses sparingly; prefer lightweight factories that mock Microsoft Graph payloads.

## Commit & Pull Request Guidelines
- Mirror the Git history style: concise, present-tense subjects capped around 72 characters (`Enhances bearer token authentication in FastAPI server`).
- Keep commits focused on a single concern and update documentation or configuration files alongside code changes.
- Pull requests should outline scope, highlight authentication/transport impacts, link tracking issues, and embed screenshots or logs when adjusting HTTP behavior.
- Run Ruff, Pyright, and the pytest suite before submitting; note any intentionally skipped checks in the PR description.

## Security & Configuration Tips
- Copy `.env.example` to `.env`, set `M365_MCP_CLIENT_ID`, and avoid committing secrets or local token caches.
- Generate bearer tokens for HTTP transport with `openssl rand -hex 32` and rotate them when sharing environments.
- When testing new accounts, clear or back up `~/.m365_mcp_token_cache.json` to avoid leaking credentials between runs.
