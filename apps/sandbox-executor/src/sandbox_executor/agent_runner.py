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
        """Processes Tier 1 secret bundles / generic envvars and maps credentials into os.environ."""
        # 1. Ephemeral Secret Bundle Injection (HOLON_SECRET_BUNDLE_PATH or default /run/secrets/holon_auth.json)
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
                        self._apply_generic_token(api_key)

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

        # 2. Universal Env Contract (HOLON_AGENT_KEY)
        generic_token = os.getenv("HOLON_AGENT_KEY")
        if generic_token:
            self._apply_generic_token(generic_token)

    def _apply_generic_token(self, token: str) -> None:
        """Maps generic auth token to agent-specific environment variables in os.environ."""
        mapping = {
            "antigravity": ["AGY_USER_TOKEN", "GOOGLE_API_KEY"],
            "claude": ["ANTHROPIC_API_KEY"],
            "pi": ["PI_API_KEY"],
            "codex": ["OPENAI_API_KEY"],
            "open-codex": ["OPENAI_API_KEY"],
            "gemini": ["GEMINI_API_KEY"],
            "opencode": ["OPENCODE_API_KEY"],
        }
        target_envs = mapping.get(self.agent_id, [])
        for target_env in target_envs:
            if not os.getenv(target_env):
                os.environ[target_env] = token

    def validate(self) -> None:
        """Validates that required environment variables or credentials exist across the 3-Tier Fallback Contract."""
        self.resolve_credentials()

        # Tier 2 & 3: Agent-specific environment variables and session directory fallbacks
        if self.custom_validator == "codex":
            if os.getenv("CODEX_OSS") in ("true", "1"):
                return
            has_key = os.getenv("OPENAI_API_KEY")
            has_session = os.path.exists("/home/holon/.codex") or os.path.exists(os.path.expanduser("~/.codex"))
            if not (has_key or has_session):
                print(
                    "Error: Missing required credentials for agent 'codex'.\n"
                    "Please set 'OPENAI_API_KEY', set 'CODEX_OSS=true', "
                    "mount active credentials to '/home/holon/.codex', or set 'HOLON_AGENT_KEY'.",
                    file=sys.stderr,
                )
                sys.exit(1)
            return

        if self.custom_validator == "gemini":
            has_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
            has_gcloud = os.path.exists("/home/holon/.config/gcloud") or os.path.exists(
                os.path.expanduser("~/.config/gcloud")
            )
            if not (has_key or has_gcloud):
                print(
                    "Error: Missing required API credentials for agent 'gemini'.\n"
                    "Please set 'GEMINI_API_KEY' or mount active gcloud credentials to '/home/holon/.config/gcloud'.",
                    file=sys.stderr,
                )
                sys.exit(1)
            return

        if self.custom_validator == "antigravity":
            has_key = os.getenv("GOOGLE_API_KEY") or os.getenv("AGY_USER_TOKEN") or os.getenv("AGY_SESSION_TOKEN")
            has_session = (
                os.path.exists("/home/holon/.gemini/antigravity-cli")
                or os.path.exists(os.path.expanduser("~/.gemini/antigravity-cli"))
                or os.path.exists("/home/holon/.config/gcloud")
                or os.path.exists(os.path.expanduser("~/.config/gcloud"))
            )
            if not (has_key or has_session):
                print(
                    "Error: Missing required API credentials for agent 'antigravity'.\n"
                    "Please set 'AGY_USER_TOKEN', 'GOOGLE_API_KEY', "
                    "mount active session to '/home/holon/.gemini/antigravity-cli', or set 'HOLON_AGENT_KEY'.",
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

            if not (any(os.getenv(k) for k in self.required_keys) or has_session_dir):
                keys_str = ", ".join(self.required_keys)
                print(
                    f"Error: Missing required API credentials for agent '{self.agent_id}'.\n"
                    f"Please set at least one of the following environment variables: {keys_str}, "
                    "set 'HOLON_AGENT_KEY', or mount session credentials.",
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


runners = {
    "pi": StandardAgentRunner(
        "pi",
        "pi",
        "--model",
        prefix=["-p"],
        env_mappings=[
            EnvMapping("PI_PROVIDER", "--provider"),
            EnvMapping("PI_API_KEY", "--api-key"),
        ],
        required_keys=["PI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY"],
    ),
    "open-codex": StandardAgentRunner(
        "open-codex",
        "open-codex",
        "-m",
        prefix=["-q"],
        env_mappings=[
            EnvMapping("OPEN_CODEX_PROVIDER", "--provider"),
        ],
        required_keys=["OPENAI_API_KEY"],
    ),
    "claude": StandardAgentRunner(
        "claude",
        "claude",
        "--model",
        suffix=["-p"],
        env_mappings=[
            EnvMapping("CLAUDE_SETTINGS", "--settings"),
        ],
        required_keys=["ANTHROPIC_API_KEY", "CLAUDE_CODE_API_KEY"],
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
            EnvMapping("OPENCODE_AGENT", "--agent"),
        ],
        required_keys=["OPENCODE_API_KEY", "KIMI_API_KEY"],
    ),
    "codex": StandardAgentRunner(
        "codex",
        "codex",
        "-m",
        prefix=["exec"],
        env_mappings=[
            EnvMapping("CODEX_OSS", "--oss", is_boolean=True),
            EnvMapping("CODEX_LOCAL_PROVIDER", "--local-provider"),
            EnvMapping("CODEX_CONFIG", "-c"),
        ],
        custom_validator="codex",
    ),
    "antigravity": StandardAgentRunner(
        "antigravity",
        "agy",
        "--model",
        suffix=["-p"],
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
