#!/usr/bin/env bash
set -euo pipefail

ROLE="${HOLON_ROLE:-}"

case "$ROLE" in
    intent-creator)
        exec python3 /home/holon/entrypoints/intent_creator.py "$@"
        ;;
    planner)
        exec python3 /home/holon/entrypoints/planner.py "$@"
        ;;
    executor)
        exec python3 /home/holon/entrypoints/executor.py "$@"
        ;;
    *)
        # If no role, allow running arbitrary commands (like ls or bash)
        exec "$@"
        ;;
esac
