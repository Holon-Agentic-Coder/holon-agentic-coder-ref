#!/usr/bin/env bash
set -euo pipefail


# Extract key from ephemeral secret bundle if present
SECRET_BUNDLE="${HOLON_SECRET_BUNDLE_PATH:-/run/secrets/holon_auth.json}"
if [ -f "$SECRET_BUNDLE" ] && command -v jq &>/dev/null; then
    BUNDLE_AGENT=$(jq -r '.agent_id // ""' "$SECRET_BUNDLE" | tr '[:upper:]' '[:lower:]')
    BUNDLE_AGENT_ID="${BUNDLE_AGENT//-agent/}"
    BUNDLE_AGENT_ID="${BUNDLE_AGENT_ID//agent-/}"
    
    TARGET_AGENT_ID=$(echo "${HOLON_AGENT_ID:-}" | tr '[:upper:]' '[:lower:]' | sed 's/-agent//g' | sed 's/agent-//g')
    
    if [ -z "$BUNDLE_AGENT_ID" ] || [ "$BUNDLE_AGENT_ID" = "$TARGET_AGENT_ID" ]; then
        API_KEY=$(jq -r '.api_key // .token // ""' "$SECRET_BUNDLE")
        if [ -n "$API_KEY" ] && [ "$API_KEY" != "null" ]; then
            export HOLON_AGENT_KEY="$API_KEY"
        fi
    fi
fi

# Map HOLON_AGENT_KEY to legacy/vendor-specific API variables
if [ -n "${HOLON_AGENT_KEY:-}" ] && [ -n "${HOLON_AGENT_ID:-}" ]; then
    AGENT_ID=$(echo "${HOLON_AGENT_ID}" | tr '[:upper:]' '[:lower:]' | sed 's/-agent//g' | sed 's/agent-//g')
    case "${AGENT_ID}" in
        antigravity)
            export AGY_USER_TOKEN="${HOLON_AGENT_KEY}"
            export GOOGLE_API_KEY="${HOLON_AGENT_KEY}"
            ;;
        claude)
            export ANTHROPIC_API_KEY="${HOLON_AGENT_KEY}"
            ;;
        pi)
            export PI_API_KEY="${HOLON_AGENT_KEY}"
            ;;
        codex|open-codex)
            export OPENAI_API_KEY="${HOLON_AGENT_KEY}"
            ;;
        gemini)
            export GEMINI_API_KEY="${HOLON_AGENT_KEY}"
            ;;
        opencode)
            export OPENCODE_API_KEY="${HOLON_AGENT_KEY}"
            ;;
    esac
fi

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
