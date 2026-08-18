# Behavioral Rules for Holon Agentic Coder

- **Pytest execution**: Always execute `pytest` commands using `uv run pytest` (e.g., `uv run pytest <args>`) to ensure
  environment consistency and dependencies are resolved correctly.
- **Single Root Virtual Environment**: Always execute all `uv` and Python commands strictly from the repository root
  directory. Never run `uv` commands with a working directory inside subfolders (e.g. `apps/sandbox-executor/`). Virtual
  environments must exist exclusively at the root `.venv`.
- **Cleaning virtual environments**: If the virtual environment/stale code requires cleanup, always run
  `uv run task clean` instead of manually removing `.venv` or cache directories yourself.
