# Migration Guide — HOLON*AGENT*\* Environment Variable Rename

> **Breaking change introduced in PR #27**:
> [`feat(sandbox-executor): replace agent-specific envvars with HOLON_AGENT_* prefix`](https://github.com/Holon-Agentic-Coder/holon-agentic-coder-ref/pull/27)

All agent-specific and vendor-specific environment variables have been unified under a single `HOLON_AGENT_*` namespace.
This is a **hard cutover** — legacy variable names are no longer honoured.

---

## Authentication Keys

The most important change: a single `HOLON_AGENT_KEY` replaces all provider-specific API key variables.
`sandbox-executor` injects this key into each agent container and the appropriate internal translation
(`_apply_generic_token`) maps it to the agent CLI's native credential variable at runtime.

| Old variable        | New variable      | Notes                                  |
| :------------------ | :---------------- | :------------------------------------- |
| `ANTHROPIC_API_KEY` | `HOLON_AGENT_KEY` | Used by `claude`, `pi-agent`           |
| `OPENAI_API_KEY`    | `HOLON_AGENT_KEY` | Used by `codex`, `open-codex`          |
| `GOOGLE_API_KEY`    | `HOLON_AGENT_KEY` | Used by `antigravity`, `gemini`        |
| `GEMINI_API_KEY`    | `HOLON_AGENT_KEY` | Used by `gemini`                       |
| `PI_API_KEY`        | `HOLON_AGENT_KEY` | Mapped internally → `PI_API_KEY`       |
| `OPENCODE_API_KEY`  | `HOLON_AGENT_KEY` | Mapped internally → `OPENCODE_API_KEY` |
| `AGY_USER_TOKEN`    | `HOLON_AGENT_KEY` | Mapped internally → `AGY_USER_TOKEN`   |

---

## Agent Configuration Variables

| Old variable           | New variable                 | Agent         | Purpose                                       |
| :--------------------- | :--------------------------- | :------------ | :-------------------------------------------- |
| `AGY_EFFORT`           | `HOLON_AGENT_EFFORT`         | `antigravity` | Effort level (default: `medium`)              |
| `PI_PROVIDER`          | `HOLON_AGENT_PROVIDER`       | `pi-agent`    | Backend provider (e.g. `anthropic`, `openai`) |
| `OPEN_CODEX_PROVIDER`  | `HOLON_AGENT_PROVIDER`       | `open-codex`  | Backend provider                              |
| `CLAUDE_SETTINGS`      | `HOLON_AGENT_SETTINGS`       | `claude`      | Path to settings JSON                         |
| `OPENCODE_AGENT`       | `HOLON_AGENT_MODE`           | `opencode`    | Sub-agent mode (e.g. `code`, `architect`)     |
| `CODEX_OSS`            | `HOLON_AGENT_OSS_MODE`       | `codex`       | `true` enables offline/keyless mode           |
| `CODEX_LOCAL_PROVIDER` | `HOLON_AGENT_LOCAL_PROVIDER` | `codex`       | Local provider (e.g. `ollama`)                |
| `CODEX_CONFIG`         | `HOLON_AGENT_CONFIG`         | `codex`       | Config string (e.g. `temperature=0.2`)        |

---

## Migration Steps

1. **Replace your API key variable** with `HOLON_AGENT_KEY`:

   ```bash
   # Before
   export ANTHROPIC_API_KEY="sk-ant-..."
   # After
   export HOLON_AGENT_KEY="sk-ant-..."
   ```

2. **Update any agent-specific config variables** using the table above.

3. **Verify** by running:
   ```bash
   holon plan <intent-branch> --agent claude-agent
   ```

---

## Diagnostic Warning

If `sandbox-executor` detects a legacy key in the environment but `HOLON_AGENT_KEY` is not set, it will print a warning
to stderr. The following keys are checked (in order):

- `GOOGLE_API_KEY`
- `ANTHROPIC_API_KEY`
- `OPENAI_API_KEY`
- `GEMINI_API_KEY`
- `OPENCODE_API_KEY`

Example warning (first detected key wins):

```
Warning: 'ANTHROPIC_API_KEY' is set but is no longer used by sandbox-executor.
Please set 'HOLON_AGENT_KEY' instead. See MIGRATION.md (...) for the complete variable mapping.
```

This warning is emitted **at most once per invocation** (the first detected legacy key triggers it and execution
continues). The agent container will not receive an API key and authentication will fail inside the agent CLI.
