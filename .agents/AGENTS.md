# Behavioral Rules for Holon Agentic Coder

- **Pytest execution**: Always execute `pytest` commands using `uv run pytest` (e.g., `uv run pytest <args>`) to ensure
  environment consistency and dependencies are resolved correctly.
- **Cleaning virtual environments**: If the virtual environment/stale code requires cleanup, always run
  `uv run task clean` instead of manually removing `.venv` or cache directories yourself.
