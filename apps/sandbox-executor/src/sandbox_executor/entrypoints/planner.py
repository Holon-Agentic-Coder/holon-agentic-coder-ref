#!/usr/bin/env python3
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime


def run_cmd(args, cwd=None, env=None, check=True):
    print(f"Running: {' '.join(args)}")
    result = subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True)
    if result.returncode != 0 and check:
        print(f"Command failed with code {result.returncode}")
        print(f"Stdout:\n{result.stdout}")
        print(f"Stderr:\n{result.stderr}")
        sys.exit(result.returncode)
    return result


def get_file_structure(root_dir, max_depth=3):
    lines = []
    root_dir = os.path.abspath(root_dir)
    prefix_len = len(root_dir) + 1

    for root, dirs, files in os.walk(root_dir):
        # Filter out dot directories in-place to prevent os.walk from recursing into them
        dirs[:] = [d for d in dirs if not d.startswith(".")]

        rel_path = root[prefix_len:]
        depth = rel_path.count(os.sep) + 1 if rel_path else 0
        if depth >= max_depth:
            dirs[:] = []

        indent = "  " * depth
        if rel_path:
            lines.append(f"{indent}{os.path.basename(root)}/")
        else:
            lines.append("./")

        for f in files:
            if not f.startswith("."):
                lines.append(f"{indent}  {f}")

    return "\n".join(lines)


def parse_metrics(content):
    import re

    metrics = {}
    row_pat = re.compile(r"\|\s*([a-zA-Z_0-9]+)\s*\|\s*([0-9\.\-]+)\s*\|")
    for line in content.splitlines():
        m = row_pat.search(line)
        if m:
            name = m.group(1).strip()
            try:
                val = float(m.group(2).strip())
                # Normalize standard metric names
                name_clean = name.replace("_pred", "").strip()
                metrics[name_clean] = val
            except ValueError:
                # Ignore malformed numeric values and continue parsing other metric rows.
                continue
    return metrics


def main():
    if len(sys.argv) < 4:
        print("Usage: planner.py <intent_branch> <agent_name> <model_name>")
        sys.exit(1)

    intent_branch = sys.argv[1]
    agent_name = sys.argv[2]
    model_name = sys.argv[3]

    intent_branch_prefix = intent_branch
    if intent_branch_prefix.endswith("/_"):
        intent_branch_prefix = intent_branch_prefix[:-2]

    repo_dir = os.path.expanduser("~/repo")
    if os.path.exists(repo_dir):
        shutil.rmtree(repo_dir)
    os.makedirs(repo_dir, exist_ok=True)

    # Clone the repo
    repo_url = "git@github.com:Holon-Agentic-Coder/holon-agentic-coder-ref.git"
    run_cmd(["git", "clone", "--branch", intent_branch, "--single-branch", "--depth", "1", repo_url, "."], cwd=repo_dir)

    plan_seq = int(time.time())
    safe_model = model_name.replace("/", "_")
    plan_id = f"P-{plan_seq}-{agent_name}-{safe_model}"
    plan_branch = f"{intent_branch_prefix}/P-{plan_seq}-{agent_name}-{safe_model}/_"

    # Checkout plan branch
    run_cmd(["git", "checkout", "-b", plan_branch], cwd=repo_dir)

    # Get intent data
    intents_file_path = os.path.join(repo_dir, "holon-knowledge/ledger/intents.jsonl")
    intent_data = None
    if os.path.exists(intents_file_path):
        with open(intents_file_path) as f:
            for line_no, line in enumerate(f, start=1):
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    # Match branch name prefix (e.g. branch == "I-timestamp-slug")
                    if data.get("branch") == intent_branch_prefix or data.get("intent_id") == intent_branch_prefix:
                        intent_data = data
                except json.JSONDecodeError as e:
                    print(f"Warning: skipping invalid JSON in {intents_file_path} at line {line_no}: {e}")
                except Exception as e:
                    print(f"Warning: error processing line in {intents_file_path} at line {line_no}: {e}")

    if not intent_data:
        print(f"Error: No intent found for branch prefix '{intent_branch_prefix}' in '{intents_file_path}'")
        sys.exit(1)

    # Prepare prompt using template
    template_path = os.path.join(repo_dir, "holon-config/prompts/planner.template.md")
    if os.path.exists(template_path):
        with open(template_path) as f:
            template = f.read()
    else:
        template = """Based on the following intent JSON:
{intent_json}
Generate a detailed markdown implementation plan.
Include metrics in this format:
| metric | value |
| p_success_pred | {p_success_pred} |
| entropy_pred | {entropy_pred} |
| impact_pred | {impact_pred} |
| cost_pred | {cost_pred} |
| learning_value_pred | {learning_value_pred} |
| ev_pred | {ev_pred} |
"""

    replacements = {
        "{timestamp}": str(plan_seq),
        "{agent}": agent_name,
        "{model}": model_name,
        "{intent_id}": intent_data.get("intent_id", intent_data.get("branch", intent_branch_prefix)),
        "{parent_intent_id}": intent_data.get("parent_intent_id", "NONE"),
        "{description}": intent_data.get("description", ""),
        "{plan_id": plan_id,  # cover partial braces
        "{plan_id}": plan_id,
        "{date}": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
        "{intent_json}": json.dumps(intent_data, indent=2),
        "{safe_model}": safe_model,
        "{budget_from_intent}": str(intent_data.get("entropy_budget", "15.0")),
    }
    for k, v in replacements.items():
        template = template.replace(k, v)

    prompt_file = f"/tmp/plan_prompt-{plan_seq}.md"
    with open(prompt_file, "w") as f:
        f.write(template)
        f.write("\n\nRepository file structure:\n")
        f.write(get_file_structure(repo_dir))

    intent_file = f"/tmp/intent-{plan_seq}.json"
    with open(intent_file, "w") as f:
        json.dump(intent_data, f)

    # Invoke AI agent
    plan_md_rel = f"plans/P-{plan_seq}-{agent_name}-{safe_model}.md"
    plan_md_path = os.path.join(repo_dir, plan_md_rel)
    os.makedirs(os.path.dirname(plan_md_path), exist_ok=True)

    agent_id = agent_name.lower().replace("-agent", "").replace("agent-", "")
    agent_mapping = {
        "pi": ("pi", "@mariozechner/pi-coding-agent"),
        "open-codex": ("open-codex", "open-codex"),
        "claude": ("claude", "@anthropic-ai/claude-code"),
        "gemini": ("gemini", "@google/gemini-cli"),
        "opencode": ("opencode", "opencode-ai"),
        "codex": ("codex", "@openai/codex"),
        "hermes": ("hermes", None),
        "antigravity": ("agy", None),
    }

    binary_name, package_name = agent_mapping.get(agent_id, ("pi", "@mariozechner/pi-coding-agent"))

    if shutil.which(binary_name):
        cmd = [binary_name]
    else:
        if package_name:
            cmd = ["npx", "-y", "--package", package_name, binary_name]
        else:
            cmd = [binary_name]

    cmd.extend(["-p", "--model", model_name])
    pi_provider = os.getenv("PI_PROVIDER")
    if pi_provider:
        cmd.extend(["--provider", pi_provider])
    pi_api_key = os.getenv("PI_API_KEY")
    if pi_api_key:
        cmd.extend(["--api-key", pi_api_key])
    cmd.extend([f"@{prompt_file}", f"@{intent_file}"])

    print(f"Running command: {' '.join(cmd)}")
    agent_failed = False
    exit_code = 0
    try:
        # Run agent and redirect output to the plan file
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            with open(plan_md_path, "w") as f:
                f.write(result.stdout)
        else:
            print(f"Error: agent command failed or returned empty. code={result.returncode}")
            print(f"Stdout:\n{result.stdout}")
            print(f"Stderr:\n{result.stderr}")
            agent_failed = True
            exit_code = result.returncode if result.returncode != 0 else 1
    except Exception as e:
        print(f"Error: Exception running agent: {e}")
        agent_failed = True
        exit_code = 1

    # Clean up temp files
    for temp_f in [prompt_file, intent_file]:
        if os.path.exists(temp_f):
            os.remove(temp_f)

    if agent_failed:
        sys.exit(exit_code)

    # Parse metrics
    with open(plan_md_path) as f:
        plan_content = f.read()
    metrics = parse_metrics(plan_content)

    # Ensure required metrics exist with default heuristics if parsing fails
    defaults = {"p_success": 0.7, "entropy": 3.0, "impact": 1.0, "cost": 0.5, "learning_value": 0.0}
    for k, default_val in defaults.items():
        if k not in metrics:
            metrics[k] = default_val

    # Recalculate EV based on default formula: EV = P(success)*Impact + 1.0*LV - 0.1*Entropy - Cost
    p_success = metrics["p_success"]
    entropy = metrics["entropy"]
    impact = metrics["impact"]
    cost = metrics["cost"]
    learning_value = metrics["learning_value"]
    ev = p_success * impact + 1.0 * learning_value - 0.1 * entropy - cost
    metrics["ev"] = ev

    # Append plan summary to ledger
    timestamp_str = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    plan_entry = {
        "plan_id": plan_id,
        "intent_branch": intent_branch,
        "agent": agent_name,
        "model": model_name,
        "p_success": p_success,
        "entropy": entropy,
        "impact": impact,
        "cost": cost,
        "learning_value": learning_value,
        "ev": ev,
        "created_at": timestamp_str,
        "plan_file": plan_md_rel,
        "status": "proposed",
    }

    plans_ledger_dir = os.path.join(repo_dir, "holon-knowledge/ledger")
    os.makedirs(plans_ledger_dir, exist_ok=True)
    plans_ledger_path = os.path.join(plans_ledger_dir, "plans.jsonl")
    with open(plans_ledger_path, "a") as lf:
        lf.write(json.dumps(plan_entry) + "\n")

    # Git commit and push
    run_cmd(["git", "add", plan_md_rel, "holon-knowledge/ledger/plans.jsonl"], cwd=repo_dir)
    run_cmd(["git", "config", "--local", "user.email", "planner-agent@holon-agentic-coder.com"], cwd=repo_dir)
    run_cmd(["git", "config", "--local", "user.name", "Holon Planner Agent"], cwd=repo_dir)
    run_cmd(["git", "commit", "-m", f"plan: {plan_id} created by {agent_name} ({model_name})"], cwd=repo_dir)
    run_cmd(["git", "push", "-u", "origin", plan_branch], cwd=repo_dir)

    print(f"Plan branch '{plan_branch}' successfully created, committed, and pushed.")


if __name__ == "__main__":
    main()
