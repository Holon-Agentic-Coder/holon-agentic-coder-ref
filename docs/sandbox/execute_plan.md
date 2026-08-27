# Running Execution via Docker

This guide explains how to run the Sandbox Executor role using the Docker sandbox environment.

The Executor checks out a plan branch, runs the AI coding agent to implement changes, executes validation test suites,
records execution results in the ledger `holon-knowledge/ledger/executions.jsonl`, and pushes the execution branch.

---

## Recommended Execution Method (`./holon` CLI)

> [!IMPORTANT] **Use `./holon` instead of raw `docker run` commands.** Always run sandbox executions via the
> [`./holon`](../../holon) host CLI script from the repository root:

```bash
./holon execute "I-1782654790-bootstrap-holon-cli-intent/P-1784988130-antigravity-agent-gemini-3.5-flash/_" --agent antigravity-agent --model gemini-3.5-flash
```

The `./holon` wrapper script automatically handles setting up the container and environment, mapping directly into the
[3-Tier Fallback Contract](../executor/agent_credentials_requirements.md#the-3-tier-fallback-contract):

### 1. Ephemeral Secret & Env Forwarding (Tier 1 & 2)

The script searches the host environment for active tokens and passes them down as Docker environment flags (`-e`):

- **GitHub Token Discovery**: Auto-detects tokens using `GITHUB_TOKEN` or `GH_TOKEN` environment variables, or
  automatically executes the host `gh auth token` command.
- **Agent Keys & Configuration**: Forwards all environment variables starting with `HOLON_AGENT_` (such as
  `HOLON_AGENT_KEY`, `HOLON_AGENT_OSS_MODE`, and `HOLON_AGENT_EFFORT`).

### 2. Session Directory Mounts (Tier 3)

The wrapper checks the host user's home folder for existing agent credentials/sessions and maps them into the container
under `/home/holon/...` as read-only (`:ro`) mounts:

- **`antigravity`**: Maps `~/.gemini/antigravity-cli` and `~/.config/antigravity`
- **`claude`**: Maps `~/.config/claude`
- **`codex`**: Maps `~/.codex`
- **`pi`**: Maps `~/.config/pi`
- **`gemini`**: Maps `~/.config/gcloud`

### 3. SSH Agent Socket Forwarding

To allow the containerized executor to perform git pushes to remote origins without requiring SSH keys inside the
sandbox:

- **macOS**: Mounts `/run/host-services/ssh-auth.sock` to the container and updates the `SSH_AUTH_SOCK` environment.
- **Linux/Other**: Mounts the host's existing `SSH_AUTH_SOCK` value to `/run/ssh-agent` in the container.

---

## Command Breakdown

- **`plan_branch`** (positional, required): The target plan branch to execute.
- **`--agent`** (optional, default: `antigravity-agent`): Agent runner to execute.
- **`--model`** (optional, default: `gemini-3.5-flash`): Target LLM model name.

---

## Related Documents

- [Executor Architecture Specification](../executor/execution_architecture_specification.md)
- [Agent Credentials & API Key Requirements](../executor/agent_credentials_requirements.md)
- [Planning Architecture Specification](../planner/planning_architecture_specification.md)
- [Creating a Plan in Sandbox](create_plan.md)
