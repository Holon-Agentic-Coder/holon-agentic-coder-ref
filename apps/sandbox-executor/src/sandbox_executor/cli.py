#!/usr/bin/env python3
"""Host wrapper CLI for running Holon Docker sandbox roles (intent, plan, execute)."""

import argparse
import logging
import os
import shutil
import socket
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from urllib.parse import urlparse

from sandbox_executor.token_reduction import generate_root_ca

logger = logging.getLogger(__name__)

# Directory the Root CA is mounted into inside the sandbox (picked up by update-ca-certificates
# in the entrypoint, and referenced by the *_CA_BUNDLE / SSL_CERT_FILE env vars).
CONTAINER_CA_DIR = "/usr/local/share/ca-certificates"
PROXY_LISTEN_PORT = 8080
PROXY_READY_TIMEOUT_SECONDS = 15.0
PROXY_ATTACH_TIMEOUT_SECONDS = 3.0
PROXY_POLL_INTERVAL_SECONDS = 0.5
PROXY_CONNECT_TIMEOUT_SECONDS = 0.5
_TRUTHY_ENV_VALUES = ("1", "true", "yes", "on")

_TOKEN_REDUCE_HELP = (
    "Cut agent token usage by routing sandbox egress through a locally-owned mitmproxy sidecar. "
    "Requires the 'docker' and 'openssl' host binaries and performs LOCAL TLS INTERCEPTION: a Holon "
    "Root CA is generated under ~/.holon/certs and trusted inside the sandbox (the private key never "
    "leaves the host)."
)


@dataclass
class _SidecarState:
    """Tracks the proxy resources created by THIS run so teardown never touches foreign ones."""

    container_name: str | None = None
    network_name: str | None = None
    network_created: bool = False


_sidecar_state = _SidecarState()


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
        except Exception as e:
            logger.debug("Failed to retrieve token via gh CLI: %s", e)
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


def _run_docker(*args: str) -> subprocess.CompletedProcess[str]:
    """Run a docker command without raising, capturing stdout/stderr for diagnostics."""
    return subprocess.run(["docker", *args], capture_output=True, text=True, check=False)


def _container_ca_path(ca_cert_path: str) -> str:
    """Map a host Root CA path onto its read-only in-container location."""
    return f"{CONTAINER_CA_DIR}/{os.path.basename(ca_cert_path)}"


def _ca_mount_args(ca_cert_path: str) -> list[str]:
    """Docker args mounting the host Root CA certificate read-only into the sandbox."""
    return ["-v", f"{ca_cert_path}:{_container_ca_path(ca_cert_path)}:ro"]


def _build_proxy_envs(ca_cert_path: str, proxy_url: str) -> dict[str, str]:
    """Env vars that route the sandbox through ``proxy_url`` and make it trust the Holon Root CA."""
    container_ca = _container_ca_path(ca_cert_path)
    return {
        "HTTP_PROXY": proxy_url,
        "HTTPS_PROXY": proxy_url,
        "NODE_EXTRA_CA_CERTS": container_ca,
        "REQUESTS_CA_BUNDLE": container_ca,
        "CURL_CA_BUNDLE": container_ca,
        "SSL_CERT_FILE": container_ca,
    }


def _proxy_gateway_url(port: int = PROXY_LISTEN_PORT) -> str:
    """URL of a proxy listening on the Docker host, correct for the current platform.

    ``172.17.0.1`` is the Linux bridge gateway only; Docker Desktop (macOS/Windows) does not route
    it, so ``host.docker.internal`` is used there instead.
    """
    if sys.platform in ("darwin", "win32"):
        return f"http://host.docker.internal:{port}"
    return f"http://172.17.0.1:{port}"


def _gateway_host_args() -> list[str]:
    """Docker args that make ``host.docker.internal`` resolvable on Linux."""
    if sys.platform in ("darwin", "win32"):
        return []
    return ["--add-host", "host.docker.internal:host-gateway"]


def _token_reduce_opt_in(token_reduce: bool) -> bool:
    """True only on explicit opt-in; host HTTP_PROXY/HTTPS_PROXY are never treated as opt-in."""
    if token_reduce:
        return True
    return os.getenv("HOLON_TOKEN_REDUCE", "").strip().lower() in _TRUTHY_ENV_VALUES


def _wait_for_proxy(host: str, port: int, timeout: float = PROXY_READY_TIMEOUT_SECONDS) -> bool:
    """Poll a TCP endpoint until it accepts a connection; return False if it never does."""
    deadline = time.monotonic() + timeout
    while True:
        try:
            with socket.create_connection((host, port), timeout=PROXY_CONNECT_TIMEOUT_SECONDS):
                return True
        except OSError:
            if time.monotonic() >= deadline:
                return False
            time.sleep(PROXY_POLL_INTERVAL_SECONDS)


def _proxy_host_port(proxy_url: str) -> tuple[str, int] | None:
    """Split a proxy URL into ``(host, port)``; None when it cannot be parsed."""
    parsed = urlparse(proxy_url if "//" in proxy_url else f"//{proxy_url}")
    if not parsed.hostname:
        return None
    return parsed.hostname, parsed.port or PROXY_LISTEN_PORT


def _ensure_network(network_name: str) -> bool:
    """Create a per-run bridge network; returns True when THIS run created it."""
    result = _run_docker("network", "create", network_name)
    stderr = (result.stderr or "").strip()
    if result.returncode == 0:
        return True
    logger.debug("docker network create %s exited %s: %s", network_name, result.returncode, stderr)
    if "already exists" in stderr.lower():
        return False
    raise RuntimeError(f"could not create Docker network '{network_name}': {stderr or 'unknown docker error'}")


def _published_loopback_port(container_name: str) -> int | None:
    """Read the host loopback port Docker published for the sidecar's proxy port."""
    result = _run_docker("port", container_name, f"{PROXY_LISTEN_PORT}/tcp")
    if result.returncode != 0:
        logger.debug("docker port %s exited %s: %s", container_name, result.returncode, (result.stderr or "").strip())
        return None
    for line in (result.stdout or "").splitlines():
        candidate = line.strip().rsplit(":", 1)[-1]
        if candidate.isdigit():
            return int(candidate)
    return None


def setup_token_reduction_proxy() -> tuple[list[str], dict[str, str]]:
    """Start this run's mitmproxy sidecar and return the sandbox mounts and env vars.

    Resources are named per run (pid + uuid suffix) and recorded in ``_sidecar_state`` so teardown
    only ever removes what this run created.

    Raises:
        FileNotFoundError: If the mitmproxy addon script is missing.
        RuntimeError: If Docker networking, the sidecar spawn, or the readiness probe fails.
    """
    run_suffix = f"{os.getpid()}-{uuid.uuid4().hex[:8]}"
    container_name = f"holon-proxy-{run_suffix}"
    network_name = f"holon-net-{run_suffix}"

    addon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "token_reduction", "mitm_addon.py")
    if not os.path.isfile(addon_path):
        raise FileNotFoundError(
            f"mitmproxy addon script not found at '{addon_path}'. Token reduction cannot start its proxy "
            "without it; re-run without --token-reduce to execute with direct egress."
        )

    ca_cert_path, _ = generate_root_ca()

    # Share ONLY a narrow proxy cache dir, read-only. Never mount ~/.holon: that subtree holds the
    # Root CA private key (~/.holon/certs) and the agent auth session stores (~/.holon/sessions).
    proxy_cache_dir = os.path.join(os.path.expanduser(os.path.join("~", ".holon")), "proxy-cache")
    os.makedirs(proxy_cache_dir, exist_ok=True)

    _sidecar_state.network_name = network_name
    _sidecar_state.network_created = _ensure_network(network_name)
    _sidecar_state.container_name = container_name

    docker_run_proxy = [
        "docker",
        "run",
        "-d",
        "--name",
        container_name,
        "--network",
        network_name,
        "--memory=256m",
        "--cpus=0.5",
        "--log-opt",
        "max-size=5m",
        "--log-opt",
        "max-file=2",
        "--restart=no",
        # Loopback-only publish so the host can run a real TCP readiness probe.
        "-p",
        f"127.0.0.1::{PROXY_LISTEN_PORT}",
        "-v",
        f"{proxy_cache_dir}:/home/mitmproxy/.holon/proxy-cache:ro",
        "-v",
        f"{addon_path}:/tmp/mitm_addon.py:ro",
        "mitmproxy/mitmproxy:12.2.3",
        "mitmdump",
        "-s",
        "/tmp/mitm_addon.py",
        "--listen-port",
        str(PROXY_LISTEN_PORT),
        "--set",
        "stream_large_bodies=1m",
    ]

    proxy_spawn = subprocess.run(docker_run_proxy, capture_output=True, text=True, check=False)
    if proxy_spawn.returncode != 0:
        stderr = (proxy_spawn.stderr or "").strip() or (proxy_spawn.stdout or "").strip()
        teardown_token_reduction_proxy()
        raise RuntimeError(
            f"mitmproxy sidecar '{container_name}' failed to start: {stderr or 'unknown docker error'}. "
            "Re-run without --token-reduce to execute with direct egress."
        )

    host_port = _published_loopback_port(container_name)
    if host_port is None:
        teardown_token_reduction_proxy()
        raise RuntimeError(
            f"mitmproxy sidecar '{container_name}' published no host loopback port, so its readiness cannot be "
            "verified. Re-run without --token-reduce to execute with direct egress."
        )
    if not _wait_for_proxy("127.0.0.1", host_port):
        teardown_token_reduction_proxy()
        raise RuntimeError(
            f"mitmproxy sidecar '{container_name}' never accepted connections on 127.0.0.1:{host_port} within "
            f"{PROXY_READY_TIMEOUT_SECONDS}s (the addon likely crashed on startup). "
            "Re-run without --token-reduce to execute with direct egress."
        )

    mounts = ["--network", network_name, *_gateway_host_args(), *_ca_mount_args(ca_cert_path)]
    return mounts, _build_proxy_envs(ca_cert_path, f"http://{container_name}:{PROXY_LISTEN_PORT}")


def teardown_token_reduction_proxy() -> None:
    """Remove only the sidecar container and network THIS run created (no-op otherwise)."""
    if _sidecar_state.container_name:
        result = _run_docker("rm", "-f", _sidecar_state.container_name)
        if result.returncode != 0:
            logger.debug(
                "docker rm -f %s exited %s: %s",
                _sidecar_state.container_name,
                result.returncode,
                (result.stderr or "").strip(),
            )
        _sidecar_state.container_name = None

    if _sidecar_state.network_created and _sidecar_state.network_name:
        result = _run_docker("network", "rm", _sidecar_state.network_name)
        if result.returncode != 0:
            logger.debug(
                "docker network rm %s exited %s: %s",
                _sidecar_state.network_name,
                result.returncode,
                (result.stderr or "").strip(),
            )

    _sidecar_state.network_name = None
    _sidecar_state.network_created = False


def _attach_external_proxy() -> tuple[list[str], dict[str, str]]:
    """Attach the sandbox to an already-running proxy (``HOLON_PROXY_URL`` or host gateway).

    Used for the ``HOLON_TOKEN_REDUCE`` opt-in path: the proxy is owned by the user, so this run
    neither starts nor tears it down. An unreachable proxy degrades to direct egress.
    """
    proxy_url = os.getenv("HOLON_PROXY_URL") or _proxy_gateway_url()
    host_port = _proxy_host_port(proxy_url)
    if host_port is None:
        logger.error(
            "HOLON_TOKEN_REDUCE is enabled but HOLON_PROXY_URL='%s' is not a valid proxy URL. "
            "This run continues with DIRECT egress (no token reduction).",
            proxy_url,
        )
        return [], {}

    ca_cert_path, _ = generate_root_ca()
    if not _wait_for_proxy(host_port[0], host_port[1], timeout=PROXY_ATTACH_TIMEOUT_SECONDS):
        logger.error(
            "HOLON_TOKEN_REDUCE is enabled but no proxy accepted a TCP connection at %s:%s. Start the proxy or "
            "point HOLON_PROXY_URL at it; this run continues with DIRECT egress (no token reduction).",
            host_port[0],
            host_port[1],
        )
        return [], {}

    return [*_gateway_host_args(), *_ca_mount_args(ca_cert_path)], _build_proxy_envs(ca_cert_path, proxy_url)


def get_token_reduction_mounts_and_envs(
    token_reduce: bool = False,
) -> tuple[list[str], dict[str, str]]:
    """Build token-reduction mounts/env vars for an explicitly opted-in run.

    Opt-in is strictly ``--token-reduce`` or ``HOLON_TOKEN_REDUCE`` in ``("1", "true", "yes",
    "on")``. Host ``HTTP_PROXY``/``HTTPS_PROXY`` alone never change sandbox networking. Any failure
    degrades to direct egress (empty mounts/envs) with an actionable error log.
    """
    if not _token_reduce_opt_in(token_reduce):
        return [], {}

    try:
        if token_reduce:
            return setup_token_reduction_proxy()
        return _attach_external_proxy()
    except (FileNotFoundError, RuntimeError, OSError) as exc:
        logger.error(
            "Token reduction is enabled but could not be configured (%s: %s). This run continues with DIRECT "
            "egress (no TLS interception, no token reduction).",
            type(exc).__name__,
            exc,
        )
        return [], {}


def run_docker_container(
    role: str,
    image_name: str,
    container_args: list[str],
    agent_id: str = "antigravity",
    intent_file: str | None = None,
    token_reduce: bool = False,
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

    # Token Reduction Proxy & CA Mounts
    tr_mounts, tr_envs = get_token_reduction_mounts_and_envs(token_reduce=token_reduce)
    docker_cmd.extend(tr_mounts)
    for k, v in tr_envs.items():
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
    try:
        result = subprocess.run(docker_cmd)
        return result.returncode
    finally:
        teardown_token_reduction_proxy()


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
    plan_parser.add_argument(
        "--token-reduce",
        action="store_true",
        help=_TOKEN_REDUCE_HELP,
    )

    # Subcommand: execute
    exec_parser = subparsers.add_parser("execute", help="Run Sandbox Executor to execute code changes for a plan.")
    exec_parser.add_argument("plan_branch", help="Target plan branch name")
    exec_parser.add_argument("--agent", default="antigravity-agent", help="Agent runner to execute")
    exec_parser.add_argument("--model", default="gemini-3.5-flash", help="Model name to pass to agent")
    exec_parser.add_argument(
        "--token-reduce",
        action="store_true",
        help=_TOKEN_REDUCE_HELP,
    )

    args = parser.parse_args()

    agent_id = args.agent.replace("-agent", "").replace("agent-", "") if hasattr(args, "agent") else "antigravity"
    agent_image_mapping = {
        "antigravity": "holon/agent-antigravity",
        "claude": "holon/agent-claude",
        "pi": "holon/agent-pi",
        "codex": "holon/agent-codex",
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
        sys.exit(
            run_docker_container(
                "planner",
                image_name,
                container_args,
                agent_id=agent_id,
                token_reduce=args.token_reduce,
            )
        )

    elif args.command == "execute":
        image_name = agent_image_mapping.get(agent_id, f"holon/agent-{agent_id}")
        container_args = [args.plan_branch, args.agent, args.model]
        sys.exit(
            run_docker_container(
                "executor",
                image_name,
                container_args,
                agent_id=agent_id,
                token_reduce=args.token_reduce,
            )
        )


if __name__ == "__main__":
    main()
