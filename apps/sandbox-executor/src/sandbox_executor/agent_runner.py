import logging
import os
import sys

logger = logging.getLogger(__name__)


class EnvMapping:
    """Defines a mapping from an environment variable to a command-line flag."""

    def __init__(self, env_var: str, flag: str, is_boolean: bool = False):
        self.env_var = env_var
        self.flag = flag
        self.is_boolean = is_boolean


class AgentRunner:
    """Base class for constructing and running agent CLI commands."""

    def __init__(self, agent_id: str, binary_name: str, model_flag: str):
        self.agent_id = agent_id
        self.binary_name = binary_name
        self.model_flag = model_flag

    def build_cmd(self, model_name: str, prompt_file: str, intent_file: str, full_prompt: str) -> list[str]:
        raise NotImplementedError


class StandardAgentRunner(AgentRunner):
    """Runner for agents that accept prompt strings directly via arguments."""

    def __init__(
        self,
        agent_id: str,
        binary_name: str,
        model_flag: str,
        prefix: list[str] | None = None,
        suffix: list[str] | None = None,
        env_mappings: list[EnvMapping] | None = None,
        required_keys: list[str] | None = None,
        custom_validator: str | None = None,
    ):
        super().__init__(agent_id, binary_name, model_flag)
        self.prefix = prefix or []
        self.suffix = suffix or []
        self.env_mappings = env_mappings or []
        self.required_keys = required_keys or []
        self.custom_validator = custom_validator

    def resolve_credentials(self) -> None:
        """Processes Tier 1 secret bundles to unpack configuration files."""
        # Ephemeral Secret Bundle Injection (HOLON_SECRET_BUNDLE_PATH or default /run/secrets/holon_auth.json)
        secret_bundle_path = os.getenv("HOLON_SECRET_BUNDLE_PATH", "/run/secrets/holon_auth.json")
        if os.path.exists(secret_bundle_path):
            try:
                import json

                with open(secret_bundle_path) as f:
                    bundle = json.load(f)
                target_agent = bundle.get("agent_id", "")
                if not target_agent or target_agent.lower() == self.agent_id:
                    api_key = bundle.get("api_key") or bundle.get("token")
                    if api_key:
                        os.environ["HOLON_AGENT_KEY"] = api_key

                    # Unpack session files into /home/holon/ if specified
                    config_files = bundle.get("config_files", {})
                    base_home = os.path.abspath(os.path.expanduser("~"))
                    if not base_home.endswith(os.sep):
                        base_home += os.sep
                    for rel_path, content in config_files.items():
                        full_dest = os.path.abspath(os.path.expanduser(rel_path))
                        if not full_dest.startswith(base_home):
                            raise ValueError(f"Path traversal detected in config_files path: {rel_path}")
                        os.makedirs(os.path.dirname(full_dest), exist_ok=True)
                        with open(full_dest, "w") as sf:
                            sf.write(content)
            except Exception as e:
                logger.warning(f"Failed to process secret bundle {secret_bundle_path}: {e}")

    def validate(self) -> None:
        """Validates that required environment variables or credentials exist across the 3-Tier Fallback Contract."""
        self.resolve_credentials()

        # Tier 2 & 3: Agent-specific environment variables and session directory fallbacks
        if self.custom_validator == "codex":
            if os.getenv("HOLON_AGENT_OSS_MODE") in ("true", "1"):
                return
            has_key = os.getenv("HOLON_AGENT_KEY")
            has_session = os.path.exists("/home/holon/.codex") or os.path.exists(os.path.expanduser("~/.codex"))
            if not (has_key or has_session):
                print(
                    "Error: Missing required credentials for agent 'codex'.\n"
                    "Please set 'HOLON_AGENT_KEY', set 'HOLON_AGENT_OSS_MODE=true', "
                    "or mount active credentials to '/home/holon/.codex'.",
                    file=sys.stderr,
                )
                sys.exit(1)
            return

        if self.custom_validator == "gemini":
            has_key = os.getenv("HOLON_AGENT_KEY")
            has_gcloud = os.path.exists("/home/holon/.config/gcloud") or os.path.exists(
                os.path.expanduser("~/.config/gcloud")
            )
            if not (has_key or has_gcloud):
                print(
                    "Error: Missing required API credentials for agent 'gemini'.\n"
                    "Please set 'HOLON_AGENT_KEY' or mount active gcloud credentials to '/home/holon/.config/gcloud'.",
                    file=sys.stderr,
                )
                sys.exit(1)
            return

        if self.custom_validator == "antigravity":
            has_key = os.getenv("HOLON_AGENT_KEY")
            has_session = (
                os.path.exists("/home/holon/.gemini/antigravity-cli")
                or os.path.exists(os.path.expanduser("~/.gemini/antigravity-cli"))
                or os.path.exists("/home/holon/.gemini")
                or os.path.exists(os.path.expanduser("~/.gemini"))
                or os.path.exists("/home/holon/.config/gcloud")
                or os.path.exists(os.path.expanduser("~/.config/gcloud"))
                or os.path.exists(os.path.expanduser("~/.holon/sessions/antigravity"))
                or os.path.exists("/run/user/1000/bus")
                or bool(os.getenv("DBUS_SESSION_BUS_ADDRESS"))
            )
            if not (has_key or has_session):
                print(
                    "Error: Missing required API credentials for agent 'antigravity'.\n"
                    "Please set 'HOLON_AGENT_KEY' or mount active session to '/home/holon/.gemini'.",
                    file=sys.stderr,
                )
                sys.exit(1)
            return

        if self.required_keys:
            session_dirs = {
                "claude": ["/home/holon/.config/claude", "~/.config/claude"],
                "pi": ["/home/holon/.config/pi", "~/.config/pi"],
            }
            has_session_dir = False
            if self.agent_id in session_dirs:
                has_session_dir = any(
                    os.path.exists(p) or os.path.exists(os.path.expanduser(p)) for p in session_dirs[self.agent_id]
                )

            has_key = any(os.getenv(k) for k in self.required_keys)

            if not (has_key or has_session_dir):
                print(
                    f"Error: Missing required API credentials for agent '{self.agent_id}'.\n"
                    "Please set 'HOLON_AGENT_KEY' or mount session credentials.",
                    file=sys.stderr,
                )
                sys.exit(1)

    def build_cmd(self, model_name: str, prompt_file: str, intent_file: str, full_prompt: str) -> list[str]:
        self.validate()
        cmd = [self.binary_name, *self.prefix, self.model_flag, model_name, *self.suffix]

        for mapping in self.env_mappings:
            val = os.getenv(mapping.env_var)
            if not val:
                continue
            if mapping.is_boolean:
                if val.lower() in ("true", "1", "yes", "on"):
                    cmd.append(mapping.flag)
            else:
                cmd.extend([mapping.flag, val])

        cmd.append(full_prompt)
        return cmd


class AntigravityAgentRunner(StandardAgentRunner):
    """Runner for the Antigravity agent.

    Defers evaluation of ``HOLON_AGENT_EFFORT`` and ``HOLON_AGENT_SKIP_PERMISSIONS``
    environment variables to :meth:`build_cmd` so that runtime changes to the variables
    are always respected instead of being frozen at module import time.
    """

    def build_cmd(self, model_name: str, prompt_file: str, intent_file: str, full_prompt: str) -> list[str]:
        # Resolve HOLON_AGENT_EFFORT and optional permissions bypass at call time
        prefix = list(self.prefix)
        suffix = list(self.suffix)
        if os.getenv("HOLON_AGENT_SKIP_PERMISSIONS", "true").lower() in ("1", "true", "yes", "on"):
            prefix.append("--dangerously-skip-permissions")
        suffix.extend(["--effort", os.getenv("HOLON_AGENT_EFFORT", "medium"), "-p"])

        self.validate()
        cmd = [self.binary_name, *prefix, self.model_flag, model_name, *suffix]

        for mapping in self.env_mappings:
            val = os.getenv(mapping.env_var)
            if not val:
                continue
            if mapping.is_boolean:
                if val.lower() in ("true", "1", "yes", "on"):
                    cmd.append(mapping.flag)
            else:
                cmd.extend([mapping.flag, val])

        cmd.append(full_prompt)
        return cmd


# Runner registry: maps agent_id -> StandardAgentRunner instance.
#
# Architectural assumption: one agent per sandbox container execution.
# HOLON_AGENT_PROVIDER is shared across runners that use it (pi-agent, open-codex),
# but since only a single agent is active per container, a single HOLON_AGENT_PROVIDER
# value is always unambiguous at runtime. If multi-agent orchestration is ever needed,
# per-agent provider overrides would need to be introduced.
runners = {
    "pi": StandardAgentRunner(
        "pi",
        "pi",
        "--model",
        prefix=["-p"],
        env_mappings=[
            # HOLON_AGENT_PROVIDER selects the backend provider (e.g. anthropic, openai).
            # Auth is handled by HOLON_AGENT_KEY, which _apply_generic_token maps to PI_API_KEY
            # internally so the pi CLI can authenticate via its native env var.
            EnvMapping("HOLON_AGENT_PROVIDER", "--provider"),
        ],
        required_keys=["HOLON_AGENT_KEY"],
    ),
    "open-codex": StandardAgentRunner(
        "open-codex",
        "open-codex",
        "-m",
        prefix=["-q"],
        env_mappings=[
            EnvMapping("HOLON_AGENT_PROVIDER", "--provider"),
        ],
        required_keys=["HOLON_AGENT_KEY"],
    ),
    "claude": StandardAgentRunner(
        "claude",
        "claude",
        "--model",
        suffix=["-p"],
        env_mappings=[
            EnvMapping("HOLON_AGENT_SETTINGS", "--settings"),
        ],
        required_keys=["HOLON_AGENT_KEY"],
    ),
    "gemini": StandardAgentRunner(
        "gemini",
        "gemini",
        "--model",
        suffix=["-p"],
        custom_validator="gemini",
    ),
    "opencode": StandardAgentRunner(
        "opencode",
        "opencode",
        "--model",
        prefix=["run"],
        env_mappings=[
            # HOLON_AGENT_MODE selects the opencode sub-agent (e.g. code, architect).
            EnvMapping("HOLON_AGENT_MODE", "--agent"),
        ],
        required_keys=["HOLON_AGENT_KEY"],
    ),
    "codex": StandardAgentRunner(
        "codex",
        "codex",
        "-m",
        prefix=["exec"],
        env_mappings=[
            # HOLON_AGENT_OSS_MODE=true enables offline/open-source mode (no API key required).
            EnvMapping("HOLON_AGENT_OSS_MODE", "--oss", is_boolean=True),
            EnvMapping("HOLON_AGENT_LOCAL_PROVIDER", "--local-provider"),
            EnvMapping("HOLON_AGENT_CONFIG", "-c"),
        ],
        custom_validator="codex",
    ),
    "antigravity": AntigravityAgentRunner(
        "antigravity",
        "agy",
        "--model",
        custom_validator="antigravity",
    ),
}


def get_runner(agent_name: str) -> AgentRunner:
    """Helper function to parse the agent name and return the appropriate AgentRunner instance."""
    agent_id = agent_name.lower().replace("-agent", "").replace("agent-", "")
    if agent_id not in runners:
        supported = ", ".join(sorted(runners.keys()))
        print(f"Error: Unsupported agent '{agent_name}'. Supported agents are: {supported}")
        sys.exit(1)
    return runners[agent_id]


def get_repo_url() -> str:
    """Helper to get the repository URL for git operations."""
    if os.getenv("HOLON_REPO_URL"):
        return os.environ["HOLON_REPO_URL"]

    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN") or os.getenv("HOLON_AGENT_KEY")
    if token and (token.startswith("gh") or token.startswith("github_pat_")):
        return f"https://x-access-token:{token}@github.com/Holon-Agentic-Coder/holon-agentic-coder-ref.git"

    return "git@github.com:Holon-Agentic-Coder/holon-agentic-coder-ref.git"
