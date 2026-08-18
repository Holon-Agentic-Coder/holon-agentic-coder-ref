# Running Execution via Docker

This guide explains how to run the Sandbox Executor role using the Docker sandbox environment.

The Executor checks out a plan branch, runs the AI coding agent to implement changes, executes validation test suites, records execution results in the ledger `holon-knowledge/ledger/executions.jsonl`, and pushes the execution branch.

For detailed design specs and configuration requirements, see:
- [execution_architecture_specification.md](../executor/execution_architecture_specification.md) for the Executor's internals, lifecycle, and safety boundaries.
- [agent_credentials_requirements.md](../executor/agent_credentials_requirements.md) for key management, path traversal verification, and supported agent config parameters.

---

## Recommended Execution Method (`./holon` CLI)

> [!IMPORTANT] **Use `./holon` instead of raw `docker run` commands.** Always run sandbox executions via the
> [`./holon`](../../holon) host CLI script from the repository root:

```bash
./holon execute "I-1782654790-bootstrap-holon-cli-intent/P-1784988130-antigravity-agent-gemini-3.5-flash/_" --agent antigravity-agent --model gemini-3.5-flash
```

### The 3-Tier Fallback Contract Mapping

The `./holon` wrapper CLI automatically integrates with the Sandbox Executor's **3-Tier Fallback Contract** for resolving credentials:

- **Tier 1 (Ephemeral Secret Bundle)**: Can load or bind-mount the temporary secret bundle JSON file (such as at `/run/secrets/holon_auth.json`) depending on the orchestration context.
- **Tier 2 (Environment variables)**: Automatically discovers and forwards relevant environment variables from your host terminal. It scans for the `GITHUB_TOKEN` (via `find_github_token()`, falling back to the `gh` CLI credentials) and any variables prefixed with `HOLON_AGENT_` (such as `HOLON_AGENT_KEY`, `HOLON_AGENT_OSS_MODE`, or `HOLON_AGENT_EFFORT`), mounting them into the container via `-e` flags.
- **Tier 3 (Session directory mounts)**: Auto-detects active user credentials in standard host directories (e.g. `~/.gemini/antigravity-cli`, `~/.config/gcloud`, `~/.config/claude`, `~/.config/pi`, `~/.codex`) and mounts them read-only (`:ro`) into the corresponding path in the container user's home folder (`/home/holon/`). This allows OAuth profiles and locally-cached sessions to function out-of-the-box in the headless container.

In addition, `./holon` manages:
- Cross-platform SSH agent socket forwarding (`SSH_AUTH_SOCK`) for git push operations.
- Automatically routing the container's operational role (`HOLON_ROLE=executor`).

---

## Command Breakdown

- **`plan_branch`** (positional, required): The target plan branch to execute.
- **`--agent`** (optional, default: `antigravity-agent`): Agent runner to execute.
- **`--model`** (optional, default: `gemini-3.5-flash`): Target LLM model name.
