# Multi-stage Dockerfile for holon agent images
# For reference of coding agents https://github.com/bradAGI/awesome-cli-coding-agents/blob/main/README.md
# TODO: do we want to bake in the agents or decide at runtime? we can run agent at runtime by running `npx @anthropic-ai/claude-code`
# TODO: if we bake the agents in we need to rebuild the image everytime there is an update
# TODO: if we choose the agent at runtime we can choose certain version or latest at runtime
# Build targets: holon-base, agent-claude, agent-gemini, agent-opencode, agent-codex, agent-open-codex, holon-orchestrator

# --- Base Layer ---
FROM python:3.13-slim AS holon-base
RUN apt-get update && \
    apt-get install -y --no-install-recommends git curl jq build-essential ca-certificates ssh vim && \
    rm -rf /var/lib/apt/lists/*

# Install Node.js v24.18.0 (multi-architecture support)
RUN dpkgArch="$(dpkg --print-architecture)" && \
    case "${dpkgArch##*-}" in \
      amd64) ARCH='x64';; \
      arm64) ARCH='arm64';; \
      *) echo "unsupported architecture"; exit 1 ;; \
    esac && \
    curl -fsSL "https://nodejs.org/dist/v24.18.0/node-v24.18.0-linux-${ARCH}.tar.gz" | tar -xz --strip-components=1 -C /usr/local

# Create non-root user
RUN useradd -m holon
WORKDIR /home/holon

# Copy orchestrator entrypoints and package
COPY --chown=holon:holon src/ /home/holon/src/
COPY --chown=holon:holon entrypoint/role_dispatcher.sh /home/holon/entrypoint/role_dispatcher.sh

# Configure PYTHONPATH to make sandbox_executor package importable
ENV PYTHONPATH="/home/holon/src"

# Provide a lightweight entry that delegates to role-specific scripts
ENV LEDGER_PATH=/workspace/repo/holon/ledger

ENTRYPOINT ["/home/holon/entrypoint/role_dispatcher.sh"]

USER holon
ENV PATH="/home/holon/.local/bin:${PATH}"
RUN mkdir -p /home/holon/.cache

# --- Claude Agent Layer ---
FROM holon-base AS agent-claude
USER root
RUN --mount=type=cache,id=npm-claude,target=/root/.npm \
    npm install -g --prefer-offline --no-audit --no-fund @anthropic-ai/claude-code@2.1.202
USER holon

# --- Gemini Agent Layer ---
FROM holon-base AS agent-gemini
USER root
RUN --mount=type=cache,id=npm-gemini,target=/root/.npm \
    npm install -g --prefer-offline --no-audit --no-fund @google/gemini-cli@0.49.0
USER holon

# --- OpenCode Agent Layer (opencode) ---
FROM holon-base AS agent-opencode
USER root
RUN --mount=type=cache,id=npm-opencode,target=/root/.npm \
    npm install -g --prefer-offline --no-audit --no-fund opencode-ai@1.17.14
USER holon

# --- Pi Agent Layer ---
FROM holon-base AS agent-pi
USER root
RUN --mount=type=cache,id=npm-pi,target=/root/.npm \
    npm install -g --prefer-offline --no-audit --no-fund @earendil-works/pi-coding-agent@0.80.3
USER holon

# --- Codex Agent Layer ---
FROM holon-base AS agent-codex
USER root
RUN --mount=type=cache,id=npm-codex,target=/root/.npm \
    npm install -g --prefer-offline --no-audit --no-fund @openai/codex@0.142.5
USER holon

# --- Open Codex Agent Layer ---
FROM holon-base AS agent-open-codex
USER root
RUN --mount=type=cache,id=npm-open-codex,target=/root/.npm \
    npm install -g --prefer-offline --no-audit --no-fund open-codex@0.1.31
USER holon

# --- Antigravity Agent Layer ---
FROM holon-base AS agent-antigravity
RUN --mount=type=cache,id=uv-antigravity,uid=1000,gid=1000,target=/home/holon/.cache/uv \
    --mount=type=cache,id=npm-antigravity,uid=1000,gid=1000,target=/home/holon/.npm \
    curl -fsSL https://antigravity.google/cli/install.sh | bash

# --- Final Orchestrator Image ---
FROM holon-base AS holon-orchestrator
