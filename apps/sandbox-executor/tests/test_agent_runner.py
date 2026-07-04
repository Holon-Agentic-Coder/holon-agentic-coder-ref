import subprocess
import unittest

import pytest
from sandbox_executor.agent_runner import get_runner, runners


class TestAgentRunner(unittest.TestCase):
    def test_runner_mappings(self):
        """Test that get_runner correctly maps agent names and validates support."""
        supported_agents = ["pi", "pi-agent", "gemini-agent", "claude-agent", "antigravity-agent"]
        for agent in supported_agents:
            runner = get_runner(agent)
            self.assertIsNotNone(runner)

        with self.assertRaises(SystemExit):
            get_runner("unsupported-agent-name")

    def test_standard_runner_cmd(self):
        """Test command construction for all agents in the registry."""
        import os
        from unittest.mock import patch

        expected_commands = {
            "pi": ["pi", "-p", "--model", "gemini-2.0-flash", "compiled prompt text"],
            "open-codex": ["open-codex", "-q", "-m", "gemini-2.0-flash", "compiled prompt text"],
            "claude": ["claude", "--model", "gemini-2.0-flash", "-p", "compiled prompt text"],
            "gemini": ["gemini", "--model", "gemini-2.0-flash", "-p", "compiled prompt text"],
            "opencode": ["opencode", "run", "--model", "gemini-2.0-flash", "compiled prompt text"],
            "codex": ["codex", "exec", "-m", "gemini-2.0-flash", "compiled prompt text"],
            "antigravity": ["agy", "--model", "gemini-2.0-flash", "-p", "compiled prompt text"],
        }
        dummy_env = {
            "OPENAI_API_KEY": "dummy",
            "ANTHROPIC_API_KEY": "dummy",
            "GEMINI_API_KEY": "dummy",
            "OPENCODE_API_KEY": "dummy",
            "GOOGLE_API_KEY": "dummy",
        }
        with patch.dict(os.environ, dummy_env):
            for agent_name, expected_cmd in expected_commands.items():
                with self.subTest(agent=agent_name):
                    runner = get_runner(agent_name)
                    cmd = runner.build_cmd(
                        model_name="gemini-2.0-flash",
                        prompt_file="/tmp/prompt.md",
                        intent_file="/tmp/intent.json",
                        full_prompt="compiled prompt text",
                    )
                    self.assertEqual(cmd, expected_cmd)

    def test_runner_validation_failures(self):
        """Test that validation fails with SystemExit when credentials are missing."""
        import os
        from unittest.mock import patch

        with patch.dict(os.environ, {}, clear=True):
            for agent_name in runners:
                with self.subTest(agent=agent_name):
                    runner = get_runner(agent_name)
                    with self.assertRaises(SystemExit):
                        runner.build_cmd("model", "/tmp/p", "/tmp/i", "prompt")

    def test_runner_env_vars(self):
        """Test that runners correctly append configurations derived from environment variables."""
        import os
        from unittest.mock import patch

        # 1. Claude settings
        with patch.dict(os.environ, {"CLAUDE_SETTINGS": "/path/to/settings.json", "ANTHROPIC_API_KEY": "dummy"}):
            runner = get_runner("claude")
            cmd = runner.build_cmd("claude-3", "/tmp/p", "/tmp/i", "prompt")
            self.assertIn("--settings", cmd)
            self.assertIn("/path/to/settings.json", cmd)

        # 2. Codex OSS and local provider configurations
        env = {
            "CODEX_OSS": "true",
            "CODEX_LOCAL_PROVIDER": "ollama",
            "CODEX_CONFIG": "temperature=0.2",
        }
        with patch.dict(os.environ, env):
            runner = get_runner("codex")
            cmd = runner.build_cmd("codex-m", "/tmp/p", "/tmp/i", "prompt")
            self.assertIn("--oss", cmd)
            self.assertIn("--local-provider", cmd)
            self.assertIn("ollama", cmd)
            self.assertIn("-c", cmd)
            self.assertIn("temperature=0.2", cmd)

        # 3. Open Codex provider
        with patch.dict(os.environ, {"OPEN_CODEX_PROVIDER": "custom-ollama", "OPENAI_API_KEY": "dummy"}):
            runner = get_runner("open-codex")
            cmd = runner.build_cmd("m", "/tmp/p", "/tmp/i", "prompt")
            self.assertIn("--provider", cmd)
            self.assertIn("custom-ollama", cmd)

        # 4. Pi provider and api-key
        env = {
            "PI_PROVIDER": "anthropic",
            "PI_API_KEY": "sk-ant-123",
        }
        with patch.dict(os.environ, env):
            runner = get_runner("pi-agent")
            cmd = runner.build_cmd("claude-3", "/tmp/p", "/tmp/i", "prompt")
            self.assertIn("--provider", cmd)
            self.assertIn("anthropic", cmd)
            self.assertIn("--api-key", cmd)
            self.assertIn("sk-ant-123", cmd)

    @pytest.mark.integration_test
    def test_real_images_have_binaries(self):
        """Integration test to verify that the configured agent runner binaries

        actually exist and are runnable inside the corresponding real Docker images.
        """
        agent_image_mapping = {
            "pi": "holon/agent-pi",
            "open-codex": "holon/agent-open-codex",
            "claude": "holon/agent-claude",
            "gemini": "holon/agent-gemini",
            "opencode": "holon/agent-opencode",
            "codex": "holon/agent-codex",
            "antigravity": "holon/agent-antigravity",
        }

        for agent_id, runner in runners.items():
            with self.subTest(agent=agent_id):
                image_name = agent_image_mapping.get(agent_id)
                self.assertIsNotNone(image_name, f"Missing image mapping for agent: {agent_id}")

                # Run 'docker run --rm <image> <binary> --help'
                cmd = ["docker", "run", "--rm", image_name, runner.binary_name, "--help"]
                try:
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
                    # Verify command was found (127 means command not found)
                    self.assertNotEqual(
                        result.returncode,
                        127,
                        f"Binary '{runner.binary_name}' not found (exited 127) inside image '{image_name}'.\n"
                        f"Stderr:\n{result.stderr}",
                    )
                except subprocess.TimeoutExpired:
                    # Timeout is fine since it means the binary started up and block-waited
                    pass
                except Exception as e:
                    self.fail(f"Failed to run container for agent {agent_id}: {e}")
