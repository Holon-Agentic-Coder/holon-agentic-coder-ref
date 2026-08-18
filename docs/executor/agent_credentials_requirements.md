# Agent Credentials & API Key Requirements

To maintain a secure and decoupled sandbox model, the Sandbox Executor does not hardcode api keys or sensitive configuration files. Instead, it utilizes a multi-tier fallback system to retrieve and configure credentials at runtime before starting any AI agent.

---

## The 3-Tier Fallback Contract

Credentials resolution follows three distinct fallback tiers, which are queried in sequence:

```mermaid
graph TD
    Start[Resolve Credentials] --> Tier1[Tier 1: Ephemeral Secret Bundle]
    Tier1 -->|Found| ApplyT1[Load key & unpack config_files]
    Tier1 -->|Not Found| Tier2[Tier 2: Environment Variables]
    Tier2 -->|Found| ApplyT2[Resolve GITHUB_TOKEN & HOLON_AGENT_KEY]
    Tier2 -->|Not Found| Tier3[Tier 3: Session Directory Mounts]
    Tier3 -->|Found| ApplyT3[Mount read-only host configs to container]
    Tier3 -->|Not Found| Fail[Validation Error: Exit 1]
```

### Tier 1: Ephemeral Secret Bundle
- **Source**: Resolved from the file path specified in `HOLON_SECRET_BUNDLE_PATH` (defaults to `/run/secrets/holon_auth.json`).
- **Use Case**: Typically used in automated CI/CD pipelines or orchestrated sandbox grids where credentials are provisioned dynamically for a single execution.
- **Handling**:
  - The executor reads and parses the JSON secret bundle.
  - If the bundle includes an `api_key` or `token`, it is written to the `HOLON_AGENT_KEY` environment variable.
  - If the bundle includes a `config_files` dictionary, its key-value pairs (relative paths to file contents) are unpacked into the sandbox user's home directory.

#### Path Traversal Protection
During the unpacking of configuration files from the ephemeral secret bundle, a path-traversal safeguard is strictly enforced to prevent malicious or malformed bundles from writing files outside the sandbox user's home directory (e.g. overwriting `/etc/shadow` or `/usr/bin/`).
- **Validation Logic**:
  1. The target path is constructed via `os.path.abspath(os.path.expanduser(rel_path))`.
  2. The sandbox home directory is retrieved via `os.path.abspath(os.path.expanduser("~"))` and appended with a directory separator.
  3. The target path is verified to ensure it strictly starts with the resolved home directory prefix.
  4. If the target path attempts to write outside the home directory, a `ValueError` is raised, and the execution is aborted.

---

### Tier 2: Environment Variables
- **Source**: Environment variables forwarded directly to the container/process.
- **Key Variables**:
  - `HOLON_AGENT_KEY`: The primary API key or bearer token used by the agent runner.
  - `HOLON_AGENT_OSS_MODE`: Set to `true` or `1` to run agents in offline or open-source modes without requiring external API keys.
  - `HOLON_AGENT_PROVIDER`: Specifies the target model provider (e.g., `openai`, `anthropic`, `google`).
  - `HOLON_AGENT_SETTINGS`: Custom JSON or file-path configurations passed directly to the agent.
  - `GITHUB_TOKEN` / `GH_TOKEN`: Authenticates git fetch and push operations. The `./holon` host CLI automatically retrieves this token using `find_github_token()`, falling back to the local `gh` CLI credentials if not set in the environment.

---

### Tier 3: Session Directory Mounts
- **Source**: Host credential directories mounted read-only (`:ro`) into the corresponding paths inside the container user's home folder (`/home/holon/`).
- **Use Case**: Enables seamless developer experience when executing containerized runs locally, reusing credentials stored on the host.
- **Mapping (Host -> Container)**:
  - **Antigravity**: `~/.gemini/antigravity-cli` -> `/home/holon/.gemini/antigravity-cli` & `~/.config/antigravity` -> `/home/holon/.config/antigravity`
  - **Claude**: `~/.config/claude` -> `/home/holon/.config/claude`
  - **Codex**: `~/.codex` -> `/home/holon/.codex`
  - **Pi**: `~/.config/pi` -> `/home/holon/.config/pi`
  - **Gemini**: `~/.config/gcloud` -> `/home/holon/.config/gcloud`

---

## Agent-Specific Requirements & Configuration Mappings

Each agent has specific command-line structures and validation routines:

### 1. `antigravity`
- **Binary**: `agy`
- **Command template**: `agy --model <model_name> --effort <HOLON_AGENT_EFFORT> -p <prompt>`
- **Effort Evaluation**: The `--effort` argument (e.g., `medium`, `high`) is resolved dynamically at runner execution time to support runtime environment changes.
- **Validation**: Requires `HOLON_AGENT_KEY` to be set, or an active session directory mounted to `/home/holon/.gemini/antigravity-cli` or `/home/holon/.config/gcloud`.

### 2. `gemini`
- **Binary**: `gemini`
- **Command template**: `gemini --model <model_name> -p <prompt>`
- **Validation**: Requires `HOLON_AGENT_KEY` to be set, or active gcloud credentials mounted to `/home/holon/.config/gcloud`.

### 3. `claude`
- **Binary**: `claude`
- **Command template**: `claude --model <model_name> --settings <HOLON_AGENT_SETTINGS> -p <prompt>`
- **Validation**: Requires `HOLON_AGENT_KEY` to be set, or active session configuration mounted to `/home/holon/.config/claude`.

### 4. `pi`
- **Binary**: `pi`
- **Command template**: `pi -p --model <model_name> --provider <HOLON_AGENT_PROVIDER> <prompt>`
- **Validation**: Requires `HOLON_AGENT_KEY` to be set, or active session configuration mounted to `/home/holon/.config/pi`.

### 5. `open-codex`
- **Binary**: `open-codex`
- **Command template**: `open-codex -q -m <model_name> --provider <HOLON_AGENT_PROVIDER> <prompt>`
- **Validation**: Requires the `HOLON_AGENT_KEY` environment variable.

### 6. `opencode`
- **Binary**: `opencode`
- **Command template**: `opencode run --model <model_name> --agent <HOLON_AGENT_MODE> <prompt>`
- **Validation**: Requires the `HOLON_AGENT_KEY` environment variable.

### 7. `codex`
- **Binary**: `codex`
- **Command template**: `codex exec -m <model_name> [--oss] [--local-provider <HOLON_AGENT_LOCAL_PROVIDER>] [-c <HOLON_AGENT_CONFIG>] <prompt>`
- **Offline / Open-Source Mode**: If `HOLON_AGENT_OSS_MODE=true` is set, the `--oss` flag is appended, and API key validation is skipped.
- **Validation**: Requires `HOLON_AGENT_KEY` to be set, `HOLON_AGENT_OSS_MODE=true`, or an active credentials session directory mounted to `/home/holon/.codex`.
