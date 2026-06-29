#!/usr/bin/env bash
set -euo pipefail

ROLE="${HOLON_ROLE:-}"

case "$ROLE" in
    intent-creator)
        exec python3 -m sandbox_executor.entrypoint.intent_creator "$@"
        ;;
    planner)
        exec python3 -m sandbox_executor.entrypoint.planner "$@"
        ;;
    executor)
        exec python3 -m sandbox_executor.entrypoint.executor "$@"
        ;;
    *)
        # If no role, allow running arbitrary commands (like ls or bash)
        exec "$@"
        ;;
esac
