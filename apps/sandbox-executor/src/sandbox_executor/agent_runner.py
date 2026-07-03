import os
import sys


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

    def validate(self) -> None:
        """Validates that the required environment variables or credentials exist."""
        if self.custom_validator == "codex":
            if os.getenv("CODEX_OSS") in ("true", "1"):
                return
            if not os.getenv("OPENAI_API_KEY"):
                print(
                    "Error: Missing required environment variable 'OPENAI_API_KEY' for agent 'codex'.\n"
                    "Please set 'OPENAI_API_KEY' or set 'CODEX_OSS=true' to use a local/OSS inference provider.",
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
            has_key = os.getenv("GOOGLE_API_KEY")
            has_gcloud = os.path.exists("/home/holon/.config/gcloud") or os.path.exists(
                os.path.expanduser("~/.config/gcloud")
            )
            if not (has_key or has_gcloud):
                print(
                    "Error: Missing required API credentials for agent 'antigravity'.\n"
                    "Please set 'GOOGLE_API_KEY' or mount active gcloud credentials to '/home/holon/.config/gcloud'.",
                    file=sys.stderr,
                )
                sys.exit(1)
            return

        if self.required_keys and not any(os.getenv(k) for k in self.required_keys):
            keys_str = ", ".join(self.required_keys)
            print(
                f"Error: Missing required API credentials for agent '{self.agent_id}'.\n"
                f"Please set at least one of the following environment variables: {keys_str}",
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
    "hermes": StandardAgentRunner(
        "hermes",
        "hermes",
        "-m",
        suffix=["-z"],
        env_mappings=[
            EnvMapping("HERMES_PROVIDER", "--provider"),
        ],
        required_keys=["OPENAI_API_KEY", "OPENROUTER_API_KEY", "HERMES_API_KEY", "TOGETHER_API_KEY"],
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
