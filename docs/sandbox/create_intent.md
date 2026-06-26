# Running Intent Creation via Docker

This guide explains how to run the Intent Creation role using the Docker sandbox environment.

The Intent Creator initializes a new development branch, appends the intent to the append-only ledger
`holon-knowledge/ledger/intents.jsonl`, and pushes the branch to the remote repository.

---

## Prerequisites

Before running the command, ensure you have:

1. Built the Docker images using the build script:
   ```bash
   ./apps/sandbox-executor/build_all_images.sh
   ```
2. Set up SSH keys on your host machine configured for GitHub access.

---

## 1. Prepare the Intent JSON File

Create a JSON file on your host machine (e.g., `intent.json`) representing the metadata for the intent you wish to
create.

### JSON Schema

- **`branch`** (string, optional): The target branch name (e.g., `I-1771890389-refactor-metrics`). If omitted, it will
  be automatically generated on the fly as `I-{timestamp}-{slug}`.
- **`slug`** (string, required if `branch` is omitted): A short URL-safe identifier for the task.
- **`description`** (string, optional): A high-level description of what changes are being made.
- **`goal`** (string, optional): The target objective or test criteria.
- **`target_branch`** (string, optional): The base branch to check out and fork the new branch from (e.g. `develop`). If omitted, defaults to `main`.

### Example (`intent.json`)

```json
{
  "branch": "I-1771890389-refactor-metrics",
  "slug": "refactor-metrics",
  "description": "Clean up metrics estimators and configuration structure",
  "goal": "Refactor local metrics calculations to reduce entropy",
  "target_branch": "develop"
}
```

---

## 2. Execute the Docker Container

Run the following command, replacing `/path/to/intent.json` with the absolute path to the JSON file you created:

```bash
docker run --rm \
  -e HOLON_ROLE=intent-creator \
  -e GIT_SSH_COMMAND="ssh -o StrictHostKeyChecking=no" \
  -v /path/to/intent.json:/tmp/intent.json \
  -v ~/.ssh:/home/holon/.ssh:ro \
  holon/orchestrator
```

### Argument Breakdown:

- **`-e HOLON_ROLE=intent-creator`**: Routes the entrypoint call to the Python intent creator module inside the
  container.
- **`-e GIT_SSH_COMMAND="ssh -o StrictHostKeyChecking=no"`**: Prevents the container from pausing to interactively ask
  you to trust GitHub's host key.
- **`-v /path/to/intent.json:/tmp/intent.json`**: Mounts your host-defined JSON file into the container at the expected
  path.
- **`-v ~/.ssh:/home/holon/.ssh:ro`**: Mounts your host's SSH keys inside the container so it can clone the repository
  and push the new branch.

---

## 3. Verification

Once execution completes, you should verify:

1. A new remote branch has been created: `I-1771890389-refactor-metrics/_`.
2. The intent is appended to `holon-knowledge/ledger/intents.jsonl` on that branch with status `"proposed"` and a UTC `"created_at"`
   timestamp.
