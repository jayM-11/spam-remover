# Repository Guidelines

## Project Structure & Module Organization

This Python 3.11+ project runs an always-on Discord moderation bot. Source lives in `spam_remover/`: `bot.py` handles gateway events, `config.py` loads typed environment settings, `moderation.py` performs actions and sends notices, and `views.py` implements officer buttons. Keep event handlers thin and place behavior in the relevant module.

`detection/rules.py` provides the rule pre-filter, `detection/llm.py` wraps Claude, and `detection/classifier.py` orchestrates them. Rules catch obvious spam without an API call; all remaining eligible messages reach the LLM, regardless of join age. Tests live in `tests/`; deployment uses the root `Dockerfile`. There is no separate assets directory.

## Build, Test, and Development Commands

- `uv sync --extra dev`: install runtime and test dependencies from the project configuration and lockfile.
- `uv run python -m spam_remover.bot`: start the bot using local environment settings. The installed `spam-remover` command is another entry point.
- `uv run pytest -v`: run the full offline suite.
- `uv run pytest tests/test_rules.py -v`: run focused detection tests.
- `docker build -t spam-remover .`: build the deployment image.
- `docker run --env-file .env --restart unless-stopped spam-remover`: run the container with local configuration.

## Coding Style & Naming Conventions

Follow existing Python style: four-space indentation, `snake_case` functions and modules, `PascalCase` classes, and `UPPER_CASE` constants. Use type annotations for production interfaces, concise docstrings, and asynchronous functions for Discord/API operations. Keep rules pure and external services injectable for testing. No formatter or linter is currently configured.

## Testing Guidelines

Use `pytest` and `pytest-asyncio`; async tests run automatically through `asyncio_mode = "auto"` in `pyproject.toml`. Name files `test_<module>.py` and functions `test_<behavior>`. Mock Discord objects and use fake judges; tests require neither tokens nor network access. Cover changed behavior, especially LLM short-circuits, dry-run actions, permission checks, and repeated button actions. No numeric coverage threshold is configured; all tests should pass before review.

## Commit & Pull Request Guidelines

History currently contains one descriptive initial commit, so no established commit convention exists. Use short, imperative subjects describing the change. Pull requests should explain the behavior and motivation, link relevant issues, and report test commands and results. Include screenshots when changing officer notices or buttons.

## Security & Configuration

Copy `.env.example` to `.env` and supply credentials locally; never commit tokens or `.env`. Document new settings in both `.env.example` and `README.md`. Keep `DRY_RUN=true` while validating detection, and use a throwaway server for live moderation checks.
