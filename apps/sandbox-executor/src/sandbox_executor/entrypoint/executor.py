#!/usr/bin/env python3
import contextlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import traceback
from datetime import UTC, datetime

from sandbox_executor.agent_runner import get_repo_url, get_runner

SECRET_FLAGS = {
    "--token",
    "--access-token",
    "--access_token",
    "--secret",
    "--password",
    "--api-key",
    "--api_key",
    "--auth",
    "--auth-token",
    "--auth_token",
    "--bearer",
    "--pat",
    "--key",
    "--client-secret",
    "--client_secret",
}


def _handle_remove_readonly(func, path, exc_info):
    """Error handler for shutil.rmtree to handle read-only files/directories (e.g. git pack files)."""
    os.chmod(path, stat.S_IWRITE)
    func(path)


def _clear_dir_contents(path: str, raise_on_error: bool = False) -> None:
    """Clear all contents of a directory without removing the directory itself (useful for mount points)."""
    if not os.path.isdir(path):
        return
    for item in os.listdir(path):
        item_path = os.path.join(path, item)
        try:
            if os.path.islink(item_path) or not os.path.isdir(item_path):
                try:
                    os.unlink(item_path)
                except PermissionError:
                    os.chmod(item_path, stat.S_IWRITE)
                    os.unlink(item_path)
            else:
                shutil.rmtree(item_path, onerror=_handle_remove_readonly)
        except Exception as e:
            if raise_on_error:
                raise
            print(f"Warning: Failed to remove {item_path}: {e}", file=sys.stderr)


def _cleanup_repo_dir(repo_dir: str, raise_on_error: bool = False) -> None:
    """Clean up existing repo directory (clearing contents if mount, unlinking if symlink, rmtree otherwise)."""
    if not os.path.lexists(repo_dir):
        return
    try:
        if os.path.ismount(repo_dir):
            _clear_dir_contents(repo_dir, raise_on_error=raise_on_error)
        elif os.path.islink(repo_dir):
            os.unlink(repo_dir)
        else:
            shutil.rmtree(repo_dir, onerror=_handle_remove_readonly)
    except Exception as e:
        if raise_on_error:
            raise RuntimeError(f"Failed to clean up existing repo dir {repo_dir}: {e}") from e
        print(f"Warning: Failed to clean up repo dir {repo_dir}: {e}", file=sys.stderr)


def redact_text(text: str | None) -> str | None:
    if text is None:
        return None
    if not isinstance(text, str):
        text = str(text)
    if not text:
        return text
    s = re.sub(r"(https?://)[^@/]+@", r"\1*******@", text)
    pattern = (
        r'(["\']?)(\b[a-zA-Z0-9_-]*(?:token|access_token|secret|password|api_key|auth|bearer|_pat|-pat|\bpat|_key|-key|\bkey))\1'
        r'\s*(:\s*|=)\s*(?:(["\'])(.*?)\4|([^&\s\'"]+))'
    )

    def _replace_secret(match: re.Match) -> str:
        q_key = match.group(1) or ""
        key = match.group(2)
        sep = match.group(3)
        q_val = match.group(4) or ""
        return f"{q_key}{key}{q_key}{sep}{q_val}*******{q_val}"

    s = re.sub(pattern, _replace_secret, s, flags=re.IGNORECASE)
    s = re.sub(r"(Bearer\s+)[^\s]+", r"\1*******", s, flags=re.IGNORECASE)
    return s


def redact_args(args: list[str]) -> list[str]:
    redacted = []
    mask_next = False
    for arg in args:
        s_arg = str(arg)
        if mask_next:
            if re.match(r"^--?[a-zA-Z]", s_arg):
                mask_next = False
            else:
                redacted.append("*******")
                mask_next = False
                continue

        parts = s_arg.split("=", 1)
        flag_lowered = parts[0].lower()
        if flag_lowered in SECRET_FLAGS:
            if len(parts) == 2:
                redacted.append(f"{parts[0]}=*******")
            else:
                masked = redact_text(s_arg)
                redacted.append(masked if masked is not None else "")
                mask_next = True
        else:
            masked = redact_text(s_arg)
            redacted.append(masked if masked is not None else "")

    return redacted


def run_cmd(
    args: list[str],
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    redacted_args = redact_args(args)
    print_args = [arg[:250] + "..." if len(arg) > 250 else arg for arg in redacted_args]
    print(f"Running: {' '.join(print_args)}")
    result = subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True)
    if result.returncode != 0 and check:
        print(f"Command failed with code {result.returncode}", file=sys.stderr)
        print(f"Command args: {' '.join(print_args)}", file=sys.stderr)
        out = redact_text(result.stdout) or ""
        err = redact_text(result.stderr) or ""
        if len(out) > 5000:
            out = out[:5000] + "... (truncated)"
        if len(err) > 5000:
            err = err[:5000] + "... (truncated)"
        print(f"Stdout:\n{out}", file=sys.stderr)
        print(f"Stderr:\n{err}", file=sys.stderr)
        raise subprocess.CalledProcessError(
            result.returncode, redacted_args, output=redact_text(result.stdout), stderr=redact_text(result.stderr)
        )
    return result


def _safe_float(val, default: float = 0.0) -> float:
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


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
    entropy = _safe_float(plan_data.get("entropy"), 0.0)
    budget = _safe_float(plan_data.get("entropy_budget"), 5.0)
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
            stripped_line = line.strip()
            if in_section and (
                stripped_line.startswith("- ")
                or stripped_line.startswith("* ")
                or re.match(r"^\d+\.\s+", stripped_line)
            ):
                text = re.sub(r"^([\s\-*]|\d+\.)\s*", "", stripped_line).strip()
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
    is_default_repo = False
    repo_dir = None

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

    keep_workspace = str(os.getenv("HOLON_KEEP_WORKSPACE", "")).lower() in ("1", "true", "yes")
    repo_dir = os.getenv("HOLON_REPO_DIR")
    is_default_repo = False
    if not repo_dir:
        in_sandbox = bool(
            os.getenv("HOLON_ROLE")
            or os.path.exists("/.dockerenv")
            or os.getenv("USER") == "holon"
            or os.getenv("USERNAME") == "holon"
        )
        repo_dir = os.path.expanduser("~/repo") if in_sandbox else os.path.expanduser("~/.holon/repo")
        is_default_repo = True
        if not keep_workspace:
            _cleanup_repo_dir(repo_dir, raise_on_error=True)
    os.makedirs(repo_dir, exist_ok=True)
    try:
        repo_url = get_repo_url()
        run_cmd(
            ["git", "clone", "--branch", plan_branch, "--single-branch", "--depth", "1", repo_url, "."],
            cwd=repo_dir,
        )

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
                            plan_branch_prefix.split("/")[-1] == plan_id or plan_branch_prefix.endswith("/" + plan_id)
                        ):
                            plan_data = data
                            break
                    except Exception as e:
                        print(f"Warning: skipping line {line_no} in plans.jsonl: {e}", file=sys.stderr)

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
                        if isinstance(branch, str) and (target_intent_branch.rstrip("/_") == branch.rstrip("/_")):
                            intent_data = data
                            break
                    except Exception as e:
                        # Ignore invalid or corrupted lines in intents ledger
                        print(f"Warning: skipping unparseable line in intents.jsonl: {e}", file=sys.stderr)

        if not intent_data:
            intent_data = {"branch": plan_data.get("intent_branch", "I-unknown")}

        timestamp_str = datetime.now(UTC).isoformat()
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
            prompt_file = os.path.join(tempfile.gettempdir(), f"exec_prompt-{exec_seq}.md")
            intent_file = os.path.join(tempfile.gettempdir(), f"exec_intent-{exec_seq}.json")
            full_prompt = (
                f"Execute plan {plan_branch}.\n\n"
                f"Plan content:\n{plan_content}\n\n"
                f"Intent data:\n{json.dumps(intent_data, indent=2)}"
            )

            try:
                with open(prompt_file, "w") as f:
                    f.write(full_prompt)
                with open(intent_file, "w") as f:
                    json.dump(intent_data, f)

                agent_cmd = runner.build_cmd(model_name, prompt_file, intent_file, full_prompt)
                res = run_cmd(agent_cmd, cwd=repo_dir, check=False)
                if res.returncode == 0:
                    exec_status = "success"
                    summary = "Plan executed successfully"
                else:
                    exec_status = "failure"
                    summary = f"Plan execution failed with exit code {res.returncode}"
            finally:
                for tf in (prompt_file, intent_file):
                    if os.path.exists(tf):
                        with contextlib.suppress(Exception):
                            os.remove(tf)

            exec_file_rel = f"executions/{exec_id}.md"
            exec_file_path = os.path.join(repo_dir, exec_file_rel)
            os.makedirs(os.path.dirname(exec_file_path), exist_ok=True)
            with open(exec_file_path, "w") as ef:
                ef.write(f"# Execution Record: {exec_id}\n\n")
                ef.write(f"- Plan Branch: `{plan_branch}`\n")
                ef.write(f"- Agent: `{agent_name}`\n")
                ef.write(f"- Model: `{model_name}`\n")
                ef.write(f"- Timestamp: `{timestamp_str}`\n\n")
                ef.write(f"## Status\n{exec_status.capitalize()}\n\n## Summary\n{summary}\n")

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
            if exec_status == "success":
                run_cmd(["git", "add", "-A"], cwd=repo_dir)

            # Log staged changes to provide visibility
            status_output = run_cmd(["git", "status", "--short"], cwd=repo_dir, check=False)
            print("Current git repository status:")
            print(redact_text(status_output.stdout))

        staged_check = run_cmd(["git", "diff", "--cached", "--quiet"], cwd=repo_dir, check=False)
        if staged_check.returncode != 0:
            run_cmd(["git", "config", "--local", "user.email", "executor-agent@holon-agentic-coder.com"], cwd=repo_dir)
            run_cmd(["git", "config", "--local", "user.name", "Holon Executor Agent"], cwd=repo_dir)
            run_cmd(["git", "commit", "-m", commit_msg], cwd=repo_dir)
            skip_push = os.getenv("HOLON_SKIP_PUSH")
            if not (skip_push and skip_push.lower() in ("1", "true", "yes")):
                run_cmd(["git", "push", "-u", "origin", exec_branch], cwd=repo_dir)
            else:
                print(f"Skipping git push for {exec_branch} (push disabled via environment variable).")
            print(f"Execution branch '{exec_branch}' successfully committed and pushed.")
        else:
            print("No staged changes to commit.")

    except Exception as e:
        print(f"Execution failed: {e}", file=sys.stderr)
        raise
    finally:
        keep_workspace = str(os.getenv("HOLON_KEEP_WORKSPACE", "")).lower() in ("1", "true", "yes")
        if is_default_repo and repo_dir and not keep_workspace:
            _cleanup_repo_dir(repo_dir, raise_on_error=False)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
