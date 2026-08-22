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
    """Auto-detect and construct session mounts for supported agents."""
    mounts = []
    home = os.path.expanduser("~")

    # Handle Antigravity specific mounts
    if agent_id.lower() in ("antigravity", "antigravity-agent"):
        dedicated_session = os.getenv(
            "HOLON_ANTIGRAVITY_SESSION_DIR",
            os.path.join(home, ".holon", "sessions", "antigravity"),
        )

        # If HOLON_AGENT_KEY is supplied, session mount is optional
        has_key = bool(os.getenv("HOLON_AGENT_KEY"))

        # On macOS, ~/.holon/sessions/antigravity is required if not using HOLON_AGENT_KEY
        if sys.platform == "darwin":
            if os.path.exists(dedicated_session):
                mounts.extend(["-v", f"{dedicated_session}:/home/holon/.gemini/antigravity-cli:rw"])
                mounts.extend(["--tmpfs", "/home/holon/.gemini/config:uid=1000,gid=1000"])
                return mounts
            elif not has_key:
                print(
                    "Error: Missing Antigravity sandbox session directory on macOS.\n"
                    f"The session directory '{dedicated_session}' does not exist.\n\n"
                    "Please initialize the Antigravity session in an interactive TTY by running:\n\n"
                    f"  mkdir -p {dedicated_session}\n"
                    "  docker run -it "
                    f"-v {dedicated_session}:/home/holon/.gemini/antigravity-cli:rw holon/agent-antigravity agy\n\n"
                    "After completing interactive authentication, rerun this command.",
                    file=sys.stderr,
                )
                sys.exit(1)

        # On Linux and other platforms, mount ~/.holon/sessions/antigravity or host ~/.gemini/antigravity-cli
        if os.path.exists(dedicated_session):
            mounts.extend(["-v", f"{dedicated_session}:/home/holon/.gemini/antigravity-cli:rw"])
            mounts.extend(["--tmpfs", "/home/holon/.gemini/config:uid=1000,gid=1000"])
            return mounts

        host_agy_cli = os.path.join(home, ".gemini", "antigravity-cli")
        if os.path.exists(host_agy_cli):
            mounts.extend(["-v", f"{host_agy_cli}:/home/holon/.gemini/antigravity-cli:rw"])

        # Linux Host D-Bus session socket mount if present
        if sys.platform.startswith("linux"):
            uid = os.getuid() if hasattr(os, "getuid") else 1000
            dbus_socket = f"/run/user/{uid}/bus"
            if os.path.exists(dbus_socket):
                mounts.extend(["-v", f"{dbus_socket}:/run/user/1000/bus"])

        return mounts

    session_mapping = {
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

    # Forward all host environment variables prefixed with HOLON_AGENT_ and GITHUB_TOKEN
    env_to_forward = {}
    gh_token = find_github_token()
    if gh_token:
        env_to_forward["GITHUB_TOKEN"] = gh_token

    for key, value in os.environ.items():
        if key.startswith("HOLON_AGENT_") or key == "GITHUB_TOKEN":
            env_to_forward[key] = value

    for key, value in sorted(env_to_forward.items()):
        docker_cmd.extend(["-e", f"{key}={value}"])

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
