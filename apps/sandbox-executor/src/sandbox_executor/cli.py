#!/usr/bin/env python3
"""Host wrapper CLI for running Holon Docker sandbox roles (intent, plan, execute)."""

import argparse
import os
import shutil
import subprocess
import sys


def find_github_token() -> str | None:
    """Auto-detect GitHub token from environment variables or gh CLI."""
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if token:
        return token
    if shutil.which("gh"):
        try:
            res = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True)
            if res.returncode == 0 and res.stdout.strip():
                return res.stdout.strip()
        except Exception:
            # gh CLI not logged in or failed to retrieve token
            pass
    return None


def get_ssh_auth_mounts() -> tuple[list[str], dict[str, str]]:
    """Determine SSH agent socket volume mounts and env vars based on OS."""
    mounts = []
    env_vars = {}

    if sys.platform == "darwin":
        # macOS Docker Desktop magic socket path
        mounts.extend(["-v", "/run/host-services/ssh-auth.sock:/run/host-services/ssh-auth.sock"])
        env_vars["SSH_AUTH_SOCK"] = "/run/host-services/ssh-auth.sock"
    else:
        ssh_sock = os.getenv("SSH_AUTH_SOCK")
        if ssh_sock and os.path.exists(ssh_sock):
            mounts.extend(["-v", f"{ssh_sock}:/run/ssh-agent"])
            env_vars["SSH_AUTH_SOCK"] = "/run/ssh-agent"

    return mounts, env_vars


def get_agent_session_mounts(agent_id: str) -> list[str]:
    """Auto-detect and construct read-only session mounts for supported agents."""
    mounts = []
    home = os.path.expanduser("~")

    session_mapping = {
        "antigravity": [
            (os.path.join(home, ".gemini/antigravity-cli"), "/home/holon/.gemini/antigravity-cli"),
            (os.path.join(home, ".config/antigravity"), "/home/holon/.config/antigravity"),
        ],
        "claude": [
            (os.path.join(home, ".config/claude"), "/home/holon/.config/claude"),
        ],
        "codex": [
            (os.path.join(home, ".codex"), "/home/holon/.codex"),
        ],
        "pi": [
            (os.path.join(home, ".config/pi"), "/home/holon/.config/pi"),
        ],
        "gemini": [
            (os.path.join(home, ".config/gcloud"), "/home/holon/.config/gcloud"),
        ],
    }

    dirs = session_mapping.get(agent_id.lower(), [])
    for host_path, container_path in dirs:
        if os.path.exists(host_path):
            mounts.extend(["-v", f"{host_path}:{container_path}:ro"])

    return mounts


def run_docker_container(
    role: str,
    image_name: str,
    container_args: list[str],
    agent_id: str = "antigravity",
    intent_file: str | None = None,
) -> int:
    """Constructs docker run command with auto-discovered credentials and executes it."""
    if not shutil.which("docker"):
        print("Error: 'docker' CLI command not found. Please install Docker.", file=sys.stderr)
        return 1

    tty_flag = ["-it"] if sys.stdin.isatty() else ["-i"]
    docker_cmd = ["docker", "run", "--rm", *tty_flag]

    # Set Role
    docker_cmd.extend(["-e", f"HOLON_ROLE={role}"])

    # Auto-detect GitHub Token
    gh_token = find_github_token()
    if gh_token:
        docker_cmd.extend(["-e", f"GITHUB_TOKEN={gh_token}"])

    # Auto-detect HOLON_AGENT_KEY
    agent_key = (
        os.getenv("HOLON_AGENT_KEY")
        or os.getenv("GOOGLE_API_KEY")
        or os.getenv("ANTHROPIC_API_KEY")
        or os.getenv("OPENAI_API_KEY")
    )
    if agent_key:
        docker_cmd.extend(["-e", f"HOLON_AGENT_KEY={agent_key}"])

    # SSH Agent Socket Mounts
    ssh_mounts, ssh_envs = get_ssh_auth_mounts()
    docker_cmd.extend(ssh_mounts)
    for k, v in ssh_envs.items():
        docker_cmd.extend(["-e", f"{k}={v}"])

    # Intent file mount for intent-creator role
    if role == "intent-creator" and intent_file:
        abs_intent = os.path.abspath(intent_file)
        if not os.path.exists(abs_intent):
            print(f"Error: Intent file '{intent_file}' does not exist.", file=sys.stderr)
            return 1
        docker_cmd.extend(["-v", f"{abs_intent}:/tmp/intent.json"])

    # Auto-detect Session Mounts
    session_mounts = get_agent_session_mounts(agent_id)
    docker_cmd.extend(session_mounts)

    # Image and args
    docker_cmd.append(image_name)
    docker_cmd.extend(container_args)

    sensitive_keys = [
        "GITHUB_TOKEN",
        "HOLON_AGENT_KEY",
        "GOOGLE_API_KEY",
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
    ]
    sanitized_cmd = []
    for item in docker_cmd:
        if any(item.startswith(f"{key}=") for key in sensitive_keys):
            k, _ = item.split("=", 1)
            sanitized_cmd.append(f"{k}=***REDACTED***")
        else:
            sanitized_cmd.append(item)
    print(f"Executing: {' '.join(sanitized_cmd)}")
    result = subprocess.run(docker_cmd)
    return result.returncode


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="holon",
        description="Holon CLI: Host wrapper for running containerized Holon AI agent roles.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcommand: intent
    intent_parser = subparsers.add_parser("intent", help="Run Intent Creator to initialize a new intent branch.")
    intent_parser.add_argument("intent_file", help="Path to local intent JSON/YAML file (e.g. intents/my-task.json)")

    # Subcommand: plan
    plan_parser = subparsers.add_parser("plan", help="Run Plan Generator to create a detailed markdown plan branch.")
    plan_parser.add_argument("intent_branch", help="Target intent branch name (e.g. I-1784983150-build-execution/_)")
    plan_parser.add_argument(
        "--agent",
        default="antigravity-agent",
        help="Agent runner to execute (e.g. antigravity-agent, pi-agent, claude-agent, codex-agent)",
    )
    plan_parser.add_argument(
        "--model",
        default="gemini-3.5-flash",
        help="Model name to pass to agent (e.g. gemini-3.5-flash, claude-3-5-sonnet)",
    )

    # Subcommand: execute
    exec_parser = subparsers.add_parser("execute", help="Run Sandbox Executor to execute code changes for a plan.")
    exec_parser.add_argument("plan_branch", help="Target plan branch name")
    exec_parser.add_argument("--agent", default="antigravity-agent", help="Agent runner to execute")
    exec_parser.add_argument("--model", default="gemini-3.5-flash", help="Model name to pass to agent")

    args = parser.parse_args()

    agent_id = args.agent.replace("-agent", "").replace("agent-", "") if hasattr(args, "agent") else "antigravity"
    agent_image_mapping = {
        "antigravity": "holon/agent-antigravity",
        "claude": "holon/agent-claude",
        "pi": "holon/agent-pi",
        "codex": "holon/agent-codex",
        "open-codex": "holon/agent-open-codex",
        "gemini": "holon/agent-gemini",
        "opencode": "holon/agent-opencode",
    }

    if args.command == "intent":
        image_name = "holon/orchestrator"
        sys.exit(
            run_docker_container("intent-creator", image_name, [], agent_id="antigravity", intent_file=args.intent_file)
        )

    elif args.command == "plan":
        image_name = agent_image_mapping.get(agent_id, f"holon/agent-{agent_id}")
        container_args = [args.intent_branch, args.agent, args.model]
        sys.exit(run_docker_container("planner", image_name, container_args, agent_id=agent_id))

    elif args.command == "execute":
        image_name = agent_image_mapping.get(agent_id, f"holon/agent-{agent_id}")
        container_args = [args.plan_branch, args.agent, args.model]
        sys.exit(run_docker_container("executor", image_name, container_args, agent_id=agent_id))


if __name__ == "__main__":
    main()
