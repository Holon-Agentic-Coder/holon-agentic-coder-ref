# Running Plan Generation via Docker

This guide explains how to run the Plan Generation role using the Docker sandbox environment.

The Planner initializes a new plan branch off of the active intent branch, compiles a prompt using system templates and
intent metadata, runs the AI agent (e.g.,`pi`) to write a structured markdown plan, extracts predicted metrics, logs
them to the plans ledger `holon-knowledge/ledger/plans.jsonl`, and pushes the new plan branch to the remote repository.

---

## Prerequisites

Before running the command, ensure you have:

1. Built the Docker images using the build script:
   ```bash
   ./apps/sandbox-executor/build_all_images.sh
   ```
2. Set up SSH keys on your host machine configured for GitHub access.
3. Created an intent branch (e.g., `I-1771890389-refactor-metrics/_`) and registered it in the intent ledger.

---

## 1. Execute the Docker Container

Run the following command to start the planner container, replacing the branch, agent name, and model name arguments as
needed:

```bash
docker run --rm \
  -e HOLON_ROLE=planner \
  -e GIT_SSH_COMMAND="ssh -o StrictHostKeyChecking=no" \
  -v $HOME/.ssh:/home/holon/.ssh:ro \
  holon/orchestrator \
  "I-1782654790-bootstrap-holon-cli-intent/_" \
  "pi-agent" \
  "gemini-2.0-flash"
```

### Argument Breakdown:

- **`-e HOLON_ROLE=planner`**: Routes the entrypoint call to the Python planner module ( `planner.py`) inside the
  container.
- **`-e GIT_SSH_COMMAND="ssh -o StrictHostKeyChecking=no"` **: Prevents the container from pausing to interactively ask
  you to trust GitHub's host key.
- **`-v ~/.ssh:/home/holon/.ssh:ro` **: Mounts your host's SSH keys inside the container so it can clone the repository,
  commit files, and push new branches.
- **`holon/orchestrator`**: The name of the built Docker orchestrator image.
- **Container Arguments:**
  1. **`intent_branch`** (e.g., `"I-1771890389-refactor-metrics/_"`): The target intent branch to branch off from.
  2. **`agent_name`** (e.g., `"pi-agent"`): The name of the planning agent.
  3. **`model_name`** (e.g., `"gemini-2.0-flash"`): The model used for planning.

---

## 2. Execution Details & Fail-Fast Behavior

During execution, the container performs the following operations:

1. Clones the repository fresh into `/home/holon/repo` targeting the provided `intent_branch`.
2. Creates an ephemeral plan branch: `I-{timestamp}-{slug}/P-{plan_timestamp}-{agent_name}-{model_name}/_`.
3. Compiles a detailed prompt using the template in `holon-config/prompts/planner.template.md` combined with the intent
   data from the ledger.
4. Invokes the AI planning agent (and fails fast, exiting with a non-zero exit code if the agent invocation fails or
   returns empty).
5. Parses metrics (`p_success`, `entropy`, `impact`, `cost`, `learning_value`, `ev`) directly from the markdown plan
   file.
6. Appends a structured plan entry to `holon-knowledge/ledger/plans.jsonl`.
7. Commits the changes and pushes the plan branch to origin.

---

## 3. Verification

Once execution completes, you should verify:

1. A new remote plan branch exists:
   ```bash
   git fetch origin && git branch -r
   # e.g., origin/I-1771890389-refactor-metrics/P-1772691068-architect-agent-gemini-2.0-flash/_
   ```
2. The generated plan markdown file is present under `plans/`:
   ```markdown
   # plans/P-{timestamp}-{agent}-{model}.md
   ```
3. A plan entry is appended to `holon-knowledge/ledger/plans.jsonl` with parsed metrics and expected value (EV)
   calculations:
   ```json
   {
     "plan_id": "P-1772691068-architect-agent-gemini-2.0-flash",
     "intent_branch": "I-1771890389-refactor-metrics/_",
     "agent": "architect-agent",
     "model": "gemini-2.0-flash",
     "p_success": 0.7,
     "entropy": 2.5,
     "impact": 1.0,
     "cost": 0.5,
     "learning_value": 0.0,
     "ev": 0.45,
     "created_at": "2026-06-27T13:14:15.000Z",
     "plan_file": "plans/P-1772691068-architect-agent-gemini-2.0-flash.md",
     "status": "proposed"
   }
   ```
