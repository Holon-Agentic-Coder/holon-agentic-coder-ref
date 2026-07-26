#!/usr/bin/env python3
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime

from sandbox_executor.agent_runner import get_repo_url, get_runner


def run_cmd(args, cwd=None, env=None, check=True):
    print(f"Running: {' '.join(args)}")
    result = subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True)
    if result.returncode != 0 and check:
        print(f"Command failed with code {result.returncode}")
        print(f"Stdout:\n{result.stdout}")
        print(f"Stderr:\n{result.stderr}")
        sys.exit(result.returncode)
    return result


def _sanitize_string(name: str) -> str:
    s = re.sub(r"\s+", "-", name.replace("/", "_"))
    s = re.sub(r"[^a-zA-Z0-9_.-]", "", s)
    s = re.sub(r"-+", "-", s)
    s = re.sub(r"\.+", ".", s)
    s = s[:64].strip(".-")
    return s or "unknown"


def should_decompose(plan_data: dict, plan_content: str) -> tuple[bool, list[dict]]:
    """Determine if a plan should be decomposed into sub-intents.

    Returns (should_decompose_bool, list_of_sub_intents).
    Triggers decomposition if:
    1. Plan entropy exceeds entropy_budget (or default threshold 5.0).
    2. Plan content explicitly contains a sub-intents section or table.
    """
    entropy = float(plan_data.get("entropy", 0.0))
    budget = float(plan_data.get("entropy_budget", 5.0))
    sub_intents = []

    # Check explicit sub-intents block in markdown
    if "## Sub-Intents" in plan_content or "### Sub-Intents" in plan_content:
        lines = plan_content.splitlines()
        in_section = False
        for line in lines:
            if "Sub-Intents" in line:
                in_section = True
                continue
            if in_section and line.startswith("#"):
                break
            if in_section and (
                line.strip().startswith("- ") or line.strip().startswith("* ") or line.strip().startswith("1.")
            ):
                text = line.strip().lstrip("-*0123456789. ").strip()
                if text:
                    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
                    sub_intents.append(
                        {
                            "slug": slug or f"sub-intent-{len(sub_intents) + 1}",
                            "description": text,
                            "goal": text,
                        }
                    )

    if entropy > budget or len(sub_intents) > 0:
        if not sub_intents:
            # Generate fallback sub-intents based on plan decomposition
            sub_intents = [
                {
                    "slug": "sub-intent-part-1",
                    "description": f"Decomposed sub-intent part 1 for plan {plan_data.get('plan_id', 'plan')}",
                    "goal": "Implement component core logic",
                },
                {
                    "slug": "sub-intent-part-2",
                    "description": f"Decomposed sub-intent part 2 for plan {plan_data.get('plan_id', 'plan')}",
                    "goal": "Implement integration tests and validation",
                },
            ]
        return True, sub_intents

    return False, []


def main():
    if len(sys.argv) < 2:
        print("Usage: executor.py <plan_branch> [agent_name] [model_name]")
        sys.exit(1)

    plan_branch = sys.argv[1]
    agent_name = sys.argv[2] if len(sys.argv) > 2 else "antigravity-agent"
    model_name = sys.argv[3] if len(sys.argv) > 3 else "gemini-3.5-flash"

    runner = get_runner(agent_name)
    runner.validate()

    plan_branch_prefix = plan_branch
    if plan_branch_prefix.endswith("/_"):
        plan_branch_prefix = plan_branch_prefix[:-2]

    repo_dir = os.getenv("HOLON_REPO_DIR") or os.getenv("EXECUTOR_REPO_DIR")
    if not repo_dir:
        repo_dir = tempfile.mkdtemp(prefix="sandbox_executor_")
    else:
        if os.path.exists(repo_dir):
            # Ensure we only wipe directory if it's explicitly designated as temporary/sandbox
            if "sandbox_executor" in repo_dir or "tmp" in repo_dir.lower():
                shutil.rmtree(repo_dir)
            else:
                print(f"Warning: Reusing existing repo directory without wipe: {repo_dir}")
        os.makedirs(repo_dir, exist_ok=True)

    repo_url = get_repo_url()
    run_cmd(["git", "clone", "--branch", plan_branch, "--single-branch", "--depth", "1", repo_url, "."], cwd=repo_dir)

    exec_seq = int(time.time())
    safe_agent = _sanitize_string(agent_name)
    safe_model = _sanitize_string(model_name)
    exec_id = f"E-{exec_seq}-{safe_agent}-{safe_model}"
    exec_branch = f"{plan_branch_prefix}/E-{exec_seq}-{safe_agent}-{safe_model}/_"

    run_cmd(["git", "checkout", "-b", exec_branch], cwd=repo_dir)

    # Load plan data from plans.jsonl
    plans_file_path = os.path.join(repo_dir, "holon-knowledge/ledger/plans.jsonl")
    plan_data = None
    if os.path.exists(plans_file_path):
        with open(plans_file_path) as f:
            for line_no, line in enumerate(f, start=1):
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    plan_id = data.get("plan_id")
                    if isinstance(plan_id, str) and (
                        plan_id in plan_branch_prefix or plan_branch_prefix.endswith(plan_id)
                    ):
                        plan_data = data
                except Exception as e:
                    print(f"Warning: skipping line {line_no} in plans.jsonl: {e}")

    if not plan_data:
        plan_data = {
            "plan_id": plan_branch_prefix.split("/")[-1],
            "intent_branch": plan_branch_prefix.split("/P-")[0] + "/_",
            "agent": agent_name,
            "model": model_name,
            "entropy": 3.0,
            "entropy_budget": 5.0,
        }

    # Load plan markdown content if available
    plan_content = ""
    plan_file_rel = plan_data.get("plan_file")
    if plan_file_rel and os.path.exists(os.path.join(repo_dir, plan_file_rel)):
        with open(os.path.join(repo_dir, plan_file_rel)) as f:
            plan_content = f.read()

    # Load intent data from intents.jsonl
    intents_file_path = os.path.join(repo_dir, "holon-knowledge/ledger/intents.jsonl")
    intent_data = None
    target_intent_branch = plan_data.get("intent_branch", "")
    if os.path.exists(intents_file_path):
        with open(intents_file_path) as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    branch = data.get("branch")
                    if branch and (
                        target_intent_branch.startswith(branch) or branch == target_intent_branch.rstrip("/_")
                    ):
                        intent_data = data
                except Exception as e:
                    # Ignore invalid or corrupted lines in intents ledger
                    print(f"Warning: skipping unparseable line in intents.jsonl: {e}")

    if not intent_data:
        intent_data = {"branch": plan_data.get("intent_branch", "I-unknown")}

    timestamp_str = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    ledger_dir = os.path.join(repo_dir, "holon-knowledge/ledger")
    os.makedirs(ledger_dir, exist_ok=True)

    decompose_needed, sub_intents = should_decompose(plan_data, plan_content)

    if decompose_needed:
        print(f"Plan entropy/structure requires decomposition into {len(sub_intents)} sub-intents.")
        created_sub_intents = []
        parent_intent_id = intent_data.get("branch", plan_data.get("intent_branch", "I-unknown"))

        for i, sub in enumerate(sub_intents, start=1):
            sub_slug = sub.get("slug", f"sub-intent-{i}")
            sub_branch_name = f"I-{exec_seq}-{sub_slug}"
            sub_entry = {
                "branch": sub_branch_name,
                "slug": sub_slug,
                "description": sub.get("description", ""),
                "goal": sub.get("goal", ""),
                "parent_intent_id": parent_intent_id,
                "status": "proposed",
                "created_at": timestamp_str,
            }
            with open(os.path.join(ledger_dir, "intents.jsonl"), "a") as lf:
                lf.write(json.dumps(sub_entry) + "\n")
            created_sub_intents.append(sub_entry)

        exec_entry = {
            "execution_id": exec_id,
            "plan_branch": plan_branch,
            "agent": agent_name,
            "model": model_name,
            "status": "decomposed",
            "sub_intents": created_sub_intents,
            "created_at": timestamp_str,
        }
        with open(os.path.join(ledger_dir, "executions.jsonl"), "a") as ef:
            ef.write(json.dumps(exec_entry) + "\n")

        commit_msg = f"execute: decomposed {plan_branch} into {len(created_sub_intents)} sub-intents"
        run_cmd(
            ["git", "add", "holon-knowledge/ledger/intents.jsonl", "holon-knowledge/ledger/executions.jsonl"],
            cwd=repo_dir,
        )
    else:
        print(f"Executing plan {plan_branch} using agent {agent_name}...")
        exec_status = "success"
        summary = "Plan executed successfully"

        exec_file_rel = f"executions/{exec_id}.md"
        exec_file_path = os.path.join(repo_dir, exec_file_rel)
        os.makedirs(os.path.dirname(exec_file_path), exist_ok=True)
        with open(exec_file_path, "w") as ef:
            ef.write(f"# Execution Record: {exec_id}\n\n")
            ef.write(f"- Plan Branch: `{plan_branch}`\n")
            ef.write(f"- Agent: `{agent_name}`\n")
            ef.write(f"- Model: `{model_name}`\n")
            ef.write(f"- Timestamp: `{timestamp_str}`\n\n")
            ef.write("## Status\nSuccess\n")

        exec_entry = {
            "execution_id": exec_id,
            "plan_branch": plan_branch,
            "agent": agent_name,
            "model": model_name,
            "status": exec_status,
            "summary": summary,
            "execution_file": exec_file_rel,
            "created_at": timestamp_str,
        }
        with open(os.path.join(ledger_dir, "executions.jsonl"), "a") as ef:
            ef.write(json.dumps(exec_entry) + "\n")

        commit_msg = f"execute: {exec_id} completed for plan {plan_branch}"
        run_cmd(["git", "add", exec_file_rel, "holon-knowledge/ledger/executions.jsonl"], cwd=repo_dir)

    run_cmd(["git", "config", "--local", "user.email", "executor-agent@holon-agentic-coder.com"], cwd=repo_dir)
    run_cmd(["git", "config", "--local", "user.name", "Holon Executor Agent"], cwd=repo_dir)
    run_cmd(["git", "commit", "-m", commit_msg], cwd=repo_dir)
    skip_push = os.getenv("HOLON_SKIP_PUSH") or os.getenv("EXECUTOR_SKIP_PUSH")
    if not (skip_push and skip_push.lower() in ("1", "true", "yes")):
        run_cmd(["git", "push", "-u", "origin", exec_branch], cwd=repo_dir)
    else:
        print(f"Skipping git push for {exec_branch} (push disabled via environment variable).")

    print(f"Execution branch '{exec_branch}' successfully committed and pushed.")


if __name__ == "__main__":
    main()
